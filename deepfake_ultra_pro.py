#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🎭 DEEPFAKE ULTRA PRO 7.5  ⚡  (real-time face swap)

Più impostazioni, più realismo, più potenza.

NOVITÀ della 7.5
  * OCCLUDER AI: modello neurale di occlusione → quando metti la MANO (o un
    oggetto) davanti al viso, la faccia swappata si ritira e si vede la mano
    vera. Il colore-pelle non bastava (la mano è pelle); questo sì.
  * COASTING più lungo (9 frame): quando ti muovi veloce lo swap non "si stacca".

NOVITÀ della 7.4 (stile Deep-Live-Cam)
  * MATCH TARGET: in una scena con più persone, sostituisce SOLO la persona
    scelta (riconoscimento d'identità via embedding). Carichi la foto di "chi
    sostituire" 🎯 e vengono swappati solo i volti che le somigliano.

NOVITÀ della 7.3
  * EXPORT VIDEO HQ (offline): processa un file video a risoluzione nativa,
    ogni frame, senza vincolo di FPS → qualità massima. Output MP4 (senza audio).

NOVITÀ della 7.2
  * OCCLUSION: dove nell'area del volto non c'è pelle (ciuffi, occhiali,
    oggetti) lo swap si ritira → niente faccia "spalmata" sopra le cose.

NOVITÀ della 7.1 (fix realismo + GPU)
  * FOREHEAD: la maschera precisa ora si estende verso la FRONTE seguendo
    l'inclinazione della testa → sopracciglia e fronte coperte, niente stacco.
  * COASTING: se il detector salta un frame la posizione viene tenuta per
    qualche frame → basta swap "a trattini"/flicker.
  * ENHANCER SUL CROP (GFPGAN): lavora solo sul volto (512→restore→blend),
    real-time su GPU (es. RTX 4070); il modello si scarica da solo.

NOVITÀ della 7.0 (realismo del volto)
  * MASCHERA PRECISA dai landmark 2D-106: segue la reale forma di mascella/
    mento invece di un'ellisse fissa → meno effetto "faccia incollata".
  * KEEP MOUTH: lascia trasparire la BOCCA REALE, così quando parli o muovi
    la lingua l'espressione resta naturale (limite tipico dello swap 128px).

Dalla 6.0
  * Slider live: soglia, mask size, feather, color-match, sharpen, skin-smooth.
  * det_size 256/320/512/640 a caldo; multi-face; mirror; input da file video;
    snapshot PNG e registrazione MP4; enhancer opzionale GFPGAN.
  * Provider ONNX auto (CUDA/CoreML/DirectML/CPU); un solo thread di inferenza.

LIMITI DEL MODELLO (inswapper_128) — onestà tecnica
  * NON scambia i capelli / la testa: sostituisce solo il volto interno.
    Capelli, attaccatura e forma della testa restano del soggetto ripreso.
    Uno swap di capelli/testa richiede un'altra classe di modelli, molto più
    pesanti e non real-time.
  * Lavora a 128x128: il dettaglio di denti/lingua è limitato. GFPGAN aiuta
    ma non elimina del tutto il problema; "Keep mouth" è il rimedio pratico.

Uso etico: usa solo volti per cui hai il consenso. Non creare contenuti
ingannevoli o che ledano le persone.

Requisiti: vedi requirements.txt · Modello: inswapper_128.onnx
"""

import warnings
warnings.filterwarnings('ignore')

import os
os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '3')
os.environ.setdefault('KMP_DUPLICATE_LIB_OK', 'TRUE')
os.environ.setdefault('OMP_NUM_THREADS', str(max(1, (os.cpu_count() or 4))))

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
# 🔥 CONFIG (default; molti valori sono regolabili dalla UI)
# ============================================================
config = {
    'model_path': 'inswapper_128.onnx',
    'detector_name': 'buffalo_l',
    'det_size': 320,
    'det_thresh': 0.5,
    'display_hz': 60,
    'record_fps': 24,
    'output_dir': 'output',
    'gfpgan_model': 'GFPGANv1.4.pth',
    'occluder_model': 'face_occluder.onnx',
    # default regolazioni
    'swap_threshold': 0.35,
    'mask_size': 1.0,       # 0.6 - 1.3
    'feather': 0.06,        # 0.02 - 0.15
    'color_strength': 0.80,  # 0 - 1
    'sharpen': 0.15,        # 0 - 1
    'smooth': 0.0,          # 0 - 1
    'multi_face': True,
    'realistic_blend': True,
    'mirror': False,
    'fast_detect_stride': 2,
    'precise_mask': True,   # maschera dai landmark (segue la mascella)
    'forehead': 0.30,       # estensione maschera verso la fronte (0-0.6)
    'keep_mouth': 0.30,     # 0=bocca sorgente, 1=bocca reale (lingua/parlato)
    'stabilize': 0.40,      # anti-jitter temporale (0=off, 0.9=molto fermo)
    'coast_frames': 9,      # frame in cui "tiene" l'ultima faccia se il detect salta
    'occlusion': 0.0,       # protezione occlusioni (0=off): ciuffi/occhiali/oggetti
    'match': False,         # sostituisci SOLO la persona-target (per identità)
    'match_thresh': 0.35,   # soglia similarità coseno (buffalo_l w600k)
}

MODE_RES = {'fast': (640, 360), 'balanced': (854, 480), 'quality': (960, 540)}


def _cpu_count():
    try:
        return psutil.cpu_count() if _HAS_PSUTIL else (os.cpu_count() or 4)
    except Exception:
        return os.cpu_count() or 4


# ============================================================
# 🧠 FACE ENGINE
# ============================================================
class FaceEngine:
    """Carica i modelli e fornisce rilevamento, swap, blending ed enhance."""

    def __init__(self, model_path):
        self.model_path = model_path
        self.detector = None      # detection-only (live)
        self.app = None           # completo (embedding sorgente)
        self.swapper = None
        self.enhancer = None
        self.enhancer_ready = False
        self.matcher = None            # detector con recognition (match identità)
        self.matcher_ready = False
        self.occluder = None           # modello neurale di occlusione (mani/oggetti)
        self.occluder_ready = False
        self.occluder_in = None
        self._occ_size = 256
        self._occ_nchw = False
        self.loaded = False

        self.providers = []
        self.provider_name = 'CPU'
        self.ctx_id = -1

        self._lock = threading.Lock()
        self._last_faces = []
        self._frame_idx = 0

    # ---- providers ----------------------------------------------------------
    def _select_providers(self):
        try:
            import onnxruntime as ort
            avail = ort.get_available_providers()
        except Exception:
            avail = ['CPUExecutionProvider']
        preferred = ['CUDAExecutionProvider', 'CoreMLExecutionProvider',
                     'DmlExecutionProvider', 'CPUExecutionProvider']
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

        det = (config['det_size'], config['det_size'])
        # detection + landmark_2d_106 per la maschera precisa (niente recognition)
        self.detector = FaceAnalysis(name=config['detector_name'],
                                     allowed_modules=['detection', 'landmark_2d_106'],
                                     providers=self.providers)
        self.detector.prepare(ctx_id=self.ctx_id, det_size=det,
                              det_thresh=config['det_thresh'])

        self.app = FaceAnalysis(name=config['detector_name'],
                                allowed_modules=['detection', 'recognition'],
                                providers=self.providers)
        self.app.prepare(ctx_id=self.ctx_id, det_size=(320, 320),
                         det_thresh=config['det_thresh'])

        if not os.path.exists(self.model_path):
            print(f"❌ Modello non trovato: {self.model_path}")
            return False
        self.swapper = insightface.model_zoo.get_model(self.model_path,
                                                       providers=self.providers)
        self.loaded = True
        return True

    GFPGAN_URL = ('https://github.com/TencentARC/GFPGAN/releases/download/'
                  'v1.3.0/GFPGANv1.4.pth')

    def try_load_enhancer(self):
        """Carica GFPGAN. Usa il file locale se c'è, altrimenti lo scarica.
        Ritorna (ok, messaggio)."""
        if self.enhancer_ready:
            return True, "enhancer già pronto"
        try:
            from gfpgan import GFPGANer
        except Exception:
            return False, "pacchetto 'gfpgan' non installato (pip install gfpgan)"
        local = config['gfpgan_model']
        model = local if os.path.exists(local) else self.GFPGAN_URL
        try:
            self.enhancer = GFPGANer(model_path=model, upscale=1, arch='clean',
                                     channel_multiplier=2, bg_upsampler=None)
            self.enhancer_ready = True
            src = "file locale" if model == local else "download automatico"
            return True, f"GFPGAN pronto ({src})"
        except Exception as e:
            return False, f"errore GFPGAN: {str(e)[:80]}"

    def enhance_crop(self, crop):
        """Migliora SOLO il crop del volto (aligned): veloce, adatto al live su
        GPU. Upscale a 512, restore, torna alla dimensione originale."""
        if not self.enhancer_ready:
            return crop
        try:
            a = cv2.resize(crop, (512, 512), interpolation=cv2.INTER_LINEAR)
            _, restored, _ = self.enhancer.enhance(a, has_aligned=True,
                                                   paste_back=False)
            if restored:
                return cv2.resize(restored[0], (crop.shape[1], crop.shape[0]),
                                  interpolation=cv2.INTER_AREA)
        except Exception:
            pass
        return crop

    def set_det_size(self, n):
        with self._lock:
            self.detector.prepare(ctx_id=self.ctx_id, det_size=(int(n), int(n)),
                                  det_thresh=config['det_thresh'])

    # ---- detection ----------------------------------------------------------
    def detect_source(self, img):
        faces = self.app.get(img)
        if not faces:
            return None
        return max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))

    def detect(self, frame):
        """Rilevamento diretto (no stride/cache) — per l'export offline."""
        with self._lock:
            return self.detector.get(frame)

    def ensure_matcher(self):
        """Costruisce (lazy) un detector con detection+landmark+recognition,
        usato per il match d'identità. Ritorna (ok, messaggio)."""
        if self.matcher_ready:
            return True, "matcher pronto"
        try:
            from insightface.app import FaceAnalysis
            self.matcher = FaceAnalysis(
                name=config['detector_name'],
                allowed_modules=['detection', 'landmark_2d_106', 'recognition'],
                providers=self.providers)
            self.matcher.prepare(ctx_id=self.ctx_id,
                                 det_size=(config['det_size'], config['det_size']),
                                 det_thresh=config['det_thresh'])
            self.matcher_ready = True
            return True, "match identità pronto"
        except Exception as e:
            return False, f"errore matcher: {str(e)[:80]}"

    def detect_match(self, frame):
        """Rilevamento con embedding (per il match d'identità)."""
        with self._lock:
            return self.matcher.get(frame)

    OCCLUDER_URLS = [
        'https://github.com/facefusion/facefusion-assets/releases/download/'
        'models/face_occluder.onnx',
        'https://huggingface.co/facefusion/models/resolve/main/face_occluder.onnx',
    ]

    @staticmethod
    def _download_first(urls, dest):
        import urllib.request
        d = os.path.dirname(dest)
        if d:
            os.makedirs(d, exist_ok=True)
        for u in urls:
            try:
                urllib.request.urlretrieve(u, dest)
                if os.path.exists(dest) and os.path.getsize(dest) > 10000:
                    return True
            except Exception:
                continue
        return False

    def try_load_occluder(self):
        """Carica il modello neurale di occlusione (gestisce anche le MANI).
        Scarica il file se manca. Ritorna (ok, messaggio)."""
        if self.occluder_ready:
            return True, "occluder pronto"
        try:
            import onnxruntime as ort
        except Exception:
            return False, "onnxruntime non disponibile"
        path = config['occluder_model']
        if not os.path.exists(path):
            if not self._download_first(self.OCCLUDER_URLS, path):
                return False, f"scarica 'face_occluder.onnx' e mettilo come {path}"
        try:
            so = ort.SessionOptions()
            so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            self.occluder = ort.InferenceSession(path, sess_options=so,
                                                 providers=self.providers)
            inp = self.occluder.get_inputs()[0]
            self.occluder_in = inp.name
            shape = inp.shape  # [1,3,H,W] (NCHW) oppure [1,H,W,3] (NHWC)
            self._occ_nchw = len(shape) == 4 and shape[1] == 3
            dim = shape[2] if self._occ_nchw else shape[1]
            self._occ_size = int(dim) if isinstance(dim, int) and dim > 0 else 256
            self.occluder_ready = True
            return True, f"occluder AI pronto ({'NCHW' if self._occ_nchw else 'NHWC'}"\
                         f" {self._occ_size})"
        except Exception as e:
            return False, f"errore occluder: {str(e)[:80]}"

    def occlusion_mask_crop(self, crop):
        """Maschera 'faccia visibile' (1=faccia, 0=occluso) sul crop allineato.
        Dove c'è una mano/oggetto davanti, il modello restituisce ~0."""
        if not self.occluder_ready:
            return None
        try:
            s = self._occ_size
            img = cv2.resize(crop, (s, s))[:, :, ::-1].astype(np.float32) / 255.0
            blob = np.transpose(img, (2, 0, 1))[None] if self._occ_nchw else img[None]
            out = self.occluder.run(None, {self.occluder_in: blob})[0]
            m = np.asarray(out, np.float32).squeeze()
            if m.ndim == 3:
                m = m[0] if m.shape[0] < m.shape[-1] else m[..., 0]
            m = np.clip(m, 0.0, 1.0)
            return cv2.resize(m, (crop.shape[1], crop.shape[0]))
        except Exception:
            return None

    def detect_live(self, frame, stride=1):
        self._frame_idx += 1
        if stride > 1 and self._last_faces and (self._frame_idx % stride) != 0:
            return self._last_faces
        with self._lock:
            faces = self.detector.get(frame)
        self._last_faces = faces
        return faces

    # ---- blending -----------------------------------------------------------
    @staticmethod
    def _color_transfer(src, ref):
        s = cv2.cvtColor(src, cv2.COLOR_BGR2LAB).astype(np.float32)
        r = cv2.cvtColor(ref, cv2.COLOR_BGR2LAB).astype(np.float32)
        out = s.copy()
        for i in range(3):
            sm, ss = float(s[..., i].mean()), float(s[..., i].std()) + 1e-6
            rm, rs = float(r[..., i].mean()), float(r[..., i].std()) + 1e-6
            out[..., i] = (s[..., i] - sm) * (rs / ss) + rm
        return cv2.cvtColor(np.clip(out, 0, 255).astype(np.uint8), cv2.COLOR_LAB2BGR)

    @staticmethod
    def _sharpen(img, amount):
        if amount <= 0:
            return img
        blur = cv2.GaussianBlur(img, (0, 0), 3)
        return cv2.addWeighted(img, 1.0 + amount, blur, -amount, 0)

    @staticmethod
    def _smooth(img, amount):
        if amount <= 0:
            return img
        sm = cv2.bilateralFilter(img, 7, 45, 45)
        return cv2.addWeighted(img, 1.0 - amount, sm, amount, 0)

    @staticmethod
    def _ellipse_mask_full(M, size, w, h, ms):
        ax = int(np.clip(size * 0.42 * ms, 4, size // 2))
        ay = int(np.clip(size * 0.50 * ms, 4, size // 2))
        mask = np.zeros((size, size), np.float32)
        cv2.ellipse(mask, (size // 2, size // 2), (ax, ay), 0, 0, 360, 1.0, -1)
        IM = cv2.invertAffineTransform(M)
        return cv2.warpAffine(mask, IM, (w, h), borderValue=0)

    @staticmethod
    def _landmark_mask_full(face, w, h, ms, forehead, M):
        """Maschera che segue la reale forma del volto (convex hull dei 106
        landmark) ED estesa verso la FRONTE lungo l'asse 'su' della testa —
        così sopracciglia e fronte vengono coperte dallo swap (niente stacco)."""
        pts = getattr(face, 'landmark_2d_106', None)
        if pts is None:
            return None
        try:
            pts = np.asarray(pts, dtype=np.float32)
            allpts = pts
            if forehead > 0:
                # direzione "su" del volto in coordinate frame (dal crop allineato)
                IM = cv2.invertAffineTransform(M)
                up = -IM[:, 1].astype(np.float32)
                up = up / (float(np.linalg.norm(up)) + 1e-6)
                fh = float(pts[:, 1].max() - pts[:, 1].min())
                shift = up * (fh * float(forehead))
                allpts = np.vstack([pts, pts + shift])
            hull = cv2.convexHull(allpts.astype(np.int32))
            mask = np.zeros((h, w), np.float32)
            cv2.fillConvexPoly(mask, hull, 1.0)
            fw = float(face.bbox[2] - face.bbox[0])
            k = max(1, int(fw * 0.05 * ms))
            mask = cv2.dilate(mask, np.ones((k, k), np.uint8))
            return mask
        except Exception:
            return None

    @staticmethod
    def _mouth_mask_full(face, w, h):
        """Ellisse morbida sulla bocca (dai keypoint) per far trasparire la
        bocca reale: espressioni e lingua restano naturali."""
        kps = getattr(face, 'kps', None)
        if kps is None or len(kps) < 5:
            return None
        lm = np.asarray(kps[3], np.float32)
        rm = np.asarray(kps[4], np.float32)
        cx, cy = (lm + rm) / 2.0
        wd = float(np.linalg.norm(rm - lm)) + 1e-6
        ang = float(np.degrees(np.arctan2(rm[1] - lm[1], rm[0] - lm[0])))
        m = np.zeros((h, w), np.float32)
        cv2.ellipse(m, (int(cx), int(cy)),
                    (int(wd * 0.85), int(wd * 0.60)), ang, 0, 360, 1.0, -1)
        b = max(3, int(wd * 0.4))
        b = b + 1 if b % 2 == 0 else b
        return cv2.GaussianBlur(m, (b, b), 0)

    @staticmethod
    def _skin_prob(bgr):
        """Probabilità di pelle (YCrCb). Serve a NON coprire con lo swap ciò
        che non è pelle dentro l'area del volto (ciuffi, occhiali, oggetti).
        Nota: le mani sono color pelle, quindi non vengono protette."""
        ycrcb = cv2.cvtColor(bgr, cv2.COLOR_BGR2YCrCb)
        lower = np.array([0, 133, 77], np.uint8)
        upper = np.array([255, 173, 127], np.uint8)
        m = cv2.inRange(ycrcb, lower, upper).astype(np.float32) / 255.0
        return cv2.GaussianBlur(m, (7, 7), 0)

    def _blend(self, frame, bgr_fake, M, face, p):
        h, w = frame.shape[:2]
        # enhancer sul crop (denti/pelle/bocca ad alta fedeltà) prima del blend
        if p.get('enhance') and self.enhancer_ready:
            bgr_fake = self.enhance_crop(bgr_fake)
        size = bgr_fake.shape[0]

        aimg = cv2.warpAffine(frame, M, (size, size), flags=cv2.INTER_LINEAR)
        cs = float(p['color_strength'])
        if cs > 0:
            ct = self._color_transfer(bgr_fake, aimg)
            fake = cv2.addWeighted(bgr_fake, 1.0 - cs, ct, cs, 0)
        else:
            fake = bgr_fake
        fake = self._smooth(fake, float(p['smooth']))
        fake = self._sharpen(fake, float(p['sharpen']))

        IM = cv2.invertAffineTransform(M)
        fake_full = cv2.warpAffine(fake, IM, (w, h), borderValue=0)

        ms = float(p['mask_size'])
        mask_full = None
        if p.get('precise_mask'):
            mask_full = self._landmark_mask_full(face, w, h, ms,
                                                 float(p.get('forehead', 0.0)), M)
        if mask_full is None:
            mask_full = self._ellipse_mask_full(M, size, w, h, ms)

        km = float(p.get('keep_mouth', 0.0))
        if km > 0:
            mm = self._mouth_mask_full(face, w, h)
            if mm is not None:
                mask_full = mask_full * (1.0 - km * mm)

        # occlusione neurale (mani/oggetti): il modello dice dov'è la faccia vera
        if p.get('occluder') and self.occluder_ready:
            occm = self.occlusion_mask_crop(aimg)
            if occm is not None:
                occ_full = cv2.warpAffine(occm, IM, (w, h), borderValue=1.0)
                mask_full = mask_full * occ_full

        # occlusione "leggera": dove NON c'è pelle nell'area del volto, originale
        occ = float(p.get('occlusion', 0.0))
        if occ > 0:
            skin = self._skin_prob(frame)
            mask_full = mask_full * (1.0 - occ * (1.0 - skin))

        scale = float(np.sqrt(M[0, 0] ** 2 + M[0, 1] ** 2)) + 1e-6
        face_px = size / scale
        blur = int(max(3, face_px * float(p['feather'])))
        blur = blur + 1 if blur % 2 == 0 else blur
        mask_full = cv2.GaussianBlur(mask_full, (blur, blur), 0)
        mask_full = np.clip(mask_full, 0.0, 1.0)[..., None]

        out = fake_full.astype(np.float32) * mask_full + \
            frame.astype(np.float32) * (1.0 - mask_full)
        return out.astype(np.uint8)

    def swap_one(self, frame, target, source, p):
        if not self.loaded or target is None or source is None:
            return frame
        with self._lock:
            if p['realistic_blend']:
                try:
                    bgr_fake, M = self.swapper.get(frame, target, source, paste_back=False)
                except Exception:
                    return self.swapper.get(frame, target, source, paste_back=True) or frame
            else:
                return self.swapper.get(frame, target, source, paste_back=True) or frame
        # blend fuori dal lock (solo numpy/cv2)
        return self._blend(frame, bgr_fake, M, target, p)

    @staticmethod
    def best_face(faces):
        return max(faces, key=lambda f: f.det_score) if faces else None


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
# 🎯 FACE STABILIZER (anti-jitter temporale)
# ============================================================
class FaceStabilizer:
    """Leviga bbox/keypoint/landmark nel tempo per togliere il tremolìo dello
    swap. Associa i volti tra frame consecutivi per centroide (greedy)."""

    _KEYS = ('bbox', 'kps', 'landmark_2d_106')

    def __init__(self):
        self.tracks = {}   # id -> {'c':centroid, 'geo':{key:array}, 'age':int}
        self._next = 0

    @staticmethod
    def _centroid(face):
        b = np.asarray(face.bbox, np.float32)
        return np.array([(b[0] + b[2]) / 2.0, (b[1] + b[3]) / 2.0], np.float32)

    @staticmethod
    def _face_w(face):
        b = np.asarray(face.bbox, np.float32)
        return float(b[2] - b[0])

    def update(self, faces, strength):
        """strength in [0,0.95]: quota del valore precedente da mantenere.
        0 = nessuna levigatura, 0.9 = molto fermo (più latenza)."""
        if not faces:
            self.tracks.clear()
            return faces
        s = float(np.clip(strength, 0.0, 0.95))

        cents = [self._centroid(f) for f in faces]
        used = set()
        assigned = {}
        # greedy match: per ogni volto, la traccia più vicina entro soglia
        for i, f in enumerate(faces):
            best_id, best_d = None, None
            thr = max(40.0, 0.6 * self._face_w(f))
            for tid, t in self.tracks.items():
                if tid in used:
                    continue
                d = float(np.linalg.norm(cents[i] - t['c']))
                if d <= thr and (best_d is None or d < best_d):
                    best_id, best_d = tid, d
            if best_id is not None:
                used.add(best_id)
                assigned[i] = best_id

        new_tracks = {}
        for i, f in enumerate(faces):
            tid = assigned.get(i)
            geo = {}
            for k in self._KEYS:
                cur = getattr(f, k, None)
                if cur is None:
                    continue
                cur = np.asarray(cur, np.float32)
                if s > 0 and tid is not None and k in self.tracks[tid]['geo']:
                    prev = self.tracks[tid]['geo'][k]
                    if prev.shape == cur.shape:
                        cur = s * prev + (1.0 - s) * cur
                        setattr(f, k, cur)
                geo[k] = cur
            nid = tid if tid is not None else self._new_id()
            new_tracks[nid] = {'c': self._centroid(f), 'geo': geo, 'age': 0}
        self.tracks = new_tracks
        return faces

    def _new_id(self):
        self._next += 1
        return self._next


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
        self.root.title("🎭 DEEPFAKE ULTRA PRO 7.5")
        self.root.geometry("1680x940")
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
        self.source_mode = 'camera'   # 'camera' | 'video'
        self.video_path = None

        self.last_result = None       # ultimo frame processato (BGR) per snapshot/rec
        self.recording = False
        self.writer = None
        self.rec_size = None

        # parametri sincronizzati dal main thread (thread-safe per l'inferenza)
        self.params = {k: config[k] for k in
                       ('swap_threshold', 'mask_size', 'feather', 'color_strength',
                        'sharpen', 'smooth', 'multi_face', 'realistic_blend', 'mirror',
                        'precise_mask', 'keep_mouth', 'stabilize', 'forehead',
                        'occlusion', 'match', 'match_thresh')}
        self.params['enhance'] = False
        self.params['occluder'] = False
        self.stabilizer = FaceStabilizer()
        self._coast_faces = None
        self._coast = 0
        self.target_ref = None        # embedding della persona da sostituire

        self.capture_queue = queue.Queue(maxsize=2)
        self.display_queue = queue.Queue(maxsize=2)

        self.init_ui()
        self.start_system()
        self.root.after(50, self.display_pump)
        self.root.after(500, self.stats_pump)
        print("✅ System initialized")

    # ---- helpers UI ---------------------------------------------------------
    def _card(self, parent, title):
        border = tk.Frame(parent, bg=self.colors['primary'])
        border.pack(pady=8, padx=10, fill=tk.X)
        card = tk.Frame(border, bg=self.colors['card'])
        card.pack(padx=1, pady=1, fill=tk.BOTH, expand=True)
        if title:
            tk.Label(card, text=title, bg=self.colors['card'], fg='white',
                     font=('Arial', 10, 'bold')).pack(pady=4)
        return card

    def _slider(self, parent, label, var, frm, to, fmt="{:.2f}"):
        row = tk.Frame(parent, bg=self.colors['card'])
        row.pack(fill=tk.X, padx=10, pady=2)
        lab = tk.Label(row, text=label, bg=self.colors['card'], fg='white',
                       font=('Arial', 8), width=14, anchor='w')
        lab.pack(side=tk.LEFT)
        val = tk.Label(row, text=fmt.format(var.get()), bg=self.colors['card'],
                       fg=self.colors['primary'], font=('Arial', 8), width=5)
        val.pack(side=tk.RIGHT)
        s = ttk.Scale(row, from_=frm, to=to, variable=var, orient='horizontal',
                      command=lambda _v, l=val, f=fmt, vv=var: l.config(text=f.format(vv.get())))
        s.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        return s

    def _toggle(self, parent, text, var):
        tk.Checkbutton(parent, text=text, variable=var, bg=self.colors['card'],
                       fg='white', selectcolor=self.colors['card'],
                       activebackground=self.colors['card'], activeforeground='white',
                       font=('Arial', 8), anchor='w').pack(anchor='w', padx=10, pady=1)

    # ---- UI -----------------------------------------------------------------
    def init_ui(self):
        self.main_frame = tk.Frame(self.root, bg=self.colors['bg'])
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # ---------- LEFT ----------
        self.left_panel = tk.Frame(self.main_frame, width=290, bg=self.colors['panel'])
        self.left_panel.pack(side=tk.LEFT, fill=tk.Y)
        self.left_panel.pack_propagate(False)

        tk.Label(self.left_panel, text="🎭 DEEPFAKE ULTRA", font=('Arial', 15, 'bold'),
                 bg=self.colors['panel'], fg='white').pack(pady=(12, 0))
        tk.Label(self.left_panel, text="PRO 7.5", font=('Arial', 11),
                 bg=self.colors['panel'], fg=self.colors['primary']).pack(pady=(0, 8))

        self.status_var = tk.StringVar(value="⚡ Loading AI...")
        tk.Label(self.left_panel, textvariable=self.status_var, font=('Arial', 9),
                 bg=self.colors['panel'], fg=self.colors['warning']).pack(pady=4)

        self.load_btn = tk.Button(self.left_panel, text="📁 LOAD FACE IMAGE",
                                  command=self.load_face_image, state='disabled',
                                  bg='#0066cc', fg='white', font=('Arial', 10, 'bold'),
                                  relief='raised', padx=8, pady=5)
        self.load_btn.pack(pady=6, padx=18, fill=tk.X)

        pv = self._card(self.left_panel, "FACE PREVIEW")
        self.face_label = tk.Label(pv, text="No face loaded\n\nFoto frontale nitida",
                                   bg='#000033', fg='#8888ff', font=('Arial', 9),
                                   width=30, height=8)
        self.face_label.pack(pady=8, padx=8)

        self.swap_btn = tk.Button(self.left_panel, text="🔴 SWAP OFF",
                                  command=self.toggle_swap, state='disabled',
                                  bg='#cc0000', fg='white', font=('Arial', 12, 'bold'),
                                  relief='raised', padx=8, pady=8)
        self.swap_btn.pack(pady=6, padx=18, fill=tk.X)

        src = self._card(self.left_panel, "SOURCE / CAPTURE")
        brow = tk.Frame(src, bg=self.colors['card']); brow.pack(fill=tk.X, padx=8, pady=4)
        tk.Button(brow, text="📷 Cam", command=self.use_camera, bg='#334', fg='white',
                  font=('Arial', 8, 'bold')).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        tk.Button(brow, text="🎬 Video", command=self.load_video_file, bg='#334',
                  fg='white', font=('Arial', 8, 'bold')).pack(side=tk.LEFT, expand=True,
                                                              fill=tk.X, padx=2)
        brow2 = tk.Frame(src, bg=self.colors['card']); brow2.pack(fill=tk.X, padx=8, pady=(0, 6))
        tk.Button(brow2, text="📸 Snapshot", command=self.snapshot, bg='#0088aa',
                  fg='white', font=('Arial', 8, 'bold')).pack(side=tk.LEFT, expand=True,
                                                             fill=tk.X, padx=2)
        self.rec_btn = tk.Button(brow2, text="⏺ REC", command=self.toggle_record,
                                 bg='#aa0044', fg='white', font=('Arial', 8, 'bold'))
        self.rec_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        self.export_btn = tk.Button(src, text="🎞 EXPORT VIDEO HQ (offline)",
                                    command=self.export_video, bg='#6a0dad', fg='white',
                                    font=('Arial', 8, 'bold'))
        self.export_btn.pack(fill=tk.X, padx=8, pady=(0, 6))

        st = self._card(self.left_panel, "PERFORMANCE")
        self.fps_label = tk.Label(st, text="FPS: 0", font=('Arial', 22),
                                  bg=self.colors['card'], fg='#00ff00')
        self.fps_label.pack(pady=6)
        self.cpu_label = tk.Label(st, text="CPU: 0%", bg=self.colors['card'], fg='white')
        self.cpu_label.pack()
        self.ram_label = tk.Label(st, text="RAM: 0%", bg=self.colors['card'], fg='white')
        self.ram_label.pack(pady=(0, 8))

        # ---------- CENTER ----------
        self.center_panel = tk.Frame(self.main_frame, bg=self.colors['bg'])
        self.center_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        vb = tk.Frame(self.center_panel, bg=self.colors['primary'])
        vb.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        vf = tk.Frame(vb, bg='black'); vf.pack(padx=1, pady=1, fill=tk.BOTH, expand=True)
        tk.Label(vf, text="LIVE PREVIEW", bg='black', fg='white',
                 font=('Arial', 12, 'bold')).pack(pady=4)
        self.video_label = tk.Label(vf, bg='black')
        self.video_label.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        # ---------- RIGHT ----------
        self.right_panel = tk.Frame(self.main_frame, width=320, bg=self.colors['panel'])
        self.right_panel.pack(side=tk.RIGHT, fill=tk.Y)
        self.right_panel.pack_propagate(False)

        md = self._card(self.right_panel, "PROCESSING MODE")
        self.mode_var = tk.StringVar(value='balanced')
        mrow = tk.Frame(md, bg=self.colors['card']); mrow.pack(fill=tk.X, padx=6, pady=2)
        for text, val in [("⚡Fast", 'fast'), ("⚖Balanced", 'balanced'), ("🎯Quality", 'quality')]:
            tk.Radiobutton(mrow, text=text, variable=self.mode_var, value=val,
                           bg=self.colors['card'], fg='white', selectcolor=self.colors['card'],
                           activebackground=self.colors['card'], activeforeground='white',
                           font=('Arial', 8)).pack(side=tk.LEFT, expand=True)
        drow = tk.Frame(md, bg=self.colors['card']); drow.pack(fill=tk.X, padx=8, pady=(2, 6))
        tk.Label(drow, text="Detector size:", bg=self.colors['card'], fg='white',
                 font=('Arial', 8)).pack(side=tk.LEFT)
        self.detsize_combo = ttk.Combobox(drow, values=['256', '320', '512', '640'],
                                          state='readonly', width=6)
        self.detsize_combo.set(str(config['det_size']))
        self.detsize_combo.pack(side=tk.RIGHT)
        self.detsize_combo.bind('<<ComboboxSelected>>', self.on_detsize)

        pre = self._card(self.right_panel, "PRESETS")
        prow = tk.Frame(pre, bg=self.colors['card']); prow.pack(fill=tk.X, padx=8, pady=(0, 6))
        for text, name, bg in [("🗣 Talking", 'talking', '#0a7'),
                               ("💎 Quality", 'quality', '#07a'),
                               ("⚡ Speed", 'speed', '#a70')]:
            tk.Button(prow, text=text, command=lambda n=name: self.apply_preset(n),
                      bg=bg, fg='white', font=('Arial', 8, 'bold')).pack(
                          side=tk.LEFT, expand=True, fill=tk.X, padx=2)

        adj = self._card(self.right_panel, "ADJUSTMENTS")
        self.v_thresh = tk.DoubleVar(value=config['swap_threshold'])
        self.v_mask = tk.DoubleVar(value=config['mask_size'])
        self.v_feather = tk.DoubleVar(value=config['feather'])
        self.v_color = tk.DoubleVar(value=config['color_strength'])
        self.v_sharpen = tk.DoubleVar(value=config['sharpen'])
        self.v_smooth = tk.DoubleVar(value=config['smooth'])
        self.v_keepmouth = tk.DoubleVar(value=config['keep_mouth'])
        self.v_stabilize = tk.DoubleVar(value=config['stabilize'])
        self.v_forehead = tk.DoubleVar(value=config['forehead'])
        self.v_occlusion = tk.DoubleVar(value=config['occlusion'])
        self.v_matchthresh = tk.DoubleVar(value=config['match_thresh'])
        self._slider(adj, "Swap thresh", self.v_thresh, 0.20, 0.70)
        self._slider(adj, "Mask size", self.v_mask, 0.60, 1.30)
        self._slider(adj, "Forehead", self.v_forehead, 0.0, 0.60)
        self._slider(adj, "Feather", self.v_feather, 0.02, 0.15)
        self._slider(adj, "Color match", self.v_color, 0.0, 1.0)
        self._slider(adj, "Sharpen", self.v_sharpen, 0.0, 1.0)
        self._slider(adj, "Skin smooth", self.v_smooth, 0.0, 1.0)
        self._slider(adj, "Keep mouth", self.v_keepmouth, 0.0, 1.0)
        self._slider(adj, "Occlusion", self.v_occlusion, 0.0, 1.0)
        self._slider(adj, "Stabilize", self.v_stabilize, 0.0, 0.90)
        self._slider(adj, "Match thresh", self.v_matchthresh, 0.20, 0.70)

        opt = self._card(self.right_panel, "OPTIONS")
        self.v_realistic = tk.BooleanVar(value=config['realistic_blend'])
        self.v_precise = tk.BooleanVar(value=config['precise_mask'])
        self.v_multi = tk.BooleanVar(value=config['multi_face'])
        self.v_mirror = tk.BooleanVar(value=config['mirror'])
        self.v_enhance = tk.BooleanVar(value=False)
        self.v_match = tk.BooleanVar(value=False)
        self.v_occluder = tk.BooleanVar(value=False)
        self.v_bbox = tk.BooleanVar(value=True)
        self.v_fps = tk.BooleanVar(value=True)
        self._toggle(opt, "Realistic blend (feather+color)", self.v_realistic)
        self._toggle(opt, "Precise mask (landmark, segue mascella)", self.v_precise)
        self._toggle(opt, "Multi-face (swap tutti i volti)", self.v_multi)
        self._toggle(opt, "Mirror (specchia)", self.v_mirror)
        self.enhance_cb = tk.Checkbutton(opt, text="Enhancer GFPGAN (lento, HQ)",
                                         variable=self.v_enhance, command=self.on_enhance_toggle,
                                         bg=self.colors['card'], fg='white',
                                         selectcolor=self.colors['card'],
                                         activebackground=self.colors['card'],
                                         activeforeground='white', font=('Arial', 8), anchor='w')
        self.enhance_cb.pack(anchor='w', padx=10, pady=1)
        self.occluder_cb = tk.Checkbutton(opt, text="Occluder AI (mani/oggetti sul viso)",
                                          variable=self.v_occluder, command=self.on_occluder_toggle,
                                          bg=self.colors['card'], fg='white',
                                          selectcolor=self.colors['card'],
                                          activebackground=self.colors['card'],
                                          activeforeground='white', font=('Arial', 8), anchor='w')
        self.occluder_cb.pack(anchor='w', padx=10, pady=1)
        mrow2 = tk.Frame(opt, bg=self.colors['card']); mrow2.pack(fill=tk.X, padx=10, pady=1)
        tk.Checkbutton(mrow2, text="Match target (solo 1 persona)",
                       variable=self.v_match, command=self.on_match_toggle,
                       bg=self.colors['card'], fg='white', selectcolor=self.colors['card'],
                       activebackground=self.colors['card'], activeforeground='white',
                       font=('Arial', 8), anchor='w').pack(side=tk.LEFT)
        tk.Button(mrow2, text="🎯 Target", command=self.load_target_image,
                  bg='#663399', fg='white', font=('Arial', 7, 'bold')).pack(side=tk.RIGHT)
        self._toggle(opt, "Show bounding box", self.v_bbox)
        self._toggle(opt, "Show FPS", self.v_fps)
        crow = tk.Frame(opt, bg=self.colors['card']); crow.pack(fill=tk.X, padx=10, pady=4)
        tk.Label(crow, text="Box color:", bg=self.colors['card'], fg='white',
                 font=('Arial', 8)).pack(side=tk.LEFT)
        self.color_combo = ttk.Combobox(crow, values=list(self.COLOR_MAP.keys()),
                                        state='readonly', width=9)
        self.color_combo.set('green'); self.color_combo.pack(side=tk.RIGHT)

        cons = self._card(self.right_panel, "SYSTEM LOG")
        self.console = tk.Text(cons, bg='#0a0a0a', fg='#00ffaa', font=('Consolas', 8),
                               height=10, relief='flat', wrap='word')
        self.console.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        self.bottom_status = tk.Label(self.root, text="Deepfake Ultra Pro 7.5 | Initializing...",
                                      bg='#1a1a2e', fg='white', font=('Arial', 10),
                                      relief='sunken', anchor='w')
        self.bottom_status.pack(side=tk.BOTTOM, fill=tk.X)

        self.root.bind('<Escape>', lambda e: self.quit_app())
        self.root.bind('<space>', lambda e: self.toggle_swap())
        self.root.bind('f', lambda e: self.toggle_fullscreen())
        self.root.bind('r', lambda e: self.reset_camera())
        self.root.bind('s', lambda e: self.snapshot())
        self.root.bind('v', lambda e: self.toggle_record())
        self.root.bind('m', lambda e: self.v_multi.set(not self.v_multi.get()))

    # ---- param sync (main thread) ------------------------------------------
    def _sync_params(self):
        try:
            self.params.update({
                'swap_threshold': float(self.v_thresh.get()),
                'mask_size': float(self.v_mask.get()),
                'feather': float(self.v_feather.get()),
                'color_strength': float(self.v_color.get()),
                'sharpen': float(self.v_sharpen.get()),
                'smooth': float(self.v_smooth.get()),
                'multi_face': bool(self.v_multi.get()),
                'realistic_blend': bool(self.v_realistic.get()),
                'mirror': bool(self.v_mirror.get()),
                'precise_mask': bool(self.v_precise.get()),
                'keep_mouth': float(self.v_keepmouth.get()),
                'stabilize': float(self.v_stabilize.get()),
                'forehead': float(self.v_forehead.get()),
                'occlusion': float(self.v_occlusion.get()),
                'match': bool(self.v_match.get()),
                'match_thresh': float(self.v_matchthresh.get()),
                'enhance': bool(self.v_enhance.get()) and self.engine is not None
                and self.engine.enhancer_ready,
                'occluder': bool(self.v_occluder.get()) and self.engine is not None
                and self.engine.occluder_ready,
            })
        except Exception:
            pass

    # ---- startup ------------------------------------------------------------
    def start_system(self):
        threading.Thread(target=self.initialize_models, daemon=True).start()

    def initialize_models(self):
        self.log("⚡ Initializing AI models...")
        self.status_var.set("⚡ Loading AI models...")
        try:
            if not os.path.exists(config['model_path']):
                self.log(f"❌ Model not found: {config['model_path']}")
                self.log("📥 github.com/deepinsight/insightface/releases")
                self.status_var.set("❌ Model missing")
                return
            self.engine = FaceEngine(config['model_path'])
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
            self.log(f"❌ Init error: {e}")
            self.status_var.set("❌ Init failed")

    def start_camera_thread(self):
        threading.Thread(target=self.initialize_camera, daemon=True).start()

    def initialize_camera(self):
        self.log("📷 Initializing camera...")
        self.source_mode = 'camera'
        for cam_id in range(3):
            try:
                cap = cv2.VideoCapture(cam_id, cv2.CAP_DSHOW) if os.name == 'nt' \
                    else cv2.VideoCapture(cam_id)
                if cap.isOpened():
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                    cap.set(cv2.CAP_PROP_FPS, 60)
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    self.cap = cap
                    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    self.log(f"✅ Camera {cam_id}: {w}x{h}")
                    self.status_var.set("✅ Camera ready")
                    self.start_processing_threads()
                    return
                cap.release()
            except Exception:
                continue
        self.log("❌ No camera found")
        self.status_var.set("❌ No camera")

    _threads_started = False

    def start_processing_threads(self):
        if self._threads_started:
            return
        self._threads_started = True
        threading.Thread(target=self.capture_loop, daemon=True).start()
        threading.Thread(target=self.process_loop, daemon=True, name="Inference").start()
        self.log("⚡ Pipeline started (1 capture + 1 inference)")

    # ---- capture ------------------------------------------------------------
    def capture_loop(self):
        while self.running:
            cap = self.cap
            if cap is None:
                time.sleep(0.02); continue
            try:
                ok, frame = cap.read()
                if not ok:
                    if self.source_mode == 'video':
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)  # loop video
                        continue
                    time.sleep(0.003); continue
                if self.capture_queue.full():
                    try:
                        self.capture_queue.get_nowait()
                    except queue.Empty:
                        pass
                self.capture_queue.put_nowait(frame)
                if self.source_mode == 'video':
                    time.sleep(1.0 / 30.0)  # non correre nei file video
            except Exception:
                time.sleep(0.005)

    # ---- process ------------------------------------------------------------
    def process_loop(self):
        while self.running:
            try:
                frame = self.capture_queue.get(timeout=0.05)
            except queue.Empty:
                continue
            try:
                p = self.params
                mode = self.mode_var.get()
                frame = cv2.resize(frame, MODE_RES.get(mode, (854, 480)))
                if p['mirror']:
                    frame = cv2.flip(frame, 1)
                stride = config['fast_detect_stride'] if mode == 'fast' else 1
                result = frame

                if self.swap_active and self.models_ready and self.source_face is not None:
                    match_on = (p.get('match') and self.target_ref is not None
                                and self.engine.matcher_ready)
                    if match_on:
                        faces = self.engine.detect_match(frame)
                    else:
                        faces = self.engine.detect_live(frame, stride=stride)
                    faces = [f for f in faces if f.det_score >= p['swap_threshold']]
                    if match_on and faces:
                        # sostituisci SOLO chi somiglia alla persona-target
                        ref = self.target_ref
                        mt = float(p.get('match_thresh', 0.35))
                        faces = [f for f in faces
                                 if getattr(f, 'normed_embedding', None) is not None
                                 and float(np.dot(f.normed_embedding, ref)) >= mt]
                    if faces:
                        if not p['multi_face']:
                            faces = [max(faces, key=lambda f: f.det_score)]
                        if p['stabilize'] > 0:
                            faces = self.stabilizer.update(faces, p['stabilize'])
                        self._coast_faces = faces
                        self._coast = 0
                    elif (self._coast_faces is not None
                          and self._coast < config['coast_frames']):
                        # il detect ha "saltato" un frame: tieni l'ultima posizione
                        # (niente scatto/flicker "a trattini")
                        faces = self._coast_faces
                        self._coast += 1
                    else:
                        self._coast_faces = None
                    if faces:
                        for face in faces:
                            result = self.engine.swap_one(result, face, self.source_face, p)
                        if self.v_bbox.get():
                            color = self.COLOR_MAP.get(self.color_combo.get(), (0, 255, 0))
                            for face in faces:
                                b = face.bbox.astype(int)
                                cv2.rectangle(result, (b[0], b[1]), (b[2], b[3]), color, 2)
                                cv2.putText(result, f"{face.det_score:.2f}", (b[0], b[1] - 5),
                                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

                if self.v_fps.get():
                    cv2.putText(result, f"FPS: {self.monitor.current_fps}", (10, 28),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

                self.monitor.update_fps()
                self.last_result = result
                if self.recording:
                    self._write_frame(result)

                if self.display_queue.full():
                    try:
                        self.display_queue.get_nowait()
                    except queue.Empty:
                        pass
                self.display_queue.put_nowait(result)
            except Exception as e:
                self.log(f"⚠️ Process error: {str(e)[:60]}")

    # ---- UI pumps -----------------------------------------------------------
    def display_pump(self):
        if not self.running:
            return
        self._sync_params()
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
        rec = " | ⏺REC" if self.recording else ""
        self.bottom_status.config(
            text=f"Deepfake Ultra Pro 7.5 | FPS: {s['fps']} (avg {s['avg_fps']}) | "
                 f"Swap: {'ON' if self.swap_active else 'OFF'} | "
                 f"Multi: {'ON' if self.params['multi_face'] else 'OFF'} | "
                 f"Mode: {self.mode_var.get().upper()} | "
                 f"CPU {s['cpu']:.0f}% RAM {s['ram']:.0f}%{rec}")
        self.root.after(500, self.stats_pump)

    # ---- actions: source ----------------------------------------------------
    def load_face_image(self):
        if not self.models_ready:
            messagebox.showwarning("Wait", "AI models still loading")
            return
        fp = filedialog.askopenfilename(
            title="Select face image",
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp"),
                       ("All files", "*.*")])
        if not fp:
            return
        try:
            self.log(f"📁 Loading: {os.path.basename(fp)}")
            img = cv2.imread(fp)
            if img is None:
                messagebox.showerror("Error", "Cannot read image file"); return
            face = self.engine.detect_source(img)
            if face is None:
                messagebox.showwarning("No face", "No face detected in image"); return
            self.source_face = face
            self.source_image = img
            self.face_loaded = True
            preview = img.copy()
            b = face.bbox.astype(int)
            cv2.rectangle(preview, (b[0], b[1]), (b[2], b[3]), (0, 255, 0), 3)
            pil = Image.fromarray(cv2.cvtColor(preview, cv2.COLOR_BGR2RGB))
            pil.thumbnail((250, 250))
            photo = ImageTk.PhotoImage(image=pil)
            self.face_label.config(image=photo, text=""); self.face_label.image = photo
            self.status_var.set("✅ Face loaded")
            self.log(f"✅ Face loaded (score: {face.det_score:.3f})")
            self.swap_btn.config(state='normal')
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load: {e}")
            self.log(f"❌ Load error: {e}")

    def use_camera(self):
        if self.cap:
            self.cap.release(); self.cap = None
        threading.Thread(target=self.initialize_camera, daemon=True).start()

    def load_video_file(self):
        fp = filedialog.askopenfilename(title="Select video",
                                        filetypes=[("Video", "*.mp4 *.avi *.mov *.mkv"),
                                                   ("All files", "*.*")])
        if not fp:
            return
        try:
            cap = cv2.VideoCapture(fp)
            if not cap.isOpened():
                messagebox.showerror("Error", "Cannot open video"); return
            if self.cap:
                self.cap.release()
            self.cap = cap
            self.source_mode = 'video'
            self.video_path = fp
            self.log(f"🎬 Video: {os.path.basename(fp)}")
            self.status_var.set("✅ Video loaded")
            self.start_processing_threads()
        except Exception as e:
            self.log(f"❌ Video error: {e}")

    # ---- actions: swap ------------------------------------------------------
    def toggle_swap(self):
        if not self.face_loaded:
            messagebox.showwarning("No face", "Load a face first"); return
        self.swap_active = not self.swap_active
        if self.swap_active:
            self.swap_btn.config(text="✅ SWAP ON", bg='#00aa00')
            self.log("⚡ Face swap ACTIVATED")
        else:
            self.swap_btn.config(text="🔴 SWAP OFF", bg='#cc0000')
            self._coast_faces = None
            self._coast = 0
            self.log("⚡ Face swap DEACTIVATED")

    def on_detsize(self, _e=None):
        if not self.models_ready:
            return
        n = int(self.detsize_combo.get())
        self.log(f"🔧 Detector size → {n}")
        threading.Thread(target=lambda: self.engine.set_det_size(n), daemon=True).start()

    def on_enhance_toggle(self):
        if not self.v_enhance.get():
            return
        if not self.models_ready:
            self.v_enhance.set(False); return
        self.log("⏳ Carico GFPGAN (prima volta: può scaricare il modello)...")
        # load in background per non bloccare la UI
        threading.Thread(target=self._load_enhancer_bg, daemon=True).start()

    def _load_enhancer_bg(self):
        ok, msg = self.engine.try_load_enhancer()
        self.log(("✅ " if ok else "⚠️ ") + msg)
        if ok:
            self.v_realistic.set(True)  # l'enhance sul crop gira nel blend realistico
        else:
            self.v_enhance.set(False)

    def on_occluder_toggle(self):
        if not self.v_occluder.get():
            return
        if not self.models_ready:
            self.v_occluder.set(False); return
        self.log("⏳ Carico l'occluder AI (prima volta: scarica ~fewMB)...")
        threading.Thread(target=self._load_occluder_bg, daemon=True).start()

    def _load_occluder_bg(self):
        ok, msg = self.engine.try_load_occluder()
        self.log(("✅ " if ok else "⚠️ ") + msg)
        if ok:
            self.v_realistic.set(True)  # l'occluder agisce nel blend realistico
        else:
            self.v_occluder.set(False)

    def load_target_image(self):
        """Carica la foto della PERSONA DA SOSTITUIRE (target). In match mode
        solo i volti che le somigliano verranno swappati."""
        if not self.models_ready:
            messagebox.showwarning("Aspetta", "Modelli in caricamento"); return
        fp = filedialog.askopenfilename(title="Foto della persona da sostituire",
                                        filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp"),
                                                   ("All files", "*.*")])
        if not fp:
            return
        try:
            img = cv2.imread(fp)
            if img is None:
                messagebox.showerror("Error", "Cannot read image file"); return
            face = self.engine.detect_source(img)  # include l'embedding
            emb = getattr(face, 'normed_embedding', None) if face is not None else None
            if emb is None:
                messagebox.showwarning("No face", "Nessun volto/embedding nell'immagine"); return
            self.target_ref = np.asarray(emb, np.float32)
            self.log(f"🎯 Target impostato: {os.path.basename(fp)}")
            self.v_match.set(True)
            self.on_match_toggle()
        except Exception as e:
            self.log(f"❌ Target error: {e}")

    def on_match_toggle(self):
        if not self.v_match.get():
            return
        if self.target_ref is None:
            self.log("⚠️ Match: carica prima una foto 🎯 Target")
            self.v_match.set(False); return
        self.log("⏳ Preparo il match d'identità...")
        threading.Thread(target=self._load_matcher_bg, daemon=True).start()

    def _load_matcher_bg(self):
        ok, msg = self.engine.ensure_matcher()
        self.log(("✅ " if ok else "⚠️ ") + msg)
        if not ok:
            self.v_match.set(False)

    def apply_preset(self, name):
        """Imposta gli slider su combinazioni collaudate."""
        presets = {
            # realismo del parlato: bocca reale, maschera precisa, fronte coperta
            'talking': dict(mode='balanced', det=320, thresh=0.35, mask=1.0,
                            forehead=0.32, feather=0.09, color=0.85, sharpen=0.20,
                            smooth=0.30, keep=0.55, stab=0.55, occ=0.40,
                            precise=True, multi=False),
            # massima fedeltà (adatto a GPU tipo RTX 4070)
            'quality': dict(mode='quality', det=512, thresh=0.35, mask=1.05,
                            forehead=0.35, feather=0.07, color=0.90, sharpen=0.25,
                            smooth=0.35, keep=0.30, stab=0.50, occ=0.50,
                            precise=True, multi=True),
            # massimi FPS
            'speed': dict(mode='fast', det=256, thresh=0.40, mask=1.0,
                          forehead=0.25, feather=0.05, color=0.70, sharpen=0.10,
                          smooth=0.0, keep=0.20, stab=0.35, occ=0.0,
                          precise=True, multi=False),
        }
        p = presets.get(name)
        if not p:
            return
        self.mode_var.set(p['mode'])
        self.detsize_combo.set(str(p['det']))
        self.on_detsize()
        self.v_thresh.set(p['thresh']); self.v_mask.set(p['mask'])
        self.v_forehead.set(p['forehead']); self.v_occlusion.set(p['occ'])
        self.v_feather.set(p['feather']); self.v_color.set(p['color'])
        self.v_sharpen.set(p['sharpen']); self.v_smooth.set(p['smooth'])
        self.v_keepmouth.set(p['keep']); self.v_stabilize.set(p['stab'])
        self.v_precise.set(p['precise']); self.v_multi.set(p['multi'])
        self._sync_params()
        self.log(f"🎚️ Preset '{name}' applicato")

    # ---- actions: export offline HQ -----------------------------------------
    def export_video(self):
        """Processa un file video OFFLINE alla risoluzione nativa, ogni frame,
        con le impostazioni correnti → qualità massima (niente vincolo FPS)."""
        if not self.models_ready or self.source_face is None:
            messagebox.showwarning("Aspetta", "Carica prima una faccia e i modelli")
            return
        inp = filedialog.askopenfilename(title="Video da processare",
                                         filetypes=[("Video", "*.mp4 *.avi *.mov *.mkv"),
                                                    ("All files", "*.*")])
        if not inp:
            return
        threading.Thread(target=self._export_worker, args=(inp,), daemon=True).start()

    def _export_worker(self, inp):
        cap = cv2.VideoCapture(inp)
        if not cap.isOpened():
            self.log("❌ Export: impossibile aprire il video"); return
        fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self._ensure_output()
        out_path = os.path.join(config['output_dir'],
                                f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4")
        writer = cv2.VideoWriter(out_path, cv2.VideoWriter_fourcc(*'mp4v'), fps, (w, h))
        if not writer.isOpened():
            self.log("❌ Export: writer non disponibile"); cap.release(); return

        self.export_btn.config(state='disabled')
        self.log(f"🎞 Export avviato: {os.path.basename(inp)} ({w}x{h}, {total} frame)")
        p = dict(self.params)          # snapshot impostazioni
        stab = FaceStabilizer()        # stabilizer separato dal live
        i = 0
        while self.running:
            ok, frame = cap.read()
            if not ok:
                break
            i += 1
            result = frame
            try:
                faces = self.engine.detect(frame)
                faces = [f for f in faces if f.det_score >= p['swap_threshold']]
                if faces:
                    if not p['multi_face']:
                        faces = [max(faces, key=lambda f: f.det_score)]
                    if p['stabilize'] > 0:
                        faces = stab.update(faces, p['stabilize'])
                    for face in faces:
                        result = self.engine.swap_one(result, face, self.source_face, p)
            except Exception:
                pass
            writer.write(result)
            if total and i % 10 == 0:
                pct = 100.0 * i / total
                self.root.after(0, lambda v=pct: self.status_var.set(f"⏳ Export {v:.0f}%"))
        writer.release(); cap.release()
        self.root.after(0, lambda: self.status_var.set("✅ Export completato"))
        self.root.after(0, lambda: self.export_btn.config(state='normal'))
        self.log(f"✅ Export salvato: {out_path} ({i} frame) — video senza audio")

    # ---- actions: capture ---------------------------------------------------
    def _ensure_output(self):
        os.makedirs(config['output_dir'], exist_ok=True)

    def snapshot(self):
        if self.last_result is None:
            self.log("⚠️ No frame to save"); return
        self._ensure_output()
        path = os.path.join(config['output_dir'],
                            f"snap_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
        try:
            cv2.imwrite(path, self.last_result)
            self.log(f"📸 Saved: {path}")
        except Exception as e:
            self.log(f"❌ Snapshot error: {e}")

    def toggle_record(self):
        if self.recording:
            self.recording = False
            if self.writer:
                self.writer.release(); self.writer = None
            self.rec_btn.config(text="⏺ REC", bg='#aa0044')
            self.log("⏹ Recording stopped")
        else:
            if self.last_result is None:
                self.log("⚠️ No frame to record"); return
            self._ensure_output()
            path = os.path.join(config['output_dir'],
                                f"rec_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4")
            h, w = self.last_result.shape[:2]
            self.rec_size = (w, h)
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            self.writer = cv2.VideoWriter(path, fourcc, config['record_fps'], (w, h))
            if not self.writer.isOpened():
                self.log("❌ Cannot open video writer"); self.writer = None; return
            self.recording = True
            self.rec_btn.config(text="⏹ STOP", bg='#ff2266')
            self.log(f"⏺ Recording → {path}")

    def _write_frame(self, frame):
        try:
            if self.rec_size and (frame.shape[1], frame.shape[0]) != self.rec_size:
                frame = cv2.resize(frame, self.rec_size)
            if self.writer:
                self.writer.write(frame)
        except Exception:
            pass

    # ---- misc ---------------------------------------------------------------
    def toggle_fullscreen(self):
        self.root.attributes('-fullscreen', not self.root.attributes('-fullscreen'))

    def reset_camera(self):
        self.use_camera(); self.log("🔄 Camera reset")

    def log(self, message):
        ts = datetime.now().strftime("%H:%M:%S")
        try:
            self.console.insert(tk.END, f"[{ts}] {message}\n")
            self.console.see(tk.END)
            if int(self.console.index('end-1c').split('.')[0]) > 200:
                self.console.delete("1.0", "50.0")
        except Exception:
            print(f"[{ts}] {message}")

    def quit_app(self):
        self.running = False
        if self.recording and self.writer:
            self.writer.release()
        if self.cap:
            self.cap.release()
        try:
            self.root.quit(); self.root.destroy()
        except Exception:
            pass
        print("\n" + "=" * 80 + "\n👋 Application closed\n" + "=" * 80)


# ============================================================
# 🚀 MAIN
# ============================================================
def main():
    print("=" * 80)
    print("🚀 DEEPFAKE ULTRA PRO 7.5 - STARTING")
    ram = f"{psutil.virtual_memory().percent}%" if _HAS_PSUTIL else "n/a"
    print(f"🔥 PID {os.getpid()} | CPU {_cpu_count()} | RAM {ram}")
    print("=" * 80)

    if not os.path.exists(config['model_path']):
        print(f"\n⚠️  Modello '{config['model_path']}' non trovato!")
        print("   github.com/deepinsight/insightface/releases")
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
    root.geometry(f"{ww}x{wh}+{max(0, (sw - ww) // 2)}+{max(0, (sh - wh) // 2)}")
    root.protocol("WM_DELETE_WINDOW", app.quit_app)
    root.mainloop()


if __name__ == "__main__":
    main()
