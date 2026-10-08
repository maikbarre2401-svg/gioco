#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ORION // SPY OSINT CINEMA PRO  —  by MAIKGOST
Simulatore d'intelligence dall'estetica cinematografica (gioco / demo UI).

⚠️  SIMULAZIONE / GIOCO
    Questo programma NON esegue nessuna ricerca reale e non raccoglie dati su
    nessuna persona. TUTTI i dati (nomi, foto, email, profili, ecc.) sono
    generati in modo casuale e deterministico dal testo digitato, a puro scopo
    di intrattenimento. I ritratti sono silhouette astratte generate dal codice
    oppure volti generati da IA (thispersondoesnotexist): NON persone reali.

    Uniche connessioni di rete (entrambe disattivabili):
      • download dei volti IA (opzione "Foto realistiche");
      • mappa 3D Mapbox, aperta nel browser solo su richiesta.

Interfaccia HUD futuristica: pulsanti neon, pannelli olografici, schede
animate, mappa del mondo a punti, grafo relazioni, timeline, galleria con
scansione facciale, notifiche animate ed effetti sonori sintetizzati.

Comandi rapidi:  Invio avvia · Esc ferma · Ctrl+G galleria · Ctrl+P slideshow
                 Ctrl+E esporta · Ctrl+R casuale · F5 rigenera · F11 schermo intero
                 Ctrl+, impostazioni

