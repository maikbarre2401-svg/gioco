"""Advanced Re-ID: multi-space appearance features with adaptive weighting."""

from __future__ import annotations

from typing import List, Optional, Tuple

import cv2
import numpy as np


class AppearanceTracker:
    """Track target identity using multi-histogram features + shape analysis."""

    def __init__(self, history_size: int = 20) -> None:
        self._history: List[np.ndarray] = []
        self._max_history = history_size
        self._avg_feature: Optional[np.ndarray] = None
        self._aspect_ratio: float = 1.0
        self._avg_color: Optional[np.ndarray] = None
        self._stable_count: int = 0
        self._buf_resized = np.empty((128, 64, 3), dtype=np.uint8)
        self._buf_hsv = np.empty((128, 64, 3), dtype=np.uint8)
        self._buf_lab = np.empty((128, 64, 3), dtype=np.uint8)
        self._buf_score_resized = np.empty((32, 32, 3), dtype=np.uint8)

    def reset(self) -> None:
        self._history.clear()
        self._avg_feature = None
        self._aspect_ratio = 1.0
        self._avg_color = None
        self._stable_count = 0

    @property
    def ready(self) -> bool:
        return self._avg_feature is not None and len(self._history) >= 3

    def update(self, frame: np.ndarray, box: Tuple[float, float, float, float]) -> None:
        """Extract and store appearance feature from target crop."""
        crop = self._safe_crop(frame, box)
        if crop is None:
            return

        feat = self._extract(crop)
        self._history.append(feat)
        if len(self._history) > self._max_history:
            self._history.pop(0)

        weights = np.array([0.7 + 0.3 * i / len(self._history) for i in range(len(self._history))])
        weights /= weights.sum()
        self._avg_feature = np.average(self._history, axis=0, weights=weights)

        bw = box[2] - box[0]
        bh = box[3] - box[1]
        new_ar = bw / max(1.0, bh)
        self._aspect_ratio = self._aspect_ratio * 0.8 + new_ar * 0.2

        cv2.resize(crop, (32, 32), interpolation=cv2.INTER_AREA, dst=self._buf_score_resized)
        avg_c = self._buf_score_resized.mean(axis=(0, 1))
        if self._avg_color is None:
            self._avg_color = avg_c
        else:
            self._avg_color = self._avg_color * 0.85 + avg_c * 0.15

        self._stable_count = min(self._stable_count + 1, 50)

    def score(self, frame: np.ndarray, box: Tuple[float, float, float, float]) -> float:
        """Score how likely this box contains the tracked target (0.0 - 1.0)."""
        if self._avg_feature is None:
            return 0.5

        crop = self._safe_crop(frame, box)
        if crop is None:
            return 0.0

        feat = self._extract(crop)

        hist_sim = float(cv2.compareHist(
            self._avg_feature.astype(np.float32),
            feat.astype(np.float32),
            cv2.HISTCMP_CORREL,
        ))
        hist_sim = max(0.0, (hist_sim + 1.0) / 2.0)

        bw = box[2] - box[0]
        bh = box[3] - box[1]
        ar = bw / max(1.0, bh)
        ar_diff = abs(ar - self._aspect_ratio) / max(0.1, self._aspect_ratio)
        ar_sim = max(0.0, 1.0 - ar_diff)

        color_sim = 0.5
        if self._avg_color is not None:
            cv2.resize(crop, (32, 32), interpolation=cv2.INTER_AREA, dst=self._buf_score_resized)
            avg_c = self._buf_score_resized.mean(axis=(0, 1))
            diff = np.linalg.norm(avg_c - self._avg_color)
            color_sim = max(0.0, 1.0 - diff / 120.0)

        stability = min(1.0, self._stable_count / 15.0)
        w_hist = 0.55 + stability * 0.15
        w_color = 0.15 + stability * 0.05
        w_ar = 0.10
        w_remain = 1.0 - w_hist - w_color - w_ar

        return hist_sim * w_hist + color_sim * w_color + ar_sim * w_ar + 0.5 * w_remain

    def _safe_crop(self, frame: np.ndarray, box: Tuple[float, float, float, float]) -> Optional[np.ndarray]:
        fh, fw = frame.shape[:2]
        cx1 = max(0, int(box[0]))
        cy1 = max(0, int(box[1]))
        cx2 = min(fw, int(box[2]))
        cy2 = min(fh, int(box[3]))
        if cx2 <= cx1 + 4 or cy2 <= cy1 + 4:
            return None
        crop = frame[cy1:cy2, cx1:cx2]
        if crop.size == 0:
            return None
        return crop

    def _extract(self, crop: np.ndarray) -> np.ndarray:
        """Extract multi-region HSV+LAB histogram feature vector."""
        cv2.resize(crop, (64, 128), interpolation=cv2.INTER_AREA, dst=self._buf_resized)
        cv2.cvtColor(self._buf_resized, cv2.COLOR_BGR2HSV, dst=self._buf_hsv)
        cv2.cvtColor(self._buf_resized, cv2.COLOR_BGR2LAB, dst=self._buf_lab)
        resized = self._buf_resized
        hsv = self._buf_hsv
        lab = self._buf_lab

        h_third = hsv.shape[0] // 3
        regions = [
            hsv[:h_third],
            hsv[h_third:2 * h_third],
            hsv[2 * h_third:],
        ]

        parts = []
        for region in regions:
            h_hist = cv2.calcHist([region], [0, 1], None, [12, 12], [0, 180, 0, 256])
            cv2.normalize(h_hist, h_hist)
            parts.append(h_hist.flatten())

        l_third = lab.shape[0] // 3
        lab_regions = [
            lab[:l_third],
            lab[l_third:2 * l_third],
            lab[2 * l_third:],
        ]
        for region in lab_regions:
            l_hist = cv2.calcHist([region], [1, 2], None, [8, 8], [0, 256, 0, 256])
            cv2.normalize(l_hist, l_hist)
            parts.append(l_hist.flatten())

        return np.concatenate(parts)
