"""COCO-17 skeleton: color-coded limbs, glow effect, smooth joints, head circle, motion trails."""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

BONES: List[Tuple[int, int]] = [
    (5, 7), (7, 9), (6, 8), (8, 10),
    (5, 6), (5, 11), (6, 12), (11, 12),
    (11, 13), (13, 15), (12, 14), (14, 16),
    (0, 1), (0, 2), (1, 3), (2, 4),
    (0, 5), (0, 6),
]

ZONE_HEAD = {(0, 1), (0, 2), (1, 3), (2, 4)}
ZONE_TORSO = {(5, 6), (5, 11), (6, 12), (11, 12), (0, 5), (0, 6)}
ZONE_ARM_L = {(5, 7), (7, 9)}
ZONE_ARM_R = {(6, 8), (8, 10)}
ZONE_LEG_L = {(11, 13), (13, 15)}
ZONE_LEG_R = {(12, 14), (14, 16)}

COLOR_HEAD_BGR = (255, 100, 255)
COLOR_TORSO_BGR = (255, 92, 122)
COLOR_ARM_L_BGR = (255, 180, 50)
COLOR_ARM_R_BGR = (50, 220, 255)
COLOR_LEG_L_BGR = (100, 255, 100)
COLOR_LEG_R_BGR = (80, 160, 255)

COLOR_HEAD_HEX = "#ff64ff"
COLOR_TORSO_HEX = "#7a5cff"
COLOR_ARM_L_HEX = "#32b4ff"
COLOR_ARM_R_HEX = "#ffdc32"
COLOR_LEG_L_HEX = "#64ff64"
COLOR_LEG_R_HEX = "#ffa050"

_KP_HEAD = {0, 1, 2, 3, 4}
_KP_TORSO = {5, 6, 11, 12}
_KP_ARM_L = {5, 7, 9}
_KP_ARM_R = {6, 8, 10}
_KP_LEG_L = {11, 13, 15}
_KP_LEG_R = {12, 14, 16}

_EXTREMITIES = {9, 10, 15, 16}


def _bone_zone_bgr(i: int, j: int) -> Tuple[int, int, int]:
    pair = (i, j)
    if pair in ZONE_HEAD:
        return COLOR_HEAD_BGR
    if pair in ZONE_TORSO:
        return COLOR_TORSO_BGR
    if pair in ZONE_ARM_L:
        return COLOR_ARM_L_BGR
    if pair in ZONE_ARM_R:
        return COLOR_ARM_R_BGR
    if pair in ZONE_LEG_L:
        return COLOR_LEG_L_BGR
    if pair in ZONE_LEG_R:
        return COLOR_LEG_R_BGR
    return COLOR_TORSO_BGR


def _bone_zone_hex(i: int, j: int) -> str:
    pair = (i, j)
    if pair in ZONE_HEAD:
        return COLOR_HEAD_HEX
    if pair in ZONE_TORSO:
        return COLOR_TORSO_HEX
    if pair in ZONE_ARM_L:
        return COLOR_ARM_L_HEX
    if pair in ZONE_ARM_R:
        return COLOR_ARM_R_HEX
    if pair in ZONE_LEG_L:
        return COLOR_LEG_L_HEX
    if pair in ZONE_LEG_R:
        return COLOR_LEG_R_HEX
    return COLOR_TORSO_HEX


def _kp_color_bgr(idx: int) -> Tuple[int, int, int]:
    if idx in _KP_HEAD:
        return COLOR_HEAD_BGR
    if idx in _KP_TORSO:
        return COLOR_TORSO_BGR
    if idx in _KP_ARM_L:
        return COLOR_ARM_L_BGR
    if idx in _KP_ARM_R:
        return COLOR_ARM_R_BGR
    if idx in _KP_LEG_L:
        return COLOR_LEG_L_BGR
    if idx in _KP_LEG_R:
        return COLOR_LEG_R_BGR
    return COLOR_TORSO_BGR


def _kp_color_hex(idx: int) -> str:
    if idx in _KP_HEAD:
        return COLOR_HEAD_HEX
    if idx in _KP_TORSO:
        return COLOR_TORSO_HEX
    if idx in _KP_ARM_L:
        return COLOR_ARM_L_HEX
    if idx in _KP_ARM_R:
        return COLOR_ARM_R_HEX
    if idx in _KP_LEG_L:
        return COLOR_LEG_L_HEX
    if idx in _KP_LEG_R:
        return COLOR_LEG_R_HEX
    return COLOR_TORSO_HEX


def _glow_color(bgr: Tuple[int, int, int], alpha: float) -> Tuple[int, int, int]:
    return (
        int(bgr[0] * alpha),
        int(bgr[1] * alpha),
        int(bgr[2] * alpha),
    )


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
    x1, y1, x2, y2 = box
    cx = (x1 + x2) / 2.0
    bh = y2 - y1
    ratios = {"head": 0.16, "neck": 0.28, "chest": 0.40, "pelvis": 0.60}
    ratio = ratios.get(name, 0.16)
    return (cx, y1 + bh * ratio)


def head_radius(kps: np.ndarray, box: Tuple[float, float, float, float], min_conf: float = 0.3) -> float:
    if kps is not None and kps.shape[0] >= 5:
        if float(kps[3, 2]) >= min_conf and float(kps[4, 2]) >= min_conf:
            dx = float(kps[3, 0]) - float(kps[4, 0])
            dy = float(kps[3, 1]) - float(kps[4, 1])
            return max(8.0, math.hypot(dx, dy) * 0.7)
    bw = box[2] - box[0]
    return max(8.0, bw * 0.14)