Creato da MAIKGOST.
Requisiti: Python 3.8+, tkinter (di serie), Pillow (`pip install Pillow`).
Opzionale: opencv-python (video d'avvio).
"""

import base64
import hashlib
import html
import json
import math
import os
import queue
import random
import shutil
import sqlite3
import struct
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
import urllib.request
import wave
import webbrowser
import zlib
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from tkinter import filedialog, ttk

try:
    from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageTk
    PIL_OK = True
except Exception:  # pragma: no cover
    PIL_OK = False

try:                                    # opzionale: solo per lo splash video
    import cv2
    CV2_OK = True
except Exception:
    CV2_OK = False

VIDEO_EXTS = (".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v")


# ===========================================================================
#  IDENTITÀ CREATORE  (firma presente in tutta l'app)
# ===========================================================================
CREATOR = "MAIKGOST"
CREATOR_TAG = f"created by {CREATOR}"
APP_NAME = "ORION // SPY OSINT CINEMA PRO"
APP_VERSION = "6.0"


# ===========================================================================
#  TEMA
# ===========================================================================
THEME = {
    "bg": "#03050c", "bg2": "#060a15", "panel": "#08101f", "panel2": "#0d1730",
    "card": "#0a1326", "line": "#16264a", "line2": "#23407a",
    "accent": "#00e5ff", "accent2": "#7c5cff", "magenta": "#ff2bd6",
    "green": "#00ff9c", "amber": "#ffb020", "red": "#ff3b5c",
    "text": "#d8e6ff", "dim": "#6b7ca8", "white": "#ffffff", "black": "#000000",
}
SEV_COLORS = {"info": "green", "warn": "amber", "bad": "red"}
DATA_GLYPHS = "アカサタナハマヤラ0123456789ABCDEF<>/*ΞΨΛØ§#$%&"


def threat_color(level):
    return THEME[{"LOW": "green", "MEDIUM": "amber", "HIGH": "red"}.get(level, "dim")]


# Font: vengono scelti all'avvio fra quelli installati (vedi resolve_fonts).
MONO = "Consolas"
UI = "Segoe UI"
DISPLAY = "Segoe UI"
_FONT_PREFS = {
    "MONO": ["Share Tech Mono", "Cascadia Mono", "Consolas", "JetBrains Mono", "Menlo",
             "DejaVu Sans Mono", "Courier New"],
    "UI": ["Rajdhani SemiBold", "Bahnschrift", "Segoe UI Semibold", "Segoe UI",
           "Helvetica Neue", "DejaVu Sans", "Arial"],
    "DISPLAY": ["Orbitron", "Bahnschrift SemiBold", "Bahnschrift", "Segoe UI Semibold",
                "Helvetica Neue", "DejaVu Sans", "Arial"],
}


def resolve_fonts(root):
    """Sceglie i font più 'tech' disponibili sul sistema (Orbitron, Bahnschrift…)."""
    try:
        fams = {f.lower(): f for f in tkfont.families(root)}
    except tk.TclError:
        return
    for name, prefs in _FONT_PREFS.items():
        for p in prefs:
            if p.lower() in fams:
                globals()[name] = fams[p.lower()]
                break


# --- file dell'app: sempre accanto allo script (non nella cartella corrente) ---
try:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:                       # es. eseguito da un REPL / freezer
    APP_DIR = os.getcwd()
SETTINGS_FILE = os.path.join(APP_DIR, "orion_settings.json")
CACHE_DB = os.path.join(APP_DIR, "orion_cache.db")
DOSSIER_SCHEMA = 2      # incrementare quando cambia la struttura del dossier

# --- impostazioni (persistite in orion_settings.json) ---
DEFAULT_SETTINGS = {
    "skip_intro": False, "intro_speed": "media", "slideshow_sec": 4.0,
    "bg_anim": True, "redacted": True, "sound": True, "accent": THEME["accent"],
    "splash": True, "mapbox_token": "", "splash_video": "", "real_faces": True,
    "typewriter": True, "fx": True,
}
INTRO_SCALE = {"corta": 0.6, "media": 1.0, "lunga": 1.55}
ACCENTS = [("Ciano", "#00e5ff"), ("Neon", "#00ff9c"), ("Magenta", "#ff2bd6"),
           ("Viola", "#a26bff"), ("Ambra", "#ffb020"), ("Rosso", "#ff3b5c")]


def _is_hex_color(v):
    return (isinstance(v, str) and len(v) == 7 and v[0] == "#"
            and all(c in "0123456789abcdefABCDEF" for c in v[1:]))


def sanitize_settings(raw):
    """Unisce `raw` ai default scartando chiavi sconosciute e valori del tipo
    sbagliato (un JSON modificato a mano non deve far crashare l'app)."""
    s = dict(DEFAULT_SETTINGS)
    if not isinstance(raw, dict):
        return s
    for k, default in DEFAULT_SETTINGS.items():
        v = raw.get(k)
        if v is None:
            continue
        if isinstance(default, bool):
            if isinstance(v, bool):
                s[k] = v
        elif isinstance(default, float):
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                s[k] = float(v)
        elif isinstance(v, str):
            s[k] = v
    s["slideshow_sec"] = max(1.5, min(8.0, s["slideshow_sec"]))
    if s["intro_speed"] not in INTRO_SCALE:
        s["intro_speed"] = DEFAULT_SETTINGS["intro_speed"]
    if not _is_hex_color(s["accent"]):
        s["accent"] = DEFAULT_SETTINGS["accent"]
    return s


# Volti realistici: generati da IA (thispersondoesnotexist) → NON persone reali.
FACES_DIR = os.path.join(APP_DIR, "orion_faces")
FACE_URL = "https://thispersondoesnotexist.com/"


def fetch_ai_face(cache_path, timeout=7):
    """Scarica un volto generato da IA (persona NON reale). None se non riesce."""
    try:
        if os.path.exists(cache_path) and os.path.getsize(cache_path) > 2000:
            return cache_path
        if not PIL_OK:
            return None
        req = urllib.request.Request(FACE_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read()
        if not data or len(data) < 2000:
            return None
        Image.open(BytesIO(data)).verify()          # deve essere un'immagine valida
        with open(cache_path, "wb") as f:
            f.write(data)
        return cache_path
    except Exception:
        return None


# ===========================================================================
#  UTILITÀ  —  colori, geometria, misure testo, cicli di animazione
# ===========================================================================
def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb):
    r, g, b = (max(0, min(255, int(c))) for c in rgb)
    return f"#{r:02x}{g:02x}{b:02x}"


def lerp(a, b, t):
    return a + (b - a) * t


def lerp_color(c1, c2, t):
    a, b = hex_to_rgb(c1), hex_to_rgb(c2)
    return rgb_to_hex(tuple(lerp(a[i], b[i], t) for i in range(3)))


mix = lerp_color


def ease_out(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def chamfer(x0, y0, x1, y1, c, corners="tl br"):
    """Punti di un rettangolo con gli angoli tagliati (stile HUD)."""
    c = max(0, min(c, (x1 - x0) / 2, (y1 - y0) / 2))
    pts = []
    pts += [x0, y0 + c, x0 + c, y0] if "tl" in corners else [x0, y0]
    pts += [x1 - c, y0, x1, y0 + c] if "tr" in corners else [x1, y0]
    pts += [x1, y1 - c, x1 - c, y1] if "br" in corners else [x1, y1]
    pts += [x0 + c, y1, x0, y1 - c] if "bl" in corners else [x0, y1]
    return pts


def hexagon(cx, cy, r, rot=0.0):
    return [v for k in range(6)
            for v in (cx + r * math.cos(rot + k * math.pi / 3),
                      cy + r * math.sin(rot + k * math.pi / 3))]


def brackets(cv, x0, y0, x1, y1, L, color, width=2, tags=()):
    """Quattro staffe d'angolo (mirino) su un Canvas."""
    for (ax, ay, dx, dy) in [(x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)]:
        cv.create_line(ax, ay + dy * L, ax, ay, ax + dx * L, ay, fill=color, width=width,
                       tags=tags)


_MEASURE = {}


def text_w(text, font):
    key = (text, font)
    w = _MEASURE.get(key)
    if w is None:
        try:
            w = tkfont.Font(font=font).measure(text)
        except tk.TclError:
            w = len(text) * 8
        _MEASURE[key] = w
    return w


def bg_of(widget):
    try:
        return widget.cget("bg")
    except tk.TclError:
        return THEME["bg"]


def visible(widget):
    try:
        return bool(widget.winfo_viewable())
    except tk.TclError:
        return False


class Anim:
    """Ciclo di animazione legato a un widget: si ferma da solo quando il widget
    viene distrutto. `step()` può restituire False (stop) o un ritardo in ms."""

    def __init__(self, widget, ms, step):
        self.w, self.ms, self.step = widget, ms, step
        self.alive = True
        self.id = None
        widget.bind("<Destroy>", self._destroyed, add="+")
        self.id = widget.after(ms, self._run)

    def _run(self):
        self.id = None
        if not self.alive:
            return
        try:
            r = self.step()
        except tk.TclError:
            self.alive = False
            return
        if r is False:
            self.alive = False
            return
        delay = r if (isinstance(r, int) and not isinstance(r, bool) and r > 0) else self.ms
        try:
            self.id = self.w.after(delay, self._run)
        except tk.TclError:
            self.alive = False

    def _destroyed(self, e):
        if str(e.widget) == str(self.w):
            self.stop()

    def stop(self):
        self.alive = False
        if self.id:
            try:
                self.w.after_cancel(self.id)
            except tk.TclError:
                pass
            self.id = None


# ===========================================================================
#  EFFETTI SONORI  —  sintetizzati al volo (nessun file da scaricare)
# ===========================================================================
_SFX = None


def sfx(name):
    if _SFX is not None:
        _SFX.play(name)


class SoundFX:
    RATE = 22050
    # (freq iniziale, freq finale, durata s, ampiezza, forma d'onda)
    SOUNDS = {
        "click": [(1900, 2600, 0.035, 0.18, "sin")],
        "open": [(520, 1250, 0.11, 0.15, "sin")],
        "scan": [(240, 1400, 0.30, 0.10, "saw"), (1400, 1800, 0.06, 0.09, "sin")],
        "done": [(880, 880, 0.08, 0.18, "sin"), (1320, 1320, 0.07, 0.18, "sin"),
                 (1760, 1760, 0.18, 0.16, "sin")],
        "alert": [(240, 200, 0.12, 0.16, "sqr"), (0, 0, 0.04, 0.0, "sin"),
                  (240, 200, 0.12, 0.16, "sqr")],
        "boot": [(55, 330, 0.65, 0.28, "sin"), (1300, 2600, 0.10, 0.09, "sin")],
        "toast": [(1450, 1450, 0.03, 0.12, "sin"), (1950, 1950, 0.05, 0.12, "sin")],
    }

    def __init__(self, root, enabled):
        self.root = root
        self.enabled = enabled
        self.files = {}
        self.player = None
        self._last = {}
        try:
            self._detect()
            self._prepare()
        except Exception:
            self.files = {}

    def _detect(self):
        if sys.platform.startswith("win"):
            import winsound
            self._winsound = winsound
            self.player = "win"
        elif sys.platform == "darwin" and shutil.which("afplay"):
            self.player = "afplay"
        else:
            for p in ("paplay", "aplay"):
                if shutil.which(p):
                    self.player = p
                    break

    def _prepare(self):
        if not self.player:
            return
        d = os.path.join(tempfile.gettempdir(), "orion_sfx_v1")
        os.makedirs(d, exist_ok=True)
        for name, segs in self.SOUNDS.items():
            path = os.path.join(d, name + ".wav")
            if not os.path.exists(path):
                tmp = path + f".{os.getpid()}.tmp"
                self._write(tmp, self._synth(segs))
                os.replace(tmp, path)
            self.files[name] = path

    def _synth(self, segs):
        out, ph, R = [], 0.0, self.RATE
        for f0, f1, dur, amp, kind in segs:
            n = max(1, int(dur * R))
            for i in range(n):
                t = i / n
                ph += 2 * math.pi * (f0 + (f1 - f0) * t) / R
                if kind == "saw":
                    v = 2 * ((ph / (2 * math.pi)) % 1.0) - 1
                elif kind == "sqr":
                    v = 1.0 if math.sin(ph) >= 0 else -1.0
                else:
                    v = math.sin(ph)
                env = min(1.0, i / (0.004 * R)) * (1 - t) ** 1.6
                out.append(int(max(-1.0, min(1.0, v * amp * env)) * 32767))
        return out

    def _write(self, path, samples):
        with wave.open(path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(self.RATE)
            w.writeframes(struct.pack("<%dh" % len(samples), *samples))

    def play(self, name, force=False):
        if not force and not self.enabled():
            return
        now = time.time()
        if now - self._last.get(name, 0) < 0.06:        # anti-raffica
            return
        self._last[name] = now
        path = self.files.get(name)
        try:
            if path and self.player == "win":
                ws = self._winsound
                ws.PlaySound(path, ws.SND_FILENAME | ws.SND_ASYNC | ws.SND_NODEFAULT)
            elif path and self.player:
                cmd = ["aplay", "-q", path] if self.player == "aplay" else [self.player, path]
                subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif name in ("done", "alert"):
                self.root.bell()
        except Exception:
            pass


# ===========================================================================
#  MAPPA DEL MONDO  —  maschera terre emerse 0.5° (Natural Earth, pubblico dominio)
# ===========================================================================
LAND_RES = 2                            # celle per grado
_LAND_B64 = (
    "eNrtnU9v3cp1wIfijUYPETQO3kZtFY0eEiDLtDsXUDQq3gfItksHWWSThYoggB7qmDT8WidIEGeXTRHnU2QZ0xBQZVHU6S6L"
    "h4iKAygFipqCC3j8TM9kZkjeyyHP/CEloQigWdjy1b0/Hp45c+acM+fSCN2O23E7bse1DyZlcY04LKXk5qdM/SSvEUxli2b6"
    "BymuC2y4Ur6VFW3I5XWRG7Bkshuvr0lq1shcyv7w3GE0OJHAWP7203ZeV+/PqlhyKuUzxbrsgztlfNT+iKve2+uJMhe4R25B"
    "ZPVj3+DzOIPLG0vjBtONcmnma8BS2o/RBMfigMhsIHInVQqIrKYwi7DKtMSSPaoVywIv75fVDyD1hcn/QNS6+xeeaGVkEBnz"
    "bOxE1lAenrtEy12ppfJDm9zhaLkBWTQP+yG0hdAb+UTLTOXYNlDSv29SLHUUWqLsUtA9xuWFNloCaQOyNoaXxoNdCl+k8hVn"
    "/CvyUd25ZjeZtipqJODtay60ehdPL991q9lHTloNpX11ZfKFa0Fq23j9tkNhjz9K5GqPWK5+LB9WsMPgxIiaVBt9eSS0X2GO"
    "esoIuQ596f2kzs75h5Xt9QA1l6vNzLBTTT92OrkqkeS9fPzynexvAZDfZ+o27vTIIlU3lkiXOb+Qm7WyYyKFtCQClKffwP7d"
    "Wk/qWrnLMp5JUWNxRLsp7D732/H96dtgp5RZDrHnsQqbrEgiEcd6Vi772ihh08ie2G7r4QedYSNk/k47vlKDUuk/CdKZ8NcA"
    "bRzmDblQ2ntmkS+bKdlbrcZMtm7mUKtBfYh0s9b6jvd9j9NehlaK/ATaMo0F4s4iuRLkg+fGgMWX5KNu3bGxzGxlKKmacXg3"
    "3kCrNSyUfC/v6wVVH2TqYmdmqtlocaerf8lUvwsY5CHpm1bRREVKPvn0j6ROzLStZ8MVRlcrMjt1kKU8lXWObD98Kt9Xf0Vf"
    "kTptbjobmkajHLXNbi9YzS6kc/C+Q9P/ViuJZZLw9FQrNx0qo1nvIuFIhsYwJOLmT1rjEy00Hi7t1vvldfP3Sw+5RODV6/RE"
    "X5WsnHrfs8nzqvn7hYd8lidPgZe1sSok7kwusePfsl32mU8dJQNefF1o6apGRGUJ1cftJBpUBa8QezwzhjYa/6OlI2Uzg2Yq"
    "ys40OJP1BguT/0sg6F0vciXtaWFmNzdK4J1pqHusPwqDZS5se+60r3WkVnzSWoZcbadKxXUWQVaRy9rXxy/Tz8mFXnkdmXTx"
    "hDILKQcuzrVQKvTheFYzpuSsjbBmZTO+NA0io4b6gEgBe9lYU+I+MLbQ+Iy9zjRqGkdWH9uAyOh4gbLPRkGPolYsjizQIH7r"
    "rvf8TKRVT8FLf1tFyCxkkxpQSEdqYeZ3zJT1NyplE2UE+X23r0BkJSxvfllOJj8/bz04BpzGkpxYcReL0jN63Prdf1aKycjA"
    "/6nr8TVrX2/JNeEsNHdU7Ji339VOGT0akzFU6uCLO1nIktlvNjpbqkpraymNNmqSAzUEngZ0cSLQcqvYNDNJ7IBBXYjaoS0u"
    "EH0pKz9ZucciXW3I36ysWNmQ8SjmUslt+khNqN/DtdF9twW9QJbQor1QNUoHviDzRWBbVba52jjZvk3WwqaDDVD9Xl3oBzKn"
    "AW9hkR/8LRqpIx2lCCqQQ8qIWMDDqSWwCs+qUcEElFndSR0glzaZVFb1aLl1D7IT/bY33E8uzL0v56dGI3Lr0iyDfqVu4XsB"
    "MrLIy/Xb/0w1ysWSd+pfR/l7GZaZL2sIrb32d7cqG5LTKlPT/sa/AE83tZ6Haxc/HpGlpWaGvhj0c5+CZKsixYbpNn4t8yxm"
    "+xuTkz6Zj8kvW+WHtr9knCkX/WuPyeeRZMSd5VDzjmyYyG9hE8QExu9hcga6rlW4fxEm/6fO/SLqoY/tfP8sTH4RWWkl1urO"
    "2XWRT0rSz+QXGxGh0Qu4WECsGFPsc1qjcY7iHU8cZCtjUR4zq+26Snj84hCuyZwN1hMToYL3cPzEUbwckrPJ5M2YMvwrFU9+"
    "FzixWEaF0BLciivw/yv6DJ7BM1e0W1P/aUc33ozPhUxBoVbXKEAy/yCOPHCHHbl6QCWckslyO45cj2V+2u5kNUwu4sgXxZj8"
    "cy3YgUo8YUvJd6NmkALnbydasDtY1vC6yeleBLnesX9bKzKpjNNOpYDJiJUR5HIscf01vfPqpFkk8C4oK1fF1U1O9Qe/w6nZ"
    "0FkNRTT1UeI4DkokdGjQJ39PmzLaVYaBvg6JnFzEzCAfaUOge7pImEtFzjFUyEn+gKbrOdXX2stOTMY3PHxa3mUZQ85H5AJV"
    "5HV71FmmoMwxZD6e3hxV+J38saP89ETdZVJFrMFqvE4QqpIftUdl4yyZaaOJIZcgGZVNcXrs68Q2m0kmWhuHSZk1MufD/bba"
    "y3Knni3rLyCZUZazJzCZo6yws3QXOR/NoN4UZc6aDL0YkutDRcaF/2zeQa7R1l/vot3GgqpR9MFxib45i/xMRetqB91pyHxE"
    "rlVa5+yaIL4Twd2mELaFtj+Bsx/sIWMfeRM3yYIuLoC+GZfYSU59fQS0TUM4uoSjfVxmzjP1GLIKvN/CZPLQfZiXuN1GY5Lc"
    "E4flW9jT9kKdbqNZoLUnKs2VAeTe9hjHIWa6OkxIHZkx+28UQXb8qkL3oQpfQ6alt3XDdYjZneRKF7lEBEWQaxc5kXwBpxUV"
    "2vI1Flw4yS1OJbpPX9wI+a0z3A90y7wMkeVccrNw60WQfAbWvTzj780s76MDr4fVifNUmb/curkD734zh7zb2vKBP5qU8tFU"
    "cpY1s3fgc91vmwAMqHv5utRoWyTe8JAve+d4/raUvgU8acj0wGMalSk0ZdPI6eOGTL7qMQ2uoJ8vnrl6zhyL8LQlLzymocnv"
    "kqnk88bk8baHbApj6cPBbrUXIJftYtr2VK+EIgtdnLeTlIDQKnmKIjfJW39aQ+Rt1pA3fOktaZyWRS5DnYE7zZHrgTfRwK07"
    "7N9IHupX2zbkRP7MR37UGkN/WsHkZ9DSosln3Oc2TvrkpjrzJwTVpv5xRP54WJAFyKJdPry9DETetR1ErY8haO50G22jgugC"
    "Mv3zjmNJ55bMtQ4cBrGDTX7e7iFbmYkTFN5VMSmG5KLfEDqewY6sjcO0JfId18KzpBOIqRjtgnsS56z19Jn+S590HjhkLu25"
    "Mj1daR1HLs1Z9X0HObdX20vlaze+LI/cZLYi56Yf4xihe8HOzsaLUyqO3aUP2u5OrG1M4XvOBriBj1dvR4WbzLuWM9Y209Rw"
    "eR/YpUNFFdJGq8Z9teSIjmKIbK9BXQb7P9R1jGDnYcdYHeJOoOCG2w2V6nkkZ6YeFkHGZCy0LbNYkdU8rlNDjuncTsdhySBE"
    "wm1SQNouGt3CGENOxmQyjOqqIRlFdZuD1Q3b2RXty3lzWfXP+zHkLKSN1yK3yco/ZDFkDFQ3wNJ080ZsyG9QlDoCMq862tGS"
    "fK+MUoci/8ZDFmi9fdnM42NN3juKISsHnf7OU/QW7Q7XkHGqybtRZLULsl94CvUiEat+VE1WK2UryuxIruzjUrjTFCpW3blo"
    "S4ue0ig9k0I79f91kzvjMOR13WWyTu5FkctCZlaGR2Gybt5U5LsIbZK9GHLy7nJQMCAw+UFhOmXV5O2s340z6GEYj+GM9RPT"
    "raMbzu6sHceRh70QDvLflc18K3MmPIpM6CDFS+G88ktVR0aR5JQM0tIEJhuvnBjybuRXa/Aw4YUdR0PWf9z74E8TyPzQadDd"
    "sjAX5+aHOG1Y34boXuifGhT98Kopau5NkLlv0SaSBPP3tKzbXvkJ5J7dYX7cJ+f9PpcH0ZaxIhdWWLkL5sIJ1+R6PtnKN617"
    "Fw8QivN0/fKco2JgkZmKy7NoMvWTrXunz/qNU8H9CjyvoWDRiEr0oTLQZBKZO8jWveA3uQ4dPyquQGZgaQe/zVUgffTtKHIC"
    "l8oYWIBJ9Rqq5ckkcgmTxSDMUeZ4Lh9OIguYbC+LRMt8nifhr7f1HL0owZUyUL/uX3j9a/S4mkAeMDJY/bpv8uTz5Rel4sgC"
    "1EY1DAOJPFEGze9OIMtDiDx0J5UiN62Z0TM4MF0CVyqZIp9ydP5W2RKOJxdA1DEgU74mH3HK9TFfmsdqQ5bAy0PHWCH8kG8u"
    "Mi1HGeWeh7PlIOMKLR7+G0LfVnIk8eR6rKThnqe7ZJNfmV9XSRGtjb6iE/hMRAcc6U8R2lAu7+liFhk5TlvUdpV8qiNdWYv1"
    "aG1YU+gg0+Yb1Ios76fxMpej5S3G3tzc2IY+yE+LmAA6lkyW2bIIln2ySWTUei5Tv1hEk4uR44DOJb/xHypFpELF0ulhzD44"
    "JLtkRgtW62LBA6wyw2hyPr4V4APfMlH0flqi5JcxkcyQzJxk/LxogjyU/DaWDNwK5M9OzIu6cH03Jq4bKpUGTpIWaHN8ruEi"
    "19Fk5eY2o6Pc4R7rl/n7rs69CPJSz0egSygiyCl8Vsk6Ez8CpSnobHLmIxMVd0zZvEuIDFVB1+lVyMsFD5Apk4geXpUMyawL"
    "6E0itB7n7CByjuEG+CgyhcjJsi8Ubtov2ZKchw0aJANdBOabQw05Rb5QKYHc8zLeAJI001DKmm/2I294l7nJNfRcDGK+utBd"
    "cWceuUQO8soX7EdMYT4mF9dPRt1LAJnG9Ie4yVm7FwBk17Y+lVy4XFgeTx4LVkNk0pvwMoosIDLQjdw3pXszyLR5KXUfMWh5"
    "j65Cdu7IZcDkVmQOAACyVa3ZujFylG0I6KaBJ3hMJ9dTySKWXAFkgRLhjl3zSHIOlXgREu4IM0xmYLbaGtaxOw4srkAu0Lgi"
    "zKaShYPsyRHKeeT02sgylkyuKnPimv0rk1GYHC6tZZPIeCqZQ6/64+0yjgw86gz2OVcnUwcZTyDDb6OOkCKdSoa2aO6P5Is4"
    "beQAuXSRqylkyG4LB1k4hAHJAvLauYNcIhJHhrce4tiOEo3EET2YqN9lb5O5KzNtvugp4shjCnEs3lRsqD+eduS9QEL4dmwG"
    "iUuNmpgsV+i9ADn6ZA61O2PWfeZuIKWfQrbX0XaAPPlhl0lH3gmUTuaQ23aiQCGpnk3G101GywcG1n4yn0zuvqnsOw7Ccs6T"
    "YfF+FLlC00f3VJbKq4055M4lljdF/ri4dvK3Gr/yuvAF5nU5g5w1ZJ//pzOsGZm+Lr1iPvcnE/l8sk+RfzPvQcescWellzxL"
    "G035EhdeXzeL3JS2vZ0RM2dwtXXdCDkR/pCfzyantZ9czCbj2h985fPJlX93mC+zv0R1FT2HQtG/PHKMno9mksO2cX+mNsLk"
    "43lkcUNq1g9ouEHyL2/G6kRcR80MmSVaO7wZ8o3NIDm7KTK+ghcNhe/VTQktb8ygs89uipyg23E7bsftuB1XGndvjHxjuwou"
    "/+JETiaLvHYtyuh/mRrnyHyzM41N+ytvONJeV5eNqX6u71p88JPl3hCqJev20N4jr6I0KPxpjDSNQWTak0Oawb2VhPbLmpn/"
    "OX2TMye8fHLy1Mdw6HHHOR/7naQV9MSWcNz9ifPyWbk8ZKSOhxMHUs1yHOrtHVgHo9T5pF/feD8OoAlfPkm3fSyg80m/fpnt"
    "29obT1fJPI+uducpA/JOJkYPTXnufcL02FT/0OaDGbfz8PFIfI/NBYQVbdaWAf32kQMmy+dN1/WhdU90EnloeMd39vRtq9mv"
    "U/3YfjFX5JFVEVZs9BU6n1wOSiXnr6Q47Nlobfu2uWpugSI9Ab8jOFsZu8y/StkkchGYej7ymrEDBcgzldz/5DaoxnKmkvsT"
    "SAO6YlNlzr1k3nk4RORc8n3qNnYdQkwGLxeCRG6RyZXItMicxk5D/z2B1zYWkFvQ87veVnSnKrrw27N+PnDedGukVyED+ih0"
    "E72eSDrb6Fwy8UT/H2TpdDWXwaWgVSzodHIV9pH59EUy8DguV3YxD9xTB5bXPIx1bKA5niEsdPZYTN/zo+KCTt9M3tAoibwd"
    "t+N2/H+MPwOFg3U3"
)
_LAND = None


def land_at(lat, lon):
    """True se (lat, lon) cade su terraferma (maschera a bassa risoluzione)."""
    global _LAND
    if _LAND is None:
        try:
            _LAND = zlib.decompress(base64.b64decode(_LAND_B64))
        except Exception:
            _LAND = b""
    if not _LAND:
        return False
    cols = 360 * LAND_RES
    col = int((lon + 180.0) * LAND_RES) % cols
    row = int((90.0 - lat) * LAND_RES)
    if row < 0 or row >= 180 * LAND_RES:
        return False
    return bool(_LAND[row * (cols // 8) + col // 8] >> (7 - col % 8) & 1)


# ===========================================================================
#  GRAFICA PILLOW  —  logo, sfondi, radar, ritratti, mappa, glitch
# ===========================================================================
_FONT_CACHE = {}
_DEJAVU = "/usr/share/fonts/truetype/dejavu/"
_FONT_FILES = {
    "mono": ["consola.ttf", "CascadiaMono.ttf", "DejaVuSansMono.ttf", _DEJAVU + "DejaVuSansMono.ttf",
             "/System/Library/Fonts/Menlo.ttc", "cour.ttf", "arial.ttf"],
    "mono_bold": ["consolab.ttf", "DejaVuSansMono-Bold.ttf", _DEJAVU + "DejaVuSansMono-Bold.ttf",
                  "/System/Library/Fonts/Menlo.ttc", "courbd.ttf", "arialbd.ttf"],
    "display": ["Orbitron-Bold.ttf", "Orbitron-Black.ttf", "bahnschrift.ttf", "segoeuib.ttf",
                "DejaVuSans-Bold.ttf", _DEJAVU + "DejaVuSans-Bold.ttf",
                "/System/Library/Fonts/Supplemental/Arial Bold.ttf", "arialbd.ttf"],
}


def load_font(size, bold=False, kind=None):
    if not PIL_OK:
        return None
    kind = kind or ("mono_bold" if bold else "mono")
    key = (size, kind)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    font = None
    for name in _FONT_FILES[kind] + _FONT_FILES["mono"]:
        try:
            font = ImageFont.truetype(name, size)
        except Exception:
            continue
        if "bahnschrift" in name.lower():          # font variabile: istanza Bold
            try:
                for n in font.get_variation_names():
                    if n in (b"Bold", "Bold"):
                        font.set_variation_by_name(n)
                        break
            except Exception:
                pass
        break
    if font is None:
        try:
            font = ImageFont.load_default(size)
        except Exception:
            font = ImageFont.load_default()
    _FONT_CACHE[key] = font
    return font


def _cache_put_lru(cache, key, value, limit=12):
    cache[key] = value
    while len(cache) > limit:
        cache.pop(next(iter(cache)))
    return value


_VIGNETTE_CACHE = {}


def _vignette_mask(size, strength=0.85):
    key = (size, round(strength, 2))
    if key in _VIGNETTE_CACHE:
        return _VIGNETTE_CACHE[key]
    mask = Image.radial_gradient("L").resize(size).point(lambda v: int(v * strength))
    return _cache_put_lru(_VIGNETTE_CACHE, key, mask)


def _vgrad(size, top, bottom):
    w, h = size
    g = Image.new("RGB", (1, h))
    tp, bt = hex_to_rgb(top), hex_to_rgb(bottom)
    px = g.load()
    for y in range(h):
        t = y / max(1, h - 1)
        px[0, y] = tuple(int(lerp(tp[i], bt[i], t)) for i in range(3))
    return g.resize((w, h))


def _cover_fit(src, size):
    """Ridimensiona e ritaglia al centro per riempire `size` (cover)."""
    w, h = size
    sw, sh = src.size
    sc = max(w / sw, h / sh)
    src = src.resize((max(1, int(sw * sc)), max(1, int(sh * sc))))
    left = (src.width - w) // 2
    top = (src.height - h) // 2
    return src.crop((left, top, left + w, top + h))


def _chroma(img, px=2):
    """Aberrazione cromatica: canali rosso/blu leggermente sfasati."""
    r, g, b = img.convert("RGB").split()
    return Image.merge("RGB", (ImageChops.offset(r, -px, 0), g, ImageChops.offset(b, px, 0)))


def _hex_grid(draw, w, h, r, fill):
    dx, dy = r * math.sqrt(3), r * 1.5
    row, y = 0, -r
    while y < h + r:
        x = -dx + (dx / 2 if row % 2 else 0)
        while x < w + dx:
            pts = hexagon(x, y, r, math.pi / 6)
            draw.line(pts + pts[:2], fill=fill, width=1)
            x += dx
        y += dy
        row += 1


_BACKDROP_CACHE = {}


def render_backdrop(w, h, accent=None, center=(0.5, 0.45), hexr=22, base=None):
    """Sfondo olografico: gradiente, bagliore radiale, griglia esagonale, vignetta."""
    accent = accent or THEME["accent"]
    base = base or THEME["bg2"]
    w, h = max(2, int(w)), max(2, int(h))
    key = (w, h, accent, center, hexr, base)
    if key in _BACKDROP_CACHE:
        return _BACKDROP_CACHE[key]
    img = _vgrad((w, h), mix(base, accent, 0.035), THEME["bg"])
    gw, gh = int(w * 1.3), int(h * 1.6)
    glow = Image.radial_gradient("L").resize((gw, gh)).point(lambda v: max(0, 255 - v * 2))
    mask = Image.new("L", (w, h), 0)
    mask.paste(glow, (int(w * center[0] - gw / 2), int(h * center[1] - gh / 2)))
    img = Image.composite(Image.new("RGB", (w, h), hex_to_rgb(accent)), img,
                          mask.point(lambda v: int(v * 0.14)))
    if hexr:
        d = ImageDraw.Draw(img, "RGBA")
        _hex_grid(d, w, h, hexr, hex_to_rgb(accent) + (13,))
    img = Image.composite(Image.new("RGB", (w, h), (0, 0, 0)), img, _vignette_mask((w, h), 0.75))
    return _cache_put_lru(_BACKDROP_CACHE, key, img)


def render_logo(height=74, accent=None):
    """Logo: emblema esagonale con bagliore + ORION sfumato con aberrazione cromatica."""
    if not PIL_OK:
        return None
    accent = accent or THEME["accent"]
    S = 2
    W, H = 520 * S, height * S
    acc, mag = hex_to_rgb(accent), hex_to_rgb(THEME["magenta"])
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    # --- emblema ---
    em = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(em)
    cx, cy, r = 36 * S, H // 2, 30 * S
    outer = hexagon(cx, cy, r, math.pi / 6)
    d.line(outer + outer[:2], fill=acc + (255,), width=3 * S, joint="curve")
    inner = hexagon(cx, cy, r * 0.7, 0)
    d.line(inner + inner[:2], fill=acc + (150,), width=S)
    rr = r * 0.36
    d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=(255, 255, 255, 255), width=2 * S)
    for ax, ay in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        d.line([(cx + ax * rr * 1.25, cy + ay * rr * 1.25), (cx + ax * r * 0.95, cy + ay * r * 0.95)],
               fill=acc + (230,), width=S)
    d.ellipse([cx - 3 * S, cy - 3 * S, cx + 3 * S, cy + 3 * S], fill=mag + (255,))
    img = Image.alpha_composite(img, em.filter(ImageFilter.GaussianBlur(5 * S)))
    img = Image.alpha_composite(img, em)

    # --- titolo: maschera lettere spaziate ---
    f = load_font(44 * S, kind="display")
    m = Image.new("L", (W, H), 0)
    md = ImageDraw.Draw(m)
    tx, ty = 82 * S, 2 * S
    for ch in "ORION":
        md.text((tx, ty), ch, font=f, fill=255)
        tx += md.textlength(ch, font=f) + 7 * S
    title_end = tx
    glow = Image.new("RGBA", (W, H), acc + (0,))
    glow.putalpha(m.filter(ImageFilter.GaussianBlur(7 * S)).point(lambda v: int(v * 0.9)))
    img = Image.alpha_composite(img, glow)
    for col, dx in ((THEME["red"], -3 * S), (THEME["accent"], 3 * S)):
        lay = Image.new("RGBA", (W, H), hex_to_rgb(col) + (0,))
        lay.putalpha(ImageChops.offset(m, dx, 0).point(lambda v: int(v * 0.45)))
        img = Image.alpha_composite(img, lay)
    grad = _vgrad((W, H), "#ffffff", accent).convert("RGBA")
    grad.putalpha(m)
    img = Image.alpha_composite(img, grad)

    # --- sottotitolo, firma, versione ---
    d = ImageDraw.Draw(img)
    fs = load_font(12 * S, bold=True)
    sx = 84 * S
    for ch in "SPY · OSINT · CINEMA PRO":
        d.text((sx, 55 * S), ch, font=fs, fill=acc + (230,))
        sx += d.textlength(ch, font=fs) + 2 * S
    tx2 = title_end + 12 * S
    d.polygon([(tx2, 12 * S), (tx2 + 9 * S, 12 * S), (tx2, 21 * S)], fill=mag + (255,))
    d.text((tx2 + 14 * S, 10 * S), "CREATED BY " + CREATOR, font=load_font(12 * S, bold=True),
           fill=mag + (255,))
    vb = f"v{APP_VERSION} · SIM"
    fv = load_font(11 * S)
    vw = d.textlength(vb, font=fv)
    d.rectangle([tx2, 30 * S, tx2 + vw + 12 * S, 46 * S], outline=acc + (160,), width=S)
    d.text((tx2 + 6 * S, 32 * S), vb, font=fv, fill=acc + (220,))

    bbox = img.getbbox() or (0, 0, W, H)
    img = img.crop((0, 0, min(W, bbox[2] + 4 * S), H))
    return img.resize((img.width // S, height), Image.LANCZOS)


def render_radar_chart(axes, size=260, accent=None, bg=None):
    """Spider/radar chart olografico. axes = [(etichetta, valore0-100), ...]."""
    if not PIL_OK:
        return None
    accent = accent or THEME["accent"]
    bg = bg or THEME["panel"]
    S = 3
    W = size * S
    acc, line = hex_to_rgb(accent), hex_to_rgb(THEME["line2"])
    img = render_backdrop(W, W, accent, center=(0.5, 0.5), hexr=0, base=bg).copy()
    d = ImageDraw.Draw(img, "RGBA")          # su RGB: i colori RGBA vengono fusi
    cx = cy = W // 2
    R = int(W * 0.31)
    n = len(axes)

    def ang(k):
        return 2 * math.pi * k / n - math.pi / 2

    for ring in range(5, 0, -1):
        rr = R * ring / 5
        pts = [(cx + rr * math.cos(ang(k)), cy + rr * math.sin(ang(k))) for k in range(n)]
        d.polygon(pts, fill=acc + (12 if ring % 2 else 5,))
        d.line(pts + [pts[0]], fill=line + (200,), width=S)
    for k in range(n):
        d.line([(cx, cy), (cx + R * math.cos(ang(k)), cy + R * math.sin(ang(k)))],
               fill=line + (220,), width=S)
    fsm = load_font(8 * S)
    for ring in (1, 2, 3, 4):
        d.text((cx + 4 * S, cy - R * ring / 5), str(ring * 20), font=fsm,
               fill=hex_to_rgb(THEME["dim"]) + (170,), anchor="lm")

    poly = []
    for k, (_, val) in enumerate(axes):
        rr = R * max(0, min(100, val)) / 100
        poly.append((cx + rr * math.cos(ang(k)), cy + rr * math.sin(ang(k))))
    img = img.convert("RGBA")
    lay = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    ld = ImageDraw.Draw(lay)
    ld.polygon(poly, fill=acc + (70,))
    ld.line(poly + [poly[0]], fill=acc + (255,), width=2 * S, joint="curve")
    for p in poly:
        ld.ellipse([p[0] - 9 * S, p[1] - 9 * S, p[0] + 9 * S, p[1] + 9 * S], outline=acc + (255,),
                   width=S)
        ld.ellipse([p[0] - 4 * S, p[1] - 4 * S, p[0] + 4 * S, p[1] + 4 * S], fill=(255, 255, 255, 255))
    img = Image.alpha_composite(img, lay.filter(ImageFilter.GaussianBlur(6 * S)))
    img = Image.alpha_composite(img, lay).convert("RGB")

    d = ImageDraw.Draw(img, "RGBA")
    fl, fv = load_font(11 * S, bold=True), load_font(13 * S, bold=True)
    for k, (label, val) in enumerate(axes):
        lx = cx + (R + 34 * S) * math.cos(ang(k))
        ly = cy + (R + 30 * S) * math.sin(ang(k))
        d.text((lx, ly - 7 * S), label, font=fl, fill=hex_to_rgb(THEME["dim"]) + (255,), anchor="mm")
        d.text((lx, ly + 8 * S), str(int(val)), font=fv, fill=acc + (255,), anchor="mm")
    d.text((8 * S, W - 8 * S), "by " + CREATOR, font=load_font(9 * S),
           fill=hex_to_rgb(THEME["dim"]) + (140,), anchor="ls")
    return img.resize((size, size), Image.LANCZOS)


# landmark (x, y) relativi all'ellisse della testa → mesh "riconoscimento facciale"
_MESH_PTS = {
    "fh": (0, -0.78), "tl": (-0.62, -0.55), "tr": (0.62, -0.55), "bl": (-0.55, -0.22),
    "br": (0.55, -0.22), "bm": (0, -0.28), "el": (-0.36, -0.08), "er": (0.36, -0.08),
    "eli": (-0.14, -0.08), "eri": (0.14, -0.08), "nb": (0, 0.02), "nt": (0, 0.28),
    "nl": (-0.15, 0.33), "nr": (0.15, 0.33), "ml": (-0.32, 0.55), "mr": (0.32, 0.55),
    "mt": (0, 0.5), "mb": (0, 0.64), "jl": (-0.86, 0.12), "jr": (0.86, 0.12),
    "cl": (-0.62, 0.66), "cr": (0.62, 0.66), "ch": (0, 0.94),
}
_MESH_EDGES = [("fh", "tl"), ("fh", "tr"), ("tl", "bl"), ("tr", "br"), ("bl", "el"), ("br", "er"),
               ("bl", "bm"), ("br", "bm"), ("bm", "eli"), ("bm", "eri"), ("el", "eli"),
               ("er", "eri"), ("eli", "nb"), ("eri", "nb"), ("nb", "nt"), ("nt", "nl"),
               ("nt", "nr"), ("nl", "ml"), ("nr", "mr"), ("ml", "mt"), ("mr", "mt"), ("ml", "mb"),
               ("mr", "mb"), ("tl", "jl"), ("tr", "jr"), ("jl", "cl"), ("jr", "cr"), ("cl", "ch"),
               ("cr", "ch"), ("cl", "mb"), ("cr", "mb"), ("el", "jl"), ("er", "jr"), ("nl", "el"),
               ("nr", "er"), ("mb", "ch"), ("fh", "bm")]


def face_mesh_points(cx, cy, rx, ry, rng=None):
    j = (lambda: rng.uniform(-1.5, 1.5)) if rng else (lambda: 0.0)
    return {k: (cx + x * rx + j(), cy + y * ry + j()) for k, (x, y) in _MESH_PTS.items()}


def generate_portrait(seed, size=(240, 290), accent=None, caption="", subcaption="",
                      matched=True, redacted=True, base_image=None):
    """Ritratto 'da sorveglianza'. Se base_image è dato usa quel volto (IA, NON
    reale) come sfondo; altrimenti disegna una silhouette astratta procedurale."""
    if not PIL_OK:
        return None
    accent = accent or THEME["accent"]
    w, h = size
    rng = random.Random(int(hashlib.md5(str(seed).encode()).hexdigest(), 16))
    acc = hex_to_rgb(accent)

    if base_image is not None:
        # --- volto (IA / non reale) come sfondo, con grading olografico ---
        cx = w // 2
        head_rx, head_ry, head_cy = int(w * 0.26), int(h * 0.30), int(h * 0.50)
        img = _cover_fit(base_image.convert("RGB"), (w, h))
        img = Image.blend(img, Image.new("RGB", (w, h), acc), 0.10)
    else:
        palettes = [("#04121c", "#0b3346"), ("#071a16", "#0f3a33"), ("#0d0b1e", "#2a1d4a"),
                    ("#0a0f24", "#1a2c5a"), ("#06121a", "#0f3a4c"), ("#140a1a", "#3a1840")]
        top, bottom = rng.choice(palettes)
        img = _vgrad((w, h), top, bottom)

        # --- silhouette busto (layer separato, sfocato) ---
        cx = w // 2 + rng.randint(-12, 12)
        head_rx = int(w * rng.uniform(0.16, 0.19))
        head_ry = int(head_rx * rng.uniform(1.18, 1.32))
        head_cy = int(h * 0.40)
        neutral = (150, 170, 200)
        sil = tuple(int(lerp(hex_to_rgb(bottom)[i], neutral[i], 0.52)) for i in range(3))
        sil_dark = tuple(int(c * 0.55) for c in sil)
        rim = tuple(int(lerp(acc[i], 255, 0.35)) for i in range(3))
        lit_left = rng.random() < 0.5

        layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        sd = ImageDraw.Draw(layer)
        sw = int(w * rng.uniform(0.66, 0.84))
        sh_top = head_cy + int(head_ry * 0.7)
        sd.ellipse([cx - sw // 2, sh_top, cx + sw // 2, h + int(h * 0.4)], fill=sil + (255,))
        nw = int(head_rx * 0.75)
        sd.polygon([(cx - nw, sh_top + 4), (cx + nw, sh_top + 4),
                    (cx + nw - 4, head_cy), (cx - nw + 4, head_cy)], fill=sil + (255,))
        sd.ellipse([cx - head_rx, head_cy - head_ry, cx + head_rx, head_cy + head_ry],
                   fill=sil + (255,))
        sd.pieslice([cx - head_rx - 2, head_cy - head_ry - 4,
                     cx + head_rx + 2, head_cy + int(head_ry * 0.35)], 180, 360,
                    fill=sil_dark + (255,))
        if lit_left:
            sd.chord([cx, head_cy - head_ry, cx + head_rx, head_cy + head_ry], -90, 90,
                     fill=sil_dark + (110,))
            sd.arc([cx - head_rx, head_cy - head_ry, cx + head_rx, head_cy + head_ry],
                   100, 250, fill=rim + (230,), width=3)
        else:
            sd.chord([cx - head_rx, head_cy - head_ry, cx, head_cy + head_ry], 90, 270,
                     fill=sil_dark + (110,))
            sd.arc([cx - head_rx, head_cy - head_ry, cx + head_rx, head_cy + head_ry],
                   -70, 80, fill=rim + (230,), width=3)
        layer = layer.filter(ImageFilter.GaussianBlur(1.4))
        img = Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")

    # grana + aberrazione cromatica
    try:
        noise = Image.effect_noise((w, h), 26).convert("L")
        img = Image.blend(img, Image.merge("RGB", (noise, noise, noise)), 0.06)
    except Exception:
        pass
    img = _chroma(img, 2)
    draw = ImageDraw.Draw(img, "RGBA")

    # glitch bars occasionali
    if rng.random() < 0.5:
        for _ in range(rng.randint(1, 3)):
            gy = rng.randint(int(h * 0.25), int(h * 0.7))
            gh = rng.randint(2, 6)
            dxg = rng.randint(4, 14) * rng.choice([-1, 1])
            strip = img.crop((0, gy, w, gy + gh))
            img.paste(strip, (dxg, gy))
            draw = ImageDraw.Draw(img, "RGBA")
            draw.rectangle([0, gy, w, gy + gh], fill=acc + (30,))

    # scanline
    for y in range(0, h, 3):
        draw.line([(0, y), (w, y)], fill=(0, 0, 0, 55))

    # mesh facciale
    if matched or rng.random() < 0.4:
        pts = face_mesh_points(cx, head_cy, head_rx, head_ry, rng)
        for a, b in _MESH_EDGES:
            draw.line([pts[a], pts[b]], fill=acc + (60,), width=1)
        for px, py in pts.values():
            draw.ellipse([px - 1.6, py - 1.6, px + 1.6, py + 1.6], fill=acc + (200,))

    # barra REDACTED sugli occhi (rinforza: non è una persona reale)
    if redacted and rng.random() < 0.45:
        ey = head_cy - int(head_ry * 0.10)
        draw.rectangle([cx - head_rx - 4, ey - 8, cx + head_rx + 4, ey + 8],
                       fill=(0, 0, 0, 235))
        draw.text((cx, ey), "REDACTED", font=load_font(10, bold=True),
                  fill=hex_to_rgb(THEME["red"]), anchor="mm")

    # vignettatura
    img = Image.composite(Image.new("RGB", (w, h), (0, 0, 0)), img, _vignette_mask((w, h)))
    draw = ImageDraw.Draw(img, "RGBA")

    # face-lock box + reticolo
    bx0, by0 = cx - head_rx - 10, head_cy - head_ry - 8
    bx1, by1 = cx + head_rx + 10, head_cy + head_ry + 14
    tick = 16
    for (px, py, sx, sy) in [(bx0, by0, 1, 1), (bx1, by0, -1, 1),
                             (bx0, by1, 1, -1), (bx1, by1, -1, -1)]:
        draw.line([(px, py + sy * tick), (px, py), (px + sx * tick, py)], fill=acc, width=2)
    fcy = head_cy - int(head_ry * 0.15)
    r = int(head_rx * 0.45)
    draw.ellipse([cx - r, fcy - r, cx + r, fcy + r], outline=acc + (130,), width=1)
    draw.line([(cx - r - 6, fcy), (cx + r + 6, fcy)], fill=acc + (100,), width=1)
    draw.line([(cx, fcy - r - 6), (cx, fcy + r + 6)], fill=acc + (100,), width=1)

    # cornice tagliata + angoli
    m = 6
    fr = chamfer(m, m, w - m, h - m, 14)
    draw.line(list(zip(fr[::2], fr[1::2])) + [(fr[0], fr[1])], fill=acc + (120,), width=1)
    L = 22
    for (ax, ay, dx, dy) in [(w - m, m, -1, 1), (m, h - m, 1, -1)]:      # angoli pieni
        draw.line([(ax, ay + dy * L), (ax, ay), (ax + dx * L, ay)], fill=acc, width=3)
    draw.line([(m, m + 14), (m + 14, m)], fill=acc, width=3)               # angoli tagliati
    draw.line([(w - m, h - m - 14), (w - m - 14, h - m)], fill=acc, width=3)

    # HUD testo
    fmono = load_font(11)
    fsmall = load_font(12, bold=True)
    bar = 34 if caption else 0
    cam = f"CAM-{rng.randint(1,9)}{rng.choice('ABKZ')}{rng.randint(10,99)}"
    draw.text((m + 10, m + 6), cam, font=fmono, fill=acc)
    draw.text((w - m - 66, m + 6), "● REC", font=fsmall, fill=hex_to_rgb(THEME["red"]))
    lat = rng.uniform(35, 60)
    lon = rng.uniform(-8, 25)
    draw.text((m + 10, m + 24), f"{lat:.4f}N {lon:.4f}E", font=fmono, fill=acc + (170,))
    bx = m + 10
    for i in range(26):
        if rng.random() < 0.5:
            draw.line([(bx + i * 3, m + 42), (bx + i * 3, m + 50)], fill=acc + (200,), width=2)
    ry = h - bar - 20
    ts = f"{rng.randint(0,23):02d}:{rng.randint(0,59):02d}:{rng.randint(0,59):02d}"
    draw.text((m + 10, ry), ts, font=fmono, fill=acc)
    tag = f"MATCH {rng.randint(78,99)}.{rng.randint(0,9)}%" if matched else "NO MATCH"
    col = hex_to_rgb(THEME["green"]) if matched else hex_to_rgb(THEME["red"])
    draw.text((w - m - 100, ry), tag, font=fsmall, fill=col)

    # caption bar + watermark creatore
    if caption:
        draw.rectangle([0, h - bar, w, h], fill=(0, 0, 0, 200))
        draw.line([(0, h - bar), (w, h - bar)], fill=acc + (200,), width=1)
        draw.text((10, h - bar + 4), caption[:22], font=load_font(14, bold=True),
                  fill=hex_to_rgb(THEME["white"]))
        if subcaption:
            draw.text((10, h - bar + 20), subcaption[:max(12, (w - 80) // 7)], font=fmono,
                      fill=hex_to_rgb(THEME["dim"]))
    draw.text((w - 8, h - 6), CREATOR, font=load_font(10),
              fill=hex_to_rgb(THEME["white"]) + (140,), anchor="rs")
    return img


_MAP_CACHE = {}


def render_world_map(w, h, view, accent=None):
    """Mappa del mondo a punti (equirettangolare) per la vista (lon0, lat0, lon1, lat1)."""
    accent = accent or THEME["accent"]
    w, h = max(2, int(w)), max(2, int(h))
    lon0, lat0, lon1, lat1 = view
    key = (w, h, tuple(round(v, 3) for v in view), accent)
    if key in _MAP_CACHE:
        return _MAP_CACHE[key]
    acc = hex_to_rgb(accent)
    base = render_backdrop(w, h, accent, center=(0.5, 0.5), hexr=0).convert("RGBA")
    dot_col = hex_to_rgb(mix(accent, THEME["accent2"], 0.15))
    ppd = w / max(1e-6, lon1 - lon0)                 # pixel per grado (uguale in x e y)
    step = 0.5
    while step * ppd < 6.5:
        step += 0.5
    dots = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dd = ImageDraw.Draw(dots)
    r = max(1.2, min(2.5, step * ppd * 0.23))
    lat = math.floor(lat1 / step) * step
    while lat >= lat0:
        y = (lat1 - lat) * ppd
        lon = math.ceil(lon0 / step) * step
        while lon <= lon1:
            x = (lon - lon0) * ppd
            if land_at(lat, lon):
                dd.ellipse([x - r, y - r, x + r, y + r], fill=dot_col + (215,))
            else:
                dd.point((x, y), fill=acc + (34,))
            lon += step
        lat -= step
    glow = dots.filter(ImageFilter.GaussianBlur(4))
    base = Image.alpha_composite(base, glow)
    base = Image.alpha_composite(base, dots).convert("RGB")
    d = ImageDraw.Draw(base, "RGBA")           # su RGB: linee semi-trasparenti fuse
    g = 10 if (lon1 - lon0) < 120 else 30
    f = load_font(10)
    dim = hex_to_rgb(THEME["dim"])
    lon = math.ceil(lon0 / g) * g
    while lon <= lon1:
        x = (lon - lon0) * ppd
        d.line([(x, 0), (x, h)], fill=acc + (26,), width=1)
        lab = ((lon + 180) % 360) - 180
        d.text((x + 3, h - 14), f"{abs(lab):.0f}°{'E' if lab >= 0 else 'W'}", font=f, fill=dim + (150,))
        lon += g
    lat = math.ceil(lat0 / g) * g
    while lat <= lat1:
        y = (lat1 - lat) * ppd
        d.line([(0, y), (w, y)], fill=acc + (26,), width=1)
        d.text((4, y + 2), f"{abs(lat):.0f}°{'N' if lat >= 0 else 'S'}", font=f, fill=dim + (150,))
        lat += g
    base = Image.composite(Image.new("RGB", (w, h), (0, 0, 0)), base, _vignette_mask((w, h), 0.45))
    return _cache_put_lru(_MAP_CACHE, key, base, limit=6)


def glitch_frame(img, amount, rng):
    """Fotogramma 'disturbato': strisce traslate + aberrazione cromatica."""
    if amount <= 0:
        return img
    out = img.copy()
    w, h = out.size
    for _ in range(int(3 + amount * 10)):
        y = rng.randint(0, h - 3)
        hh = rng.randint(2, max(3, int(h * 0.05 * amount) + 3))
        dx = int(rng.uniform(-1, 1) * w * 0.06 * amount)
        out.paste(img.crop((0, y, w, min(h, y + hh))), (dx, y))
    if amount > 0.3:
        out = _chroma(out, int(2 + 6 * amount))
    return out


# ===========================================================================
#  DATI  —  dossier simulato deterministico
# ===========================================================================
FIRST = ["Marco", "Luca", "Andrea", "Giulia", "Sara", "Elena", "Matteo", "Alex",
         "Nina", "Ivan", "Sofia", "Dario", "Karim", "Mila", "Noa", "Leo"]
LAST = ["Rossi", "Bianchi", "Esposito", "Romano", "Ferrari", "Costa", "Moreau",
        "Keller", "Petrov", "Nakamura", "Vidal", "Okoye", "Haas", "Silva"]
# città con coordinate REALI (nome, lat, lon)
CITIES = [("Roma, IT", 41.902, 12.496), ("Milano, IT", 45.464, 9.190),
          ("Napoli, IT", 40.852, 14.268), ("Torino, IT", 45.070, 7.687),
          ("London, UK", 51.507, -0.128), ("Berlin, DE", 52.520, 13.405),
          ("Paris, FR", 48.857, 2.352), ("Zürich, CH", 47.377, 8.542),
          ("Lisboa, PT", 38.722, -9.139), ("Wien, AT", 48.209, 16.373),
          ("New York, US", 40.713, -74.006), ("Dubai, AE", 25.205, 55.271)]


def project_equirect(lat, lon):
    """Proiezione equirettangolare → frazioni (0..1) per la mappa stilizzata."""
    return (lon + 180.0) / 360.0, (90.0 - lat) / 180.0


MAPBOX_HTML = r"""<!DOCTYPE html>
<html lang="it"><head><meta charset="utf-8"/>
<title>ORION 3D GEO-INT — by __CREATOR__</title>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<script src="https://api.mapbox.com/mapbox-gl-js/v3.9.0/mapbox-gl.js"></script>
<link href="https://api.mapbox.com/mapbox-gl-js/v3.9.0/mapbox-gl.css" rel="stylesheet"/>
<style>
  html,body{margin:0;height:100%;background:#05060b;font-family:Consolas,monospace;color:#e2e8ff}
  #map{position:absolute;inset:0}
  .hud{position:absolute;left:16px;top:14px;z-index:5;pointer-events:none}
  .hud h1{margin:0;font-size:20px;color:#00e5ff;text-shadow:0 0 12px #00e5ff}
  .hud p{margin:2px 0;font-size:12px;color:#8791b8}
  .badge{position:absolute;right:16px;top:14px;z-index:5;color:#ffb020;font-size:12px;
         border:1px solid #ffb020;padding:4px 8px;border-radius:4px;background:#20140acc}
  .cred{position:absolute;right:16px;bottom:14px;z-index:5;color:#ff2bd6;font-size:12px;
        text-shadow:0 0 8px #ff2bd6}
  .ping{width:14px;height:14px;border-radius:50%;box-shadow:0 0 0 0 currentColor;
        animation:pulse 1.6s infinite;cursor:pointer}
  @keyframes pulse{0%{box-shadow:0 0 0 0 currentColor}70%{box-shadow:0 0 0 16px transparent}
                   100%{box-shadow:0 0 0 0 transparent}}
  .mapboxgl-popup-content{background:#0f1320;color:#e2e8ff;border:1px solid #1e2444;
        font-family:Consolas,monospace;font-size:12px}
  .mapboxgl-popup-content b{color:#00e5ff}
  .tour{position:absolute;left:50%;bottom:16px;transform:translateX(-50%);z-index:5;
        display:flex;gap:8px}
  .tour button{background:#151a2b;color:#00e5ff;border:1px solid #1e2444;padding:6px 12px;
        font-family:Consolas,monospace;cursor:pointer;border-radius:4px}
</style></head><body>
<div id="map"></div>
<div class="hud"><h1>◈ ORION // 3D GEO-INT</h1>
  <p>TARGET: __TARGET__ · operator __CREATOR__</p>
  <p>◦ SIMULAZIONE — coordinate reali, dati fittizi ◦</p></div>
<div class="badge">CLASSIFIED // SIM</div>
<div class="cred">created by __CREATOR__</div>
<div class="tour"><button id="tourBtn">⏸ ferma tour</button>
  <button id="topBtn">🌍 globo</button></div>
<script>
mapboxgl.accessToken="__TOKEN__";
const targets=__MARKERS__;
const first=targets[0]||{lat:41.9,lon:12.5};
const colorFor=t=>({LOW:"#39ff14",MEDIUM:"#ffb020",HIGH:"#ff3b5c"}[t]||"#00e5ff");
const map=new mapboxgl.Map({container:"map",style:"mapbox://styles/mapbox/standard",
  center:[first.lon,first.lat],zoom:4,pitch:62,bearing:-18,projection:"globe",antialias:true});
map.addControl(new mapboxgl.NavigationControl({visualizePitch:true}),"bottom-right");
map.on("style.load",()=>{
  try{map.setConfigProperty("basemap","lightPreset","night");}catch(e){}
  map.addSource("dem",{type:"raster-dem",url:"mapbox://mapbox.mapbox-terrain-dem-v1",
    tileSize:512,maxzoom:14});
  map.setTerrain({source:"dem",exaggeration:1.5});
  map.setFog({color:"rgb(10,12,20)","high-color":"rgb(20,45,90)","horizon-blend":0.2,
    "space-color":"rgb(2,3,8)","star-intensity":0.7});
  targets.forEach(t=>{
    const el=document.createElement("div");el.className="ping";el.style.color=colorFor(t.threat);
    el.style.background=colorFor(t.threat);
    new mapboxgl.Marker({element:el}).setLngLat([t.lon,t.lat])
      .setPopup(new mapboxgl.Popup({offset:18}).setHTML(
        "<b>"+t.name+"</b><br>"+t.role+"<br>minaccia: "+t.threat+
        "<br>"+t.lat.toFixed(4)+", "+t.lon.toFixed(4)+"<br><i>SIM · by __CREATOR__</i>"))
      .addTo(map);
  });
  let i=0,playing=true;
  function tour(){ if(!playing||!targets.length)return;
    const t=targets[i%targets.length];i++;
    map.flyTo({center:[t.lon,t.lat],zoom:6.5,pitch:65,bearing:(i*40)%360,
      duration:5000,essential:true});}
  tour();const iv=setInterval(tour,6000);
  document.getElementById("tourBtn").onclick=e=>{playing=!playing;
    e.target.textContent=playing?"⏸ ferma tour":"▶ avvia tour";if(playing)tour();};
  document.getElementById("topBtn").onclick=()=>map.flyTo({center:[10,30],zoom:1.6,pitch:0,
    bearing:0,duration:3000});
  map.on("dragstart",()=>{playing=false;
    document.getElementById("tourBtn").textContent="▶ avvia tour";});
});
</script></body></html>"""


def build_mapbox_html(data, token):
    """Costruisce la pagina Mapbox GL JS (globo 3D + terreno + marker identità)."""
    # nome e ruolo finiscono in setHTML() → vanno escapati; il JSON finisce
    # dentro <script> → niente '<', '>' o '&' letterali.
    markers = [{"name": html.escape(it["name"]), "lat": it["geo"][0], "lon": it["geo"][1],
                "threat": it["threat"], "role": html.escape(it["role"])}
               for it in data["identities"]]
    markers_js = (json.dumps(markers).replace("<", "\\u003c")
                  .replace(">", "\\u003e").replace("&", "\\u0026"))
    return (MAPBOX_HTML
            .replace("__TOKEN__", json.dumps(token)[1:-1])
            .replace("__MARKERS__", markers_js)
            .replace("__TARGET__", html.escape(str(data["target"])))
            .replace("__CREATOR__", CREATOR))


ROLES = ["Consulente", "Sviluppatore", "Analista", "Imprenditore", "Fotografo",
         "Ricercatore", "Broker", "Giornalista", "Ingegnere", "DJ", "Trader"]
PLATFORMS = [("Instagram", "◎"), ("Facebook", "f"), ("X", "✕"), ("LinkedIn", "in"),
             ("TikTok", "♪"), ("YouTube", "▶"), ("Telegram", "✈"), ("GitHub", "⌥")]
DOMAINS = ["gmail.com", "proton.me", "outlook.com", "icloud.com", "fastmail.com"]
PHOTO_TAGS = ["Profilo social", "Foto professionale", "Evento pubblico", "Foto di gruppo",
              "Conferenza", "Vacanza", "Documento", "Articolo stampa", "Serata",
              "Sede di lavoro", "Sport", "Viaggio"]
EVENTS = ["Account creato", "Cambio città", "Nuovo dispositivo", "Login sospetto",
          "Post virale", "Data breach", "Viaggio internazionale", "Nuovo lavoro",
          "Transazione rilevante", "Cambio numero"]


def _slug(name):
    """Versione 'sicura' del nome: usata per handle, email e nomi di file
    (niente spazi, slash, due punti, ecc.)."""
    return "".join(c for c in name.lower() if c.isalnum() or c in "._-") or "unknown"


def build_dossier(target, variant=0):
    """Dossier deterministico: stesso target (+ stessa variante) → stessi dati.
    `variant` > 0 produce una versione alternativa (bottone RIGENERA)."""
    target = (target or "Sconosciuto").strip()
    key = target.lower() if not variant else f"{target.lower()}#{variant}"
    seed = int(hashlib.md5(key.encode()).hexdigest(), 16)
    rng = random.Random(seed)

    n_id = rng.randint(2, 4)
    identities = []
    for i in range(n_id):
        if i == 0:
            name, status, conf = target, "IDENTITÀ PRIMARIA", rng.randint(88, 99)
        else:
            if rng.random() < 0.5 and len(target.split()) >= 2:
                name = f"{target.split()[0]} {rng.choice(LAST)}"
            else:
                name = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
            status, conf = "IDENTITÀ SECONDARIA", rng.randint(58, 84)
        first = name.split()[0].lower()
        city = rng.choice(CITIES)
        identities.append({
            "index": i, "name": name, "status": status, "confidence": conf,
            "age": rng.randint(24, 57), "location": city[0], "geo": (city[1], city[2]),
            "role": rng.choice(ROLES),
            "threat": rng.choice(["LOW", "LOW", "MEDIUM", "MEDIUM", "HIGH"]),
            "aliases": [f"{first}_{rng.randint(10,99)}",
                        f"{first}.{rng.choice(['ofc','real','x','hq'])}"],
            "social_score": rng.randint(45, 96),
            "biometrics": {
                "eyes": rng.choice(["Marroni", "Verdi", "Azzurri", "Nocciola"]),
                "height": f"{rng.randint(160,195)} cm",
                "build": rng.choice(["Snella", "Media", "Atletica", "Robusta"]),
                "marks": rng.choice(["Nessuno", "Tatuaggio", "Cicatrice", "Occhiali"]),
            },
        })

    photos = []
    for i in range(rng.randint(12, 20)):
        owner = rng.randint(0, n_id - 1)
        photos.append({
            "id": i, "identity": owner, "identity_name": identities[owner]["name"],
            "tag": rng.choice(PHOTO_TAGS),
            "date": f"20{rng.randint(20,25)}-{rng.randint(1,12):02d}-{rng.randint(1,28):02d}",
            "location": rng.choice(CITIES)[0], "quality": rng.choice(["SD", "HD", "HD", "4K"]),
            "intel": rng.randint(4, 10),
            "source": rng.choice([p[0] for p in PLATFORMS] + ["Archivio", "Registro"]),
            "matched": rng.random() > 0.15,
        })

    socials = []
    for plat, glyph in rng.sample(PLATFORMS, rng.randint(5, len(PLATFORMS))):
        socials.append({
            "platform": plat, "glyph": glyph,
            "handle": "@" + _slug(target)[:14] + rng.choice(["", "_", str(rng.randint(1, 99))]),
            "followers": f"{rng.randint(1,240)}K", "activity": rng.choice(
                ["Molto alta", "Alta", "Media", "Bassa"]),
            "last_seen": f"{rng.randint(1,20)}g fa", "verified": rng.random() < 0.35,
            "posts": rng.randint(40, 1200),
        })

    emails = []
    for dom in rng.sample(DOMAINS, rng.randint(2, 4)):
        emails.append({"address": f"{_slug(target)[:16]}@{dom}",
                       "breached": rng.random() < 0.4, "leaks": rng.randint(0, 4),
                       "type": rng.choice(["Personale", "Lavoro", "Backup"])})

    footprint = {
        "domains": rng.randint(2, 11), "platforms": len(socials),
        "records": rng.randint(3, 9), "breaches": sum(1 for e in emails if e["breached"]),
        "exposure": rng.randint(40, 96), "privacy": rng.randint(12, 60),
        "presence": rng.choice(["Estesa", "Molto alta", "Globale"]),
    }
    behavior = {
        "online": rng.choice(["Notturno", "Diurno", "Continuo", "Irregolare"]),
        "shopping": rng.choice(["Tech", "Lusso", "Viaggi", "Vario"]),
        "travel": rng.choice(["Frequente", "Internazionale", "Occasionale"]),
        "engagement": rng.choice(["Molto alto", "Alto", "Medio"]),
        "sentiment": rng.randint(-40, 70),
    }
    finance = {"cards": rng.randint(1, 5), "accounts": rng.randint(1, 4),
               "wallets": rng.randint(0, 3), "last4": f"•••• {rng.randint(1000,9999)}",
               "monthly": f"€{rng.randint(2,18)}.{rng.randint(0,9)}k"}

    # timeline eventi
    timeline = []
    base = datetime.now()                      # non deterministico: date relative a oggi
    for _ in range(rng.randint(6, 9)):
        base = base - timedelta(days=rng.randint(20, 200))
        timeline.append({"date": base.strftime("%Y-%m-%d"), "event": rng.choice(EVENTS),
                         "sev": rng.choice(["info", "warn", "bad"])})

    risk = min(99, int(footprint["exposure"] * 0.6 + (100 - footprint["privacy"]) * 0.4))
    case_id = f"ORION-{rng.randint(1000,9999)}-{rng.choice('ABCDEFXZ')}{rng.randint(10,99)}"
    return {
        "simulation": True, "schema": DOSSIER_SCHEMA, "variant": variant,
        "creator": CREATOR, "target": target,
        "case_id": case_id, "classification": rng.choice(["CONFIDENTIAL", "SECRET", "TOP SECRET"]),
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "summary": {"threat": identities[0]["threat"], "confidence": identities[0]["confidence"],
                    "clearance": f"LEVEL {rng.randint(2,4)}", "risk": risk},
        "identities": identities, "photos": photos, "socials": socials, "emails": emails,
        "footprint": footprint, "behavior": behavior, "finance": finance, "timeline": timeline,
    }


# ===========================================================================
#  WIDGET HUD  —  pulsanti neon, pannelli, barre, schede, interruttori, toast
# ===========================================================================
class NeonButton(tk.Canvas):
    """Pulsante HUD: angoli tagliati, bagliore al passaggio del mouse, riflesso animato."""

    def __init__(self, parent, text, command=None, color=None, primary=False, height=34,
                 width=120, font=None, sound="click"):
        self.bgc = bg_of(parent)
        super().__init__(parent, width=width, height=height, bg=self.bgc, highlightthickness=0,
                         bd=0, cursor="hand2")
        self.text, self.command, self.primary, self.sound = text, command, primary, sound
        self.color = color or THEME["accent"]
        self.font = font or (UI, 10, "bold")
        self._state = "normal"
        self.hover = self.pressed = False
        self.shine = None
        self._shine_id = None
        self.bind("<Configure>", self._draw)
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)
        self.bind("<ButtonPress-1>", self._press)
        self.bind("<ButtonRelease-1>", self._release)
        self.bind("<Destroy>", self._destroyed, add="+")

    def configure(self, cnf=None, **kw):
        changed = False
        if "state" in kw:
            self._state = kw.pop("state")
            kw["cursor"] = "hand2" if self._state == "normal" else "arrow"
            changed = True
        for k in ("text", "color", "command"):
            if k in kw:
                setattr(self, k, kw.pop(k))
                changed = True
        res = super().configure(cnf, **kw) if (cnf or kw) else None
        if changed:
            self._draw()
        return res

    config = configure

    def _destroyed(self, e):
        if str(e.widget) == str(self) and self._shine_id:
            try:
                self.after_cancel(self._shine_id)
            except tk.TclError:
                pass

    def _draw(self, _=None):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w <= 1:
            w, h = int(self["width"]), int(self["height"])
        dis = self._state == "disabled"
        c = mix(self.color, self.bgc, 0.55) if dis else self.color
        k = min(10, h // 3)
        hot = self.hover and not dis
        if self.primary:
            fill = mix(c, "#ffffff", 0.22) if hot else c
            if self.pressed and hot:
                fill = mix(c, "#000000", 0.25)
            fg = mix(self.bgc, "#000000", 0.4) if dis else "#000000"
            edge = mix(c, "#ffffff", 0.4)
        else:
            fill = mix(self.bgc, c, 0.38 if (self.pressed and hot) else 0.2 if hot else 0.07)
            fg = "#ffffff" if hot else c
            edge = c if hot else mix(self.bgc, c, 0.5)
        if hot:
            self.create_polygon(chamfer(0, 0, w - 1, h - 1, k + 1), fill="",
                                outline=mix(self.bgc, c, 0.45), width=2)
        self.create_polygon(chamfer(2, 2, w - 3, h - 3, k), fill=fill, outline=edge)
        if self.shine is not None and hot:
            x = self.shine
            self.create_polygon(x, 4, x + 16, 4, x + 6, h - 4, x - 10, h - 4,
                                fill=mix(fill, "#ffffff", 0.28), outline="")
        self.create_line(7, h * 0.32, 7, h * 0.68, fill=fg if self.primary else c, width=2)
        self.create_rectangle(w - 13, 5, w - 9, 8, fill=edge, outline="")
        self.create_text(w / 2 + 2, h / 2, text=self.text, fill=fg, font=self.font)

    def _enter(self, _):
        self.hover = True
        if self._state == "normal":
            self.shine = 6
            if not self._shine_id:
                self._shine_id = self.after(16, self._shine_step)
        self._draw()

    def _shine_step(self):
        self._shine_id = None
        if not self.hover or self.shine is None:
            return
        w = self.winfo_width()
        self.shine += max(8, w / 10)
        if self.shine > w - 8:
            self.shine = None
        self._draw()
        if self.shine is not None:
            self._shine_id = self.after(16, self._shine_step)

    def _leave(self, _):
        self.hover = self.pressed = False
        self.shine = None
        self._draw()

    def _press(self, _):
        if self._state == "normal":
            self.pressed = True
            self._draw()

    def _release(self, _):
        was = self.pressed
        self.pressed = False
        self._draw()
        if was and self.hover and self._state == "normal":
            if self.sound:
                sfx(self.sound)
            if callable(self.command):
                self.command()


class HudPanel(tk.Frame):
    """Pannello con testata olografica (linguetta tagliata + indicatori lampeggianti).
    I contenuti vanno messi in `.body`."""

    def __init__(self, parent, title, color=None, pad=12, bg=None):
        self.bgc = bg or THEME["panel"]
        super().__init__(parent, bg=self.bgc, highlightthickness=1,
                         highlightbackground=THEME["line"], highlightcolor=THEME["line"])
        self.title, self.color = title, color or THEME["accent"]
        self.head = tk.Canvas(self, height=30, bg=self.bgc, highlightthickness=0)
        self.head.pack(fill="x")
        self.body = tk.Frame(self, bg=self.bgc)
        self.body.pack(fill="both", expand=True, padx=pad, pady=(4, pad))
        self.head.bind("<Configure>", self._draw)
        self._blink = 0
        Anim(self.head, 650, self._tick)

    def _draw(self, _=None):
        c, col, bgc = self.head, self.color, self.bgc
        c.delete("all")
        w = c.winfo_width()
        f = (DISPLAY, 10, "bold")
        x1 = 26 + text_w(self.title, f) + 16
        c.create_polygon(chamfer(0, 0, x1, 26, 10, "br"), fill=mix(bgc, col, 0.16), outline="")
        c.create_line(0, 26, w, 26, fill=mix(bgc, col, 0.35))
        c.create_line(1, 0, 1, 26, fill=col, width=3)
        c.create_text(14, 13, text=self.title, anchor="w", font=f, fill=col)
        for x in range(int(x1) + 10, w - 46, 9):
            c.create_line(x, 21, x, 26, fill=mix(bgc, col, 0.22))
        for i in range(3):
            c.create_rectangle(w - 14 - i * 9, 10, w - 9 - i * 9, 15, outline="", tags=f"b{i}",
                               fill=mix(bgc, col, 0.35))

    def _tick(self):
        if not visible(self.head):
            return 1500
        self._blink = (self._blink + 1) % 3
        for i in range(3):
            self.head.itemconfig(f"b{i}", fill=mix(self.bgc, self.color,
                                                   1.0 if i == self._blink else 0.3))


class SegmentBar(tk.Canvas):
    """Barra di avanzamento a segmenti inclinati con riflesso che scorre."""

    def __init__(self, parent, segments=30, height=14):
        super().__init__(parent, height=height, bg=bg_of(parent), highlightthickness=0)
        self.n = segments
        self.value = self.target = 0.0
        self.active = False
        self.phase = 0
        self.bind("<Configure>", self._draw)
        Anim(self, 33, self._tick)

    def set(self, v, active=None):
        self.target = max(0.0, min(100.0, float(v)))
        if active is not None:
            self.active = active

    def _tick(self):
        if not visible(self):
            return 300
        moving = abs(self.target - self.value) > 0.3
        if moving:
            self.value += (self.target - self.value) * 0.22
        elif self.value != self.target:
            self.value = self.target
            moving = True
        if moving or self.active:
            self.phase += 1
            self._draw()
            return 33
        return 150

    def _draw(self, _=None):
        self.delete("all")
        w, h = self.winfo_width(), int(self["height"])
        n, gap, bgc, acc = self.n, 3, self["bg"], THEME["accent"]
        sw = (w - gap * (n - 1) - 6) / n
        filled = self.value / 100 * n
        hi = (self.phase // 2) % (n + 6) if self.active else -99
        for i in range(n):
            x0 = 3 + i * (sw + gap)
            if i + 1 <= filled:
                col = mix(THEME["accent2"], acc, i / max(1, n - 1))
                if abs(i - hi) <= 1:
                    col = mix(col, "#ffffff", 0.55 if i == hi else 0.25)
            elif i < filled:
                col = mix(bgc, acc, 0.45)
            else:
                col = mix(bgc, acc, 0.10)
            self.create_polygon(x0 + 3, 1, x0 + sw + 3, 1, x0 + sw, h - 1, x0, h - 1,
                                fill=col, outline="")


class StatTile(tk.Canvas):
    """Riquadro metrica con conteggio animato e barra di riempimento."""

    def __init__(self, parent, label, color, height=56):
        super().__init__(parent, height=height, width=120, bg=bg_of(parent), highlightthickness=0)
        self.label, self.color = label, color
        self.value = None
        self.suffix = ""
        self.ratio = 0.0
        self.t0 = 0.0
        self.p = 1.0
        self.bind("<Configure>", self._draw)
        Anim(self, 33, self._tick)

    def set(self, value, ratio=1.0, suffix=""):
        self.value, self.suffix = value, suffix
        self.ratio = max(0.0, min(1.0, ratio))
        self.t0, self.p = time.time(), 0.0

    def _tick(self):
        if self.p >= 1.0:
            return 200
        if not visible(self):            # l'animazione parte quando la scheda è visibile
            self.t0 = time.time()
            return 200
        self.p = ease_out((time.time() - self.t0) / 0.9)
        self._draw()
        return 33

    def _draw(self, _=None):
        self.delete("all")
        w, h = self.winfo_width(), int(self["height"])
        card, c = THEME["card"], self.color
        self.create_polygon(chamfer(1, 1, w - 2, h - 2, 9), fill=card, outline=THEME["line"])
        self.create_line(2, 10, 2, h - 10, fill=c, width=2)
        self.create_text(12, 13, anchor="w", text=self.label, fill=c, font=(UI, 8, "bold"))
        v = "—" if self.value is None else f"{int(round(self.value * self.p))}{self.suffix}"
        self.create_text(12, h / 2 + 5, anchor="w", text=v, fill=THEME["white"],
                         font=(DISPLAY, 16, "bold"))
        self.create_line(12, h - 8, w - 12, h - 8, fill=THEME["line"], width=2)
        if self.value is not None:
            self.create_line(12, h - 8, 12 + (w - 24) * self.ratio * self.p, h - 8, fill=c, width=2)
        self.create_rectangle(w - 15, 6, w - 8, 8, fill=mix(card, c, 0.6), outline="")


class ThreatBanner(tk.Canvas):
    """Testata del dossier: anello di rischio, livello minaccia luminoso, scala."""

    def __init__(self, parent, height=112):
        super().__init__(parent, height=height, bg=bg_of(parent), highlightthickness=0)
        self.data = None
        self.t0 = 0.0
        self.phase = 0
        self.bind("<Configure>", self._draw)
        Anim(self, 60, self._tick)

    def set(self, data):
        self.data, self.t0 = data, time.time()
        self._draw()

    def _tick(self):
        if not visible(self):
            return 400
        self.phase += 1
        self._draw()

    def _draw(self, _=None):
        self.delete("all")
        w, h = self.winfo_width(), int(self["height"])
        card, dim, acc = THEME["card"], THEME["dim"], THEME["accent"]
        d = self.data
        p = ease_out((time.time() - self.t0) / 1.1) if d else 0.0
        col = threat_color(d["summary"]["threat"]) if d else dim
        self.create_polygon(chamfer(1, 1, w - 2, h - 2, 16), fill=card, outline=mix(card, col, 0.45))
        self.create_line(2, 18, 2, h - 18, fill=col, width=3)
        cx, cy, R = 66, h / 2, 36
        for k in range(36):
            a = 2 * math.pi * k / 36
            r0 = R + 8 if k % 3 else R + 6
            self.create_line(cx + r0 * math.cos(a), cy + r0 * math.sin(a),
                             cx + (R + 12) * math.cos(a), cy + (R + 12) * math.sin(a),
                             fill=mix(card, col, 0.35))
        self.create_oval(cx - R, cy - R, cx + R, cy + R, outline=mix(card, col, 0.18), width=8)
        risk = d["summary"]["risk"] if d else 0
        if d:
            self.create_arc(cx - R, cy - R, cx + R, cy + R, start=90, style="arc",
                            extent=-359.9 * risk / 100 * p, outline=col, width=8)
        self.create_text(cx, cy - 5, text=str(int(risk * p)) if d else "—", fill=THEME["white"],
                         font=(DISPLAY, 19, "bold"))
        self.create_text(cx, cy + 17, text="RISK", fill=dim, font=(MONO, 8, "bold"))
        x = 132
        pulse = (math.sin(self.phase * 0.14) + 1) / 2
        if not d:
            self.create_text(x, h / 2 - 14, anchor="w", text="BERSAGLIO NON IDENTIFICATO",
                             fill=mix(dim, acc, pulse * 0.6), font=(DISPLAY, 20, "bold"))
            self.create_text(x, h / 2 + 18, anchor="w", fill=dim, font=(MONO, 10),
                             text="inserisci un nome e avvia la scansione  ▸")
            return
        s = d["summary"]
        self.create_text(x, 22, anchor="w", fill=dim, font=(MONO, 9, "bold"),
                         text=f"VALUTAZIONE MINACCIA · CASO {d.get('case_id', '—')} · "
                              f"{d.get('classification', '')}")
        txt = f"MINACCIA {s['threat']}"
        gcol = mix(card, col, 0.2 + 0.25 * pulse)
        for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
            self.create_text(x + dx, h / 2 - 2 + dy, anchor="w", text=txt, fill=gcol,
                             font=(DISPLAY, 24, "bold"))
        self.create_text(x, h / 2 - 2, anchor="w", text=txt, fill=col, font=(DISPLAY, 24, "bold"))
        cx0, y = x, h - 22
        f = (MONO, 9, "bold")
        for label in (f"CONF {s['confidence']}%", f"CLEARANCE {s['clearance']}",
                      f"IDENTITÀ {len(d['identities'])}", f"TARGET {d['target'].upper()[:22]}"):
            tw = text_w(label, f) + 18
            self.create_polygon(chamfer(cx0, y - 9, cx0 + tw, y + 9, 5), fill=mix(card, acc, 0.1),
                                outline=mix(card, acc, 0.4))
            self.create_text(cx0 + tw / 2, y, text=label, fill=acc, font=f)
            cx0 += tw + 6
        if w > 860:
            sx1 = w - 28
            sx0, sy, seg = sx1 - 240, h / 2 - 2, 80
            levels = [("LOW", THEME["green"]), ("MEDIUM", THEME["amber"]), ("HIGH", THEME["red"])]
            self.create_text(sx1, 22, anchor="e", text="THREAT LEVEL", fill=dim,
                             font=(MONO, 8, "bold"))
            for i, (name, c2) in enumerate(levels):
                on = name == s["threat"]
                x0, x1 = sx0 + i * seg + 3, sx0 + (i + 1) * seg - 3
                self.create_polygon(x0 + 6, sy - 8, x1 + 6, sy - 8, x1, sy + 8, x0, sy + 8,
                                    fill=c2 if on else mix(card, c2, 0.16),
                                    outline=mix(card, c2, 0.6))
                self.create_text((x0 + x1) / 2 + 3, sy + 21, text=name,
                                 fill=c2 if on else dim, font=(MONO, 8, "bold"))
                if on:
                    mx = (x0 + x1) / 2 + 3
                    self.create_polygon(mx - 7, sy - 21, mx + 7, sy - 21, mx, sy - 12,
                                        fill=THEME["white"], outline="")


class RadarView(tk.Canvas):
    """Radar chart (Pillow) che si adatta allo spazio, con fascio rotante sopra."""

    def __init__(self, parent):
        super().__init__(parent, bg=bg_of(parent), highlightthickness=0)
        self.axes = None
        self.img = None
        self.size = 0
        self.ang = 0.0
        self._pending = None
        self.bind("<Configure>", self._schedule)
        Anim(self, 50, self._tick)

    def set_axes(self, axes):
        self.axes = axes
        self._render()

    def _schedule(self, _=None):
        if self._pending:
            self.after_cancel(self._pending)
        self._pending = self.after(120, self._render)

    def _render(self):
        self._pending = None
        if not PIL_OK:
            return
        w, h = self.winfo_width(), self.winfo_height()
        if w <= 1 or h <= 1:
            return
        self.size = max(140, min(w, h) - 4)
        axes = self.axes or [(k, 0) for k in ("ESPOS.", "RISK", "SOCIAL", "BREACH", "VISIB.", "CONF.")]
        self.img = ImageTk.PhotoImage(render_radar_chart(axes, self.size, THEME["accent"],
                                                         bg=self["bg"]))
        self.delete("img")
        self.create_image(w / 2, h / 2, image=self.img, tags="img")
        self.tag_lower("img")

    def _tick(self):
        if not visible(self) or not self.size:
            return 400
        self.delete("sweep")
        w, h = self.winfo_width(), self.winfo_height()
        cx, cy, R = w / 2, h / 2, self.size * 0.31
        for i in range(8):
            a = self.ang - i * 0.055
            self.create_line(cx, cy, cx + R * math.cos(a), cy + R * math.sin(a), tags="sweep",
                             fill=mix(self["bg"], THEME["accent"], 0.75 * (1 - i / 8)), width=2)
        self.ang = (self.ang + 0.06) % (2 * math.pi)


class TabView(tk.Frame):
    """Schede HUD con indicatore che scivola; le schede possono essere costruite
    in modo pigro (`builder`) alla prima apertura."""

    def __init__(self, parent, bg=None, font=None, height=38, on_change=None):
        self.bgc = bg or bg_of(parent)
        super().__init__(parent, bg=self.bgc)
        self.font = font or (UI, 10, "bold")
        self.on_change = on_change
        self.bar = tk.Canvas(self, height=height, bg=self.bgc, highlightthickness=0)
        self.bar.pack(fill="x")
        self.stack = tk.Frame(self, bg=self.bgc, highlightthickness=1,
                              highlightbackground=THEME["line"])
        self.stack.pack(fill="both", expand=True)
        self.tabs = []
        self.cur = self.hover = -1
        self.ind, self.ind_to = [0.0, 0.0], [0.0, 0.0]
        self.bar.bind("<Configure>", self._draw)
        self.bar.bind("<Motion>", self._motion)
        self.bar.bind("<Leave>", self._leave)
        self.bar.bind("<Button-1>", self._click)
        Anim(self.bar, 16, self._tick)

    def add(self, label, builder=None, bg=None):
        f = tk.Frame(self.stack, bg=bg or THEME["panel"])
        self.tabs.append({"label": label, "frame": f, "builder": builder, "built": builder is None})
        self._layout()
        if self.cur < 0:
            self.select(0)
        else:
            self._draw()
        return f

    def _layout(self):
        x = 6
        for t in self.tabs:
            tw = text_w(t["label"], self.font) + 34
            t["x0"], t["x1"] = x, x + tw
            x += tw + 4

    def select(self, i, user=False):
        if not (0 <= i < len(self.tabs)) or i == self.cur:
            return
        if self.cur >= 0:
            self.tabs[self.cur]["frame"].pack_forget()
        self.cur = i
        t = self.tabs[i]
        t["frame"].pack(fill="both", expand=True)
        if not t["built"]:
            t["built"] = True
            t["builder"](t["frame"])
        self.ind_to = [t["x0"], t["x1"]]
        if self.ind == [0.0, 0.0]:
            self.ind = list(self.ind_to)
        if user:
            sfx("click")
        self._draw()
        if self.on_change:
            self.on_change(i)

    def _hit(self, x):
        for i, t in enumerate(self.tabs):
            if t["x0"] <= x <= t["x1"]:
                return i
        return -1

    def _motion(self, e):
        h = self._hit(e.x)
        if h != self.hover:
            self.hover = h
            self.bar.config(cursor="hand2" if h >= 0 else "")
            self._draw()

    def _leave(self, _):
        self.hover = -1
        self._draw()

    def _click(self, e):
        i = self._hit(e.x)
        if i >= 0:
            self.select(i, user=True)

    def _tick(self):
        if not visible(self.bar):
            return 300
        if any(abs(a - b) > 0.5 for a, b in zip(self.ind, self.ind_to)):
            self.ind = [a + (b - a) * 0.28 for a, b in zip(self.ind, self.ind_to)]
            self._draw()
            return 16
        if self.ind != self.ind_to:
            self.ind = list(self.ind_to)
            self._draw()
        return 120

    def _draw(self, _=None):
        c = self.bar
        c.delete("all")
        w, h = c.winfo_width(), int(c["height"])
        acc, bgc = THEME["accent"], self.bgc
        c.create_line(0, h - 1, w, h - 1, fill=THEME["line"])
        for i, t in enumerate(self.tabs):
            x0, x1 = t["x0"], t["x1"]
            if i == self.cur:
                c.create_polygon(chamfer(x0, 4, x1, h - 1, 9, "tl tr"), fill=mix(bgc, acc, 0.13),
                                 outline=mix(bgc, acc, 0.4))
                col = acc
            elif i == self.hover:
                c.create_polygon(chamfer(x0, 4, x1, h - 1, 9, "tl tr"), fill=mix(bgc, acc, 0.06),
                                 outline="")
                col = THEME["white"]
            else:
                col = THEME["dim"]
            c.create_text((x0 + x1) / 2, h / 2 + 2, text=t["label"], fill=col, font=self.font)
        a, b = self.ind
        if b > a:
            c.create_line(a + 8, h - 2, b - 8, h - 2, fill=acc, width=3)
            c.create_rectangle(b - 8, h - 5, b - 4, h - 1, fill=THEME["white"], outline="")


class ToggleSwitch(tk.Canvas):
    """Interruttore animato collegato a una BooleanVar."""

    def __init__(self, parent, text, variable, color=None):
        font = (UI, 10)
        super().__init__(parent, width=64 + text_w(text, font), height=30, bg=bg_of(parent),
                         highlightthickness=0, cursor="hand2")
        self.var, self.text, self.font = variable, text, font
        self.color = color or THEME["accent"]
        self.pos = 1.0 if variable.get() else 0.0
        self.bind("<Button-1>", self._toggle)
        self.bind("<Configure>", self._draw)
        Anim(self, 16, self._tick)

    def _toggle(self, _):
        self.var.set(not self.var.get())
        sfx("click")

    def _tick(self):
        target = 1.0 if self.var.get() else 0.0
        if abs(self.pos - target) > 0.02:
            self.pos += (target - self.pos) * 0.35
            self._draw()
            return 16
        if self.pos != target:
            self.pos = target
            self._draw()
        return 120

    def _draw(self, _=None):
        self.delete("all")
        on, bgc = self.pos, self["bg"]
        col = mix(THEME["line2"], self.color, on)
        x0, y0, x1, y1 = 3, 7, 47, 23
        self.create_polygon(chamfer(x0, y0, x1, y1, 5, "tl tr br bl"),
                            fill=mix(bgc, col, 0.18 + 0.22 * on), outline=col)
        kx = x0 + 3 + (x1 - x0 - 24) * on
        self.create_polygon(chamfer(kx, y0 + 3, kx + 18, y1 - 3, 3, "tl tr br bl"),
                            fill=mix(THEME["dim"], "#ffffff", on), outline="")
        self.create_text(x1 + 12, 15, anchor="w", text=self.text, font=self.font,
                         fill=THEME["text"] if on > 0.5 else THEME["dim"])


class Segmented(tk.Canvas):
    """Selettore a segmenti collegato a una StringVar."""

    def __init__(self, parent, options, variable, width=270, height=30):
        super().__init__(parent, width=width, height=height, bg=bg_of(parent),
                         highlightthickness=0, cursor="hand2")
        self.options, self.var = options, variable
        self._last = None
        self.bind("<Button-1>", self._click)
        self.bind("<Configure>", self._draw)
        Anim(self, 150, self._tick)

    def _click(self, e):
        n = len(self.options)
        i = int(e.x / max(1, self.winfo_width()) * n)
        self.var.set(self.options[max(0, min(n - 1, i))][1])
        sfx("click")
        self._draw()

    def _tick(self):
        if self.var.get() != self._last:
            self._draw()

    def _draw(self, _=None):
        self.delete("all")
        self._last = self.var.get()
        w, h, n = self.winfo_width(), int(self["height"]), len(self.options)
        sw, bgc, acc = w / n, self["bg"], THEME["accent"]
        for i, (lab, val) in enumerate(self.options):
            on = val == self._last
            x0, x1 = i * sw + 2, (i + 1) * sw - 2
            self.create_polygon(x0 + 6, 2, x1, 2, x1 - 6, h - 2, x0, h - 2,
                                fill=acc if on else mix(bgc, acc, 0.06),
                                outline=acc if on else THEME["line2"])
            self.create_text((x0 + x1) / 2, h / 2, text=lab, font=(UI, 9, "bold"),
                             fill="#000000" if on else THEME["dim"])


class NeonSlider(tk.Canvas):
    """Cursore orizzontale collegato a una DoubleVar."""

    def __init__(self, parent, variable, from_, to, resolution=0.5, fmt="{:.1f} s",
                 width=300, height=34):
        super().__init__(parent, width=width, height=height, bg=bg_of(parent),
                         highlightthickness=0, cursor="hand2")
        self.var, self.lo, self.hi, self.res, self.fmt = variable, from_, to, resolution, fmt
        self.bind("<Button-1>", self._set)
        self.bind("<B1-Motion>", self._set)
        self.bind("<Configure>", self._draw)

    def _track(self):
        return 10, self.winfo_width() - 70

    def _set(self, e):
        x0, x1 = self._track()
        t = max(0.0, min(1.0, (e.x - x0) / max(1, x1 - x0)))
        v = self.lo + t * (self.hi - self.lo)
        self.var.set(round(round(v / self.res) * self.res, 2))
        self._draw()

    def _draw(self, _=None):
        self.delete("all")
        x0, x1 = self._track()
        h, acc = int(self["height"]), THEME["accent"]
        y = h / 2
        t = (self.var.get() - self.lo) / max(1e-9, self.hi - self.lo)
        kx = x0 + t * (x1 - x0)
        self.create_line(x0, y, x1, y, fill=THEME["line2"], width=4)
        self.create_line(x0, y, kx, y, fill=acc, width=4)
        steps = int(round((self.hi - self.lo) / self.res))
        for i in range(steps + 1):
            tx = x0 + (x1 - x0) * i / max(1, steps)
            self.create_line(tx, y + 7, tx, y + (11 if i % 2 == 0 else 9), fill=THEME["dim"])
        self.create_polygon(hexagon(kx, y, 9, math.pi / 6), fill=THEME["panel2"], outline=acc,
                            width=2)
        self.create_text(x1 + 14, y, anchor="w", text=self.fmt.format(self.var.get()),
                         fill=acc, font=(MONO, 11, "bold"))


class Swatches(tk.Canvas):
    """Scelta colore: esagoni luminosi, quello attivo è cerchiato."""

    def __init__(self, parent, options, variable):
        super().__init__(parent, width=len(options) * 46 + 4, height=58, bg=bg_of(parent),
                         highlightthickness=0, cursor="hand2")
        self.options, self.var = options, variable
        self.bind("<Button-1>", self._click)
        self.bind("<Configure>", self._draw)

    def _click(self, e):
        i = int(e.x // 46)
        if 0 <= i < len(self.options):
            self.var.set(self.options[i][1])
            sfx("click")
            self._draw()

    def _draw(self, _=None):
        self.delete("all")
        for i, (name, col) in enumerate(self.options):
            cx, on = 25 + i * 46, self.var.get().lower() == col.lower()
            if on:
                self.create_polygon(hexagon(cx, 21, 17, math.pi / 6), fill="", outline="#ffffff",
                                    width=2)
            self.create_polygon(hexagon(cx, 21, 12, math.pi / 6), fill=col, outline="")
            self.create_text(cx, 49, text=name, font=(UI, 8, "bold"),
                             fill=col if on else THEME["dim"])


FEED_LINES = [
    "uplink ORION-SAT 3 · segnale stabile", "nodo relay CH-07 · handshake OK",
    "cifratura quantistica (SIM) · attiva", "sincronizzazione orologio atomico · ±0.2 ns",
    "proxy chain · 7 salti · latenza 41 ms", "motore neurale face-match · pronto",
    "archivio cifrato · integrità 100%", "SIMULAZIONE — nessun dato reale",
    f"operator {CREATOR} · sessione autenticata", "telemetria · 0 anomalie",
]


class StatusBar(tk.Frame):
    """Barra inferiore: stato con LED pulsante, notiziario scorrevole, scorciatoie."""

    def __init__(self, parent):
        bgc = THEME["panel"]
        super().__init__(parent, bg=bgc)
        tk.Frame(self, bg=THEME["line"], height=1).pack(fill="x", side="top")
        self.left = tk.Canvas(self, width=600, height=27, bg=bgc, highlightthickness=0)
        self.left.pack(side="left")
        tk.Label(self, text="ESC stop · CTRL+G galleria · CTRL+P slideshow · CTRL+E esporta · "
                            "F11 schermo intero", font=(MONO, 8), bg=bgc,
                 fg=THEME["dim"]).pack(side="right", padx=10)
        self.mid = tk.Canvas(self, height=27, bg=bgc, highlightthickness=0)
        self.mid.pack(side="left", fill="x", expand=True)
        self.status, self.color = "SISTEMA OPERATIVO — in attesa del bersaglio", THEME["green"]
        self.feed = list(FEED_LINES)
        self.phase = 0
        self.left.bind("<Configure>", lambda e: self._draw_left())
        Anim(self.mid, 33, self._tick)

    def set_status(self, text, color=None):
        self.status, self.color = text, color or THEME["green"]
        self._draw_left()

    def push_feed(self, line):
        self.feed.insert(0, line)
        del self.feed[24:]

    def _draw_left(self):
        c = self.left
        c.delete("all")
        c.create_oval(10, 9, 19, 18, fill=self.color, outline="", tags="led")
        c.create_text(28, 14, anchor="w", text=self.status[:86], fill=self.color,
                      font=(MONO, 9, "bold"))
        c.create_line(598, 4, 598, 24, fill=THEME["line"])

    def _tick(self):
        self.phase += 1
        p = (math.sin(self.phase * 0.12) + 1) / 2
        self.left.itemconfig("led", fill=mix(THEME["panel"], self.color, 0.35 + 0.65 * p))
        if not visible(self.mid):
            return 300
        c = self.mid
        items = c.find_withtag("mq")
        if not items:
            line = "     ◆     ".join(self.feed)
            c.create_text(c.winfo_width() + 10, 14, anchor="w", text=line, tags="mq",
                          fill=THEME["dim"], font=(MONO, 9))
            return 33
        c.move("mq", -1.6, 0)
        bb = c.bbox("mq")
        if bb and bb[2] < 0:
            c.delete("mq")


class HeaderBar(tk.Canvas):
    """Intestazione animata: logo, equalizzatore, indicatori di sistema, orologio."""
    H = 84

    def __init__(self, parent, on_settings):
        super().__init__(parent, height=self.H, bg=THEME["bg"], highlightthickness=0)
        self.logo = ImageTk.PhotoImage(render_logo(66, THEME["accent"])) if PIL_OK else None
        self.bg_img = None
        self.geo = {}
        self.frame = 0
        self._pending = None
        self.meters = [["NODE", 0.4, 0.6], ["LINK", 0.7, 0.8], ["CRYPT", 0.9, 0.95],
                       ["AI-CORE", 0.3, 0.5]]
        self.eq = [random.random() for _ in range(22)]
        self.btn = NeonButton(self, "⚙  IMPOSTAZIONI", on_settings, width=156, height=34,
                              sound="open")
        self.bind("<Configure>", self._schedule)
        Anim(self, 90, self._tick)

    def _schedule(self, _=None):
        if self._pending:
            self.after_cancel(self._pending)
        self._pending = self.after(60, self._layout)

    def _layout(self):
        self._pending = None
        w, h = self.winfo_width(), self.H
        if w <= 1:
            return
        acc, bgc = THEME["accent"], THEME["bg"]
        self.delete("all")
        self.geo = {}
        if PIL_OK:
            self.bg_img = ImageTk.PhotoImage(render_backdrop(w, h, acc, center=(0.22, 0.0),
                                                             hexr=13))
            self.create_image(0, 0, image=self.bg_img, anchor="nw")
        self.create_line(0, h - 1, w, h - 1, fill=mix(bgc, acc, 0.5))
        self.create_line(0, h - 3, w * 0.3, h - 3, fill=acc, width=2)
        self.create_line(0, h - 3, 0, h - 3, fill="#ffffff", width=2, tags="scan")
        x = 14
        if self.logo:
            self.create_image(x, h / 2, image=self.logo, anchor="w")
            x += self.logo.width() + 30
        if w > 1250:                                   # equalizzatore "SIGNAL"
            self.create_text(x, 16, anchor="w", text="SIGNAL", fill=THEME["dim"],
                             font=(MONO, 8, "bold"))
            for i in range(len(self.eq)):
                self.create_rectangle(0, 0, 0, 0, outline="", tags=f"eq{i}",
                                      fill=mix(THEME["accent2"], acc, i / len(self.eq)))
            self.geo["eq"] = (x, 26, h - 14)
            x += len(self.eq) * 6 + 30
        if w > 1460:                                   # indicatori di sistema
            for i, (name, v, _) in enumerate(self.meters):
                mx, my = x + (i % 2) * 150, 22 + (i // 2) * 30
                self.create_text(mx, my, anchor="w", text=name, fill=THEME["dim"],
                                 font=(MONO, 8, "bold"))
                self.create_rectangle(mx, my + 8, mx + 110, my + 12, fill=THEME["line"], outline="")
                self.create_rectangle(mx, my + 8, mx + 110 * v, my + 12, fill=acc, outline="",
                                      tags=f"m{i}")
                self.create_text(mx + 110, my, anchor="e", text="", fill=acc,
                                 font=(MONO, 8, "bold"), tags=f"mv{i}")
                self.geo[f"m{i}"] = (mx, my)
        self.create_window(w - 16, h / 2, window=self.btn, anchor="e")
        rx = w - 190
        self.create_text(rx, h / 2 - 9, anchor="e", text="", fill=THEME["white"],
                         font=(MONO, 19, "bold"), tags="clock")
        self.create_text(rx, h / 2 + 16, anchor="e", text="", fill=THEME["magenta"],
                         font=(MONO, 9, "bold"), tags="date")
        self.create_oval(0, 0, 0, 0, fill=THEME["green"], outline="", tags="up")
        self.geo["up"] = rx
        self._tick()

    def _tick(self):
        if not self.geo or not visible(self):
            return 400
        self.frame += 1
        w, h = self.winfo_width(), self.H
        now = datetime.now()
        self.itemconfig("clock", text=now.strftime("%H:%M:%S"))
        self.itemconfig("date", text=now.strftime("%Y-%m-%d") + f"  ·  OPERATOR {CREATOR}")
        bb = self.bbox("clock")
        if bb:
            p = (math.sin(self.frame * 0.25) + 1) / 2
            self.coords("up", bb[0] - 16, h / 2 - 13, bb[0] - 8, h / 2 - 5)
            self.itemconfig("up", fill=mix(THEME["bg"], THEME["green"], 0.3 + 0.7 * p))
        sx = (self.frame * 14) % (w + 300) - 150
        self.coords("scan", sx, h - 3, sx + 90, h - 3)
        if "eq" in self.geo:
            x0, top, bot = self.geo["eq"]
            for i in range(len(self.eq)):
                self.eq[i] += (random.random() - self.eq[i]) * 0.35
                bh = (bot - top) * (0.15 + 0.85 * self.eq[i])
                self.coords(f"eq{i}", x0 + i * 6, bot - bh, x0 + i * 6 + 4, bot)
        for i, m in enumerate(self.meters):
            if f"m{i}" not in self.geo:
                break
            if random.random() < 0.03:
                m[2] = random.uniform(0.25, 0.98)
            m[1] += (m[2] - m[1]) * 0.08
            mx, my = self.geo[f"m{i}"]
            self.coords(f"m{i}", mx, my + 8, mx + 110 * m[1], my + 12)
            self.itemconfig(f"mv{i}", text=f"{int(m[1] * 100)}%")


class Toast:
    """Notifica animata che scivola dal bordo destro (sostituisce i vecchi popup)."""
    _active = []

    def __init__(self, root, text, color=None, icon="◆", ms=2600):
        Toast._active = [t for t in Toast._active if t.alive()]
        color = color or THEME["accent"]
        font = (UI, 10, "bold")
        tw = min(460, text_w(text, font))
        self.W, self.H, self.ms = tw + 66, 44, ms
        cv = self.cv = tk.Canvas(root, width=self.W, height=self.H, bg=THEME["bg"],
                                 highlightthickness=0)
        cv.create_polygon(chamfer(1, 1, self.W - 2, self.H - 2, 10), fill=THEME["panel2"],
                          outline=color)
        cv.create_rectangle(1, 10, 4, self.H - 10, fill=color, outline="")
        cv.create_text(22, self.H / 2, text=icon, fill=color, font=(UI, 13, "bold"))
        cv.create_text(40, self.H / 2, text=text, anchor="w", fill=THEME["text"], font=font)
        cv.create_line(12, self.H - 5, self.W - 12, self.H - 5, tags="t",
                       fill=mix(THEME["panel2"], color, 0.6))
        cv.bind("<Button-1>", lambda e: self.close())
        Toast._active.append(self)
        self.t0 = time.time()
        self.x = self.W + 20
        self._place()
        Anim(cv, 16, self._tick)
        sfx("toast")

    def alive(self):
        try:
            return bool(self.cv.winfo_exists())
        except tk.TclError:
            return False

    def _place(self):
        idx = Toast._active.index(self) if self in Toast._active else 0
        self.cv.place(relx=1.0, rely=1.0, x=-16 + self.x, y=-40 - idx * (self.H + 8), anchor="se")

    def _tick(self):
        el = (time.time() - self.t0) * 1000
        if el < 220:
            self.x = (self.W + 20) * (1 - ease_out(el / 220))
        elif el < self.ms:
            self.x = 0
        elif el < self.ms + 220:
            self.x = (self.W + 20) * ease_out((el - self.ms) / 220)
        else:
            self.close()
            return False
        self.cv.coords("t", 12, self.H - 5, 12 + (self.W - 24) * (1 - min(1.0, el / self.ms)),
                       self.H - 5)
        self._place()

    def close(self):
        if self in Toast._active:
            Toast._active.remove(self)
        try:
            self.cv.destroy()
        except tk.TclError:
            pass
        for t in Toast._active:
            if t.alive():
                t._place()


# --- contenitori scorrevoli / griglie adattive / console -------------------
def _wheel(e):
    """Scorre il contenitore sotto il puntatore (Windows/macOS/Linux)."""
    try:
        w = e.widget.winfo_containing(e.x_root, e.y_root)
    except (tk.TclError, AttributeError):
        return
    while w is not None and not getattr(w, "orion_scroll", False):
        w = w.master
    if w is None:
        return
    up = e.num == 4 or getattr(e, "delta", 0) > 0
    w.yview_scroll(-1 if up else 1, "units")


def enable_wheel(widget):
    """Un solo gestore rotella per finestra (si chiude con lei, niente bind_all)."""
    top = widget.winfo_toplevel()
    if not getattr(top, "orion_wheel", False):
        top.orion_wheel = True
        for ev in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            top.bind(ev, _wheel, add="+")


def make_scroll(parent, bg=None):
    """Area scorrevole verticale; restituisce il frame interno."""
    bg = bg or bg_of(parent)
    cont = tk.Frame(parent, bg=bg)
    cont.pack(fill="both", expand=True)
    canvas = tk.Canvas(cont, bg=bg, highlightthickness=0)
    sb = ttk.Scrollbar(cont, orient="vertical", command=canvas.yview,
                       style="Orion.Vertical.TScrollbar")
    inner = tk.Frame(canvas, bg=bg)
    inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    wid = canvas.create_window((0, 0), window=inner, anchor="nw")
    canvas.bind("<Configure>", lambda e: canvas.itemconfig(wid, width=e.width))
    canvas.configure(yscrollcommand=sb.set)
    canvas.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")
    canvas.orion_scroll = True
    enable_wheel(parent)
    return inner


class ResponsiveGrid:
    """Dispone le card in colonne che si adattano alla larghezza disponibile."""

    def __init__(self, frame, cell_w, pad=8):
        self.frame, self.cell_w, self.pad = frame, cell_w, pad
        self.items, self.cols = [], 0
        frame.bind("<Configure>", lambda e: self._regrid(e.width), add="+")

    def set(self, widgets):
        self.items, self.cols = widgets, 0
        self._regrid(self.frame.winfo_width())

    def _regrid(self, width):
        cols = max(1, int(width // (self.cell_w + 2 * self.pad))) if width > 1 else 3
        if cols == self.cols:
            return
        for c in range(max(self.cols, cols) + 1):
            self.frame.columnconfigure(c, weight=1 if c < cols else 0)
        self.cols = cols
        for i, w in enumerate(self.items):
            w.grid(row=i // cols, column=i % cols, padx=self.pad, pady=self.pad, sticky="n")


def make_console(parent, size=10, height=None):
    """Console testuale HUD (Text + scrollbar a tema). Restituisce (contenitore, text)."""
    bg2, acc = THEME["bg2"], THEME["accent"]
    wrap = tk.Frame(parent, bg=bg2, highlightthickness=1, highlightbackground=THEME["line"])
    txt = tk.Text(wrap, bg=bg2, fg=THEME["text"], font=(MONO, size), relief="flat", bd=0,
                  padx=14, pady=10, wrap="word", highlightthickness=0, cursor="arrow",
                  insertbackground=acc, selectbackground=mix(bg2, acc, 0.35))
    if height:
        txt.config(height=height)
    sb = ttk.Scrollbar(wrap, orient="vertical", command=txt.yview,
                       style="Orion.Vertical.TScrollbar")
    txt.config(yscrollcommand=sb.set)
    sb.pack(side="right", fill="y")
    txt.pack(side="left", fill="both", expand=True)
    for tag, col, fnt in [("h", acc, (DISPLAY, 12, "bold")), ("h2", THEME["magenta"], (DISPLAY, 11, "bold")),
                          ("k", THEME["dim"], (MONO, size)), ("v", THEME["white"], (MONO, size, "bold")),
                          ("ok", THEME["green"], (MONO, size)), ("warn", THEME["amber"], (MONO, size)),
                          ("bad", THEME["red"], (MONO, size)), ("bar", acc, (MONO, size)),
                          ("track", THEME["line2"], (MONO, size)), ("sep", THEME["line2"], (MONO, size)),
                          ("cur", acc, (MONO, size, "bold"))]:
        txt.tag_config(tag, foreground=col, font=fnt)
    txt.config(state="disabled")
    return wrap, txt


def tbar(value, n=24):
    """Barra testuale (pieni, vuoti) per le console."""
    f = int(round(max(0, min(100, value)) / 100 * n))
    return "█" * f, "░" * (n - f)


# ===========================================================================
#  SCENA OLOGRAFICA  —  usata dallo splash d'avvio e dall'intro della galleria
# ===========================================================================
class HoloScene:
    """Pioggia di dati, anelli rotanti, titolo che si 'decritta', log di sistema,
    barra a segmenti e chiusura a otturatore. Elementi persistenti (niente
    delete('all') a ogni frame) per restare fluida anche a schermo intero."""
    FPS_MS = 33

    def __init__(self, canvas, phases, log, on_done=None, accent=None, subtitle="",
                 reticle=False, footer="", fx=True):
        self.c, self.phases, self.log, self.on_done = canvas, phases, log, on_done
        self.accent = accent or THEME["accent"]
        self.subtitle, self.reticle, self.footer, self.fx = subtitle, reticle, footer, fx
        self.frame = 0
        self.total = sum(p[3] for p in phases) + 8
        self.size = None
        self.shutter = -1
        self.rng = random.Random()
        self.anim = Anim(canvas, self.FPS_MS, self._tick)

    def stop(self):
        self.anim.stop()

    def _rain(self, n):
        return "\n".join(self.rng.choice(DATA_GLYPHS) for _ in range(n))

    def _setup(self, w, h):
        c, acc, bgc = self.c, self.accent, THEME["bg"]
        c.delete("all")
        self.size = (w, h)
        if PIL_OK:
            self.bg = ImageTk.PhotoImage(render_backdrop(w, h, acc, center=(0.5, 0.42), hexr=26))
            c.create_image(0, 0, image=self.bg, anchor="nw")
        else:
            c.create_rectangle(0, 0, w, h, fill=bgc, outline="")
        self.cols = []
        if self.fx:
            n = min(70, max(10, w // 30))
            for i in range(n):
                x, ln, y = (i + 0.5) * w / n, self.rng.randint(8, 18), self.rng.uniform(-h, h)
                tail = c.create_text(x, y, text=self._rain(ln), anchor="s", font=(MONO, 11),
                                     fill=mix(bgc, acc, 0.26))
                head = c.create_text(x, y, text=self.rng.choice(DATA_GLYPHS), anchor="n",
                                     font=(MONO, 11, "bold"), fill=mix(acc, "#ffffff", 0.6))
                self.cols.append([tail, head, y, self.rng.uniform(5, 14), ln, x])
        cx, cy, R = w / 2, h * 0.42, min(w, h) * 0.24
        self.cx, self.cy, self.R = cx, cy, R
        for k in range(120):
            a = 2 * math.pi * k / 120
            r0 = R * (1.08 if k % 10 == 0 else 1.12)
            c.create_line(cx + r0 * math.cos(a), cy + r0 * math.sin(a),
                          cx + R * 1.16 * math.cos(a), cy + R * 1.16 * math.sin(a),
                          fill=mix(bgc, acc, 0.75 if k % 10 == 0 else 0.3))
        specs = [(R, 70, 4, 1.6, acc, 0), (R * 0.9, 210, 1, -0.9, THEME["accent2"], 40),
                 (R * 1.26, 34, 3, 0.6, THEME["magenta"], 0), (R * 1.26, 34, 3, 0.6, THEME["magenta"], 180),
                 (R * 0.76, 100, 2, -2.2, acc, 90), (R * 1.4, 300, 1, 0.25, mix(bgc, acc, 0.4), 0)]
        self.rings = []
        for r, ext, wd, spd, col, st in specs:
            it = c.create_arc(cx - r, cy - r, cx + r, cy + r, start=st, extent=ext, style="arc",
                              outline=col, width=wd)
            self.rings.append([it, st, spd])
        self.hexi = c.create_polygon(hexagon(cx, cy, R * 0.62, math.pi / 6), fill="",
                                     outline=mix(bgc, acc, 0.5), width=2)
        self.sweep = [c.create_line(cx, cy, cx, cy, width=2, fill=mix(bgc, acc, 0.9 - i * 0.13))
                      for i in range(6)]
        self.t_red = c.create_text(cx, cy, text="", fill=THEME["red"], state="hidden")
        self.t_cyan = c.create_text(cx, cy, text="", fill=acc, state="hidden")
        self.t_main = c.create_text(cx, cy, text="", fill=THEME["white"])
        if self.subtitle:
            sub = "  ".join(self.subtitle)
            c.create_text(cx, cy + R * 1.4 + 34, text=sub, fill=acc, font=(DISPLAY, 18, "bold"))
        self.log_items = []
        for i in range(len(self.log)):
            self.log_items.append(c.create_text(40, h * 0.72 + i * 18, anchor="w", text="",
                                                font=(MONO, 10), fill=acc))
        n = 40
        self.pw, self.px, self.py = w * 0.42, w * 0.29, h * 0.9
        sw = (self.pw - 3 * (n - 1)) / n
        self.segs = []
        for i in range(n):
            x0 = self.px + i * (sw + 3)
            self.segs.append(c.create_polygon(x0 + 3, self.py, x0 + sw + 3, self.py, x0 + sw,
                                              self.py + 10, x0, self.py + 10,
                                              fill=mix(bgc, acc, 0.1), outline=""))
        self.pct = c.create_text(self.px + self.pw + 16, self.py + 5, anchor="w", text="0%",
                                 fill=acc, font=(MONO, 11, "bold"))
        brackets(c, 18, 18, w - 18, h - 18, 40, acc, 2)
        c.create_text(28, 32, anchor="w", text=f"ORION//INTEL · {CREATOR}", fill=acc,
                      font=(MONO, 10, "bold"))
        c.create_text(w - 28, 32, anchor="e", fill=THEME["amber"], font=(MONO, 9, "bold"),
                      text="◦ SIMULAZIONE / GIOCO ◦    SPAZIO = salta")
        if self.footer:
            c.create_text(w / 2, h - 14, anchor="s", text=self.footer, fill=THEME["dim"],
                          font=(MONO, 9))
        self.sh = [c.create_rectangle(0, 0, w, 0, fill="#000000", outline=""),
                   c.create_rectangle(0, h, w, h, fill="#000000", outline=""),
                   c.create_line(0, 0, w, 0, fill=acc, width=2),
                   c.create_line(0, h, w, h, fill=acc, width=2)]

    def _phase(self):
        f, acc = self.frame - 4, 0
        for p in self.phases:
            if f < acc + p[3]:
                return p, max(0, f - acc)
            acc += p[3]
        return self.phases[-1], self.phases[-1][3]

    def _tick(self):
        c = self.c
        w, h = c.winfo_width(), c.winfo_height()
        if w <= 1 or h <= 1:
            w, h = c.winfo_screenwidth(), c.winfo_screenheight()
        if self.size != (w, h):
            self._setup(w, h)
        self.frame += 1
        fr, acc, bgc = self.frame, self.accent, THEME["bg"]
        cx, cy, R = self.cx, self.cy, self.R
        for col in self.cols:
            col[2] += col[3]
            if col[2] - col[4] * 16 > h:
                col[2] = self.rng.uniform(-h * 0.4, 0)
                c.itemconfig(col[0], text=self._rain(col[4]))
            c.coords(col[0], col[5], col[2])
            c.coords(col[1], col[5], col[2])
            if fr % 3 == 0:
                c.itemconfig(col[1], text=self.rng.choice(DATA_GLYPHS))
        for r in self.rings:
            r[1] = (r[1] + r[2] * 2) % 360
            c.itemconfig(r[0], start=r[1])
        a = fr * 0.09
        for i, it in enumerate(self.sweep):
            aa = a - i * 0.05
            c.coords(it, cx, cy, cx + R * 0.95 * math.cos(aa), cy + R * 0.95 * math.sin(aa))
        p = (math.sin(fr * 0.15) + 1) / 2
        c.itemconfig(self.hexi, outline=mix(bgc, acc, 0.25 + 0.5 * p))

        (text, size, color, dur), local = self._phase()
        reveal = min(1.0, local / max(1, dur * 0.55))
        k = int(len(text) * reveal)
        shown = text if reveal >= 1 else text[:k] + "".join(
            ch if ch == " " else self.rng.choice(DATA_GLYPHS) for ch in text[k:])
        font = (DISPLAY, size, "bold")
        c.itemconfig(self.t_main, text=shown, font=font, fill=color)
        glitch = self.fx and (fr // 3) % 6 == 0
        for it, dx in ((self.t_red, 4), (self.t_cyan, -4)):
            c.itemconfig(it, text=shown, font=font, state="normal" if glitch else "hidden")
            c.coords(it, cx + dx, cy)
        if self.reticle:
            s = 1 - ease_out(fr / max(1, self.total * 0.45))
            half = R * (0.95 + 1.3 * s)
            c.delete("ret")
            brackets(c, cx - half * 1.6, cy - half, cx + half * 1.6, cy + half, 26,
                     THEME["green"] if s <= 0.01 else acc, 3, tags="ret")
        for i, it in enumerate(self.log_items):
            n = int((fr - 6 - i * 7) * 3)
            if n > 0:
                line = self.log[i][:n]
                c.itemconfig(it, text=line, fill=THEME["green"] if ("OK" in line or "GRANTED" in line)
                             else acc)
        prog = min(1.0, fr / self.total)
        filled = prog * len(self.segs)
        for i, it in enumerate(self.segs):
            if i < filled:
                col = mix(THEME["accent2"], acc, i / len(self.segs))
                if i == int(filled):
                    col = "#ffffff"
            else:
                col = mix(bgc, acc, 0.1)
            c.itemconfig(it, fill=col)
        c.itemconfig(self.pct, text=f"{int(prog * 100)}%")
        if fr >= self.total:
            self.shutter += 1
            cov = (h / 2) * self.shutter / 8
            c.coords(self.sh[0], 0, 0, w, cov)
            c.coords(self.sh[1], 0, h - cov, w, h)
            c.coords(self.sh[2], 0, cov, w, cov)
            c.coords(self.sh[3], 0, h - cov, w, h - cov)
            for it in self.sh:
                c.tag_raise(it)
            if self.shutter >= 8:
                if callable(self.on_done):
                    self.on_done()
                return False


class CinematicIntro:
    """Intro della galleria: aggancio del bersaglio in stile olografico."""

    def __init__(self, canvas, target, on_done, accent=None, scale=1.0, fx=True):
        acc = accent or THEME["accent"]
        t = (target or "UNKNOWN").upper()
        base = [("◈ O R I O N", 46, acc, 18), (CREATOR_TAG.upper(), 22, THEME["magenta"], 14),
                (f"TARGET ▸ {t}", 32, THEME["white"], 22), ("◎ BIOMETRICS MATCHED", 26, THEME["green"], 18),
                ("◉ ACCESS GRANTED", 42, THEME["green"], 20)]
        phases = [(a, b, c, max(6, int(d * scale))) for (a, b, c, d) in base]
        log = ["conn secure://orion.grid  [OK]", f"operator: {CREATOR.lower()} ...... [OK]",
               "biometric vector match ..... [OK]", "decrypting media cache ..... [OK]",
               "access token elevated ...... [OK]"]
        self.scene = HoloScene(canvas, phases, log, on_done, acc, reticle=True, fx=fx,
                               footer=f"◦ SIMULAZIONE — dati casuali, nessun dato reale · by {CREATOR} ◦")

    def stop(self):
        self.scene.stop()


# ===========================================================================
#  SPLASH D'AVVIO  —  video dell'utente (OpenCV) oppure scena olografica
# ===========================================================================
def _go_fullscreen(win):
    """Schermo intero, con geometria di riserva se il window manager lo ignora."""
    win.geometry(f"{win.winfo_screenwidth()}x{win.winfo_screenheight()}+0+0")
    try:
        win.attributes("-fullscreen", True)
    except tk.TclError:
        pass


def _fullscreen_toplevel(root, bg="#000000"):
    win = tk.Toplevel(root)
    win.configure(bg=bg)
    win.attributes("-topmost", True)
    _go_fullscreen(win)
    win.after(40, win.lift)
    return win


class BootSplash:
    """Splash d'avvio: emblema ORION olografico + boot-log."""

    def __init__(self, root, on_done=None, accent=None, fx=True):
        self.on_done = on_done
        self.finished = False
        acc = accent or THEME["accent"]
        self.win = _fullscreen_toplevel(root)
        self.cv = tk.Canvas(self.win, bg="#000000", highlightthickness=0)
        self.cv.pack(fill="both", expand=True)
        for ev in ("<Button-1>", "<Escape>", "<space>", "<Return>"):
            self.win.bind(ev, lambda e: self.finish())
        self.win.focus_set()
        sfx("boot")
        log = [f"ORION INTELLIGENCE TERMINAL  v{APP_VERSION}",
               "> establishing secure enclave ......... [OK]",
               f"> loading operator profile: {CREATOR} . [OK]",
               "> mounting encrypted vault ............ [OK]",
               "> spoofing egress node  CH-07 ......... [OK]",
               "> neural face-match engine ............ [OK]",
               "> ACCESS GRANTED — welcome, operator"]
        phases = [("◈ ORION", 66, THEME["white"], 34), ("SECURE TERMINAL", 40, acc, 26),
                  ("◉ ACCESS GRANTED", 44, THEME["green"], 26)]
        self.scene = HoloScene(self.cv, phases, log, self.finish, acc, fx=fx,
                               subtitle=f"CREATED BY {CREATOR}",
                               footer="ORION INTELLIGENCE // CLASSIFIED   ·   click / ⎵ per entrare")

    def finish(self):
        if self.finished:
            return
        self.finished = True
        self.scene.stop()
        try:
            self.win.destroy()
        except tk.TclError:
            pass
        if callable(self.on_done):
            self.on_done()


class VideoSplash:
    """Riproduce un video a schermo intero con overlay HUD 'CREATED BY MAIKGOST'."""

    def __init__(self, root, path, on_done=None, accent=None):
        self.on_done = on_done
        self.accent = accent or THEME["accent"]
        self.running = True
        self.after_id = None
        self.photo = None
        self.frame = 0
        self.cap = None
        self.delay = 40
        self.win = _fullscreen_toplevel(root)
        self.cv = tk.Canvas(self.win, bg="black", highlightthickness=0)
        self.cv.pack(fill="both", expand=True)
        for ev in ("<Button-1>", "<Escape>", "<space>", "<Return>"):
            self.win.bind(ev, lambda e: self.finish())
        self.win.focus_set()
        try:
            self.cap = cv2.VideoCapture(path)
            fps = self.cap.get(cv2.CAP_PROP_FPS)
            self.delay = int(1000 / fps) if fps and fps > 1 else 40
        except Exception:
            self.cap = None
        if not self.cap or not self.cap.isOpened():
            self.finish()
            return
        self.win.after(20, self._tick)

    def _tick(self):
        self.after_id = None
        if not self.running:
            return
        try:
            ok, frame = self.cap.read()
        except Exception:
            ok, frame = False, None
        if not ok:
            self.finish()
            return
        try:
            w, h = self.cv.winfo_width(), self.cv.winfo_height()
            if w <= 1:
                w, h = self.win.winfo_screenwidth(), self.win.winfo_screenheight()
            img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            sc = min(w / img.width, h / img.height)
            img = img.resize((max(1, int(img.width * sc)), max(1, int(img.height * sc))))
            self.photo = ImageTk.PhotoImage(img)
            self.cv.delete("all")
            self.cv.create_image(w // 2, h // 2, image=self.photo)
            self._overlay(w, h)
        except tk.TclError:
            return
        except Exception:
            pass
        self.frame += 1
        self.after_id = self.win.after(self.delay, self._tick)

    def _overlay(self, w, h):
        acc, c = self.accent, self.cv
        brackets(c, 18, 18, w - 18, h - 18, 40, acc, 2)
        c.create_text(28, 32, anchor="w", fill=acc, font=(MONO, 11, "bold"),
                      text=f"◈ ORION//SECURE · operator {CREATOR}")
        c.create_text(w - 28, 32, anchor="e", fill=THEME["amber"], font=(MONO, 10, "bold"),
                      text="◦ SIMULAZIONE / GIOCO ◦   ● REC")
        by = h - 64
        glitch = (self.frame // 4) % 7 == 0
        for dx, col in ((-3, THEME["red"]), (3, acc)) if glitch else ():
            c.create_text(w // 2 + dx, by, text=f"CREATED BY  {CREATOR}", fill=col,
                          font=(DISPLAY, 26, "bold"))
        for dx, dy in ((2, 0), (-2, 0), (0, 2), (0, -2)):
            c.create_text(w // 2 + dx, by + dy, text=f"CREATED BY  {CREATOR}",
                          fill=mix("#000000", acc, 0.6), font=(DISPLAY, 26, "bold"))
        c.create_text(w // 2, by, text=f"CREATED BY  {CREATOR}", fill=THEME["white"],
                      font=(DISPLAY, 26, "bold"))
        c.create_text(w // 2, h - 26, fill=THEME["dim"], font=(MONO, 10),
                      text="ORION INTELLIGENCE // CLASSIFIED   ·   click / ⎵ per entrare")

    def finish(self):
        if not self.running:
            return
        self.running = False
        if self.after_id:
            try:
                self.win.after_cancel(self.after_id)
            except tk.TclError:
                pass
        try:
            if self.cap:
                self.cap.release()
        except Exception:
            pass
        try:
            self.win.destroy()
        except tk.TclError:
            pass
        if callable(self.on_done):
            self.on_done()


# ===========================================================================
#  VISTE ANIMATE: GRAFO RELAZIONI + MAPPA GEO-INT
# ===========================================================================
class _BackdropMixin:
    """Sfondo Pillow rigenerato solo quando la dimensione si è stabilizzata."""

    def _init_bg(self):
        self.bg, self.bg_key, self._seen = None, None, (None, 0.0)

    def _ensure_bg(self, key, make):
        if not PIL_OK or key == self.bg_key:
            return
        now = time.time()
        if key != self._seen[0]:
            self._seen = (key, now)
            return
        if now - self._seen[1] >= 0.15:
            self.bg, self.bg_key = ImageTk.PhotoImage(make()), key


class NetworkGraph(_BackdropMixin):
    """Grafo relazioni animato (target ▸ identità ▸ entità) con pacchetti dati."""

    def __init__(self, canvas, data, accent=None):
        self.c = canvas
        self.accent = accent or THEME["accent"]
        self.frame = 0
        self.nodes, self.edges = self._layout(data) if data else ([], [])
        self._init_bg()
        self.anim = Anim(canvas, 40, self._tick)

    def stop(self):
        self.anim.stop()

    def _layout(self, data):
        nodes = [{"dist": 0, "ang": 0, "col": THEME["white"], "label": data["target"],
                  "kind": "target"}]
        edges = []
        ids = data["identities"]
        span = 2 * math.pi / max(1, len(ids))
        for k, it in enumerate(ids):
            a = span * k + 0.35
            id_idx = len(nodes)
            nodes.append({"dist": 1.0, "ang": a, "label": it["name"], "kind": "id", "num": k + 1,
                          "col": self.accent if k == 0 else THEME["accent2"],
                          "conf": it["confidence"]})
            edges.append((0, id_idx))
            ent = ([("@" + s["platform"], THEME["magenta"]) for s in data["socials"][:2]] +
                   [(e["type"], THEME["amber"]) for e in data["emails"][:1]] +
                   [(it["location"].split(",")[0], THEME["green"])])
            for j, (lab, col) in enumerate(ent):
                off = (j - (len(ent) - 1) / 2) * span * 0.62 / len(ent)
                edges.append((id_idx, len(nodes)))       # entità → sua identità
                nodes.append({"dist": 1.75, "ang": a + off, "col": col, "label": lab,
                              "kind": "ent"})
        return nodes, edges

    def _pill(self, x, y, text, col, font):
        tw = text_w(text, font) + 16
        self.c.create_polygon(chamfer(x - tw / 2, y - 10, x + tw / 2, y + 10, 5),
                              fill=mix(THEME["bg"], col, 0.12), outline=mix(THEME["bg"], col, 0.55))
        self.c.create_text(x, y, text=text, fill=THEME["white"], font=font)

    def _tick(self):
        c = self.c
        if not visible(c):
            return 300
        w, h = c.winfo_width(), c.winfo_height()
        if w <= 1:
            return 100
        self._ensure_bg((w, h), lambda: render_backdrop(w, h, self.accent, (0.5, 0.5), 24))
        self.frame += 1
        fr, acc, bgc, dim = self.frame, self.accent, THEME["bg"], THEME["dim"]
        c.delete("all")
        if self.bg is not None:
            c.create_image(0, 0, image=self.bg, anchor="nw")
        else:
            c.create_rectangle(0, 0, w, h, fill=bgc, outline="")
        cx, cy = w / 2, h / 2 + 8
        uy = h * 0.22
        ux = min(w * 0.24, uy * 1.55)
        for rr, n, spd in ((1.0, 3, 0.6), (1.75, 4, -0.35)):
            x0, y0, x1, y1 = cx - rr * ux, cy - rr * uy, cx + rr * ux, cy + rr * uy
            c.create_oval(x0, y0, x1, y1, outline=mix(bgc, acc, 0.13))
            for j in range(n):
                c.create_arc(x0, y0, x1, y1, start=(fr * spd + j * 360 / n) % 360,
                             extent=360 / n * 0.3, style="arc", outline=mix(bgc, acc, 0.45), width=2)
        brackets(c, 12, 12, w - 12, h - 12, 26, mix(bgc, acc, 0.6))
        c.create_text(24, 28, anchor="w", text="⬡ RELATION MAP", fill=acc, font=(DISPLAY, 12, "bold"))
        c.create_text(w - 24, h - 24, anchor="e", text=f"SIM · by {CREATOR}", fill=dim,
                      font=(MONO, 8))
        if not self.nodes:
            p = (math.sin(fr * 0.08) + 1) / 2
            c.create_polygon(hexagon(cx, cy, 30, fr * 0.01), fill="", outline=mix(bgc, acc, 0.3 + 0.5 * p),
                             width=2)
            c.create_text(cx, cy + 62, text="IN ATTESA DEL BERSAGLIO", fill=mix(dim, acc, p * 0.6),
                          font=(DISPLAY, 13, "bold"))
            return
        c.create_text(24, 48, anchor="w", fill=dim, font=(MONO, 9),
                      text=f"NODI {len(self.nodes)} · LINK {len(self.edges)} · SIMULAZIONE")
        phase = fr * 0.004
        pos = [(cx + n["dist"] * ux * math.cos(n["ang"] + phase),
                cy + n["dist"] * uy * math.sin(n["ang"] + phase)) for n in self.nodes]
        for a, b in self.edges:
            (x1, y1), (x2, y2) = pos[a], pos[b]
            col = self.nodes[b]["col"]
            c.create_line(x1, y1, x2, y2, fill=mix(bgc, col, 0.32))
            for q in (0.0, 0.5):
                t = ((fr * 0.012) + (a * 7 + b) * 0.13 + q) % 1.0
                for tr in range(3):
                    tt = t - tr * 0.03
                    if tt < 0:
                        continue
                    px, py, rad = lerp(x1, x2, tt), lerp(y1, y2, tt), 2.8 - tr * 0.8
                    c.create_oval(px - rad, py - rad, px + rad, py + rad, outline="",
                                  fill=mix(bgc, col, 1 - tr * 0.3))
        for n, (x, y) in zip(self.nodes, pos):
            col = n["col"]
            pulse = (math.sin(fr * 0.08 + x * 0.01) + 1) / 2
            if n["kind"] == "target":
                r = 26
                for g in (3, 2, 1):
                    c.create_polygon(hexagon(x, y, r + g * 7, -fr * 0.01), fill="",
                                     outline=mix(bgc, acc, 0.5 - g * 0.12))
                c.create_polygon(hexagon(x, y, r, fr * 0.01), fill=mix(bgc, acc, 0.25), outline=acc,
                                 width=2)
                c.create_oval(x - 6, y - 6, x + 6, y + 6, fill="#ffffff", outline="")
                self._pill(x, y + r + 26, n["label"].upper(), acc, (DISPLAY, 10, "bold"))
            elif n["kind"] == "id":
                r = 14 + pulse * 1.5
                c.create_polygon(hexagon(x, y, r + 7, math.pi / 6), fill="", outline=mix(bgc, col, 0.3))
                c.create_polygon(hexagon(x, y, r, math.pi / 6), fill=mix(bgc, col, 0.35), outline=col,
                                 width=2)
                c.create_text(x, y, text=str(n["num"]), fill="#ffffff", font=(MONO, 9, "bold"))
                self._pill(x, y - r - 18, n["label"], col, (UI, 9, "bold"))
                c.create_text(x, y + r + 12, text=f"{n['conf']}%", fill=dim, font=(MONO, 8))
            else:
                c.create_oval(x - 9, y - 9, x + 9, y + 9, outline=mix(bgc, col, 0.3 + 0.3 * pulse))
                c.create_oval(x - 5, y - 5, x + 5, y + 5, fill=col, outline="")
                c.create_text(x, y + 17, text=n["label"], fill=mix(dim, col, 0.35), font=(MONO, 8))


class GeoMap(_BackdropMixin):
    """Mappa GEO-INT: mondo a punti, rotte animate, ping, mirino col mouse."""

    def __init__(self, canvas, data, accent=None):
        self.c = canvas
        self.accent = accent or THEME["accent"]
        self.frame = 0
        self.mouse = None
        self.points = ([(it["geo"][0], it["geo"][1], it["name"], it["threat"])
                        for it in data["identities"]] if data else [])
        self._init_bg()
        canvas.bind("<Motion>", lambda e: setattr(self, "mouse", (e.x, e.y)))
        canvas.bind("<Leave>", lambda e: setattr(self, "mouse", None))
        self.anim = Anim(canvas, 50, self._tick)

    def stop(self):
        self.anim.stop()

    def _view(self, w, h):
        if self.points:
            lats = [p[0] for p in self.points]
            lons = [p[1] for p in self.points]
            lon0, lon1 = min(lons) - 14, max(lons) + 14
            lat0, lat1 = min(lats) - 9, max(lats) + 9
            if lon1 - lon0 < 44:
                m = (lon0 + lon1) / 2
                lon0, lon1 = m - 22, m + 22
            if lat1 - lat0 < 24:
                m = (lat0 + lat1) / 2
                lat0, lat1 = m - 12, m + 12
        else:
            lon0, lon1, lat0, lat1 = -170, 190, -58, 82
        ppd = min(w / (lon1 - lon0), h / (lat1 - lat0))   # stessa scala su x e y
        mx, my = (lon0 + lon1) / 2, (lat0 + lat1) / 2
        sx, sy = w / ppd / 2, h / ppd / 2
        lat0, lat1 = my - sy, my + sy
        if lat1 > 88:
            lat0, lat1 = lat0 - (lat1 - 88), 88
        return (mx - sx, lat0, mx + sx, lat1)

    def _tick(self):
        c = self.c
        if not visible(c):
            return 300
        w, h = c.winfo_width(), c.winfo_height()
        if w <= 1:
            return 100
        view = self._view(w, h)
        lon0, lat0, lon1, lat1 = view
        self._ensure_bg((w, h, view), lambda: render_world_map(w, h, view, self.accent))
        self.frame += 1
        fr, acc, bgc, dim = self.frame, self.accent, THEME["bg"], THEME["dim"]
        c.delete("all")
        if self.bg is not None:
            c.create_image(0, 0, image=self.bg, anchor="nw")
        else:
            c.create_rectangle(0, 0, w, h, fill=THEME["bg2"], outline="")

        def xy(lat, lon):
            return (lon - lon0) / (lon1 - lon0) * w, (lat1 - lat) / (lat1 - lat0) * h

        pts = [xy(lat, lon) + (name, threat, lat, lon) for (lat, lon, name, threat) in self.points]
        sx = (fr * 6) % (w + 200) - 100
        for k in range(6):
            c.create_line(sx - k * 5, 0, sx - k * 5, h, fill=mix(bgc, acc, 0.3 - k * 0.045))
        for i in range(len(pts) - 1):
            (x1, y1), (x2, y2) = pts[i][:2], pts[i + 1][:2]
            mx, my = (x1 + x2) / 2, min(y1, y2) - max(40, abs(x2 - x1) * 0.25)
            c.create_line(x1, y1, mx, my, x2, y2, smooth=True, splinesteps=24, dash=(4, 3),
                          fill=mix(bgc, acc, 0.55))
            for tr in range(4):
                t = (fr * 0.015 + i * 0.3 - tr * 0.02) % 1.0
                px = (1 - t) ** 2 * x1 + 2 * (1 - t) * t * mx + t * t * x2
                py = (1 - t) ** 2 * y1 + 2 * (1 - t) * t * my + t * t * y2
                rad = 3.2 - tr * 0.6
                c.create_oval(px - rad, py - rad, px + rad, py + rad, outline="",
                              fill=mix(bgc, acc, 1 - tr * 0.22))
        for (x, y, name, threat, lat, lon) in pts:
            col = threat_color(threat)
            for k in range(3):
                rad = 6 + ((fr * 1.6 + k * 18) % 54)
                c.create_oval(x - rad, y - rad, x + rad, y + rad,
                              outline=mix(bgc, col, max(0.05, 1 - rad / 60)))
            for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
                c.create_line(x + dx * 8, y + dy * 8, x + dx * 17, y + dy * 17, fill=col, width=2)
            c.create_oval(x - 4, y - 4, x + 4, y + 4, fill=col, outline="#ffffff")
            f1, f2 = (UI, 9, "bold"), (MONO, 8, "bold")
            sub = f"{lat:.3f}, {lon:.3f} · {threat}"
            bw = max(text_w(name, f1), text_w(sub, f2)) + 20
            right = x + 40 + bw < w - 10
            lx = x + 36 if right else x - 36 - bw
            ly = y - 44
            c.create_line(x, y, x + (24 if right else -24), ly + 18,
                          lx if right else lx + bw, ly + 18, fill=col)
            c.create_polygon(chamfer(lx, ly, lx + bw, ly + 36, 7), fill=mix(bgc, col, 0.12),
                             outline=col)
            c.create_text(lx + 10, ly + 11, anchor="w", text=name, fill=THEME["white"], font=f1)
            c.create_text(lx + 10, ly + 26, anchor="w", text=sub, fill=col, font=f2)
        if self.mouse:
            mx, my = self.mouse
            c.create_line(0, my, w, my, fill=mix(bgc, acc, 0.22), dash=(2, 4))
            c.create_line(mx, 0, mx, h, fill=mix(bgc, acc, 0.22), dash=(2, 4))
            mlon = lon0 + mx / w * (lon1 - lon0)
            mlat = lat1 - my / h * (lat1 - lat0)
            c.create_text(mx + 10, my - 10, anchor="sw", fill=acc, font=(MONO, 9, "bold"),
                          text=f"{mlat:+.3f}  {((mlon + 180) % 360) - 180:+.3f}")
        brackets(c, 12, 12, w - 12, h - 12, 26, mix(bgc, acc, 0.6))
        c.create_polygon(chamfer(18, 14, 330, 60, 10), fill=mix(bgc, acc, 0.06),
                         outline=mix(bgc, acc, 0.4))
        c.create_text(28, 28, anchor="w", text="⌖ GEO-INT", fill=acc, font=(DISPLAY, 12, "bold"))
        c.create_text(28, 47, anchor="w", fill=THEME["text"], font=(MONO, 9),
                      text=f"coordinate reali · dati SIM · {len(pts)} posizioni")
        c.create_text(w - 24, h - 24, anchor="e", text=f"by {CREATOR}", fill=dim, font=(MONO, 8))
        if not pts:
            p = (math.sin(fr * 0.08) + 1) / 2
            c.create_text(w / 2, h - 46, text="NESSUN BERSAGLIO · scansione globale in corso",
                          fill=mix(dim, acc, p * 0.7), font=(DISPLAY, 12, "bold"))


class TimelineView(tk.Frame):
    """Timeline verticale con nodi luminosi e card che entrano in sequenza."""
    STEP = 76

    def __init__(self, parent):
        super().__init__(parent, bg=THEME["panel"])
        self.cv = tk.Canvas(self, bg=THEME["panel"], highlightthickness=0)
        sb = ttk.Scrollbar(self, orient="vertical", command=self.cv.yview,
                           style="Orion.Vertical.TScrollbar")
        self.cv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.cv.pack(fill="both", expand=True)
        self.cv.orion_scroll = True
        enable_wheel(self)
        self.events, self.target = [], ""
        self.t0, self.final = 0.0, True
        self.cv.bind("<Configure>", lambda e: self._draw())
        Anim(self.cv, 33, self._tick)

    def set(self, events, target=""):
        self.events, self.target = events, target
        self.t0, self.final = time.time(), False

    def _tick(self):
        if not visible(self.cv):
            if not self.final:
                self.t0 = time.time()
            return 300
        if time.time() - self.t0 < 0.22 * len(self.events) + 0.6:
            self._draw()
            return 33
        if not self.final:
            self.final = True
            self._draw()
        return 400

    def _draw(self):
        c = self.cv
        c.delete("all")
        w, pan, acc, dim = c.winfo_width(), THEME["panel"], THEME["accent"], THEME["dim"]
        c.create_text(28, 28, anchor="w", text="◷ TIMELINE ATTIVITÀ", fill=acc,
                      font=(DISPLAY, 13, "bold"))
        ev = self.events
        if not ev:
            c.create_text(28, 50, anchor="w", fill=dim, font=(MONO, 9),
                          text="avvia una scansione per ricostruire la cronologia")
            return
        c.create_text(28, 50, anchor="w", fill=dim, font=(MONO, 9),
                      text=f"{len(ev)} eventi ricostruiti (SIM) · target {self.target} · by {CREATOR}")
        x, y0, step = 170, 104, self.STEP
        el = time.time() - self.t0 if not self.final else 99
        c.create_line(x, y0 - 24, x, y0 + (len(ev) - 1) * step + 24, fill=mix(pan, acc, 0.35), width=2)
        names = {"info": "INFO", "warn": "ATTENZIONE", "bad": "CRITICO"}
        glyphs = {"info": "●", "warn": "▲", "bad": "✖"}
        for i, e in enumerate(ev):
            p = ease_out((el - i * 0.22) / 0.45)
            if p <= 0:
                continue
            y = y0 + i * step
            col = THEME[SEV_COLORS.get(e["sev"], "dim")]
            try:
                ago = (datetime.now() - datetime.strptime(e["date"], "%Y-%m-%d")).days
                ago_txt = f"T-{ago} giorni"
            except ValueError:
                ago_txt = ""
            c.create_text(x - 26, y - 8, anchor="e", text=e["date"], font=(MONO, 11, "bold"),
                          fill=mix(pan, THEME["text"], p))
            c.create_text(x - 26, y + 11, anchor="e", text=ago_txt, font=(MONO, 8),
                          fill=mix(pan, dim, p))
            c.create_oval(x - 12, y - 12, x + 12, y + 12, outline=mix(pan, col, 0.45 * p))
            c.create_oval(x - 6, y - 6, x + 6, y + 6, fill=mix(pan, col, p), outline="")
            x0, x1 = x + 34 + (1 - p) * 50, w - 28
            c.create_line(x + 12, y, x0, y, fill=mix(pan, col, 0.5 * p))
            c.create_polygon(chamfer(x0, y - 26, x1, y + 26, 10), fill=mix(pan, THEME["card"], p),
                             outline=mix(pan, col, 0.6 * p))
            c.create_text(x0 + 16, y - 8, anchor="w", font=(UI, 11, "bold"),
                          text=f"{glyphs.get(e['sev'], '•')}  {e['event'].upper()}",
                          fill=mix(pan, "#ffffff", p))
            c.create_text(x0 + 16, y + 12, anchor="w", font=(MONO, 8, "bold"), fill=mix(pan, col, p),
                          text=f"SEVERITÀ {names.get(e['sev'], '—')} · fonte SIM · evento #{i + 1:02d}")
        c.configure(scrollregion=(0, 0, w, y0 + len(ev) * step + 10))


# ===========================================================================
#  CARD  —  social, identità, foto
# ===========================================================================
class _HoverCard(tk.Canvas):
    def __init__(self, parent, W, H, on_click=None):
        super().__init__(parent, width=W, height=H, bg=bg_of(parent), highlightthickness=0,
                         cursor="hand2" if on_click else "")
        self.W, self.H, self.hover, self.on_click = W, H, False, on_click
        self.bind("<Enter>", lambda e: self._hov(True))
        self.bind("<Leave>", lambda e: self._hov(False))
        if on_click:
            self.bind("<Button-1>", lambda e: on_click())

    def _hov(self, v):
        self.hover = v
        self._draw()

    def _chip(self, x, y, text, col, anchor="w", filled=False):
        f = (MONO, 8, "bold")
        tw = text_w(text, f) + 14
        x0 = x if anchor == "w" else x - tw
        self.create_polygon(chamfer(x0, y - 9, x0 + tw, y + 9, 5), outline=col,
                            fill=col if filled else mix(THEME["card"], col, 0.12))
        self.create_text(x0 + tw / 2, y, text=text, font=f, fill="#000000" if filled else col)
        return tw

    def _segs(self, x, y, n, k, col, sw=10, gap=3, h=8):
        for i in range(n):
            x0 = x + i * (sw + gap)
            self.create_polygon(x0 + 3, y, x0 + sw + 3, y, x0 + sw, y + h, x0, y + h, outline="",
                                fill=col if i < k else mix(THEME["card"], col, 0.15))


class SocialCard(_HoverCard):
    LEVEL = {"Bassa": 1, "Media": 2, "Alta": 3, "Molto alta": 4}

    def __init__(self, parent, p):
        super().__init__(parent, 304, 140)
        self.p = p
        self._draw()

    def _draw(self):
        self.delete("all")
        W, H, p, card = self.W, self.H, self.p, THEME["card"]
        acc, mag, dim = THEME["accent"], THEME["magenta"], THEME["dim"]
        self.create_polygon(chamfer(1, 1, W - 2, H - 2, 12), fill=card,
                            outline=acc if self.hover else THEME["line2"])
        if self.hover:
            brackets(self, 6, 6, W - 6, H - 6, 12, acc)
        self.create_polygon(hexagon(38, 40, 21, math.pi / 6), fill=mix(card, mag, 0.2), outline=mag,
                            width=2)
        self.create_text(38, 40, text=p["glyph"], fill="#ffffff", font=(UI, 13, "bold"))
        self.create_text(70, 30, anchor="w", text=p["platform"].upper(), fill="#ffffff",
                         font=(DISPLAY, 12, "bold"))
        self.create_text(70, 50, anchor="w", text=p["handle"], fill=acc, font=(MONO, 10))
        if p["verified"]:
            self._chip(W - 12, 22, "✔ VERIF.", THEME["green"], anchor="e")
        else:
            self._chip(W - 12, 22, "◌ NON VERIF.", dim, anchor="e")
        for i, (lab, val) in enumerate((("FOLLOWER", p["followers"]), ("POST", p["posts"]),
                                        ("VISTO", p["last_seen"]))):
            x = 16 + i * 96
            self.create_text(x, 78, anchor="w", text=lab, fill=dim, font=(MONO, 8, "bold"))
            self.create_text(x, 96, anchor="w", text=str(val), fill="#ffffff", font=(DISPLAY, 13, "bold"))
        lvl = self.LEVEL.get(p["activity"], 2)
        self.create_text(16, 122, anchor="w", text="ATTIVITÀ", fill=dim, font=(MONO, 8, "bold"))
        self._segs(80, 118, 8, lvl * 2, mix(acc, mag, lvl / 4), sw=14)
        self.create_text(W - 14, 122, anchor="e", text=p["activity"].upper(), fill=acc,
                         font=(MONO, 8, "bold"))


class IdentityCard(_HoverCard):
    def __init__(self, parent, it, thumb, n_photos):
        super().__init__(parent, 620, 186)
        self.it, self.n_photos = it, n_photos
        self.thumb = ImageTk.PhotoImage(thumb) if thumb is not None else None
        self._draw()

    def _draw(self):
        self.delete("all")
        W, H, it, card = self.W, self.H, self.it, THEME["card"]
        acc, dim = THEME["accent"], THEME["dim"]
        tcol = threat_color(it["threat"])
        primary = it["index"] == 0
        self.create_polygon(chamfer(1, 1, W - 2, H - 2, 14), fill=card,
                            outline=acc if self.hover else THEME["line2"])
        self.create_line(2, 20, 2, H - 20, fill=acc if primary else THEME["accent2"], width=3)
        if self.thumb:
            self.create_image(14, 14, image=self.thumb, anchor="nw")
            brackets(self, 12, 12, 14 + self.thumb.width() + 2, 14 + self.thumb.height() + 2, 12,
                     acc if self.hover else mix(card, acc, 0.6))
        x = 164
        self.create_text(x, 28, anchor="w", text=it["name"].upper(), fill="#ffffff",
                         font=(DISPLAY, 15, "bold"))
        cx = x
        cx += self._chip(cx, 54, "PRIMARIA" if primary else f"SECONDARIA #{it['index']}",
                         acc if primary else THEME["accent2"], filled=primary) + 6
        cx += self._chip(cx, 54, f"MINACCIA {it['threat']}", tcol) + 6
        self._chip(cx, 54, f"ALIAS {', '.join(it['aliases'])}", dim)
        b = it["biometrics"]
        fields = [("ETÀ", it["age"]), ("LUOGO", it["location"]), ("RUOLO", it["role"]),
                  ("FOTO", self.n_photos), ("ALTEZZA", b["height"]), ("OCCHI", b["eyes"]),
                  ("CORPORATURA", b["build"]), ("SEGNI", b["marks"])]
        for i, (lab, val) in enumerate(fields):
            fx, fy = x + (i % 4) * 112, 82 + (i // 4) * 36
            self.create_text(fx, fy, anchor="w", text=lab, fill=dim, font=(MONO, 8, "bold"))
            self.create_text(fx, fy + 15, anchor="w", text=str(val), fill="#ffffff",
                             font=(UI, 10, "bold"))
        for j, (lab, v, col) in enumerate((("CONFIDENCE", it["confidence"], acc),
                                           ("SOCIAL SCORE", it["social_score"], THEME["magenta"]))):
            bx = x + j * 224
            self.create_text(bx, 160, anchor="w", text=f"{lab} {v}%", fill=col, font=(MONO, 8, "bold"))
            self._segs(bx, 168, 14, int(round(v / 100 * 14)), col, sw=11, h=7)


class PhotoCard(_HoverCard):
    def __init__(self, parent, img, photo, on_open):
        self.tk_img = ImageTk.PhotoImage(img)
        self.pw, self.ph = img.size
        self.photo = photo
        super().__init__(parent, self.pw + 16, self.ph + 64, on_click=on_open)
        self._draw()

    def _draw(self):
        self.delete("all")
        W, H, p, card = self.W, self.H, self.photo, THEME["card"]
        acc, dim = THEME["accent"], THEME["dim"]
        self.create_polygon(chamfer(1, 1, W - 2, H - 2, 12), fill=card,
                            outline=acc if self.hover else THEME["line2"],
                            width=2 if self.hover else 1)
        self.create_image(8, 8, image=self.tk_img, anchor="nw")
        if self.hover:
            brackets(self, 4, 4, W - 4, self.ph + 12, 18, acc, 3)
            y1 = 8 + self.ph
            self.create_rectangle(8, y1 - 28, 8 + self.pw, y1, fill=acc, outline="")
            self.create_text(8 + self.pw / 2, y1 - 14, text="▶  ANALIZZA ASSET", fill="#000000",
                             font=(UI, 10, "bold"))
        y = self.ph + 26
        icol = THEME["green"] if p["intel"] >= 7 else THEME["amber"] if p["intel"] >= 5 else THEME["red"]
        self.create_text(10, y, anchor="w", text="INTEL", fill=dim, font=(MONO, 8, "bold"))
        self._segs(48, y - 4, 10, p["intel"], icol, sw=8, gap=2)
        self._chip(W - 10, y, p["quality"], acc, anchor="e")
        self.create_text(10, y + 22, anchor="w", text=f"{p['date']} · {p['source']}", fill=dim,
                         font=(MONO, 8))


class FaceScan:
    """Overlay animato di riconoscimento facciale: scansione → mesh → aggancio."""

    def __init__(self, canvas, w, h, accent, matched, face=None):
        self.c, self.w, self.h, self.accent, self.matched = canvas, w, h, accent, matched
        cx, cy, rx, ry = face or (w / 2, h * 0.40, w * 0.18, h * 0.23)
        self.face = (cx, cy, rx, ry)
        self.mesh = face_mesh_points(cx, cy, rx, ry)
        self.order = list(self.mesh)
        self.frame = 0
        self.score = random.uniform(91, 99.4)
        Anim(canvas, 40, self._tick)

    def _tick(self):
        c, w, h, acc = self.c, self.w, self.h, self.accent
        self.frame += 1
        fr = self.frame
        c.delete("scan")
        bw = 2 + int((math.sin(fr * 0.2) + 1))
        brackets(c, 14, 14, w - 14, h - 14, 30, acc, bw, tags="scan")
        cx, cy, rx, ry = self.face
        if fr < 60:                                    # 1) scansione
            t = fr / 60
            y = 14 + (h - 28) * (t * 2 if t < 0.5 else 2 - t * 2)
            c.create_rectangle(10, y, w - 10, y + 3, fill=acc, outline="", tags="scan")
            for k in range(1, 6):
                c.create_line(10, y - k * 5, w - 10, y - k * 5, fill=mix("#000000", acc, 0.5 - k * 0.08),
                              tags="scan")
            c.create_text(w - 20, y + 12, anchor="e", fill=acc, font=(MONO, 9, "bold"),
                          text=f"SCAN {int(t * 100)}%", tags="scan")
            return 40
        k = min(len(self.order), int((fr - 60) / 30 * len(self.order)))
        shown = set(self.order[:k])
        for a, b in _MESH_EDGES:                       # 2) mesh progressiva
            if a in shown and b in shown:
                c.create_line(*self.mesh[a], *self.mesh[b], fill=mix("#000000", acc, 0.75),
                              tags="scan")
        for name in shown:
            px, py = self.mesh[name]
            c.create_oval(px - 2.5, py - 2.5, px + 2.5, py + 2.5, fill="#ffffff", outline=acc,
                          tags="scan")
        c.create_text(w - 20, 70, anchor="e", fill=acc, font=(MONO, 9, "bold"),
                      text=f"LANDMARK {k:02d}/{len(self.order)}", tags="scan")
        if fr < 92:
            return 40
        col = THEME["green"] if self.matched else THEME["red"]   # 3) aggancio
        p = (math.sin(fr * 0.15) + 1) / 2
        c.create_polygon(hexagon(cx, cy, min(max(rx, ry) * 1.45, w * 0.4), math.pi / 6), fill="",
                         outline=mix("#000000", col, 0.4 + 0.6 * p), width=2, tags="scan")
        label = f"◉ IDENTITY MATCH  {self.score:.1f}%" if self.matched else "✕ NO MATCH"
        yb = h * 0.82
        c.create_rectangle(0, yb - 20, w, yb + 20, fill="#000000", outline=col, tags="scan")
        c.create_text(w / 2, yb, fill=col, font=(DISPLAY, 15, "bold"), text=label, tags="scan")
        c.create_text(w / 2, h - 8, fill=THEME["dim"], font=(MONO, 8), text=f"by {CREATOR}",
                      tags="scan", anchor="s")
        return 80


class Slideshow:
    """Presentazione a schermo intero con transizioni glitch, HUD e timer."""

    def __init__(self, root, data, settings, face_for):
        self.data, self.settings, self.face_for = data, settings, face_for
        self.photos = data["photos"]
        self.accent = settings.get("accent", THEME["accent"])
        self.fx = settings.get("fx", True)
        self.i = 0
        self.paused = False
        self.after_id = self.fade_id = None
        self.cur_img = None
        self.cache = {}
        self.ref = None
        self.W = self.H = 0
        self.t_slide = time.time()
        self.rng = random.Random()
        self.interval = max(1000, int(settings.get("slideshow_sec", 4.0) * 1000))

        self.win = tk.Toplevel(root)
        self.win.title(f"SLIDESHOW — by {CREATOR}")
        self.win.configure(bg="#000000")
        _go_fullscreen(self.win)
        bar = tk.Frame(self.win, bg=THEME["panel"])
        bar.pack(side="bottom", fill="x")
        tk.Frame(bar, bg=THEME["line"], height=1).pack(fill="x", side="top")
        self.info = tk.Label(bar, text="", font=(MONO, 10), bg=THEME["panel"], fg=THEME["dim"])
        self.info.pack(side="left", padx=14)
        for txt, cmd, wd in [("✕  ESCI", self.stop, 96), ("⏭", self.next, 46), ("⏯", self.toggle, 46),
                             ("⏮", self.prev, 46), ("+", self.faster, 40), ("−", self.slower, 40)]:
            NeonButton(bar, txt, cmd, width=wd, height=32,
                       color=THEME["red"] if "ESCI" in txt else self.accent).pack(
                side="right", padx=3, pady=6)
        self.speed_lbl = tk.Label(bar, text="", font=(MONO, 11, "bold"), bg=THEME["panel"],
                                  fg=self.accent)
        self.speed_lbl.pack(side="right", padx=10)
        self.cv = tk.Canvas(self.win, bg="#000000", highlightthickness=0)
        self.cv.pack(side="top", fill="both", expand=True)
        self.win.bind("<Escape>", lambda e: self.stop())
        self.win.bind("<Right>", lambda e: self.next())
        self.win.bind("<Left>", lambda e: self.prev())
        self.win.bind("<space>", lambda e: self.toggle())
        self.win.focus_set()
        self._update_speed()
        self.win.after(90, self._start)
        Anim(self.cv, 50, self._hud_tick)

    def _dims(self):
        self.win.update_idletasks()
        w, h = self.cv.winfo_width(), self.cv.winfo_height()
        if w <= 1:
            w = self.win.winfo_screenwidth()
        if h <= 1:
            h = self.win.winfo_screenheight() - 60
        return max(400, w), max(400, h)

    def _portrait(self, idx):
        if idx in self.cache:
            return self.cache[idx]
        p = self.photos[idx]
        ph = max(360, min(self.H - 110, int((self.W - 160) * 1.2)))
        pw = int(ph / 1.2)
        img = generate_portrait(f"{self.data['target']}|{p['id']}", (pw, ph), self.accent,
                                p["identity_name"], f"{p['tag']} · {p['location']}",
                                p["matched"], self.settings.get("redacted", True),
                                base_image=self.face_for(p))
        self.cache[idx] = img
        return img

    def _start(self):
        if not self.win.winfo_exists():
            return
        self.W, self.H = self._dims()
        self.cur_img = self._portrait(self.i)
        self._blit(self.cur_img)
        self._schedule()

    def _blit(self, img, hud=True):
        if not self.win.winfo_exists():
            return
        self.ref = ImageTk.PhotoImage(img)
        c, W, H, acc = self.cv, self.W, self.H, self.accent
        c.delete("img")
        c.create_image(W // 2, H // 2, image=self.ref, tags="img")
        c.tag_lower("img")
        if not hud:
            return
        c.delete("hud")
        p = self.photos[self.i]
        iw, ih = img.size
        x0, y0, x1, y1 = W / 2 - iw / 2, H / 2 - ih / 2, W / 2 + iw / 2, H / 2 + ih / 2
        brackets(c, x0 - 12, y0 - 12, x1 + 12, y1 + 12, 34, acc, 3, tags="hud")
        brackets(c, 16, 16, W - 16, H - 16, 40, mix("#000000", acc, 0.5), 2, tags="hud")
        c.create_text(W / 2, 34, fill=acc, font=(DISPLAY, 17, "bold"), tags="hud",
                      text=f"{p['identity_name'].upper()}  —  {p['tag'].upper()}")
        c.create_text(W - 40, 34, anchor="e", fill="#ffffff", font=(DISPLAY, 15, "bold"), tags="hud",
                      text=f"{self.i + 1:02d} / {len(self.photos):02d}")
        if x0 > 260:
            rows = [("IDENTITÀ", p["identity_name"]), ("LUOGO", p["location"]),
                    ("DATA", p["date"]), ("FONTE", p["source"]), ("QUALITÀ", p["quality"]),
                    ("INTEL", f"{p['intel']}/10"), ("MATCH", "SÌ" if p["matched"] else "NO")]
            for k, (lab, val) in enumerate(rows):
                yy = y0 + 10 + k * 46
                c.create_text(40, yy, anchor="w", text=lab, fill=THEME["dim"],
                              font=(MONO, 9, "bold"), tags="hud")
                c.create_text(40, yy + 18, anchor="w", text=str(val), fill="#ffffff",
                              font=(UI, 12, "bold"), tags="hud")
        c.create_rectangle(0, 0, 0, 0, fill=acc, outline="", tags=("hud", "timer"))
        c.create_rectangle(W * 0.2, H - 22, W * 0.8, H - 18, fill=THEME["line"], outline="",
                           tags="hud")
        c.tag_raise("timer")
        self.info.config(text=f"{'⏸ PAUSA' if self.paused else '▶ PLAY'}  ·  Esc esci · "
                              f"←→ naviga · ⎵ pausa · by {CREATOR}")

    def _hud_tick(self):
        if not self.W:
            return 100
        W, H = self.W, self.H
        t = 0.0 if self.paused else min(1.0, (time.time() - self.t_slide) * 1000 / self.interval)
        self.cv.coords("timer", W * 0.2, H - 22, W * 0.2 + W * 0.6 * t, H - 18)

    def _schedule(self):
        if self.after_id:
            try:
                self.win.after_cancel(self.after_id)
            except tk.TclError:
                pass
            self.after_id = None
        self.t_slide = time.time()
        if not self.paused and self.win.winfo_exists():
            self.after_id = self.win.after(self.interval, self.next)

    def next(self):
        self._go(self.i + 1)

    def prev(self):
        self._go(self.i - 1)

    def _go(self, idx):
        if not self.win.winfo_exists() or self.cur_img is None:
            return
        if self.fade_id:                        # tasti rapidi: annullo la transizione in corso
            try:
                self.win.after_cancel(self.fade_id)
            except tk.TclError:
                pass
            self.fade_id = None
        idx %= len(self.photos)
        nxt = self._portrait(idx)
        prev = self.cur_img
        self.i = idx
        self._crossfade(prev, nxt, 1)

    def _crossfade(self, a, b, step, steps=10):
        self.fade_id = None
        if not self.win.winfo_exists():
            return
        if a is None or a.size != b.size or step > steps:
            self.cur_img = b
            self._blit(b)
            self._schedule()
            return
        t = step / steps
        frame = Image.blend(a, b, t)
        if self.fx:
            frame = glitch_frame(frame, (1 - abs(2 * t - 1)) * 0.8, self.rng)
        self._blit(frame, hud=step == 1)
        self.fade_id = self.win.after(28, lambda: self._crossfade(a, b, step + 1, steps))

    def toggle(self):
        self.paused = not self.paused
        if self.cur_img is None:                # finestra non ancora pronta
            return
        self._blit(self.cur_img)
        self._schedule()

    def slower(self):
        self.interval = min(12000, self.interval + 500)
        self._update_speed()
        self._schedule()

    def faster(self):
        self.interval = max(1000, self.interval - 500)
        self._update_speed()
        self._schedule()

    def _update_speed(self):
        self.speed_lbl.config(text=f"⏱ {self.interval / 1000:.1f}s")

    def stop(self):
        for aid in (self.after_id, self.fade_id):
            try:
                if aid:
                    self.win.after_cancel(aid)
            except tk.TclError:
                pass
        if self.win.winfo_exists():
            self.win.destroy()


# ===========================================================================
#  APP PRINCIPALE
# ===========================================================================
QUICK_TARGETS = ["Mario Rossi", "John Smith", "Anna Müller", "Luca Bianchi", "Marco Esposito",
                 "Yuki Tanaka"]


class SpyOSINTApp:
    def __init__(self, root):
        global _SFX
        self.root = root
        self.root.title(f"◈ {APP_NAME} — by {CREATOR}")
        self.root.configure(bg=THEME["bg"])
        self.root.geometry("1560x940")
        self.root.minsize(1180, 740)
        self._maximize(self.root)

        self.results = None
        self.current_target = ""
        self.search_active = False
        self._search_id = 0                 # invalida i risultati di ricerche vecchie
        self._ui_queue = queue.Queue()      # worker → thread Tk (Tk non è thread-safe)
        self._db_lock = threading.Lock()
        self._face_cache = {}
        self._portrait_cache = {}
        self._typing = {}
        self._settings_win = None
        self.net_anim = None
        self.geo_anim = None

        self.settings = self._load_settings()
        THEME["accent"] = self.settings["accent"]
        self.sfx = _SFX = SoundFX(root, lambda: self.settings.get("sound", True))

        self._setup_db()
        self._style()
        self._build_ui()
        self._poll_queue()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._bind_keys()
        if self.settings.get("splash", True):
            self._launch_splash()

    # ---- avvio ----------------------------------------------------------
    def _autodetect_video(self):
        """Cerca un video 'intro.*' vicino allo script o nella cartella corrente."""
        for d in (os.getcwd(), APP_DIR):
            for base in ("intro", "splash", "logo"):
                for ext in VIDEO_EXTS:
                    p = os.path.join(d, base + ext)
                    if os.path.exists(p):
                        return p
        return ""

    def _launch_splash(self):
        video = (self.settings.get("splash_video", "").strip()
                 or self._autodetect_video())
        if video and CV2_OK and PIL_OK and os.path.exists(video):
            VideoSplash(self.root, video, accent=THEME["accent"])
        else:
            BootSplash(self.root, accent=THEME["accent"], fx=self.settings.get("fx", True))

    def _bind_keys(self):
        r = self.root
        r.bind("<Escape>", lambda e: self.stop_search())
        r.bind("<Control-g>", lambda e: self.open_gallery())
        r.bind("<Control-p>", lambda e: self.open_slideshow())
        r.bind("<Control-e>", lambda e: self.export_report())
        r.bind("<Control-r>", lambda e: self.random_target())
        r.bind("<Control-comma>", lambda e: self.open_settings())
        r.bind("<F5>", lambda e: self.regenerate())
        r.bind("<F11>", lambda e: self._toggle_fullscreen())

    def _toggle_fullscreen(self):
        try:
            self.root.attributes("-fullscreen", not self.root.attributes("-fullscreen"))
        except tk.TclError:
            pass

    # ---- impostazioni ---------------------------------------------------
    def _load_settings(self):
        try:
            with open(SETTINGS_FILE, encoding="utf-8") as f:
                return sanitize_settings(json.load(f))
        except (OSError, ValueError):
            return sanitize_settings({})

    def _save_settings(self):
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=2)
        except OSError as e:
            self.toast(f"Impossibile salvare le impostazioni: {e}", THEME["red"], "✖")

    @staticmethod
    def _maximize(win):
        for a in (lambda: win.state("zoomed"), lambda: win.attributes("-zoomed", True)):
            try:
                a()
                return
            except tk.TclError:
                continue

    # ---- cache SQLite -----------------------------------------------------
    def _setup_db(self):
        try:
            self.conn = sqlite3.connect(CACHE_DB, check_same_thread=False)
            self.conn.execute("CREATE TABLE IF NOT EXISTS cache(target TEXT PRIMARY KEY, "
                              "data TEXT, ts DATETIME DEFAULT CURRENT_TIMESTAMP)")
            self.conn.commit()
        except sqlite3.Error:
            self.conn = None

    # la connessione è condivisa tra thread Tk e worker → serializzo gli accessi
    def _cache_put(self, t, d):
        if not self.conn:
            return
        try:
            with self._db_lock:
                self.conn.execute("INSERT OR REPLACE INTO cache(target,data) VALUES(?,?)",
                                  (t.lower(), json.dumps(d)))
                self.conn.commit()
        except (sqlite3.Error, TypeError, ValueError):
            pass

    def _cache_get(self, t):
        """Dossier in cache, oppure None se assente o di uno schema vecchio."""
        if not self.conn:
            return None
        try:
            with self._db_lock:
                r = self.conn.execute("SELECT data FROM cache WHERE target=?",
                                      (t.lower(),)).fetchone()
            d = json.loads(r[0]) if r else None
        except (sqlite3.Error, ValueError):
            return None
        return d if isinstance(d, dict) and d.get("schema") == DOSSIER_SCHEMA else None

    def _on_close(self):
        self.search_active = False
        for anim in (self.net_anim, self.geo_anim):
            if anim:
                anim.stop()
        if self.conn:
            try:
                with self._db_lock:
                    self.conn.close()
            except sqlite3.Error:
                pass
            self.conn = None
        self.root.destroy()

    # ---- comunicazione worker → UI ------------------------------------
    def _post(self, fn, *args):
        """Chiamabile da qualsiasi thread: esegue fn(*args) nel thread Tk."""
        self._ui_queue.put((fn, args))

    def _poll_queue(self):
        try:
            while True:
                fn, args = self._ui_queue.get_nowait()
                try:
                    fn(*args)
                except tk.TclError:
                    pass
        except queue.Empty:
            pass
        try:
            self.root.after(40, self._poll_queue)
        except tk.TclError:
            pass                                # finestra chiusa

    # ---- stile ttk ---------------------------------------------------------
    def _style(self):
        st = ttk.Style()
        try:
            st.theme_use("clam")
        except tk.TclError:
            pass
        st.configure("Orion.Vertical.TScrollbar", troughcolor=THEME["bg2"], background=THEME["line2"],
                     bordercolor=THEME["bg2"], arrowcolor=THEME["accent"], lightcolor=THEME["line2"],
                     darkcolor=THEME["line2"], gripcount=0, arrowsize=12, relief="flat")
        st.map("Orion.Vertical.TScrollbar",
               background=[("pressed", THEME["accent"]), ("active", mix(THEME["line2"], THEME["accent"], 0.5))])

    # ---- UI -------------------------------------------------------------
    def _build_ui(self):
        r = self.root
        self.hazard = tk.Canvas(r, height=22, bg="#140c02", highlightthickness=0)
        self.hazard.pack(fill="x")
        self.hazard.bind("<Configure>", lambda e: self._draw_hazard())
        self.header = HeaderBar(r, self.open_settings)
        self.header.btn.sound = None
        self.header.pack(fill="x")
        self.status = StatusBar(r)
        self.status.pack(side="bottom", fill="x")
        body = tk.Frame(r, bg=THEME["bg"])
        body.pack(fill="both", expand=True, padx=14, pady=(10, 8))
        left = tk.Frame(body, bg=THEME["bg"], width=392)
        left.pack(side="left", fill="y", padx=(0, 12))
        left.pack_propagate(False)
        right = tk.Frame(body, bg=THEME["bg"])
        right.pack(side="right", fill="both", expand=True)
        self._build_left(left)
        self._build_right(right)
        self._start_idle_anims()

    def _draw_hazard(self):
        c, amb = self.hazard, THEME["amber"]
        c.delete("all")
        w = c.winfo_width()
        for x0 in (0, w - 170):
            for x in range(x0 - 22, x0 + 170, 16):
                c.create_polygon(x, 22, x + 8, 22, x + 30, 0, x + 22, 0, fill=mix("#140c02", amb, 0.7),
                                 outline="")
        c.create_rectangle(170, 0, w - 170, 22, fill="#140c02", outline="")
        c.create_text(w / 2, 11, fill=amb, font=(UI, 9, "bold"),
                      text="⚠  SIMULAZIONE — nessuna ricerca reale · dati casuali a scopo di "
                           f"intrattenimento   ◆   {APP_NAME} · created by {CREATOR}")

    def _build_left(self, parent):
        pan, acc = THEME["panel"], THEME["accent"]
        ctrl = HudPanel(parent, "◢ TARGET ACQUISITION", acc)
        ctrl.pack(fill="x", pady=(0, 10))
        b = ctrl.body
        tk.Label(b, text="IDENTIFICATIVO BERSAGLIO", font=(MONO, 8, "bold"), bg=pan,
                 fg=THEME["dim"]).pack(anchor="w")
        row = tk.Frame(b, bg=THEME["bg2"], highlightthickness=1, highlightbackground=THEME["line2"])
        row.pack(fill="x", pady=(4, 10))
        tk.Label(row, text="▸", font=(MONO, 14, "bold"), bg=THEME["bg2"], fg=acc).pack(
            side="left", padx=(8, 2))
        self.input = tk.Entry(row, font=(MONO, 13), bg=THEME["bg2"], fg=THEME["white"],
                              insertbackground=acc, relief="flat", bd=0, highlightthickness=0,
                              selectbackground=mix(THEME["bg2"], acc, 0.4))
        self.input.pack(side="left", fill="x", expand=True, ipady=7)
        self.input.bind("<Return>", lambda e: self.start_search())
        self.input.bind("<FocusIn>", lambda e: row.config(highlightbackground=acc))
        self.input.bind("<FocusOut>", lambda e: row.config(highlightbackground=THEME["line2"]))
        NeonButton(row, "⌕", self.start_search, width=40, height=34, sound=None,
                   font=(UI, 13, "bold")).pack(side="right", padx=3, pady=2)
        self.launch_btn = NeonButton(b, "▶  AVVIA SCANSIONE OSINT", self.start_search, primary=True,
                                     height=46, width=340, font=(DISPLAY, 11, "bold"), sound=None)
        self.launch_btn.pack(fill="x", pady=(0, 6))
        brow = tk.Frame(b, bg=pan)
        brow.pack(fill="x")
        NeonButton(brow, "⌬  DEEP SCAN", self.deep_scan, color=THEME["accent2"], sound=None).pack(
            side="left", expand=True, fill="x", padx=(0, 4))
        NeonButton(brow, "■  STOP", self.stop_search, color=THEME["red"]).pack(
            side="left", expand=True, fill="x", padx=(4, 0))
        self.segbar = SegmentBar(b, segments=30, height=14)
        self.segbar.pack(fill="x", pady=(12, 4))
        self.progress_label = tk.Label(b, text="PRONTO", font=(MONO, 9, "bold"), bg=pan,
                                       fg=THEME["green"], anchor="w")
        self.progress_label.pack(fill="x")

        tools = HudPanel(parent, "◢ MODULI", THEME["green"])
        tools.pack(fill="x", pady=(0, 10))
        grid = tools.body
        specs = [("◈  GALLERIA", THEME["magenta"], self.open_gallery),
                 ("▶  SLIDESHOW", acc, self.open_slideshow),
                 ("⇩  ESPORTA", THEME["amber"], self.export_report),
                 ("⧉  COPIA", THEME["accent2"], self.copy_summary),
                 ("⚄  CASUALE", THEME["green"], self.random_target),
                 ("↻  RIGENERA", THEME["text"], self.regenerate)]
        for i, (txt, col, cmd) in enumerate(specs):
            NeonButton(grid, txt, cmd, color=col, height=34, sound=None).grid(
                row=i // 2, column=i % 2, sticky="ew", padx=3, pady=3)
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)

        ex = HudPanel(parent, "◢ BERSAGLI RAPIDI", THEME["magenta"])
        ex.pack(fill="x", pady=(0, 10))
        for i, name in enumerate(QUICK_TARGETS):
            NeonButton(ex.body, "⌖ " + name, lambda n=name: self.load_example(n), height=28,
                       color=THEME["text"], font=(UI, 9, "bold"), sound=None).grid(
                row=i // 2, column=i % 2, sticky="ew", padx=3, pady=2)
        ex.body.columnconfigure(0, weight=1)
        ex.body.columnconfigure(1, weight=1)

        feed = HudPanel(parent, "◢ LIVE FEED", THEME["accent2"])
        feed.pack(fill="both", expand=True)
        wrap, self.feed_text = make_console(feed.body, size=9)
        wrap.pack(fill="both", expand=True)
        for line in (f"ORION v{APP_VERSION} online · operator {CREATOR}",
                     "modalità SIMULAZIONE — nessuna ricerca reale",
                     "in attesa del bersaglio…"):
            self._feed(line)

    def _build_right(self, parent):
        self.tabs = TabView(parent, bg=THEME["bg"], font=(UI, 10, "bold"))
        self.tabs.pack(fill="both", expand=True)
        pan = THEME["panel"]
        self._build_overview(self.tabs.add("◈ INTELLIGENCE", bg=pan))
        self.social_inner = make_scroll(self.tabs.add("◉ SOCIAL", bg=pan), pan)
        self.ident_inner = make_scroll(self.tabs.add("⌬ IDENTITÀ", bg=pan), pan)
        for inner, msg in ((self.social_inner, "◉ SOCIAL MEDIA INTELLIGENCE"),
                           (self.ident_inner, "⌬ ANALISI IDENTITÀ MULTIPLE")):
            self._placeholder(inner, msg)
        tab_net = self.tabs.add("⬡ RETE", bg=THEME["bg"])
        self.net_canvas = tk.Canvas(tab_net, bg=THEME["bg"], highlightthickness=0)
        self.net_canvas.pack(fill="both", expand=True)
        tab_geo = self.tabs.add("⌖ MAPPA", bg=THEME["bg"])
        geo_bar = tk.Frame(tab_geo, bg=pan)
        geo_bar.pack(fill="x")
        NeonButton(geo_bar, "◎  APRI MAPPA 3D MAPBOX", self._open_mapbox_3d, width=250, height=32,
                   sound="open").pack(side="left", padx=8, pady=6)
        tk.Label(geo_bar, text="globo 3D + terreno nel browser · richiede token Mapbox (⚙ Impostazioni)",
                 font=(UI, 9), bg=pan, fg=THEME["dim"]).pack(side="left", padx=6)
        self.geo_canvas = tk.Canvas(tab_geo, bg=THEME["bg2"], highlightthickness=0)
        self.geo_canvas.pack(fill="both", expand=True)
        self.timeline = TimelineView(self.tabs.add("◷ TIMELINE", bg=pan))
        self.timeline.pack(fill="both", expand=True)
        cons = []
        for label in ("⊕ FOOTPRINT", "∿ PROFILO"):
            tab = self.tabs.add(label, bg=pan)
            wrap, txt = make_console(tab)
            wrap.pack(fill="both", expand=True, padx=12, pady=12)
            cons.append(txt)
        self.foot_text, self.behav_text = cons
        self._type(self.foot_text, [("⊕ DIGITAL FOOTPRINT\n", "h"), ("avvia una scansione", "k")])
        self._type(self.behav_text, [("∿ ANALISI COMPORTAMENTALE\n", "h"), ("avvia una scansione", "k")])

    def _placeholder(self, inner, title):
        for w in inner.winfo_children():
            w.destroy()
        tk.Label(inner, text=title, font=(DISPLAY, 13, "bold"), bg=THEME["panel"],
                 fg=THEME["accent"]).pack(anchor="w", padx=18, pady=(18, 4))
        tk.Label(inner, text="Nessun dato · avvia una scansione dal pannello TARGET ACQUISITION.",
                 font=(UI, 10), bg=THEME["panel"], fg=THEME["dim"]).pack(anchor="w", padx=18)

    def _build_overview(self, parent):
        pan = THEME["panel"]
        content = tk.Frame(parent, bg=pan)
        content.pack(fill="both", expand=True, padx=12, pady=12)
        self.banner = ThreatBanner(content)
        self.banner.pack(fill="x")
        tiles = tk.Frame(content, bg=pan)
        tiles.pack(fill="x", pady=8)
        self.stat_rows = {}
        specs = [("photos", "FOTO", THEME["magenta"]), ("identities", "IDENTITÀ", THEME["accent"]),
                 ("socials", "SOCIAL", THEME["accent2"]), ("emails", "EMAIL", THEME["accent"]),
                 ("breaches", "BREACH", THEME["red"]), ("records", "RECORD", THEME["amber"]),
                 ("exposure", "ESPOSIZIONE", THEME["green"]), ("privacy", "PRIVACY", THEME["magenta"]),
                 ("risk", "RISCHIO", THEME["red"]), ("confidence", "CONFIDENCE", THEME["accent"])]
        for i, (key, label, col) in enumerate(specs):
            t = StatTile(tiles, label, col)
            t.grid(row=i // 5, column=i % 5, sticky="ew", padx=3, pady=3)
            self.stat_rows[key] = t
        for c in range(5):
            tiles.columnconfigure(c, weight=1)
        low = tk.Frame(content, bg=pan)
        low.pack(fill="both", expand=True)
        rp = HudPanel(low, "◢ PROFILO RADAR", THEME["magenta"])
        rp.configure(width=340)
        rp.pack(side="right", fill="y", padx=(6, 0))
        rp.pack_propagate(False)
        self.radar = RadarView(rp.body)
        self.radar.pack(fill="both", expand=True)
        bp = HudPanel(low, "◢ BRIEFING", THEME["accent"])
        bp.pack(side="left", fill="both", expand=True)
        wrap, self.briefing_text = make_console(bp.body)
        wrap.pack(fill="both", expand=True)
        self._type(self.briefing_text, [("In attesa del bersaglio.\n", "h"), (f"by {CREATOR}", "k")])

    def _start_idle_anims(self):
        """Grafo e mappa 'in attesa' quando non c'è ancora un dossier."""
        if self.results or not self.settings.get("bg_anim", True):
            return
        self.net_anim = NetworkGraph(self.net_canvas, None, THEME["accent"])
        self.geo_anim = GeoMap(self.geo_canvas, None, THEME["accent"])

    def _rebuild_ui(self):
        """Ricostruisce l'interfaccia (es. dopo il cambio del colore accento)."""
        for anim in (self.net_anim, self.geo_anim):
            if anim:
                anim.stop()
        self.net_anim = self.geo_anim = None
        for w in self.root.winfo_children():
            if not isinstance(w, tk.Toplevel):
                w.destroy()
        self._typing.clear()
        self._style()
        self._build_ui()
        if self.results:
            self._render(self.results)

    # ---- feedback: stato, avanzamento, feed, toast -------------------
    def _status(self, msg, color=None):
        self.status.set_status(msg, color)

    def _progress(self, v, msg):
        self.segbar.set(v, active=self.search_active and v < 100)
        self.progress_label.config(text=msg.upper())
        self._feed(msg, "v" if v >= 100 else "k")

    def _feed(self, msg, tag="k"):
        t = self.feed_text
        try:
            t.config(state="normal")
            t.insert("end", datetime.now().strftime("%H:%M:%S  "), "track")
            t.insert("end", msg + "\n", tag)
            lines = int(t.index("end-1c").split(".")[0])
            if lines > 300:
                t.delete("1.0", f"{lines - 300}.0")
            t.see("end")
            t.config(state="disabled")
        except tk.TclError:
            pass

    def toast(self, text, color=None, icon="◆"):
        Toast(self.root, text, color, icon)

    def _need_results(self):
        if self.results:
            return True
        sfx("alert")
        self.toast("Prima esegui una scansione.", THEME["amber"], "!")
        return False

    def _type(self, widget, chunks):
        """Scrive i `chunks` [(testo, tag)] con effetto macchina da scrivere."""
        key = str(widget)
        prev = self._typing.pop(key, None)
        if prev:
            try:
                widget.after_cancel(prev)
            except tk.TclError:
                pass
        widget.config(state="normal")
        widget.delete("1.0", "end")
        items = [(t, g) for t, g in chunks if t]
        if not self.settings.get("typewriter", True):
            for text, tag in items:
                widget.insert("end", text, tag)
            widget.config(state="disabled")
            return
        per = max(6, sum(len(t) for t, _ in items) // 45)
        pos = [0, 0]

        def step():
            self._typing.pop(key, None)
            try:
                widget.config(state="normal")
                if widget.tag_ranges("cur"):
                    widget.delete("cur.first", "cur.last")
                n = per
                while n > 0 and pos[0] < len(items):
                    text, tag = items[pos[0]]
                    part = text[pos[1]:pos[1] + n]
                    widget.insert("end", part, tag)
                    n -= len(part)
                    pos[1] += len(part)
                    if pos[1] >= len(text):
                        pos[0], pos[1] = pos[0] + 1, 0
                if pos[0] < len(items):
                    widget.insert("end", "▌", "cur")
                    self._typing[key] = widget.after(16, step)
                widget.config(state="disabled")
            except tk.TclError:
                pass

        step()

    # ---- azioni strumenti ----------------------------------------------
    def load_example(self, name):
        self.input.delete(0, tk.END)
        self.input.insert(0, name)
        self.start_search()

    def deep_scan(self):
        self.start_search(fresh=True)

    def random_target(self):
        self.load_example(f"{random.choice(FIRST)} {random.choice(LAST)}")

    def regenerate(self):
        if not self.current_target:
            self._need_results()
            return
        self.input.delete(0, tk.END)
        self.input.insert(0, self.current_target)
        # variante casuale → dossier diverso per lo stesso nome (non salvato in cache)
        self.start_search(fresh=True, variant=random.randint(1, 999_999))

    def copy_summary(self):
        if not self._need_results():
            return
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(self._report_text(self.results))
            self._status("SOMMARIO COPIATO NEGLI APPUNTI", THEME["green"])
            self.toast("Sommario copiato negli appunti", THEME["green"], "⧉")
        except tk.TclError as e:
            self.toast(f"Copia non riuscita: {e}", THEME["red"], "✖")

    def export_report(self):
        if not self._need_results():
            return
        slug = _slug(self.results["target"])
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = filedialog.asksaveasfilename(
            parent=self.root, title="Esporta dossier (SIMULAZIONE)",
            initialfile=f"dossier_{slug}_{stamp}.txt", defaultextension=".txt",
            filetypes=[("Testo + JSON", "*.txt")])
        if not path:
            return
        base = os.path.splitext(path)[0]
        try:
            with open(base + ".txt", "w", encoding="utf-8") as f:
                f.write(self._report_text(self.results))
            with open(base + ".json", "w", encoding="utf-8") as f:
                json.dump(self.results, f, ensure_ascii=False, indent=2)
            self._status("DOSSIER ESPORTATO", THEME["green"])
            self._feed(f"dossier esportato → {os.path.basename(base)}.txt / .json", "ok")
            self.toast(f"Dossier esportato: {os.path.basename(base)}.txt + .json", THEME["green"], "⇩")
        except OSError as e:
            self.toast(f"Esportazione non riuscita: {e}", THEME["red"], "✖")

    def _report_text(self, d):
        s = d["summary"]
        L = [f"{'='*58}", f"  {APP_NAME}", f"  DOSSIER (SIMULAZIONE) — created by {CREATOR}",
             f"{'='*58}", f"Target      : {d['target']}", f"Generato    : {d['generated']}",
             f"Minaccia    : {s['threat']}   Confidence: {s['confidence']}%   Risk: {s['risk']}/100",
             "", "IDENTITÀ:"]
        for it in d["identities"]:
            L.append(f"  - {it['name']} ({it['confidence']}%) · {it['location']} · {it['role']} "
                     f"· minaccia {it['threat']}")
        L += ["", f"SOCIAL   : {len(d['socials'])} piattaforme",
              f"EMAIL    : {len(d['emails'])} ({d['footprint']['breaches']} compromesse)",
              f"FOTO     : {len(d['photos'])} asset",
              f"ESPOSIZ. : {d['footprint']['exposure']}/100   PRIVACY: {d['footprint']['privacy']}/100",
              "", "⚠ SIMULAZIONE: dati generati casualmente, nessun dato reale.",
              f"— created by {CREATOR} —"]
        return "\n".join(L)

    # ---- scansione ----------------------------------------------------
    def stop_search(self):
        if not self.search_active:
            return
        self.search_active = False
        self._search_id += 1                    # il worker in corso verrà ignorato
        self.launch_btn.config(state="normal")
        self._progress(0, "interrotto")
        self._status("SCANSIONE INTERROTTA", THEME["amber"])
        sfx("alert")
        self.toast("Scansione interrotta", THEME["amber"], "■")

    def start_search(self, fresh=False, variant=0):
        if self.search_active:                  # Invio / ⌕ / rapidi durante una scansione
            return
        target = self.input.get().strip()
        if not target:
            sfx("alert")
            self.toast("Inserisci il nome di un bersaglio", THEME["amber"], "!")
            self.input.focus_set()
            return
        if not PIL_OK:
            self.toast("Pillow mancante: pip install Pillow", THEME["red"], "✖")
            return
        self.search_active = True
        self._search_id += 1
        self.launch_btn.config(state="disabled")
        self.segbar.set(0, active=True)
        self._status(f"SCANSIONE OSINT ATTIVA: {target}", THEME["accent"])
        self._feed(f"▶ nuova scansione: {target}" + (" (deep)" if fresh and not variant else ""), "h2")
        sfx("scan")
        threading.Thread(target=self._run, args=(self._search_id, target, fresh, variant),
                         daemon=True).start()

    def _alive(self, sid):
        return self.search_active and sid == self._search_id

    def _run(self, sid, target, fresh, variant):
        """Thread di lavoro: NON tocca Tk direttamente, passa da self._post()."""
        steps = [(8, "Inizializzo i nodi..."), (22, "Accesso alle banche dati..."),
                 (38, "Deploy crawler deep web..."), (54, "Scansione social..."),
                 (68, "Mappatura footprint..."), (80, "Raccolta asset visivi..."),
                 (90, "Valutazione minaccia..."), (100, "Dossier pronto.")]
        for v, m in steps:
            if not self._alive(sid):
                return
            self._post(self._progress, v, m)
            time.sleep(0.11)
        data = None if (fresh or variant) else self._cache_get(target)
        if not data:
            data = build_dossier(target, variant)
        # volti IA (se attivi/online), con fallback; le varianti non vanno in cache
        self._ensure_faces(data, target, sid, cache=not variant)
        if self._alive(sid):
            self._post(self._on_search_done, sid, data)

    def _on_search_done(self, sid, data):
        if sid != self._search_id:              # nel frattempo STOP o nuova ricerca
            return
        self.results = data
        self.current_target = data["target"]
        try:
            self._render(data)
        finally:
            self.launch_btn.config(state="normal")
            self.search_active = False
            self.segbar.set(100, active=False)
            self.progress_label.config(text=f"DOSSIER PRONTO · {data['target'].upper()}")
        sfx("done")
        self.toast(f"Dossier pronto · {data['target']} · minaccia {data['summary']['threat']}",
                   threat_color(data["summary"]["threat"]), "✔")

    # ---- volti realistici (IA, NON reali) ------------------------------
    def _ensure_faces(self, data, target, sid, cache=True):
        for it in data["identities"]:
            it.setdefault("face_path", "")
        if not self.settings.get("real_faces", True):
            for it in data["identities"]:
                it["face_path"] = ""
            if cache:
                self._cache_put(target, data)
            return
        try:
            os.makedirs(FACES_DIR, exist_ok=True)
        except OSError:
            if cache:
                self._cache_put(target, data)
            return
        online = True
        n = len(data["identities"])
        for idx, it in enumerate(data["identities"]):
            cur = it.get("face_path", "")
            if cur and os.path.exists(cur):
                continue
            it["face_path"] = ""
            if not online or not self._alive(sid):
                continue
            self._post(self._progress, 96, f"Recupero volti IA… ({idx+1}/{n})")
            cp = os.path.join(FACES_DIR,
                              hashlib.md5(f"{target}|{idx}".encode()).hexdigest() + ".jpg")
            p = fetch_ai_face(cp)
            if p:
                it["face_path"] = p
            else:
                online = False       # probabilmente offline: smetto di riprovare
        if cache:
            self._cache_put(target, data)

    def _face_for(self, photo, data):
        """PIL del volto IA per la foto (in base all'identità), o None."""
        if not self.settings.get("real_faces", True) or not data:
            return None
        ids = data.get("identities", [])
        ix = photo.get("identity", 0)
        path = ids[ix].get("face_path", "") if ix < len(ids) else ""
        if not path or not os.path.exists(path):
            return None
        if path in self._face_cache:
            return self._face_cache[path]
        try:
            im = Image.open(path).convert("RGB")
            self._face_cache[path] = im
            return im
        except Exception:
            return None

    def _portrait_img(self, seed, size, caption, sub, matched, face):
        key = (seed, size, caption, sub, matched, THEME["accent"],
               self.settings.get("redacted", True), id(face) if face is not None else None)
        img = self._portrait_cache.get(key)
        if img is None:
            img = generate_portrait(seed, size, THEME["accent"], caption, sub, matched,
                                    self.settings.get("redacted", True), base_image=face)
            _cache_put_lru(self._portrait_cache, key, img, limit=120)
        return img

    def _portrait_for(self, data, photo, size):
        return self._portrait_img(f"{data['target']}|{photo['id']}", size, photo["identity_name"],
                                  f"{photo['tag']} · {photo['location']}", photo["matched"],
                                  self._face_for(photo, data))

    # ---- render ---------------------------------------------------------
    def _render(self, data):
        try:
            self._render_overview(data)
            self._render_social(data)
            self._render_identities(data)
            self.timeline.set(data["timeline"], data["target"])
            self._render_footprint(data)
            self._render_behavior(data)
            for anim in (self.net_anim, self.geo_anim):
                if anim:
                    anim.stop()
            self.net_anim = self.geo_anim = None
            self.net_canvas.delete("all")
            self.geo_canvas.delete("all")
            if self.settings.get("bg_anim", True):
                self.net_anim = NetworkGraph(self.net_canvas, data, THEME["accent"])
                self.geo_anim = GeoMap(self.geo_canvas, data, THEME["accent"])
            else:
                for cv, msg in [(self.net_canvas, "⬡ RETE"), (self.geo_canvas, "⌖ MAPPA")]:
                    cv.create_text(max(400, cv.winfo_width() // 2), 220, justify="center",
                                   text=f"{msg}\n(animazioni disattivate nelle impostazioni)",
                                   fill=THEME["dim"], font=(MONO, 13))
            self._status(f"COMPLETATO: {data['target']} — {len(data['photos'])} foto / "
                         f"{len(data['identities'])} identità · by {CREATOR}", THEME["green"])
            self.status.push_feed(f"dossier {data.get('case_id', '')} cifrato e archiviato")
            self._feed(f"✔ dossier {data.get('case_id', '')} · minaccia {data['summary']['threat']}",
                       "ok")
        except Exception as e:
            self.toast(f"Errore di visualizzazione: {e}", THEME["red"], "✖")

    def _render_overview(self, data):
        s, fp, idt = data["summary"], data["footprint"], data["identities"]
        self.banner.set(data)
        avg_social = int(sum(i["social_score"] for i in idt) / len(idt))
        self.radar.set_axes([("ESPOS.", fp["exposure"]), ("RISK", s["risk"]), ("SOCIAL", avg_social),
                             ("BREACH", min(100, fp["breaches"] * 25)),
                             ("VISIB.", 100 - fp["privacy"]), ("CONF.", s["confidence"])])
        tiles = {"photos": (len(data["photos"]), len(data["photos"]) / 20, ""),
                 "identities": (len(idt), len(idt) / 4, ""),
                 "socials": (len(data["socials"]), len(data["socials"]) / 8, ""),
                 "emails": (len(data["emails"]), len(data["emails"]) / 4, ""),
                 "breaches": (fp["breaches"], fp["breaches"] / 4, ""),
                 "records": (fp["records"], fp["records"] / 9, ""),
                 "exposure": (fp["exposure"], fp["exposure"] / 100, "/100"),
                 "privacy": (fp["privacy"], fp["privacy"] / 100, "/100"),
                 "risk": (s["risk"], s["risk"] / 100, "/100"),
                 "confidence": (s["confidence"], s["confidence"] / 100, "%")}
        for k, (v, ratio, suf) in tiles.items():
            self.stat_rows[k].set(v, ratio, suf)
        chunks = [(f"DOSSIER OSINT — {data['target']}\n", "h"),
                  (f"CASO {data.get('case_id', '—')}  ·  {data.get('classification', '')}  ·  "
                   f"operator {CREATOR}\n", "k"), ("─" * 52 + "\n\n", "sep"),
                  ("IDENTITÀ RILEVATE  ", "k"), (f"{len(idt)}\n", "v"),
                  ("  ▸ PRIMARIA   ", "k"), (f"{idt[0]['name']}\n", "v"),
                  ("  ▸ ALIAS      ", "k"), (", ".join(idt[0]["aliases"]) + "\n", "v"),
                  ("  ▸ LUOGO      ", "k"), (f"{idt[0]['location']}\n", "v"),
                  ("  ▸ RUOLO      ", "k"), (f"{idt[0]['role']}\n", "v"),
                  ("\nVISUAL INTEL\n", "h2"),
                  ("  email        ", "k"), (f"{len(data['emails'])} ", "v"),
                  (f"({fp['breaches']} compromesse)\n", "warn" if fp["breaches"] else "k"),
                  ("  social       ", "k"), (f"{len(data['socials'])} piattaforme\n", "v"),
                  ("  foto         ", "k"), (f"{len(data['photos'])} asset\n", "v"),
                  ("\nINDICI\n", "h2")]
        for name, v in (("esposizione", fp["exposure"]), ("rischio", s["risk"]),
                        ("privacy", fp["privacy"]), ("confidence", s["confidence"])):
            full, empty = tbar(v, 26)
            chunks += [(f"  {name:<13}", "k"), (full, "bar"), (empty, "track"), (f" {v}\n", "v")]
        chunks.append(("\nIDENTITY MATRIX\n", "h2"))
        for i, it in enumerate(idt):
            n_ph = sum(1 for p in data["photos"] if p["identity"] == i)
            chunks += [(f"  {i + 1}. {it['name']:<22}", "v"),
                       (f"{it['confidence']:>3}%  ·  {n_ph} foto  ·  ", "k"),
                       (f"{it['threat']}\n", {"LOW": "ok", "MEDIUM": "warn", "HIGH": "bad"}[it["threat"]])]
        self._type(self.briefing_text, chunks)

    def _section_header(self, inner, title, sub):
        pan = THEME["panel"]
        tk.Label(inner, text=title, font=(DISPLAY, 13, "bold"), bg=pan,
                 fg=THEME["accent"]).pack(anchor="w", padx=18, pady=(16, 0))
        tk.Label(inner, text=sub, font=(MONO, 9), bg=pan, fg=THEME["dim"]).pack(anchor="w", padx=18)

    def _render_social(self, data):
        inner = self.social_inner
        for w in inner.winfo_children():
            w.destroy()
        soc = data["socials"]
        ver = sum(1 for p in soc if p["verified"])
        self._section_header(inner, "◉ SOCIAL MEDIA INTELLIGENCE",
                             f"{len(soc)} piattaforme · {ver} verificate · dati SIMULATI · by {CREATOR}")
        grid = tk.Frame(inner, bg=THEME["panel"])
        grid.pack(fill="both", expand=True, padx=10, pady=8)
        ResponsiveGrid(grid, 304).set([SocialCard(grid, p) for p in soc])

    def _render_identities(self, data):
        inner = self.ident_inner
        for w in inner.winfo_children():
            w.destroy()
        ids = data["identities"]
        self._section_header(inner, "⌬ ANALISI IDENTITÀ MULTIPLE",
                             f"{len(ids)} profili correlati · ritratti NON reali · by {CREATOR}")
        grid = tk.Frame(inner, bg=THEME["panel"])
        grid.pack(fill="both", expand=True, padx=10, pady=8)
        cards = []
        for it in ids:
            img = self._portrait_img(f"{data['target']}|id{it['index']}", (240, 290), "", "", True,
                                     self._face_for({"identity": it["index"]}, data))
            thumb = img.resize((130, 157), Image.LANCZOS) if img is not None else None
            n_ph = sum(1 for p in data["photos"] if p["identity"] == it["index"])
            cards.append(IdentityCard(grid, it, thumb, n_ph))
        ResponsiveGrid(grid, 620).set(cards)

    def _render_footprint(self, data):
        fp = data["footprint"]
        chunks = [("⊕ DIGITAL FOOTPRINT\n", "h"), (f"created by {CREATOR} · SIMULAZIONE\n", "k"),
                  ("─" * 52 + "\n\n", "sep")]
        for k, v in [("domini registrati", fp["domains"]), ("piattaforme social", fp["platforms"]),
                     ("record pubblici", fp["records"]), ("data breach", fp["breaches"]),
                     ("presenza online", fp["presence"])]:
            chunks += [(f"  • {k:<22}", "k"), (f"{v}\n", "v")]
        chunks.append(("\nINDICI DI ESPOSIZIONE\n", "h2"))
        for name, v in (("esposizione", fp["exposure"]), ("visibilità", 100 - fp["privacy"]),
                        ("privacy", fp["privacy"])):
            full, empty = tbar(v, 30)
            chunks += [(f"  {name:<13}", "k"), (full, "bar"), (empty, "track"), (f" {v}/100\n", "v")]
        vtag = "bad" if fp["privacy"] < 40 else "warn"
        chunks += [("\n⚠ SICUREZZA\n", "h2"),
                   ("  vulnerabilità   ", "k"),
                   (("ALTA" if fp["privacy"] < 40 else "MEDIA") + "\n", vtag),
                   ("\n▸ RACCOMANDAZIONI\n", "h2"),
                   ("  ▸ sorveglianza multi-identità continua\n", "k"),
                   ("  ▸ analisi di tutti gli asset foto\n", "k"),
                   (f"  ▸ report generato da {CREATOR}\n", "k")]
        self._type(self.foot_text, chunks)

    def _render_behavior(self, data):
        b, fin = data["behavior"], data["finance"]
        chunks = [("∿ ANALISI COMPORTAMENTALE\n", "h"), (f"created by {CREATOR} · SIMULAZIONE\n", "k"),
                  ("─" * 52 + "\n\n", "sep")]
        for k, v in [("attività online", b["online"]), ("abitudini d'acquisto", b["shopping"]),
                     ("frequenza viaggi", b["travel"]), ("engagement sociale", b["engagement"])]:
            chunks += [(f"  • {k:<22}", "k"), (f"{v}\n", "v")]
        st = b["sentiment"]
        stag = "ok" if st > 20 else "bad" if st < -10 else "warn"
        full, empty = tbar((st + 40) / 110 * 100, 30)
        chunks += [("\nSENTIMENT\n", "h2"), ("  ", "k"), (full, "bar"), (empty, "track"),
                   (f" {st:+d}\n", stag),
                   ("\n◆ PROFILO FINANZIARIO (simulato)\n", "h2"),
                   ("  • carte                 ", "k"), (f"{fin['cards']}  {fin['last4']}\n", "v"),
                   ("  • conti                 ", "k"), (f"{fin['accounts']}\n", "v"),
                   ("  • wallet crypto         ", "k"), (f"{fin['wallets']}\n", "v"),
                   ("  • transazioni/mese      ", "k"), (f"{fin['monthly']}\n", "v"),
                   ("\n▸ PREDITTIVA\n", "h2"),
                   ("  ▸ priorità monitoraggio: MOLTO ALTA\n", "warn"),
                   (f"  ▸ analisi by {CREATOR}\n", "k")]
        self._type(self.behav_text, chunks)

    # ===================================================================
    #  GALLERIA + DETTAGLIO + SLIDESHOW
    # ===================================================================
    def open_gallery(self):
        if not self._need_results():
            return
        if not PIL_OK:
            self.toast("Pillow mancante: pip install Pillow", THEME["red"], "✖")
            return
        data = self.results          # fisso i dati: una nuova scansione non li cambia qui
        win = tk.Toplevel(self.root)
        win.title(f"◈ CINEMATIC GALLERY — by {CREATOR}")
        win.configure(bg=THEME["bg"])
        _go_fullscreen(win)
        sfx("open")
        canvas = tk.Canvas(win, bg=THEME["bg"], highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        win.focus_set()
        if self.settings.get("skip_intro"):
            self._gallery(win, canvas, data)
            return
        state = {"intro": None, "shown": False}

        def show(_=None):
            if state["shown"]:          # Spazio/Invio + fine intro → una sola galleria
                return
            state["shown"] = True
            if state["intro"]:
                state["intro"].stop()
            self._gallery(win, canvas, data)

        def close(_=None):
            if state["intro"]:
                state["intro"].stop()
            win.destroy()

        win.bind("<Escape>", close)
        win.bind("<space>", show)
        win.bind("<Return>", show)
        scale = INTRO_SCALE.get(self.settings["intro_speed"], 1.0)
        state["intro"] = CinematicIntro(canvas, data["target"], on_done=show,
                                        accent=THEME["accent"], scale=scale,
                                        fx=self.settings.get("fx", True))

    def _gallery(self, win, canvas, data):
        if not win.winfo_exists():
            return
        win.unbind("<space>")
        win.unbind("<Return>")
        try:
            win.attributes("-fullscreen", False)
        except tk.TclError:
            pass
        canvas.destroy()
        win.geometry("1500x900")
        self._maximize(win)
        win.bind("<Escape>", lambda e: win.destroy())
        s = data["summary"]
        head = tk.Canvas(win, height=96, bg=THEME["bg"], highlightthickness=0)
        head.pack(fill="x")
        btns = tk.Frame(head, bg=THEME["bg"])
        NeonButton(btns, "▶  SLIDESHOW", self.open_slideshow, width=150, height=36,
                   sound=None).pack(side="left", padx=4)
        NeonButton(btns, "✕  CHIUDI  (Esc)", win.destroy, color=THEME["red"], width=160,
                   height=36).pack(side="left", padx=4)
        faces_on = self.settings.get("real_faces", True) and any(
            it.get("face_path") for it in data["identities"])
        note = ("SIMULAZIONE — volti generati da IA (thispersondoesnotexist): NON sono persone reali."
                if faces_on else "SIMULAZIONE — ritratti generati proceduralmente, non persone reali.")

        def draw_head(_=None):
            w, h, acc = head.winfo_width(), 96, THEME["accent"]
            head.delete("all")
            if PIL_OK:
                head.bg_img = ImageTk.PhotoImage(render_backdrop(w, h, acc, (0.2, 0.0), 14))
                head.create_image(0, 0, image=head.bg_img, anchor="nw")
            head.create_line(0, h - 1, w, h - 1, fill=mix(THEME["bg"], acc, 0.5))
            head.create_text(26, 28, anchor="w", text="◈ DOSSIER VISIVO", fill=acc,
                             font=(DISPLAY, 20, "bold"))
            head.create_text(28 + text_w("◈ DOSSIER VISIVO", (DISPLAY, 20, "bold")) + 16, 30,
                             anchor="w", text=data["target"].upper(), fill="#ffffff",
                             font=(DISPLAY, 16, "bold"))
            x = 26
            for label, col in ((f"{len(data['identities'])} IDENTITÀ", acc),
                               (f"{len(data['photos'])} ASSET", THEME["magenta"]),
                               (f"MINACCIA {s['threat']}", threat_color(s["threat"])),
                               (f"CONF {s['confidence']}%", THEME["accent2"]),
                               (f"created by {CREATOR}", THEME["dim"])):
                f = (MONO, 9, "bold")
                tw = text_w(label, f) + 16
                head.create_polygon(chamfer(x, 52, x + tw, 70, 5), fill=mix(THEME["bg"], col, 0.12),
                                    outline=col)
                head.create_text(x + tw / 2, 61, text=label, fill=col, font=f)
                x += tw + 6
            head.create_text(26, 84, anchor="w", text=note, fill=THEME["amber"], font=(UI, 9, "italic"))
            head.create_window(w - 18, 34, window=btns, anchor="e")

        head.bind("<Configure>", draw_head)
        tv = TabView(win, bg=THEME["bg"])
        tv.pack(fill="both", expand=True, padx=16, pady=(8, 14))
        for it in data["identities"]:
            sub = [p for p in data["photos"] if p["identity"] == it["index"]]
            tv.add(f"⌬ {it['name'].upper()}  ({len(sub)})", bg=THEME["bg"],
                   builder=lambda f, it=it, sub=sub: self._photo_grid(f, data, sub, it))
        tv.add(f"◈ TUTTI  ({len(data['photos'])})", bg=THEME["bg"],
               builder=lambda f: self._photo_grid(f, data, data["photos"], None))

    def _photo_grid(self, frame, data, photos, ident):
        bg = THEME["bg"]
        inner = make_scroll(frame, bg)
        if ident:
            it = ident
            tk.Label(inner, text=f"⌬ {it['name']}  ·  conf {it['confidence']}%  ·  {it['location']}  ·  "
                                 f"{it['role']}  ·  minaccia {it['threat']}", font=(UI, 11, "bold"),
                     bg=bg, fg=THEME["accent"], anchor="w").pack(fill="x", padx=18, pady=(14, 4))
        grid = tk.Frame(inner, bg=bg)
        grid.pack(fill="both", expand=True, padx=10, pady=6)
        if not photos:
            tk.Label(grid, text="Nessun asset per questa identità.", font=(UI, 13),
                     bg=bg, fg=THEME["dim"]).pack(pady=40)
            return
        rg = ResponsiveGrid(grid, 236, pad=8)
        cards = []

        def batch(i=0):                    # le card "entrano" a gruppi: UI sempre reattiva
            if not grid.winfo_exists():
                return
            for p in photos[i:i + 3]:
                cards.append(PhotoCard(grid, self._portrait_for(data, p, (220, 266)), p,
                                       lambda p=p: self._detail(data, p)))
            rg.set(cards)
            if i + 3 < len(photos):
                grid.after(10, batch, i + 3)

        batch()

    def _detail(self, data, photo):
        sfx("open")
        win = tk.Toplevel(self.root)
        win.title(f"◈ {photo['identity_name']} — {photo['tag']} · by {CREATOR}")
        win.configure(bg=THEME["bg"])
        win.geometry("1020x640")
        win.bind("<Escape>", lambda e: win.destroy())
        body = tk.Frame(win, bg=THEME["bg"])
        body.pack(fill="both", expand=True, padx=20, pady=20)
        face = self._face_for(photo, data)
        big = self._portrait_for(data, photo, (400, 480))
        cv = tk.Canvas(body, width=400, height=480, bg="#000000", highlightthickness=1,
                       highlightbackground=THEME["line2"])
        cv.image = ImageTk.PhotoImage(big)
        cv.create_image(0, 0, image=cv.image, anchor="nw")
        cv.pack(side="left", anchor="n")
        geo = (200, 240, 104, 144) if face is not None else (200, 192, 70, 88)
        FaceScan(cv, 400, 480, THEME["accent"], photo["matched"], geo)
        right = HudPanel(body, "◢ ANALISI ASSET", THEME["accent"])
        right.pack(side="left", fill="both", expand=True, padx=(18, 0))
        wrap, txt = make_console(right.body, size=11)
        wrap.pack(fill="both", expand=True)
        full, empty = tbar(photo["intel"] * 10, 20)
        rows = [("DATI ASSET\n", "h"), ("identità   ", "k"), (photo["identity_name"] + "\n", "v"),
                ("tipo       ", "k"), (photo["tag"] + "\n", "v"),
                ("data       ", "k"), (photo["date"] + "\n", "v"),
                ("luogo      ", "k"), (photo["location"] + "\n", "v"),
                ("qualità    ", "k"), (photo["quality"] + "\n", "v"),
                ("fonte      ", "k"), (photo["source"] + "\n\n", "v"),
                ("METRICHE\n", "h"), ("intel      ", "k"), (full, "bar"), (empty, "track"),
                (f" {photo['intel']}/10\n", "v"),
                ("match      ", "k"), (("SÌ" if photo["matched"] else "NO") + "\n",
                                       "ok" if photo["matched"] else "bad"),
                ("classe     ", "k"), ("Open Source (SIM)\n\n", "v"),
                ("ANALISI\n", "h"), ("riconoscimento facciale  ", "k"), ("disponibile\n", "ok"),
                ("metadati                 ", "k"), ("estratti\n", "ok"),
                ("geolocalizzazione        ", "k"), ("verificata\n\n", "ok"),
                (f"— created by {CREATOR} · SIMULAZIONE —\n", "k")]
        self._type(txt, rows)
        NeonButton(right.body, "✕  CHIUDI", win.destroy, color=THEME["red"], width=140,
                   height=34).pack(anchor="e", pady=(10, 0))

    def open_slideshow(self):
        if not self._need_results() or not self.results.get("photos"):
            return
        if not PIL_OK:
            self.toast("Pillow mancante: pip install Pillow", THEME["red"], "✖")
            return
        sfx("open")
        data = self.results
        Slideshow(self.root, data, self.settings, lambda p: self._face_for(p, data))

    def _open_mapbox_3d(self):
        if not self._need_results():
            return
        token = (self.settings.get("mapbox_token", "").strip()
                 or os.environ.get("MAPBOX_TOKEN", "").strip())
        if not token:
            self.toast("Serve un token Mapbox (pk.…): inseriscilo nelle impostazioni",
                       THEME["amber"], "!")
            self.open_settings()
            return
        try:
            page = build_mapbox_html(self.results, token)
            path = os.path.join(tempfile.gettempdir(),
                                f"orion_map_{_slug(self.results['target'])}.html")
            with open(path, "w", encoding="utf-8") as f:
                f.write(page)
            webbrowser.open(Path(path).as_uri())
            self._status("MAPPA 3D MAPBOX APERTA NEL BROWSER", THEME["green"])
            self.toast("Mappa 3D aperta nel browser", THEME["green"], "◎")
        except OSError as e:
            self.toast(f"Mapbox 3D: {e}", THEME["red"], "✖")

    # ---- IMPOSTAZIONI ---------------------------------------------------
    def open_settings(self):
        if self._settings_win is not None and self._settings_win.winfo_exists():
            self._settings_win.lift()           # già aperta: niente doppioni
            self._settings_win.focus_force()
            return
        sfx("open")
        win = self._settings_win = tk.Toplevel(self.root)
        win.title(f"⚙ Impostazioni — {CREATOR}")
        win.configure(bg=THEME["bg"])
        win.geometry("940x720")
        win.minsize(880, 660)
        win.transient(self.root)
        win.bind("<Escape>", lambda e: win.destroy())
        s = self.settings
        v = {k: (tk.BooleanVar if isinstance(d, bool) else tk.DoubleVar if isinstance(d, float)
                 else tk.StringVar)(value=s[k]) for k, d in DEFAULT_SETTINGS.items()}

        head = tk.Canvas(win, height=70, bg=THEME["bg"], highlightthickness=0)
        head.pack(fill="x")

        def draw_head(_=None):
            w, acc = head.winfo_width(), THEME["accent"]
            head.delete("all")
            head.create_text(24, 28, anchor="w", text="⚙  IMPOSTAZIONI", fill=acc,
                             font=(DISPLAY, 18, "bold"))
            head.create_text(26, 52, anchor="w", fill=THEME["dim"], font=(MONO, 9),
                             text=f"ORION v{APP_VERSION} · operator {CREATOR} · Esc per chiudere")
            head.create_line(0, 69, w, 69, fill=mix(THEME["bg"], acc, 0.5))
            head.create_line(0, 67, w * 0.25, 67, fill=acc, width=2)

        head.bind("<Configure>", draw_head)
        cols = tk.Frame(win, bg=THEME["bg"])
        cols.pack(fill="both", expand=True, padx=16, pady=12)
        L = tk.Frame(cols, bg=THEME["bg"])
        R = tk.Frame(cols, bg=THEME["bg"])
        L.pack(side="left", fill="both", expand=True, padx=(0, 8))
        R.pack(side="left", fill="both", expand=True, padx=(8, 0))

        def panel(parent, title, color):
            p = HudPanel(parent, title, color)
            p.pack(fill="x", pady=(0, 10))
            return p.body

        def label(parent, text):
            tk.Label(parent, text=text, font=(MONO, 8, "bold"), bg=THEME["panel"],
                     fg=THEME["dim"]).pack(anchor="w", pady=(8, 2))

        b = panel(L, "◢ INTRO CINEMATICA", THEME["accent"])
        ToggleSwitch(b, "Salta l'intro della galleria", v["skip_intro"]).pack(anchor="w")
        label(b, "DURATA INTRO")
        Segmented(b, [("CORTA", "corta"), ("MEDIA", "media"), ("LUNGA", "lunga")],
                  v["intro_speed"]).pack(anchor="w")
        b = panel(L, "◢ SLIDESHOW", THEME["accent2"])
        label(b, "SECONDI PER FOTO")
        NeonSlider(b, v["slideshow_sec"], 1.5, 8.0, 0.5).pack(anchor="w", fill="x")
        b = panel(L, "◢ AVVIO", THEME["magenta"])
        ToggleSwitch(b, "Schermata d'avvio (splash)", v["splash"]).pack(anchor="w")
        label(b, "VIDEO D'AVVIO  (il tuo video con overlay MAIKGOST)")
        vrow = tk.Frame(b, bg=THEME["panel"])
        vrow.pack(fill="x")
        tk.Entry(vrow, textvariable=v["splash_video"], font=(MONO, 9), bg=THEME["bg2"],
                 fg=THEME["accent"], insertbackground=THEME["accent"], relief="flat",
                 highlightbackground=THEME["line2"], highlightthickness=1).pack(
            side="left", fill="x", expand=True, ipady=6)

        def browse_video():
            p = filedialog.askopenfilename(
                parent=win, title="Scegli il video d'avvio",
                filetypes=[("Video", "*.mp4 *.mov *.avi *.mkv *.webm *.m4v"), ("Tutti", "*.*")])
            if p:
                v["splash_video"].set(p)

        NeonButton(vrow, "SFOGLIA…", browse_video, width=112, height=30).pack(side="left", padx=(6, 0))
        cv2_note = "OpenCV OK" if CV2_OK else "installa opencv-python per il video"
        tk.Label(b, text=f"vuoto = scena olografica · auto-rileva intro.mp4\n{cv2_note} · senza audio",
                 font=(UI, 8), bg=THEME["panel"], fg=THEME["dim"], justify="left").pack(
            anchor="w", pady=(4, 0))
        b = panel(L, "◢ AUDIO", THEME["amber"])
        arow = tk.Frame(b, bg=THEME["panel"])
        arow.pack(fill="x")
        ToggleSwitch(arow, "Effetti sonori", v["sound"]).pack(side="left")
        NeonButton(arow, "▶  TEST", lambda: self.sfx.play("done", force=True), width=90, height=28,
                   color=THEME["amber"], sound=None).pack(side="right")

        b = panel(R, "◢ GRAFICA & EFFETTI", THEME["green"])
        for key, text in (("bg_anim", "Animazioni rete / mappa"),
                          ("fx", "Effetti glitch e pioggia di dati"),
                          ("typewriter", "Testo 'macchina da scrivere'"),
                          ("redacted", "Barra REDACTED sui volti"),
                          ("real_faces", "Volti IA realistici (internet)")):
            ToggleSwitch(b, text, v[key]).pack(anchor="w")
        tk.Label(b, text="i volti IA sono generati: NON sono persone reali", font=(UI, 8),
                 bg=THEME["panel"], fg=THEME["dim"]).pack(anchor="w", padx=(52, 0))
        b = panel(R, "◢ COLORE ACCENTO", THEME["accent"])
        Swatches(b, ACCENTS, v["accent"]).pack(anchor="w")
        b = panel(R, "◢ MAPPA 3D — TOKEN MAPBOX", THEME["accent2"])
        tk.Entry(b, textvariable=v["mapbox_token"], font=(MONO, 10), bg=THEME["bg2"], show="•",
                 fg=THEME["accent"], insertbackground=THEME["accent"], relief="flat",
                 highlightbackground=THEME["line2"], highlightthickness=1).pack(fill="x", ipady=6)
        tk.Label(b, text="token pk.… da account.mapbox.com\nresta salvato solo su questo PC",
                 font=(UI, 8), bg=THEME["panel"], fg=THEME["dim"], justify="left").pack(
            anchor="w", pady=(4, 0))

        def save():
            old_accent = self.settings["accent"]
            self.settings = sanitize_settings({k: (var.get().strip() if isinstance(var, tk.StringVar)
                                                   else var.get()) for k, var in v.items()})
            THEME["accent"] = self.settings["accent"]
            self._save_settings()
            win.destroy()
            if self.settings["accent"] != old_accent:
                self._rebuild_ui()
            elif self.results:
                self._render(self.results)
            else:
                for anim in (self.net_anim, self.geo_anim):
                    if anim:
                        anim.stop()
                self.net_anim = self.geo_anim = None
                self.net_canvas.delete("all")
                self.geo_canvas.delete("all")
                self._start_idle_anims()
            self._status("IMPOSTAZIONI SALVATE", THEME["green"])
            sfx("done")
            self.toast("Impostazioni salvate", THEME["green"], "✔")

        bot = tk.Frame(win, bg=THEME["bg"])
        bot.pack(fill="x", padx=16, pady=(0, 16))
        NeonButton(bot, "✔  SALVA IMPOSTAZIONI", save, primary=True, width=260, height=42,
                   font=(DISPLAY, 11, "bold"), sound=None).pack(side="right")
        NeonButton(bot, "ANNULLA", win.destroy, color=THEME["dim"], width=120, height=42).pack(
            side="right", padx=8)
        tk.Label(bot, text=f"created by {CREATOR}", font=(UI, 8), bg=THEME["bg"],
                 fg=THEME["dim"]).pack(side="left")


def main():
    print(f"◈ {APP_NAME} — by {CREATOR}")
    print("  ⚠  Gioco/simulazione: nessuna ricerca reale, dati casuali.")
    if not PIL_OK:
        print("  ✗ Pillow non installato → pip install Pillow")
    try:
        root = tk.Tk()
    except tk.TclError as e:
        print("GUI non disponibile (display?):", e)
        return
    try:
        resolve_fonts(root)
        SpyOSINTApp(root)
        root.mainloop()
    except Exception as e:
        print("Errore fatale:", e)
        raise


if __name__ == "__main__":
    main()
