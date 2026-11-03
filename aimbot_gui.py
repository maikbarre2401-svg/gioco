"""Dark Tkinter control panel with live preview, metrics, and hotkey bindings."""

from __future__ import annotations

import ctypes
import logging
import os
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk
from typing import Optional

import cv2
import numpy as np
from PIL import Image, ImageTk

from core.config import Config
from core.engine import Engine
from core.metrics import MetricsCollector
from core.overlay import Overlay
from core.profile import ensure as ensure_profiles, load as load_profile, names as profile_names, save as save_profile
from core.utils import is_admin, screen_size, set_dpi_aware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("gui")

BG = "#1a1a2e"
BG2 = "#16213e"
FG = "#e0e0e0"
ACCENT = "#ff2fd0"
ACCENT2 = "#7a5cff"


def _elevate() -> None:
    """Self-elevate via UAC if not admin."""
    if is_admin():
        return
    try:
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, " ".join(sys.argv), None, 1
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

        self._build_gui()
        self._setup_hotkeys()

        if self._cfg.overlay:
            self._create_overlay()

        self._poll_id: Optional[str] = None
        self._start_poll()
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_gui(self) -> None:
        """Build the dark-themed Tkinter interface."""
        self._root = tk.Tk()
        self._root.title("Aim Assist Control Panel")
        self._root.geometry("820x720")
        self._root.configure(bg=BG)
        self._root.resizable(False, False)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure(".", background=BG, foreground=FG, fieldbackground=BG2)
        style.configure("TNotebook", background=BG)
        style.configure("TNotebook.Tab", background=BG2, foreground=FG, padding=[10, 4])
        style.map("TNotebook.Tab", background=[("selected", ACCENT2)])
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=FG)
        style.configure("TButton", background=BG2, foreground=FG)
        style.configure("TCheckbutton", background=BG, foreground=FG)
        style.configure("TCombobox", fieldbackground=BG2, foreground=FG)
        style.configure("Horizontal.TScale", background=BG, troughcolor=BG2)

        top_frame = tk.Frame(self._root, bg=BG)
        top_frame.pack(fill="x", padx=10, pady=5)

        self._preview_canvas = tk.Canvas(top_frame, width=320, height=320, bg="#000", highlightthickness=0)
        self._preview_canvas.pack(side="left", padx=(0, 5))

        right_top = tk.Frame(top_frame, bg=BG)
        right_top.pack(side="left", fill="both", expand=True)

        self._crop_canvas = tk.Canvas(right_top, width=200, height=200, bg="#000", highlightthickness=0)
        self._crop_canvas.pack(pady=(0, 5))

        self._settle_canvas = tk.Canvas(right_top, width=200, height=80, bg=BG2, highlightthickness=0)
        self._settle_canvas.pack()

        btn_frame = tk.Frame(self._root, bg=BG)
        btn_frame.pack(fill="x", padx=10, pady=5)

        self._start_btn = tk.Button(
            btn_frame, text="AVVIA", bg=ACCENT2, fg="white", font=("Segoe UI", 11, "bold"),
            command=self._on_start, width=10
        )
        self._start_btn.pack(side="left", padx=5)

        self._stop_btn = tk.Button(
            btn_frame, text="FERMA", bg="#333", fg=FG, font=("Segoe UI", 11, "bold"),
            command=self._on_stop, width=10, state="disabled"
        )
        self._stop_btn.pack(side="left", padx=5)

        self._aim_btn = tk.Button(
            btn_frame, text="MIRA", bg=ACCENT, fg="white", font=("Segoe UI", 11, "bold"),
            command=self._on_aim_toggle, width=10
        )
        self._aim_btn.pack(side="left", padx=5)

        prof_frame = tk.Frame(btn_frame, bg=BG)
        prof_frame.pack(side="right")
        tk.Label(prof_frame, text="Profilo:", bg=BG, fg=FG).pack(side="left")
        self._profile_var = tk.StringVar(value="naturale")
        self._profile_combo = ttk.Combobox(
            prof_frame, textvariable=self._profile_var,
            values=profile_names(), state="readonly", width=14
        )
        self._profile_combo.pack(side="left", padx=3)
        self._profile_combo.bind("<<ComboboxSelected>>", self._on_profile_select)

        tk.Button(prof_frame, text="Salva", bg=BG2, fg=FG, command=self._on_profile_save).pack(side="left", padx=2)

        notebook = ttk.Notebook(self._root)
        notebook.pack(fill="both", expand=True, padx=10, pady=5)

        self._aim_tab = ttk.Frame(notebook)
        self._human_tab = ttk.Frame(notebook)
        self._trigger_tab = ttk.Frame(notebook)
        notebook.add(self._aim_tab, text="MIRA")
        notebook.add(self._human_tab, text="UMANO")
        notebook.add(self._trigger_tab, text="TRIGGER")

        self._build_aim_tab()
        self._build_human_tab()
        self._build_trigger_tab()

        checks_frame = tk.Frame(self._root, bg=BG)
        checks_frame.pack(fill="x", padx=10)

        self._check_vars = {}
        checks = [
            ("trigger", "Trigger"), ("human", "Human"), ("use_pose", "Pose"),
            ("overlay", "Overlay"), ("overlay_skeleton", "Skeleton"),
            ("overlay_boxes", "Boxes"), ("always_active", "Always Active"),
            ("toggle_mode", "Toggle Mode"), ("fatigue", "Fatigue"),
            ("log_metrics", "Log Metrics"),
        ]
        for attr, label in checks:
            var = tk.BooleanVar(value=getattr(self._cfg, attr))
            cb = ttk.Checkbutton(checks_frame, text=label, variable=var,
                                 command=lambda a=attr, v=var: self._on_check(a, v))
            cb.pack(side="left", padx=4)
            self._check_vars[attr] = var

        bottom_frame = tk.Frame(self._root, bg=BG)
        bottom_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self._log_text = tk.Text(
            bottom_frame, height=5, bg="#0d0d1a", fg="#88ff88",
            font=("Consolas", 9), state="disabled", wrap="word"
        )
        self._log_text.pack(fill="both", expand=True, side="left")
        scrollbar = ttk.Scrollbar(bottom_frame, command=self._log_text.yview)
        scrollbar.pack(side="right", fill="y")
        self._log_text.config(yscrollcommand=scrollbar.set)

        save_btn = tk.Button(
            self._root, text="SALVA CONFIG", bg=ACCENT2, fg="white",
            font=("Segoe UI", 10, "bold"), command=self._on_save
        )
        save_btn.pack(pady=5)

        self._preview_photo: Optional[ImageTk.PhotoImage] = None
        self._crop_photo: Optional[ImageTk.PhotoImage] = None

    def _build_aim_tab(self) -> None:
        """Build the MIRA (aim) settings tab."""
        f = self._aim_tab
        self._aim_sliders = {}
        sliders = [
            ("conf", "Confidence", 0.1, 0.9, 0.01),
            ("fov_px", "FOV (px)", 50, 800, 10),
            ("max_step", "Max Step", 10, 500, 5),
            ("deadzone", "Deadzone", 0.1, 5.0, 0.1),
            ("counts_per_deg", "Counts/deg", 100, 5000, 50),
            ("hfov_deg", "HFOV (deg)", 40, 120, 1),
            ("tick_hz", "Tick Hz", 60, 500, 10),
            ("lead_ms", "Lead (ms)", 0, 200, 5),
            ("sticky_radius", "Sticky Radius", 0, 150, 5),
            ("sticky_gain", "Sticky Gain", 0.0, 1.0, 0.05),
            ("switch_margin", "Switch Margin", 0.0, 1.0, 0.05),
            ("switch_cooldown_ms", "Switch CD (ms)", 0, 500, 10),
        ]
        for i, (attr, label, lo, hi, step) in enumerate(sliders):
            row, col = divmod(i, 2)
            self._make_slider(f, attr, label, lo, hi, step, row, col * 2)

    def _build_human_tab(self) -> None:
        """Build the UMANO (human) settings tab."""
        f = self._human_tab
        sliders = [
            ("reaction_ms", "Reaction (ms)", 10, 500, 5),
            ("reaction_var", "Reaction Var", 5, 150, 5),
            ("omega", "Omega", 5.0, 80.0, 1.0),
            ("zeta", "Zeta", 0.1, 1.5, 0.01),
            ("overshoot", "Overshoot", 0.0, 0.5, 0.01),
            ("tremor", "Tremor", 0.0, 2.0, 0.05),
            ("tremor_hz", "Tremor Hz", 1.0, 20.0, 0.5),
            ("fatigue_rate", "Fatigue Rate", 0.0, 0.05, 0.001),
            ("miss_rate", "Miss Rate", 0.0, 0.5, 0.01),
            ("miss_deg", "Miss (deg)", 0.0, 3.0, 0.1),
            ("settle_ms", "Settle (ms)", 10, 300, 10),
            ("ads_delay_ms", "ADS Delay (ms)", 0, 500, 10),
        ]
        for i, (attr, label, lo, hi, step) in enumerate(sliders):
            row, col = divmod(i, 2)
            self._make_slider(f, attr, label, lo, hi, step, row, col * 2)

    def _build_trigger_tab(self) -> None:
        """Build the TRIGGER settings tab."""
        f = self._trigger_tab
        sliders = [
            ("trigger_radius", "Trigger Radius", 1, 60, 1),
            ("trigger_delay_ms", "Trigger Delay (ms)", 0, 200, 5),
            ("trigger_var_ms", "Trigger Var (ms)", 0, 100, 5),
            ("recoil", "Recoil", 0.0, 5.0, 0.1),
        ]
        for i, (attr, label, lo, hi, step) in enumerate(sliders):
            row, col = divmod(i, 2)
            self._make_slider(f, attr, label, lo, hi, step, row, col * 2)

    def _make_slider(
        self, parent: ttk.Frame, attr: str, label: str,
        lo: float, hi: float, step: float, row: int, col: int,
    ) -> None:
        """Create a labeled slider bound to a Config attribute."""
        lbl = ttk.Label(parent, text=label)
        lbl.grid(row=row, column=col, sticky="w", padx=5, pady=2)

        var = tk.DoubleVar(value=float(getattr(self._cfg, attr)))
        scale = ttk.Scale(
            parent, from_=lo, to=hi, variable=var, orient="horizontal", length=180,
            command=lambda val, a=attr, v=var: self._on_slider(a, v),
        )
        scale.grid(row=row, column=col + 1, padx=5, pady=2)

        val_lbl = ttk.Label(parent, text=f"{var.get():.2f}", width=8)
        val_lbl.grid(row=row, column=col + 1, sticky="e", padx=(190, 0))

        if not hasattr(self, "_slider_labels"):
            self._slider_labels = {}
        self._slider_labels[attr] = (var, val_lbl)

    def _on_slider(self, attr: str, var: tk.DoubleVar) -> None:
        """Update config and label when a slider changes."""
        value = var.get()
        field_type = type(getattr(self._cfg, attr))
        if field_type is int:
            setattr(self._cfg, attr, int(round(value)))
        else:
            setattr(self._cfg, attr, value)
        if attr in self._slider_labels:
            _, lbl = self._slider_labels[attr]
            lbl.config(text=f"{value:.2f}")

    def _on_check(self, attr: str, var: tk.BooleanVar) -> None:
        """Update config when a checkbutton changes."""
        setattr(self._cfg, attr, var.get())
        if attr == "overlay":
            if var.get() and self._overlay is None:
                self._create_overlay()
            elif not var.get() and self._overlay is not None:
                self._overlay.destroy()
                self._overlay = None

    def _on_start(self) -> None:
        """Start the engine thread."""
        if self._engine is not None and self._engine.is_alive():
            return
        self._log_gui("Starting engine...")
        self._engine = Engine(self._cfg, self._log_gui, self._metrics)
        self._engine.start()
        self._start_btn.config(state="disabled")
        self._stop_btn.config(state="normal")

    def _on_stop(self) -> None:
        """Stop the engine thread."""
        if self._engine is not None:
            self._engine.stop()
            self._engine = None
        self._start_btn.config(state="normal")
        self._stop_btn.config(state="disabled")
        self._log_gui("Engine stopped")

    def _on_aim_toggle(self) -> None:
        """Toggle aiming on the engine."""
        if self._engine is not None:
            self._engine.enabled = not self._engine.enabled
            state = "ON" if self._engine.enabled else "OFF"
            self._aim_btn.config(bg=ACCENT if self._engine.enabled else "#333")
            self._log_gui(f"Aim: {state}")

    def _on_profile_select(self, event: object = None) -> None:
        """Load a selected profile into config."""
        name = self._profile_var.get()
        data = load_profile(name)
        if data:
            for k, v in data.items():
                if hasattr(self._cfg, k):
                    setattr(self._cfg, k, v)
            self._sync_ui_from_config()
            self._log_gui(f"Profile loaded: {name}")

    def _on_profile_save(self) -> None:
        """Save current humanizer settings as a profile."""
        name = self._profile_var.get()
        fields = [
            "human", "reaction_ms", "reaction_var", "omega", "zeta",
            "overshoot", "tremor", "tremor_hz", "fatigue", "fatigue_rate",
            "miss_rate", "miss_deg", "sticky_gain", "sticky_radius",
        ]
        data = {f: getattr(self._cfg, f) for f in fields}
        save_profile(name, data)
        self._profile_combo["values"] = profile_names()
        self._log_gui(f"Profile saved: {name}")

    def _on_save(self) -> None:
        """Save the full config to disk."""
        self._cfg.save()
        self._log_gui("Config saved to cfg.json")

    def _sync_ui_from_config(self) -> None:
        """Sync all UI elements from the current config state."""
        if hasattr(self, "_slider_labels"):
            for attr, (var, lbl) in self._slider_labels.items():
                val = float(getattr(self._cfg, attr))
                var.set(val)
                lbl.config(text=f"{val:.2f}")
        for attr, var in self._check_vars.items():
            var.set(getattr(self._cfg, attr))

    def _create_overlay(self) -> None:
        """Create the transparent overlay window."""
        try:
            sw, sh = screen_size()
            self._overlay = Overlay(sw, sh)
            self._overlay.create(self._root)
        except Exception:
            logger.warning("Overlay creation failed", exc_info=True)
            self._overlay = None

    def _setup_hotkeys(self) -> None:
        """Set up global pynput hotkeys."""
        try:
            from pynput import mouse, keyboard

            btn_map = {
                "x1": mouse.Button.x1,
                "x2": mouse.Button.x2,
                "middle": mouse.Button.middle,
            }
            aim_button = btn_map.get(self._cfg.hold_button, mouse.Button.x2)

            def on_mouse_click(x: int, y: int, button: mouse.Button, pressed: bool) -> None:
                if button == aim_button:
                    if self._cfg.toggle_mode:
                        if pressed:
                            self._toggle_aim_state = not self._toggle_aim_state
                            if self._engine:
                                self._engine.aiming = self._toggle_aim_state
                    else:
                        if self._engine:
                            self._engine.aiming = pressed

            def on_key_press(key: keyboard.Key | keyboard.KeyCode) -> None:
                try:
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

            self._mouse_listener = mouse.Listener(on_click=on_mouse_click)
            self._mouse_listener.daemon = True
            self._mouse_listener.start()

            self._kb_listener = keyboard.Listener(on_press=on_key_press)
            self._kb_listener.daemon = True
            self._kb_listener.start()
        except Exception:
            logger.warning("Hotkey setup failed", exc_info=True)

    def _start_poll(self) -> None:
        """Start the 30 Hz UI polling loop."""
        self._poll()

    def _poll(self) -> None:
        """Update preview, crop, overlay, and settle graph from the main thread."""
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

            self._update_settle_graph()
        except Exception:
            pass

        self._poll_id = self._root.after(33, self._poll)

    def _update_preview(self, frame: np.ndarray) -> None:
        """Render the annotated frame onto the preview canvas."""
        try:
            resized = cv2.resize(frame, (320, 320), interpolation=cv2.INTER_AREA)
            rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(rgb)
            self._preview_photo = ImageTk.PhotoImage(img)
            self._preview_canvas.create_image(0, 0, anchor="nw", image=self._preview_photo)
        except Exception:
            pass

    def _update_crop(self, crop: np.ndarray) -> None:
        """Render the target crop onto the crop canvas."""
        try:
            rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(rgb)
            self._crop_photo = ImageTk.PhotoImage(img)
            self._crop_canvas.create_image(0, 0, anchor="nw", image=self._crop_photo)
        except Exception:
            pass

    def _update_settle_graph(self) -> None:
        """Draw a simple bar graph of recent settle times."""
        canvas = self._settle_canvas
        canvas.delete("all")
        samples = list(self._metrics.settle_samples)
        if not samples:
            canvas.create_text(100, 40, text="No settle data", fill=FG, font=("Consolas", 9))
            return
        recent = samples[-20:]
        max_val = max(recent) if recent else 1.0
        if max_val < 1.0:
            max_val = 1.0
        bar_w = 200 / max(len(recent), 1)
        for i, val in enumerate(recent):
            h = (val / max_val) * 70
            x = i * bar_w
            canvas.create_rectangle(x, 80 - h, x + bar_w - 1, 80, fill=ACCENT2, outline="")

    def _log_gui(self, msg: str) -> None:
        """Append a message to the log text box (thread-safe)."""
        def _append() -> None:
            self._log_text.config(state="normal")
            self._log_text.insert("end", f"{time.strftime('%H:%M:%S')} {msg}\n")
            self._log_text.see("end")
            self._log_text.config(state="disabled")
        self._root.after(0, _append)

    def _on_close(self) -> None:
        """Clean shutdown."""
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
        """Start the Tk main loop."""
        self._root.mainloop()


def main() -> None:
    """Entry point with UAC elevation."""
    _elevate()
    app = App()
    app.run()


if __name__ == "__main__":
    main()
