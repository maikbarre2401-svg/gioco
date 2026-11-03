"""Main engine thread: capture -> detect -> aim -> output loop with smooth skeleton."""

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
from core.kalman import Axis, Tracker
from core.metrics import MetricsCollector
from core.output import MouseOutput
from core.skeleton import (
    BONES, bone_point, draw as draw_skeleton, draw_overlay_items,
    heuristic_point, head_radius, body_center, body_radius,
)
from core.utils import clamp, foreground_exe, screen_size
from core.vision import Detection, Vision

logger = logging.getLogger(__name__)


class _BoxSmoother:
    """Kalman-smooth bounding box coordinates to prevent jitter."""

    def __init__(self) -> None:
        self._axes = [Axis(process_noise=120.0, measurement_noise=8.0) for _ in range(4)]
        self._valid = False

    def reset(self) -> None:
        for ax in self._axes:
            ax._initialised = False
        self._valid = False

    def feed(self, box: Tuple[float, float, float, float], dt: float) -> Tuple[float, float, float, float]:
        results = []
        for ax, val in zip(self._axes, box):
            ax.predict(dt)
            results.append(ax.update(val))
        self._valid = True
        return (results[0], results[1], results[2], results[3])

    def predict(self, dt: float) -> Optional[Tuple[float, float, float, float]]:
        if not self._valid:
            return None
        return tuple(ax.predict(dt) for ax in self._axes)


class _KpSmoother:
    """Per-keypoint Kalman smoothing with confidence-adaptive noise for 17 COCO joints."""

    def __init__(self, n_kp: int = 17) -> None:
        self._n = n_kp
        self._axes_x: List[Axis] = [Axis(process_noise=50.0, measurement_noise=5.0) for _ in range(n_kp)]
        self._axes_y: List[Axis] = [Axis(process_noise=50.0, measurement_noise=5.0) for _ in range(n_kp)]
        self._last_kps: Optional[np.ndarray] = None
        self._valid = False

    def reset(self) -> None:
        for ax in self._axes_x:
            ax._initialised = False
        for ay in self._axes_y:
            ay._initialised = False
        self._last_kps = None
        self._valid = False

    def feed(self, kps: Optional[np.ndarray], dt: float) -> Optional[np.ndarray]:
        """Feed raw keypoints, return smoothed (17,3) array or last valid if kps is None."""
        if kps is None or kps.shape[0] < self._n:
            if self._valid and self._last_kps is not None:
                out = self._last_kps.copy()
                for k in range(self._n):
                    if out[k, 2] > 0.1:
                        self._axes_x[k].predict(dt)
                        self._axes_y[k].predict(dt)
                        out[k, 0] = self._axes_x[k]._x[0]
                        out[k, 1] = self._axes_y[k]._x[0]
                        out[k, 2] *= 0.93
                self._last_kps = out
                return out
            return None

        out = kps.copy()
        for k in range(self._n):
            conf = float(kps[k, 2])
            if conf < 0.08:
                continue
            self._axes_x[k]._R = max(1.0, 12.0 - conf * 14.0)
            self._axes_y[k]._R = max(1.0, 12.0 - conf * 14.0)
            self._axes_x[k].predict(dt)
            self._axes_y[k].predict(dt)
            sx = self._axes_x[k].update(float(kps[k, 0]))
            sy = self._axes_y[k].update(float(kps[k, 1]))
            out[k, 0] = sx
            out[k, 1] = sy

        self._last_kps = out
        self._valid = True
        return out

    def extrapolate(self, dt: float) -> Optional[np.ndarray]:
        """Predict keypoint positions forward without a measurement (pure velocity extrapolation)."""
        if not self._valid or self._last_kps is None:
            return None
        out = self._last_kps.copy()
        for k in range(self._n):
            if out[k, 2] > 0.1:
                out[k, 0] = self._axes_x[k].lead(dt)
                out[k, 1] = self._axes_y[k].lead(dt)
        return out


