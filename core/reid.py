"""Lightweight Re-ID: HSV appearance features for target identity across frames."""

from __future__ import annotations

from typing import List, Optional, Tuple

import cv2
import numpy as np


class AppearanceTracker:
    """Track target identity using split HSV histogram + aspect ratio."""

    def __init__(self, history_size: int = 15) -> None:
        self._history: List[np.ndarray] = []
        self._max_history = history_size
        self._avg_feature: Optional[np.ndarray] = None
        self._aspect_ratio: float = 1.0

    def reset(self) -> None:
        self._history.clear()
        self._avg_feature = None
        self._aspect_ratio = 1.0

    @property
    def ready(self) -> bool:
        return self._avg_feature is not None

    def update(self, frame: np.ndarray, box: Tuple[float, float, float, float]) -> None:
        """Extract and store appearance feature from target crop."""
        crop = self._safe_crop(frame, box)
        if crop is None:
            return

        feat = self._extract(crop)
        self._history.append(feat)
        if len(self._history) > self._max_history:
            self._history.pop(0)

        self._avg_feature = np.mean(self._history, axis=0)
        bw = box[2] - box[0]
        bh = box[3] - box[1]
        self._aspect_ratio = bw / max(1.0, bh)

    def score(self, frame: np.ndarray, box: Tuple[float, float, float, float]) -> float:
        """Score how likely this box contains the tracked target (0.0 – 1.0)."""
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

        return hist_sim * 0.85 + ar_sim * 0.15

    def _safe_crop(self, frame: np.ndarray, box: Tuple[float, float, float, float]) -> Optional[np.ndarray]:
        fh, fw = frame.shape[:2]
        cx1 = max(0, int(box[0]))
        cy1 = max(0, int(box[1]))
        cx2 = min(fw, int(box[2]))
        cy2 = min(fh, int(box[3]))
        if cx2 <= cx1 or cy2 <= cy1:
            return None
        crop = frame[cy1:cy2, cx1:cx2]
        if crop.size == 0:
            return None
        return crop

    def _extract(self, crop: np.ndarray) -> np.ndarray:
        """Extract split HSV histogram (upper + lower body) as feature vector."""
        resized = cv2.resize(crop, (64, 128), interpolation=cv2.INTER_AREA)
        hsv = cv2.cvtColor(resized, cv2.COLOR_BGR2HSV)

        mid = hsv.shape[0] // 2
        upper = hsv[:mid]
        lower = hsv[mid:]

        hu = cv2.calcHist([upper], [0, 1], None, [16, 16], [0, 180, 0, 256])
        hl = cv2.calcHist([lower], [0, 1], None, [16, 16], [0, 180, 0, 256])
        cv2.normalize(hu, hu)
        cv2.normalize(hl, hl)

        return np.concatenate([hu.flatten(), hl.flatten()])
