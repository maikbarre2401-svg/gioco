"""Dark Tkinter control panel with tabbed settings, live metrics, and hotkey bindings."""

from __future__ import annotations

import ctypes
import logging
import os
import subprocess
import sys
import time
import tkinter as tk
from tkinter import colorchooser, ttk
from typing import Optional

import cv2
import numpy as np
from PIL import Image, ImageTk

from core.config import Config
from core.engine import Engine
from core.metrics import MetricsCollector
from core.overlay import Overlay
from core.profile import (
    ensure as ensure_profiles,
    load as load_profile,
    names as profile_names,
    save as save_profile,
)
from core.utils import is_admin, screen_size, set_dpi_aware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("gui")

BG = "#1a1a2e"
BG2 = "#16213e"
BG3 = "#0f1529"
FG = "#e0e0e0"
FG_DIM = "#808090"
ACCENT = "#ff2fd0"
ACCENT2 = "#7a5cff"
GREEN = "#34d058"
RED = "#f85149"
YELLOW = "#d29922"
BORDER = "#2a2a4a"


def _elevate() -> None:
    """Self-elevate via UAC if not admin."""
    if is_admin():
        return
    # list2cmdline applies Windows quoting rules; a plain join breaks as soon as
    # the install path contains a space, e.g. "...\Downloads\gioco (13)\".
    params = subprocess.list2cmdline([os.path.abspath(sys.argv[0])] + sys.argv[1:])
    try:
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, params, os.getcwd(), 1
        )
        sys.exit(0)
    except Exception:
        logger.warning("UAC elevation failed, continuing without admin")


