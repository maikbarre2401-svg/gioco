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
from core.gamepad import Gamepad
from core.human import Humanizer
from core.kalman import Axis, Tracker
from core.metrics import MetricsCollector
from core.output import MouseOutput
from core.skeleton import (
    BONES, bone_point, progressive_bone, multi_bone_aim, target_silhouette,
    draw as draw_skeleton, draw_overlay_items, preprocess as preprocess_skeleton,
    heuristic_point, head_radius, body_center, body_radius, pose_stability,
)
from core.utils import clamp, foreground_exe, screen_size
from core.vision import Detection, Vision

logger = logging.getLogger(__name__)


class _BoxSmoother:
    """Kalman-smooth bounding box coordinates to prevent jitter.

    Time is advanced by advance(dt) once per engine tick; correct(box) folds in a
    new measurement without advancing time again. This keeps the filter correct
    when detections arrive less often than ticks.
    """

    def __init__(self) -> None:
        self._axes = [Axis(process_noise=45.0, measurement_noise=2.0) for _ in range(4)]
        self._valid = False

    def reset(self) -> None:
        for ax in self._axes:
            ax._initialised = False
        self._valid = False

    def advance(self, dt: float) -> Optional[Tuple[float, float, float, float]]:
        """Step the filter forward by dt without a measurement."""
        if not self._valid:
            return None
        return tuple(ax.predict(dt) for ax in self._axes)

    def correct(self, box: Tuple[float, float, float, float]) -> Tuple[float, float, float, float]:
        """Fold in a measurement at the current filter time."""
        results = [ax.update(val) for ax, val in zip(self._axes, box)]
        self._valid = True
        return (results[0], results[1], results[2], results[3])

    def feed(self, box: Tuple[float, float, float, float], dt: float) -> Tuple[float, float, float, float]:
        self.advance(dt)
        return self.correct(box)


class _KpSmoother:
    """Per-keypoint Kalman smoothing with confidence-adaptive noise for 17 COCO joints.

    Time is tracked internally: feed() uses the real elapsed time since the last
    measurement instead of the engine tick period. This keeps velocity estimates
    correct when poses arrive less often than ticks (the typical case with async
    pose inference).
    """

    def __init__(self, n_kp: int = 17) -> None:
        self._n = n_kp
        self._axes_x: List[Axis] = [Axis(process_noise=30.0, measurement_noise=2.0) for _ in range(n_kp)]
        self._axes_y: List[Axis] = [Axis(process_noise=30.0, measurement_noise=2.0) for _ in range(n_kp)]
        self._last_kps: Optional[np.ndarray] = None
        self._valid = False
        self._miss_count: List[int] = [0] * n_kp
        self._max_hold: int = 12
        self._last_feed_time: float = 0.0

    def reset(self) -> None:
        for ax in self._axes_x:
            ax._initialised = False
        for ay in self._axes_y:
            ay._initialised = False
        self._last_kps = None
        self._valid = False
        self._miss_count = [0] * self._n
        self._last_feed_time = 0.0

    def feed(self, kps: Optional[np.ndarray], dt_fallback: float) -> Optional[np.ndarray]:
        """Feed raw keypoints, return smoothed (17,3) array or last valid if kps is None.

        dt_fallback is used only on the very first call or for miss-hold advances.
        For actual measurements the real elapsed time since the previous feed() is used,
        so the Kalman velocity/acceleration track real motion speed regardless of how
        often the pose thread delivers results.
        """
        now = time.perf_counter()
        if self._last_feed_time > 0.0:
            real_dt = max(0.001, now - self._last_feed_time)
        else:
            real_dt = dt_fallback
        self._last_feed_time = now

        if kps is None or kps.shape[0] < self._n:
            if self._valid and self._last_kps is not None:
                out = self._last_kps.copy()
                for k in range(self._n):
                    self._miss_count[k] += 1
                    if out[k, 2] > 0.05 and self._miss_count[k] <= self._max_hold:
                        self._axes_x[k].predict(dt_fallback)
                        self._axes_y[k].predict(dt_fallback)
                        out[k, 0] = self._axes_x[k]._x[0]
                        out[k, 1] = self._axes_y[k]._x[0]
                        decay = 0.97 if self._miss_count[k] <= 4 else 0.92
                        out[k, 2] *= decay
                    elif self._miss_count[k] > self._max_hold:
                        out[k, 2] = 0.0
                self._last_kps = out
                return out
            return None

        out = kps.copy()
        for k in range(self._n):
            conf = float(kps[k, 2])
            if conf < 0.05:
                if self._last_kps is not None and float(self._last_kps[k, 2]) > 0.1 and self._miss_count[k] < self._max_hold:
                    self._miss_count[k] += 1
                    self._axes_x[k].predict(real_dt)
                    self._axes_y[k].predict(real_dt)
                    out[k, 0] = self._axes_x[k]._x[0]
                    out[k, 1] = self._axes_y[k]._x[0]
                    out[k, 2] = float(self._last_kps[k, 2]) * 0.95
                continue
            self._miss_count[k] = 0
            adaptive_r = max(0.5, 8.0 - conf * 10.0)
            self._axes_x[k]._R_base = adaptive_r
            self._axes_y[k]._R_base = adaptive_r
            self._axes_x[k].predict(real_dt)
            self._axes_y[k].predict(real_dt)
            sx = self._axes_x[k].update(float(kps[k, 0]))
            sy = self._axes_y[k].update(float(kps[k, 1]))
            out[k, 0] = sx
            out[k, 1] = sy

        self._last_kps = out
        self._valid = True
        return out

    def extrapolate(self, dt: float) -> Optional[np.ndarray]:
        """Predict keypoint positions forward using Kalman lead (velocity+acceleration)."""
        if not self._valid or self._last_kps is None:
            return None
        out = self._last_kps.copy()
        for k in range(self._n):
            if out[k, 2] > 0.05 and self._miss_count[k] < self._max_hold:
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


