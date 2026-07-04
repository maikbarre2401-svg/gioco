#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🎭 DEEPFAKE ULTRA PRO 5.0  ⚡  (real-time face swap)

Versione ottimizzata: più veloce e più realistica.

Miglioramenti rispetto alla 4.1
--------------------------------
VELOCITÀ
  * Auto-selezione del provider ONNX (CUDA / CoreML / DirectML / CPU):
    usa la GPU quando è disponibile invece del solo CPUExecutionProvider.
  * Detector "detection-only" per il flusso live: salta i modelli di
    recognition/landmark/genderage che il face-swap non usa.
  * Un solo thread di inferenza (niente più lock contesi tra N thread che
    di fatto serializzavano tutto) + una coda "ultimo frame".
  * Session ONNX con ottimizzazione del grafo attiva e thread intra-op.
  * Cache di rilevamento corretta (la vecchia usava id(frame): non colpiva
    mai e poteva restituire dati obsoleti). Ora si può saltare il detect
    ogni N frame in modalità FAST riusando l'ultimo risultato.

REALISMO
  * Blending ellittico con bordi sfumati (feather) al posto del quadrato.
  * Color transfer LAB: la faccia sostituita adotta luminosità/tinta della
    scena, così l'illuminazione combacia.
  * Selezione della faccia sorgente in base alla dimensione (il soggetto),
    non solo allo score.

Uso etico: usa solo volti per cui hai il consenso. Non creare contenuti
ingannevoli o che ledano le persone.

