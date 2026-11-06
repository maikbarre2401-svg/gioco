"""Ultra-advanced skeleton: confidence-gradient bones, motion trails, spine curve, energy field, 3D neon glow."""

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
_KP_TORSO = {5, 6, 11, 12}
_KP_ARMS = {7, 8, 9, 10}
_KP_LEGS = {13, 14, 15, 16}

_NEIGHBORS: Dict[int, List[int]] = {
    0: [1, 2, 5, 6], 1: [0, 3], 2: [0, 4], 3: [1], 4: [2],
    5: [0, 6, 7, 11], 6: [0, 5, 8, 12],
    7: [5, 9], 8: [6, 10], 9: [7], 10: [8],
    11: [5, 12, 13], 12: [6, 11, 14],
    13: [11, 15], 14: [12, 16], 15: [13], 16: [14],
}

_SPINE_CHAIN = [0, (5, 6), (5, 6, 11, 12), (11, 12)]


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


def _blend_bgr(a: Tuple[int, int, int], b: Tuple[int, int, int], t: float) -> Tuple[int, int, int]:
    return (
        int(a[0] * (1 - t) + b[0] * t),
        int(a[1] * (1 - t) + b[1] * t),
        int(a[2] * (1 - t) + b[2] * t),
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


def _blend_hex(hex_a: str, hex_b: str, t: float) -> str:
    a = hex_a.lstrip("#")
    b = hex_b.lstrip("#")
    ra, ga, ba = int(a[0:2], 16), int(a[2:4], 16), int(a[4:6], 16)
    rb, gb, bb = int(b[0:2], 16), int(b[2:4], 16), int(b[4:6], 16)
    r = int(ra * (1 - t) + rb * t)
    g = int(ga * (1 - t) + gb * t)
    b = int(ba * (1 - t) + bb * t)
    return f"#{r:02x}{g:02x}{b:02x}"


def _conf_color_bgr(base: Tuple[int, int, int], conf: float) -> Tuple[int, int, int]:
    """Shift color based on confidence: high=base, mid=amber, low=red."""
    if conf >= 0.7:
        return base
    amber = (0, 170, 255)
    red = (60, 60, 255)
    if conf >= 0.4:
        t = (0.7 - conf) / 0.3
        return _blend_bgr(base, amber, t)
    t = min(1.0, (0.4 - conf) / 0.3)
    return _blend_bgr(amber, red, t)


def _conf_color_hex(base_hex: str, conf: float) -> str:
    if conf >= 0.7:
        return base_hex
    amber = "#ffaa00"
    red = "#ff3c3c"
    if conf >= 0.4:
        t = (0.7 - conf) / 0.3
        return _blend_hex(base_hex, amber, t)
    t = min(1.0, (0.4 - conf) / 0.3)
    return _blend_hex(amber, red, t)


_BONE_LENGTH_RATIOS = {
    (5, 7): (0.12, 0.35), (6, 8): (0.12, 0.35),
    (7, 9): (0.10, 0.32), (8, 10): (0.10, 0.32),
    (5, 11): (0.20, 0.55), (6, 12): (0.20, 0.55),
    (11, 13): (0.15, 0.42), (12, 14): (0.15, 0.42),
    (13, 15): (0.12, 0.38), (14, 16): (0.12, 0.38),
    (5, 6): (0.06, 0.30), (11, 12): (0.04, 0.25),
}


def _enforce_bone_lengths(kps: np.ndarray, box: Tuple[float, float, float, float], min_conf: float) -> np.ndarray:
    """Clamp keypoints so no bone exceeds anatomically plausible length ratios vs box height."""
    bh = max(1.0, box[3] - box[1])
    out = kps.copy()
    for (i, j), (lo, hi) in _BONE_LENGTH_RATIOS.items():
        if i >= out.shape[0] or j >= out.shape[0]:
            continue
        ci, cj = float(out[i, 2]), float(out[j, 2])
        if ci < min_conf * 0.3 or cj < min_conf * 0.3:
            continue
        dx = float(out[j, 0]) - float(out[i, 0])
        dy = float(out[j, 1]) - float(out[i, 1])
        length = math.hypot(dx, dy)
        ratio = length / bh
        if ratio > hi:
            scale = (hi * bh) / max(length, 1e-6)
            mx = (float(out[i, 0]) + float(out[j, 0])) / 2
            my = (float(out[i, 1]) + float(out[j, 1])) / 2
            if ci < cj:
                out[i, 0] = mx - dx * scale * 0.5
                out[i, 1] = my - dy * scale * 0.5
                out[i, 2] = ci * 0.85
            else:
                out[j, 0] = mx + dx * scale * 0.5
                out[j, 1] = my + dy * scale * 0.5
                out[j, 2] = cj * 0.85
    return out


def _interpolate_kps(kps: np.ndarray, min_conf: float) -> np.ndarray:
    out = kps.copy()
    for k in range(min(17, kps.shape[0])):
        if float(out[k, 2]) >= min_conf:
            continue
        nbrs = _NEIGHBORS.get(k, [])
        valid = []
        for n in nbrs:
            if n < out.shape[0] and float(out[n, 2]) >= min_conf * 0.5:
                valid.append((float(out[n, 0]), float(out[n, 1]), float(out[n, 2])))
        if len(valid) >= 1:
            tw = sum(v[2] for v in valid)
            out[k, 0] = sum(v[0] * v[2] for v in valid) / tw
            out[k, 1] = sum(v[1] * v[2] for v in valid) / tw
            out[k, 2] = min(v[2] for v in valid) * (0.55 if len(valid) >= 2 else 0.35)
    return out


def pose_stability(kps: np.ndarray, prev_kps_list: Optional[List[np.ndarray]], min_conf: float = 0.3) -> float:
    """Compute pose stability 0-1 from temporal variance of keypoint positions."""
    if prev_kps_list is None or len(prev_kps_list) < 3 or kps is None:
        return 0.5
    all_frames = prev_kps_list[-5:] + [kps]
    total_var = 0.0
    n_valid = 0
    for k in range(min(17, kps.shape[0])):
        xs, ys = [], []
        for fkps in all_frames:
            if fkps.shape[0] > k and float(fkps[k, 2]) >= min_conf:
                xs.append(float(fkps[k, 0]))
                ys.append(float(fkps[k, 1]))
        if len(xs) >= 3:
            total_var += np.var(xs) + np.var(ys)
            n_valid += 1
    if n_valid == 0:
        return 0.5
    avg_var = total_var / n_valid
    return max(0.0, min(1.0, 1.0 - avg_var / 400.0))


def _estimate_depths(kps: np.ndarray, box: Tuple[float, float, float, float], min_conf: float) -> np.ndarray:
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
        shoulder_w = abs(float(kps[5, 0]) - float(kps[6, 0]))

        for arm_kps, shoulder in [([7, 9], 5), ([8, 10], 6)]:
            max_ext = 0.0
            for ak in arm_kps:
                if ak < kps.shape[0] and float(kps[ak, 2]) >= min_conf * 0.5:
                    max_ext = max(max_ext, abs(float(kps[ak, 0]) - scx))
            if max_ext > bw * 0.3:
                ext_ratio = min(1.0, max_ext / (bw * 0.5))
                for ak in arm_kps:
                    if ak < kps.shape[0]:
                        depths[ak] = min(1.0, depths[ak] + 0.25 * ext_ratio)
                depths[shoulder] = min(1.0, depths[shoulder] + 0.12 * ext_ratio)

        if kps.shape[0] >= 17:
            l_hip = kps[11] if kps.shape[0] > 11 else None
            r_hip = kps[12] if kps.shape[0] > 12 else None
            if l_hip is not None and r_hip is not None:
                hip_w = abs(float(l_hip[0]) - float(r_hip[0]))
                if shoulder_w > 5 and hip_w > 5:
                    ratio = hip_w / shoulder_w
                    if ratio < 0.6:
                        for k in [11, 12, 13, 14, 15, 16]:
                            if k < kps.shape[0]:
                                depths[k] = min(1.0, depths[k] + 0.1)

    if kps.shape[0] >= 17:
        for leg_kps, hip in [([13, 15], 11), ([14, 16], 12)]:
            for lk in leg_kps:
                if lk < kps.shape[0] and float(kps[lk, 2]) >= min_conf * 0.5:
                    y_rel = (float(kps[lk, 1]) - box[1]) / bh
                    if y_rel > 0.7:
                        depths[lk] = min(1.0, depths[lk] + 0.15)

    return depths


def _sort_bones_by_depth(kps: np.ndarray, depths: np.ndarray, min_conf: float) -> List[Tuple[int, int]]:
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


def _spine_points(kps: np.ndarray, box: Tuple[float, float, float, float], min_conf: float) -> List[Tuple[int, int]]:
    """Extract spine control points: nose, neck, chest, pelvis."""
    pts = []
    rc = min_conf * 0.3
    if float(kps[0, 2]) >= rc:
        pts.append((int(kps[0, 0]), int(kps[0, 1])))
    if float(kps[5, 2]) >= rc and float(kps[6, 2]) >= rc:
        nx = (float(kps[5, 0]) + float(kps[6, 0])) / 2
        ny = (float(kps[5, 1]) + float(kps[6, 1])) / 2
        pts.append((int(nx), int(ny)))
        bh = box[3] - box[1]
        pts.append((int(nx), int(ny + bh * 0.15)))
    if float(kps[11, 2]) >= rc and float(kps[12, 2]) >= rc:
        px = (float(kps[11, 0]) + float(kps[12, 0])) / 2
        py = (float(kps[11, 1]) + float(kps[12, 1])) / 2
        pts.append((int(px), int(py)))
    return pts


def _draw_catmull_rom(img: np.ndarray, pts: List[Tuple[int, int]], color: Tuple[int, int, int], thickness: int) -> None:
    """Draw a smooth Catmull-Rom spline through the given points."""
    if len(pts) < 2:
        return
    if len(pts) == 2:
        cv2.line(img, pts[0], pts[1], color, thickness, cv2.LINE_AA)
        return

    all_pts = [pts[0]] + pts + [pts[-1]]
    curve = []
    for seg in range(len(all_pts) - 3):
        p0, p1, p2, p3 = all_pts[seg], all_pts[seg + 1], all_pts[seg + 2], all_pts[seg + 3]
        steps = 12
        for step in range(steps + 1):
            t = step / steps
            t2, t3 = t * t, t * t * t
            x = 0.5 * (
                (2 * p1[0]) +
                (-p0[0] + p2[0]) * t +
                (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2 +
                (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3
            )
            y = 0.5 * (
                (2 * p1[1]) +
                (-p0[1] + p2[1]) * t +
                (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2 +
                (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3
            )
            curve.append((int(x), int(y)))

    for i in range(len(curve) - 1):
        cv2.line(img, curve[i], curve[i + 1], color, thickness, cv2.LINE_AA)


def _draw_motion_trails(
    img: np.ndarray, prev_kps_list: List[np.ndarray], color: Tuple[int, int, int], min_conf: float
) -> None:
    """Draw fading motion trails from previous keypoint frames."""
    n_frames = len(prev_kps_list)
    if n_frames < 2:
        return
    trail_kps = [0, 9, 10, 15, 16]
    for k in trail_kps:
        pts = []
        for frame_kps in prev_kps_list:
            if frame_kps.shape[0] > k and float(frame_kps[k, 2]) >= min_conf * 0.5:
                pts.append((int(frame_kps[k, 0]), int(frame_kps[k, 1])))
        if len(pts) < 2:
            continue
        for i in range(len(pts) - 1):
            alpha = (i + 1) / len(pts)
            trail_c = _scale_bgr(color, alpha * 0.4)
            th = max(1, int(alpha * 2))
            cv2.line(img, pts[i], pts[i + 1], trail_c, th, cv2.LINE_AA)


def _draw_energy_field(
    img: np.ndarray, kps: np.ndarray, box: Tuple[float, float, float, float],
    color: Tuple[int, int, int], min_conf: float, frame_hash: int
) -> None:
    """Draw ambient energy particles near confident keypoints."""
    rng = np.random.RandomState(frame_hash & 0x7FFFFFFF)
    bh = max(1.0, box[3] - box[1])
    spread = max(8.0, bh * 0.06)
    particle_c = _scale_bgr(color, 0.35)

    for k in range(min(17, kps.shape[0])):
        if float(kps[k, 2]) < min_conf:
            continue
        n_particles = 2 if k in _KP_TORSO else 1
        for _ in range(n_particles):
            ox = rng.normal(0, spread)
            oy = rng.normal(0, spread)
            px = int(kps[k, 0] + ox)
            py = int(kps[k, 1] + oy)
            r = rng.randint(1, 3)
            cv2.circle(img, (px, py), r, particle_c, -1, cv2.LINE_AA)


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


def progressive_bone(
    kps: np.ndarray, preferred: str, box: Tuple[float, float, float, float], min_conf: float = 0.35
) -> Tuple[Optional[Tuple[float, float]], str]:
    """Try preferred bone, then fall back through head→neck→chest→pelvis.
    Returns (point, actual_bone_used)."""
    chain = ["head", "neck", "chest", "pelvis"]
    try:
        start = chain.index(preferred)
    except ValueError:
        start = 0
    order = chain[start:] + chain[:start]
    for name in order:
        pt = bone_point(kps, name, box)
        if pt is not None:
            idx_map = {"head": 0, "neck": 5, "chest": 5, "pelvis": 11}
            check_idx = idx_map.get(name, 0)
            if kps.shape[0] > check_idx and float(kps[check_idx, 2]) >= min_conf:
                return pt, name
    return None, preferred


def multi_bone_aim(
    kps: np.ndarray, preferred: str, box: Tuple[float, float, float, float], min_conf: float = 0.3
) -> Optional[Tuple[float, float]]:
    """Confidence-weighted blend of all visible bone points biased toward preferred.
    Returns a single aim point that uses information from every visible bone."""
    if kps is None or kps.shape[0] < 17:
        return None
    weights_map = {"head": 3.0, "neck": 1.5, "chest": 1.0, "pelvis": 0.5}
    if preferred in weights_map:
        weights_map[preferred] *= 2.5

    total_w = 0.0
    wx, wy = 0.0, 0.0
    for name, base_w in weights_map.items():
        pt = bone_point(kps, name, box)
        if pt is None:
            continue
        idx_map = {"head": 0, "neck": 5, "chest": 5, "pelvis": 11}
        ci = idx_map.get(name, 0)
        conf = float(kps[ci, 2]) if kps.shape[0] > ci else 0.0
        if conf < min_conf * 0.5:
            continue
        w = base_w * conf
        wx += pt[0] * w
        wy += pt[1] * w
        total_w += w
    if total_w < 0.01:
        return None
    return (wx / total_w, wy / total_w)


def target_silhouette(
    kps: np.ndarray, box: Tuple[float, float, float, float], min_conf: float = 0.3
) -> Optional[np.ndarray]:
    """Return convex hull points from confident keypoints for silhouette outline."""
    if kps is None or kps.shape[0] < 17:
        return None
    pts = []
    for k in range(min(17, kps.shape[0])):
        if float(kps[k, 2]) >= min_conf:
            pts.append([int(kps[k, 0]), int(kps[k, 1])])
    if len(pts) < 4:
        return None
    hull = cv2.convexHull(np.array(pts, dtype=np.int32))
    return hull


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


def preprocess(
    kps: np.ndarray, box: Tuple[float, float, float, float], min_conf: float = 0.3,
) -> Optional[Tuple[np.ndarray, np.ndarray, List[Tuple[int, int]]]]:
    """Run bone-length enforcement, interpolation, depth estimation, and bone sorting once.

    Returns (processed_kps, depths, sorted_bones) or None if kps is invalid.
    Both draw() and draw_overlay_items() accept this tuple to skip recomputation.
    """
    if kps is None or kps.shape[0] < 17:
        return None
    kps = _enforce_bone_lengths(kps, box, min_conf)
    kps = _interpolate_kps(kps, min_conf)
    depths = _estimate_depths(kps, box, min_conf)
    sorted_bones = _sort_bones_by_depth(kps, depths, min_conf)
    return (kps, depths, sorted_bones)


def draw(
    frame: np.ndarray,
    kps: np.ndarray,
    color_hex: str,
    box: Tuple[float, float, float, float],
    th: int = 2,
    min_conf: float = 0.3,
    draw_fov_circle: bool = True,
    prev_kps_list: Optional[List[np.ndarray]] = None,
    preprocessed: Optional[Tuple[np.ndarray, np.ndarray, List[Tuple[int, int]]]] = None,
) -> None:
    """Ultra-advanced skeleton: confidence-gradient glow, motion trails, spine curve, energy field."""
    if kps is None or kps.shape[0] < 17:
        return

    if preprocessed is not None:
        kps, depths, sorted_bones = preprocessed
    else:
        kps = _enforce_bone_lengths(kps, box, min_conf)
        kps = _interpolate_kps(kps, min_conf)
        depths = _estimate_depths(kps, box, min_conf)
        sorted_bones = _sort_bones_by_depth(kps, depths, min_conf)
    c = _hex_to_bgr(color_hex)
    render_conf = min_conf * 0.2

    if prev_kps_list:
        _draw_motion_trails(frame, prev_kps_list + [kps], c, min_conf)

    frame_hash = int(kps[0, 0] * 1000 + kps[0, 1] * 777) if kps.shape[0] > 0 else 0
    _draw_energy_field(frame, kps, box, c, min_conf, frame_hash)

    fh, fw = frame.shape[:2]
    glow_margin = 30
    gx1 = max(0, int(box[0]) - glow_margin)
    gy1 = max(0, int(box[1]) - glow_margin)
    gx2 = min(fw, int(box[2]) + glow_margin)
    gy2 = min(fh, int(box[3]) + glow_margin)
    gw, gh = gx2 - gx1, gy2 - gy1
    if gw < 4 or gh < 4:
        gw, gh = fw, fh
        gx1, gy1, gx2, gy2 = 0, 0, fw, fh
    glow_local = np.zeros((gh, gw, 3), dtype=frame.dtype)

    for i, j in sorted_bones:
        ci = float(kps[i, 2])
        cj = float(kps[j, 2])
        if ci < render_conf or cj < render_conf:
            continue
        pt1 = (int(kps[i, 0]) - gx1, int(kps[i, 1]) - gy1)
        pt2 = (int(kps[j, 0]) - gx1, int(kps[j, 1]) - gy1)
        di = depths[min(i, len(depths) - 1)]
        dj = depths[min(j, len(depths) - 1)]
        avg_d = (di + dj) / 2.0
        avg_conf = (ci + cj) / 2.0
        conf_f = min(1.0, avg_conf / 0.8)
        brightness = (0.5 + avg_d * 0.5) * conf_f
        glow_th = max(1, int((th + 3) * (1.0 + avg_d * 0.8)))
        glow_c = _conf_color_bgr(_scale_bgr(c, brightness * 1.3), avg_conf)
        cv2.line(glow_local, pt1, pt2, glow_c, glow_th, cv2.LINE_AA)

    for k in range(min(17, kps.shape[0])):
        if float(kps[k, 2]) < render_conf:
            continue
        pt = (int(kps[k, 0]) - gx1, int(kps[k, 1]) - gy1)
        d = depths[min(k, len(depths) - 1)]
        conf = float(kps[k, 2])
        r = 7 if k in _KP_HEAD else 6
        gc = _conf_color_bgr(_scale_bgr(c, 0.6 + d * 0.4), conf)
        cv2.circle(glow_local, pt, r + 4, gc, -1, cv2.LINE_AA)

    if float(kps[0, 2]) >= min_conf:
        nose = (int(kps[0, 0]) - gx1, int(kps[0, 1]) - gy1)
        hr = int(head_radius(kps, box, min_conf))
        cv2.circle(glow_local, nose, hr + 8, _scale_bgr(c, 0.9), 3, cv2.LINE_AA)

    glow_local = cv2.GaussianBlur(glow_local, (0, 0), sigmaX=8, sigmaY=8)
    roi = frame[gy1:gy2, gx1:gx2]
    cv2.addWeighted(glow_local, 0.7, roi, 1.0, 0, roi)

    spine_pts = _spine_points(kps, box, min_conf)
    if len(spine_pts) >= 3:
        _draw_catmull_rom(frame, spine_pts, _scale_bgr(c, 0.3), max(1, th - 1))

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
        avg_conf = (ci + cj) / 2.0
        conf_f = min(1.0, avg_conf / 0.8)
        core_th = max(1, int(th * (0.8 + avg_d * 0.6)))
        brightness = (0.7 + avg_d * 0.3) * conf_f
        bone_color = _conf_color_bgr(_scale_bgr(c, brightness), avg_conf)
        cv2.line(frame, pt1, pt2, bone_color, core_th, cv2.LINE_AA)

    for k in range(min(17, kps.shape[0])):
        conf = float(kps[k, 2])
        if conf < render_conf:
            continue
        pt = (int(kps[k, 0]), int(kps[k, 1]))
        d = depths[min(k, len(depths) - 1)]
        conf_f = min(1.0, conf / 0.7)
        brightness = (0.6 + d * 0.4) * conf_f
        jc = _conf_color_bgr(_scale_bgr(c, brightness), conf)

        if k in _KP_TORSO:
            r = max(3, int(4 * (0.8 + d * 0.5)))
            half = r
            diamond = np.array([
                [pt[0], pt[1] - half],
                [pt[0] + half, pt[1]],
                [pt[0], pt[1] + half],
                [pt[0] - half, pt[1]],
            ], dtype=np.int32)
            cv2.fillPoly(frame, [diamond], _scale_bgr(jc, 0.5), cv2.LINE_AA)
            cv2.polylines(frame, [diamond], True, jc, 1, cv2.LINE_AA)
        else:
            r = 4 if k in _KP_HEAD else 3
            r = max(2, int(r * (0.8 + d * 0.5)))
            cv2.circle(frame, pt, r + 2, _scale_bgr(jc, 0.5), -1, cv2.LINE_AA)
            cv2.circle(frame, pt, r, jc, -1, cv2.LINE_AA)
            if r >= 2:
                cv2.circle(frame, pt, max(1, r - 1), _brighten_bgr(jc, 0.5), -1, cv2.LINE_AA)

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
    prev_kps_list: Optional[List[np.ndarray]] = None,
    preprocessed: Optional[Tuple[np.ndarray, np.ndarray, List[Tuple[int, int]]]] = None,
) -> list:
    """Overlay items: confidence-gradient bones, motion trails, enhanced joints."""
    items: list = []
    if kps is None or kps.shape[0] < 17:
        return items

    if preprocessed is not None:
        kps, depths, sorted_bones = preprocessed
    else:
        kps = _enforce_bone_lengths(kps, box, min_conf)
        kps = _interpolate_kps(kps, min_conf)
        depths = _estimate_depths(kps, box, min_conf)
        sorted_bones = _sort_bones_by_depth(kps, depths, min_conf)
    render_conf = min_conf * 0.2

    if prev_kps_list and len(prev_kps_list) >= 2:
        trail_kps = [0, 9, 10, 15, 16]
        all_frames = prev_kps_list + [kps]
        for k in trail_kps:
            pts = []
            for fkps in all_frames:
                if fkps.shape[0] > k and float(fkps[k, 2]) >= min_conf * 0.5:
                    pts.append((int(fkps[k, 0]), int(fkps[k, 1])))
            if len(pts) >= 2:
                for i in range(len(pts) - 1):
                    alpha = (i + 1) / len(pts)
                    trail_hex = _dim_hex(color_hex, alpha * 0.3)
                    items.append(("line", pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], trail_hex, max(1, int(alpha * 2))))

    glow_hex = _dim_hex(color_hex, 0.2)
    mid_hex = _dim_hex(color_hex, 0.5)

    for i, j in sorted_bones:
        ci = float(kps[i, 2])
        cj = float(kps[j, 2])
        if ci < render_conf or cj < render_conf:
            continue
        x1, y1 = int(kps[i, 0]), int(kps[i, 1])
        x2, y2 = int(kps[j, 0]), int(kps[j, 1])
        di = depths[min(i, len(depths) - 1)]
        dj = depths[min(j, len(depths) - 1)]
        avg_d = (di + dj) / 2.0
        avg_conf = (ci + cj) / 2.0
        gw = max(1, int(7 + avg_d * 5))
        conf_glow = _conf_color_hex(glow_hex, avg_conf)
        items.append(("line", x1, y1, x2, y2, conf_glow, gw))

    for i, j in sorted_bones:
        ci = float(kps[i, 2])
        cj = float(kps[j, 2])
        if ci < render_conf or cj < render_conf:
            continue
        x1, y1 = int(kps[i, 0]), int(kps[i, 1])
        x2, y2 = int(kps[j, 0]), int(kps[j, 1])
        di = depths[min(i, len(depths) - 1)]
        dj = depths[min(j, len(depths) - 1)]
        avg_d = (di + dj) / 2.0
        avg_conf = (ci + cj) / 2.0
        mw = max(1, int(4 + avg_d * 3))
        conf_mid = _conf_color_hex(mid_hex, avg_conf)
        items.append(("line", x1, y1, x2, y2, conf_mid, mw))

    for i, j in sorted_bones:
        ci = float(kps[i, 2])
        cj = float(kps[j, 2])
        if ci < render_conf or cj < render_conf:
            continue
        x1, y1 = int(kps[i, 0]), int(kps[i, 1])
        x2, y2 = int(kps[j, 0]), int(kps[j, 1])
        di = depths[min(i, len(depths) - 1)]
        dj = depths[min(j, len(depths) - 1)]
        avg_d = (di + dj) / 2.0
        avg_conf = (ci + cj) / 2.0
        cw = max(1, int(2 + avg_d * 1.5))
        bright = _conf_color_hex(_brighten_hex(color_hex, avg_d * 0.25), avg_conf)
        items.append(("line", x1, y1, x2, y2, bright, cw))

    for k in range(min(17, kps.shape[0])):
        conf = float(kps[k, 2])
        if conf < render_conf:
            continue
        x, y = int(kps[k, 0]), int(kps[k, 1])
        d = depths[min(k, len(depths) - 1)]
        r = 5 if k in _KP_HEAD else 4
        r = max(2, int(r * (0.8 + d * 0.5)))
        conf_glow_j = _conf_color_hex(glow_hex, conf)
        conf_mid_j = _conf_color_hex(mid_hex, conf)
        conf_bright_j = _conf_color_hex(_brighten_hex(color_hex, d * 0.25), conf)
        items.append(("dot", x, y, r + 4, conf_glow_j))
        items.append(("dot", x, y, r + 2, conf_mid_j))
        items.append(("dot", x, y, r, conf_bright_j))

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