class _AsyncDetect:
    """Runs YOLO detection in a dedicated thread so the aim loop runs at full tick rate."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._request_event = threading.Event()
        self._stop = False
        self._thread: Optional[threading.Thread] = None

        self._req_frame: Optional[np.ndarray] = None
        self._req_box: Optional[Tuple[float, float, float, float]] = None

        self._result: List[Detection] = []
        self._result_stamp: float = 0.0
        self._generation: int = 0

        self._vision: Optional[Vision] = None
        self._busy = False

    def start(self, vision: Vision) -> None:
        self._vision = vision
        self._stop = False
        self._result = []
        self._generation = 0
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop = True
        self._request_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def submit(self, frame: np.ndarray, tracked_box: Optional[Tuple[float, float, float, float]]) -> None:
        """Queue a frame for detection. Skipped while a detection is in flight."""
        with self._lock:
            if self._busy:
                return
            self._req_frame = frame
            self._req_box = tracked_box
        self._request_event.set()

    def latest(self) -> Tuple[List[Detection], float, int]:
        """Return (detections, stamp, generation). Never blocks; may be slightly stale."""
        with self._lock:
            return (list(self._result), self._result_stamp, self._generation)

    def _run(self) -> None:
        while not self._stop:
            self._request_event.wait(timeout=0.5)
            self._request_event.clear()
            if self._stop:
                break

            with self._lock:
                frame = self._req_frame
                box = self._req_box
                self._req_frame = None
                self._req_box = None
                if frame is None:
                    continue
                self._busy = True

            dets: List[Detection] = []
            try:
                if self._vision is not None:
                    dets = self._vision.detect(frame, tracked_box=box)
            except Exception:
                logger.debug("Async detection failed", exc_info=True)

            with self._lock:
                self._result = dets
                self._result_stamp = time.perf_counter()
                self._generation += 1
                self._busy = False


class _SelfTracker:
    """Identifies the player's own character in 3rd person by positional stability.

    The player's body sits in a fixed screen region and barely moves in screen
    space because the camera follows it. Enemies that cross that region move.
    So a candidate must stay put for several frames before it is treated as self,
    and from then on it is excluded by box identity rather than by position.
    """

    def __init__(self) -> None:
        self._box: Optional[Tuple[float, float, float, float]] = None
        self._hits: int = 0
        self._misses: int = 0
        self._locked: bool = False
        self._lock_frames: int = 15
        self._max_misses: int = 25

    def reset(self) -> None:
        self._box = None
        self._hits = 0
        self._misses = 0
        self._locked = False

    @property
    def locked(self) -> bool:
        return self._locked

    @property
    def box(self) -> Optional[Tuple[float, float, float, float]]:
        return self._box if self._locked else None

    def update(
        self, dets: List[Detection], cx: float, cy: float, h: int, cfg: Config
    ) -> None:
        """Advance the self-track against this frame's detections."""
        zone_x1 = cx - cfg.self_zone_w / 2.0
        zone_x2 = cx + cfg.self_zone_w / 2.0
        zone_y1 = cy + cfg.self_zone_offset_y
        zone_y2 = cy + cfg.self_zone_offset_y + cfg.self_zone_h

        best = None
        best_score = -1.0
        for d in dets:
            mx = (d[0] + d[2]) / 2.0
            my = (d[1] + d[3]) / 2.0
            bh = d[3] - d[1]
            if not (zone_x1 <= mx <= zone_x2 and zone_y1 <= my <= zone_y2):
                continue
            if bh < h * 0.18:
                continue
            score = bh / max(1.0, float(h))
            if self._box is not None:
                score += _iou_box(d[:4], self._box) * 2.0
            if score > best_score:
                best_score = score
                best = d

        if best is None:
            self._misses += 1
            if self._misses > self._max_misses:
                self.reset()
            return

        cand = (best[0], best[1], best[2], best[3])
        if self._box is None:
            self._box = cand
            self._hits = 1
            self._misses = 0
            return

        overlap = _iou_box(cand, self._box)
        if overlap > 0.55:
            self._hits += 1
            self._misses = 0
            a = 0.25
            self._box = tuple(
                self._box[i] * (1.0 - a) + cand[i] * a for i in range(4)
            )
            if self._hits >= self._lock_frames:
                self._locked = True
        else:
            self._hits = max(0, self._hits - 2)
            self._misses += 1
            if self._hits == 0:
                self._box = cand
                self._locked = False

    def is_self(self, det: Detection) -> bool:
        """True if this detection is the tracked player character."""
        if not self._locked or self._box is None:
            return False
        return _iou_box(det[:4], self._box) > 0.45