class _AsyncPose:
    """Runs pose inference in a dedicated thread, decoupled from the engine tick."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._request_event = threading.Event()
        self._stop = False
        self._thread: Optional[threading.Thread] = None

        self._req_frame: Optional[np.ndarray] = None
        self._req_box: Optional[Tuple[float, float, float, float]] = None
        self._req_stamp: float = 0.0

        self._result_kps: Optional[np.ndarray] = None
        self._result_stamp: float = 0.0
        self._result_consumed: bool = True

        self._vision: Optional[Vision] = None
        self._busy = False

    def start(self, vision: Vision) -> None:
        self._vision = vision
        self._stop = False
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop = True
        self._request_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def submit(self, frame: np.ndarray, box: Tuple[float, float, float, float]) -> None:
        with self._lock:
            if self._busy:
                return
            self._req_frame = frame
            self._req_box = box
            self._req_stamp = time.perf_counter()
        self._request_event.set()

    def poll(self) -> Tuple[Optional[np.ndarray], float, bool]:
        """Return (keypoints, stamp, is_new). Non-blocking."""
        with self._lock:
            if not self._result_consumed and self._result_kps is not None:
                self._result_consumed = True
                return (self._result_kps.copy(), self._result_stamp, True)
            return (None, 0.0, False)

    def _run(self) -> None:
        while not self._stop:
            self._request_event.wait(timeout=0.5)
            self._request_event.clear()
            if self._stop:
                break

            with self._lock:
                frame = self._req_frame
                box = self._req_box
                stamp = self._req_stamp
                self._req_frame = None
                self._req_box = None
                if frame is None or box is None:
                    continue
                self._busy = True

            kps = None
            try:
                if self._vision is not None:
                    kps = self._vision.keypoints(frame, box)
            except Exception:
                logger.debug("Async pose inference failed", exc_info=True)

            with self._lock:
                self._result_kps = kps
                self._result_stamp = stamp
                self._result_consumed = False
                self._busy = False


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
        self._kp_smoother = _KpSmoother()
        self._box_smoother = _BoxSmoother()
        self._async_pose = _AsyncPose()

        self._frame_lock = threading.Lock()
        self._annotated_frame: Optional[np.ndarray] = None
        self._target_crop: Optional[np.ndarray] = None

        self._last_fg_check: float = 0.0
        self._focused: bool = False
        self._trigger_pending: bool = False
        self._trigger_time: float = 0.0

        self._last_pose_stamp: float = 0.0
        self._cached_smooth_kps: Optional[np.ndarray] = None
        self._snap_start: float = 0.0
        self._snap_active: bool = False
        self._screen_ox: int = 0
        self._screen_oy: int = 0

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value
        if not value:
            self._mouse.release()
            self._aim.release()
            self._kp_smoother.reset()
            self._box_smoother.reset()

    @property
    def aiming(self) -> bool:
        return self._aiming

    @aiming.setter
    def aiming(self, value: bool) -> None:
        self._aiming = value
        if value:
            self._snap_start = time.perf_counter()
            self._snap_active = True
        else:
            self._mouse.release()
            self._aim.release()
            self._snap_active = False

    def get_annotated_frame(self) -> Optional[np.ndarray]:
        with self._frame_lock:
            if self._annotated_frame is not None:
                return self._annotated_frame.copy()
        return None

    def get_target_crop(self) -> Optional[np.ndarray]:
        with self._frame_lock:
            if self._target_crop is not None:
                return self._target_crop.copy()
        return None

    def get_overlay_items(self) -> list:
        return list(self._overlay_items) if hasattr(self, "_overlay_items") else []

    def run(self) -> None:
        self._running = True
        while self._running:
            try:
                self._init_systems()
                self._loop()
            except Exception:
                logger.exception("Engine crashed, restarting in 700ms")
                self._log("Engine error, restarting...")
                self._async_pose.stop()
                time.sleep(0.7)

    def stop(self) -> None:
        self._running = False
        self._async_pose.stop()
        self._mouse.release()

    def _init_systems(self) -> None:
        self._async_pose.stop()
        if self._capturer is not None:
            self._capturer.release()
            self._capturer = None
        self._log("Initialising capture...")
        self._capturer = Capturer(self._cfg.capture)
        self._log("Initialising vision...")
        self._vision = Vision(self._cfg, self._log)
        self._async_pose.start(self._vision)
        try:
            sw, sh = screen_size()
            cap = self._cfg.capture
            self._screen_ox = (sw - cap) // 2
            self._screen_oy = (sh - cap) // 2
        except Exception:
            self._screen_ox = 0
            self._screen_oy = 0
        self._log("Engine ready")

    def _loop(self) -> None:
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

            main_color = self._hex_bgr(self._cfg.overlay_color)
            main_hex = self._cfg.overlay_color
            skel_hex = self._cfg.overlay_skeleton_color

            cox = self._cfg.crosshair_offset_x
            coy = self._cfg.crosshair_offset_y
            scx, scy = w // 2 + cox, h // 2 + coy
            sox, soy = self._screen_ox, self._screen_oy
            fov_r = self._cfg.fov_px
            fov_dim = self._dim_hex(skel_hex, 0.35)
            fov_bright = self._dim_hex(skel_hex, 0.7)
            overlay_items.append(("cross", scx + sox, scy + soy, 10, main_hex))
            overlay_items.append(("circle", scx + sox, scy + soy, fov_r, fov_dim))

            cv2.drawMarker(ann, (scx, scy), main_color, cv2.MARKER_CROSS, 16, 1, cv2.LINE_AA)
            cv2.circle(ann, (scx, scy), fov_r, self._hex_bgr(skel_hex), 1, cv2.LINE_AA)

            fov_detections: List[Detection] = []
            for x1, y1, x2, y2, conf in detections:
                mx = (x1 + x2) / 2.0
                my = (y1 + y2) / 2.0
                dist_to_center = math.hypot(mx - scx, my - scy)
                if dist_to_center <= fov_r:
                    fov_detections.append((x1, y1, x2, y2, conf))

            if self._cfg.overlay_boxes:
                for x1, y1, x2, y2, conf in fov_detections:
                    cv2.rectangle(ann, (int(x1), int(y1)), (int(x2), int(y2)), main_color, 2)
                    overlay_items.append(("box", int(x1) + sox, int(y1) + soy, int(x2) + sox, int(y2) + soy, main_hex))

            n_in_fov = len(fov_detections)
            if n_in_fov > 0:
                cv2.circle(ann, (scx, scy), fov_r, self._hex_bgr(fov_bright), 2, cv2.LINE_AA)
                overlay_items.append(("circle", scx + sox, scy + soy, fov_r + 2, fov_bright))
                label = str(n_in_fov)
                lx = scx + fov_r - 12
                ly = scy - fov_r + 14
                cv2.putText(ann, label, (lx, ly), cv2.FONT_HERSHEY_SIMPLEX, 0.4, self._hex_bgr(fov_bright), 1, cv2.LINE_AA)
                overlay_items.append(("text", lx + sox, ly + soy, label, fov_bright, 10))

            self._aim.set_frame(frame)
            picked = self._aim.pick(fov_detections, w, h)

            smooth_kps: Optional[np.ndarray] = None
            target_point: Optional[Tuple[float, float]] = None

            if picked is not None:
                raw_box = picked
                self._aim.update_reid(frame)

                if not self._aim.engaged:
                    self._aim.begin()
                    self._metrics.lock()
                    self._kp_smoother.reset()
                    self._box_smoother.reset()
                    self._cached_smooth_kps = None

                smoothed_box = self._box_smoother.feed(raw_box, tick_s)
                bx1, by1, bx2, by2 = smoothed_box

                if self._cfg.use_pose and self._vision:
                    self._async_pose.submit(frame, (bx1, by1, bx2, by2))

                    pose_kps, pose_stamp, is_new = self._async_pose.poll()
                    if is_new and pose_kps is not None:
                        smooth_kps = self._kp_smoother.feed(pose_kps, tick_s)
                        self._last_pose_stamp = time.perf_counter()
                        self._cached_smooth_kps = smooth_kps
                    else:
                        since_pose = time.perf_counter() - self._last_pose_stamp
                        if since_pose < 0.25:
                            smooth_kps = self._kp_smoother.extrapolate(since_pose)
                            if smooth_kps is not None:
                                self._cached_smooth_kps = smooth_kps
                        else:
                            smooth_kps = self._kp_smoother.feed(None, tick_s)
                            if smooth_kps is not None:
                                self._cached_smooth_kps = smooth_kps

                display_box = (bx1, by1, bx2, by2)

                snap_phase = False
                if self._snap_active:
                    snap_elapsed = time.perf_counter() - self._snap_start
                    if snap_elapsed < self._cfg.snap_duration_ms / 1000.0:
                        snap_phase = True
                    else:
                        self._snap_active = False

                active_bone = "head" if snap_phase else self._aim.auto_bone(h)

                if smooth_kps is not None:
                    skel_point = bone_point(smooth_kps, active_bone, display_box)
                    heur_point = heuristic_point(active_bone, display_box)

                    if skel_point is not None:
                        avg_conf = float(smooth_kps[:, 2].mean())
                        if avg_conf >= 0.55:
                            target_point = skel_point
                        elif avg_conf >= 0.25:
                            blend = (avg_conf - 0.25) / 0.30
                            target_point = (
                                skel_point[0] * blend + heur_point[0] * (1.0 - blend),
                                skel_point[1] * blend + heur_point[1] * (1.0 - blend),
                            )
                        else:
                            target_point = heur_point

                    if self._cfg.overlay_skeleton:
                        skel_hex = self._cfg.overlay_skeleton_color
                        draw_skeleton(
                            ann, smooth_kps, skel_hex, display_box,
                            th=2, min_conf=self._cfg.kp_conf,
                            draw_fov_circle=self._cfg.overlay_aim_circle,
                        )
                        ov_items = draw_overlay_items(
                            smooth_kps, self._cfg.kp_conf, display_box,
                            color_hex=skel_hex,
                            draw_fov_circle=self._cfg.overlay_aim_circle,
                        )
                        for oi in ov_items:
                            overlay_items.append(self._offset_item(oi, sox, soy))

                if target_point is None:
                    target_point = heuristic_point(active_bone, display_box)
                    px, py = target_point
                    cv2.drawMarker(
                        ann, (int(px), int(py)), main_color,
                        cv2.MARKER_CROSS, 14, 2, cv2.LINE_AA,
                    )
                    overlay_items.append(("cross", int(px) + sox, int(py) + soy, 8, main_hex))
                else:
                    px, py = target_point
                    cv2.circle(ann, (int(px), int(py)), 6, self._hex_bgr(self._dim_hex(self._cfg.overlay_color, 0.3)), -1, cv2.LINE_AA)
                    cv2.circle(ann, (int(px), int(py)), 4, main_color, -1, cv2.LINE_AA)
                    cv2.circle(ann, (int(px), int(py)), 2, (255, 255, 255), -1, cv2.LINE_AA)
                    overlay_items.append(("dot", int(px) + sox, int(py) + soy, 7, self._dim_hex(main_hex, 0.3)))
                    overlay_items.append(("dot", int(px) + sox, int(py) + soy, 4, main_hex))

                active = self._enabled and self._aiming and (self._focused or self._cfg.always_active)
                if active and target_point is not None:
                    aim_c = self._hex_bgr(self._dim_hex(main_hex, 0.4))
                    cv2.line(ann, (scx, scy), (int(px), int(py)), aim_c, 1, cv2.LINE_AA)
                    overlay_items.append(("line", scx + sox, scy + soy, int(px) + sox, int(py) + soy, self._dim_hex(main_hex, 0.25), 1))

                if smooth_kps is not None:
                    avg_conf = float(smooth_kps[:, 2].mean())
                    bar_len = int(min(40, avg_conf * 50))
                    bar_x = int(display_box[2]) + 4
                    bar_y = int(display_box[1])
                    cv2.rectangle(ann, (bar_x, bar_y), (bar_x + 4, bar_y + 40), (40, 40, 40), -1)
                    bar_color = (0, 255, 100) if avg_conf > 0.5 else (0, 180, 255)
                    cv2.rectangle(ann, (bar_x, bar_y + 40 - bar_len), (bar_x + 4, bar_y + 40), bar_color, -1)

                dt = tick_s
                active = self._enabled and self._aiming and (self._focused or self._cfg.always_active)
                if active and target_point is not None:
                    if snap_phase:
                        saved_omega = self._cfg.omega
                        saved_zeta = self._cfg.zeta
                        saved_human = self._cfg.human
                        self._cfg.omega = self._cfg.snap_omega
                        self._cfg.zeta = self._cfg.snap_zeta
                        self._cfg.human = True
                        self._humanizer.skip_reaction()

                    dx, dy, dist = self._aim.step(target_point, w, h, dt, self._ads_mult)

                    if snap_phase:
                        self._cfg.omega = saved_omega
                        self._cfg.zeta = saved_zeta
                        self._cfg.human = saved_human
                    if abs(dx) > 0.5 or abs(dy) > 0.5:
                        self._mouse.move(int(round(dx)), int(round(dy)))

                    if dist < self._cfg.deadzone * 3:
                        self._metrics.snap()
                    if dist < self._cfg.deadzone:
                        self._metrics.settle()

                    self._handle_trigger(dist)

                self._update_crop(frame, raw_box)
            else:
                self._aim.release()
                self._mouse.release()
                self._trigger_pending = False
                self._kp_smoother.reset()
                self._box_smoother.reset()
                self._cached_smooth_kps = None

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

    @staticmethod
    def _hex_bgr(hex_color: str) -> Tuple[int, int, int]:
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return (b, g, r)

    @staticmethod
    def _dim_hex(hex_color: str, factor: float) -> str:
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f"#{int(r * factor):02x}{int(g * factor):02x}{int(b * factor):02x}"

    @staticmethod
    def _offset_item(item: tuple, ox: int, oy: int) -> tuple:
        """Offset an overlay item from frame coordinates to screen coordinates."""
        kind = item[0]
        if kind == "line":
            _, x1, y1, x2, y2, color, width = item
            return ("line", x1 + ox, y1 + oy, x2 + ox, y2 + oy, color, width)
        elif kind == "dot":
            _, x, y, r, color = item
            return ("dot", x + ox, y + oy, r, color)
        elif kind == "box":
            _, x1, y1, x2, y2, color = item
            return ("box", x1 + ox, y1 + oy, x2 + ox, y2 + oy, color)
        elif kind == "circle":
            _, x, y, r, color = item
            return ("circle", x + ox, y + oy, r, color)
        elif kind == "cross":
            _, x, y, s, color = item
            return ("cross", x + ox, y + oy, s, color)
        elif kind == "text":
            _, x, y, text_str, color, size = item
            return ("text", x + ox, y + oy, text_str, color, size)
        return item
