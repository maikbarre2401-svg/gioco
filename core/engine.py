"""Main engine thread: capture -> detect -> aim -> output loop."""

from __future__ import annotations

import logging
import math
import random
import threading
import time
from typing import Callable, List, Optional, Tuple

import cv2
import numpy as np

from core.aim import Aim
from core.capture import Capturer
from core.config import Config
from core.human import Humanizer
from core.kalman import Tracker
from core.metrics import MetricsCollector
from core.output import MouseOutput
from core.skeleton import bone_point, draw as draw_skeleton, heuristic_point, BONES
from core.utils import clamp, foreground_exe
from core.vision import Detection, Vision

logger = logging.getLogger(__name__)


class Engine(threading.Thread):
    """Aim-assist engine running detection and aim in a background thread."""

    def __init__(
        self,
        cfg: Config,
        log_fn: Callable[[str], None],
        metrics: MetricsCollector,
    ) -> None:
        super().__init__(daemon=True)
        self._cfg = cfg
        self._log = log_fn
        self._metrics = metrics
        self._running = False
        self._enabled = False
        self._aiming = False
        self._ads_mult: float = 1.0

        self._vision: Optional[Vision] = None
        self._capturer: Optional[Capturer] = None
        self._mouse = MouseOutput()
        self._humanizer = Humanizer(cfg)
        self._aim = Aim(cfg, self._humanizer)

        self._frame_lock = threading.Lock()
        self._annotated_frame: Optional[np.ndarray] = None
        self._target_crop: Optional[np.ndarray] = None

        self._last_fg_check: float = 0.0
        self._focused: bool = False
        self._trigger_pending: bool = False
        self._trigger_time: float = 0.0

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value
        if not value:
            self._mouse.release()
            self._aim.release()

    @property
    def aiming(self) -> bool:
        return self._aiming

    @aiming.setter
    def aiming(self, value: bool) -> None:
        self._aiming = value
        if not value:
            self._mouse.release()
            self._aim.release()

    def get_annotated_frame(self) -> Optional[np.ndarray]:
        """Return the latest annotated frame (thread-safe copy)."""
        with self._frame_lock:
            if self._annotated_frame is not None:
                return self._annotated_frame.copy()
        return None

    def get_target_crop(self) -> Optional[np.ndarray]:
        """Return the latest 200x200 target crop (thread-safe copy)."""
        with self._frame_lock:
            if self._target_crop is not None:
                return self._target_crop.copy()
        return None

    def get_overlay_items(self) -> list:
        """Return overlay draw items for the current frame."""
        return list(self._overlay_items) if hasattr(self, "_overlay_items") else []

    def run(self) -> None:
        """Thread entry: run the engine loop with watchdog restart."""
        self._running = True
        while self._running:
            try:
                self._init_systems()
                self._loop()
            except Exception:
                logger.exception("Engine crashed, restarting in 700ms")
                self._log("Engine error, restarting...")
                time.sleep(0.7)

    def stop(self) -> None:
        """Signal the engine to stop."""
        self._running = False
        self._mouse.release()

    def _init_systems(self) -> None:
        """Initialise capture and vision systems."""
        self._log("Initialising capture...")
        self._capturer = Capturer(self._cfg.capture)
        self._log("Initialising vision...")
        self._vision = Vision(self._cfg, self._log)
        self._log("Engine ready")

    def _loop(self) -> None:
        """Main engine cycle loop."""
        tick_s = 1.0 / self._cfg.tick_hz
        self._overlay_items: list = []

        while self._running:
            t0 = time.perf_counter()

            frame = self._capturer.grab() if self._capturer else None
            if frame is None:
                time.sleep(0.05)
                continue

            now = time.monotonic()
            if now - self._last_fg_check > 0.25:
                self._last_fg_check = now
                fg = foreground_exe()
                self._focused = (
                    self._cfg.process.lower() in fg if fg else False
                )

            h, w = frame.shape[:2]
            detections = self._vision.detect(frame) if self._vision else []

            overlay_items: list = []
            ann = frame.copy()

            skel_color = self._hex_bgr(self._cfg.overlay_skeleton_color)
            main_color = self._hex_bgr(self._cfg.overlay_color)
            skel_hex = self._cfg.overlay_skeleton_color
            main_hex = self._cfg.overlay_color

            if self._cfg.overlay_boxes:
                for x1, y1, x2, y2, conf in detections:
                    cv2.rectangle(ann, (int(x1), int(y1)), (int(x2), int(y2)), main_color, 2)
                    overlay_items.append(("box", int(x1), int(y1), int(x2), int(y2), main_hex))

            picked = self._aim.pick(detections, w, h)

            kps: Optional[np.ndarray] = None
            target_point: Optional[Tuple[float, float]] = None

            if picked is not None:
                bx1, by1, bx2, by2 = picked

                if not self._aim.engaged:
                    self._aim.begin()
                    self._metrics.lock()

                if self._cfg.use_pose and self._vision:
                    try:
                        kps = self._vision.keypoints(frame, picked)
                    except Exception:
                        kps = None

                if kps is not None:
                    target_point = bone_point(kps, self._cfg.bone, picked)
                    if self._cfg.overlay_skeleton:
                        draw_skeleton(ann, kps, skel_color, th=2, min_conf=self._cfg.kp_conf)
                        self._add_skeleton_overlay(overlay_items, kps, skel_hex, self._cfg.kp_conf)

                if target_point is None:
                    target_point = heuristic_point(self._cfg.bone, picked)
                    px, py = target_point
                    cv2.drawMarker(
                        ann, (int(px), int(py)), main_color,
                        cv2.MARKER_CROSS, 12, 2, cv2.LINE_AA
                    )
                    overlay_items.append(("cross", int(px), int(py), 8, main_hex))
                else:
                    px, py = target_point
                    cv2.circle(ann, (int(px), int(py)), 4, main_color, -1, cv2.LINE_AA)
                    overlay_items.append(("dot", int(px), int(py), 4, main_hex))

                dt = tick_s
                active = self._enabled and self._aiming and (self._focused or self._cfg.always_active)
                if active and target_point is not None:
                    dx, dy, dist = self._aim.step(target_point, w, h, dt, self._ads_mult)
                    if abs(dx) > 0.5 or abs(dy) > 0.5:
                        self._mouse.move(int(round(dx)), int(round(dy)))

                    if dist < self._cfg.deadzone * 3:
                        self._metrics.snap()
                    if dist < self._cfg.deadzone:
                        self._metrics.settle()

                    self._handle_trigger(dist)

                self._update_crop(frame, picked)
            else:
                self._aim.release()
                self._mouse.release()
                self._trigger_pending = False

            self._overlay_items = overlay_items
            with self._frame_lock:
                self._annotated_frame = ann
                if picked is None:
                    self._target_crop = None

            elapsed = time.perf_counter() - t0
            sleep_time = tick_s - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    def _handle_trigger(self, distance: float) -> None:
        """Handle triggerbot logic."""
        if not self._cfg.trigger:
            return
        if distance <= self._cfg.trigger_radius:
            if not self._trigger_pending:
                self._trigger_pending = True
                delay = max(
                    0,
                    random.gauss(self._cfg.trigger_delay_ms, self._cfg.trigger_var_ms),
                )
                self._trigger_time = time.monotonic() + delay / 1000.0
            elif time.monotonic() >= self._trigger_time:
                self._mouse.click(down=True)
        else:
            if self._trigger_pending:
                self._mouse.click(down=False)
                self._trigger_pending = False

    def _update_crop(
        self, frame: np.ndarray, box: Tuple[float, float, float, float]
    ) -> None:
        """Extract and resize a 200x200 crop around the target box."""
        x1, y1, x2, y2 = box
        fh, fw = frame.shape[:2]
        cx1 = max(0, int(x1) - 10)
        cy1 = max(0, int(y1) - 10)
        cx2 = min(fw, int(x2) + 10)
        cy2 = min(fh, int(y2) + 10)
        crop = frame[cy1:cy2, cx1:cx2]
        if crop.size > 0:
            crop = cv2.resize(crop, (200, 200), interpolation=cv2.INTER_AREA)
            with self._frame_lock:
                self._target_crop = crop

    def _add_skeleton_overlay(
        self,
        items: list,
        kps: np.ndarray,
        color: str,
        min_conf: float,
    ) -> None:
        """Add skeleton lines and dots to overlay items list."""
        if kps is None or kps.shape[0] < 17:
            return
        for i, j in BONES:
            if float(kps[i, 2]) < min_conf or float(kps[j, 2]) < min_conf:
                continue
            items.append((
                "line",
                int(kps[i, 0]), int(kps[i, 1]),
                int(kps[j, 0]), int(kps[j, 1]),
                color, 2,
            ))
        for k in range(17):
            if float(kps[k, 2]) < min_conf:
                continue
            items.append(("dot", int(kps[k, 0]), int(kps[k, 1]), 3, color))

    @staticmethod
    def _hex_bgr(hex_color: str) -> Tuple[int, int, int]:
        """Convert '#rrggbb' to BGR tuple."""
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return (b, g, r)