def _iou_box(a, b) -> float:
    ix1 = max(a[0], b[0])
    iy1 = max(a[1], b[1])
    ix2 = min(a[2], b[2])
    iy2 = min(a[3], b[3])
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    aa = max(0.0, (a[2] - a[0]) * (a[3] - a[1]))
    ab = max(0.0, (b[2] - b[0]) * (b[3] - b[1]))
    union = aa + ab - inter
    return inter / union if union > 1e-6 else 0.0


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
        self._async_detect = _AsyncDetect()
        self._self_tracker = _SelfTracker()
        self._gamepad = Gamepad(
            aim_trigger=cfg.gamepad_aim_trigger,
            trigger_threshold=cfg.gamepad_trigger_threshold,
        )
        self._det_generation: int = -1
        self._last_box_stamp: float = 0.0
        self._smoothed_box: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
        self._det_intervals: List[float] = []
        self._last_det_tick: float = 0.0

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
        self._head_snap_active: bool = False
        self._screen_ox: int = 0
        self._screen_oy: int = 0

        self._target_state: str = "SEARCH"
        self._lock_time: float = 0.0
        self._prev_kps_history: List[Optional[np.ndarray]] = []
        self._max_kps_history: int = 10
        self._prev_target_cx: float = 0.0
        self._prev_target_cy: float = 0.0
        self._target_vx: float = 0.0
        self._target_vy: float = 0.0
        self._vel_smooth: float = 0.85
        self._last_reid_score: float = 0.0
        self._tick_count: int = 0

        self._aim_trail: List[Tuple[int, int]] = []
        self._max_aim_trail: int = 18
        self._adaptive_fov: float = 0.0
        self._tick_times: List[float] = []
        self._movement_class: str = "STILL"
        self._hit_probability: float = 0.0
        self._all_detections_for_radar: List[Detection] = []
        self._occlusion_warning: bool = False
        self._target_edge_dist: float = 999.0
        self._confidence_trend: List[float] = []
        self._max_conf_trend: int = 20
        self._state_blend: float = 0.0
        self._tracking_score: float = 0.0

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
            self._target_state = "SEARCH"
            self._prev_kps_history.clear()

    @property
    def aiming(self) -> bool:
        return self._aiming

    @aiming.setter
    def aiming(self, value: bool) -> None:
        was_aiming = self._aiming
        self._aiming = value
        if value:
            self._snap_start = time.perf_counter()
            self._snap_active = True
            self._head_snap_active = self._cfg.head_snap and self._gamepad.aim_down
        else:
            self._mouse.release()
            self._aim.release()
            self._snap_active = False
            self._head_snap_active = False

    def aiming_from_gamepad(self, pressed: bool) -> None:
        """Called by gamepad callbacks — sets aiming and head snap flag."""
        self._head_snap_active = self._cfg.head_snap and pressed
        self.aiming = pressed

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
                self._gamepad.stop()
                self._async_pose.stop()
                self._async_detect.stop()
                time.sleep(0.7)

    def stop(self) -> None:
        self._running = False
        self._gamepad.stop()
        self._async_pose.stop()
        self._async_detect.stop()
        self._mouse.release()

    def _init_systems(self) -> None:
        self._async_pose.stop()
        self._async_detect.stop()
        if self._capturer is not None:
            self._capturer.release()
            self._capturer = None
        self._log("Initialising capture...")
        self._capturer = Capturer(self._cfg.capture)
        self._log("Initialising vision...")
        self._vision = Vision(self._cfg, self._log)
        self._async_pose.start(self._vision)
        self._async_detect.start(self._vision)
        self._self_tracker.reset()
        self._det_generation = -1
        if self._cfg.gamepad:
            self._gamepad.configure(self._cfg.gamepad_aim_trigger, self._cfg.gamepad_trigger_threshold)
            self._gamepad.set_callbacks(
                on_press=lambda: self.aiming_from_gamepad(True),
                on_release=lambda: self.aiming_from_gamepad(False),
            )
            self._gamepad.start()
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
            trk_box = self._aim.target_box
            self._async_detect.submit(frame, trk_box)
            detections, det_stamp, det_gen = self._async_detect.latest()
            det_is_new = det_gen != self._det_generation
            if det_is_new:
                self._det_generation = det_gen

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

            if self._target_state == "TRACK" or self._target_state == "SNAP":
                target_fov_shrink = 0.92
            elif self._target_state == "LOCK":
                target_fov_shrink = 0.96
            else:
                target_fov_shrink = 1.0
            self._adaptive_fov += (target_fov_shrink - self._adaptive_fov) * 0.08 if self._adaptive_fov > 0 else 0
            if self._adaptive_fov == 0:
                self._adaptive_fov = target_fov_shrink
            eff_fov = int(fov_r * self._adaptive_fov)

            self_box: Optional[Tuple[float, float, float, float]] = None
            if self._cfg.third_person:
                if det_is_new:
                    self._self_tracker.update(detections, scx, scy, h, self._cfg)
                self_box = self._self_tracker.box
                if self_box is not None:
                    detections = [d for d in detections if not self._self_tracker.is_self(d)]
                    sx1, sy1, sx2, sy2 = (int(v) for v in self_box)
                    cv2.rectangle(ann, (sx1, sy1), (sx2, sy2), (70, 70, 70), 1, cv2.LINE_AA)
                    cv2.putText(ann, "SELF", (sx1, sy1 - 4),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.3, (90, 90, 90), 1, cv2.LINE_AA)

            self._all_detections_for_radar = list(detections)

            fov_detections: List[Detection] = []
            for x1, y1, x2, y2, conf in detections:
                mx = (x1 + x2) / 2.0
                my = (y1 + y2) / 2.0
                dist_to_center = math.hypot(mx - scx, my - scy)
                if dist_to_center <= eff_fov:
                    fov_detections.append((x1, y1, x2, y2, conf))

            if self._cfg.overlay_boxes:
                for x1, y1, x2, y2, conf in fov_detections:
                    mx = (x1 + x2) / 2.0
                    my = (y1 + y2) / 2.0
                    cdist = math.hypot(mx - scx, my - scy)
                    prox = max(0.0, 1.0 - cdist / max(1.0, eff_fov))
                    box_hex = self._threat_hex(main_hex, prox * 0.6)
                    cv2.rectangle(ann, (int(x1), int(y1)), (int(x2), int(y2)), self._hex_bgr(box_hex), 2)
                    overlay_items.append(("box", int(x1) + sox, int(y1) + soy, int(x2) + sox, int(y2) + soy, box_hex))
                    conf_label = f"{conf:.0%}"
                    cv2.putText(ann, conf_label, (int(x1), int(y2) + 12),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.3, self._hex_bgr(box_hex), 1, cv2.LINE_AA)

            n_in_fov = len(fov_detections)
            threat_factor = 0.0
            if n_in_fov > 0:
                closest_dist = min(
                    math.hypot((d[0] + d[2]) / 2 - scx, (d[1] + d[3]) / 2 - scy)
                    for d in fov_detections
                )
                threat_factor = max(0.0, 1.0 - closest_dist / eff_fov)
                threat_hex = self._threat_hex(skel_hex, threat_factor)
                cv2.circle(ann, (scx, scy), eff_fov, self._hex_bgr(threat_hex), 2, cv2.LINE_AA)
                overlay_items.append(("circle", scx + sox, scy + soy, eff_fov + 2, threat_hex))
                label = str(n_in_fov)
                lx = scx + eff_fov - 12
                ly = scy - eff_fov + 14
                cv2.putText(ann, label, (lx, ly), cv2.FONT_HERSHEY_SIMPLEX, 0.4, self._hex_bgr(threat_hex), 1, cv2.LINE_AA)
                overlay_items.append(("text", lx + sox, ly + soy, label, threat_hex, 10))

            self._draw_radar(
                ann, overlay_items, self._all_detections_for_radar, fov_detections,
                scx, scy, eff_fov, w, h, sox, soy, main_hex,
            )

            self._aim.set_frame(frame)
            self._aim.set_velocity(self._target_vx, self._target_vy, self._movement_class)
            picked = self._aim.pick(fov_detections, w, h)
            self._tick_count += 1

            smooth_kps: Optional[np.ndarray] = None
            target_point: Optional[Tuple[float, float]] = None

            if picked is not None:
                raw_box = picked
                if det_is_new:
                    self._aim.update_reid(frame)
                    if self._aim._reid.ready and self._aim._frame_ref is not None:
                        self._last_reid_score = self._aim._reid.score(self._aim._frame_ref, raw_box)

                if not self._aim.engaged:
                    self._aim.begin()
                    self._metrics.lock()
                    self._kp_smoother.reset()
                    self._box_smoother.reset()
                    self._cached_smooth_kps = None
                    self._lock_time = time.perf_counter()
                    self._prev_kps_history.clear()
                    self._prev_target_cx = (raw_box[0] + raw_box[2]) / 2
                    self._prev_target_cy = (raw_box[1] + raw_box[3]) / 2
                    self._target_vx = 0.0
                    self._target_vy = 0.0
                    self._last_box_stamp = time.perf_counter()
                    self._smoothed_box = raw_box

                advanced = self._box_smoother.advance(tick_s)
                if det_is_new:
                    smoothed_box = self._box_smoother.correct(raw_box)
                    now_p = time.perf_counter()
                    box_dt = max(0.001, now_p - self._last_box_stamp)
                    self._last_box_stamp = now_p
                    tcx_now = (smoothed_box[0] + smoothed_box[2]) / 2.0
                    tcy_now = (smoothed_box[1] + smoothed_box[3]) / 2.0
                    raw_vx = (tcx_now - self._prev_target_cx) / box_dt
                    raw_vy = (tcy_now - self._prev_target_cy) / box_dt
                    self._target_vx = self._target_vx * self._vel_smooth + raw_vx * (1 - self._vel_smooth)
                    self._target_vy = self._target_vy * self._vel_smooth + raw_vy * (1 - self._vel_smooth)
                    self._prev_target_cx = tcx_now
                    self._prev_target_cy = tcy_now
                else:
                    smoothed_box = advanced if advanced is not None else self._smoothed_box
                    tcx_now = (smoothed_box[0] + smoothed_box[2]) / 2.0
                    tcy_now = (smoothed_box[1] + smoothed_box[3]) / 2.0

                self._smoothed_box = smoothed_box
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
                        if since_pose < 0.5:
                            smooth_kps = self._kp_smoother.extrapolate(since_pose)
                            if smooth_kps is not None:
                                self._cached_smooth_kps = smooth_kps
                        else:
                            smooth_kps = self._kp_smoother.feed(None, tick_s)
                            if smooth_kps is not None:
                                self._cached_smooth_kps = smooth_kps

                if smooth_kps is not None:
                    self._prev_kps_history.append(smooth_kps.copy())
                    if len(self._prev_kps_history) > self._max_kps_history:
                        self._prev_kps_history.pop(0)

                display_box = (bx1, by1, bx2, by2)

                snap_phase = False
                snap_blend = 0.0
                if self._snap_active:
                    snap_elapsed = time.perf_counter() - self._snap_start
                    if self._head_snap_active:
                        snap_dur = self._cfg.head_snap_duration_ms / 1000.0
                    else:
                        snap_dur = self._cfg.snap_duration_ms / 1000.0
                    if snap_elapsed < snap_dur:
                        snap_phase = True
                        t = snap_elapsed / snap_dur
                        snap_blend = 1.0 - t * t * (3.0 - 2.0 * t)
                    else:
                        self._snap_active = False
                        self._head_snap_active = False

                avg_kp_conf = float(smooth_kps[:, 2].mean()) if smooth_kps is not None else 0.0
                self._confidence_trend.append(avg_kp_conf)
                if len(self._confidence_trend) > self._max_conf_trend:
                    self._confidence_trend.pop(0)

                edge_margin = 30.0
                self._target_edge_dist = min(
                    tcx_now - 0, w - tcx_now, tcy_now - 0, h - tcy_now
                )
                speed = math.hypot(self._target_vx, self._target_vy)
                conf_dropping = False
                if len(self._confidence_trend) >= 6:
                    recent = self._confidence_trend[-3:]
                    older = self._confidence_trend[-6:-3]
                    conf_dropping = sum(recent) / 3 < sum(older) / 3 * 0.75
                self._occlusion_warning = (
                    self._target_edge_dist < edge_margin and speed > 30
                ) or conf_dropping

                reid_factor = min(1.0, self._last_reid_score / 0.7) if self._last_reid_score > 0 else 0.5
                speed_penalty = max(0.0, 1.0 - speed / 500.0)
                track_dur = min(1.0, (time.perf_counter() - self._lock_time) / 2.0)
                stability = pose_stability(
                    smooth_kps, self._prev_kps_history[:-1] if len(self._prev_kps_history) > 1 else None,
                    self._cfg.kp_conf,
                )
                self._tracking_score = (
                    avg_kp_conf * 0.25 + reid_factor * 0.20 +
                    speed_penalty * 0.15 + track_dur * 0.10 + stability * 0.20 + 0.10
                )
                self._tracking_score = max(0.0, min(1.0, self._tracking_score))

                if snap_phase:
                    self._target_state = "SNAP"
                elif smooth_kps is not None and avg_kp_conf > 0.4:
                    self._target_state = "TRACK"
                else:
                    self._target_state = "LOCK"

                if self._head_snap_active and snap_phase:
                    preferred_bone = "head"
                elif snap_phase:
                    preferred_bone = "head"
                else:
                    preferred_bone = self._aim.auto_bone(h)

                if smooth_kps is not None:
                    skel_point_val, actual_bone = progressive_bone(
                        smooth_kps, preferred_bone, display_box, self._cfg.kp_conf
                    )
                    multi_pt = multi_bone_aim(smooth_kps, preferred_bone, display_box, self._cfg.kp_conf)
                    heur_point_val = heuristic_point(actual_bone, display_box)

                    if skel_point_val is not None:
                        avg_conf = float(smooth_kps[:, 2].mean())
                        if avg_conf >= 0.60:
                            target_point = skel_point_val
                        elif avg_conf >= 0.40 and multi_pt is not None:
                            blend = (avg_conf - 0.40) / 0.20
                            target_point = (
                                skel_point_val[0] * blend + multi_pt[0] * (1 - blend),
                                skel_point_val[1] * blend + multi_pt[1] * (1 - blend),
                            )
                        elif avg_conf >= 0.25:
                            blend = (avg_conf - 0.25) / 0.15
                            base = multi_pt if multi_pt else heur_point_val
                            target_point = (
                                base[0] * blend + heur_point_val[0] * (1 - blend),
                                base[1] * blend + heur_point_val[1] * (1 - blend),
                            )
                        else:
                            target_point = heur_point_val

                    hull = target_silhouette(smooth_kps, display_box, self._cfg.kp_conf)
                    if hull is not None:
                        sil_c = self._hex_bgr(self._dim_hex(skel_hex, 0.12))
                        cv2.polylines(ann, [hull], True, sil_c, 1, cv2.LINE_AA)

                    if self._cfg.overlay_skeleton:
                        skel_hex = self._cfg.overlay_skeleton_color
                        skel_prep = preprocess_skeleton(smooth_kps, display_box, self._cfg.kp_conf)
                        prev_kps = self._prev_kps_history[:-1] if len(self._prev_kps_history) > 1 else None
                        draw_skeleton(
                            ann, smooth_kps, skel_hex, display_box,
                            th=2, min_conf=self._cfg.kp_conf,
                            draw_fov_circle=self._cfg.overlay_aim_circle,
                            prev_kps_list=prev_kps,
                            preprocessed=skel_prep,
                        )
                        ov_items = draw_overlay_items(
                            smooth_kps, self._cfg.kp_conf, display_box,
                            color_hex=skel_hex,
                            draw_fov_circle=self._cfg.overlay_aim_circle,
                            prev_kps_list=prev_kps,
                            preprocessed=skel_prep,
                        )
                        for oi in ov_items:
                            overlay_items.append(self._offset_item(oi, sox, soy))

                if target_point is None:
                    target_point = heuristic_point(preferred_bone, display_box)
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

                self._aim_trail.append((int(px), int(py)))
                if len(self._aim_trail) > self._max_aim_trail:
                    self._aim_trail.pop(0)
                self._draw_aim_trail(ann, overlay_items, sox, soy, main_hex)

                speed = math.hypot(self._target_vx, self._target_vy)
                self._movement_class = self._classify_movement()

                if speed > 15.0:
                    arrow_scale = min(40.0, speed * 0.15)
                    norm = max(1.0, speed)
                    arx = int(tcx_now + self._target_vx / norm * arrow_scale)
                    ary = int(tcy_now + self._target_vy / norm * arrow_scale)
                    vel_color = self._hex_bgr(self._dim_hex(main_hex, 0.5))
                    cv2.arrowedLine(ann, (int(tcx_now), int(tcy_now)), (arx, ary), vel_color, 2, cv2.LINE_AA, tipLength=0.3)
                    overlay_items.append(("line", int(tcx_now) + sox, int(tcy_now) + soy, arx + sox, ary + soy, self._dim_hex(main_hex, 0.4), 2))

                lead_ms = self._cfg.lead_ms
                if speed > 20:
                    pred_x = int(px + self._target_vx * lead_ms / 1000.0)
                    pred_y = int(py + self._target_vy * lead_ms / 1000.0)
                    p_ax = self._aim._tracker.kx.acceleration
                    p_ay = self._aim._tracker.ky.acceleration
                    pred_conf = max(0.1, 1.0 - math.hypot(p_ax, p_ay) / 600.0)
                    conf_radius = int(8 + (1.0 - pred_conf) * 16)
                    ghost_c = self._hex_bgr(self._dim_hex(skel_hex, 0.10 + pred_conf * 0.15))
                    cv2.circle(ann, (pred_x, pred_y), conf_radius, ghost_c, 1, cv2.LINE_AA)
                    cv2.circle(ann, (pred_x, pred_y), 4, ghost_c, -1, cv2.LINE_AA)
                    cv2.drawMarker(ann, (pred_x, pred_y), ghost_c, cv2.MARKER_CROSS, 6, 1, cv2.LINE_AA)
                    overlay_items.append(("circle", pred_x + sox, pred_y + soy, conf_radius, self._dim_hex(skel_hex, 0.10 + pred_conf * 0.15)))
                    overlay_items.append(("dot", pred_x + sox, pred_y + soy, 4, self._dim_hex(skel_hex, 0.10 + pred_conf * 0.15)))

                active = self._enabled and self._aiming and (self._focused or self._cfg.always_active)
                if active and target_point is not None:
                    aim_c = self._hex_bgr(self._dim_hex(main_hex, 0.4))
                    cv2.line(ann, (scx, scy), (int(px), int(py)), aim_c, 1, cv2.LINE_AA)
                    overlay_items.append(("line", scx + sox, scy + soy, int(px) + sox, int(py) + soy, self._dim_hex(main_hex, 0.25), 1))

                hud_x = int(display_box[2]) + 6
                hud_y = int(display_box[1])
                box_h = display_box[3] - display_box[1]
                dist_to_tgt = math.hypot(px - scx, py - scy)
                self._hit_probability = self._calc_hit_prob(dist_to_tgt, avg_kp_conf, speed, box_h)

                if smooth_kps is not None:
                    bar_h = 40
                    bar_w = 4
                    cv2.rectangle(ann, (hud_x, hud_y), (hud_x + bar_w, hud_y + bar_h), (40, 40, 40), -1)
                    bar_len = int(min(bar_h, avg_kp_conf * bar_h * 1.25))
                    bar_color = (0, 255, 100) if avg_kp_conf > 0.5 else (0, 180, 255)
                    cv2.rectangle(ann, (hud_x, hud_y + bar_h - bar_len), (hud_x + bar_w, hud_y + bar_h), bar_color, -1)

                    reid_x = hud_x + bar_w + 2
                    cv2.rectangle(ann, (reid_x, hud_y), (reid_x + bar_w, hud_y + bar_h), (40, 40, 40), -1)
                    reid_len = int(min(bar_h, self._last_reid_score * bar_h))
                    reid_color = (255, 200, 0) if self._last_reid_score > 0.6 else (100, 100, 200)
                    cv2.rectangle(ann, (reid_x, hud_y + bar_h - reid_len), (reid_x + bar_w, hud_y + bar_h), reid_color, -1)

                    hit_x = reid_x + bar_w + 2
                    cv2.rectangle(ann, (hit_x, hud_y), (hit_x + bar_w, hud_y + bar_h), (40, 40, 40), -1)
                    hit_len = int(min(bar_h, self._hit_probability * bar_h))
                    hit_color = (100, 255, 100) if self._hit_probability > 0.7 else (0, 200, 255) if self._hit_probability > 0.4 else (50, 50, 200)
                    cv2.rectangle(ann, (hit_x, hud_y + bar_h - hit_len), (hit_x + bar_w, hud_y + bar_h), hit_color, -1)

                    trk_x = hit_x + bar_w + 2
                    cv2.rectangle(ann, (trk_x, hud_y), (trk_x + bar_w, hud_y + bar_h), (40, 40, 40), -1)
                    trk_len = int(min(bar_h, self._tracking_score * bar_h))
                    trk_color = (200, 200, 50) if self._tracking_score > 0.6 else (100, 100, 150)
                    cv2.rectangle(ann, (trk_x, hud_y + bar_h - trk_len), (trk_x + bar_w, hud_y + bar_h), trk_color, -1)

                if self._occlusion_warning:
                    occ_y = int(display_box[1]) - 26
                    cv2.putText(ann, "! OCCLUDE", (int(display_box[0]), occ_y),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.28, (0, 80, 255), 1, cv2.LINE_AA)
                    overlay_items.append(("text", int(display_box[0]) + sox, occ_y + soy, "! OCCLUDE", "#ff5000", 8))

                lock_dur = time.perf_counter() - self._lock_time
                state_label = self._target_state
                hud_text = f"{state_label} {self._movement_class} {dist_to_tgt:.0f}px"
                hud_text2 = f"HIT:{self._hit_probability:.0%} TRK:{self._tracking_score:.0%} T:{lock_dur:.1f}s"
                cv2.putText(ann, hud_text, (int(display_box[0]), int(display_box[1]) - 14),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.32, main_color, 1, cv2.LINE_AA)
                cv2.putText(ann, hud_text2, (int(display_box[0]), int(display_box[1]) - 4),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.28, self._hex_bgr(self._dim_hex(main_hex, 0.7)), 1, cv2.LINE_AA)
                overlay_items.append(("text", int(display_box[0]) + sox, int(display_box[1]) - 14 + soy, hud_text, main_hex, 9))
                overlay_items.append(("text", int(display_box[0]) + sox, int(display_box[1]) - 4 + soy, hud_text2, self._dim_hex(main_hex, 0.7), 8))

                box_h_ratio = box_h / h
                size_sens = 1.0 - 0.3 * min(1.0, max(0.0, (box_h_ratio - 0.15) / 0.35))
                speed_sens = 1.0 - 0.15 * min(1.0, speed / 300.0)
                trk_bonus = 0.05 * min(1.0, self._tracking_score)
                auto_sens = clamp(size_sens * speed_sens + trk_bonus, 0.55, 1.0)

                dt = tick_s
                active = self._enabled and self._aiming and (self._focused or self._cfg.always_active)
                if active and target_point is not None:
                    if snap_phase:
                        saved_omega = self._cfg.omega
                        saved_zeta = self._cfg.zeta
                        saved_human = self._cfg.human
                        if self._head_snap_active:
                            target_omega = self._cfg.head_snap_omega
                            target_zeta = self._cfg.head_snap_zeta
                        else:
                            target_omega = self._cfg.snap_omega
                            target_zeta = self._cfg.snap_zeta
                        self._cfg.omega = saved_omega + (target_omega - saved_omega) * snap_blend
                        self._cfg.zeta = saved_zeta + (target_zeta - saved_zeta) * snap_blend
                        self._cfg.human = True
                        self._humanizer.skip_reaction()

                    dx, dy, dist = self._aim.step(target_point, w, h, dt, self._ads_mult * auto_sens)

                    if snap_phase:
                        self._cfg.omega = saved_omega
                        self._cfg.zeta = saved_zeta
                        self._cfg.human = saved_human
                    if abs(dx) > 0.3 or abs(dy) > 0.3:
                        self._mouse.move_precise(dx, dy)

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
                self._target_state = "SEARCH"
                self._prev_kps_history.clear()
                self._target_vx = 0.0
                self._target_vy = 0.0
                self._last_reid_score = 0.0
                self._aim_trail.clear()
                self._hit_probability = 0.0
                self._movement_class = "STILL"
                self._occlusion_warning = False
                self._confidence_trend.clear()
                self._tracking_score = 0.0

            elapsed = time.perf_counter() - t0
            self._tick_times.append(elapsed)
            if len(self._tick_times) > 60:
                self._tick_times.pop(0)
            avg_tick = sum(self._tick_times) / len(self._tick_times) if self._tick_times else tick_s
            fps = int(1.0 / max(avg_tick, 0.001))

            if det_is_new:
                self._det_intervals.append(time.perf_counter() - self._last_det_tick)
                self._last_det_tick = time.perf_counter()
                if len(self._det_intervals) > 30:
                    self._det_intervals.pop(0)
            det_fps = 0
            if self._det_intervals:
                avg_det = sum(self._det_intervals) / len(self._det_intervals)
                det_fps = int(1.0 / max(avg_det, 0.001))

            fps_text = f"FPS:{fps} DET:{det_fps}"
            cv2.putText(ann, fps_text, (8, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (180, 180, 180), 1, cv2.LINE_AA)
            overlay_items.append(("text", 8 + sox, 16 + soy, fps_text, "#b0b0b0", 9))

            state_text = f"[{self._target_state}]"
            st_color = {"SEARCH": (100, 100, 100), "LOCK": (0, 200, 255), "TRACK": (0, 255, 100), "SNAP": (100, 100, 255)}
            cv2.putText(ann, state_text, (8, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.4, st_color.get(self._target_state, (180, 180, 180)), 1, cv2.LINE_AA)
            st_hex = {"SEARCH": "#646464", "LOCK": "#ffc800", "TRACK": "#64ff00", "SNAP": "#6464ff"}
            overlay_items.append(("text", 8 + sox, 32 + soy, state_text, st_hex.get(self._target_state, "#b0b0b0"), 9))

            self._overlay_items = overlay_items
            with self._frame_lock:
                self._annotated_frame = ann
                if picked is None:
                    self._target_crop = None

            sleep_time = tick_s - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    def _classify_movement(self) -> str:
        speed = math.hypot(self._target_vx, self._target_vy)
        vy = abs(self._target_vy)
        ax, ay = self._aim._tracker.kx.acceleration, self._aim._tracker.ky.acceleration
        accel_mag = math.hypot(ax, ay)
        if self._target_vy < -100 and (vy > 200 or ay < -400):
            return "JUMP"
        if speed < 8 and accel_mag < 50:
            return "STILL"
        if speed < 80:
            return "WALK"
        if speed < 250:
            if accel_mag > 300:
                return "FAST"
            return "RUN"
        return "FAST"

    def _calc_hit_prob(self, dist_px: float, avg_conf: float, speed: float, box_h: float) -> float:
        dist_score = max(0.0, 1.0 - dist_px / max(1.0, self._cfg.fov_px))
        conf_score = min(1.0, avg_conf / 0.7)
        speed_penalty = max(0.0, 1.0 - speed / 400.0)
        size_score = min(1.0, box_h / 120.0)
        reid_bonus = self._last_reid_score * 0.1
        raw = dist_score * 0.30 + conf_score * 0.25 + speed_penalty * 0.20 + size_score * 0.15 + reid_bonus + 0.10
        return max(0.0, min(1.0, raw))

    def _draw_radar(
        self, ann: np.ndarray, overlay_items: list,
        all_dets: List[Detection], fov_dets: List[Detection],
        cx: int, cy: int, fov_r: int, w: int, h: int,
        sox: int, soy: int, main_hex: str,
    ) -> None:
        radar_r = 45
        radar_cx = w - radar_r - 10
        radar_cy = radar_r + 10
        cv2.circle(ann, (radar_cx, radar_cy), radar_r, (40, 40, 40), -1, cv2.LINE_AA)
        cv2.circle(ann, (radar_cx, radar_cy), radar_r, (80, 80, 80), 1, cv2.LINE_AA)
        cv2.circle(ann, (radar_cx, radar_cy), radar_r // 2, (60, 60, 60), 1, cv2.LINE_AA)
        cv2.line(ann, (radar_cx - radar_r, radar_cy), (radar_cx + radar_r, radar_cy), (60, 60, 60), 1)
        cv2.line(ann, (radar_cx, radar_cy - radar_r), (radar_cx, radar_cy + radar_r), (60, 60, 60), 1)

        scale = radar_r / max(w / 2.0, 1.0)
        for x1, y1, x2, y2, conf in all_dets:
            dx = ((x1 + x2) / 2.0 - cx) * scale
            dy = ((y1 + y2) / 2.0 - cy) * scale
            rpx = int(radar_cx + dx)
            rpy = int(radar_cy + dy)
            if math.hypot(rpx - radar_cx, rpy - radar_cy) <= radar_r - 2:
                in_fov = any(
                    abs((f[0] + f[2]) / 2 - (x1 + x2) / 2) < 3 and abs((f[1] + f[3]) / 2 - (y1 + y2) / 2) < 3
                    for f in fov_dets
                )
                dot_c = (0, 255, 100) if in_fov else (0, 100, 200)
                dot_r = 4 if in_fov else 3
                cv2.circle(ann, (rpx, rpy), dot_r, dot_c, -1, cv2.LINE_AA)

        cv2.circle(ann, (radar_cx, radar_cy), 2, (255, 255, 255), -1)
        fov_radar = int(fov_r * scale)
        if fov_radar > 2:
            cv2.circle(ann, (radar_cx, radar_cy), fov_radar, (100, 100, 200), 1, cv2.LINE_AA)

        overlay_items.append(("dot", radar_cx + sox, radar_cy + soy, radar_r, "#1a1a1a"))
        overlay_items.append(("circle", radar_cx + sox, radar_cy + soy, radar_r, "#505050"))

    def _draw_aim_trail(self, ann: np.ndarray, overlay_items: list, sox: int, soy: int, main_hex: str) -> None:
        n = len(self._aim_trail)
        if n < 2:
            return
        for i in range(n - 1):
            alpha = (i + 1) / n
            c = int(60 + alpha * 140)
            trail_color = (c // 3, c // 2, c)
            th = max(1, int(alpha * 2))
            cv2.line(ann, self._aim_trail[i], self._aim_trail[i + 1], trail_color, th, cv2.LINE_AA)
        if n >= 2:
            dim = self._dim_hex(main_hex, 0.15)
            for i in range(n - 1):
                x1, y1 = self._aim_trail[i]
                x2, y2 = self._aim_trail[i + 1]
                overlay_items.append(("line", x1 + sox, y1 + soy, x2 + sox, y2 + soy, dim, 1))

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
    def _threat_hex(base_hex: str, threat: float) -> str:
        """Blend base color toward red based on threat factor (0-1)."""
        h = base_hex.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        t = min(1.0, threat)
        tr, tg, tb = 255, 60, 40
        r = int(r * (1 - t) + tr * t)
        g = int(g * (1 - t) + tg * t)
        b = int(b * (1 - t) + tb * t)
        return f"#{r:02x}{g:02x}{b:02x}"

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