Requisiti: vedi requirements.txt
Modello:  inswapper_128.onnx  (deepinsight/insightface releases)
"""

import warnings
warnings.filterwarnings('ignore')

import os
os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '3')
os.environ.setdefault('KMP_DUPLICATE_LIB_OK', 'TRUE')
os.environ.setdefault('OMP_NUM_THREADS', str(max(1, (os.cpu_count() or 4))))

import sys
import time
import queue
import threading
from datetime import datetime

import numpy as np
import cv2

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk

try:
    import psutil
    _HAS_PSUTIL = True
except Exception:
    _HAS_PSUTIL = False


# ============================================================
# 🔥 CONFIG
# ============================================================
config = {
    'model_path': 'inswapper_128.onnx',
    'detector_name': 'buffalo_l',
    'camera_id': 0,
    'swap_threshold': 0.35,     # score minimo per applicare lo swap
    'det_size': 320,            # input rete di detection (256=veloce, 512=preciso)
    'det_thresh': 0.5,
    'realistic_blend': True,    # feather + color-match
    'fast_detect_stride': 2,    # in modalità FAST: rileva 1 frame su N
    'display_hz': 60,           # frequenza di refresh della UI
}


def _cpu_count():
    try:
        return psutil.cpu_count() if _HAS_PSUTIL else (os.cpu_count() or 4)
    except Exception:
        return os.cpu_count() or 4


def _sys_banner():
    print("=" * 80)
    print("⚡ DEEPFAKE ULTRA PRO 5.0")
    print("=" * 80)
    ram = f"{psutil.virtual_memory().percent}%" if _HAS_PSUTIL else "n/a"
    print(f"🔥 PID: {os.getpid()} | CPU cores: {_cpu_count()} | RAM: {ram}")
    print("=" * 80)


# ============================================================
# 🧠 FACE ENGINE  (detection + swap + blending)
# ============================================================
class FaceEngine:
    """Carica i modelli e fornisce rilevamento e face-swap ottimizzati."""

    def __init__(self, model_path):
        self.model_path = model_path
        self.detector = None      # detection-only (flusso live, veloce)
        self.app = None           # completo (embedding della faccia sorgente)
        self.swapper = None       # inswapper_128
        self.loaded = False

        self.providers = []
        self.provider_name = 'CPU'
        self.ctx_id = -1

        self._lock = threading.Lock()
        self._last_faces = []
        self._frame_idx = 0

    # ---- provider selection -------------------------------------------------
    def _select_providers(self):
        try:
            import onnxruntime as ort
            avail = ort.get_available_providers()
        except Exception:
            avail = ['CPUExecutionProvider']

        preferred = [
            'CUDAExecutionProvider',
            'CoreMLExecutionProvider',
            'DmlExecutionProvider',
            'CPUExecutionProvider',
        ]
        self.providers = [p for p in preferred if p in avail] or ['CPUExecutionProvider']
        top = self.providers[0]
        self.provider_name = {
            'CUDAExecutionProvider': 'CUDA (GPU)',
            'CoreMLExecutionProvider': 'CoreML (Apple)',
            'DmlExecutionProvider': 'DirectML (GPU)',
            'CPUExecutionProvider': 'CPU',
        }.get(top, top)
        self.ctx_id = 0 if top == 'CUDAExecutionProvider' else -1
        return self.providers

    # ---- load ---------------------------------------------------------------
    def load(self):
        try:
            import insightface
            from insightface.app import FaceAnalysis
        except Exception as e:
            print(f"❌ insightface non disponibile: {e}")
            return False

        self._select_providers()
        print(f"⚡ Execution provider: {self.provider_name}")

        det_size = (config['det_size'], config['det_size'])

        # Detector veloce per il live: SOLO detection (niente recognition/landmark).
        self.detector = FaceAnalysis(
            name=config['detector_name'],
            allowed_modules=['detection'],
            providers=self.providers,
        )
        self.detector.prepare(ctx_id=self.ctx_id, det_size=det_size,
                              det_thresh=config['det_thresh'])

        # App completa: serve l'embedding (recognition) della faccia sorgente.
        self.app = FaceAnalysis(
            name=config['detector_name'],
            allowed_modules=['detection', 'recognition'],
            providers=self.providers,
        )
        self.app.prepare(ctx_id=self.ctx_id, det_size=(320, 320),
                         det_thresh=config['det_thresh'])

        if not os.path.exists(self.model_path):
            print(f"❌ Modello non trovato: {self.model_path}")
            return False

        self.swapper = insightface.model_zoo.get_model(
            self.model_path, providers=self.providers
        )
        self.loaded = True
        return True

    # ---- detection ----------------------------------------------------------
    def detect_source(self, img):
        """Rileva la faccia della foto sorgente (con embedding). Prende la
        faccia più grande = il soggetto principale."""
        faces = self.app.get(img)
        if not faces:
            return None
        return max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))

    def detect_live(self, frame, stride=1):
        """Rilevamento veloce sul flusso live. Con stride>1 riusa l'ultimo
        risultato per i frame intermedi (compromesso latenza/fluidità)."""
        self._frame_idx += 1
        if stride > 1 and self._last_faces and (self._frame_idx % stride) != 0:
            return self._last_faces
        faces = self.detector.get(frame)
        self._last_faces = faces
        return faces

    # ---- swap + blend -------------------------------------------------------
    @staticmethod
    def _color_transfer(src, ref):
        """Adatta le statistiche di colore (LAB) di src a quelle di ref."""
        s = cv2.cvtColor(src, cv2.COLOR_BGR2LAB).astype(np.float32)
        r = cv2.cvtColor(ref, cv2.COLOR_BGR2LAB).astype(np.float32)
        out = s.copy()
        for i in range(3):
            sm, ss = float(s[..., i].mean()), float(s[..., i].std()) + 1e-6
            rm, rs = float(r[..., i].mean()), float(r[..., i].std()) + 1e-6
            out[..., i] = (s[..., i] - sm) * (rs / ss) + rm
        return cv2.cvtColor(np.clip(out, 0, 255).astype(np.uint8), cv2.COLOR_LAB2BGR)

    def _blend(self, frame, bgr_fake, M):
        """Fonde la faccia generata nel frame con maschera ellittica sfumata
        e color-match rispetto all'illuminazione locale."""
        h, w = frame.shape[:2]
        size = bgr_fake.shape[0]

        # crop originale allineato (stesso M dello swapper) per il color-match
        aimg = cv2.warpAffine(frame, M, (size, size), flags=cv2.INTER_LINEAR)
        fake = self._color_transfer(bgr_fake, aimg)

        # maschera ellittica nello spazio del crop (evita gli angoli quadrati)
        mask = np.zeros((size, size), np.float32)
        cv2.ellipse(mask, (size // 2, size // 2),
                    (int(size * 0.42), int(size * 0.50)), 0, 0, 360, 1.0, -1)

        IM = cv2.invertAffineTransform(M)
        fake_full = cv2.warpAffine(fake, IM, (w, h), borderValue=0)
        mask_full = cv2.warpAffine(mask, IM, (w, h), borderValue=0)

        # feather proporzionale alla dimensione reale della faccia nel frame
        scale = float(np.sqrt(M[0, 0] ** 2 + M[0, 1] ** 2)) + 1e-6  # frame->crop
        face_px = size / scale
        blur = int(max(5, face_px * 0.06))
        blur = blur + 1 if blur % 2 == 0 else blur
        mask_full = cv2.GaussianBlur(mask_full, (blur, blur), 0)
        mask_full = np.clip(mask_full, 0.0, 1.0)[..., None]

        out = fake_full.astype(np.float32) * mask_full + \
            frame.astype(np.float32) * (1.0 - mask_full)
        return out.astype(np.uint8)

    def swap(self, frame, target_face, source_face, realistic=True):
        if not self.loaded or target_face is None or source_face is None:
            return frame
        with self._lock:
            if realistic:
                try:
                    bgr_fake, M = self.swapper.get(frame, target_face, source_face,
                                                   paste_back=False)
                    return self._blend(frame, bgr_fake, M)
                except Exception:
                    pass  # fallback al paste_back nativo
            result = self.swapper.get(frame, target_face, source_face, paste_back=True)
            return result if result is not None else frame

    @staticmethod
    def best_face(faces):
        if not faces:
            return None
        return max(faces, key=lambda f: f.det_score)


# ============================================================
# 📊 PERFORMANCE MONITOR
# ============================================================
class PerformanceMonitor:
    def __init__(self):
        self.max_history = 100
        self.fps_history = []
        self.frame_count = 0
        self.last_time = time.time()
        self.current_fps = 0
        self._cpu = 0.0
        self._ram = 0.0

    def update_fps(self):
        self.frame_count += 1
        now = time.time()
        if now - self.last_time >= 0.5:
            self.current_fps = int(self.frame_count / (now - self.last_time))
            self.frame_count = 0
            self.last_time = now
            self.fps_history.append(self.current_fps)
            if len(self.fps_history) > self.max_history:
                self.fps_history.pop(0)
            if _HAS_PSUTIL:
                self._cpu = psutil.cpu_percent()
                self._ram = psutil.virtual_memory().percent
        return self.current_fps

    def get_stats(self):
        avg = int(np.mean(self.fps_history)) if self.fps_history else 0
        return {"fps": self.current_fps, "cpu": self._cpu, "ram": self._ram, "avg_fps": avg}


# ============================================================
# 🎨 APP UI
# ============================================================
class DeepfakeUltraPro:
    COLOR_MAP = {
        'green': (0, 255, 0), 'red': (0, 0, 255), 'blue': (255, 0, 0),
        'yellow': (0, 255, 255), 'cyan': (255, 255, 0), 'magenta': (255, 0, 255),
    }

    def __init__(self, root):
        self.root = root
        self.root.title("🎭 DEEPFAKE ULTRA PRO 5.0")
        self.root.geometry("1600x900")
        self.root.configure(bg='#0a0a0a')

        self.colors = {
            'bg': '#0a0a0a', 'panel': '#1a1a2e', 'card': '#16213e',
            'primary': '#00d4ff', 'accent': '#ff006e', 'success': '#00ff88',
            'warning': '#ffaa00', 'danger': '#ff5555',
        }

        # stato
        self.running = True
        self.swap_active = False
        self.models_ready = False
        self.face_loaded = False

        self.monitor = PerformanceMonitor()
        self.engine = None
        self.source_face = None
        self.source_image = None

        self.cap = None
        self.camera_index = 0

        # code: teniamo solo l'ultimo frame per ridurre la latenza
        self.capture_queue = queue.Queue(maxsize=2)
        self.display_queue = queue.Queue(maxsize=2)

        self.init_ui()
        self.start_system()
        self.root.after(50, self.display_pump)
        self.root.after(500, self.stats_pump)
        print("✅ System initialized")

    # ---- UI -----------------------------------------------------------------
    def init_ui(self):
        self.main_frame = tk.Frame(self.root, bg=self.colors['bg'])
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # ----- LEFT -----
        self.left_panel = tk.Frame(self.main_frame, width=280, bg=self.colors['panel'])
        self.left_panel.pack(side=tk.LEFT, fill=tk.Y)
        self.left_panel.pack_propagate(False)

        tk.Label(self.left_panel, text="🎭", font=('Arial', 48),
                 bg=self.colors['panel'], fg=self.colors['primary']).pack(pady=10)
        tk.Label(self.left_panel, text="DEEPFAKE ULTRA", font=('Arial', 16, 'bold'),
                 bg=self.colors['panel'], fg='white').pack()
        tk.Label(self.left_panel, text="PRO 5.0", font=('Arial', 12),
                 bg=self.colors['panel'], fg=self.colors['primary']).pack(pady=(0, 20))

        self.status_var = tk.StringVar(value="⚡ Loading AI...")
        tk.Label(self.left_panel, textvariable=self.status_var, font=('Arial', 10),
                 bg=self.colors['panel'], fg=self.colors['warning']).pack(pady=10)

        self.load_btn = tk.Button(self.left_panel, text="📁 LOAD FACE IMAGE",
                                  command=self.load_face_image, state='disabled',
                                  bg='#0066cc', fg='white', font=('Arial', 10, 'bold'),
                                  relief='raised', padx=10, pady=5)
        self.load_btn.pack(pady=10, padx=20, fill=tk.X)

        face_border = tk.Frame(self.left_panel, bg=self.colors['primary'])
        face_border.pack(pady=10, padx=10, fill=tk.X)
        face_frame = tk.Frame(face_border, bg=self.colors['card'])
        face_frame.pack(padx=1, pady=1, fill=tk.BOTH, expand=True)
        tk.Label(face_frame, text="FACE PREVIEW", bg=self.colors['card'], fg='white',
                 font=('Arial', 10, 'bold')).pack(pady=5)
        self.face_label = tk.Label(face_frame,
                                   text="No face loaded\n\nSelect clear frontal photo",
                                   bg='#000033', fg='#8888ff', font=('Arial', 9),
                                   width=30, height=10)
        self.face_label.pack(pady=10, padx=10)

        self.swap_btn = tk.Button(self.left_panel, text="🔴 SWAP OFF",
                                  command=self.toggle_swap, state='disabled',
                                  bg='#cc0000', fg='white', font=('Arial', 12, 'bold'),
                                  relief='raised', padx=10, pady=10)
        self.swap_btn.pack(pady=10, padx=20, fill=tk.X)

        # settings
        settings_border = tk.Frame(self.left_panel, bg=self.colors['primary'])
        settings_border.pack(pady=10, padx=10, fill=tk.X)
        settings_frame = tk.Frame(settings_border, bg=self.colors['card'])
        settings_frame.pack(padx=1, pady=1, fill=tk.BOTH, expand=True)
        tk.Label(settings_frame, text="SETTINGS", bg=self.colors['card'], fg='white',
                 font=('Arial', 10, 'bold')).pack(pady=5)

        self.realistic_var = tk.BooleanVar(value=config['realistic_blend'])
        tk.Checkbutton(settings_frame, text="Realistic blend (feather + color)",
                       variable=self.realistic_var, bg=self.colors['card'], fg='white',
                       selectcolor=self.colors['card'], activebackground=self.colors['card'],
                       activeforeground='white').pack(anchor='w', padx=10, pady=5)

        self.bbox_var = tk.BooleanVar(value=True)
        tk.Checkbutton(settings_frame, text="Show bounding box", variable=self.bbox_var,
                       bg=self.colors['card'], fg='white', selectcolor=self.colors['card'],
                       activebackground=self.colors['card'],
                       activeforeground='white').pack(anchor='w', padx=10, pady=5)

        self.fps_var = tk.BooleanVar(value=True)
        tk.Checkbutton(settings_frame, text="Show FPS counter", variable=self.fps_var,
                       bg=self.colors['card'], fg='white', selectcolor=self.colors['card'],
                       activebackground=self.colors['card'],
                       activeforeground='white').pack(anchor='w', padx=10, pady=5)

        color_frame = tk.Frame(settings_frame, bg=self.colors['card'])
        color_frame.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(color_frame, text="Box color:", bg=self.colors['card'],
                 fg='white').pack(side=tk.LEFT)
        self.color_combo = ttk.Combobox(color_frame,
                                        values=list(self.COLOR_MAP.keys()),
                                        state='readonly', width=10)
        self.color_combo.set('green')
        self.color_combo.pack(side=tk.RIGHT)

        # performance
        stats_border = tk.Frame(self.left_panel, bg=self.colors['primary'])
        stats_border.pack(pady=10, padx=10, fill=tk.X)
        stats_frame = tk.Frame(stats_border, bg=self.colors['card'])
        stats_frame.pack(padx=1, pady=1, fill=tk.BOTH, expand=True)
        tk.Label(stats_frame, text="PERFORMANCE", bg=self.colors['card'], fg='white',
                 font=('Arial', 10, 'bold')).pack(pady=5)
        self.fps_label = tk.Label(stats_frame, text="FPS: 0", font=('Arial', 24),
                                  bg=self.colors['card'], fg='#00ff00')
        self.fps_label.pack(pady=10)
        self.cpu_label = tk.Label(stats_frame, text="CPU: 0%", bg=self.colors['card'],
                                  fg='white')
        self.cpu_label.pack()
        self.ram_label = tk.Label(stats_frame, text="RAM: 0%", bg=self.colors['card'],
                                  fg='white')
        self.ram_label.pack(pady=(0, 10))

        # ----- CENTER -----
        self.center_panel = tk.Frame(self.main_frame, bg=self.colors['bg'])
        self.center_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        video_border = tk.Frame(self.center_panel, bg=self.colors['primary'])
        video_border.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        video_frame = tk.Frame(video_border, bg='black')
        video_frame.pack(padx=1, pady=1, fill=tk.BOTH, expand=True)
        tk.Label(video_frame, text="LIVE CAMERA", bg='black', fg='white',
                 font=('Arial', 12, 'bold')).pack(pady=5)
        self.video_label = tk.Label(video_frame, bg='black')
        self.video_label.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        # ----- RIGHT -----
        self.right_panel = tk.Frame(self.main_frame, width=250, bg=self.colors['panel'])
        self.right_panel.pack(side=tk.RIGHT, fill=tk.Y)
        self.right_panel.pack_propagate(False)

        mode_border = tk.Frame(self.right_panel, bg=self.colors['primary'])
        mode_border.pack(pady=10, padx=10, fill=tk.X)
        mode_frame = tk.Frame(mode_border, bg=self.colors['card'])
        mode_frame.pack(padx=1, pady=1, fill=tk.BOTH, expand=True)
        tk.Label(mode_frame, text="PROCESSING MODE", bg=self.colors['card'], fg='white',
                 font=('Arial', 10, 'bold')).pack(pady=5)
        self.mode_var = tk.StringVar(value='balanced')
        for text, val in [("⚡ FAST (Max FPS)", 'fast'),
                          ("⚖️ BALANCED", 'balanced'),
                          ("🎯 QUALITY", 'quality')]:
            tk.Radiobutton(mode_frame, text=text, variable=self.mode_var, value=val,
                           bg=self.colors['card'], fg='white',
                           selectcolor=self.colors['card'],
                           activebackground=self.colors['card'],
                           activeforeground='white').pack(anchor='w', padx=10, pady=2)

        console_border = tk.Frame(self.right_panel, bg=self.colors['primary'])
        console_border.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)
        console_frame = tk.Frame(console_border, bg=self.colors['card'])
        console_frame.pack(padx=1, pady=1, fill=tk.BOTH, expand=True)
        tk.Label(console_frame, text="SYSTEM LOG", bg=self.colors['card'], fg='white',
                 font=('Arial', 10, 'bold')).pack(pady=5)
        self.console = tk.Text(console_frame, bg='#0a0a0a', fg='#00ffaa',
                               font=('Consolas', 8), height=15, relief='flat', wrap='word')
        self.console.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        scrollbar = tk.Scrollbar(self.console)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.console.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.console.yview)

        self.bottom_status = tk.Label(self.root,
                                      text="Deepfake Ultra Pro 5.0 | Initializing...",
                                      bg='#1a1a2e', fg='white', font=('Arial', 10),
                                      relief='sunken', anchor='w')
        self.bottom_status.pack(side=tk.BOTTOM, fill=tk.X)

        self.root.bind('<Escape>', lambda e: self.quit_app())
        self.root.bind('<space>', lambda e: self.toggle_swap())
        self.root.bind('f', lambda e: self.toggle_fullscreen())
        self.root.bind('r', lambda e: self.reset_camera())

    # ---- startup ------------------------------------------------------------
    def start_system(self):
        threading.Thread(target=self.initialize_models, daemon=True).start()

    def initialize_models(self):
        self.log("⚡ Initializing AI models...")
        self.status_var.set("⚡ Loading AI models...")
        try:
            model_path = config['model_path']
            if not os.path.exists(model_path):
                self.log(f"❌ Model not found: {model_path}")
                self.log("📥 Download: github.com/deepinsight/insightface/releases")
                self.status_var.set("❌ Model missing")
                return

            self.engine = FaceEngine(model_path)
            if self.engine.load():
                self.models_ready = True
                self.status_var.set(f"✅ Ready · {self.engine.provider_name}")
                self.log(f"✅ Models loaded · provider: {self.engine.provider_name}")
                self.load_btn.config(state='normal', bg='#0088cc')
                self.start_camera_thread()
            else:
                self.status_var.set("❌ Model error")
                self.log("❌ Model load failed")
        except Exception as e:
            self.log(f"❌ Initialization error: {e}")
            self.status_var.set("❌ Initialization failed")

    def start_camera_thread(self):
        threading.Thread(target=self.initialize_camera, daemon=True).start()

    def initialize_camera(self):
        self.log("📷 Initializing camera...")
        for cam_id in range(3):
            try:
                if os.name == 'nt':
                    cap = cv2.VideoCapture(cam_id, cv2.CAP_DSHOW)
                else:
                    cap = cv2.VideoCapture(cam_id)
                if cap.isOpened():
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                    cap.set(cv2.CAP_PROP_FPS, 60)
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    self.cap = cap
                    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    fps = int(cap.get(cv2.CAP_PROP_FPS))
                    self.log(f"✅ Camera {cam_id}: {w}x{h} @ {fps}FPS")
                    self.status_var.set("✅ Camera ready")
                    self.camera_index = cam_id
                    self.start_processing_threads()
                    return
                cap.release()
            except Exception:
                continue
        self.log("❌ No camera found")
        self.status_var.set("❌ No camera")

    def start_processing_threads(self):
        # UN capture thread + UN inference thread. Il display è gestito dal
        # main thread (Tk) tramite display_pump.
        threading.Thread(target=self.capture_loop, daemon=True).start()
        threading.Thread(target=self.process_loop, daemon=True, name="Inference").start()
        self.log("⚡ Pipeline started (1 capture + 1 inference)")

    # ---- threads ------------------------------------------------------------
    def capture_loop(self):
        while self.running and self.cap is not None:
            try:
                ok, frame = self.cap.read()
                if not ok:
                    time.sleep(0.002)
                    continue
                # tieni solo l'ultimo frame
                if self.capture_queue.full():
                    try:
                        self.capture_queue.get_nowait()
                    except queue.Empty:
                        pass
                self.capture_queue.put_nowait(frame)
            except Exception:
                time.sleep(0.002)

    def process_loop(self):
        while self.running:
            try:
                frame = self.capture_queue.get(timeout=0.05)
            except queue.Empty:
                continue
            try:
                mode = self.mode_var.get()
                if mode == 'fast':
                    frame = cv2.resize(frame, (640, 360))
                    stride = config['fast_detect_stride']
                elif mode == 'quality':
                    frame = cv2.resize(frame, (960, 540))
                    stride = 1
                else:  # balanced
                    frame = cv2.resize(frame, (854, 480))
                    stride = 1

                result = frame

                if self.swap_active and self.models_ready and self.source_face is not None:
                    faces = self.engine.detect_live(frame, stride=stride)
                    best = self.engine.best_face(faces)
                    if best is not None and best.det_score >= config['swap_threshold']:
                        result = self.engine.swap(frame, best, self.source_face,
                                                  realistic=self.realistic_var.get())
                        if self.bbox_var.get():
                            color = self.COLOR_MAP.get(self.color_combo.get(), (0, 255, 0))
                            b = best.bbox.astype(int)
                            cv2.rectangle(result, (b[0], b[1]), (b[2], b[3]), color, 2)
                            cv2.putText(result, f"{best.det_score:.2f}", (b[0], b[1] - 5),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

                if self.fps_var.get():
                    cv2.putText(result, f"FPS: {self.monitor.current_fps}", (10, 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

                self.monitor.update_fps()

                if self.display_queue.full():
                    try:
                        self.display_queue.get_nowait()
                    except queue.Empty:
                        pass
                self.display_queue.put_nowait(result)
            except Exception as e:
                self.log(f"⚠️ Process error: {str(e)[:60]}")

    # ---- UI pumps (main thread) --------------------------------------------
    def display_pump(self):
        if not self.running:
            return
        frame = None
        try:
            while True:
                frame = self.display_queue.get_nowait()
        except queue.Empty:
            pass
        if frame is not None:
            try:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                photo = ImageTk.PhotoImage(image=Image.fromarray(rgb))
                self.video_label.config(image=photo)
                self.video_label.image = photo
            except Exception:
                pass
        self.root.after(int(1000 / config['display_hz']), self.display_pump)

    def stats_pump(self):
        if not self.running:
            return
        s = self.monitor.get_stats()
        self.fps_label.config(text=f"FPS: {s['fps']}")
        self.cpu_label.config(text=f"CPU: {s['cpu']:.1f}%")
        self.ram_label.config(text=f"RAM: {s['ram']:.1f}%")
        mode = self.mode_var.get().upper()
        self.bottom_status.config(
            text=f"Deepfake Ultra Pro 5.0 | FPS: {s['fps']} (avg {s['avg_fps']}) | "
                 f"Swap: {'ON' if self.swap_active else 'OFF'} | Mode: {mode} | "
                 f"CPU: {s['cpu']:.0f}% | RAM: {s['ram']:.0f}%")
        self.root.after(500, self.stats_pump)

    # ---- actions ------------------------------------------------------------
    def load_face_image(self):
        if not self.models_ready:
            messagebox.showwarning("Wait", "AI models still loading")
            return
        file_path = filedialog.askopenfilename(
            title="Select face image",
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp"),
                       ("JPEG files", "*.jpg *.jpeg"), ("PNG files", "*.png"),
                       ("All files", "*.*")])
        if not file_path:
            return
        try:
            self.log(f"📁 Loading: {os.path.basename(file_path)}")
            img = cv2.imread(file_path)
            if img is None:
                messagebox.showerror("Error", "Cannot read image file")
                return
            face = self.engine.detect_source(img)
            if face is None:
                messagebox.showwarning("No face", "No face detected in image")
                return

            self.source_face = face
            self.source_image = img
            self.face_loaded = True

            preview = img.copy()
            b = face.bbox.astype(int)
            cv2.rectangle(preview, (b[0], b[1]), (b[2], b[3]), (0, 255, 0), 3)
            pil_img = Image.fromarray(cv2.cvtColor(preview, cv2.COLOR_BGR2RGB))
            pil_img.thumbnail((250, 250))
            photo = ImageTk.PhotoImage(image=pil_img)
            self.face_label.config(image=photo, text="")
            self.face_label.image = photo

            self.status_var.set("✅ Face loaded")
            self.log(f"✅ Face loaded (score: {face.det_score:.3f})")
            self.swap_btn.config(state='normal')
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load: {e}")
            self.log(f"❌ Load error: {e}")

    def toggle_swap(self):
        if not self.face_loaded:
            messagebox.showwarning("No face", "Load a face first")
            return
        self.swap_active = not self.swap_active
        if self.swap_active:
            self.swap_btn.config(text="✅ SWAP ON", bg='#00aa00')
            self.log("⚡ Face swap ACTIVATED")
        else:
            self.swap_btn.config(text="🔴 SWAP OFF", bg='#cc0000')
            self.log("⚡ Face swap DEACTIVATED")

    def toggle_fullscreen(self):
        self.root.attributes('-fullscreen', not self.root.attributes('-fullscreen'))

    def reset_camera(self):
        if self.cap:
            self.cap.release()
            self.cap = None
        threading.Thread(target=self.initialize_camera, daemon=True).start()
        self.log("🔄 Camera reset")

    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        try:
            self.console.insert(tk.END, f"[{timestamp}] {message}\n")
            self.console.see(tk.END)
            if int(self.console.index('end-1c').split('.')[0]) > 200:
                self.console.delete("1.0", "50.0")
        except Exception:
            print(f"[{timestamp}] {message}")

    def quit_app(self):
        self.running = False
        if self.cap:
            self.cap.release()
        try:
            self.root.quit()
            self.root.destroy()
        except Exception:
            pass
        print("\n" + "=" * 80)
        print("👋 Application closed")
        print("=" * 80)


# ============================================================
# 🚀 MAIN
# ============================================================
def main():
    _sys_banner()
    print("🚀 DEEPFAKE ULTRA PRO 5.0 - STARTING")
    print("=" * 80)

    if not os.path.exists(config['model_path']):
        print(f"\n⚠️  Modello '{config['model_path']}' non trovato!")
        print("   Scaricalo da: github.com/deepinsight/insightface/releases")
        print("   e mettilo nella stessa cartella di questo script.")
        print("=" * 80)
        try:
            if input("\nContinuo comunque? (y/n): ").lower() != 'y':
                return
        except EOFError:
            return

    root = tk.Tk()
    app = DeepfakeUltraPro(root)

    root.update_idletasks()
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    ww, wh = root.winfo_width(), root.winfo_height()
    root.geometry(f"{ww}x{wh}+{(sw - ww) // 2}+{(sh - wh) // 2}")

    root.protocol("WM_DELETE_WINDOW", app.quit_app)
    root.mainloop()


if __name__ == "__main__":
    main()
