"""Aim controller: target picking, Kalman tracking, humanised movement."""

from __future__ import annotations

import math
import time
from typing import List, Optional, Tuple

from core.config import Config
from core.human import Humanizer
from core.kalman import Tracker
from core.utils import clamp

Detection = Tuple[float, float, float, float, float]


class Aim:
    """Picks targets from detections and computes per-tick aim deltas."""

    def __init__(self, cfg: Config, human: Humanizer) -> None:
        self._cfg = cfg
        self._human = human
        self._tracker = Tracker()
        self._target_id: Optional[int] = None
        self._target_box: Optional[Tuple[float, float, float, float]] = None
        self._last_switch: float = 0.0
        self._engaged: bool = False

    @property
    def target_box(self) -> Optional[Tuple[float, float, float, float]]:
        """The bounding box of the currently locked target."""
        return self._target_box

    @property
    def engaged(self) -> bool:
        """Whether a target is currently engaged."""
        return self._engaged

    def pick(
        self, dets: List[Detection], w: int, h: int
    ) -> Optional[Tuple[float, float, float, float]]:
        """Pick the best target from detections within fov_px, with hysteresis."""
        cx, cy = w / 2.0, h / 2.0
        fov = self._cfg.fov_px

        candidates = []
        for i, (x1, y1, x2, y2, conf) in enumerate(dets):
            mx = (x1 + x2) / 2.0
            my = (y1 + y2) / 2.0
            dist = math.hypot(mx - cx, my - cy)
            if dist <= fov:
                candidates.append((i, x1, y1, x2, y2, dist))

        if not candidates:
            self._target_id = None
            self._target_box = None
            self._engaged = False
            return None

        candidates.sort(key=lambda c: c[5])
        best_idx, bx1, by1, bx2, by2, best_dist = candidates[0]

        now = time.monotonic()
        cooldown_ok = (now - self._last_switch) * 1000.0 >= self._cfg.switch_cooldown_ms

        if self._target_id is not None and cooldown_ok:
            current_cands = [c for c in candidates if c[0] == self._target_id]
            if current_cands:
                _, _, _, _, _, cur_dist = current_cands[0]
                margin = best_dist < cur_dist * (1.0 - self._cfg.switch_margin)
                if not margin:
                    cc = current_cands[0]
                    self._target_box = (cc[1], cc[2], cc[3], cc[4])
                    return self._target_box

        if self._target_id != best_idx:
            self._last_switch = now

        self._target_id = best_idx
        self._target_box = (bx1, by1, bx2, by2)
        return self._target_box

    def begin(self) -> None:
        """Start a new engagement: seed humanizer and reset tracker."""
        if self._target_box is not None:
            cx = (self._target_box[0] + self._target_box[2]) / 2.0
            cy = (self._target_box[1] + self._target_box[3]) / 2.0
            self._tracker.reset(cx, cy)
            dist = math.hypot(cx - 320, cy - 320)
            self._human.start_engagement(dist)
        self._engaged = True

    def step(
        self,
        point: Tuple[float, float],
        w: int,
        h: int,
        dt: float,
        ads: float,
    ) -> Tuple[float, float, float]:
        """Compute aim step toward point. Returns (dx, dy, distance_px)."""
        cx, cy = w / 2.0, h / 2.0
        px, py = point

        self._tracker.feed(px, py, dt)

        lead_s = self._cfg.lead_ms / 1000.0
        pred_x, pred_y = self._tracker.predict(lead_s)

        miss_dx, miss_dy = self._human.miss_offset()
        deg_per_px = self._cfg.hfov_deg / 1920.0
        err_x_px = pred_x - cx + miss_dx / deg_per_px
        err_y_px = pred_y - cy + miss_dy / deg_per_px

        distance = math.hypot(err_x_px, err_y_px)

        if distance < self._cfg.deadzone:
            return (0.0, 0.0, distance)

        err_x_deg = err_x_px * deg_per_px
        err_y_deg = err_y_px * deg_per_px

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
        """Release the current target."""
        self._target_id = None
        self._target_box = None
        self._engaged = False