def _spine_midpoint(kps: np.ndarray, min_conf: float) -> Optional[Tuple[float, float]]:
    """Compute spine midpoint (between shoulders and hips) for torso centre."""
    s5 = float(kps[5, 2]) >= min_conf
    s6 = float(kps[6, 2]) >= min_conf
    h11 = float(kps[11, 2]) >= min_conf
    h12 = float(kps[12, 2]) >= min_conf
    if (s5 or s6) and (h11 or h12):
        sx = 0.0
        sy = 0.0
        sn = 0
        for idx in (5, 6, 11, 12):
            if float(kps[idx, 2]) >= min_conf:
                sx += float(kps[idx, 0])
                sy += float(kps[idx, 1])
                sn += 1
        return (sx / sn, sy / sn)
    return None


def draw(
    frame: np.ndarray,
    kps: np.ndarray,
    color: Tuple[int, int, int],
    th: int = 2,
    min_conf: float = 0.3,
) -> None:
    """Draw color-coded skeleton with layered glow, head circle, and confidence-scaled joints."""
    if kps is None or kps.shape[0] < 17:
        return

    overlay = frame.copy()

    for i, j in BONES:
        ci = float(kps[i, 2])
        cj = float(kps[j, 2])
        if ci < min_conf or cj < min_conf:
            continue
        pt1 = (int(kps[i, 0]), int(kps[i, 1]))
        pt2 = (int(kps[j, 0]), int(kps[j, 1]))
        zone_c = _bone_zone_bgr(i, j)
        conf_avg = (ci + cj) / 2.0
        alpha_outer = 0.25 + 0.2 * conf_avg
        cv2.line(overlay, pt1, pt2, _glow_color(zone_c, alpha_outer), th + 6, cv2.LINE_AA)
        cv2.line(overlay, pt1, pt2, _glow_color(zone_c, 0.55), th + 3, cv2.LINE_AA)
        cv2.line(overlay, pt1, pt2, zone_c, th, cv2.LINE_AA)

    for k in range(17):
        conf = float(kps[k, 2])
        if conf < min_conf:
            continue
        pt = (int(kps[k, 0]), int(kps[k, 1]))
        kc = _kp_color_bgr(k)
        r = 5 if k in _KP_HEAD else (4 if k in _EXTREMITIES else 3)
        conf_scale = 0.5 + 0.5 * min(1.0, conf)
        glow_r = int(r * 1.8)
        cv2.circle(overlay, pt, glow_r, _glow_color(kc, 0.2 * conf_scale), -1, cv2.LINE_AA)
        cv2.circle(overlay, pt, r + 1, _glow_color(kc, 0.45 * conf_scale), -1, cv2.LINE_AA)
        cv2.circle(overlay, pt, r, kc, -1, cv2.LINE_AA)
        cv2.circle(overlay, pt, max(1, r - 2), (255, 255, 255), -1, cv2.LINE_AA)

    if float(kps[0, 2]) >= min_conf:
        nose = (int(kps[0, 0]), int(kps[0, 1]))
        hr = int(head_radius(kps, (0, 0, 100, 200), min_conf))
        cv2.circle(overlay, nose, hr + 3, _glow_color(COLOR_HEAD_BGR, 0.2), 2, cv2.LINE_AA)
        cv2.circle(overlay, nose, hr, COLOR_HEAD_BGR, 2, cv2.LINE_AA)

    spine = _spine_midpoint(kps, min_conf)
    if spine is not None:
        sp = (int(spine[0]), int(spine[1]))
        cv2.circle(overlay, sp, 3, COLOR_TORSO_BGR, -1, cv2.LINE_AA)

    cv2.addWeighted(overlay, 0.85, frame, 0.15, 0, frame)


def draw_overlay_items(
    kps: np.ndarray, min_conf: float, box: Tuple[float, float, float, float]
) -> list:
    """Build overlay draw items with per-zone colors, layered glow lines, and head circle."""
    items: list = []
    if kps is None or kps.shape[0] < 17:
        return items

    for i, j in BONES:
        ci = float(kps[i, 2])
        cj = float(kps[j, 2])
        if ci < min_conf or cj < min_conf:
            continue
        zone_hex = _bone_zone_hex(i, j)
        glow_hex = _dim_hex(zone_hex, 0.3)
        mid_hex = _dim_hex(zone_hex, 0.6)
        x1, y1 = int(kps[i, 0]), int(kps[i, 1])
        x2, y2 = int(kps[j, 0]), int(kps[j, 1])
        items.append(("line", x1, y1, x2, y2, glow_hex, 7))
        items.append(("line", x1, y1, x2, y2, mid_hex, 4))
        items.append(("line", x1, y1, x2, y2, zone_hex, 2))

    for k in range(17):
        if float(kps[k, 2]) < min_conf:
            continue
        kc = _kp_color_hex(k)
        r = 6 if k in _KP_HEAD else (5 if k in _EXTREMITIES else 4)
        items.append(("dot", int(kps[k, 0]), int(kps[k, 1]), r, kc))

    if float(kps[0, 2]) >= min_conf:
        hr = int(head_radius(kps, box, min_conf))
        items.append(("circle", int(kps[0, 0]), int(kps[0, 1]), hr, COLOR_HEAD_HEX))

    return items


def _dim_hex(hex_color: str, factor: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    r = int(r * factor)
    g = int(g * factor)
    b = int(b * factor)
    return f"#{r:02x}{g:02x}{b:02x}"
