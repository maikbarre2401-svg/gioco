"""Aim controller: IoU target tracking, Kalman prediction, humanised movement."""

from __future__ import annotations

import math
import time
from typing import List, Optional, Tuple

from core.config import Config
from core.human import Humanizer
from core.kalman import Tracker
from core.utils import clamp

Detection = Tuple[float, float, float, float, float]


def _iou(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]) -> float:
    ix1 = max(a[0], b[0])
    iy1 = max(a[1], b[1])
    ix2 = min(a[2], b[2])
    iy2 = min(a[3], b[3])
    iw = max(0.0, ix2 - ix1)
    ih = max(0.0, iy2 - iy1)
    inter = iw * ih
    aa = max(0.0, (a[2] - a[0]) * (a[3] - a[1]))
    ab = max(0.0, (b[2] - b[0]) * (b[3] - b[1]))
    union = aa + ab - inter
    if union < 1e-6:
        return 0.0
    return inter / union


class Aim:
    """Picks targets from detections and computes per-tick aim deltas."""

    def __init__(self, cfg: Config, human: Humanizer) -> None:
        self._cfg = cfg
        self._human = human
        self._tracker = Tracker()
        self._target_box: Optional[Tuple[float, float, float, float]] = None
        self._last_switch: float = 0.0
        self._engaged: bool = False

    @property
    def target_box(self) -> Optional[Tuple[float, float, float, float]]:
        return self._target_box

    @property
    def engaged(self) -> bool:
        return self._engaged

    def pick(
        self, dets: List[Detection], w: int, h: int
    ) -> Optional[Tuple[float, float, float, float]]:
        """Pick best target using IoU continuity + distance + confidence scoring."""
        cx, cy = w / 2.0, h / 2.0
        fov = self._cfg.fov_px

        candidates = []
        for x1, y1, x2, y2, conf in dets:
            mx = (x1 + x2) / 2.0
            my = (y1 + y2) / 2.0
            dist = math.hypot(mx - cx, my - cy)
            if dist <= fov:
                candidates.append((x1, y1, x2, y2, conf, dist))

        if not candidates:
            self._target_box = None
            self._engaged = False
            return None

        now = time.monotonic()
        cooldown_ok = (now - self._last_switch) * 1000.0 >= self._cfg.switch_cooldown_ms

        if self._target_box is not None and cooldown_ok:
            best_iou_cand = None
            best_iou_val = 0.0
            for c in candidates:
                iou = _iou((c[0], c[1], c[2], c[3]), self._target_box)
                if iou > best_iou_val:
                    best_iou_val = iou
                    best_iou_cand = c

            if best_iou_cand is not None and best_iou_val > 0.25:
                c = best_iou_cand
                self._target_box = (c[0], c[1], c[2], c[3])
                return self._target_box

        best = min(candidates, key=lambda c: c[5])
        new_box = (best[0], best[1], best[2], best[3])

        if self._target_box is not None:
            iou_with_prev = _iou(new_box, self._target_box)
            if iou_with_prev < 0.1:
                self._last_switch = now

        self._target_box = new_box
        return self._target_box

    def begin(self) -> None:
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
        self._target_box = None
        self._engaged = False
