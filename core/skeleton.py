"""Advanced 3D-style skeleton: neon glow, depth ordering, joint interpolation, head halo."""

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

_KP_HEAD = {0, 1, 2, 3, 4}

_NEIGHBORS: Dict[int, List[int]] = {
    0: [1, 2, 5, 6], 1: [0, 3], 2: [0, 4], 3: [1], 4: [2],
    5: [0, 6, 7, 11], 6: [0, 5, 8, 12],
    7: [5, 9], 8: [6, 10], 9: [7], 10: [8],
    11: [5, 12, 13], 12: [6, 11, 14],
    13: [11, 15], 14: [12, 16], 15: [13], 16: [14],
}


def _hex_to_bgr(h: str) -> Tuple[int, int, int]:
    h = h.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return (b, g, r)


def _scale_bgr(bgr: Tuple[int, int, int], f: float) -> Tuple[int, int, int]:
    return (min(255, int(bgr[0] * f)), min(255, int(bgr[1] * f)), min(255, int(bgr[2] * f)))


def _brighten_bgr(bgr: Tuple[int, int, int], f: float) -> Tuple[int, int, int]:
    return (
        min(255, int(bgr[0] + (255 - bgr[0]) * f)),
        min(255, int(bgr[1] + (255 - bgr[1]) * f)),
        min(255, int(bgr[2] + (255 - bgr[2]) * f)),
    )


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


def _interpolate_kps(kps: np.ndarray, min_conf: float) -> np.ndarray:
    """Fill in missing joints by interpolating from confident neighbors."""
    out = kps.copy()
    for k in range(min(17, kps.shape[0])):
        if float(out[k, 2]) >= min_conf:
            continue
        nbrs = _NEIGHBORS.get(k, [])
        valid = []
        for n in nbrs:
            if n < out.shape[0] and float(out[n, 2]) >= min_conf:
                valid.append((float(out[n, 0]), float(out[n, 1]), float(out[n, 2])))
        if len(valid) >= 2:
            tw = sum(v[2] for v in valid)
            out[k, 0] = sum(v[0] * v[2] for v in valid) / tw
            out[k, 1] = sum(v[1] * v[2] for v in valid) / tw
            out[k, 2] = min(v[2] for v in valid) * 0.45
    return out


def _estimate_depths(kps: np.ndarray, box: Tuple[float, float, float, float], min_conf: float) -> np.ndarray:
    """Per-keypoint pseudo-depth (0=far, 1=close) from body proportions."""
    depths = np.full(min(17, kps.shape[0]), 0.5)
    bh = max(1.0, box[3] - box[1])
    bw = max(1.0, box[2] - box[0])

    for k in range(min(17, kps.shape[0])):
        if float(kps[k, 2]) < min_conf * 0.3:
            continue
        y_ratio = (float(kps[k, 1]) - box[1]) / bh
        depths[k] = 0.3 + y_ratio * 0.4

    if kps.shape[0] >= 13 and float(kps[5, 2]) >= min_conf and float(kps[6, 2]) >= min_conf:
        scx = (float(kps[5, 0]) + float(kps[6, 0])) / 2
        for arm_kps, shoulder in [([7, 9], 5), ([8, 10], 6)]:
            max_ext = 0.0
            for ak in arm_kps:
                if ak < kps.shape[0] and float(kps[ak, 2]) >= min_conf * 0.5:
                    max_ext = max(max_ext, abs(float(kps[ak, 0]) - scx))
            if max_ext > bw * 0.3:
                for ak in arm_kps:
                    if ak < kps.shape[0]:
                        depths[ak] = min(1.0, depths[ak] + 0.25)
                depths[shoulder] = min(1.0, depths[shoulder] + 0.12)

    if kps.shape[0] >= 17:
        for leg_kps, hip in [([13, 15], 11), ([14, 16], 12)]:
            for lk in leg_kps:
                if lk < kps.shape[0] and float(kps[lk, 2]) >= min_conf * 0.5:
                    y_rel = (float(kps[lk, 1]) - box[1]) / bh
                    if y_rel > 0.7:
                        depths[lk] = min(1.0, depths[lk] + 0.15)

    return depths


def _sort_bones_by_depth(kps: np.ndarray, depths: np.ndarray, min_conf: float) -> List[Tuple[int, int]]:
    """Sort bones back-to-front for proper 3D occlusion."""
    bone_depths = []
    n = min(17, kps.shape[0])
    for i, j in BONES:
        if i >= n or j >= n:
            continue
        if float(kps[i, 2]) < min_conf * 0.3 and float(kps[j, 2]) < min_conf * 0.3:
            continue
        avg_d = (depths[min(i, len(depths) - 1)] + depths[min(j, len(depths) - 1)]) / 2.0
        bone_depths.append(((i, j), avg_d))
    bone_depths.sort(key=lambda x: x[1])
    return [b for b, _ in bone_depths]