class App:
    """Main application: Tk GUI, engine management, hotkeys."""

    def __init__(self) -> None:
        set_dpi_aware()
        ensure_profiles()
        self._cfg = Config.load()
        self._metrics = MetricsCollector()
        self._engine: Optional[Engine] = None
        self._overlay: Optional[Overlay] = None
        self._aiming = False
        self._toggle_aim_state = False
        self._listener = None
        self._ctrl_held = False
        self._poll_failed = False
        self._settle_drawn = -1

        self._build_gui()
        self._setup_hotkeys()

        if self._cfg.overlay:
            self._create_overlay()

        self._poll_id: Optional[str] = None
        self._start_poll()
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── GUI construction ─────────────────────────────────────────────

    def _build_gui(self) -> None:
        self._root = tk.Tk()
        self._root.title("Aim Assist Control Panel")
        self._root.geometry("1020x820")
        self._root.configure(bg=BG)
        self._root.minsize(900, 700)
        self._slider_labels: dict = {}
        self._slider_bounds: dict = {}
        self._check_vars: dict = {}
        self._restart_attrs: set = set()
        self._pending_restart: set = set()
        self._syncing = False

        self._setup_styles()
        self._build_toolbar()
        self._build_preview_row()
        self._build_notebook()
        self._build_status_bar()
        self._build_log()

        self._preview_photo: Optional[ImageTk.PhotoImage] = None
        self._crop_photo: Optional[ImageTk.PhotoImage] = None

    def _setup_styles(self) -> None:
        s = ttk.Style()
        s.theme_use("clam")
        s.configure(".", background=BG, foreground=FG, fieldbackground=BG2)
        s.configure("TNotebook", background=BG, borderwidth=0)
        s.configure("TNotebook.Tab", background=BG2, foreground=FG,
                     padding=[14, 5], font=("Segoe UI", 9, "bold"))
        s.map("TNotebook.Tab",
               background=[("selected", ACCENT2)],
               foreground=[("selected", "#ffffff")])
        s.configure("TFrame", background=BG)
        s.configure("TLabel", background=BG, foreground=FG, font=("Segoe UI", 9))
        s.configure("TLabelframe", background=BG, foreground=ACCENT2,
                     font=("Segoe UI", 9, "bold"), borderwidth=1, relief="groove")
        s.configure("TLabelframe.Label", background=BG, foreground=ACCENT2,
                     font=("Segoe UI", 9, "bold"))
        s.configure("TButton", background=BG2, foreground=FG, font=("Segoe UI", 9))
        s.configure("TCheckbutton", background=BG, foreground=FG, font=("Segoe UI", 9))
        s.configure("Horizontal.TScale", background=BG, troughcolor=BG2)

        # Comboboxes and spinboxes need their states mapped explicitly, otherwise
        # clam paints a readonly combobox with its own light palette and the text
        # is unreadable on the dark panel.
        s.configure("TCombobox", fieldbackground=BG2, background=BG2,
                     foreground=FG, arrowcolor=FG, borderwidth=1)
        s.map(
            "TCombobox",
            fieldbackground=[("readonly", BG2), ("disabled", BG3)],
            foreground=[("readonly", FG), ("disabled", FG_DIM)],
            selectbackground=[("readonly", BG2)],
            selectforeground=[("readonly", FG)],
            arrowcolor=[("readonly", ACCENT2)],
        )
        s.configure("TSpinbox", fieldbackground=BG2, background=BG2,
                     foreground=FG, arrowcolor=FG, borderwidth=1)
        s.map("TSpinbox", fieldbackground=[("readonly", BG2)],
               foreground=[("readonly", FG)])
        s.configure("TEntry", fieldbackground=BG2, foreground=FG,
                     insertcolor=FG, borderwidth=1)
        s.configure("Vertical.TScrollbar", background=BG2, troughcolor=BG3,
                     arrowcolor=FG, borderwidth=0)
        s.map("Vertical.TScrollbar", background=[("active", ACCENT2)])

        # the dropdown list is a classic Tk listbox, styled through the option db
        self._root.option_add("*TCombobox*Listbox.background", BG2)
        self._root.option_add("*TCombobox*Listbox.foreground", FG)
        self._root.option_add("*TCombobox*Listbox.selectBackground", ACCENT2)
        self._root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
        self._root.option_add("*TCombobox*Listbox.font", "Consolas 9")
        s.configure("Dim.TLabel", background=BG, foreground=FG_DIM, font=("Segoe UI", 8))
        s.configure("Status.TLabel", background=BG3, foreground=FG_DIM,
                     font=("Consolas", 9))
        s.configure("StatusAccent.TLabel", background=BG3, foreground=ACCENT,
                     font=("Consolas", 9, "bold"))
        s.configure("StatusWarn.TLabel", background=BG3, foreground=YELLOW,
                     font=("Consolas", 9, "bold"))

    def _build_toolbar(self) -> None:
        bar = tk.Frame(self._root, bg=BG, pady=4)
        bar.pack(fill="x", padx=8)

        self._start_btn = tk.Button(
            bar, text="▶ AVVIA", bg=GREEN, fg="white",
            font=("Segoe UI", 10, "bold"), command=self._on_start,
            width=10, relief="flat", cursor="hand2",
        )
        self._start_btn.pack(side="left", padx=3)

        self._stop_btn = tk.Button(
            bar, text="■ FERMA", bg="#444", fg=FG,
            font=("Segoe UI", 10, "bold"), command=self._on_stop,
            width=10, state="disabled", relief="flat", cursor="hand2",
        )
        self._stop_btn.pack(side="left", padx=3)

        self._aim_btn = tk.Button(
            bar, text="◎ MIRA", bg="#444", fg=FG,
            font=("Segoe UI", 10, "bold"), command=self._on_aim_toggle,
            width=10, relief="flat", cursor="hand2",
        )
        self._aim_btn.pack(side="left", padx=3)

        sep = ttk.Separator(bar, orient="vertical")
        sep.pack(side="left", fill="y", padx=8, pady=2)

        tk.Label(bar, text="Profilo:", bg=BG, fg=FG_DIM,
                 font=("Segoe UI", 9)).pack(side="left")
        self._profile_var = tk.StringVar(value="naturale")
        self._profile_combo = ttk.Combobox(
            bar, textvariable=self._profile_var,
            values=profile_names(), state="readonly", width=12,
        )
        self._profile_combo.pack(side="left", padx=3)
        self._profile_combo.bind("<<ComboboxSelected>>", self._on_profile_select)

        tk.Button(bar, text="Salva", bg=BG2, fg=FG, relief="flat",
                  font=("Segoe UI", 9), command=self._on_profile_save,
                  ).pack(side="left", padx=2)

        tk.Button(bar, text="💾 SALVA CONFIG", bg=ACCENT2, fg="white",
                  font=("Segoe UI", 9, "bold"), command=self._on_save,
                  relief="flat", cursor="hand2",
                  ).pack(side="right", padx=3)

    def _build_preview_row(self) -> None:
        row = tk.Frame(self._root, bg=BG)
        row.pack(fill="x", padx=8, pady=4)

        left = tk.Frame(row, bg=BG)
        left.pack(side="left")

        self._preview_canvas = tk.Canvas(
            left, width=300, height=300, bg="#000", highlightthickness=1,
            highlightbackground=BORDER,
        )
        self._preview_canvas.pack(padx=(0, 6))

        mid = tk.Frame(row, bg=BG)
        mid.pack(side="left", fill="y")

        self._crop_canvas = tk.Canvas(
            mid, width=180, height=180, bg="#000", highlightthickness=1,
            highlightbackground=BORDER,
        )
        self._crop_canvas.pack(pady=(0, 4))

        self._settle_canvas = tk.Canvas(
            mid, width=180, height=90, bg=BG2, highlightthickness=1,
            highlightbackground=BORDER,
        )
        self._settle_canvas.pack()

        right = tk.Frame(row, bg=BG)
        right.pack(side="left", fill="both", expand=True, padx=(6, 0))

        self._metrics_frame = tk.Frame(right, bg=BG2, highlightthickness=1,
                                        highlightbackground=BORDER)
        self._metrics_frame.pack(fill="both", expand=True)

        self._metric_labels: dict = {}
        metrics = [
            ("engine", "Engine", "OFFLINE"),
            ("fps", "Loop FPS", "—"),
            ("det_fps", "Det FPS", "—"),
            ("state", "State", "SEARCH"),
            ("trk_score", "Track Score", "—"),
            ("hit_prob", "Hit Prob", "—"),
            ("movement", "Movement", "—"),
            ("reid", "ReID Score", "—"),
        ]
        for i, (key, label, default) in enumerate(metrics):
            lbl = tk.Label(self._metrics_frame, text=f"  {label}", bg=BG2,
                           fg=FG_DIM, font=("Consolas", 9), anchor="w")
            lbl.grid(row=i, column=0, sticky="w", padx=(6, 0), pady=1)
            val = tk.Label(self._metrics_frame, text=default, bg=BG2,
                           fg=FG, font=("Consolas", 10, "bold"), anchor="e")
            val.grid(row=i, column=1, sticky="e", padx=(0, 8), pady=1)
            self._metric_labels[key] = val
        self._metrics_frame.columnconfigure(1, weight=1)

    def _build_notebook(self) -> None:
        nb = ttk.Notebook(self._root)
        nb.pack(fill="both", expand=True, padx=8, pady=4)

        self._det_tab = self._add_tab(nb, " RILEVAMENTO ")
        self._aim_tab = self._add_tab(nb, " MIRA ")
        self._human_tab = self._add_tab(nb, " UMANO ")
        self._trigger_tab = self._add_tab(nb, " TRIGGER ")
        self._gamepad_tab = self._add_tab(nb, " GAMEPAD ")
        self._overlay_tab = self._add_tab(nb, " OVERLAY ")
        self._adv_tab = self._add_tab(nb, " SISTEMA ")

        self._build_det_tab()
        self._build_aim_tab()
        self._build_human_tab()
        self._build_trigger_tab()
        self._build_gamepad_tab()
        self._build_overlay_tab()
        self._build_adv_tab()

    def _add_tab(self, nb: ttk.Notebook, title: str) -> ttk.Frame:
        """Add a notebook page whose content scrolls when the window is small."""
        outer = ttk.Frame(nb)
        nb.add(outer, text=title)

        canvas = tk.Canvas(outer, bg=BG, highlightthickness=0)
        vsb = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        inner = ttk.Frame(canvas)
        window = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _on_inner_resize(_event: object) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_canvas_resize(event: object) -> None:
            canvas.itemconfigure(window, width=event.width)

        inner.bind("<Configure>", _on_inner_resize)
        canvas.bind("<Configure>", _on_canvas_resize)

        def _on_wheel(event: object) -> None:
            first, last = canvas.yview()
            if first <= 0.0 and last >= 1.0:
                return  # everything already fits; leave the wheel alone
            canvas.yview_scroll(-1 * (event.delta // 120), "units")

        canvas.bind("<Enter>", lambda _e: canvas.bind_all("<MouseWheel>", _on_wheel))
        canvas.bind("<Leave>", lambda _e: canvas.unbind_all("<MouseWheel>"))
        return inner

    def _build_det_tab(self) -> None:
        f = self._det_tab
        f.columnconfigure(0, weight=1)
        f.columnconfigure(1, weight=1)

        g1 = ttk.LabelFrame(f, text="Modelli e Risoluzione")
        g1.grid(row=0, column=0, sticky="nsew", padx=6, pady=4)

        self._make_slider(g1, "conf", "Confidence", 0.1, 0.9, 0.01, 0, 0)
        self._make_slider(g1, "kp_conf", "KP Confidence", 0.05, 0.8, 0.01, 1, 0)
        self._make_slider(g1, "imgsz", "Det Size", 320, 960, 32, 2, 0)
        self._make_slider(g1, "pose_imgsz", "Pose Size", 160, 640, 32, 3, 0)

        g2 = ttk.LabelFrame(f, text="Multi-scala")
        g2.grid(row=0, column=1, sticky="nsew", padx=6, pady=4)

        self._make_check(g2, "multiscale", "Multi-scale", 0, 0)
        self._make_slider(g2, "imgsz_far", "Far Size", 640, 1280, 32, 1, 0)

        g3 = ttk.LabelFrame(f, text="Cattura")
        g3.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=6, pady=4)

        ttk.Label(g3, text="Capture Size *:").grid(row=0, column=0, sticky="w", padx=6, pady=3)
        self._restart_attrs.add("capture")
        self._capture_var = tk.IntVar(value=self._cfg.capture)
        cap_combo = ttk.Combobox(
            g3, textvariable=self._capture_var,
            values=[320, 480, 640, 800, 960], state="readonly", width=8,
        )
        cap_combo.grid(row=0, column=1, padx=6, pady=3)
        cap_combo.bind("<<ComboboxSelected>>", lambda e: self._on_capture_change())

        self._make_check(g3, "half", "FP16 (GPU)", 0, 2, restart=True)
        self._make_check(g3, "use_pose", "Use Pose", 0, 4)

        self._restart_legend(f, row=2)

    def _build_aim_tab(self) -> None:
        f = self._aim_tab
        f.columnconfigure(0, weight=1)
        f.columnconfigure(1, weight=1)

        g1 = ttk.LabelFrame(f, text="Campo Visivo")
        g1.grid(row=0, column=0, sticky="nsew", padx=6, pady=4)

        self._make_slider(g1, "fov_px", "FOV (px)", 50, 800, 10, 0, 0)
        self._make_slider(g1, "hfov_deg", "HFOV (deg)", 40, 120, 1, 1, 0)
        self._make_slider(g1, "counts_per_deg", "Counts/deg", 100, 5000, 50, 2, 0)

        g2 = ttk.LabelFrame(f, text="Movimento")
        g2.grid(row=0, column=1, sticky="nsew", padx=6, pady=4)

        self._make_slider(g2, "max_step", "Max Step", 10, 500, 5, 0, 0)
        self._make_slider(g2, "deadzone", "Deadzone", 0.1, 5.0, 0.1, 1, 0)
        self._make_slider(g2, "tick_hz", "Tick Hz", 60, 500, 10, 2, 0, restart=True)

        g3 = ttk.LabelFrame(f, text="Target Switching")
        g3.grid(row=1, column=0, sticky="nsew", padx=6, pady=4)

        self._make_slider(g3, "sticky_radius", "Sticky Radius", 0, 150, 5, 0, 0)
        self._make_slider(g3, "sticky_gain", "Sticky Gain", 0.0, 1.0, 0.05, 1, 0)
        self._make_slider(g3, "switch_margin", "Switch Margin", 0.0, 1.0, 0.05, 2, 0)
        self._make_slider(g3, "switch_cooldown_ms", "Switch CD (ms)", 0, 500, 10, 3, 0)

        g4 = ttk.LabelFrame(f, text="Lead e Snap")
        g4.grid(row=1, column=1, sticky="nsew", padx=6, pady=4)

        self._make_slider(g4, "lead_ms", "Lead (ms)", 0, 200, 5, 0, 0)
        self._make_slider(g4, "settle_ms", "Settle (ms)", 10, 300, 10, 1, 0)
        self._make_slider(g4, "ads_delay_ms", "ADS Delay (ms)", 0, 500, 10, 2, 0)
        self._make_slider(g4, "snap_duration_ms", "Snap Dur (ms)", 50, 600, 10, 3, 0)
        self._make_slider(g4, "snap_omega", "Snap Omega", 10, 100, 1, 4, 0)
        self._make_slider(g4, "snap_zeta", "Snap Zeta", 0.3, 1.2, 0.01, 5, 0)

        g5 = ttk.LabelFrame(f, text="Bone")
        g5.grid(row=2, column=0, sticky="nsew", padx=6, pady=4)

        ttk.Label(g5, text="Aim Bone:").grid(row=0, column=0, sticky="w", padx=6, pady=3)
        self._bone_var = tk.StringVar(value=self._cfg.bone)
        bone_combo = ttk.Combobox(
            g5, textvariable=self._bone_var,
            values=["head", "neck", "chest", "pelvis"], state="readonly", width=10,
        )
        bone_combo.grid(row=0, column=1, padx=6, pady=3)
        bone_combo.bind("<<ComboboxSelected>>",
                         lambda e: setattr(self._cfg, "bone", self._bone_var.get()))

        self._make_check(g5, "bone_by_distance", "Auto bone by distance", 1, 0, colspan=2)

        self._restart_legend(f, row=3)

    def _build_human_tab(self) -> None:
        f = self._human_tab
        f.columnconfigure(0, weight=1)
        f.columnconfigure(1, weight=1)

        g1 = ttk.LabelFrame(f, text="Reazione")
        g1.grid(row=0, column=0, sticky="nsew", padx=6, pady=4)

        self._make_slider(g1, "reaction_ms", "Reaction (ms)", 10, 500, 5, 0, 0)
        self._make_slider(g1, "reaction_var", "Reaction Var", 5, 150, 5, 1, 0)
        self._make_check(g1, "fitts", "Fitts' Law", 2, 0)

        g2 = ttk.LabelFrame(f, text="Spring Dynamics")
        g2.grid(row=0, column=1, sticky="nsew", padx=6, pady=4)

        self._make_slider(g2, "omega", "Omega", 5.0, 80.0, 1.0, 0, 0)
        self._make_slider(g2, "zeta", "Zeta", 0.1, 1.5, 0.01, 1, 0)
        self._make_slider(g2, "overshoot", "Overshoot", 0.0, 0.5, 0.01, 2, 0)

        g3 = ttk.LabelFrame(f, text="Tremor e Fatica")
        g3.grid(row=1, column=0, sticky="nsew", padx=6, pady=4)

        self._make_slider(g3, "tremor", "Tremor", 0.0, 2.0, 0.05, 0, 0)
        self._make_slider(g3, "tremor_hz", "Tremor Hz", 1.0, 20.0, 0.5, 1, 0)
        self._make_check(g3, "fatigue", "Fatigue", 2, 0)
        self._make_slider(g3, "fatigue_rate", "Fatigue Rate", 0.0, 0.05, 0.001, 3, 0)

        g4 = ttk.LabelFrame(f, text="Errore")
        g4.grid(row=1, column=1, sticky="nsew", padx=6, pady=4)

        self._make_slider(g4, "miss_rate", "Miss Rate", 0.0, 0.5, 0.01, 0, 0)
        self._make_slider(g4, "miss_deg", "Miss (deg)", 0.0, 3.0, 0.1, 1, 0)

        g5 = ttk.LabelFrame(f, text="Umanizzazione")
        g5.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=6, pady=4)

        self._make_check(g5, "human", "Enable Human", 0, 0)

    def _build_trigger_tab(self) -> None:
        f = self._trigger_tab
        f.columnconfigure(0, weight=1)

        g1 = ttk.LabelFrame(f, text="Trigger Bot")
        g1.grid(row=0, column=0, sticky="nsew", padx=6, pady=4)

        self._make_check(g1, "trigger", "Enable Trigger", 0, 0)
        self._make_slider(g1, "trigger_radius", "Trigger Radius", 1, 60, 1, 1, 0)
        self._make_slider(g1, "trigger_delay_ms", "Delay (ms)", 0, 200, 5, 2, 0)
        self._make_slider(g1, "trigger_var_ms", "Variance (ms)", 0, 100, 5, 3, 0)
        self._make_slider(g1, "recoil", "Recoil", 0.0, 5.0, 0.1, 4, 0)

    def _build_overlay_tab(self) -> None:
        f = self._overlay_tab
        f.columnconfigure(0, weight=1)
        f.columnconfigure(1, weight=1)

        g1 = ttk.LabelFrame(f, text="Visibilità")
        g1.grid(row=0, column=0, sticky="nsew", padx=6, pady=4)

        self._make_check(g1, "overlay", "Enable Overlay", 0, 0)
        self._make_check(g1, "overlay_skeleton", "Skeleton", 1, 0)
        self._make_check(g1, "overlay_boxes", "Boxes", 2, 0)
        self._make_check(g1, "overlay_aim_circle", "FOV Circle", 3, 0)

        g2 = ttk.LabelFrame(f, text="Colori")
        g2.grid(row=0, column=1, sticky="nsew", padx=6, pady=4)

        self._color_btn = tk.Button(
            g2, text="■ Main Color", bg=self._cfg.overlay_color, fg="white",
            font=("Segoe UI", 9, "bold"), relief="flat", cursor="hand2",
            command=lambda: self._pick_color("overlay_color", self._color_btn),
        )
        self._color_btn.grid(row=0, column=0, padx=8, pady=4, sticky="ew")

        self._skel_color_btn = tk.Button(
            g2, text="■ Skeleton Color", bg=self._cfg.overlay_skeleton_color,
            fg="white", font=("Segoe UI", 9, "bold"), relief="flat", cursor="hand2",
            command=lambda: self._pick_color("overlay_skeleton_color", self._skel_color_btn),
        )
        self._skel_color_btn.grid(row=1, column=0, padx=8, pady=4, sticky="ew")

        g2.columnconfigure(0, weight=1)

    def _build_adv_tab(self) -> None:
        f = self._adv_tab
        f.columnconfigure(0, weight=1)
        f.columnconfigure(1, weight=1)

        g1 = ttk.LabelFrame(f, text="Input")
        g1.grid(row=0, column=0, sticky="nsew", padx=6, pady=4)

        ttk.Label(g1, text="Hold Button:").grid(row=0, column=0, sticky="w", padx=6, pady=3)
        self._hold_var = tk.StringVar(value=self._cfg.hold_button)
        hold_combo = ttk.Combobox(
            g1, textvariable=self._hold_var,
            values=["x1", "x2", "middle"], state="readonly", width=8,
        )
        hold_combo.grid(row=0, column=1, padx=6, pady=3)
        hold_combo.bind("<<ComboboxSelected>>",
                         lambda e: setattr(self._cfg, "hold_button", self._hold_var.get()))

        self._make_check(g1, "toggle_mode", "Toggle Mode", 1, 0, colspan=2)
        self._make_check(g1, "always_active", "Always Active", 2, 0, colspan=2)

        self._make_slider(g1, "crosshair_offset_x", "Crosshair X", -200, 200, 1, 3, 0)
        self._make_slider(g1, "crosshair_offset_y", "Crosshair Y", -200, 200, 1, 4, 0)

        g2 = ttk.LabelFrame(f, text="Processo")
        g2.grid(row=0, column=1, sticky="nsew", padx=6, pady=4)

        ttk.Label(g2, text="Process:").grid(row=0, column=0, sticky="w", padx=6, pady=3)
        self._process_var = tk.StringVar(value=self._cfg.process)
        proc_entry = ttk.Entry(g2, textvariable=self._process_var, width=28)
        proc_entry.grid(row=0, column=1, padx=6, pady=3)
        self._process_var.trace_add(
            "write", lambda *_: setattr(self._cfg, "process", self._process_var.get()),
        )

        self._make_check(g2, "log_metrics", "Log Metrics", 1, 0, colspan=2)
        self._make_check(g2, "third_person", "Third Person", 2, 0, colspan=2)

        g3 = ttk.LabelFrame(f, text="ADS Multiplier")
        g3.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=6, pady=4)

        self._ads_entries: dict = {}
        for i, (zoom, mult) in enumerate(sorted(self._cfg.ads_mult.items(), key=lambda x: float(x[0]))):
            ttk.Label(g3, text=f"{zoom}x:").grid(row=0, column=i * 2, padx=(8, 2), pady=3)
            var = tk.DoubleVar(value=mult)
            entry = ttk.Spinbox(g3, from_=0.1, to=2.0, increment=0.05,
                                textvariable=var, width=6)
            entry.grid(row=0, column=i * 2 + 1, padx=(0, 8), pady=3)
            self._ads_entries[zoom] = var
            var.trace_add("write", lambda *_, z=zoom, v=var: self._on_ads_change(z, v))

        g4 = ttk.LabelFrame(f, text="Self-Tracker (3rd Person)")
        g4.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=6, pady=4)

        self._make_slider(g4, "self_zone_w", "Zone Width", 40, 300, 10, 0, 0)
        self._make_slider(g4, "self_zone_h", "Zone Height", 100, 600, 10, 0, 2)
        self._make_slider(g4, "self_zone_offset_y", "Zone Y Offset", -100, 200, 10, 1, 0)

    def _build_gamepad_tab(self) -> None:
        f = self._gamepad_tab
        f.columnconfigure(0, weight=1)
        f.columnconfigure(1, weight=1)

        g1 = ttk.LabelFrame(f, text="Controller (XInput)")
        g1.grid(row=0, column=0, sticky="nsew", padx=6, pady=4)

        self._make_check(g1, "gamepad", "Abilita Gamepad", 0, 0, colspan=3)

        ttk.Label(g1, text="Tasto Mira:").grid(row=1, column=0, sticky="w", padx=6, pady=3)
        self._gp_trigger_var = tk.StringVar(value=self._cfg.gamepad_aim_trigger)
        gp_combo = ttk.Combobox(
            g1, textvariable=self._gp_trigger_var,
            values=["lt", "rt", "lb", "rb"], state="readonly", width=6,
        )
        gp_combo.grid(row=1, column=1, sticky="w", padx=6, pady=3)
        gp_combo.bind("<<ComboboxSelected>>",
                       lambda e: setattr(self._cfg, "gamepad_aim_trigger", self._gp_trigger_var.get()))

        self._make_slider(g1, "gamepad_trigger_threshold", "Soglia Trigger", 10, 255, 5, 2, 0)

        self._gp_status = ttk.Label(g1, text="Controller: —", style="Dim.TLabel")
        self._gp_status.grid(row=3, column=0, columnspan=3, sticky="w", padx=6, pady=(4, 2))
        ttk.Label(
            g1, text="Soglia = quanto premere il grilletto analogico (0-255).",
            style="Dim.TLabel",
        ).grid(row=4, column=0, columnspan=3, sticky="w", padx=6, pady=(0, 2))

        g2 = ttk.LabelFrame(f, text="Head Snap")
        g2.grid(row=0, column=1, sticky="nsew", padx=6, pady=4)

        self._make_check(g2, "head_snap", "Snap alla testa alla mira", 0, 0, colspan=3)
        self._make_slider(g2, "head_snap_omega", "Omega", 20.0, 120.0, 1.0, 1, 0)
        self._make_slider(g2, "head_snap_zeta", "Zeta", 0.3, 1.0, 0.01, 2, 0)
        self._make_slider(g2, "head_snap_duration_ms", "Durata (ms)", 50, 500, 10, 3, 0)
        ttk.Label(
            g2,
            text="Si applica quando la mira parte dal controller.\n"
                 "Omega alto = snap più rapido, Zeta alto = meno rimbalzo.",
            style="Dim.TLabel", justify="left",
        ).grid(row=4, column=0, columnspan=3, sticky="w", padx=6, pady=(4, 2))

        ttk.Label(
            f,
            text="Lo snap standard (usato dalla mira col mouse) è nella scheda MIRA.",
            style="Dim.TLabel",
        ).grid(row=1, column=0, columnspan=2, sticky="w", padx=12, pady=(2, 4))

    def _build_status_bar(self) -> None:
        bar = tk.Frame(self._root, bg=BG3, height=24)
        bar.pack(fill="x", padx=0, side="bottom")

        self._status_engine = ttk.Label(bar, text="● OFFLINE", style="Status.TLabel")
        self._status_engine.pack(side="left", padx=(8, 16))

        self._status_fps = ttk.Label(bar, text="FPS: —", style="Status.TLabel")
        self._status_fps.pack(side="left", padx=(0, 16))

        self._status_det = ttk.Label(bar, text="DET: —", style="Status.TLabel")
        self._status_det.pack(side="left", padx=(0, 16))

        self._status_state = ttk.Label(bar, text="SEARCH", style="StatusAccent.TLabel")
        self._status_state.pack(side="left", padx=(0, 16))

        self._status_restart = ttk.Label(bar, text="", style="StatusWarn.TLabel")
        self._status_restart.pack(side="left", padx=(0, 16))

        self._status_hotkeys = ttk.Label(
            bar, text="F8:Aim  F9:Trigger  F10:Quit  Ctrl+Arrows:Offset",
            style="Status.TLabel",
        )
        self._status_hotkeys.pack(side="right", padx=8)

    def _build_log(self) -> None:
        frame = tk.Frame(self._root, bg=BG)
        frame.pack(fill="x", padx=8, pady=(0, 4), side="bottom")

        self._log_text = tk.Text(
            frame, height=4, bg=BG3, fg="#88ff88",
            font=("Consolas", 9), state="disabled", wrap="word",
            borderwidth=1, relief="sunken", highlightthickness=0,
        )
        self._log_text.pack(fill="x", side="left", expand=True)
        sb = ttk.Scrollbar(frame, command=self._log_text.yview)
        sb.pack(side="right", fill="y")
        self._log_text.config(yscrollcommand=sb.set)

    # ── Widget factories ──────────────────────────────────────────────

    def _make_slider(
        self, parent: ttk.Frame, attr: str, label: str,
        lo: float, hi: float, step: float, row: int, col: int,
        restart: bool = False,
    ) -> None:
        text = f"{label} *" if restart else label
        lbl = ttk.Label(parent, text=text)
        lbl.grid(row=row, column=col, sticky="w", padx=6, pady=2)
        if restart:
            self._restart_attrs.add(attr)

        # An int setting gets an IntVar so the box reads "180", not "180.0".
        is_int = type(getattr(self._cfg, attr)) is int
        if is_int:
            var: tk.Variable = tk.IntVar(value=int(getattr(self._cfg, attr)))
        else:
            var = tk.DoubleVar(value=float(getattr(self._cfg, attr)))

        scale = ttk.Scale(
            parent, from_=lo, to=hi, variable=var, orient="horizontal", length=150,
        )
        scale.grid(row=row, column=col + 1, padx=4, pady=2, sticky="ew")

        spin_kw = {} if is_int else {"format": "%.3f"}
        spin = ttk.Spinbox(
            parent, from_=lo, to=hi, increment=step, width=7,
            textvariable=var, **spin_kw,
        )
        spin.grid(row=row, column=col + 2, padx=(2, 6), pady=2)

        # Trace the shared variable rather than wiring each widget's own callback:
        # a Scale's command fires only on drag and a Spinbox's only on its arrows,
        # so a value typed into the box never reached the config.
        var.trace_add("write", lambda *_, a=attr, v=var: self._on_slider(a, v))

        parent.columnconfigure(col + 1, weight=1)
        self._slider_labels[attr] = (var, spin)
        self._slider_bounds[attr] = (lo, hi)

    def _make_check(
        self, parent: ttk.Frame, attr: str, label: str,
        row: int, col: int, colspan: int = 1, restart: bool = False,
    ) -> None:
        if restart:
            self._restart_attrs.add(attr)
        var = tk.BooleanVar(value=getattr(self._cfg, attr))
        cb = ttk.Checkbutton(
            parent, text=f"{label} *" if restart else label, variable=var,
            command=lambda a=attr, v=var: self._on_check(a, v),
        )
        cb.grid(row=row, column=col, columnspan=colspan, sticky="w", padx=6, pady=2)
        self._check_vars[attr] = var

    def _restart_legend(self, parent: ttk.Frame, row: int) -> None:
        ttk.Label(
            parent, text="*  si applica al prossimo avvio dell'engine",
            style="Dim.TLabel",
        ).grid(row=row, column=0, columnspan=2, sticky="w", padx=12, pady=(2, 6))

    def _note_restart(self, attr: str) -> None:
        """Flag a setting the running engine only picks up when it is restarted."""
        label = getattr(self, "_status_restart", None)
        if label is None:
            return
        if self._engine is None or not self._engine.is_alive():
            return
        if attr in self._pending_restart:
            return
        self._pending_restart.add(attr)
        label.config(text=f"⟳ riavvia per: {', '.join(sorted(self._pending_restart))}")

    def _clear_restart_note(self) -> None:
        self._pending_restart.clear()
        label = getattr(self, "_status_restart", None)
        if label is not None:
            label.config(text="")

    def _pick_color(self, attr: str, button: tk.Button) -> None:
        current = getattr(self._cfg, attr)
        result = colorchooser.askcolor(color=current, title=f"Scegli colore")
        if result and result[1]:
            setattr(self._cfg, attr, result[1])
            button.config(bg=result[1])

    # ── Callbacks ─────────────────────────────────────────────────────

    def _on_slider(self, attr: str, var: tk.Variable) -> None:
        if self._syncing:
            return
        try:
            value = float(var.get())
        except tk.TclError:
            # An IntVar rejects "45.5"; fall back to the literal text so typing a
            # decimal into an int field rounds instead of being silently dropped.
            value = self._raw_spin_value(attr)
            if value is None:
                return  # half-typed text; wait for something parseable
        lo, hi = self._slider_bounds.get(attr, (float("-inf"), float("inf")))
        value = max(lo, min(hi, value))
        if type(getattr(self._cfg, attr)) is int:
            setattr(self._cfg, attr, int(round(value)))
        else:
            setattr(self._cfg, attr, value)
        if attr in self._restart_attrs:
            self._note_restart(attr)

    def _on_check(self, attr: str, var: tk.BooleanVar) -> None:
        setattr(self._cfg, attr, var.get())
        if attr == "overlay":
            if var.get() and self._overlay is None:
                self._create_overlay()
            elif not var.get() and self._overlay is not None:
                self._overlay.destroy()
                self._overlay = None
        if attr in self._restart_attrs:
            self._note_restart(attr)

    def _raw_spin_value(self, attr: str) -> Optional[float]:
        """Parse whatever text is literally in the spinbox, or None if unusable."""
        entry = self._slider_labels.get(attr)
        if entry is None:
            return None
        try:
            return float(entry[1].get().strip().replace(",", "."))
        except (ValueError, tk.TclError):
            return None

    def _on_capture_change(self) -> None:
        self._cfg.capture = self._capture_var.get()
        self._note_restart("capture")

    def _on_ads_change(self, zoom: str, var: tk.DoubleVar) -> None:
        try:
            self._cfg.ads_mult[zoom] = var.get()
        except tk.TclError:
            pass

    def _on_start(self) -> None:
        if self._engine is not None and self._engine.is_alive():
            return
        self._log_gui("Starting engine...")
        self._clear_restart_note()
        self._engine = Engine(self._cfg, self._log_gui, self._metrics)
        self._engine.start()
        self._start_btn.config(state="disabled", bg="#555")
        self._stop_btn.config(state="normal", bg=RED)
        self._status_engine.config(text="● RUNNING", foreground=GREEN)
        self._metric_labels["engine"].config(text="RUNNING", fg=GREEN)

    def _on_stop(self) -> None:
        if self._engine is not None:
            self._engine.stop()
            self._engine = None
        self._clear_restart_note()
        self._start_btn.config(state="normal", bg=GREEN)
        self._stop_btn.config(state="disabled", bg="#444")
        self._status_engine.config(text="● OFFLINE", foreground=FG_DIM)
        self._metric_labels["engine"].config(text="OFFLINE", fg=FG_DIM)
        self._log_gui("Engine stopped")

    def _on_aim_toggle(self) -> None:
        if self._engine is not None:
            self._engine.enabled = not self._engine.enabled
            on = self._engine.enabled
            self._aim_btn.config(bg=ACCENT if on else "#444")
            self._log_gui(f"Aim: {'ON' if on else 'OFF'}")

    def _on_profile_select(self, event: object = None) -> None:
        name = self._profile_var.get()
        data = load_profile(name)
        if data:
            for k, v in data.items():
                if hasattr(self._cfg, k):
                    setattr(self._cfg, k, v)
            self._sync_ui_from_config()
            self._log_gui(f"Profile loaded: {name}")

    def _on_profile_save(self) -> None:
        name = self._profile_var.get()
        fields = [
            "human", "reaction_ms", "reaction_var", "omega", "zeta",
            "overshoot", "tremor", "tremor_hz", "fatigue", "fatigue_rate",
            "miss_rate", "miss_deg", "sticky_gain", "sticky_radius",
            "snap_duration_ms", "snap_omega", "snap_zeta",
            "head_snap", "head_snap_omega", "head_snap_zeta", "head_snap_duration_ms",
        ]
        data = {f: getattr(self._cfg, f) for f in fields}
        save_profile(name, data)
        self._profile_combo["values"] = profile_names()
        self._log_gui(f"Profile saved: {name}")

    def _on_save(self) -> None:
        self._cfg.save()
        self._log_gui("Config saved to cfg.json")

    def _sync_ui_from_config(self) -> None:
        # The slider variables are traced, so suppress write-back while we push
        # config values into them or every set() would bounce straight back.
        self._syncing = True
        try:
            for attr, (var, _) in self._slider_labels.items():
                val = getattr(self._cfg, attr)
                var.set(int(val) if isinstance(var, tk.IntVar) else float(val))
            for attr, var in self._check_vars.items():
                var.set(getattr(self._cfg, attr))
            self._bone_var.set(self._cfg.bone)
            self._hold_var.set(self._cfg.hold_button)
            self._process_var.set(self._cfg.process)
            self._gp_trigger_var.set(self._cfg.gamepad_aim_trigger)
            self._capture_var.set(self._cfg.capture)
            self._color_btn.config(bg=self._cfg.overlay_color)
            self._skel_color_btn.config(bg=self._cfg.overlay_skeleton_color)
            for zoom, var in self._ads_entries.items():
                if zoom in self._cfg.ads_mult:
                    var.set(self._cfg.ads_mult[zoom])
        finally:
            self._syncing = False

    def _create_overlay(self) -> None:
        try:
            sw, sh = screen_size()
            self._overlay = Overlay(sw, sh)
            self._overlay.create(self._root)
        except Exception:
            logger.warning("Overlay creation failed", exc_info=True)
            self._overlay = None

    # ── Hotkeys ───────────────────────────────────────────────────────

    def _setup_hotkeys(self) -> None:
        try:
            from pynput import mouse, keyboard

            btn_map = {
                "x1": mouse.Button.x1,
                "x2": mouse.Button.x2,
                "middle": mouse.Button.middle,
            }

            def on_mouse_click(x, y, button, pressed):
                # Resolved per click, so changing Hold Button in the GUI takes
                # effect immediately instead of only on the next launch.
                if button != btn_map.get(self._cfg.hold_button, mouse.Button.x2):
                    return
                if not self._engine:
                    return
                if self._cfg.toggle_mode:
                    if pressed:
                        self._toggle_aim_state = not self._toggle_aim_state
                        self._engine.aiming = self._toggle_aim_state
                else:
                    self._engine.aiming = pressed

            def on_key_press(key):
                try:
                    if key in (keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
                        self._ctrl_held = True
                    if self._ctrl_held:
                        step = 5
                        if key == keyboard.Key.up:
                            self._cfg.crosshair_offset_y = max(-200, self._cfg.crosshair_offset_y - step)
                        elif key == keyboard.Key.down:
                            self._cfg.crosshair_offset_y = min(200, self._cfg.crosshair_offset_y + step)
                        elif key == keyboard.Key.left:
                            self._cfg.crosshair_offset_x = max(-200, self._cfg.crosshair_offset_x - step)
                        elif key == keyboard.Key.right:
                            self._cfg.crosshair_offset_x = min(200, self._cfg.crosshair_offset_x + step)
                        elif key == keyboard.Key.home:
                            self._cfg.crosshair_offset_x = 0
                            self._cfg.crosshair_offset_y = 0
                        if key in (keyboard.Key.up, keyboard.Key.down,
                                   keyboard.Key.left, keyboard.Key.right, keyboard.Key.home):
                            self._root.after(0, lambda: self._log_gui(
                                f"Offset: ({self._cfg.crosshair_offset_x}, {self._cfg.crosshair_offset_y})"
                            ))
                            self._sync_ui_from_config()
                            return
                    if key == keyboard.Key.f8:
                        self._root.after(0, self._on_aim_toggle)
                    elif key == keyboard.Key.f9:
                        self._cfg.trigger = not self._cfg.trigger
                        self._check_vars["trigger"].set(self._cfg.trigger)
                        self._root.after(0, lambda: self._log_gui(
                            f"Trigger: {'ON' if self._cfg.trigger else 'OFF'}"
                        ))
                    elif key == keyboard.Key.f10:
                        self._root.after(0, self._on_close)
                except Exception:
                    pass

            def on_key_release(key):
                try:
                    if key in (keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
                        self._ctrl_held = False
                except Exception:
                    pass

            self._mouse_listener = mouse.Listener(on_click=on_mouse_click)
            self._mouse_listener.daemon = True
            self._mouse_listener.start()

            self._kb_listener = keyboard.Listener(on_press=on_key_press, on_release=on_key_release)
            self._kb_listener.daemon = True
            self._kb_listener.start()
        except Exception:
            logger.warning("Hotkey setup failed", exc_info=True)

    # ── Polling and display ───────────────────────────────────────────

    def _start_poll(self) -> None:
        self._poll()

    def _poll(self) -> None:
        try:
            if self._engine is not None and self._engine.is_alive():
                frame = self._engine.get_annotated_frame()
                if frame is not None:
                    self._update_preview(frame)

                crop = self._engine.get_target_crop()
                if crop is not None:
                    self._update_crop(crop)

                if self._overlay is not None and self._cfg.overlay:
                    items = self._engine.get_overlay_items()
                    self._overlay.frame(items)

                self._update_live_metrics()

            self._update_settle_graph()
        except Exception:
            # Logged once rather than swallowed: a repeating GUI fault used to be
            # completely invisible here.
            if not self._poll_failed:
                self._poll_failed = True
                logger.warning("GUI poll failed, continuing", exc_info=True)

        self._poll_id = self._root.after(33, self._poll)

    def _update_preview(self, frame: np.ndarray) -> None:
        try:
            resized = cv2.resize(frame, (300, 300), interpolation=cv2.INTER_AREA)
            rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(rgb)
            self._preview_photo = ImageTk.PhotoImage(img)
            self._preview_canvas.create_image(0, 0, anchor="nw", image=self._preview_photo)
        except Exception:
            pass

    def _update_crop(self, crop: np.ndarray) -> None:
        try:
            rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(rgb)
            self._crop_photo = ImageTk.PhotoImage(img)
            self._crop_canvas.create_image(0, 0, anchor="nw", image=self._crop_photo)
        except Exception:
            pass

    def _update_settle_graph(self) -> None:
        samples = list(self._metrics.settle_samples)
        if len(samples) == self._settle_drawn:
            return  # nothing new; don't repaint 30x a second
        self._settle_drawn = len(samples)

        c = self._settle_canvas
        c.delete("all")
        if not samples:
            c.create_text(90, 45, text="No settle data", fill=FG_DIM,
                          font=("Consolas", 9))
            return
        recent = samples[-20:]
        max_val = max(recent) if recent else 1.0
        if max_val < 1.0:
            max_val = 1.0
        bar_w = 180 / max(len(recent), 1)
        for i, val in enumerate(recent):
            h = (val / max_val) * 80
            x = i * bar_w
            c.create_rectangle(x, 90 - h, x + bar_w - 1, 90, fill=ACCENT2, outline="")

    def _update_live_metrics(self) -> None:
        if self._engine is None:
            return
        eng = self._engine
        state = getattr(eng, "_target_state", "SEARCH")
        trk = getattr(eng, "_tracking_score", 0.0)
        hit = getattr(eng, "_hit_probability", 0.0)
        move = getattr(eng, "_movement_class", "STILL")
        reid = getattr(eng, "_last_reid_score", 0.0)

        tick_times = getattr(eng, "_tick_times", [])
        if tick_times:
            avg_tick = sum(tick_times) / len(tick_times)
            fps = int(1.0 / max(avg_tick, 0.001))
        else:
            fps = 0

        det_intervals = getattr(eng, "_det_intervals", [])
        if det_intervals:
            avg_det = sum(det_intervals) / len(det_intervals)
            det_fps = int(1.0 / max(avg_det, 0.001))
        else:
            det_fps = 0

        self._metric_labels["fps"].config(text=str(fps))
        self._metric_labels["det_fps"].config(text=str(det_fps))
        self._metric_labels["state"].config(
            text=state,
            fg={"SEARCH": FG_DIM, "LOCK": YELLOW, "TRACK": GREEN, "SNAP": ACCENT2}.get(state, FG),
        )
        self._metric_labels["trk_score"].config(text=f"{trk:.0%}")
        self._metric_labels["hit_prob"].config(text=f"{hit:.0%}")
        self._metric_labels["movement"].config(text=move)
        self._metric_labels["reid"].config(text=f"{reid:.2f}")

        self._status_fps.config(text=f"FPS: {fps}")
        self._status_det.config(text=f"DET: {det_fps}")
        state_colors = {"SEARCH": FG_DIM, "LOCK": YELLOW, "TRACK": GREEN, "SNAP": ACCENT2}
        self._status_state.config(text=state, foreground=state_colors.get(state, FG))

        pad = getattr(eng, "_gamepad", None)
        if pad is not None:
            if not self._cfg.gamepad:
                text = "Controller: disabilitato"
            elif not pad.available:
                text = "Controller: XInput non disponibile"
            elif pad.connected:
                text = f"Controller: collegato{'  ◉ MIRA' if pad.aim_down else ''}"
            else:
                text = "Controller: nessuno rilevato"
            self._gp_status.config(text=text)

    def _log_gui(self, msg: str) -> None:
        def _append():
            self._log_text.config(state="normal")
            self._log_text.insert("end", f"{time.strftime('%H:%M:%S')} {msg}\n")
            self._log_text.see("end")
            self._log_text.config(state="disabled")
        self._root.after(0, _append)

    def _on_close(self) -> None:
        if self._engine is not None:
            self._engine.stop()
        if self._overlay is not None:
            self._overlay.destroy()
        if self._cfg.log_metrics:
            self._metrics.csv_append()
        try:
            self._root.quit()
            self._root.destroy()
        except Exception:
            pass

    def run(self) -> None:
        self._root.mainloop()


def main() -> None:
    _elevate()
    app = App()
    app.run()


if __name__ == "__main__":
    main()
