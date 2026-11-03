"""COCO-17 skeleton: clean monochrome style with FOV circle and subtle glow."""

from __future__ import annotations

import math
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

_KP_HEAD = {0, 1, 2, 3, 4}
_EXTREMITIES = {9, 10, 15, 16}


def _hex_to_bgr(hex_color: str) -> Tuple[int, int, int]:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return (b, g, r)


def _dim_bgr(bgr: Tuple[int, int, int], factor: float) -> Tuple[int, int, int]:
    return (int(bgr[0] * factor), int(bgr[1] * factor), int(bgr[2] * factor))


def _dim_hex(hex_color: str, factor: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"#{int(r * factor):02x}{int(g * factor):02x}{int(b * factor):02x}"


def _brighten_hex(hex_color: str, factor: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    r = min(255, int(r + (255 - r) * factor))
    g = min(255, int(g + (255 - g) * factor))
    b = min(255, int(b + (255 - b) * factor))
    return f"#{r:02x}{g:02x}{b:02x}"


def bone_point(
    kps: np.ndarray, name: str, box: Tuple[float, float, float, float]
) -> Optional[Tuple[float, float]]:
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
            return (
                (float(kps[5, 0]) + float(kps[6, 0])) / 2.0,
                (float(kps[5, 1]) + float(kps[6, 1])) / 2.0,
            )
        return None
    if name == "chest":
        if _valid(5) and _valid(6):
            mx = (float(kps[5, 0]) + float(kps[6, 0])) / 2.0
            my = (float(kps[5, 1]) + float(kps[6, 1])) / 2.0
            bh = box[3] - box[1]
            return (mx, my + bh * 0.12)
        return None
    if name == "pelvis":
        if _valid(11) and _valid(12):
            return (
                (float(kps[11, 0]) + float(kps[12, 0])) / 2.0,
                (float(kps[11, 1]) + float(kps[12, 1])) / 2.0,
            )
        return None
    return None


def heuristic_point(
    name: str, box: Tuple[float, float, float, float]
) -> Tuple[float, float]:
    x1, y1, x2, y2 = box
    cx = (x1 + x2) / 2.0
    bh = y2 - y1
    ratios = {"head": 0.16, "neck": 0.28, "chest": 0.40, "pelvis": 0.60}
    return (cx, y1 + bh * ratios.get(name, 0.16))


def head_radius(kps: np.ndarray, box: Tuple[float, float, float, float], min_conf: float = 0.3) -> float:
    if kps is not None and kps.shape[0] >= 5:
        if float(kps[3, 2]) >= min_conf and float(kps[4, 2]) >= min_conf:
            dx = float(kps[3, 0]) - float(kps[4, 0])
            dy = float(kps[3, 1]) - float(kps[4, 1])
            return max(8.0, math.hypot(dx, dy) * 0.7)
    return max(8.0, (box[2] - box[0]) * 0.14)


def body_center(kps: np.ndarray, box: Tuple[float, float, float, float], min_conf: float = 0.3) -> Tuple[float, float]:
    """Compute body centroid from torso keypoints, fallback to box center."""
    if kps is not None and kps.shape[0] >= 13:
        pts = []
        for idx in (5, 6, 11, 12):
            if float(kps[idx, 2]) >= min_conf:
                pts.append((float(kps[idx, 0]), float(kps[idx, 1])))
        if len(pts) >= 2:
            sx = sum(p[0] for p in pts) / len(pts)
            sy = sum(p[1] for p in pts) / len(pts)
            return (sx, sy)
    return ((box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0)


def body_radius(kps: np.ndarray, box: Tuple[float, float, float, float], min_conf: float = 0.3) -> float:
    """Compute radius of circle that encloses the body from skeleton or box."""
    cx, cy = body_center(kps, box, min_conf)
    max_r = 0.0
    if kps is not None and kps.shape[0] >= 17:
        for k in range(17):
            if float(kps[k, 2]) >= min_conf:
                dx = float(kps[k, 0]) - cx
                dy = float(kps[k, 1]) - cy
                max_r = max(max_r, math.hypot(dx, dy))
    if max_r < 20.0:
        bw = box[2] - box[0]
        bh = box[3] - box[1]
        max_r = math.hypot(bw, bh) / 2.0
    return max_r * 1.15


def draw(
    frame: np.ndarray,
    kps: np.ndarray,
    color_hex: str,
    box: Tuple[float, float, float, float],
    th: int = 2,
    min_conf: float = 0.3,
    draw_fov_circle: bool = True,
) -> None:
    """Draw monochrome skeleton with subtle glow, head circle, and FOV body circle."""
    if kps is None or kps.shape[0] < 17:
        return

    c = _hex_to_bgr(color_hex)
    c_glow = _dim_bgr(c, 0.35)
    overlay = frame.copy()

    for i, j in BONES:
        if float(kps[i, 2]) < min_conf or float(kps[j, 2]) < min_conf:
            continue
        pt1 = (int(kps[i, 0]), int(kps[i, 1]))
        pt2 = (int(kps[j, 0]), int(kps[j, 1]))
        cv2.line(overlay, pt1, pt2, c_glow, th + 4, cv2.LINE_AA)
        cv2.line(overlay, pt1, pt2, c, th, cv2.LINE_AA)

    for k in range(17):
        conf = float(kps[k, 2])
        if conf < min_conf:
            continue
        pt = (int(kps[k, 0]), int(kps[k, 1]))
        r = 4 if k in _KP_HEAD else 3
        cv2.circle(overlay, pt, r + 1, c_glow, -1, cv2.LINE_AA)
        cv2.circle(overlay, pt, r, c, -1, cv2.LINE_AA)

    if float(kps[0, 2]) >= min_conf:
        nose = (int(kps[0, 0]), int(kps[0, 1]))
        hr = int(head_radius(kps, box, min_conf))
        cv2.circle(overlay, nose, hr, c, 2, cv2.LINE_AA)

    if draw_fov_circle:
        bcx, bcy = body_center(kps, box, min_conf)
        br = int(body_radius(kps, box, min_conf))
        center = (int(bcx), int(bcy))
        cv2.circle(overlay, center, br + 4, _dim_bgr(c, 0.15), 2, cv2.LINE_AA)
        cv2.circle(overlay, center, br, _dim_bgr(c, 0.5), 1, cv2.LINE_AA)

    cv2.addWeighted(overlay, 0.88, frame, 0.12, 0, frame)


def draw_overlay_items(
    kps: np.ndarray,
    min_conf: float,
    box: Tuple[float, float, float, float],
    color_hex: str = "#7a5cff",
    draw_fov_circle: bool = True,
) -> list:
    """Build overlay draw items: monochrome skeleton, head circle, FOV body circle."""
    items: list = []
    if kps is None or kps.shape[0] < 17:
        return items

    glow_hex = _dim_hex(color_hex, 0.35)

    for i, j in BONES:
        if float(kps[i, 2]) < min_conf or float(kps[j, 2]) < min_conf:
            continue
        x1, y1 = int(kps[i, 0]), int(kps[i, 1])
        x2, y2 = int(kps[j, 0]), int(kps[j, 1])
        items.append(("line", x1, y1, x2, y2, glow_hex, 5))
        items.append(("line", x1, y1, x2, y2, color_hex, 2))

    for k in range(17):
        if float(kps[k, 2]) < min_conf:
            continue
        r = 4 if k in _KP_HEAD else 3
        items.append(("dot", int(kps[k, 0]), int(kps[k, 1]), r, color_hex))

    if float(kps[0, 2]) >= min_conf:
        hr = int(head_radius(kps, box, min_conf))
        items.append(("circle", int(kps[0, 0]), int(kps[0, 1]), hr, color_hex))

    if draw_fov_circle:
        bcx, bcy = body_center(kps, box, min_conf)
        br = int(body_radius(kps, box, min_conf))
        circle_color = _dim_hex(color_hex, 0.55)
        items.append(("circle", int(bcx), int(bcy), br, circle_color))

    return items
