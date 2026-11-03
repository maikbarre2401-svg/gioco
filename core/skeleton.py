"""COCO-17 skeleton utilities: bone definitions, named points, drawing."""

from __future__ import annotations

from typing import List, Optional, Tuple

import cv2
import numpy as np

BONES: List[Tuple[int, int]] = [
    (5, 7), (7, 9), (6, 8), (8, 10),
    (5, 6), (5, 11), (6, 12), (11, 12),
    (11, 13), (13, 15), (12, 14), (14, 16),
    (0, 1), (0, 2), (1, 3), (2, 4),
    (0, 5), (0, 6),
]

_BONE_NAMES = {"head", "neck", "chest", "pelvis"}


def bone_point(
    kps: np.ndarray, name: str, box: Tuple[float, float, float, float]
) -> Optional[Tuple[float, float]]:
    """Return named skeletal point from keypoints, or None if confidence is too low."""
    if kps is None or kps.shape[0] < 17:
        return None

    def _valid(idx: int, min_conf: float = 0.3) -> bool:
        return float(kps[idx, 2]) >= min_conf

    if name == "head":
        if _valid(0):
            return (float(kps[0, 0]), float(kps[0, 1]))
        return None

    if name == "neck":
        if _valid(5) and _valid(6):
            mx = (float(kps[5, 0]) + float(kps[6, 0])) / 2.0
            my = (float(kps[5, 1]) + float(kps[6, 1])) / 2.0
            return (mx, my)
        return None

    if name == "chest":
        if _valid(5) and _valid(6):
            mx = (float(kps[5, 0]) + float(kps[6, 0])) / 2.0
            my = (float(kps[5, 1]) + float(kps[6, 1])) / 2.0
            _, y1, _, y2 = box
            bh = y2 - y1
            return (mx, my + bh * 0.12)
        return None

    if name == "pelvis":
        if _valid(11) and _valid(12):
            mx = (float(kps[11, 0]) + float(kps[12, 0])) / 2.0
            my = (float(kps[11, 1]) + float(kps[12, 1])) / 2.0
            return (mx, my)
        return None

    return None


def heuristic_point(
    name: str, box: Tuple[float, float, float, float]
) -> Tuple[float, float]:
    """Return a named point from box geometry when pose is unavailable."""
    x1, y1, x2, y2 = box
    cx = (x1 + x2) / 2.0
    bh = y2 - y1

    ratios = {"head": 0.16, "neck": 0.28, "chest": 0.40, "pelvis": 0.60}
    ratio = ratios.get(name, 0.16)
    return (cx, y1 + bh * ratio)


def draw(
    frame: np.ndarray,
    kps: np.ndarray,
    color: Tuple[int, int, int],
    th: int = 2,
    min_conf: float = 0.3,
) -> None:
    """Draw skeleton bones and joint dots on frame with antialiased lines."""
    if kps is None or kps.shape[0] < 17:
        return

    for i, j in BONES:
        if float(kps[i, 2]) < min_conf or float(kps[j, 2]) < min_conf:
            continue
        pt1 = (int(kps[i, 0]), int(kps[i, 1]))
        pt2 = (int(kps[j, 0]), int(kps[j, 1]))
        cv2.line(frame, pt1, pt2, color, th, cv2.LINE_AA)

    for k in range(17):
        if float(kps[k, 2]) < min_conf:
            continue
        pt = (int(kps[k, 0]), int(kps[k, 1]))
        cv2.circle(frame, pt, th + 1, color, -1, cv2.LINE_AA)
