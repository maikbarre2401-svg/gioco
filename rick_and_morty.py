#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
  RICK AND MORTY - AVVENTURA INTERDIMENSIONALE
  Fan game NON ufficiale scritto da zero in Python + pygame.
===============================================================================
Tutta la grafica (personaggi, mostri, sfondi, portali) e tutto l'audio
(effetti e musiche) sono generati via codice: non serve nessun file esterno.

Avvio:
    pip install pygame
    python rick_and_morty.py

Comandi:
    A / D  oppure  Frecce ............ muoviti
    W / Spazio / Freccia su .......... salta (di nuovo in aria = doppio salto)
    S / Giu + Salto .................. scendi da una piattaforma sottile
    J / Z  oppure  Click sinistro .... spara (mira automatica / mira col mouse)
    K / X / Shift  o  Click destro ... pistola portale: teletrasporto
    H / Q ............................ bevi dalla fiaschetta (cura)  *burp*
    E ................................ parla con i personaggi
    Esc / P .......................... pausa
    M ................................ audio on/off
    F11 .............................. schermo intero

Rick and Morty e tutti i personaggi sono (c) Adult Swim / Williams Street.
Questo e' un progetto amatoriale, gratuito e senza scopo di lucro.
"""

import array
import json
import math
import os
import random
import sys
import threading

try:
    import pygame
except ImportError:  # pragma: no cover
    print("Questo gioco richiede pygame.  Installalo con:   pip install pygame")
    input("Premi Invio per uscire...")
    sys.exit(1)

# =============================================================================
#  COSTANTI
# =============================================================================
W, H = 1280, 720
TILE = 48
ROWS = H // TILE
FPS = 60
SS = 2  # supersampling degli sprite (disegnati a 2x e poi ridotti = bordi lisci)
GAME_TITLE = "Rick and Morty - Avventura Interdimensionale"

GRAVITY = 2300.0
MAX_FALL = 1100.0
RUN_SPEED = 340.0
ACCEL_GROUND = 3200.0
ACCEL_AIR = 1900.0
FRICTION = 2800.0
JUMP_V = 900.0
DJUMP_V = 790.0
COYOTE = 0.10
JUMP_BUFFER = 0.13
PORTAL_COST = 34.0
PORTAL_REGEN = 9.0
PORTAL_DIST = 4.3 * TILE

OUTLINE = (24, 20, 30)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
PORTAL_GREEN = (110, 240, 60)

SAVE_PATH = os.path.join(os.path.expanduser("~"), ".rick_morty_avventura_save.json")


# =============================================================================
#  UTILITA'
# =============================================================================
def clamp(v, a, b):
    return a if v < a else b if v > b else v


def lerp(a, b, t):
    return a + (b - a) * t


def approach(v, target, delta):
    if v < target:
        return min(v + delta, target)
    return max(v - delta, target)


def lerp_col(c1, c2, t):
    t = clamp(t, 0.0, 1.0)
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def shade(c, f):
    return tuple(clamp(int(x * f), 0, 255) for x in c[:3])


def sign(x):
    return 1 if x > 0 else -1 if x < 0 else 0


def dist(ax, ay, bx, by):
    return math.hypot(bx - ax, by - ay)


def seg_point_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return math.hypot(px - ax, py - ay)
    t = clamp(((px - ax) * dx + (py - ay) * dy) / L2, 0.0, 1.0)
    return math.hypot(px - (ax + dx * t), py - (ay + dy * t))


def load_save():
    data = {}
    try:
        with open(SAVE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            data = {}
    except Exception:
        data = {}
    data.setdefault("unlocked", 1)
    data.setdefault("seeds", {})
    data.setdefault("best", {})
    data.setdefault("intro_seen", False)
    data.setdefault("audio", True)
    data.setdefault("completed", False)
    return data


def write_save(data):
    try:
        with open(SAVE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=1)
    except Exception:
        pass


# =============================================================================
#  FONT E TESTO
# =============================================================================
_FONT_CACHE = {}
FONT_NAMES = {
    "title": ["impact", "arialblack", "haettenschweiler", "dejavusanscondensed", "dejavusans", "freesansbold"],
    "ui": ["verdana", "trebuchetms", "segoeui", "arial", "dejavusans", "liberationsans", "freesans"],
    "comic": ["comicsansms", "comicneue", "chalkboardse", "verdana", "dejavusans"],
}


def font(size, kind="ui", bold=False):
    key = (size, kind, bold)
    f = _FONT_CACHE.get(key)
    if f is not None:
        return f
    for name in FONT_NAMES.get(kind, FONT_NAMES["ui"]):
        try:
            path = pygame.font.match_font(name, bold=bold)
        except Exception:
            path = None
        if path:
            try:
                f = pygame.font.Font(path, size)
                break
            except Exception:
                f = None
    if f is None:
        f = pygame.font.Font(None, int(size * 1.35))
        f.set_bold(bold)
    _FONT_CACHE[key] = f
    return f


_TEXT_CACHE = {}


def text(s, size, color=WHITE, kind="ui", bold=False, outline=None, ow=2):
    key = (s, size, color, kind, bold, outline, ow)
    surf = _TEXT_CACHE.get(key)
    if surf is not None:
        return surf
    if len(_TEXT_CACHE) > 900:
        _TEXT_CACHE.clear()
    f = font(size, kind, bold)
    base = f.render(s, True, color)
    if outline:
        w, h = base.get_size()
        surf = pygame.Surface((w + ow * 2, h + ow * 2), pygame.SRCALPHA)
        o = f.render(s, True, outline)
        for dx in range(-ow, ow + 1):
            for dy in range(-ow, ow + 1):
                if dx * dx + dy * dy <= ow * ow + ow:
                    surf.blit(o, (dx + ow, dy + ow))
        surf.blit(base, (ow, ow))
    else:
        surf = base
    _TEXT_CACHE[key] = surf
    return surf


def blit_text(surf, s, size, pos, color=WHITE, anchor="topleft", **kw):
    t = text(s, size, color, **kw)
    r = t.get_rect(**{anchor: pos})
    surf.blit(t, r)
    return r


def wrap_text(s, size, maxw, kind="ui", bold=False):
    f = font(size, kind, bold)
    lines, cur = [], ""
    for w in s.split(" "):
        test = (cur + " " + w).strip()
        if f.size(test)[0] <= maxw:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


# =============================================================================
#  LUCI ED EFFETTI LUMINOSI
# =============================================================================
_GLOW = {}


def glow_surf(radius, color, strength=1.0):
    radius = max(4, int(radius) // 4 * 4)
    key = (radius, color, strength)
    g = _GLOW.get(key)
    if g is not None:
        return g
    g = pygame.Surface((radius * 2, radius * 2))
    g.fill(BLACK)
    steps = max(8, radius // 2)
    for i in range(steps, 0, -1):
        r = radius * i / steps
        k = (1.0 - i / steps) ** 1.7 * strength
        col = tuple(clamp(int(c * k), 0, 255) for c in color)
        pygame.draw.circle(g, col, (radius, radius), max(1, int(r)))
    _GLOW[key] = g
    return g


def draw_glow(surf, x, y, radius, color, strength=1.0):
    g = glow_surf(radius, color, strength)
    r = g.get_width() // 2
    surf.blit(g, (int(x) - r, int(y) - r), special_flags=pygame.BLEND_RGB_ADD)


_LIGHT = {}


def light_surf(radius, power):
    radius = max(8, int(radius) // 8 * 8)
    key = (radius, power)
    s = _LIGHT.get(key)
    if s is not None:
        return s
    s = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
    s.fill((0, 0, 0, 0))
    steps = max(10, radius // 3)
    for i in range(steps, 0, -1):
        r = radius * i / steps
        a = int(power * (1.0 - i / steps) ** 1.2)
        pygame.draw.circle(s, (0, 0, 0, clamp(a, 0, 255)), (radius, radius), max(1, int(r)))
    _LIGHT[key] = s
    return s


def make_vignette(strength=170, inner=0.55):
    v = pygame.Surface((W, H), pygame.SRCALPHA)
    small = pygame.Surface((160, 90), pygame.SRCALPHA)
    for y in range(90):
        for x in range(160):
            dx = (x - 80) / 80.0
            dy = (y - 45) / 45.0
            d = math.sqrt(dx * dx * 0.9 + dy * dy * 1.1)
            k = clamp((d - inner) / (1.25 - inner), 0.0, 1.0)
            small.set_at((x, y), (0, 0, 0, int(strength * k * k)))
    v.blit(pygame.transform.smoothscale(small, (W, H)), (0, 0))
    return v


def vertical_gradient(w, h, stops):
    """stops: lista di (posizione 0..1, colore)"""
    s = pygame.Surface((w, h))
    for y in range(h):
        t = y / max(1, h - 1)
        for i in range(len(stops) - 1):
            p0, c0 = stops[i]
            p1, c1 = stops[i + 1]
            if p0 <= t <= p1:
                col = lerp_col(c0, c1, (t - p0) / max(1e-6, p1 - p0))
                break
        else:
            col = stops[-1][1]
        pygame.draw.line(s, col, (0, y), (w, y))
    return s


# =============================================================================
#  INPUT
# =============================================================================
BINDINGS = {
    "left": (pygame.K_a, pygame.K_LEFT),
    "right": (pygame.K_d, pygame.K_RIGHT),
    "up": (pygame.K_w, pygame.K_UP),
    "down": (pygame.K_s, pygame.K_DOWN),
    "jump": (pygame.K_SPACE, pygame.K_w, pygame.K_UP),
    "shoot": (pygame.K_j, pygame.K_z, pygame.K_LCTRL, pygame.K_RCTRL),
    "portal": (pygame.K_k, pygame.K_x, pygame.K_LSHIFT, pygame.K_RSHIFT),
    "flask": (pygame.K_h, pygame.K_q),
    "interact": (pygame.K_e, pygame.K_f),
    "pause": (pygame.K_ESCAPE, pygame.K_p),
    "confirm": (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE, pygame.K_j),
    "back": (pygame.K_ESCAPE, pygame.K_BACKSPACE),
    "menu_up": (pygame.K_w, pygame.K_UP),
    "menu_down": (pygame.K_s, pygame.K_DOWN),
}


class Input:
    def __init__(self):
        self.just = set()
        self.mjust = set()
        self.keys = None
        self.mouse = (0, 0)
        self.mbuttons = (False, False, False)
        self.mouse_aim = False

    def begin(self):
        self.just.clear()
        self.mjust.clear()

    def feed(self, e):
        if e.type == pygame.KEYDOWN:
            self.just.add(e.key)
        elif e.type == pygame.MOUSEBUTTONDOWN:
            self.mjust.add(e.button)
            self.mouse_aim = True

    def end(self):
        self.keys = pygame.key.get_pressed()
        self.mouse = pygame.mouse.get_pos()
        self.mbuttons = pygame.mouse.get_pressed()

    def held(self, action):
        k = self.keys
        if k is None:
            return False
        return any(k[c] for c in BINDINGS[action])

    def hit(self, action):
        return any(c in self.just for c in BINDINGS[action])

    def mheld(self, b):
        return bool(self.mbuttons[b - 1])

    def mhit(self, b):
        return b in self.mjust

    def any_confirm(self):
        return self.hit("confirm") or self.mhit(1)


# =============================================================================
#  AUDIO SINTETIZZATO  (nessun file: ogni suono e' calcolato al volo)
# =============================================================================
BASE_RATE = 22050
SINE_TAB = [math.sin(2 * math.pi * i / 1024) for i in range(1024)]


def synth(dur, f0, f1=None, wave="sq", decay=1.0, attack=0.004, noise=0.0,
          vib=0.0, vib_depth=0.04, curve=1.0, rate=BASE_RATE):
    n = int(dur * rate)
    out = [0.0] * n
    ph = 0.0
    a = max(1, int(attack * rate))
    rnd = random.random
    tab = SINE_TAB
    for i in range(n):
        t = i / n
        f = f0 if f1 is None else f0 + (f1 - f0) * (t ** curve)
        if vib:
            f *= 1.0 + vib_depth * tab[int(vib * i / rate * 1024) & 1023]
        ph += f / rate
        p = ph - int(ph)
        if wave == "sin":
            v = tab[int(p * 1024) & 1023]
        elif wave == "sq":
            v = 1.0 if p < 0.5 else -1.0
        elif wave == "pulse":
            v = 1.0 if p < 0.25 else -1.0
        elif wave == "saw":
            v = 2.0 * p - 1.0
        else:
            v = 4.0 * abs(p - 0.5) - 1.0
        if noise:
            v = v * (1.0 - noise) + (rnd() * 2.0 - 1.0) * noise
        env = (1.0 - t) ** decay
        if i < a:
            env *= i / a
        out[i] = v * env
    return out


def lowpass(buf, k):
    y = 0.0
    for i in range(len(buf)):
        y += (buf[i] - y) * k
        buf[i] = y
    return buf


def mix_into(dst, src, offset=0, gain=1.0):
    n = len(dst)
    for i, v in enumerate(src):
        j = offset + i
        if j >= n:
            break
        dst[j] += v * gain
    return dst


def silence(dur, rate=BASE_RATE):
    return [0.0] * int(dur * rate)


def midi_hz(n):
    return 440.0 * 2.0 ** ((n - 69) / 12.0)


CHORD_TONES = {"M": (0, 4, 7), "m": (0, 3, 7), "5": (0, 7, 12), "7": (0, 4, 7, 10), "m7": (0, 3, 7, 10)}

# Ogni brano: bpm, progressione (nota MIDI radice, tipo), stile, scala per la melodia
SONGS = {
    "title": dict(bpm=96, chords=[(57, "m"), (53, "M"), (48, "M"), (55, "M")], style="space", scale=(0, 2, 3, 5, 7, 8, 10), seed=1),
    "garage": dict(bpm=88, chords=[(50, "m7"), (55, "7"), (48, "M"), (57, "m")], style="chill", scale=(0, 2, 4, 7, 9), seed=2),
    "cronenberg": dict(bpm=116, chords=[(52, "m"), (48, "M"), (57, "m"), (59, "M")], style="eerie", scale=(0, 2, 3, 5, 7, 8, 11), seed=3),
    "federation": dict(bpm=134, chords=[(50, "m"), (46, "M"), (48, "M"), (57, "M")], style="drive", scale=(0, 2, 3, 5, 7, 8, 10), seed=4),
    "sewer": dict(bpm=108, chords=[(55, "m7"), (55, "m7"), (48, "m7"), (50, "7")], style="funk", scale=(0, 3, 5, 6, 7, 10), seed=5),
    "citadel": dict(bpm=124, chords=[(48, "M"), (57, "m"), (53, "M"), (55, "M")], style="heroic", scale=(0, 2, 4, 5, 7, 9, 11), seed=6),
    "boss": dict(bpm=150, chords=[(52, "5"), (53, "5"), (52, "5"), (51, "5")], style="boss", scale=(0, 1, 3, 5, 7, 8, 10), seed=7),
    "victory": dict(bpm=120, chords=[(48, "M"), (55, "M"), (57, "m"), (53, "M")], style="party", scale=(0, 2, 4, 7, 9), seed=8),
}
TRACK_ORDER = ["title", "garage", "cronenberg", "federation", "sewer", "citadel", "boss", "victory"]


def _add_note(buf, start, dur, freq, wave, vol, attack=0.01, release=0.08, rate=BASE_RATE):
    n = int(dur * rate)
    if n <= 0:
        return
    s0 = int(start * rate)
    L = len(buf)
    inc = freq / rate
    a = max(1, int(attack * rate))
    r = max(1, int(min(release, dur) * rate))
    tab = SINE_TAB
    ph = 0.0
    nr = n - r
    for i in range(n):
        if i < a:
            env = i / a
        elif i > nr:
            env = (n - i) / r
        else:
            env = 1.0
        p = ph - int(ph)
        if wave == 0:
            v = tab[int(p * 1024) & 1023]
        elif wave == 1:
            v = 1.0 if p < 0.5 else -1.0
        elif wave == 2:
            v = 2.0 * p - 1.0
        elif wave == 3:
            v = 4.0 * abs(p - 0.5) - 1.0
        else:
            v = 1.0 if p < 0.25 else -1.0
        buf[(s0 + i) % L] += v * env * vol
        ph += inc


def compose(name):
    spec = SONGS[name]
    rate = BASE_RATE
    rng = random.Random(spec["seed"])
    beat = 60.0 / spec["bpm"]
    bar = beat * 4
    chords = spec["chords"]
    bars = len(chords) * 2
    total = bars * bar
    buf = [0.0] * int(total * rate)
    style = spec["style"]
    s16 = beat / 4
    SIN, SQ, SAW, TRI, PUL = 0, 1, 2, 3, 4

    kick = synth(0.2, 130, 38, "sin", decay=1.6, curve=0.4)
    snare = lowpass(synth(0.16, 190, 140, "tri", decay=2.0, noise=0.75), 0.55)
    hat = synth(0.035, 9000, None, "sq", decay=2.5, noise=1.0)
    for i in range(1, len(hat)):
        hat[i] = hat[i] - hat[i - 1] * 0.6

    def drum(sample, t, g):
        mix_into(buf, sample, int(t * rate), g)

    scale = spec["scale"]
    melody_root = chords[0][0] + 12
    last = 0
    for b in range(bars):
        root, q = chords[b % len(chords)]
        tones = CHORD_TONES[q]
        t0 = b * bar
        second = b >= len(chords)
        # --- pad ---
        if style in ("space", "chill", "eerie", "heroic", "party", "title"):
            for tt in tones[:3]:
                _add_note(buf, t0, bar, midi_hz(root + 12 + tt), TRI if style != "eerie" else SIN,
                          0.035, attack=0.25, release=0.35)
        # --- basso ---
        if style == "space":
            _add_note(buf, t0, bar * 0.95, midi_hz(root - 12), TRI, 0.22, attack=0.02, release=0.3)
        elif style == "chill":
            for k, (pos, off) in enumerate(((0, 0), (1.5, 7), (2, 0), (3.5, 12))):
                _add_note(buf, t0 + pos * beat, beat * 0.9, midi_hz(root - 12 + off), TRI, 0.22)
        elif style == "funk":
            pattern = [0, None, 12, None, None, 0, None, 10, 0, None, 12, 7, None, 5, None, 3]
            for k, off in enumerate(pattern):
                if off is not None:
                    _add_note(buf, t0 + k * s16, s16 * 0.85, midi_hz(root - 12 + off), SQ, 0.11, release=0.03)
        elif style == "boss":
            for k in range(16):
                off = 0 if k % 4 != 3 else 12
                _add_note(buf, t0 + k * s16, s16 * 0.8, midi_hz(root - 12 + off), SAW, 0.12, release=0.02)
        else:
            for k in range(8):
                off = 0 if k % 2 == 0 else (12 if style in ("drive", "heroic") else 7)
                _add_note(buf, t0 + k * beat / 2, beat / 2 * 0.85, midi_hz(root - 12 + off),
                          SQ if style == "drive" else TRI, 0.12 if style == "drive" else 0.2, release=0.04)
        # --- arpeggio ---
        if style != "boss" or second:
            step = s16 if style in ("space", "eerie", "drive", "heroic", "boss") else beat / 2
            count = int(round(bar / step))
            seq = list(tones) + [tones[1] + 12 if len(tones) > 1 else 12]
            for k in range(count):
                idx = k % len(seq) if (k // len(seq)) % 2 == 0 else len(seq) - 1 - (k % len(seq))
                _add_note(buf, t0 + k * step, step * 0.7, midi_hz(root + 24 + seq[idx]), PUL,
                          0.028, release=0.03)
        # --- melodia (seconda meta' del brano) ---
        if second or style in ("party", "boss"):
            pos = 0.0
            while pos < 4.0 - 1e-6:
                d = rng.choice((0.5, 0.5, 1.0, 1.0, 1.5, 0.25, 0.25)) if style != "chill" else rng.choice((1.0, 1.5, 2.0))
                d = min(d, 4.0 - pos)
                if rng.random() < 0.82:
                    if pos % 2 == 0:
                        deg = rng.choice(tones[:3])
                        note = root + 12 + deg
                    else:
                        last = clamp(last + rng.choice((-2, -1, -1, 1, 1, 2)), -3, 9)
                        octv, deg = divmod(last, len(scale))
                        note = melody_root + octv * 12 + scale[deg]
                    wave = SAW if style in ("boss", "drive") else SQ if style in ("funk", "party") else TRI
                    _add_note(buf, t0 + pos * beat, d * beat * 0.9, midi_hz(note), wave,
                              0.06 if wave != TRI else 0.1, attack=0.01, release=0.08)
                pos += d
        # --- batteria ---
        if style == "space":
            drum(kick, t0, 0.5)
            drum(snare, t0 + 2 * beat, 0.25)
            for k in range(8):
                drum(hat, t0 + k * beat / 2, 0.12)
        elif style == "chill":
            drum(kick, t0, 0.45)
            drum(kick, t0 + 1.5 * beat, 0.3)
            drum(snare, t0 + beat, 0.22)
            drum(snare, t0 + 3 * beat, 0.22)
            for k in range(8):
                drum(hat, t0 + k * beat / 2, 0.08 if k % 2 else 0.12)
        else:
            for k in range(4):
                drum(kick, t0 + k * beat, 0.5)
                if k % 2 == 1:
                    drum(snare, t0 + k * beat, 0.3)
            hats = 16 if style in ("drive", "funk", "boss") else 8
            for k in range(hats):
                drum(hat, t0 + k * bar / hats, 0.1 if k % 2 else 0.14)
    peak = max(1e-6, max(abs(min(buf)), abs(max(buf))))
    g = 0.85 / peak
    return [v * g for v in buf]


class Audio:
    def __init__(self, enabled=True):
        self.ok = False
        self.enabled = enabled
        self.sfx = {}
        self.tracks = {}
        self._raw = {}
        self.wanted = None
        self.current = None
        self.music_ch = None
        try:
            init = pygame.mixer.get_init()
        except Exception:
            init = None
        if not init:
            return
        self.rate, self.fmt, self.ch = init
        if self.fmt != -16:
            return
        try:
            pygame.mixer.set_num_channels(24)
            pygame.mixer.set_reserved(1)
            self.music_ch = pygame.mixer.Channel(0)
            self._build_sfx()
            self.ok = True
        except Exception:
            self.ok = False
            return
        t = threading.Thread(target=self._music_worker, daemon=True)
        t.start()

    # -- conversione float -> pygame.Sound ------------------------------------
    def _to_bytes(self, samples, vol):
        if self.rate != BASE_RATE:
            ratio = BASE_RATE / self.rate
            m = int(len(samples) / ratio)
            samples = [samples[int(i * ratio)] for i in range(m)]
        g = vol * 32767
        a = array.array("h", [int(clamp(s * g, -32767, 32767)) for s in samples])
        if self.ch == 2:
            b = array.array("h", bytes(len(a) * 4))
            b[0::2] = a
            b[1::2] = a
            a = b
        elif self.ch > 2:
            b = array.array("h")
            for s in a:
                b.extend((s,) * self.ch)
            a = b
        return a.tobytes()

    def _sound(self, samples, vol=0.5):
        return pygame.mixer.Sound(buffer=self._to_bytes(samples, vol))

    def _build_sfx(self):
        s = {}
        s["laser"] = self._sound(synth(0.16, 1500, 280, "sq", decay=1.4, curve=0.6), 0.16)
        s["laser_m"] = self._sound(synth(0.14, 1900, 600, "pulse", decay=1.5, curve=0.6), 0.12)
        s["elaser"] = self._sound(synth(0.22, 700, 160, "saw", decay=1.2), 0.15)
        portal = synth(0.5, 180, 1100, "sin", decay=0.8, vib=22, vib_depth=0.12, attack=0.05, curve=0.7)
        mix_into(portal, lowpass(synth(0.5, 100, None, "sq", decay=1.0, noise=1.0, attack=0.05), 0.25), 0, 0.5)
        s["portal"] = self._sound(portal, 0.33)
        s["jump"] = self._sound(synth(0.13, 260, 680, "tri", decay=1.3), 0.25)
        s["djump"] = self._sound(synth(0.16, 520, 1250, "tri", decay=1.3, vib=30), 0.2)
        s["hit"] = self._sound(lowpass(synth(0.09, 260, 70, "sq", decay=1.5, noise=0.5), 0.5), 0.3)
        s["hurt"] = self._sound(synth(0.32, 420, 110, "saw", decay=1.0, vib=14, vib_depth=0.08), 0.28)
        s["explode"] = self._sound(lowpass(synth(0.7, 60, 30, "sq", decay=2.0, noise=0.85), 0.18), 0.6)
        coin = synth(0.06, 988, None, "sq", decay=0.3) + synth(0.14, 1319, None, "sq", decay=1.2)
        s["coin"] = self._sound(coin, 0.11)
        seed = []
        for f in (523, 659, 784, 1047, 1319):
            seed += synth(0.07, f, None, "tri", decay=0.4)
        seed += synth(0.3, 1568, None, "tri", decay=1.5, vib=8)
        s["seed"] = self._sound(seed, 0.3)
        burp = synth(0.55, 105, 72, "saw", decay=0.7, vib=27, vib_depth=0.25, attack=0.03, noise=0.25)
        s["burp"] = self._sound(lowpass(burp, 0.12), 0.9)
        up = []
        for f in (392, 523, 659, 784, 1047):
            up += synth(0.06, f, None, "sq", decay=0.5)
        s["powerup"] = self._sound(up, 0.12)
        s["select"] = self._sound(synth(0.05, 660, None, "sq", decay=1.0), 0.1)
        s["confirm"] = self._sound(synth(0.06, 880, None, "sq", decay=0.4) + synth(0.12, 1320, None, "sq", decay=1.4), 0.12)
        roar = lowpass(synth(1.3, 95, 48, "saw", decay=0.6, vib=9, vib_depth=0.15, attack=0.08, noise=0.3), 0.15)
        s["roar"] = self._sound(roar, 0.85)
        s["shock"] = self._sound(lowpass(synth(0.6, 70, 35, "sin", decay=1.4, noise=0.4), 0.3), 0.7)
        s["poof"] = self._sound(synth(0.28, 900, 200, "tri", decay=1.6, noise=0.6), 0.2)
        s["death"] = self._sound(synth(1.0, 620, 70, "sq", decay=0.9, vib=7, vib_depth=0.06), 0.18)
        s["stomp"] = self._sound(lowpass(synth(0.12, 220, 60, "sq", decay=1.2, noise=0.3), 0.4), 0.35)
        s["charge"] = self._sound(synth(0.6, 200, 900, "saw", decay=0.2, vib=20, vib_depth=0.05, attack=0.05), 0.08)
        s["beam"] = self._sound(lowpass(synth(0.7, 140, 120, "saw", decay=0.8, noise=0.5, vib=40), 0.35), 0.3)
        s["drink"] = self._sound(lowpass(synth(0.35, 300, 200, "sin", decay=0.6, noise=0.6, vib=12, vib_depth=0.3), 0.3), 0.3)
        self.sfx = s

    def _music_worker(self):
        for name in TRACK_ORDER:
            try:
                self._raw[name] = self._to_bytes(compose(name), 0.95)
            except Exception:
                pass

    # -- API --------------------------------------------------------------------
    def play(self, name, vol=1.0):
        if not (self.ok and self.enabled):
            return
        snd = self.sfx.get(name)
        if snd is None:
            return
        ch = snd.play()
        if ch is not None:
            ch.set_volume(vol)

    def music(self, name):
        self.wanted = name
        self.update()

    def update(self):
        if not self.ok:
            return
        name = self.wanted
        if name == self.current:
            return
        if name is None:
            self.music_ch.fadeout(500)
            self.current = None
            return
        if name not in self.tracks:
            raw = self._raw.get(name)
            if raw is None:
                return  # non ancora generato: riprovo al prossimo frame
            try:
                self.tracks[name] = pygame.mixer.Sound(buffer=raw)
            except Exception:
                return
        self.music_ch.play(self.tracks[name], loops=-1, fade_ms=700)
        self.music_ch.set_volume(0.42 if self.enabled else 0.0)
        self.current = name

    def toggle(self):
        self.enabled = not self.enabled
        if self.ok and self.music_ch is not None:
            self.music_ch.set_volume(0.42 if self.enabled else 0.0)
        return self.enabled


# =============================================================================
#  GRAFICA PROCEDURALE: personaggi disegnati con primitive e contorno nero,
#  in stile cartone animato della serie.
# =============================================================================
class Pen:
    """Disegna in 'unita' di design moltiplicate per la scala (supersampling)."""

    def __init__(self, surf, s):
        self.surf = surf
        self.s = s

    def _p(self, pts):
        s = self.s
        return [(x * s, y * s) for x, y in pts]

    def poly(self, color, pts, ow=1.5):
        p = self._p(pts)
        pygame.draw.polygon(self.surf, color, p)
        if ow:
            pygame.draw.polygon(self.surf, OUTLINE, p, max(1, round(ow * self.s)))

    def ell(self, color, cx, cy, rx, ry, ow=1.5):
        s = self.s
        r = pygame.Rect(0, 0, max(2, round(2 * rx * s)), max(2, round(2 * ry * s)))
        r.center = (round(cx * s), round(cy * s))
        pygame.draw.ellipse(self.surf, color, r)
        if ow:
            pygame.draw.ellipse(self.surf, OUTLINE, r, max(1, round(ow * s)))

    def circ(self, color, cx, cy, r, ow=1.5):
        self.ell(color, cx, cy, r, r, ow)

    def line(self, color, a, b, w=1.5):
        s = self.s
        pygame.draw.line(self.surf, color, (a[0] * s, a[1] * s), (b[0] * s, b[1] * s), max(1, round(w * s)))

    def lines(self, color, pts, w=1.5, closed=False):
        pygame.draw.lines(self.surf, color, closed, self._p(pts), max(1, round(w * self.s)))

    def limb(self, color, a, b, width, ow=1.5):
        """Arto a capsula con contorno."""
        s = self.s
        A = (a[0] * s, a[1] * s)
        B = (b[0] * s, b[1] * s)
        if ow:
            wo = round((width + ow * 2) * s)
            pygame.draw.line(self.surf, OUTLINE, A, B, wo)
            pygame.draw.circle(self.surf, OUTLINE, A, wo / 2)
            pygame.draw.circle(self.surf, OUTLINE, B, wo / 2)
        wi = round(width * s)
        pygame.draw.line(self.surf, color, A, B, wi)
        pygame.draw.circle(self.surf, color, A, wi / 2)
        pygame.draw.circle(self.surf, color, B, wi / 2)

    def chain(self, color, pts, width, ow=1.5):
        if ow:
            for i in range(len(pts) - 1):
                self.limb(OUTLINE, pts[i], pts[i + 1], width + ow * 2, 0)
        for i in range(len(pts) - 1):
            self.limb(color, pts[i], pts[i + 1], width, 0)


def rot(cx, cy, ang, u, v):
    """punto locale (u avanti, v giu) ruotato di ang attorno a (cx,cy)"""
    c, s = math.cos(ang), math.sin(ang)
    return (cx + u * c - v * s, cy + u * s + v * c)


# Palette dei personaggi
SKIN_RICK = (238, 216, 194)
HAIR_RICK = (172, 224, 242)
BROW_RICK = (150, 206, 228)
COAT = (242, 246, 248)
SHIRT_RICK = (150, 206, 228)
PANTS_RICK = (134, 98, 62)
SHOES_RICK = (64, 46, 36)
SKIN_MORTY = (248, 216, 180)
HAIR_MORTY = (112, 64, 32)
SHIRT_MORTY = (247, 222, 76)
PANTS_MORTY = (58, 102, 172)
SHOES_MORTY = (240, 240, 242)
GUN_COL = (156, 164, 176)
GUN_DARK = (96, 102, 114)


def leg_pose(st, fr, stride=9.0):
    """ritorna: offset piede1, offset piede2, alzata1, alzata2, bob corpo, oscillazione braccio"""
    if st == "run":
        ph = fr / 8.0 * 2 * math.pi
        s, c = math.sin(ph), math.cos(ph)
        return s * stride, -s * stride, max(0.0, c) * 6, max(0.0, -c) * 6, abs(c) * 2.0, s
    if st == "jump":
        return -stride * 0.8, stride * 0.7, 9, 3, 0, -0.6
    if st == "fall":
        return stride * 0.6, -stride * 0.5, 2, 6, 0, 0.8
    if st == "hurt":
        return -4, 5, 3, 1, 0, 1.0
    b = math.sin(fr / 4.0 * 2 * math.pi) * 0.8 + 0.8
    return -3, 3, 0, 0, b, 0


def draw_gun(p, hx, hy, a, big=True, glow=PORTAL_GREEN, body=GUN_COL, dark=GUN_DARK):
    k = 1.0 if big else 0.72
    R = lambda u, v: rot(hx, hy, a, u * k, v * k)
    p.poly(dark, [R(-1, 1), R(4, 1), R(3, 9), R(-2, 8)], 1.2)  # impugnatura
    p.poly(body, [R(-4, -4), R(14, -4), R(15, 2), R(-4, 2)], 1.2)  # corpo
    p.poly(dark, [R(14, -2.5), R(21, -2.5), R(21, 1), R(14, 1)], 1.2)  # canna
    p.poly(glow, [R(2, -8), R(10, -8), R(11, -4), R(1, -4)], 1.0)  # capsula fluido
    p.line(shade(glow, 1.3), R(3, -6.5), R(9, -6.5), 1.0)


def draw_rick(p, st, fr, aim, guard=False):
    cx, gy = 40, 112
    coat, shirt, pants, shoes = COAT, SHIRT_RICK, PANTS_RICK, SHOES_RICK
    if guard:
        coat, shirt, pants, shoes = (72, 78, 96), (44, 48, 60), (52, 56, 70), (28, 28, 34)
    l1, l2, lf1, lf2, bob, sw = leg_pose(st, fr)
    oy = -bob
    # braccio dietro
    shb = (cx - 10, 50 + oy)
    hb = (cx - 12 - sw * 7, 76 + oy - abs(sw) * 2)
    eb = ((shb[0] + hb[0]) / 2 - 2, (shb[1] + hb[1]) / 2)
    p.chain(shade(coat, 0.86), [shb, eb, hb], 8.5)
    p.circ(shade(SKIN_RICK, 0.92), hb[0], hb[1] + 2, 3.6, 1.2)
    # gambe
    for hipx, off, lift, col in ((cx - 4, l2, lf2, shade(pants, 0.82)), (cx + 4, l1, lf1, pants)):
        hip = (hipx, 82 + oy)
        foot = (hipx + off, gy - 5 - lift)
        knee = ((hip[0] + foot[0]) / 2 + 2, (hip[1] + foot[1]) / 2)
        p.chain(col, [hip, knee, foot], 9.5)
        p.ell(shoes, foot[0] + 3, foot[1] + 2.5, 7.5, 4, 1.4)
    # busto
    p.poly(pants, [(cx - 12, 76 + oy), (cx + 12, 76 + oy), (cx + 11, 88 + oy), (cx - 11, 88 + oy)], 1.4)
    p.poly(shirt, [(cx - 11, 44 + oy), (cx + 11, 44 + oy), (cx + 12, 80 + oy), (cx - 12, 80 + oy)], 1.4)
    # camice da laboratorio
    p.poly(shade(coat, 0.9), [(cx - 16, 43 + oy), (cx - 5, 43 + oy), (cx - 3, 62 + oy), (cx - 5, 95 + oy), (cx - 19, 93 + oy)], 1.5)
    p.poly(coat, [(cx + 5, 43 + oy), (cx + 16, 43 + oy), (cx + 19, 93 + oy), (cx + 5, 95 + oy), (cx + 3, 62 + oy)], 1.5)
    p.poly(shade(coat, 0.8), [(cx - 5, 43 + oy), (cx - 1, 44 + oy), (cx - 4, 57 + oy)], 1.0)
    p.poly(shade(coat, 0.8), [(cx + 5, 43 + oy), (cx + 1, 44 + oy), (cx + 4, 57 + oy)], 1.0)
    p.line(OUTLINE, (cx + 9, 74 + oy), (cx + 15, 74 + oy), 1.1)  # tasca
    # collo
    p.limb(SKIN_RICK, (cx + 1, 38 + oy), (cx + 1, 46 + oy), 7.5, 1.3)
    # capelli a punte (dietro la testa)
    hcx, hcy = cx - 2, 21 + oy
    spikes = [(-62, 15), (-86, 23), (-108, 18), (-128, 25), (-150, 20), (-170, 26), (172, 19), (154, 23), (136, 15)]
    pts = [(hcx + math.cos(math.radians(-50)) * 10, hcy + math.sin(math.radians(-50)) * 10)]
    for i, (ang, L) in enumerate(spikes):
        a = math.radians(ang)
        pts.append((hcx + math.cos(a) * L, hcy + math.sin(a) * L))
        if i < len(spikes) - 1:
            m = math.radians((ang + spikes[i + 1][0]) / 2 if abs(ang - spikes[i + 1][0]) < 180
                             else (ang + spikes[i + 1][0] + 360) / 2)
            pts.append((hcx + math.cos(m) * 11, hcy + math.sin(m) * 11))
    pts.append((hcx + math.cos(math.radians(125)) * 10, hcy + math.sin(math.radians(125)) * 10))
    p.poly(HAIR_RICK, pts, 1.5)
    # testa allungata
    p.ell(SKIN_RICK, cx + 3, 24 + oy, 12, 16, 1.5)
    p.ell(SKIN_RICK, cx - 7.5, 26 + oy, 3, 4.5, 1.2)  # orecchio
    if guard:
        p.poly((40, 44, 54), [(cx - 11, 22 + oy), (cx - 10, 9 + oy), (cx + 2, 4 + oy), (cx + 13, 7 + oy),
                              (cx + 17, 15 + oy), (cx + 16, 17 + oy), (cx - 9, 22 + oy)], 1.5)
        p.line((90, 200, 240), (cx - 4, 14 + oy), (cx + 14, 13 + oy), 1.6)
    # occhi (leggermente storti, come Rick)
    p.circ(WHITE, cx + 2, 22 + oy, 5.2, 1.3)
    p.circ(WHITE, cx + 11.5, 22.5 + oy, 4.6, 1.3)
    p.circ(OUTLINE, cx + 3.2, 22.4 + oy, 1.5, 0)
    p.circ(OUTLINE, cx + 11.2, 23.2 + oy, 1.5, 0)
    # monociglio
    p.poly(BROW_RICK, [(cx - 5, 15.5 + oy), (cx + 3, 13.2 + oy), (cx + 16, 14.2 + oy), (cx + 16, 17.4 + oy),
                       (cx + 3, 16.8 + oy), (cx - 5, 18.6 + oy)], 1.2)
    # occhiaie, naso, bocca e bava
    p.lines(OUTLINE, [(cx - 2, 27.5 + oy), (cx + 2, 28.6 + oy), (cx + 6, 27.6 + oy)], 0.9)
    p.lines(OUTLINE, [(cx + 9, 25 + oy), (cx + 13.5, 30 + oy), (cx + 9.5, 31 + oy)], 1.3)
    p.lines(OUTLINE, [(cx - 1, 34.5 + oy), (cx + 5, 35.8 + oy), (cx + 13, 34 + oy)], 1.5)
    p.ell((214, 236, 214), cx + 0.5, 37.6 + oy, 1.3, 2.4, 0.8)
    # braccio davanti con pistola
    a = math.radians(aim)
    sh = (cx + 9, 50 + oy)
    hand = rot(sh[0], sh[1], a, 21, 0)
    elbow = rot(sh[0], sh[1], a, 10.5, 4)
    p.chain(coat, [sh, elbow, hand], 8.5)
    draw_gun(p, hand[0], hand[1], a, True, glow=PORTAL_GREEN if not guard else (240, 90, 80))
    p.circ(SKIN_RICK, hand[0], hand[1] + 1, 3.8, 1.2)


def draw_morty(p, st, fr, aim, armed=True):
    cx, gy = 32, 88
    l1, l2, lf1, lf2, bob, sw = leg_pose(st, fr, 7.0)
    oy = -bob
    shb = (cx - 10, 50 + oy)
    hb = (cx - 12 - sw * 5, 66 + oy)
    p.limb(shade(SKIN_MORTY, 0.92), shb, hb, 6.5, 1.3)
    p.circ(shade(SHIRT_MORTY, 0.88), shb[0] + 1, shb[1] + 1, 5, 1.3)
    for hipx, off, lift, col in ((cx - 4, l2, lf2, shade(PANTS_MORTY, 0.82)), (cx + 4, l1, lf1, PANTS_MORTY)):
        hip = (hipx, 70 + oy)
        foot = (hipx + off, gy - 4.5 - lift)
        p.limb(col, hip, foot, 9.5, 1.4)
        p.ell(SHOES_MORTY, foot[0] + 2.5, foot[1] + 2.2, 7, 4, 1.4)
    p.poly(PANTS_MORTY, [(cx - 13, 66 + oy), (cx + 13, 66 + oy), (cx + 13, 75 + oy), (cx - 13, 75 + oy)], 1.4)
    p.poly(SHIRT_MORTY, [(cx - 12, 45 + oy), (cx + 12, 45 + oy), (cx + 14, 71 + oy), (cx - 14, 71 + oy)], 1.5)
    p.lines(OUTLINE, [(cx - 4, 45.5 + oy), (cx + 1, 48 + oy), (cx + 6, 45.5 + oy)], 1.1)
    p.limb(SKIN_MORTY, (cx + 1, 40 + oy), (cx + 1, 46 + oy), 6, 1.2)
    # testa grande e rotonda
    hx, hy = cx + 2, 25 + oy
    p.ell(SKIN_MORTY, hx, hy, 17.5, 16.5, 1.5)
    p.ell(SKIN_MORTY, cx - 14, 28 + oy, 3, 4.2, 1.2)
    pts = []
    for d in range(168, 356, 8):
        a = math.radians(d)
        pts.append((hx + math.cos(a) * 18.4, hy + math.sin(a) * 17.4))
    pts += [(hx + 17.5, hy - 6), (hx + 11, hy - 11), (hx + 5, hy - 9.5), (hx - 1, hy - 12), (hx - 7, hy - 9.5),
            (hx - 12, hy - 7), (hx - 15.5, hy - 1)]
    p.poly(HAIR_MORTY, pts, 1.5)
    p.circ(WHITE, cx + 1, 26 + oy, 6.3, 1.3)
    p.circ(WHITE, cx + 13, 26 + oy, 6.0, 1.3)
    p.circ(OUTLINE, cx + 2, 26.5 + oy, 1.7, 0)
    p.circ(OUTLINE, cx + 13.5, 26.5 + oy, 1.7, 0)
    p.lines(OUTLINE, [(cx + 2, 36 + oy), (cx + 6, 35 + oy), (cx + 10, 36.5 + oy), (cx + 14, 35 + oy)], 1.4)
    sh = (cx + 10, 51 + oy)
    if armed:
        a = math.radians(aim)
        hand = rot(sh[0], sh[1], a, 15, 0)
        elbow = rot(sh[0], sh[1], a, 7.5, 3)
        p.chain(SKIN_MORTY, [sh, elbow, hand], 6.5, 1.3)
        draw_gun(p, hand[0], hand[1], a, False, glow=(255, 220, 90))
        p.circ(SKIN_MORTY, hand[0], hand[1] + 1, 3.2, 1.1)
    else:
        hand = (cx + 12 + sw * 5, 66 + oy)
        p.limb(SKIN_MORTY, sh, hand, 6.5, 1.3)
    p.circ(SHIRT_MORTY, sh[0] - 1, sh[1] + 1, 5.2, 1.3)


def draw_pickle(p, st, fr, aim):
    cx, gy = 34, 84
    G, GD, GL = (92, 164, 62), (60, 124, 40), (140, 206, 96)
    RAT = (140, 112, 102)
    l1, l2, lf1, lf2, bob, sw = leg_pose(st, fr, 6.0)
    oy = -bob
    p.limb(shade(RAT, 0.85), (cx - 10, 50 + oy), (cx - 13 - sw * 5, 62 + oy), 4.5, 1.2)
    for hipx, off, lift in ((cx - 5, l2, lf2), (cx + 5, l1, lf1)):
        hip = (hipx, 72 + oy)
        foot = (hipx + off, gy - 4 - lift)
        knee = ((hip[0] + foot[0]) / 2 + 3, (hip[1] + foot[1]) / 2)
        p.chain(RAT, [hip, knee, foot], 5.0, 1.3)
        p.ell((236, 170, 176), foot[0] + 2.5, foot[1] + 2, 5, 3, 1.2)
    p.ell(G, cx, 44 + oy, 15.5, 33, 1.6)
    p.ell(GL, cx - 7, 42 + oy, 3, 20, 0)
    for bx, by in ((cx - 9, 60), (cx + 7, 66), (cx + 10, 52), (cx - 4, 70), (cx - 10, 30), (cx + 2, 56), (cx + 11, 40)):
        p.circ(GD, bx, by + oy, 1.6, 0)
    # faccia di Rick
    p.poly((54, 100, 34), [(cx - 5, 21 + oy), (cx + 3, 19 + oy), (cx + 16, 20 + oy), (cx + 16, 23 + oy),
                           (cx + 3, 22.5 + oy), (cx - 5, 24 + oy)], 1.1)
    p.circ(WHITE, cx + 3, 28 + oy, 5, 1.3)
    p.circ(WHITE, cx + 12, 28.5 + oy, 4.5, 1.3)
    p.circ(OUTLINE, cx + 4, 28.5 + oy, 1.5, 0)
    p.circ(OUTLINE, cx + 12, 29 + oy, 1.5, 0)
    p.poly((120, 40, 40), [(cx + 0, 38 + oy), (cx + 14, 37 + oy), (cx + 11, 43 + oy), (cx + 3, 43 + oy)], 1.3)
    p.line(WHITE, (cx + 2, 39 + oy), (cx + 12.5, 38.4 + oy), 1.4)
    a = math.radians(aim)
    sh = (cx + 12, 50 + oy)
    hand = rot(sh[0], sh[1], a, 14, 0)
    elbow = rot(sh[0], sh[1], a, 7, 3)
    p.chain(RAT, [sh, elbow, hand], 4.5, 1.2)
    draw_gun(p, hand[0], hand[1], a, False, glow=(255, 90, 90), body=(150, 120, 100), dark=(90, 70, 60))
    p.circ((236, 170, 176), hand[0], hand[1] + 1, 2.6, 1.0)


def draw_meeseeks(p, st, fr, aim):
    cx, gy = 30, 98
    B, BD = (124, 192, 242), (96, 160, 214)
    l1, l2, lf1, lf2, bob, sw = leg_pose(st, fr, 7.0)
    oy = -bob
    up = (fr % 2 == 0) if st != "idle" else (fr < 2)
    for hipx, off, lift in ((cx - 4, l2, lf2), (cx + 4, l1, lf1)):
        p.limb(BD if hipx < cx else B, (hipx, 64 + oy), (hipx + off, gy - 3 - lift), 5.5, 1.3)
        p.ell(B, hipx + off + 2, gy - 2 - lift, 5, 2.6, 1.2)
    for side in (-1, 1):
        shp = (cx + side * 7, 44 + oy)
        if up:
            hand = (cx + side * 16, 22 + oy)
        else:
            hand = (cx + side * 13, 62 + oy)
        el = ((shp[0] + hand[0]) / 2 + side * 4, (shp[1] + hand[1]) / 2)
        p.chain(B, [shp, el, hand], 4.5, 1.2)
        p.circ(B, hand[0], hand[1], 3, 1.1)
    p.ell(B, cx, 53 + oy, 9, 15, 1.5)
    p.ell(B, cx + 1, 22 + oy, 13, 17, 1.5)
    p.lines(OUTLINE, [(cx - 1, 6 + oy), (cx + 1, 1 + oy), (cx + 5, 3 + oy)], 1.4)
    p.circ(WHITE, cx - 3, 18 + oy, 4.3, 1.2)
    p.circ(WHITE, cx + 7, 18 + oy, 4.3, 1.2)
    p.circ(OUTLINE, cx - 2.5, 18.5 + oy, 1.4, 0)
    p.circ(OUTLINE, cx + 7.5, 18.5 + oy, 1.4, 0)
    p.ell((70, 20, 40), cx + 2, 31 + oy, 6, 4.2, 1.2)
    p.ell((230, 110, 130), cx + 2, 33 + oy, 3, 1.5, 0)


def draw_poopy(p, st, fr, aim):
    cx, gy = 26, 58
    Y, YD = (240, 198, 84), (210, 166, 60)
    bob = math.sin(fr / 4 * 2 * math.pi) * 1.2
    p.ell(YD, cx - 7, gy - 3, 5.5, 3, 1.3)
    p.ell(YD, cx + 7, gy - 3, 5.5, 3, 1.3)
    wave = math.sin(fr / 4 * 2 * math.pi) * 6
    p.limb(Y, (cx - 14, 34 - bob), (cx - 21, 42 - bob), 5, 1.3)
    p.limb(Y, (cx + 14, 32 - bob), (cx + 22, 22 - bob + wave), 5, 1.3)
    p.ell(Y, cx, 32 - bob, 17, 22, 1.6)
    p.ell(WHITE, cx - 6, 24 - bob, 5.5, 6.5, 1.3)
    p.ell(WHITE, cx + 6, 24 - bob, 5.5, 6.5, 1.3)
    p.circ(OUTLINE, cx - 5, 25 - bob, 2.1, 0)
    p.circ(OUTLINE, cx + 7, 25 - bob, 2.1, 0)
    p.lines(OUTLINE, [(cx - 7, 34 - bob), (cx, 39 - bob), (cx + 7, 34 - bob)], 1.5)
    p.lines(OUTLINE, [(cx - 10, 16 - bob), (cx - 4, 15 - bob)], 1.2)
    p.lines(OUTLINE, [(cx + 4, 15 - bob), (cx + 10, 16 - bob)], 1.2)


_BLOB_NOISE = [1.0, 0.92, 1.08, 0.95, 1.12, 0.9, 1.05, 0.97, 1.1, 0.93, 1.02, 0.96, 1.09, 0.91, 1.06, 0.98, 1.04, 0.94]


def draw_cronen(p, st, fr, aim):
    cx, gy = 35, 62
    FL, FD, FX = (232, 152, 140), (196, 104, 100), (250, 196, 180)
    wob = math.sin(fr / 8 * 2 * math.pi)
    for i, lx in enumerate((cx - 15, cx - 1, cx + 14)):
        off = wob * (5 if i % 2 == 0 else -5)
        p.limb(FD, (lx, 46), (lx + off, gy - 3 - abs(off) * 0.4), 8, 1.4)
        p.ell(FD, lx + off + 2, gy - 2, 5.5, 3, 1.2)
    p.chain(FL, [(cx - 12, 22), (cx - 18, 12), (cx - 16 + wob * 4, 4)], 6, 1.4)
    p.circ(FX, cx - 16 + wob * 4, 4, 3.4, 1.2)
    pts = []
    n = len(_BLOB_NOISE)
    for i in range(n):
        a = i / n * 2 * math.pi
        r = _BLOB_NOISE[i] + 0.04 * math.sin(a * 3 + fr)
        pts.append((cx + math.cos(a) * 27 * r, 34 + math.sin(a) * 19 * r + wob * 0.8))
    p.poly(FL, pts, 1.6)
    for sx, sy, r in ((cx - 14, 38, 4), (cx - 6, 46, 2.5), (cx + 18, 44, 3), (cx - 20, 30, 2.2)):
        p.circ(FD, sx, sy, r, 0)
    p.line(FD, (cx - 2, 18), (cx - 6, 26), 1.2)
    p.chain(FL, [(cx + 2, 18), (cx + 4, 10)], 2.5, 1.0)
    p.circ(WHITE, cx + 4, 9, 3.6, 1.2)
    p.circ(OUTLINE, cx + 5, 9, 1.3, 0)
    p.circ(WHITE, cx + 12, 27, 6.6, 1.3)
    p.circ((180, 40, 40), cx + 13.5, 27.5, 2.8, 0)
    p.circ(OUTLINE, cx + 13.5, 27.5, 1.3, 0)
    p.circ(WHITE, cx - 3, 24, 4, 1.2)
    p.circ(OUTLINE, cx - 2, 24.5, 1.4, 0)
    p.circ(WHITE, cx + 22, 36, 3, 1.1)
    p.circ(OUTLINE, cx + 22.6, 36.2, 1.1, 0)
    p.ell((120, 30, 44), cx + 9, 43, 8.5, 4.6, 1.3)
    for tx in range(-6, 8, 3):
        p.poly(WHITE, [(cx + 9 + tx - 1.2, 40), (cx + 9 + tx + 1.2, 40), (cx + 9 + tx, 43)], 0)


def draw_cronen_flyer(p, st, fr, aim):
    cx, cy = 35, 26
    FL, FD = (226, 146, 138), (180, 92, 96)
    flap = math.sin(fr / 8 * 2 * math.pi)
    for side in (-1, 1):
        tip = (cx + side * 33, cy - 12 + flap * 14)
        p.poly(FD, [(cx + side * 8, cy - 3), tip, (cx + side * 27, cy + 4 + flap * 6),
                    (cx + side * 18, cy + 2 + flap * 3), (cx + side * 12, cy + 8)], 1.4)
        p.line(OUTLINE, (cx + side * 9, cy), tip, 1.0)
    for i, tx in enumerate((cx - 7, cx, cx + 7)):
        pts = [(tx + math.sin(fr * 0.8 + i + k * 0.9) * 3, cy + 10 + k * 5.5) for k in range(6)]
        p.chain(FD, pts, 2.6, 1.0)
    p.ell(FL, cx, cy, 15.5, 13.5, 1.5)
    p.circ(WHITE, cx + 3, cy - 2, 7.2, 1.3)
    p.circ((210, 40, 40), cx + 4.5, cy - 1.5, 3.6, 0)
    p.circ(OUTLINE, cx + 4.8, cy - 1.5, 1.6, 0)
    p.line((210, 80, 80), (cx - 3, cy - 6), (cx - 1, cy - 4), 0.8)
    p.ell((110, 30, 40), cx + 2, cy + 8, 4.5, 2.2, 1.1)


def draw_grom(p, st, fr, aim):
    cx, gy = 32, 90
    SK, UN, UD, YE = (156, 178, 104), (52, 64, 104), (36, 44, 74), (234, 200, 70)
    l1, l2, lf1, lf2, bob, sw = leg_pose(st, fr, 7.5)
    oy = -bob
    p.limb(shade(UN, 0.85), (cx - 9, 42 + oy), (cx - 11 - sw * 5, 62 + oy), 7.5, 1.3)
    p.circ(shade(SK, 0.9), cx - 11 - sw * 5, 64 + oy, 3, 1.1)
    for hipx, off, lift, col in ((cx - 4, l2, lf2, shade(UD, 0.85)), (cx + 4, l1, lf1, UD)):
        hip = (hipx, 64 + oy)
        foot = (hipx + off, gy - 5 - lift)
        p.limb(col, hip, foot, 8.5, 1.4)
        p.ell((24, 24, 30), foot[0] + 3, foot[1] + 2.5, 7, 4, 1.3)
    p.poly(UN, [(cx - 11, 38 + oy), (cx + 11, 38 + oy), (cx + 12, 66 + oy), (cx - 12, 66 + oy)], 1.5)
    p.poly(YE, [(cx - 12, 59 + oy), (cx + 12, 59 + oy), (cx + 12, 62.5 + oy), (cx - 12, 62.5 + oy)], 1.0)
    p.circ(YE, cx + 6, 45 + oy, 2.6, 1.0)
    p.line(UD, (cx, 38 + oy), (cx, 58 + oy), 1.0)
    p.limb(SK, (cx + 1, 32 + oy), (cx + 1, 40 + oy), 6, 1.2)
    p.chain(SK, [(cx - 2, 8 + oy), (cx - 7, 2 + oy), (cx - 13, 3 + oy)], 1.8, 0.9)
    p.chain(SK, [(cx + 6, 7 + oy), (cx + 8, 1 + oy), (cx + 14, 1 + oy)], 1.8, 0.9)
    p.ell(SK, cx + 3, 20 + oy, 12.5, 14.5, 1.5)
    p.ell((20, 22, 26), cx + 1.5, 17 + oy, 5.2, 7.2, 1.2)
    p.ell((20, 22, 26), cx + 11.5, 17.5 + oy, 4.6, 6.6, 1.2)
    p.circ((200, 220, 230), cx + 3, 14 + oy, 1.6, 0)
    p.circ((200, 220, 230), cx + 13, 14.5 + oy, 1.4, 0)
    p.poly(shade(SK, 0.75), [(cx + 7, 28 + oy), (cx + 11, 30 + oy), (cx + 9, 34 + oy)], 1.0)
    p.poly(shade(SK, 0.75), [(cx + 13, 28 + oy), (cx + 16, 30 + oy), (cx + 13, 34 + oy)], 1.0)
    p.poly(UD, [(cx - 9, 8 + oy), (cx + 3, 3 + oy), (cx + 15, 7 + oy), (cx + 14, 9 + oy), (cx - 9, 11 + oy)], 1.2)
    a = math.radians(aim)
    sh = (cx + 9, 43 + oy)
    hand = rot(sh[0], sh[1], a, 18, 0)
    elbow = rot(sh[0], sh[1], a, 9, 3)
    p.chain(UN, [sh, elbow, hand], 7.5, 1.3)
    draw_gun(p, hand[0], hand[1], a, True, glow=(255, 80, 70), body=(70, 74, 86), dark=(40, 42, 50))
    p.circ(SK, hand[0], hand[1] + 1, 3.2, 1.1)


def draw_drone(p, st, fr, aim, citadel=False):
    cx, cy = 32, 20
    body = (210, 222, 234) if citadel else (62, 72, 114)
    dome = (255, 222, 120) if citadel else (130, 210, 255)
    p.ell(dome, cx, cy - 5, 10, 8, 1.4)
    p.ell(WHITE, cx - 3, cy - 8, 3, 2, 0)
    p.ell(body, cx, cy, 27, 8.5, 1.6)
    p.ell(shade(body, 0.75), cx, cy + 4, 18, 3.5, 1.2)
    for i in range(5):
        on = (i + fr) % 4 == 0
        col = (255, 90, 80) if on else (120, 40, 40)
        p.circ(col, cx - 18 + i * 9, cy + 1, 1.8, 0.8)
    p.circ((255, 60, 50), cx + 22, cy - 1, 3.4, 1.1)
    p.circ((255, 220, 210), cx + 23, cy - 2, 1.0, 0)


def draw_rat(p, st, fr, aim):
    cx, gy = 34, 38
    FUR, PINK = (120, 108, 102), (236, 160, 170)
    ph = fr / 8 * 2 * math.pi
    tail = [(cx - 18 - k * 4, 26 - k * 1.2 + math.sin(ph + k * 0.8) * 2.2) for k in range(5)]
    p.chain(PINK, tail, 2.3, 1.0)
    for i, lx in enumerate((cx - 12, cx - 6, cx + 8, cx + 14)):
        off = math.sin(ph + i * math.pi / 2) * 4
        p.limb(shade(FUR, 0.8), (lx, 28), (lx + off, gy - 2), 3.6, 1.1)
        p.ell(PINK, lx + off + 1.5, gy - 1.5, 2.8, 1.6, 0.8)
    p.ell(FUR, cx - 2, 25, 20, 10.5, 1.5)
    p.ell(shade(FUR, 1.15), cx - 2, 29, 13, 4, 0)
    p.poly(FUR, [(cx + 10, 18), (cx + 31, 26), (cx + 10, 31)], 1.4)
    p.ell(FUR, cx + 16, 24, 9.5, 7.8, 1.4)
    p.circ(PINK, cx + 31, 26, 2.2, 1.0)
    p.circ(FUR, cx + 13, 15, 5, 1.3)
    p.circ(PINK, cx + 13, 15, 2.8, 0)
    p.circ((230, 30, 40), cx + 20, 21, 2.4, 0.9)
    for dy in (-1.5, 1.5):
        p.line(OUTLINE, (cx + 27, 26 + dy), (cx + 34, 25 + dy * 2.5), 0.7)


def draw_roach(p, st, fr, aim):
    cx, cy = 24, 18
    BR = (112, 66, 36)
    flap = abs(math.sin(fr / 8 * 2 * math.pi))
    for i, lx in enumerate((cx - 7, cx, cx + 7)):
        p.lines(OUTLINE, [(lx, cy + 4), (lx - 3, cy + 9), (lx - 5 + (i - 1) * 2, cy + 12)], 1.0)
    p.ell((200, 170, 120, 150), cx - 4, cy - 6 - flap * 4, 12, 4 + flap * 3, 0)
    p.ell(BR, cx, cy, 14, 7.5, 1.4)
    p.line(shade(BR, 0.7), (cx - 12, cy), (cx + 10, cy), 1.0)
    p.circ(shade(BR, 0.7), cx + 14, cy + 1, 5, 1.3)
    p.circ(WHITE, cx + 16, cy - 1, 1.6, 0)
    p.lines(OUTLINE, [(cx + 17, cy - 2), (cx + 22, cy - 9), (cx + 23, cy - 14)], 0.9)
    p.lines(OUTLINE, [(cx + 18, cy - 1), (cx + 24, cy - 6), (cx + 23, cy - 11)], 0.9)


# ---- definizione sprite: dimensione tela (in pixel finali) e ancora piedi ----
SPRITES = {
    "rick": dict(size=(100, 114), anchor=40, fn=draw_rick),
    "guard": dict(size=(100, 114), anchor=40, fn=lambda p, s, f, a: draw_rick(p, s, f, a, guard=True)),
    "morty": dict(size=(84, 90), anchor=32, fn=draw_morty),
    "morty_unarmed": dict(size=(84, 90), anchor=32, fn=lambda p, s, f, a: draw_morty(p, s, f, a, armed=False)),
    "pickle": dict(size=(84, 86), anchor=34, fn=draw_pickle),
    "meeseeks": dict(size=(60, 100), anchor=30, fn=draw_meeseeks),
    "poopy": dict(size=(52, 60), anchor=26, fn=draw_poopy),
    "cronen_walker": dict(size=(70, 64), anchor=35, fn=draw_cronen),
    "cronen_flyer": dict(size=(70, 62), anchor=35, fn=draw_cronen_flyer),
    "gromflomite": dict(size=(80, 92), anchor=32, fn=draw_grom),
    "fed_drone": dict(size=(64, 34), anchor=32, fn=draw_drone),
    "citadel_drone": dict(size=(64, 34), anchor=32, fn=lambda p, s, f, a: draw_drone(p, s, f, a, citadel=True)),
    "rat": dict(size=(70, 40), anchor=34, fn=draw_rat),
    "roach": dict(size=(48, 34), anchor=24, fn=draw_roach),
}

_SPRITE_CACHE = {}


def render_sprite(kind, st="idle", fr=0, aim=0, scale=1.0):
    d = SPRITES[kind]
    w, h = d["size"]
    k = SS * scale
    big = pygame.Surface((int(w * k), int(h * k)), pygame.SRCALPHA)
    d["fn"](Pen(big, k), st, fr, aim)
    return pygame.transform.smoothscale(big, (int(w * scale), int(h * scale)))


def get_sprite(kind, st="idle", fr=0, aim=0, facing=1):
    key = (kind, st, fr, aim, facing)
    s = _SPRITE_CACHE.get(key)
    if s is None:
        s = render_sprite(kind, st, fr, aim)
        if facing < 0:
            s = pygame.transform.flip(s, True, False)
        _SPRITE_CACHE[key] = s
    return s


def blit_sprite(surf, kind, st, fr, aim, facing, foot_x, foot_y, alpha=None):
    d = SPRITES[kind]
    s = get_sprite(kind, st, fr, aim, facing)
    ax = d["anchor"] if facing > 0 else d["size"][0] - d["anchor"]
    pos = (int(foot_x - ax), int(foot_y - d["size"][1] + 2))
    if alpha is not None and alpha < 255:
        s = s.copy()
        s.set_alpha(alpha)
    surf.blit(s, pos)


# ---- Cromulon (boss finale): testa gigante ----
_CROM_CACHE = {}


def render_cromulon(mouth=False, glow=False, flash=False):
    key = (mouth, glow, flash)
    if key in _CROM_CACHE:
        return _CROM_CACHE[key]
    w, h = 340, 380
    big = pygame.Surface((w * SS, h * SS), pygame.SRCALPHA)
    p = Pen(big, SS)
    cx, cy = 170, 200
    SK, SKD = (226, 176, 150), (196, 140, 118)
    HAIR = (64, 44, 56)
    p.poly(HAIR, [(cx - 150, cy - 10), (cx - 160, cy - 110), (cx - 120, cy - 170), (cx - 40, cy - 192),
                  (cx + 50, cy - 192), (cx + 125, cy - 168), (cx + 160, cy - 110), (cx + 150, cy - 10)], 2.5)
    p.ell(SK, cx - 140, cy + 10, 22, 40, 2.5)
    p.ell(SK, cx + 140, cy + 10, 22, 40, 2.5)
    p.ell(SKD, cx - 140, cy + 10, 10, 22, 0)
    p.ell(SKD, cx + 140, cy + 10, 10, 22, 0)
    p.ell(SK, cx, cy, 138, 168, 2.6)
    p.poly(HAIR, [(cx - 136, cy - 60), (cx - 128, cy - 130), (cx - 70, cy - 168), (cx + 70, cy - 168),
                  (cx + 128, cy - 130), (cx + 136, cy - 60), (cx + 110, cy - 100), (cx + 40, cy - 118),
                  (cx - 40, cy - 118), (cx - 110, cy - 100)], 2.4)
    for side in (-1, 1):
        ex = cx + side * 55
        p.poly(SKD, [(ex - 42, cy - 62), (ex + 42, cy - 62), (ex + 36, cy - 48), (ex - 36, cy - 48)], 2.0)
        p.ell(WHITE, ex, cy - 22, 34, 25, 2.4)
        iris = (255, 70, 40) if glow else (70, 130, 200)
        p.circ(iris, ex + side * 2, cy - 20, 13, 2.0)
        p.circ((255, 240, 200) if glow else OUTLINE, ex + side * 2, cy - 20, 6, 0)
        p.circ(WHITE, ex - 6, cy - 27, 3.5, 0)
        p.lines(OUTLINE, [(ex - 30, cy + 8), (ex, cy + 14), (ex + 30, cy + 8)], 1.6)
    p.poly(SKD, [(cx - 6, cy - 10), (cx + 6, cy - 10), (cx + 26, cy + 50), (cx, cy + 58), (cx - 26, cy + 50)], 2.2)
    p.ell(OUTLINE, cx - 11, cy + 52, 5, 3, 0)
    p.ell(OUTLINE, cx + 11, cy + 52, 5, 3, 0)
    if mouth:
        p.ell((80, 20, 30), cx, cy + 100, 60, 36, 2.6)
        p.ell((220, 90, 100), cx, cy + 118, 34, 14, 0)
        for tx in range(-44, 50, 14):
            p.poly(WHITE, [(cx + tx - 6, cy + 70), (cx + tx + 6, cy + 70), (cx + tx, cy + 82)], 1.0)
    else:
        p.poly((190, 110, 110), [(cx - 62, cy + 96), (cx, cy + 86), (cx + 62, cy + 96), (cx, cy + 110)], 2.2)
        p.line(OUTLINE, (cx - 62, cy + 96), (cx + 62, cy + 96), 2.0)
    p.lines(OUTLINE, [(cx - 30, cy + 150), (cx, cy + 156), (cx + 30, cy + 150)], 1.8)
    s = pygame.transform.smoothscale(big, (w, h))
    if flash:
        s.fill((120, 120, 120), special_flags=pygame.BLEND_RGB_ADD)
    _CROM_CACHE[key] = s
    return s


# ---- oggetti raccoglibili ----
_ITEM_CACHE = {}


def item_sprite(kind, frame=0):
    key = (kind, frame)
    if key in _ITEM_CACHE:
        return _ITEM_CACHE[key]
    if kind == "coin":
        w, h = 22, 22
    elif kind == "seed":
        w, h = 30, 38
    elif kind == "flask":
        w, h = 26, 34
    elif kind == "fluid":
        w, h = 22, 36
    else:
        w, h = 36, 34
    big = pygame.Surface((w * SS, h * SS), pygame.SRCALPHA)
    p = Pen(big, SS)
    if kind == "coin":
        k = abs(math.cos(frame / 8 * math.pi))
        rx = max(1.5, 9 * k)
        p.ell((250, 206, 60), 11, 11, rx, 9, 1.4)
        if k > 0.4:
            p.ell((255, 236, 130), 11, 11, rx * 0.62, 5.6, 1.0)
            p.lines(OUTLINE, [(11 + 2 * k, 8), (11 - 2 * k, 9.5), (11 + 2 * k, 12.5), (11 - 2 * k, 14)], 1.1)
    elif kind == "seed":
        p.ell((248, 206, 58), 15, 19, 9.5, 15, 1.6)
        p.ell((255, 240, 150), 12, 14, 3, 6, 0)
        p.lines((200, 150, 30), [(15, 6), (17, 19), (15, 32)], 1.3)
        p.ell((150, 230, 90), 15, 5, 4, 2.4, 1.1)
    elif kind == "flask":
        p.poly((182, 190, 200), [(4, 10), (22, 10), (23, 30), (3, 30)], 1.5)
        p.poly((150, 158, 170), [(9, 3), (17, 3), (17, 10), (9, 10)], 1.3)
        p.poly((210, 216, 224), [(6, 13), (10, 13), (9, 27), (6, 27)], 0)
        p.line(OUTLINE, (4, 22), (22, 22), 0.8)
    elif kind == "fluid":
        p.poly((130, 138, 150), [(4, 2), (18, 2), (18, 7), (4, 7)], 1.3)
        p.poly((130, 138, 150), [(4, 29), (18, 29), (18, 34), (4, 34)], 1.3)
        p.poly((90, 240, 70), [(5, 7), (17, 7), (17, 29), (5, 29)], 1.3)
        p.poly((200, 255, 170), [(7, 9), (9, 9), (9, 27), (7, 27)], 0)
    else:  # scatola Meeseeks
        p.poly((70, 120, 210), [(4, 12), (32, 12), (32, 32), (4, 32)], 1.6)
        p.poly((100, 150, 230), [(4, 12), (32, 12), (28, 7), (8, 7)], 1.4)
        p.ell((90, 140, 230), 18, 7, 6, 2.8, 1.2)
        p.ell((250, 240, 120), 18, 5.5, 4, 2.2, 1.2)
        p.lines(WHITE, [(10, 18), (26, 18)], 1.3)
        p.lines(WHITE, [(10, 23), (22, 23)], 1.3)
    s = pygame.transform.smoothscale(big, (w, h))
    _ITEM_CACHE[key] = s
    return s


# ---- portale verde a spirale ----
_PORTAL_CACHE = {}
PORTAL_FRAMES = 16


def portal_frame(rx, ry, frame):
    key = (rx, ry, frame)
    if key in _PORTAL_CACHE:
        return _PORTAL_CACHE[key]
    s = SS
    w, h = int((rx * 2 + 8) * s), int((ry * 2 + 8) * s)
    big = pygame.Surface((w, h), pygame.SRCALPHA)
    cx, cy = w / 2, h / 2
    layers = [(1.0, (34, 120, 30)), (0.93, (66, 186, 46)), (0.8, (120, 236, 70)),
              (0.55, (176, 252, 110)), (0.3, (222, 255, 180))]
    for k, col in layers:
        r = pygame.Rect(0, 0, rx * 2 * s * k, ry * 2 * s * k)
        r.center = (cx, cy)
        pygame.draw.ellipse(big, col, r)
    rot_a = frame / PORTAL_FRAMES * 2 * math.pi
    for arm in range(5):
        pts = []
        for i in range(26):
            u = i / 25
            ang = -rot_a + arm * 2 * math.pi / 5 + u * 3.6
            r = 0.96 - u * 0.9
            pts.append((cx + math.cos(ang) * r * rx * s, cy + math.sin(ang) * r * ry * s))
        pygame.draw.lines(big, (30, 140, 30), False, pts, max(2, int(2.2 * s)))
        pygame.draw.lines(big, (236, 255, 190), False, [(x + s, y) for x, y in pts], max(1, int(1.0 * s)))
    r = pygame.Rect(0, 0, rx * 2 * s, ry * 2 * s)
    r.center = (cx, cy)
    pygame.draw.ellipse(big, (20, 80, 20), r, max(2, int(2 * s)))
    out = pygame.transform.smoothscale(big, (w // s, h // s))
    _PORTAL_CACHE[key] = out
    return out


def draw_portal(surf, x, y, rx, ry, t, scale=1.0, glow=True):
    if scale <= 0.02:
        return
    rx2, ry2 = max(3, int(rx * scale)), max(3, int(ry * scale))
    fr = int(t * 18) % PORTAL_FRAMES
    if glow:
        draw_glow(surf, x, y, int(max(rx2, ry2) * 1.7), (50, 160, 40))
    if scale >= 0.99:
        img = portal_frame(rx, ry, fr)
    else:
        img = pygame.transform.smoothscale(portal_frame(rx, ry, fr), (rx2 * 2 + 8, ry2 * 2 + 8))
    surf.blit(img, (int(x - img.get_width() / 2), int(y - img.get_height() / 2)))


# ---- ritratti per i dialoghi ----
_PORTRAIT_CACHE = {}
PORTRAIT_SPEC = {
    # tipo sprite, scala, rettangolo testa (in unita' di design)
    "rick": ("rick", 3.2, (14, 0, 46, 46)),
    "morty": ("morty", 3.0, (10, 4, 44, 42)),
    "pickle": ("pickle", 3.0, (12, 10, 44, 44)),
    "meeseeks": ("meeseeks", 3.0, (10, 0, 40, 42)),
    "poopy": ("poopy", 2.8, (4, 6, 44, 44)),
    "guard": ("guard", 3.2, (14, 0, 46, 46)),
}


def portrait(who, size):
    key = (who, size)
    if key in _PORTRAIT_CACHE:
        return _PORTRAIT_CACHE[key]
    if who == "cromulon":
        img = render_cromulon(mouth=True)
        img = pygame.transform.smoothscale(img, (size, int(size * img.get_height() / img.get_width())))
        out = pygame.Surface((size, size), pygame.SRCALPHA)
        out.blit(img, (0, (size - img.get_height()) // 2 + size // 10))
    else:
        kind, sc, (x, y, w, h) = PORTRAIT_SPEC[who]
        full = render_sprite(kind, "idle", 0, 0, scale=sc)
        sub = full.subsurface(pygame.Rect(int(x * sc), int(y * sc), int(w * sc), int(h * sc)).clip(full.get_rect()))
        out = pygame.transform.smoothscale(sub, (size, size))
    _PORTRAIT_CACHE[key] = out
    return out


# =============================================================================
#  MONDI: temi, tile, sfondi a parallasse
# =============================================================================
THEMES = {
    "cronenberg": dict(seed=11, sky=[(0, (36, 16, 30)), (0.5, (140, 58, 50)), (0.82, (226, 128, 70)), (1, (240, 170, 96))],
                       vignette=150, dark=0, title_col=(255, 170, 150)),
    "federation": dict(seed=22, sky=[(0, (8, 10, 34)), (0.55, (52, 30, 96)), (1, (150, 72, 140))],
                       vignette=140, dark=0, title_col=(150, 200, 255)),
    "sewer": dict(seed=33, sky=[(0, (16, 20, 14)), (1, (30, 36, 24))], vignette=120, dark=175,
                  title_col=(150, 255, 120)),
    "citadel": dict(seed=44, sky=[(0, (4, 4, 14)), (0.7, (14, 24, 52)), (1, (30, 50, 90))],
                    vignette=130, dark=0, title_col=(140, 240, 255)),
    "arena": dict(seed=55, sky=[(0, (16, 6, 32)), (0.5, (74, 24, 84)), (0.85, (180, 76, 118)), (1, (230, 120, 120))],
                  vignette=150, dark=0, title_col=(255, 150, 230)),
}


def _tile_base(theme, rng):
    s = pygame.Surface((TILE, TILE))
    if theme == "cronenberg":
        s.fill((92, 38, 46))
        for _ in range(7):
            pygame.draw.ellipse(s, (72, 28, 36), (rng.randint(-6, 40), rng.randint(-6, 40), rng.randint(8, 18), rng.randint(6, 14)))
        for _ in range(2):
            x, y = rng.randint(0, 48), rng.randint(0, 48)
            pts = [(x, y)]
            for _ in range(4):
                x += rng.randint(-12, 12)
                y += rng.randint(-12, 12)
                pts.append((x, y))
            pygame.draw.lines(s, (150, 58, 72), False, pts, 2)
    elif theme == "federation":
        s.fill((54, 60, 86))
        pygame.draw.rect(s, (40, 44, 66), (0, 0, TILE, TILE), 2)
        pygame.draw.line(s, (70, 78, 108), (2, 2), (45, 2), 1)
        for x, y in ((6, 6), (41, 6), (6, 41), (41, 41)):
            pygame.draw.circle(s, (100, 108, 140), (x, y), 2)
        pygame.draw.line(s, (44, 50, 72), (0, 24), (48, 24), 1)
    elif theme == "sewer":
        s.fill((44, 38, 32))
        for row in range(4):
            off = 0 if row % 2 == 0 else 12
            for col in range(-1, 3):
                c = rng.randint(64, 82)
                pygame.draw.rect(s, (c, c - 12, c - 24), (col * 24 + off + 1, row * 12 + 1, 22, 10))
    elif theme == "citadel":
        s.fill((176, 186, 204))
        pygame.draw.rect(s, (140, 150, 170), (0, 0, TILE, TILE), 2)
        pygame.draw.line(s, (200, 210, 226), (3, 3), (44, 3), 2)
        pygame.draw.line(s, (150, 160, 180), (24, 4), (24, 44), 1)
    else:
        s.fill((48, 34, 66))
        for _ in range(4):
            x, y = rng.randint(4, 44), rng.randint(4, 44)
            pygame.draw.polygon(s, (110, 70, 150), [(x, y - 5), (x + 3, y), (x, y + 5), (x - 3, y)])
        for _ in range(5):
            pygame.draw.circle(s, (38, 26, 52), (rng.randint(0, 48), rng.randint(0, 48)), rng.randint(3, 7))
    return s


def _tile_top(theme, base, rng):
    s = base.copy()
    if theme == "cronenberg":
        pygame.draw.rect(s, (214, 118, 118), (0, 0, TILE, 13))
        for x in range(0, TILE + 8, 8):
            pygame.draw.circle(s, (214, 118, 118), (x, 12), 6)
        pygame.draw.line(s, (240, 162, 150), (0, 2), (TILE, 2), 2)
        for x in range(4, TILE, 12):
            pygame.draw.circle(s, (238, 150, 140), (x + rng.randint(-2, 2), 6), 2)
    elif theme == "federation":
        pygame.draw.rect(s, (30, 30, 40), (0, 0, TILE, 10))
        for x in range(-10, TILE + 10, 12):
            pygame.draw.polygon(s, (236, 196, 60), [(x, 10), (x + 6, 10), (x + 14, 0), (x + 8, 0)])
        pygame.draw.line(s, (170, 180, 220), (0, 10), (TILE, 10), 2)
    elif theme == "sewer":
        pygame.draw.rect(s, (64, 116, 46), (0, 0, TILE, 7))
        for x in range(2, TILE, 7):
            pygame.draw.rect(s, (64, 116, 46), (x, 6, 4, rng.randint(2, 9)))
        pygame.draw.line(s, (110, 170, 70), (0, 1), (TILE, 1), 2)
    elif theme == "citadel":
        pygame.draw.rect(s, (110, 120, 140), (0, 0, TILE, 7))
        pygame.draw.line(s, (90, 236, 255), (0, 2), (TILE, 2), 3)
    else:
        pygame.draw.rect(s, (96, 72, 122), (0, 0, TILE, 9))
        pygame.draw.line(s, (255, 96, 210), (0, 1), (TILE, 1), 3)
    return s


def _tile_oneway(theme):
    s = pygame.Surface((TILE, 16), pygame.SRCALPHA)
    if theme == "cronenberg":
        pygame.draw.rect(s, (226, 214, 186), (0, 2, TILE, 9), border_radius=4)
        pygame.draw.rect(s, OUTLINE, (0, 2, TILE, 9), 2, border_radius=4)
        pygame.draw.circle(s, (200, 120, 120), (12, 12), 3)
        pygame.draw.circle(s, (200, 120, 120), (36, 13), 2)
    elif theme == "federation":
        pygame.draw.rect(s, (96, 104, 134), (0, 0, TILE, 10))
        for x in range(4, TILE, 8):
            pygame.draw.rect(s, (40, 44, 60), (x, 3, 4, 4))
        pygame.draw.line(s, (236, 196, 60), (0, 0), (TILE, 0), 2)
        pygame.draw.circle(s, (120, 220, 255), (24, 12), 2)
    elif theme == "sewer":
        pygame.draw.rect(s, (124, 88, 54), (0, 0, TILE, 11))
        pygame.draw.line(s, (96, 66, 40), (0, 5), (TILE, 5), 1)
        pygame.draw.rect(s, OUTLINE, (0, 0, TILE, 11), 2)
        pygame.draw.circle(s, (170, 170, 170), (5, 5), 1)
        pygame.draw.circle(s, (170, 170, 170), (43, 5), 1)
    elif theme == "citadel":
        pygame.draw.rect(s, (150, 230, 255, 150), (0, 0, TILE, 10))
        pygame.draw.line(s, (230, 255, 255), (0, 1), (TILE, 1), 2)
        pygame.draw.rect(s, (60, 140, 180), (0, 0, TILE, 10), 1)
    else:
        pygame.draw.rect(s, (84, 84, 100), (0, 0, TILE, 11))
        for x in range(0, TILE, 12):
            pygame.draw.line(s, (50, 50, 64), (x, 1), (x + 12, 10), 2)
            pygame.draw.line(s, (50, 50, 64), (x + 12, 1), (x, 10), 2)
        pygame.draw.line(s, (255, 96, 210), (0, 0), (TILE, 0), 2)
    return s


def _acid_frames():
    frames = []
    for f in range(8):
        s = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
        for y in range(TILE):
            col = lerp_col((96, 236, 60), (24, 110, 20), y / TILE)
            pygame.draw.line(s, col, (0, y), (TILE, y))
        pts = [(x, 4 + math.sin((x / TILE + f / 8) * 2 * math.pi) * 3) for x in range(0, TILE + 1, 4)]
        pygame.draw.polygon(s, (0, 0, 0, 0), [(0, 0)] + pts + [(TILE, 0)])
        pygame.draw.lines(s, (190, 255, 140), False, pts, 3)
        rng = random.Random(f)
        for _ in range(3):
            pygame.draw.circle(s, (170, 255, 120), (rng.randint(4, 44), rng.randint(14, 44)), rng.randint(1, 3), 1)
        frames.append(s)
    return frames


def _deco(theme, rng):
    out = []
    for k in range(3):
        big = pygame.Surface((40 * SS, 40 * SS), pygame.SRCALPHA)
        p = Pen(big, SS)
        if theme == "cronenberg":
            if k == 0:
                p.chain((214, 118, 118), [(20, 40), (18, 30), (22, 20), (19, 12)], 3.5, 1.2)
                p.circ(WHITE, 19, 10, 5, 1.3)
                p.circ((180, 40, 40), 20.5, 10, 2.2, 0)
            elif k == 1:
                p.chain((200, 104, 110), [(10, 40), (8, 30), (14, 22), (10, 14), (16, 8)], 4, 1.2)
                p.chain((200, 104, 110), [(28, 40), (30, 32), (26, 26)], 3.5, 1.2)
            else:
                p.ell((226, 140, 130), 20, 36, 12, 6, 1.3)
                p.circ((250, 200, 160), 16, 34, 2.5, 0.8)
                p.circ((250, 200, 160), 24, 35, 2, 0.8)
        elif theme == "federation":
            if k == 0:
                p.poly((70, 76, 100), [(18, 12), (22, 12), (22, 40), (18, 40)], 1.2)
                p.ell((255, 220, 120), 20, 10, 5, 4, 1.2)
            elif k == 1:
                p.poly((90, 96, 120), [(6, 22), (34, 22), (34, 40), (6, 40)], 1.4)
                p.line((236, 196, 60), (6, 28), (34, 28), 2)
            else:
                p.poly((60, 66, 90), [(12, 30), (28, 30), (30, 40), (10, 40)], 1.2)
                p.circ((120, 220, 255), 20, 27, 3, 1.0)
        elif theme == "sewer":
            if k == 0:
                for mx, mh in ((12, 10), (20, 16), (28, 8)):
                    p.limb((220, 210, 180), (mx, 40), (mx, 40 - mh), 2.5, 1.0)
                    p.ell((140, 200, 80), mx, 40 - mh, 5, 3, 1.1)
            elif k == 1:
                p.limb((230, 224, 200), (8, 38), (30, 34), 3, 1.1)
                p.circ((230, 224, 200), 8, 38, 3, 1.1)
                p.circ((230, 224, 200), 30, 34, 3, 1.1)
            else:
                p.ell((90, 170, 60), 20, 38, 14, 3, 1.0)
        elif theme == "citadel":
            if k == 0:
                p.poly((200, 210, 226), [(16, 24), (24, 24), (24, 40), (16, 40)], 1.2)
                p.ell((90, 236, 255), 20, 24, 5, 3, 1.0)
            elif k == 1:
                p.poly((150, 110, 80), [(12, 30), (28, 30), (26, 40), (14, 40)], 1.2)
                p.circ((90, 170, 80), 20, 24, 8, 1.2)
            else:
                p.poly((140, 150, 170), [(8, 34), (32, 34), (32, 40), (8, 40)], 1.0)
        else:
            if k == 0:
                p.poly((40, 40, 50), [(8, 16), (32, 16), (32, 40), (8, 40)], 1.4)
                p.circ((90, 90, 110), 20, 24, 6, 1.2)
                p.circ((90, 90, 110), 20, 35, 3.5, 1.0)
            elif k == 1:
                p.poly((255, 96, 210), [(20, 14), (26, 40), (14, 40)], 1.2)
            else:
                p.poly((120, 230, 255), [(16, 22), (24, 22), (28, 40), (12, 40)], 1.2)
        out.append(pygame.transform.smoothscale(big, (40, 40)))
    return out


class TileSet:
    def __init__(self, theme):
        rng = random.Random(THEMES[theme]["seed"])
        self.inner = [_tile_base(theme, rng).convert() for _ in range(3)]
        self.top = [_tile_top(theme, _tile_base(theme, rng), rng).convert() for _ in range(3)]
        self.oneway = _tile_oneway(theme).convert_alpha()
        self.acid = [f.convert_alpha() for f in _acid_frames()]
        self.deco = [d.convert_alpha() for d in _deco(theme, rng)]


class Background:
    LW = 1600

    def __init__(self, theme):
        self.theme = theme
        cfg = THEMES[theme]
        rng = random.Random(cfg["seed"] * 7)
        self.rng = rng
        self.sky = vertical_gradient(W, H, cfg["sky"]).convert()
        self.far = pygame.Surface((self.LW, H), pygame.SRCALPHA)
        self.mid = pygame.Surface((self.LW, H), pygame.SRCALPHA)
        getattr(self, "_build_" + theme)(rng)
        self.far = self.far.convert_alpha()
        self.mid = self.mid.convert_alpha()
        self.ambient = []
        for _ in range(40):
            self.ambient.append([rng.uniform(0, W), rng.uniform(0, H), rng.uniform(0.3, 1.0), rng.uniform(0, 6.28)])
        self.ships = [[rng.uniform(0, W), rng.uniform(90, 300), rng.uniform(40, 120) * rng.choice((-1, 1))]
                      for _ in range(4)]

    def _stars(self, n, rng, maxy=H):
        for _ in range(n):
            x, y = rng.randint(0, W), rng.randint(0, maxy)
            b = rng.randint(120, 255)
            self.sky.set_at((x, y), (b, b, b))
            if rng.random() < 0.12:
                pygame.draw.circle(self.sky, (b, b, min(255, b + 20)), (x, y), 1)

    def _build_cronenberg(self, rng):
        draw_glow(self.sky, 930, 420, 260, (120, 60, 20))
        pygame.draw.circle(self.sky, (252, 196, 120), (930, 420), 70)
        x = 0
        while x < self.LW - 60:
            bw = rng.randint(50, 120)
            if x + bw > self.LW:
                break
            bh = rng.randint(160, 400)
            top = 640 - bh
            pts = [(x, 640), (x, top + rng.randint(0, 30))]
            for k in range(1, 5):
                pts.append((x + bw * k / 5, top + rng.randint(-10, 40)))
            pts += [(x + bw, top + rng.randint(0, 30)), (x + bw, 640)]
            pygame.draw.polygon(self.far, (78, 30, 40), pts)
            for wy in range(top + 30, 620, 22):
                for wx in range(x + 8, x + bw - 10, 16):
                    if rng.random() < 0.35:
                        col = (232, 140, 70) if rng.random() < 0.3 else (110, 50, 50)
                        pygame.draw.rect(self.far, col, (wx, wy, 7, 10))
            x += bw + rng.randint(10, 60)
        pygame.draw.rect(self.far, (78, 30, 40), (0, 630, self.LW, H))
        pts = [(0, H)]
        for x in range(0, self.LW + 1, 20):
            y = 560 + math.sin(x / self.LW * 2 * math.pi * 3) * 30 + math.sin(x / self.LW * 2 * math.pi * 7) * 14
            pts.append((x, y))
        pts.append((self.LW, H))
        pygame.draw.polygon(self.mid, (122, 48, 60), pts)
        for _ in range(9):
            tx = rng.randint(40, self.LW - 40)
            ty = 570
            seg = [(tx, ty)]
            for k in range(6):
                seg.append((tx + math.sin(k * 0.9 + tx) * 18, ty - 30 - k * 26))
            pygame.draw.lines(self.mid, (140, 58, 72), False, seg, 14)
            pygame.draw.lines(self.mid, (160, 70, 84), False, seg, 6)
            pygame.draw.circle(self.mid, (240, 236, 220), (int(seg[-1][0]), int(seg[-1][1])), 9)
            pygame.draw.circle(self.mid, (160, 30, 30), (int(seg[-1][0]) + 2, int(seg[-1][1])), 4)
        for _ in range(30):
            pygame.draw.circle(self.mid, (170, 80, 90), (rng.randint(0, self.LW), rng.randint(590, 700)), rng.randint(4, 12))

    def _build_federation(self, rng):
        self._stars(160, rng, 420)
        pygame.draw.circle(self.sky, (200, 190, 240), (220, 150), 46)
        pygame.draw.circle(self.sky, (170, 160, 220), (205, 140), 12)
        pygame.draw.circle(self.sky, (240, 200, 160), (1040, 110), 22)
        x = 0
        while x < self.LW - 60:
            bw = rng.randint(40, 90)
            if x + bw > self.LW:
                break
            bh = rng.randint(200, 480)
            top = 650 - bh
            pygame.draw.rect(self.far, (28, 28, 66), (x, top, bw, bh + 80), border_top_left_radius=bw // 3,
                             border_top_right_radius=bw // 3)
            pygame.draw.line(self.far, (28, 28, 66), (x + bw // 2, top), (x + bw // 2, top - 40), 3)
            pygame.draw.circle(self.far, (255, 60, 60), (x + bw // 2, top - 40), 3)
            for wy in range(top + 20, 640, 14):
                for wx in range(x + 6, x + bw - 6, 10):
                    if rng.random() < 0.3:
                        pygame.draw.rect(self.far, rng.choice(((255, 220, 120), (120, 220, 255), (90, 90, 160))), (wx, wy, 4, 6))
            x += bw + rng.randint(10, 40)
        for _ in range(6):
            dx = rng.randint(0, self.LW - 200)
            pygame.draw.ellipse(self.mid, (46, 52, 96), (dx, 520, 200, 160))
            pygame.draw.ellipse(self.mid, (70, 80, 130), (dx + 30, 540, 60, 30))
            for k in range(5):
                pygame.draw.circle(self.mid, (255, 220, 120), (dx + 30 + k * 34, 610), 3)
        pygame.draw.rect(self.mid, (40, 44, 82), (0, 620, self.LW, 100))
        for x in range(0, self.LW, 80):
            pygame.draw.rect(self.mid, (56, 62, 110), (x, 600, 12, 40))
            pygame.draw.circle(self.mid, (120, 220, 255), (x + 6, 598), 4)

    def _build_sewer(self, rng):
        self.sky.fill((22, 22, 18))
        for row in range(0, H, 24):
            off = 0 if (row // 24) % 2 == 0 else 24
            for col in range(-1, W // 48 + 2):
                c = rng.randint(30, 40)
                pygame.draw.rect(self.sky, (c, c - 2, c - 8), (col * 48 + off + 1, row + 1, 46, 22))
        for k in range(4):
            ax = 120 + k * 400
            pygame.draw.ellipse(self.far, (10, 12, 8), (ax, 260, 260, 420))
            pygame.draw.ellipse(self.far, (60, 56, 44), (ax, 260, 260, 420), 10)
            pygame.draw.rect(self.far, (14, 30, 12), (ax + 20, 560, 220, 120))
        for y in (150, 330):
            pygame.draw.rect(self.mid, (58, 76, 60), (0, y, self.LW, 34))
            pygame.draw.line(self.mid, (84, 104, 84), (0, y + 6), (self.LW, y + 6), 3)
            for x in range(0, self.LW, 160):
                pygame.draw.rect(self.mid, (46, 60, 48), (x, y - 5, 18, 44))
        for x in range(90, self.LW, 330):
            pygame.draw.rect(self.mid, (66, 84, 64), (x, 0, 30, 560))
            pygame.draw.rect(self.mid, (90, 70, 40), (x + 4, 200 + rng.randint(0, 200), 22, 30))

    def _build_citadel(self, rng):
        self._stars(260, rng)
        for _ in range(4):
            draw_glow(self.sky, rng.randint(0, W), rng.randint(0, 500), rng.randint(140, 260),
                      rng.choice(((60, 30, 90), (20, 50, 90), (70, 20, 60))))
        cx, cy = 800, 300
        for k in range(14):
            a = k / 14 * 2 * math.pi
            x2, y2 = cx + math.cos(a) * 330, cy + math.sin(a) * 220
            pygame.draw.line(self.far, (120, 130, 150), (cx, cy), (x2, y2), 10)
            pygame.draw.circle(self.far, (150, 160, 180), (int(x2), int(y2)), 16)
            pygame.draw.circle(self.far, (120, 230, 255), (int(x2), int(y2)), 5)
        pygame.draw.ellipse(self.far, (100, 110, 130), (cx - 260, cy - 30, 520, 60), 8)
        pygame.draw.circle(self.far, (170, 180, 198), (cx, cy), 140)
        pygame.draw.circle(self.far, (196, 206, 222), (cx - 30, cy - 30), 90)
        for k in range(30):
            a = rng.uniform(0, 6.28)
            r = rng.uniform(20, 130)
            pygame.draw.circle(self.far, (255, 240, 170), (int(cx + math.cos(a) * r), int(cy + math.sin(a) * r)), 2)
        for x in range(0, self.LW, 200):
            pygame.draw.rect(self.mid, (120, 130, 152), (x, 430, 24, 300))
            pygame.draw.rect(self.mid, (150, 160, 180), (x - 10, 420, 44, 16))
            pygame.draw.circle(self.mid, (90, 236, 255), (x + 12, 470), 5)
        pygame.draw.rect(self.mid, (110, 120, 142), (0, 520, self.LW, 10))
        pygame.draw.line(self.mid, (90, 236, 255), (0, 524), (self.LW, 524), 2)

    def _build_arena(self, rng):
        self._stars(180, rng, 400)
        draw_glow(self.sky, 640, 780, 520, (140, 50, 80))
        pygame.draw.circle(self.sky, (210, 110, 120), (640, 1180), 560)
        pygame.draw.circle(self.sky, (230, 140, 140), (640, 1180), 560, 6)
        for k, (hx, hy, s) in enumerate(((180, 210, 0.45), (1100, 190, 0.5), (1420, 240, 0.35))):
            img = render_cromulon(mouth=(k == 1))
            img = pygame.transform.smoothscale(img, (int(img.get_width() * s), int(img.get_height() * s)))
            img.set_alpha(70)
            self.far.blit(img, (hx - img.get_width() // 2, hy - img.get_height() // 2))
        for x in (60, 1260):
            pygame.draw.rect(self.mid, (40, 36, 52), (x, 300, 40, 340))
            for y in range(300, 640, 30):
                pygame.draw.line(self.mid, (70, 64, 90), (x, y), (x + 40, y + 30), 3)
            pygame.draw.rect(self.mid, (28, 26, 36), (x - 30, 520, 100, 120))
            pygame.draw.circle(self.mid, (70, 66, 86), (x + 20, 560), 26)
            pygame.draw.circle(self.mid, (70, 66, 86), (x + 20, 615), 14)
        pygame.draw.rect(self.mid, (40, 36, 52), (0, 290, self.LW, 14))

    def draw(self, surf, cam_x, t):
        surf.blit(self.sky, (0, 0))
        if self.theme in ("federation", "citadel"):
            for s in self.ships:
                s[0] += s[2] / 60.0
                if s[0] < -80:
                    s[0] = W + 80
                elif s[0] > W + 80:
                    s[0] = -80
                x, y = int(s[0]), int(s[1])
                col = (90, 96, 140) if self.theme == "federation" else (200, 210, 225)
                pygame.draw.ellipse(surf, col, (x - 18, y - 4, 36, 9))
                pygame.draw.ellipse(surf, (150, 220, 255), (x - 7, y - 9, 14, 8))
                if int(t * 4) % 2 == 0:
                    pygame.draw.circle(surf, (255, 80, 70), (x + (15 if s[2] > 0 else -15), y), 2)
        for layer, f in ((self.far, 0.15), (self.mid, 0.42)):
            off = -(cam_x * f) % self.LW
            surf.blit(layer, (int(off - self.LW), 0))
            surf.blit(layer, (int(off), 0))
        if self.theme == "arena":
            if not hasattr(self, "_beam"):
                self._beam = pygame.Surface((W, H)).convert()
            beam = self._beam
            beam.fill(BLACK)
            for k in range(3):
                ang = math.sin(t * 0.7 + k * 2.1) * 0.5
                bx = 200 + k * 440
                tip1 = (bx + math.sin(ang - 0.12) * 900, 300 + math.cos(ang - 0.12) * 900)
                tip2 = (bx + math.sin(ang + 0.12) * 900, 300 + math.cos(ang + 0.12) * 900)
                pygame.draw.polygon(beam, (40, 18, 40), [(bx, 300), tip1, tip2])
            surf.blit(beam, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
        self._ambient(surf, t)

    def _ambient(self, surf, t):
        th = self.theme
        for a in self.ambient:
            if th == "cronenberg":
                a[1] -= 14 * a[2] / 60
                a[0] += math.sin(t + a[3]) * 0.3
                if a[1] < -10:
                    a[1] = H + 10
                pygame.draw.circle(surf, (255, 190, 170), (int(a[0]), int(a[1])), 1 + int(a[2] * 2))
            elif th == "sewer":
                a[1] += 260 * a[2] / 60
                if a[1] > H:
                    a[1] = -10
                    a[0] = self.rng.uniform(0, W)
                pygame.draw.line(surf, (120, 200, 110), (int(a[0]), int(a[1])), (int(a[0]), int(a[1]) + 6), 2)
            elif th == "citadel":
                b = int(120 + 120 * (0.5 + 0.5 * math.sin(t * 3 + a[3])))
                surf.set_at((int(a[0]), int(a[1] * 0.7)), (b, b, 255))
            elif th == "arena":
                a[1] += 40 * a[2] / 60
                a[0] += math.sin(t * 2 + a[3]) * 0.6
                if a[1] > H:
                    a[1] = -10
                col = ((255, 120, 220), (120, 230, 255), (255, 230, 120))[int(a[3] * 10) % 3]
                pygame.draw.rect(surf, col, (int(a[0]), int(a[1]), 3, 5))


def build_garage():
    """Il garage di Rick: sfondo dell'hub."""
    s = vertical_gradient(W, H, [(0, (70, 66, 62)), (0.62, (118, 108, 96)), (0.621, (84, 78, 74)), (1, (52, 48, 46))])
    rng = random.Random(137)
    for x in range(0, W, 96):
        pygame.draw.line(s, (96, 88, 80), (x, 0), (x, 446), 2)
    for _ in range(14):
        pygame.draw.ellipse(s, (64, 60, 56), (rng.randint(0, W), rng.randint(470, 700), rng.randint(40, 140), rng.randint(10, 26)))
    # porta del garage
    pygame.draw.rect(s, (150, 146, 136), (40, 120, 330, 330))
    for y in range(130, 450, 26):
        pygame.draw.line(s, (112, 108, 100), (40, y), (370, y), 3)
    pygame.draw.rect(s, OUTLINE, (40, 120, 330, 330), 4)
    # scaffale con barattoli
    pygame.draw.rect(s, (110, 80, 54), (440, 140, 280, 14))
    pygame.draw.rect(s, (110, 80, 54), (440, 240, 280, 14))
    for shelf_y in (140, 240):
        x = 452
        while x < 700:
            w = rng.randint(18, 40)
            h = rng.randint(24, 60)
            col = rng.choice(((200, 60, 60), (70, 140, 200), (230, 200, 80), (90, 180, 90), (180, 180, 190)))
            pygame.draw.rect(s, col, (x, shelf_y - h, w, h))
            pygame.draw.rect(s, OUTLINE, (x, shelf_y - h, w, h), 2)
            x += w + rng.randint(4, 12)
    # banco da lavoro
    pygame.draw.rect(s, (126, 92, 60), (780, 330, 420, 22))
    pygame.draw.rect(s, OUTLINE, (780, 330, 420, 22), 3)
    for lx in (800, 1170):
        pygame.draw.rect(s, (96, 70, 46), (lx, 352, 16, 110))
    pygame.draw.rect(s, (60, 64, 70), (820, 280, 90, 50))
    pygame.draw.rect(s, (90, 236, 120), (830, 290, 70, 30))
    for k in range(5):
        pygame.draw.line(s, (40, 120, 60), (832, 296 + k * 5), (898, 296 + k * 5), 1)
    pygame.draw.rect(s, OUTLINE, (820, 280, 90, 50), 3)
    for k in range(4):
        x = 950 + k * 50
        pygame.draw.rect(s, (90, 240, 70), (x, 296, 14, 34))
        pygame.draw.rect(s, (150, 150, 160), (x - 2, 290, 18, 8))
        pygame.draw.rect(s, OUTLINE, (x, 296, 14, 34), 2)
    pygame.draw.rect(s, (60, 60, 64), (790, 90, 400, 160))
    for k in range(9):
        pygame.draw.line(s, (90, 90, 96), (800 + k * 44, 100), (800 + k * 44, 240), 2)
    for (tx, ty) in ((820, 120), (880, 150), (980, 110), (1080, 160), (1140, 120)):
        pygame.draw.rect(s, (160, 164, 176), (tx, ty, 10, 46))
        pygame.draw.rect(s, (200, 60, 60), (tx - 4, ty + 40, 18, 24))
    # navicella spaziale di Rick
    pygame.draw.ellipse(s, (40, 38, 36), (380, 520, 400, 40))
    pygame.draw.ellipse(s, (150, 160, 166), (400, 440, 360, 100))
    pygame.draw.ellipse(s, OUTLINE, (400, 440, 360, 100), 4)
    pygame.draw.ellipse(s, (120, 126, 132), (430, 500, 300, 34))
    pygame.draw.ellipse(s, (160, 220, 230), (500, 400, 160, 80))
    pygame.draw.ellipse(s, OUTLINE, (500, 400, 160, 80), 3)
    pygame.draw.ellipse(s, (220, 250, 255), (530, 412, 50, 20))
    for k in range(5):
        pygame.draw.circle(s, (255, 200, 80), (450 + k * 64, 492), 7)
        pygame.draw.circle(s, OUTLINE, (450 + k * 64, 492), 7, 2)
    # lampada
    pygame.draw.line(s, (40, 40, 40), (640, 0), (640, 60), 3)
    pygame.draw.polygon(s, (60, 70, 60), [(610, 60), (670, 60), (690, 84), (590, 84)])
    cone = pygame.Surface((W, H))
    cone.fill(BLACK)
    pygame.draw.polygon(cone, (50, 46, 30), [(600, 84), (680, 84), (900, 700), (380, 700)])
    s.blit(cone, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
    return s.convert()


# =============================================================================
#  LIVELLI: costruiti unendo "pezzi" disegnati a mano (15 righe ciascuno)
#   #=terreno  ==piattaforma sottile  ~=acido  $=Schmeckle  m=posto per Mega Seme
#   e=nemico a terra  a=nemico volante  ?=oggetto  S=partenza  E=uscita  N=personaggio
# =============================================================================
CHUNK_START = [
    "..............", "..............", "..............", "..............", "..............",
    "..............", "..............", "..............", "..............", "..............",
    "..........$$..", "..S.....N.....", "##############", "##############", "##############",
]
CHUNK_END = [
    "................", "................", "................", "................", "................",
    "................", "................", "................", "................", "....$.$.$.......",
    "................", "...........E....", "################", "################", "################",
]
CHUNK_POOL = [
    [  # piatto con piattaforma
        "................", "................", "................", "................", "................",
        ".......a........", "................", "................", "......$$$$......", ".....======.....",
        "................", "..e.........e...", "################", "################", "################",
    ],
    [  # fossa d'acido
        "................", "................", "................", "................", "................",
        "................", "................", "................", ".......$$.......", "......====......",
        "................", "..e..........e..", "#####......#####", "#####......#####", "#####~~~~~~#####",
    ],
    [  # scalinata e torre
        "..................", "..................", "..................", "..................", ".............m....",
        "..................", "............####..", "..........a.####..", ".........$$.####..", "........####......",
        "....$$..####......", "...####.####...e..", "##################", "##################", "##################",
    ],
    [  # piattaforme sospese sull'acido
        "....................", "....................", "....................", "....................", "....................",
        "..........m.........", "....................", ".........===........", "....$.............$.", "...===....a.....===.",
        "....................", ".e..................", "####..............##", "####..............##", "####~~~~~~~~~~~~~~##",
    ],
    [  # arena con pilastri
        "..................", "..................", "..................", "..................", "..................",
        "....a.......a.....", "..................", ".......$$$$.......", "......======......", "..................",
        "..##..........##..", "..##..e....e..##..", "##################", "##################", "##################",
    ],
    [  # percorso alto
        "....................", "....................", "....................", ".........m..........", "........====........",
        "....................", "...$$..........$$...", "..====........====..", "....................", "....................",
        "...........?........", ".......e.......e....", "####################", "####################", "####################",
    ],
    [  # tunnel
        "..................", "..................", "..................", "..................", "..................",
        ".........m........", "..................", "....##########....", "....##########....", ".....$$.$$.$$.....",
        "..................", ".......e....?.....", "##################", "##################", "##################",
    ],
    [  # pilastri sull'acido
        ".....................", ".....................", ".....................", ".....................", ".....................",
        ".........m...........", ".....................", "....$$.....a.$$......", ".....................", "...####....####......",
        "...####....####......", "...####....####...e..", "#######....####...###", "#######....####...###", "#######~~~~####~~~###",
    ],
    [  # ponte di piattaforme
        "......................", "......................", "......................", "......................", "......................",
        "..........a...........", "......$......$........", ".....==.....==........", "......................", "..$......$......$.....",
        "..==.....==.....==....", "......................", "##..................##", "##..................##", "##~~~~~~~~~~~~~~~~~~##",
    ],
    [  # corridoio pericoloso
        "................", "................", "................", "................", "................",
        "................", "................", "................", "................", "....$$$..$$$....",
        "................", "..e....?....e...", "################", "################", "################",
    ],
    [  # muro
        "................", "................", "................", "................", "................",
        "................", "................", ".......$........", "................", "......###.......",
        "......###.......", "..?...###...e...", "################", "################", "################",
    ],
]
CHUNK_BOSS = [
    "...........................", "...........................", "...........................", "...........................",
    "...........................", "...........................", "...........................", "...........................",
    "...===...............===...", "...........................", "..........=======..........", ".S...........B.............",
    "###########################", "###########################", "###########################",
]


def _norm_chunk(rows):
    w = max(len(r) for r in rows)
    return [r + (r[-1] if r else ".") * (w - len(r)) for r in rows]


class Level:
    def __init__(self, ldef):
        rng = random.Random(ldef["seed"])
        self.ldef = ldef
        if ldef.get("boss"):
            chunks = [CHUNK_BOSS]
        else:
            chunks = [CHUNK_START]
            last = None
            for _ in range(ldef["chunks"]):
                c = rng.choice([c for c in CHUNK_POOL if c is not last])
                chunks.append(c)
                last = c
            chunks.append(CHUNK_END)
        rows = [""] * ROWS
        for c in chunks:
            c = _norm_chunk(c)
            for i in range(ROWS):
                rows[i] += c[i]
        self.wt = len(rows[0])
        self.pw = self.wt * TILE
        self.start = (100, 11 * TILE)
        self.exit = None
        self.npc = None
        self.boss = False
        self.spawns = []  # (tipo, x, y_piedi)
        seeds, coins = [], []
        grid = [list(r) for r in rows]
        for ty in range(ROWS):
            for tx in range(self.wt):
                ch = grid[ty][tx]
                cx, by = tx * TILE + TILE // 2, (ty + 1) * TILE
                if ch in "#=~.":
                    continue
                grid[ty][tx] = "."
                if ch == "S":
                    self.start = (cx, by)
                elif ch == "E":
                    self.exit = (cx, by)
                elif ch == "N":
                    self.npc = (cx, by)
                elif ch == "B":
                    self.boss = True
                elif ch == "e":
                    if rng.random() < ldef["enemy_p"]:
                        self.spawns.append((rng.choice(ldef["ground"]), cx, by))
                elif ch == "a":
                    if rng.random() < ldef["enemy_p"] * 0.9:
                        self.spawns.append((rng.choice(ldef["air"]), cx, by - 10))
                elif ch == "$":
                    coins.append((cx, ty * TILE + TILE // 2))
                elif ch == "m":
                    seeds.append((cx, ty * TILE + TILE // 2))
                elif ch == "?":
                    kind = rng.choices(("flask", "fluid", "box", "coin"), (4, 3, 2, 2))[0]
                    self.spawns.append((kind, cx, ty * TILE + TILE // 2))
        self.grid = ["".join(r) for r in grid]
        chosen = []
        if not ldef.get("boss"):
            seeds.sort()
            pool = seeds[:] if len(seeds) >= 3 else seeds + rng.sample(coins, 3 - len(seeds))
            pool.sort()
            n = len(pool)
            for k in range(3):
                part = pool[k * n // 3:(k + 1) * n // 3] or pool
                pick = rng.choice([p for p in part if p not in chosen] or [p for p in pool if p not in chosen])
                chosen.append(pick)
        for s in seeds:
            if s not in chosen:
                coins.append(s)
        coins = [c for c in coins if c not in chosen]
        for c in coins:
            self.spawns.append(("coin", c[0], c[1]))
        for s in chosen:
            self.spawns.append(("seed", s[0], s[1]))

    def tile(self, tx, ty):
        if tx < 0 or tx >= self.wt:
            return "#"
        if ty < 0 or ty >= ROWS:
            return "."
        return self.grid[ty][tx]

    def solid(self, tx, ty):
        return self.tile(tx, ty) == "#"

    def ground(self, tx, ty):
        return self.tile(tx, ty) in "#="

    def rect_free(self, r):
        if r.left < 0 or r.right > self.pw:
            return False
        for ty in range(r.top // TILE, (r.bottom - 1) // TILE + 1):
            for tx in range(r.left // TILE, (r.right - 1) // TILE + 1):
                if self.solid(tx, ty):
                    return False
        return True

    def touches_acid(self, r):
        for ty in range((r.top + 10) // TILE, (r.bottom - 1) // TILE + 1):
            for tx in range((r.left + 4) // TILE, (r.right - 5) // TILE + 1):
                if self.tile(tx, ty) == "~" and r.bottom > ty * TILE + 10:
                    return True
        return False

    def ray_clear(self, x1, y1, x2, y2):
        d = dist(x1, y1, x2, y2)
        steps = max(1, int(d / 20))
        for i in range(1, steps):
            t = i / steps
            if self.solid(int((x1 + (x2 - x1) * t) // TILE), int((y1 + (y2 - y1) * t) // TILE)):
                return False
        return True


class Body:
    """Corpo fisico con collisioni AABB contro la griglia di tile."""

    def __init__(self, x, y, w, h):
        self.x, self.y = float(x), float(y)
        self.w, self.h = w, h
        self.vx = self.vy = 0.0
        self.on_ground = False
        self.ground_kind = "#"

    @property
    def rect(self):
        return pygame.Rect(int(self.x), int(self.y), self.w, self.h)

    @property
    def cx(self):
        return self.x + self.w / 2

    @property
    def cy(self):
        return self.y + self.h / 2

    @property
    def bottom(self):
        return self.y + self.h


def move_body(b, level, dt, drop=False):
    hit_wall = False
    b.x += b.vx * dt
    top_t = int(b.y // TILE)
    bot_t = int((b.y + b.h - 0.01) // TILE)
    if b.vx > 0:
        tx = int((b.x + b.w - 0.01) // TILE)
        for ty in range(top_t, bot_t + 1):
            if level.solid(tx, ty):
                b.x = tx * TILE - b.w
                b.vx = 0
                hit_wall = True
                break
    elif b.vx < 0:
        tx = int(b.x // TILE)
        for ty in range(top_t, bot_t + 1):
            if level.solid(tx, ty):
                b.x = (tx + 1) * TILE
                b.vx = 0
                hit_wall = True
                break
    prev_bottom = b.y + b.h
    b.y += b.vy * dt
    b.on_ground = False
    l_t = int(b.x // TILE)
    r_t = int((b.x + b.w - 0.01) // TILE)
    if b.vy >= 0:
        ty = int((b.y + b.h - 0.01) // TILE)
        for tx in range(l_t, r_t + 1):
            t = level.tile(tx, ty)
            if t == "#" or (t == "=" and not drop and prev_bottom <= ty * TILE + 1):
                b.y = ty * TILE - b.h
                b.vy = 0
                b.on_ground = True
                b.ground_kind = t
                break
    else:
        ty = int(b.y // TILE)
        for tx in range(l_t, r_t + 1):
            if level.solid(tx, ty):
                b.y = (ty + 1) * TILE
                b.vy = 0
                break
    return hit_wall


# =============================================================================
#  EFFETTI: particelle, testi volanti, fumetti
# =============================================================================
class Particle:
    __slots__ = ("x", "y", "vx", "vy", "life", "max_life", "color", "size", "grav", "kind", "drag", "glow")

    def __init__(self, x, y, vx, vy, life, color, size=3, grav=0.0, kind="dot", drag=0.0, glow=False):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.life = self.max_life = life
        self.color, self.size, self.grav, self.kind, self.drag, self.glow = color, size, grav, kind, drag, glow


class Particles:
    MAX = 900

    def __init__(self):
        self.items = []

    def add(self, *a, **k):
        if len(self.items) < self.MAX:
            self.items.append(Particle(*a, **k))

    def burst(self, x, y, n, color, speed=200, life=0.6, size=3, grav=600, kind="dot", glow=False, up=False):
        for _ in range(n):
            a = random.uniform(0, 2 * math.pi) if not up else random.uniform(math.pi * 1.1, math.pi * 1.9)
            s = random.uniform(speed * 0.3, speed)
            self.add(x, y, math.cos(a) * s, math.sin(a) * s, random.uniform(life * 0.5, life),
                     color, random.uniform(size * 0.6, size * 1.3), grav, kind, 1.5, glow)

    def update(self, dt):
        alive = []
        for p in self.items:
            p.life -= dt
            if p.life <= 0:
                continue
            p.vy += p.grav * dt
            if p.drag:
                f = max(0.0, 1.0 - p.drag * dt)
                p.vx *= f
                p.vy *= f
            p.x += p.vx * dt
            p.y += p.vy * dt
            alive.append(p)
        self.items = alive

    def draw(self, surf, cx, cy):
        for p in self.items:
            k = p.life / p.max_life
            x, y = p.x - cx, p.y - cy
            if x < -40 or x > W + 40 or y < -40 or y > H + 40:
                continue
            if p.kind == "spark":
                pygame.draw.line(surf, p.color, (x, y), (x - p.vx * 0.03, y - p.vy * 0.03), max(1, int(p.size * k)))
            elif p.kind == "smoke":
                r = int(p.size * (2.0 - k))
                if r > 0:
                    pygame.draw.circle(surf, lerp_col(p.color, (60, 60, 60), 1 - k), (int(x), int(y)), r)
            else:
                r = max(1, int(p.size * k))
                pygame.draw.circle(surf, p.color, (int(x), int(y)), r)
            if p.glow and k > 0.2:
                draw_glow(surf, x, y, int(p.size * 5 * k) + 4, p.color, 0.6)


class FloatText:
    def __init__(self, x, y, s, color=(255, 240, 120), size=22, life=1.0, vy=-60):
        self.x, self.y, self.s, self.color, self.size, self.life, self.max_life, self.vy = x, y, s, color, size, life, life, vy

    def update(self, dt):
        self.life -= dt
        self.y += self.vy * dt
        return self.life > 0

    def draw(self, surf, cx, cy):
        img = text(self.s, self.size, self.color, kind="title", outline=OUTLINE, ow=2)
        a = int(255 * clamp(self.life / self.max_life * 2, 0, 1))
        if a < 255:
            img = img.copy()
            img.set_alpha(a)
        surf.blit(img, (self.x - cx - img.get_width() / 2, self.y - cy - img.get_height() / 2))


class Bubble:
    """Fumetto sopra la testa di un personaggio."""

    def __init__(self, s, life=2.6):
        self.s = s
        self.life = life

    def draw(self, surf, x, y):
        lines = wrap_text(self.s, 17, 260, kind="comic", bold=True)
        imgs = [text(l, 17, (20, 20, 20), kind="comic", bold=True) for l in lines]
        w = max(i.get_width() for i in imgs) + 22
        h = sum(i.get_height() for i in imgs) + 14
        r = pygame.Rect(0, 0, w, h)
        r.midbottom = (int(x), int(y) - 14)
        r.clamp_ip(pygame.Rect(6, 70, W - 12, H - 76))
        tail = [(int(x) - 7, r.bottom - 2), (int(x) + 7, r.bottom - 2), (int(x), r.bottom + 12)]
        pygame.draw.polygon(surf, WHITE, tail)
        pygame.draw.lines(surf, OUTLINE, False, tail, 2)
        pygame.draw.rect(surf, WHITE, r, border_radius=12)
        pygame.draw.rect(surf, OUTLINE, r, 2, border_radius=12)
        pygame.draw.line(surf, WHITE, (tail[0][0] + 2, r.bottom - 2), (tail[1][0] - 2, r.bottom - 2), 3)
        yy = r.top + 7
        for i in imgs:
            surf.blit(i, (r.centerx - i.get_width() // 2, yy))
            yy += i.get_height()


class Camera:
    def __init__(self, level_w):
        self.x = 0.0
        self.y = 0.0
        self.level_w = level_w
        self.shake_amt = 0.0
        self.ox = self.oy = 0

    def shake(self, a):
        self.shake_amt = max(self.shake_amt, a)

    def update(self, dt, tx, snap=False):
        target = clamp(tx - W / 2, 0, max(0, self.level_w - W))
        self.x = target if snap else lerp(self.x, target, clamp(dt * 7, 0, 1))
        if self.shake_amt > 0.2:
            self.ox = random.uniform(-1, 1) * self.shake_amt
            self.oy = random.uniform(-1, 1) * self.shake_amt
            self.shake_amt *= max(0.0, 1 - dt * 7)
        else:
            self.ox = self.oy = 0
            self.shake_amt = 0

    @property
    def cx(self):
        return int(self.x + self.ox)

    @property
    def cy(self):
        return int(self.y + self.oy)


# =============================================================================
#  PROIETTILI
# =============================================================================
class Projectile:
    def __init__(self, x, y, vx, vy, owner, dmg, color, kind="laser", life=1.3, radius=6):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.owner, self.dmg, self.color, self.kind, self.life, self.radius = owner, dmg, color, kind, life, radius
        self.dead = False
        self.ignore_tiles = kind == "orb"

    def update(self, dt, scene):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.life -= dt
        if self.life <= 0:
            self.dead = True
            return
        if not self.ignore_tiles and scene.level.solid(int(self.x // TILE), int(self.y // TILE)):
            self.dead = True
            scene.particles.burst(self.x, self.y, 6, self.color, 180, 0.3, 2, 0, "spark", True)
        if self.y > H + 50 or self.x < -50 or self.x > scene.level.pw + 50:
            self.dead = True

    def draw(self, surf, cx, cy):
        x, y = self.x - cx, self.y - cy
        if self.kind == "laser":
            sp = math.hypot(self.vx, self.vy) or 1
            dx, dy = self.vx / sp, self.vy / sp
            tail = (x - dx * 26, y - dy * 26)
            draw_glow(surf, x - dx * 10, y - dy * 10, 26, self.color, 0.8)
            pygame.draw.line(surf, self.color, tail, (x, y), 6)
            pygame.draw.line(surf, (255, 255, 255), (x - dx * 20, y - dy * 20), (x, y), 2)
        else:
            draw_glow(surf, x, y, self.radius * 4, self.color, 0.9)
            pygame.draw.circle(surf, self.color, (int(x), int(y)), self.radius)
            pygame.draw.circle(surf, WHITE, (int(x), int(y)), max(2, self.radius // 2))


# =============================================================================
#  GIOCATORE (Rick o Pickle Rick)
# =============================================================================
RICK_QUIPS = ["*burp*", "Wubba Lubba Dub Dub!", "Ah, la scienza.", "Nessuno esiste di proposito, Morty.",
              "Sono troppo intelligente per questo.", "Riggity riggity wrecked, figliolo!", "Aaah, il multiverso...",
              "Sbrigati, Morty!", "Ci serve altro fluido portale."]
RICK_KILL = ["Riggity riggity wrecked!", "Prendi questo!", "*burp* Fatto.", "Troppo facile.", "Ciao ciao!"]
PICKLE_QUIPS = ["Sono PICKLE RIIICK!", "Funky!", "Un sottaceto non ha paura dei ratti!", "La terapia? No grazie!",
                "Il sottaceto più figo dell'universo!"]
MORTY_QUIPS = ["Aw jeez, Rick!", "Oh cavolo, Rick!", "Rick, aspettami!", "Questo è troppo per me!",
               "Ok, ok, ce la posso fare!", "Rick, ho paura!", "Mi mancano la scuola e Jessica..."]
MORTY_HURT = ["Ahia! Rick!", "Aw jeez, fa male!", "Ehi! Attento!"]
MEESEEKS_QUIPS = ["Sono Mr. Meeseeks! Guardami!", "Esistere è dolore!", "Posso farcela!", "Oooh, sì! Si può fare!",
                  "Missione: aiutare Rick!"]


class Player:
    def __init__(self, x, y, kind="rick"):
        self.kind = kind
        w, h = (32, 88) if kind == "rick" else (28, 72)
        self.body = Body(x - w / 2, y - h, w, h)
        self.facing = 1
        self.hp = 100.0
        self.max_hp = 100.0
        self.fluid = 100.0
        self.flasks = 2
        self.inv = 0.0
        self.shoot_cd = 0.0
        self.coyote = 0.0
        self.jump_buf = 0.0
        self.air_jumps = 1
        self.anim_t = 0.0
        self.aim = 0.0
        self.aim_hold = 0.0
        self.dead = False
        self.last_safe = (x, y)
        self.bubble = None
        self.drop_t = 0.0
        self.quip_t = random.uniform(12, 20)
        self.visible = True
        self.portal_cd = 0.0
        self.recoil = 0.0

    @property
    def sprite_kind(self):
        return "rick" if self.kind == "rick" else "pickle"

    def shoulder(self):
        b = self.body
        if self.kind == "rick":
            return b.cx + self.facing * 9, b.bottom - 62
        return b.cx + self.facing * 12, b.bottom - 34

    def say(self, s, life=2.6):
        self.bubble = Bubble(s, life)

    def update(self, dt, sc, inp):
        b = self.body
        lvl = sc.level
        self.anim_t += dt
        self.inv = max(0.0, self.inv - dt)
        self.shoot_cd -= dt
        self.portal_cd -= dt
        self.drop_t -= dt
        self.recoil = max(0.0, self.recoil - dt * 6)
        self.fluid = min(100.0, self.fluid + PORTAL_REGEN * dt)
        if self.bubble:
            self.bubble.life -= dt
            if self.bubble.life <= 0:
                self.bubble = None
        self.quip_t -= dt
        if self.quip_t <= 0:
            self.quip_t = random.uniform(16, 28)
            self.say(random.choice(RICK_QUIPS if self.kind == "rick" else PICKLE_QUIPS))

        mv = (1 if inp.held("right") else 0) - (1 if inp.held("left") else 0)
        if mv:
            b.vx = approach(b.vx, mv * RUN_SPEED, (ACCEL_GROUND if b.on_ground else ACCEL_AIR) * dt)
            if self.aim_hold <= 0:
                self.facing = mv
        else:
            b.vx = approach(b.vx, 0, (FRICTION if b.on_ground else ACCEL_AIR * 0.4) * dt)

        if b.on_ground:
            self.coyote = COYOTE
            self.air_jumps = 1
        else:
            self.coyote -= dt
        if inp.hit("jump"):
            self.jump_buf = JUMP_BUFFER
        else:
            self.jump_buf -= dt
        if self.jump_buf > 0 and inp.held("down") and b.on_ground and b.ground_kind == "=":
            self.drop_t = 0.25
            self.jump_buf = 0
            b.on_ground = False
        if self.jump_buf > 0:
            if self.coyote > 0:
                b.vy = -JUMP_V
                self.coyote = 0
                self.jump_buf = 0
                sc.audio.play("jump")
                sc.particles.burst(b.cx, b.bottom, 8, (200, 200, 190), 120, 0.4, 3, 200, "smoke", up=True)
            elif self.air_jumps > 0:
                b.vy = -DJUMP_V
                self.air_jumps -= 1
                self.jump_buf = 0
                sc.audio.play("djump")
                for k in range(10):
                    a = math.pi / 2 + random.uniform(-0.6, 0.6)
                    sc.particles.add(b.cx, b.bottom, math.cos(a) * 160, math.sin(a) * 160, 0.35,
                                     PORTAL_GREEN, 3, 0, "dot", 2, True)
        if b.vy < 0 and not inp.held("jump"):
            b.vy += GRAVITY * 1.3 * dt
        b.vy = min(b.vy + GRAVITY * dt, MAX_FALL)
        was_ground = b.on_ground
        fall_v = b.vy
        move_body(b, lvl, dt, drop=self.drop_t > 0)
        if b.on_ground and not was_ground and fall_v > 600:
            sc.particles.burst(b.cx, b.bottom, 6, (190, 190, 180), 90, 0.35, 3, 100, "smoke", up=True)
        if b.on_ground:
            l, r = int((b.x + 2) // TILE), int((b.x + b.w - 2) // TILE)
            ty = int((b.bottom + 2) // TILE)
            if lvl.ground(l, ty) and lvl.ground(r, ty):
                self.last_safe = (b.cx, b.bottom)

        # ---- mira e sparo ----
        ox, oy = self.shoulder()
        firing_mouse = inp.mheld(1)
        firing_key = inp.held("shoot")
        want_aim = None
        if firing_mouse:
            mx, my = inp.mouse
            want_aim = math.atan2(my + sc.cam.cy - oy, mx + sc.cam.cx - ox)
        elif firing_key:
            tgt = sc.auto_target(ox, oy, self.facing)
            want_aim = math.atan2(tgt[1] - oy, tgt[0] - ox) if tgt else (0.0 if self.facing > 0 else math.pi)
        if want_aim is not None:
            self.facing = 1 if math.cos(want_aim) >= 0 else -1
            self.aim_hold = 0.35
            local = want_aim if self.facing > 0 else math.pi - want_aim
            local = (local + math.pi) % (2 * math.pi) - math.pi
            self.aim = clamp(math.degrees(local), -80, 60)
            if self.shoot_cd <= 0:
                self.fire(sc)
        else:
            self.aim_hold -= dt
            if self.aim_hold <= 0:
                self.aim = approach(self.aim, 0, 300 * dt)

        # ---- pistola portale ----
        if (inp.hit("portal") or inp.mhit(3)) and self.portal_cd <= 0:
            if self.fluid >= PORTAL_COST:
                if inp.mhit(3):
                    mx, my = inp.mouse
                    dx, dy = mx + sc.cam.cx - b.cx, my + sc.cam.cy - b.cy
                    L = math.hypot(dx, dy) or 1
                    dx, dy = dx / L, dy / L
                elif inp.held("up"):
                    dx, dy = self.facing * 0.6, -0.8
                elif inp.held("down"):
                    dx, dy = self.facing * 0.6, 0.8
                else:
                    dx, dy = self.facing, 0.0
                self.portal_dash(sc, dx, dy)
            else:
                sc.add_text(b.cx, b.y - 20, "Fluido portale esaurito!", (140, 255, 120), 18)
                self.portal_cd = 0.4

        # ---- fiaschetta ----
        if inp.hit("flask"):
            if self.flasks > 0 and self.hp < self.max_hp:
                self.flasks -= 1
                self.hp = min(self.max_hp, self.hp + 40)
                sc.audio.play("drink")
                sc.burp_t = 0.45
                self.say("*BUUURP*", 1.6)
                sc.particles.burst(b.cx, b.y + 20, 16, (120, 255, 120), 140, 0.7, 3, -60, "dot", True)
            elif self.flasks <= 0:
                sc.add_text(b.cx, b.y - 20, "Fiaschetta vuota!", (255, 200, 120), 18)

        # ---- cadute e acido ----
        if lvl.touches_acid(b.rect) or b.y > H + 60:
            sc.player_fell()

    def fire(self, sc):
        ox, oy = self.shoulder()
        a = math.radians(self.aim)
        if self.facing < 0:
            a = math.pi - a
        L = 40 if self.kind == "rick" else 30
        x, y = ox + math.cos(a) * L, oy + math.sin(a) * L
        col = (120, 255, 90) if self.kind == "rick" else (255, 110, 90)
        sc.projectiles.append(Projectile(x, y, math.cos(a) * 950, math.sin(a) * 950, "player", 1, col))
        sc.particles.burst(x, y, 4, col, 160, 0.15, 2, 0, "spark", True)
        sc.flashes.append([x, y, 0.06, col])
        sc.audio.play("laser")
        self.shoot_cd = 0.17
        self.recoil = 1.0

    def portal_dash(self, sc, dx, dy):
        b = self.body
        L = PORTAL_DIST
        found = None
        while L >= TILE * 0.8:
            nx = b.x + dx * L
            ny = b.y + dy * L
            r = pygame.Rect(int(nx), int(ny), b.w, b.h)
            if sc.level.rect_free(r) and ny > -40:
                found = (nx, ny)
                break
            L -= 8
        if not found:
            sc.add_text(b.cx, b.y - 20, "Bloccato!", (140, 255, 120), 18)
            self.portal_cd = 0.3
            return
        sc.portal_fx.append([b.cx, b.cy, 0.55])
        b.x, b.y = found
        sc.portal_fx.append([b.cx, b.cy, 0.55])
        b.vy = min(b.vy, 0) * 0.2
        b.vx = dx * RUN_SPEED * 0.6
        self.fluid -= PORTAL_COST
        self.inv = max(self.inv, 0.3)
        self.portal_cd = 0.25
        self.air_jumps = max(self.air_jumps, 1) if not b.on_ground else self.air_jumps
        sc.audio.play("portal")
        sc.particles.burst(b.cx, b.cy, 20, PORTAL_GREEN, 260, 0.5, 3, 0, "dot", True)

    def hurt(self, dmg, src_x, sc):
        if self.inv > 0 or self.dead or sc.state != "play":
            return False
        self.hp -= dmg
        self.inv = 1.1
        b = self.body
        d = 1 if b.cx >= src_x else -1
        b.vx = d * 380
        b.vy = -420
        sc.cam.shake(9)
        sc.audio.play("hurt")
        sc.particles.burst(b.cx, b.cy, 14, (255, 240, 120), 260, 0.4, 3, 400, "spark", True)
        sc.hits_taken += 1
        if self.hp <= 0:
            self.hp = 0
            self.dead = True
            sc.player_died()
        elif random.random() < 0.4:
            self.say(random.choice(["Ahia!", "*burp* Ahi!", "Questo fa male!", "Ehi!"]), 1.4)
        return True

    def anim_state(self):
        b = self.body
        if not b.on_ground:
            return ("jump", 0) if b.vy < 0 else ("fall", 0)
        if abs(b.vx) > 30:
            return "run", int(self.anim_t * 13) % 8
        return "idle", int(self.anim_t * 3) % 4

    def draw(self, surf, cx, cy):
        if not self.visible:
            return
        if self.inv > 0 and not self.dead and int(self.inv * 14) % 2 == 0:
            return
        st, fr = self.anim_state()
        b = self.body
        aim = int(round(self.aim / 10.0)) * 10
        rx = -self.facing * self.recoil * 3
        blit_sprite(surf, self.sprite_kind, st, fr, aim, self.facing, b.cx - cx + rx, b.bottom - cy)

    def draw_bubble(self, surf, cx, cy):
        if self.bubble and self.visible:
            self.bubble.draw(surf, self.body.cx - cx, self.body.y - cy)


# =============================================================================
#  MORTY (compagno controllato dal computer)
# =============================================================================
class Morty:
    def __init__(self, x, y):
        self.body = Body(x - 14, y - 72, 28, 72)
        self.facing = 1
        self.anim_t = 0.0
        self.aim = 0
        self.shoot_cd = 1.0
        self.bubble = None
        self.quip_t = random.uniform(8, 14)
        self.stuck_t = 0.0
        self.hurt_t = 0.0
        self.air_jumps = 1
        self.visible = True

    def say(self, s, life=2.4):
        self.bubble = Bubble(s, life)

    def teleport_near(self, sc):
        p = sc.player.body
        b = self.body
        for off in (-60, 60, -110, 110, 0):
            r = pygame.Rect(int(p.cx + off - b.w / 2), int(p.bottom - b.h), b.w, b.h)
            if sc.level.rect_free(r):
                sc.portal_fx.append([b.cx, b.cy, 0.5])
                b.x, b.y = r.x, r.y
                b.vx = b.vy = 0
                sc.portal_fx.append([b.cx, b.cy, 0.5])
                sc.audio.play("portal", 0.5)
                return

    def update(self, dt, sc):
        b = self.body
        p = sc.player.body
        self.anim_t += dt
        self.shoot_cd -= dt
        self.hurt_t = max(0.0, self.hurt_t - dt)
        if self.bubble:
            self.bubble.life -= dt
            if self.bubble.life <= 0:
                self.bubble = None
        self.quip_t -= dt
        if self.quip_t <= 0:
            self.quip_t = random.uniform(14, 26)
            if not (sc.player.bubble):
                self.say(random.choice(MORTY_QUIPS))
        tx = p.cx - sc.player.facing * 58
        dx = tx - b.cx
        if abs(dx) > 18:
            b.vx = approach(b.vx, sign(dx) * RUN_SPEED * 1.05, ACCEL_GROUND * dt)
            self.facing = sign(dx)
        else:
            b.vx = approach(b.vx, 0, FRICTION * dt)
            self.facing = sc.player.facing
        if b.on_ground:
            self.air_jumps = 1
            front = int((b.cx + self.facing * (b.w / 2 + 10)) // TILE)
            below = int((b.bottom + 4) // TILE)
            gap = not sc.level.ground(front, below)
            higher = p.bottom < b.bottom - 40 and abs(p.cx - b.cx) < 260
            if (higher or (gap and abs(dx) > 30) or (abs(b.vx) < 5 and abs(dx) > 40)) and self.hurt_t <= 0:
                b.vy = -JUMP_V
        elif b.vy > 80 and self.air_jumps > 0 and p.bottom < b.bottom - 20:
            b.vy = -DJUMP_V
            self.air_jumps -= 1
        b.vy = min(b.vy + GRAVITY * dt, MAX_FALL)
        hit = move_body(b, sc.level, dt)
        if hit or (abs(dx) > 120 and abs(b.vx) < 20):
            self.stuck_t += dt
        else:
            self.stuck_t = max(0.0, self.stuck_t - dt)
        far = dist(b.cx, b.cy, p.cx, p.cy) > 560
        if b.y > H + 40 or sc.level.touches_acid(b.rect) or self.stuck_t > 1.6 or far:
            self.stuck_t = 0
            self.teleport_near(sc)
        # spara ai nemici vicini
        if self.shoot_cd <= 0:
            tgt = sc.nearest_enemy(b.cx, b.cy - 40, 460)
            if tgt is not None:
                ex, ey = tgt
                sx, sy = b.cx + self.facing * 10, b.bottom - 37
                if sc.level.ray_clear(sx, sy, ex, ey):
                    a = math.atan2(ey - sy, ex - sx)
                    self.facing = 1 if math.cos(a) >= 0 else -1
                    local = a if self.facing > 0 else math.pi - a
                    local = (local + math.pi) % (2 * math.pi) - math.pi
                    self.aim = clamp(math.degrees(local), -80, 60)
                    x, y = sx + math.cos(a) * 26, sy + math.sin(a) * 26
                    sc.projectiles.append(Projectile(x, y, math.cos(a) * 800, math.sin(a) * 800, "player", 1, (255, 220, 90)))
                    sc.audio.play("laser_m", 0.6)
                    self.shoot_cd = random.uniform(0.8, 1.2)
                else:
                    self.shoot_cd = 0.3
            else:
                self.shoot_cd = 0.3
                self.aim = approach(self.aim, 0, 40)

    def hurt(self, sc, src_x):
        if self.hurt_t > 0:
            return
        self.hurt_t = 1.2
        b = self.body
        b.vx = (1 if b.cx >= src_x else -1) * 320
        b.vy = -380
        self.say(random.choice(MORTY_HURT), 1.5)
        sc.particles.burst(b.cx, b.cy, 8, (255, 240, 120), 200, 0.3, 2, 300, "spark")

    def draw(self, surf, cx, cy):
        if not self.visible:
            return
        if self.hurt_t > 0 and int(self.hurt_t * 14) % 2 == 0:
            return
        b = self.body
        if not b.on_ground:
            st, fr = ("jump", 0) if b.vy < 0 else ("fall", 0)
        elif abs(b.vx) > 30:
            st, fr = "run", int(self.anim_t * 13) % 8
        else:
            st, fr = "idle", int(self.anim_t * 3) % 4
        blit_sprite(surf, "morty", st, fr, int(round(self.aim / 10.0)) * 10, self.facing, b.cx - cx, b.bottom - cy)

    def draw_bubble(self, surf, cx, cy):
        if self.bubble and self.visible:
            self.bubble.draw(surf, self.body.cx - cx, self.body.y - cy)


# =============================================================================
#  MR. MEESEEKS (alleato temporaneo)
# =============================================================================
class Meeseeks:
    def __init__(self, x, y):
        self.body = Body(x - 13, y - 90, 26, 90)
        self.life = 16.0
        self.facing = 1
        self.anim_t = 0.0
        self.hit_cd = 0.0
        self.bubble = Bubble(random.choice(MEESEEKS_QUIPS[:2]), 2.5)
        self.quip_t = 5.0
        self.dead = False

    def update(self, dt, sc):
        b = self.body
        self.life -= dt
        self.anim_t += dt
        self.hit_cd -= dt
        if self.bubble:
            self.bubble.life -= dt
            if self.bubble.life <= 0:
                self.bubble = None
        self.quip_t -= dt
        if self.quip_t <= 0:
            self.quip_t = random.uniform(4, 7)
            self.bubble = Bubble(random.choice(MEESEEKS_QUIPS), 2.0)
        tgt = sc.nearest_enemy_obj(b.cx, b.cy, 520)
        if tgt is not None:
            tx, ty = tgt.body.cx, tgt.body.cy
        else:
            tx, ty = sc.player.body.cx + 70, sc.player.body.cy
        dx = tx - b.cx
        if abs(dx) > 10:
            b.vx = approach(b.vx, sign(dx) * 360, ACCEL_GROUND * dt)
            self.facing = sign(dx)
        if b.on_ground and (ty < b.y or abs(b.vx) < 5) and abs(dx) > 5:
            b.vy = -JUMP_V
        b.vy = min(b.vy + GRAVITY * dt, MAX_FALL)
        move_body(b, sc.level, dt)
        if b.y > H or sc.level.touches_acid(b.rect):
            p = sc.player.body
            b.x, b.y = p.x, p.y - 20
            b.vy = 0
        if tgt is not None and self.hit_cd <= 0 and b.rect.colliderect(tgt.rect()):
            tgt.hurt(1, sc, b.cx)
            self.hit_cd = 0.35
            sc.particles.burst(tgt.body.cx, tgt.body.cy, 6, (124, 192, 242), 200, 0.3, 3, 300)
        if self.life <= 0:
            self.dead = True
            sc.particles.burst(b.cx, b.cy, 40, (124, 192, 242), 300, 0.8, 4, 0, "smoke")
            sc.add_text(b.cx, b.y, "*POOF*", (160, 220, 255), 26)
            sc.audio.play("poof")

    def draw(self, surf, cx, cy):
        b = self.body
        if self.life < 3 and int(self.life * 10) % 2 == 0:
            return
        st = "run" if abs(b.vx) > 30 or not b.on_ground else "idle"
        fr = int(self.anim_t * 12) % 8 if st == "run" else int(self.anim_t * 3) % 4
        blit_sprite(surf, "meeseeks", st, fr, 0, self.facing, b.cx - cx, b.bottom - cy)
        if self.bubble:
            self.bubble.draw(surf, b.cx - cx, b.y - cy)


# =============================================================================
#  NEMICI
# =============================================================================
ENEMY_DEFS = {
    "cronen_walker": dict(beh="walker", hp=3, speed=70, chase=150, w=50, h=50, dmg=12, score=100, stomp=True),
    "cronen_flyer": dict(beh="flyer", hp=2, speed=110, w=44, h=36, dmg=10, score=120, stomp=True),
    "gromflomite": dict(beh="shooter", hp=4, speed=70, w=32, h=82, dmg=10, score=150, cd=1.7, sdmg=12, stomp=True),
    "fed_drone": dict(beh="flyshooter", hp=2, speed=90, w=50, h=24, dmg=8, score=140, cd=2.3, sdmg=10, stomp=True),
    "rat": dict(beh="walker", hp=2, speed=130, chase=270, w=50, h=28, dmg=10, score=90, stomp=True),
    "roach": dict(beh="flyer", hp=1, speed=150, w=36, h=24, dmg=8, score=80, stomp=True),
    "guard": dict(beh="shooter", hp=5, speed=80, w=32, h=88, dmg=12, score=220, cd=1.3, sdmg=14, stomp=False),
    "citadel_drone": dict(beh="flyshooter", hp=3, speed=110, w=50, h=24, dmg=10, score=180, cd=1.8, sdmg=12, stomp=True),
}
GROUND_SPRITE_OFFSET = {"cronen_walker": 0, "rat": 0, "gromflomite": 0, "guard": 0}


class Enemy:
    def __init__(self, kind, x, y, diff=1.0):
        self.kind = kind
        d = ENEMY_DEFS[kind]
        self.d = d
        self.beh = d["beh"]
        self.body = Body(x - d["w"] / 2, y - d["h"], d["w"], d["h"])
        self.hp = d["hp"]
        self.dir = random.choice((-1, 1))
        self.facing = self.dir
        self.t = random.uniform(0, 10)
        self.flash = 0.0
        self.shot_t = random.uniform(0.8, d.get("cd", 2.0))
        self.charge = 0.0
        self.home = (x, y - d["h"] / 2)
        self.dead = False
        self.diff = diff
        self.aim = 0
        self.alerted = False

    def rect(self):
        return self.body.rect

    def update(self, dt, sc):
        b = self.body
        self.t += dt
        self.flash = max(0.0, self.flash - dt)
        p = sc.player.body
        dx, dy = p.cx - b.cx, p.cy - b.cy
        lvl = sc.level
        beh = self.beh
        sp = self.d["speed"] * (0.85 + 0.15 * self.diff)
        if beh == "walker":
            near = abs(dx) < 300 and abs(dy) < 110 and not sc.player.dead
            if near:
                if not self.alerted:
                    self.alerted = True
                    sc.add_text(b.cx, b.y - 14, "!", (255, 80, 80), 26, 0.5)
                self.dir = sign(dx) or self.dir
                target = self.d["chase"] * (0.85 + 0.15 * self.diff)
            else:
                self.alerted = False
                target = sp
            b.vx = approach(b.vx, self.dir * target, 900 * dt)
            self._ground_move(dt, lvl, stop_at_edge=True)
        elif beh == "shooter":
            in_range = abs(dx) < 560 and abs(dy) < 170 and not sc.player.dead
            if in_range:
                self.dir = sign(dx) or self.dir
                b.vx = approach(b.vx, 0, 900 * dt)
                self.shot_t -= dt
                if self.shot_t < 0.45 and self.charge == 0:
                    self.charge = 0.45
                if self.charge > 0:
                    self.charge -= dt
                    if self.charge <= 0:
                        self.charge = 0
                        self._shoot(sc, p.cx, p.cy - 10, 520)
                        self.shot_t = self.d["cd"] / (0.8 + 0.2 * self.diff)
            else:
                self.charge = 0
                b.vx = approach(b.vx, self.dir * sp, 900 * dt)
            self._ground_move(dt, lvl, stop_at_edge=True)
            gx, gy = self._gun()
            self.aim = clamp(math.degrees(math.atan2((p.cy - 10) - gy, abs(dx) or 1)), -60, 50) if in_range else 0
        elif beh == "flyer":
            near = dist(b.cx, b.cy, p.cx, p.cy) < 380 and not sc.player.dead
            if near:
                L = math.hypot(dx, dy) or 1
                b.vx = approach(b.vx, dx / L * sp * 1.6, 500 * dt)
                b.vy = approach(b.vy, dy / L * sp * 1.6, 500 * dt)
            else:
                hx = self.home[0] + math.sin(self.t * 0.8) * 90
                hy = self.home[1] + math.sin(self.t * 1.7) * 30
                b.vx = approach(b.vx, (hx - b.cx) * 2, 400 * dt)
                b.vy = approach(b.vy, (hy - b.cy) * 2, 400 * dt)
            b.x += b.vx * dt
            b.y += b.vy * dt
            b.y = clamp(b.y, 90, H - 80)
            self.dir = sign(b.vx) or self.dir
        elif beh == "flyshooter":
            L = math.hypot(dx, dy) or 1
            near = L < 600 and not sc.player.dead
            if near:
                want = 250
                tx = p.cx - sign(dx) * want
                ty = p.cy - 170
                b.vx = approach(b.vx, clamp((tx - b.cx) * 2, -sp, sp), 400 * dt)
                b.vy = approach(b.vy, clamp((ty - b.cy) * 2, -sp, sp), 400 * dt)
                self.shot_t -= dt
                if self.shot_t <= 0:
                    self._shoot(sc, p.cx, p.cy, 420)
                    self.shot_t = self.d["cd"] / (0.8 + 0.2 * self.diff)
                self.dir = sign(dx) or self.dir
            else:
                hx = self.home[0] + math.sin(self.t * 0.7) * 100
                hy = self.home[1] + math.sin(self.t * 1.3) * 26
                b.vx = approach(b.vx, (hx - b.cx) * 1.5, 300 * dt)
                b.vy = approach(b.vy, (hy - b.cy) * 1.5, 300 * dt)
                self.dir = sign(b.vx) or self.dir
            b.x += b.vx * dt
            b.y += b.vy * dt
            b.y = clamp(b.y, 90, H - 120)
        self.facing = self.dir
        if b.y > H + 100 or lvl.touches_acid(b.rect) and beh in ("walker", "shooter"):
            self.dead = True

    def _ground_move(self, dt, lvl, stop_at_edge):
        b = self.body
        b.vy = min(b.vy + GRAVITY * dt, MAX_FALL)
        if b.on_ground and stop_at_edge:
            front = int((b.cx + self.dir * (b.w / 2 + 4)) // TILE)
            below = int((b.bottom + 4) // TILE)
            if not lvl.ground(front, below):
                b.vx = 0
                self.dir = -self.dir
        if move_body(b, lvl, dt):
            self.dir = -self.dir

    def _gun(self):
        b = self.body
        return b.cx + self.dir * 26, b.bottom - (b.h * 0.55)

    def _shoot(self, sc, tx, ty, speed):
        b = self.body
        if self.beh == "shooter":
            gx, gy = self._gun()
        else:
            gx, gy = b.cx + self.dir * 22, b.cy
        a = math.atan2(ty - gy, tx - gx) + random.uniform(-0.06, 0.06)
        sc.projectiles.append(Projectile(gx, gy, math.cos(a) * speed, math.sin(a) * speed, "enemy",
                                         self.d["sdmg"], (255, 70, 60), "orb" if self.beh == "flyshooter" else "laser",
                                         2.2, 6))
        sc.audio.play("elaser", 0.6)

    def hurt(self, dmg, sc, src_x):
        if self.dead:
            return
        self.hp -= dmg
        self.flash = 0.12
        b = self.body
        b.vx += (1 if b.cx >= src_x else -1) * 160
        sc.audio.play("hit", 0.6)
        if self.hp <= 0:
            self.die(sc)

    def die(self, sc):
        self.dead = True
        b = self.body
        sc.kills += 1
        sc.score += self.d["score"]
        sc.add_text(b.cx, b.y, "+%d" % self.d["score"], (255, 240, 140), 20)
        organic = self.kind in ("cronen_walker", "cronen_flyer", "rat", "roach")
        col = (230, 120, 120) if organic else (255, 200, 90)
        sc.particles.burst(b.cx, b.cy, 26, col, 320, 0.7, 4, 700)
        sc.particles.burst(b.cx, b.cy, 10, (255, 255, 200), 240, 0.35, 3, 0, "spark", True)
        sc.audio.play("explode", 0.5)
        sc.cam.shake(5)
        if random.random() < 0.35:
            sc.spawn_pickup("coin", b.cx, b.cy - 10, drop=True)
        if random.random() < 0.18:
            sc.player.say(random.choice(RICK_KILL if sc.player.kind == "rick" else PICKLE_QUIPS), 1.6)

    def draw(self, surf, cx, cy):
        b = self.body
        kind = self.kind
        if self.beh in ("flyer", "flyshooter"):
            fr = int(self.t * 14) % 8
            st = "idle"
        elif abs(b.vx) > 20:
            st, fr = "run", int(self.t * 12) % 8
        else:
            st, fr = "idle", int(self.t * 3) % 4
        aim = int(round(self.aim / 10.0)) * 10 if self.beh == "shooter" else 0
        foot_y = b.bottom - cy
        if self.beh in ("flyer", "flyshooter"):
            d = SPRITES[kind]
            foot_y = b.cy - cy + d["size"][1] / 2
        if self.beh == "flyshooter":
            draw_glow(surf, b.cx - cx, b.bottom - cy + 4, 22, (255, 120, 60), 0.6)
        if self.charge > 0:
            gx, gy = self._gun()
            draw_glow(surf, gx - cx, gy - cy, int(30 * (1 - self.charge / 0.45)) + 8, (255, 80, 60))
        blit_sprite(surf, kind, st, fr, aim, self.facing, b.cx - cx, foot_y)
        if self.flash > 0:
            r = b.rect.move(-cx, -cy).inflate(10, 10)
            fl = pygame.Surface(r.size, pygame.SRCALPHA)
            fl.fill((255, 255, 255, 110))
            surf.blit(fl, r.topleft)


# =============================================================================
#  BOSS: IL CROMULON  ("Mostrami cosa sai fare!")
# =============================================================================
class Cromulon:
    MAX_HP = 110

    def __init__(self, level_w):
        self.x = level_w / 2
        self.y = -260.0
        self.base_y = 200.0
        self.hp = self.MAX_HP
        self.t = 0.0
        self.state = "intro"
        self.st = 0.0
        self.flash = 0.0
        self.mouth = False
        self.glow = False
        self.beam_target = (level_w / 2, 11 * TILE)
        self.attack_i = 0
        self.dead = False
        self.dying_t = 0.0
        self.waves = []  # onde d'urto a terra: [x, dir, life]
        self.shout_t = 0.0
        self.level_w = level_w
        self.scale = 0.62

    def rect(self):
        w, h = 340 * self.scale, 380 * self.scale
        return pygame.Rect(int(self.x - w * 0.42), int(self.y - h * 0.45), int(w * 0.84), int(h * 0.9))

    @property
    def body(self):
        r = self.rect()
        return Body(r.x, r.y, r.w, r.h)

    def eyes(self):
        k = self.scale
        return [(self.x - 55 * k, self.y - 22 * k), (self.x + 55 * k, self.y - 22 * k)]

    def phase2(self):
        return self.hp < self.MAX_HP * 0.5

    def update(self, dt, sc):
        self.t += dt
        self.st += dt
        self.flash = max(0.0, self.flash - dt)
        self.shout_t = max(0.0, self.shout_t - dt)
        p = sc.player.body
        for w in self.waves:
            w[0] += w[1] * 430 * dt
            w[2] -= dt
            if abs(p.cx - w[0]) < 26 and p.bottom > 12 * TILE - 34 and not sc.player.dead:
                sc.player.hurt(15, w[0], sc)
        self.waves = [w for w in self.waves if w[2] > 0 and 0 < w[0] < self.level_w]
        if self.state == "dying":
            self.dying_t += dt
            self.y += 20 * dt
            if random.random() < 0.4:
                r = self.rect()
                x, y = random.uniform(r.left, r.right), random.uniform(r.top, r.bottom)
                sc.particles.burst(x, y, 16, random.choice(((255, 200, 90), (255, 120, 60), (255, 255, 200))), 300, 0.6, 4, 0, "dot", True)
                sc.audio.play("explode", 0.4)
                sc.cam.shake(6)
            if self.dying_t > 3.0:
                self.dead = True
                r = self.rect()
                sc.particles.burst(self.x, self.y, 120, (255, 220, 140), 600, 1.2, 5, 300, "dot", True)
                sc.cam.shake(20)
                sc.audio.play("explode")
            return
        speed = 1.4 if self.phase2() else 1.0
        if self.state == "intro":
            self.y = lerp(self.y, self.base_y, clamp(dt * 1.5, 0, 1))
            self.mouth = int(self.t * 6) % 2 == 0 and self.st > 1.0
            if self.st > 1.0 and self.shout_t <= 0 and self.st < 1.2:
                self.shout_t = 2.2
                sc.audio.play("roar")
                sc.cam.shake(14)
            if self.st > 3.2:
                self.mouth = False
                self._next(sc)
            return
        hover_x = self.level_w / 2 + math.sin(self.t * 0.45 * speed) * 380
        self.x = lerp(self.x, hover_x, clamp(dt * 2, 0, 1))
        self.y = self.base_y + math.sin(self.t * 1.3) * 16
        if self.state == "idle":
            self.mouth = False
            self.glow = False
            if self.st > (1.6 / speed):
                self._next(sc)
        elif self.state == "orbs":
            self.mouth = True
            n = 7 if self.phase2() else 5
            if self.st > 0.35 and self.attack_i < 3:
                self.attack_i += 1
                self.st = 0.0
                mx, my = self.x, self.y + 100 * self.scale
                base = math.atan2(p.cy - my, p.cx - mx)
                for k in range(n):
                    a = base + (k - (n - 1) / 2) * 0.2
                    sc.projectiles.append(Projectile(mx, my, math.cos(a) * 300, math.sin(a) * 300, "enemy", 12,
                                                     (255, 110, 200), "orb", 4.0, 9))
                sc.audio.play("elaser")
            elif self.attack_i >= 3 and self.st > 0.5:
                self._go("idle")
        elif self.state == "beam_charge":
            self.glow = True
            if self.attack_i == 0:
                self.attack_i = 1
                sc.audio.play("charge")
            tx, ty = self.beam_target
            self.beam_target = (lerp(tx, p.cx, clamp(dt * 1.5, 0, 1)), lerp(ty, p.cy, clamp(dt * 1.5, 0, 1)))
            if self.st > 1.0:
                self._go("beam")
                sc.audio.play("beam")
                sc.cam.shake(8)
        elif self.state == "beam":
            self.glow = True
            tx, ty = self.beam_target
            for ex, ey in self.eyes():
                a = math.atan2(ty - ey, tx - ex)
                bx, by = ex + math.cos(a) * 1600, ey + math.sin(a) * 1600
                if seg_point_dist(p.cx, p.cy, ex, ey, bx, by) < 30 and not sc.player.dead:
                    sc.player.hurt(20, ex, sc)
            if self.st > 0.7:
                self._go("idle")
        elif self.state == "shout":
            self.mouth = int(self.t * 8) % 2 == 0
            if self.attack_i == 0:
                self.attack_i = 1
                self.shout_t = 2.0
                sc.audio.play("roar")
                sc.cam.shake(16)
            if self.st > 0.7 and self.attack_i == 1:
                self.attack_i = 2
                gx = self.x
                self.waves.append([gx, -1, 3.5])
                self.waves.append([gx, 1, 3.5])
                sc.audio.play("shock")
                sc.cam.shake(10)
                if self.phase2():
                    self.waves.append([gx - 200, 1, 3.5])
                    self.waves.append([gx + 200, -1, 3.5])
            if self.st > 1.6:
                self._go("idle")
        elif self.state == "summon":
            self.mouth = True
            if self.attack_i == 0:
                self.attack_i = 1
                for k in (-1, 1):
                    sc.enemies.append(Enemy("cronen_flyer", self.x + k * 160, self.y + 40, 1.4))
                    sc.portal_fx.append([self.x + k * 160, self.y + 20, 0.6])
                sc.audio.play("portal")
            if self.st > 1.0:
                self._go("idle")
        # contatto con la testa
        if sc.player.body.rect.colliderect(self.rect().inflate(-60, -60)):
            sc.player.hurt(15, self.x, sc)

    def _go(self, s):
        self.state = s
        self.st = 0.0
        self.attack_i = 0

    def _next(self, sc):
        seq = ["orbs", "shout", "beam_charge", "orbs", "beam_charge"]
        if self.phase2():
            seq = ["orbs", "beam_charge", "shout", "summon", "orbs", "beam_charge", "shout"]
        self._seq_i = getattr(self, "_seq_i", -1) + 1
        nxt = seq[self._seq_i % len(seq)]
        if nxt == "summon" and len([e for e in sc.enemies if not e.dead]) > 3:
            nxt = "orbs"
        p = sc.player.body
        self.beam_target = (p.cx, p.cy)
        self._go(nxt)

    def hurt(self, dmg, sc, src_x):
        if self.state in ("intro", "dying"):
            return
        self.hp -= dmg
        self.flash = 0.08
        sc.audio.play("hit", 0.5)
        if self.hp <= 0:
            self.hp = 0
            self.state = "dying"
            self.dying_t = 0
            self.mouth = True
            self.glow = False
            self.shout_t = 3.0
            sc.boss_defeated()

    def draw(self, surf, cx, cy):
        img = render_cromulon(self.mouth, self.glow, self.flash > 0)
        k = self.scale
        w, h = int(img.get_width() * k), int(img.get_height() * k)
        key = (self.mouth, self.glow, self.flash > 0, w)
        cache = _CROM_CACHE.setdefault("scaled", {})
        sc_img = cache.get(key)
        if sc_img is None:
            sc_img = pygame.transform.smoothscale(img, (w, h))
            cache[key] = sc_img
        x, y = self.x - cx, self.y - cy
        if self.state == "dying":
            x += random.uniform(-5, 5)
            y += random.uniform(-5, 5)
        draw_glow(surf, x, y, 260, (90, 40, 90), 0.7)
        surf.blit(sc_img, (x - w / 2, y - h * (200 / 380)))
        if self.state == "beam_charge":
            tx, ty = self.beam_target
            for ex, ey in self.eyes():
                draw_glow(surf, ex - cx, ey - cy, 40, (255, 60, 40))
                a = math.atan2(ty - ey, tx - ex)
                pygame.draw.line(surf, (255, 60, 50), (ex - cx, ey - cy),
                                 (ex - cx + math.cos(a) * 1600, ey - cy + math.sin(a) * 1600), 1)
        elif self.state == "beam":
            tx, ty = self.beam_target
            for ex, ey in self.eyes():
                a = math.atan2(ty - ey, tx - ex)
                end = (ex - cx + math.cos(a) * 1600, ey - cy + math.sin(a) * 1600)
                wbeam = int(26 + math.sin(self.t * 60) * 5)
                pygame.draw.line(surf, (255, 60, 40), (ex - cx, ey - cy), end, wbeam)
                pygame.draw.line(surf, (255, 200, 160), (ex - cx, ey - cy), end, wbeam // 3)
                draw_glow(surf, ex - cx, ey - cy, 60, (255, 90, 40))
        for wv in self.waves:
            wx = wv[0] - cx
            gy = 12 * TILE - cy
            draw_glow(surf, wx, gy - 14, 50, (255, 120, 220))
            pygame.draw.polygon(surf, (255, 150, 230), [(wx - 22, gy), (wx - 6, gy - 34), (wx + 6, gy - 34), (wx + 22, gy)])
            pygame.draw.polygon(surf, WHITE, [(wx - 10, gy), (wx - 2, gy - 22), (wx + 2, gy - 22), (wx + 10, gy)])


# =============================================================================
#  OGGETTI, PERSONAGGI, USCITA
# =============================================================================
class Pickup:
    def __init__(self, kind, x, y, drop=False):
        self.kind, self.x, self.y = kind, float(x), float(y)
        self.t = random.uniform(0, 6)
        self.dead = False
        self.vy = -320.0 if drop else 0.0
        self.drop = drop
        self.base_y = y

    def rect(self):
        w = 22 if self.kind == "coin" else 30
        return pygame.Rect(int(self.x - w / 2), int(self.y - w / 2), w, w)

    def update(self, dt, sc):
        self.t += dt
        if self.drop:
            self.vy += GRAVITY * 0.6 * dt
            self.y += self.vy * dt
            if sc.level.ground(int(self.x // TILE), int((self.y + 10) // TILE)) and self.vy > 0:
                self.y = (int((self.y + 10) // TILE)) * TILE - 12
                self.drop = False
                self.base_y = self.y
            if self.y > H + 20:
                self.dead = True
        # i semi e le monete vengono attratti un po' dal giocatore
        p = sc.player.body
        if self.kind in ("coin", "seed") and not self.drop:
            d = dist(self.x, self.y, p.cx, p.cy)
            if d < 70:
                self.x = lerp(self.x, p.cx, clamp(dt * 8, 0, 1))
                self.y = lerp(self.y, p.cy, clamp(dt * 8, 0, 1))

    def draw(self, surf, cx, cy):
        bob = 0 if self.drop else math.sin(self.t * 3) * 4
        x, y = self.x - cx, self.y - cy + bob
        if x < -60 or x > W + 60:
            return
        if self.kind == "coin":
            img = item_sprite("coin", int(self.t * 10) % 8)
            draw_glow(surf, x, y, 18, (90, 70, 10))
        elif self.kind == "seed":
            draw_glow(surf, x, y, 56, (160, 130, 30), 0.9 + 0.3 * math.sin(self.t * 4))
            img = item_sprite("seed")
        elif self.kind == "fluid":
            draw_glow(surf, x, y, 40, (40, 140, 30))
            img = item_sprite("fluid")
        else:
            draw_glow(surf, x, y, 34, (90, 90, 90) if self.kind == "flask" else (40, 70, 140))
            img = item_sprite(self.kind)
        surf.blit(img, (x - img.get_width() / 2, y - img.get_height() / 2))


class NPC:
    def __init__(self, x, y, lines):
        self.x, self.y = x, y
        self.lines = lines
        self.i = 0
        self.t = 0.0
        self.bubble = None
        self.near = False

    def update(self, dt, sc, inp):
        self.t += dt
        p = sc.player.body
        self.near = abs(p.cx - self.x) < 90 and abs(p.bottom - self.y) < 60
        if self.bubble:
            self.bubble.life -= dt
            if self.bubble.life <= 0:
                self.bubble = None
        if self.near and inp.hit("interact"):
            self.bubble = Bubble(self.lines[self.i % len(self.lines)], 4.5)
            self.i += 1
            sc.audio.play("select")

    def draw(self, surf, cx, cy):
        fr = int(self.t * 3) % 4
        blit_sprite(surf, "poopy", "idle", fr, 0, -1, self.x - cx, self.y - cy)
        if self.bubble:
            self.bubble.draw(surf, self.x - cx, self.y - 60 - cy)
        elif self.near:
            blit_text(surf, "[E] Parla", 16, (self.x - cx, self.y - 76 - cy), (255, 255, 200), "center",
                      kind="ui", bold=True, outline=OUTLINE)


class ExitPortal:
    def __init__(self, x, y):
        self.x, self.y = x, y - 70
        self.t = 0.0
        self.open = 0.0

    def rect(self):
        return pygame.Rect(int(self.x - 30), int(self.y - 60), 60, 120)

    def update(self, dt):
        self.t += dt
        self.open = min(1.0, self.open + dt * 1.5)

    def draw(self, surf, cx, cy):
        draw_portal(surf, self.x - cx, self.y - cy, 46, 74, self.t, self.open)
        if self.open >= 1:
            blit_text(surf, "USCITA", 16, (self.x - cx, self.y - cy - 96), (190, 255, 160), "center",
                      kind="title", outline=OUTLINE)


# =============================================================================
#  STORIA E LIVELLI
# =============================================================================
GAME_INTRO = [
    ("rick", "Morty! *burp* Morty, svegliati! Ho bisogno di te per una missione, Morty!"),
    ("morty", "Ma Rick... sono le tre di notte! Domani ho la verifica di matematica!"),
    ("rick", "La scuola non è un posto per persone intelligenti, Morty. Mi servono i Mega Semi per le mie ricerche."),
    ("rick", "E una razza di teste giganti distruggerà la Terra se non gli diamo uno spettacolo. Dettagli."),
    ("morty", "Aw jeez, Rick... va bene, va bene. Da dove cominciamo?"),
    ("rick", "Scegli una dimensione, apri un portale e cerca di non morire. Wubba Lubba Dub Dub!"),
]

LEVELS = [
    dict(id="cronenberg", name="Dimensione Cronenberg", sub="Quel che resta di una Terra... rovinata",
         theme="cronenberg", music="cronenberg", seed=1371, chunks=8, enemy_p=0.7, diff=1.0,
         ground=["cronen_walker"], air=["cronen_flyer"], player="rick", morty=True,
         intro=[("rick", "Ah, la dimensione Cronenberg. Quella che... ehm... abbiamo un po' rovinato noi, Morty."),
                ("morty", "Rick, questi mostri una volta erano persone!"),
                ("rick", "E adesso sono carne con le gambe. Prendi 3 Mega Semi e raggiungi il portale d'uscita."),
                ("rick", "Doppio salto con i miei stivali anti-gravità, laser e pistola portale. E occhio all'acido!")],
         outro=[("morty", "Ce l'abbiamo fatta! Ma ho visto delle cose, Rick... delle cose orribili."),
                ("rick", "Benvenuto nella scienza, Morty. *burp* Prossima dimensione.")],
         npc=["Uuuh-uiii! Ciao Rick, ciao Morty!",
              "Premi K per la pistola portale: ti teletrasporta in avanti, anche attraverso i muri sottili!",
              "Su+K o Giù+K e il portale va in diagonale. Uuuh-uiii!",
              "I Mega Semi brillano d'oro. Ce ne sono 3 in ogni dimensione!"]),
    dict(id="federation", name="Pianeta della Federazione", sub="I Gromflomiti sparano a vista",
         theme="federation", music="federation", seed=2022, chunks=9, enemy_p=0.8, diff=1.2,
         ground=["gromflomite"], air=["fed_drone"], player="rick", morty=True,
         intro=[("morty", "Rick, perché la Federazione Galattica ci dà la caccia?"),
                ("rick", "Perché sono burocrati con la faccia da insetto, Morty! Odiano la libertà. E odiano me."),
                ("rick", "Quando la pistola di un Gromflomita si illumina di rosso: salta o teletrasportati!")],
         outro=[("morty", "Rick, abbiamo appena fatto esplodere mezza base della Federazione!"),
                ("rick", "Si chiama diplomazia interdimensionale, Morty. Impara.")],
         npc=["Uuuh-uiii! Anche qui? Che coincidenza!",
              "Salta in testa ai nemici per schiacciarli! Tranne le guardie corazzate...",
              "Poca vita? Premi H per bere dalla fiaschetta di Rick!"]),
    dict(id="sewer", name="Le Fogne: Pickle Rick", sub="Un sottaceto contro un esercito di ratti",
         theme="sewer", music="sewer", seed=3033, chunks=9, enemy_p=0.85, diff=1.3,
         ground=["rat"], air=["roach"], player="pickle", morty=False,
         intro=[("pickle", "Morty! Guardami! Mi sono trasformato in un sottaceto! Sono PICKLE RIIICK!"),
                ("morty", "(alla radio) Rick, sei finito nelle fogne! E la terapia di famiglia?!"),
                ("pickle", "La terapia è per chi non sa trasformarsi in un sottaceto, Morty."),
                ("pickle", "Mi sono costruito un'armatura con parti di ratto. Ora esco di qui. Da solo. Funky!")],
         outro=[("pickle", "Fuori dalle fogne! Ora mi ritrasformo in umano... più o meno."),
                ("rick", "*burp* Non dirlo alla psicologa, Morty.")],
         npc=None),
    dict(id="citadel", name="La Cittadella dei Rick", sub="Mille Rick, nessuno simpatico",
         theme="citadel", music="citadel", seed=4044, chunks=10, enemy_p=0.85, diff=1.45,
         ground=["guard"], air=["citadel_drone"], player="rick", morty=True,
         intro=[("rick", "La Cittadella dei Rick. Un posto pieno di versioni di me... ma peggiori."),
                ("morty", "Anche i Rick guardiani vogliono arrestarci?"),
                ("rick", "Il Consiglio dei Rick odia un Rick che non segue le regole. Cioè, io. Spara, Morty!")],
         outro=[("morty", "Rick... quel Morty con la benda sull'occhio ci fissava in modo strano."),
                ("rick", "Tutti i Morty sono strani, Morty. Andiamo: i Cromulon ci aspettano.")],
         npc=["Uuuh-uiii! Sono in vacanza alla Cittadella!",
              "Le guardie Rick hanno l'elmetto: non puoi schiacciarle saltando!",
              "La scatola Meeseeks evoca un aiutante. Per lui esistere è dolore, ma combatte!"]),
    dict(id="arena", name="L'Arena dei Cromulon", sub="MOSTRAMI COSA SAI FARE!", boss=True,
         theme="arena", music="boss", seed=5055, chunks=0, enemy_p=0, diff=1.5,
         ground=[], air=[], player="rick", morty=True,
         intro=[("cromulon", "MOSTRAMI COSA SAI FARE!"),
                ("morty", "Rick! C'è una testa gigante nel cielo!"),
                ("rick", "Un Cromulon, Morty. Vogliono uno spettacolo, altrimenti distruggono il pianeta."),
                ("rick", "Diamogli uno spettacolo a colpi di laser! Salta le onde d'urto ed evita i raggi dagli occhi!")],
         outro=[("cromulon", "...NON MALE. NON MALE PER NIENTE! CI PIACE!"),
                ("morty", "Ce l'abbiamo fatta, Rick! Abbiamo salvato la Terra!"),
                ("rick", "Ovvio, Morty. È così che si diventa Schwifty. Wubba Lubba Dub Dub!")],
         npc=None),
]

DEATH_QUOTES = [
    "Nel multiverso c'è un altro me che ce l'ha fatta. Riprova.",
    "Sono morto? Pazzesco. Ricarico da un backup del cervello.",
    "Anche i geni sbagliano. Raramente. Riprova.",
    "Nessuno esiste di proposito, Morty. Ma riprova lo stesso.",
]
GARAGE_TIPS = [
    "Rick: \"Mega Semi, Morty! Ficcateli dove sai tu... cioè, nella borsa.\"",
    "Rick: \"Il fluido portale si ricarica da solo. Come il mio fegato.\"",
    "Morty: \"Rick, possiamo fare un'avventura normale, per una volta?\"",
    "Rick: \"Doppio salto, Morty! Gli stivali anti-gravità non si pagano da soli.\"",
    "Rick: \"Se ti perdi, premi Esc. Se ti perdi nella vita... beh, benvenuto.\"",
]

SPEAKERS = {
    "rick": ("Rick", (150, 230, 255)),
    "morty": ("Morty", (255, 230, 100)),
    "pickle": ("Pickle Rick", (140, 230, 100)),
    "meeseeks": ("Mr. Meeseeks", (140, 200, 255)),
    "poopy": ("Mr. Poopybutthole", (255, 210, 110)),
    "cromulon": ("Cromulon", (255, 140, 200)),
}


# =============================================================================
#  INTERFACCIA: dialoghi, pannelli, menu
# =============================================================================
def panel(surf, rect, alpha=200, border=(90, 220, 90), radius=16):
    s = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(s, (10, 14, 22, alpha), s.get_rect(), border_radius=radius)
    pygame.draw.rect(s, border, s.get_rect(), 3, border_radius=radius)
    surf.blit(s, rect.topleft)


def draw_menu(surf, items, sel, cx, y, t, size=34, gap=54):
    for i, it in enumerate(items):
        on = i == sel
        col = (180, 255, 120) if on else (230, 230, 230)
        label = ("> " + it + " <") if on else it
        r = blit_text(surf, label, size + (4 if on else 0), (cx, y + i * gap), col, "center", kind="title",
                      outline=OUTLINE, ow=3)
        if on:
            draw_glow(surf, r.centerx, r.centery, 70, (30, 80, 20), 0.6 + 0.2 * math.sin(t * 5))


class Dialog:
    def __init__(self, game, lines):
        self.game = game
        self.lines = lines
        self.i = 0
        self.chars = 0.0
        self.done = not lines
        self.t = 0.0
        self.beep = 0

    def update(self, dt, inp):
        if self.done:
            return
        self.t += dt
        who, line = self.lines[self.i]
        self.chars = min(len(line), self.chars + 62 * dt)
        if inp.any_confirm() or inp.hit("interact"):
            if self.chars < len(line):
                self.chars = len(line)
            else:
                self.i += 1
                self.chars = 0
                self.game.audio.play("select")
                if self.i >= len(self.lines):
                    self.done = True
        elif inp.hit("back"):
            self.done = True

    def draw(self, surf):
        if self.done:
            return
        who, line = self.lines[self.i]
        name, col = SPEAKERS[who]
        box = pygame.Rect(50, H - 214, W - 100, 188)
        panel(surf, box, 225, border=col)
        pr = pygame.Rect(box.x + 18, box.y + 18, 152, 152)
        pygame.draw.rect(surf, (30, 36, 50), pr, border_radius=14)
        pygame.draw.rect(surf, col, pr, 3, border_radius=14)
        img = portrait(who, 144)
        surf.blit(img, (pr.x + 4, pr.y + 4))
        blit_text(surf, name, 28, (pr.right + 22, box.y + 14), col, kind="title", outline=OUTLINE, ow=2)
        shown = line[:int(self.chars)]
        f = font(24, "ui")
        yy = box.y + 58
        for l in wrap_text(shown, 24, box.right - pr.right - 50):
            surf.blit(f.render(l, True, (240, 240, 240)), (pr.right + 22, yy))
            yy += 32
        if self.chars >= len(line) and int(self.t * 3) % 2 == 0:
            blit_text(surf, "Invio / Spazio  >", 16, (box.right - 20, box.bottom - 14), (190, 255, 160), "bottomright",
                      bold=True)
        blit_text(surf, "Esc: salta", 14, (box.right - 20, box.y + 12), (150, 150, 160), "topright")


# =============================================================================
#  SCENE
# =============================================================================
class Scene:
    def __init__(self, game):
        self.game = game

    def update(self, dt, inp):
        pass

    def draw(self, surf):
        pass


class LevelScene(Scene):
    def __init__(self, game, idx):
        super().__init__(game)
        self.idx = idx
        self.ld = ld = LEVELS[idx]
        self.audio = game.audio
        self.level = Level(ld)
        self.theme = ld["theme"]
        self.tiles = game.tileset(self.theme)
        self.bg = Background(self.theme)
        self.vignette = game.vignette(THEMES[self.theme]["vignette"])
        self.dark = THEMES[self.theme]["dark"]
        self.dark_surf = pygame.Surface((W, H), pygame.SRCALPHA) if self.dark else None
        sx, sy = self.level.start
        self.player = Player(sx, sy, ld["player"])
        self.morty = Morty(sx - 52, sy) if ld["morty"] else None
        self.enemies, self.pickups, self.allies, self.projectiles = [], [], [], []
        self.particles = Particles()
        self.texts, self.flashes, self.portal_fx = [], [], []
        for kind, x, y in self.level.spawns:
            if kind in ENEMY_DEFS:
                self.enemies.append(Enemy(kind, x, y, ld["diff"]))
            else:
                self.pickups.append(Pickup(kind, x, y))
        self.npc = NPC(self.level.npc[0], self.level.npc[1], ld["npc"]) if (self.level.npc and ld.get("npc")) else None
        self.exit = ExitPortal(*self.level.exit) if self.level.exit else None
        self.boss = Cromulon(self.level.pw) if self.level.boss else None
        self.cam = Camera(self.level.pw)
        self.cam.update(0, self.player.body.cx, snap=True)
        self.score = self.coins = self.seeds = self.kills = self.hits_taken = 0
        self.time = 0.0
        self.t = 0.0
        self.title_t = 4.5
        self.burp_t = 0.0
        self.state_t = 0.0
        self.menu_i = 0
        self.state = "dialog"
        self.dialog = Dialog(game, ld["intro"])
        self.after_dialog = "play"
        self.portal_fx.append([sx, sy - 44, 1.3])
        if self.morty:
            self.portal_fx.append([sx - 52, sy - 36, 1.3])
        self.audio.music(ld["music"])
        self.death_quote = random.choice(DEATH_QUOTES)
        self.final = None
        self.beam_surf = None

    # ---- servizi per le entita' ----------------------------------------------
    def add_text(self, x, y, s, color=(255, 240, 120), size=22, life=1.0):
        self.texts.append(FloatText(x, y, s, color, size, life))

    def spawn_pickup(self, kind, x, y, drop=False):
        self.pickups.append(Pickup(kind, x, y, drop))

    def on_screen(self, x, margin=200):
        return self.cam.x - margin < x < self.cam.x + W + margin

    def auto_target(self, ox, oy, facing):
        best, bs = None, 1e9
        cands = [(e.body.cx, e.body.cy) for e in self.enemies if not e.dead and self.on_screen(e.body.cx, 0)]
        if self.boss and not self.boss.dead and self.boss.state not in ("intro", "dying"):
            cands.append((self.boss.x, self.boss.y))
        for (x, y) in cands:
            dx, dy = x - ox, y - oy
            d = math.hypot(dx, dy)
            if d > 760 or dx * facing < -10:
                continue
            ang = abs(math.atan2(dy, abs(dx)))
            if ang > math.radians(80):
                continue
            if self.boss is None or (x, y) != (self.boss.x, self.boss.y):
                if not self.level.ray_clear(ox, oy, x, y):
                    continue
            score = d * (1 + ang)
            if score < bs:
                best, bs = (x, y), score
        return best

    def nearest_enemy_obj(self, x, y, r):
        best, bd = None, r
        for e in self.enemies:
            if e.dead:
                continue
            d = dist(x, y, e.body.cx, e.body.cy)
            if d < bd:
                best, bd = e, d
        return best

    def nearest_enemy(self, x, y, r):
        e = self.nearest_enemy_obj(x, y, r)
        if e is not None:
            return (e.body.cx, e.body.cy)
        if self.boss and not self.boss.dead and self.boss.state not in ("intro", "dying"):
            if dist(x, y, self.boss.x, self.boss.y) < r + 300:
                return (self.boss.x, self.boss.y)
        return None

    def player_fell(self):
        p = self.player
        if p.dead or self.state != "play":
            return
        p.hp -= 20
        self.hits_taken += 1
        self.audio.play("hurt")
        self.cam.shake(10)
        self.particles.burst(p.body.cx, p.body.bottom, 20, (140, 255, 90), 260, 0.6, 4, 400)
        if p.hp <= 0:
            p.hp = 0
            p.dead = True
            p.visible = False
            self.player_died()
            return
        x, y = p.last_safe
        p.body.x, p.body.y = x - p.body.w / 2, y - p.body.h
        p.body.vx = p.body.vy = 0
        p.inv = 1.4
        self.portal_fx.append([p.body.cx, p.body.cy, 0.7])
        self.audio.play("portal", 0.6)
        p.say(random.choice(["Fiuu! Salvato da un portale.", "Questo acido brucia, Morty!", "*burp* Riproviamo."]), 2.0)

    def player_died(self):
        self.state = "dying"
        self.state_t = 0.0
        self.audio.play("death")
        b = self.player.body
        self.particles.burst(b.cx, b.cy, 40, (255, 120, 100), 380, 1.0, 5, 600)
        self.cam.shake(14)

    def boss_defeated(self):
        self.score += 5000
        self.add_text(self.boss.x, self.boss.y + 140, "+5000", (255, 230, 120), 36, 2.0)
        self.player.say("Wubba Lubba Dub Dub!", 3.0)
        if self.morty:
            self.morty.say("L'abbiamo battuto, Rick!", 3.0)
        for e in self.enemies:
            if not e.dead:
                e.die(self)

    # ---- aggiornamento -----------------------------------------------------------
    def update(self, dt, inp):
        self.t += dt
        self.state_t += dt
        st = self.state
        if st == "dialog":
            self.dialog.update(dt, inp)
            self._update_ambient(dt)
            if self.dialog.done:
                self.state = self.after_dialog
                self.state_t = 0.0
            return
        if st == "pause":
            self._update_pause(inp)
            return
        if st == "dead":
            if inp.any_confirm():
                self.game.change(lambda: LevelScene(self.game, self.idx))
            elif inp.hit("back"):
                self.game.change(lambda: GarageScene(self.game, self.idx))
            self._update_ambient(dt)
            return
        if st == "summary":
            if self.state_t > 0.6 and (inp.any_confirm() or inp.hit("back")):
                self._finish()
            self._update_ambient(dt)
            return
        if st == "dying":
            self._update_ambient(dt)
            if self.state_t > 1.8:
                self.state = "dead"
                self.state_t = 0
            return
        if st == "exiting":
            self._update_ambient(dt)
            if self.state_t > 1.2:
                self._complete()
            return
        # ---- gioco attivo ----
        if inp.hit("pause"):
            self.state = "pause"
            self.menu_i = 0
            self.audio.play("select")
            return
        self.time += dt
        self.title_t -= dt
        if self.burp_t > 0:
            self.burp_t -= dt
            if self.burp_t <= 0:
                self.audio.play("burp")
                self.cam.shake(4)
        p = self.player
        p.update(dt, self, inp)
        if self.morty:
            self.morty.update(dt, self)
        for a in self.allies:
            a.update(dt, self)
        self.allies = [a for a in self.allies if not a.dead]
        if self.npc:
            self.npc.update(dt, self, inp)
        if self.boss and not self.boss.dead:
            self.boss.update(dt, self)
            if self.boss.dead:
                self.exit = ExitPortal(self.level.pw / 2, 12 * TILE)
                self.audio.play("portal")
        # nemici
        pr = p.body.rect
        mr = self.morty.body.rect if self.morty else None
        for e in self.enemies:
            if e.dead or not self.on_screen(e.body.cx, 260):
                continue
            e.update(dt, self)
            if e.dead:
                continue
            er = e.rect()
            if er.colliderect(pr) and not p.dead:
                if e.d["stomp"] and p.body.vy > 120 and pr.bottom - er.top < 26:
                    e.hurt(2, self, p.body.cx)
                    p.body.vy = -680
                    p.air_jumps = 1
                    self.audio.play("stomp")
                    self.particles.burst(p.body.cx, pr.bottom, 10, (255, 255, 200), 200, 0.3, 3, 0, "spark")
                else:
                    p.hurt(e.d["dmg"], e.body.cx, self)
            if mr is not None and er.colliderect(mr):
                self.morty.hurt(self, e.body.cx)
        self.enemies = [e for e in self.enemies if not e.dead]
        # proiettili
        for pj in self.projectiles:
            pj.update(dt, self)
            if pj.dead:
                continue
            if pj.owner == "player":
                for e in self.enemies:
                    if not e.dead and e.rect().inflate(8, 8).collidepoint(pj.x, pj.y):
                        e.hurt(pj.dmg, self, pj.x - pj.vx * 0.02)
                        pj.dead = True
                        self.particles.burst(pj.x, pj.y, 6, pj.color, 200, 0.25, 2, 0, "spark", True)
                        break
                if not pj.dead and self.boss and not self.boss.dead and self.boss.rect().collidepoint(pj.x, pj.y):
                    self.boss.hurt(pj.dmg, self, pj.x)
                    pj.dead = True
                    self.particles.burst(pj.x, pj.y, 6, pj.color, 200, 0.25, 2, 0, "spark", True)
            else:
                if pr.inflate(-6, -6).collidepoint(pj.x, pj.y) and not p.dead:
                    if p.hurt(pj.dmg, pj.x, self) or p.inv > 0:
                        pj.dead = True
                elif mr is not None and mr.collidepoint(pj.x, pj.y):
                    self.morty.hurt(self, pj.x)
                    pj.dead = True
        self.projectiles = [pj for pj in self.projectiles if not pj.dead]
        # oggetti
        for pk in self.pickups:
            pk.update(dt, self)
            if not pk.dead and pk.rect().colliderect(pr) and not p.dead:
                self._collect(pk)
        self.pickups = [pk for pk in self.pickups if not pk.dead]
        # uscita
        if self.exit:
            self.exit.update(dt)
            if self.exit.open >= 1 and self.exit.rect().colliderect(pr) and not p.dead:
                self._enter_exit()
        self._update_ambient(dt)

    def _update_ambient(self, dt):
        self.particles.update(dt)
        self.texts = [t for t in self.texts if t.update(dt)]
        for f in self.flashes:
            f[2] -= dt
        self.flashes = [f for f in self.flashes if f[2] > 0]
        for f in self.portal_fx:
            f[2] -= dt
        self.portal_fx = [f for f in self.portal_fx if f[2] > 0]
        if self.state not in ("dialog",):
            pass
        self.cam.update(dt, self.player.body.cx + self.player.facing * 70)
        if self.state == "dialog" and self.boss:
            self.boss.t += dt
            self.boss.y = lerp(self.boss.y, 120, clamp(dt, 0, 1))
            self.boss.mouth = self.dialog.lines[min(self.dialog.i, len(self.dialog.lines) - 1)][0] == "cromulon" and int(self.t * 6) % 2 == 0

    def _collect(self, pk):
        p = self.player
        pk.dead = True
        k = pk.kind
        if k == "coin":
            self.coins += 1
            self.score += 10
            self.audio.play("coin", 0.7)
            self.particles.burst(pk.x, pk.y, 5, (255, 230, 120), 120, 0.3, 2, 0, "spark", True)
        elif k == "seed":
            self.seeds += 1
            self.score += 500
            self.audio.play("seed")
            self.add_text(pk.x, pk.y - 30, "MEGA SEME! %d/3" % self.seeds, (255, 220, 80), 30, 1.8)
            self.particles.burst(pk.x, pk.y, 30, (255, 220, 90), 300, 0.9, 4, 100, "dot", True)
            line = ["Ottimo! Un Mega Seme!", "Questi semi sono roba forte, Morty.", "*burp* Un altro seme!"][self.seeds % 3]
            p.say(line if p.kind == "rick" else "Funky! Un Mega Seme!", 2.0)
        elif k == "flask":
            p.flasks = min(5, p.flasks + 1)
            self.add_text(pk.x, pk.y - 20, "+1 Fiaschetta (H)", (200, 220, 255), 22)
            self.audio.play("powerup")
        elif k == "fluid":
            p.fluid = 100
            p.hp = min(p.max_hp, p.hp + 10)
            self.add_text(pk.x, pk.y - 20, "Fluido portale!", (140, 255, 110), 22)
            self.audio.play("powerup")
        elif k == "box":
            mx = p.body.cx
            for off in (40, -40, 80, -80):
                if self.level.rect_free(pygame.Rect(int(p.body.cx + off - 13), int(p.body.bottom - 90), 26, 90)):
                    mx = p.body.cx + off
                    break
            self.allies.append(Meeseeks(mx, p.body.bottom))
            self.add_text(pk.x, pk.y - 20, "Mr. Meeseeks!", (140, 200, 255), 26)
            self.audio.play("powerup")
            self.audio.play("poof", 0.6)
            self.particles.burst(mx, p.body.bottom - 45, 30, (124, 192, 242), 240, 0.6, 4, 0, "smoke")

    def _enter_exit(self):
        self.state = "exiting"
        self.state_t = 0.0
        self.audio.play("portal")
        self.player.visible = False
        b = self.player.body
        self.particles.burst(b.cx, b.cy, 40, PORTAL_GREEN, 300, 0.8, 4, 0, "dot", True)
        if self.morty:
            self.morty.visible = False
            self.particles.burst(self.morty.body.cx, self.morty.body.cy, 20, PORTAL_GREEN, 200, 0.6, 3, 0, "dot", True)

    def _complete(self):
        bonus_time = max(0, int(3000 - self.time * 12)) if not self.boss else max(0, int(4000 - self.time * 20))
        bonus_hp = int(self.player.hp * 10)
        self.final = dict(score=self.score + bonus_time + bonus_hp, bonus_time=bonus_time, bonus_hp=bonus_hp)
        if self.ld["outro"]:
            self.dialog = Dialog(self.game, self.ld["outro"])
            self.state = "dialog"
            self.after_dialog = "summary"
        else:
            self.state = "summary"
        self.state_t = 0.0
        self.audio.play("confirm")

    def _finish(self):
        save = self.game.save
        lid = self.ld["id"]
        save["seeds"][lid] = max(save["seeds"].get(lid, 0), self.seeds)
        save["best"][lid] = max(save["best"].get(lid, 0), self.final["score"])
        save["unlocked"] = max(save["unlocked"], min(len(LEVELS), self.idx + 2))
        last = self.idx == len(LEVELS) - 1
        if last:
            save["completed"] = True
        write_save(save)
        if last:
            self.game.change(lambda: VictoryScene(self.game))
        else:
            self.game.change(lambda: GarageScene(self.game, min(len(LEVELS) - 1, self.idx + 1)))

    def _update_pause(self, inp):
        items = self._pause_items()
        if inp.hit("menu_up"):
            self.menu_i = (self.menu_i - 1) % len(items)
            self.audio.play("select")
        elif inp.hit("menu_down"):
            self.menu_i = (self.menu_i + 1) % len(items)
            self.audio.play("select")
        elif inp.hit("back") or inp.hit("pause"):
            self.state = "play"
        elif inp.hit("confirm"):
            self.audio.play("confirm")
            if self.menu_i == 0:
                self.state = "play"
            elif self.menu_i == 1:
                self.game.change(lambda: LevelScene(self.game, self.idx))
            elif self.menu_i == 2:
                self.game.change(lambda: GarageScene(self.game, self.idx))
            elif self.menu_i == 3:
                self.game.toggle_audio()

    def _pause_items(self):
        return ["Riprendi", "Ricomincia livello", "Torna al garage",
                "Audio: " + ("ON" if self.audio.enabled else "OFF")]

    # ---- disegno -------------------------------------------------------------------
    def draw(self, surf):
        cx, cy = self.cam.cx, self.cam.cy
        self.bg.draw(surf, cx, self.t)
        if self.boss and not self.boss.dead:
            self.boss.draw(surf, cx, cy)
        self._draw_tiles(surf, cx, cy)
        if self.exit:
            self.exit.draw(surf, cx, cy)
        if self.npc:
            self.npc.draw(surf, cx, cy)
        for pk in self.pickups:
            pk.draw(surf, cx, cy)
        for e in self.enemies:
            if self.on_screen(e.body.cx, 80):
                e.draw(surf, cx, cy)
        if self.morty:
            self.morty.draw(surf, cx, cy)
        for a in self.allies:
            a.draw(surf, cx, cy)
        if self.state != "dying" and self.state != "dead":
            self.player.draw(surf, cx, cy)
        for pj in self.projectiles:
            pj.draw(surf, cx, cy)
        for f in self.flashes:
            draw_glow(surf, f[0] - cx, f[1] - cy, 34, f[3])
        for f in self.portal_fx:
            k = f[2]
            sc = clamp(min(k * 4, 1.0), 0, 1)
            draw_portal(surf, f[0] - cx, f[1] - cy, 30, 52, self.t, sc)
        self.particles.draw(surf, cx, cy)
        for t in self.texts:
            t.draw(surf, cx, cy)
        if self.dark_surf is not None:
            self._draw_darkness(surf, cx, cy)
        surf.blit(self.vignette, (0, 0))
        if self.state in ("play", "dialog", "pause"):
            self.player.draw_bubble(surf, cx, cy)
            if self.morty:
                self.morty.draw_bubble(surf, cx, cy)
        self._draw_hud(surf)
        st = self.state
        if st == "dialog":
            self.dialog.draw(surf)
        elif st == "pause":
            self._draw_pause(surf)
        elif st == "dead":
            self._draw_dead(surf)
        elif st == "summary":
            self._draw_summary(surf)
        if self.boss and self.boss.shout_t > 0 and st != "dialog":
            k = self.boss.shout_t
            txt = "MOSTRAMI COSA SAI FARE!" if self.boss.state != "dying" else "NON MALE! NON MALE!"
            size = 54 + int(math.sin(self.t * 30) * 3)
            img = text(txt, size, (255, 230, 120), kind="title", outline=(120, 20, 60), ow=4)
            if k < 0.5:
                img = img.copy()
                img.set_alpha(int(255 * k * 2))
            surf.blit(img, (W / 2 - img.get_width() / 2 + random.uniform(-3, 3), 120 + random.uniform(-3, 3)))

    def _draw_tiles(self, surf, cx, cy):
        lvl, ts = self.level, self.tiles
        t0 = max(0, cx // TILE)
        t1 = min(lvl.wt - 1, (cx + W) // TILE + 1)
        af = int(self.t * 8)
        grid = lvl.grid
        for ty in range(ROWS):
            row = grid[ty]
            y = ty * TILE - cy
            for tx in range(t0, t1 + 1):
                ch = row[tx]
                if ch == ".":
                    continue
                x = tx * TILE - cx
                if ch == "#":
                    above = ty > 0 and grid[ty - 1][tx] == "#"
                    v = (tx * 7 + ty * 13) % 3
                    surf.blit(ts.inner[v] if above else ts.top[v], (x, y))
                    if tx > 0 and row[tx - 1] != "#":
                        pygame.draw.line(surf, OUTLINE, (x, y), (x, y + TILE), 3)
                    if tx < lvl.wt - 1 and row[tx + 1] != "#":
                        pygame.draw.line(surf, OUTLINE, (x + TILE - 2, y), (x + TILE - 2, y + TILE), 3)
                    if not above:
                        pygame.draw.line(surf, OUTLINE, (x, y), (x + TILE, y), 2)
                        if ty > 0 and grid[ty - 1][tx] == "." and (tx * 31 + ty * 17) % 7 == 0:
                            d = ts.deco[(tx * 5 + ty) % len(ts.deco)]
                            surf.blit(d, (x + 4, y - 38))
                elif ch == "=":
                    surf.blit(ts.oneway, (x, y))
                elif ch == "~":
                    surf.blit(ts.acid[(af + tx) % 8], (x, y))
                    if tx % 2 == 0:
                        draw_glow(surf, x + 24, y + 8, 44, (30, 90, 20), 0.8)

    def _draw_darkness(self, surf, cx, cy):
        d = self.dark_surf
        d.fill((0, 0, 0, self.dark))
        lights = []
        b = self.player.body
        if self.player.visible:
            lights.append((b.cx - cx, b.cy - cy, 300, self.dark))
        for pj in self.projectiles:
            lights.append((pj.x - cx, pj.y - cy, 96, 150))
        for f in self.flashes:
            lights.append((f[0] - cx, f[1] - cy, 140, 170))
        for pk in self.pickups:
            if pk.kind == "seed":
                lights.append((pk.x - cx, pk.y - cy, 110, 140))
        for f in self.portal_fx:
            lights.append((f[0] - cx, f[1] - cy, 160, 160))
        if self.exit:
            lights.append((self.exit.x - cx, self.exit.y - cy, 240, 170))
        for a in self.allies:
            lights.append((a.body.cx - cx, a.body.cy - cy, 160, 120))
        t0 = max(0, cx // TILE)
        for tx in range(t0, min(self.level.wt, t0 + W // TILE + 2), 2):
            if self.level.grid[ROWS - 1][tx] == "~":
                lights.append((tx * TILE + 24 - cx, (ROWS - 1) * TILE - cy, 110, 120))
        for x, y, r, pw in lights:
            if -r < x < W + r and -r < y < H + r:
                ls = light_surf(r, pw)
                rr = ls.get_width() // 2
                d.blit(ls, (int(x) - rr, int(y) - rr), special_flags=pygame.BLEND_RGBA_SUB)
        surf.blit(d, (0, 0))

    def _draw_hud(self, surf):
        p = self.player
        panel(surf, pygame.Rect(12, 10, 386, 96), 190, border=(80, 200, 90), radius=14)
        who = "rick" if p.kind == "rick" else "pickle"
        pygame.draw.circle(surf, (30, 36, 50), (58, 58), 40)
        surf.blit(portrait(who, 72), (22, 22))
        pygame.draw.circle(surf, (80, 200, 90), (58, 58), 40, 3)
        # vita
        r = pygame.Rect(110, 22, 270, 20)
        pygame.draw.rect(surf, (60, 16, 20), r, border_radius=6)
        k = p.hp / p.max_hp
        col = lerp_col((230, 50, 50), (90, 230, 80), k)
        if k > 0:
            pygame.draw.rect(surf, col, (r.x, r.y, int(r.w * k), r.h), border_radius=6)
        pygame.draw.rect(surf, OUTLINE, r, 2, border_radius=6)
        blit_text(surf, "VITA %d" % p.hp, 15, (r.x + 8, r.centery), WHITE, "midleft", bold=True, outline=OUTLINE, ow=1)
        # fluido portale
        r2 = pygame.Rect(110, 50, 220, 14)
        pygame.draw.rect(surf, (16, 40, 16), r2, border_radius=5)
        kf = p.fluid / 100.0
        pygame.draw.rect(surf, (110, 240, 60) if p.fluid >= PORTAL_COST else (70, 130, 50),
                         (r2.x, r2.y, int(r2.w * kf), r2.h), border_radius=5)
        for m in (PORTAL_COST, PORTAL_COST * 2):
            mx = r2.x + int(r2.w * m / 100)
            pygame.draw.line(surf, OUTLINE, (mx, r2.y), (mx, r2.bottom), 1)
        pygame.draw.rect(surf, OUTLINE, r2, 2, border_radius=5)
        blit_text(surf, "PORTALE", 12, (r2.right + 8, r2.centery), (170, 255, 140), "midleft", bold=True)
        # fiaschette
        fl = pygame.transform.smoothscale(item_sprite("flask"), (17, 22))
        for i in range(p.flasks):
            surf.blit(fl, (112 + i * 22, 72))
        blit_text(surf, "H", 13, (112 + max(1, p.flasks) * 22 + 6, 83), (200, 200, 210), "midleft", bold=True)
        # destra: schmeckles e semi
        panel(surf, pygame.Rect(W - 312, 10, 300, 96), 190, border=(220, 190, 80), radius=14)
        surf.blit(item_sprite("coin", 0), (W - 296, 22))
        blit_text(surf, "Schmeckles: %d" % self.coins, 20, (W - 266, 33), (255, 230, 120), "midleft", bold=True, outline=OUTLINE, ow=1)
        blit_text(surf, "Punti: %d" % self.score, 18, (W - 296, 66), WHITE, "midleft", bold=True, outline=OUTLINE, ow=1)
        if not self.boss:
            seed = pygame.transform.smoothscale(item_sprite("seed"), (20, 26))
            ghost = seed.copy()
            ghost.set_alpha(60)
            for i in range(3):
                surf.blit(seed if i < self.seeds else ghost, (W - 104 + i * 28, 54))
        # titolo del livello
        if self.title_t > 0 and self.state == "play":
            a = clamp(self.title_t, 0, 1)
            img = text(self.ld["name"].upper(), 50, THEMES[self.theme]["title_col"], kind="title", outline=OUTLINE, ow=4)
            img2 = text(self.ld["sub"], 22, WHITE, kind="ui", bold=True, outline=OUTLINE, ow=2)
            if a < 1:
                img, img2 = img.copy(), img2.copy()
                img.set_alpha(int(255 * a))
                img2.set_alpha(int(255 * a))
            surf.blit(img, (W / 2 - img.get_width() / 2, 150))
            surf.blit(img2, (W / 2 - img2.get_width() / 2, 214))
        if self.idx == 0 and self.time < 14 and self.state == "play":
            blit_text(surf, "A/D muovi  -  Spazio salta (x2 doppio)  -  J o Click spara  -  K o Click dx portale  -  H fiaschetta  -  E parla",
                      16, (W / 2, H - 22), (230, 255, 220), "center", bold=True, outline=OUTLINE, ow=2)
        # barra del boss
        b = self.boss
        if b and not b.dead and b.state != "intro" and self.state == "play":
            r = pygame.Rect(W / 2 - 320, H - 52, 640, 22)
            pygame.draw.rect(surf, (40, 10, 30), r, border_radius=8)
            pygame.draw.rect(surf, (255, 90, 190), (r.x, r.y, int(r.w * b.hp / b.MAX_HP), r.h), border_radius=8)
            pygame.draw.rect(surf, OUTLINE, r, 3, border_radius=8)
            blit_text(surf, "CROMULON", 22, (W / 2, r.y - 16), (255, 170, 230), "center", kind="title", outline=OUTLINE, ow=2)

    def _dim(self, surf, a=150):
        s = pygame.Surface((W, H), pygame.SRCALPHA)
        s.fill((0, 0, 0, a))
        surf.blit(s, (0, 0))

    def _draw_pause(self, surf):
        self._dim(surf)
        blit_text(surf, "PAUSA", 80, (W / 2, 170), (180, 255, 140), "center", kind="title", outline=OUTLINE, ow=4)
        draw_menu(surf, self._pause_items(), self.menu_i, W / 2, 300, self.t)
        blit_text(surf, "Su/Giu per scegliere - Invio per confermare - Esc per riprendere", 16, (W / 2, H - 40),
                  (200, 200, 200), "center")

    def _draw_dead(self, surf):
        self._dim(surf, 170)
        blit_text(surf, "SEI MORTO!", 90, (W / 2, 220), (255, 90, 80), "center", kind="title", outline=OUTLINE, ow=5)
        blit_text(surf, "Rick: \"" + self.death_quote + "\"", 22, (W / 2, 320), (230, 230, 230), "center", bold=True,
                  outline=OUTLINE, ow=2)
        if int(self.t * 2) % 2 == 0:
            blit_text(surf, "Invio: riprova        Esc: torna al garage", 28, (W / 2, 430), (180, 255, 140), "center",
                      kind="title", outline=OUTLINE, ow=3)

    def _draw_summary(self, surf):
        self._dim(surf, 160)
        box = pygame.Rect(W / 2 - 360, 96, 720, 540)
        draw_portal(surf, box.x - 80, box.centery, 46, 78, self.t, 1.0)
        draw_portal(surf, box.right + 80, box.centery, 46, 78, self.t + 1, 1.0)
        panel(surf, box, 230, border=(110, 240, 80), radius=22)
        blit_text(surf, "DIMENSIONE COMPLETATA!", 46, (W / 2, box.y + 52), (180, 255, 140), "center", kind="title",
                  outline=OUTLINE, ow=3)
        blit_text(surf, self.ld["name"], 24, (W / 2, box.y + 104), WHITE, "center", bold=True)
        f = self.final or dict(score=self.score, bonus_time=0, bonus_hp=0)
        rows = [("Mega Semi", "%d / 3" % self.seeds if not self.boss else "-"),
                ("Schmeckles", str(self.coins)),
                ("Nemici sconfitti", str(self.kills)),
                ("Tempo", "%d:%02d" % (int(self.time) // 60, int(self.time) % 60)),
                ("Bonus tempo", "+%d" % f["bonus_time"]),
                ("Bonus vita", "+%d" % f["bonus_hp"])]
        y = box.y + 156
        for k, v in rows:
            blit_text(surf, k, 24, (box.x + 120, y), (220, 220, 230), "midleft", bold=True)
            blit_text(surf, v, 24, (box.right - 120, y), (255, 230, 120), "midright", bold=True)
            y += 40
        blit_text(surf, "PUNTEGGIO: %d" % f["score"], 40, (W / 2, y + 30), (255, 220, 90), "center", kind="title",
                  outline=OUTLINE, ow=3)
        if int(self.t * 2) % 2 == 0 and self.state_t > 0.6:
            blit_text(surf, "Invio per continuare", 22, (W / 2, box.bottom - 26), (180, 255, 140), "center", bold=True)


class TitleScene(Scene):
    def __init__(self, game):
        super().__init__(game)
        self.t = 0.0
        self.sel = 0
        self.bg = vertical_gradient(W, H, [(0, (4, 6, 18)), (0.6, (16, 30, 50)), (1, (30, 70, 50))])
        rng = random.Random(7)
        for _ in range(300):
            b = rng.randint(100, 255)
            self.bg.set_at((rng.randint(0, W - 1), rng.randint(0, H - 1)), (b, b, b))
        for _ in range(5):
            draw_glow(self.bg, rng.randint(0, W), rng.randint(0, H), rng.randint(150, 260),
                      rng.choice(((40, 20, 70), (10, 40, 70), (20, 60, 30))))
        self.bg = self.bg.convert()
        game.audio.music("title")
        self.rick = [render_sprite("rick", "idle", f, -20, scale=2.3) for f in range(4)]
        self.morty = [pygame.transform.flip(render_sprite("morty", "idle", f, -10, scale=2.3), True, False) for f in range(4)]
        self.logo = self._logo()
        self.show_controls = False

    def _logo(self):
        a = text("RICK AND MORTY", 104, (156, 236, 255), kind="title", outline=(220, 240, 90), ow=9)
        b = text("RICK AND MORTY", 104, (156, 236, 255), kind="title", outline=(26, 60, 40), ow=5)
        s = pygame.Surface(a.get_size(), pygame.SRCALPHA)
        s.blit(a, (0, 0))
        s.blit(b, (4, 4))
        return s

    def items(self):
        save = self.game.save
        first = "Continua" if save.get("intro_seen") else "Nuova partita"
        return [first, "Comandi", "Audio: " + ("ON" if self.game.audio.enabled else "OFF"), "Esci"]

    def update(self, dt, inp):
        self.t += dt
        if self.show_controls:
            if inp.any_confirm() or inp.hit("back"):
                self.show_controls = False
                self.game.audio.play("select")
            return
        items = self.items()
        if inp.hit("menu_up"):
            self.sel = (self.sel - 1) % len(items)
            self.game.audio.play("select")
        elif inp.hit("menu_down"):
            self.sel = (self.sel + 1) % len(items)
            self.game.audio.play("select")
        elif inp.hit("confirm"):
            self.game.audio.play("confirm")
            if self.sel == 0:
                if self.game.save.get("intro_seen"):
                    self.game.change(lambda: GarageScene(self.game))
                else:
                    self.game.change(lambda: GarageScene(self.game, intro=True))
            elif self.sel == 1:
                self.show_controls = True
            elif self.sel == 2:
                self.game.toggle_audio()
            else:
                self.game.running = False
        elif inp.hit("back"):
            self.game.running = False

    def draw(self, surf):
        surf.blit(self.bg, (0, 0))
        k = 1.0 + 0.03 * math.sin(self.t * 1.5)
        draw_portal(surf, W / 2, 245, 150, 150, self.t * 0.6, k * 1.05)
        fr = int(self.t * 3) % 4
        r = self.rick[fr]
        surf.blit(r, (90, H - r.get_height() + 10))
        m = self.morty[fr]
        surf.blit(m, (W - m.get_width() - 90, H - m.get_height() + 10))
        y = 70 + math.sin(self.t * 2) * 6
        surf.blit(self.logo, (W / 2 - self.logo.get_width() / 2, y))
        blit_text(surf, "AVVENTURA INTERDIMENSIONALE", 34, (W / 2, y + 150), (255, 236, 120), "center", kind="title",
                  outline=OUTLINE, ow=3)
        if self.show_controls:
            self._draw_controls(surf)
        else:
            mb = pygame.Rect(W / 2 - 230, 412, 460, 246)
            panel(surf, mb, 170, border=(60, 140, 70), radius=20)
            draw_menu(surf, self.items(), self.sel, W / 2, 448, self.t, 34, 58)
        blit_text(surf, "Fan game non ufficiale - Rick and Morty (c) Adult Swim. Tutto generato via codice in Python + pygame.",
                  14, (W / 2, H - 14), (150, 160, 170), "center")

    def _draw_controls(self, surf):
        box = pygame.Rect(W / 2 - 400, 230, 800, 440)
        panel(surf, box, 235)
        blit_text(surf, "COMANDI", 40, (W / 2, box.y + 36), (180, 255, 140), "center", kind="title", outline=OUTLINE, ow=3)
        rows = [("A / D  o  Frecce", "Muoviti"),
                ("Spazio / W / Su", "Salta - premi di nuovo in aria per il doppio salto"),
                ("Giu + Salto", "Scendi da una piattaforma sottile"),
                ("J / Z  o  Click sinistro", "Spara (mira automatica - col mouse miri tu)"),
                ("K / X / Shift  o  Click destro", "Pistola portale: teletrasporto (+Su/Giu = diagonale)"),
                ("H / Q", "Bevi dalla fiaschetta (+40 vita)  *burp*"),
                ("E", "Parla con i personaggi"),
                ("Esc / P", "Pausa"),
                ("M  /  F11", "Audio on/off  /  Schermo intero")]
        y = box.y + 86
        for a, b in rows:
            blit_text(surf, a, 19, (box.x + 30, y), (255, 230, 120), "midleft", bold=True)
            blit_text(surf, b, 18, (box.x + 330, y), (230, 230, 230), "midleft")
            y += 36
        blit_text(surf, "Invio o Esc per tornare", 16, (W / 2, box.bottom - 22), (180, 255, 140), "center", bold=True)


class GarageScene(Scene):
    def __init__(self, game, sel=None, intro=False):
        super().__init__(game)
        self.t = 0.0
        save = game.save
        unlocked = clamp(save.get("unlocked", 1), 1, len(LEVELS))
        self.sel = clamp(sel if sel is not None else unlocked - 1, 0, len(LEVELS) - 1)
        self.bg = game.garage()
        game.audio.music("garage")
        self.dialog = Dialog(game, GAME_INTRO) if intro else None
        self.tip = random.choice(GARAGE_TIPS)
        self.confirm_reset = False

    def unlocked(self, i):
        return i < self.game.save.get("unlocked", 1)

    def update(self, dt, inp):
        self.t += dt
        if self.dialog:
            self.dialog.update(dt, inp)
            if self.dialog.done:
                self.dialog = None
                self.game.save["intro_seen"] = True
                write_save(self.game.save)
            return
        if inp.hit("menu_up"):
            self.sel = (self.sel - 1) % len(LEVELS)
            self.game.audio.play("select")
            self.confirm_reset = False
        elif inp.hit("menu_down"):
            self.sel = (self.sel + 1) % len(LEVELS)
            self.game.audio.play("select")
            self.confirm_reset = False
        elif inp.hit("confirm"):
            if self.unlocked(self.sel):
                self.game.audio.play("portal")
                idx = self.sel
                self.game.change(lambda: LevelScene(self.game, idx))
            else:
                self.game.audio.play("hit")
        elif inp.hit("back"):
            self.game.change(lambda: TitleScene(self.game))
        elif pygame.K_DELETE in inp.just:
            if self.confirm_reset:
                audio = self.game.save.get("audio", True)
                self.game.save.clear()
                self.game.save.update(dict(unlocked=1, seeds={}, best={}, intro_seen=True, audio=audio, completed=False))
                write_save(self.game.save)
                self.sel = 0
                self.confirm_reset = False
                self.game.audio.play("poof")
            else:
                self.confirm_reset = True

    def draw(self, surf):
        surf.blit(self.bg, (0, 0))
        fr = int(self.t * 3) % 4
        draw_portal(surf, 1170, 520, 62, 104, self.t, 1.0 if self.unlocked(self.sel) else 0.35)
        blit_sprite(surf, "rick", "idle", fr, -10, 1, 900, 652)
        blit_sprite(surf, "morty", "idle", fr, -10, 1, 1010, 652)
        save = self.game.save
        box = pygame.Rect(30, 24, 640, 600)
        panel(surf, box, 215, radius=18)
        blit_text(surf, "IL GARAGE DI RICK", 40, (box.x + 24, box.y + 16), (180, 255, 140), kind="title", outline=OUTLINE, ow=3)
        tot = sum(save["seeds"].values()) if save.get("seeds") else 0
        blit_text(surf, "Mega Semi: %d/%d" % (tot, 3 * (len(LEVELS) - 1)), 20, (box.right - 24, box.y + 34),
                  (255, 220, 90), "topright", bold=True)
        y = box.y + 84
        seed = pygame.transform.smoothscale(item_sprite("seed"), (18, 23))
        ghost = seed.copy()
        ghost.set_alpha(55)
        for i, ld in enumerate(LEVELS):
            r = pygame.Rect(box.x + 18, y, box.w - 36, 92)
            on = i == self.sel
            ok = self.unlocked(i)
            col = (40, 70, 40) if on else (24, 28, 36)
            pygame.draw.rect(surf, col, r, border_radius=12)
            pygame.draw.rect(surf, (140, 255, 110) if on else (60, 70, 80), r, 3 if on else 1, border_radius=12)
            tc = THEMES[ld["theme"]]["title_col"] if ok else (110, 110, 120)
            blit_text(surf, "%d. %s" % (i + 1, ld["name"]), 26, (r.x + 16, r.y + 10), tc, kind="title", outline=OUTLINE, ow=2)
            if ok:
                blit_text(surf, ld["sub"], 16, (r.x + 18, r.y + 50), (210, 210, 220))
                if not ld.get("boss"):
                    got = save["seeds"].get(ld["id"], 0)
                    for k in range(3):
                        surf.blit(seed if k < got else ghost, (r.right - 106 + k * 26, r.y + 12))
                best = save["best"].get(ld["id"], 0)
                if best:
                    blit_text(surf, "Record: %d" % best, 16, (r.right - 16, r.y + 62), (255, 230, 120), "topright", bold=True)
            else:
                blit_text(surf, "BLOCCATO - completa la dimensione precedente", 16, (r.x + 18, r.y + 52), (150, 150, 160))
            y += 102
        blit_text(surf, self.tip, 17, (W / 2 + 20, H - 62), (255, 250, 220), "center", bold=True, outline=OUTLINE, ow=2)
        hint = "Su/Giu: scegli dimensione   -   Invio: apri il portale   -   Esc: menu   -   Canc: azzera progressi"
        if self.confirm_reset:
            hint = "Premi di nuovo CANC per azzerare tutti i progressi"
        blit_text(surf, hint, 16, (W / 2, H - 26), (190, 255, 160), "center", bold=True, outline=OUTLINE, ow=2)
        if self.dialog:
            self.dialog.draw(surf)


class VictoryScene(Scene):
    def __init__(self, game):
        super().__init__(game)
        self.t = 0.0
        game.audio.music("victory")
        self.bg = Background("arena")
        self.particles = Particles()
        save = game.save
        self.total_seeds = sum(save["seeds"].values())
        self.total_score = sum(save["best"].values())

    def update(self, dt, inp):
        self.t += dt
        if random.random() < 0.15:
            x = random.uniform(100, W - 100)
            self.particles.burst(x, random.uniform(80, 300), 30,
                                 random.choice(((255, 120, 220), (120, 230, 255), (255, 230, 120), PORTAL_GREEN)),
                                 300, 1.2, 3, 200, "dot", True)
        self.particles.update(dt)
        if self.t > 2 and (inp.any_confirm() or inp.hit("back")):
            self.game.change(lambda: TitleScene(self.game))

    def draw(self, surf):
        self.bg.draw(surf, self.t * 60, self.t)
        draw_portal(surf, W / 2, 380, 110, 160, self.t, 1.0)
        fr = int(self.t * 10) % 8
        jump = abs(math.sin(self.t * 4)) * 30
        blit_sprite(surf, "rick", "run" if int(self.t * 2) % 2 else "jump", fr, -60, 1, 380, 620 - jump)
        blit_sprite(surf, "morty", "run" if int(self.t * 2) % 2 == 0 else "jump", fr, -60, -1, 900, 620 - jump)
        blit_sprite(surf, "meeseeks", "run", fr, 0, 1, 230, 640)
        blit_sprite(surf, "poopy", "idle", int(self.t * 3) % 4, 0, -1, 1060, 640)
        self.particles.draw(surf, 0, 0)
        y = 70 + math.sin(self.t * 3) * 8
        blit_text(surf, "WUBBA LUBBA DUB DUB!", 76, (W / 2, y), (255, 236, 120), "center", kind="title",
                  outline=(120, 20, 60), ow=5)
        blit_text(surf, "Hai salvato la Terra dai Cromulon!", 30, (W / 2, y + 80), WHITE, "center", kind="title",
                  outline=OUTLINE, ow=3)
        blit_text(surf, "Mega Semi raccolti: %d/12      Punteggio totale: %d" % (self.total_seeds, self.total_score),
                  22, (W / 2, y + 126), (180, 255, 140), "center", bold=True, outline=OUTLINE, ow=2)
        if self.t > 2 and int(self.t * 2) % 2 == 0:
            blit_text(surf, "GRAZIE PER AVER GIOCATO!  -  Invio per tornare al menu", 22, (W / 2, H - 30),
                      (255, 255, 255), "center", bold=True, outline=OUTLINE, ow=2)


# =============================================================================
#  GIOCO
# =============================================================================
class Game:
    def __init__(self):
        try:
            pygame.mixer.pre_init(BASE_RATE, -16, 2, 1024)
        except Exception:
            pass
        pygame.init()
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(BASE_RATE, -16, 2, 1024)
        except Exception:
            pass
        pygame.display.set_caption(GAME_TITLE)
        icon = pygame.Surface((32, 32), pygame.SRCALPHA)
        pygame.draw.ellipse(icon, (40, 140, 30), (2, 0, 28, 32))
        pygame.draw.ellipse(icon, (140, 250, 90), (6, 4, 20, 24))
        pygame.draw.ellipse(icon, (230, 255, 190), (11, 10, 10, 12))
        pygame.display.set_icon(icon)
        try:
            self.screen = pygame.display.set_mode((W, H), pygame.SCALED | pygame.RESIZABLE)
        except pygame.error:
            self.screen = pygame.display.set_mode((W, H))
        self.clock = pygame.time.Clock()
        self.inp = Input()
        self.null_inp = Input()
        self.save = load_save()
        self.audio = Audio(self.save.get("audio", True))
        self._vign = {}
        self._tiles = {}
        self._garage = None
        self.fade = 0.0
        self.fade_dir = 0
        self.next_scene = None
        self.running = True
        self.scene = TitleScene(self)

    def vignette(self, strength):
        if strength not in self._vign:
            self._vign[strength] = make_vignette(strength).convert_alpha()
        return self._vign[strength]

    def tileset(self, theme):
        if theme not in self._tiles:
            self._tiles[theme] = TileSet(theme)
        return self._tiles[theme]

    def garage(self):
        if self._garage is None:
            self._garage = build_garage()
        return self._garage

    def toggle_audio(self):
        on = self.audio.toggle()
        self.save["audio"] = on
        write_save(self.save)

    def change(self, factory):
        if self.fade_dir == 0:
            self.next_scene = factory
            self.fade_dir = 1

    def step(self, dt):
        """Un frame di gioco (separato da run() per poterlo testare)."""
        self.audio.update()
        if self.fade_dir == 0:
            self.scene.update(dt, self.inp)
        elif self.fade_dir == 1:
            self.fade = min(1.0, self.fade + dt * 4)
            if self.fade >= 1.0:
                self.scene = self.next_scene()
                self.next_scene = None
                self.fade_dir = -1
        else:
            self.scene.update(dt, self.null_inp)
            self.fade = max(0.0, self.fade - dt * 4)
            if self.fade <= 0:
                self.fade_dir = 0
        self.scene.draw(self.screen)
        if self.fade > 0:
            s = pygame.Surface((W, H))
            s.fill(BLACK)
            s.set_alpha(int(255 * self.fade))
            self.screen.blit(s, (0, 0))

    def run(self):
        while self.running:
            dt = min(self.clock.tick(FPS) / 1000.0, 1 / 30)
            self.inp.begin()
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    self.running = False
                elif e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_F11:
                        try:
                            pygame.display.toggle_fullscreen()
                        except pygame.error:
                            pass
                    elif e.key == pygame.K_m:
                        self.toggle_audio()
                self.inp.feed(e)
            self.inp.end()
            self.step(dt)
            pygame.display.flip()
        write_save(self.save)
        pygame.quit()


def main():
    try:
        Game().run()
    except Exception:
        import traceback
        msg = traceback.format_exc()
        try:
            with open(os.path.join(os.path.expanduser("~"), "rick_morty_errore.txt"), "w", encoding="utf-8") as f:
                f.write(msg)
        except Exception:
            pass
        print(msg)
        raise


if __name__ == "__main__":
    main()
