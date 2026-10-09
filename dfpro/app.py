"""Finestra principale: UI moderna + pipeline di cattura/inferenza/display.

La logica di inferenza è identica alla versione monolitica già verificata;
cambia l'interfaccia (widget custom) e l'organizzazione in moduli.
"""
import os
import queue
import threading
import time
from datetime import datetime

import cv2
import numpy as np
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk

from . import theme as T
from . import widgets as W
from .config import (BOX_COLORS, MODE_RES, PARAM_KEYS, PRESETS, config,
                     _cpu_count)
from .engine import FaceEngine
from .tracking import FaceStabilizer, PerformanceMonitor

VERSION = '8.0'


class DeepfakeUltraPro:
    # ---------------------------------------------------------------- setup
    def __init__(self, root):
        self.root = root
        self.root.title(f'DEEPFAKE ULTRA PRO {VERSION}')
        self.root.geometry('1720x980')
        self.root.minsize(1280, 820)
        self.root.configure(bg=T.BG)
        T.apply_ttk(self.root)

        # stato
        self.running = True
        self.swap_active = False
        self.models_ready = False
        self.face_loaded = False

        self.monitor = PerformanceMonitor()
        self.engine = None
        self.source_face = None
        self.source_image = None
        self.target_ref = None

        self.cap = None
        self.source_mode = 'camera'
        self.video_path = None

        self.last_result = None
        self.recording = False
        self.writer = None
        self.rec_size = None

        self.params = {k: config[k] for k in PARAM_KEYS}
        self.params['enhance'] = False
        self.params['occluder'] = False
        self.stabilizer = FaceStabilizer()
        self._coast_faces = None
        self._coast = 0
        self._threads_started = False

        self.capture_queue = queue.Queue(maxsize=2)
        self.display_queue = queue.Queue(maxsize=2)

        self.init_ui()
        self.start_system()
        self.root.after(50, self.display_pump)
        self.root.after(500, self.stats_pump)
        print('✅ System initialized')

    # ------------------------------------------------------------------- UI
    def init_ui(self):
        self._build_header()
        main = tk.Frame(self.root, bg=T.BG)
        main.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 8))
        self._build_left(main)
        self._build_right(main)
        self._build_center(main)      # dopo i laterali: prende lo spazio restante
        self._build_statusbar()
        self._bind_keys()

    # ---- header
    def _build_header(self):
        h = tk.Frame(self.root, bg=T.BG, height=58)
        h.pack(fill=tk.X, padx=12, pady=(10, 8))
        h.pack_propagate(False)

        logo = tk.Canvas(h, width=34, height=34, bg=T.BG, highlightthickness=0)
        logo.pack(side=tk.LEFT, padx=(0, 10))
        T.round_rect(logo, 1, 1, 33, 33, 10, fill=T.mix(T.BG, T.ACCENT, 0.22),
                     outline=T.ACCENT)
        logo.create_text(17, 17, text='◈', fill=T.ACCENT, font=T.f(16, 'bold'))

        tit = tk.Frame(h, bg=T.BG)
        tit.pack(side=tk.LEFT)
        tk.Label(tit, text='DEEPFAKE ULTRA PRO', bg=T.BG, fg=T.TEXT,
                 font=T.f(15, 'bold')).pack(anchor='w')
        tk.Label(tit, text=f'v{VERSION}  ·  real-time face swap',
                 bg=T.BG, fg=T.TEXT_MUTE, font=T.f(8)).pack(anchor='w')

        right = tk.Frame(h, bg=T.BG)
        right.pack(side=tk.RIGHT)
        self.badge_status = W.Badge(right, 'LOADING', T.AMBER, bg=T.BG)
        self.badge_status.pack(side=tk.RIGHT, padx=3)
        self.badge_provider = W.Badge(right, '…', T.TEXT_MUTE, bg=T.BG)
        self.badge_provider.pack(side=tk.RIGHT, padx=3)
        self.badge_rec = W.Badge(right, '● REC', T.ROSE, bg=T.BG)
        # mostrato solo durante la registrazione

    # ---- colonna sinistra
    def _build_left(self, parent):
        col = tk.Frame(parent, bg=T.BG, width=306)
        col.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        col.pack_propagate(False)

        # --- sorgente
        c = W.Card(col, 'volto sorgente', accent=T.CYAN)
        c.pack(fill=tk.X, pady=(0, 10))
        self.face_label = tk.Label(c.body, text='Nessun volto\n\nFoto frontale nitida',
                                   bg=T.SUNKEN, fg=T.TEXT_MUTE, font=T.f(9),
                                   height=8, bd=0,
                                   highlightthickness=1, highlightbackground=T.BORDER_SOFT)
        self.face_label.pack(fill=tk.X, pady=(0, 8))
        self.btn_load = W.NeoButton(c.body, '📁  CARICA VOLTO', self.load_face_image,
                                    kind='primary', h=34, width=10)
        self.btn_load.pack(fill=tk.X)
        self.btn_load.set_enabled(False)

        row = tk.Frame(c.body, bg=T.SURFACE)
        row.pack(fill=tk.X, pady=(8, 0))
        self.btn_target = W.NeoButton(row, '🎯 Target', self.load_target_image,
                                      kind='ghost', h=28, width=10)
        self.btn_target.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 3))
        self.v_match = tk.BooleanVar(value=False)
        W.NeoSwitch(row, 'solo lui', self.v_match, command=self.on_match_toggle,
                    accent=T.VIOLET).pack(side=tk.LEFT, padx=(3, 0))

        # --- azione
        c2 = W.Card(col, 'swap', accent=T.GREEN)
        c2.pack(fill=tk.X, pady=(0, 10))
        self.btn_swap = W.NeoButton(c2.body, '◉  SWAP OFF', self.toggle_swap,
                                    kind='danger', h=46, width=10,
                                    font=T.f(12, 'bold'))
        self.btn_swap.pack(fill=tk.X)
        self.btn_swap.set_enabled(False)

        self.mode_var = tk.StringVar(value='balanced')
        W.Segmented(c2.body, [('⚡ Fast', 'fast'), ('⚖ Balanced', 'balanced'),
                              ('🎯 Quality', 'quality')],
                    self.mode_var, accent=T.AMBER).pack(fill=tk.X, pady=(8, 6))
        prow = tk.Frame(c2.body, bg=T.SURFACE)
        prow.pack(fill=tk.X)
        for txt, name, kind in (('🗣 Talking', 'talking', 'primary'),
                                ('💎 Quality', 'quality', 'accent'),
                                ('⚡ Speed', 'speed', 'ghost')):
            W.NeoButton(prow, txt, lambda n=name: self.apply_preset(n), kind=kind,
                        h=28, width=10).pack(side=tk.LEFT, expand=True,
                                             fill=tk.X, padx=2)

        # --- cattura
        c3 = W.Card(col, 'sorgente & cattura', accent=T.VIOLET)
        c3.pack(fill=tk.X, pady=(0, 10))
        r1 = tk.Frame(c3.body, bg=T.SURFACE)
        r1.pack(fill=tk.X, pady=(0, 5))
        W.NeoButton(r1, '📷 Webcam', self.use_camera, h=28, width=10).pack(
            side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 3))
        W.NeoButton(r1, '🎬 Video', self.load_video_file, h=28, width=10).pack(
            side=tk.LEFT, expand=True, fill=tk.X, padx=(3, 0))
        r2 = tk.Frame(c3.body, bg=T.SURFACE)
        r2.pack(fill=tk.X, pady=(0, 5))
        W.NeoButton(r2, '📸 Snapshot', self.snapshot, h=28, width=10).pack(
            side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 3))
        self.btn_rec = W.NeoButton(r2, '⏺ REC', self.toggle_record, kind='danger',
                                   h=28, width=10)
        self.btn_rec.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(3, 0))
        self.btn_export = W.NeoButton(c3.body, '🎞  EXPORT VIDEO HQ',
                                      self.export_video, kind='accent', h=30,
                                      width=10)
        self.btn_export.pack(fill=tk.X)

        # --- performance
        c4 = W.Card(col, 'performance', accent=T.GREEN)
        c4.pack(fill=tk.X)
        srow = tk.Frame(c4.body, bg=T.SURFACE)
        srow.pack(fill=tk.X)
        self.tile_fps = W.StatTile(srow, 'fps', '0', color=T.GREEN)
        self.tile_fps.pack(side=tk.LEFT, expand=True, anchor='w')
        self.tile_cpu = W.StatTile(srow, 'cpu', '0', '%', color=T.CYAN)
        self.tile_cpu.pack(side=tk.LEFT, expand=True, anchor='w')
        self.tile_ram = W.StatTile(srow, 'ram', '0', '%', color=T.VIOLET)
        self.tile_ram.pack(side=tk.LEFT, expand=True, anchor='w')
        self.spark = W.Sparkline(c4.body, height=44, color=T.GREEN)
        self.spark.pack(fill=tk.X, pady=(8, 0))

    # ---- colonna destra
    def _build_right(self, parent):
        col = tk.Frame(parent, bg=T.BG, width=344)
        col.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        col.pack_propagate(False)

        # variabili slider
        self.v_thresh = tk.DoubleVar(value=config['swap_threshold'])
        self.v_mask = tk.DoubleVar(value=config['mask_size'])
        self.v_forehead = tk.DoubleVar(value=config['forehead'])
        self.v_feather = tk.DoubleVar(value=config['feather'])
        self.v_color = tk.DoubleVar(value=config['color_strength'])
        self.v_colorstab = tk.DoubleVar(value=config['color_stab'])
        self.v_sharpen = tk.DoubleVar(value=config['sharpen'])
        self.v_smooth = tk.DoubleVar(value=config['smooth'])
        self.v_keepmouth = tk.DoubleVar(value=config['keep_mouth'])
        self.v_occlusion = tk.DoubleVar(value=config['occlusion'])
        self.v_stabilize = tk.DoubleVar(value=config['stabilize'])
        self.v_matchthresh = tk.DoubleVar(value=config['match_thresh'])

        card = W.Card(col, 'regolazioni', accent=T.CYAN)
        card.pack(fill=tk.X, pady=(0, 10))
        self.tab_var = tk.StringVar(value='blend')
        W.Segmented(card.body, [('Blend', 'blend'), ('Volto', 'face'),
                                ('Moto', 'motion')],
                    self.tab_var, command=self._show_tab,
                    accent=T.CYAN).pack(fill=tk.X, pady=(0, 8))
        holder = tk.Frame(card.body, bg=T.SURFACE)
        holder.pack(fill=tk.X)
        self._tabs = {}
        for name in ('blend', 'face', 'motion'):
            self._tabs[name] = tk.Frame(holder, bg=T.SURFACE)

        tb = self._tabs['blend']
        W.NeoSlider(tb, 'Mask size', self.v_mask, 0.60, 1.30).pack(fill=tk.X, pady=3)
        W.NeoSlider(tb, 'Forehead', self.v_forehead, 0.0, 0.60,
                    hint='alza se vedi lo stacco sulle sopracciglia').pack(fill=tk.X, pady=3)
        W.NeoSlider(tb, 'Feather', self.v_feather, 0.02, 0.15).pack(fill=tk.X, pady=3)
        W.NeoSlider(tb, 'Color match', self.v_color, 0.0, 1.0).pack(fill=tk.X, pady=3)
        W.NeoSlider(tb, 'Color stab', self.v_colorstab, 0.0, 0.90,
                    hint='anti-flicker della tinta').pack(fill=tk.X, pady=3)

        tf = self._tabs['face']
        W.NeoSlider(tf, 'Keep mouth', self.v_keepmouth, 0.0, 1.0, accent=T.VIOLET,
                    hint='alza quando parli / muovi la lingua').pack(fill=tk.X, pady=3)
        W.NeoSlider(tf, 'Sharpen', self.v_sharpen, 0.0, 1.0, accent=T.VIOLET).pack(fill=tk.X, pady=3)
        W.NeoSlider(tf, 'Skin smooth', self.v_smooth, 0.0, 1.0, accent=T.VIOLET).pack(fill=tk.X, pady=3)
        W.NeoSlider(tf, 'Occlusion', self.v_occlusion, 0.0, 1.0, accent=T.VIOLET,
                    hint='ripiego colore-pelle; per le mani usa Occluder AI').pack(fill=tk.X, pady=3)

        tm = self._tabs['motion']
        W.NeoSlider(tm, 'Stabilize', self.v_stabilize, 0.0, 0.90, accent=T.AMBER,
                    hint='toglie tremolìo e scatti').pack(fill=tk.X, pady=3)
        W.NeoSlider(tm, 'Swap thresh', self.v_thresh, 0.20, 0.70, accent=T.AMBER).pack(fill=tk.X, pady=3)
        W.NeoSlider(tm, 'Match thresh', self.v_matchthresh, 0.20, 0.70, accent=T.AMBER,
                    hint='somiglianza minima col target').pack(fill=tk.X, pady=3)
        drow = tk.Frame(tm, bg=T.SURFACE)
        drow.pack(fill=tk.X, pady=(6, 0))
        tk.Label(drow, text='Detector size', bg=T.SURFACE, fg=T.TEXT_DIM,
                 font=T.f(9)).pack(side=tk.LEFT)
        self.detsize_combo = ttk.Combobox(drow, values=['256', '320', '512', '640'],
                                          state='readonly', width=6,
                                          style='Neo.TCombobox')
        self.detsize_combo.set(str(config['det_size']))
        self.detsize_combo.pack(side=tk.RIGHT)
        self.detsize_combo.bind('<<ComboboxSelected>>', self.on_detsize)
        self._show_tab()

        # --- opzioni
        c2 = W.Card(col, 'opzioni', accent=T.VIOLET)
        c2.pack(fill=tk.X, pady=(0, 10))
        self.v_realistic = tk.BooleanVar(value=config['realistic_blend'])
        self.v_precise = tk.BooleanVar(value=config['precise_mask'])
        self.v_multi = tk.BooleanVar(value=config['multi_face'])
        self.v_mirror = tk.BooleanVar(value=config['mirror'])
        self.v_enhance = tk.BooleanVar(value=False)
        self.v_occluder = tk.BooleanVar(value=False)
        self.v_bbox = tk.BooleanVar(value=True)
        self.v_fps = tk.BooleanVar(value=True)
        sw = [('Realistic blend', self.v_realistic, None),
              ('Precise mask (segue la mascella)', self.v_precise, None),
              ('Occluder AI (mani/oggetti)', self.v_occluder, self.on_occluder_toggle),
              ('Enhancer GFPGAN (HQ)', self.v_enhance, self.on_enhance_toggle),
              ('Multi-face', self.v_multi, None),
              ('Mirror', self.v_mirror, None),
              ('Mostra riquadro', self.v_bbox, None),
              ('Mostra FPS', self.v_fps, None)]
        for text, var, cmd in sw:
            W.NeoSwitch(c2.body, text, var, command=cmd, accent=T.VIOLET,
                        wrap=250).pack(fill=tk.X, pady=2)
        crow = tk.Frame(c2.body, bg=T.SURFACE)
        crow.pack(fill=tk.X, pady=(6, 0))
        tk.Label(crow, text='Colore riquadro', bg=T.SURFACE, fg=T.TEXT_DIM,
                 font=T.f(9)).pack(side=tk.LEFT)
        self.color_combo = ttk.Combobox(crow, values=list(BOX_COLORS),
                                        state='readonly', width=9,
                                        style='Neo.TCombobox')
        self.color_combo.set('green')
        self.color_combo.pack(side=tk.RIGHT)

        # --- log
        c3 = W.Card(col, 'log di sistema', accent=T.TEXT_MUTE)
        c3.pack(fill=tk.BOTH, expand=True)
        self.console = tk.Text(c3.body, bg=T.SUNKEN, fg=T.GREEN,
                               font=T.f(8, mono=True), height=8, relief='flat',
                               wrap='word', bd=0, highlightthickness=1,
                               highlightbackground=T.BORDER_SOFT,
                               insertbackground=T.TEXT)
        self.console.pack(fill=tk.BOTH, expand=True)

    def _show_tab(self):
        for name, frame in self._tabs.items():
            frame.pack_forget()
        self._tabs[self.tab_var.get()].pack(fill=tk.X)

    # ---- centro
    def _build_center(self, parent):
        col = tk.Frame(parent, bg=T.BG)
        col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        card = W.Card(col, None, pad=8)
        card.pack(fill=tk.BOTH, expand=True)
        bar = tk.Frame(card.body, bg=T.SURFACE)
        bar.pack(fill=tk.X, pady=(0, 6))
        tk.Frame(bar, bg=T.ROSE, width=8, height=8).pack(side=tk.LEFT, padx=(2, 7))
        tk.Label(bar, text='LIVE PREVIEW', bg=T.SURFACE, fg=T.TEXT_MUTE,
                 font=T.f(8, 'bold')).pack(side=tk.LEFT)
        self.res_label = tk.Label(bar, text='—', bg=T.SURFACE, fg=T.TEXT_MUTE,
                                  font=T.f(8, mono=True))
        self.res_label.pack(side=tk.RIGHT)
        self.video_label = tk.Label(card.body, bg='#000000', bd=0,
                                    highlightthickness=1,
                                    highlightbackground=T.BORDER_SOFT)
        self.video_label.pack(fill=tk.BOTH, expand=True)

    # ---- barra di stato
    def _build_statusbar(self):
        bar = tk.Frame(self.root, bg=T.SURFACE, height=26)
        bar.pack(side=tk.BOTTOM, fill=tk.X)
        bar.pack_propagate(False)
        self.status_label = tk.Label(bar, text='Inizializzazione…', bg=T.SURFACE,
                                     fg=T.TEXT_MUTE, font=T.f(8), anchor='w')
        self.status_label.pack(side=tk.LEFT, padx=12)
        tk.Label(bar, text='SPAZIO swap  ·  S snapshot  ·  V rec  ·  F fullscreen  ·  ESC esci',
                 bg=T.SURFACE, fg=T.TEXT_MUTE, font=T.f(8)).pack(side=tk.RIGHT, padx=12)

    def _bind_keys(self):
        self.root.bind('<Escape>', lambda e: self.quit_app())
        self.root.bind('<space>', lambda e: self.toggle_swap())
        self.root.bind('f', lambda e: self.toggle_fullscreen())
        self.root.bind('r', lambda e: self.reset_camera())
        self.root.bind('s', lambda e: self.snapshot())
        self.root.bind('v', lambda e: self.toggle_record())
        self.root.bind('m', lambda e: self.v_multi.set(not self.v_multi.get()))

    def set_status(self, text, color=None):
        """Badge in alto a destra + testo nella barra di stato."""
        self.badge_status.set(text.upper()[:14], color or T.TEXT_MUTE)

    # --------------------------------------------------------------- params
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
                'color_stab': float(self.v_colorstab.get()),
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

    # -------------------------------------------------------------- startup
    def start_system(self):
        threading.Thread(target=self.initialize_models, daemon=True).start()

    def initialize_models(self):
        self.log('⚡ Inizializzo i modelli AI…')
        self.set_status('loading', T.AMBER)
        try:
            if not os.path.exists(config['model_path']):
                self.log(f"❌ Modello non trovato: {config['model_path']}")
                self.log('📥 github.com/deepinsight/insightface/releases')
                self.set_status('no model', T.BAD)
                return
            self.engine = FaceEngine(config['model_path'])
            if self.engine.load():
                self.models_ready = True
                self.badge_provider.set(self.engine.provider_name.upper()[:14],
                                        T.GREEN if self.engine.ctx_id >= 0 else T.TEXT_DIM)
                self.set_status('ready', T.GREEN)
                self.log(f'✅ Modelli caricati · provider: {self.engine.provider_name}')
                self.btn_load.set_enabled(True)
                self.start_camera_thread()
            else:
                self.set_status('model err', T.BAD)
                self.log('❌ Caricamento modello fallito')
        except Exception as e:
            self.log(f'❌ Errore init: {e}')
            self.set_status('init fail', T.BAD)

    def start_camera_thread(self):
        threading.Thread(target=self.initialize_camera, daemon=True).start()

    def initialize_camera(self):
        self.log('📷 Inizializzo la webcam…')
        self.source_mode = 'camera'
        for cam_id in range(3):
            try:
                cap = (cv2.VideoCapture(cam_id, cv2.CAP_DSHOW) if os.name == 'nt'
                       else cv2.VideoCapture(cam_id))
                if cap.isOpened():
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                    cap.set(cv2.CAP_PROP_FPS, 60)
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    self.cap = cap
                    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    self.log(f'✅ Webcam {cam_id}: {w}x{h}')
                    self.set_status('camera ok', T.GREEN)
                    self.start_processing_threads()
                    return
                cap.release()
            except Exception:
                continue
        self.log('❌ Nessuna webcam trovata')
        self.set_status('no camera', T.BAD)

    def start_processing_threads(self):
        if self._threads_started:
            return
        self._threads_started = True
        threading.Thread(target=self.capture_loop, daemon=True).start()
        threading.Thread(target=self.process_loop, daemon=True,
                         name='Inference').start()
        self.log('⚡ Pipeline avviata (1 cattura + 1 inferenza)')

    # -------------------------------------------------------------- threads
    def capture_loop(self):
        while self.running:
            cap = self.cap
            if cap is None:
                time.sleep(0.02)
                continue
            try:
                ok, frame = cap.read()
                if not ok:
                    if self.source_mode == 'video':
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        continue
                    time.sleep(0.003)
                    continue
                if self.capture_queue.full():
                    try:
                        self.capture_queue.get_nowait()
                    except queue.Empty:
                        pass
                self.capture_queue.put_nowait(frame)
                if self.source_mode == 'video':
                    time.sleep(1.0 / 30.0)
            except Exception:
                time.sleep(0.005)

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
                        faces = self._coast_faces
                        self._coast += 1
                    else:
                        self._coast_faces = None
                    if faces:
                        skin = (self.engine._skin_prob(frame)
                                if (p.get('occlusion', 0.0) > 0 and len(faces) > 1)
                                else None)
                        for face in faces:
                            result = self.engine.swap_one(result, face,
                                                          self.source_face, p,
                                                          skin=skin)
                        if self.v_bbox.get():
                            color = BOX_COLORS.get(self.color_combo.get(), (0, 255, 0))
                            for face in faces:
                                b = face.bbox.astype(int)
                                cv2.rectangle(result, (b[0], b[1]), (b[2], b[3]),
                                              color, 2)
                                cv2.putText(result, f'{face.det_score:.2f}',
                                            (b[0], b[1] - 5),
                                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

                if self.v_fps.get():
                    cv2.putText(result, f'FPS: {self.monitor.current_fps}', (10, 28),
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
                self.log(f'⚠️ Errore processing: {str(e)[:60]}')

    # ------------------------------------------------------------- UI pumps
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
                src_h, src_w = frame.shape[:2]
                # adatta l'anteprima all'area disponibile mantenendo le proporzioni
                aw = max(1, self.video_label.winfo_width())
                ah = max(1, self.video_label.winfo_height())
                shown = frame
                if aw > 20 and ah > 20:
                    k = min(aw / src_w, ah / src_h)
                    tw, th = max(1, int(src_w * k)), max(1, int(src_h * k))
                    if (tw, th) != (src_w, src_h):
                        shown = cv2.resize(
                            frame, (tw, th),
                            interpolation=cv2.INTER_AREA if k < 1 else cv2.INTER_LINEAR)
                rgb = cv2.cvtColor(shown, cv2.COLOR_BGR2RGB)
                photo = ImageTk.PhotoImage(image=Image.fromarray(rgb))
                self.video_label.config(image=photo, text='')
                self.video_label.image = photo
                self.res_label.config(text=f'{src_w}×{src_h}')
            except Exception:
                pass
        self.root.after(int(1000 / config['display_hz']), self.display_pump)

    def stats_pump(self):
        if not self.running:
            return
        s = self.monitor.get_stats()
        col = T.GREEN if s['fps'] >= 24 else (T.AMBER if s['fps'] >= 12 else T.BAD)
        self.tile_fps.set(s['fps'], col)
        self.tile_cpu.set(f"{s['cpu']:.0f}")
        self.tile_ram.set(f"{s['ram']:.0f}")
        self.spark.set_series(self.monitor.fps_history)
        self.status_label.config(
            text=f"Swap {'ON' if self.swap_active else 'OFF'}  ·  "
                 f"Mode {self.mode_var.get().upper()}  ·  "
                 f"Multi {'ON' if self.params['multi_face'] else 'OFF'}  ·  "
                 f"FPS {s['fps']} (medio {s['avg_fps']})  ·  "
                 f"CPU {s['cpu']:.0f}%  RAM {s['ram']:.0f}%")
        self.root.after(500, self.stats_pump)

    # -------------------------------------------------------------- sorgenti
    def load_face_image(self):
        if not self.models_ready:
            messagebox.showwarning('Attendi', 'Modelli ancora in caricamento')
            return
        fp = filedialog.askopenfilename(
            title='Scegli il volto da mettere',
            filetypes=[('Immagini', '*.jpg *.jpeg *.png *.bmp'), ('Tutti', '*.*')])
        if not fp:
            return
        try:
            self.log(f'📁 Carico: {os.path.basename(fp)}')
            img = cv2.imread(fp)
            if img is None:
                messagebox.showerror('Errore', 'Immagine illeggibile')
                return
            face = self.engine.detect_source(img)
            if face is None:
                messagebox.showwarning('Nessun volto', 'Nessun volto rilevato')
                return
            self.source_face = face
            self.source_image = img
            self.face_loaded = True
            preview = img.copy()
            b = face.bbox.astype(int)
            cv2.rectangle(preview, (b[0], b[1]), (b[2], b[3]), (34, 211, 238), 3)
            pil = Image.fromarray(cv2.cvtColor(preview, cv2.COLOR_BGR2RGB))
            pil.thumbnail((262, 200))
            photo = ImageTk.PhotoImage(image=pil)
            self.face_label.config(image=photo, text='', height=0)
            self.face_label.image = photo
            self.set_status('face ok', T.GREEN)
            self.log(f'✅ Volto caricato (score {face.det_score:.3f})')
            self.btn_swap.set_enabled(True)
        except Exception as e:
            messagebox.showerror('Errore', f'Caricamento fallito: {e}')
            self.log(f'❌ Errore caricamento: {e}')

    def load_target_image(self):
        if not self.models_ready:
            messagebox.showwarning('Attendi', 'Modelli in caricamento')
            return
        fp = filedialog.askopenfilename(
            title='Foto della persona DA SOSTITUIRE',
            filetypes=[('Immagini', '*.jpg *.jpeg *.png *.bmp'), ('Tutti', '*.*')])
        if not fp:
            return
        try:
            img = cv2.imread(fp)
            if img is None:
                messagebox.showerror('Errore', 'Immagine illeggibile')
                return
            face = self.engine.detect_source(img)
            emb = getattr(face, 'normed_embedding', None) if face is not None else None
            if emb is None:
                messagebox.showwarning('Nessun volto', 'Nessun volto/embedding')
                return
            self.target_ref = np.asarray(emb, np.float32)
            self.log(f'🎯 Target impostato: {os.path.basename(fp)}')
            self.v_match.set(True)
            self.on_match_toggle()
        except Exception as e:
            self.log(f'❌ Errore target: {e}')

    def use_camera(self):
        if self.cap:
            self.cap.release()
            self.cap = None
        threading.Thread(target=self.initialize_camera, daemon=True).start()

    def load_video_file(self):
        fp = filedialog.askopenfilename(
            title='Scegli un video',
            filetypes=[('Video', '*.mp4 *.avi *.mov *.mkv'), ('Tutti', '*.*')])
        if not fp:
            return
        try:
            cap = cv2.VideoCapture(fp)
            if not cap.isOpened():
                messagebox.showerror('Errore', 'Video non apribile')
                return
            if self.cap:
                self.cap.release()
            self.cap = cap
            self.source_mode = 'video'
            self.video_path = fp
            self.log(f'🎬 Video: {os.path.basename(fp)}')
            self.set_status('video ok', T.GREEN)
            self.start_processing_threads()
        except Exception as e:
            self.log(f'❌ Errore video: {e}')

    # ---------------------------------------------------------------- swap
    def toggle_swap(self):
        if not self.face_loaded:
            messagebox.showwarning('Nessun volto', 'Carica prima un volto')
            return
        self.swap_active = not self.swap_active
        if self.swap_active:
            self.btn_swap.configure_text('◉  SWAP ON')
            self.btn_swap.set_kind('ok')
            self.log('⚡ Face swap ATTIVO')
        else:
            self.btn_swap.configure_text('◉  SWAP OFF')
            self.btn_swap.set_kind('danger')
            self._coast_faces = None
            self._coast = 0
            self.log('⚡ Face swap SPENTO')

    def on_detsize(self, _e=None):
        if not self.models_ready:
            return
        n = int(self.detsize_combo.get())
        self.log(f'🔧 Detector size → {n}')
        threading.Thread(target=lambda: self.engine.set_det_size(n),
                         daemon=True).start()

    def on_enhance_toggle(self):
        if not self.v_enhance.get():
            return
        if not self.models_ready:
            self.v_enhance.set(False)
            return
        self.log('⏳ Carico GFPGAN (la prima volta scarica il modello)…')
        threading.Thread(target=self._load_enhancer_bg, daemon=True).start()

    def _load_enhancer_bg(self):
        ok, msg = self.engine.try_load_enhancer()
        self.log(('✅ ' if ok else '⚠️ ') + msg)
        if ok:
            self.v_realistic.set(True)
        else:
            self.v_enhance.set(False)

    def on_occluder_toggle(self):
        if not self.v_occluder.get():
            return
        if not self.models_ready:
            self.v_occluder.set(False)
            return
        self.log('⏳ Carico l\'occluder AI (la prima volta scarica il modello)…')
        threading.Thread(target=self._load_occluder_bg, daemon=True).start()

    def _load_occluder_bg(self):
        ok, msg = self.engine.try_load_occluder()
        self.log(('✅ ' if ok else '⚠️ ') + msg)
        if ok:
            self.v_realistic.set(True)
        else:
            self.v_occluder.set(False)

    def on_match_toggle(self):
        if not self.v_match.get():
            return
        if self.target_ref is None:
            self.log('⚠️ Match: carica prima una foto 🎯 Target')
            self.v_match.set(False)
            return
        self.log('⏳ Preparo il match d\'identità…')
        threading.Thread(target=self._load_matcher_bg, daemon=True).start()

    def _load_matcher_bg(self):
        ok, msg = self.engine.ensure_matcher()
        self.log(('✅ ' if ok else '⚠️ ') + msg)
        if not ok:
            self.v_match.set(False)

    def apply_preset(self, name):
        p = PRESETS.get(name)
        if not p:
            return
        self.mode_var.set(p['mode'])
        self.detsize_combo.set(str(p['det']))
        self.on_detsize()
        self.v_thresh.set(p['thresh'])
        self.v_mask.set(p['mask'])
        self.v_forehead.set(p['forehead'])
        self.v_occlusion.set(p['occ'])
        self.v_feather.set(p['feather'])
        self.v_color.set(p['color'])
        self.v_colorstab.set(p['cstab'])
        self.v_sharpen.set(p['sharpen'])
        self.v_smooth.set(p['smooth'])
        self.v_keepmouth.set(p['keep'])
        self.v_stabilize.set(p['stab'])
        self.v_precise.set(p['precise'])
        self.v_multi.set(p['multi'])
        self._sync_params()
        self.log(f"🎚️ Preset '{name}' applicato")

    # --------------------------------------------------------- export / rec
    def _ensure_output(self):
        os.makedirs(config['output_dir'], exist_ok=True)

    def export_video(self):
        if not self.models_ready or self.source_face is None:
            messagebox.showwarning('Attendi', 'Carica prima un volto e i modelli')
            return
        inp = filedialog.askopenfilename(
            title='Video da processare',
            filetypes=[('Video', '*.mp4 *.avi *.mov *.mkv'), ('Tutti', '*.*')])
        if not inp:
            return
        threading.Thread(target=self._export_worker, args=(inp,), daemon=True).start()

    def _export_worker(self, inp):
        cap = cv2.VideoCapture(inp)
        if not cap.isOpened():
            self.log('❌ Export: video non apribile')
            return
        fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self._ensure_output()
        out_path = os.path.join(
            config['output_dir'],
            f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4")
        writer = cv2.VideoWriter(out_path, cv2.VideoWriter_fourcc(*'mp4v'), fps,
                                 (w, h))
        if not writer.isOpened():
            self.log('❌ Export: writer non disponibile')
            cap.release()
            return

        self.root.after(0, lambda: self.btn_export.set_enabled(False))
        self.log(f'🎞 Export avviato: {os.path.basename(inp)} ({w}x{h}, {total} frame)')
        p = dict(self.params)
        stab = FaceStabilizer()
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
                    skin = (self.engine._skin_prob(frame)
                            if (p.get('occlusion', 0.0) > 0 and len(faces) > 1)
                            else None)
                    for face in faces:
                        result = self.engine.swap_one(result, face,
                                                      self.source_face, p,
                                                      skin=skin)
            except Exception:
                pass
            writer.write(result)
            if total and i % 10 == 0:
                pct = 100.0 * i / total
                self.root.after(0, lambda v=pct: self.set_status(f'export {v:.0f}%',
                                                                 T.VIOLET))
        writer.release()
        cap.release()
        self.root.after(0, lambda: self.set_status('export ok', T.GREEN))
        self.root.after(0, lambda: self.btn_export.set_enabled(True))
        self.log(f'✅ Export salvato: {out_path} ({i} frame) — video senza audio')

    def snapshot(self):
        if self.last_result is None:
            self.log('⚠️ Nessun frame da salvare')
            return
        self._ensure_output()
        path = os.path.join(config['output_dir'],
                            f"snap_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
        try:
            cv2.imwrite(path, self.last_result)
            self.log(f'📸 Salvato: {path}')
        except Exception as e:
            self.log(f'❌ Errore snapshot: {e}')

    def toggle_record(self):
        if self.recording:
            self.recording = False
            if self.writer:
                self.writer.release()
                self.writer = None
            self.btn_rec.configure_text('⏺ REC')
            self.btn_rec.set_kind('danger')
            self.badge_rec.pack_forget()
            self.log('⏹ Registrazione fermata')
        else:
            if self.last_result is None:
                self.log('⚠️ Nessun frame da registrare')
                return
            self._ensure_output()
            path = os.path.join(
                config['output_dir'],
                f"rec_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4")
            h, w = self.last_result.shape[:2]
            self.rec_size = (w, h)
            self.writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*'mp4v'),
                                          config['record_fps'], (w, h))
            if not self.writer.isOpened():
                self.log('❌ Writer video non disponibile')
                self.writer = None
                return
            self.recording = True
            self.btn_rec.configure_text('⏹ STOP')
            self.btn_rec.set_kind('ok')
            self.badge_rec.pack(side=tk.RIGHT, padx=3)
            self.log(f'⏺ Registro → {path}')

    def _write_frame(self, frame):
        try:
            if self.rec_size and (frame.shape[1], frame.shape[0]) != self.rec_size:
                frame = cv2.resize(frame, self.rec_size)
            if self.writer:
                self.writer.write(frame)
        except Exception:
            pass

    # ---------------------------------------------------------------- varie
    def toggle_fullscreen(self):
        self.root.attributes('-fullscreen',
                             not self.root.attributes('-fullscreen'))

    def reset_camera(self):
        self.use_camera()
        self.log('🔄 Webcam reinizializzata')

    def log(self, message):
        ts = datetime.now().strftime('%H:%M:%S')
        try:
            self.console.insert(tk.END, f'[{ts}] {message}\n')
            self.console.see(tk.END)
            if int(self.console.index('end-1c').split('.')[0]) > 200:
                self.console.delete('1.0', '50.0')
        except Exception:
            print(f'[{ts}] {message}')

    def quit_app(self):
        self.running = False
        if self.recording and self.writer:
            self.writer.release()
        if self.cap:
            self.cap.release()
        try:
            self.root.quit()
            self.root.destroy()
        except Exception:
            pass
        print('\n' + '=' * 70 + '\n👋 Applicazione chiusa\n' + '=' * 70)


# ============================================================
def main():
    print('=' * 70)
    print(f'🚀 DEEPFAKE ULTRA PRO {VERSION}')
    print(f'🔥 PID {os.getpid()} | CPU {_cpu_count()}')
    print('=' * 70)

    if not os.path.exists(config['model_path']):
        print(f"\n⚠️  Modello '{config['model_path']}' non trovato!")
        print('   github.com/deepinsight/insightface/releases')
        try:
            if input('\nContinuo comunque? (y/n): ').lower() != 'y':
                return
        except EOFError:
            return

    root = tk.Tk()
    app = DeepfakeUltraPro(root)
    root.update_idletasks()
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    ww, wh = root.winfo_width(), root.winfo_height()
    root.geometry(f'{ww}x{wh}+{max(0, (sw - ww) // 2)}+{max(0, (sh - wh) // 2)}')
    root.protocol('WM_DELETE_WINDOW', app.quit_app)
    root.mainloop()
