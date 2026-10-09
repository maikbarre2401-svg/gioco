#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
  RICK AND MORTY - CITTA' INTERDIMENSIONALE
  Open world 3D in stile "GTA", in terza e prima persona.
  Fan game NON ufficiale scritto da zero in Python + Panda3D.
===============================================================================
Tutto (citta', personaggi, auto, cielo, texture, suoni e musica) e' generato
via codice: non serve nessun file esterno.

Avvio:
    pip install panda3d numpy
    python rick_morty_3d.py

Comandi principali (a piedi):
    W A S D ........... muoviti          Shift .......... scatto
    Mouse ............. guarda           Spazio ......... salta
    Click sinistro .... spara            Click destro ... mira
    1 2 3 / rotellina . cambia arma      E .............. pistola portale
    F ................. entra/esci auto  V .............. 1a / 3a persona
    H ................. fiaschetta       M .............. mappa grande
    Esc ............... pausa
In auto: W/S acceleratore/freno, A/D sterzo, Spazio freno a mano,
         H clacson, R radio, (navicella: Spazio sali, Ctrl scendi)

Rick and Morty e tutti i personaggi sono (c) Adult Swim / Williams Street.
Progetto amatoriale, gratuito e senza scopo di lucro.
"""

import json
import math
import os
import random
import sys
import tempfile
import wave

try:
    import numpy as np
    import panda3d
    from panda3d.core import loadPrcFileData, Filename
except ImportError:  # pragma: no cover
    print("Servono panda3d e numpy.  Installali con:   pip install panda3d numpy")
    try:
        input("Premi Invio per uscire...")
    except Exception:
        pass
    sys.exit(1)

OFFSCREEN = os.environ.get("RM3D_OFFSCREEN") == "1"
SAVE_PATH = os.path.join(os.path.expanduser("~"), ".rick_morty_3d_save.json")


def _configure_panda():
    pdir = Filename.fromOsSpecific(os.path.dirname(os.path.abspath(panda3d.__file__))).getFullpath()
    cfg = [
        "window-title Rick and Morty - Citta' Interdimensionale",
        "win-size 1280 720",
        "sync-video 1",
        "textures-power-2 none",
        "notify-level warning",
        "default-directnotify-level warning",
        "load-display pandagl",
        "plugin-path " + pdir,
        "framebuffer-multisample 1",
        "multisamples 4",
        "gl-coordinate-system default",
        "basic-shaders-only 0",
        "texture-anisotropic-degree 8",
        "model-cache-dir",
    ]
    if OFFSCREEN:
        cfg += ["window-type offscreen", "audio-library-name null", "framebuffer-multisample 0", "multisamples 0"]
    else:
        cfg += ["audio-library-name p3openal_audio"]
    loadPrcFileData("rm3d", "\n".join(cfg))


_configure_panda()

from direct.showbase.ShowBase import ShowBase  # noqa: E402
from direct.gui.OnscreenText import OnscreenText  # noqa: E402
from direct.gui.OnscreenImage import OnscreenImage  # noqa: E402
from panda3d.core import (  # noqa: E402
    BitMask32, CardMaker, ColorBlendAttrib, DirectionalLight, Geom, GeomNode, GeomTriangles, GeomVertexArrayFormat,
    GeomVertexData, GeomVertexFormat, KeyboardButton, LMatrix4f, LVecBase4f, MouseButton, NodePath, PTA_LVecBase4f,
    SamplerState, Shader, TextNode, Texture, TextureStage, TransformState, TransparencyAttrib, Vec3, Vec4,
    WindowProperties, ClockObject, AudioSound, CullFaceAttrib, LODNode, Point3,
    RenderState, FrameBufferProperties,
)

# =============================================================================
#  COSTANTI E UTILITA'
# =============================================================================
TAU = math.pi * 2


def clamp(v, a, b):
    return a if v < a else b if v > b else v


def lerp(a, b, t):
    return a + (b - a) * t


def smoothstep(a, b, x):
    t = clamp((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def approach(v, target, d):
    if v < target:
        return min(v + d, target)
    return max(v - d, target)


def wrap_angle(a):
    """angolo in gradi in [-180, 180)"""
    return (a + 180.0) % 360.0 - 180.0


def angle_lerp(a, b, t):
    return a + wrap_angle(b - a) * t


def lerp3(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t)


def dist2(ax, ay, bx, by):
    return math.hypot(bx - ax, by - ay)


def heading_vec(h):
    """vettore avanti (x, y) per heading in gradi (Panda: 0 = +Y, positivo = antiorario)"""
    r = math.radians(h)
    return -math.sin(r), math.cos(r)


def vec_heading(x, y):
    return math.degrees(math.atan2(-x, y))


def load_save():
    try:
        with open(SAVE_PATH, "r", encoding="utf-8") as f:
            d = json.load(f)
        if not isinstance(d, dict):
            d = {}
    except Exception:
        d = {}
    d.setdefault("mission", 0)
    d.setdefault("money", 250)
    d.setdefault("weapons", [0, 1])
    d.setdefault("quality", 1)
    d.setdefault("audio", True)
    d.setdefault("sens", 1.0)
    return d


def write_save(d):
    try:
        with open(SAVE_PATH, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=1)
    except Exception:
        pass


# =============================================================================
#  TEXTURE PROCEDURALI (numpy)
# =============================================================================
def value_noise(size, cells, seed):
    rng = np.random.default_rng(seed)
    g = rng.random((cells, cells), dtype=np.float32)
    x = np.arange(size, dtype=np.float32) * cells / size
    i0 = np.floor(x).astype(np.int64)
    f = x - i0
    f = f * f * (3 - 2 * f)
    i1 = (i0 + 1) % cells
    i0 = i0 % cells
    a = g[i0][:, i0]
    b = g[i0][:, i1]
    c = g[i1][:, i0]
    d = g[i1][:, i1]
    fx = f[None, :]
    fy = f[:, None]
    top = a + (b - a) * fx
    bot = c + (d - c) * fx
    return top + (bot - top) * fy


def fbm(size, base_cells, octaves, seed, persistence=0.5):
    total = np.zeros((size, size), np.float32)
    amp, norm = 1.0, 0.0
    for o in range(octaves):
        cells = base_cells * (2 ** o)
        if cells > size:
            break
        total += value_noise(size, cells, seed + o * 131) * amp
        norm += amp
        amp *= persistence
    return total / norm


def grain(shape, seed, amount):
    rng = np.random.default_rng(seed)
    return (rng.random(shape, dtype=np.float32) - 0.5) * amount


def to_u8(a):
    return np.clip(a, 0, 255).astype(np.uint8)


def make_texture(arr, name="tex", repeat=True, mipmap=True, nearest=False):
    arr = np.ascontiguousarray(arr)
    h, w = arr.shape[:2]
    c = arr.shape[2] if arr.ndim == 3 else 1
    tex = Texture(name)
    fmt = {1: Texture.F_luminance, 3: Texture.F_rgb8, 4: Texture.F_rgba8}[c]
    tex.setup2dTexture(w, h, Texture.T_unsigned_byte, fmt)
    flipped = np.ascontiguousarray(arr[::-1])
    tex.setRamImageAs(flipped.tobytes(), {1: "G", 3: "RGB", 4: "RGBA"}[c])
    wm = SamplerState.WM_repeat if repeat else SamplerState.WM_clamp
    tex.setWrapU(wm)
    tex.setWrapV(wm)
    if nearest:
        tex.setMinfilter(SamplerState.FT_nearest)
        tex.setMagfilter(SamplerState.FT_nearest)
    elif mipmap:
        tex.setMinfilter(SamplerState.FT_linear_mipmap_linear)
        tex.setMagfilter(SamplerState.FT_linear)
        tex.setAnisotropicDegree(8)
    else:
        tex.setMinfilter(SamplerState.FT_linear)
        tex.setMagfilter(SamplerState.FT_linear)
    return tex


def solid_texture(rgb, name="solid"):
    a = np.zeros((4, 4, 3), np.uint8)
    a[:, :] = rgb
    return make_texture(a, name, mipmap=False)


def tex_asphalt(size=512, seed=1):
    n = fbm(size, 8, 6, seed)
    g = grain((size, size), seed + 7, 26)
    base = 52 + n * 26 + g
    rng = np.random.default_rng(seed)
    # macchie d'olio e rattoppi
    stains = fbm(size, 4, 3, seed + 40)
    base -= np.clip(stains - 0.62, 0, 1) * 70
    patch = fbm(size, 3, 2, seed + 90)
    base += np.where(patch > 0.7, 9, 0)
    # ghiaietto chiaro
    dots = rng.random((size, size)) > 0.985
    base += dots * 30
    rgb = np.stack([base, base + 1, base + 4], -1)
    return to_u8(rgb)


def tex_sidewalk(size=256, seed=2):
    n = fbm(size, 8, 5, seed)
    g = grain((size, size), seed + 3, 18)
    base = 128 + n * 26 + g
    tile = size // 2
    yy, xx = np.mgrid[0:size, 0:size]
    seam = ((xx % tile) < 2) | ((yy % tile) < 2)
    base = np.where(seam, base - 45, base)
    stains = fbm(size, 3, 3, seed + 11)
    base -= np.clip(stains - 0.6, 0, 1) * 80
    rgb = np.stack([base, base - 2, base - 6], -1)
    return to_u8(rgb)


def tex_grass(size=256, seed=3):
    n = fbm(size, 6, 6, seed)
    g = grain((size, size), seed + 5, 40)
    r = 62 + n * 26 + g * 0.5
    gg = 84 + n * 30 + g * 0.8
    b = 44 + n * 14
    dry = fbm(size, 3, 3, seed + 9)
    r += np.clip(dry - 0.55, 0, 1) * 120
    gg += np.clip(dry - 0.55, 0, 1) * 40
    return to_u8(np.stack([r, gg, b], -1))


def tex_gravel(size=256, seed=4):
    n = fbm(size, 16, 4, seed)
    g = grain((size, size), seed, 50)
    base = 140 + n * 40 + g
    return to_u8(np.stack([base + 8, base, base - 16], -1))


def tex_roof(size=256, seed=5):
    n = fbm(size, 10, 5, seed)
    g = grain((size, size), seed, 40)
    base = 92 + n * 34 + g
    return to_u8(np.stack([base, base, base + 2], -1))


def tex_shingles(size=256, seed=6):
    rng = np.random.default_rng(seed)
    out = np.zeros((size, size, 3), np.float32)
    rows = 16
    rh = size // rows
    for r in range(rows):
        off = (r % 2) * 8
        for c in range(-1, size // 16 + 1):
            v = rng.uniform(0.8, 1.2)
            x0 = c * 16 + off
            out[r * rh:(r + 1) * rh, max(0, x0):max(0, min(size, x0 + 15))] = np.array([92, 58, 50]) * v
        out[r * rh + rh - 2:r * rh + rh] = (40, 28, 26)
    out += grain((size, size), seed, 30)[..., None]
    return to_u8(out)


def _wall_material(kind, size, seed):
    n = fbm(size, 8, 5, seed)
    g = grain((size, size), seed + 1, 16)
    if kind == "brick":
        out = np.zeros((size, size, 3), np.float32)
        rng = np.random.default_rng(seed)
        bh, bw = 8, 20
        for r in range(size // bh):
            off = (r % 2) * (bw // 2)
            for c in range(-1, size // bw + 1):
                col = np.array([150, 70, 52]) * rng.uniform(0.78, 1.15)
                x0 = c * bw + off
                out[r * bh:r * bh + bh - 2, max(0, x0):max(0, min(size, x0 + bw - 2))] = col
        mortar = out.sum(-1) == 0
        out[mortar] = (176, 168, 156)
        out += (n[..., None] - 0.5) * 30 + g[..., None]
        return out
    if kind == "plaster":
        base = np.stack([218 + n * 20, 202 + n * 18, 170 + n * 14], -1)
    elif kind == "concrete":
        base = np.stack([170 + n * 30, 170 + n * 30, 166 + n * 28], -1)
    elif kind == "dark":
        base = np.stack([62 + n * 18, 66 + n * 18, 74 + n * 18], -1)
    elif kind == "teal":
        base = np.stack([120 + n * 18, 150 + n * 20, 150 + n * 20], -1)
    else:
        base = np.stack([196 + n * 22, 180 + n * 20, 156 + n * 18], -1)
    return base + g[..., None]


def tex_facade(kind, seed, size=256):
    """Facciata con 4x4 finestre (= 12 m x 12 m). Ritorna (albedo, emissive)."""
    rng = np.random.default_rng(seed)
    alb = _wall_material(kind, size, seed)
    emi = np.zeros((size, size, 3), np.float32)
    cell = size // 4
    yy, xx = np.mgrid[0:cell, 0:cell]
    if kind == "glass":
        # torre a vetri: pannelli quasi continui
        n = fbm(size, 4, 3, seed + 5)
        sky = np.linspace(1.0, 0.55, size)[:, None]
        alb[..., 0] = 60 + 50 * sky + n * 30
        alb[..., 1] = 92 + 60 * sky + n * 30
        alb[..., 2] = 118 + 70 * sky + n * 30
        for f in range(4):
            y0 = f * cell
            alb[y0 + cell - 10:y0 + cell] = (44, 50, 58)
            alb[y0:y0 + 2] = (150, 160, 170)
            for c in range(8):
                x0 = c * (size // 8)
                alb[y0:y0 + cell, x0:x0 + 2] = (150, 160, 170)
                if rng.random() < 0.55:
                    lvl = rng.uniform(0.6, 1.0)
                    emi[y0 + 4:y0 + cell - 12, x0 + 3:x0 + size // 8 - 1] = np.array([190, 200, 215]) * lvl * 0.8
        return to_u8(alb), to_u8(emi)
    frame_col = {"brick": (225, 220, 210), "plaster": (110, 84, 60), "concrete": (60, 64, 70),
                 "dark": (30, 32, 36), "teal": (240, 240, 235)}.get(kind, (250, 248, 240))
    wx0, wx1 = int(cell * 0.22), int(cell * 0.78)
    wy0, wy1 = int(cell * 0.18), int(cell * 0.82)
    if kind in ("concrete", "dark"):
        wx0, wx1 = int(cell * 0.06), int(cell * 0.94)
        wy0, wy1 = int(cell * 0.2), int(cell * 0.78)
    for fy in range(4):
        for fx in range(4):
            y0, x0 = fy * cell, fx * cell
            # cornice
            alb[y0 + wy0 - 3:y0 + wy1 + 3, x0 + wx0 - 3:x0 + wx1 + 3] = frame_col
            # vetro con riflesso del cielo
            gy = np.linspace(0, 1, wy1 - wy0)[:, None]
            tint = rng.uniform(0.85, 1.1)
            glass = np.stack([46 + 70 * (1 - gy), 60 + 84 * (1 - gy), 76 + 96 * (1 - gy)], -1) * tint
            glass = np.broadcast_to(glass, (wy1 - wy0, wx1 - wx0, 3)).copy()
            # tende
            if rng.random() < 0.4:
                cw = int((wx1 - wx0) * rng.uniform(0.2, 0.45))
                ccol = np.array(rng.choice([(200, 190, 160), (170, 60, 50), (220, 220, 220), (90, 110, 150)]))
                glass[:, :cw] = ccol * 0.8
            alb[y0 + wy0:y0 + wy1, x0 + wx0:x0 + wx1] = glass
            mx = (wx0 + wx1) // 2
            alb[y0 + wy0:y0 + wy1, x0 + mx - 1:x0 + mx + 1] = frame_col
            # davanzale
            alb[y0 + wy1 + 3:y0 + wy1 + 6, x0 + wx0 - 5:x0 + wx1 + 5] = (200, 196, 188)
            # luci di notte
            if rng.random() < 0.45:
                warm = rng.random() < 0.8
                col = np.array([255, 196, 120]) if warm else np.array([150, 190, 255])
                lvl = rng.uniform(0.55, 1.0)
                emi[y0 + wy0:y0 + wy1, x0 + wx0:x0 + wx1] = col * lvl
                emi[y0 + wy0:y0 + wy1, x0 + mx - 1:x0 + mx + 1] = 0
    return to_u8(alb), to_u8(emi)


def tex_shopfront(seed, w=256, h=96):
    """Piano terra con negozi (12 m x 4.5 m)."""
    rng = np.random.default_rng(seed)
    alb = np.zeros((h, w, 3), np.float32)
    emi = np.zeros((h, w, 3), np.float32)
    alb[:] = (70, 66, 62)
    n = fbm(256, 8, 3, seed)[:h, :w]
    alb += (n[..., None] - 0.5) * 20
    units = 3
    uw = w // units
    for u in range(units):
        x0 = u * uw
        sign = np.array(rng.choice([(200, 40, 40), (40, 90, 180), (240, 190, 40), (40, 140, 80), (150, 60, 160), (30, 30, 30)]))
        alb[2:18, x0 + 4:x0 + uw - 4] = sign
        emi[2:18, x0 + 4:x0 + uw - 4] = np.minimum(sign * 1.2 + 40, 255)
        # lettere finte
        for k in range(rng.integers(3, 7)):
            lx = x0 + 10 + k * 9
            if lx + 6 < x0 + uw - 6:
                alb[6:14, lx:lx + 6] = (250, 250, 245)
                emi[6:14, lx:lx + 6] = (255, 255, 240)
        # tenda da sole
        if rng.random() < 0.6:
            c1 = np.array(rng.choice([(200, 50, 50), (40, 110, 60), (40, 70, 140), (220, 160, 40)]))
            for k in range(x0 + 2, x0 + uw - 2):
                alb[19:27, k] = c1 if ((k - x0) // 6) % 2 == 0 else (235, 235, 230)
        # vetrina
        gy = np.linspace(0, 1, 60)[:, None]
        glass = np.stack([60 + 60 * (1 - gy), 72 + 70 * (1 - gy), 84 + 80 * (1 - gy)], -1)
        alb[30:90, x0 + 6:x0 + uw - 22] = glass
        inner = np.array([230, 200, 150]) * rng.uniform(0.45, 0.8)
        emi[30:90, x0 + 6:x0 + uw - 22] = inner
        # porta
        alb[34:94, x0 + uw - 20:x0 + uw - 6] = (50, 44, 40)
        alb[38:90, x0 + uw - 18:x0 + uw - 8] = (90, 110, 120)
        emi[38:90, x0 + uw - 18:x0 + uw - 8] = (200, 170, 120)
        alb[28:30, x0 + 4:x0 + uw - 4] = (40, 40, 40)
    alb[90:] = (95, 92, 88)
    return to_u8(alb), to_u8(emi)


def tex_house(seed, w=256, h=128):
    """Casa di periferia: assi di legno + finestre (12 m x 6 m)."""
    rng = np.random.default_rng(seed)
    col = np.array(rng.choice([(226, 214, 190), (180, 200, 214), (214, 190, 160), (200, 210, 186), (236, 236, 228)]))
    alb = np.zeros((h, w, 3), np.float32)
    alb[:] = col
    for y in range(0, h, 6):
        alb[y:y + 1] = col * 0.78
    alb += grain((h, w), seed, 10)[..., None]
    emi = np.zeros((h, w, 3), np.float32)
    for wx in (30, 110, 190):
        for wy0 in (14, 74):
            alb[wy0 - 3:wy0 + 37, wx - 3:wx + 41] = (250, 250, 248)
            gy = np.linspace(0, 1, 34)[:, None]
            alb[wy0:wy0 + 34, wx:wx + 38] = np.stack([50 + 60 * (1 - gy), 66 + 70 * (1 - gy), 80 + 80 * (1 - gy)], -1)
            alb[wy0:wy0 + 34, wx + 18:wx + 20] = (250, 250, 248)
            alb[wy0 - 3:wy0 + 37, wx - 12:wx - 3] = col * 0.55
            alb[wy0 - 3:wy0 + 37, wx + 41:wx + 50] = col * 0.55
            if rng.random() < 0.5:
                emi[wy0:wy0 + 34, wx:wx + 38] = (255, 200, 130)
    return to_u8(alb), to_u8(emi)


def tex_portal(size=256):
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    cx = cy = size / 2
    dx, dy = (xx - cx) / cx, (yy - cy) / cy
    r = np.sqrt(dx * dx + dy * dy)
    a = np.arctan2(dy, dx)
    swirl = 0.5 + 0.5 * np.sin(a * 4 + r * 14)
    g = np.clip(1 - r, 0, 1)
    rr = (40 + 150 * swirl * g + 200 * g ** 4)
    gg = (140 + 115 * g + 30 * swirl)
    bb = (30 + 100 * swirl * g ** 2 + 160 * g ** 5)
    alpha = np.clip((1 - r) * 6, 0, 1) * 255
    rim = np.exp(-((r - 0.92) ** 2) / 0.002)
    gg += rim * 60
    return to_u8(np.stack([rr, gg, bb, alpha], -1))


def tex_soft(size=64, power=2.0):
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    c = (size - 1) / 2
    r = np.sqrt((xx - c) ** 2 + (yy - c) ** 2) / c
    a = np.clip(1 - r, 0, 1) ** power * 255
    w = np.full((size, size), 255, np.float32)
    return to_u8(np.stack([w, w, w, a], -1))


def tex_smoke(size=64, seed=9):
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    c = (size - 1) / 2
    r = np.sqrt((xx - c) ** 2 + (yy - c) ** 2) / c
    n = fbm(size, 4, 4, seed)
    a = np.clip((1 - r) * 1.4 - (1 - n) * 0.6, 0, 1) * 255
    w = 200 + n * 55
    return to_u8(np.stack([w, w, w, a], -1))


def tex_clouds(size=512, seed=12):
    n = fbm(size, 4, 7, seed, 0.55)
    n = (n - n.min()) / (n.max() - n.min())
    return to_u8(n * 255)


# =============================================================================
#  COSTRUTTORE DI MESH (geometria generata via codice)
# =============================================================================
_VFORMAT = None


def vertex_format():
    global _VFORMAT
    if _VFORMAT is None:
        a = GeomVertexArrayFormat()
        a.addColumn("vertex", 3, Geom.NT_float32, Geom.C_point)
        a.addColumn("normal", 3, Geom.NT_float32, Geom.C_normal)
        a.addColumn("color", 4, Geom.NT_float32, Geom.C_color)
        a.addColumn("texcoord", 2, Geom.NT_float32, Geom.C_texcoord)
        f = GeomVertexFormat()
        f.addArray(a)
        _VFORMAT = GeomVertexFormat.registerFormat(f)
    return _VFORMAT


def _col(c):
    if len(c) == 3:
        return (c[0] / 255.0, c[1] / 255.0, c[2] / 255.0, 1.0)
    return (c[0] / 255.0, c[1] / 255.0, c[2] / 255.0, c[3] / 255.0)


def _norm(v):
    l = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]) or 1.0
    return (v[0] / l, v[1] / l, v[2] / l)


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


class Mesh:
    """Accumula triangoli (posizione, normale, colore, uv) e crea un GeomNode."""

    def __init__(self):
        self.vs = []
        self.ids = []
        self.chunks = []

    def __len__(self):
        return len(self.vs) + sum(len(c[0]) for c in self.chunks)

    def v(self, p, n, c, uv=(0.0, 0.0)):
        self.vs.append((p[0], p[1], p[2], n[0], n[1], n[2], c[0], c[1], c[2], c[3], uv[0], uv[1]))
        return len(self.vs) - 1

    def tri(self, a, b, c):
        self.ids.extend((a, b, c))

    def quad(self, a, b, c, d, color, uvs=((0, 0), (1, 0), (1, 1), (0, 1)), n=None):
        if n is None:
            n = _norm(_cross(_sub(b, a), _sub(d, a)))
        col = _col(color)
        i = self.v(a, n, col, uvs[0])
        self.v(b, n, col, uvs[1])
        self.v(c, n, col, uvs[2])
        self.v(d, n, col, uvs[3])
        self.ids.extend((i, i + 1, i + 2, i, i + 2, i + 3))

    def box(self, x0, y0, z0, x1, y1, z1, color, uv=None, faces="xXyYzZ", u_off=0.0, v_base=0.0, wrap_u=False):
        """uv=(su, sv): coordinate texture in metri (facciate). None = 0..1 per faccia.
        wrap_u: la coordinata u continua attorno al perimetro (finestre allineate agli angoli)."""
        state = [u_off]

        def fuv(L, za, zb):
            if uv is None:
                return ((0, 0), (1, 0), (1, 1), (0, 1))
            su, sv = uv
            u0 = state[0] if wrap_u else u_off
            if wrap_u:
                state[0] += L / su
            va, vb = (za - v_base) / sv, (zb - v_base) / sv
            return ((u0, va), (u0 + L / su, va), (u0 + L / su, vb), (u0, vb))
        dx, dy = x1 - x0, y1 - y0
        if "z" in faces:
            tuv = ((0, 0), (1, 0), (1, 1), (0, 1)) if uv is None else ((x0 / uv[0], y0 / uv[0]), (x1 / uv[0], y0 / uv[0]),
                                                                       (x1 / uv[0], y1 / uv[0]), (x0 / uv[0], y1 / uv[0]))
            self.quad((x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1), color, tuv, (0, 0, 1))
        if "Z" in faces:
            self.quad((x0, y1, z0), (x1, y1, z0), (x1, y0, z0), (x0, y0, z0), color, n=(0, 0, -1))
        if "y" in faces:
            self.quad((x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1), color, fuv(dx, z0, z1), (0, -1, 0))
        if "X" in faces:
            self.quad((x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1), color, fuv(dy, z0, z1), (1, 0, 0))
        if "Y" in faces:
            self.quad((x1, y1, z0), (x0, y1, z0), (x0, y1, z1), (x1, y1, z1), color, fuv(dx, z0, z1), (0, 1, 0))
        if "x" in faces:
            self.quad((x0, y1, z0), (x0, y0, z0), (x0, y0, z1), (x0, y1, z1), color, fuv(dy, z0, z1), (-1, 0, 0))

    def quad4(self, a, b, c, d, colors, uvs=((0, 0), (1, 0), (1, 1), (0, 1))):
        """quad con un colore per vertice (sfumature morbide)"""
        n = _norm(_cross(_sub(b, a), _sub(d, a)))
        i = self.v(a, n, _col(colors[0]), uvs[0])
        self.v(b, n, _col(colors[1]), uvs[1])
        self.v(c, n, _col(colors[2]), uvs[2])
        self.v(d, n, _col(colors[3]), uvs[3])
        self.ids.extend((i, i + 1, i + 2, i, i + 2, i + 3))

    def hexa(self, c, color):
        """8 angoli: 0-3 base (antiorario visto dall'alto), 4-7 sopra nello stesso ordine."""
        b0, b1, b2, b3, t0, t1, t2, t3 = c
        self.quad(t0, t1, t2, t3, color)
        self.quad(b3, b2, b1, b0, color)
        self.quad(b0, b1, t1, t0, color)
        self.quad(b1, b2, t2, t1, color)
        self.quad(b2, b3, t3, t2, color)
        self.quad(b3, b0, t0, t3, color)

    def frustum(self, x0, y0, x1, y1, z0, z1, tx0, ty0, tx1, ty1, color):
        self.hexa([(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
                   (tx0, ty0, z1), (tx1, ty0, z1), (tx1, ty1, z1), (tx0, ty1, z1)], color)

    def cylinder(self, cx, cy, z0, z1, r, color, seg=12, cap=True, r_top=None, axis="z"):
        rt = r if r_top is None else r_top
        col = _col(color)
        base = len(self.vs)
        slope = (r - rt) / max(1e-6, (z1 - z0))

        def P(x, y, z):
            if axis == "z":
                return (cx + x, cy + y, z)
            if axis == "x":
                return (z, cx + x, cy + y)
            return (cx + x, z, cy + y)

        def Nn(x, y, z):
            if axis == "z":
                return (x, y, z)
            if axis == "x":
                return (z, x, y)
            return (x, z, y)
        for i in range(seg + 1):
            a = TAU * i / seg
            ca, sa = math.cos(a), math.sin(a)
            n = _norm(Nn(ca, sa, slope))
            self.v(P(ca * r, sa * r, z0), n, col, (i / seg, 0))
            self.v(P(ca * rt, sa * rt, z1), n, col, (i / seg, 1))
        for i in range(seg):
            a = base + i * 2
            self.ids.extend((a, a + 2, a + 3, a, a + 3, a + 1))
        if cap:
            for zz, rr, up in ((z1, rt, 1), (z0, r, -1)):
                if rr <= 0:
                    continue
                c0 = self.v(P(0, 0, zz), Nn(0, 0, up), col, (0.5, 0.5))
                for i in range(seg + 1):
                    a = TAU * i / seg
                    self.v(P(math.cos(a) * rr, math.sin(a) * rr, zz), Nn(0, 0, up), col,
                           (0.5 + math.cos(a) * 0.5, 0.5 + math.sin(a) * 0.5))
                for i in range(seg):
                    if (up > 0) == (axis != "y"):
                        self.ids.extend((c0, c0 + 1 + i, c0 + 2 + i))
                    else:
                        self.ids.extend((c0, c0 + 2 + i, c0 + 1 + i))

    def ellipsoid(self, cx, cy, cz, rx, ry, rz, color, seg=12, rings=8, jitter=0.0, seed=0, color_var=0.0):
        rng = random.Random(seed)
        base = len(self.vs)
        for j in range(rings + 1):
            phi = math.pi * j / rings
            sp, cp = math.sin(phi), math.cos(phi)
            for i in range(seg + 1):
                th = TAU * (i % seg) / seg
                ct, st = math.cos(th), math.sin(th)
                k = 1.0
                if jitter and 0 < j < rings:
                    k += rng.uniform(-jitter, jitter)
                nx, ny, nz = ct * sp, st * sp, cp
                p = (cx + nx * rx * k, cy + ny * ry * k, cz + nz * rz * k)
                n = _norm((nx / rx, ny / ry, nz / rz))
                if color_var:
                    f = 1 + rng.uniform(-color_var, color_var)
                    c = _col((clamp(color[0] * f, 0, 255), clamp(color[1] * f, 0, 255), clamp(color[2] * f, 0, 255)))
                else:
                    c = _col(color)
                self.v(p, n, c, (i / seg, j / rings))
        for j in range(rings):
            for i in range(seg):
                a = base + j * (seg + 1) + i
                b = a + seg + 1
                self.ids.extend((a, b, b + 1, a, b + 1, a + 1))

    def add_mesh(self, other, x=0.0, y=0.0, z=0.0, h=0.0, s=1.0):
        V, I = other.arrays()
        if len(V) == 0:
            return
        V = V.copy()
        if h:
            r = math.radians(h)
            c, sn = math.cos(r), math.sin(r)
            px, py = V[:, 0].copy(), V[:, 1].copy()
            V[:, 0] = px * c - py * sn
            V[:, 1] = px * sn + py * c
            nx, ny = V[:, 3].copy(), V[:, 4].copy()
            V[:, 3] = nx * c - ny * sn
            V[:, 4] = nx * sn + ny * c
        if s != 1.0:
            V[:, 0:3] *= s
        V[:, 0] += x
        V[:, 1] += y
        V[:, 2] += z
        self.chunks.append((V, I))

    def arrays(self):
        parts_v, parts_i = [], []
        off = 0
        if self.vs:
            parts_v.append(np.array(self.vs, np.float32))
            parts_i.append(np.array(self.ids, np.uint32))
            off = len(self.vs)
        for V, I in self.chunks:
            parts_v.append(V)
            parts_i.append(I + off)
            off += len(V)
        if not parts_v:
            return np.zeros((0, 12), np.float32), np.zeros(0, np.uint32)
        return np.concatenate(parts_v), np.concatenate(parts_i).astype(np.uint32)

    def node(self, name="mesh"):
        V, I = self.arrays()
        gn = GeomNode(name)
        if len(V) == 0:
            return gn
        vd = GeomVertexData(name, vertex_format(), Geom.UH_static)
        vd.uncleanSetNumRows(len(V))
        memoryview(vd.modifyArray(0)).cast("B")[:] = np.ascontiguousarray(V, np.float32).tobytes()
        pr = GeomTriangles(Geom.UH_static)
        pr.setIndexType(Geom.NT_uint32)
        ia = pr.modifyVertices()
        ia.uncleanSetNumRows(len(I))
        memoryview(ia).cast("B")[:] = np.ascontiguousarray(I, np.uint32).tobytes()
        g = Geom(vd)
        g.addPrimitive(pr)
        gn.addGeom(g)
        return gn

    def attach(self, parent, name="mesh", tex=None, emit=None, mat=None):
        np_ = parent.attachNewNode(self.node(name))
        if tex is not None:
            np_.setTexture(tex)
        if emit is not None:
            np_.setShaderInput("emit_tex", emit)
        if mat is not None:
            np_.setShaderInput("u_mat", Vec4(*mat))
        return np_


# =============================================================================
#  SHADER (luce realistica: sole + ombre morbide, cielo, riflessi, nebbia)
# =============================================================================
WORLD_VS_BODY = """uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat4 p3d_ModelViewMatrix;
uniform mat4 p3d_ModelMatrix;
uniform struct p3d_LightSourceParameters {
  vec4 color;
  sampler2DShadow shadowMap;
  mat4 shadowViewMatrix;
} p3d_LightSource[NLIGHT];
in vec4 p3d_Vertex;
in vec3 p3d_Normal;
in vec4 p3d_Color;
in vec2 p3d_MultiTexCoord0;
out vec3 v_pos;
out vec3 v_nrm;
out vec4 v_col;
out vec2 v_uv;
out vec4 v_shd;
#ifdef CASCADE
out vec4 v_shd2;
#endif
void main() {
  vec4 wp = p3d_ModelMatrix * p3d_Vertex;
  v_pos = wp.xyz;
  v_nrm = normalize(mat3(p3d_ModelMatrix) * p3d_Normal);
  v_col = p3d_Color;
  v_uv = p3d_MultiTexCoord0;
  vec4 vp = p3d_ModelViewMatrix * p3d_Vertex;
  vec3 vn = normalize(mat3(p3d_ModelViewMatrix) * p3d_Normal);
  v_shd = p3d_LightSource[0].shadowViewMatrix * vec4(vp.xyz + vn * 0.07, 1.0);
#ifdef CASCADE
  v_shd2 = p3d_LightSource[1].shadowViewMatrix * vec4(vp.xyz + vn * 0.6, 1.0);
#endif
  gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
}
"""


WORLD_FS_BODY = """
uniform struct p3d_LightSourceParameters {
  vec4 color;
  sampler2DShadow shadowMap;
  mat4 shadowViewMatrix;
} p3d_LightSource[NLIGHT];
uniform sampler2D p3d_Texture0;
uniform sampler2D emit_tex;
uniform vec4 p3d_ColorScale;
uniform vec3 u_sun_dir;
uniform vec3 u_sun_col;
uniform vec3 u_sky_col;
uniform vec3 u_gnd_col;
uniform vec3 u_fog_col;
uniform vec4 u_fog;
uniform vec3 u_cam;
uniform vec4 u_mat;
uniform float u_night;
uniform vec4 u_plight_pos[8];
uniform vec4 u_plight_col[8];
uniform vec4 u_spot_pos;
uniform vec4 u_spot_dir;
uniform vec3 u_tint;
uniform float u_texel;
#ifdef FACADE
uniform sampler2DArray u_fac_alb;
uniform sampler2DArray u_fac_nrm;
uniform vec4 u_fac_grid[32];
uniform vec4 u_fac_info[32];
#endif
in vec3 v_pos;
in vec3 v_nrm;
in vec4 v_col;
in vec2 v_uv;
in vec4 v_shd;
#ifdef CASCADE
in vec4 v_shd2;
uniform float u_texel2;
#endif
out vec4 o_color;

float shadow_term() {
  vec4 c = v_shd;
  float t = u_texel * c.w;
  float s = textureProj(p3d_LightSource[0].shadowMap, c) * 2.0;
  s += textureProj(p3d_LightSource[0].shadowMap, c + vec4(-t, -t, 0.0, 0.0));
  s += textureProj(p3d_LightSource[0].shadowMap, c + vec4( t, -t, 0.0, 0.0));
  s += textureProj(p3d_LightSource[0].shadowMap, c + vec4(-t,  t, 0.0, 0.0));
  s += textureProj(p3d_LightSource[0].shadowMap, c + vec4( t,  t, 0.0, 0.0));
  s += textureProj(p3d_LightSource[0].shadowMap, c + vec4( 0.0, 2.0 * t, 0.0, 0.0));
  s += textureProj(p3d_LightSource[0].shadowMap, c + vec4( 0.0, -2.0 * t, 0.0, 0.0));
  return s / 8.0;
}

#ifdef CASCADE
float shadow_far() {
  vec4 c = v_shd2;
  float t = u_texel2 * c.w;
  float s = textureProj(p3d_LightSource[1].shadowMap, c) * 2.0;
  s += textureProj(p3d_LightSource[1].shadowMap, c + vec4(-t, 0.0, 0.0, 0.0));
  s += textureProj(p3d_LightSource[1].shadowMap, c + vec4( t, 0.0, 0.0, 0.0));
  s += textureProj(p3d_LightSource[1].shadowMap, c + vec4(0.0, -t, 0.0, 0.0));
  s += textureProj(p3d_LightSource[1].shadowMap, c + vec4(0.0,  t, 0.0, 0.0));
  return s / 6.0;
}
#endif

vec3 aces(vec3 x) {
  return clamp((x * (2.51 * x + 0.03)) / (x * (2.43 * x + 0.59) + 0.14), 0.0, 1.0);
}

void main() {
  vec4 mat = u_mat;
#ifdef FACADE
  float layer = floor(v_col.a * 255.0 + 0.5);
  vec4 gi = u_fac_grid[int(layer)];
  vec4 tx = texture(u_fac_alb, vec3(v_uv, layer));
  vec4 base = vec4(tx.rgb * v_col.rgb * p3d_ColorScale.rgb, 1.0);
  float glass = tx.a * gi.w;
  vec4 nt = texture(u_fac_nrm, vec3(v_uv, layer));
  vec3 nm = nt.xyz * 2.0 - 1.0;
  float emask = nt.a;
  mat = mix(u_mat, vec4(1.1, 140.0, 1.0, 0.0), glass);
#else
  vec4 tx = texture(p3d_Texture0, v_uv);
  vec4 base = tx * v_col * p3d_ColorScale;
  if (base.a < 0.03) discard;
#endif
  vec3 alb = pow(base.rgb, vec3(2.2)) * u_tint;
  vec3 N = normalize(v_nrm);
  if (!gl_FrontFacing) N = -N;
#ifdef FACADE
  if (abs(N.z) < 0.7) {
    vec3 T = normalize(cross(vec3(0.0, 0.0, 1.0), N));
    N = normalize(T * nm.x + vec3(0.0, 0.0, 1.0) * nm.y + N * max(nm.z, 0.2));
  }
#endif
  vec3 toc = u_cam - v_pos;
  float dist = length(toc);
  vec3 V = toc / max(dist, 0.001);
  float ndl = dot(N, u_sun_dir);
  float sh = 0.0;
  if (ndl > 0.0) {
    vec3 sc = v_shd.xyz / v_shd.w;
    float edge = min(min(sc.x, 1.0 - sc.x), min(sc.y, 1.0 - sc.y));
    float sn = 1.0;
    if (edge > 0.0) sn = shadow_term();
#ifdef CASCADE
    float sf = 1.0;
    vec3 sc2 = v_shd2.xyz / v_shd2.w;
    if (sc2.x > 0.0 && sc2.x < 1.0 && sc2.y > 0.0 && sc2.y < 1.0 && edge < 0.08) sf = shadow_far();
    sh = mix(sf, sn, smoothstep(0.0, 0.08, edge));
#else
    sh = sn;
#endif
  }
  float diff = max(ndl, 0.0) * sh;
  vec3 H = normalize(u_sun_dir + V);
  float gloss = mat.y;
  float spec = pow(max(dot(N, H), 0.0), gloss) * mat.x * (gloss + 2.0) / 8.0;
  float hemi = N.z * 0.5 + 0.5;
  vec3 amb = mix(u_gnd_col, u_sky_col, hemi);
  float ao = mix(0.55, 1.0, clamp(v_pos.z * 0.45 + 0.1, 0.0, 1.0));
  if (N.z > 0.7) ao = 1.0;
  vec3 col = alb * (amb * ao + u_sun_col * diff) + u_sun_col * spec * sh;
  vec3 R = reflect(-V, N);
  float fres = mat.z * (0.06 + 0.94 * pow(1.0 - max(dot(N, V), 0.0), 5.0));
  vec3 env = mix(u_gnd_col * 0.7, u_sky_col * 1.6 + u_sun_col * 0.05, smoothstep(-0.15, 0.35, R.z));
  col = mix(col, env + u_sun_col * spec * sh, clamp(fres, 0.0, 1.0));
  for (int i = 0; i < 8; i++) {
    vec3 L = u_plight_pos[i].xyz - v_pos;
    float d = length(L);
    float r = u_plight_pos[i].w;
    if (d < r) {
      float a = 1.0 - d / r;
      a *= a;
      col += alb * u_plight_col[i].rgb * max(dot(N, L / d), 0.0) * a;
    }
  }
  if (u_spot_pos.w > 0.5) {
    vec3 L = u_spot_pos.xyz - v_pos;
    float d = length(L);
    vec3 l = L / max(d, 0.001);
    float cs = dot(-l, u_spot_dir.xyz);
    float cone = smoothstep(u_spot_dir.w, u_spot_dir.w + 0.1, cs);
    col += alb * vec3(1.0, 0.93, 0.8) * 6.0 * cone * max(dot(N, l), 0.0) / (1.0 + d * d * 0.02);
  }
#ifdef FACADE
  vec2 cell = floor(v_uv * gi.xy);
  float hsh = fract(sin(dot(cell + vec2(layer * 7.13, layer * 3.71), vec2(12.9898, 78.233))) * 43758.5453);
  float lit = step(1.0 - gi.z, hsh);
  vec3 lcol = mix(vec3(1.0, 0.70, 0.40), vec3(0.60, 0.76, 1.0), step(0.8, fract(hsh * 7.0)));
  float ltype = u_fac_info[int(layer)].x;
  if (ltype > 1.5) lcol = vec3(0.80, 0.92, 1.0);
  else if (ltype > 0.5) lcol = base.rgb * 2.4 + 0.1;
  vec3 em = emask * lit * lcol * (0.25 + 0.55 * fract(hsh * 13.0)) * u_night * 0.95;
  col = mix(col, col * 0.35, emask * u_night * (1.0 - lit));
#else
  vec3 em = pow(texture(emit_tex, v_uv).rgb, vec3(2.2)) * u_mat.w * (u_night * 0.85);
#endif
  col += em;
  float kz = u_fog.y * (v_pos.z - u_cam.z);
  float hf = abs(kz) > 0.001 ? (1.0 - exp(-kz)) / kz : 1.0;
  float od = u_fog.x * max(dist - u_fog.z, 0.0) * exp(-u_fog.y * max(u_cam.z, 0.0)) * hf;
  float fog = 1.0 - exp(-od);
  col = mix(col, u_fog_col, clamp(fog, 0.0, u_fog.w));
  col = aces(col);
  o_color = vec4(pow(col, vec3(1.0 / 2.2)), base.a);
}
"""


def world_shader_src(facade=False, cascade=False):
    head = "#version 130\n" + ("#define NLIGHT 2\n#define CASCADE 1\n" if cascade else "#define NLIGHT 1\n")
    vs = head + WORLD_VS_BODY
    fs = head + ("#define FACADE 1\n" if facade else "") + WORLD_FS_BODY
    return vs, fs

SKY_VS = """
#version 130
uniform mat4 p3d_ModelViewProjectionMatrix;
in vec4 p3d_Vertex;
out vec3 v_dir;
void main() {
  v_dir = p3d_Vertex.xyz;
  gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
}
"""

SKY_FS = """
#version 130
uniform vec3 u_sun_dir;
uniform vec3 u_sun_col;
uniform vec3 u_zenith;
uniform vec3 u_horizon;
uniform vec3 u_fog_col;
uniform float u_night;
uniform float u_time;
uniform float u_cloud;
uniform vec3 u_tint;
uniform sampler2D u_clouds;
in vec3 v_dir;
out vec4 o_color;
vec3 aces(vec3 x) {
  return clamp((x * (2.51 * x + 0.03)) / (x * (2.43 * x + 0.59) + 0.14), 0.0, 1.0);
}
float hash(vec3 p) {
  return fract(sin(dot(p, vec3(12.9898, 78.233, 45.164))) * 43758.5453);
}
void main() {
  vec3 d = normalize(v_dir);
  float h = d.z;
  vec3 col;
  if (h >= 0.0) col = mix(u_horizon, u_zenith, pow(clamp(h, 0.0, 1.0), 0.5));
  else col = mix(u_fog_col, u_fog_col * 0.6, clamp(-h * 3.0, 0.0, 1.0));
  float sd = max(dot(d, u_sun_dir), 0.0);
  float above = smoothstep(-0.05, 0.02, u_sun_dir.z);
  col += u_sun_col * (pow(sd, 900.0) * 40.0 * above + pow(sd, 10.0) * 0.25 + pow(sd, 3.0) * 0.08);
  if (h > 0.0 && u_night > 0.02) {
    vec3 cell = floor(d * 900.0);
    float st = hash(cell);
    if (st > 0.9993) col += vec3(0.8, 0.85, 1.0) * u_night * (st - 0.9993) * 2200.0 * smoothstep(0.0, 0.3, h);
    vec3 moon = normalize(vec3(-u_sun_dir.x, -u_sun_dir.y, abs(u_sun_dir.z) + 0.3));
    float md = max(dot(d, moon), 0.0);
    col += vec3(0.9, 0.95, 1.0) * (pow(md, 1500.0) * 6.0 + pow(md, 40.0) * 0.08) * u_night;
  }
  if (h > 0.0) {
    vec2 uv = d.xy / (h + 0.18) * 0.14 + vec2(u_time * 0.0035, u_time * 0.0012);
    float c = texture(u_clouds, uv).r;
    float c2 = texture(u_clouds, uv * 2.3 + 0.37).r;
    c = c * 0.7 + c2 * 0.3;
    float cov = mix(0.62, 0.42, u_cloud);
    c = smoothstep(cov, cov + 0.25, c) * smoothstep(0.0, 0.18, h);
    vec3 lit = u_sun_col * 0.55 * (0.6 + 0.4 * pow(sd, 4.0)) + u_zenith * 0.6 + u_horizon * 0.25;
    vec3 ccol = mix(lit, u_horizon * 0.7, 0.25);
    col = mix(col, ccol, c * 0.9);
  }
  col *= u_tint;
  col = aces(col);
  o_color = vec4(pow(col, vec3(1.0 / 2.2)), 1.0);
}
"""

FX_VS = """
#version 130
uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat4 p3d_ModelMatrix;
in vec4 p3d_Vertex;
in vec4 p3d_Color;
in vec2 p3d_MultiTexCoord0;
out vec4 v_col;
out vec2 v_uv;
out vec3 v_pos;
void main() {
  v_col = p3d_Color;
  v_uv = p3d_MultiTexCoord0;
  v_pos = (p3d_ModelMatrix * p3d_Vertex).xyz;
  gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
}
"""

FX_FS = """
#version 130
uniform sampler2D p3d_Texture0;
uniform vec4 p3d_ColorScale;
uniform vec3 u_cam;
uniform vec3 u_fog_col;
uniform vec4 u_fog;
in vec4 v_col;
in vec2 v_uv;
in vec3 v_pos;
out vec4 o_color;
void main() {
  vec4 c = texture(p3d_Texture0, v_uv) * v_col * p3d_ColorScale;
  float dist = length(u_cam - v_pos);
  float fog = clamp(1.0 - exp(-max(dist - u_fog.z, 0.0) * u_fog.x), 0.0, u_fog.w);
  c.rgb *= (1.0 - fog * 0.85);
  o_color = c;
}
"""

SIGN_FS = """
#version 130
uniform sampler2D p3d_Texture0;
uniform vec4 p3d_ColorScale;
uniform vec3 u_cam;
uniform vec3 u_fog_col;
uniform vec4 u_fog;
uniform float u_night;
uniform float u_glow;
in vec4 v_col;
in vec2 v_uv;
in vec3 v_pos;
out vec4 o_color;
void main() {
  vec4 t = texture(p3d_Texture0, v_uv);
  float a = t.a * v_col.a * p3d_ColorScale.a;
  if (a < 0.02) discard;
  vec3 c = v_col.rgb * p3d_ColorScale.rgb;
  c *= mix(mix(1.0, 0.12, u_night), 1.15, u_glow);
  float dist = length(u_cam - v_pos);
  float fog = clamp(1.0 - exp(-max(dist - u_fog.z, 0.0) * u_fog.x), 0.0, u_fog.w);
  c = mix(c, pow(u_fog_col, vec3(1.0 / 2.2)), fog);
  o_color = vec4(c, a);
}
"""



# =============================================================================
#  AMBIENTE: sole, ombre, cielo, ciclo giorno/notte
# =============================================================================
MASK_MAIN = BitMask32.bit(0)
MASK_SHADOW = BitMask32.bit(1)
MASK_MAP = BitMask32.bit(2)


class Environment:
    QUALITY = [  # (shadow map, film size)
        dict(shadow=1024, film=110, name="Bassa"),
        dict(shadow=2048, film=140, name="Media"),
        dict(shadow=4096, film=170, name="Alta"),
    ]

    def __init__(self, base, quality=1):
        self.base = base
        render = base.render
        self.q = self.QUALITY[clamp(quality, 0, 2)]
        base.cam.node().setCameraMask(MASK_MAIN)
        self.cascade = quality >= 1
        self.world_shader = Shader.make(Shader.SL_GLSL, *world_shader_src(False, self.cascade))
        self.sky_shader = Shader.make(Shader.SL_GLSL, SKY_VS, SKY_FS)
        self.fx_shader = Shader.make(Shader.SL_GLSL, FX_VS, FX_FS)
        self.sign_shader = Shader.make(Shader.SL_GLSL, FX_VS, SIGN_FS)
        self.facade_shader = Shader.make(Shader.SL_GLSL, *world_shader_src(True, self.cascade))
        self.root = render.attachNewNode("mondo")
        self.root.setShader(self.world_shader)
        self.white = solid_texture((255, 255, 255), "bianco")
        self.black = solid_texture((0, 0, 0), "nero")
        self.root.setTexture(self.white)
        self.root.setShaderInput("emit_tex", self.black)
        self.root.setShaderInput("u_mat", Vec4(0.25, 24.0, 0.0, 0.0))
        self.pl_pos = PTA_LVecBase4f.emptyArray(8)
        self.pl_col = PTA_LVecBase4f.emptyArray(8)
        render.setShaderInput("u_plight_pos", self.pl_pos)
        render.setShaderInput("u_plight_col", self.pl_col)
        render.setShaderInput("u_spot_pos", Vec4(0, 0, 0, 0))
        render.setShaderInput("u_spot_dir", Vec4(0, 1, 0, 0.9))
        render.setShaderInput("u_tint", Vec3(1, 1, 1))
        render.setShaderInput("u_texel", 1.0 / self.q["shadow"])
        render.setShaderInput("u_night", 0.0)
        render.setShaderInput("u_cam", Vec3(0, 0, 0))
        render.setShaderInput("u_fog", Vec4(0.0008, 0.003, 60.0, 0.9))
        render.setShaderInput("u_glow", 0.0)
        self.tint = Vec3(1, 1, 1)
        # sole con ombre
        self.sun = DirectionalLight("sole")
        self.sun.setShadowCaster(True, self.q["shadow"], self.q["shadow"])
        self.sun.setCameraMask(MASK_SHADOW)
        lens = self.sun.getLens()
        lens.setFilmSize(self.q["film"], self.q["film"])
        lens.setNearFar(10, 900)
        self.sun.setPriority(10)
        self.sun_np = render.attachNewNode(self.sun)
        self.root.setLight(self.sun_np)
        # seconda mappa d'ombra, larga 1.5 km: i grattacieli proiettano l'ombra sulla citta'
        if self.cascade:
            sz = 2048 if quality == 1 else 4096
            self.sun2 = DirectionalLight("sole_lontano")
            self.sun2.setShadowCaster(True, sz, sz)
            self.sun2.setCameraMask(MASK_SHADOW)
            self.sun2.setPriority(5)
            self.sun2.setColor((0, 0, 0, 1))
            lens2 = self.sun2.getLens()
            lens2.setFilmSize(1500, 1500)
            lens2.setNearFar(20, 3200)
            self.sun2_np = render.attachNewNode(self.sun2)
            self.root.setLight(self.sun2_np)
            render.setShaderInput("u_texel2", 1.0 / sz)
            self.step2 = 1500.0 / sz * 4
        # cielo
        sky = Mesh()
        sky.ellipsoid(0, 0, 0, 1, 1, 1, (255, 255, 255), seg=32, rings=16)
        self.sky = render.attachNewNode(sky.node("cielo"))
        self.sky.setScale(5000)
        self.sky.setShader(self.sky_shader)
        self.sky.setAttrib(CullFaceAttrib.makeReverse())
        self.sky.setBin("background", 0)
        self.sky.setDepthWrite(False)
        self.sky.setDepthTest(False)
        self.sky.setLightOff(1)
        self.sky.hide(MASK_SHADOW | MASK_MAP)
        self.sky.setShaderInput("u_clouds", make_texture(tex_clouds(), "nuvole"))
        self.sky.setShaderInput("u_cloud", 0.55)
        base.camLens.setNearFar(0.2, 9000)
        self.hour = 10.0
        self.night = 0.0
        self.light_dir = Vec3(0, 0, 1)
        self.sun_dir = Vec3(0, 0, 1)
        self.fog_col = Vec3(0.6, 0.7, 0.8)
        self.lights = []
        self.post = None
        if quality >= 1 and not OFFSCREEN_NO_POST:
            try:
                self.post = PostFX(base)
            except Exception:  # noqa: BLE001
                import traceback
                traceback.print_exc()
                self.post = None

    # ---------------------------------------------------------------------
    def set_fog(self, density, height, start, maximum):
        self.base.render.setShaderInput("u_fog", Vec4(density, height, start, maximum))

    def set_tint(self, rgb):
        self.tint = Vec3(*rgb)
        self.base.render.setShaderInput("u_tint", self.tint)

    def sky_colors(self, hour):
        t = (hour - 6.0) / 12.0
        elev = math.sin(t * math.pi)
        e_deg = math.degrees(math.asin(clamp(elev, -1, 1))) * 0.95
        az = math.radians(100 + t * 160)
        el = math.radians(e_deg * 0.68)
        sun = Vec3(math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el))
        s = sun.z
        day = smoothstep(-0.10, 0.22, s)
        warm = smoothstep(0.38, 0.02, abs(s)) * smoothstep(-0.16, 0.0, s)
        night = 1.0 - smoothstep(-0.16, 0.04, s)
        zen = lerp3((0.004, 0.006, 0.018), (0.16, 0.34, 0.78), day)
        zen = lerp3(zen, (0.18, 0.18, 0.40), warm * 0.6)
        hor = lerp3((0.02, 0.028, 0.06), (0.62, 0.74, 0.90), day)
        hor = lerp3(hor, (1.15, 0.55, 0.26), warm * 0.85)
        sun_col = lerp3((0.0, 0.0, 0.0), (2.25, 2.12, 1.92), day)
        sun_col = lerp3(sun_col, (2.1, 1.05, 0.45), warm)
        sky_amb = lerp3((0.03, 0.04, 0.075), (0.30, 0.37, 0.50), day)
        sky_amb = lerp3(sky_amb, (0.34, 0.30, 0.36), warm * 0.5)
        gnd_amb = lerp3((0.012, 0.014, 0.02), (0.15, 0.135, 0.11), day)
        return dict(sun=sun, day=day, warm=warm, night=night, zen=zen, hor=hor, sun_col=sun_col,
                    sky_amb=sky_amb, gnd_amb=gnd_amb)

    def update(self, dt, cam_pos, focus, game_time, lights=None, spot=None):
        r = self.base.render
        c = self.sky_colors(self.hour)
        self.night = c["night"]
        sun = c["sun"]
        self.sun_dir = sun
        if sun.z > -0.04:
            L = Vec3(sun.x, sun.y, max(sun.z, 0.05))
            L.normalize()
            lc = c["sun_col"]
        else:
            L = Vec3(-sun.x * 0.6, -sun.y * 0.6, 0.75)
            L.normalize()
            lc = (0.13, 0.17, 0.30)
        k = c["day"]
        if sun.z > -0.04 and k < 0.3:
            lc = lerp3((0.13, 0.17, 0.30), lc, smoothstep(0.0, 0.3, k))
        self.light_dir = L
        tint = self.tint
        fog = lerp3(c["hor"], c["zen"], 0.25)
        fog = (fog[0] * tint[0], fog[1] * tint[1], fog[2] * tint[2])
        self.fog_col = Vec3(*fog)
        r.setShaderInput("u_sun_dir", L)
        r.setShaderInput("u_sun_col", Vec3(*lc))
        r.setShaderInput("u_sky_col", Vec3(*c["sky_amb"]))
        r.setShaderInput("u_gnd_col", Vec3(*c["gnd_amb"]))
        r.setShaderInput("u_fog_col", self.fog_col)
        r.setShaderInput("u_night", self.night)
        r.setShaderInput("u_cam", Vec3(cam_pos))
        sk = self.sky
        sk.setPos(cam_pos)
        sk.setShaderInput("u_sun_dir", sun)
        sk.setShaderInput("u_sun_col", Vec3(*c["sun_col"]))
        sk.setShaderInput("u_zenith", Vec3(*c["zen"]))
        sk.setShaderInput("u_horizon", Vec3(*c["hor"]))
        sk.setShaderInput("u_fog_col", self.fog_col)
        sk.setShaderInput("u_night", self.night)
        sk.setShaderInput("u_time", game_time)
        # la camera delle ombre segue il giocatore (a passi di texel per evitare tremolii)
        step = self.q["film"] / self.q["shadow"] * 4
        fx = round(focus[0] / step) * step
        fy = round(focus[1] / step) * step
        self.sun_np.setPos(fx + L.x * 400, fy + L.y * 400, L.z * 400)
        self.sun_np.lookAt(fx, fy, 0)
        if self.cascade:
            s2 = self.step2
            gx = round(focus[0] / s2) * s2
            gy = round(focus[1] / s2) * s2
            self.sun2_np.setPos(gx + L.x * 1600, gy + L.y * 1600, L.z * 1600)
            self.sun2_np.lookAt(gx, gy, 0)
        if self.post is not None:
            self.post.update(self.night)
        # luci puntiformi (lampioni, esplosioni, sirene...)
        lights = lights or []
        for i in range(8):
            if i < len(lights):
                x, y, z, rad, cr, cg, cb = lights[i]
                self.pl_pos.setElement(i, LVecBase4f(x, y, z, rad))
                self.pl_col.setElement(i, LVecBase4f(cr, cg, cb, 1))
            else:
                self.pl_pos.setElement(i, LVecBase4f(0, 0, -1000, 0.001))
                self.pl_col.setElement(i, LVecBase4f(0, 0, 0, 1))
        if spot:
            (px, py, pz), (dx, dy, dz) = spot
            r.setShaderInput("u_spot_pos", Vec4(px, py, pz, 1))
            r.setShaderInput("u_spot_dir", Vec4(dx, dy, dz, 0.86))
        else:
            r.setShaderInput("u_spot_pos", Vec4(0, 0, 0, 0))


# =============================================================================
#  POST-PRODUZIONE: occlusione ambientale (SSAO), bagliore (bloom), antialiasing (FXAA)
# =============================================================================
OFFSCREEN_NO_POST = os.environ.get("RM3D_NOPOST") == "1"

POST_VS = """
#version 130
uniform mat4 p3d_ModelViewProjectionMatrix;
in vec4 p3d_Vertex;
in vec2 p3d_MultiTexCoord0;
out vec2 v_uv;
void main() {
  gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
  v_uv = p3d_MultiTexCoord0;
}
"""

AO_FS = """
#version 130
uniform sampler2D u_depth;
uniform vec4 u_ao;
uniform vec2 u_px;
in vec2 v_uv;
out vec4 o_color;
float lin(float d) { return u_ao.x * u_ao.y / (u_ao.y - d * (u_ao.y - u_ao.x)); }
void main() {
  float z0 = lin(texture(u_depth, v_uv).r);
  if (z0 > 300.0) { o_color = vec4(1.0); return; }
  float w0 = 1.0 / z0;
  float wl = 1.0 / lin(texture(u_depth, v_uv - vec2(u_px.x, 0.0)).r);
  float wr = 1.0 / lin(texture(u_depth, v_uv + vec2(u_px.x, 0.0)).r);
  float wd = 1.0 / lin(texture(u_depth, v_uv - vec2(0.0, u_px.y)).r);
  float wu = 1.0 / lin(texture(u_depth, v_uv + vec2(0.0, u_px.y)).r);
  float gx = abs(wr - w0) < abs(w0 - wl) ? (wr - w0) : (w0 - wl);
  float gy = abs(wu - w0) < abs(w0 - wd) ? (wu - w0) : (w0 - wd);
  float rad = clamp(0.75 / z0, 0.003, 0.07);
  float ang = fract(sin(dot(gl_FragCoord.xy, vec2(12.9898, 78.233))) * 43758.5453) * 6.2831853;
  float ca = cos(ang);
  float sa = sin(ang);
  float occ = 0.0;
  for (int i = 0; i < 12; i++) {
    float fi = float(i);
    float r = (fi + 0.5) / 12.0;
    float a = fi * 2.39996;
    vec2 k = vec2(cos(a), sin(a)) * r;
    k = vec2(k.x * ca - k.y * sa, k.x * sa + k.y * ca);
    vec2 off = k * rad * vec2(1.0 / u_ao.z, 1.0);
    vec2 opx = off / u_px;
    float ws = 1.0 / lin(texture(u_depth, v_uv + off).r);
    float we = max(w0 + gx * opx.x + gy * opx.y, 1e-5);
    float dz = 1.0 / we - 1.0 / ws;
    occ += smoothstep(0.03, 0.22, dz) * (1.0 - smoothstep(1.0, 2.6, dz));
  }
  float ao = 1.0 - u_ao.w * occ / 12.0;
  o_color = vec4(ao, ao, ao, 1.0);
}
"""

BRIGHT_FS = """
#version 130
uniform sampler2D u_scene;
uniform vec4 u_bloom;
uniform vec2 u_px;
in vec2 v_uv;
out vec4 o_color;
void main() {
  vec3 c = texture(u_scene, v_uv + vec2(-u_px.x, -u_px.y)).rgb;
  c += texture(u_scene, v_uv + vec2(u_px.x, -u_px.y)).rgb;
  c += texture(u_scene, v_uv + vec2(-u_px.x, u_px.y)).rgb;
  c += texture(u_scene, v_uv + vec2(u_px.x, u_px.y)).rgb;
  c *= 0.25;
  float l = dot(c, vec3(0.2126, 0.7152, 0.0722));
  float k = smoothstep(u_bloom.x, u_bloom.x + 0.22, l);
  o_color = vec4(c * k, 1.0);
}
"""

BLUR_FS = """
#version 130
uniform sampler2D u_src;
uniform vec2 u_dir;
in vec2 v_uv;
out vec4 o_color;
void main() {
  vec3 c = texture(u_src, v_uv).rgb * 0.227;
  c += (texture(u_src, v_uv + u_dir * 1.385).rgb + texture(u_src, v_uv - u_dir * 1.385).rgb) * 0.316;
  c += (texture(u_src, v_uv + u_dir * 3.231).rgb + texture(u_src, v_uv - u_dir * 3.231).rgb) * 0.070;
  o_color = vec4(c, 1.0);
}
"""

COMP_FS = """
#version 130
uniform sampler2D u_scene;
uniform sampler2D u_aotex;
uniform sampler2D u_bloomtex;
uniform vec4 u_bloom;
uniform vec2 u_aopx;
in vec2 v_uv;
out vec4 o_color;
void main() {
  vec3 c = texture(u_scene, v_uv).rgb;
  float ao = texture(u_aotex, v_uv + vec2(u_aopx.x, u_aopx.y)).r + texture(u_aotex, v_uv + vec2(-u_aopx.x, u_aopx.y)).r
           + texture(u_aotex, v_uv + vec2(u_aopx.x, -u_aopx.y)).r + texture(u_aotex, v_uv + vec2(-u_aopx.x, -u_aopx.y)).r;
  ao *= 0.25;
  c *= pow(clamp(ao, 0.0, 1.0), 0.4545);
  vec3 b = texture(u_bloomtex, v_uv).rgb * u_bloom.y;
  c = 1.0 - (1.0 - c) * (1.0 - min(b, vec3(1.0)));
  vec2 q = v_uv - 0.5;
  c *= 1.0 - dot(q, q) * 0.32;
  o_color = vec4(c, 1.0);
}
"""

FXAA_FS = """
#version 130
uniform sampler2D u_comp;
uniform vec2 u_rcp;
in vec2 v_uv;
out vec4 o_color;
void main() {
  vec3 L = vec3(0.299, 0.587, 0.114);
  vec3 nw = texture(u_comp, v_uv + vec2(-1.0, -1.0) * u_rcp).rgb;
  vec3 ne = texture(u_comp, v_uv + vec2(1.0, -1.0) * u_rcp).rgb;
  vec3 sw = texture(u_comp, v_uv + vec2(-1.0, 1.0) * u_rcp).rgb;
  vec3 se = texture(u_comp, v_uv + vec2(1.0, 1.0) * u_rcp).rgb;
  vec3 m = texture(u_comp, v_uv).rgb;
  float lnw = dot(nw, L), lne = dot(ne, L), lsw = dot(sw, L), lse = dot(se, L), lm = dot(m, L);
  float lmin = min(lm, min(min(lnw, lne), min(lsw, lse)));
  float lmax = max(lm, max(max(lnw, lne), max(lsw, lse)));
  vec2 dir = vec2(-((lnw + lne) - (lsw + lse)), (lnw + lsw) - (lne + lse));
  float red = max((lnw + lne + lsw + lse) * 0.03125, 1.0 / 128.0);
  float rmin = 1.0 / (min(abs(dir.x), abs(dir.y)) + red);
  dir = clamp(dir * rmin, vec2(-8.0), vec2(8.0)) * u_rcp;
  vec3 a = 0.5 * (texture(u_comp, v_uv + dir * (1.0 / 3.0 - 0.5)).rgb + texture(u_comp, v_uv + dir * (2.0 / 3.0 - 0.5)).rgb);
  vec3 b = a * 0.5 + 0.25 * (texture(u_comp, v_uv - dir * 0.5).rgb + texture(u_comp, v_uv + dir * 0.5).rgb);
  float lb = dot(b, L);
  o_color = vec4((lb < lmin || lb > lmax) ? a : b, 1.0);
}
"""


class PostFX:
    def __init__(self, base):
        from direct.filter.FilterManager import FilterManager
        self.base = base
        self.fm = FilterManager(base.win, base.cam)
        self.t_scene = Texture("scena")
        self.t_depth = Texture("profondita")
        fb = FrameBufferProperties()
        fb.setRgbColor(True)
        fb.setRgbaBits(8, 8, 8, 8)
        fb.setDepthBits(24)
        self.final = self.fm.renderSceneInto(colortex=self.t_scene, depthtex=self.t_depth, fbprops=fb)
        if self.final is None:
            raise RuntimeError("post-produzione non disponibile")
        self.t_ao = Texture("ao")
        self.q_ao = self.fm.renderQuadInto(colortex=self.t_ao, div=2)
        self.t_br = Texture("luce")
        self.q_br = self.fm.renderQuadInto(colortex=self.t_br, div=4)
        self.t_bh = Texture("sfoca_h")
        self.q_bh = self.fm.renderQuadInto(colortex=self.t_bh, div=4)
        self.t_bv = Texture("sfoca_v")
        self.q_bv = self.fm.renderQuadInto(colortex=self.t_bv, div=4)
        self.t_comp = Texture("composizione")
        self.q_comp = self.fm.renderQuadInto(colortex=self.t_comp)
        for t in (self.t_scene, self.t_ao, self.t_br, self.t_bh, self.t_bv, self.t_comp):
            t.setMinfilter(SamplerState.FT_linear)
            t.setMagfilter(SamplerState.FT_linear)
            t.setWrapU(SamplerState.WM_clamp)
            t.setWrapV(SamplerState.WM_clamp)
        mk = lambda fs: Shader.make(Shader.SL_GLSL, POST_VS, fs)
        self.q_ao.setShader(mk(AO_FS))
        self.q_ao.setShaderInput("u_depth", self.t_depth)
        self.q_br.setShader(mk(BRIGHT_FS))
        self.q_br.setShaderInput("u_scene", self.t_scene)
        blur = mk(BLUR_FS)
        self.q_bh.setShader(blur)
        self.q_bh.setShaderInput("u_src", self.t_br)
        self.q_bv.setShader(blur)
        self.q_bv.setShaderInput("u_src", self.t_bh)
        self.q_comp.setShader(mk(COMP_FS))
        self.q_comp.setShaderInput("u_scene", self.t_scene)
        self.q_comp.setShaderInput("u_aotex", self.t_ao)
        self.q_comp.setShaderInput("u_bloomtex", self.t_bv)
        self.final.setShader(mk(FXAA_FS))
        self.final.setShaderInput("u_comp", self.t_comp)
        self.update(0.0)

    def update(self, night):
        win = self.base.win
        w, h = max(1, win.getXSize()), max(1, win.getYSize())
        lens = self.base.camLens
        self.q_ao.setShaderInput("u_ao", Vec4(lens.getNear(), lens.getFar(), w / float(h), 0.85))
        self.q_ao.setShaderInput("u_px", (1.0 / w, 1.0 / h))
        bloom = Vec4(lerp(0.78, 0.55, night), lerp(0.42, 0.9, night), 0, 0)
        self.q_br.setShaderInput("u_bloom", bloom)
        self.q_br.setShaderInput("u_px", (1.0 / w, 1.0 / h))
        self.q_bh.setShaderInput("u_dir", (4.0 / w, 0.0))
        self.q_bv.setShaderInput("u_dir", (0.0, 4.0 / h))
        self.q_comp.setShaderInput("u_bloom", bloom)
        self.q_comp.setShaderInput("u_aopx", (1.0 / w, 1.0 / h))
        self.final.setShaderInput("u_rcp", (1.0 / w, 1.0 / h))


# =============================================================================
#  GEOMETRIA 2D: triangolazione di poligoni con buchi, linee spezzate, raster
# =============================================================================
class _ENode:
    __slots__ = ("i", "x", "y", "prev", "next", "steiner")

    def __init__(self, i, x, y):
        self.i = i
        self.x = x
        self.y = y
        self.prev = None
        self.next = None
        self.steiner = False


def _e_insert(i, x, y, last):
    p = _ENode(i, x, y)
    if last is None:
        p.prev = p
        p.next = p
    else:
        p.next = last.next
        p.prev = last
        last.next.prev = p
        last.next = p
    return p


def _e_remove(p):
    p.next.prev = p.prev
    p.prev.next = p.next


def _e_area(p, q, r):
    return (q.y - p.y) * (r.x - q.x) - (q.x - p.x) * (r.y - q.y)


def _e_equals(a, b):
    return a.x == b.x and a.y == b.y


def _e_signed_area(pts, start, end):
    s = 0.0
    j = end - 1
    for i in range(start, end):
        s += (pts[j][0] - pts[i][0]) * (pts[i][1] + pts[j][1])
        j = i
    return s


def _e_linked(pts, start, end, clockwise):
    last = None
    if clockwise == (_e_signed_area(pts, start, end) > 0):
        for i in range(start, end):
            last = _e_insert(i, pts[i][0], pts[i][1], last)
    else:
        for i in range(end - 1, start - 1, -1):
            last = _e_insert(i, pts[i][0], pts[i][1], last)
    if last is not None and _e_equals(last, last.next):
        _e_remove(last)
        last = last.next
    return last


def _e_filter(start, end=None):
    if start is None:
        return start
    if end is None:
        end = start
    p = start
    while True:
        again = False
        if not p.steiner and (_e_equals(p, p.next) or _e_area(p.prev, p, p.next) == 0):
            _e_remove(p)
            p = end = p.prev
            if p is p.next:
                break
            again = True
        else:
            p = p.next
        if not (again or p is not end):
            break
    return end


def _e_in_tri(ax, ay, bx, by, cx, cy, px, py):
    return ((cx - px) * (ay - py) >= (ax - px) * (cy - py) and
            (ax - px) * (by - py) >= (bx - px) * (ay - py) and
            (bx - px) * (cy - py) >= (cx - px) * (by - py))


def _e_is_ear(ear):
    a, b, c = ear.prev, ear, ear.next
    if _e_area(a, b, c) >= 0:
        return False
    p = ear.next.next
    while p is not ear.prev:
        if (_e_in_tri(a.x, a.y, b.x, b.y, c.x, c.y, p.x, p.y) and _e_area(p.prev, p, p.next) >= 0):
            return False
        p = p.next
    return True


def _e_sign(v):
    return (v > 0) - (v < 0)


def _e_on_seg(p, q, r):
    return min(p.x, r.x) <= q.x <= max(p.x, r.x) and min(p.y, r.y) <= q.y <= max(p.y, r.y)


def _e_intersects(p1, q1, p2, q2):
    o1 = _e_sign(_e_area(p1, q1, p2))
    o2 = _e_sign(_e_area(p1, q1, q2))
    o3 = _e_sign(_e_area(p2, q2, p1))
    o4 = _e_sign(_e_area(p2, q2, q1))
    if o1 != o2 and o3 != o4:
        return True
    if o1 == 0 and _e_on_seg(p1, p2, q1):
        return True
    if o2 == 0 and _e_on_seg(p1, q2, q1):
        return True
    if o3 == 0 and _e_on_seg(p2, p1, q2):
        return True
    if o4 == 0 and _e_on_seg(p2, q1, q2):
        return True
    return False


def _e_locally_inside(a, b):
    if _e_area(a.prev, a, a.next) < 0:
        return _e_area(a, b, a.next) >= 0 and _e_area(a, a.prev, b) >= 0
    return _e_area(a, b, a.prev) < 0 or _e_area(a, a.next, b) < 0


def _e_middle_inside(a, b):
    p = a
    inside = False
    px, py = (a.x + b.x) / 2, (a.y + b.y) / 2
    while True:
        if (((p.y > py) != (p.next.y > py)) and p.next.y != p.y and
                (px < (p.next.x - p.x) * (py - p.y) / (p.next.y - p.y) + p.x)):
            inside = not inside
        p = p.next
        if p is a:
            break
    return inside


def _e_intersects_poly(a, b):
    p = a
    while True:
        if (p.i != a.i and p.next.i != a.i and p.i != b.i and p.next.i != b.i and _e_intersects(p, p.next, a, b)):
            return True
        p = p.next
        if p is a:
            break
    return False


def _e_valid_diag(a, b):
    return (a.next.i != b.i and a.prev.i != b.i and not _e_intersects_poly(a, b) and
            (_e_locally_inside(a, b) and _e_locally_inside(b, a) and _e_middle_inside(a, b) and
             (_e_area(a.prev, a, b.prev) or _e_area(a, b.prev, b)) or
             _e_equals(a, b) and _e_area(a.prev, a, a.next) > 0 and _e_area(b.prev, b, b.next) > 0))


def _e_split(a, b):
    a2 = _ENode(a.i, a.x, a.y)
    b2 = _ENode(b.i, b.x, b.y)
    an, bp = a.next, b.prev
    a.next = b
    b.prev = a
    a2.next = an
    an.prev = a2
    b2.next = a2
    a2.prev = b2
    bp.next = b2
    b2.prev = bp
    return b2


def _e_cure(start, tris):
    p = start
    while True:
        a, b = p.prev, p.next.next
        if (not _e_equals(a, b) and _e_intersects(a, p, p.next, b) and _e_locally_inside(a, b) and
                _e_locally_inside(b, a)):
            tris.extend((a.i, p.i, b.i))
            _e_remove(p)
            _e_remove(p.next)
            p = start = b
        p = p.next
        if p is start:
            break
    return _e_filter(p)


def _e_split_earcut(start, tris):
    a = start
    while True:
        b = a.next.next
        while b is not a.prev:
            if a.i != b.i and _e_valid_diag(a, b):
                c = _e_split(a, b)
                a = _e_filter(a, a.next)
                c = _e_filter(c, c.next)
                _e_earcut_linked(a, tris, 0)
                _e_earcut_linked(c, tris, 0)
                return
            b = b.next
        a = a.next
        if a is start:
            break


def _e_earcut_linked(ear, tris, pas):
    if ear is None:
        return
    stop = ear
    guard = 0
    while ear.prev is not ear.next:
        guard += 1
        if guard > 200000:
            return
        prev, nxt = ear.prev, ear.next
        if _e_is_ear(ear):
            tris.extend((prev.i, ear.i, nxt.i))
            _e_remove(ear)
            ear = nxt.next
            stop = nxt.next
            continue
        ear = nxt
        if ear is stop:
            if pas == 0:
                _e_earcut_linked(_e_filter(ear), tris, 1)
            elif pas == 1:
                ear = _e_cure(_e_filter(ear), tris)
                _e_earcut_linked(ear, tris, 2)
            elif pas == 2:
                _e_split_earcut(ear, tris)
            break


def _e_leftmost(start):
    p = start
    left = start
    while True:
        if p.x < left.x or (p.x == left.x and p.y < left.y):
            left = p
        p = p.next
        if p is start:
            break
    return left


def _e_sector_contains(m, p):
    return _e_area(m.prev, m, p.prev) < 0 and _e_area(p.next, m, m.next) < 0


def _e_bridge(hole, outer):
    p = outer
    hx, hy = hole.x, hole.y
    qx = -math.inf
    m = None
    while True:
        if hy <= p.y and hy >= p.next.y and p.next.y != p.y:
            x = p.x + (hy - p.y) * (p.next.x - p.x) / (p.next.y - p.y)
            if hx >= x > qx:
                qx = x
                m = p if p.x < p.next.x else p.next
                if x == hx:
                    return m
        p = p.next
        if p is outer:
            break
    if m is None:
        return None
    stop = m
    mx, my = m.x, m.y
    tan_min = math.inf
    p = m
    while True:
        if (hx >= p.x >= mx and hx != p.x and
                _e_in_tri(hx if hy < my else qx, hy, mx, my, qx if hy < my else hx, hy, p.x, p.y)):
            tan = abs(hy - p.y) / (hx - p.x)
            if _e_locally_inside(p, hole) and (tan < tan_min or (tan == tan_min and (
                    p.x > m.x or (p.x == m.x and _e_sector_contains(m, p))))):
                m = p
                tan_min = tan
        p = p.next
        if p is stop:
            break
    return m


def earcut(outer, holes=()):
    """Triangola un poligono (lista di (x, y)) con eventuali buchi. Ritorna indici nella lista
    concatenata outer + holes[0] + holes[1] + ..."""
    pts = list(outer)
    hole_idx = []
    for h in holes:
        if len(h) >= 3:
            hole_idx.append(len(pts))
            pts.extend(h)
    tris = []
    end0 = hole_idx[0] if hole_idx else len(pts)
    node = _e_linked(pts, 0, end0, True)
    if node is None or node.next is node.prev:
        return tris
    if hole_idx:
        queue = []
        for k, s in enumerate(hole_idx):
            e = hole_idx[k + 1] if k + 1 < len(hole_idx) else len(pts)
            lst = _e_linked(pts, s, e, False)
            if lst is None:
                continue
            if lst is lst.next:
                lst.steiner = True
            queue.append(_e_leftmost(lst))
        queue.sort(key=lambda n: (n.x, n.y))
        for h in queue:
            b = _e_bridge(h, node)
            if b is None:
                continue
            c = _e_split(b, h)
            _e_filter(c, c.next)
            node = _e_filter(b, b.next)
    _e_earcut_linked(node, tris, 0)
    return tris


def ring_area(pts):
    """area con segno (positiva = antioraria)"""
    a = 0.0
    n = len(pts)
    for i in range(n):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % n]
        a += x0 * y1 - x1 * y0
    return a * 0.5


def is_convex(pts):
    n = len(pts)
    if n < 4:
        return True
    sgn = 0
    for i in range(n):
        ax, ay = pts[i]
        bx, by = pts[(i + 1) % n]
        cx, cy = pts[(i + 2) % n]
        cr = (bx - ax) * (cy - by) - (by - ay) * (cx - bx)
        if abs(cr) < 1e-9:
            continue
        s = 1 if cr > 0 else -1
        if sgn == 0:
            sgn = s
        elif s != sgn:
            return False
    return True


def triangulate(outer, holes=()):
    if not holes and is_convex(outer):
        return [k for i in range(1, len(outer) - 1) for k in (0, i, i + 1)]
    return earcut(outer, holes)


def point_in_ring(x, y, pts):
    inside = False
    n = len(pts)
    j = n - 1
    for i in range(n):
        xi, yi = pts[i]
        xj, yj = pts[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-12) + xi:
            inside = not inside
        j = i
    return inside


def clean_ring(pts, eps=0.05):
    """toglie l'ultimo punto se uguale al primo e i punti doppi"""
    out = []
    for p in pts:
        if not out or abs(p[0] - out[-1][0]) > eps or abs(p[1] - out[-1][1]) > eps:
            out.append(p)
    if len(out) > 1 and abs(out[0][0] - out[-1][0]) <= eps and abs(out[0][1] - out[-1][1]) <= eps:
        out.pop()
    return out


# ------------------------------------------------------------------ linee spezzate
class Polyline:
    """linea spezzata con lunghezze cumulative: punto e direzione a una certa distanza"""
    __slots__ = ("P", "S", "L")

    def __init__(self, pts):
        self.P = np.asarray(pts, np.float64).reshape(-1, 2)
        d = np.hypot(np.diff(self.P[:, 0]), np.diff(self.P[:, 1]))
        self.S = np.concatenate([[0.0], np.cumsum(d)])
        self.L = float(self.S[-1])

    def at(self, s):
        P, S = self.P, self.S
        if s <= 0:
            i = 0
        elif s >= self.L:
            i = len(S) - 2
        else:
            i = int(np.searchsorted(S, s, "right")) - 1
            i = min(max(i, 0), len(S) - 2)
        seg = S[i + 1] - S[i]
        t = (s - S[i]) / seg if seg > 1e-9 else 0.0
        x0, y0 = P[i]
        x1, y1 = P[i + 1]
        dx, dy = x1 - x0, y1 - y0
        l = math.hypot(dx, dy) or 1.0
        return x0 + dx * t, y0 + dy * t, dx / l, dy / l

    def at_many(self, ss):
        """come at() ma per un array di distanze: ritorna X, Y, TX, TY"""
        P, S = self.P, self.S
        ss = np.clip(np.asarray(ss, np.float64), 0.0, self.L)
        i = np.clip(np.searchsorted(S, ss, "right") - 1, 0, len(S) - 2)
        seg = S[i + 1] - S[i]
        t = np.where(seg > 1e-9, (ss - S[i]) / np.where(seg > 1e-9, seg, 1.0), 0.0)
        A = P[i]
        D = P[i + 1] - A
        l = np.hypot(D[:, 0], D[:, 1])
        l = np.where(l > 1e-12, l, 1.0)
        return A[:, 0] + D[:, 0] * t, A[:, 1] + D[:, 1] * t, D[:, 0] / l, D[:, 1] / l

    def piece(self, s0, s1):
        """punti tra s0 e s1 (inclusi gli estremi interpolati)"""
        s0 = max(0.0, s0)
        s1 = min(self.L, s1)
        if s1 <= s0:
            return np.zeros((0, 2))
        a = self.at(s0)
        b = self.at(s1)
        inner = self.P[(self.S > s0 + 1e-6) & (self.S < s1 - 1e-6)]
        return np.vstack([[a[:2]], inner, [b[:2]]])

    def project(self, x, y):
        """distanza lungo la linea del punto piu' vicino a (x, y), e distanza laterale"""
        P = self.P
        a = P[:-1]
        d = P[1:] - a
        l2 = (d * d).sum(1)
        l2[l2 < 1e-12] = 1e-12
        t = np.clip(((x - a[:, 0]) * d[:, 0] + (y - a[:, 1]) * d[:, 1]) / l2, 0, 1)
        cx = a[:, 0] + d[:, 0] * t
        cy = a[:, 1] + d[:, 1] * t
        dd = (cx - x) ** 2 + (cy - y) ** 2
        i = int(np.argmin(dd))
        return float(self.S[i] + t[i] * math.sqrt(l2[i])), math.sqrt(dd[i])


def offset_line(P, off):
    """sposta una linea spezzata lateralmente (off > 0 = a destra) con giunti a mitra limitati"""
    P = np.asarray(P, np.float64)
    n = len(P)
    if n < 2:
        return P.copy()
    d = np.diff(P, axis=0)
    l = np.hypot(d[:, 0], d[:, 1])
    l[l < 1e-9] = 1e-9
    d /= l[:, None]
    nr = np.stack([d[:, 1], -d[:, 0]], 1)        # normale destra di ogni segmento
    N = np.zeros((n, 2))
    N[0] = nr[0]
    N[-1] = nr[-1]
    if n > 2:
        m = nr[:-1] + nr[1:]
        ml = np.hypot(m[:, 0], m[:, 1])
        ml[ml < 1e-9] = 1e-9
        m /= ml[:, None]
        cosh = (m * nr[1:]).sum(1)
        k = 1.0 / np.maximum(cosh, 0.35)
        N[1:-1] = m * k[:, None]
    return P + N * off


def ribbon(m, P, w_left, w_right, z, color, uv_scale=None, along_uv=None, nrm=(0, 0, 1)):
    """striscia orizzontale lungo P tra -w_left (sinistra) e +w_right (destra); uv nel mondo (x/uv, y/uv)
    oppure lungo la linea (along_uv=(scala_u, scala_v))"""
    L = offset_line(P, -w_left)
    R = offset_line(P, w_right)
    n = len(P)
    if n < 2:
        return
    col = _col(color)
    V = np.zeros((2 * n, 12), np.float32)
    V[0::2, 0:2] = L
    V[1::2, 0:2] = R
    V[:, 2] = z
    V[:, 3:6] = nrm
    V[:, 6:10] = col
    if along_uv is not None:
        su, sv = along_uv
        S = np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(np.asarray(P, np.float64), axis=0).T))])
        V[0::2, 10] = 0.0
        V[1::2, 10] = (w_left + w_right) / su
        V[0::2, 11] = S / sv
        V[1::2, 11] = S / sv
    else:
        k = uv_scale or 8.0
        V[:, 10] = V[:, 0] / k
        V[:, 11] = V[:, 1] / k
    i = np.arange(n - 1, dtype=np.uint32) * 2
    I = np.stack([i, i + 1, i + 3, i, i + 3, i + 2], 1).reshape(-1)
    m.chunks.append((V, I))


def wall_strip(m, P, z0, z1, color, outward_right=True, uv=None, v_base=0.0):
    """muro verticale lungo P (normale verso destra se outward_right)"""
    P = np.asarray(P, np.float64)
    n = len(P)
    if n < 2:
        return
    col = _col(color)
    a, b = P[:-1], P[1:]
    if not outward_right:
        a, b = b[::-1], a[::-1]
    d = b - a
    l = np.hypot(d[:, 0], d[:, 1])
    ok = l > 1e-4
    a, b, d, l = a[ok], b[ok], d[ok], l[ok]
    k = len(a)
    if k == 0:
        return
    nx, ny = d[:, 1] / l, -d[:, 0] / l
    V = np.zeros((4 * k, 12), np.float32)
    V[0::4, 0:2] = a
    V[1::4, 0:2] = b
    V[2::4, 0:2] = b
    V[3::4, 0:2] = a
    V[0::4, 2] = z0
    V[1::4, 2] = z0
    V[2::4, 2] = z1
    V[3::4, 2] = z1
    for j in range(4):
        V[j::4, 3] = nx
        V[j::4, 4] = ny
    V[:, 6:10] = col
    if uv is not None:
        su, sv = uv
        s = np.concatenate([[0.0], np.cumsum(l)])[:-1]
        V[0::4, 10] = s / su
        V[3::4, 10] = s / su
        V[1::4, 10] = (s + l) / su
        V[2::4, 10] = (s + l) / su
        V[0::4, 11] = (z0 - v_base) / sv
        V[1::4, 11] = (z0 - v_base) / sv
        V[2::4, 11] = (z1 - v_base) / sv
        V[3::4, 11] = (z1 - v_base) / sv
    else:
        V[1::4, 10] = 1
        V[2::4, 10] = 1
        V[2::4, 11] = 1
        V[3::4, 11] = 1
    i = np.arange(k, dtype=np.uint32) * 4
    I = np.stack([i, i + 1, i + 2, i, i + 2, i + 3], 1).reshape(-1)
    m.chunks.append((V, I))


def flat_poly(m, outer, holes, z, color, uv_scale=8.0, up=True):
    """poligono orizzontale triangolato (tetti, parchi, piazze)"""
    tri = triangulate(outer, holes)
    if not tri:
        return
    pts = list(outer)
    for h in holes:
        if len(h) >= 3:
            pts.extend(h)
    A = np.asarray(pts, np.float64)
    V = np.zeros((len(A), 12), np.float32)
    V[:, 0:2] = A
    V[:, 2] = z
    V[:, 5] = 1.0 if up else -1.0
    V[:, 6:10] = _col(color)
    V[:, 10] = A[:, 0] / uv_scale
    V[:, 11] = A[:, 1] / uv_scale
    I = np.asarray(tri, np.uint32)
    if not up:
        I = I.reshape(-1, 3)[:, ::-1].reshape(-1)
    else:
        # earcut produce triangoli orari: li giriamo verso l'alto
        T = I.reshape(-1, 3)
        a, b, c = A[T[:, 0]], A[T[:, 1]], A[T[:, 2]]
        cr = (b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) - (b[:, 1] - a[:, 1]) * (c[:, 0] - a[:, 0])
        flip = cr < 0
        T[flip] = T[flip][:, ::-1]
        I = T.reshape(-1)
    m.chunks.append((V, I.astype(np.uint32)))


# ------------------------------------------------------------------ raster
class Raster:
    """griglia 2D che copre [-L, L] x [-L, L] con celle di lato res metri"""

    def __init__(self, L, res=1.0, dtype=np.float32, fill=0):
        self.L = float(L)
        self.res = float(res)
        self.n = int(math.ceil(2 * L / res))
        self.a = np.full((self.n, self.n), fill, dtype)

    def idx(self, x, y):
        k = 1.0 / self.res
        return int((y + self.L) * k), int((x + self.L) * k)

    def get(self, x, y, default=0):
        k = 1.0 / self.res
        iy = int((y + self.L) * k)
        ix = int((x + self.L) * k)
        if 0 <= ix < self.n and 0 <= iy < self.n:
            return self.a[iy, ix]
        return default

    def fill_rings(self, rings, val, mode="set"):
        """riempie i poligoni (regola pari/dispari: i buchi restano vuoti)"""
        k = 1.0 / self.res
        segs = []
        for r in rings:
            A = (np.asarray(r, np.float64) + self.L) * k
            if len(A) < 3:
                continue
            B = np.roll(A, -1, axis=0)
            segs.append(np.hstack([A, B]))
        if not segs:
            return None
        E = np.vstack(segs)
        ymin, ymax = E[:, [1, 3]].min(), E[:, [1, 3]].max()
        xmin, xmax = E[:, [0, 2]].min(), E[:, [0, 2]].max()
        r0 = max(0, int(math.ceil(ymin - 0.5)))
        r1 = min(self.n - 1, int(math.floor(ymax - 0.5)))
        c0 = max(0, int(math.floor(xmin)) - 1)
        c1 = min(self.n - 1, int(math.ceil(xmax)) + 1)
        if r1 < r0 or c1 < c0:
            return None
        yc = np.arange(r0, r1 + 1) + 0.5
        Y0, Y1 = E[:, 1][None, :], E[:, 3][None, :]
        X0, X1 = E[:, 0][None, :], E[:, 2][None, :]
        cond = (Y0 <= yc[:, None]) != (Y1 <= yc[:, None])
        with np.errstate(divide="ignore", invalid="ignore"):
            xi = X0 + (yc[:, None] - Y0) * (X1 - X0) / (Y1 - Y0)
        xi = np.where(cond, xi, np.inf)
        xi.sort(axis=1)
        W = c1 - c0 + 2
        diff = np.zeros((len(yc), W + 1), np.int32)
        cnt = cond.sum(1)
        maxc = int(cnt.max()) if len(cnt) else 0
        for j in range(0, maxc - 1, 2):
            xa = xi[:, j]
            xb = xi[:, j + 1]
            ok = np.isfinite(xa) & np.isfinite(xb)
            if not ok.any():
                continue
            ca = np.clip(np.ceil(xa[ok] - 0.5).astype(np.int64) - c0, 0, W)
            cb = np.clip(np.ceil(xb[ok] - 0.5).astype(np.int64) - c0, 0, W)
            rows = np.nonzero(ok)[0]
            np.add.at(diff, (rows, ca), 1)
            np.add.at(diff, (rows, cb), -1)
        mask = np.cumsum(diff, axis=1)[:, :W] > 0
        mask = mask[:, :c1 - c0 + 1]
        sub = self.a[r0:r1 + 1, c0:c1 + 1]
        if mode == "max":
            np.maximum(sub, np.where(mask, val, sub), out=sub)
        elif mode == "add":
            sub[mask] += val
        elif mode == "where0":
            sub[mask & (sub == 0)] = val
        elif mode == "min":
            np.minimum(sub, np.where(mask, val, sub), out=sub)
        else:
            sub[mask] = val
        return (r0, c0, mask)

    def stamp_line(self, P, half_w, val, mode="set"):
        """disegna una linea spessa (strade): celle entro half_w dalla linea"""
        P = np.asarray(P, np.float64)
        if len(P) < 2:
            return
        for i in range(len(P) - 1):
            ax, ay = P[i]
            bx, by = P[i + 1]
            dx, dy = bx - ax, by - ay
            l = math.hypot(dx, dy)
            if l < 1e-6:
                continue
            nx, ny = -dy / l * half_w, dx / l * half_w
            quad = [(ax + nx, ay + ny), (bx + nx, by + ny), (bx - nx, by - ny), (ax - nx, ay - ny)]
            self.fill_rings([quad], val, mode)

    def stamp_disc(self, x, y, r, val):
        iy, ix = self.idx(x, y)
        k = int(math.ceil(r / self.res))
        r0, r1 = max(0, iy - k), min(self.n, iy + k + 1)
        c0, c1 = max(0, ix - k), min(self.n, ix + k + 1)
        if r1 <= r0 or c1 <= c0:
            return
        yy, xx = np.mgrid[r0:r1, c0:c1]
        cx = (xx + 0.5) * self.res - self.L
        cy = (yy + 0.5) * self.res - self.L
        m = (cx - x) ** 2 + (cy - y) ** 2 <= r * r
        self.a[r0:r1, c0:c1][m] = val


# =============================================================================
#  CITTA'
# =============================================================================
CELL = 72.0          # distanza tra gli assi stradali
ROAD_W = 14.0        # larghezza dell'asfalto
SIDE_W = 4.0         # marciapiede
NB = 8               # isolati per lato
HALF = NB * CELL / 2
CURB = 0.14          # altezza del marciapiede
LANE = 3.0           # distanza della corsia dal centro strada
PARK_LANE = 5.6      # auto parcheggiate lungo il marciapiede
WORLD_LIMIT = HALF + 170
MAP_R = HALF + 180

BLOCK_PLAN = [  # riga 0 = nord (by = 7)
    "SSMMMPMS",
    "SCMDDMMS",
    "MMDDBDMG",
    "PMDDDDMM",
    "MMDDDDFM",
    "SMMDDMML",
    "SHMMPMMS",
    "SSSMMLSS",
]


def rc(i):
    """coordinata dell'asse stradale i"""
    return -HALF + i * CELL


def block_rect(bx, by):
    return (rc(bx) + ROAD_W / 2, rc(by) + ROAD_W / 2, rc(bx + 1) - ROAD_W / 2, rc(by + 1) - ROAD_W / 2)


def lot_rect(bx, by):
    x0, y0, x1, y1 = block_rect(bx, by)
    return (x0 + SIDE_W, y0 + SIDE_W, x1 - SIDE_W, y1 - SIDE_W)


class StaticWorld:
    """Collisioni statiche: scatole (edifici) e cilindri (alberi, pali) in una griglia spaziale."""
    CS = 16.0

    def __init__(self):
        self.limit = WORLD_LIMIT
        self.boxes = []      # (x0, y0, x1, y1, z0, z1, tag)
        self.circles = []    # (x, y, r, z1, tag)
        self.gb = {}
        self.gc = {}

    def _cells(self, x0, y0, x1, y1):
        cs = self.CS
        for ix in range(int(math.floor(x0 / cs)), int(math.floor(x1 / cs)) + 1):
            for iy in range(int(math.floor(y0 / cs)), int(math.floor(y1 / cs)) + 1):
                yield (ix, iy)

    def add_box(self, x0, y0, x1, y1, z0, z1, tag=None):
        if x0 > x1:
            x0, x1 = x1, x0
        if y0 > y1:
            y0, y1 = y1, y0
        i = len(self.boxes)
        self.boxes.append((x0, y0, x1, y1, z0, z1, tag))
        for c in self._cells(x0, y0, x1, y1):
            self.gb.setdefault(c, []).append(i)
        return i

    def add_circle(self, x, y, r, z1, tag=None):
        i = len(self.circles)
        self.circles.append((x, y, r, z1, tag))
        for c in self._cells(x - r, y - r, x + r, y + r):
            self.gc.setdefault(c, []).append(i)
        return i

    def near(self, x0, y0, x1, y1):
        bs, cs = set(), set()
        for c in self._cells(x0, y0, x1, y1):
            l = self.gb.get(c)
            if l:
                bs.update(l)
            l = self.gc.get(c)
            if l:
                cs.update(l)
        return bs, cs

    @staticmethod
    def terrain(x, y):
        f = GROUND_FN[0]
        if f is not None:
            return f(x, y)
        if abs(x) > HALF + ROAD_W / 2 or abs(y) > HALF + ROAD_W / 2:
            return 0.0
        lx = (x + HALF) % CELL
        ly = (y + HALF) % CELL
        if ROAD_W / 2 <= lx <= CELL - ROAD_W / 2 and ROAD_W / 2 <= ly <= CELL - ROAD_W / 2:
            return CURB
        return 0.0

    def hb_blocked(self, x, y):
        return False

    def support(self, x, y, z, r=0.3):
        """altezza della superficie su cui si appoggia un corpo a quota z (tetti inclusi)"""
        g = self.terrain(x, y)
        bs, _ = self.near(x - r, y - r, x + r, y + r)
        for i in bs:
            x0, y0, x1, y1, z0, z1, _t = self.boxes[i]
            if x0 - r * 0.5 <= x <= x1 + r * 0.5 and y0 - r * 0.5 <= y <= y1 + r * 0.5 and z1 <= z + 0.55 and z1 > g:
                g = z1
        return g

    def push_circle(self, x, y, z, r, h=1.8, step=0.55):
        """sposta un cerchio fuori dagli ostacoli; ritorna (x, y, urtato, normale)"""
        hit = False
        nrm = (0.0, 0.0)
        bs, cs = self.near(x - r - 1, y - r - 1, x + r + 1, y + r + 1)
        for i in bs:
            x0, y0, x1, y1, z0, z1, _t = self.boxes[i]
            if z + step >= z1 or z + h <= z0:
                continue
            cx = clamp(x, x0, x1)
            cy = clamp(y, y0, y1)
            dx, dy = x - cx, y - cy
            d2 = dx * dx + dy * dy
            if d2 < r * r:
                if d2 > 1e-9:
                    d = math.sqrt(d2)
                    x = cx + dx / d * r
                    y = cy + dy / d * r
                    nrm = (dx / d, dy / d)
                else:
                    # centro dentro la scatola: esci dal lato piu' vicino
                    opts = ((x - x0, -1, 0), (x1 - x, 1, 0), (y - y0, 0, -1), (y1 - y, 0, 1))
                    pen, sx, sy = min(opts)
                    if sx:
                        x = (x0 - r) if sx < 0 else (x1 + r)
                    else:
                        y = (y0 - r) if sy < 0 else (y1 + r)
                    nrm = (sx, sy)
                hit = True
        for i in cs:
            ox, oy, orad, oz1, _t = self.circles[i]
            if z + step >= oz1:
                continue
            dx, dy = x - ox, y - oy
            d = math.hypot(dx, dy)
            rr = r + orad
            if d < rr:
                if d < 1e-6:
                    dx, dy, d = 1.0, 0.0, 1.0
                x = ox + dx / d * rr
                y = oy + dy / d * rr
                nrm = (dx / d, dy / d)
                hit = True
        lim = self.limit
        if abs(x) > lim or abs(y) > lim:
            x = clamp(x, -lim, lim)
            y = clamp(y, -lim, lim)
            hit = True
        return x, y, hit, nrm

    def raycast(self, ox, oy, oz, dx, dy, dz, maxd, ground=True):
        """ritorna (t, normale) del primo impatto, oppure None"""
        best = maxd
        bn = None
        if ground and dz < -1e-6:
            t = (0.0 - oz) / dz
            if 0 < t < best:
                best, bn = t, (0, 0, 1)
        ex, ey = ox + dx * maxd, oy + dy * maxd
        steps = max(1, int(maxd / (self.CS * 0.5)))
        seen_b, seen_c = set(), set()
        for k in range(steps + 1):
            t0 = maxd * k / steps
            px, py = ox + dx * t0, oy + dy * t0
            bs, cs = self.near(px - 2, py - 2, px + 2, py + 2)
            seen_b |= bs
            seen_c |= cs
            if k * maxd / steps > best:
                break
        for i in seen_b:
            x0, y0, x1, y1, z0, z1, _t = self.boxes[i]
            tmin, tmax = 0.0, best
            n = None
            ok = True
            for o, d, lo, hi, axis in ((ox, dx, x0, x1, 0), (oy, dy, y0, y1, 1), (oz, dz, z0, z1, 2)):
                if abs(d) < 1e-9:
                    if o < lo or o > hi:
                        ok = False
                        break
                    continue
                ta, tb = (lo - o) / d, (hi - o) / d
                sgn = -1
                if ta > tb:
                    ta, tb = tb, ta
                    sgn = 1
                if ta > tmin:
                    tmin = ta
                    n = [0, 0, 0]
                    n[axis] = sgn
                tmax = min(tmax, tb)
                if tmin > tmax:
                    ok = False
                    break
            if ok and 0 < tmin < best and n is not None:
                best, bn = tmin, tuple(n)
        for i in seen_c:
            cx, cy, r, z1, _t = self.circles[i]
            fx, fy = ox - cx, oy - cy
            a = dx * dx + dy * dy
            if a < 1e-9:
                continue
            b = 2 * (fx * dx + fy * dy)
            c = fx * fx + fy * fy - r * r
            disc = b * b - 4 * a * c
            if disc < 0:
                continue
            t = (-b - math.sqrt(disc)) / (2 * a)
            if 0 < t < best and oz + dz * t < z1:
                best = t
                hx, hy = ox + dx * t - cx, oy + dy * t - cy
                l = math.hypot(hx, hy) or 1
                bn = (hx / l, hy / l, 0)
        if bn is None:
            return None
        return best, bn

    def los(self, a, b):
        dx, dy, dz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
        d = math.sqrt(dx * dx + dy * dy + dz * dz)
        if d < 0.01:
            return True
        hit = self.raycast(a[0], a[1], a[2], dx / d, dy / d, dz / d, d, ground=False)
        return hit is None


def tex_garage(w=128, h=128):
    a = np.zeros((h, w, 3), np.float32)
    a[:] = (236, 236, 230)
    for y in range(0, h, 26):
        a[y:y + 3] = (170, 170, 165)
    a[:, :3] = (150, 150, 145)
    a[:, -3:] = (150, 150, 145)
    a += grain((h, w), 4, 8)[..., None]
    return to_u8(a)


def tex_field(size=256):
    n = fbm(size, 8, 4, 77)
    g = np.stack([60 + n * 20, 110 + n * 30, 50 + n * 10], -1)
    stripe = (np.arange(size) // 32) % 2
    g *= (0.92 + 0.08 * stripe)[None, :, None]
    return to_u8(g)


class City:
    def __init__(self, env, seed=137):
        self.env = env
        self.rng = random.Random(seed)
        self.world = StaticWorld()
        self.meshes = {}
        self.lamps = []
        self.spots = {}
        self.parking = []
        self.ped_rects = []
        self.cop_spawns = []
        self.rooftops = []
        self.signs = []
        self.types = {}
        self.font = None
        self._textures()
        for by in range(NB):
            row = BLOCK_PLAN[NB - 1 - by]
            for bx in range(NB):
                self.types[(bx, by)] = row[bx]
        self._ground()
        self._roads()
        for bx in range(NB):
            for by in range(NB):
                self._block(bx, by)
                self._street_furniture(bx, by)
        self._outskirts()
        self._street_parking()
        self.root = env.root.attachNewNode("citta")
        self._finalize()
        self.map_img = self._make_map()
        self.map_r = MAP_R
        self.limit = WORLD_LIMIT
        self.ped_rings = [RectRing(r) for r in self.ped_rects]
        self._net()

    def _net(self):
        """grafo stradale della griglia (lo stesso formato della citta' vera)"""
        net = RoadNet()
        for i in range(NB + 1):
            for j in range(NB + 1):
                net.node((i, j), rc(i), rc(j))
        trim = ROAD_W / 2 + 1.5
        for i in range(NB + 1):
            for j in range(NB + 1):
                for (di, dj) in ((1, 0), (0, 1)):
                    a, b = (i, j), (i + di, j + dj)
                    if b[0] > NB or b[1] > NB:
                        continue
                    ch = Chain()
                    ch.id = len(net.chains)
                    ch.k = "residential"
                    ch.pl = Polyline([(rc(a[0]), rc(a[1])), (rc(b[0]), rc(b[1]))])
                    ch.n0, ch.n1 = net.key2node[a], net.key2node[b]
                    ch.ow = 0
                    ch.lf = ch.lb = 1
                    ch.lane_w = (LANE - 0.3) * 2
                    ch.hw = ROAD_W / 2
                    ch.park = False
                    ch.speed = 12.5
                    ch.traffic = True
                    ch.sw = SIDE_W
                    ch.name = ""
                    ch.trim = [trim, trim]
                    ch.signal = [False, False]
                    ch.group = [0, 0]
                    ch.cut = None
                    net.chains.append(ch)
                    net.out[ch.n0].append((ch.id, 1))
                    net.out[ch.n1].append((ch.id, -1))
        net.finish()
        self.net = net

    def update(self, dt, t):
        pass

    def ped_link(self, ring, end):
        return None

    def free_point_near(self, x, y, roads_ok=False, rmax=60.0):
        return (x, y)

    def mission_starts(self):
        parks = self.spots.get("parchi", [(0, 0)])
        center_park = min(parks, key=lambda p: abs(p[0]) + abs(p[1]))
        sx, sy, _h = self.spots["casa"]
        return [None, (sx + 3, sy - 6), self.spots["polizia"], self.spots["cronenberg"],
                (center_park[0], center_park[1] - 13)]

    def seed_spots(self):
        parks = self.spots.get("parchi", [])
        spots = []
        if parks:
            spots.append((parks[0][0] + 12, parks[0][1] - 10, CURB))
        roofs = sorted(self.rooftops, key=lambda r: abs(r[2] - 22) + abs(r[0]) * 0.02 + abs(r[1]) * 0.02)
        spots.append(roofs[0])
        sx, sy = self.spots["scuola"]
        spots.append((sx, sy + 40, CURB))
        spots.append((-HALF - 60, HALF * 0.3, 0.0))
        spots.append((HALF * 0.5, -HALF - 40, 0.0))
        return spots

    # ------------------------------------------------------------------ materiali
    def _textures(self):
        T = {}
        E = {}
        T["asphalt"] = make_texture(tex_asphalt(), "asfalto")
        T["sidewalk"] = make_texture(tex_sidewalk(), "marciapiede")
        T["grass"] = make_texture(tex_grass(), "erba")
        T["gravel"] = make_texture(tex_gravel(), "ghiaia")
        T["roof"] = make_texture(tex_roof(), "tetto")
        T["shingles"] = make_texture(tex_shingles(), "tegole")
        T["garage"] = make_texture(tex_garage(), "garage")
        T["field"] = make_texture(tex_field(), "campo")
        kinds = [("glass", 0), ("glass", 1), ("concrete", 0), ("concrete", 1), ("dark", 0), ("brick", 0),
                 ("brick", 1), ("plaster", 0), ("plaster", 1), ("teal", 0), ("cream", 0)]
        for k, v in kinds:
            a, e = tex_facade(k, 100 + v * 17 + len(k))
            T["f_%s%d" % (k, v)] = make_texture(a, "facciata")
            E["f_%s%d" % (k, v)] = make_texture(e, "luci")
        for i in range(3):
            a, e = tex_shopfront(300 + i)
            T["shop%d" % i] = make_texture(a, "negozi")
            E["shop%d" % i] = make_texture(e, "negozi_luci")
        for i in range(4):
            a, e = tex_house(400 + i)
            T["house%d" % i] = make_texture(a, "casa")
            E["house%d" % i] = make_texture(e, "casa_luci")
        lamp_e = np.zeros((4, 4, 3), np.uint8)
        lamp_e[:] = (255, 230, 180)
        E["lamp"] = make_texture(lamp_e, "lampada", mipmap=False)
        self.T, self.E = T, E
        self.MAT = {
            "asphalt": (0.30, 40, 0.05, 0), "sidewalk": (0.12, 20, 0.0, 0), "grass": (0.04, 8, 0.0, 0),
            "gravel": (0.05, 10, 0.0, 0), "roof": (0.08, 10, 0.0, 0), "shingles": (0.15, 20, 0.02, 0),
            "garage": (0.25, 30, 0.04, 0), "field": (0.04, 8, 0, 0), "props": (0.3, 30, 0.05, 0),
            "metal": (0.9, 70, 0.35, 0), "water": (1.2, 160, 0.85, 0), "leaves": (0.05, 6, 0.0, 0),
            "lamp": (0.5, 40, 0.0, 1.0), "glassmat": (1.0, 120, 0.7, 0),
        }

    def mat_for(self, key):
        if key.startswith("f_glass"):
            return (0.9, 90, 0.55, 1.0)
        if key.startswith("f_"):
            return (0.18, 24, 0.06, 1.0)
        if key.startswith("shop"):
            return (0.4, 50, 0.15, 1.0)
        if key.startswith("house"):
            return (0.15, 20, 0.04, 1.0)
        return self.MAT.get(key, (0.25, 24, 0.0, 0))

    def M(self, key, x, y):
        if abs(x) > HALF + ROAD_W or abs(y) > HALF + ROAD_W:
            ck = ("out", int((x + 1000) // 400), int((y + 1000) // 400))
        else:
            ck = (int(clamp((x + HALF) // (CELL * 2), 0, NB // 2 - 1)), int(clamp((y + HALF) // (CELL * 2), 0, NB // 2 - 1)))
        d = self.meshes.setdefault(ck, {})
        m = d.get(key)
        if m is None:
            m = d[key] = Mesh()
        return m

    def _finalize(self):
        for ck, d in self.meshes.items():
            cnode = self.root.attachNewNode("zona")
            for key, m in d.items():
                if len(m) == 0:
                    continue
                tkey = "lamp" if key == "lamp" else key
                tex = self.T.get(tkey)
                emit = self.E.get(key)
                np_ = m.attach(cnode, key, tex, emit, self.mat_for(key))
                if key == "glassmat":
                    np_.setTransparency(TransparencyAttrib.M_alpha)
        self.meshes = {}

    # ------------------------------------------------------------------ terreno e strade
    def _ground(self):
        g = Mesh()
        E = HALF + ROAD_W / 2
        g.quad((-E, -E, 0), (E, -E, 0), (E, E, 0), (-E, E, 0), (255, 255, 255),
               ((-E / 9, -E / 9), (E / 9, -E / 9), (E / 9, E / 9), (-E / 9, E / 9)), (0, 0, 1))
        g.attach(self.env.root, "asfalto", self.T["asphalt"], None, self.MAT["asphalt"])
        # terreno esterno con colline lontane
        t = Mesh()
        N = 48
        R = 1600.0
        rng = random.Random(5)
        hn = [[0.0] * (N + 1) for _ in range(N + 1)]
        for i in range(N + 1):
            for j in range(N + 1):
                x = -R + 2 * R * i / N
                y = -R + 2 * R * j / N
                d = max(abs(x), abs(y))
                k = smoothstep(WORLD_LIMIT + 120, 1300, d)
                hn[i][j] = k * (60 + 120 * (0.5 + 0.5 * math.sin(x * 0.006 + 1.7) * math.cos(y * 0.005 - 0.4))
                                + rng.uniform(-8, 8)) - 0.03
        def tcol(x, y, z):
            f = 0.9 + 0.12 * math.sin(x * 0.013 + 0.5) * math.cos(y * 0.011 - 1.2) + 0.06 * math.sin(x * 0.041 + y * 0.037)
            rock = smoothstep(40, 110, z)
            g = (230 * f, 255 * f, 225 * f)
            return (int(lerp(g[0], 200, rock)), int(lerp(g[1], 190, rock)), int(lerp(g[2], 180, rock)))
        for i in range(N):
            for j in range(N):
                x0 = -R + 2 * R * i / N
                y0 = -R + 2 * R * j / N
                x1 = x0 + 2 * R / N
                y1 = y0 + 2 * R / N
                if max(abs(x0), abs(x1)) <= HALF + ROAD_W and max(abs(y0), abs(y1)) <= HALF + ROAD_W:
                    continue
                hh = (hn[i][j], hn[i + 1][j], hn[i + 1][j + 1], hn[i][j + 1])
                cols = [tcol(x0, y0, hh[0]), tcol(x1, y0, hh[1]), tcol(x1, y1, hh[2]), tcol(x0, y1, hh[3])]
                t.quad4((x0, y0, hh[0]), (x1, y0, hh[1]), (x1, y1, hh[2]), (x0, y1, hh[3]), cols,
                        ((x0 / 10, y0 / 10), (x1 / 10, y0 / 10), (x1 / 10, y1 / 10), (x0 / 10, y1 / 10)))
        t.attach(self.env.root, "terreno", self.T["grass"], None, self.MAT["grass"])

    def _roads(self):
        m = Mesh()
        W = (238, 238, 232)
        Y = (230, 190, 60)
        z = 0.012
        for i in range(NB + 1):
            c = rc(i)
            for j in range(NB):
                a = rc(j) + ROAD_W / 2 + 4
                b = rc(j + 1) - ROAD_W / 2 - 4
                # linea centrale tratteggiata
                t = a
                while t < b - 3:
                    m.quad((t, c - 0.08, z), (t + 3, c - 0.08, z), (t + 3, c + 0.08, z), (t, c + 0.08, z), W)
                    m.quad((c + 0.08, t, z), (c + 0.08, t + 3, z), (c - 0.08, t + 3, z), (c - 0.08, t, z), W)
                    t += 6
                # linee di bordo
                for s in (-1, 1):
                    e = c + s * (ROAD_W / 2 - 0.6)
                    m.quad((a - 4, e - 0.07, z), (b + 4, e - 0.07, z), (b + 4, e + 0.07, z), (a - 4, e + 0.07, z), Y)
                    m.quad((e + 0.07, a - 4, z), (e + 0.07, b + 4, z), (e - 0.07, b + 4, z), (e - 0.07, a - 4, z), Y)
            # strisce pedonali e linee di stop vicino agli incroci
            for j in range(NB + 1):
                cx, cy = c, rc(j)
                for dirx, diry in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ex = cx + dirx * (ROAD_W / 2 + 1.6)
                    ey = cy + diry * (ROAD_W / 2 + 1.6)
                    if abs(ex) > HALF + 1 or abs(ey) > HALF + 1:
                        continue
                    for k in range(-5, 6):
                        o = k * 1.2
                        if dirx:
                            m.quad((ex - 1.4, ey + o - 0.3, z), (ex + 1.4, ey + o - 0.3, z),
                                   (ex + 1.4, ey + o + 0.3, z), (ex - 1.4, ey + o + 0.3, z), W)
                        else:
                            m.quad((ex + o - 0.3, ey - 1.4, z), (ex + o + 0.3, ey - 1.4, z),
                                   (ex + o + 0.3, ey + 1.4, z), (ex + o - 0.3, ey + 1.4, z), W)
        node = m.attach(self.env.root, "segnaletica", None, None, (0.3, 30, 0.05, 0))
        node.setDepthOffset(1)
        # grafo stradale per il traffico
        self.nodes = {(i, j): (rc(i), rc(j)) for i in range(NB + 1) for j in range(NB + 1)}

    # ------------------------------------------------------------------ isolati
    def _slab(self, bx, by, lot_key="sidewalk", lot_uv=4.0):
        x0, y0, x1, y1 = block_rect(bx, by)
        lx0, ly0, lx1, ly1 = lot_rect(bx, by)
        s = self.M("sidewalk", x0, y0)
        z = CURB

        def top(m, a0, b0, a1, b1, uvs):
            m.quad((a0, b0, z), (a1, b0, z), (a1, b1, z), (a0, b1, z), (255, 255, 255),
                   ((a0 / uvs, b0 / uvs), (a1 / uvs, b0 / uvs), (a1 / uvs, b1 / uvs), (a0 / uvs, b1 / uvs)), (0, 0, 1))
        top(s, x0, y0, x1, ly0, 4.0)
        top(s, x0, ly1, x1, y1, 4.0)
        top(s, x0, ly0, lx0, ly1, 4.0)
        top(s, lx1, ly0, x1, ly1, 4.0)
        top(self.M(lot_key, lx0, ly0), lx0, ly0, lx1, ly1, lot_uv)
        # cordolo
        s.box(x0, y0, 0, x1, y1, z, (215, 212, 205), faces="xXyY")
        c = self.M("props", x0, y0)
        for (a0, b0, a1, b1) in ((x0, y0, x1, y0 + 0.25), (x0, y1 - 0.25, x1, y1), (x0, y0, x0 + 0.25, y1), (x1 - 0.25, y0, x1, y1)):
            c.quad((a0, b0, z + 0.004), (a1, b0, z + 0.004), (a1, b1, z + 0.004), (a0, b1, z + 0.004), (196, 194, 188))
        self.ped_rects.append((x0 + 1.9, y0 + 1.9, x1 - 1.9, y1 - 1.9))

    def _block(self, bx, by):
        t = self.types[(bx, by)]
        rng = self.rng
        lx0, ly0, lx1, ly1 = lot_rect(bx, by)
        if t in "SH":
            self._slab(bx, by, "grass", 6.0)
            self._suburb(bx, by, smith=(t == "H"))
        elif t == "P":
            self._slab(bx, by, "grass", 6.0)
            self._park(bx, by)
        elif t == "C":
            self._slab(bx, by, "sidewalk")
            self._school(bx, by)
        elif t == "F":
            self._slab(bx, by, "sidewalk")
            self._police(bx, by)
        elif t == "G":
            self._slab(bx, by, "sidewalk")
            self._gas(bx, by)
        elif t == "L":
            self._slab(bx, by, "asphalt", 9.0)
            self._parking_lot(bx, by)
        elif t in "DB":
            self._slab(bx, by, "sidewalk")
            d = max(abs(bx - 3.5), abs(by - 3.5))
            hmax = 150 - d * 28
            if t == "B":
                self._arcade(bx, by)
                self._tower(lx0, ly0 + 26, lx1, ly1, rng.uniform(50, hmax), rng.choice(["f_glass0", "f_dark0"]))
            else:
                mode = rng.choice((1, 2, 2, 4))
                if mode == 1:
                    self._tower(lx0 + 3, ly0 + 3, lx1 - 3, ly1 - 3, rng.uniform(70, hmax),
                                rng.choice(["f_glass0", "f_glass1", "f_concrete0", "f_dark0"]))
                elif mode == 2:
                    if rng.random() < 0.5:
                        mx = (lx0 + lx1) / 2
                        parts = [(lx0 + 1, ly0 + 1, mx - 3, ly1 - 1), (mx + 3, ly0 + 1, lx1 - 1, ly1 - 1)]
                    else:
                        my = (ly0 + ly1) / 2
                        parts = [(lx0 + 1, ly0 + 1, lx1 - 1, my - 3), (lx0 + 1, my + 3, lx1 - 1, ly1 - 1)]
                    for p in parts:
                        self._tower(*p, rng.uniform(40, hmax), rng.choice(["f_glass0", "f_glass1", "f_concrete0", "f_concrete1", "f_dark0"]))
                else:
                    mx, my = (lx0 + lx1) / 2, (ly0 + ly1) / 2
                    for p in ((lx0 + 1, ly0 + 1, mx - 3, my - 3), (mx + 3, ly0 + 1, lx1 - 1, my - 3),
                              (lx0 + 1, my + 3, mx - 3, ly1 - 1), (mx + 3, my + 3, lx1 - 1, ly1 - 1)):
                        self._tower(*p, rng.uniform(30, hmax * 0.85),
                                    rng.choice(["f_glass0", "f_glass1", "f_concrete0", "f_concrete1", "f_dark0", "f_cream0"]))
        else:  # M: isolato a corte con palazzi sui bordi
            self._slab(bx, by, "sidewalk")
            self._midtown(bx, by)

    def _building(self, x0, y0, x1, y1, h, fkey, shop=True, roof_props=True):
        rng = self.rng
        fm = self.M(fkey, x0, y0)
        base = CURB
        if shop:
            sk = "shop%d" % rng.randrange(3)
            self.M(sk, x0, y0).box(x0 - 0.25, y0 - 0.25, base, x1 + 0.25, y1 + 0.25, 4.6, (255, 255, 255),
                                   uv=(12, 4.6 - base), faces="yXYx", v_base=base, wrap_u=True)
            fm.box(x0, y0, 4.6, x1, y1, h, (255, 255, 255), uv=(12, 12), faces="yXYx", v_base=4.6, wrap_u=True,
                   u_off=rng.choice((0.0, 0.25, 0.5, 0.75)))
            self.M("props", x0, y0).box(x0 - 0.3, y0 - 0.3, 4.6, x1 + 0.3, y1 + 0.3, 4.9, (120, 116, 110), faces="xXyYz")
        else:
            fm.box(x0, y0, base, x1, y1, h, (255, 255, 255), uv=(12, 12), faces="yXYx", v_base=base, wrap_u=True)
        r = self.M("roof", x0, y0)
        r.quad((x0, y0, h), (x1, y0, h), (x1, y1, h), (x0, y1, h), (255, 255, 255),
               ((x0 / 8, y0 / 8), (x1 / 8, y0 / 8), (x1 / 8, y1 / 8), (x0 / 8, y1 / 8)), (0, 0, 1))
        p = self.M("props", x0, y0)
        pc = (150, 146, 140)
        p.box(x0, y0, h, x1, y0 + 0.35, h + 0.9, pc, faces="xXyYz")
        p.box(x0, y1 - 0.35, h, x1, y1, h + 0.9, pc, faces="xXyYz")
        p.box(x0, y0 + 0.35, h, x0 + 0.35, y1 - 0.35, h + 0.9, pc, faces="xXyYz")
        p.box(x1 - 0.35, y0 + 0.35, h, x1, y1 - 0.35, h + 0.9, pc, faces="xXyYz")
        if roof_props:
            for _ in range(rng.randint(1, 4)):
                w, d = rng.uniform(1.5, 3.5), rng.uniform(1.5, 3.0)
                cx = rng.uniform(x0 + 2 + w, x1 - 2 - w)
                cy = rng.uniform(y0 + 2 + d, y1 - 2 - d)
                p.box(cx - w / 2, cy - d / 2, h, cx + w / 2, cy + d / 2, h + rng.uniform(1.0, 2.2), (176, 178, 182), faces="xXyYz")
            if rng.random() < 0.35 and (x1 - x0) > 10:
                cx, cy = x0 + 4, y1 - 4
                p.cylinder(cx, cy, h + 3.0, h + 6.5, 1.6, (120, 92, 70), seg=12)
                p.cylinder(cx, cy, h + 6.5, h + 7.6, 1.8, (90, 70, 56), seg=12, r_top=0.1)
                for ox, oy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                    p.cylinder(cx + ox, cy + oy, h, h + 3.0, 0.12, (80, 80, 84), seg=6, cap=False)
        self.world.add_box(x0 - 0.25, y0 - 0.25, x1 + 0.25, y1 + 0.25, -1, h, "edificio")
        self.rooftops.append(((x0 + x1) / 2, (y0 + y1) / 2, h))

    def _tower(self, x0, y0, x1, y1, h, fkey):
        rng = self.rng
        if h > 60 and min(x1 - x0, y1 - y0) > 18:
            h1 = h * rng.uniform(0.55, 0.7)
            self._building(x0, y0, x1, y1, h1, fkey, True, roof_props=False)
            ins = rng.uniform(3, 6)
            self._building(x0 + ins, y0 + ins, x1 - ins, y1 - ins, h, fkey, False, roof_props=True)
            if h > 100:
                p = self.M("props", x0, y0)
                cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
                p.cylinder(cx, cy, h, h + 18, 0.35, (200, 200, 205), seg=8, r_top=0.12)
                self.M("lamp", x0, y0).ellipsoid(cx, cy, h + 18.3, 0.5, 0.5, 0.5, (255, 60, 50), seg=8, rings=6)
        else:
            self._building(x0, y0, x1, y1, h, fkey, True)

    def _midtown(self, bx, by):
        rng = self.rng
        lx0, ly0, lx1, ly1 = lot_rect(bx, by)
        depth = rng.uniform(13, 17)
        kinds = ["f_brick0", "f_brick1", "f_plaster0", "f_plaster1", "f_teal0", "f_concrete1", "f_cream0"]
        strips = [
            (lx0, ly0, lx1, ly0 + depth, "x"),
            (lx0, ly1 - depth, lx1, ly1, "x"),
            (lx0, ly0 + depth, lx0 + depth, ly1 - depth, "y"),
            (lx1 - depth, ly0 + depth, lx1, ly1 - depth, "y"),
        ]
        for (a0, b0, a1, b1, axis) in strips:
            L = (a1 - a0) if axis == "x" else (b1 - b0)
            n = rng.choice((1, 2, 2, 3))
            cuts = sorted(rng.uniform(0.25, 0.75) * L for _ in range(n - 1))
            edges = [0.0] + cuts + [L]
            for k in range(len(edges) - 1):
                s0, s1 = edges[k], edges[k + 1]
                if s1 - s0 < 8:
                    continue
                h = rng.uniform(14, 34)
                fk = rng.choice(kinds)
                if axis == "x":
                    self._building(a0 + s0, b0, a0 + s1, b1, h, fk, True)
                else:
                    self._building(a0, b0 + s0, a1, b0 + s1, h, fk, rng.random() < 0.5)
        # cortile interno con alberi
        cx0, cy0, cx1, cy1 = lx0 + depth, ly0 + depth, lx1 - depth, ly1 - depth
        g = self.M("grass", cx0, cy0)
        g.quad((cx0, cy0, CURB + 0.01), (cx1, cy0, CURB + 0.01), (cx1, cy1, CURB + 0.01), (cx0, cy1, CURB + 0.01),
               (255, 255, 255), ((cx0 / 6, cy0 / 6), (cx1 / 6, cy0 / 6), (cx1 / 6, cy1 / 6), (cx0 / 6, cy1 / 6)), (0, 0, 1))
        for _ in range(rng.randint(1, 3)):
            self._tree(rng.uniform(cx0 + 3, cx1 - 3), rng.uniform(cy0 + 3, cy1 - 3))

    # ------------------------------------------------------------------ periferia
    def _suburb(self, bx, by, smith=False):
        rng = self.rng
        lx0, ly0, lx1, ly1 = lot_rect(bx, by)
        w = (lx1 - lx0) / 3
        for row, (facing, yy) in enumerate(((180, ly0 + 13), (0, ly1 - 13))):
            for k in range(3):
                cx = lx0 + w * (k + 0.5)
                is_smith = smith and row == 0 and k == 1
                if is_smith:
                    cx -= 3.0
                self._house(cx, yy, facing, rng.randrange(4), is_smith)
                # vialetto
                dy0, dy1 = (ly0 - SIDE_W, yy - 4) if facing == 180 else (yy + 4, ly1 + SIDE_W)
                dxo = 4.0 if not is_smith else 7.5
                m = self.M("sidewalk", cx, yy)
                m.quad((cx + dxo - 1.6, dy0, CURB + 0.02), (cx + dxo + 1.6, dy0, CURB + 0.02),
                       (cx + dxo + 1.6, dy1, CURB + 0.02), (cx + dxo - 1.6, dy1, CURB + 0.02), (235, 235, 235),
                       ((0, dy0 / 4), (0.8, dy0 / 4), (0.8, dy1 / 4), (0, dy1 / 4)), (0, 0, 1))
                if rng.random() < 0.7:
                    tx = cx - 5.5 + rng.uniform(-1, 1)
                    ty = (ly0 + 3.5) if facing == 180 else (ly1 - 3.5)
                    self._tree(tx, ty, small=True)
                # recinzione bianca sul retro
                f = self.M("props", cx, yy)
                fy = (yy + 6.5) if facing == 180 else (yy - 6.5)
                f.box(cx - w / 2 + 0.3, fy - 0.05, CURB, cx + w / 2 - 0.3, fy + 0.05, CURB + 1.1, (240, 240, 236), faces="xXyYz")
                if is_smith:
                    self.spots["casa"] = (cx + 1.0, ly0 + 2.5, 180.0)
                    self.spots["garage_auto"] = (cx + 8.4, ly0 + 2.6, 180.0)
                    self.spots["smith"] = (cx, yy)

    def _house(self, cx, cy, facing, style, smith=False):
        """casa a due piani con tetto a falde; facing 180 = facciata verso sud"""
        rng = self.rng
        parts = {}

        def P(k):
            m = parts.get(k)
            if m is None:
                m = parts[k] = Mesh()
            return m
        hk = "house%d" % style
        W2, D2, Hh = 5.2, 4.2, 5.8
        z0 = CURB
        P(hk).box(-W2, -D2, z0, W2, D2, Hh, (255, 255, 255), uv=(12, 6), faces="yXYx", v_base=z0)
        rz = Hh + 3.0
        ov = 0.6
        rk = "shingles"
        P(rk).quad((-W2 - ov, -D2 - ov, Hh - 0.3), (W2 + ov, -D2 - ov, Hh - 0.3), (W2 + ov, 0, rz), (-W2 - ov, 0, rz),
                   (255, 255, 255), ((0, 0), (3, 0), (3, 1.4), (0, 1.4)))
        P(rk).quad((W2 + ov, D2 + ov, Hh - 0.3), (-W2 - ov, D2 + ov, Hh - 0.3), (-W2 - ov, 0, rz), (W2 + ov, 0, rz),
                   (255, 255, 255), ((0, 0), (3, 0), (3, 1.4), (0, 1.4)))
        wall = (236, 232, 222) if style != 1 else (210, 222, 232)
        for sx in (-1, 1):
            x = sx * W2
            a, b, c = (x, -D2, Hh), (x, D2, Hh), (x, 0, rz - 0.2)
            if sx > 0:
                P("props").quad(a, b, c, c, wall)
            else:
                P("props").quad(b, a, c, c, wall)
        P("props").box(-0.8, -D2 - 0.12, z0, 0.8, -D2 + 0.05, 2.4, (110, 70, 44), faces="yz")
        P("props").box(-1.6, -D2 - 1.6, 2.6, 1.6, -D2, 2.8, (240, 240, 236), faces="xXyYzZ")
        P("props").box(-1.6, -D2 - 1.8, z0, 1.6, -D2, z0 + 0.25, (196, 192, 186), faces="xXyz")
        for sx in (-1.4, 1.4):
            P("props").cylinder(sx, -D2 - 1.4, z0, 2.6, 0.09, (240, 240, 236), seg=6, cap=False)
        if smith:
            P(hk).box(W2, -D2, z0, W2 + 6.5, D2 - 0.5, 3.6, (255, 255, 255), uv=(12, 6), faces="XYx", v_base=z0)
            P("garage").box(W2 + 0.5, -D2 - 0.02, z0, W2 + 6.0, -D2 + 0.1, 3.0, (255, 255, 255), faces="y")
            P("props").box(W2, -D2, z0 + 3.0, W2 + 6.5, -D2 + 0.4, 3.6, wall, faces="y")
            P("roof").box(W2 - 0.2, -D2 - 0.3, 3.6, W2 + 6.8, D2 - 0.2, 3.8, (255, 255, 255), faces="xXyYz")
        P("props").box(-1.0, -D2 - 4.5, z0, -0.7, -D2 - 4.2, 1.2, (80, 80, 90), faces="xXyYz")
        P("props").box(-1.2, -D2 - 4.7, 1.2, -0.5, -D2 - 4.0, 1.6, (40, 70, 140), faces="xXyYz")
        h = 180 + facing
        for k, m in parts.items():
            self.M(k, cx, cy).add_mesh(m, cx, cy, 0, h)
        ex = W2 + (6.5 if smith else 0)
        pts = [(-W2, -D2), (ex, D2)]
        rad = math.radians(h)
        c, s = math.cos(rad), math.sin(rad)
        wp = [(cx + px * c - py * s, cy + px * s + py * c) for px, py in pts]
        self.world.add_box(min(wp[0][0], wp[1][0]), min(wp[0][1], wp[1][1]), max(wp[0][0], wp[1][0]),
                           max(wp[0][1], wp[1][1]), -1, Hh, "casa")
        self.rooftops.append((cx, cy, rz))

    # ------------------------------------------------------------------ parchi e luoghi speciali
    def _park(self, bx, by):
        rng = self.rng
        lx0, ly0, lx1, ly1 = lot_rect(bx, by)
        cx, cy = (lx0 + lx1) / 2, (ly0 + ly1) / 2
        g = self.M("gravel", cx, cy)
        z = CURB + 0.02
        for (a0, b0, a1, b1) in ((lx0, cy - 2, lx1, cy + 2), (cx - 2, ly0, cx + 2, ly1)):
            g.quad((a0, b0, z), (a1, b0, z), (a1, b1, z), (a0, b1, z), (255, 255, 255),
                   ((a0 / 5, b0 / 5), (a1 / 5, b0 / 5), (a1 / 5, b1 / 5), (a0 / 5, b1 / 5)), (0, 0, 1))
        p = self.M("props", cx, cy)
        p.cylinder(cx, cy, CURB, CURB + 0.7, 6.0, (178, 172, 160), seg=28)
        self.M("water", cx, cy).cylinder(cx, cy, CURB + 0.7, CURB + 0.62, 5.6, (70, 110, 130), seg=28)
        p.cylinder(cx, cy, CURB, CURB + 3.2, 0.6, (178, 172, 160), seg=10)
        p.cylinder(cx, cy, CURB + 3.2, CURB + 3.6, 1.6, (178, 172, 160), seg=14)
        self.world.add_circle(cx, cy, 6.0, CURB + 0.7, "fontana")
        self.spots.setdefault("parchi", []).append((cx, cy))
        for _ in range(26):
            for _try in range(10):
                x, y = rng.uniform(lx0 + 2, lx1 - 2), rng.uniform(ly0 + 2, ly1 - 2)
                if abs(x - cx) > 4.5 and abs(y - cy) > 4.5 and dist2(x, y, cx, cy) > 10:
                    self._tree(x, y, conifer=rng.random() < 0.3)
                    break
        for k in range(6):
            ang = k * 60 + 30
            bxp = cx + math.cos(math.radians(ang)) * 9.5
            byp = cy + math.sin(math.radians(ang)) * 9.5
            m = Mesh()
            m.box(-1.0, -0.25, CURB + 0.45, 1.0, 0.25, CURB + 0.55, (120, 84, 50))
            m.box(-1.0, 0.2, CURB + 0.55, 1.0, 0.28, CURB + 1.0, (120, 84, 50))
            for sx in (-0.85, 0.85):
                m.box(sx - 0.05, -0.2, CURB, sx + 0.05, 0.2, CURB + 0.45, (50, 50, 54))
            self.M("props", bxp, byp).add_mesh(m, bxp, byp, 0, ang + 90)

    def _tree(self, x, y, small=False, conifer=False):
        rng = self.rng
        m = self.M("leaves", x, y)
        th = rng.uniform(2.4, 3.6) * (0.75 if small else 1.0)
        m.cylinder(x, y, CURB, CURB + th, 0.22 if not small else 0.16, (92, 70, 52), seg=7, r_top=0.15)
        if conifer:
            for k in range(3):
                r = 2.6 - k * 0.7
                z0 = CURB + th * 0.6 + k * 2.0
                m.cylinder(x, y, z0, z0 + 3.0, r, (46, 82, 50), seg=9, r_top=0.05)
            top = CURB + th * 0.6 + 7
        else:
            base = rng.choice(((70, 110, 52), (86, 120, 56), (60, 100, 50), (100, 116, 54)))
            R = rng.uniform(2.0, 2.9) * (0.7 if small else 1.0)
            for k in range(rng.randint(3, 5)):
                ox, oy = rng.uniform(-1, 1) * R * 0.5, rng.uniform(-1, 1) * R * 0.5
                oz = CURB + th + R * rng.uniform(0.3, 0.9)
                r = R * rng.uniform(0.65, 0.95)
                m.ellipsoid(x + ox, y + oy, oz, r, r, r * 0.85, base, seg=9, rings=6, jitter=0.12,
                            seed=rng.randrange(10000), color_var=0.12)
            top = CURB + th + R * 2
        self.world.add_circle(x, y, 0.32, top, "albero")

    def _sign(self, text_s, x, y, z, h, scale, color, neon=False, back=None):
        if self.font is None:
            self.font = TextNode.getDefaultFont()
        tn = TextNode("insegna")
        tn.setText(text_s)
        tn.setAlign(TextNode.ACenter)
        tn.setTextColor(*color)
        if back:
            tn.setCardColor(*back)
            tn.setCardAsMargin(0.4, 0.4, 0.2, 0.2)
            tn.setCardDecal(True)
        np_ = self.env.root.attachNewNode(tn.generate())
        np_.setPos(x, y, z)
        np_.setH(h)
        np_.setScale(scale)
        np_.setTransparency(TransparencyAttrib.M_alpha)
        np_.setShader(self.env.sign_shader)
        np_.setShaderInput("u_glow", 1.0 if neon else 0.0)
        np_.setDepthOffset(2)
        np_.hide(MASK_SHADOW)
        self.signs.append(np_)
        return np_

    def _arcade(self, bx, by):
        lx0, ly0, lx1, ly1 = lot_rect(bx, by)
        x0, y0, x1, y1 = lx0 + 2, ly0 + 1, lx1 - 2, ly0 + 22
        self._building(x0, y0, x1, y1, 9.0, "f_dark0", True)
        p = self.M("props", x0, y0)
        p.box(x0 + 6, y0 - 0.9, 5.0, x1 - 6, y0 - 0.5, 8.6, (24, 20, 40), faces="xXyYz")
        self._sign("BLIPS AND CHITZ", (x0 + x1) / 2, y0 - 0.95, 6.6, 0, 1.25, (0.3, 1.0, 1.0, 1), neon=True)
        self._sign("SALA GIOCHI", (x0 + x1) / 2, y0 - 0.95, 5.5, 0, 0.7, (1.0, 0.35, 0.9, 1), neon=True)
        self.spots["arcade"] = ((x0 + x1) / 2, y0 - 8.0)

    def _school(self, bx, by):
        lx0, ly0, lx1, ly1 = lot_rect(bx, by)
        self._building(lx0 + 2, ly0 + 2, lx1 - 2, ly0 + 18, 11.0, "f_brick1", False)
        p = self.M("props", lx0, ly0)
        cx = (lx0 + lx1) / 2
        p.box(cx - 5, ly0 - 0.2, CURB, cx + 5, ly0 + 2, 4.5, (200, 196, 186), faces="xXyz")
        self._sign("LICEO HARRY HERPSON", cx, ly0 - 0.3, 8.0, 0, 1.1, (0.1, 0.12, 0.3, 1), back=(0.95, 0.93, 0.85, 1))
        f = self.M("field", cx, ly1)
        z = CURB + 0.02
        f.quad((lx0 + 2, ly0 + 21, z), (lx1 - 2, ly0 + 21, z), (lx1 - 2, ly1 - 2, z), (lx0 + 2, ly1 - 2, z), (255, 255, 255),
               ((0, 0), (5, 0), (5, 3), (0, 3)), (0, 0, 1))
        for gx in (lx0 + 4, lx1 - 4):
            p.box(gx - 0.08, (ly0 + ly1) / 2 + 12, CURB, gx + 0.08, (ly0 + ly1) / 2 + 12.2, 2.4, (240, 240, 240))
        p.cylinder(lx0 + 4, ly0 + 0.6, CURB, 10, 0.08, (200, 200, 205), seg=6)
        self.spots["scuola"] = (cx, ly0 - 8.0)

    def _police(self, bx, by):
        lx0, ly0, lx1, ly1 = lot_rect(bx, by)
        self._building(lx0 + 2, ly1 - 26, lx1 - 2, ly1 - 2, 22.0, "f_concrete0", False)
        cx = (lx0 + lx1) / 2
        self._sign("FEDERAZIONE GALATTICA", cx, ly1 - 26.3, 16.0, 0, 1.4, (1.0, 0.85, 0.2, 1), neon=True)
        self._sign("DISTRETTO TERRA", cx, ly1 - 26.3, 14.2, 0, 0.9, (0.8, 0.9, 1.0, 1), neon=True)
        m = self.M("props", cx, ly0)
        for k in range(5):
            x = lx0 + 6 + k * 9
            m.quad((x, ly0 + 2, CURB + 0.02), (x + 0.15, ly0 + 2, CURB + 0.02), (x + 0.15, ly0 + 12, CURB + 0.02),
                   (x, ly0 + 12, CURB + 0.02), (240, 240, 240))
        for k in range(4):
            self.cop_spawns.append((lx0 + 10.5 + k * 9, ly0 + 7, 0.0))
        for fx in (cx - 6, cx + 6):
            m.cylinder(fx, ly1 - 30, CURB, 12, 0.1, (210, 210, 215), seg=6)
            m.box(fx, ly1 - 30.05, 9.6, fx + 2.6, ly1 - 29.95, 11.6, (40, 50, 120))
        self.spots["polizia"] = (cx, ly0 - 6.0)

    def _gas(self, bx, by):
        lx0, ly0, lx1, ly1 = lot_rect(bx, by)
        cx, cy = (lx0 + lx1) / 2, (ly0 + ly1) / 2
        p = self.M("props", cx, cy)
        p.box(cx - 10, cy - 7, 5.2, cx + 10, cy + 7, 6.0, (236, 236, 236), faces="xXyYzZ")
        p.box(cx - 10, cy - 7, 5.6, cx + 10, cy - 6.8, 6.0, (200, 40, 40), faces="y")
        for ox in (-8, 8):
            for oy in (-5, 5):
                p.box(cx + ox - 0.25, cy + oy - 0.25, CURB, cx + ox + 0.25, cy + oy + 0.25, 5.2, (220, 220, 220))
                self.world.add_circle(cx + ox, cy + oy, 0.35, 5.2, "colonna")
        for ox in (-4, 4):
            p.box(cx + ox - 2.5, cy - 0.8, CURB, cx + ox + 2.5, cy + 0.8, CURB + 0.3, (190, 190, 186))
            for oo in (-1.3, 1.3):
                p.box(cx + ox + oo - 0.4, cy - 0.35, CURB + 0.3, cx + ox + oo + 0.4, cy + 0.35, 1.9, (200, 40, 40))
            self.world.add_box(cx + ox - 2.5, cy - 0.8, cx + ox + 2.5, cy + 0.8, -1, 1.9, "pompa")
        self.lamps.append((cx - 6, cy, 5.0))
        self.lamps.append((cx + 6, cy, 5.0))
        self._building(lx0 + 4, ly1 - 14, lx0 + 20, ly1 - 4, 4.6, "f_cream0", True, roof_props=False)
        self._sign("CARBURANTE  1.99 S", cx, cy - 7.05, 5.6, 0, 0.55, (1, 1, 1, 1), neon=True)

    def _parking_lot(self, bx, by):
        lx0, ly0, lx1, ly1 = lot_rect(bx, by)
        m = self.M("props", lx0, ly0)
        rng = self.rng
        z = CURB + 0.015
        for row in range(3):
            y = ly0 + 6 + row * 16
            for k in range(9):
                x = lx0 + 3 + k * 5
                m.quad((x, y, z), (x + 0.15, y, z), (x + 0.15, y + 5.5, z), (x, y + 5.5, z), (236, 236, 230))
                if rng.random() < 0.55 and k < 8:
                    self.parking.append((x + 2.5, y + 2.75, 0.0 if row % 2 else 180.0))

    # ------------------------------------------------------------------ arredo urbano
    def _street_furniture(self, bx, by):
        rng = self.rng
        x0, y0, x1, y1 = block_rect(bx, by)
        t = self.types[(bx, by)]
        sides = [((x0, y0), (x1, y0), (0, -1)), ((x1, y1), (x0, y1), (0, 1)),
                 ((x0, y1), (x0, y0), (-1, 0)), ((x1, y0), (x1, y1), (1, 0))]
        for (ax, ay), (ex, ey), (nx, ny) in sides:
            L = math.hypot(ex - ax, ey - ay)
            ux, uy = (ex - ax) / L, (ey - ay) / L
            n = int(L // 24)
            for k in range(n):
                s = 10 + k * 24
                if s > L - 8:
                    break
                px = ax + ux * s - nx * 0.6
                py = ay + uy * s - ny * 0.6
                self._lamp(px, py, nx, ny)
                if t in "MSHP" and rng.random() < 0.7:
                    tx = ax + ux * (s + 12) - nx * 1.0
                    ty = ay + uy * (s + 12) - ny * 1.0
                    if 6 < s + 12 < L - 6:
                        self._tree(tx, ty, small=True)
                elif rng.random() < 0.18:
                    hx = ax + ux * (s + 6) - nx * 0.7
                    hy = ay + uy * (s + 6) - ny * 0.7
                    p = self.M("props", hx, hy)
                    p.cylinder(hx, hy, CURB, CURB + 0.7, 0.16, (200, 40, 36), seg=8)
                    p.ellipsoid(hx, hy, CURB + 0.72, 0.17, 0.17, 0.12, (200, 40, 36), seg=8, rings=4)
                    self.world.add_circle(hx, hy, 0.2, 0.9, "idrante")

    def _lamp(self, x, y, nx, ny):
        p = self.M("metal", x, y)
        p.cylinder(x, y, CURB, 8.2, 0.12, (64, 66, 70), seg=8, r_top=0.08)
        ax, ay = x + nx * 2.2, y + ny * 2.2
        p.box(min(x, ax) - 0.06, min(y, ay) - 0.06, 8.0, max(x, ax) + 0.06, max(y, ay) + 0.06, 8.14, (64, 66, 70))
        hx, hy = x + nx * 2.4, y + ny * 2.4
        p.box(hx - 0.35, hy - 0.35, 7.85, hx + 0.35, hy + 0.35, 8.1, (54, 56, 60))
        self.M("lamp", hx, hy).box(hx - 0.28, hy - 0.28, 7.8, hx + 0.28, hy + 0.28, 7.86, (255, 250, 230), faces="Z")
        self.world.add_circle(x, y, 0.16, 8.2, "lampione")
        self.lamps.append((hx, hy, 7.6))

    def _outskirts(self):
        rng = self.rng
        for _ in range(170):
            for _t in range(10):
                x, y = rng.uniform(-WORLD_LIMIT, WORLD_LIMIT), rng.uniform(-WORLD_LIMIT, WORLD_LIMIT)
                if max(abs(x), abs(y)) > HALF + ROAD_W / 2 + 6:
                    break
            else:
                continue
            if dist2(x, y, HALF + 80, 0) < 25:
                continue
            m = self.M("leaves", x, y)
            if rng.random() < 0.5:
                h = rng.uniform(5, 9)
                m.cylinder(x, y, 0, 2.0, 0.25, (92, 70, 52), seg=7)
                for k in range(3):
                    r = rng.uniform(2.0, 2.8) - k * 0.6
                    m.cylinder(x, y, 1.5 + k * h / 4, 1.5 + k * h / 4 + h / 2.2, r, (40, 76, 46), seg=9, r_top=0.05)
                top = h + 2
            else:
                R = rng.uniform(2.2, 3.4)
                m.cylinder(x, y, 0, 3.0, 0.24, (92, 70, 52), seg=7)
                for k in range(4):
                    ox, oy = rng.uniform(-1, 1), rng.uniform(-1, 1)
                    m.ellipsoid(x + ox, y + oy, 3 + R * 0.7, R * 0.8, R * 0.8, R * 0.7, (78, 112, 54), seg=9, rings=6,
                                jitter=0.12, seed=rng.randrange(9999), color_var=0.12)
                top = 3 + R * 1.6
            self.world.add_circle(x, y, 0.35, top, "albero")
        # recinzione al limite del mondo
        f = Mesh()
        L = WORLD_LIMIT + 1
        for k in range(-30, 31):
            t = k / 30 * L
            for (x, y) in ((t, -L), (t, L), (-L, t), (L, t)):
                f.cylinder(x, y, 0, 1.4, 0.06, (120, 100, 80), seg=5, cap=False)
        for (a, b) in (((-L, -L), (L, -L)), ((L, -L), (L, L)), ((L, L), (-L, L)), ((-L, L), (-L, -L))):
            for z in (0.6, 1.2):
                f.box(min(a[0], b[0]) - 0.03, min(a[1], b[1]) - 0.03, z, max(a[0], b[0]) + 0.03, max(a[1], b[1]) + 0.03, z + 0.06,
                      (130, 110, 90))
        f.attach(self.env.root, "recinzione", None, None, (0.1, 10, 0, 0))
        self.spots["cronenberg"] = (HALF + 80.0, 0.0)

    def _street_parking(self):
        rng = self.rng
        for i in range(NB + 1):
            c = rc(i)
            for j in range(NB):
                a = rc(j) + ROAD_W / 2 + 10
                b = rc(j + 1) - ROAD_W / 2 - 10
                for s in (-1, 1):
                    t = a
                    while t < b:
                        if rng.random() < 0.18:
                            # strada orizzontale (lungo x) e verticale (lungo y)
                            if rng.random() < 0.5:
                                self.parking.append((t, c + s * PARK_LANE, 90.0 if s < 0 else -90.0))
                            else:
                                self.parking.append((c + s * PARK_LANE, t, 0.0 if s > 0 else 180.0))
                        t += 7

    # ------------------------------------------------------------------ mappa (minimappa e mappa grande)
    def _make_map(self, size=1024):
        img = np.zeros((size, size, 3), np.float32)
        img[:] = (46, 60, 46)
        R = MAP_R

        def px(v):
            return int((v + R) / (2 * R) * size)

        def rect(x0, y0, x1, y1, col):
            a0, a1 = sorted((px(x0), px(x1)))
            b0, b1 = sorted((px(y0), px(y1)))
            img[size - b1:size - b0, a0:a1] = col
        E = HALF + ROAD_W / 2
        rect(-E, -E, E, E, (96, 98, 104))
        for bx in range(NB):
            for by in range(NB):
                x0, y0, x1, y1 = block_rect(bx, by)
                t = self.types[(bx, by)]
                col = {"P": (60, 104, 60), "S": (64, 80, 62), "H": (64, 80, 62), "L": (78, 80, 86)}.get(t, (52, 54, 62))
                rect(x0, y0, x1, y1, col)
        for (x0, y0, x1, y1, z0, z1, tag) in self.world.boxes:
            if tag in ("edificio", "casa"):
                v = clamp(70 + z1 * 0.5, 70, 140)
                rect(x0, y0, x1, y1, (v, v, v + 8))
        L = WORLD_LIMIT
        img[size - px(L):size - px(-L), px(-L):px(-L) + 2] = (150, 130, 100)
        img[size - px(L):size - px(-L), px(L) - 2:px(L)] = (150, 130, 100)
        img[size - px(L):size - px(L) + 2, px(-L):px(L)] = (150, 130, 100)
        img[size - px(-L) - 2:size - px(-L), px(-L):px(L)] = (150, 130, 100)
        return to_u8(img)

    def nearest_lamps(self, x, y, n=8, maxd=90.0):
        best = []
        for (lx, ly, lz) in self.lamps:
            d = abs(lx - x) + abs(ly - y)
            if d < maxd:
                best.append((d, lx, ly, lz))
        best.sort()
        return best[:n]


# =============================================================================
#  CITTA' VERA: collisioni con poligoni, grafo stradale, percorsi pedonali
# =============================================================================
GROUND_FN = [None]          # funzione dell'altezza del suolo della citta' attiva


def find_city_data(name="losangeles"):
    cands = []
    if getattr(sys, "_MEIPASS", None):
        cands.append(os.path.join(sys._MEIPASS, "citta"))
    if getattr(sys, "frozen", False):
        cands.append(os.path.join(os.path.dirname(sys.executable), "citta"))
    cands.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "citta"))
    cands.append(os.path.join(os.getcwd(), "citta"))
    for d in cands:
        p = os.path.join(d, name + ".json.gz")
        if os.path.exists(p):
            return p
    return None


def city_title(name):
    t = {"losangeles": "Los Angeles", "newyork": "New York", "sanfrancisco": "San Francisco"}.get(name)
    return t or name.replace("_", " ").title()


def list_cities():
    """nomi delle citta' vere disponibili (file citta/<nome>.json.gz)"""
    names = []
    dirs = []
    if getattr(sys, "_MEIPASS", None):
        dirs.append(os.path.join(sys._MEIPASS, "citta"))
    if getattr(sys, "frozen", False):
        dirs.append(os.path.join(os.path.dirname(sys.executable), "citta"))
    dirs.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "citta"))
    dirs.append(os.path.join(os.getcwd(), "citta"))
    for d in dirs:
        if os.path.isdir(d):
            for f in sorted(os.listdir(d)):
                if f.endswith(".json.gz") and f[:-8] not in names:
                    names.append(f[:-8])
    return names


def load_city_data(path):
    import gzip
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return json.load(f)


class RealWorld(StaticWorld):
    """collisioni: oltre a scatole e cilindri, edifici come prismi a base poligonale"""
    ECS = 8.0

    def __init__(self, L, limit):
        StaticWorld.__init__(self)
        self.limit = limit
        self.solids = []            # (anello esterno, buchi, z0, z1)
        self.eg = {}                # cella -> lati (ax, ay, bx, by, nx, ny, id)
        self.hb = Raster(L, 1.0, np.int16, -1)       # id dell'edificio a terra
        self.hh = Raster(L, 1.0, np.float32, 0.0)    # altezza del tetto

    def add_solid(self, outer, holes, z0, z1, raster=True):
        sid = len(self.solids)
        self.solids.append((outer, holes, z0, z1))
        cs = self.ECS
        for ring in [outer] + list(holes):
            n = len(ring)
            for i in range(n):
                ax, ay = float(ring[i][0]), float(ring[i][1])
                bx, by = float(ring[(i + 1) % n][0]), float(ring[(i + 1) % n][1])
                dx, dy = bx - ax, by - ay
                l = math.hypot(dx, dy)
                if l < 1e-3:
                    continue
                e = (ax, ay, bx, by, dy / l, -dx / l, sid)
                for ix in range(int(math.floor(min(ax, bx) / cs)), int(math.floor(max(ax, bx) / cs)) + 1):
                    for iy in range(int(math.floor(min(ay, by) / cs)), int(math.floor(max(ay, by) / cs)) + 1):
                        self.eg.setdefault((ix, iy), []).append(e)
        if raster and z0 < 2.5:
            rings = [outer] + list(holes)
            self.hb.fill_rings(rings, sid)
            self.hh.fill_rings(rings, z1, "max")
        return sid

    def hb_blocked(self, x, y):
        return self.hb.get(x, y, -1) >= 0

    def inside(self, sid, x, y):
        outer, holes, _z0, _z1 = self.solids[sid]
        if not point_in_ring(x, y, outer):
            return False
        for h in holes:
            if point_in_ring(x, y, h):
                return False
        return True

    def _edges_near(self, x0, y0, x1, y1):
        cs = self.ECS
        out = []
        for ix in range(int(math.floor(x0 / cs)), int(math.floor(x1 / cs)) + 1):
            for iy in range(int(math.floor(y0 / cs)), int(math.floor(y1 / cs)) + 1):
                l = self.eg.get((ix, iy))
                if l:
                    out.extend(l)
        return out

    def push_circle(self, x, y, z, r, h=1.8, step=0.55):
        hit = False
        nrm = (0.0, 0.0)
        solids = self.solids
        for _it in range(2):
            moved = False
            for (ax, ay, bx, by, nx, ny, sid) in self._edges_near(x - r, y - r, x + r, y + r):
                s = solids[sid]
                if z + step >= s[3] or z + h <= s[2]:
                    continue
                dx, dy = bx - ax, by - ay
                l2 = dx * dx + dy * dy
                t = ((x - ax) * dx + (y - ay) * dy) / l2
                t = 0.0 if t < 0 else (1.0 if t > 1 else t)
                cx, cy = ax + dx * t, ay + dy * t
                ex, ey = x - cx, y - cy
                d2 = ex * ex + ey * ey
                if d2 >= r * r:
                    continue
                if (x - ax) * nx + (y - ay) * ny >= 0:
                    d = math.sqrt(d2)
                    if d > 1e-6:
                        x, y = cx + ex / d * r, cy + ey / d * r
                        nrm = (ex / d, ey / d)
                    else:
                        x, y = cx + nx * r, cy + ny * r
                        nrm = (nx, ny)
                elif self.inside(sid, x, y):
                    x, y = cx + nx * r, cy + ny * r
                    nrm = (nx, ny)
                else:
                    continue
                hit = moved = True
            if not moved:
                break
        # dentro un edificio senza lati vicini (teletrasporto, spawn): esci dal lato piu' vicino
        sid = int(self.hb.get(x, y, -1))
        if sid >= 0:
            s = solids[sid]
            if not (z + step >= s[3] or z + h <= s[2]) and self.inside(sid, x, y):
                best = None
                for ring in [s[0]] + list(s[1]):
                    A = np.asarray(ring, np.float64)
                    B = np.roll(A, -1, axis=0)
                    D = B - A
                    l2 = np.maximum((D * D).sum(1), 1e-9)
                    t = np.clip(((x - A[:, 0]) * D[:, 0] + (y - A[:, 1]) * D[:, 1]) / l2, 0, 1)
                    C = A + D * t[:, None]
                    dd = (C[:, 0] - x) ** 2 + (C[:, 1] - y) ** 2
                    i = int(np.argmin(dd))
                    if best is None or dd[i] < best[0]:
                        l = math.sqrt(l2[i])
                        best = (dd[i], C[i, 0], C[i, 1], D[i, 1] / l, -D[i, 0] / l)
                if best is not None:
                    _d, cx, cy, nx, ny = best
                    x, y = cx + nx * (r + 0.05), cy + ny * (r + 0.05)
                    nrm = (nx, ny)
                    hit = True
        x, y, hit2, nrm2 = StaticWorld.push_circle(self, x, y, z, r, h, step)
        if hit2:
            return x, y, True, nrm2
        return x, y, hit, nrm

    def support(self, x, y, z, r=0.3):
        g = StaticWorld.support(self, x, y, z, r)
        hv = float(self.hh.get(x, y, 0.0))
        if g < hv <= z + 0.55:
            g = hv
        return g

    def raycast(self, ox, oy, oz, dx, dy, dz, maxd, ground=True):
        best = StaticWorld.raycast(self, ox, oy, oz, dx, dy, dz, maxd, ground)
        bt = best[0] if best else maxd
        h = self._ray_raster(ox, oy, oz, dx, dy, dz, bt)
        if h is not None and h[0] < bt:
            return h
        return best

    def _ray_raster(self, ox, oy, oz, dx, dy, dz, maxd):
        step = 0.5
        n = int(maxd / step) + 2
        t = np.minimum(np.arange(n, dtype=np.float64) * step, maxd)
        xs = ox + dx * t
        ys = oy + dy * t
        zs = oz + dz * t
        R = self.hh
        k = 1.0 / R.res
        ix = ((xs + R.L) * k).astype(np.int64)
        iy = ((ys + R.L) * k).astype(np.int64)
        ok = (ix >= 0) & (iy >= 0) & (ix < R.n) & (iy < R.n)
        H = np.where(ok, R.a[np.clip(iy, 0, R.n - 1), np.clip(ix, 0, R.n - 1)], 0.0)
        ins = zs < H - 0.02
        if not ins.any():
            return None
        enter = ins[1:] & ~ins[:-1]
        if not enter.any():
            return None
        i = int(np.argmax(enter)) + 1
        hv = float(H[i])
        if dz < -1e-6 and zs[i - 1] >= hv - 0.05:
            tr = (hv - oz) / dz
            if 0 <= tr <= maxd:
                return tr, (0, 0, 1)
        sid = int(self.hb.a[iy[i], ix[i]]) if ok[i] else -1
        t0, t1 = t[i - 1] - 1.0, t[i] + 1.0
        bestt = None
        bn = None
        cands = self._edges_near(min(xs[i - 1], xs[i]) - 1.5, min(ys[i - 1], ys[i]) - 1.5,
                                 max(xs[i - 1], xs[i]) + 1.5, max(ys[i - 1], ys[i]) + 1.5)
        for (ax, ay, bx, by, nx, ny, s_id) in cands:
            if sid >= 0 and s_id != sid:
                s = self.solids[s_id]
                if s[3] < hv - 0.5:
                    continue
            ex, ey = bx - ax, by - ay
            den = dx * ey - dy * ex
            if abs(den) < 1e-9:
                continue
            tt = ((ax - ox) * ey - (ay - oy) * ex) / den
            u = ((ax - ox) * dy - (ay - oy) * dx) / den
            if 0 <= u <= 1 and t0 <= tt <= t1 and (bestt is None or tt < bestt):
                if dx * nx + dy * ny < 0:
                    bestt, bn = tt, (nx, ny, 0)
        if bestt is not None:
            return max(0.0, bestt), bn
        l = math.hypot(dx, dy) or 1.0
        return float(t[i - 1]), (-dx / l, -dy / l, 0)


# ------------------------------------------------------------------ percorsi dei pedoni
class RectRing:
    """marciapiede ad anello attorno a un isolato rettangolare (citta' procedurale)"""
    closed = True

    def __init__(self, r):
        self.r = r
        x0, y0, x1, y1 = r
        self.length = 2 * ((x1 - x0) + (y1 - y0))
        self.center = ((x0 + x1) / 2, (y0 + y1) / 2)

    def point(self, p, o):
        x0, y0, x1, y1 = self.r
        w, hh = x1 - x0, y1 - y0
        p %= self.length
        if p < w:
            return x0 + p, y0 + o
        p -= w
        if p < hh:
            return x1 - o, y0 + p
        p -= hh
        if p < w:
            return x1 - p, y1 - o
        p -= w
        return x0 + o, y1 - p

    def project(self, x, y):
        x0, y0, x1, y1 = self.r
        w, hh = x1 - x0, y1 - y0
        cands = [(abs(y - y0), clamp(x - x0, 0, w)), (abs(x - x1), w + clamp(y - y0, 0, hh)),
                 (abs(y - y1), w + hh + clamp(x1 - x, 0, w)), (abs(x - x0), 2 * w + hh + clamp(y1 - y, 0, hh))]
        return min(cands)[1]


class PathRing:
    """percorso pedonale aperto (marciapiede tra due incroci, vialetto nel parco)"""
    closed = False

    def __init__(self, pts):
        self.pl = Polyline(pts)
        self.length = self.pl.L
        m = self.pl.at(self.length / 2)
        self.center = (m[0], m[1])
        self.ends = (tuple(self.pl.P[0]), tuple(self.pl.P[-1]))
        self.links = ([], [])

    def point(self, p, o):
        x, y, tx, ty = self.pl.at(p)
        return x + ty * o, y - tx * o

    def project(self, x, y):
        return self.pl.project(x, y)[0]


# ------------------------------------------------------------------ grafo stradale
class Chain:
    """tratto di strada tra due nodi del grafo"""
    __slots__ = ("id", "k", "pl", "n0", "n1", "ow", "lf", "lb", "hw", "park", "speed", "traffic", "trim",
                 "sw", "name", "lane_w", "group", "signal", "cut")

    def lane_offset(self, d, lane):
        """distanza laterale (a destra del senso di marcia) del centro della corsia"""
        if self.ow:
            n = self.lf
            return -n * self.lane_w / 2 + self.lane_w * (lane + 0.5)
        return 0.3 + self.lane_w * (lane + 0.5)

    def lanes(self, d):
        if self.ow:
            return self.lf if d > 0 else 0
        return self.lf if d > 0 else self.lb

    def point(self, d, lane, s):
        L = self.pl.L
        x, y, tx, ty = self.pl.at(s if d > 0 else L - s)
        if d < 0:
            tx, ty = -tx, -ty
        o = self.lane_offset(d, lane)
        return x + ty * o, y - tx * o, tx, ty


class RoadNet:
    def __init__(self):
        self.nodes = []          # (x, y)
        self.out = []            # nodo -> [(catena, verso)]
        self.chains = []
        self.signal = set()
        self.key2node = {}

    def node(self, key, x, y):
        i = self.key2node.get(key)
        if i is None:
            i = self.key2node[key] = len(self.nodes)
            self.nodes.append((x, y))
            self.out.append([])
        return i

    def finish(self):
        self.N = np.asarray(self.nodes, np.float64).reshape(-1, 2)
        self.traffic_nodes = np.array([i for i, o in enumerate(self.out)
                                       if any(self.chains[c].traffic for c, _d in o)], np.int64)
        samp = []
        for c in self.chains:
            if not c.traffic:
                continue
            n = max(1, int(c.pl.L // 25))
            for k in range(n):
                s = (k + 0.5) * c.pl.L / n
                x, y, _tx, _ty = c.pl.at(s)
                samp.append((x, y, c.id, s))
        self.samples = np.asarray(samp, np.float64).reshape(-1, 4)

    def end_node(self, c, d):
        ch = self.chains[c]
        return ch.n1 if d > 0 else ch.n0

    def nearest_node(self, x, y, traffic=True):
        idx = self.traffic_nodes if traffic and len(self.traffic_nodes) else np.arange(len(self.nodes))
        P = self.N[idx]
        i = int(np.argmin((P[:, 0] - x) ** 2 + (P[:, 1] - y) ** 2))
        return int(idx[i])

    def options(self, node, came=None, traffic=True):
        res = []
        for (c, d) in self.out[node]:
            ch = self.chains[c]
            if traffic and not ch.traffic:
                continue
            if ch.ow and d < 0:
                continue
            if came is not None and c == came[0] and d == -came[1]:
                continue
            res.append((c, d))
        return res

    def astar(self, a, b, max_iter=6000):
        import heapq
        N = self.N
        bx, by = N[b]
        openh = [(0.0, a)]
        g = {a: 0.0}
        prev = {a: None}
        it = 0
        while openh and it < max_iter:
            it += 1
            _f, n = heapq.heappop(openh)
            if n == b:
                break
            for (c, d) in self.out[n]:
                ch = self.chains[c]
                if not ch.traffic and ch.k != "service":
                    continue
                m = ch.n1 if d > 0 else ch.n0
                ng = g[n] + ch.pl.L
                if ng < g.get(m, 1e18):
                    g[m] = ng
                    prev[m] = (n, c, d)
                    hx, hy = N[m]
                    heapq.heappush(openh, (ng + math.hypot(hx - bx, hy - by), m))
        if b not in prev:
            return None
        steps = []
        n = b
        while prev[n] is not None:
            p, c, d = prev[n]
            steps.append((c, d))
            n = p
        steps.reverse()
        return steps


# =============================================================================
#  TEXTURE DELLA CITTA' VERA: facciate (texture array con rilievo e vetri), suoli
# =============================================================================
FPX = 512          # pixel per tessera di facciata (12 m x 12 m)


def _px(m, n=FPX):
    return int(round(m * n / 12.0))


def _streaks(seed, n=FPX, amount=0.12):
    """sporco verticale (colature della pioggia)"""
    rng = np.random.default_rng(seed)
    cols = rng.random(n // 4 + 2).astype(np.float32)
    x = np.linspace(0, len(cols) - 2, n)
    i = x.astype(int)
    f = x - i
    line = cols[i] * (1 - f) + cols[i + 1] * f
    v = value_noise(n, 6, seed + 3)
    s = (line[None, :] ** 3) * (0.4 + 0.6 * v)
    return 1.0 - s * amount


def _wall(seed, rgb, var=16, grain_amt=10, n=FPX, streak=0.10):
    nz = fbm(n, 6, 5, seed)
    g = grain((n, n), seed + 1, grain_amt)
    a = np.empty((n, n, 3), np.float32)
    for c in range(3):
        a[..., c] = rgb[c] + (nz - 0.5) * var * 2 + g
    a *= _streaks(seed + 5, n, streak)[..., None]
    return a


def _bricks(seed, rgb, n=FPX, mortar=(178, 170, 158), bh=8, bw=24):
    rng = np.random.default_rng(seed)
    a = np.zeros((n, n, 3), np.float32)
    H = np.zeros((n, n), np.float32)
    base = np.array(rgb, np.float32)
    for r in range(n // bh + 1):
        off = (r % 2) * (bw // 2)
        y0 = r * bh
        for c in range(-1, n // bw + 2):
            x0 = c * bw + off
            col = base * rng.uniform(0.82, 1.14) + rng.uniform(-6, 6)
            xa, xb = max(0, x0), min(n, x0 + bw - 2)
            if xb > xa:
                a[y0:y0 + bh - 2, xa:xb] = col
                H[y0:y0 + bh - 2, xa:xb] = 0.25
    m = H == 0
    a[m] = mortar
    a += (fbm(n, 8, 4, seed + 2)[..., None] - 0.5) * 26 + grain((n, n), seed + 4, 12)[..., None]
    a *= _streaks(seed + 9, n, 0.08)[..., None]
    return a, H


def _sky_glass(h, w, seed, tint=(1.0, 1.0, 1.0), dark=1.0):
    """vetro: riflesso del cielo + un po' di interno"""
    rng = np.random.default_rng(seed)
    gy = np.linspace(0, 1, max(h, 1))[:, None]
    base = np.stack([46 + 60 * (1 - gy), 58 + 72 * (1 - gy), 72 + 88 * (1 - gy)], -1) * dark
    base = np.broadcast_to(base, (h, w, 3)).copy()
    base *= np.array(tint, np.float32)
    base += rng.uniform(-6, 6)
    return base


class FacadePainter:
    """dipinge una facciata: albedo (rgb + riflessione), altezza (rilievo), maschera luci"""

    def __init__(self, alb, height=None, n=FPX):
        self.n = n
        self.A = alb.astype(np.float32)
        self.R = np.zeros((n, n), np.float32)      # riflessione (vetro)
        self.E = np.zeros((n, n), np.float32)      # maschera luci notturne
        self.H = np.zeros((n, n), np.float32) if height is None else height.astype(np.float32)

    def rect(self, x0, z0, x1, z1, col=None, h=None, refl=None, emit=None, add_h=False):
        """rettangolo in metri (x da sinistra, z dal basso della tessera)"""
        n = self.n
        c0, c1 = _px(x0, n), _px(x1, n)
        r0, r1 = n - _px(z1, n), n - _px(z0, n)
        c0, c1 = max(0, c0), min(n, c1)
        r0, r1 = max(0, r0), min(n, r1)
        if c1 <= c0 or r1 <= r0:
            return None
        if col is not None:
            col = np.asarray(col, np.float32)
            self.A[r0:r1, c0:c1] = col if col.ndim == 1 else col[:r1 - r0, :c1 - c0]
        if h is not None:
            if add_h:
                self.H[r0:r1, c0:c1] += h
            else:
                self.H[r0:r1, c0:c1] = h
        if refl is not None:
            self.R[r0:r1, c0:c1] = refl
        if emit is not None:
            self.E[r0:r1, c0:c1] = emit
        return (r0, r1, c0, c1)

    def window(self, x0, z0, x1, z1, frame_col, frame=0.07, seed=0, tint=(1, 1, 1), mull_v=1, mull_h=0,
               recess=-0.6, refl=1.0, blinds=0.35, dark=1.0):
        rng = np.random.default_rng(seed)
        self.rect(x0 - frame, z0 - frame, x1 + frame, z1 + frame, frame_col, 0.12)
        r = self.rect(x0, z0, x1, z1, None, recess, refl, 1.0)
        if r is None:
            return
        r0, r1, c0, c1 = r
        g = _sky_glass(r1 - r0, c1 - c0, seed, tint, dark)
        if rng.random() < blinds:          # tende o veneziane
            k = rng.uniform(0.25, 0.8)
            cut = int((r1 - r0) * k)
            ccol = np.array(rng.choice([(190, 182, 160), (220, 214, 200), (150, 70, 60), (120, 130, 150)]), np.float32)
            if rng.random() < 0.5:
                g[:cut] = g[:cut] * 0.35 + ccol * 0.65
                g[:cut:3] *= 0.85
            else:
                w = int((c1 - c0) * rng.uniform(0.2, 0.4))
                g[:, :w] = g[:, :w] * 0.3 + ccol * 0.7
        self.A[r0:r1, c0:c1] = g
        fw = max(1, _px(0.05, self.n))
        for k in range(1, mull_v + 1):
            mx = c0 + (c1 - c0) * k // (mull_v + 1)
            self.A[r0:r1, mx - fw // 2:mx + fw - fw // 2] = frame_col
            self.H[r0:r1, mx - fw // 2:mx + fw - fw // 2] = 0.05
            self.R[r0:r1, mx - fw // 2:mx + fw - fw // 2] = 0
        for k in range(1, mull_h + 1):
            my = r0 + (r1 - r0) * k // (mull_h + 1)
            self.A[my - fw // 2:my + fw - fw // 2, c0:c1] = frame_col
            self.H[my - fw // 2:my + fw - fw // 2, c0:c1] = 0.05
            self.R[my - fw // 2:my + fw - fw // 2, c0:c1] = 0

    def grid(self, bays, floors, ww, wh, sill, frame_col, seed, sill_col=None, lintel_col=None, **kw):
        cw, fh = 12.0 / bays, 12.0 / floors
        rng = np.random.default_rng(seed)
        for k in range(floors):
            for b in range(bays):
                cx = (b + 0.5) * cw
                z0 = k * fh + sill
                x0, x1 = cx - ww / 2, cx + ww / 2
                if sill_col is not None:
                    self.rect(x0 - 0.12, z0 - 0.16, x1 + 0.12, z0 - 0.04, sill_col, 0.35)
                if lintel_col is not None:
                    self.rect(x0 - 0.1, z0 + wh + 0.05, x1 + 0.1, z0 + wh + 0.28, lintel_col, 0.2)
                self.window(x0, z0, x1, z0 + wh, frame_col, seed=int(rng.integers(1 << 30)), **kw)

    def band(self, z0, z1, col, h=0.2, refl=None):
        self.rect(0, z0, 12, z1, col, h, refl)

    def finish(self, strength=3.0):
        """ritorna (albedo RGBA, normali RGBA) come uint8"""
        H = self.H
        gx = (np.roll(H, -1, 1) - np.roll(H, 1, 1)) * 0.5
        gr = (np.roll(H, -1, 0) - np.roll(H, 1, 0)) * 0.5
        nx = -gx * strength
        ny = gr * strength
        nz = np.ones_like(H)
        l = np.sqrt(nx * nx + ny * ny + nz * nz)
        N = np.stack([nx / l, ny / l, nz / l], -1)
        nrm = np.concatenate([(N * 0.5 + 0.5) * 255, self.E[..., None] * 255], -1)
        alb = np.concatenate([self.A, self.R[..., None] * 255], -1)
        return to_u8(alb), to_u8(nrm)


def _fac_curtain(seed, tint, frame_col, bays=8, spandrel_col=None, dark=1.0):
    n = FPX
    rng = np.random.default_rng(seed)
    p = FacadePainter(np.zeros((n, n, 3), np.float32))
    fh = 3.0
    for k in range(4):
        z0 = k * fh
        # vetro della fascia del solaio (non trasparente, riflette)
        sc = spandrel_col if spandrel_col is not None else np.array(tint) * np.array([40, 48, 58]) * dark
        p.rect(0, z0, 12, z0 + 0.85, sc, 0.0, 0.85, 0.0)
        g = p.rect(0, z0 + 0.85, 12, z0 + fh, None, -0.15, 1.0, 1.0)
        r0, r1, c0, c1 = g
        p.A[r0:r1, c0:c1] = _sky_glass(r1 - r0, c1 - c0, int(rng.integers(1 << 30)), tint, dark)
        # interni: qualche ufficio con le veneziane
        for b in range(bays):
            if rng.random() < 0.3:
                x0 = b * 12.0 / bays
                q = p.rect(x0, z0 + 2.0, x0 + 12.0 / bays, z0 + fh)
                if q:
                    a0, a1, b0, b1 = q
                    p.A[a0:a1, b0:b1] = p.A[a0:a1, b0:b1] * 0.6 + np.array([170, 170, 165]) * 0.4
                    p.A[a0:a1:3, b0:b1] *= 0.8
        p.rect(0, z0 + 0.82, 12, z0 + 0.9, frame_col, 0.1, 0.2, 0.0)
    for b in range(bays + 1):
        x = b * 12.0 / bays
        p.rect(x - 0.05, 0, x + 0.05, 12, frame_col, 0.18, 0.3, 0.0)
    p.H += grain((n, n), seed, 0.02)
    return p


def _fac_ribbon(seed):
    """uffici anni '60-'70: fasce di cemento e finestre a nastro"""
    n = FPX
    p = FacadePainter(_wall(seed, (184, 180, 170), 14, 8))
    rng = np.random.default_rng(seed)
    for k in range(4):
        z0 = k * 3.0
        g = p.rect(0, z0 + 1.0, 12, z0 + 2.7, None, -0.5, 0.9, 1.0)
        r0, r1, c0, c1 = g
        p.A[r0:r1, c0:c1] = _sky_glass(r1 - r0, c1 - c0, int(rng.integers(1 << 30)), (0.85, 0.95, 1.0), 0.85)
        for b in range(9):
            x = b * 1.5
            p.rect(x - 0.04, z0 + 1.0, x + 0.04, z0 + 2.7, (60, 62, 66), -0.2, 0.0)
        p.rect(0, z0 + 0.95, 12, z0 + 1.02, (150, 146, 138), 0.3)
        p.rect(0, z0 + 2.7, 12, z0 + 2.76, (150, 146, 138), 0.3)
    return p


def _fac_precast(seed):
    """griglia di pannelli prefabbricati con finestre incassate"""
    p = FacadePainter(_wall(seed, (196, 190, 178), 12, 8))
    p.grid(4, 4, 2.2, 1.9, 0.75, (80, 82, 86), seed, recess=-1.0, mull_v=1, dark=0.9, blinds=0.45)
    for b in range(5):
        p.rect(b * 3.0 - 0.18, 0, b * 3.0 + 0.18, 12, (206, 200, 188), 0.5, add_h=False)
    for k in range(5):
        p.rect(0, k * 3.0 - 0.12, 12, k * 3.0 + 0.12, (206, 200, 188), 0.5)
    return p


def _fac_classic(seed, rgb, frame_col):
    """palazzo storico in pietra/terracotta (centro storico di LA)"""
    p = FacadePainter(_wall(seed, rgb, 14, 10, streak=0.16))
    rng = np.random.default_rng(seed)
    p.grid(4, 4, 1.25, 1.95, 0.8, frame_col, seed, sill_col=np.array(rgb) * 1.08,
           lintel_col=np.array(rgb) * 0.92, mull_v=0, mull_h=1, recess=-1.2, dark=0.85, blinds=0.5)
    for b in range(5):     # lesene
        p.rect(b * 3.0 - 0.22, 0, b * 3.0 + 0.22, 12, np.array(rgb) * 1.05, 0.45)
    for k in range(4):     # cornice marcapiano
        p.rect(0, k * 3.0 - 0.06, 12, k * 3.0 + 0.1, np.array(rgb) * 0.9, 0.55)
    del rng
    return p


def _fac_brick(seed, rgb):
    a, H = _bricks(seed, rgb)
    p = FacadePainter(a, H)
    p.grid(4, 4, 1.35, 1.85, 0.85, (232, 228, 218), seed, sill_col=(196, 190, 178), lintel_col=(180, 170, 158),
           mull_v=0, mull_h=1, recess=-1.0, blinds=0.45)
    return p


def _fac_stucco(seed, rgb, frame_col=(250, 250, 246), balcony=False):
    """palazzine residenziali di Los Angeles (intonaco)"""
    p = FacadePainter(_wall(seed, rgb, 10, 9, streak=0.12))
    rng = np.random.default_rng(seed)
    for k in range(4):
        for b in range(4):
            cx = 1.5 + b * 3.0
            z0 = k * 3.0 + 0.9
            wide = (b % 2 == 0) and rng.random() < 0.4
            ww = 1.9 if wide else 1.2
            p.window(cx - ww / 2, z0, cx + ww / 2, z0 + 1.45, frame_col, seed=int(rng.integers(1 << 30)),
                     mull_v=1, recess=-0.7, blinds=0.6)
            if balcony and b % 2 == 0:
                p.rect(cx - 1.3, z0 - 0.9, cx + 1.3, z0 - 0.7, np.array(rgb) * 0.85, 0.9)
                p.rect(cx - 1.3, z0 - 0.7, cx + 1.3, z0 + 0.1, (70, 72, 76), 0.6)
                for k2 in range(14):
                    xx = cx - 1.25 + k2 * 0.19
                    p.rect(xx, z0 - 0.7, xx + 0.04, z0 + 0.1, (40, 40, 44), 0.7)
                p.rect(cx - 1.3, z0 + 0.08, cx + 1.3, z0 + 0.14, (40, 40, 44), 0.7)
    return p


def _fac_modern_apt(seed):
    p = FacadePainter(_wall(seed, (120, 124, 128), 8, 6, streak=0.05))
    rng = np.random.default_rng(seed)
    for b in range(4):      # pannelli di colore diverso
        col = np.array(rng.choice([(200, 196, 188), (110, 114, 120), (176, 120, 86), (230, 228, 222)]), np.float32)
        p.rect(b * 3.0, 0, b * 3.0 + 3.0, 12, col * rng.uniform(0.92, 1.05), 0.1)
    p.grid(4, 4, 2.4, 2.25, 0.35, (40, 42, 46), seed, mull_v=1, recess=-0.5, dark=0.8, blinds=0.5)
    for k in range(4):
        p.rect(0, k * 3.0, 12, k * 3.0 + 0.22, (90, 92, 96), 0.7)
    return p


def _fac_industrial(seed):
    """lamiera ondulata con finestre a nastro in alto"""
    n = FPX
    a = _wall(seed, (168, 172, 170), 10, 6, streak=0.2)
    x = np.arange(n)
    wave = 0.5 + 0.5 * np.sin(x * 2 * np.pi / 10.0)
    a *= (0.88 + 0.12 * wave)[None, :, None]
    H = np.broadcast_to(wave[None, :] * 0.3, (n, n)).copy()
    p = FacadePainter(a, H)
    rng = np.random.default_rng(seed)
    for k in range(2):
        z0 = k * 6.0 + 4.3
        g = p.rect(0.3, z0, 11.7, z0 + 1.0, None, -0.4, 0.7, 1.0)
        r0, r1, c0, c1 = g
        p.A[r0:r1, c0:c1] = _sky_glass(r1 - r0, c1 - c0, int(rng.integers(1 << 30)), (0.9, 1.0, 0.95), 0.9)
        for b in range(9):
            xx = 0.3 + b * 1.425
            p.rect(xx - 0.04, z0, xx + 0.04, z0 + 1.0, (70, 74, 72), 0.1, 0.0)
    for b in range(5):
        p.rect(b * 3.0 - 0.08, 0, b * 3.0 + 0.08, 12, (120, 124, 122), 0.4)
    return p


def _fac_warehouse(seed):
    """vecchio magazzino in mattoni con grandi finestre a quadretti (Arts District)"""
    a, H = _bricks(seed, (140, 74, 54), bh=8, bw=26)
    p = FacadePainter(a, H)
    rng = np.random.default_rng(seed)
    for k in range(2):
        for b in range(3):
            cx = 2.0 + b * 4.0
            z0 = k * 6.0 + 1.6
            p.rect(cx - 1.6, z0 + 3.2, cx + 1.6, z0 + 3.5, (150, 120, 100), 0.3)
            p.window(cx - 1.4, z0, cx + 1.4, z0 + 3.1, (52, 58, 56), seed=int(rng.integers(1 << 30)),
                     mull_v=4, mull_h=5, recess=-1.0, dark=0.75, blinds=0.1)
            p.rect(cx - 1.55, z0 - 0.2, cx + 1.55, z0 - 0.05, (170, 160, 150), 0.4)
    return p


def _fac_parking(seed):
    """parcheggio multipiano: solai aperti"""
    n = FPX
    p = FacadePainter(_wall(seed, (178, 176, 170), 12, 8, streak=0.18))
    rng = np.random.default_rng(seed)
    for k in range(4):
        z0 = k * 3.0
        g = p.rect(0, z0 + 1.05, 12, z0 + 2.75, None, -2.0, 0.0, 0.8)
        r0, r1, c0, c1 = g
        gy = np.linspace(0, 1, r1 - r0)[:, None, None]
        inner = 22 + 30 * gy + rng.uniform(-4, 4)
        p.A[r0:r1, c0:c1] = np.broadcast_to(inner, (r1 - r0, c1 - c0, 1))
        # auto parcheggiate intraviste
        for b in range(8):
            if rng.random() < 0.6:
                x = b * 1.5 + 0.2
                col = np.array(rng.choice([(150, 30, 30), (200, 200, 205), (30, 30, 34), (40, 60, 120), (120, 120, 124)]))
                p.rect(x, z0 + 1.05, x + 1.1, z0 + 1.6, col * 0.5, -1.5)
        p.rect(0, z0 + 0.95, 12, z0 + 1.05, (120, 120, 116), 0.2)
    for b in range(3):
        p.rect(b * 4.0 + 1.8, 0, b * 4.0 + 2.2, 12, (186, 184, 178), 0.5)
    return p


def _fac_plain(seed, rgb):
    p = FacadePainter(_wall(seed, rgb, 14, 10, streak=0.16))
    for k in range(4):
        p.rect(0, k * 3.0 - 0.04, 12, k * 3.0 + 0.04, np.array(rgb) * 0.9, -0.1)
    return p


def _fac_shop(seed):
    """piano terra con negozi: 3 vetrine da 4 m nei 4.5 m in basso della tessera"""
    rng = np.random.default_rng(seed)
    wall_rgb = rng.choice([(200, 190, 170), (150, 146, 140), (120, 70, 56), (230, 226, 214)])
    p = FacadePainter(_wall(seed, wall_rgb, 12, 8))
    for u in range(3):
        x0 = u * 4.0
        sign = np.array(rng.choice([(190, 36, 36), (36, 80, 170), (230, 180, 40), (36, 130, 76), (140, 50, 150),
                                    (24, 24, 26), (230, 230, 226)]), np.float32)
        # insegna (si accende di notte)
        p.rect(x0 + 0.15, 3.55, x0 + 3.85, 4.25, sign, 0.4, 0.0, 0.9)
        for k in range(int(rng.integers(3, 7))):
            lx = x0 + 0.5 + k * 0.48
            if lx + 0.3 < x0 + 3.6:
                p.rect(lx, 3.7, lx + 0.3, 4.1, (250, 250, 244) if sign.sum() < 600 else (30, 30, 30), 0.45, 0.0, 1.0)
        # tenda da sole
        if rng.random() < 0.5:
            c1 = np.array(rng.choice([(190, 46, 46), (36, 100, 56), (36, 64, 130), (210, 150, 40)]), np.float32)
            for k in range(10):
                xx = x0 + 0.1 + k * 0.38
                p.rect(xx, 3.1, xx + 0.38, 3.5, c1 if k % 2 == 0 else (236, 236, 230), 0.8)
        # vetrina e porta
        p.window(x0 + 0.25, 0.35, x0 + 2.65, 3.0, (40, 40, 42), seed=int(rng.integers(1 << 30)), mull_v=1,
                 recess=-0.4, blinds=0.0, dark=1.15)
        q = p.rect(x0 + 0.35, 0.45, x0 + 2.55, 2.0)
        if q:          # merce in vetrina
            a0, a1, b0, b1 = q
            p.A[a0:a1, b0:b1] = p.A[a0:a1, b0:b1] * 0.55 + np.array(rng.choice(
                [(220, 190, 150), (200, 200, 210), (230, 170, 170), (170, 210, 170)]), np.float32) * 0.45
        p.window(x0 + 2.95, 0.0, x0 + 3.75, 2.5, (36, 36, 38), seed=int(rng.integers(1 << 30)), mull_v=0,
                 recess=-0.6, blinds=0.0)
        p.rect(x0, 0, x0 + 0.08, 4.5, (90, 88, 84), 0.3)
    p.rect(0, 0, 12, 0.3, (110, 108, 104), 0.2)
    p.rect(0, 4.35, 12, 4.55, (170, 166, 158), 0.6)
    return p


def _fac_house(seed):
    """casa unifamiliare: assi di legno orizzontali"""
    rng = np.random.default_rng(seed)
    col = np.array(rng.choice([(232, 220, 196), (190, 206, 216), (220, 196, 166), (206, 214, 190), (240, 240, 232),
                               (226, 210, 160)]), np.float32)
    n = FPX
    a = np.zeros((n, n, 3), np.float32)
    a[:] = col
    H = np.zeros((n, n), np.float32)
    plank = 8
    for y in range(0, n, plank):
        a[y:y + 1] = col * 0.72
        H[y:y + plank] = np.linspace(0, 0.3, plank)[:min(plank, n - y), None]
    a += grain((n, n), seed, 8)[..., None]
    p = FacadePainter(a, H)
    for k in range(4):
        for b in range(3):
            cx = 2.0 + b * 4.0
            z0 = k * 3.0 + 0.9
            p.rect(cx - 0.95, z0 - 0.08, cx - 0.72, z0 + 1.5, col * 0.55, 0.3)
            p.rect(cx + 0.72, z0 - 0.08, cx + 0.95, z0 + 1.5, col * 0.55, 0.3)
            p.window(cx - 0.65, z0, cx + 0.65, z0 + 1.45, (250, 250, 248), seed=int(rng.integers(1 << 30)), mull_v=1,
                     mull_h=1, frame=0.09, recess=-0.5, blinds=0.5)
    return p


# (nome, costruttore, finestre per tessera (u), piani per tessera (v), probabilita' luce, riflessione vetri, tipo luce)
FACADE_DEFS = [
    ("vetro_blu", lambda s: _fac_curtain(s, (0.82, 1.0, 1.12), (150, 160, 172)), 8, 4, 0.3, 0.95, 0),
    ("vetro_scuro", lambda s: _fac_curtain(s, (0.7, 0.74, 0.8), (44, 46, 50), dark=0.75), 8, 4, 0.28, 1.0, 0),
    ("vetro_bronzo", lambda s: _fac_curtain(s, (1.15, 0.92, 0.7), (90, 74, 56), bays=6), 6, 4, 0.28, 0.9, 0),
    ("uffici_nastro", _fac_ribbon, 8, 4, 0.3, 0.7, 0),
    ("uffici_griglia", _fac_precast, 4, 4, 0.3, 0.55, 0),
    ("pietra", lambda s: _fac_classic(s, (206, 192, 162), (60, 54, 48)), 4, 4, 0.32, 0.4, 0),
    ("terracotta", lambda s: _fac_classic(s, (226, 214, 190), (110, 100, 86)), 4, 4, 0.32, 0.4, 0),
    ("mattoni_rossi", lambda s: _fac_brick(s, (150, 68, 50)), 4, 4, 0.35, 0.35, 0),
    ("mattoni_bruni", lambda s: _fac_brick(s, (118, 80, 60)), 4, 4, 0.35, 0.35, 0),
    ("intonaco_crema", lambda s: _fac_stucco(s, (226, 212, 180)), 4, 4, 0.4, 0.35, 0),
    ("intonaco_bianco", lambda s: _fac_stucco(s, (236, 234, 226), (90, 92, 96), balcony=True), 4, 4, 0.4, 0.35, 0),
    ("intonaco_pesca", lambda s: _fac_stucco(s, (230, 186, 158), balcony=True), 4, 4, 0.4, 0.35, 0),
    ("appartamenti_moderni", _fac_modern_apt, 4, 4, 0.42, 0.6, 0),
    ("capannone", _fac_industrial, 8, 2, 0.25, 0.4, 2),
    ("magazzino_mattoni", _fac_warehouse, 3, 2, 0.3, 0.35, 0),
    ("parcheggio", _fac_parking, 1, 4, 0.92, 0.0, 2),
    ("cemento", lambda s: _fac_plain(s, (178, 176, 170)), 4, 4, 0.0, 0.0, 0),
    ("stucco", lambda s: _fac_plain(s, (214, 200, 172)), 4, 4, 0.0, 0.0, 0),
    ("negozi0", _fac_shop, 3, 1, 0.85, 0.6, 1),
    ("negozi1", _fac_shop, 3, 1, 0.85, 0.6, 1),
    ("negozi2", _fac_shop, 3, 1, 0.85, 0.6, 1),
    ("casa0", _fac_house, 3, 4, 0.5, 0.35, 0),
    ("casa1", _fac_house, 3, 4, 0.5, 0.35, 0),
    ("casa2", _fac_house, 3, 4, 0.5, 0.35, 0),
]
FACADE_INDEX = {d[0]: i for i, d in enumerate(FACADE_DEFS)}


def make_texture_array(layers, name, size):
    """layers: lista di array (size, size, 4) uint8"""
    tex = Texture(name)
    tex.setup2dTextureArray(size, size, len(layers), Texture.T_unsigned_byte, Texture.F_rgba8)
    data = b"".join(np.ascontiguousarray(l[::-1]).tobytes() for l in layers)
    tex.setRamImageAs(data, "RGBA")
    tex.setWrapU(SamplerState.WM_repeat)
    tex.setWrapV(SamplerState.WM_repeat)
    tex.setMinfilter(SamplerState.FT_linear_mipmap_linear)
    tex.setMagfilter(SamplerState.FT_linear)
    tex.setAnisotropicDegree(8)
    return tex


def _half(a):
    a = a.astype(np.float32)
    return to_u8((a[0::2, 0::2] + a[1::2, 0::2] + a[0::2, 1::2] + a[1::2, 1::2]) * 0.25)


def build_facade_arrays(size=FPX, progress=None):
    albs, nrms = [], []
    for i, d in enumerate(FACADE_DEFS):
        p = d[1](1000 + i * 37)
        a, n = p.finish()
        if size < FPX:
            a, n = _half(a), _half(n)
        albs.append(a)
        nrms.append(n)
        if progress:
            progress((i + 1) / len(FACADE_DEFS))
    grid = PTA_LVecBase4f.emptyArray(32)
    info = PTA_LVecBase4f.emptyArray(32)
    for i, d in enumerate(FACADE_DEFS):
        grid.setElement(i, LVecBase4f(d[2], d[3], d[4], d[5]))
        info.setElement(i, LVecBase4f(d[6], 0, 0, 0))
    return make_texture_array(albs, "facciate", size), make_texture_array(nrms, "facciate_rilievo", size), grid, info


# ------------------------------------------------------------------ suoli e tetti
def tex_concrete_walk(size=512, seed=21):
    """marciapiede di cemento di LA: lastre da 1.5 m con giunti"""
    n = fbm(size, 8, 5, seed)
    g = grain((size, size), seed + 1, 14)
    base = 150 + n * 22 + g
    yy, xx = np.mgrid[0:size, 0:size]
    tile = size // 4
    seam = ((xx % tile) < 2) | ((yy % tile) < 2)
    base = np.where(seam, base - 38, base)
    stains = fbm(size, 4, 4, seed + 11)
    base -= np.clip(stains - 0.58, 0, 1) * 90
    gum = np.random.default_rng(seed).random((size, size)) > 0.9985
    base -= gum * 40
    return to_u8(np.stack([base + 2, base, base - 5], -1))


def tex_pavers(size=512, seed=22):
    """piazza pedonale: mattonelle"""
    rng = np.random.default_rng(seed)
    a = np.zeros((size, size, 3), np.float32)
    t = 32
    for r in range(size // t):
        for c in range(size // t):
            v = rng.uniform(0.85, 1.12)
            col = np.array(rng.choice([(196, 180, 160), (180, 168, 150), (206, 196, 180)])) * v
            a[r * t:(r + 1) * t - 2, c * t:(c + 1) * t - 2] = col
    a[a.sum(-1) == 0] = (120, 112, 104)
    a += grain((size, size), seed, 10)[..., None]
    return to_u8(a)


def tex_lot_asphalt(size=512, seed=23):
    a = tex_asphalt(size, seed).astype(np.float32)
    a = a * 1.12 + 10
    return to_u8(a)


def tex_dirt(size=256, seed=24):
    n = fbm(size, 8, 5, seed)
    g = grain((size, size), seed, 30)
    base = 120 + n * 40 + g
    return to_u8(np.stack([base + 20, base + 4, base - 16], -1))


def tex_membrane(size=256, seed=25):
    """tetto piatto: guaina chiara con giunti"""
    n = fbm(size, 8, 4, seed)
    g = grain((size, size), seed, 10)
    base = 186 + n * 26 + g
    yy, xx = np.mgrid[0:size, 0:size]
    seam = (xx % 64) < 2
    base = np.where(seam, base - 22, base)
    dirt = fbm(size, 3, 3, seed + 3)
    base -= np.clip(dirt - 0.5, 0, 1) * 70
    return to_u8(np.stack([base, base, base - 2], -1))


def tex_rail(size=256, seed=26):
    a = tex_gravel(size, seed).astype(np.float32) * 0.8
    for k in range(0, size, 32):
        a[:, k:k + 10] = (96, 72, 54)
    return to_u8(a)


def tex_water(size=256, seed=27):
    n = fbm(size, 6, 5, seed)
    return to_u8(np.stack([40 + n * 20, 70 + n * 26, 86 + n * 30], -1))


def tex_helipad(size=256):
    a = np.zeros((size, size, 3), np.float32)
    a[:] = (70, 74, 70)
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    c = size / 2
    r = np.sqrt((xx - c) ** 2 + (yy - c) ** 2)
    ring = (r > size * 0.40) & (r < size * 0.44)
    a[ring] = (240, 240, 236)
    s = size
    hb = ((np.abs(xx - c + s * 0.12) < s * 0.03) | (np.abs(xx - c - s * 0.12) < s * 0.03)) & (np.abs(yy - c) < s * 0.18)
    hc = (np.abs(yy - c) < s * 0.03) & (np.abs(xx - c) < s * 0.12)
    a[hb | hc] = (240, 240, 236)
    a += grain((size, size), 3, 10)[..., None]
    return to_u8(a)


def tex_palm(size=128, seed=28):
    """fronda di palma (RGBA, foglie su fondo trasparente)"""
    rng = np.random.default_rng(seed)
    a = np.zeros((size, size, 4), np.float32)
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    v = yy / size
    u = xx / size
    rib = np.abs(u - 0.5) < 0.02
    leaf_w = 0.48 * np.sin(np.clip(v, 0, 1) * np.pi) ** 0.7
    teeth = (np.sin(v * 70) > -0.2)
    inside = (np.abs(u - 0.5) < leaf_w) & teeth
    g = 0.75 + 0.25 * rng.random((size, size))
    a[..., 0] = 70 * g
    a[..., 1] = 112 * g
    a[..., 2] = 52 * g
    a[..., 3] = np.where(inside | rib, 255, 0)
    a[rib, 0:3] = (120, 116, 70)
    return to_u8(a)


# =============================================================================
#  CITTA' VERA: costruzione 3D dai dati di OpenStreetMap
# =============================================================================
ROAD_DEF = {  # classe: (corsie, larghezza corsia, marciapiede, sosta ai lati, velocita' m/s, traffico)
    "motorway": (6, 3.6, 0.0, False, 25.0, 1.0),
    "trunk": (4, 3.5, 3.0, False, 17.0, 1.0),
    "primary": (4, 3.3, 3.4, True, 14.0, 1.0),
    "secondary": (4, 3.2, 3.2, True, 13.0, 0.9),
    "tertiary": (2, 3.3, 2.8, True, 12.0, 0.7),
    "unclassified": (2, 3.2, 2.4, True, 10.0, 0.5),
    "residential": (2, 3.2, 2.4, True, 9.5, 0.5),
    "living_street": (2, 3.0, 2.0, False, 6.0, 0.2),
    "road": (2, 3.2, 2.4, True, 9.0, 0.4),
    "motorway_link": (1, 4.0, 0.0, False, 15.0, 0.6),
    "trunk_link": (1, 4.0, 0.0, False, 13.0, 0.5),
    "primary_link": (1, 4.0, 2.4, False, 11.0, 0.5),
    "secondary_link": (1, 4.0, 2.4, False, 10.0, 0.5),
    "tertiary_link": (1, 4.0, 2.4, False, 10.0, 0.5),
    "service": (1, 4.5, 0.0, False, 6.0, 0.0),
}
ONEWAY_LANES = {"motorway": 3, "trunk": 2, "primary": 3, "secondary": 3, "tertiary": 2}
PATH_W = {"footway": 2.6, "path": 2.0, "cycleway": 2.2, "pedestrian": 6.0, "steps": 2.6, "track": 3.0,
          "bridleway": 2.0}
HOUSE_KINDS = {"house", "detached", "semidetached_house", "bungalow", "terrace", "cabin", "farm"}
CSS_COL = {"white": (240, 240, 236), "grey": (150, 150, 150), "gray": (150, 150, 150), "black": (50, 50, 52),
           "red": (170, 70, 60), "brown": (130, 90, 64), "beige": (220, 205, 175), "yellow": (230, 210, 120),
           "tan": (210, 180, 140), "blue": (110, 140, 180), "green": (120, 150, 110), "silver": (190, 192, 196),
           "orange": (220, 140, 80), "pink": (230, 180, 180), "cream": (240, 230, 200), "maroon": (120, 50, 50),
           "lightgrey": (200, 200, 200), "darkgrey": (90, 90, 92), "ivory": (245, 240, 220), "sandybrown": (230, 170, 110)}


def parse_colour(s):
    if not s:
        return None
    s = s.strip().lower().replace(" ", "")
    if s.startswith("#"):
        h = s[1:]
        try:
            if len(h) == 3:
                return tuple(int(c * 2, 16) for c in h)
            if len(h) == 6:
                return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
        except ValueError:
            return None
    return CSS_COL.get(s)


def _num(v, default=None):
    if v is None:
        return default
    try:
        return float(str(v).split(";")[0].replace(",", ".").split()[0].rstrip("m"))
    except (ValueError, IndexError):
        return default


def offset_ring(P, d):
    P = np.asarray(P, np.float64)
    Pc = np.vstack([P[-1:], P, P[:1]])
    return offset_line(Pc, d)[1:-1]


class RealCity:
    TILE = 320.0
    LOD_FAR = 620.0
    CACHE_VER = 4

    def __init__(self, env, data, quality=1, progress=None, cache_key=None):
        self.env = env
        self.q = quality
        self.prog = progress or (lambda f, msg="": None)
        self.font = None
        self.signs = []
        self.sign_specs = []
        if cache_key and self._load_cache(cache_key):
            GROUND_FN[0] = self.ground
            return
        if callable(data):
            data = data()
        self.data = data
        S = data.get("scala", 0.1)
        self.S = S
        self.R = R = float(data.get("raggio", 1300.0))
        self.limit = R - 30.0
        self.map_r = R
        self.CL = R + 160.0
        self.name = data.get("nome", "citta")
        self.rng = random.Random(4242)
        L = R + 200.0
        self.world = RealWorld(L, self.limit)
        self.gt = Raster(L, 1.0, np.uint8, 0)       # 1 strada, 2 marciapiede, 3 verde, 4 acqua, 5 parcheggio, 6 piazza
        self.rid = Raster(L, 1.0, np.int32, -1)     # id della catena stradale
        self.cnt = Raster(L, 1.0, np.uint8, 0)      # quante strade coprono la cella
        self.tiles = {}
        self.lamps = []
        self.spots = {}
        self.parking = []
        self.ped_rings = []
        self.rooftops = []
        self.net = RoadNet()
        self.prog(0.02, "Texture delle facciate")
        self._textures()
        self.prog(0.12, "Edifici")
        self._load_buildings()
        for b in self.blds:
            self._building(b)
        self.prog(0.30, "Strade")
        self._roads()
        self.prog(0.50, "Marciapiedi e segnaletica")
        self._road_details()
        self.prog(0.62, "Parchi e piazze")
        self._areas()
        self._paths()
        self.prog(0.70, "Luoghi di Rick and Morty")
        self._template_meshes()
        self._places()
        self.prog(0.76, "Alberi, lampioni, semafori")
        self._props()
        self._link_ped()
        self.prog(0.84, "Periferia e colline")
        self._outskirts()
        self.root = env.root.attachNewNode("citta")
        self.prog(0.90, "Preparo la grafica")
        self._finalize()
        self.map_img = self._make_map()
        self.net.finish()
        self._lamp_grid()
        GROUND_FN[0] = self.ground
        self.data = None
        if cache_key:
            self.prog(0.97, "Salvo la citta' per i prossimi avvii")
            self._save_cache(cache_key)

    # ------------------------------------------------------------------ utilita'
    def ground(self, x, y):
        return CURB if self.gt.get(x, y) == 2 else 0.0

    def M(self, key, x, y):
        ck = (int(math.floor(x / self.TILE)), int(math.floor(y / self.TILE)))
        d = self.tiles.setdefault(ck, {})
        m = d.get(key)
        if m is None:
            m = d[key] = Mesh()
        return m

    def free(self, x, y, roads_ok=False):
        if self.world.hb.get(x, y, -1) >= 0:
            return False
        g = self.gt.get(x, y, 0)
        if g == 4:
            return False
        if g == 1 and not roads_ok:
            return False
        return max(abs(x), abs(y)) < self.limit - 5

    def free_point_near(self, x, y, roads_ok=False, rmax=120.0):
        if self.free(x, y, roads_ok):
            return (x, y)
        for r in np.arange(2.0, rmax, 2.0):
            for k in range(int(6 + r)):
                a = k / (6 + r) * TAU
                px, py = x + math.cos(a) * r, y + math.sin(a) * r
                if self.free(px, py, roads_ok) and self.free(px + 1.2, py, roads_ok) and self.free(px, py + 1.2, roads_ok) \
                        and self.free(px - 1.2, py, roads_ok) and self.free(px, py - 1.2, roads_ok):
                    return (px, py)
        return (x, y)

    # ------------------------------------------------------------------ texture
    def _textures(self):
        hq = self.q >= 1
        self.fac_alb, self.fac_nrm, self.fac_grid, self.fac_info = build_facade_arrays(FPX if hq else FPX // 2)
        T = {}
        E = {}
        T["asphalt"] = make_texture(tex_asphalt(512 if hq else 256), "asfalto")
        T["walk"] = make_texture(tex_concrete_walk(512 if hq else 256), "marciapiede")
        T["pavers"] = make_texture(tex_pavers(), "piazza")
        T["lot"] = make_texture(tex_lot_asphalt(256), "parcheggio")
        T["grass"] = make_texture(tex_grass(), "erba")
        T["dirt"] = make_texture(tex_dirt(), "terra")
        T["gravel"] = make_texture(tex_gravel(), "ghiaia")
        T["water"] = make_texture(tex_water(), "acqua")
        T["rail"] = make_texture(tex_rail(), "binari")
        T["roof"] = make_texture(tex_membrane(), "tetto")
        T["roof2"] = make_texture(tex_roof(), "tetto2")
        T["shingles"] = make_texture(tex_shingles(), "tegole")
        T["helipad"] = make_texture(tex_helipad(), "eliporto", repeat=False)
        T["garage"] = make_texture(tex_garage(), "garage")
        T["field"] = make_texture(tex_field(), "campo")
        g = (tex_concrete_walk(256, 31).astype(np.float32) * 0.55 + tex_dirt(256, 32).astype(np.float32) * 0.45)
        T["ground"] = make_texture(to_u8(g * 0.92), "suolo")
        for i in range(4):
            a, e = tex_house(400 + i)
            T["house%d" % i] = make_texture(a, "casa")
            E["house%d" % i] = make_texture(e, "casa_luci")
        lamp_e = np.zeros((4, 4, 3), np.uint8)
        lamp_e[:] = (255, 230, 180)
        E["lamp"] = make_texture(lamp_e, "lampada", mipmap=False)
        self.T, self.E = T, E
        self.MAT = {
            "asphalt": (0.30, 40, 0.06, 0), "walk": (0.12, 20, 0.0, 0), "pavers": (0.15, 24, 0.02, 0),
            "lot": (0.25, 36, 0.04, 0), "grass": (0.04, 8, 0.0, 0), "dirt": (0.05, 8, 0.0, 0),
            "gravel": (0.05, 10, 0.0, 0), "water": (1.2, 160, 0.85, 0), "rail": (0.2, 30, 0.0, 0),
            "roof": (0.10, 12, 0.0, 0), "roof2": (0.08, 10, 0.0, 0), "shingles": (0.15, 20, 0.02, 0),
            "helipad": (0.2, 20, 0.0, 0), "garage": (0.25, 30, 0.04, 0), "field": (0.04, 8, 0, 0),
            "props": (0.3, 30, 0.05, 0), "marks": (0.3, 30, 0.05, 0), "metal": (0.9, 70, 0.35, 0),
            "leaves": (0.05, 6, 0.0, 0), "fronds": (0.08, 8, 0.0, 0), "lamp": (0.5, 40, 0.0, 1.0),
            "ground": (0.08, 12, 0.0, 0), "glassmat": (1.0, 120, 0.7, 0), "fac": (0.18, 24, 0.0, 1.0),
            "house0": (0.15, 20, 0.04, 1.0), "house1": (0.15, 20, 0.04, 1.0), "house2": (0.15, 20, 0.04, 1.0),
            "house3": (0.15, 20, 0.04, 1.0),
        }
        self.DEPTH = {"ground": 0, "grass": 1, "dirt": 1, "water": 1, "rail": 1, "gravel": 1, "lot": 1, "field": 1,
                      "pavers": 1, "asphalt": 2, "walkflat": 2, "marks": 3}

    # ------------------------------------------------------------------ edifici
    def _rings(self, rec):
        S = self.S
        rings = []
        for flat in rec["r"]:
            if len(flat) < 6:
                continue
            P = clean_ring([(flat[i] * S, flat[i + 1] * S) for i in range(0, len(flat), 2)])
            if len(P) >= 3 and abs(ring_area(P)) > 0.5:
                rings.append(P)
        if not rings:
            return []
        rings.sort(key=lambda r: -abs(ring_area(r)))
        shapes = []
        for r in rings:
            parent = None
            for sh in shapes:
                if point_in_ring(r[0][0], r[0][1], sh[0]):
                    parent = sh
                    break
            if parent is not None:
                parent[1].append(r)
            else:
                shapes.append((r, []))
        out = []
        for outer, holes in shapes:
            if ring_area(outer) < 0:
                outer = outer[::-1]
            holes = [h if ring_area(h) < 0 else h[::-1] for h in holes]
            out.append((outer, holes))
        return out

    def _load_buildings(self):
        d = self.data
        CL = self.CL
        blds, parts = [], []
        for src, dst in ((d.get("edifici", []), blds), (d.get("parti", []), parts)):
            for rec in src:
                for outer, holes in self._rings(rec):
                    A = np.asarray(outer)
                    cx, cy = A[:, 0].mean(), A[:, 1].mean()
                    if max(abs(cx), abs(cy)) > CL:
                        continue
                    k = rec.get("k", "yes")
                    h = float(rec.get("h", 9.0))
                    m = float(rec.get("m", 0.0))
                    if k == "bridge":
                        m = max(m, h - 3.0)
                    if h <= m + 0.3:
                        h = m + 1.0
                    dst.append(dict(outer=outer, holes=holes, h=h, m=m, k=k, rec=rec, cx=cx, cy=cy,
                                    area=abs(ring_area(outer))))
        # le parti sostituiscono il contorno dell'edificio a cui appartengono
        tmp = Raster(self.world.hb.L, 2.0, np.int32, -1)
        for i, b in enumerate(blds):
            tmp.fill_rings([b["outer"]] + b["holes"], i)
        has_parts = set()
        for p in parts:
            A = np.asarray(p["outer"])
            pts = [(p["cx"], p["cy"])] + [(p["cx"] + (x - p["cx"]) * 0.6, p["cy"] + (y - p["cy"]) * 0.6) for x, y in A[:6]]
            for (x, y) in pts:
                v = int(tmp.get(x, y, -1))
                if v >= 0:
                    has_parts.add(v)
                    break
        solids = [b for i, b in enumerate(blds) if i not in has_parts] + parts
        solids.sort(key=lambda b: b["h"])
        self.blds = solids
        for b in solids:
            b["sid"] = self.world.add_solid(b["outer"], b["holes"], b["m"], b["h"], raster=(b["m"] < 2.5))
        self.n_buildings = len(solids)

    def _style(self, b, rng):
        k, h, area = b["k"], b["h"], b["area"]
        rec = b["rec"]
        mat = rec.get("mat", "")
        tint = parse_colour(rec.get("c"))
        shop = False
        roof = "flat"
        if k in HOUSE_KINDS and h < 13:
            st = "casa%d" % rng.randrange(3)
            roof = "gable"
        elif k in ("garage", "garages", "shed", "carport", "service", "kiosk", "hut", "construction", "roof",
                   "transformer_tower", "bridge", "toilets"):
            st = rng.choice(("cemento", "stucco"))
        elif k in ("parking",):
            st = "parcheggio"
        elif k in ("industrial", "warehouse", "factory", "manufacture"):
            st = "magazzino_mattoni" if (mat == "brick" or rng.random() < 0.45) else "capannone"
        elif mat in ("glass", "metal") or h >= 95:
            st = rng.choices(("vetro_blu", "vetro_scuro", "vetro_bronzo", "uffici_griglia"), (3, 3, 2, 1))[0]
        elif h >= 45:
            if k in ("apartments", "residential", "hotel", "dormitory"):
                st = rng.choice(("appartamenti_moderni", "intonaco_bianco", "vetro_blu", "uffici_griglia"))
            else:
                st = rng.choice(("vetro_blu", "vetro_scuro", "uffici_nastro", "uffici_griglia", "pietra"))
        elif k in ("apartments", "residential", "dormitory", "hotel"):
            st = rng.choice(("intonaco_crema", "intonaco_bianco", "intonaco_pesca", "appartamenti_moderni",
                             "mattoni_rossi" if h < 30 else "intonaco_crema"))
            shop = h >= 9 and area >= 150 and rng.random() < 0.35
        else:
            if mat == "brick":
                st = rng.choice(("mattoni_rossi", "mattoni_bruni"))
            else:
                st = rng.choices(("pietra", "terracotta", "mattoni_rossi", "mattoni_bruni", "intonaco_crema",
                                  "uffici_griglia", "uffici_nastro"), (3, 3, 2, 2, 2, 1, 1))[0]
            if k in ("retail", "commercial", "yes", "mixed_use", "office", "hotel"):
                shop = h >= 4.5 and area >= 50 and rng.random() < (0.9 if k in ("retail", "commercial") else 0.55)
        if b["m"] > 2.0:
            shop = False
        return st, shop, roof, tint

    def _fac_ring(self, m, P, z0, z1, layer, tint, v_base, rng, bay_fit=True):
        P = np.asarray(P, np.float64)
        A = P
        B = np.roll(P, -1, axis=0)
        D = B - A
        l = np.hypot(D[:, 0], D[:, 1])
        ok = l > 0.05
        A, B, D, l = A[ok], B[ok], D[ok], l[ok]
        k = len(A)
        if k == 0 or z1 <= z0:
            return
        bay = 12.0 / FACADE_DEFS[layer][2]
        if bay_fit:
            nb = np.maximum(1, np.round(l / bay))
            span = np.where(l > bay * 0.5, nb * bay / 12.0, l / 12.0)
        else:
            span = l / 12.0
        u0 = np.array([rng.randrange(0, 40) for _ in range(k)], np.float64)
        nx, ny = D[:, 1] / l, -D[:, 0] / l
        V = np.zeros((4 * k, 12), np.float32)
        V[0::4, 0:2] = A
        V[1::4, 0:2] = B
        V[2::4, 0:2] = B
        V[3::4, 0:2] = A
        V[0::4, 2] = z0
        V[1::4, 2] = z0
        V[2::4, 2] = z1
        V[3::4, 2] = z1
        for j in range(4):
            V[j::4, 3] = nx
            V[j::4, 4] = ny
        c = tint or (255, 255, 255)
        V[:, 6] = c[0] / 255.0
        V[:, 7] = c[1] / 255.0
        V[:, 8] = c[2] / 255.0
        V[:, 9] = layer / 255.0
        va, vb = (z0 - v_base) / 12.0, (z1 - v_base) / 12.0
        V[0::4, 10] = u0
        V[3::4, 10] = u0
        V[1::4, 10] = u0 + span
        V[2::4, 10] = u0 + span
        V[0::4, 11] = va
        V[1::4, 11] = va
        V[2::4, 11] = vb
        V[3::4, 11] = vb
        i = np.arange(k, dtype=np.uint32) * 4
        I = np.stack([i, i + 1, i + 2, i, i + 2, i + 3], 1).reshape(-1)
        m.chunks.append((V, I))

    def _building(self, b):
        rng = random.Random(int(b["cx"] * 7.3 + b["cy"] * 13.1))
        st, shop, roof, tint = self._style(b, rng)
        b["style"] = st
        outer, holes = b["outer"], b["holes"]
        h, z0 = b["h"], b["m"]
        if z0 < 0.5:
            z0 = -0.4
        cx, cy = b["cx"], b["cy"]
        fac = self.M("fac", cx, cy)
        layer = FACADE_INDEX[st]
        rings = [outer] + holes
        small = b["area"] < 45 or h < 4.0
        roof_col = parse_colour(b["rec"].get("rc"))
        if roof == "gable" and len(outer) == 4 and not holes:
            self._gable_house(b, layer, tint, roof_col, rng)
            return
        para = 0.0 if (small or b["k"] == "roof" or b["m"] > 2.0) else (1.0 if h > 20 else 0.7)
        top = h + para
        vb = -3.0 * rng.randrange(0, 4)
        for P in rings:
            if shop and h > 4.6:
                self._fac_ring(fac, P, z0, 4.5, FACADE_INDEX["negozi%d" % rng.randrange(3)], None, 0.0, rng)
                self._fac_ring(fac, P, 4.5, top, layer, tint, 4.5 + vb, rng)
                band = offset_ring(P, 0.18)
                wall_strip(self.M("props", cx, cy), np.vstack([band, band[:1]]), 4.45, 4.75, (120, 116, 110))
            else:
                self._fac_ring(fac, P, z0, top, layer, tint, vb, rng)
        # tetto
        rk = "roof" if rng.random() < 0.7 else "roof2"
        rc = roof_col or rng.choice(((236, 236, 232), (210, 210, 206), (178, 176, 172), (150, 150, 152)))
        flat_poly(self.M(rk, cx, cy), outer, holes, h, rc, 6.0)
        if b["m"] > 2.0:
            flat_poly(self.M("props", cx, cy), outer, holes, b["m"], (150, 148, 144), 6.0, up=False)
        if para > 0:
            pc = (172, 168, 160)
            p = self.M("props", cx, cy)
            for P in rings:
                Pa = np.asarray(P, np.float64)
                ins = offset_ring(Pa, -0.35)
                wall_strip(p, np.vstack([ins, ins[:1]]), h, top, pc, outward_right=False)
                n = len(Pa)
                V = np.zeros((4 * n, 12), np.float32)
                Pb = np.roll(Pa, -1, axis=0)
                Ib = np.roll(ins, -1, axis=0)
                V[0::4, 0:2] = Pa
                V[1::4, 0:2] = Pb
                V[2::4, 0:2] = Ib
                V[3::4, 0:2] = ins
                V[:, 2] = top
                V[:, 5] = 1.0
                V[:, 6:10] = _col(pc)
                ii = np.arange(n, dtype=np.uint32) * 4
                I = np.stack([ii, ii + 2, ii + 1, ii, ii + 3, ii + 2], 1).reshape(-1)
                p.chunks.append((V, I))
        # impianti sul tetto ed eliporto (i grattacieli di LA hanno l'eliporto sul tetto!)
        if not small and b["m"] < 2.0:
            self._roof_stuff(b, h, rng)
        if 6 <= h <= 70 and b["area"] > 120 and b["m"] < 2.0:
            if self.world.hb.get(cx, cy, -1) == b["sid"] and abs(self.world.hh.get(cx, cy) - h) < 0.5:
                self.rooftops.append((cx, cy, h))

    def _roof_stuff(self, b, h, rng):
        cx, cy = b["cx"], b["cy"]
        sid = b["sid"]
        hb = self.world.hb

        def inside(x, y, mrg):
            for ox, oy in ((0, 0), (mrg, 0), (-mrg, 0), (0, mrg), (0, -mrg)):
                if hb.get(x + ox, y + oy, -1) != sid:
                    return False
            return True
        p = self.M("props", cx, cy)
        if h > 80 and b["area"] > 700 and inside(cx, cy, 12.0):
            m = self.M("helipad", cx, cy)
            z = h + 0.15
            m.quad((cx - 10, cy - 10, z), (cx + 10, cy - 10, z), (cx + 10, cy + 10, z), (cx - 10, cy + 10, z),
                   (255, 255, 255), ((0, 0), (1, 0), (1, 1), (0, 1)), (0, 0, 1))
            p.box(cx - 10.4, cy - 10.4, h, cx + 10.4, cy + 10.4, h + 0.12, (90, 92, 90), faces="xXyY")
            self.rooftops.append((cx, cy, h + 0.15))
            return
        A = np.asarray(b["outer"])
        x0, y0 = A.min(0)
        x1, y1 = A.max(0)
        n = int(clamp(b["area"] / 250, 0, 7))
        for _ in range(n):
            for _t in range(6):
                x, y = rng.uniform(x0, x1), rng.uniform(y0, y1)
                w, d = rng.uniform(1.6, 4.0), rng.uniform(1.4, 3.2)
                if inside(x, y, max(w, d) + 0.8):
                    hh = rng.uniform(1.0, 2.4)
                    p.box(x - w / 2, y - d / 2, h, x + w / 2, y + d / 2, h + hh, rng.choice(
                        ((176, 178, 182), (196, 198, 200), (150, 152, 156))), faces="xXyYz")
                    self.world.add_box(x - w / 2, y - d / 2, x + w / 2, y + d / 2, h, h + hh, "impianto")
                    break

    def _gable_house(self, b, layer, tint, roof_col, rng):
        a, bb, c, d = [np.array(p, np.float64) for p in b["outer"]]
        h = b["h"]
        if np.hypot(*(bb - a)) < np.hypot(*(c - bb)):
            a, bb, c, d = bb, c, d, a
        short = np.hypot(*(c - bb))
        rh = clamp(short * 0.35, 1.2, 3.2)
        zw = max(2.8, h - rh) if b["rec"].get("e") == 0 else 5.6
        zt = zw + rh
        cx, cy = b["cx"], b["cy"]
        self._fac_ring(self.M("fac", cx, cy), b["outer"], -0.3, zw, layer, tint, 0.0, rng)
        mbc = (bb + c) / 2
        mda = (d + a) / 2
        P3 = lambda p, z: (float(p[0]), float(p[1]), z)
        sh = self.M("shingles", cx, cy)
        rc = roof_col or rng.choice(((255, 255, 255), (200, 170, 160), (150, 150, 160), (210, 190, 170)))
        ov = 0.0
        sh.quad(P3(a, zw - ov), P3(bb, zw - ov), P3(mbc, zt), P3(mda, zt), rc,
                ((0, 0), (np.hypot(*(bb - a)) / 4, 0), (np.hypot(*(bb - a)) / 4, 1.2), (0, 1.2)))
        sh.quad(P3(c, zw - ov), P3(d, zw - ov), P3(mda, zt), P3(mbc, zt), rc,
                ((0, 0), (np.hypot(*(d - c)) / 4, 0), (np.hypot(*(d - c)) / 4, 1.2), (0, 1.2)))
        wall = tint or (230, 222, 206)
        p = self.M("props", cx, cy)
        p.quad(P3(bb, zw), P3(c, zw), P3(mbc, zt), P3(mbc, zt), wall)
        p.quad(P3(d, zw), P3(a, zw), P3(mda, zt), P3(mda, zt), wall)
        b["style"] = "casa"

    # ------------------------------------------------------------------ strade
    def _parse_roads(self):
        S = self.S
        CL = self.CL
        drive, paths, crossings = [], [], []
        for rec in self.data.get("strade", []):
            k = rec.get("k")
            if rec.get("t") or k in ("proposed", "construction", "platform", "raceway", "bus_guideway", "elevator",
                                     "corridor", "escape", "busway", "rest_area", "services", "abandoned"):
                continue
            flat = rec.get("p", [])
            keys = [(flat[i], flat[i + 1]) for i in range(0, len(flat) - 1, 2)]
            if len(keys) < 2:
                continue
            P = np.asarray(keys, np.float64) * S
            ins = np.max(np.abs(P), axis=1) <= CL
            runs = []
            i = 0
            n = len(P)
            while i < n:
                if not ins[i]:
                    i += 1
                    continue
                j = i
                while j < n and ins[j]:
                    j += 1
                a, bnd = max(0, i - 1), min(n, j + 1)
                if bnd - a >= 2:
                    runs.append((a, bnd))
                i = j
            for (a, bnd) in runs:
                if k in ROAD_DEF:
                    drive.append(dict(rec=rec, k=k, P=P[a:bnd], keys=keys[a:bnd]))
                elif k in PATH_W:
                    f = rec.get("f", "")
                    if f == "crossing":
                        crossings.append(P[a:bnd])
                    elif f in ("sidewalk", "traffic_island", "access_aisle"):
                        continue
                    else:
                        paths.append(dict(k=k, P=P[a:bnd], w=PATH_W[k]))
        self.paths = paths
        self.crossings = crossings
        return drive

    def _road_profile(self, rec, k):
        nl, lw, sw, park, speed, traffic = ROAD_DEF[k]
        o = str(rec.get("o", "")).lower()
        ow = 0
        if o in ("yes", "true", "1"):
            ow = 1
        elif o in ("-1", "reverse"):
            ow = -1
        elif o != "no" and (k in ("motorway", "motorway_link", "trunk_link") or rec.get("j") in ("roundabout", "circular")):
            ow = 1
        lanes = _num(rec.get("l"))
        if lanes is None:
            lanes = ONEWAY_LANES.get(k, 1) if ow else nl
        lanes = int(clamp(round(lanes), 1, 8))
        if k == "service":
            sv = rec.get("s", "")
            w0 = {"driveway": 3.5, "parking_aisle": 6.0, "alley": 5.0, "drive-through": 3.5}.get(sv, 4.5)
        else:
            w0 = lanes * lw + (4.8 if park else 0.0) + (0.0 if ow else 0.6)
        wt = _num(rec.get("w"))
        if wt is not None and 3 <= wt <= 40:
            w0 = wt
        return dict(ow=ow, lanes=lanes, w0=clamp(w0, 3.0, 32.0), sw=sw, park=park, speed=speed, traffic=traffic,
                    lw=lw)

    def _roads(self):
        drive = self._parse_roads()
        for w in drive:
            w.update(self._road_profile(w["rec"], w["k"]))
            if w["ow"] < 0:
                w["P"] = w["P"][::-1].copy()
                w["keys"] = w["keys"][::-1]
                w["ow"] = 1
        # nodi del grafo: estremi e punti condivisi
        cnt = {}
        for w in drive:
            ks = w["keys"]
            for i, key in enumerate(ks):
                cnt[key] = cnt.get(key, 0) + (2 if i == 0 or i == len(ks) - 1 else 1)
        edges = []
        for w in drive:
            ks = w["keys"]
            start = 0
            for i in range(1, len(ks)):
                if cnt.get(ks[i], 0) >= 2 or i == len(ks) - 1:
                    if i > start:
                        edges.append(dict(w=w, P=w["P"][start:i + 1], keys=ks[start:i + 1]))
                    start = i
        adj = {}
        for ei, e in enumerate(edges):
            adj.setdefault(e["keys"][0], []).append((ei, 0))
            adj.setdefault(e["keys"][-1], []).append((ei, 1))

        def prof(e):
            w = e["w"]
            return (w["k"], w["ow"], w["lanes"], round(w["w0"]))
        used = [False] * len(edges)
        chains = []
        for ei in range(len(edges)):
            if used[ei]:
                continue
            used[ei] = True
            pf = prof(edges[ei])
            ow = edges[ei]["w"]["ow"]
            seq = [(ei, False)]
            for direction in (1, -1):
                key = edges[ei]["keys"][-1] if direction > 0 else edges[ei]["keys"][0]
                while True:
                    lst = adj.get(key, [])
                    if len(lst) != 2:
                        break
                    cur = seq[-1][0] if direction > 0 else seq[0][0]
                    other = [t for t in lst if t[0] != cur]
                    if len(other) != 1:
                        break
                    e2, end2 = other[0]
                    if used[e2] or prof(edges[e2]) != pf:
                        break
                    if direction > 0:
                        rev = end2 == 1
                    else:
                        rev = end2 == 0
                    if ow and rev:
                        break
                    used[e2] = True
                    ks2 = edges[e2]["keys"]
                    if direction > 0:
                        seq.append((e2, rev))
                        key = ks2[0] if rev else ks2[-1]
                    else:
                        seq.insert(0, (e2, rev))
                        key = ks2[-1] if rev else ks2[0]
            pts, keys = [], []
            for (e, rev) in seq:
                P = edges[e]["P"][::-1] if rev else edges[e]["P"]
                ks = edges[e]["keys"][::-1] if rev else edges[e]["keys"]
                if pts:
                    P = P[1:]
                    ks = ks[1:]
                pts.append(P)
                keys.extend(ks)
            P = np.vstack(pts)
            if len(P) < 2:
                continue
            chains.append(dict(w=edges[ei]["w"], P=P, keys=keys))
        # oggetti Chain e grafo
        net = self.net
        S = self.S
        for c in chains:
            w = c["w"]
            P = c["P"]
            d = np.hypot(*np.diff(P, axis=0).T)
            if d.sum() < 1.0:
                continue
            keep = np.concatenate([[True], d > 0.05])
            P = P[keep]
            if len(P) < 2:
                continue
            ch = Chain()
            ch.id = len(net.chains)
            ch.k = w["k"]
            ch.pl = Polyline(P)
            k0, k1 = c["keys"][0], c["keys"][-1]
            ch.n0 = net.node(k0, k0[0] * S, k0[1] * S)
            ch.n1 = net.node(k1, k1[0] * S, k1[1] * S)
            ch.ow = w["ow"]
            if ch.ow:
                ch.lf, ch.lb = w["lanes"], 0
            else:
                ch.lf = max(1, w["lanes"] // 2 + w["lanes"] % 2)
                ch.lb = max(1, w["lanes"] // 2)
            ch.hw = w["w0"] / 2
            ch.park = w["park"]
            ch.speed = w["speed"]
            ch.traffic = w["traffic"] > 0
            ch.sw = w["sw"]
            ch.name = w["rec"].get("n", "")
            ch.trim = [0.0, 0.0]
            ch.signal = [False, False]
            ch.group = [0, 0]
            ch.cut = None
            ch.lane_w = w["lw"]
            net.chains.append(ch)
            net.out[ch.n0].append((ch.id, 1))
            net.out[ch.n1].append((ch.id, -1))
        self._fit_widths()
        # nastri d'asfalto e raster delle strade
        for ch in net.chains:
            self._road_ribbon(ch)

    def _fit_widths(self):
        """restringe le strade dove gli edifici sono vicini e misura i marciapiedi fino alla facciata"""
        hb = self.world.hb
        for ch in self.net.chains:
            pl = ch.pl
            n = max(2, int(pl.L / 5.0))
            ss = np.linspace(0, pl.L, n)
            X, Y, TX, TY = pl.at_many(ss)
            NX, NY = TY, -TX
            dist = np.arange(1.0, ch.hw + 13.0, 0.5)
            res = []
            for side in (1, -1):
                xs = X[:, None] + NX[:, None] * dist[None, :] * side
                ys = Y[:, None] + NY[:, None] * dist[None, :] * side
                k = 1.0 / hb.res
                ix = ((xs + hb.L) * k).astype(np.int64)
                iy = ((ys + hb.L) * k).astype(np.int64)
                ok = (ix >= 0) & (iy >= 0) & (ix < hb.n) & (iy < hb.n)
                v = np.where(ok, hb.a[np.clip(iy, 0, hb.n - 1), np.clip(ix, 0, hb.n - 1)], -1)
                bld = v >= 0
                anyb = bld.any(1)
                first = np.where(anyb, dist[np.argmax(bld, 1)], np.inf)
                if anyb.mean() >= 0.3:
                    res.append(float(np.percentile(first[anyb], 20)))
                else:
                    res.append(None)
            dR, dL = res
            hw0 = ch.hw
            need = 1.8 if ch.sw > 0 else 0.4
            lim = min([d for d in (dR, dL) if d is not None], default=None)
            if lim is not None:
                ch.hw = clamp(min(hw0, lim - need), max(2.2, hw0 * 0.55), hw0)
            so = []
            for d in (dR, dL):
                if ch.sw <= 0:
                    so.append(None)
                elif d is not None:
                    so.append(clamp(d, ch.hw + 1.6, ch.hw + 7.0))
                else:
                    so.append(ch.hw + ch.sw)
            ch.cut = so          # distanza del bordo esterno del marciapiede (destra, sinistra)
            # corsie: larghezza effettiva
            park = 2.4 if ch.park else 0.3
            if ch.ow:
                avail = max(2.6, 2 * ch.hw - 2 * park)
                ch.lane_w = clamp(avail / ch.lf, 2.6, 3.8)
                while ch.lf > 1 and avail / ch.lf < 2.6:
                    ch.lf -= 1
            else:
                avail = max(2.6, ch.hw - park - 0.3)
                for attr in ("lf", "lb"):
                    while getattr(ch, attr) > 1 and avail / getattr(ch, attr) < 2.6:
                        setattr(ch, attr, getattr(ch, attr) - 1)
                ch.lane_w = clamp(avail / max(ch.lf, ch.lb), 2.6, 3.8)

    def _road_ribbon(self, ch):
        P = ch.pl.P
        hw = ch.hw
        Lft = offset_line(P, -hw)
        Rgt = offset_line(P, hw)
        poly = np.vstack([Lft, Rgt[::-1]])
        if ch.k != "service":
            self.rid.fill_rings([poly], ch.id)
            self.cnt.fill_rings([poly], 1, "add")
        self.gt.fill_rings([poly], 1)
        # a pezzi di ~120 m per il culling
        S = ch.pl.S
        n = len(P)
        i = 0
        while i < n - 1:
            j = i + 1
            while j < n - 1 and S[j] - S[i] < 120:
                j += 1
            mx, my = (P[i] + P[j]) / 2
            m = self.M("asphalt", mx, my)
            self._ribbon_lr(m, Lft[i:j + 1], Rgt[i:j + 1], 0.0, (255, 255, 255), 9.0)
            i = j
        # tappi rotondi alle estremita' (raccordi negli incroci)
        for (x, y) in (P[0], P[-1]):
            self._disc(self.M("asphalt", x, y), x, y, hw, 0.0, 9.0)
            self.gt.stamp_disc(x, y, hw, 1)

    @staticmethod
    def _ribbon_lr(m, Lft, Rgt, z, color, uvs, nrm=(0, 0, 1)):
        n = len(Lft)
        if n < 2:
            return
        V = np.zeros((2 * n, 12), np.float32)
        V[0::2, 0:2] = Lft
        V[1::2, 0:2] = Rgt
        V[:, 2] = z
        V[:, 3:6] = nrm
        V[:, 6:10] = _col(color)
        V[:, 10] = V[:, 0] / uvs
        V[:, 11] = V[:, 1] / uvs
        i = np.arange(n - 1, dtype=np.uint32) * 2
        I = np.stack([i, i + 1, i + 3, i, i + 3, i + 2], 1).reshape(-1)
        m.chunks.append((V, I))

    @staticmethod
    def _disc(m, x, y, r, z, uvs, seg=14, color=(255, 255, 255)):
        a = np.linspace(0, TAU, seg + 1)[:-1]
        V = np.zeros((seg + 1, 12), np.float32)
        V[0, 0:3] = (x, y, z)
        V[1:, 0] = x + np.cos(a) * r
        V[1:, 1] = y + np.sin(a) * r
        V[:, 2] = z
        V[:, 5] = 1
        V[:, 6:10] = _col(color)
        V[:, 10] = V[:, 0] / uvs
        V[:, 11] = V[:, 1] / uvs
        i = np.arange(seg, dtype=np.uint32)
        I = np.stack([np.zeros(seg, np.uint32), 1 + i, 1 + (i + 1) % seg], 1).reshape(-1)
        m.chunks.append((V, I))

    # ------------------------------------------------------------------ marciapiedi, segnaletica, attraversamenti
    def _runs(self, good, step):
        """intervalli [s0, s1] dove good e' vero (campioni ogni step metri)"""
        out = []
        n = len(good)
        i = 0
        while i < n:
            if not good[i]:
                i += 1
                continue
            j = i
            while j < n and good[j]:
                j += 1
            out.append((i * step, (j - 1) * step))
            i = j
        return out

    def _sample_raster(self, R, xs, ys, default):
        k = 1.0 / R.res
        ix = ((xs + R.L) * k).astype(np.int64)
        iy = ((ys + R.L) * k).astype(np.int64)
        ok = (ix >= 0) & (iy >= 0) & (ix < R.n) & (iy < R.n)
        return np.where(ok, R.a[np.clip(iy, 0, R.n - 1), np.clip(ix, 0, R.n - 1)], default)

    def _line_samples(self, ch, off, step=0.5):
        pl = ch.pl
        n = max(2, int(pl.L / step) + 1)
        ss = np.arange(n) * step
        ss[-1] = min(ss[-1], pl.L)
        X, Y, TX, TY = pl.at_many(ss)
        return ss, X + TY * off, Y - TX * off

    def _other_road(self, ch, X, Y):
        """un'altra strada copre il punto (anche se e' stata disegnata prima di questa)"""
        v = self._sample_raster(self.rid, X, Y, -1)
        c = self._sample_raster(self.cnt, X, Y, 0)
        return (c >= 2) | ((c == 1) & (v != ch.id))

    def _road_details(self):
        net = self.net
        deg = [len(o) for o in net.out]
        hb = self.world.hb
        self.walk_runs = []
        signals = [tuple(p) for p in self.data.get("punti", {}).get("signals", [])]
        sig_nodes = set()
        if signals and len(net.nodes):
            N = np.asarray(net.nodes)
            for (sx, sy) in signals:
                d = (N[:, 0] - sx) ** 2 + (N[:, 1] - sy) ** 2
                i = int(np.argmin(d))
                if d[i] < 30 ** 2 and deg[i] >= 3:
                    sig_nodes.add(i)
        net.signal = sig_nodes
        for ch in net.chains:
            pl = ch.pl
            # dove la mezzeria entra in un'altra strada: rifilature per traffico e segnaletica
            ss, X, Y = self._line_samples(ch, 0.0, 0.5)
            oth = self._other_road(ch, X, Y)
            for end in (0, 1):
                node = ch.n0 if end == 0 else ch.n1
                if deg[node] < 3:
                    continue
                seq = oth if end == 0 else oth[::-1]
                k = 0
                while k < len(seq) and seq[k] and k * 0.5 < 35:
                    k += 1
                ch.trim[end] = min(k * 0.5 + 1.0, pl.L * 0.45)
                ch.signal[end] = node in sig_nodes
            # marciapiedi (rialzati) ai due lati
            if ch.cut is not None and ch.sw > 0:
                for si, side in enumerate((1, -1)):
                    so = ch.cut[si]
                    if so is None:
                        continue
                    self._sidewalk(ch, side, so)
            if ch.k != "service":
                self._markings(ch)
        # attraversamenti pedonali veri (strisce "continental" stile USA)
        for P in self.crossings:
            self._crossing(P)
        # gruppi semaforici: strade quasi parallele nello stesso gruppo
        for node in sig_nodes:
            outs = net.out[node]
            if not outs:
                continue
            base = None
            for (c, d) in outs:
                ch = net.chains[c]
                s = 0.5 if d > 0 else ch.pl.L - 0.5
                _x, _y, tx, ty = ch.pl.at(s)
                if d < 0:
                    tx, ty = -tx, -ty
                ang = math.degrees(math.atan2(ty, tx)) % 180.0
                if base is None:
                    base = ang
                diff = abs((ang - base + 90) % 180 - 90)
                ch.group[0 if d > 0 else 1] = 0 if diff < 45 else 1

    def _sidewalk(self, ch, side, so):
        hw = ch.hw
        mid = (hw + so) / 2
        step = 0.5
        ss, Xm, Ym = self._line_samples(ch, mid * side, step)
        _s, Xi, Yi = self._line_samples(ch, (hw + 0.35) * side, step)
        _s, Xo, Yo = self._line_samples(ch, (so - 0.3) * side, step)
        bad = self._other_road(ch, Xm, Ym) | self._other_road(ch, Xi, Yi) | self._other_road(ch, Xo, Yo)
        bad |= self._sample_raster(self.gt, Xm, Ym, 0) == 4
        good = ~bad
        for (s0, s1) in self._runs(good, step):
            if s1 - s0 < 1.0:
                continue
            P = ch.pl.piece(s0, s1)
            if len(P) < 2:
                continue
            if side > 0:
                Li = offset_line(P, hw)
                Lo = offset_line(P, so)
            else:
                Li = offset_line(P[::-1], hw)
                Lo = offset_line(P[::-1], so)
            mx, my = Li[len(Li) // 2]
            m = self.M("walk", mx, my)
            z = CURB
            self._ribbon_lr(m, Li, Lo, z, (255, 255, 255), 6.0)
            wall_strip(m, Li[::-1], 0.0, z, (215, 212, 205), True, uv=(6.0, 6.0))
            wall_strip(m, Lo, -0.05, z, (200, 198, 192), True, uv=(6.0, 6.0))
            for (a, b2) in ((Li[0], Lo[0]), (Lo[-1], Li[-1])):
                wall_strip(m, np.array([a, b2]), 0.0, z, (205, 202, 196), True)
            self.gt.fill_rings([np.vstack([Li, Lo[::-1]])], 2)
            self.walk_runs.append(dict(ch=ch, side=side, s0=s0, s1=s1, hw=hw, so=so))

    def _markings(self, ch):
        net = self.net
        pl = ch.pl
        lanes_marked = ch.k in ("motorway", "trunk", "primary", "secondary", "tertiary", "motorway_link",
                                "trunk_link", "primary_link", "secondary_link") or ch.lf + ch.lb > 2
        if not lanes_marked:
            return
        W = (240, 240, 236)
        Y = (236, 184, 40)
        lines = []          # (offset, colore, tratteggio)
        if ch.ow:
            n = ch.lf
            for k in range(1, n):
                lines.append((-n * ch.lane_w / 2 + ch.lane_w * k, W, True))
            if ch.k in ("motorway", "trunk", "motorway_link"):
                lines.append((-n * ch.lane_w / 2 - 0.2, Y, False))
                lines.append((n * ch.lane_w / 2 + 0.2, W, False))
        else:
            lines.append((0.12, Y, False))
            lines.append((-0.12, Y, False))
            for k in range(1, ch.lf):
                lines.append((0.3 + ch.lane_w * k, W, True))
            for k in range(1, ch.lb):
                lines.append((-(0.3 + ch.lane_w * k), W, True))
        for (off, col, dash) in lines:
            if abs(off) > ch.hw - 0.3:
                continue
            ss, X, Y_ = self._line_samples(ch, off, 0.5)
            good = ~self._other_road(ch, X, Y_)
            for (s0, s1) in self._runs(good, 0.5):
                s0 += 0.5
                s1 -= 0.5
                if s1 - s0 < 1.0:
                    continue
                if dash:
                    s = s0
                    while s < s1:
                        e = min(s + 3.0, s1)
                        self._mark_piece(pl, s, e, off, 0.12, col)
                        s += 9.0
                else:
                    self._mark_piece(pl, s0, s1, off, 0.11, col)
        # linee d'arresto agli incroci con semaforo
        for end in (0, 1):
            node = ch.n0 if end == 0 else ch.n1
            if node not in net.signal or ch.trim[end] <= 1.0:
                continue
            d_in = -1 if end == 0 else 1          # verso del traffico che arriva al nodo
            if ch.ow and d_in < 0:
                continue
            s_stop = ch.trim[end] + 1.2
            s = s_stop if end == 0 else pl.L - s_stop
            if ch.ow:
                o0, o1 = -ch.hw + 0.4, ch.hw - 0.4
            elif d_in > 0:
                o0, o1 = 0.3, ch.hw - 0.4
            else:
                o0, o1 = -ch.hw + 0.4, -0.3
            x, y, tx, ty = pl.at(s)
            m = self.M("marks", x, y)
            nx, ny = ty, -tx
            ax, ay = x + nx * o0, y + ny * o0
            bx, by = x + nx * o1, y + ny * o1
            z = 0.012
            w = 0.25
            m.quad((ax - tx * w, ay - ty * w, z), (bx - tx * w, by - ty * w, z), (bx + tx * w, by + ty * w, z),
                   (ax + tx * w, ay + ty * w, z), W, n=(0, 0, 1))

    def _mark_piece(self, pl, s0, s1, off, w, col):
        P = pl.piece(s0, s1)
        if len(P) < 2:
            return
        C = offset_line(P, off)
        Lft = offset_line(C, -w / 2)
        Rgt = offset_line(C, w / 2)
        mx, my = C[len(C) // 2]
        self._ribbon_lr(self.M("marks", mx, my), Lft, Rgt, 0.012, col, 4.0)

    def _crossing(self, P):
        P = np.asarray(P, np.float64)
        pl = Polyline(P)
        if pl.L < 2:
            return
        n = int(pl.L / 0.25) + 1
        ss = np.linspace(0, pl.L, n)
        X, Y, _tx, _ty = pl.at_many(ss)
        v = self._sample_raster(self.rid, X, Y, -1)
        good = v >= 0
        step = pl.L / max(n - 1, 1)
        for (s0, s1) in self._runs(good, step):
            if s1 - s0 < 2.0:
                continue
            ax, ay, tx, ty = pl.at(s0)
            nx, ny = -ty, tx
            m = self.M("marks", ax, ay)
            s = s0 + 0.3
            z = 0.013
            while s < s1 - 0.3:
                x, y, _tx, _ty = pl.at(s)
                a, b = 0.25, 1.5
                m.quad((x - tx * a - nx * b, y - ty * a - ny * b, z), (x + tx * a - nx * b, y + ty * a - ny * b, z),
                       (x + tx * a + nx * b, y + ty * a + ny * b, z), (x - tx * a + nx * b, y - ty * a + ny * b, z),
                       (240, 240, 236), n=(0, 0, 1))
                s += 1.1

    # ------------------------------------------------------------------ aree: parchi, parcheggi, piazze, acqua
    def _areas(self):
        S = self.S
        order = {"wood": 0, "grass": 1, "park": 1, "pitch": 2, "railway": 0, "construction": 0, "parking": 3,
                 "road_area": 4, "plaza": 4, "water": 5}
        areas = []
        for rec in self.data.get("aree", []):
            flat = rec.get("r", [])
            P = clean_ring([(flat[i] * S, flat[i + 1] * S) for i in range(0, len(flat) - 1, 2)])
            if len(P) < 3:
                continue
            A = np.asarray(P)
            cx, cy = A[:, 0].mean(), A[:, 1].mean()
            if max(abs(cx), abs(cy)) > self.CL:
                continue
            if ring_area(P) < 0:
                P = P[::-1]
            areas.append(dict(k=rec["k"], P=P, cx=cx, cy=cy, area=abs(ring_area(P)), n=rec.get("n", "")))
        areas.sort(key=lambda a: order.get(a["k"], 0))
        self.areas = areas
        self.parks = []
        for a in areas:
            k = a["k"]
            P = a["P"]
            cx, cy = a["cx"], a["cy"]
            if k in ("park", "grass", "wood"):
                flat_poly(self.M("grass", cx, cy), P, [], -0.03, (255, 255, 255), 6.0)
                self.gt.fill_rings([P], 3, "where0")
                if k == "park" and a["area"] > 900:
                    self.parks.append(a)
            elif k == "pitch":
                flat_poly(self.M("field", cx, cy), P, [], -0.025, (255, 255, 255), 30.0)
                self.gt.fill_rings([P], 3, "where0")
            elif k == "water":
                flat_poly(self.M("water", cx, cy), P, [], -0.02, (255, 255, 255), 10.0)
                self.gt.fill_rings([P], 4, "where0")
            elif k == "parking":
                flat_poly(self.M("lot", cx, cy), P, [], -0.02, (255, 255, 255), 9.0)
                self._lot_cars(a)
            elif k in ("plaza", "road_area"):
                flat_poly(self.M("pavers", cx, cy), P, [], -0.015, (255, 255, 255), 5.0)
                self._fill_free(P, 6)
            elif k == "railway":
                flat_poly(self.M("gravel", cx, cy), P, [], -0.03, (255, 255, 255), 5.0)
            elif k == "construction":
                flat_poly(self.M("dirt", cx, cy), P, [], -0.03, (255, 255, 255), 6.0)

    def _fill_free(self, P, val):
        self.gt.fill_rings([P], val, "where0")

    def _lot_cars(self, a):
        """posti auto nei parcheggi a raso: righe allineate al lato piu' lungo"""
        P = np.asarray(a["P"])
        if a["area"] < 150:
            return
        self._fill_free(a["P"], 5)
        D = np.roll(P, -1, axis=0) - P
        L = np.hypot(D[:, 0], D[:, 1])
        i = int(np.argmax(L))
        ux, uy = D[i] / L[i]
        vx, vy = -uy, ux
        cx, cy = a["cx"], a["cy"]
        pu = (P[:, 0] - cx) * ux + (P[:, 1] - cy) * uy
        pv = (P[:, 0] - cx) * vx + (P[:, 1] - cy) * vy
        rng = random.Random(int(cx * 3 + cy * 5))
        m = self.M("marks", cx, cy)
        hdg = vec_heading(vx, vy)
        row = pv.min() + 3.0
        flip = False
        while row < pv.max() - 2.5:
            u = pu.min() + 1.6
            while u < pu.max() - 1.4:
                x = cx + ux * u + vx * row
                y = cy + uy * u + vy * row
                ok = True
                for (ou, ov) in ((-1.2, -2.5), (1.2, -2.5), (-1.2, 2.5), (1.2, 2.5)):
                    qx, qy = x + ux * ou + vx * ov, y + uy * ou + vy * ov
                    if not point_in_ring(qx, qy, a["P"]) or self.world.hb.get(qx, qy, -1) >= 0 or \
                            self.gt.get(qx, qy) in (1, 2):
                        ok = False
                        break
                if ok:
                    z = 0.01
                    for s in (-1.35, 1.35):
                        lx, ly = x + ux * s, y + uy * s
                        m.quad((lx - ux * 0.06 - vx * 2.6, ly - uy * 0.06 - vy * 2.6, z),
                               (lx + ux * 0.06 - vx * 2.6, ly + uy * 0.06 - vy * 2.6, z),
                               (lx + ux * 0.06 + vx * 2.6, ly + uy * 0.06 + vy * 2.6, z),
                               (lx - ux * 0.06 + vx * 2.6, ly - uy * 0.06 + vy * 2.6, z), (226, 226, 220), n=(0, 0, 1))
                    if rng.random() < 0.3:
                        self.parking.append((x, y, hdg + (180 if flip else 0)))
                u += 2.7
            row += 6.0 if not flip else 8.0
            flip = not flip

    def _paths(self):
        """vialetti, zone pedonali, scale: lastricati piatti (anche percorsi per i pedoni)"""
        self.path_rings = []
        for p in self.paths:
            P = p["P"]
            pl = Polyline(P)
            if pl.L < 2:
                continue
            n = int(pl.L / 0.5) + 1
            ss = np.linspace(0, pl.L, n)
            X, Y, _tx, _ty = pl.at_many(ss)
            on_road = self._sample_raster(self.rid, X, Y, -1) >= 0
            in_bld = self._sample_raster(self.world.hb, X, Y, -1) >= 0
            good = ~(on_road | in_bld)
            step = pl.L / max(n - 1, 1)
            w = p["w"]
            key = "pavers" if p["k"] == "pedestrian" else "walk"
            for (s0, s1) in self._runs(good, step):
                if s1 - s0 < 1.5:
                    continue
                Q = pl.piece(s0, s1)
                if len(Q) < 2:
                    continue
                Lft = offset_line(Q, -w / 2)
                Rgt = offset_line(Q, w / 2)
                mx, my = Q[len(Q) // 2]
                self._ribbon_lr(self.M(key + "flat" if key == "walk" else key, mx, my), Lft, Rgt, 0.0,
                                (232, 230, 226), 6.0)
                if s1 - s0 > 6 and p["k"] != "cycleway":
                    self.path_rings.append(PathRing(Q))

    # ------------------------------------------------------------------ luoghi della storia
    def _facade_to_road(self, b, min_len=6.0):
        """lato dell'edificio rivolto verso la strada piu' vicina: (mx, my, nx, ny, lunghezza, distanza)"""
        P = np.asarray(b["outer"])
        best = None
        for i in range(len(P)):
            a, c = P[i], P[(i + 1) % len(P)]
            d = c - a
            l = float(np.hypot(*d))
            if l < min_len:
                continue
            nx, ny = d[1] / l, -d[0] / l
            mx, my = (a + c) / 2
            for dist in np.arange(1.0, 30.0, 1.0):
                g = self.gt.get(mx + nx * dist, my + ny * dist)
                if self.world.hb.get(mx + nx * dist, my + ny * dist, -1) >= 0 and dist > 1.5:
                    break
                if g in (1, 2):
                    score = dist - l * 0.15
                    if best is None or score < best[0]:
                        best = (score, mx, my, nx, ny, l, dist)
                    break
        return best[1:] if best else None

    def _sign(self, text_s, x, y, z, h, scale, color, neon=False, back=None):
        self.sign_specs.append((text_s, float(x), float(y), float(z), float(h), float(scale), tuple(color), neon,
                                tuple(back) if back else None))
        if self.font is None:
            self.font = TextNode.getDefaultFont()
        tn = TextNode("insegna")
        tn.setText(text_s)
        tn.setAlign(TextNode.ACenter)
        tn.setTextColor(*color)
        if back:
            tn.setCardColor(*back)
            tn.setCardAsMargin(0.4, 0.4, 0.2, 0.2)
            tn.setCardDecal(True)
        np_ = self.env.root.attachNewNode(tn.generate())
        np_.setPos(x, y, z)
        np_.setH(h)
        np_.setScale(scale)
        np_.setTransparency(TransparencyAttrib.M_alpha)
        np_.setShader(self.env.sign_shader)
        np_.setShaderInput("u_glow", 1.0 if neon else 0.0)
        np_.setDepthOffset(2)
        np_.hide(MASK_SHADOW)
        self.signs.append(np_)
        return np_

    def _sign_on(self, b, lines, z, neon=True, back=None, backing=None):
        f = self._facade_to_road(b)
        if f is None:
            return None
        mx, my, nx, ny, l, dist = f
        hdg = math.degrees(math.atan2(nx, -ny))
        sx, sy = mx + nx * 0.45, my + ny * 0.45
        if backing is not None:
            p = self.M("props", mx, my)
            w = min(l * 0.42, 9.0)
            tx, ty = -ny, nx
            m = Mesh()
            m.box(-w, -0.4, z - 1.6, w, 0.0, z + 1.4, backing, faces="xXyYz")
            p.add_mesh(m, mx + nx * 0.02, my + ny * 0.02, 0, hdg)
            del tx, ty
            sx, sy = mx + nx * 0.47, my + ny * 0.47
        for (text_s, dz, scale, col) in lines:
            self._sign(text_s, sx, sy, z + dz, hdg, scale, col, neon, back)
        return (mx + nx * (dist + 0.5), my + ny * (dist + 0.5), nx, ny)

    def _places(self):
        rng = random.Random(77)
        R = self.R
        self._smith_house()
        sx, sy = self.spots["smith"]
        servizi = self.data.get("servizi", [])
        blds = [b for b in self.blds if b["m"] < 2.0 and b["area"] > 60]

        def building_at(x, y):
            sid = int(self.world.hb.get(x, y, -1))
            for b in blds:
                if b["sid"] == sid:
                    return b
            best = min(blds, key=lambda b: (b["cx"] - x) ** 2 + (b["cy"] - y) ** 2)
            return best
        # Federazione Galattica (la vera centrale di polizia)
        pol = [b for b in blds if b["rec"].get("a") == "police"]
        if pol:
            pb = min(pol, key=lambda b: math.hypot(b["cx"], b["cy"]) - b["area"] * 0.02)
        else:
            pts = [s for s in servizi if s["k"] == "police"]
            if pts:
                p = min(pts, key=lambda s: abs(s["p"][0]) + abs(s["p"][1]))
                pb = building_at(*p["p"])
            else:
                pb = min(blds, key=lambda b: abs(math.hypot(b["cx"], b["cy"]) - 500) - b["area"] * 0.01)
        r = self._sign_on(pb, [("FEDERAZIONE GALATTICA", 0.0, 1.5, (1.0, 0.85, 0.2, 1)),
                               ("DISTRETTO TERRA", -1.6, 0.9, (0.8, 0.9, 1.0, 1))], min(pb["h"] - 2, 14.0))
        self.spots["polizia"] = self.free_point_near(*(r[:2] if r else (pb["cx"], pb["cy"])), roads_ok=False)
        # liceo Harry Herpson: la scuola vera piu' vicina a casa Smith
        sch = [b for b in blds if b["k"] == "school" or b["rec"].get("a") == "school"]
        pts = [s for s in servizi if s["k"] == "school"]
        cand = sch + [building_at(*s["p"]) for s in pts]
        if cand:
            sb = min(cand, key=lambda b: (b["cx"] - sx) ** 2 + (b["cy"] - sy) ** 2)
        else:
            sb = min(blds, key=lambda b: abs(math.hypot(b["cx"] - sx, b["cy"] - sy) - 300))
        r = self._sign_on(sb, [("LICEO HARRY HERPSON", 0.0, 1.1, (0.1, 0.12, 0.3, 1))], min(sb["h"] - 1.5, 8.0),
                          neon=False, back=(0.95, 0.93, 0.85, 1))
        self.spots["scuola"] = self.free_point_near(*(r[:2] if r else (sb["cx"], sb["cy"])))
        # Blips and Chitz: un negozio su una strada principale a qualche isolato da casa
        main = set(c.id for c in self.net.chains if c.k in ("primary", "secondary", "tertiary"))
        best = None
        for b in blds:
            if b["k"] not in ("retail", "commercial", "yes") or not (150 < b["area"] < 3000) or not (4 < b["h"] < 30):
                continue
            d = math.hypot(b["cx"] - sx, b["cy"] - sy)
            if not (250 < d < 1100):
                continue
            tall = max((o["h"] for o in blds if abs(o["cx"] - b["cx"]) < 70 and abs(o["cy"] - b["cy"]) < 70), default=0)
            if tall > 45:
                continue
            f = self._facade_to_road(b, 10.0)
            if f is None:
                continue
            mx, my, nx, ny, l, dist = f
            rid = int(self.rid.get(mx + nx * (dist + 3), my + ny * (dist + 3), -1))
            if rid not in main:
                continue
            score = abs(d - 550) + abs(b["h"] - 10) * 4
            if best is None or score < best[0]:
                best = (score, b)
        ab = best[1] if best else min(blds, key=lambda b: abs(math.hypot(b["cx"] - sx, b["cy"] - sy) - 500))
        r = self._sign_on(ab, [("BLIPS AND CHITZ", 0.4, 1.3, (0.3, 1.0, 1.0, 1)),
                               ("SALA GIOCHI", -0.75, 0.7, (1.0, 0.35, 0.9, 1))], 5.6, backing=(24, 20, 40))
        self.spots["arcade"] = self.free_point_near(*(r[:2] if r else (ab["cx"], ab["cy"])))
        # parchi veri (il Cromulon appare nel parco piu' centrale: Pershing Square a LA)
        parks = sorted(self.parks, key=lambda a: -a["area"])
        pts = []
        for a in parks[:12]:
            pts.append(self.free_point_near(a["cx"], a["cy"], roads_ok=False, rmax=40))
        if not pts:
            pts = [self.free_point_near(0, 0)]
        self.spots["parchi"] = pts
        self.center_park = min(pts, key=lambda p: math.hypot(*p) * 1.0)
        # portale Cronenberg: un grande spazio libero lontano da casa (parcheggio o piazza)
        self.spots["cronenberg"] = self._open_space(far_from=(sx, sy))
        del rng, R

    def _open_space(self, far_from):
        """cerca un quadrato di ~50 m senza edifici (raster a 4 m)"""
        hb = self.world.hb
        f = 4
        n = hb.n // f
        occ = (hb.a[:n * f, :n * f] >= 0).reshape(n, f, n, f).any(axis=(1, 3))
        occ |= (self.gt.a[:n * f, :n * f] == 4).reshape(n, f, n, f).any(axis=(1, 3))
        I = np.zeros((n + 1, n + 1), np.int32)
        I[1:, 1:] = np.cumsum(np.cumsum(occ.astype(np.int32), 0), 1)
        k = 7
        best = None
        for iy in range(k, n - k, 2):
            for ix in range(k, n - k, 2):
                s = I[iy + k + 1, ix + k + 1] - I[iy - k, ix + k + 1] - I[iy + k + 1, ix - k] + I[iy - k, ix - k]
                if s:
                    continue
                x = (ix + 0.5) * f - hb.L
                y = (iy + 0.5) * f - hb.L
                if max(abs(x), abs(y)) > self.limit - 60:
                    continue
                d = math.hypot(x - far_from[0], y - far_from[1])
                if d < 400:
                    continue
                score = -d * 0.2 + math.hypot(x, y) * 0.05
                if best is None or score < best[0]:
                    best = (score, x, y)
        if best is None:
            return self.free_point_near(self.limit * 0.6, 0.0, roads_ok=True)
        return (best[1] - 10.0, best[2])

    def _smith_house(self):
        """casa Smith in un lotto libero lungo una strada residenziale"""
        best = None
        hb = self.world.hb
        for ch in self.net.chains:
            if ch.k not in ("residential", "tertiary", "unclassified", "living_street", "secondary") or ch.cut is None:
                continue
            pl = ch.pl
            for s in np.arange(18.0, pl.L - 18.0, 8.0):
                x, y, tx, ty = pl.at(s)
                nx, ny = ty, -tx
                for si, side in enumerate((1, -1)):
                    so = ch.cut[si] if ch.cut[si] is not None else ch.hw + 2.5
                    dfront = so + 1.0 + 10.5
                    cx, cy = x + nx * side * dfront, y + ny * side * dfront
                    if max(abs(cx), abs(cy)) > self.limit - 80:
                        continue
                    fx, fy = -nx * side, -ny * side      # verso la strada
                    rx, ry = -fy, fx
                    ok = True
                    lot_pen = 0
                    for lx in np.arange(-11.0, 15.5, 1.5):
                        for ly in np.arange(-10.0, 10.5, 1.5):
                            px = cx + rx * lx - fx * ly
                            py = cy + ry * lx - fy * ly
                            if hb.get(px, py, -1) >= 0:
                                ok = False
                                break
                            g = self.gt.get(px, py)
                            if g in (1, 2, 4):
                                ok = False
                                break
                            if g == 5:
                                lot_pen += 1
                        if not ok:
                            break
                    if not ok:
                        continue
                    d = math.hypot(cx, cy)
                    score = abs(d - 700) + lot_pen * 2 + (150 if ch.k == "secondary" else 0)
                    if best is None or score < best[0]:
                        best = (score, cx, cy, fx, fy, dfront - so)
        if best is None:
            cx, cy = self.free_point_near(self.limit * 0.5, -self.limit * 0.5)
            fx, fy, front = 0.0, -1.0, 11.5
        else:
            _s, cx, cy, fx, fy, front = best
        self._build_smith(cx, cy, fx, fy, front)

    def _build_smith(self, cx, cy, fx, fy, front):
        """casa a due piani con garage (come in City._house) ruotata verso la strada"""
        hdeg = math.degrees(math.atan2(fx, -fy))
        rad = math.radians(hdeg)
        c, s = math.cos(rad), math.sin(rad)

        def W(lx, ly):
            return cx + lx * c - ly * s, cy + lx * s + ly * c
        parts = {}

        def P(k):
            m = parts.get(k)
            if m is None:
                m = parts[k] = Mesh()
            return m
        hk = "house1"
        W2, D2, Hh = 5.2, 4.2, 5.8
        z0 = 0.0
        P(hk).box(-W2, -D2, z0 - 0.3, W2, D2, Hh, (255, 255, 255), uv=(12, 6), faces="yXYx", v_base=z0)
        rz = Hh + 3.0
        ov = 0.6
        P("shingles").quad((-W2 - ov, -D2 - ov, Hh - 0.3), (W2 + ov, -D2 - ov, Hh - 0.3), (W2 + ov, 0, rz),
                           (-W2 - ov, 0, rz), (255, 255, 255), ((0, 0), (3, 0), (3, 1.4), (0, 1.4)))
        P("shingles").quad((W2 + ov, D2 + ov, Hh - 0.3), (-W2 - ov, D2 + ov, Hh - 0.3), (-W2 - ov, 0, rz),
                           (W2 + ov, 0, rz), (255, 255, 255), ((0, 0), (3, 0), (3, 1.4), (0, 1.4)))
        wall = (210, 222, 232)
        P("props").quad((W2, -D2, Hh), (W2, D2, Hh), (W2, 0, rz - 0.2), (W2, 0, rz - 0.2), wall)
        P("props").quad((-W2, D2, Hh), (-W2, -D2, Hh), (-W2, 0, rz - 0.2), (-W2, 0, rz - 0.2), wall)
        P("props").box(-0.8, -D2 - 0.12, z0, 0.8, -D2 + 0.05, 2.4, (110, 70, 44), faces="yz")
        P("props").box(-1.6, -D2 - 1.6, 2.6, 1.6, -D2, 2.8, (240, 240, 236), faces="xXyYzZ")
        P("props").box(-1.6, -D2 - 1.8, z0, 1.6, -D2, z0 + 0.25, (196, 192, 186), faces="xXyz")
        for sx in (-1.4, 1.4):
            P("props").cylinder(sx, -D2 - 1.4, z0, 2.6, 0.09, (240, 240, 236), seg=6, cap=False)
        P(hk).box(W2, -D2, z0 - 0.3, W2 + 6.5, D2 - 0.5, 3.6, (255, 255, 255), uv=(12, 6), faces="XYx", v_base=z0)
        P("garage").box(W2 + 0.5, -D2 - 0.02, z0, W2 + 6.0, -D2 + 0.1, 3.0, (255, 255, 255), faces="y")
        P("props").box(W2, -D2, z0 + 3.0, W2 + 6.5, -D2 + 0.4, 3.6, wall, faces="y")
        P("roof2").box(W2 - 0.2, -D2 - 0.3, 3.6, W2 + 6.8, D2 - 0.2, 3.8, (255, 255, 255), faces="xXyYz")
        # buca delle lettere, prato, vialetto, recinzione
        P("props").box(-1.0, -D2 - 4.5, z0, -0.7, -D2 - 4.2, 1.2, (80, 80, 90), faces="xXyYz")
        P("props").box(-1.2, -D2 - 4.7, 1.2, -0.5, -D2 - 4.0, 1.6, (40, 70, 140), faces="xXyYz")
        yf = -front - 0.5
        P("grass").quad((-11, yf, 0.01), (15, yf, 0.01), (15, 10, 0.01), (-11, 10, 0.01), (255, 255, 255),
                        ((0, 0), (4, 0), (4, 3), (0, 3)), (0, 0, 1))
        P("walkflat").quad((W2 + 1.5, yf, 0.03), (W2 + 5.0, yf, 0.03), (W2 + 5.0, -D2, 0.03), (W2 + 1.5, -D2, 0.03),
                           (236, 234, 230), ((0, 0), (0.6, 0), (0.6, 2), (0, 2)), (0, 0, 1))
        P("walkflat").quad((-0.8, yf, 0.025), (0.8, yf, 0.025), (0.8, -D2 - 1.8, 0.025), (-0.8, -D2 - 1.8, 0.025),
                           (236, 234, 230), ((0, 0), (0.3, 0), (0.3, 2), (0, 2)), (0, 0, 1))
        P("props").box(-11, 9.4, 0, 15, 9.5, 1.1, (240, 240, 236), faces="xXyYz")
        for k, m in parts.items():
            self.M(k, cx, cy).add_mesh(m, cx, cy, 0, hdeg)
        house = [W(-W2, -D2), W(W2 + 6.5, -D2), W(W2 + 6.5, D2), W(-W2, D2)]
        if ring_area(house) < 0:
            house = house[::-1]
        self.world.add_solid(house, [], -1.0, Hh)
        self.world.hh.fill_rings([house], rz - 1.0, "max")
        lot = [W(-11, yf), W(15, yf), W(15, 10), W(-11, 10)]
        self.gt.fill_rings([lot], 3)
        self.smith_lot = lot
        self.parking = [p for p in self.parking if not point_in_ring(p[0], p[1], lot)]
        hh = (hdeg + 180) % 360
        self.spots["casa"] = (*W(1.0, -D2 - 6.3), hh)
        self.spots["garage_auto"] = (*W(8.4, -D2 - 6.2), hh)
        self.spots["smith"] = (cx, cy)
        self.rooftops.append((cx, cy, rz - 0.6))
        self._tree_at(*W(-7.5, yf + 2.5), kind="broad", small=True)

    # ------------------------------------------------------------------ arredo: alberi, lampioni, semafori
    def _template_meshes(self):
        rng = random.Random(5)
        T = {}
        broad = []
        for v in range(4):
            m = Mesh()
            th = rng.uniform(2.6, 3.4)
            m.cylinder(0, 0, 0, th, 0.2, (92, 70, 52), seg=6, r_top=0.14, cap=False)
            base = rng.choice(((70, 110, 52), (86, 120, 56), (60, 100, 50), (100, 116, 54)))
            R = rng.uniform(2.2, 2.9)
            for k in range(3):
                ox, oy = rng.uniform(-1, 1) * R * 0.45, rng.uniform(-1, 1) * R * 0.45
                oz = th + R * rng.uniform(0.4, 0.9)
                r = R * rng.uniform(0.7, 0.95)
                m.ellipsoid(ox, oy, oz, r, r, r * 0.85, base, seg=7, rings=4, jitter=0.14, seed=rng.randrange(9999),
                            color_var=0.12)
            broad.append((m, th + R * 2))
        T["broad"] = broad
        palms = []
        for v in range(3):
            m = Mesh()
            f = Mesh()
            H = rng.uniform(11, 18)
            lean = rng.uniform(-0.6, 0.6)
            segs = 4
            for k in range(segs):
                z0, z1 = H * k / segs, H * (k + 1) / segs
                x0, x1 = lean * (k / segs) ** 2, lean * ((k + 1) / segs) ** 2
                r0 = 0.32 - 0.12 * k / segs
                r1 = 0.32 - 0.12 * (k + 1) / segs
                c = Mesh()
                c.cylinder(0, 0, z0, z1, r0, (120, 104, 84), seg=6, r_top=r1, cap=False)
                m.add_mesh(c, x1 - (x1 - x0) / 2, 0, 0)
            tx = lean
            m.ellipsoid(tx, 0, H, 0.55, 0.55, 0.7, (110, 96, 60), seg=6, rings=4)
            nf = 11
            for k in range(nf):
                a = k / nf * TAU + rng.uniform(-0.15, 0.15)
                ca, sa = math.cos(a), math.sin(a)
                droop = rng.uniform(0.6, 1.2)
                Lf = rng.uniform(3.2, 4.2)
                pts = []
                for j in range(5):
                    t = j / 4
                    r = Lf * t
                    z = H + 0.3 + 1.2 * t - droop * 3.0 * t * t
                    w = 0.55 * math.sin(math.pi * min(1.0, t * 1.1 + 0.05))
                    pts.append((tx + ca * r, sa * r, z, w))
                col = (64, 104, 48) if k % 2 else (78, 116, 52)
                for j in range(4):
                    x0, y0, z0, w0 = pts[j]
                    x1, y1, z1, w1 = pts[j + 1]
                    px, py = -sa, ca
                    f.quad((x0 - px * w0, y0 - py * w0, z0 - 0.15 * w0), (x1 - px * w1, y1 - py * w1, z1 - 0.15 * w1),
                           (x1 + px * w1, y1 + py * w1, z1 - 0.15 * w1), (x0 + px * w0, y0 + py * w0, z0 - 0.15 * w0),
                           col, n=(0, 0, 1))
            palms.append((m, f, H + 1))
        T["palm"] = palms
        # lampione "cobra" delle strade principali
        cob = Mesh()
        cob.cylinder(0, 0, 0, 9.0, 0.13, (110, 112, 116), seg=6, r_top=0.09, cap=False)
        cob.box(-0.06, 0, 8.75, 0.06, 2.6, 8.88, (110, 112, 116), faces="xXyYzZ")
        cob.box(-0.3, 2.3, 8.55, 0.3, 3.1, 8.85, (120, 122, 126), faces="xXyYzZ")
        head_c = Mesh()
        head_c.box(-0.24, 2.36, 8.52, 0.24, 3.04, 8.55, (255, 250, 230), faces="Z")
        T["cobra"] = (cob, head_c, (0.0, 2.7, 8.3))
        # lampione ornamentale del centro di LA (due globi)
        orn = Mesh()
        orn.cylinder(0, 0, 0, 0.5, 0.22, (40, 46, 42), seg=6, cap=False)
        orn.cylinder(0, 0, 0.5, 5.2, 0.1, (40, 46, 42), seg=6, cap=False)
        orn.box(-0.9, -0.04, 4.9, 0.9, 0.04, 5.0, (40, 46, 42), faces="xXyYzZ")
        glob = Mesh()
        for sx in (-0.85, 0.85):
            glob.ellipsoid(sx, 0, 5.35, 0.28, 0.28, 0.34, (250, 246, 230), seg=6, rings=3)
        glob.ellipsoid(0, 0, 5.55, 0.32, 0.32, 0.4, (250, 246, 230), seg=6, rings=3)
        T["orn"] = (orn, glob, (0.0, 0.0, 5.4))
        # semaforo a sbraccio (stile California)
        T["sig_pole"] = Mesh()
        T["sig_pole"].cylinder(0, 0, 0, 6.6, 0.15, (150, 146, 120), seg=8, r_top=0.12, cap=True)
        self.templ = T

    def _tree_at(self, x, y, kind="broad", small=False, rng=None):
        rng = rng or self.rng
        if kind == "palm":
            m, f, top = rng.choice(self.templ["palm"])
            s = rng.uniform(0.8, 1.15)
            h = rng.uniform(0, 360)
            self.M("leaves", x, y).add_mesh(m, x, y, 0, h, s)
            self.M("fronds", x, y).add_mesh(f, x, y, 0, h, s)
            self.world.add_circle(x, y, 0.35, top * s, "albero")
        else:
            m, top = rng.choice(self.templ["broad"])
            s = rng.uniform(0.75, 1.1) * (0.7 if small else 1.0)
            self.M("leaves", x, y).add_mesh(m, x, y, 0, rng.uniform(0, 360), s)
            self.world.add_circle(x, y, 0.3, top * s, "albero")

    def _lamp_at(self, x, y, tx, ty, nx, ny, kind):
        """lampione al bordo del marciapiede; (nx, ny) = verso la strada"""
        body, head, lp = self.templ[kind]
        hdg = math.degrees(math.atan2(-nx, ny))
        self.M("metal", x, y).add_mesh(body, x, y, 0, hdg)
        self.M("lamp", x, y).add_mesh(head, x, y, 0, hdg)
        r = math.radians(hdg)
        c, s = math.cos(r), math.sin(r)
        lx, ly = x + lp[0] * c - lp[1] * s, y + lp[0] * s + lp[1] * c
        self.lamps.append((lx, ly, lp[2]))
        self.world.add_circle(x, y, 0.18, 9.0, "lampione")

    def _props(self):
        rng = self.rng
        hb = self.world.hb
        main = ("primary", "secondary", "trunk", "tertiary")
        palm_chain = {}
        lamp_pts = []
        for wr in self.walk_runs:
            ch = wr["ch"]
            side = wr["side"]
            s0, s1 = wr["s0"], wr["s1"]
            hw, so = wr["hw"], wr["so"]
            if s1 - s0 < 8:
                continue
            kind = "cobra" if ch.k in ("primary", "secondary", "trunk") else "orn"
            phase = 6.0 if side > 0 else 25.0
            s = s0 + phase
            while s < s1 - 3:
                x, y, tx, ty = ch.pl.at(s)
                nx, ny = ty * side, -tx * side
                px, py = x + nx * (hw + 0.55), y + ny * (hw + 0.55)
                if hb.get(px, py, -1) < 0:
                    self._lamp_at(px, py, tx, ty, -nx, -ny, kind)
                    lamp_pts.append((px, py))
                s += 38.0
            # alberi lungo la strada (palme su alcune vie, come a LA)
            if so - hw >= 2.6 and ch.k in main + ("residential", "unclassified"):
                if ch.id not in palm_chain:
                    palm_chain[ch.id] = rng.random() < 0.3
                palms = palm_chain[ch.id]
                spacing = 11.0 if palms else 13.0
                prob = 0.75 if ch.k in ("residential", "tertiary") else 0.5
                s = s0 + 4.0 + rng.uniform(0, 4)
                while s < s1 - 4:
                    x, y, tx, ty = ch.pl.at(s)
                    nx, ny = ty * side, -tx * side
                    px, py = x + nx * (hw + 1.1), y + ny * (hw + 1.1)
                    if rng.random() < prob and hb.get(px, py, -1) < 0 and hb.get(px + nx * 2, py + ny * 2, -1) < 0:
                        if all((px - lx) ** 2 + (py - ly) ** 2 > 9 for lx, ly in lamp_pts[-6:]):
                            self._tree_at(px, py, "palm" if palms else "broad", small=not palms)
                    s += spacing
            # idranti
            if rng.random() < 0.35:
                s = rng.uniform(s0 + 3, max(s0 + 3.5, s1 - 3))
                x, y, tx, ty = ch.pl.at(s)
                nx, ny = ty * side, -tx * side
                hx, hy = x + nx * (hw + 0.5), y + ny * (hw + 0.5)
                p = self.M("props", hx, hy)
                p.cylinder(hx, hy, CURB, CURB + 0.7, 0.16, (220, 190, 40), seg=8)
                p.ellipsoid(hx, hy, CURB + 0.72, 0.17, 0.17, 0.12, (220, 190, 40), seg=8, rings=4)
                self.world.add_circle(hx, hy, 0.2, 0.9, "idrante")
            # posti auto lungo il marciapiede
            if ch.park and ch.k != "service":
                s = s0 + 6.0
                while s < s1 - 6.0:
                    x, y, tx, ty = ch.pl.at(s)
                    if rng.random() < 0.14:
                        nx, ny = ty * side, -tx * side
                        cx, cy = x + nx * (hw - 1.25), y + ny * (hw - 1.25)
                        h = vec_heading(tx, ty) if (side > 0 or ch.ow) else vec_heading(-tx, -ty)
                        self.parking.append((cx, cy, h))
                    s += 6.6
        # alberi veri di OpenStreetMap
        for (x, y) in self.data.get("punti", {}).get("trees", []):
            if max(abs(x), abs(y)) < self.CL and hb.get(x, y, -1) < 0 and self.gt.get(x, y) not in (1, 4):
                self._tree_at(x, y, "palm" if rng.random() < 0.3 else "broad")
        # parchi: alberi e palme
        for a in self.parks:
            n = int(min(a["area"] / 260, 60))
            P = np.asarray(a["P"])
            x0, y0 = P.min(0)
            x1, y1 = P.max(0)
            for _ in range(n):
                for _t in range(8):
                    x, y = rng.uniform(x0, x1), rng.uniform(y0, y1)
                    if point_in_ring(x, y, a["P"]) and self.gt.get(x, y) == 3 and hb.get(x, y, -1) < 0:
                        self._tree_at(x, y, "palm" if rng.random() < 0.35 else "broad")
                        break
        # semafori
        self._signals()
        # fermate dell'autobus: palo con cartello e panchina
        for (x, y) in self.data.get("punti", {}).get("bus", []):
            if max(abs(x), abs(y)) > self.CL or self.gt.get(x, y) == 1 or hb.get(x, y, -1) >= 0:
                continue
            p = self.M("props", x, y)
            p.cylinder(x, y, 0, 3.0, 0.05, (120, 122, 126), seg=6, cap=False)
            p.box(x - 0.3, y - 0.03, 2.4, x + 0.3, y + 0.03, 3.0, (230, 120, 30))
            self.world.add_circle(x, y, 0.1, 3.0, "palo")

    def _signals(self):
        net = self.net
        groups = {}
        for node in net.signal:
            nx_, ny_ = net.nodes[node]
            for (c, d) in net.out[node]:
                ch = net.chains[c]
                if ch.k == "service":
                    continue
                end = 0 if d > 0 else 1
                if ch.ow and end == 0:
                    continue          # a senso unico: il traffico se ne va da questo nodo
                s_stop = ch.trim[end] + 0.5
                if s_stop >= ch.pl.L:
                    continue
                s = s_stop if end == 0 else ch.pl.L - s_stop
                x, y, tx, ty = ch.pl.at(s)
                if end == 0:
                    tx, ty = -tx, -ty          # verso di marcia del traffico in arrivo
                rx, ry = ty, -tx               # destra di chi arriva
                px, py = x + rx * (ch.hw + 0.9), y + ry * (ch.hw + 0.9)
                if self.world.hb.get(px, py, -1) >= 0:
                    continue
                arm = ch.hw + 0.6 if not ch.ow else 2 * ch.hw - 0.5
                arm = min(arm, 14.0)
                hdg = vec_heading(-rx, -ry)     # il braccio va verso il centro della strada
                pole = self.templ["sig_pole"]
                self.M("metal", px, py).add_mesh(pole, px, py, 0, 0)
                am = Mesh()
                am.box(-0.07, 0, 6.2, 0.07, arm, 6.36, (150, 146, 120), faces="xXyYzZ")
                heads = Mesh()
                g = ch.group[end]
                for k in range(3 if arm > 6 else 2):
                    ay = arm - 0.6 - k * min(3.4, (arm - 1) / 2)
                    heads.box(-0.18, ay - 0.17, 5.0, 0.18, ay + 0.17, 6.2, (40, 40, 36), faces="xXyYzZ")
                    heads.box(-0.25, ay - 0.2, 6.15, 0.18, ay + 0.2, 6.2, (40, 40, 36), faces="z")
                    for j, col in enumerate(("r", "y", "g")):
                        zc = 5.95 - j * 0.38
                        b = Mesh()
                        b.box(-0.2, ay - 0.12, zc - 0.12, -0.18, ay + 0.12, zc + 0.12, (255, 255, 255), faces="x")
                        groups.setdefault((g, col), Mesh()).add_mesh(b, px, py, 0, hdg)
                self.M("metal", px, py).add_mesh(am, px, py, 0, hdg)
                self.M("props", px, py).add_mesh(heads, px, py, 0, hdg)
                self.world.add_circle(px, py, 0.2, 6.6, "semaforo")
        self.signal_meshes = groups

    # ------------------------------------------------------------------ pedoni
    def _link_ped(self):
        rings = []
        for wr in self.walk_runs:
            ch, side = wr["ch"], wr["side"]
            mid = (wr["hw"] + wr["so"]) / 2
            if wr["s1"] - wr["s0"] < 4:
                continue
            Q = ch.pl.piece(wr["s0"] + 0.3, wr["s1"] - 0.3)
            if len(Q) < 2:
                continue
            C = offset_line(Q, mid * side)
            rings.append(PathRing(C))
        rings += self.path_rings
        self.ped_rings = rings
        grid = {}
        for ri, r in enumerate(rings):
            for e in (0, 1):
                x, y = r.ends[e]
                grid.setdefault((int(x // 16), int(y // 16)), []).append((ri, e))
        hb = self.world.hb
        for ri, r in enumerate(rings):
            for e in (0, 1):
                x, y = r.ends[e]
                cands = []
                for ix in range(int(x // 16) - 1, int(x // 16) + 2):
                    for iy in range(int(y // 16) - 1, int(y // 16) + 2):
                        for (rj, e2) in grid.get((ix, iy), ()):
                            if rj == ri:
                                continue
                            qx, qy = rings[rj].ends[e2]
                            d = math.hypot(qx - x, qy - y)
                            if d > 16:
                                continue
                            blocked = False
                            for t in np.linspace(0.1, 0.9, 6):
                                if hb.get(x + (qx - x) * t, y + (qy - y) * t, -1) >= 0:
                                    blocked = True
                                    break
                            if not blocked:
                                cands.append((d, rj, e2))
                cands.sort()
                r.links[e].extend((rj, e2) for (_d, rj, e2) in cands[:4])

    def ped_link(self, ring, end):
        """dove andare alla fine di un marciapiede: (anello, posizione, verso) oppure None"""
        try:
            ri = self.ped_rings.index(ring)
        except ValueError:
            return None
        lst = self.ped_rings[ri].links[end]
        if not lst:
            return None
        rj, e2 = random.choice(lst[:3])
        r2 = self.ped_rings[rj]
        return r2, (0.0 if e2 == 0 else r2.length), (1 if e2 == 0 else -1)

    # ------------------------------------------------------------------ periferia
    def _outskirts(self):
        rng = random.Random(9)
        R = self.R
        CL = self.CL
        # orientamento prevalente delle strade (la griglia di LA e' ruotata)
        hist = np.zeros(90)
        for ch in self.net.chains:
            P = ch.pl.P
            D = np.diff(P, axis=0)
            l = np.hypot(D[:, 0], D[:, 1])
            ang = (np.degrees(np.arctan2(D[:, 1], D[:, 0])) % 90).astype(int) % 90
            np.add.at(hist, ang, l)
        th = math.radians(float(np.argmax(np.convolve(np.r_[hist[-3:], hist, hist[:3]], np.ones(7), "valid"))))
        ux, uy = math.cos(th), math.sin(th)
        vx, vy = -uy, ux
        # isolati finti fino all'orizzonte
        cell = 82.0
        outer = CL + 900
        n = int(outer * 1.5 / cell)
        for i in range(-n, n + 1):
            for j in range(-n, n + 1):
                bx = (i * cell) * ux + (j * cell) * vx
                by = (i * cell) * uy + (j * cell) * vy
                d = max(abs(bx), abs(by))
                if d < CL + 45 or d > outer:
                    continue
                far = d > CL + 400
                k = 1 if far else rng.randint(1, 3)
                for _q in range(k):
                    w = rng.uniform(16, 36)
                    dd = rng.uniform(14, 30)
                    ox = rng.uniform(-22, 22)
                    oy = rng.uniform(-22, 22)
                    cx = bx + ux * ox + vx * oy
                    cy = by + uy * ox + vy * oy
                    if max(abs(cx), abs(cy)) < CL + 30:
                        continue
                    h = rng.choice((5, 7, 9, 12, 15, 22, 30)) * (1.0 if d < CL + 300 else 0.8)
                    pts = [(cx - ux * w / 2 - vx * dd / 2, cy - uy * w / 2 - vy * dd / 2),
                           (cx + ux * w / 2 - vx * dd / 2, cy + uy * w / 2 - vy * dd / 2),
                           (cx + ux * w / 2 + vx * dd / 2, cy + uy * w / 2 + vy * dd / 2),
                           (cx - ux * w / 2 + vx * dd / 2, cy - uy * w / 2 + vy * dd / 2)]
                    st = rng.choice(("intonaco_crema", "intonaco_bianco", "intonaco_pesca", "mattoni_rossi", "pietra",
                                     "capannone", "uffici_griglia", "casa0", "casa1"))
                    self._fac_ring(self.M("fac", cx, cy), pts, 0.0, h, FACADE_INDEX[st], None, 0.0, rng, False)
                    flat_poly(self.M("roof", cx, cy), pts, [], h, (190, 190, 186), 6.0)
        # suolo della citta' e colline lontane (a nord le montagne di San Gabriel)
        E = CL + 960
        g = Mesh()
        g.quad((-E, -E, -0.06), (E, -E, -0.06), (E, E, -0.06), (-E, E, -0.06), (255, 255, 255),
               ((-E / 8, -E / 8), (E / 8, -E / 8), (E / 8, E / 8), (-E / 8, E / 8)), (0, 0, 1))
        self.ground_mesh = g
        t = Mesh()
        Nn = 56
        RR = 7000.0
        hn = np.zeros((Nn + 1, Nn + 1))
        for i in range(Nn + 1):
            for j in range(Nn + 1):
                x = -RR + 2 * RR * i / Nn
                y = -RR + 2 * RR * j / Nn
                dd = max(abs(x), abs(y))
                kk = smoothstep(E + 200, E + 2200, dd)
                north = smoothstep(-500, 5000, y)
                hgt = 30 + 120 * (0.5 + 0.5 * math.sin(x * 0.0021 + 1.7) * math.cos(y * 0.0017 - 0.4))
                hgt += 45 * math.sin(x * 0.0071 + y * 0.0049) + 25 * math.sin(x * 0.013 - y * 0.011)
                hgt += north * 700 * (0.6 + 0.4 * math.sin(x * 0.0013 + 0.3)) * smoothstep(3500, 6500, dd)
                hn[i, j] = kk * (hgt + rng.uniform(-15, 15)) - 0.08
        for i in range(Nn):
            for j in range(Nn):
                x0 = -RR + 2 * RR * i / Nn
                y0 = -RR + 2 * RR * j / Nn
                x1 = x0 + 2 * RR / Nn
                y1 = y0 + 2 * RR / Nn
                if max(abs(x0), abs(x1)) < E and max(abs(y0), abs(y1)) < E:
                    continue
                hh = (hn[i, j], hn[i + 1, j], hn[i + 1, j + 1], hn[i, j + 1])

                def col(z):
                    rock = smoothstep(250, 750, z)
                    v = 0.85 + 0.15 * math.sin(z * 0.05)
                    return (int(lerp(150, 176, rock) * v), int(lerp(150, 168, rock) * v), int(lerp(104, 150, rock) * v))
                t.quad4((x0, y0, hh[0]), (x1, y0, hh[1]), (x1, y1, hh[2]), (x0, y1, hh[3]),
                        [col(hh[0]), col(hh[1]), col(hh[2]), col(hh[3])],
                        ((x0 / 30, y0 / 30), (x1 / 30, y0 / 30), (x1 / 30, y1 / 30), (x0 / 30, y1 / 30)))
        self.hills_mesh = t
        self.spots.setdefault("cronenberg", (R * 0.6, 0.0))

    # ------------------------------------------------------------------ nodi grafici
    def _finalize(self):
        root = self.root
        self.ground_mesh.attach(root, "suolo")
        self.hills_mesh.attach(root, "colline")
        facs = root.attachNewNode("facciate_root")
        self.n_geoms = 0
        small = ("metal", "lamp", "leaves", "fronds", "props", "marks", "helipad")
        for ck, d in sorted(self.tiles.items()):
            cnode = root.attachNewNode("zona")
            lod = LODNode("dettagli")
            lnp = cnode.attachNewNode(lod)
            lod.addSwitch(self.LOD_FAR, 0.0)
            lod.setCenter(Point3((ck[0] + 0.5) * self.TILE, (ck[1] + 0.5) * self.TILE, 0))
            near = lnp.attachNewNode("vicino")
            for key, m in d.items():
                if len(m) == 0:
                    continue
                self.n_geoms += 1
                if key == "fac":
                    m.attach(facs, "facciate")
                else:
                    m.attach(near if key in small else cnode, key)
        self.tiles = {}
        for (grp, col), m in self.signal_meshes.items():
            m.attach(root, "semaforo_%d_%s" % (grp, col))
        self.signal_meshes = {}
        self._apply_states()
        for s_ in self.signs:
            s_.reparentTo(root)

    def _apply_states(self):
        """texture, materiali e shader (non salvati nella cache della geometria)"""
        env = self.env
        root = self.root
        self.sig_nodes = {}
        for np_ in root.findAllMatches("**/+GeomNode"):
            name = np_.getName()
            if name == "suolo":
                np_.setTexture(self.T["ground"])
                np_.setShaderInput("u_mat", Vec4(*self.MAT["ground"]))
            elif name == "colline":
                np_.setTexture(self.T["grass"])
                np_.setShaderInput("u_mat", Vec4(0.05, 8, 0.0, 0))
                np_.hide(MASK_SHADOW)
            elif name == "facciate":
                continue
            elif name.startswith("semaforo_"):
                _n, grp, col = name.split("_")
                np_.setShader(env.fx_shader)
                np_.hide(MASK_SHADOW | MASK_MAP)
                self.sig_nodes[(int(grp), col)] = np_
            elif name in self.MAT or name.endswith("flat"):
                key = name
                tkey = key[:-4] if key.endswith("flat") else key
                tex = self.T.get(tkey)
                if tex is not None:
                    np_.setTexture(tex)
                emit = self.E.get(key)
                if emit is not None:
                    np_.setShaderInput("emit_tex", emit)
                np_.setShaderInput("u_mat", Vec4(*self.MAT.get(tkey, (0.25, 24, 0.0, 0))))
                dep = self.DEPTH.get(key)
                if dep:
                    np_.setDepthOffset(dep)
                if key == "fronds":
                    np_.setTwoSided(True)
                if key == "marks":
                    np_.hide(MASK_SHADOW)
        facs = root.find("**/facciate_root")
        if not facs.isEmpty():
            facs.setShader(env.facade_shader)
            facs.setShaderInput("u_fac_alb", self.fac_alb)
            facs.setShaderInput("u_fac_nrm", self.fac_nrm)
            facs.setShaderInput("u_fac_grid", self.fac_grid)
            facs.setShaderInput("u_fac_info", self.fac_info)
            facs.setShaderInput("u_mat", Vec4(*self.MAT["fac"]))
        self.set_signals(0.0)

    # ------------------------------------------------------------------ cache su disco
    @staticmethod
    def cache_dir():
        return os.path.join(os.path.expanduser("~"), ".rick_morty_3d_cache")

    def _save_cache(self, key):
        import gzip
        import pickle
        try:
            d = self.cache_dir()
            os.makedirs(d, exist_ok=True)
            for f in os.listdir(d):          # vecchie versioni
                if f.startswith(self.name + "_") and not f.startswith(key):
                    try:
                        os.remove(os.path.join(d, f))
                    except OSError:
                        pass
            base = os.path.join(d, key)
            cp = self.root.copyTo(NodePath("cache"))
            for n in cp.findAllMatches("**"):
                n.node().setState(RenderState.makeEmpty())
            for n in cp.findAllMatches("**/insegna"):
                n.removeNode()
            w = self.world
            net = self.net
            chains = [{k: getattr(c, k) for k in Chain.__slots__ if k != "pl"} for c in net.chains]
            for c, cd in zip(net.chains, chains):
                cd["P"] = c.pl.P
            meta = dict(
                ver=self.CACHE_VER, S=self.S, R=self.R, limit=self.limit, map_r=self.map_r, CL=self.CL, name=self.name,
                n_buildings=self.n_buildings, n_geoms=self.n_geoms, L=w.hb.L,
                world=dict(boxes=w.boxes, circles=w.circles, gb=w.gb, gc=w.gc, solids=w.solids, eg=w.eg,
                           hb=w.hb.a, hh=w.hh.a),
                gt=self.gt.a, net=dict(nodes=net.nodes, out=net.out, signal=sorted(net.signal), chains=chains),
                rings=[(r.pl.P, r.links) for r in self.ped_rings], lamps=self.lamps, spots=self.spots,
                parking=self.parking, rooftops=self.rooftops, center_park=self.center_park, signs=self.sign_specs,
                map=self.map_img)
            cp.writeBamFile(Filename.fromOsSpecific(base + ".tmp.bam.pz"))
            with gzip.open(base + ".tmp.pkl.gz", "wb", compresslevel=3) as f:
                pickle.dump(meta, f, protocol=4)
            os.replace(base + ".tmp.bam.pz", base + ".bam.pz")
            os.replace(base + ".tmp.pkl.gz", base + ".pkl.gz")
            cp.removeNode()
        except Exception:  # noqa: BLE001
            import traceback
            traceback.print_exc()

    def _load_cache(self, key):
        import gzip
        import pickle
        base = os.path.join(self.cache_dir(), key)
        if not (os.path.exists(base + ".bam.pz") and os.path.exists(base + ".pkl.gz")):
            return False
        root = None
        try:
            self.prog(0.05, "Carico Los Angeles dalla cache")
            with gzip.open(base + ".pkl.gz", "rb") as f:
                meta = pickle.load(f)
            if meta.get("ver") != self.CACHE_VER:
                return False
            for k in ("S", "R", "limit", "map_r", "CL", "name", "n_buildings", "n_geoms"):
                setattr(self, k, meta[k])
            self.prog(0.25, "Texture delle facciate")
            self._textures()
            w = RealWorld.__new__(RealWorld)
            StaticWorld.__init__(w)
            wd = meta["world"]
            for k in ("boxes", "circles", "gb", "gc", "solids", "eg"):
                setattr(w, k, wd[k])
            w.limit = self.limit
            w.hb = Raster.__new__(Raster)
            w.hh = Raster.__new__(Raster)
            self.gt = Raster.__new__(Raster)
            for r, a in ((w.hb, wd["hb"]), (w.hh, wd["hh"]), (self.gt, meta["gt"])):
                r.L, r.res, r.n, r.a = meta["L"], 1.0, a.shape[0], a
            self.world = w
            net = RoadNet()
            nd = meta["net"]
            net.nodes, net.out, net.signal = nd["nodes"], nd["out"], set(nd["signal"])
            for cd in nd["chains"]:
                c = Chain()
                for k, v in cd.items():
                    if k != "P":
                        setattr(c, k, v)
                c.pl = Polyline(cd["P"])
                net.chains.append(c)
            net.finish()
            self.net = net
            rings = []
            for (P, links) in meta["rings"]:
                r = PathRing(P)
                r.links = links
                rings.append(r)
            self.ped_rings = rings
            self.lamps = meta["lamps"]
            self.spots = meta["spots"]
            self.parking = meta["parking"]
            self.rooftops = meta["rooftops"]
            self.center_park = meta["center_park"]
            self.map_img = meta["map"]
            self.prog(0.6, "Geometria della citta'")
            root = self.env.base.loader.loadModel(Filename.fromOsSpecific(base + ".bam.pz"), noCache=True)
            root.reparentTo(self.env.root)
            root.setName("citta")
            self.root = root
            self._apply_states()
            for spec in meta["signs"]:
                self._sign(*spec).reparentTo(root)
            self._lamp_grid()
            self.prog(1.0, "Pronto")
            return True
        except Exception:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            if root is not None:
                root.removeNode()
            return False

    SIG_COL = {"r": (1.0, 0.12, 0.08), "y": (1.0, 0.7, 0.1), "g": (0.15, 1.0, 0.45)}

    def signal_state(self, group, t):
        """stato del semaforo per il gruppo: 'g', 'y' o 'r' (ciclo di 30 s)"""
        c = (t + (0.0 if group == 0 else 15.0)) % 30.0
        if c < 11.5:
            return "g"
        if c < 14.0:
            return "y"
        return "r"

    def set_signals(self, t):
        for (grp, col), np_ in self.sig_nodes.items():
            on = self.signal_state(grp, t) == col
            r, g, b = self.SIG_COL[col]
            k = 1.0 if on else 0.12
            np_.setColorScale(r * k + (0.02 if not on else 0), g * k, b * k, 1)

    def update(self, dt, t):
        self.set_signals(t)

    # ------------------------------------------------------------------ lampioni vicini
    def _lamp_grid(self):
        g = {}
        for (x, y, z) in self.lamps:
            g.setdefault((int(x // 50), int(y // 50)), []).append((x, y, z))
        self.lgrid = g

    def nearest_lamps(self, x, y, n=8, maxd=90.0):
        best = []
        k = int(maxd // 50) + 1
        ix, iy = int(x // 50), int(y // 50)
        for a in range(ix - k, ix + k + 1):
            for b in range(iy - k, iy + k + 1):
                for (lx, ly, lz) in self.lgrid.get((a, b), ()):
                    d = abs(lx - x) + abs(ly - y)
                    if d < maxd:
                        best.append((d, lx, ly, lz))
        best.sort()
        return best[:n]

    # ------------------------------------------------------------------ missioni
    def mission_starts(self):
        sx, sy, _h = self.spots["casa"]
        cpx, cpy = self.center_park
        m4 = self.free_point_near(cpx, cpy - 13)
        hx, hy = self.spots["smith"]
        fx, fy = sx - hx, sy - hy
        l = math.hypot(fx, fy) or 1
        m1 = self.free_point_near(sx + fx / l * 2.5 - fy / l * 3.0, sy + fy / l * 2.5 + fx / l * 3.0)
        return [None, m1, self.spots["polizia"], self.spots["cronenberg"], m4]

    def seed_spots(self):
        out = []
        cpx, cpy = self.center_park
        x, y = self.free_point_near(cpx + 12, cpy - 10)
        out.append((x, y, 0.0))
        roofs = sorted(self.rooftops, key=lambda r: abs(r[2] - 22) + math.hypot(r[0], r[1]) * 0.03)
        out.append(roofs[0] if roofs else (0.0, 0.0, 0.0))
        sx, sy = self.spots["scuola"]
        x, y = self.free_point_near(sx + 25, sy + 25)
        out.append((x, y, 0.0))
        for (qx, qy) in ((-0.55, 0.35), (0.45, -0.5)):
            x, y = self.free_point_near(qx * self.limit, qy * self.limit)
            out.append((x, y, 0.0))
        return out

    # ------------------------------------------------------------------ mappa
    def _make_map(self, size=2048):
        R = self.map_r
        L = self.gt.L
        xs = (np.arange(size) + 0.5) / size * 2 * R - R
        ix = ((xs + L) / self.gt.res).astype(np.int64)
        iy = ix[::-1]
        G = self.gt.a[np.ix_(iy, ix)]
        H = self.world.hh.a[np.ix_(iy, ix)]
        B = self.world.hb.a[np.ix_(iy, ix)]
        img = np.zeros((size, size, 3), np.float32)
        img[:] = (58, 60, 58)
        img[G == 3] = (62, 104, 62)
        img[G == 4] = (60, 96, 140)
        img[G == 5] = (76, 78, 84)
        img[G == 6] = (110, 106, 100)
        img[G == 2] = (128, 126, 122)
        img[G == 1] = (150, 152, 158)
        bl = B >= 0
        v = np.clip(78 + H * 0.55, 78, 170)
        img[bl] = np.stack([v[bl], v[bl], v[bl] + 10], -1)
        return to_u8(img)


# =============================================================================
#  PERSONAGGI 3D (articolati, animati via codice)
# =============================================================================
SKIN_TONES = [(244, 214, 186), (232, 190, 160), (208, 160, 120), (170, 120, 86), (122, 84, 60), (92, 62, 46)]
SHIRTS = [(200, 50, 50), (60, 90, 170), (240, 240, 236), (40, 40, 44), (90, 140, 80), (230, 190, 60), (150, 80, 160),
          (110, 110, 118), (220, 120, 60), (70, 150, 170), (190, 160, 130)]
PANTS = [(40, 50, 80), (60, 60, 66), (30, 30, 34), (110, 90, 70), (150, 140, 120), (70, 90, 120)]
HAIRS = [(30, 22, 18), (70, 46, 28), (120, 80, 40), (200, 170, 110), (150, 150, 150), (180, 70, 30)]

PALETTE_RICK = dict(skin=(238, 216, 194), shirt=(150, 206, 228), pants=(134, 98, 62), shoes=(64, 46, 36),
                    hair=(172, 224, 242), coat=(238, 242, 244))
PALETTE_MORTY = dict(skin=(248, 216, 180), shirt=(247, 222, 76), pants=(58, 102, 172), shoes=(240, 240, 242),
                     hair=(112, 64, 32))


def random_look(rng, kind="ped"):
    if kind == "rick":
        d = dict(PALETTE_RICK)
        d.update(kind="rick", scale=1.0, hair_style="rick", coat=True, head=1.0, width=0.95)
        return d
    if kind == "morty":
        d = dict(PALETTE_MORTY)
        d.update(kind="morty", scale=0.84, hair_style="morty", coat=False, head=1.38, width=1.0)
        return d
    if kind == "grom":
        return dict(kind="grom", skin=(150, 178, 104), shirt=(46, 58, 100), pants=(36, 44, 74), shoes=(24, 24, 28),
                    hair=(0, 0, 0), scale=rng.uniform(0.95, 1.05), hair_style="grom", coat=False, head=1.2, width=1.0)
    if kind == "cronen":
        return dict(kind="cronen", skin=(226, 150, 140), shirt=(200, 110, 110), pants=(170, 90, 96), shoes=(150, 80, 86),
                    hair=(0, 0, 0), scale=rng.uniform(0.9, 1.25), hair_style="cronen", coat=False, head=1.6, width=1.25)
    female = rng.random() < 0.5
    return dict(kind="ped", skin=rng.choice(SKIN_TONES), shirt=rng.choice(SHIRTS), pants=rng.choice(PANTS),
                shoes=rng.choice(((30, 30, 30), (240, 240, 240), (90, 60, 40))), hair=rng.choice(HAIRS),
                scale=rng.uniform(0.9, 1.05) * (0.95 if female else 1.0),
                hair_style=rng.choice(("long", "bun", "short")) if female else rng.choice(("short", "short", "bald", "cap")),
                coat=False, skirt=female and rng.random() < 0.45, head=1.0, width=0.9 if female else 1.0,
                cap_col=rng.choice(SHIRTS))


def build_weapon_mesh(kind):
    m = Mesh()
    if kind == 1:  # pistola laser
        m.box(-0.025, -0.06, -0.03, 0.025, 0.14, 0.03, (150, 158, 170))
        m.box(-0.02, -0.04, -0.12, 0.02, 0.01, -0.03, (80, 84, 92))
        m.cylinder(0, 0.14, -0.0, 0.0, 0.012, (60, 60, 66), seg=6)
        m.box(-0.018, 0.0, 0.03, 0.018, 0.08, 0.055, (110, 240, 70))
        m.cylinder(0, 0.0, 0.14, 0.2, 0.014, (90, 94, 100), seg=8, axis="y")
    elif kind == 2:  # fucile al plasma
        m.box(-0.035, -0.25, -0.04, 0.035, 0.32, 0.05, (70, 76, 92))
        m.box(-0.025, -0.05, -0.16, 0.025, 0.02, -0.04, (50, 52, 60))
        m.box(-0.03, -0.42, -0.08, 0.03, -0.25, 0.03, (60, 62, 70))
        m.box(-0.02, 0.05, 0.05, 0.02, 0.24, 0.085, (90, 170, 255))
        m.cylinder(0, 0.0, 0.32, 0.5, 0.02, (110, 116, 130), seg=8, axis="y")
    else:  # pistola portale
        m.box(-0.03, -0.08, -0.03, 0.03, 0.12, 0.035, (196, 200, 206))
        m.box(-0.022, -0.06, -0.13, 0.022, 0.0, -0.03, (150, 154, 160))
        m.cylinder(0, 0.0, -0.0, 0.0, 0.01, (0, 0, 0), seg=4, cap=False)
        m.cylinder(0, 0.06, 0.12, 0.17, 0.03, (200, 204, 210), seg=10, axis="y", r_top=0.015)
        m.cylinder(0, 0.03, -0.06, 0.08, 0.022, (110, 250, 80), seg=10, axis="y")
    return m


class Rig:
    """Personaggio con articolazioni: anche, ginocchia, spalle, gomiti, testa."""

    def __init__(self, parent, look, seed=0):
        rng = random.Random(seed)
        self.look = look
        s = look.get("scale", 1.0)
        self.root = parent.attachNewNode("personaggio")
        self.body = self.root.attachNewNode("corpo")
        self.body.setScale(s)
        self.height = 1.82 * s
        self.phase = rng.uniform(0, TAU)
        self.anim_speed = 0.0
        self.state = "idle"
        self.dead_t = 0.0
        self.aim_pitch = 0.0
        self.weapon_np = None
        self.weapon_kind = 0
        k = look.get("kind")
        W = look.get("width", 1.0)
        skin, shirt, pants, shoes = look["skin"], look["shirt"], look["pants"], look["shoes"]
        hip_h = 0.92
        self.pelvis = self.body.attachNewNode("bacino")
        self.pelvis.setZ(hip_h)
        pm = Mesh()
        pm.ellipsoid(0, 0, 0.02, 0.17 * W, 0.12, 0.12, pants, seg=10, rings=6)
        if look.get("skirt"):
            pm.cylinder(0, 0, -0.38, 0.06, 0.25 * W, shirt if rng.random() < 0.5 else pants, seg=12, r_top=0.17 * W)
        pm.attach(self.pelvis, "bacino")
        # gambe
        self.hips, self.knees = [], []
        for side in (-1, 1):
            hp = self.pelvis.attachNewNode("anca")
            hp.setPos(side * 0.095 * W, 0, -0.02)
            tm = Mesh()
            tm.ellipsoid(0, 0, -0.22, 0.085 * W, 0.09, 0.25, pants, seg=10, rings=6)
            tm.attach(hp, "coscia")
            kn = hp.attachNewNode("ginocchio")
            kn.setZ(-0.44)
            sm = Mesh()
            sm.ellipsoid(0, 0, -0.2, 0.066 * W, 0.072, 0.23, pants if not look.get("skirt") else skin, seg=10, rings=6)
            sm.box(-0.055, -0.07, -0.48, 0.055, 0.17, -0.40, shoes)
            sm.attach(kn, "stinco")
            self.hips.append(hp)
            self.knees.append(kn)
        # busto
        self.torso = self.pelvis.attachNewNode("busto")
        self.torso.setZ(0.07)
        tm = Mesh()
        tl = 0.52
        tm.ellipsoid(0, 0, 0.2, 0.165 * W, 0.105, 0.25, shirt, seg=12, rings=8)
        tm.ellipsoid(0, 0, 0.4, 0.2 * W, 0.115, 0.16, shirt, seg=12, rings=8)
        tm.cylinder(0, 0, tl - 0.06, tl + 0.1, 0.055, skin, seg=8)
        if k == "grom":
            tm.cylinder(0, 0, 0.0, 0.06, 0.172, (234, 200, 70), seg=12)
            tm.ellipsoid(0.08, 0.11, 0.38, 0.03, 0.01, 0.03, (234, 200, 70), seg=6, rings=4)
        if look.get("coat"):
            c = (238, 242, 244)
            cb = -0.46
            # camice aperto davanti, leggermente svasato in basso
            tm.hexa([(-0.25, -0.15, cb), (0.25, -0.15, cb), (0.25, -0.11, cb), (-0.25, -0.11, cb),
                     (-0.215, -0.135, tl - 0.02), (0.215, -0.135, tl - 0.02), (0.215, -0.1, tl - 0.02), (-0.215, -0.1, tl - 0.02)], c)
            for sx in (-1, 1):
                xo, xi = sx * 0.25, sx * 0.075
                xo2, xi2 = sx * 0.215, sx * 0.05
                pts_b = [(xi, 0.12, cb), (xo, 0.12, cb), (xo, 0.16, cb), (xi, 0.16, cb)]
                pts_t = [(xi2, 0.105, tl - 0.02), (xo2, 0.105, tl - 0.02), (xo2, 0.14, tl - 0.02), (xi2, 0.14, tl - 0.02)]
                if sx < 0:
                    pts_b = [pts_b[1], pts_b[0], pts_b[3], pts_b[2]]
                    pts_t = [pts_t[1], pts_t[0], pts_t[3], pts_t[2]]
                tm.hexa(pts_b + pts_t, c)
                side_b = [(sx * 0.23, -0.15, cb), (sx * 0.26, -0.15, cb), (sx * 0.26, 0.16, cb), (sx * 0.23, 0.16, cb)]
                side_t = [(sx * 0.2, -0.135, tl - 0.02), (sx * 0.225, -0.135, tl - 0.02), (sx * 0.225, 0.14, tl - 0.02),
                          (sx * 0.2, 0.14, tl - 0.02)]
                if sx < 0:
                    side_b = [side_b[1], side_b[0], side_b[3], side_b[2]]
                    side_t = [side_t[1], side_t[0], side_t[3], side_t[2]]
                tm.hexa(side_b + side_t, c)
                # bavero
                tm.hexa([(sx * 0.05, 0.13, tl - 0.24), (sx * 0.1, 0.13, tl - 0.24), (sx * 0.1, 0.15, tl - 0.24),
                         (sx * 0.05, 0.15, tl - 0.24), (sx * 0.06, 0.12, tl), (sx * 0.15, 0.12, tl), (sx * 0.15, 0.14, tl),
                         (sx * 0.06, 0.14, tl)] if sx > 0 else
                        [(sx * 0.1, 0.13, tl - 0.24), (sx * 0.05, 0.13, tl - 0.24), (sx * 0.05, 0.15, tl - 0.24),
                         (sx * 0.1, 0.15, tl - 0.24), (sx * 0.15, 0.12, tl), (sx * 0.06, 0.12, tl), (sx * 0.06, 0.14, tl),
                         (sx * 0.15, 0.14, tl)], (214, 220, 224))
            tm.ellipsoid(0, 0, tl - 0.03, 0.235, 0.15, 0.06, c, seg=12, rings=5)
        tm.attach(self.torso, "busto")
        # testa
        self.head = self.torso.attachNewNode("testa")
        self.head.setZ(tl + 0.1)
        self._head(look, rng)
        # braccia
        self.shoulders, self.elbows, self.hands = [], [], []
        sleeve = (238, 242, 244) if look.get("coat") else shirt
        for side in (-1, 1):
            sh = self.torso.attachNewNode("spalla")
            sh.setPos(side * 0.235 * W, 0, tl - 0.06)
            um = Mesh()
            um.ellipsoid(0, 0, -0.14, 0.06, 0.065, 0.17, sleeve, seg=8, rings=6)
            um.attach(sh, "braccio")
            el = sh.attachNewNode("gomito")
            el.setZ(-0.29)
            fm = Mesh()
            short = k == "ped" and rng.random() < 0.5 or k == "morty"
            fm.ellipsoid(0, 0, -0.12, 0.05, 0.055, 0.15, skin if short else sleeve, seg=8, rings=6)
            fm.ellipsoid(0, 0.0, -0.29, 0.048, 0.04, 0.06, skin if k != "grom" else (150, 178, 104), seg=8, rings=5)
            fm.attach(el, "avambraccio")
            hand = el.attachNewNode("mano")
            hand.setZ(-0.3)
            self.shoulders.append(sh)
            self.elbows.append(el)
            self.hands.append(hand)
        self.root.setShaderInput("u_mat", Vec4(0.2, 18, 0.0, 0.0))

    def _head(self, look, rng):
        k = look.get("kind")
        hs = look.get("head", 1.0)
        skin = look["skin"]
        m = Mesh()
        hair = look.get("hair", (40, 30, 20))
        style = look.get("hair_style")
        eye_y = 0.1 * hs
        if k == "grom":
            m.ellipsoid(0, 0.02, 0.13, 0.13, 0.15, 0.16, skin, seg=12, rings=8)
            for sx in (-1, 1):
                m.ellipsoid(sx * 0.065, 0.12, 0.17, 0.05, 0.04, 0.07, (18, 18, 22), seg=8, rings=6)
                m.ellipsoid(sx * 0.07, 0.15, 0.2, 0.012, 0.008, 0.012, (200, 220, 230), seg=5, rings=3)
                m.cylinder(sx * 0.05, 0.0, 0.27, 0.42, 0.008, skin, seg=4, cap=False)
                m.ellipsoid(sx * 0.05, 0.0, 0.43, 0.02, 0.02, 0.02, skin, seg=5, rings=3)
            m.box(-0.12, -0.11, 0.24, 0.12, 0.13, 0.29, (40, 50, 90))
            m.box(-0.1, 0.1, 0.24, 0.1, 0.2, 0.255, (30, 36, 70))
            m.attach(self.head, "testa")
            return
        if k == "cronen":
            m.ellipsoid(0, 0.02, 0.15, 0.17, 0.16, 0.19, skin, seg=12, rings=8, jitter=0.18, seed=rng.randrange(999),
                        color_var=0.15)
            for (ex, ez, er) in ((-0.07, 0.2, 0.04), (0.06, 0.16, 0.05), (0.12, 0.26, 0.03), (-0.02, 0.3, 0.025)):
                m.ellipsoid(ex, 0.15, ez, er, er * 0.7, er, (245, 245, 240), seg=6, rings=4)
                m.ellipsoid(ex, 0.15 + er * 0.6, ez, er * 0.45, er * 0.3, er * 0.45, (160, 30, 30), seg=6, rings=4)
            m.box(-0.07, 0.14, 0.04, 0.07, 0.17, 0.08, (110, 30, 40))
            m.attach(self.head, "testa")
            return
        if k == "morty":
            m.ellipsoid(0, 0.0, 0.16, 0.16, 0.15, 0.155, skin, seg=14, rings=10)
            m.ellipsoid(0, -0.015, 0.22, 0.168, 0.155, 0.12, hair, seg=14, rings=8)
            m.ellipsoid(0, -0.01, 0.12, 0.16, 0.13, 0.06, skin, seg=12, rings=6)
            for sx in (-1, 1):
                m.ellipsoid(sx * 0.06, 0.13, 0.15, 0.045, 0.02, 0.045, (250, 250, 250), seg=8, rings=6)
                m.ellipsoid(sx * 0.06, 0.149, 0.15, 0.012, 0.006, 0.012, (20, 20, 20), seg=6, rings=4)
                m.ellipsoid(sx * 0.165, 0.0, 0.14, 0.02, 0.03, 0.035, skin, seg=6, rings=4)
            m.box(-0.04, 0.135, 0.065, 0.04, 0.15, 0.075, (90, 50, 40))
            m.attach(self.head, "testa")
            return
        # testa umana (Rick e passanti)
        long_face = 1.25 if k == "rick" else 1.0
        m.ellipsoid(0, 0.0, 0.12 * long_face, 0.1, 0.115, 0.13 * long_face, skin, seg=12, rings=8)
        er = 0.036 if k == "rick" else 0.024
        for sx in (-1, 1):
            m.ellipsoid(sx * 0.1, 0.0, 0.12, 0.018, 0.03, 0.035, skin, seg=6, rings=4)
            m.ellipsoid(sx * 0.042, eye_y - 0.012, 0.155 * long_face, er, er * 0.5, er, (250, 250, 250), seg=8, rings=6)
            m.ellipsoid(sx * 0.042 + (0.008 if k == "rick" and sx > 0 else 0), eye_y - 0.012 + er * 0.48, 0.155 * long_face,
                        er * 0.32, er * 0.12, er * 0.32, (20, 20, 20), seg=6, rings=4)
        m.ellipsoid(0, 0.112, 0.12 * long_face, 0.018, 0.03, 0.025, skin, seg=6, rings=4)
        m.box(-0.035, 0.093, 0.06 * long_face, 0.035, 0.11, 0.066 * long_face, (90, 40, 36))
        if style == "rick":
            m.box(-0.085, 0.086, 0.183 * long_face, 0.085, 0.12, 0.2 * long_face, (130, 190, 214))
            m.ellipsoid(-0.03, 0.105, 0.035, 0.008, 0.004, 0.014, (210, 235, 210), seg=4, rings=3)
            m.ellipsoid(0, -0.015, 0.2 * long_face, 0.103, 0.11, 0.075, hair, seg=12, rings=6)
            cz = 0.13 * long_face
            dirs = [(-90, 30, 0.2), (-90, 60, 0.21), (-90, 95, 0.2), (-90, 130, 0.19),
                    (-45, 40, 0.19), (-45, 85, 0.2), (-45, 125, 0.18),
                    (-135, 40, 0.19), (-135, 85, 0.2), (-135, 125, 0.18),
                    (0, 70, 0.15), (180, 70, 0.15), (-20, 110, 0.15), (-160, 110, 0.15)]
            for az, el, L in dirs:
                a, e = math.radians(az), math.radians(el)
                dx, dy, dz = math.cos(a) * math.sin(e), math.sin(a) * math.sin(e), math.cos(e)
                bx, by, bz = dx * 0.07, dy * 0.08 - 0.01, cz + dz * 0.08
                tip = (bx + dx * L, by + dy * L - 0.04, bz + dz * L * 0.9)
                self._spike(m, (bx, by, bz), tip, 0.056, hair)
        elif style == "short":
            m.ellipsoid(0, -0.01, 0.17, 0.106, 0.12, 0.1, hair, seg=12, rings=6)
        elif style == "long":
            m.ellipsoid(0, -0.02, 0.15, 0.112, 0.125, 0.13, hair, seg=12, rings=6)
            m.ellipsoid(0, -0.07, 0.02, 0.1, 0.06, 0.16, hair, seg=10, rings=6)
        elif style == "bun":
            m.ellipsoid(0, -0.01, 0.17, 0.108, 0.122, 0.1, hair, seg=12, rings=6)
            m.ellipsoid(0, -0.1, 0.23, 0.05, 0.05, 0.05, hair, seg=8, rings=5)
        elif style == "cap":
            c = look.get("cap_col", (200, 40, 40))
            m.ellipsoid(0, -0.005, 0.18, 0.108, 0.122, 0.09, c, seg=12, rings=6)
            m.box(-0.07, 0.06, 0.19, 0.07, 0.19, 0.205, c)
        m.attach(self.head, "testa")

    @staticmethod
    def _spike(m, base, tip, r, col):
        """cono da base a tip (per i capelli a punta di Rick)"""
        bx, by, bz = base
        tx, ty, tz = tip
        ax, ay, az = tx - bx, ty - by, tz - bz
        L = math.sqrt(ax * ax + ay * ay + az * az) or 1
        ax, ay, az = ax / L, ay / L, az / L
        ux, uy, uz = _norm(_cross((ax, ay, az), (1, 0, 0) if abs(ax) < 0.9 else (0, 1, 0)))
        vx, vy, vz = _cross((ax, ay, az), (ux, uy, uz))
        c = _col(col)
        seg = 5
        ti = m.v(tip, (ax, ay, az), c)
        ring = []
        for i in range(seg):
            a = TAU * i / seg
            ca, sa = math.cos(a), math.sin(a)
            nx, ny, nz = ux * ca + vx * sa, uy * ca + vy * sa, uz * ca + vz * sa
            ring.append(m.v((bx + nx * r, by + ny * r, bz + nz * r), (nx, ny, nz), c))
        for i in range(seg):
            m.tri(ring[i], ring[(i + 1) % seg], ti)

    # --------------------------------------------------------------- armi
    def set_weapon(self, kind, meshes):
        if self.weapon_np is not None:
            self.weapon_np.removeNode()
            self.weapon_np = None
        self.weapon_kind = kind
        if kind <= 0:
            return
        self.weapon_np = meshes[kind].copyTo(self.hands[1])
        self.weapon_np.setPos(0, 0.02, -0.02)
        self.weapon_np.setHpr(0, -90, 0)

    # --------------------------------------------------------------- animazione
    def animate(self, dt, speed, state="move", aim=False, aim_pitch=0.0):
        """speed in m/s. state: move, sit, dead, fall, ride"""
        b = self.body
        if state == "dead":
            self.dead_t += dt
            k = min(1.0, self.dead_t * 2.5)
            b.setP(-88 * k * k)
            b.setZ(0.12 * k)
            for i, hp in enumerate(self.hips):
                hp.setP(lerp(hp.getP(), 10 + i * 8, 0.2))
                self.knees[i].setP(lerp(self.knees[i].getP(), -20, 0.2))
            for i, sh in enumerate(self.shoulders):
                sh.setR(lerp(sh.getR(), (-1 if i == 0 else 1) * 70, 0.2))
            return
        self.dead_t = 0
        b.setP(0)
        if state == "sit":
            for hp in self.hips:
                hp.setP(85)
            for kn in self.knees:
                kn.setP(-85)
            b.setZ(-0.38)
            for i, sh in enumerate(self.shoulders):
                sh.setP(48)
                sh.setR(0)
                self.elbows[i].setP(22)
            self.torso.setP(-6)
            return
        if state == "fall":
            for i, hp in enumerate(self.hips):
                hp.setP(25 if i else -10)
                self.knees[i].setP(-50)
            for sh in self.shoulders:
                sh.setP(20)
                sh.setR(0)
            b.setZ(0)
            return
        run = clamp(speed / 7.0, 0, 1)
        walk = clamp(speed / 1.6, 0, 1)
        stride = 1.35 + run * 0.9
        self.phase = (self.phase + speed / stride * TAU * dt) % TAU
        sw = math.sin(self.phase)
        amp = 28 * walk + 22 * run
        for i, hp in enumerate(self.hips):
            s = sw if i == 0 else -sw
            hp.setP(s * amp)
            c = math.cos(self.phase + (0 if i == 0 else math.pi))
            self.knees[i].setP(-max(0.0, c) * (25 * walk + 55 * run) - 4)
        bob = abs(math.cos(self.phase)) * (0.02 * walk + 0.05 * run)
        b.setZ(bob)
        self.torso.setP(-run * 9)
        for i, sh in enumerate(self.shoulders):
            s = -sw if i == 0 else sw
            sh.setR(0)
            if aim and i == 1:
                sh.setP(85 + aim_pitch)
                self.elbows[i].setP(4)
            elif aim and i == 0 and self.weapon_kind == 2:
                sh.setP(70 + aim_pitch)
                sh.setR(-25)
                self.elbows[i].setP(30)
            else:
                sh.setP(s * (22 * walk + 30 * run) + (15 if self.weapon_kind and i == 1 else 0))
                self.elbows[i].setP(10 + run * 60 + (25 if self.weapon_kind and i == 1 else 0))
        if speed < 0.1:
            t = self.phase
            self.torso.setP(math.sin(t * 0.3) * 1.2)


# =============================================================================
#  VEICOLI (modelli)
# =============================================================================
CAR_TYPES = {
    "berlina": dict(L=4.6, W=1.84, H=1.45, wheel=0.34, mass=1.0, top=46.0, acc=8.5, grip=9.0, colors=[
        (190, 30, 30), (30, 60, 140), (230, 230, 228), (30, 30, 34), (150, 150, 156), (40, 110, 70), (200, 170, 60)]),
    "utilitaria": dict(L=3.9, W=1.72, H=1.5, wheel=0.31, mass=0.85, top=40.0, acc=8.0, grip=9.5, colors=[
        (220, 200, 60), (70, 160, 200), (220, 90, 40), (240, 240, 236), (110, 50, 120)]),
    "furgone": dict(L=5.2, W=2.0, H=2.3, wheel=0.36, mass=1.6, top=34.0, acc=6.0, grip=7.5, colors=[
        (240, 240, 236), (60, 70, 90), (180, 40, 40), (90, 110, 60)]),
    "sportiva": dict(L=4.4, W=1.9, H=1.18, wheel=0.35, mass=0.95, top=62.0, acc=12.5, grip=11.0, colors=[
        (220, 30, 30), (255, 200, 0), (30, 30, 34), (20, 120, 220), (240, 240, 240)]),
    "polizia": dict(L=4.7, W=1.86, H=1.5, wheel=0.35, mass=1.1, top=55.0, acc=11.0, grip=10.5, colors=[(28, 36, 86)]),
    "navicella": dict(L=4.4, W=2.3, H=1.3, wheel=0.0, mass=0.9, top=58.0, acc=12.0, grip=8.0, colors=[(176, 184, 190)],
                      fly=True),
}


SEAT = {  # posizione del guidatore: (x, y, z)
    "berlina": (-0.38, -0.05, -0.1), "utilitaria": (-0.36, -0.15, -0.06), "furgone": (-0.42, 1.25, 0.3),
    "sportiva": (-0.38, -0.15, -0.3), "polizia": (-0.38, -0.05, -0.08), "navicella": (0.0, 0.25, 0.35),
}


def loft_body(m, L, hw, z0, belt, kind):
    """carrozzeria arrotondata costruita per sezioni (cofano inclinato, spigoli smussati, normali morbide)"""
    T = np.array([-1.0, -0.975, -0.93, -0.84, -0.55, -0.1, 0.3, 0.55, 0.75, 0.88, 0.95, 0.985, 1.0])
    van = kind == "furgone"
    sport = kind == "sportiva"
    h0 = belt - z0
    prof = [(0.93, 0.0), (1.0, 0.13), (1.0, 0.6), (0.97, 0.86), (0.84, 0.97), (0.45, 1.0), (0.0, 1.005)]
    prof = prof + [(-x, z) for (x, z) in reversed(prof[:-1])]
    K = len(prof)
    P = np.zeros((len(T), K, 3))
    for i, t in enumerate(T):
        a = abs(t)
        sx = 1.0 - (0.04 if van else 0.13) * max(0.0, a - 0.82) / 0.18
        sx -= (0.0 if van else 0.06) * max(0.0, a - 0.96) / 0.04
        h = h0
        if t > 0.25:
            h -= (0.04 if van else (0.16 if sport else 0.09)) * (t - 0.25) / 0.75
        if t > 0.9:
            h -= (0.05 if van else 0.13) * (t - 0.9) / 0.1
        if t < -0.82:
            h -= (0.03 if van else 0.07) * (a - 0.82) / 0.18
        zb = z0 + (0.0 if van else 0.08) * max(0.0, a - 0.8) / 0.2
        y = t * L / 2
        for k, (px, pz) in enumerate(prof):
            P[i, k] = (px * hw * sx, y, zb + pz * (z0 + h - zb))
    I_, K_ = P.shape[0], P.shape[1]
    # normali morbide: media delle facce adiacenti
    N = np.zeros_like(P)
    for i in range(I_ - 1):
        for k in range(K_ - 1):
            n = np.cross(P[i + 1, k] - P[i, k], P[i, k + 1] - P[i, k])
            for (a_, b_) in ((i, k), (i + 1, k), (i, k + 1), (i + 1, k + 1)):
                N[a_, b_] += n
    N /= np.maximum(np.linalg.norm(N, axis=2, keepdims=True), 1e-9)
    V = np.zeros((I_ * K_, 12), np.float32)
    V[:, 0:3] = P.reshape(-1, 3)
    V[:, 3:6] = N.reshape(-1, 3)
    V[:, 6:10] = 1.0
    V[:, 10] = (P[:, :, 1].reshape(-1) / L + 0.5)
    V[:, 11] = P[:, :, 2].reshape(-1)
    idx = []
    for i in range(I_ - 1):
        for k in range(K_ - 1):
            a_ = i * K_ + k
            b_ = (i + 1) * K_ + k
            idx += [a_, b_, b_ + 1, a_, b_ + 1, a_ + 1]
    m.chunks.append((V, np.asarray(idx, np.uint32)))
    # tappi davanti e dietro
    for i, front in ((0, False), (I_ - 1, True)):
        ring = P[i]
        c = ring.mean(axis=0)
        for k in range(K_):
            a_, b_ = tuple(ring[k]), tuple(ring[(k + 1) % K_])
            if front:
                m.quad(tuple(c), b_, a_, a_, (255, 255, 255), n=(0, 1, 0))
            else:
                m.quad(tuple(c), a_, b_, b_, (255, 255, 255), n=(0, -1, 0))


class CarFactory:
    """Crea i modelli delle auto una volta sola e li copia per ogni veicolo."""

    def __init__(self, env):
        self.env = env
        self.templates = {}
        lamp = np.zeros((4, 4, 3), np.uint8)
        lamp[:] = (255, 245, 220)
        self.head_emit = make_texture(lamp, "fari", mipmap=False)
        red = np.zeros((4, 4, 3), np.uint8)
        red[:] = (255, 40, 30)
        self.tail_emit = make_texture(red, "stop", mipmap=False)
        blue = np.zeros((4, 4, 3), np.uint8)
        blue[:] = (120, 200, 255)
        self.blue_emit = make_texture(blue, "blu", mipmap=False)

    def template(self, kind):
        if kind not in self.templates:
            self.templates[kind] = self._build(kind)
        return self.templates[kind]

    def _build(self, kind):
        d = CAR_TYPES[kind]
        L, W, H, wr = d["L"], d["W"], d["H"], d["wheel"]
        root = NodePath("auto_" + kind)
        body = root.attachNewNode("carrozzeria")
        paint, glass, dark, chrome, head, tail = Mesh(), Mesh(), Mesh(), Mesh(), Mesh(), Mesh()
        WH = (255, 255, 255)
        hw = W / 2
        if kind == "navicella":
            paint.ellipsoid(0, 0, 0.75, hw, L / 2, 0.38, WH, seg=20, rings=10)
            paint.ellipsoid(0, -0.4, 0.95, hw * 0.75, L * 0.32, 0.28, WH, seg=16, rings=8)
            dark.ellipsoid(0, 0.15, 1.02, hw * 0.55, 0.75, 0.22, (40, 40, 46), seg=14, rings=6)
            glass.ellipsoid(0, 0.95, 1.12, hw * 0.55, 0.32, 0.26, (120, 200, 230, 150), seg=14, rings=6)
            for sx in (-1, 1):
                chrome.cylinder(sx * 0.7, -L / 2 + 0.2, 0.55, 0.85, 0.22, (150, 150, 160), seg=12, axis="y", r_top=0.17)
                tail.cylinder(sx * 0.7, -L / 2 + 0.12, 0.56, 0.86, 0.16, (120, 200, 255), seg=12, axis="y")
                dark.cylinder(sx * (hw - 0.3), L / 2 - 0.9, 0.0, 0.42, 0.12, (60, 60, 66), seg=8)
                dark.cylinder(sx * (hw - 0.3), -L / 2 + 1.0, 0.0, 0.42, 0.12, (60, 60, 66), seg=8)
            head.box(-0.5, L / 2 - 0.15, 0.68, 0.5, L / 2 - 0.05, 0.78, WH)
            dark.box(-0.05, 0.25, 0.85, 0.05, 0.6, 1.25, (60, 60, 66))
            dark.cylinder(0, 0.6, 1.2, 1.24, 0.18, (40, 40, 44), seg=12, axis="y")
        else:
            z0 = wr * 0.9
            belt = z0 + (H - z0) * 0.52
            nose, tailo = (0.7, 0.55) if kind != "furgone" else (0.25, 0.1)
            loft_body(paint, L, hw, z0, belt, kind)
            dark.box(-hw - 0.01, L / 2 - 0.05, z0 - 0.04, hw + 0.01, L / 2 + 0.08, z0 + 0.22, (40, 40, 44))
            dark.box(-hw - 0.01, -L / 2 - 0.08, z0 - 0.04, hw + 0.01, -L / 2 + 0.05, z0 + 0.22, (40, 40, 44))
            if kind == "furgone":
                cab_y0, cab_y1 = -L / 2 + 0.15, L / 2 - 0.9
                top_y0, top_y1 = cab_y0, L / 2 - 1.25
            elif kind == "sportiva":
                cab_y0, cab_y1 = -L / 2 + 1.2, L / 2 - 1.55
                top_y0, top_y1 = -L / 2 + 1.75, L / 2 - 2.15
            elif kind == "utilitaria":
                cab_y0, cab_y1 = -L / 2 + 0.35, L / 2 - 1.15
                top_y0, top_y1 = -L / 2 + 0.55, L / 2 - 1.75
            else:
                cab_y0, cab_y1 = -L / 2 + 1.0, L / 2 - 1.35
                top_y0, top_y1 = -L / 2 + 1.5, L / 2 - 2.0
            ins = 0.12 if kind != "furgone" else 0.06
            glass.frustum(-hw + 0.06, cab_y0, hw - 0.06, cab_y1, belt, H - 0.05, -hw + ins + 0.06, top_y0, hw - ins - 0.06,
                          top_y1, (60, 80, 100, 150))
            paint.frustum(-hw + ins + 0.04, top_y0 - 0.02, hw - ins - 0.04, top_y1 + 0.02, H - 0.06, H, -hw + ins + 0.08,
                          top_y0 + 0.05, hw - ins - 0.08, top_y1 - 0.05, WH)
            # montanti
            for sx in (-1, 1):
                x_b = sx * (hw - 0.07)
                x_t = sx * (hw - ins - 0.07)
                mid_b = (cab_y0 + cab_y1) / 2
                mid_t = (top_y0 + top_y1) / 2
                paint.hexa([(x_b - 0.03, mid_b - 0.05, belt), (x_b + 0.03, mid_b - 0.05, belt),
                            (x_b + 0.03, mid_b + 0.05, belt), (x_b - 0.03, mid_b + 0.05, belt),
                            (x_t - 0.03, mid_t - 0.05, H - 0.05), (x_t + 0.03, mid_t - 0.05, H - 0.05),
                            (x_t + 0.03, mid_t + 0.05, H - 0.05), (x_t - 0.03, mid_t + 0.05, H - 0.05)], WH)
                # specchietti
                paint.box(sx * hw - (0.18 if sx > 0 else -0.02), cab_y1 - 0.15, belt + 0.02, sx * hw + (0.02 if sx > 0 else 0.18) - (0.0),
                          cab_y1 - 0.02, belt + 0.14, WH)
                # passaruota (semicerchi scuri sulla fiancata)
                for wy in (L / 2 - 0.85 * (L / 4.6), -L / 2 + 0.95 * (L / 4.6)):
                    xs = sx * (hw + 0.012)
                    rr = wr + 0.07
                    pts = [(xs, wy + math.cos(a_) * rr, wr + math.sin(a_) * rr) for a_ in np.linspace(0, math.pi, 10)]
                    for j in range(len(pts) - 1):
                        a0, a1 = pts[j], pts[j + 1]
                        b0, b1 = (xs, a0[1], z0 - 0.04), (xs, a1[1], z0 - 0.04)
                        if sx > 0:
                            dark.quad(b0, b1, a1, a0, (22, 22, 25), n=(1, 0, 0))
                        else:
                            dark.quad(b1, b0, a0, a1, (22, 22, 25), n=(-1, 0, 0))
                # linee porte e maniglie
                dark.box(sx * (hw + 0.004) - 0.004, -0.1, z0 + 0.12, sx * (hw + 0.004) + 0.004, -0.08, belt - 0.03, (30, 30, 34))
                chrome.box(sx * (hw + 0.01) - 0.01, 0.25, belt - 0.12, sx * (hw + 0.01) + 0.01, 0.42, belt - 0.08, (200, 200, 205))
            # fari e stop
            for sx in (-1, 1):
                head.box(sx * hw * 0.62 - 0.2, L / 2 - 0.11, z0 + 0.3, sx * hw * 0.62 + 0.2, L / 2 - 0.02, z0 + 0.44, WH)
                tail.box(sx * hw * 0.68 - 0.18, -L / 2 + 0.02, z0 + 0.32, sx * hw * 0.68 + 0.18, -L / 2 + 0.11, z0 + 0.46, WH)
            chrome.box(-0.35, L / 2 - 0.05, z0 + 0.08, 0.35, L / 2 + 0.09, z0 + 0.28, (60, 62, 68))
            dark.box(-0.26, -L / 2 - 0.1, z0 + 0.08, 0.26, -L / 2 - 0.07, z0 + 0.2, (236, 236, 230))
            dark.box(-0.26, L / 2 + 0.07, z0 + 0.04, 0.26, L / 2 + 0.1, z0 + 0.16, (236, 236, 230))
            # interni visibili dai vetri
            dark.box(-hw + 0.15, cab_y0 + 0.2, z0 + 0.1, hw - 0.15, cab_y1 - 0.1, belt - 0.05, (40, 36, 34))
            dark.box(-hw + 0.2, cab_y1 - 0.45, belt - 0.05, hw - 0.2, cab_y1 - 0.15, belt + 0.12, (34, 34, 36))
            dark.cylinder(-0.38, cab_y1 - 0.5, belt + 0.05, belt + 0.07, 0.17, (20, 20, 22), seg=10, axis="y")
            if kind == "polizia":
                paint.box(-hw - 0.005, -0.9, z0 + 0.15, hw + 0.005, 0.9, z0 + 0.3, (234, 200, 70))
                mid = (top_y0 + top_y1) / 2
                dark.box(-0.6, mid - 0.15, H, 0.6, mid + 0.15, H + 0.06, (30, 30, 34))
        nodes = {}
        nodes["paint"] = paint.attach(body, "vernice", None, None, (1.0, 90, 0.45, 0.0))
        nodes["glass"] = glass.attach(body, "vetri", None, None, (1.2, 140, 0.75, 0.0))
        nodes["glass"].setTransparency(TransparencyAttrib.M_alpha)
        nodes["glass"].setDepthWrite(False)
        nodes["dark"] = dark.attach(body, "plastica", None, None, (0.3, 30, 0.05, 0.0))
        nodes["chrome"] = chrome.attach(body, "cromature", None, None, (1.2, 120, 0.7, 0.0))
        nodes["head"] = head.attach(body, "fari", None, self.head_emit, (1.0, 100, 0.4, 1.0))
        tail_emit = self.blue_emit if kind == "navicella" else self.tail_emit
        nodes["tail"] = tail.attach(body, "stop", None, tail_emit, (1.0, 100, 0.3, 1.0))
        nodes["tail"].setColorScale(1.0, 0.25, 0.2, 1) if kind != "navicella" else None
        if kind == "polizia":
            mid = 0.0
            for sx, col in ((-1, (255, 40, 40)), (1, (40, 90, 255))):
                lb = Mesh()
                lb.box(sx * 0.5 - 0.22, -0.13, 0.0, sx * 0.5 + 0.22, 0.13, 0.12, (255, 255, 255))
                e = np.zeros((4, 4, 3), np.uint8)
                e[:] = col
                n = lb.attach(body, "lampeggiante", None, make_texture(e, "lamp", mipmap=False), (1.0, 60, 0.0, 1.0))
                n.setColorScale(col[0] / 255.0, col[1] / 255.0, col[2] / 255.0, 1)
                cab_mid = ((-L / 2 + 1.5) + (L / 2 - 2.0)) / 2
                n.setPos(0, cab_mid, H + 0.06)
                nodes["siren%d" % (0 if sx < 0 else 1)] = n
        # ruote
        wheels = []
        if wr > 0:
            wm = Mesh()
            wm.cylinder(0, 0, -0.12, 0.12, wr, (24, 24, 26), seg=16, axis="x")
            wm.cylinder(0, 0, 0.121, 0.125, wr * 0.62, (170, 172, 178), seg=12, axis="x")
            wm.cylinder(0, 0, -0.125, -0.121, wr * 0.62, (170, 172, 178), seg=12, axis="x")
            for k, (sx, wy) in enumerate(((-1, L / 2 - 0.85 * (L / 4.6)), (1, L / 2 - 0.85 * (L / 4.6)),
                                         (-1, -L / 2 + 0.95 * (L / 4.6)), (1, -L / 2 + 0.95 * (L / 4.6)))):
                steer = root.attachNewNode("sterzo")
                steer.setPos(sx * (hw - 0.14), wy, wr)
                spin = wm.attach(steer, "ruota", None, None, (0.2, 20, 0.02, 0))
                wheels.append((steer, spin, k < 2))
        return dict(root=root, nodes=nodes, wheels=wheels, dims=(L, W, H, wr))

    def make(self, kind, parent, color=None):
        t = self.template(kind)
        np_ = t["root"].copyTo(parent)
        body = np_.find("carrozzeria")
        paint = body.find("vernice")
        if color is not None:
            paint.setColorScale(color[0] / 255.0, color[1] / 255.0, color[2] / 255.0, 1)
        nodes = {k: body.find(v.getName()) for k, v in t["nodes"].items() if not k.startswith("siren")}
        sirens = [c for c in body.findAllMatches("lampeggiante")]
        wheels = []
        steers = np_.findAllMatches("sterzo")
        for i in range(steers.getNumPaths()):
            st = steers.getPath(i)
            wheels.append((st, st.find("ruota"), i < 2))
        return dict(root=np_, body=body, nodes=nodes, sirens=sirens, wheels=wheels, dims=t["dims"])


# =============================================================================
#  EFFETTI VISIVI: particelle (fuoco, fumo, scintille), raggi laser, portali
# =============================================================================
from panda3d.core import OmniBoundingVolume  # noqa: E402

_QUAD_OFF = np.array([[-1, -1], [1, -1], [1, 1], [-1, 1]], np.float32)
_QUAD_UV = np.array([[0, 0], [1, 0], [1, 1], [0, 1]], np.float32)


class FXLayer:
    def __init__(self, game, tex, additive, cap=2500):
        self.cap = cap
        self.n = 0
        z = lambda *s: np.zeros(s, np.float32)
        self.pos, self.vel = z(cap, 3), z(cap, 3)
        self.life, self.maxlife = z(cap), z(cap) + 1
        self.s0, self.s1 = z(cap), z(cap)
        self.c0, self.c1 = z(cap, 4), z(cap, 4)
        self.grav, self.drag, self.stretch = z(cap), z(cap), z(cap)
        self.beams = []
        self.vdata = GeomVertexData("fx", vertex_format(), Geom.UH_dynamic)
        self.vdata.uncleanSetNumRows(cap * 4 + 400)
        self.prim = GeomTriangles(Geom.UH_dynamic)
        self.prim.setIndexType(Geom.NT_uint32)
        q = np.arange(cap + 100, dtype=np.uint32) * 4
        self.idx = np.stack([q, q + 1, q + 2, q, q + 2, q + 3], 1).reshape(-1)
        g = Geom(self.vdata)
        g.addPrimitive(self.prim)
        gn = GeomNode("effetti")
        gn.addGeom(g)
        gn.setBounds(OmniBoundingVolume())
        gn.setFinal(True)
        self.np = game.render.attachNewNode(gn)
        self.np.setShader(game.env.fx_shader)
        self.np.setTexture(tex)
        self.np.setLightOff(1)
        self.np.setDepthWrite(False)
        self.np.setTwoSided(True)
        self.np.hide(MASK_SHADOW | MASK_MAP)
        if additive:
            self.np.setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.M_add, ColorBlendAttrib.O_incoming_alpha,
                                                    ColorBlendAttrib.O_one))
            self.np.setBin("fixed", 20)
        else:
            self.np.setTransparency(TransparencyAttrib.M_alpha)
            self.np.setBin("fixed", 10)

    def emit(self, pos, vel, life, s0, s1, c0, c1, grav=0.0, drag=0.0, stretch=0.0, count=1, spread=0.0, jitter=0.0):
        rng = np.random
        for _ in range(count):
            if self.n >= self.cap:
                return
            i = self.n
            self.n += 1
            p = np.array(pos, np.float32)
            if jitter:
                p += (rng.random(3).astype(np.float32) - 0.5) * jitter
            v = np.array(vel, np.float32)
            if spread:
                d = rng.normal(size=3).astype(np.float32)
                d /= (np.linalg.norm(d) + 1e-6)
                v = v + d * spread * rng.uniform(0.3, 1.0)
            self.pos[i] = p
            self.vel[i] = v
            l = life * rng.uniform(0.7, 1.15)
            self.life[i] = l
            self.maxlife[i] = l
            self.s0[i] = s0
            self.s1[i] = s1
            self.c0[i] = c0
            self.c1[i] = c1
            self.grav[i] = grav
            self.drag[i] = drag
            self.stretch[i] = stretch

    def beam(self, a, b, width, color):
        self.beams.append((a, b, width, color))

    def update(self, dt, cam_pos, right, up):
        n = self.n
        if n:
            self.life[:n] -= dt
            alive = self.life[:n] > 0
            if not alive.all():
                k = int(alive.sum())
                for arr in (self.pos, self.vel, self.life, self.maxlife, self.s0, self.s1, self.c0, self.c1, self.grav,
                            self.drag, self.stretch):
                    arr[:k] = arr[:n][alive]
                n = self.n = k
        if n:
            self.vel[:n, 2] -= self.grav[:n] * dt
            self.vel[:n] *= np.clip(1.0 - self.drag[:n] * dt, 0, 1)[:, None]
            self.pos[:n] += self.vel[:n] * dt
        nb = len(self.beams)
        total = n + nb
        if total == 0:
            self.prim.modifyVertices().uncleanSetNumRows(0)
            return
        V = np.zeros((total * 4, 12), np.float32)
        if n:
            t = 1.0 - self.life[:n] / self.maxlife[:n]
            size = self.s0[:n] + (self.s1[:n] - self.s0[:n]) * t
            col = self.c0[:n] + (self.c1[:n] - self.c0[:n]) * t[:, None]
            R = np.array(right, np.float32)
            U = np.array(up, np.float32)
            rr = np.broadcast_to(R, (n, 3)) * size[:, None]
            uu = np.broadcast_to(U, (n, 3)) * size[:, None]
            st = self.stretch[:n] > 0
            if st.any():
                v = self.vel[:n][st]
                sp = np.linalg.norm(v, axis=1) + 1e-5
                axis = v / sp[:, None]
                uu = uu.copy()
                rr = rr.copy()
                uu[st] = axis * (size[st] + sp * self.stretch[:n][st])[:, None]
                cp = np.array(cam_pos, np.float32)
                tocam = cp - self.pos[:n][st]
                side = np.cross(axis, tocam)
                side /= (np.linalg.norm(side, axis=1)[:, None] + 1e-5)
                rr[st] = side * size[st][:, None] * 0.35
            P = self.pos[:n]
            pv = V[:n * 4].reshape(n, 4, 12)
            for k in range(4):
                ox, oy = _QUAD_OFF[k]
                pv[:, k, 0:3] = P + rr * ox + uu * oy
                pv[:, k, 6:10] = col
                pv[:, k, 10:12] = _QUAD_UV[k]
        if nb:
            cp = np.array(cam_pos, np.float32)
            for j, (a, b, w, c) in enumerate(self.beams):
                a = np.array(a, np.float32)
                b = np.array(b, np.float32)
                d = b - a
                side = np.cross(d, cp - a)
                l = np.linalg.norm(side)
                side = side / l * w if l > 1e-6 else np.array([w, 0, 0], np.float32)
                base = (n + j) * 4
                V[base + 0, 0:3] = a - side
                V[base + 1, 0:3] = a + side
                V[base + 2, 0:3] = b + side
                V[base + 3, 0:3] = b - side
                V[base:base + 4, 6:10] = c
                V[base + 0, 10:12] = (0.5, 0)
                V[base + 1, 10:12] = (0.5, 1)
                V[base + 2, 10:12] = (0.5, 1)
                V[base + 3, 10:12] = (0.5, 0)
            self.beams = []
        memoryview(self.vdata.modifyArray(0)).cast("B")[:V.nbytes] = V.tobytes()
        ia = self.prim.modifyVertices()
        ia.uncleanSetNumRows(total * 6)
        memoryview(ia).cast("B")[:] = self.idx[:total * 6].tobytes()


class FX:
    def __init__(self, game):
        self.game = game
        self.glow = FXLayer(game, make_texture(tex_soft(64, 1.6), "bagliore", repeat=False), True)
        self.smoke = FXLayer(game, make_texture(tex_smoke(64), "fumo", repeat=False), False, cap=1200)
        self.portal_tex = make_texture(tex_portal(256), "portale", repeat=False)
        self.portals = []
        self.flashes = []  # luci temporanee (x, y, z, raggio, r, g, b, vita)

    # --- effetti pronti -------------------------------------------------------------
    def sparks(self, p, n=10, col=(1.0, 0.8, 0.4, 1.0), speed=6.0):
        self.glow.emit(p, (0, 0, 1.0), 0.45, 0.06, 0.02, col, (col[0], col[1] * 0.5, 0.0, 0.0), grav=9.0, drag=0.5,
                       stretch=0.03, count=n, spread=speed)

    def impact(self, p, col):
        self.glow.emit(p, (0, 0, 0), 0.18, 0.35, 0.9, col, (col[0], col[1], col[2], 0.0))
        self.sparks(p, 6, col, 4.0)
        self.smoke.emit(p, (0, 0, 0.6), 0.9, 0.2, 0.7, (0.5, 0.5, 0.5, 0.45), (0.4, 0.4, 0.4, 0.0), spread=0.6, count=2)

    def muzzle(self, p, col):
        self.glow.emit(p, (0, 0, 0), 0.07, 0.25, 0.45, col, (col[0], col[1], col[2], 0.0))
        self.flashes.append([p[0], p[1], p[2], 9.0, col[0] * 3, col[1] * 3, col[2] * 3, 0.06])

    def laser(self, a, b, col, width=0.05):
        self.glow.beam(a, b, width * 3.0, (col[0] * 0.5, col[1] * 0.5, col[2] * 0.5, 0.6))
        self.glow.beam(a, b, width, (1.0, 1.0, 1.0, 1.0))
        self.glow.beam(a, b, width * 1.6, (col[0], col[1], col[2], 1.0))

    def blood(self, p, cronen=False):
        col = (0.75, 0.05, 0.05, 1.0) if not cronen else (0.9, 0.45, 0.4, 1.0)
        self.smoke.emit(p, (0, 0, 1.0), 0.6, 0.08, 0.16, col, (col[0], col[1], col[2], 0.0), grav=9.0, count=8, spread=3.0)

    def explosion(self, p, big=1.0):
        x, y, z = p
        self.glow.emit(p, (0, 0, 2.0), 0.7, 1.5 * big, 4.0 * big, (1.0, 0.75, 0.3, 1.0), (1.0, 0.2, 0.0, 0.0),
                       grav=-2.0, drag=1.2, count=int(18 * big), spread=7.0 * big, jitter=1.0)
        self.glow.emit(p, (0, 0, 0), 0.25, 4.0 * big, 9.0 * big, (1.0, 0.9, 0.6, 1.0), (1.0, 0.5, 0.1, 0.0))
        self.sparks(p, int(25 * big), (1.0, 0.7, 0.3, 1.0), 16.0 * big)
        self.smoke.emit((x, y, z + 1), (0, 0, 2.5), 3.5, 1.4 * big, 5.0 * big, (0.25, 0.22, 0.2, 0.75),
                        (0.35, 0.34, 0.33, 0.0), grav=-0.5, drag=0.6, count=int(14 * big), spread=3.0 * big, jitter=1.5)
        self.flashes.append([x, y, z + 2, 30.0 * big, 22.0, 12.0, 4.0, 0.45])

    def fire(self, p, scale=1.0):
        self.glow.emit(p, (0, 0, 2.2), 0.55, 0.5 * scale, 0.15 * scale, (1.0, 0.6, 0.15, 0.9), (1.0, 0.15, 0.0, 0.0),
                       grav=-1.0, count=2, spread=0.6, jitter=0.6 * scale)
        if random.random() < 0.4:
            self.smoke.emit(p, (0, 0, 2.5), 2.2, 0.5 * scale, 2.0 * scale, (0.15, 0.14, 0.13, 0.6), (0.3, 0.3, 0.3, 0.0),
                            jitter=0.5)

    def smoke_puff(self, p, dark=0.5, size=1.0):
        c = 0.6 - dark * 0.45
        self.smoke.emit(p, (0, 0, 1.4), 1.6, 0.4 * size, 1.6 * size, (c, c, c, 0.5), (c, c, c, 0.0), jitter=0.4)

    def dust(self, p, size=1.0):
        self.smoke.emit(p, (0, 0, 0.6), 1.0, 0.3 * size, 1.4 * size, (0.55, 0.52, 0.48, 0.35), (0.6, 0.58, 0.55, 0.0),
                        spread=1.0, count=2)

    def portal(self, pos, h=0.0, life=1.2, size=1.4, vertical=True, follow=None):
        cm = CardMaker("portale")
        cm.setFrame(-1, 1, -1.5, 1.5)
        np_ = self.game.render.attachNewNode(cm.generate())
        np_.setTexture(self.portal_tex)
        np_.setShader(self.game.env.fx_shader)
        np_.setTransparency(TransparencyAttrib.M_alpha)
        np_.setDepthWrite(False)
        np_.setTwoSided(True)
        np_.setLightOff(1)
        np_.setBin("fixed", 15)
        np_.hide(MASK_SHADOW | MASK_MAP)
        np_.setPos(*pos)
        np_.setH(h)
        if not vertical:
            np_.setP(-90)
        np_.setScale(0.01)
        self.portals.append(dict(np=np_, t=0.0, life=life, size=size, follow=follow))
        self.flashes.append([pos[0], pos[1], pos[2], 14.0, 0.8, 4.0, 0.6, min(life, 1.0)])
        return np_

    def update(self, dt, cam):
        cp = cam.getPos(self.game.render)
        q = cam.getQuat(self.game.render)
        right, up = q.getRight(), q.getUp()
        self.glow.update(dt, cp, right, up)
        self.smoke.update(dt, cp, right, up)
        for p in self.portals:
            p["t"] += dt
            t, life = p["t"], p["life"]
            k = min(1.0, t * 5) * min(1.0, max(0.0, (life - t) * 4)) if life > 0 else min(1.0, t * 5)
            n = p["np"]
            n.setScale(max(0.01, p["size"] * k))
            n.setR(-t * 260)
            if p["follow"] is not None:
                n.setPos(p["follow"]())
            if random.random() < 0.5 and k > 0.5:
                pp = n.getPos()
                self.glow.emit((pp[0], pp[1], pp[2]), (0, 0, 0.5), 0.6, 0.12, 0.02, (0.4, 1.0, 0.3, 1.0),
                               (0.2, 0.8, 0.1, 0.0), spread=1.5)
        keep = []
        for p in self.portals:
            if p["life"] > 0 and p["t"] >= p["life"]:
                p["np"].removeNode()
            else:
                keep.append(p)
        self.portals = keep
        for f in self.flashes:
            f[7] -= dt
        self.flashes = [f for f in self.flashes if f[7] > 0]

    def lights(self):
        out = []
        for f in self.flashes:
            k = clamp(f[7] * 4, 0, 1)
            out.append((f[0], f[1], f[2], f[3], f[4] * k, f[5] * k, f[6] * k))
        return out


# =============================================================================
#  AUDIO SINTETIZZATO (scritto in file WAV temporanei e caricato da Panda3D)
# =============================================================================
SR = 22050


def _t(d):
    return np.arange(int(d * SR), dtype=np.float32) / SR


def _env(n, a=0.005, d=1.0, power=1.5):
    t = np.linspace(0, 1, n, dtype=np.float32)
    e = (1 - t) ** power
    na = max(1, int(a * SR))
    e[:na] *= np.linspace(0, 1, na, dtype=np.float32)
    return e


def _sweep(f0, f1, d, wave="sin"):
    t = _t(d)
    f = f0 + (f1 - f0) * (t / d)
    ph = np.cumsum(f) / SR
    if wave == "sin":
        return np.sin(TAU * ph)
    if wave == "sq":
        return np.sign(np.sin(TAU * ph))
    if wave == "saw":
        return 2 * (ph % 1.0) - 1
    return 2 * np.abs(2 * (ph % 1.0) - 1) - 1


def _noise(d, seed=0):
    return np.random.default_rng(seed).uniform(-1, 1, int(d * SR)).astype(np.float32)


def _lp(x, k):
    """filtro passa-basso a un polo (vettoriale a blocchi)"""
    y = np.empty_like(x)
    acc = 0.0
    a = float(k)
    for i0 in range(0, len(x), 4096):
        seg = x[i0:i0 + 4096]
        out = np.empty_like(seg)
        for j in range(len(seg)):
            acc += (seg[j] - acc) * a
            out[j] = acc
        y[i0:i0 + 4096] = out
    return y


def _lp_fast(x, passes=3, width=8):
    k = np.ones(width, np.float32) / width
    for _ in range(passes):
        x = np.convolve(x, k, mode="same")
    return x


def _note(freq, d, wave="saw", vol=0.3, a=0.01, r=0.1):
    n = int(d * SR)
    t = np.arange(n, dtype=np.float32) / SR
    ph = t * freq
    if wave == "sin":
        s = np.sin(TAU * ph)
    elif wave == "sq":
        s = np.sign(np.sin(TAU * ph)) * 0.6
    elif wave == "tri":
        s = 2 * np.abs(2 * (ph % 1.0) - 1) - 1
    else:
        s = (2 * (ph % 1.0) - 1) * 0.7
    e = np.ones(n, np.float32)
    na, nr = max(1, int(a * SR)), max(1, int(min(r, d) * SR))
    e[:na] = np.linspace(0, 1, na)
    e[-nr:] *= np.linspace(1, 0, nr)
    return s * e * vol


def _hz(m):
    return 440.0 * 2 ** ((m - 69) / 12.0)


def compose_track(kind):
    rng = np.random.default_rng({"menu": 1, "radio1": 2, "radio2": 3}[kind])
    if kind == "radio1":   # funk "schwifty"
        bpm, prog, style = 112, [(43, "m7"), (43, "m7"), (48, "7"), (46, "M")], "funk"
    elif kind == "radio2":  # synth spaziale
        bpm, prog, style = 124, [(45, "m"), (41, "M"), (48, "M"), (43, "M")], "synth"
    else:
        bpm, prog, style = 92, [(45, "m"), (41, "M"), (48, "M"), (43, "M")], "menu"
    chords = {"m": (0, 3, 7), "M": (0, 4, 7), "m7": (0, 3, 7, 10), "7": (0, 4, 7, 10)}
    beat = 60.0 / bpm
    bars = 8
    total = bars * 4 * beat
    out = np.zeros(int(total * SR) + SR, np.float32)

    def put(sig, t0):
        i = int(t0 * SR)
        out[i:i + len(sig)] += sig[:max(0, len(out) - i)]
    kick = np.sin(TAU * np.cumsum(np.linspace(140, 40, int(0.18 * SR))) / SR) * _env(int(0.18 * SR), 0.001, 1, 2) * 0.8
    snare = _noise(0.16, 5) * _env(int(0.16 * SR), 0.001, 1, 2.5) * 0.35
    hat = np.diff(_noise(0.04, 9), prepend=0) * _env(int(0.04 * SR), 0.001, 1, 3) * 0.12
    for b in range(bars):
        root, q = prog[b % 4]
        tones = chords[q]
        t0 = b * 4 * beat
        for k in range(4):
            put(kick, t0 + k * beat) if (style != "menu" or k % 2 == 0) else None
            if k % 2 == 1:
                put(snare, t0 + k * beat)
        for k in range(8 if style != "funk" else 16):
            put(hat, t0 + k * beat / (2 if style != "funk" else 4))
        if style == "funk":
            pat = [0, None, 12, None, None, 0, None, 10, 0, None, 12, 7, None, 5, None, 3]
            for k, o in enumerate(pat):
                if o is not None:
                    put(_note(_hz(root - 12 + o), beat / 4 * 0.9, "sq", 0.16, r=0.03), t0 + k * beat / 4)
            for k in (1, 3):
                for tt in tones:
                    put(_note(_hz(root + 12 + tt), beat * 0.25, "saw", 0.05, r=0.05), t0 + k * beat + beat * 0.5)
        else:
            for k in range(8):
                put(_note(_hz(root - 12 + (0 if k % 2 == 0 else 12)), beat / 2 * 0.9, "tri", 0.22), t0 + k * beat / 2)
            for tt in tones[:3]:
                put(_note(_hz(root + 12 + tt), 4 * beat, "tri", 0.045, a=0.3, r=0.6), t0)
            for k in range(16):
                put(_note(_hz(root + 24 + tones[k % len(tones)]), beat / 4 * 0.7, "sq", 0.03, r=0.03), t0 + k * beat / 4)
        if b >= 4:
            pos = 0.0
            scale = (0, 3, 5, 7, 10, 12)
            while pos < 4:
                d = rng.choice((0.5, 0.5, 1.0, 0.25))
                if rng.random() < 0.8:
                    m = root + 24 + scale[rng.integers(0, len(scale))]
                    put(_note(_hz(m), d * beat * 0.9, "saw" if style == "synth" else "sq", 0.06, r=0.06), t0 + pos * beat)
                pos += d
    out = out[:int(total * SR)]
    out = _lp_fast(out, 1, 3)
    return out / (np.abs(out).max() + 1e-6) * 0.85


class SoundBank:
    def __init__(self, game, enabled=True):
        self.game = game
        self.enabled = enabled
        self.dir = tempfile.mkdtemp(prefix="rm3d_audio_")
        self.pool = {}
        self.loops = {}
        self.music = None
        self.music_name = None
        self.volume = 1.0
        self._make_all()

    def _write(self, name, data):
        data = np.clip(data, -1, 1)
        path = os.path.join(self.dir, name + ".wav")
        with wave.open(path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SR)
            w.writeframes((data * 32767).astype("<i2").tobytes())
        return path

    def _load(self, name, data, copies=3):
        path = self._write(name, data)
        fn = Filename.fromOsSpecific(path)
        self.pool[name] = [self.game.loader.loadSfx(fn) for _ in range(copies)]

    def _make_all(self):
        L = self._load
        n = lambda d, s=0: _noise(d, s)
        L("laser", _sweep(1700, 260, 0.2, "sq") * _env(int(0.2 * SR), 0.002, 1, 1.4) * 0.35, 4)
        L("plasma", (_sweep(900, 160, 0.13, "saw") * 0.5 + n(0.13, 1) * 0.3) * _env(int(0.13 * SR), 0.001, 1, 1.2) * 0.5, 5)
        L("elaser", _sweep(1100, 300, 0.22, "tri") * _env(int(0.22 * SR), 0.002, 1, 1.2) * 0.35, 4)
        whoosh = _lp_fast(n(0.7, 2), 2, 6) * np.sin(np.linspace(0, math.pi, int(0.7 * SR))) * 1.5
        ch = _sweep(180, 1100, 0.7, "sin") * (0.5 + 0.5 * np.sin(np.arange(int(0.7 * SR)) / SR * TAU * 22)) * 0.4
        L("portal", (whoosh + ch) * _env(int(0.7 * SR), 0.05, 1, 0.8) * 0.6, 3)
        boom = np.sin(TAU * np.cumsum(np.linspace(70, 25, int(1.6 * SR))) / SR) * 0.8
        L("explosion", (_lp_fast(n(1.6, 3), 3, 14) * 2.2 + boom) * _env(int(1.6 * SR), 0.002, 1, 2.2) * 0.9, 3)
        L("punch", (_lp_fast(n(0.12, 4), 2, 10) * 2 + _sweep(160, 60, 0.12)) * _env(int(0.12 * SR), 0.001, 1, 2) * 0.7, 3)
        L("hit", (n(0.07, 5) * 0.5 + _sweep(500, 200, 0.07, "sq") * 0.3) * _env(int(0.07 * SR), 0.001, 1, 2) * 0.5, 4)
        L("crash", (_lp_fast(n(0.6, 6), 1, 3) * 0.8 + _sweep(140, 50, 0.6) * 0.6 +
                    _sweep(2200, 1800, 0.6, "sq") * 0.08) * _env(int(0.6 * SR), 0.001, 1, 2.5), 3)
        t = _t(1.0)
        f0 = 55.0
        eng = (np.sin(TAU * f0 * t) * 0.5 + np.sin(TAU * f0 * 2 * t) * 0.3 + (2 * ((f0 * 3 * t) % 1) - 1) * 0.15)
        eng *= 0.75 + 0.25 * np.sin(TAU * f0 / 2 * t)
        eng += _lp_fast(n(1.0, 7), 2, 6) * 0.25
        L("engine", eng * 0.45, 1)
        sq = _lp_fast(n(1.0, 8), 1, 2) * 0.4 + np.sin(TAU * 1500 * t) * 0.15 * (0.6 + 0.4 * np.sin(TAU * 7 * t))
        L("skid", sq * 0.5, 1)
        t2 = _t(2.0)
        sir = np.sin(TAU * np.cumsum(900 + 450 * np.sin(TAU * 0.5 * t2)) / SR)
        L("siren", sir * 0.35 + np.sign(sir) * 0.05, 1)
        hn = (np.sign(np.sin(TAU * 415 * _t(0.5))) + np.sign(np.sin(TAU * 523 * _t(0.5)))) * 0.25
        L("horn", _lp_fast(hn, 1, 4) * _env(int(0.5 * SR), 0.01, 1, 0.3), 1)
        L("step", _lp_fast(n(0.07, 9), 2, 10) * _env(int(0.07 * SR), 0.001, 1, 2) * 1.2, 4)
        L("jump", _sweep(200, 420, 0.12, "tri") * _env(int(0.12 * SR), 0.002, 1, 1.5) * 0.25, 2)
        arp = np.concatenate([_note(_hz(m), 0.07, "sq", 0.3, r=0.03) for m in (72, 76, 79, 84)] + [_note(_hz(88), 0.25, "sq", 0.3, r=0.2)])
        L("pickup", arp, 2)
        jing = np.concatenate([_note(_hz(m), 0.13, "saw", 0.25, r=0.05) for m in (60, 64, 67, 72, 67, 72)] +
                              [sum(_note(_hz(m), 1.0, "saw", 0.18, r=0.8) for m in (60, 64, 67, 72))])
        L("mission", _lp_fast(jing, 1, 3), 1)
        wst = np.concatenate([_note(_hz(m), 0.35, "saw", 0.3, r=0.2) for m in (64, 61, 58)] + [_note(_hz(46), 1.2, "saw", 0.3, r=1.0)])
        L("wasted", _lp_fast(wst, 2, 5), 1)
        bt = _t(0.65)
        burp = (2 * ((np.cumsum(np.linspace(105, 70, len(bt)) * (1 + 0.25 * np.sin(TAU * 27 * bt))) / SR) % 1) - 1)
        burp = _lp_fast(burp + n(0.65, 10) * 0.3, 3, 12) * _env(len(bt), 0.03, 1, 0.7) * 2.0
        L("burp", burp, 1)
        L("click", _note(880, 0.05, "sq", 0.25, r=0.03), 2)
        L("door", (_lp_fast(n(0.15, 11), 2, 8) * 1.5 + _sweep(120, 70, 0.15)) * _env(int(0.15 * SR), 0.001, 1, 2), 2)
        roar = _lp_fast(_sweep(90, 45, 2.0, "saw") * (1 + 0.3 * np.sin(TAU * 8 * _t(2.0))) + n(2.0, 12) * 0.4, 3, 10)
        L("roar", roar * _env(int(2.0 * SR), 0.1, 1, 0.8) * 1.4, 1)
        amb = _lp_fast(n(4.0, 13), 3, 24) * 3.0 + np.sin(TAU * 50 * _t(4.0)) * 0.03
        fade = np.ones(len(amb), np.float32)
        m = int(0.3 * SR)
        fade[:m] = np.linspace(0, 1, m)
        fade[-m:] = np.linspace(1, 0, m)
        L("ambient", amb * fade * 0.5, 1)
        for name in ("menu", "radio1", "radio2"):
            try:
                L(name, compose_track(name), 1)
            except Exception:
                pass

    def _snd(self, name):
        lst = self.pool.get(name)
        if not lst:
            return None
        for s in lst:
            if s.status() != AudioSound.PLAYING:
                return s
        return lst[0]

    def play(self, name, vol=1.0, rate=1.0, pos=None):
        if not self.enabled:
            return
        if pos is not None:
            lp = self.game.listener_pos()
            d = math.sqrt((pos[0] - lp[0]) ** 2 + (pos[1] - lp[1]) ** 2 + (pos[2] - lp[2]) ** 2)
            vol *= clamp(1.0 - d / 90.0, 0.0, 1.0) ** 2
            if vol < 0.02:
                return
        s = self._snd(name)
        if s is None:
            return
        s.setVolume(vol * self.volume)
        s.setPlayRate(rate)
        s.play()

    def loop(self, name, vol=1.0, rate=1.0):
        """avvia o aggiorna un suono continuo (motore, sirena, sgommata)"""
        s = self.loops.get(name)
        if s is None:
            lst = self.pool.get(name)
            if not lst:
                return
            s = lst[0]
            s.setLoop(True)
            self.loops[name] = s
        if not self.enabled or vol <= 0.01:
            if s.status() == AudioSound.PLAYING:
                s.stop()
            return
        s.setVolume(vol * self.volume)
        s.setPlayRate(rate)
        if s.status() != AudioSound.PLAYING:
            s.play()

    def stop_loops(self):
        for s in self.loops.values():
            s.stop()

    def set_music(self, name, vol=0.5):
        if name == self.music_name:
            if self.music is not None:
                self.music.setVolume(vol * self.volume if self.enabled else 0)
            return
        if self.music is not None:
            self.music.stop()
        self.music = None
        self.music_name = name
        if name and name in self.pool:
            self.music = self.pool[name][0]
            self.music.setLoop(True)
            self.music.setVolume(vol * self.volume if self.enabled else 0)
            if self.enabled:
                self.music.play()

    def set_enabled(self, on):
        self.enabled = on
        if not on:
            self.stop_loops()
            if self.music is not None:
                self.music.stop()
        elif self.music is not None:
            self.music.play()


# =============================================================================
#  VEICOLI: fisica arcade, danni, esplosioni
# =============================================================================
class Vehicle:
    def __init__(self, game, kind, x, y, h, color=None):
        self.game = game
        self.kind = kind
        self.spec = CAR_TYPES[kind]
        if color is None:
            color = random.choice(self.spec["colors"])
        m = game.factory.make(kind, game.dyn_root, color)
        self.np = m["root"]
        self.body = m["body"]
        self.nodes = m["nodes"]
        self.sirens = m["sirens"]
        self.wheels = m["wheels"]
        self.L, self.W, self.H, self.wr = m["dims"]
        self.x, self.y = x, y
        self.z = StaticWorld.terrain(x, y)
        self.h = h
        self.vx = self.vy = 0.0
        self.vz = 0.0
        self.steer = 0.0
        self.hp = 100.0
        self.driver = None          # "player", "ai", "cop" o None
        self.ai = None
        self.fly = bool(self.spec.get("fly"))
        self.alt = 0.0
        self.wrecked = False
        self.fire_t = 0.0
        self.dead = False
        self.persistent = False
        self.siren_on = False
        self.last_hit = 0.0
        self.skid = 0.0
        self.accel = 0.0
        self.lat = 0.0
        self.horn_t = 0.0
        self.wheel_spin = 0.0
        self.mass = self.spec["mass"]
        self.passenger = None
        self.np.setPos(x, y, self.z)
        self.np.setH(h)

    # ------------------------------------------------------------------ geometria
    @property
    def fwd(self):
        return heading_vec(self.h)

    @property
    def speed(self):
        fx, fy = self.fwd
        return self.vx * fx + self.vy * fy

    def circles(self):
        fx, fy = self.fwd
        r = self.W / 2 * 0.98
        o = self.L / 2 - r
        return [(self.x + fx * o, self.y + fy * o, r), (self.x, self.y, r), (self.x - fx * o, self.y - fy * o, r)]

    def local(self, px, py):
        """coordinate (laterale, avanti) di un punto nel sistema dell'auto"""
        fx, fy = self.fwd
        dx, dy = px - self.x, py - self.y
        return dx * fy - dy * fx, dx * fx + dy * fy

    def contains(self, px, py, margin=0.0):
        lx, ly = self.local(px, py)
        return abs(lx) < self.W / 2 + margin and abs(ly) < self.L / 2 + margin

    def ray_hit(self, o, d, maxd):
        """intersezione raggio-auto (scatola orientata). ritorna t o None"""
        fx, fy = self.fwd
        rx, ry = fy, -fx
        ox, oy, oz = o[0] - self.x, o[1] - self.y, o[2] - self.z
        lo = (ox * rx + oy * ry, ox * fx + oy * fy, oz)
        ld = (d[0] * rx + d[1] * ry, d[0] * fx + d[1] * fy, d[2])
        lo_b = (-self.W / 2, -self.L / 2, 0.15 + self.alt)
        hi_b = (self.W / 2, self.L / 2, self.H + self.alt)
        tmin, tmax = 0.0, maxd
        for k in range(3):
            if abs(ld[k]) < 1e-9:
                if lo[k] < lo_b[k] or lo[k] > hi_b[k]:
                    return None
                continue
            a = (lo_b[k] - lo[k]) / ld[k]
            b = (hi_b[k] - lo[k]) / ld[k]
            if a > b:
                a, b = b, a
            tmin = max(tmin, a)
            tmax = min(tmax, b)
            if tmin > tmax:
                return None
        return tmin

    def seat_pos(self, side=-1):
        fx, fy = self.fwd
        rx, ry = fy, -fx
        return (self.x + rx * side * (self.W / 2 + 0.9) + fx * 0.4, self.y + ry * side * (self.W / 2 + 0.9) + fy * 0.4)

    # ------------------------------------------------------------------ fisica
    def drive(self, dt, throttle, brake, steer_in, handbrake=False, lift=0.0):
        sp = self.spec
        fx, fy = self.fwd
        rx, ry = fy, -fx
        vf = self.vx * fx + self.vy * fy
        vr = self.vx * rx + self.vy * ry
        top, acc = sp["top"], sp["acc"]
        if self.hp < 30:
            top *= 0.6
        old_vf = vf
        if throttle > 0:
            if vf >= -0.5:
                vf += acc * throttle * max(0.0, 1 - (vf / top) ** 2) * dt
            else:
                vf = min(0.0, vf + 16 * dt)
        if brake > 0:
            if vf > 0.5:
                vf = max(0.0, vf - 16 * brake * dt)
            else:
                vf = max(-11.0, vf - acc * 0.55 * brake * dt)
        drag = 0.35 + 0.0055 * vf * vf
        if throttle == 0 and brake == 0:
            drag += 1.6
        vf -= math.copysign(min(abs(vf), drag * dt), vf)
        if handbrake:
            vf = approach(vf, 0.0, 7.0 * dt)
        max_st = math.radians(34) / (1 + abs(vf) / 22)
        self.steer = approach(self.steer, steer_in * max_st, 3.2 * dt)
        wb = self.L * 0.62
        yaw = vf / wb * math.tan(self.steer)
        grip = sp["grip"]
        if handbrake and abs(vf) > 4:
            yaw *= 1.45
            grip = 1.4
        if self.fly and self.alt > 1.0:
            grip = 3.0
        self.h += math.degrees(yaw) * dt
        vr *= math.exp(-grip * dt)
        self.skid = clamp(abs(vr) / 6.0, 0, 1) if not (self.fly and self.alt > 0.5) else 0.0
        fx, fy = self.fwd
        rx, ry = fy, -fx
        self.vx = fx * vf + rx * vr
        self.vy = fy * vf + ry * vr
        self.accel = lerp(self.accel, (vf - old_vf) / max(dt, 1e-4), 0.15)
        self.lat = lerp(self.lat, yaw * vf, 0.15)
        if self.fly:
            if lift:
                self.vz = approach(self.vz, lift * 9.0, 14 * dt)
            else:
                self.vz = approach(self.vz, 0.0, 8 * dt)

    def coast(self, dt):
        self.drive(dt, 0.0, 0.0, 0.0, handbrake=self.wrecked or self.driver is None)

    def integrate(self, dt):
        g = self.game
        w = g.city.world
        self.x += self.vx * dt
        self.y += self.vy * dt
        ground = StaticWorld.terrain(self.x, self.y)
        if self.fly:
            if self.driver is None and self.alt > 0.3:
                self.vz -= 6 * dt
            self.alt = clamp(self.alt + self.vz * dt, 0.0, 160.0)
            if self.alt <= 0.0:
                self.vz = max(0.0, self.vz)
            supp = w.support(self.x, self.y, ground + self.alt + 0.3, 1.2)
            if supp > ground and ground + self.alt < supp:
                self.alt = supp - ground
                self.vz = max(0.0, self.vz)
            self.z = ground + self.alt
        else:
            self.z = lerp(self.z, ground, clamp(dt * 12, 0, 1))
        # collisioni con edifici, alberi, pali
        hit_imp = 0.0
        hit_pt = None
        for (cx, cy, r) in self.circles():
            nx_, ny_, hit, n = w.push_circle(cx, cy, self.z, r, self.H, step=0.35)
            if hit:
                dx, dy = nx_ - cx, ny_ - cy
                self.x += dx
                self.y += dy
                nl = math.hypot(n[0], n[1]) or 1
                nx, ny = n[0] / nl, n[1] / nl
                vn = self.vx * nx + self.vy * ny
                if vn < 0:
                    self.vx -= nx * vn * 1.35
                    self.vy -= ny * vn * 1.35
                    hit_imp = max(hit_imp, -vn)
                    hit_pt = (cx - nx * r, cy - ny * r, self.z + 0.6)
        if hit_imp > 4.0:
            self.impact(hit_imp, hit_pt)
        self.np.setPos(self.x, self.y, self.z)
        self.np.setH(self.h)
        vf = self.speed
        self.body.setP(clamp(-self.accel * 0.25, -3.5, 3.5))
        self.body.setR(clamp(self.lat * 0.12, -4, 4))
        if self.fly:
            self.body.setZ(0.25 + 0.06 * math.sin(g.clock_t * 3.0 + self.x))
        self.wheel_spin -= math.degrees(vf / max(self.wr, 0.1)) * dt
        for (steer, spin, front) in self.wheels:
            spin.setP(self.wheel_spin)
            if front:
                steer.setH(math.degrees(self.steer))

    def impact(self, imp, pt, other=None):
        g = self.game
        if g.clock_t - self.last_hit < 0.25:
            return
        self.last_hit = g.clock_t
        dmg = (imp - 4.0) * 1.5
        self.damage(dmg, None)
        if pt:
            g.fx.sparks(pt, int(min(20, imp * 2)), (1.0, 0.85, 0.5, 1.0), 4 + imp * 0.3)
            g.sounds.play("crash", clamp(imp / 18, 0.2, 1.0), 0.9 + random.random() * 0.2, pos=pt)
        if self.driver == "player":
            g.cam_shake(min(0.6, imp * 0.03))
            g.player.hp -= max(0.0, imp - 14) * 1.2
        elif self.driver in ("ai",) and imp > 4:
            self.disturb()

    def disturb(self):
        """un'auto del traffico urtata smette di seguire la corsia"""
        if self.driver == "ai":
            self.driver = "stopped"
            self.ai = None
            self.horn_t = 1.2

    def damage(self, d, attacker=None):
        if self.dead:
            return
        self.hp -= d
        if self.hp <= 0 and not self.wrecked:
            self.wrecked = True
            self.fire_t = 4.0 if self.driver != "player" else 6.0
            if self.driver in ("ai", "stopped"):
                self.game.peds.eject_driver(self, flee=True)
                self.driver = None
            if attacker == "player":
                self.game.police.crime("auto", (self.x, self.y))
        if self.driver in ("ai",) and attacker == "player":
            self.disturb()

    def explode(self):
        g = self.game
        self.dead = True
        p = (self.x, self.y, self.z + 0.8)
        g.fx.explosion(p, 1.3)
        g.sounds.play("explosion", 1.0, pos=p)
        g.cam_shake(0.9 if dist2(self.x, self.y, *g.player.pos2()) < 30 else 0.3)
        g.blast(p, 8.0, 120, source=self)
        self.body.setColorScale(0.12, 0.11, 0.1, 1)
        for (steer, spin, front) in self.wheels:
            steer.setZ(steer.getZ() - 0.2)
        self.vz = 0
        if self.kind == "polizia":
            g.police.crime("auto_polizia", (self.x, self.y))
            g.missions.on_cop_car_destroyed()

    def update(self, dt):
        g = self.game
        if self.wrecked and not self.dead:
            self.fire_t -= dt
            if random.random() < 0.6:
                fx, fy = self.fwd
                g.fx.fire((self.x + fx * self.L * 0.35, self.y + fy * self.L * 0.35, self.z + 1.0), 1.2)
            if self.fire_t <= 0:
                self.explode()
        elif self.hp < 45 and not self.dead and random.random() < 0.25:
            fx, fy = self.fwd
            g.fx.smoke_puff((self.x + fx * self.L * 0.38, self.y + fy * self.L * 0.38, self.z + 1.0), 0.3 if self.hp > 25 else 0.8)
        if self.sirens:
            on = self.siren_on and int(g.clock_t * 6) % 2 == 0
            on2 = self.siren_on and int(g.clock_t * 6) % 2 == 1
            self.sirens[0].setColorScale((1.0, 0.15, 0.15, 1) if on else (0.25, 0.05, 0.05, 1))
            if len(self.sirens) > 1:
                self.sirens[1].setColorScale((0.15, 0.35, 1.0, 1) if on2 else (0.05, 0.08, 0.25, 1))
        if self.horn_t > 0:
            self.horn_t -= dt
            if self.horn_t <= 0 and random.random() < 0.5:
                g.sounds.play("horn", 0.6, pos=(self.x, self.y, self.z))

    def remove(self):
        self.np.removeNode()
        self.dead = True


# =============================================================================
#  TRAFFICO (auto che seguono le corsie)
# =============================================================================
NEIGH = ((1, 0), (-1, 0), (0, 1), (0, -1))


class TrafficAI:
    """auto che seguono le corsie del grafo stradale, svoltano agli incroci e rispettano i semafori"""

    def __init__(self, car, net, c, d, lane, s):
        self.car = car
        self.net = net
        self.c, self.d, self.lane, self.s = c, d, lane, s
        self.mode = "lane"
        self.speed = 0.0
        self.cruise_k = random.uniform(0.85, 1.12)
        self.bez = None
        self.bt = 0.0
        self.blen = 1.0
        self.next = None
        self.nlane = 0
        self.blocked_t = 0.0
        self.stuck = 0.0

    def ends(self, c, d):
        ch = self.net.chains[c]
        t0 = ch.trim[0] if d > 0 else ch.trim[1]
        t1 = ch.trim[1] if d > 0 else ch.trim[0]
        a = t0 + 0.5 if t0 > 0 else 0.0
        b = ch.pl.L - (t1 + 0.5 if t1 > 0 else 0.0)
        return a, max(a, b)

    def choose_next(self):
        net = self.net
        ch = net.chains[self.c]
        node = ch.n1 if self.d > 0 else ch.n0
        opts = net.options(node, came=(self.c, self.d))
        if not opts:
            if not ch.ow:
                return (self.c, -self.d)
            return None
        _x, _y, tx, ty = ch.point(self.d, 0, ch.pl.L - 0.5)
        w = []
        for (c, d) in opts:
            o = net.chains[c]
            _x2, _y2, ux, uy = o.point(d, 0, 0.5)
            straight = tx * ux + ty * uy
            k = {"motorway": 3.0, "trunk": 2.5, "primary": 2.0, "secondary": 1.8, "tertiary": 1.3}.get(o.k, 1.0)
            w.append(k * (1.6 if straight > 0.8 else 1.0))
        return random.choices(opts, w)[0]

    def start_turn(self):
        net = self.net
        ch = net.chains[self.c]
        nc, nd = self.next
        nch = net.chains[nc]
        self.nlane = min(self.lane, max(0, nch.lanes(nd) - 1))
        _a, s_end = self.ends(self.c, self.d)
        x0, y0, tx0, ty0 = ch.point(self.d, self.lane, s_end)
        s2, _b = self.ends(nc, nd)
        x2, y2, tx2, ty2 = nch.point(nd, self.nlane, s2)
        dd = math.hypot(x2 - x0, y2 - y0)
        den = tx0 * ty2 - ty0 * tx2
        cx, cy = (x0 + x2) / 2, (y0 + y2) / 2
        if tx0 * tx2 + ty0 * ty2 < -0.6:
            cx, cy = cx + tx0 * max(5.0, dd * 0.6), cy + ty0 * max(5.0, dd * 0.6)
        elif abs(den) > 0.2:
            t = ((x2 - x0) * ty2 - (y2 - y0) * tx2) / den
            if 0 < t < dd * 1.5 + 4:
                cx, cy = x0 + tx0 * t, y0 + ty0 * t
        self.bez = ((x0, y0), (cx, cy), (x2, y2))
        self.blen = max(0.1, dist2(x0, y0, cx, cy) + dist2(cx, cy, x2, y2))
        self.s_next = s2
        self.bt = 0.0
        self.mode = "turn"

    def update(self, dt, game):
        car = self.car
        net = self.net
        ch = net.chains[self.c]
        fx, fy = car.fwd
        want = (ch.speed * self.cruise_k) if self.mode == "lane" else 6.5
        ahead = 99.0
        px, py = game.player.pos2()
        cands = [(px, py, 1.2)]
        for v in game.traffic.near(car.x, car.y, 24):
            if v is not car:
                cands.append((v.x, v.y, 1.9))
        for p in game.peds.near(car.x, car.y, 18):
            if not p.dead:
                cands.append((p.x, p.y, 1.0))
        for (ox, oy, w) in cands:
            dx, dy = ox - car.x, oy - car.y
            f = dx * fx + dy * fy
            if 0 < f < 24:
                l = abs(dx * fy - dy * fx)
                if l < w + 0.6:
                    ahead = min(ahead, f - car.L / 2)
        if ahead < 20:
            want = min(want, max(0.0, (ahead - 4.0) * 1.1))
        if ahead < 6 and dist2(px, py, car.x, car.y) < 10:
            self.blocked_t += dt
            if self.blocked_t > 2.5:
                self.blocked_t = -3.0
                game.sounds.play("horn", 0.7, pos=(car.x, car.y, car.z))
        else:
            self.blocked_t = max(0.0, self.blocked_t - dt)
        # semaforo all'incrocio di arrivo
        if self.mode == "lane":
            _a, s_end = self.ends(self.c, self.d)
            ei = 1 if self.d > 0 else 0
            togo = s_end - self.s
            if ch.signal[ei] and togo < 45 and hasattr(game.city, "signal_state"):
                st = game.city.signal_state(ch.group[ei], game.clock_t)
                stop = togo - 1.5
                if st == "r" or (st == "y" and stop > 6):
                    want = min(want, max(0.0, stop * 0.8))
        self.speed = approach(self.speed, want, (9.0 if want < self.speed else 3.5) * dt)
        x, y, h = car.x, car.y, car.h
        if self.mode == "lane":
            self.s += self.speed * dt
            _a, s_end = self.ends(self.c, self.d)
            if self.s >= s_end:
                self.next = self.choose_next()
                if self.next is None:
                    self.s = s_end
                    self.speed = 0.0
                    self.stuck += dt
                    x, y, tx, ty = ch.point(self.d, self.lane, self.s)
                    h = vec_heading(tx, ty)
                else:
                    self.start_turn()
            else:
                x, y, tx, ty = ch.point(self.d, self.lane, self.s)
                h = vec_heading(tx, ty)
        if self.mode == "turn":
            self.bt += self.speed * dt / self.blen
            if self.bt >= 1.0:
                over = (self.bt - 1.0) * self.blen
                self.c, self.d = self.next
                self.lane = self.nlane
                self.s = self.s_next + over
                self.mode = "lane"
                ch = net.chains[self.c]
                x, y, tx, ty = ch.point(self.d, self.lane, self.s)
                h = vec_heading(tx, ty)
            else:
                (x0, y0), (x1, y1), (x2, y2) = self.bez
                t = self.bt
                u = 1 - t
                x = u * u * x0 + 2 * u * t * x1 + t * t * x2
                y = u * u * y0 + 2 * u * t * y1 + t * t * y2
                tx = 2 * u * (x1 - x0) + 2 * t * (x2 - x1)
                ty = 2 * u * (y1 - y0) + 2 * t * (y2 - y1)
                if abs(tx) + abs(ty) > 1e-6:
                    h = vec_heading(tx, ty)
        car.steer = math.radians(clamp(wrap_angle(h - car.h) * 4, -30, 30))
        nfx, nfy = heading_vec(h)
        car.vx, car.vy = nfx * self.speed, nfy * self.speed
        car.x, car.y, car.h = x, y, h
        car.z = StaticWorld.terrain(x, y)
        car.np.setPos(car.x, car.y, car.z)
        car.np.setH(car.h)
        car.wheel_spin -= math.degrees(self.speed / max(car.wr, 0.1)) * dt
        for (steer, spin, front) in car.wheels:
            spin.setP(car.wheel_spin)
            if front:
                steer.setH(math.degrees(car.steer))
        car.body.setP(0)
        car.body.setR(0)


class TrafficManager:
    def __init__(self, game, count=16):
        self.game = game
        self.count = count
        self.cars = []
        self.parked_done = set()
        self.grid = {}
        self.t = 0.0

    def near(self, x, y, r):
        out = []
        cs = 24.0
        for ix in range(int((x - r) // cs), int((x + r) // cs) + 1):
            for iy in range(int((y - r) // cs), int((y + r) // cs) + 1):
                for v in self.grid.get((ix, iy), ()):
                    if abs(v.x - x) < r and abs(v.y - y) < r:
                        out.append(v)
        return out

    def _rebuild_grid(self):
        g = {}
        for v in self.cars:
            g.setdefault((int(v.x // 24), int(v.y // 24)), []).append(v)
        self.grid = g

    def add(self, v):
        self.cars.append(v)
        return v

    def spawn_moving(self, px, py, dmin=70, dmax=200):
        net = self.game.city.net
        S = net.samples
        if len(S) == 0:
            return None
        d2 = (S[:, 0] - px) ** 2 + (S[:, 1] - py) ** 2
        idx = np.nonzero((d2 > dmin * dmin) & (d2 < dmax * dmax))[0]
        if len(idx) == 0:
            return None
        for _ in range(8):
            x0, y0, c, s0 = S[int(random.choice(idx))]
            c = int(c)
            ch = net.chains[c]
            d = 1 if ch.ow else random.choice((1, -1))
            nl = ch.lanes(d)
            if nl <= 0:
                continue
            lane = random.randrange(nl)
            s = s0 if d > 0 else ch.pl.L - s0
            ai = TrafficAI(None, net, c, d, lane, s)
            a0, a1 = ai.ends(c, d)
            if not (a0 + 1 < s < a1 - 3):
                continue
            x, y, tx, ty = ch.point(d, lane, s)
            if any(dist2(v.x, v.y, x, y) < 12 for v in self.cars):
                continue
            kind = random.choices(["berlina", "utilitaria", "furgone", "sportiva"], (5, 4, 2, 1))[0]
            v = Vehicle(self.game, kind, x, y, vec_heading(tx, ty))
            v.driver = "ai"
            ai.car = v
            v.ai = ai
            ai.speed = ch.speed * 0.6
            v.rig = self.game.peds.make_driver(v)
            return self.add(v)
        return None

    def _parking_grid(self):
        g = {}
        for k, (x, y, h) in enumerate(self.game.city.parking):
            g.setdefault((int(x // 60), int(y // 60)), []).append(k)
        self.pgrid = g

    def spawn_parked(self, px, py, cap=34):
        if getattr(self, "pgrid", None) is None:
            self._parking_grid()
        parked = sum(1 for v in self.cars if hasattr(v, "parked_id"))
        if parked >= cap:
            return
        P = self.game.city.parking
        ix, iy = int(px // 60), int(py // 60)
        cands = []
        for a in range(ix - 3, ix + 4):
            for b in range(iy - 3, iy + 4):
                for k in self.pgrid.get((a, b), ()):
                    if k in self.parked_done:
                        continue
                    x, y, h = P[k]
                    d = dist2(x, y, px, py)
                    if d < 140:
                        cands.append((d, k))
        cands.sort()
        for d, k in cands[:max(0, cap - parked)]:
            x, y, h = P[k]
            self.parked_done.add(k)
            kind = random.choices(["berlina", "utilitaria", "furgone", "sportiva"], (5, 4, 2, 1))[0]
            v = Vehicle(self.game, kind, x, y, h)
            v.parked_id = k
            self.add(v)

    def update(self, dt):
        g = self.game
        px, py = g.player.pos2()
        self.t += dt
        self._rebuild_grid()
        for v in self.cars:
            if v.dead and not v.wrecked:
                continue
            if v.driver == "ai" and v.ai is not None:
                v.ai.update(dt, g)
            elif v.driver == "player":
                pass
            elif v.driver == "cop":
                pass
            else:
                if not v.dead and (abs(v.vx) + abs(v.vy) > 0.05 or v.fly and v.alt > 0.05):
                    v.coast(dt)
                    v.integrate(dt)
            v.update(dt)
        # collisioni tra auto (cerchi)
        self._collide()
        if self.t > 0.5:
            self.t = 0.0
            keep = []
            for v in self.cars:
                d = dist2(v.x, v.y, px, py)
                far = 240 if v.driver != "cop" else 400
                stuck = v.ai is not None and v.ai.stuck > 4.0 and d > 40
                if (d > far and not v.persistent and v.driver != "player") or (v.dead and d > 120) or stuck:
                    if hasattr(v, "parked_id"):
                        self.parked_done.discard(v.parked_id)
                    if getattr(v, "rig", None) is not None:
                        g.peds.release_driver(v.rig)
                        v.rig = None
                    v.remove()
                else:
                    keep.append(v)
            self.cars = keep
            moving = sum(1 for v in self.cars if v.driver == "ai")
            if moving < self.count:
                self.spawn_moving(px, py, 60 if moving < self.count // 2 else 90, 210)
            self.spawn_parked(px, py)

    def _collide(self):
        cars = [v for v in self.cars if not (v.dead and v.speed == 0)]
        g = self.game
        for i, a in enumerate(cars):
            for b in self.near(a.x, a.y, 7):
                if b is a or id(b) < id(a) or b not in cars:
                    continue
                if a.fly and a.alt > 1.5 or b.fly and b.alt > 1.5:
                    continue
                best = None
                for (ax, ay, ar) in a.circles():
                    for (bx, by, br) in b.circles():
                        dx, dy = bx - ax, by - ay
                        d = math.hypot(dx, dy)
                        if d < ar + br and (best is None or d < best[0]):
                            best = (d, dx, dy, ar + br, (ax + bx) / 2, (ay + by) / 2)
                if best is None:
                    continue
                d, dx, dy, rr, cx, cy = best
                if d < 1e-4:
                    dx, dy, d = 1.0, 0.0, 1.0
                nx, ny = dx / d, dy / d
                pen = rr - d
                ma, mb = a.mass, b.mass
                # le auto del traffico in corsia sono "pesanti" finche' non vengono urtate forte
                fa = 0.0 if a.driver == "ai" else mb / (ma + mb)
                fb = 0.0 if b.driver == "ai" else ma / (ma + mb)
                if fa == 0 and fb == 0:
                    fa = fb = 0.5
                a.x -= nx * pen * fa / max(fa + fb, 1e-6)
                a.y -= ny * pen * fa / max(fa + fb, 1e-6)
                b.x += nx * pen * fb / max(fa + fb, 1e-6)
                b.y += ny * pen * fb / max(fa + fb, 1e-6)
                rv = (b.vx - a.vx) * nx + (b.vy - a.vy) * ny
                if rv < 0:
                    imp = -rv
                    j = imp * 1.3 / (1 / ma + 1 / mb)
                    for car, sgn, m in ((a, -1, ma), (b, 1, mb)):
                        if car.driver == "ai":
                            if imp > 3:
                                car.disturb()
                            else:
                                continue
                        car.vx += sgn * nx * j / m
                        car.vy += sgn * ny * j / m
                    if imp > 2.5:
                        a.impact(imp, (cx, cy, a.z + 0.7))
                        b.impact(imp, (cx, cy, b.z + 0.7))
                        if g.player.vehicle in (a, b):
                            other = b if g.player.vehicle is a else a
                            if other.kind == "polizia":
                                g.police.crime("urto_polizia", (cx, cy))


# =============================================================================
#  PEDONI, AGENTI E MOSTRI
# =============================================================================
PED_LINES = ["Ehi! Attento!", "Ma che fa?!", "Aiuto!", "Chiamate la Federazione!", "Che schifo di giornata...",
             "Quello e' Rick Sanchez!", "Scappate!"]


class Ped:
    def __init__(self, game, look, role="ped", seed=0):
        self.game = game
        self.role = role
        self.rig = Rig(game.dyn_root, look, seed)
        self.x = self.y = self.z = 0.0
        self.h = 0.0
        self.vx = self.vy = self.vz = 0.0
        self.speed = 0.0
        self.hp = {"ped": 30, "cop": 60, "monster": 45}.get(role, 30)
        self.dead = False
        self.dead_t = 0.0
        self.state = "walk"
        self.ring = None
        self.ring_p = 0.0
        self.dir = 1
        self.offset = random.uniform(-0.8, 0.8)
        self.walk_speed = random.uniform(1.15, 1.6)
        self.panic_t = 0.0
        self.threat = (0.0, 0.0)
        self.idle_t = 0.0
        self.shoot_t = random.uniform(0.8, 1.6)
        self.air_t = 0.0
        self.attack_t = 0.0
        self.car = None
        if role == "cop":
            self.rig.set_weapon(2, game.weapon_np)

    def reset(self, role):
        self.role = role
        self.hp = {"ped": 30, "cop": 60, "monster": 45}.get(role, 30)
        self.dead = False
        self.dead_t = 0.0
        self.state = "walk"
        self.vx = self.vy = self.vz = 0.0
        self.air_t = 0.0
        self.panic_t = 0.0
        self.idle_t = 0.0
        self.ring = None
        self.car = None
        self.shoot_t = random.uniform(0.8, 1.6)
        self.rig.dead_t = 0.0
        self.rig.body.setP(0)
        self.rig.body.setZ(0)
        for sh in self.rig.shoulders:
            sh.setR(0)
        self.rig.root.setHpr(0, 0, 0)
        self.rig.root.show()

    def place(self, x, y, h=0.0):
        self.x, self.y = x, y
        self.z = StaticWorld.terrain(x, y)
        self.h = h
        self.rig.root.setPos(x, y, self.z)
        self.rig.root.setH(h)

    # --- marciapiede ad anello ----------------------------------------------------
    def ring_point(self, p):
        x, y = self.ring.point(p, self.offset)
        return x, y, 0

    def ring_project(self):
        return self.ring.project(self.x, self.y)

    def hurt(self, dmg, src=None, by_player=True, force=None):
        if self.dead:
            return
        g = self.game
        self.hp -= dmg
        g.fx.blood((self.x, self.y, self.z + 1.3), self.role == "monster")
        if force is not None:
            self.vx, self.vy, self.vz = force
            self.air_t = 1.2
        if self.hp <= 0:
            self.die(by_player)
        else:
            if self.role == "ped":
                self.panic(src or (self.x, self.y))
            if by_player and self.role == "cop":
                g.police.crime("spara_polizia", (self.x, self.y))

    def die(self, by_player=True):
        g = self.game
        self.dead = True
        self.dead_t = 0.0
        self.state = "dead"
        if self.role == "monster":
            g.missions.on_monster_killed(self)
        if by_player:
            if self.role == "cop":
                g.police.crime("uccide_polizia", (self.x, self.y))
            elif self.role == "ped":
                g.police.crime("uccide", (self.x, self.y))
            if random.random() < 0.6:
                g.pickups.drop_money(self.x, self.y, random.randint(5, 40))
        for p in g.peds.near(self.x, self.y, 30):
            if p.role == "ped" and not p.dead:
                p.panic((self.x, self.y))

    def panic(self, src):
        if self.role != "ped" or self.dead:
            return
        if self.state != "flee" and random.random() < 0.25:
            self.game.say_world(self, random.choice(PED_LINES))
        self.state = "flee"
        self.panic_t = random.uniform(5, 9)
        self.threat = src

    def update(self, dt):
        g = self.game
        w = g.city.world
        rig = self.rig
        if self.dead:
            self.dead_t += dt
            if self.air_t > 0:
                self._ballistic(dt)
            rig.animate(dt, 0, "dead")
            return
        if self.air_t > 0:
            self._ballistic(dt)
            rig.animate(dt, 0, "fall")
            return
        px, py = g.player.pos2()
        moving = 0.0
        if self.role == "ped":
            if self.state == "flee":
                self.panic_t -= dt
                dx, dy = self.x - self.threat[0], self.y - self.threat[1]
                d = math.hypot(dx, dy) or 1
                tx, ty = dx / d, dy / d
                sp = 5.2
                self._move(dt, tx * sp, ty * sp)
                moving = sp
                if self.panic_t <= 0:
                    self.state = "return"
            elif self.state == "return":
                if self.ring is None:
                    self.state = "walk"
                else:
                    p = self.ring_project()
                    rx, ry, _ = self.ring_point(p)
                    dx, dy = rx - self.x, ry - self.y
                    d = math.hypot(dx, dy)
                    if d < 0.5:
                        self.ring_p = p
                        self.state = "walk"
                    else:
                        sp = self.walk_speed * 1.3
                        self._move(dt, dx / d * sp, dy / d * sp)
                        moving = sp
            elif self.state == "idle":
                self.idle_t -= dt
                if self.idle_t <= 0:
                    self.state = "walk"
            else:
                if self.ring is not None:
                    blocked = dist2(px, py, self.x, self.y) < 1.2
                    if not blocked:
                        self.ring_p += self.dir * self.walk_speed * dt
                        ring = self.ring
                        if not ring.closed and (self.ring_p < 0 or self.ring_p > ring.length):
                            end = 1 if self.ring_p > ring.length else 0
                            nxt = g.city.ped_link(ring, end)
                            if nxt is None:
                                self.dir = -self.dir
                                self.ring_p = clamp(self.ring_p, 0.0, ring.length)
                            else:
                                self.ring, self.ring_p, self.dir = nxt
                                self.state = "return"
                                rig.animate(dt, self.walk_speed, "move")
                                return
                        x, y, _ = self.ring_point(self.ring_p)
                        dx, dy = x - self.x, y - self.y
                        if abs(dx) + abs(dy) > 1e-4:
                            self.h = angle_lerp(self.h, vec_heading(dx, dy), clamp(dt * 8, 0, 1))
                        self.x, self.y = x, y
                        moving = self.walk_speed
                    if random.random() < dt * 0.03:
                        self.state = "idle"
                        self.idle_t = random.uniform(2, 5)
        elif self.role == "cop":
            moving = self._cop_ai(dt, px, py)
        elif self.role == "monster":
            moving = self._monster_ai(dt, px, py)
        elif self.role == "driver":
            return
        self.z = lerp(self.z, w.support(self.x, self.y, self.z + 0.3), clamp(dt * 10, 0, 1))
        rig.root.setPos(self.x, self.y, self.z)
        rig.root.setH(self.h)
        aim = self.role == "cop" and self.state == "shoot"
        rig.animate(dt, moving, "move", aim=aim)

    def _move(self, dt, vx, vy):
        w = self.game.city.world
        nx, ny = self.x + vx * dt, self.y + vy * dt
        nx, ny, hit, n = w.push_circle(nx, ny, self.z, 0.3, 1.7)
        for v in self.game.traffic.near(nx, ny, 5):
            if v.contains(nx, ny, 0.3) and not (v.fly and v.alt > 1.5):
                lx, ly = v.local(nx, ny)
                fx, fy = v.fwd
                rx, ry = fy, -fx
                if abs(lx) / (v.W / 2) > abs(ly) / (v.L / 2):
                    s = (v.W / 2 + 0.31) * (1 if lx >= 0 else -1)
                    nx, ny = v.x + rx * s + fx * ly, v.y + ry * s + fy * ly
                else:
                    s = (v.L / 2 + 0.31) * (1 if ly >= 0 else -1)
                    nx, ny = v.x + rx * lx + fx * s, v.y + ry * lx + fy * s
        self.x, self.y = nx, ny
        if abs(vx) + abs(vy) > 0.05:
            self.h = angle_lerp(self.h, vec_heading(vx, vy), clamp(dt * 10, 0, 1))

    def _ballistic(self, dt):
        self.air_t -= dt
        self.vz -= 18 * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.z += self.vz * dt
        g = StaticWorld.terrain(self.x, self.y)
        if self.z <= g:
            self.z = g
            self.vz = 0
            self.vx *= 0.5
            self.vy *= 0.5
            if self.air_t < 0.6:
                self.air_t = 0
        self.rig.root.setPos(self.x, self.y, self.z)
        self.rig.root.setH(self.rig.root.getH() + 300 * dt)

    def _cop_ai(self, dt, px, py):
        g = self.game
        pl = g.player
        d = dist2(self.x, self.y, px, py)
        if g.police.stars == 0:
            self.state = "walk"
            tx, ty = self.x + math.sin(g.clock_t * 0.2 + self.offset) * 5, self.y
            return 0.0
        self.h = angle_lerp(self.h, vec_heading(px - self.x, py - self.y), clamp(dt * 6, 0, 1))
        eye = (self.x, self.y, self.z + 1.6)
        target = pl.aim_point()
        los = g.city.world.los(eye, target)
        if d > 16 or not los:
            dx, dy = px - self.x, py - self.y
            dd = math.hypot(dx, dy) or 1
            sp = 5.5
            self._move(dt, dx / dd * sp, dy / dd * sp)
            self.state = "chase"
            return sp
        self.state = "shoot"
        self.shoot_t -= dt
        if self.shoot_t <= 0:
            self.shoot_t = random.uniform(0.9, 1.6)
            g.enemy_shot(self, eye, target, 8)
        return 0.0

    def _monster_ai(self, dt, px, py):
        g = self.game
        dx, dy = px - self.x, py - self.y
        d = math.hypot(dx, dy) or 1
        if d > 1.5:
            sp = 4.6 if d < 60 else 2.0
            self._move(dt, dx / d * sp, dy / d * sp)
            return sp
        self.attack_t -= dt
        self.h = vec_heading(dx, dy)
        if self.attack_t <= 0:
            self.attack_t = 0.8
            g.player.hurt(9, (self.x, self.y))
            g.sounds.play("punch", 0.7)
        return 0.0

    def remove(self):
        self.dead = True
        self.game.peds.release(self)


class PedManager:
    def __init__(self, game, count=26):
        self.game = game
        self.count = count
        self.peds = []
        self.t = 0.0
        self.rng = random.Random(77)
        self.grid = {}
        self.monsters = False
        self.pool = {"ped": [], "cop": [], "monster": []}
        self.driver_pool = []
        for _ in range(count + 6):
            p = Ped(game, random_look(self.rng), "ped", self.rng.randrange(99999))
            p.rig.root.hide()
            self.pool["ped"].append(p)
        for _ in range(6):
            p = Ped(game, random_look(self.rng, "grom"), "cop", self.rng.randrange(99999))
            p.rig.root.hide()
            self.pool["cop"].append(p)
        for _ in range(10):
            look = random_look(self.rng)
            r = Rig(game.dyn_root, look, self.rng.randrange(99999))
            r.root.hide()
            self.driver_pool.append(r)

    def acquire(self, role):
        lst = self.pool.setdefault(role, [])
        if lst:
            p = lst.pop()
        else:
            kind = {"cop": "grom", "monster": "cronen"}.get(role, "ped")
            p = Ped(self.game, random_look(self.rng, kind), role, self.rng.randrange(99999))
        p.reset(role)
        return p

    def release(self, p):
        p.rig.root.hide()
        p.rig.root.reparentTo(self.game.dyn_root)
        lst = self.pool.setdefault(p.role, [])
        if len(lst) < 45:
            lst.append(p)
        else:
            p.rig.root.removeNode()

    def release_driver(self, rig):
        if rig is None:
            return
        rig.root.hide()
        rig.root.reparentTo(self.game.dyn_root)
        if len(self.driver_pool) < 30:
            self.driver_pool.append(rig)
        else:
            rig.root.removeNode()

    def near(self, x, y, r):
        out = []
        cs = 20.0
        for ix in range(int((x - r) // cs), int((x + r) // cs) + 1):
            for iy in range(int((y - r) // cs), int((y + r) // cs) + 1):
                for p in self.grid.get((ix, iy), ()):
                    if abs(p.x - x) < r and abs(p.y - y) < r:
                        out.append(p)
        return out

    def make_driver(self, car):
        if self.driver_pool:
            rig = self.driver_pool.pop()
        else:
            rig = Rig(self.game.dyn_root, random_look(self.rng), self.rng.randrange(9999))
        rig.root.reparentTo(car.body)
        rig.root.show()
        rig.root.setHpr(0, 0, 0)
        sx, sy, sz = SEAT.get(car.kind, (-0.38, 0.0, 0.02))
        rig.root.setPos(sx, sy, sz)
        rig.animate(0.016, 0, "sit")
        car.driver_look = True
        return rig

    def eject_driver(self, car, flee=True, cop=False):
        rig = getattr(car, "rig", None)
        look = getattr(car, "driver_look", None)
        if rig is not None:
            self.release_driver(rig)
            car.rig = None
        if look is None:
            return None
        x, y = car.seat_pos(-1)
        p = self.acquire("cop" if cop else "ped")
        p.place(x, y, car.h)
        p.ring = self.nearest_ring(x, y)
        self.peds.append(p)
        if flee and not cop:
            p.panic((car.x, car.y))
        car.driver_look = None
        return p

    def spawn_cop(self, x, y, h):
        p = self.acquire("cop")
        p.place(x, y, h)
        p.state = "chase"
        self.peds.append(p)
        return p

    def spawn_monster(self, x, y):
        p = self.acquire("monster")
        p.place(x, y, random.uniform(0, 360))
        self.peds.append(p)
        return p

    def _ring_grid(self):
        g = {}
        for r in self.game.city.ped_rings:
            g.setdefault((int(r.center[0] // 50), int(r.center[1] // 50)), []).append(r)
        self.rgrid = g

    def rings_near(self, x, y, rmax):
        if getattr(self, "rgrid", None) is None:
            self._ring_grid()
        k = int(rmax // 50) + 1
        ix, iy = int(x // 50), int(y // 50)
        out = []
        for a in range(ix - k, ix + k + 1):
            for b in range(iy - k, iy + k + 1):
                out.extend(self.rgrid.get((a, b), ()))
        return out

    def nearest_ring(self, x, y):
        cands = self.rings_near(x, y, 60) or self.game.city.ped_rings
        return min(cands, key=lambda r: abs(r.center[0] - x) + abs(r.center[1] - y))

    def spawn_walker(self, px, py):
        rings = [r for r in self.rings_near(px, py, 160) if 40 < dist2(r.center[0], r.center[1], px, py) < 150]
        if not rings:
            return
        r = self.rng.choice(rings)
        p = self.acquire("ped")
        p.ring = r
        p.dir = self.rng.choice((-1, 1))
        p.ring_p = self.rng.uniform(0, r.length)
        x, y, _ = p.ring_point(p.ring_p)
        if dist2(x, y, px, py) < 35 or self.game.city.world.hb_blocked(x, y):
            p.remove()
            return
        p.place(x, y)
        self.peds.append(p)

    def clear_civilians(self):
        for p in self.peds:
            if p.role == "ped":
                p.remove()
        self.peds = [p for p in self.peds if p.role != "ped"]

    def update(self, dt):
        g = self.game
        px, py = g.player.pos2()
        grid = {}
        for p in self.peds:
            p.update(dt)
            grid.setdefault((int(p.x // 20), int(p.y // 20)), []).append(p)
        self.grid = grid
        self.t += dt
        if self.t > 0.4:
            self.t = 0.0
            keep = []
            for p in self.peds:
                d = dist2(p.x, p.y, px, py)
                limit = 170 if p.role != "monster" else 400
                if d > limit or (p.dead and p.dead_t > 40):
                    p.remove()
                elif p.role == "cop" and g.police.stars == 0 and d > 60:
                    p.remove()
                else:
                    keep.append(p)
            self.peds = keep
            civ = sum(1 for p in self.peds if p.role == "ped" and not p.dead)
            if civ < self.count and not self.monsters:
                self.spawn_walker(px, py)


# =============================================================================
#  POLIZIA DELLA FEDERAZIONE GALATTICA  (livello di ricercato a stelle)
# =============================================================================
class Drone:
    def __init__(self, game, x, y):
        self.game = game
        m = Mesh()
        m.ellipsoid(0, 0, 0, 1.2, 1.2, 0.35, (60, 70, 112), seg=16, rings=8)
        m.ellipsoid(0, 0, 0.25, 0.5, 0.5, 0.35, (130, 210, 255, 200), seg=12, rings=6)
        m.cylinder(0, 1.1, -0.05, 0.05, 0.18, (255, 60, 50), seg=8, axis="y")
        self.np = m.attach(game.dyn_root, "drone", None, None, (1.0, 80, 0.4, 0.0))
        self.x, self.y, self.z = x, y, 30.0
        self.hp = 70
        self.dead = False
        self.shoot_t = 2.0
        self.t = random.uniform(0, 10)

    def update(self, dt):
        g = self.game
        self.t += dt
        px, py = g.player.pos2()
        pz = g.player.pos3()[2]
        tx = px + math.cos(self.t * 0.5) * 14
        ty = py + math.sin(self.t * 0.5) * 14
        tz = pz + 13 + math.sin(self.t) * 2
        self.x = lerp(self.x, tx, clamp(dt * 0.8, 0, 1))
        self.y = lerp(self.y, ty, clamp(dt * 0.8, 0, 1))
        self.z = lerp(self.z, tz, clamp(dt * 0.8, 0, 1))
        self.np.setPos(self.x, self.y, self.z)
        self.np.setH(vec_heading(px - self.x, py - self.y))
        self.shoot_t -= dt
        if self.shoot_t <= 0:
            self.shoot_t = random.uniform(1.3, 2.2)
            g.enemy_shot(self, (self.x, self.y, self.z - 0.3), g.player.aim_point(), 7)

    def hurt(self, d):
        self.hp -= d
        g = self.game
        g.fx.sparks((self.x, self.y, self.z), 6)
        if self.hp <= 0 and not self.dead:
            self.dead = True
            g.fx.explosion((self.x, self.y, self.z), 0.7)
            g.sounds.play("explosion", 0.8, pos=(self.x, self.y, self.z))
            g.police.crime("uccide_polizia", (self.x, self.y))
            self.np.removeNode()

    def ray_hit(self, o, d, maxd):
        fx, fy, fz = o[0] - self.x, o[1] - self.y, o[2] - self.z
        b = 2 * (fx * d[0] + fy * d[1] + fz * d[2])
        c = fx * fx + fy * fy + fz * fz - 1.3 * 1.3
        disc = b * b - 4 * c
        if disc < 0:
            return None
        t = (-b - math.sqrt(disc)) / 2
        return t if 0 < t < maxd else None


class Police:
    def __init__(self, game):
        self.game = game
        self.heat = 0.0
        self.unseen_t = 0.0
        self.cars = []
        self.drones = []
        self.t = 0.0
        self.flash_t = 0.0

    @property
    def stars(self):
        return int(min(5, self.heat))

    def crime(self, kind, pos):
        add = {"uccide": 0.7, "uccide_polizia": 1.0, "spara_polizia": 0.35, "auto": 0.4, "auto_polizia": 1.0,
               "investe": 0.5, "furto": 1.0, "urto_polizia": 0.25, "spari": 0.15}.get(kind, 0.3)
        minimum = {"uccide_polizia": 2.0, "auto_polizia": 2.0}.get(kind, 1.0)
        if kind == "spari" and self.heat < 1.0:
            return
        before = self.stars
        self.heat = min(5.99, max(self.heat + add, minimum if add >= 0.3 or self.heat >= 1 else self.heat + add))
        self.unseen_t = 0.0
        if self.stars > before:
            self.flash_t = 2.0

    def set_heat(self, h):
        self.heat = h
        self.unseen_t = 0.0
        self.flash_t = 2.0

    def clear(self):
        self.heat = 0.0
        for c in self.cars:
            c.siren_on = False
            if c.driver == "cop":
                c.driver = None
        for d in self.drones:
            if not d.dead:
                d.np.removeNode()
        self.drones = []
        self.cars = []

    def spawn_car(self):
        g = self.game
        px, py = g.player.pos2()
        net = g.city.net
        idx = net.traffic_nodes
        if len(idx) == 0:
            return
        P = net.N[idx]
        d2 = (P[:, 0] - px) ** 2 + (P[:, 1] - py) ** 2
        ok = np.nonzero((d2 > 90 ** 2) & (d2 < 190 ** 2))[0]
        if len(ok) == 0:
            return
        x, y = P[int(random.choice(ok))]
        x, y = float(x), float(y)
        v = Vehicle(g, "polizia", x, y, vec_heading(px - x, py - y))
        v.driver = "cop"
        v.siren_on = True
        v.cops_inside = 2
        v.path = []
        v.path_t = 0.0
        v.stuck_t = 0.0
        v.reverse_t = 0.0
        g.traffic.add(v)
        self.cars.append(v)

    def _path(self, car):
        """percorso sul grafo stradale verso il giocatore (A*)"""
        g = self.game
        px, py = g.player.pos2()
        net = g.city.net
        a = net.nearest_node(car.x, car.y)
        b = net.nearest_node(px, py)
        steps = net.astar(a, b)
        if not steps:
            return []
        path = []
        for (c, d) in steps:
            ch = net.chains[c]
            n = max(1, int(ch.pl.L / 10.0))
            ss = np.linspace(0, ch.pl.L, n + 1)[1:]
            if d < 0:
                ss = ch.pl.L - ss
            X, Y, _tx, _ty = ch.pl.at_many(ss)
            path.extend(zip(X.tolist(), Y.tolist()))
            if len(path) > 120:
                break
        return path

    def drive_car(self, car, dt):
        g = self.game
        pl = g.player
        px, py = pl.pos2()
        d = dist2(car.x, car.y, px, py)
        if car.wrecked or car.dead:
            car.coast(dt)
            car.integrate(dt)
            return
        if self.stars == 0:
            car.siren_on = False
            car.drive(dt, 0.0, 1.0, 0.0)
            car.integrate(dt)
            return
        los = d < 90 and g.city.world.los((car.x, car.y, car.z + 1.5), pl.aim_point())
        if los and d < 70:
            lead = 0.4 if pl.vehicle is not None else 0.0
            tvx, tvy = (pl.vehicle.vx, pl.vehicle.vy) if pl.vehicle is not None else (0, 0)
            tx, ty = px + tvx * lead, py + tvy * lead
        else:
            car.path_t -= dt
            if car.path_t <= 0 or not car.path:
                car.path = self._path(car)
                car.path_t = 2.0
            while car.path and dist2(car.x, car.y, *car.path[0]) < 11:
                car.path.pop(0)
            tx, ty = car.path[0] if car.path else (px, py)
        want_h = vec_heading(tx - car.x, ty - car.y)
        diff = wrap_angle(want_h - car.h)
        steer = clamp(diff / 30.0, -1, 1)
        sp = car.speed
        throttle, brake = 1.0, 0.0
        if abs(diff) > 70 and sp > 12:
            throttle, brake = 0.0, 0.8
        if pl.vehicle is None and d < 16:
            throttle, brake = 0.0, 1.0
            if abs(sp) < 2.0 and getattr(car, "cops_inside", 0) > 0:
                for k in range(car.cops_inside):
                    x, y = car.seat_pos(-1 if k == 0 else 1)
                    g.peds.spawn_cop(x, y, car.h)
                car.cops_inside = 0
        # se bloccata, fa retromarcia
        if car.reverse_t > 0:
            car.reverse_t -= dt
            throttle, brake, steer = 0.0, 1.0, -steer
        elif abs(sp) < 1.0 and throttle > 0:
            car.stuck_t += dt
            if car.stuck_t > 1.5:
                car.stuck_t = 0.0
                car.reverse_t = 1.2
        else:
            car.stuck_t = 0.0
        car.drive(dt, throttle, brake, steer)
        car.integrate(dt)
        if pl.vehicle is None and d < 3.5 and abs(sp) > 6:
            pl.hurt(abs(sp) * 1.5, (car.x, car.y))

    def update(self, dt):
        g = self.game
        pl = g.player
        self.flash_t = max(0.0, self.flash_t - dt)
        stars = self.stars
        self.cars = [c for c in self.cars if not c.dead or not c.np.isEmpty()]
        for c in self.cars:
            if c.driver == "cop":
                self.drive_car(c, dt)
        for dr in self.drones:
            if not dr.dead:
                dr.update(dt)
        self.drones = [d for d in self.drones if not d.dead]
        if stars <= 0:
            if self.cars:
                for c in self.cars:
                    c.siren_on = False
                    if c.driver == "cop":
                        c.driver = None
                self.cars = []
            for d in self.drones:
                d.np.removeNode()
            self.drones = []
            return
        # avvistamento
        seen = False
        target = pl.aim_point()
        for c in self.cars:
            if c.driver == "cop" and dist2(c.x, c.y, target[0], target[1]) < 75:
                if g.city.world.los((c.x, c.y, c.z + 1.4), target):
                    seen = True
                    break
        if not seen:
            for p in g.peds.near(target[0], target[1], 60):
                if p.role == "cop" and not p.dead:
                    seen = True
                    break
        if not seen and self.drones:
            seen = any(dist2(d.x, d.y, target[0], target[1]) < 50 for d in self.drones)
        if seen:
            self.unseen_t = 0.0
        else:
            self.unseen_t += dt
            if self.unseen_t > 7 + stars * 2.5:
                self.heat -= dt * 0.35
                if self.heat < 1.0:
                    self.heat = 0.0
                    g.hud.message("Hai seminato la Federazione!", 2.5)
        self.t -= dt
        if self.t <= 0:
            self.t = 1.0
            want_cars = {1: 1, 2: 2, 3: 3, 4: 4, 5: 5}[stars]
            alive = [c for c in self.cars if c.driver == "cop" and not c.wrecked]
            if len(alive) < want_cars:
                self.spawn_car()
            want_drones = {1: 0, 2: 0, 3: 1, 4: 2, 5: 3}[stars]
            if len(self.drones) < want_drones:
                px, py = pl.pos2()
                ang = random.uniform(0, TAU)
                self.drones.append(Drone(g, px + math.cos(ang) * 120, py + math.sin(ang) * 120))
            n_cops = sum(1 for p in g.peds.peds if p.role == "cop" and not p.dead)
            if pl.vehicle is None and n_cops < 2 + stars and stars >= 1:
                for c in alive:
                    if dist2(c.x, c.y, *pl.pos2()) < 30:
                        c.cops_inside = max(getattr(c, "cops_inside", 0), 1)


# =============================================================================
#  OGGETTI DA RACCOGLIERE
# =============================================================================
class Pickups:
    def __init__(self, game):
        self.game = game
        self.items = []
        self.models = {}
        m = Mesh()
        m.ellipsoid(0, 0, 0, 0.18, 0.18, 0.3, (250, 210, 60), seg=12, rings=8)
        m.ellipsoid(0, 0, 0.3, 0.08, 0.08, 0.05, (150, 230, 90), seg=8, rings=4)
        self.models["seme"] = NodePath(m.node("seme"))
        m = Mesh()
        m.box(-0.18, -0.1, 0, 0.18, 0.1, 0.12, (90, 170, 90))
        m.box(-0.06, -0.105, 0, 0.06, 0.105, 0.12, (240, 230, 200))
        self.models["soldi"] = NodePath(m.node("soldi"))
        m = Mesh()
        m.box(-0.12, -0.04, 0, 0.12, 0.04, 0.3, (186, 194, 204))
        m.box(-0.04, -0.03, 0.3, 0.04, 0.03, 0.38, (150, 156, 166))
        self.models["fiaschetta"] = NodePath(m.node("fiaschetta"))
        m = Mesh()
        m.box(-0.25, -0.08, 0, 0.25, 0.08, 0.3, (60, 70, 120))
        m.box(-0.22, -0.085, 0.1, 0.22, 0.085, 0.16, (90, 180, 255))
        self.models["armatura"] = NodePath(m.node("armatura"))
        self.base_spots = []
        rng = random.Random(9)
        for (x, y) in game.city.spots.get("parchi", [])[:6]:
            fx, fy = game.city.free_point_near(x + 8, y + 3) if hasattr(game.city, "free_point_near") else (x + 8, y + 3)
            self.base_spots.append(("fiaschetta", fx, fy, StaticWorld.terrain(fx, fy)))
        for (x, y, h) in rng.sample(game.city.rooftops, 8):
            self.base_spots.append(("fiaschetta" if rng.random() < 0.6 else "armatura", x, y, h))
        cx, cy = game.city.spots["polizia"]
        self.base_spots.append(("armatura", cx, cy, StaticWorld.terrain(cx, cy)))
        for (k, x, y, z) in self.base_spots:
            self.add(k, x, y, z, respawn=60.0)

    def add(self, kind, x, y, z, amount=0, respawn=0.0, tag=None):
        np_ = self.models[kind].copyTo(self.game.dyn_root)
        np_.setPos(x, y, z + 0.6)
        np_.setShaderInput("u_mat", Vec4(1.0, 80, 0.4, 0.0))
        it = dict(kind=kind, x=x, y=y, z=z, np=np_, amount=amount, respawn=respawn, wait=0.0, tag=tag, t=random.uniform(0, 6))
        self.items.append(it)
        return it

    def drop_money(self, x, y, amount):
        self.add("soldi", x + random.uniform(-0.5, 0.5), y + random.uniform(-0.5, 0.5), StaticWorld.terrain(x, y), amount)

    def remove_tag(self, tag):
        for it in self.items:
            if it["tag"] == tag:
                it["np"].removeNode()
        self.items = [it for it in self.items if it["tag"] != tag]

    def update(self, dt):
        g = self.game
        pl = g.player
        px, py, pz = pl.pos3()
        keep = []
        for it in self.items:
            it["t"] += dt
            if it["wait"] > 0:
                it["wait"] -= dt
                if it["wait"] <= 0:
                    it["np"].show()
                keep.append(it)
                continue
            n = it["np"]
            n.setH(it["t"] * 90)
            n.setZ(it["z"] + 0.6 + math.sin(it["t"] * 2.5) * 0.12)
            if it["kind"] == "seme" and random.random() < 0.3:
                g.fx.glow.emit((it["x"], it["y"], it["z"] + 0.8), (0, 0, 0.6), 0.8, 0.25, 0.05, (1.0, 0.85, 0.3, 1.0),
                               (1.0, 0.6, 0.1, 0.0), spread=0.5)
            reach = 1.4 if pl.vehicle is None else 3.0
            if abs(it["x"] - px) < reach and abs(it["y"] - py) < reach and abs(it["z"] + 0.6 - pz - 0.6) < 2.2:
                if self._take(it):
                    if it["respawn"] > 0:
                        it["wait"] = it["respawn"]
                        n.hide()
                        keep.append(it)
                    else:
                        n.removeNode()
                    continue
            keep.append(it)
        self.items = keep

    def _take(self, it):
        g = self.game
        pl = g.player
        k = it["kind"]
        if k == "soldi":
            pl.money += it["amount"]
            g.hud.toast("+%d Schmeckles" % it["amount"], (0.5, 1.0, 0.5, 1))
        elif k == "fiaschetta":
            if pl.flasks >= 5:
                return False
            pl.flasks += 1
            g.hud.toast("+1 Fiaschetta (H per bere)", (0.8, 0.9, 1.0, 1))
        elif k == "armatura":
            if pl.armor >= 100:
                return False
            pl.armor = 100
            g.hud.toast("Armatura della Federazione!", (0.5, 0.8, 1.0, 1))
        elif k == "seme":
            g.missions.on_seed(it)
        g.sounds.play("pickup", 0.8)
        return True


# =============================================================================
#  GIOCATORE: Rick (a piedi e alla guida)
# =============================================================================
WEAPONS = [
    dict(name="Pugni", dmg=22, rate=0.45, range=1.8, col=None),
    dict(name="Pistola laser", dmg=26, rate=0.2, range=160.0, col=(0.45, 1.0, 0.3), snd="laser"),
    dict(name="Fucile al plasma", dmg=15, rate=0.085, range=170.0, col=(0.35, 0.65, 1.0), snd="plasma"),
]


class Player:
    def __init__(self, game):
        self.game = game
        self.rig = Rig(game.dyn_root, random_look(random.Random(1), "rick"), 1)
        self.x, self.y = game.city.spots["casa"][0], game.city.spots["casa"][1]
        self.z = CURB
        self.vz = 0.0
        self.h = 180.0
        self.vx = self.vy = 0.0
        self.on_ground = True
        self.hp = 100.0
        self.armor = 0.0
        self.money = 0
        self.flasks = 2
        self.fluid = 100.0
        self.weapon = 1
        self.unlocked = [0, 1]
        self.vehicle = None
        self.fire_t = 0.0
        self.portal_t = 0.0
        self.dead = False
        self.dead_t = 0.0
        self.aiming = False
        self.step_t = 0.0
        self.speed_now = 0.0
        self.hurt_t = 0.0
        self.regen_t = 0.0
        self.rig.set_weapon(self.weapon, game.weapon_np)
        self.place(self.x, self.y, self.h)

    def place(self, x, y, h=None):
        self.x, self.y = x, y
        self.z = self.game.city.world.support(x, y, 200.0)
        if h is not None:
            self.h = h
        self.vz = 0.0
        self.rig.root.setPos(self.x, self.y, self.z)
        self.rig.root.setH(self.h)

    def pos2(self):
        if self.vehicle is not None:
            return self.vehicle.x, self.vehicle.y
        return self.x, self.y

    def pos3(self):
        if self.vehicle is not None:
            return self.vehicle.x, self.vehicle.y, self.vehicle.z
        return self.x, self.y, self.z

    def aim_point(self):
        x, y, z = self.pos3()
        return (x, y, z + 1.2)

    def set_weapon(self, i):
        if i in self.unlocked and i != self.weapon:
            self.weapon = i
            self.rig.set_weapon(i, self.game.weapon_np)
            self.game.hud.toast(WEAPONS[i]["name"], (1, 1, 1, 1), 1.0)
            self.game.sounds.play("click", 0.6)

    def hurt(self, d, src=None):
        if self.dead or self.game.state != "play":
            return
        if self.armor > 0:
            a = min(self.armor, d * 0.7)
            self.armor -= a
            d -= a
        self.hp -= d
        self.hurt_t = 0.4
        self.regen_t = 6.0
        self.game.hud.damage_flash(min(1.0, d / 25))
        if self.hp <= 0:
            self.hp = 0
            self.game.on_player_dead()

    def drink(self):
        g = self.game
        if self.flasks <= 0:
            g.hud.toast("Fiaschetta vuota!", (1, 0.7, 0.4, 1))
            return
        if self.hp >= 100:
            return
        self.flasks -= 1
        self.hp = min(100.0, self.hp + 45)
        g.sounds.play("burp", 1.0)
        g.subtitle("rick", random.choice(["*BUUURP*", "Ahh, molto meglio. *burp*", "Medicina per geni. *burp*"]), 2.0)

    # ------------------------------------------------------------------ a piedi
    def update_foot(self, dt, inp):
        g = self.game
        w = g.city.world
        cam_h = g.camctl.yaw
        fwd_in = inp["fwd"]
        side_in = inp["side"]
        sprint = inp["sprint"]
        walk = inp["walk"]
        mag = math.hypot(fwd_in, side_in)
        target_speed = 0.0
        if mag > 0.01:
            fwd_in, side_in = fwd_in / mag, side_in / mag
            target_speed = 7.6 if sprint else (1.7 if walk else 4.3)
            if self.aiming:
                target_speed = min(target_speed, 3.0)
        fx, fy = heading_vec(cam_h)
        rx, ry = fy, -fx
        dx = fx * fwd_in + rx * side_in
        dy = fy * fwd_in + ry * side_in
        accel = 30.0 if self.on_ground else 8.0
        self.vx = approach(self.vx, dx * target_speed, accel * dt)
        self.vy = approach(self.vy, dy * target_speed, accel * dt)
        if self.aiming or g.camctl.first_person:
            self.h = angle_lerp(self.h, cam_h, clamp(dt * 18, 0, 1))
        elif mag > 0.01:
            self.h = angle_lerp(self.h, vec_heading(dx, dy), clamp(dt * 12, 0, 1))
        nx, ny = self.x + self.vx * dt, self.y + self.vy * dt
        nx, ny, hit, n = w.push_circle(nx, ny, self.z, 0.33, 1.8)
        # auto come ostacoli
        for v in g.traffic.near(nx, ny, 6):
            if v.dead and False:
                continue
            if v.fly and v.alt > 1.2:
                continue
            if v.contains(nx, ny, 0.35):
                sp = math.hypot(v.vx, v.vy)
                if sp > 5 and v.driver != "player":
                    self.hurt(sp * 2.0, (v.x, v.y))
                    self.vx += v.vx * 0.8
                    self.vy += v.vy * 0.8
                    self.vz = 4.0
                    self.on_ground = False
                lx, ly = v.local(nx, ny)
                vfx, vfy = v.fwd
                vrx, vry = vfy, -vfx
                if abs(lx) / (v.W / 2) > abs(ly) / (v.L / 2):
                    s = (v.W / 2 + 0.36) * (1 if lx >= 0 else -1)
                    nx, ny = v.x + vrx * s + vfx * ly, v.y + vry * s + vfy * ly
                else:
                    s = (v.L / 2 + 0.36) * (1 if ly >= 0 else -1)
                    nx, ny = v.x + vrx * lx + vfx * s, v.y + vry * lx + vfy * s
        self.x, self.y = nx, ny
        supp = w.support(self.x, self.y, self.z)
        if inp["jump"] and self.on_ground:
            self.vz = 5.4
            self.on_ground = False
            g.sounds.play("jump", 0.5)
        if not self.on_ground or self.z > supp + 0.05:
            self.vz -= 20.0 * dt
            self.z += self.vz * dt
            if self.z <= supp:
                if self.vz < -15:
                    self.hurt((-self.vz - 15) * 7, None)
                    g.fx.dust((self.x, self.y, supp), 1.5)
                self.z = supp
                self.vz = 0.0
                if not self.on_ground:
                    g.sounds.play("step", 0.7)
                self.on_ground = True
            else:
                self.on_ground = False
        else:
            self.z = lerp(self.z, supp, clamp(dt * 15, 0, 1))
            self.on_ground = True
        sp = math.hypot(self.vx, self.vy)
        self.speed_now = sp
        if self.on_ground and sp > 1.0:
            self.step_t -= dt * sp
            if self.step_t <= 0:
                self.step_t = 1.6
                g.sounds.play("step", 0.35 + sp * 0.04, 0.9 + random.random() * 0.2)
        self.rig.root.setPos(self.x, self.y, self.z)
        self.rig.root.setH(self.h)
        state = "move" if self.on_ground else "fall"
        aim_pitch = clamp(-g.camctl.pitch, -60, 60) if self.aiming else 0.0
        self.rig.animate(dt, sp if self.on_ground else 0.0, state, aim=self.aiming and self.weapon > 0, aim_pitch=aim_pitch)
        if self.y > 1e6:
            pass

    # ------------------------------------------------------------------ alla guida
    def update_drive(self, dt, inp):
        v = self.vehicle
        g = self.game
        lift = 0.0
        if v.fly:
            lift = (1.0 if inp["jump"] else 0.0) - (1.0 if inp["down"] else 0.0)
        handbrake = inp["jump"] and not v.fly
        if v.wrecked:
            v.coast(dt)
        else:
            v.drive(dt, max(0.0, inp["fwd"]), max(0.0, -inp["fwd"]), -inp["side"], handbrake, lift)
        v.integrate(dt)
        sp = abs(v.speed)
        rpm = 0.6 + min(1.8, sp / v.spec["top"] * 1.8) + (0.25 if inp["fwd"] > 0 else 0)
        g.sounds.loop("engine", 0.55, rpm if not v.fly else rpm * 1.6)
        g.sounds.loop("skid", 0.5 * v.skid if sp > 6 and not v.fly else 0.0, 1.0)
        if v.skid > 0.5 and sp > 8 and not v.fly:
            for (steer, spin, front) in v.wheels[2:]:
                p = steer.getPos(g.render)
                g.fx.smoke.emit((p[0], p[1], p[2] - 0.2), (0, 0, 0.5), 1.2, 0.3, 1.2, (0.8, 0.8, 0.8, 0.25),
                                (0.8, 0.8, 0.8, 0.0))
        # investire i pedoni
        if sp > 3.0:
            for p in g.peds.near(v.x, v.y, 6):
                if not p.dead and p.air_t <= 0 and v.contains(p.x, p.y, 0.4):
                    if v.fly and v.alt > 1.2:
                        continue
                    force = (v.vx * 0.9, v.vy * 0.9, 3 + sp * 0.25)
                    p.hurt(sp * 6, (v.x, v.y), True, force)
                    g.sounds.play("punch", 0.8)
                    if p.role == "ped":
                        g.police.crime("investe", (p.x, p.y))

    # ------------------------------------------------------------------ armi
    def try_fire(self, dt, firing):
        g = self.game
        self.fire_t -= dt
        wpn = WEAPONS[self.weapon]
        if not firing or self.fire_t > 0:
            return
        self.fire_t = wpn["rate"]
        if self.weapon == 0:
            self.punch()
            return
        o, d = g.camctl.aim_ray()
        maxd = wpn["range"]
        hit = g.raycast_all(o, d, maxd, ignore_player=True)
        t, obj, n = hit if hit else (maxd, None, None)
        target = (o[0] + d[0] * t, o[1] + d[1] * t, o[2] + d[2] * t)
        if self.vehicle is not None:
            v = self.vehicle
            mz = v.z + 1.3 + v.alt * 0
            muzzle = (v.x + d[0] * 2.4, v.y + d[1] * 2.4, mz)
        else:
            hp = self.rig.hands[1].getPos(g.render)
            muzzle = (hp[0] + d[0] * 0.35, hp[1] + d[1] * 0.35, hp[2] + 0.05)
        sd = (target[0] - muzzle[0], target[1] - muzzle[1], target[2] - muzzle[2])
        sl = math.sqrt(sd[0] ** 2 + sd[1] ** 2 + sd[2] ** 2) or 1
        sdn = (sd[0] / sl, sd[1] / sl, sd[2] / sl)
        block = g.raycast_all(muzzle, sdn, sl - 0.1, ignore_player=True)
        if block is not None:
            t2, obj, n = block
            target = (muzzle[0] + sdn[0] * t2, muzzle[1] + sdn[1] * t2, muzzle[2] + sdn[2] * t2)
        col = wpn["col"]
        g.fx.laser(muzzle, target, (col[0], col[1], col[2]), 0.035 if self.weapon == 1 else 0.028)
        g.fx.muzzle(muzzle, (col[0], col[1], col[2], 1.0))
        g.sounds.play(wpn["snd"], 0.7, 0.95 + random.random() * 0.1)
        g.police.crime("spari", target)
        for p in g.peds.near(target[0], target[1], 25):
            if p.role == "ped" and not p.dead and random.random() < 0.3:
                p.panic(muzzle)
        if obj is not None or n is not None:
            g.fx.impact(target, (col[0], col[1], col[2], 1.0))
        g.apply_hit(obj, wpn["dmg"], target, sdn, by_player=True)

    def punch(self):
        g = self.game
        fx, fy = heading_vec(self.h)
        g.sounds.play("punch", 0.6)
        for p in g.peds.near(self.x, self.y, 3):
            if p.dead:
                continue
            dx, dy = p.x - self.x, p.y - self.y
            d = math.hypot(dx, dy)
            if d < 1.8 and (dx * fx + dy * fy) > 0.2:
                p.hurt(WEAPONS[0]["dmg"], (self.x, self.y), True, (fx * 4, fy * 4, 2.5))
                g.sounds.play("hit", 0.8)
                return

    def portal_jump(self):
        g = self.game
        if self.portal_t > 0:
            return
        if self.vehicle is not None:
            g.hud.toast("Prima scendi dal veicolo (F)", (0.6, 1, 0.5, 1))
            return
        if self.fluid < 25:
            g.hud.toast("Fluido portale insufficiente", (0.6, 1, 0.5, 1))
            return
        o, d = g.camctl.aim_ray()
        hit = g.city.world.raycast(o[0], o[1], o[2], d[0], d[1], d[2], 90.0)
        if hit is None:
            g.hud.toast("Troppo lontano per il portale", (0.6, 1, 0.5, 1))
            return
        t, n = hit
        p = (o[0] + d[0] * t, o[1] + d[1] * t, o[2] + d[2] * t)
        if n[2] > 0.5:
            tx, ty = p[0], p[1]
        else:
            tx, ty = p[0] + n[0] * 0.9, p[1] + n[1] * 0.9
        tz = g.city.world.support(tx, ty, p[2] + 0.5)
        tx, ty, _h, _n = g.city.world.push_circle(tx, ty, tz, 0.35, 1.8)
        tz = g.city.world.support(tx, ty, tz + 0.5)
        if abs(tx) > g.city.world.limit or abs(ty) > g.city.world.limit:
            return
        g.fx.portal((self.x, self.y, self.z + 1.2), g.camctl.yaw, 0.9, 1.1)
        g.fx.portal((tx, ty, tz + 1.2), g.camctl.yaw, 0.9, 1.1)
        g.sounds.play("portal", 0.9)
        self.x, self.y, self.z = tx, ty, tz
        self.vz = 0
        self.vx = self.vy = 0
        self.fluid -= 25
        self.portal_t = 0.8
        g.morty_follow_portal()

    def update(self, dt, inp):
        g = self.game
        self.portal_t = max(0.0, self.portal_t - dt)
        self.fluid = min(100.0, self.fluid + 7.0 * dt)
        self.hurt_t = max(0.0, self.hurt_t - dt)
        if self.regen_t > 0:
            self.regen_t -= dt
        elif self.hp < 50:
            self.hp = min(50.0, self.hp + 2.0 * dt)
        if self.vehicle is None:
            self.aiming = inp["aim"] and self.weapon > 0
            self.update_foot(dt, inp)
        else:
            self.aiming = False
            self.update_drive(dt, inp)
        self.try_fire(dt, inp["fire"])


# =============================================================================
#  TELECAMERA: terza persona (spalla) e prima persona, a piedi e in auto
# =============================================================================
class CameraCtl:
    def __init__(self, game):
        self.game = game
        self.yaw = 180.0
        self.pitch = -10.0
        self.first_person = False
        self.shake = 0.0
        self.idle_t = 0.0
        self.fov = 64.0
        self.pos = Vec3(0, 0, 0)
        self.cur_dist = 4.5

    def mouse(self, dx, dy, sens):
        if abs(dx) + abs(dy) > 0:
            self.idle_t = 0.0
        self.yaw -= dx * sens
        self.pitch = clamp(self.pitch - dy * sens, -75, 55)

    def aim_ray(self):
        cam = self.game.camera
        q = cam.getQuat(self.game.render)
        f = q.getForward()
        p = cam.getPos(self.game.render)
        skip = 0.0 if self.first_person else max(0.0, self.cur_dist - 0.6)
        return (p[0] + f[0] * skip, p[1] + f[1] * skip, p[2] + f[2] * skip), (f[0], f[1], f[2])

    def update(self, dt):
        g = self.game
        pl = g.player
        cam = g.camera
        w = g.city.world
        self.idle_t += dt
        fov_target = 64.0
        head = pl.rig.head
        if pl.vehicle is None:
            if self.first_person:
                head.hide()
                hp = head.getPos(g.render)
                fx, fy = heading_vec(self.yaw)
                pos = Vec3(hp[0] + fx * 0.14, hp[1] + fy * 0.14, hp[2] + 0.13)
                self.cur_dist = 0.0
            else:
                head.show()
                aim = pl.aiming
                dist = 2.2 if aim else 4.4
                shoulder = 0.7 if aim else 0.5
                pivot = Vec3(pl.x, pl.y, pl.z + (1.55 if not aim else 1.6))
                if aim:
                    fov_target = 50.0
                pos = self._orbit(pivot, dist, shoulder, w)
        else:
            v = pl.vehicle
            if self.idle_t > 1.2 and abs(v.speed) > 2.0:
                target_yaw = v.h if v.speed > 0 else v.h
                self.yaw = angle_lerp(self.yaw, target_yaw, clamp(dt * 2.2, 0, 1))
                self.pitch = lerp(self.pitch, -9.0 if not self.first_person else -4.0, clamp(dt * 1.5, 0, 1))
            sp = abs(v.speed)
            fov_target = 64.0 + clamp(sp / 45.0, 0, 1) * 12
            if self.first_person:
                head.hide()
                hp = head.getPos(g.render)
                fx, fy = heading_vec(v.h)
                pos = Vec3(hp[0] + fx * 0.1, hp[1] + fy * 0.1, hp[2] + 0.08)
                self.cur_dist = 0.0
            else:
                head.show()
                dist = 6.0 + v.L * 0.35 + (4.0 if v.fly and v.alt > 2 else 0.0)
                pivot = Vec3(v.x, v.y, v.z + v.H + 0.4)
                pos = self._orbit(pivot, dist, 0.0, w)
        if self.shake > 0:
            s = self.shake
            pos += Vec3(random.uniform(-1, 1) * s * 0.3, random.uniform(-1, 1) * s * 0.3, random.uniform(-1, 1) * s * 0.3)
            self.shake = max(0.0, self.shake - dt * 2.5)
        cam.setPos(pos)
        cam.setHpr(self.yaw, self.pitch, 0)
        self.fov = lerp(self.fov, fov_target, clamp(dt * 6, 0, 1))
        g.camLens.setFov(self.fov)
        self.pos = pos

    def _orbit(self, pivot, dist, shoulder, w):
        h, p = math.radians(self.yaw), math.radians(self.pitch)
        f = Vec3(-math.sin(h) * math.cos(p), math.cos(h) * math.cos(p), math.sin(p))
        r = Vec3(math.cos(h), math.sin(h), 0)
        base = pivot + r * shoulder
        back = -f
        hit = w.raycast(base[0], base[1], base[2], back[0], back[1], back[2], dist + 0.3, ground=True)
        d = dist
        if hit is not None:
            d = max(0.3, hit[0] - 0.3)
        self.cur_dist = lerp(self.cur_dist, d, 0.5) if d > self.cur_dist else d
        pos = base + back * self.cur_dist
        gz = StaticWorld.terrain(pos[0], pos[1]) + 0.3
        if pos[2] < gz:
            pos[2] = gz
        return pos


# =============================================================================
#  MORTY (compagno che ti segue)
# =============================================================================
MORTY_LINES = ["Aw jeez, Rick!", "Rick, aspettami!", "Oh cavolo, oh cavolo...", "Rick, la gente ci guarda!",
               "Possiamo tornare a casa, Rick?", "Questa citta' e' pericolosa, Rick!", "Ok, ok, ce la posso fare!"]
MORTY_SCARED = ["Rick! Stanno sparando!", "Aw jeez, la Federazione!", "Rick, non sparare alla gente!",
                "Oddio oddio oddio!"]


class Morty:
    def __init__(self, game):
        self.game = game
        self.rig = Rig(game.dyn_root, random_look(random.Random(2), "morty"), 2)
        self.rig.set_weapon(1, game.weapon_np)
        x, y = game.player.x + 1.5, game.player.y + 1.0
        self.x, self.y, self.z = x, y, CURB
        self.h = 180.0
        self.in_car = None
        self.stuck_t = 0.0
        self.talk_t = random.uniform(20, 35)
        self.shoot_t = 1.5
        self.speed = 0.0
        self.place(x, y)

    def place(self, x, y):
        self.x, self.y = x, y
        self.z = self.game.city.world.support(x, y, 200.0)
        self.rig.root.reparentTo(self.game.dyn_root)
        self.rig.root.setPos(self.x, self.y, self.z)
        self.rig.root.setH(self.h)

    def enter_car(self, v):
        self.in_car = v
        r = self.rig.root
        r.reparentTo(v.body)
        sy = {"furgone": 1.2, "navicella": -0.6, "sportiva": -0.1}.get(v.kind, 0.0)
        sz = {"furgone": 0.35, "navicella": 0.35, "sportiva": -0.18, "utilitaria": 0.02}.get(v.kind, 0.05)
        r.setPos(0.38 if v.kind != "navicella" else 0.0, sy, sz)
        r.setHpr(0, 0, 0)
        self.rig.animate(0.016, 0, "sit")

    def exit_car(self):
        v = self.in_car
        self.in_car = None
        x, y = v.seat_pos(1)
        x, y, _h, _n = self.game.city.world.push_circle(x, y, v.z, 0.3, 1.5)
        self.place(x, y)

    def teleport_near(self, x, y):
        g = self.game
        for ang in (135, -135, 90, -90, 180, 0):
            tx = x + math.cos(math.radians(g.player.h + 90 + ang)) * 1.8
            ty = y + math.sin(math.radians(g.player.h + 90 + ang)) * 1.8
            nx, ny, hit, _n = g.city.world.push_circle(tx, ty, g.player.z, 0.3, 1.5)
            if not hit:
                g.fx.portal((self.x, self.y, self.z + 0.9), 0, 0.7, 0.9)
                self.place(nx, ny)
                g.fx.portal((nx, ny, self.z + 0.9), 0, 0.7, 0.9)
                return

    def update(self, dt):
        g = self.game
        pl = g.player
        self.talk_t -= dt
        if self.talk_t <= 0:
            self.talk_t = random.uniform(30, 55)
            if g.state == "play" and not g.hud.sub_busy():
                lines = MORTY_SCARED if g.police.stars > 0 else MORTY_LINES
                g.subtitle("morty", random.choice(lines), 2.5)
        if pl.vehicle is not None:
            if self.in_car is not pl.vehicle:
                if self.in_car is not None:
                    self.exit_car()
                d = dist2(self.x, self.y, pl.vehicle.x, pl.vehicle.y)
                if d < 30:
                    if d > 8:
                        g.fx.portal((self.x, self.y, self.z + 0.9), 0, 0.6, 0.9)
                    self.enter_car(pl.vehicle)
            return
        if self.in_car is not None:
            self.exit_car()
        px, py = pl.x, pl.y
        fx, fy = heading_vec(pl.h)
        tx, ty = px - fx * 0.6 + fy * 1.7, py - fy * 0.6 - fx * 1.7
        dx, dy = tx - self.x, ty - self.y
        d = math.hypot(dx, dy)
        if d > 40 or abs(self.z - pl.z) > 4.0:
            self.teleport_near(px, py)
            return
        sp = 0.0
        if d > 0.8:
            sp = 7.0 if d > 6 else (4.2 if d > 2.5 else 1.6)
            vx, vy = dx / d * sp, dy / d * sp
            nx, ny, hit, _n = g.city.world.push_circle(self.x + vx * dt, self.y + vy * dt, self.z, 0.3, 1.5)
            moved = math.hypot(nx - self.x, ny - self.y)
            if moved < sp * dt * 0.3:
                self.stuck_t += dt
                if self.stuck_t > 1.5:
                    self.stuck_t = 0
                    self.teleport_near(px, py)
                    return
            else:
                self.stuck_t = 0.0
            self.x, self.y = nx, ny
            self.h = angle_lerp(self.h, vec_heading(vx, vy), clamp(dt * 10, 0, 1))
        else:
            self.h = angle_lerp(self.h, pl.h, clamp(dt * 4, 0, 1))
        self.z = lerp(self.z, g.city.world.support(self.x, self.y, self.z + 0.4), clamp(dt * 10, 0, 1))
        self.speed = lerp(self.speed, sp, clamp(dt * 8, 0, 1))
        # Morty aiuta (male) a sparare
        self.shoot_t -= dt
        aiming = False
        if self.shoot_t <= 0:
            self.shoot_t = random.uniform(1.2, 2.0)
            tgt = None
            for p in g.peds.near(self.x, self.y, 28):
                if not p.dead and (p.role == "monster" or (p.role == "cop" and g.police.stars > 0)):
                    tgt = p
                    break
            if tgt is not None:
                eye = (self.x, self.y, self.z + 1.2)
                tp = (tgt.x, tgt.y, tgt.z + 1.1)
                if g.city.world.los(eye, tp):
                    self.h = vec_heading(tp[0] - eye[0], tp[1] - eye[1])
                    g.fx.laser(eye, tp, (1.0, 0.85, 0.3), 0.025)
                    g.sounds.play("laser", 0.4, 1.3, pos=eye)
                    if random.random() < 0.5:
                        tgt.hurt(14, eye, True)
                    aiming = True
        self.rig.root.setPos(self.x, self.y, self.z)
        self.rig.root.setH(self.h)
        self.rig.animate(dt, self.speed, "move", aim=aiming)
        cp = g.camctl.pos
        dc = math.sqrt((cp[0] - self.x) ** 2 + (cp[1] - self.y) ** 2 + (cp[2] - self.z - 1.0) ** 2)
        if dc < 2.2:
            self.rig.root.setTransparency(TransparencyAttrib.M_alpha)
            self.rig.root.setAlphaScale(clamp((dc - 0.8) / 1.4, 0.0, 1.0) * 0.7)
        else:
            self.rig.root.clearTransparency()
            self.rig.root.setAlphaScale(1.0)


# =============================================================================
#  BOSS FINALE: il CROMULON, una testa gigante nel cielo
# =============================================================================
class Cromulon3D:
    MAX_HP = 2400

    def __init__(self, game, cx, cy):
        self.game = game
        self.cx, self.cy = cx, cy
        m = Mesh()
        SK, SKD, HAIR = (226, 176, 150), (196, 140, 118), (64, 44, 56)
        S = 9.0
        m.ellipsoid(0, 0, 0, 1.4 * S, 1.3 * S, 1.75 * S, SK, seg=28, rings=18)
        m.ellipsoid(0, -0.15 * S, 0.75 * S, 1.48 * S, 1.38 * S, 1.2 * S, HAIR, seg=26, rings=14)
        m.ellipsoid(0, 0.25 * S, 0.1 * S, 1.3 * S, 1.15 * S, 1.2 * S, SK, seg=26, rings=14)
        for sx in (-1, 1):
            m.ellipsoid(sx * 1.38 * S, 0.0, 0.0, 0.22 * S, 0.3 * S, 0.45 * S, SK, seg=12, rings=8)
            m.ellipsoid(sx * 0.52 * S, 1.12 * S, 0.3 * S, 0.36 * S, 0.12 * S, 0.27 * S, (250, 250, 250), seg=16, rings=10)
            m.ellipsoid(sx * 0.52 * S, 1.22 * S, 0.3 * S, 0.15 * S, 0.05 * S, 0.15 * S, (70, 130, 200), seg=12, rings=8)
            m.ellipsoid(sx * 0.52 * S, 1.26 * S, 0.3 * S, 0.07 * S, 0.03 * S, 0.07 * S, (10, 10, 12), seg=10, rings=6)
            m.box(sx * 0.52 * S - 0.45 * S, 1.05 * S, 0.62 * S, sx * 0.52 * S + 0.45 * S, 1.25 * S, 0.74 * S, SKD)
        m.ellipsoid(0, 1.35 * S, -0.15 * S, 0.22 * S, 0.3 * S, 0.45 * S, SKD, seg=12, rings=8)
        m.ellipsoid(0, 1.12 * S, -0.85 * S, 0.62 * S, 0.2 * S, 0.22 * S, (110, 40, 50), seg=16, rings=8)
        m.ellipsoid(0, 1.2 * S, -0.82 * S, 0.5 * S, 0.12 * S, 0.06 * S, (240, 240, 236), seg=12, rings=6)
        self.np = m.attach(game.dyn_root, "cromulon", None, None, (0.4, 30, 0.08, 0.0))
        self.np.hide(MASK_SHADOW)
        self.radius = 1.6 * S
        self.alt = 220.0
        self.target_alt = 75.0
        self.hp = self.MAX_HP
        self.t = 0.0
        self.attack_t = 4.0
        self.beams = []
        self.orbs = []
        self.dead = False
        self.dying = 0.0
        self.x, self.y, self.z = cx, cy, self.alt
        self.flash = 0.0
        self.np.setPos(self.x, self.y, self.z)
        game.sounds.play("roar", 1.0)

    def eyes(self):
        q = self.np.getQuat(self.game.render)
        out = []
        for sx in (-1, 1):
            p = self.np.getPos(self.game.render) + q.xform(Vec3(sx * 0.52 * 9, 1.3 * 9, 0.3 * 9))
            out.append((p[0], p[1], p[2]))
        return out

    def ray_hit(self, o, d, maxd):
        fx, fy, fz = o[0] - self.x, o[1] - self.y, o[2] - self.z
        b = 2 * (fx * d[0] + fy * d[1] + fz * d[2])
        c = fx * fx + fy * fy + fz * fz - self.radius ** 2
        disc = b * b - 4 * c
        if disc < 0:
            return None
        t = (-b - math.sqrt(disc)) / 2
        return t if 0 < t < maxd else None

    def hurt(self, d):
        if self.dying:
            return
        self.hp -= d
        self.flash = 0.08
        if self.hp <= 0:
            self.hp = 0
            self.dying = 0.01
            g = self.game
            g.sounds.play("roar", 1.0, 0.8)
            g.hud.big("NON MALE!", (1.0, 0.85, 0.3, 1), 3.0)

    def update(self, dt):
        g = self.game
        self.t += dt
        px, py, pz = g.player.pos3()
        if self.dying:
            self.dying += dt
            self.z -= dt * 6
            self.np.setR(math.sin(self.t * 20) * 4)
            if random.random() < 0.5:
                p = (self.x + random.uniform(-12, 12), self.y + random.uniform(-12, 12), self.z + random.uniform(-12, 12))
                g.fx.explosion(p, 1.6)
                g.sounds.play("explosion", 0.5)
            if self.dying > 4.0:
                self.dead = True
                g.fx.explosion((self.x, self.y, self.z), 4.0)
                self.np.removeNode()
                return
            self.np.setPos(self.x, self.y, self.z)
            return
        self.alt = lerp(self.alt, self.target_alt, clamp(dt * 0.6, 0, 1))
        a = self.t * 0.12
        self.x = self.cx + math.cos(a) * 70
        self.y = self.cy + math.sin(a) * 70
        self.z = self.alt + math.sin(self.t * 0.8) * 4
        self.np.setPos(self.x, self.y, self.z)
        want = vec_heading(px - self.x, py - self.y)
        self.np.setH(angle_lerp(self.np.getH(), want, clamp(dt * 1.5, 0, 1)))
        self.np.setP(clamp(math.degrees(math.atan2(pz - self.z, dist2(self.x, self.y, px, py))), -40, 0))
        if self.flash > 0:
            self.flash -= dt
            self.np.setColorScale(2.0, 2.0, 2.0, 1)
        else:
            self.np.setColorScale(1, 1, 1, 1)
        self.attack_t -= dt
        if self.attack_t <= 0:
            phase2 = self.hp < self.MAX_HP * 0.5
            self.attack_t = random.uniform(3.0, 5.0) * (0.7 if phase2 else 1.0)
            r = random.random()
            if r < 0.45:
                self.beams.append(dict(t=0.0, tx=px, ty=py, sweep=random.uniform(-1, 1), hit=False))
                g.sounds.play("roar", 0.5, 1.4)
            else:
                n = 6 if phase2 else 4
                for k in range(n):
                    ox, oy = random.uniform(-14, 14), random.uniform(-14, 14)
                    self.orbs.append(dict(x=self.x, y=self.y, z=self.z - 8, tx=px + ox, ty=py + oy, t=0.0,
                                          dur=random.uniform(2.0, 3.0)))
                g.hud.big("MOSTRAMI COSA SAI FARE!", (1.0, 0.85, 0.3, 1), 1.8)
        # raggi dagli occhi: prima un mirino rosso, poi il raggio
        keep = []
        for b in self.beams:
            b["t"] += dt
            t = b["t"]
            tx = b["tx"] + b["sweep"] * max(0.0, t - 1.2) * 12
            ty = b["ty"] + b["sweep"] * max(0.0, t - 1.2) * 6
            tz = StaticWorld.terrain(tx, ty) + 0.1
            for e in self.eyes():
                if t < 1.2:
                    g.fx.glow.beam(e, (tx, ty, tz), 0.08, (1.0, 0.1, 0.05, 0.6))
                else:
                    g.fx.laser(e, (tx, ty, tz), (1.0, 0.25, 0.1), 0.6)
            if t >= 1.2:
                g.fx.fire((tx, ty, tz), 1.5)
                g.fx.flashes.append([tx, ty, tz + 1, 18.0, 6.0, 1.5, 0.5, 0.05])
                if dist2(tx, ty, px, py) < 3.2 and pz < tz + 3:
                    g.player.hurt(40 * dt * 2.5, (tx, ty))
            if t < 2.6:
                keep.append(b)
        self.beams = keep
        keep = []
        for o in self.orbs:
            o["t"] += dt
            k = o["t"] / o["dur"]
            x = lerp(o["x"], o["tx"], k)
            y = lerp(o["y"], o["ty"], k)
            z = lerp(o["z"], StaticWorld.terrain(o["tx"], o["ty"]), k) + math.sin(k * math.pi) * 20
            g.fx.glow.emit((x, y, z), (0, 0, 0), 0.15, 1.6, 0.8, (1.0, 0.4, 0.8, 1.0), (1.0, 0.2, 0.5, 0.0))
            if k >= 1.0:
                g.fx.explosion((x, y, z), 0.9)
                g.sounds.play("explosion", 0.7, pos=(x, y, z))
                g.blast((x, y, z), 6.0, 32, source=self)
            else:
                keep.append(o)
        self.orbs = keep


# =============================================================================
#  MISSIONI
# =============================================================================
MISSION_INFO = [
    dict(title="Il garage di Rick", desc="Porta Morty da Blips and Chitz con la navicella."),
    dict(title="Mega Semi", desc="Raccogli i 5 Mega Semi sparsi per la citta'."),
    dict(title="Guai con la Federazione", desc="Distruggi le auto della Federazione e seminale."),
    dict(title="Dimensione Cronenberg", desc="Elimina i Cronenberg usciti dal portale."),
    dict(title="Mostrami cosa sai fare", desc="Sconfiggi il Cromulon che minaccia la Terra."),
]


class Missions:
    def __init__(self, game):
        self.game = game
        self.idx = game.save.get("mission", 0)
        self.active = False
        self.stage = 0
        self.t = 0.0
        self.marker = None
        self.objective = ""
        self.target = None
        self.counter = 0
        self.need = 0
        self.boss = None
        self.portal_np = None
        self.cronen_mode = False
        self.start_points = self._start_points()
        self.seed_spots = []

    def _start_points(self):
        return self.game.city.mission_starts()

    # --------------------------------------------------------------- marker
    def _make_marker(self, x, y, color=(1.0, 0.85, 0.2)):
        if self.marker is not None:
            self.marker.removeNode()
        m = Mesh()
        m.cylinder(0, 0, 0, 2.5, 1.6, (int(color[0] * 255), int(color[1] * 255), int(color[2] * 255), 110), seg=24, cap=False)
        np_ = m.attach(self.game.render, "marker")
        np_.setShader(self.game.env.fx_shader)
        np_.setTransparency(TransparencyAttrib.M_alpha)
        np_.setDepthWrite(False)
        np_.setTwoSided(True)
        np_.setLightOff(1)
        np_.setBin("fixed", 12)
        np_.hide(MASK_SHADOW | MASK_MAP)
        np_.setPos(x, y, self.game.city.world.support(x, y, 200.0))
        self.marker = np_
        self.target = (x, y)

    def _clear_marker(self):
        if self.marker is not None:
            self.marker.removeNode()
            self.marker = None
        self.target = None

    def available_start(self):
        if self.active or self.idx >= len(MISSION_INFO):
            return None
        return self.start_points[self.idx]

    # --------------------------------------------------------------- ciclo
    def update(self, dt):
        g = self.game
        self.t += dt
        if self.marker is not None:
            self.marker.setH(self.t * 40)
            k = 1.0 + 0.08 * math.sin(self.t * 4)
            self.marker.setScale(k, k, 1)
        if not self.active:
            if self.idx >= len(MISSION_INFO):
                self._clear_marker()
                self.objective = "Gioco libero: esplora la citta'!"
                return
            sp = self.start_points[self.idx]
            if sp is None:
                self.start()
                return
            if self.marker is None or self.target != sp:
                self._make_marker(sp[0], sp[1])
            self.objective = "Missione: %s  -  raggiungi il segnalino giallo" % MISSION_INFO[self.idx]["title"]
            px, py = g.player.pos2()
            if dist2(px, py, sp[0], sp[1]) < 2.6 and g.player.vehicle is None:
                self.start()
            return
        if self.idx >= len(MISSION_INFO):
            self.active = False
            return
        getattr(self, "_m%d" % self.idx)(dt)

    def start(self):
        g = self.game
        self.active = True
        self.stage = 0
        self.t = 0.0
        self.counter = 0
        self._clear_marker()
        g.hud.clear_subs()
        g.hud.big(MISSION_INFO[self.idx]["title"].upper(), (1.0, 0.85, 0.3, 1), 3.0)
        getattr(self, "_s%d" % self.idx)()

    def complete(self, reward, lines=()):
        g = self.game
        self.active = False
        for who, s in lines:
            g.subtitle(who, s, 3.5)
        g.player.money += reward
        g.hud.big("MISSIONE COMPIUTA", (1.0, 0.85, 0.3, 1), 4.0, sub="+%d Schmeckles" % reward)
        g.sounds.play("mission", 1.0)
        self.idx += 1
        self._clear_marker()
        g.save_game()

    def fail(self, reason="MISSIONE FALLITA"):
        g = self.game
        if not self.active:
            return
        self.active = False
        self._cleanup()
        g.hud.big(reason, (1.0, 0.3, 0.3, 1), 3.5)

    def _cleanup(self):
        g = self.game
        self._clear_marker()
        g.pickups.remove_tag("seme")
        if self.cronen_mode:
            self._end_cronenberg()
        if self.boss is not None and not self.boss.dead:
            self.boss.np.removeNode()
        self.boss = None

    # --------------------------------------------------------------- 0: navicella
    def _s0(self):
        g = self.game
        g.subtitle("rick", "Morty! *burp* Sali sulla navicella, andiamo da Blips and Chitz!", 4.0)
        g.subtitle("morty", "Aw jeez, Rick, adesso? Ho i compiti...", 3.0)
        g.subtitle("rick", "I compiti li fanno le persone mediocri, Morty. Premi F vicino alla navicella.", 4.0)

    def _m0(self, dt):
        g = self.game
        v = g.player.vehicle
        if self.stage == 0:
            self.objective = "Sali sulla navicella spaziale di Rick (F)"
            self.target = (g.cruiser.x, g.cruiser.y)
            if v is not None:
                self.stage = 1
                ax, ay = g.city.spots["arcade"]
                self._make_marker(ax, ay, (0.3, 1.0, 1.0))
                g.subtitle("rick", "Bene. Spazio per salire, Ctrl per scendere. Non schiantarti, Morty.", 4.0)
        elif self.stage == 1:
            self.objective = "Vai da Blips and Chitz (segui il punto azzurro sulla mappa)"
            px, py = g.player.pos2()
            if dist2(px, py, *self.target) < 9 and (v is None or abs(v.speed) < 8):
                self.complete(300, [("morty", "Blips and Chitz! Grazie Rick!"),
                                    ("rick", "Divertiti, Morty. Io intanto torno al garage a fare scienza.")])

    # --------------------------------------------------------------- 1: mega semi
    def _s1(self):
        g = self.game
        c = g.city
        spots = c.seed_spots()
        for (x, y, z) in spots:
            g.pickups.add("seme", x, y, z, tag="seme")
        self.need = len(spots)
        self.counter = 0
        g.subtitle("rick", "Morty, mi servono 5 Mega Semi. Sono sparsi per la citta'. Uno e' su un tetto.", 4.5)
        g.subtitle("rick", "Per i tetti usa la pistola portale: mira e premi E. *burp*", 4.0)

    def on_seed(self, it):
        g = self.game
        self.counter += 1
        g.hud.toast("Mega Seme %d/%d" % (self.counter, self.need), (1.0, 0.85, 0.3, 1))
        if self.counter == 3:
            g.subtitle("morty", "Rick, questi semi sono... caldi e appiccicosi.", 3.0)

    def _m1(self, dt):
        g = self.game
        self.objective = "Raccogli i Mega Semi (%d/%d)  -  punti dorati sulla mappa" % (self.counter, self.need)
        if self.counter >= self.need:
            if 2 not in g.player.unlocked:
                g.player.unlocked.append(2)
            self.complete(1000, [("rick", "Perfetto, Morty! Come premio ti ho potenziato il fucile al plasma: tasto 3."),
                                 ("morty", "Un fucile? Rick, io ho quattordici anni!")])

    # --------------------------------------------------------------- 2: federazione
    def _s2(self):
        g = self.game
        g.police.set_heat(3.2)
        self.counter = 0
        self.need = 2
        g.subtitle("rick", "La Federazione Galattica ha messo una taglia su di me, Morty. Diamogli un motivo.", 4.0)
        g.subtitle("morty", "Rick, no! Non provocare gli insetti con le pistole!", 3.0)

    def on_cop_car_destroyed(self):
        if self.active and self.idx == 2 and self.stage == 0:
            self.counter += 1

    def _m2(self, dt):
        g = self.game
        if self.stage == 0:
            self.objective = "Distruggi le auto della Federazione (%d/%d)" % (self.counter, self.need)
            if g.police.stars < 2:
                g.police.set_heat(3.2)
            if self.counter >= self.need:
                self.stage = 1
                g.police.set_heat(max(g.police.heat, 3.0))
                g.subtitle("rick", "Ottimo! Ora seminiamoli, Morty! Allontanati e nasconditi.", 3.5)
        else:
            self.objective = "Semina la Federazione (perdi le stelle)"
            if g.police.stars == 0:
                self.complete(1500, [("morty", "Li abbiamo seminati! Oh cavolo, il cuore mi esplode."),
                                     ("rick", "La burocrazia e' lenta, Morty. Ricordatelo.")])

    # --------------------------------------------------------------- 3: cronenberg
    def _s3(self):
        g = self.game
        x, y = g.city.spots["cronenberg"]
        self.portal_np = g.fx.portal((x + 14, y, 4.6), 90, -1, 3.0)
        g.sounds.play("portal", 1.0, 0.7)
        self.cronen_mode = True
        g.env.set_tint((1.28, 0.8, 0.74))
        g.peds.monsters = True
        g.peds.clear_civilians()
        self.need = 12
        self.counter = 0
        for k in range(self.need):
            a = k / self.need * TAU
            g.peds.spawn_monster(x - 10 + math.cos(a) * random.uniform(18, 40), y + math.sin(a) * random.uniform(18, 40))
        g.subtitle("rick", "Il portale per la dimensione Cronenberg si e' riaperto! Rimettiamoli dentro... a pezzi.", 4.0)
        g.subtitle("morty", "Rick, quelli erano persone! Aw jeez, sono orribili!", 3.0)

    def on_monster_killed(self, p):
        if self.active and self.idx == 3:
            self.counter += 1

    def _end_cronenberg(self):
        g = self.game
        self.cronen_mode = False
        g.env.set_tint((1, 1, 1))
        g.peds.monsters = False
        for p in g.peds.peds:
            if p.role == "monster":
                p.remove()
        g.peds.peds = [p for p in g.peds.peds if p.role != "monster"]
        if self.portal_np is not None:
            for p in g.fx.portals:
                if p["np"] is self.portal_np:
                    p["life"] = p["t"] + 0.5
            self.portal_np = None

    def _m3(self, dt):
        g = self.game
        x, y = g.city.spots["cronenberg"]
        if self.stage == 0:
            alive = sum(1 for p in g.peds.peds if p.role == "monster" and not p.dead)
            self.objective = "Elimina i Cronenberg (%d/%d)" % (min(self.counter, self.need), self.need)
            if alive < 3 and self.counter < self.need:
                px, py = g.player.pos2()
                a = random.uniform(0, TAU)
                g.peds.spawn_monster(px + math.cos(a) * 35, py + math.sin(a) * 35)
            if self.counter >= self.need:
                self.stage = 1
                self._make_marker(x + 9, y, (0.4, 1.0, 0.3))
                g.subtitle("rick", "Fatto. Torna al portale, Morty, lo chiudo io.", 3.0)
        else:
            self.objective = "Torna al portale verde per chiuderlo"
            px, py = g.player.pos2()
            if dist2(px, py, x + 9, y) < 6:
                self._end_cronenberg()
                self.complete(2000, [("rick", "Portale chiuso. La dimensione Cronenberg resta... di la'."),
                                     ("morty", "Non voglio mai piu' vedere un Cronenberg, Rick.")])

    # --------------------------------------------------------------- 4: cromulon
    def _s4(self):
        g = self.game
        cx, cy = self.start_points[4]
        self.boss = Cromulon3D(g, cx, cy + 13)
        g.hud.big("MOSTRAMI COSA SAI FARE!", (1.0, 0.85, 0.3, 1), 3.5)
        g.subtitle("morty", "Rick! C'e' una testa gigante nel cielo!", 3.0)
        g.subtitle("rick", "Un Cromulon, Morty. Vogliono uno spettacolo o distruggono il pianeta. Spara agli occhi!", 4.5)

    def _m4(self, dt):
        g = self.game
        b = self.boss
        if b is None:
            return
        b.update(dt)
        self.objective = "Sconfiggi il Cromulon!  (evita i raggi rossi e le sfere)"
        if b.dead:
            self.boss = None
            self.complete(5000, [("cromulon", "NON MALE! NON MALE PER NIENTE! CI PIACE!"),
                                 ("morty", "Ce l'abbiamo fatta, Rick! Abbiamo salvato la Terra!"),
                                 ("rick", "Ovvio, Morty. Wubba Lubba Dub Dub! Ora la citta' e' tutta nostra.")])
            g.hud.credits()

    def blips(self):
        """punti da mostrare sulla minimappa: (x, y, colore, sempre_visibile)"""
        g = self.game
        out = []
        if self.target is not None:
            col = (1.0, 0.85, 0.2, 1)
            if self.active and self.idx == 0 and self.stage == 1:
                col = (0.3, 1.0, 1.0, 1)
            out.append((self.target[0], self.target[1], col, True))
        for it in g.pickups.items:
            if it["kind"] == "seme" and it["wait"] <= 0:
                out.append((it["x"], it["y"], (1.0, 0.75, 0.1, 1), True))
        if self.boss is not None:
            out.append((self.boss.x, self.boss.y, (1.0, 0.3, 0.8, 1), True))
        if self.active and self.idx == 3:
            for p in g.peds.peds:
                if p.role == "monster" and not p.dead:
                    out.append((p.x, p.y, (1.0, 0.4, 0.4, 1), False))
        return out


# =============================================================================
#  HUD stile GTA: minimappa, vita, stelle, soldi, sottotitoli
# =============================================================================
def _icon_tex(kind, size=64):
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    c = (size - 1) / 2
    dx, dy = (xx - c) / c, (c - yy) / c
    r = np.sqrt(dx * dx + dy * dy)
    a = np.zeros((size, size), np.float32)
    rgb = np.ones((size, size, 3), np.float32) * 255
    if kind == "circle":
        a = np.clip((1 - r) * size * 0.5, 0, 1)
    elif kind == "mask":
        a = np.clip((0.97 - r) * size * 0.5, 0, 1)
    elif kind == "ring":
        a = np.clip(1 - np.abs(r - 0.94) * size * 0.35, 0, 1)
        rgb[:] = (20, 20, 24)
    elif kind in ("star", "star_off"):
        ang = np.arctan2(dy, dx) + math.pi / 2
        k = (np.cos(ang * 5) * 0.5 + 0.5)
        rad = 0.42 + 0.5 * k ** 2.2
        inside = r < rad
        a = np.clip((rad - r) * size * 0.6, 0, 1)
        if kind == "star":
            rgb[:] = (255, 255, 255)
        else:
            edge = np.clip(1 - np.abs(r - rad + 0.06) * size * 0.25, 0, 1)
            a = np.maximum(edge * inside, a * 0.18)
    elif kind == "arrow":
        inside = (dy > -0.6) & (np.abs(dx) < (0.75 - (dy + 0.6) * 0.55)) & ~((dy < -0.2) & (np.abs(dx) < (dy + 0.6) * 0.9))
        a = inside.astype(np.float32)
    elif kind == "cross":
        a = (((np.abs(dx) < 0.09) & (np.abs(dy) > 0.25) & (np.abs(dy) < 0.85)) |
             ((np.abs(dy) < 0.09) & (np.abs(dx) > 0.25) & (np.abs(dx) < 0.85))).astype(np.float32)
        a = np.maximum(a, (r < 0.1).astype(np.float32))
    elif kind == "vignette":
        a = np.clip((r - 0.55) * 1.6, 0, 1) ** 1.6
        rgb[:] = 0
    img = np.dstack([rgb, a * 255])
    return make_texture(to_u8(img), kind, repeat=False)


def find_font(loader, bold=True):
    cands = []
    windir = os.environ.get("WINDIR", "C:\\Windows")
    for n in (["arialbd.ttf", "verdanab.ttf", "segoeuib.ttf"] if bold else ["arial.ttf", "verdana.ttf", "segoeui.ttf"]):
        cands.append(os.path.join(windir, "Fonts", n))
    cands += ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
              "/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/Library/Fonts/Arial Bold.ttf"]
    for p in cands:
        if os.path.exists(p):
            try:
                f = loader.loadFont(Filename.fromOsSpecific(p))
                if f is not None and f.isValid():
                    f.setPixelsPerUnit(64)
                    return f
            except Exception:
                pass
    return None


SPEAKER_COL = {"rick": (0.55, 0.85, 1.0, 1), "morty": (1.0, 0.9, 0.35, 1), "cromulon": (1.0, 0.55, 0.85, 1),
               "passante": (0.85, 0.85, 0.85, 1)}
SPEAKER_NAME = {"rick": "Rick", "morty": "Morty", "cromulon": "Cromulon", "passante": "Passante"}


class HUD:
    def __init__(self, game):
        self.g = game
        g = game
        self.font = find_font(g.loader, True)
        self.font_r = find_font(g.loader, False) or self.font
        self.root = g.aspect2d.attachNewNode("hud")
        self.tex = {k: _icon_tex(k) for k in ("circle", "mask", "ring", "star", "star_off", "arrow", "cross", "vignette")}
        # vignettatura
        self.vig = OnscreenImage(self.tex["vignette"], parent=g.render2d, scale=(1, 1, 1))
        self.vig.setTransparency(TransparencyAttrib.M_alpha)
        self.vig.setColorScale(1, 1, 1, 0.55)
        self.vig.setBin("background", 50)
        self.dmg = OnscreenImage(self.tex["vignette"], parent=g.render2d, scale=(1, 1, 1))
        self.dmg.setTransparency(TransparencyAttrib.M_alpha)
        self.dmg.setColorScale(0.8, 0, 0, 0)
        self.dmg_a = 0.0
        # minimappa
        self.mm = g.a2dBottomLeft.attachNewNode("minimappa")
        self.mm.setPos(0.36, 0, 0.42)
        self.mm_r = 0.29
        cm = CardMaker("mappa")
        cm.setFrame(-self.mm_r, self.mm_r, -self.mm_r, self.mm_r)
        self.map_card = self.mm.attachNewNode(cm.generate())
        self.map_tex = make_texture(g.city.map_img, "mappa", repeat=False)
        self.map_tex.setWrapU(SamplerState.WM_border_color)
        self.map_tex.setWrapV(SamplerState.WM_border_color)
        self.map_tex.setBorderColor(Vec4(0.18, 0.24, 0.18, 1))
        self.ts_map = TextureStage("mappa")
        self.ts_mask = TextureStage("maschera")
        self.map_card.setTexture(self.ts_map, self.map_tex)
        self.map_card.setTexture(self.ts_mask, self.tex["mask"])
        self.map_card.setTransparency(TransparencyAttrib.M_alpha)
        self.map_card.setColorScale(1, 1, 1, 0.92)
        ring = OnscreenImage(self.tex["ring"], parent=self.mm, scale=self.mm_r * 1.04)
        ring.setTransparency(TransparencyAttrib.M_alpha)
        self.arrow = OnscreenImage(self.tex["arrow"], parent=self.mm, scale=0.028)
        self.arrow.setTransparency(TransparencyAttrib.M_alpha)
        self.arrow.setColorScale(1, 1, 1, 1)
        self.north = self._text("N", 0.045, (1, 1, 1, 1), parent=self.mm)
        self.blip_nodes = []
        self.view_r = 110.0
        # barre vita / armatura / portale
        self.bars = g.a2dBottomLeft.attachNewNode("barre")
        self.bars.setPos(0.07, 0, 0.07)
        self.bar_hp = self._bar(0.0, 0.0, 0.29, (0.35, 0.85, 0.35, 1))
        self.bar_ar = self._bar(0.31, 0.0, 0.27, (0.35, 0.65, 1.0, 1))
        self.bar_fl = self._bar(0.0, -0.04, 0.58, (0.5, 1.0, 0.35, 1), h=0.012)
        # in alto a destra
        self.tr = g.a2dTopRight.attachNewNode("tr")
        self.money = self._text("", 0.075, (0.55, 1.0, 0.55, 1), parent=self.tr, pos=(-0.06, -0.12), align=TextNode.ARight)
        self.weapon = self._text("", 0.05, (1, 1, 1, 1), parent=self.tr, pos=(-0.06, -0.31), align=TextNode.ARight)
        self.flasks = self._text("", 0.042, (0.85, 0.9, 1, 1), parent=self.tr, pos=(-0.06, -0.38), align=TextNode.ARight)
        self.stars = []
        for i in range(5):
            s = OnscreenImage(self.tex["star_off"], parent=self.tr, pos=(-0.42 + i * 0.075, 0, -0.205), scale=0.034)
            s.setTransparency(TransparencyAttrib.M_alpha)
            self.stars.append(s)
        # in alto a sinistra: obiettivo
        self.tl = g.a2dTopLeft.attachNewNode("tl")
        self.obj = self._text("", 0.048, (1, 1, 1, 1), parent=self.tl, pos=(0.06, -0.1), align=TextNode.ALeft, wrap=26)
        # sottotitoli
        self.sub = self._text("", 0.058, (1, 1, 1, 1), parent=g.a2dBottomCenter, pos=(0, 0.32), wrap=30)
        self.sub_queue = []
        self.sub_t = 0.0
        # messaggi grandi
        self.bigt = self._text("", 0.13, (1, 0.85, 0.3, 1), parent=g.aspect2d, pos=(0, 0.35), font=self.font)
        self.bigs = self._text("", 0.065, (1, 1, 1, 1), parent=g.aspect2d, pos=(0, 0.24))
        self.big_t = 0.0
        self.toasts = []
        self.toast_np = self._text("", 0.05, (1, 1, 1, 1), parent=g.a2dTopRight, pos=(-0.06, -0.5), align=TextNode.ARight)
        self.hint = self._text("", 0.05, (1, 1, 1, 1), parent=g.a2dBottomCenter, pos=(0, 0.17))
        self.speed = self._text("", 0.085, (1, 1, 1, 1), parent=g.a2dBottomRight, pos=(-0.08, 0.1), align=TextNode.ARight)
        self.cross = OnscreenImage(self.tex["cross"], parent=g.aspect2d, scale=0.03)
        self.cross.setTransparency(TransparencyAttrib.M_alpha)
        self.boss_bar = self._bar(-0.6, 0, 1.2, (1.0, 0.35, 0.75, 1), parent=g.a2dTopCenter, h=0.03)
        self.boss_bar["root"].setPos(-0.6, 0, -0.08)
        self.boss_lbl = self._text("CROMULON", 0.045, (1, 0.7, 0.9, 1), parent=g.a2dTopCenter, pos=(0, -0.05))
        self.boss_bar["root"].hide()
        self.boss_lbl.hide()
        self.credits_t = 0.0
        self.cred = self._text("", 0.06, (1, 1, 1, 1), parent=g.aspect2d, pos=(0, 0), wrap=30)
        self.bigmap = None

    # ---------------------------------------------------------------- utilita'
    def _text(self, s, scale, col, parent=None, pos=(0, 0), align=TextNode.ACenter, wrap=None, font=None):
        t = OnscreenText(text=s, scale=scale, fg=col, shadow=(0, 0, 0, 0.85), parent=parent or self.root, pos=pos,
                         align=align, mayChange=True, font=font or self.font_r, wordwrap=wrap)
        return t

    def _bar(self, x, y, w, col, h=0.022, parent=None):
        root = (parent or self.bars).attachNewNode("barra")
        root.setPos(x, 0, y)
        cm = CardMaker("bg")
        cm.setFrame(0, w, 0, h)
        bg = root.attachNewNode(cm.generate())
        bg.setColor(0, 0, 0, 0.55)
        bg.setTransparency(TransparencyAttrib.M_alpha)
        cm2 = CardMaker("fg")
        cm2.setFrame(0, w, 0, h)
        fg = root.attachNewNode(cm2.generate())
        fg.setColor(*col)
        fg.setPos(0, -0.01, 0)
        return dict(root=root, fg=fg, w=w)

    @staticmethod
    def _set_bar(b, k):
        b["fg"].setSx(max(0.001, clamp(k, 0, 1)))

    def toast(self, s, col=(1, 1, 1, 1), dur=2.2):
        self.toasts.append([s, col, dur])
        self.toasts = self.toasts[-3:]

    def big(self, s, col, dur=3.0, sub=""):
        self.bigt.setText(s)
        self.bigt.setFg(col)
        self.bigs.setText(sub)
        self.big_t = dur

    def subtitle(self, who, s, dur=3.0):
        self.sub_queue.append((who, s, dur))
        if len(self.sub_queue) > 4:
            self.sub_queue = self.sub_queue[-4:]

    def clear_subs(self):
        self.sub_queue = []
        self.sub_t = 0.0
        self.sub.setText("")

    def sub_busy(self):
        return self.sub_t > 0 or bool(self.sub_queue)

    def damage_flash(self, k):
        self.dmg_a = min(1.0, self.dmg_a + k)

    def credits(self):
        self.credits_t = 14.0

    def set_visible(self, on):
        for n in (self.root, self.mm, self.bars, self.tr, self.tl, self.cross, self.vig):
            if on:
                n.show()
            else:
                n.hide()
        for n in (self.sub, self.hint, self.speed, self.toast_np, self.bigt, self.bigs):
            if on:
                n.show()
            else:
                n.hide()

    # ---------------------------------------------------------------- aggiornamento
    def update(self, dt):
        g = self.g
        pl = g.player
        cam_h = g.camctl.yaw
        px, py = pl.pos2()
        # minimappa ruotata come la telecamera
        R = g.city.map_r
        vr = self.view_r * (1.6 if pl.vehicle is not None and abs(pl.vehicle.speed) > 15 else 1.0)
        a = math.radians(cam_h)
        c, s = math.cos(a), math.sin(a)
        k = 2 * vr / (2 * R)
        A00, A01 = c * k, -s * k
        A10, A11 = s * k, c * k
        bx = (px + R) / (2 * R) - (A00 * 0.5 + A01 * 0.5)
        by = (py + R) / (2 * R) - (A10 * 0.5 + A11 * 0.5)
        mat = LMatrix4f(A00, A10, 0, 0, A01, A11, 0, 0, 0, 0, 1, 0, bx, by, 0, 1)
        self.map_card.setTexTransform(self.ts_map, TransformState.makeMat(mat))
        self.arrow.setR(cam_h - (pl.vehicle.h if pl.vehicle is not None else pl.h))
        nx, ny = self._map_pos(0, 1e6, px, py, cam_h, vr, clampit=True)
        self.north.setPos(nx, ny - 0.016)
        blips = g.missions.blips()
        for c_ in g.police.cars:
            if not c_.dead and c_.driver == "cop":
                flash = (1, 0.2, 0.2, 1) if int(g.clock_t * 4) % 2 else (0.3, 0.4, 1, 1)
                blips.append((c_.x, c_.y, flash, False))
        if g.player.vehicle is not g.cruiser and not g.cruiser.dead:
            blips.append((g.cruiser.x, g.cruiser.y, (0.6, 1.0, 0.6, 1), False))
        while len(self.blip_nodes) < len(blips):
            b = OnscreenImage(self.tex["circle"], parent=self.mm, scale=0.016)
            b.setTransparency(TransparencyAttrib.M_alpha)
            self.blip_nodes.append(b)
        for i, b in enumerate(self.blip_nodes):
            if i >= len(blips):
                b.hide()
                continue
            x, y, col, always = blips[i]
            mx, my, inside = self._map_pos(x, y, px, py, cam_h, vr, clampit=always, ret_inside=True)
            if not inside and not always:
                b.hide()
                continue
            b.show()
            b.setPos(mx, 0, my)
            b.setColorScale(*col)
            b.setScale(0.02 if always else 0.013)
        # barre
        self._set_bar(self.bar_hp, pl.hp / 100.0)
        self.bar_hp["fg"].setColor(*((0.35, 0.85, 0.35, 1) if pl.hp > 30 else (0.9, 0.25, 0.2, 1)))
        self._set_bar(self.bar_ar, pl.armor / 100.0)
        self._set_bar(self.bar_fl, pl.fluid / 100.0)
        self.money.setText("S %s" % format(pl.money, ",").replace(",", "."))
        self.weapon.setText(WEAPONS[pl.weapon]["name"])
        self.flasks.setText("Fiaschette: %d  (H)" % pl.flasks)
        st = g.police.stars
        blink = g.police.unseen_t > 2.0 and int(g.clock_t * 3) % 2 == 0
        for i, s in enumerate(self.stars):
            on = i < st
            s.setTexture(self.tex["star"] if on else self.tex["star_off"], 1)
            if on:
                s.setColorScale(*((1, 1, 1, 0.35) if blink else (1, 1, 1, 1)))
            else:
                s.setColorScale(1, 1, 1, 0.8)
        if g.police.flash_t > 0:
            sc = 0.034 * (1 + 0.3 * math.sin(g.clock_t * 20))
            for s in self.stars:
                s.setScale(sc)
        else:
            for s in self.stars:
                s.setScale(0.034)
        self.obj.setText(g.missions.objective)
        # sottotitoli
        if self.sub_t > 0:
            self.sub_t -= dt
            if self.sub_t <= 0:
                self.sub.setText("")
        if self.sub_t <= 0 and self.sub_queue:
            who, s, d = self.sub_queue.pop(0)
            col = SPEAKER_COL.get(who, (1, 1, 1, 1))
            self.sub.setText("%s:  %s" % (SPEAKER_NAME.get(who, who), s))
            self.sub.setFg(col)
            self.sub_t = d
        # grandi messaggi
        if self.big_t > 0:
            self.big_t -= dt
            a_ = clamp(self.big_t * 2, 0, 1)
            self.bigt.setAlphaScale(a_)
            self.bigs.setAlphaScale(a_)
            if self.big_t <= 0:
                self.bigt.setText("")
                self.bigs.setText("")
        # notifiche
        if self.toasts:
            self.toasts[0][2] -= dt
            if self.toasts[0][2] <= 0:
                self.toasts.pop(0)
        self.toast_np.setText("\n".join(t[0] for t in self.toasts))
        # suggerimenti
        self.hint.setText(g.interaction_hint())
        if pl.vehicle is not None:
            v = pl.vehicle
            extra = ("   quota %d m" % v.alt) if v.fly else ""
            self.speed.setText("%d km/h%s" % (abs(v.speed) * 3.6, extra))
        else:
            self.speed.setText("")
        show_cross = pl.weapon > 0 and (pl.aiming or g.camctl.first_person) and pl.vehicle is None
        if show_cross:
            self.cross.show()
        else:
            self.cross.hide()
        self.dmg_a = max(0.0, self.dmg_a - dt * 1.5)
        self.dmg.setColorScale(0.75, 0, 0, self.dmg_a * 0.8 + (0.35 if pl.hp < 25 else 0) * (0.6 + 0.4 * math.sin(g.clock_t * 6)))
        b = g.missions.boss
        if b is not None and not b.dead:
            self.boss_bar["root"].show()
            self.boss_lbl.show()
            self._set_bar(self.boss_bar, b.hp / b.MAX_HP)
        else:
            self.boss_bar["root"].hide()
            self.boss_lbl.hide()
        if self.credits_t > 0:
            self.credits_t -= dt
            k = 14.0 - self.credits_t
            self.cred.setText("RICK AND MORTY\nCITTA' INTERDIMENSIONALE\n\nGrazie per aver giocato!\n\n"
                              "Fan game non ufficiale\nRick and Morty (c) Adult Swim\n\nOra la citta' e' tua: gioco libero!")
            self.cred.setPos(0, -0.9 + k * 0.12)
            self.cred.setAlphaScale(clamp(self.credits_t, 0, 1))
        else:
            self.cred.setText("")

    def _map_pos(self, x, y, px, py, cam_h, vr, clampit=False, ret_inside=False):
        a = math.radians(-cam_h)
        dx, dy = x - px, y - py
        rx = dx * math.cos(a) - dy * math.sin(a)
        ry = dx * math.sin(a) + dy * math.cos(a)
        mx, my = rx / vr * self.mm_r, ry / vr * self.mm_r
        d = math.hypot(mx, my)
        inside = d < self.mm_r * 0.93
        if not inside and clampit:
            k = self.mm_r * 0.93 / d
            mx, my = mx * k, my * k
        if ret_inside:
            return mx, my, inside
        return mx, my

    def toggle_bigmap(self):
        g = self.g
        if self.bigmap is not None:
            self.bigmap.removeNode()
            self.bigmap = None
            return False
        root = g.aspect2d.attachNewNode("mappa_grande")
        cm = CardMaker("bg")
        cm.setFrame(-3, 3, -1, 1)
        bg = root.attachNewNode(cm.generate())
        bg.setColor(0, 0, 0, 0.75)
        bg.setTransparency(TransparencyAttrib.M_alpha)
        cm2 = CardMaker("mappa")
        cm2.setFrame(-0.9, 0.9, -0.9, 0.9)
        card = root.attachNewNode(cm2.generate())
        card.setTexture(self.map_tex)
        R = g.city.map_r

        def mp(x, y):
            return (x / R * 0.9, (y / R) * 0.9)
        px, py = g.player.pos2()
        x, y = mp(px, py)
        ar = OnscreenImage(self.tex["arrow"], parent=root, pos=(x, 0, y), scale=0.03)
        ar.setTransparency(TransparencyAttrib.M_alpha)
        ar.setR(-(g.player.vehicle.h if g.player.vehicle is not None else g.player.h))
        for (bx, by, col, _a) in g.missions.blips():
            x, y = mp(bx, by)
            b = OnscreenImage(self.tex["circle"], parent=root, pos=(x, 0, y), scale=0.022)
            b.setTransparency(TransparencyAttrib.M_alpha)
            b.setColorScale(*col)
        sx, sy, _h = g.city.spots["casa"]
        for name, (lx, ly) in (("Casa Smith", (sx, sy)), ("Blips and Chitz", g.city.spots["arcade"]),
                               ("Liceo", g.city.spots["scuola"]), ("Federazione", g.city.spots["polizia"]),
                               ("Portale", g.city.spots["cronenberg"])):
            x, y = mp(lx, ly)
            self._text(name, 0.035, (1, 1, 0.8, 1), parent=root, pos=(x, y + 0.03))
        self._text("MAPPA  -  M o Esc per chiudere", 0.05, (1, 1, 1, 1), parent=root, pos=(0, 0.93))
        self.bigmap = root
        return True


# =============================================================================
#  MENU
# =============================================================================
class Menu:
    def __init__(self, game):
        self.g = game
        self.root = game.aspect2d.attachNewNode("menu")
        self.items = []
        self.sel = 0
        self.mode = "main"
        self.font = game.hud.font
        cm = CardMaker("velo")
        cm.setFrame(-3, 3, -1, 1)
        self.veil = self.root.attachNewNode(cm.generate())
        self.veil.setColor(0, 0, 0, 0.45)
        self.veil.setTransparency(TransparencyAttrib.M_alpha)
        self.title = OnscreenText(text="RICK AND MORTY", scale=0.17, fg=(0.6, 0.92, 1.0, 1), shadow=(0.1, 0.25, 0.1, 1),
                                  shadowOffset=(0.012, 0.012), pos=(0, 0.6), parent=self.root, font=self.font, mayChange=True)
        self.subt = OnscreenText(text="CITTA' INTERDIMENSIONALE", scale=0.075, fg=(1.0, 0.88, 0.35, 1), shadow=(0, 0, 0, 1),
                                 pos=(0, 0.47), parent=self.root, font=self.font, mayChange=True)
        self.info = OnscreenText(text="", scale=0.042, fg=(0.85, 0.85, 0.9, 1), shadow=(0, 0, 0, 1), pos=(0, -0.92),
                                 parent=self.root, mayChange=True, font=game.hud.font_r, wordwrap=60)
        self.body = OnscreenText(text="", scale=0.045, fg=(1, 1, 1, 1), shadow=(0, 0, 0, 1), pos=(0, 0.3),
                                 parent=self.root, mayChange=True, font=game.hud.font_r, align=TextNode.ACenter)
        self.show("main")

    def entries(self):
        g = self.g
        s = g.save
        if self.mode == "main":
            e = []
            if s.get("mission", 0) > 0 or s.get("money", 0) > 250:
                e.append(("Continua", "continue"))
            e += [("Nuova partita", "new"), ("Opzioni", "options"), ("Comandi", "controls"), ("Esci", "quit")]
            return e
        if self.mode == "pause":
            return [("Riprendi", "resume"), ("Mappa", "map"), ("Opzioni", "options"), ("Comandi", "controls"),
                    ("Salva e torna al menu", "to_main"), ("Esci dal gioco", "quit")]
        if self.mode == "options":
            q = Environment.QUALITY[s.get("quality", 1)]["name"]
            cty = city_title(s.get("city", "losangeles")) if s.get("city", "losangeles") else "inventata"
            return [("Qualita' grafica: %s (al riavvio)" % q, "quality"),
                    ("Citta': %s (al riavvio)" % cty, "city"),
                    ("Sensibilita' mouse: %.1f" % s.get("sens", 1.0), "sens"),
                    ("Audio: %s" % ("ON" if s.get("audio", True) else "OFF"), "audio"),
                    ("Indietro", "back")]
        return [("Indietro", "back")]

    def show(self, mode):
        self.mode = mode
        self.prev = getattr(self, "prev", "main")
        self.root.show()
        for t in self.items:
            t.destroy()
        self.items = []
        ent = self.entries()
        self.sel = clamp(self.sel, 0, len(ent) - 1)
        y0 = 0.22 if mode != "controls" else -0.75
        self.item_y = []
        for i, (label, _a) in enumerate(ent):
            t = OnscreenText(text=label, scale=0.07, fg=(1, 1, 1, 1), shadow=(0, 0, 0, 1), pos=(0, y0 - i * 0.11),
                             parent=self.root, font=self.font, mayChange=True)
            self.items.append(t)
            self.item_y.append(y0 - i * 0.11)
        if mode == "controls":
            self.body.setText(
                "A PIEDI:  WASD muoviti  -  Mouse guarda  -  Shift scatto  -  Ctrl cammina  -  Spazio salta\n"
                "Click sinistro spara  -  Click destro mira  -  1 2 3 / rotellina arma  -  E pistola portale\n"
                "F entra/esci dai veicoli  -  H bevi dalla fiaschetta  -  V prima/terza persona\n\n"
                "IN AUTO:  W acceleratore  -  S freno/retro  -  A D sterzo  -  Spazio freno a mano\n"
                "Click sinistro spara  -  H clacson  -  R radio  -  Navicella: Spazio sali, Ctrl scendi\n\n"
                "M mappa  -  Esc pausa  -  F11 schermo intero\n\n"
                "Stelle: piu' crimini fai, piu' la Federazione Galattica ti insegue.\n"
                "Per seminarla allontanati e restane fuori dalla vista finche' le stelle spariscono.")
            self.body.setPos(0, 0.3)
        else:
            self.body.setText("")
        self.info.setText("Fan game non ufficiale - Rick and Morty (c) Adult Swim / Williams Street. "
                          "Tutto e' generato via codice in Python + Panda3D." if mode == "main" else "")
        self.refresh()

    def hide(self):
        self.root.hide()

    def refresh(self):
        for i, t in enumerate(self.items):
            on = i == self.sel
            t.setFg((0.6, 1.0, 0.4, 1) if on else (1, 1, 1, 1))
            t.setScale(0.08 if on else 0.068)

    def move(self, d):
        if not self.items:
            return
        self.sel = (self.sel + d) % len(self.items)
        self.g.sounds.play("click", 0.5)
        self.refresh()

    def hover(self, mx, my):
        for i, y in enumerate(self.item_y):
            if abs(my - (y + 0.022)) < 0.05 and abs(mx) < 0.75:
                if self.sel != i:
                    self.sel = i
                    self.refresh()
                return True
        return False

    def activate(self):
        ent = self.entries()
        if not ent:
            return
        action = ent[self.sel][1]
        self.g.sounds.play("click", 0.7)
        self.g.menu_action(action)


# =============================================================================
#  GIOCO
# =============================================================================


def ray_cylinder(o, d, cx, cy, r, z0, z1, maxd):
    fx, fy = o[0] - cx, o[1] - cy
    a = d[0] * d[0] + d[1] * d[1]
    if a < 1e-9:
        return None
    b = 2 * (fx * d[0] + fy * d[1])
    c = fx * fx + fy * fy - r * r
    disc = b * b - 4 * a * c
    if disc < 0:
        return None
    t = (-b - math.sqrt(disc)) / (2 * a)
    if t < 0 or t > maxd:
        return None
    z = o[2] + d[2] * t
    if z0 <= z <= z1:
        return t
    return None


class Game(ShowBase):
    def __init__(self):
        ShowBase.__init__(self)
        self.disableMouse()
        self.save = load_save()
        self.clock_t = 0.0
        self.state = "loading"
        self.setBackgroundColor(0.02, 0.02, 0.03, 1)
        self.setFrameRateMeter(False)
        load = OnscreenText(text="RICK AND MORTY\nCitta' Interdimensionale\n\nCostruzione del multiverso in corso...",
                            scale=0.08, fg=(0.6, 1.0, 0.5, 1), shadow=(0, 0, 0, 1), mayChange=True)
        for _ in range(3):
            self.graphicsEngine.renderFrame()
        q = clamp(self.save.get("quality", 1), 0, 2)
        self.env = Environment(self, q)
        self.env.update(0.0, Vec3(0, 0, 50), (0, 0), 0.0)
        self.dyn_root = self.env.root.attachNewNode("dinamici")
        self.city = None
        cname = self.save.get("city", "losangeles")
        path = find_city_data(cname) if cname else None
        if cname and path is None:
            avail = list_cities()
            if avail:
                cname = avail[0]
                path = find_city_data(cname)
        if path:
            def prog(f, msg=""):
                load.setText("RICK AND MORTY\nCitta' Interdimensionale\n\nCostruzione di %s (dati OpenStreetMap)\n"
                             "%s  %d%%" % (city_title(cname), msg, int(f * 100)))
                self.graphicsEngine.renderFrame()
            try:
                import hashlib
                with open(path, "rb") as f:
                    key = "%s_v%d_q%d_%s" % (cname, RealCity.CACHE_VER, q,
                                             hashlib.md5(f.read()).hexdigest()[:12])
                self.city = RealCity(self.env, lambda: load_city_data(path), q, prog, key)
            except Exception:  # noqa: BLE001
                import traceback
                traceback.print_exc()
                GROUND_FN[0] = None
                for name in ("citta", "insegna"):
                    for n in self.env.root.findAllMatches(name):
                        n.removeNode()
                self.city = None
        if self.city is None:
            self.city = City(self.env)
        else:
            self.env.set_fog(0.00045, 0.0022, 120.0, 0.93)
        self.factory = CarFactory(self.env)
        self.weapon_np = {k: NodePath(build_weapon_mesh(k).node("arma")) for k in (1, 2, 3)}
        self.fx = FX(self)
        self.sounds = SoundBank(self, self.save.get("audio", True))
        counts = [(10, 16), (16, 24), (22, 32)][q]
        self.traffic = TrafficManager(self, counts[0])
        self.peds = PedManager(self, counts[1])
        self.police = Police(self)
        self.player = Player(self)
        self.player.money = self.save.get("money", 250)
        self.player.unlocked = sorted(set(self.save.get("weapons", [0, 1])) | {0, 1})
        self.morty = Morty(self)
        gx, gy, gh = self.city.spots["garage_auto"]
        self.cruiser = self.traffic.add(Vehicle(self, "navicella", gx, gy, gh))
        self.cruiser.persistent = True
        self.pickups = Pickups(self)
        self.camctl = CameraCtl(self)
        self.hud = HUD(self)
        self.missions = Missions(self)
        self.menu = Menu(self)
        load.destroy()
        self.radio = 0
        self.dead_t = 0.0
        self.mouse_skip = 2
        self.env.hour = 9.5
        self.started = False
        self.keys = {}
        self._bind()
        self.taskMgr.add(self.loop, "ciclo")
        self.set_state("menu")

    # ------------------------------------------------------------------ input
    def _bind(self):
        for k in ("escape", "f", "e", "v", "h", "m", "r", "1", "2", "3", "wheel_up", "wheel_down", "mouse1", "enter",
                  "arrow_up", "arrow_down", "w", "s", "f11", "space"):
            self.accept(k, self.on_key, [k])

    def down(self, key):
        mw = self.mouseWatcherNode
        if mw is None:
            return False
        if key == "shift":
            return mw.isButtonDown(KeyboardButton.shift())
        if key == "control":
            return mw.isButtonDown(KeyboardButton.control())
        if key == "space":
            return mw.isButtonDown(KeyboardButton.space())
        if key == "up":
            return mw.isButtonDown(KeyboardButton.up())
        if key == "down":
            return mw.isButtonDown(KeyboardButton.down())
        if key == "left":
            return mw.isButtonDown(KeyboardButton.left())
        if key == "right":
            return mw.isButtonDown(KeyboardButton.right())
        if key == "mouse1":
            return mw.isButtonDown(MouseButton.one())
        if key == "mouse3":
            return mw.isButtonDown(MouseButton.three())
        if key == "alt":
            return mw.isButtonDown(KeyboardButton.alt())
        return mw.isButtonDown(KeyboardButton.asciiKey(key))

    def read_input(self):
        if self.keys.get("_override") is not None:
            return self.keys["_override"]
        d = self.down
        fwd = (1.0 if (d("w") or d("up")) else 0.0) - (1.0 if (d("s") or d("down")) else 0.0)
        side = (1.0 if (d("d") or d("right")) else 0.0) - (1.0 if (d("a") or d("left")) else 0.0)
        return dict(fwd=fwd, side=side, sprint=d("shift"), walk=d("control") or d("alt"), jump=d("space"),
                    down=d("control"), fire=d("mouse1"), aim=d("mouse3"))

    def on_key(self, k):
        st = self.state
        if k == "f11":
            self.toggle_fullscreen()
            return
        if st in ("menu", "pause"):
            if k in ("arrow_up", "w"):
                self.menu.move(-1)
            elif k in ("arrow_down", "s"):
                self.menu.move(1)
            elif k in ("enter", "space"):
                self.menu.activate()
            elif k == "mouse1":
                if self.mouseWatcherNode.hasMouse():
                    m = self.mouseWatcherNode.getMouse()
                    if self.menu.hover(m.getX() * self.getAspectRatio(), m.getY()):
                        self.menu.activate()
            elif k == "escape":
                if self.menu.mode in ("options", "controls"):
                    self.menu.show("pause" if self.started else "main")
                elif st == "pause":
                    self.set_state("play")
            return
        if st == "bigmap":
            if k in ("m", "escape"):
                self.hud.toggle_bigmap()
                self.set_state("play")
            return
        if st != "play":
            return
        pl = self.player
        if k == "escape":
            self.set_state("pause")
        elif k == "f":
            self.toggle_vehicle()
        elif k == "e":
            pl.portal_jump()
        elif k == "v":
            self.camctl.first_person = not self.camctl.first_person
        elif k == "h":
            if pl.vehicle is not None:
                self.sounds.play("horn", 0.9)
                for p in self.peds.near(pl.vehicle.x, pl.vehicle.y, 12):
                    if p.role == "ped" and random.random() < 0.4:
                        p.panic((pl.vehicle.x, pl.vehicle.y))
            else:
                pl.drink()
        elif k == "m":
            self.hud.toggle_bigmap()
            self.set_state("bigmap")
        elif k == "r":
            if pl.vehicle is not None:
                self.radio = (self.radio + 1) % 3
                self.hud.toast(["Radio spenta", "Radio Schwifty FM", "Radio Multiverso"][self.radio], (1, 0.9, 0.6, 1))
        elif k in ("1", "2", "3"):
            pl.set_weapon(int(k) - 1)
        elif k in ("wheel_up", "wheel_down"):
            u = pl.unlocked
            i = u.index(pl.weapon) if pl.weapon in u else 0
            i = (i + (1 if k == "wheel_up" else -1)) % len(u)
            pl.set_weapon(u[i])

    def toggle_fullscreen(self):
        wp = WindowProperties()
        full = not self.win.getProperties().getFullscreen()
        wp.setFullscreen(full)
        if full:
            wp.setSize(self.pipe.getDisplayWidth(), self.pipe.getDisplayHeight())
        else:
            wp.setSize(1280, 720)
        self.win.requestProperties(wp)

    def set_cursor(self, hidden):
        if OFFSCREEN:
            return
        wp = WindowProperties()
        wp.setCursorHidden(hidden)
        wp.setMouseMode(WindowProperties.M_confined if hidden else WindowProperties.M_absolute)
        self.win.requestProperties(wp)
        self.mouse_skip = 2

    def mouse_look(self):
        if OFFSCREEN or self.win is None:
            return
        props = self.win.getProperties()
        if not props.getForeground():
            return
        cx, cy = props.getXSize() // 2, props.getYSize() // 2
        ptr = self.win.getPointer(0)
        dx, dy = ptr.getX() - cx, ptr.getY() - cy
        self.win.movePointer(0, cx, cy)
        if self.mouse_skip > 0:
            self.mouse_skip -= 1
            return
        self.camctl.mouse(dx, dy, 0.11 * self.save.get("sens", 1.0))

    # ------------------------------------------------------------------ stati
    def set_state(self, s):
        prev = self.state
        self.state = s
        if s == "menu":
            self.menu.sel = 0
            self.menu.show("main")
            self.hud.set_visible(False)
            self.set_cursor(False)
            self.sounds.stop_loops()
            self.sounds.set_music("menu", 0.5)
        elif s == "pause":
            self.menu.sel = 0
            self.menu.show("pause")
            self.hud.set_visible(False)
            self.hud.cred.hide()
            self.set_cursor(False)
            self.sounds.stop_loops()
        elif s == "bigmap":
            self.set_cursor(False)
        elif s == "play":
            self.menu.hide()
            self.hud.set_visible(True)
            self.hud.cred.show()
            self.set_cursor(True)
            if prev == "menu":
                self.sounds.set_music(None)

    def menu_action(self, a):
        s = self.save
        if a == "continue":
            self.started = True
            self.set_state("play")
        elif a == "new":
            s.update(mission=0, money=250, weapons=[0, 1])
            write_save(s)
            self.reset_game()
            self.started = True
            self.set_state("play")
        elif a in ("options", "controls"):
            self.menu.prev = self.menu.mode
            self.menu.sel = 0
            self.menu.show(a)
        elif a == "back":
            self.menu.sel = 0
            self.menu.show("pause" if self.started else "main")
        elif a == "quit":
            self.save_game()
            self.userExit()
        elif a == "resume":
            self.set_state("play")
        elif a == "map":
            self.hud.toggle_bigmap()
            self.menu.hide()
            self.state = "bigmap"
        elif a == "to_main":
            self.save_game()
            self.started = False
            self.set_state("menu")
        elif a == "quality":
            s["quality"] = (s.get("quality", 1) + 1) % 3
            write_save(s)
            self.menu.show("options")
        elif a == "city":
            opts = list_cities() + [""]
            cur = s.get("city", "losangeles")
            s["city"] = opts[(opts.index(cur) + 1) % len(opts)] if cur in opts else opts[0]
            write_save(s)
            self.menu.show("options")
        elif a == "sens":
            v = s.get("sens", 1.0) + 0.25
            s["sens"] = 0.5 if v > 2.51 else v
            write_save(s)
            self.menu.show("options")
        elif a == "audio":
            s["audio"] = not s.get("audio", True)
            self.sounds.set_enabled(s["audio"])
            write_save(s)
            self.menu.show("options")

    def reset_game(self):
        pl = self.player
        if pl.vehicle is not None:
            self.exit_vehicle(force=True)
        self.missions.fail("")
        self.missions.idx = 0
        self.police.clear()
        pl.money = 250
        pl.unlocked = [0, 1]
        pl.set_weapon(1)
        pl.hp, pl.armor, pl.flasks = 100.0, 0.0, 2
        sx, sy, sh = self.city.spots["casa"]
        pl.place(sx, sy, sh)
        self.camctl.yaw = sh
        gx, gy, gh = self.city.spots["garage_auto"]
        c = self.cruiser
        c.x, c.y, c.h, c.alt, c.vx, c.vy, c.vz = gx, gy, gh, 0.0, 0.0, 0.0, 0.0
        c.hp, c.wrecked = 100.0, False
        c.np.setPos(gx, gy, c.z)
        self.morty.place(sx + 1.5, sy + 1.0)
        self.env.hour = 9.5

    def save_game(self):
        s = self.save
        s["mission"] = self.missions.idx
        s["money"] = int(self.player.money)
        s["weapons"] = list(self.player.unlocked)
        write_save(s)

    # ------------------------------------------------------------------ veicoli
    def nearest_vehicle(self, r=3.6):
        pl = self.player
        best, bd = None, r
        for v in self.traffic.near(pl.x, pl.y, 8):
            if v.dead or v.wrecked or v is pl.vehicle:
                continue
            lx, ly = v.local(pl.x, pl.y)
            d = max(0.0, abs(lx) - v.W / 2) + max(0.0, abs(ly) - v.L / 2)
            if v.fly and abs(pl.z - v.z - v.alt) > 2.5:
                continue
            if d < bd:
                best, bd = v, d
        return best

    def toggle_vehicle(self):
        pl = self.player
        if pl.vehicle is not None:
            self.exit_vehicle()
            return
        v = self.nearest_vehicle()
        if v is None:
            return
        if v.driver in ("ai", "stopped"):
            cop_near = any(p.role == "cop" and not p.dead for p in self.peds.near(pl.x, pl.y, 40))
            self.peds.eject_driver(v, flee=True)
            if cop_near or random.random() < 0.25:
                self.police.crime("furto", (v.x, v.y))
        elif v.driver == "cop":
            self.police.crime("furto", (v.x, v.y))
            for k in range(getattr(v, "cops_inside", 0)):
                x, y = v.seat_pos(1)
                self.peds.spawn_cop(x, y, v.h)
            v.cops_inside = 0
            if v in self.police.cars:
                self.police.cars.remove(v)
            v.siren_on = False
        v.driver = "player"
        v.ai = None
        v.persistent = True
        pl.vehicle = v
        r = pl.rig.root
        r.reparentTo(v.body)
        sx, sy, sz = SEAT.get(v.kind, (-0.38, 0, 0.02))
        r.setPos(sx, sy, sz)
        r.setHpr(0, 0, 0)
        pl.rig.animate(0.016, 0, "sit")
        self.sounds.play("door", 0.8)
        self.camctl.yaw = v.h
        self.camctl.idle_t = 5.0
        if v is self.cruiser and self.missions.idx == 0 and self.missions.active:
            pass

    def exit_vehicle(self, force=False):
        pl = self.player
        v = pl.vehicle
        if v is None:
            return
        if not force and abs(v.speed) > 12 and not v.fly:
            self.hud.toast("Rallenta per scendere!", (1, 0.8, 0.5, 1))
            return
        spot = None
        for side in (-1, 1):
            x, y = v.seat_pos(side)
            nx, ny, hit, _n = self.city.world.push_circle(x, y, v.z + v.alt, 0.35, 1.8)
            if not hit:
                spot = (nx, ny)
                break
        if spot is None:
            fx, fy = v.fwd
            spot = (v.x - fx * (v.L / 2 + 1.0), v.y - fy * (v.L / 2 + 1.0))
        v.driver = None
        pl.vehicle = None
        r = pl.rig.root
        r.reparentTo(self.dyn_root)
        r.setHpr(0, 0, 0)
        pl.x, pl.y = spot
        pl.z = v.z + v.alt * 0 if not v.fly else v.z
        pl.vz = 0.0
        pl.on_ground = False
        pl.h = v.h
        pl.rig.body.setZ(0)
        for hp in pl.rig.hips:
            hp.setP(0)
        for kn in pl.rig.knees:
            kn.setP(0)
        self.sounds.play("door", 0.8)
        self.sounds.loop("engine", 0)
        self.sounds.loop("skid", 0)
        self.camctl.yaw = v.h

    def interaction_hint(self):
        pl = self.player
        if self.state != "play":
            return ""
        if pl.vehicle is not None:
            if pl.vehicle.fly:
                return "F esci   -   Spazio sali / Ctrl scendi   -   R radio"
            return ""
        v = self.nearest_vehicle()
        if v is not None:
            return "F  Ruba il veicolo" if v.driver in ("ai", "cop", "stopped") else "F  Sali sul veicolo"
        return ""

    # ------------------------------------------------------------------ combattimento
    def raycast_all(self, o, d, maxd, ignore_player=True):
        best_t, best_obj, best_n = maxd, None, None
        h = self.city.world.raycast(o[0], o[1], o[2], d[0], d[1], d[2], maxd)
        if h is not None:
            best_t, best_n = h[0], h[1]
        pv = self.player.vehicle
        for v in self.traffic.cars:
            if v is pv or (v.dead and v.np.isEmpty()):
                continue
            if abs(v.x - o[0]) > best_t + 6 or abs(v.y - o[1]) > best_t + 6:
                continue
            t = v.ray_hit(o, d, best_t)
            if t is not None and t < best_t:
                best_t, best_obj, best_n = t, v, (0, 0, 1)
        for p in self.peds.peds:
            if abs(p.x - o[0]) > best_t + 2 or abs(p.y - o[1]) > best_t + 2:
                continue
            hgt = 0.45 if p.dead else p.rig.height
            rad = 0.42 if p.role != "monster" else 0.6
            t = ray_cylinder(o, d, p.x, p.y, rad, p.z, p.z + hgt, best_t)
            if t is not None and t < best_t:
                best_t, best_obj, best_n = t, p, (0, 0, 1)
        for dr in self.police.drones:
            t = dr.ray_hit(o, d, best_t)
            if t is not None and t < best_t:
                best_t, best_obj, best_n = t, dr, (0, 0, 1)
        b = self.missions.boss
        if b is not None and not b.dead:
            t = b.ray_hit(o, d, best_t)
            if t is not None and t < best_t:
                best_t, best_obj, best_n = t, b, (0, 0, 1)
        if best_obj is None and best_n is None:
            return None
        return best_t, best_obj, best_n

    def apply_hit(self, obj, dmg, point, dirn, by_player=True):
        if obj is None:
            return
        if isinstance(obj, Ped):
            was = obj.dead
            src = (point[0] - dirn[0] * 5, point[1] - dirn[1] * 5)
            obj.hurt(dmg, src, by_player)
            if obj.dead and not was:
                obj.vx, obj.vy, obj.vz = dirn[0] * 3, dirn[1] * 3, 2.0
                obj.air_t = 0.5
            self.sounds.play("hit", 0.5, pos=point)
        elif isinstance(obj, Vehicle):
            obj.damage(dmg * 0.45, "player" if by_player else None)
            self.fx.sparks(point, 5)
        elif isinstance(obj, (Drone, Cromulon3D)):
            obj.hurt(dmg)

    def enemy_shot(self, shooter, origin, target, dmg):
        pl = self.player
        d = math.sqrt((target[0] - origin[0]) ** 2 + (target[1] - origin[1]) ** 2 + (target[2] - origin[2]) ** 2)
        sp = math.hypot(pl.vx, pl.vy) if pl.vehicle is None else abs(pl.vehicle.speed)
        acc = clamp(0.72 - d / 110 - sp * 0.025, 0.1, 0.75)
        hit = random.random() < acc
        if hit:
            end = (target[0] + random.uniform(-0.2, 0.2), target[1] + random.uniform(-0.2, 0.2), target[2])
        else:
            end = (target[0] + random.uniform(-2.5, 2.5), target[1] + random.uniform(-2.5, 2.5),
                   target[2] + random.uniform(-0.8, 1.2))
        dx, dy, dz = end[0] - origin[0], end[1] - origin[1], end[2] - origin[2]
        L = math.sqrt(dx * dx + dy * dy + dz * dz) or 1
        blk = self.city.world.raycast(origin[0], origin[1], origin[2], dx / L, dy / L, dz / L, L - 0.5)
        if blk is not None:
            t = blk[0]
            end = (origin[0] + dx / L * t, origin[1] + dy / L * t, origin[2] + dz / L * t)
            hit = False
        self.fx.laser(origin, end, (1.0, 0.18, 0.12), 0.03)
        self.fx.muzzle(origin, (1.0, 0.3, 0.2, 1.0))
        self.sounds.play("elaser", 0.6, pos=origin)
        if hit:
            if pl.vehicle is not None:
                pl.vehicle.damage(dmg * 0.6)
                self.fx.sparks(end, 4)
            else:
                pl.hurt(dmg, origin)
        else:
            self.fx.impact(end, (1.0, 0.3, 0.2, 1.0))

    def blast(self, p, radius, dmg, source=None):
        for q in self.peds.near(p[0], p[1], radius + 1):
            d = dist2(q.x, q.y, p[0], p[1])
            if d < radius and not q.dead:
                k = 1 - d / radius
                dx, dy = q.x - p[0], q.y - p[1]
                l = math.hypot(dx, dy) or 1
                q.hurt(dmg * k, (p[0], p[1]), source is not None and not isinstance(source, Cromulon3D),
                       (dx / l * 9 * k, dy / l * 9 * k, 5 + 5 * k))
        for v in self.traffic.near(p[0], p[1], radius + 3):
            if v is source or v.dead:
                continue
            d = dist2(v.x, v.y, p[0], p[1])
            if d < radius + 2:
                k = 1 - d / (radius + 2)
                v.damage(dmg * k * 0.8)
                dx, dy = v.x - p[0], v.y - p[1]
                l = math.hypot(dx, dy) or 1
                v.vx += dx / l * 8 * k
                v.vy += dy / l * 8 * k
                if v.driver == "ai":
                    v.disturb()
        px, py, pz = self.player.pos3()
        d = math.sqrt((px - p[0]) ** 2 + (py - p[1]) ** 2 + (pz + 1 - p[2]) ** 2)
        if d < radius:
            self.player.hurt(dmg * (1 - d / radius), (p[0], p[1]))
        self.cam_shake(clamp(1.2 - d / 40, 0.1, 1.0))

    def cam_shake(self, a):
        self.camctl.shake = max(self.camctl.shake, a)

    def subtitle(self, who, s, dur=3.0):
        self.hud.subtitle(who, s, dur)

    def say_world(self, ped, s):
        px, py = self.player.pos2()
        if dist2(px, py, ped.x, ped.y) < 18 and not self.hud.sub_busy():
            self.subtitle("passante", s, 1.8)

    def listener_pos(self):
        p = self.camera.getPos(self.render)
        return (p[0], p[1], p[2])

    def morty_follow_portal(self):
        m = self.morty
        if m.in_car is None and dist2(m.x, m.y, self.player.x, self.player.y) > 6:
            self.taskMgr.doMethodLater(0.4, lambda t: (m.teleport_near(self.player.x, self.player.y), t.done)[1], "morty_portale")

    # ------------------------------------------------------------------ morte
    def on_player_dead(self):
        if self.state != "play":
            return
        pl = self.player
        if pl.vehicle is not None:
            self.exit_vehicle(force=True)
        pl.dead = True
        self.state = "dead"
        self.dead_t = 0.0
        self.hud.big("SEI MORTO", (0.9, 0.15, 0.1, 1), 4.0,
                     sub="Missione fallita" if self.missions.active else "Rick: \"Nel multiverso c'e' un altro me che ce l'ha fatta.\"")
        if self.missions.active:
            self.missions.active = False
            self.missions._cleanup()
        self.sounds.play("wasted", 1.0)
        self.sounds.stop_loops()
        self.env.set_tint((0.75, 0.7, 0.7))
        self.set_cursor(False)

    def respawn(self):
        pl = self.player
        pl.dead = False
        pl.hp, pl.armor = 100.0, 0.0
        lost = int(pl.money * 0.1)
        pl.money = max(0, pl.money - lost)
        self.police.clear()
        for p in self.peds.peds:
            if p.role == "cop":
                p.remove()
        self.peds.peds = [p for p in self.peds.peds if p.role != "cop"]
        self.env.set_tint((1, 1, 1))
        sx, sy, sh = self.city.spots["casa"]
        pl.place(sx, sy, sh)
        pl.rig.dead_t = 0
        self.camctl.yaw = sh
        self.morty.teleport_near(sx, sy)
        self.state = "play"
        self.set_cursor(True)
        self.hud.toast("Rick si e' clonato nel garage. -%d Schmeckles" % lost, (1, 0.8, 0.6, 1), 4.0)

    # ------------------------------------------------------------------ ciclo principale
    def update_world(self, dt, inp):
        pl = self.player
        self.env.hour = (self.env.hour + dt * 24.0 / (20 * 60)) % 24.0
        if not pl.dead:
            pl.update(dt, inp)
        else:
            pl.rig.animate(dt, 0, "dead")
        self.morty.update(dt)
        self.traffic.update(dt)
        self.peds.update(dt)
        self.police.update(dt)
        self.pickups.update(dt)
        self.missions.update(dt)
        # audio d'ambiente
        if pl.vehicle is None:
            self.sounds.loop("engine", 0)
            self.sounds.loop("skid", 0)
        self.sounds.loop("ambient", 0.3)
        siren = 0.0
        for c in self.police.cars:
            if c.siren_on and not c.dead:
                d = dist2(c.x, c.y, *pl.pos2())
                siren = max(siren, clamp(1 - d / 140, 0, 1) ** 1.5)
        self.sounds.loop("siren", siren * 0.55)
        want = None
        if pl.vehicle is not None and self.radio:
            want = "radio1" if self.radio == 1 else "radio2"
        self.sounds.set_music(want, 0.42)

    def gather_lights(self):
        lights = self.fx.lights()
        cp = self.camera.getPos(self.render)
        for c in self.police.cars:
            if c.siren_on and not c.dead and dist2(c.x, c.y, cp[0], cp[1]) < 70:
                red = int(self.clock_t * 6) % 2 == 0
                lights.append((c.x, c.y, c.z + 2.0, 14.0, 3.5 if red else 0.4, 0.3, 0.4 if red else 3.5))
        n = self.env.night
        if n > 0.12 and len(lights) < 8:
            for d, lx, ly, lz in self.city.nearest_lamps(cp[0], cp[1], 8 - len(lights), 140):
                lights.append((lx, ly, lz, 20.0, 4.6 * n, 3.4 * n, 1.9 * n))
        return lights[:8]

    def loop(self, task):
        dt = min(ClockObject.getGlobalClock().getDt(), 1 / 20.0)
        self.clock_t += dt
        st = self.state
        if st == "menu":
            a = self.clock_t * 0.05
            if isinstance(self.city, RealCity):
                self.camera.setPos(math.cos(a) * 820, 120 + math.sin(a) * 820, 230)
                self.camera.lookAt(0, 120, 95)
            else:
                self.camera.setPos(math.cos(a) * 230, math.sin(a) * 230, 95)
                self.camera.lookAt(0, 0, 25)
            self.camLens.setFov(60)
            self.traffic.update(dt)
            self.peds.update(dt)
            self.menu_hover()
        elif st == "play":
            self.mouse_look()
            self.update_world(dt, self.read_input())
            self.camctl.update(dt)
            self.hud.update(dt)
        elif st == "dead":
            self.dead_t += dt
            self.update_world(dt, dict(fwd=0, side=0, sprint=False, walk=False, jump=False, down=False, fire=False, aim=False))
            self.camctl.yaw += dt * 12
            self.camctl.update(dt)
            self.hud.update(dt)
            if self.dead_t > 5.0:
                self.respawn()
        elif st == "pause":
            self.menu_hover()
        elif st == "bigmap":
            pass
        self.fx.update(dt, self.camera)
        self.city.update(dt, self.clock_t)
        pl = self.player
        spot = None
        if pl.vehicle is not None and self.env.night > 0.2 and not pl.vehicle.fly:
            v = pl.vehicle
            fx, fy = v.fwd
            spot = ((v.x + fx * (v.L / 2 + 0.2), v.y + fy * (v.L / 2 + 0.2), v.z + 0.8), (fx * 0.97, fy * 0.97, -0.22))
        focus = pl.pos2() if st != "menu" else (0, 120 if isinstance(self.city, RealCity) else 0)
        self.env.update(dt, self.camera.getPos(self.render), focus, self.clock_t, self.gather_lights(), spot)
        return task.cont

    def menu_hover(self):
        if self.mouseWatcherNode is not None and self.mouseWatcherNode.hasMouse():
            m = self.mouseWatcherNode.getMouse()
            pos = (round(m.getX(), 4), round(m.getY(), 4))
            if pos != getattr(self, "_last_mouse", None):
                if getattr(self, "_last_mouse", None) is not None:
                    self.menu.hover(m.getX() * self.getAspectRatio(), m.getY())
                self._last_mouse = pos


def main():
    try:
        game = Game()
        game.run()
    except SystemExit:
        raise
    except Exception:
        import traceback
        msg = traceback.format_exc()
        try:
            with open(os.path.join(os.path.expanduser("~"), "rick_morty_3d_errore.txt"), "w", encoding="utf-8") as f:
                f.write(msg)
        except Exception:
            pass
        print(msg)
        raise


if __name__ == "__main__":
    main()
