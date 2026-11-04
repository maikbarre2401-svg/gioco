"""Aim controller: ReID + IoU tracking, auto bone, Kalman prediction, humanised movement, adaptive lead."""

from __future__ import annotations

import math
import time
from typing import List, Optional, Tuple

import numpy as np

from core.config import Config
from core.human import Humanizer
from core.kalman import Tracker
from core.reid import AppearanceTracker
from core.utils import clamp

Detection = Tuple[float, float, float, float, float]

_LEAD_BY_MOVEMENT = {
    "STILL": 0.3,
    "WALK": 0.7,
    "RUN": 1.0,
    "FAST": 1.4,
    "JUMP": 1.2,
}


def _iou(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]) -> float:
    ix1 = max(a[0], b[0])
    iy1 = max(a[1], b[1])
    ix2 = min(a[2], b[2])
    iy2 = min(a[3], b[3])
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    aa = max(0.0, (a[2] - a[0]) * (a[3] - a[1]))
    ab = max(0.0, (b[2] - b[0]) * (b[3] - b[1]))
    union = aa + ab - inter
    return inter / union if union > 1e-6 else 0.0


class Aim:
    """Picks targets with ReID + IoU + velocity, computes per-tick aim deltas with adaptive lead."""

    def __init__(self, cfg: Config, human: Humanizer) -> None:
        self._cfg = cfg
        self._human = human
        self._tracker = Tracker()
        self._reid = AppearanceTracker()
        self._target_box: Optional[Tuple[float, float, float, float]] = None
        self._last_switch: float = 0.0
        self._engaged: bool = False
        self._frame_ref: Optional[np.ndarray] = None
        self._movement_class: str = "STILL"
        self._target_vx: float = 0.0
        self._target_vy: float = 0.0
        self._lost_frames: int = 0
        self._last_target_cx: float = 0.0
        self._last_target_cy: float = 0.0
        self._consecutive_track: int = 0

    @property
    def target_box(self) -> Optional[Tuple[float, float, float, float]]:
        return self._target_box

    @property
    def engaged(self) -> bool:
        return self._engaged

    def set_frame(self, frame: np.ndarray) -> None:
        self._frame_ref = frame

    def set_velocity(self, vx: float, vy: float, movement: str) -> None:
        """Receive target velocity and movement class from the engine."""
        self._target_vx = vx
        self._target_vy = vy
        self._movement_class = movement

    def pick(
        self, dets: List[Detection], w: int, h: int
    ) -> Optional[Tuple[float, float, float, float]]:
        """Pick best target using IoU + ReID + distance + velocity-toward-crosshair."""
        cx = w / 2.0 + self._cfg.crosshair_offset_x
        cy = h / 2.0 + self._cfg.crosshair_offset_y
        fov = self._cfg.fov_px

        candidates = []
        for x1, y1, x2, y2, conf in dets:
            mx = (x1 + x2) / 2.0
            my = (y1 + y2) / 2.0
            dist = math.hypot(mx - cx, my - cy)
            if dist <= fov:
                candidates.append((x1, y1, x2, y2, conf, dist))

        if not candidates:
            self._lost_frames += 1
            if self._lost_frames > 8:
                self._target_box = None
                self._engaged = False
                self._consecutive_track = 0
            elif self._target_box is not None and self._lost_frames <= 8:
                tick_s = 1.0 / max(1, self._cfg.tick_hz)
                px = self._last_target_cx + self._target_vx * tick_s * self._lost_frames
                py = self._last_target_cy + self._target_vy * tick_s * self._lost_frames
                bw = self._target_box[2] - self._target_box[0]
                bh = self._target_box[3] - self._target_box[1]
                self._target_box = (px - bw / 2, py - bh / 2, px + bw / 2, py + bh / 2)
                return self._target_box
            return None

        self._lost_frames = 0
        now = time.monotonic()
        cooldown_ok = (now - self._last_switch) * 1000.0 >= self._cfg.switch_cooldown_ms

        if self._target_box is not None and cooldown_ok:
            best_score = -1.0
            best_cand = None

            for c in candidates:
                cbox = (c[0], c[1], c[2], c[3])
                iou = _iou(cbox, self._target_box)

                reid_s = 0.5
                if self._reid.ready and self._frame_ref is not None:
                    reid_s = self._reid.score(self._frame_ref, cbox)

                dist_score = 1.0 - c[5] / fov

                approach = 0.5
                if c[5] > 1.0:
                    to_cx = cx - (c[0] + c[2]) / 2.0
                    to_cy = cy - (c[1] + c[3]) / 2.0
                    speed = math.hypot(self._target_vx, self._target_vy)
                    if speed > 5.0:
                        dot = (self._target_vx * to_cx + self._target_vy * to_cy)
                        approach = 0.5 + 0.5 * clamp(dot / (speed * c[5]), -1.0, 1.0)

                score = iou * 0.35 + reid_s * 0.35 + dist_score * 0.15 + approach * 0.15

                if score > best_score:
                    best_score = score
                    best_cand = c

            if best_cand is not None and best_score > 0.30:
                c = best_cand
                self._target_box = (c[0], c[1], c[2], c[3])
                self._last_target_cx = (c[0] + c[2]) / 2.0
                self._last_target_cy = (c[1] + c[3]) / 2.0
                self._consecutive_track += 1
                return self._target_box

        best = min(candidates, key=lambda c: c[5])
        new_box = (best[0], best[1], best[2], best[3])

        if self._target_box is not None:
            iou_with_prev = _iou(new_box, self._target_box)
            if iou_with_prev < 0.1:
                self._last_switch = now
                self._reid.reset()
                self._consecutive_track = 0

        self._target_box = new_box
        self._last_target_cx = (best[0] + best[2]) / 2.0
        self._last_target_cy = (best[1] + best[3]) / 2.0
        self._consecutive_track += 1
        return self._target_box

    def update_reid(self, frame: np.ndarray) -> None:
        if self._target_box is not None:
            self._reid.update(frame, self._target_box)

    def auto_bone(self, h: int) -> str:
        """Choose aim bone based on distance and tracking confidence."""
        if not self._cfg.bone_by_distance or self._target_box is None:
            return self._cfg.bone
        box_h = self._target_box[3] - self._target_box[1]
        ratio = box_h / h
        if ratio < 0.10:
            return "chest"
        if ratio < 0.18:
            return "neck"
        if self._consecutive_track > 30 and ratio > 0.25:
            return "head"
        return self._cfg.bone

    def begin(self) -> None:
        if self._target_box is not None:
            tx = (self._target_box[0] + self._target_box[2]) / 2.0
            ty = (self._target_box[1] + self._target_box[3]) / 2.0
            self._tracker.reset(tx, ty)
            ref_cx = self._cfg.capture / 2.0 + self._cfg.crosshair_offset_x
            ref_cy = self._cfg.capture / 2.0 + self._cfg.crosshair_offset_y
            dist = math.hypot(tx - ref_cx, ty - ref_cy)
            self._human.start_engagement(dist)
        self._engaged = True
        self._lost_frames = 0

    def step(
        self,
        point: Tuple[float, float],
        w: int,
        h: int,
        dt: float,
        ads: float,
    ) -> Tuple[float, float, float]:
        cx = w / 2.0 + self._cfg.crosshair_offset_x
        cy = h / 2.0 + self._cfg.crosshair_offset_y
        px, py = point

        self._tracker.feed(px, py, dt)

        lead_mult = _LEAD_BY_MOVEMENT.get(self._movement_class, 1.0)
        lead_s = (self._cfg.lead_ms / 1000.0) * lead_mult
        pred_x, pred_y = self._tracker.predict(lead_s)

        miss_dx, miss_dy = self._human.miss_offset()
        deg_per_px = self._cfg.hfov_deg / 1920.0
        err_x_px = pred_x - cx + miss_dx / deg_per_px
        err_y_px = pred_y - cy + miss_dy / deg_per_px

        distance = math.hypot(err_x_px, err_y_px)

        err_x_deg = err_x_px * deg_per_px
        err_y_deg = err_y_px * deg_per_px

        if distance < self._cfg.deadzone:
            if self._cfg.human and distance > self._cfg.deadzone * 0.3:
                mc_x, mc_y = self._human.micro_correction(err_x_deg, err_y_deg, dt)
                counts = self._cfg.counts_per_deg * ads
                dx = mc_x * counts
                dy = mc_y * counts
                dx = clamp(dx, -5.0, 5.0)
                dy = clamp(dy, -5.0, 5.0)
                return (dx, dy, distance)
            return (0.0, 0.0, distance)

        if self._cfg.human:
            if self._human.reacting():
                return (0.0, 0.0, distance)

            step_x, step_y = self._human.spring(err_x_deg, err_y_deg, dt)
            trem_x, trem_y = self._human.tremor(dt)
            step_x += trem_x * deg_per_px
            step_y += trem_y * deg_per_px

            sticky = self._human.sticky(distance)
            step_x *= sticky
            step_y *= sticky
        else:
            step_x = err_x_deg
            step_y = err_y_deg

        counts = self._cfg.counts_per_deg * ads
        dx = step_x * counts
        dy = step_y * counts

        max_s = self._cfg.max_step
        dx = clamp(dx, -max_s, max_s)
        dy = clamp(dy, -max_s, max_s)

        return (dx, dy, distance)

    def release(self) -> None:
        self._target_box = None
        self._engaged = False
        self._reid.reset()
        self._consecutive_track = 0
        self._lost_frames = 0