def bone_point(
    kps: np.ndarray, name: str, box: Tuple[float, float, float, float]
) -> Optional[Tuple[float, float]]:
    if kps is None or kps.shape[0] < 17:
        return None

    def _valid(idx: int, mc: float = 0.3) -> bool:
        return float(kps[idx, 2]) >= mc

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
    if kps is not None and kps.shape[0] >= 13:
        pts = []
        for idx in (5, 6, 11, 12):
            if float(kps[idx, 2]) >= min_conf:
                pts.append((float(kps[idx, 0]), float(kps[idx, 1])))
        if len(pts) >= 2:
            return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
    return ((box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0)


def body_radius(kps: np.ndarray, box: Tuple[float, float, float, float], min_conf: float = 0.3) -> float:
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
    """3D neon skeleton: glow blur pass, depth-ordered bones, halo joints, head rings."""
    if kps is None or kps.shape[0] < 17:
        return

    kps = _interpolate_kps(kps, min_conf)
    c = _hex_to_bgr(color_hex)
    depths = _estimate_depths(kps, box, min_conf)
    sorted_bones = _sort_bones_by_depth(kps, depths, min_conf)
    render_conf = min_conf * 0.4

    glow = np.zeros_like(frame)

    for i, j in sorted_bones:
        ci = float(kps[i, 2])
        cj = float(kps[j, 2])
        if ci < render_conf or cj < render_conf:
            continue
        pt1 = (int(kps[i, 0]), int(kps[i, 1]))
        pt2 = (int(kps[j, 0]), int(kps[j, 1]))
        di = depths[min(i, len(depths) - 1)]
        dj = depths[min(j, len(depths) - 1)]
        avg_d = (di + dj) / 2.0
        conf_f = min(1.0, (ci + cj) / 2.0 / 0.8)
        brightness = (0.5 + avg_d * 0.5) * conf_f
        glow_th = int((th + 3) * (1.0 + avg_d * 0.8))
        glow_c = _scale_bgr(c, brightness * 1.3)
        cv2.line(glow, pt1, pt2, glow_c, glow_th, cv2.LINE_AA)

    for k in range(min(17, kps.shape[0])):
        if float(kps[k, 2]) < render_conf:
            continue
        pt = (int(kps[k, 0]), int(kps[k, 1]))
        d = depths[min(k, len(depths) - 1)]
        r = 7 if k in _KP_HEAD else 6
        gc = _scale_bgr(c, 0.6 + d * 0.4)
        cv2.circle(glow, pt, r + 4, gc, -1, cv2.LINE_AA)

    if float(kps[0, 2]) >= min_conf:
        nose = (int(kps[0, 0]), int(kps[0, 1]))
        hr = int(head_radius(kps, box, min_conf))
        cv2.circle(glow, nose, hr + 8, _scale_bgr(c, 0.9), 3, cv2.LINE_AA)

    glow = cv2.GaussianBlur(glow, (0, 0), sigmaX=7, sigmaY=7)
    cv2.addWeighted(glow, 0.65, frame, 1.0, 0, frame)

    for i, j in sorted_bones:
        ci = float(kps[i, 2])
        cj = float(kps[j, 2])
        if ci < render_conf or cj < render_conf:
            continue
        pt1 = (int(kps[i, 0]), int(kps[i, 1]))
        pt2 = (int(kps[j, 0]), int(kps[j, 1]))
        di = depths[min(i, len(depths) - 1)]
        dj = depths[min(j, len(depths) - 1)]
        avg_d = (di + dj) / 2.0
        conf_f = min(1.0, (ci + cj) / 2.0 / 0.8)
        core_th = max(1, int(th * (0.8 + avg_d * 0.6)))
        brightness = (0.7 + avg_d * 0.3) * conf_f
        cv2.line(frame, pt1, pt2, _scale_bgr(c, brightness), core_th, cv2.LINE_AA)

    for k in range(min(17, kps.shape[0])):
        conf = float(kps[k, 2])
        if conf < render_conf:
            continue
        pt = (int(kps[k, 0]), int(kps[k, 1]))
        d = depths[min(k, len(depths) - 1)]
        conf_f = min(1.0, conf / 0.7)
        brightness = (0.6 + d * 0.4) * conf_f

        r = 4 if k in _KP_HEAD else 3
        r = max(2, int(r * (0.8 + d * 0.5)))

        cv2.circle(frame, pt, r + 2, _scale_bgr(c, brightness * 0.5), -1, cv2.LINE_AA)
        cv2.circle(frame, pt, r, _scale_bgr(c, brightness), -1, cv2.LINE_AA)
        if r >= 2:
            cv2.circle(frame, pt, max(1, r - 1), _brighten_bgr(c, brightness * 0.5), -1, cv2.LINE_AA)

    if float(kps[0, 2]) >= min_conf:
        nose = (int(kps[0, 0]), int(kps[0, 1]))
        hr = int(head_radius(kps, box, min_conf))
        for ri in range(4):
            radius = hr + ri * 3
            alpha = 1.0 - ri * 0.22
            ring_th = max(1, 2 - ri // 2)
            cv2.circle(frame, nose, radius, _scale_bgr(c, alpha), ring_th, cv2.LINE_AA)

    if draw_fov_circle:
        bcx, bcy = body_center(kps, box, min_conf)
        br = int(body_radius(kps, box, min_conf))
        center = (int(bcx), int(bcy))
        cv2.circle(frame, center, br + 6, _scale_bgr(c, 0.12), 2, cv2.LINE_AA)
        cv2.circle(frame, center, br + 2, _scale_bgr(c, 0.28), 1, cv2.LINE_AA)
        cv2.circle(frame, center, br, _scale_bgr(c, 0.5), 1, cv2.LINE_AA)


def draw_overlay_items(
    kps: np.ndarray,
    min_conf: float,
    box: Tuple[float, float, float, float],
    color_hex: str = "#7a5cff",
    draw_fov_circle: bool = True,
) -> list:
    """Overlay items: 3-pass glow bones, halo joints, head rings, body circle."""
    items: list = []
    if kps is None or kps.shape[0] < 17:
        return items

    kps = _interpolate_kps(kps, min_conf)
    depths = _estimate_depths(kps, box, min_conf)
    sorted_bones = _sort_bones_by_depth(kps, depths, min_conf)
    render_conf = min_conf * 0.4

    glow_hex = _dim_hex(color_hex, 0.2)
    mid_hex = _dim_hex(color_hex, 0.5)

    for i, j in sorted_bones:
        if float(kps[i, 2]) < render_conf or float(kps[j, 2]) < render_conf:
            continue
        x1, y1 = int(kps[i, 0]), int(kps[i, 1])
        x2, y2 = int(kps[j, 0]), int(kps[j, 1])
        di = depths[min(i, len(depths) - 1)]
        dj = depths[min(j, len(depths) - 1)]
        avg_d = (di + dj) / 2.0
        gw = int(7 + avg_d * 5)
        items.append(("line", x1, y1, x2, y2, glow_hex, gw))

    for i, j in sorted_bones:
        if float(kps[i, 2]) < render_conf or float(kps[j, 2]) < render_conf:
            continue
        x1, y1 = int(kps[i, 0]), int(kps[i, 1])
        x2, y2 = int(kps[j, 0]), int(kps[j, 1])
        di = depths[min(i, len(depths) - 1)]
        dj = depths[min(j, len(depths) - 1)]
        avg_d = (di + dj) / 2.0
        mw = int(4 + avg_d * 3)
        items.append(("line", x1, y1, x2, y2, mid_hex, mw))

    for i, j in sorted_bones:
        if float(kps[i, 2]) < render_conf or float(kps[j, 2]) < render_conf:
            continue
        x1, y1 = int(kps[i, 0]), int(kps[i, 1])
        x2, y2 = int(kps[j, 0]), int(kps[j, 1])
        di = depths[min(i, len(depths) - 1)]
        dj = depths[min(j, len(depths) - 1)]
        avg_d = (di + dj) / 2.0
        cw = max(1, int(2 + avg_d * 1.5))
        bright = _brighten_hex(color_hex, avg_d * 0.25)
        items.append(("line", x1, y1, x2, y2, bright, cw))

    for k in range(min(17, kps.shape[0])):
        if float(kps[k, 2]) < render_conf:
            continue
        x, y = int(kps[k, 0]), int(kps[k, 1])
        d = depths[min(k, len(depths) - 1)]
        r = 5 if k in _KP_HEAD else 4
        r = max(2, int(r * (0.8 + d * 0.5)))
        items.append(("dot", x, y, r + 4, glow_hex))
        items.append(("dot", x, y, r + 2, mid_hex))
        bright = _brighten_hex(color_hex, d * 0.25)
        items.append(("dot", x, y, r, bright))

    if float(kps[0, 2]) >= min_conf:
        hr = int(head_radius(kps, box, min_conf))
        hx, hy = int(kps[0, 0]), int(kps[0, 1])
        for ri in range(4):
            radius = hr + ri * 3
            rc = _dim_hex(color_hex, 1.0 - ri * 0.2)
            items.append(("circle", hx, hy, radius, rc))

    if draw_fov_circle:
        bcx, bcy = body_center(kps, box, min_conf)
        br = int(body_radius(kps, box, min_conf))
        items.append(("circle", int(bcx), int(bcy), br + 5, _dim_hex(color_hex, 0.12)))
        items.append(("circle", int(bcx), int(bcy), br + 2, _dim_hex(color_hex, 0.3)))
        items.append(("circle", int(bcx), int(bcy), br, _dim_hex(color_hex, 0.5)))

    return items
