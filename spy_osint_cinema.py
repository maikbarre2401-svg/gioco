#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ORION // SPY OSINT CINEMA PRO  —  simulatore d'intelligence cinematografico.

⚠️  SIMULAZIONE / GIOCO
    Questo programma NON esegue nessuna ricerca reale, non contatta internet
    e non raccoglie dati su nessuna persona. TUTTI i dati (nomi, foto, email,
    profili, ecc.) sono generati in modo casuale e deterministico a partire dal
    testo digitato, a puro scopo di intrattenimento / dimostrazione di UI.
    È un "gioco" con estetica da film di spionaggio: nessun dato è reale.

Requisiti: Python 3.8+, tkinter (di serie con Python), Pillow (`pip install Pillow`).
"""

import hashlib
import json
import math
import os
import random
import sqlite3
import threading
import time
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, scrolledtext, ttk

# --- Pillow: obbligatorio per la grafica cinematografica -------------------
try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageTk, ImageOps
    PIL_OK = True
except Exception:  # pragma: no cover - dipende dall'ambiente
    PIL_OK = False


# ===========================================================================
#  TEMA / PALETTE
# ===========================================================================
THEME = {
    "bg":       "#05060b",
    "bg2":      "#090c16",
    "panel":    "#0f1320",
    "panel2":   "#151a2b",
    "card":     "#12172a",
    "line":     "#1e2444",
    "accent":   "#00e5ff",   # ciano
    "accent2":  "#3ba9ff",   # blu
    "magenta":  "#ff2bd6",
    "green":    "#39ff14",
    "amber":    "#ffb020",
    "red":      "#ff3b5c",
    "text":     "#e2e8ff",
    "dim":      "#8791b8",
    "white":    "#ffffff",
    "black":    "#000000",
}

MONO = "Consolas"       # sostituito automaticamente da Tk se assente
UI = "Segoe UI"
MATRIX_CHARS = "アカサタナハマヤラабвг0123456789ABCDEF$#@%&<>/*ΞΨΛØ§"


# ===========================================================================
#  UTILITÀ COLORE / FONT
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


_FONT_CACHE = {}
_TTF_CANDIDATES = [
    "consola.ttf", "Consolas.ttf", "arial.ttf", "Arial.ttf",
    "DejaVuSansMono.ttf", "DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/Library/Fonts/Arial.ttf",
]


def load_font(size, bold=False):
    """Carica un font TTF con fallback robusto (per la grafica Pillow)."""
    if not PIL_OK:
        return None
    key = (size, bold)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    candidates = list(_TTF_CANDIDATES)
    if bold:
        candidates = ["consolab.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf",
                      "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"] + candidates
    font = None
    for name in candidates:
        try:
            font = ImageFont.truetype(name, size)
            break
        except Exception:
            continue
    if font is None:
        try:
            font = ImageFont.load_default(size)  # Pillow >= 10.1
        except Exception:
            font = ImageFont.load_default()
    _FONT_CACHE[key] = font
    return font


# ===========================================================================
#  GENERATORE DI RITRATTI "DA SORVEGLIANZA" (procedurali, non persone reali)
# ===========================================================================
_VIGNETTE_CACHE = {}


def _vignette_mask(size, strength=0.9):
    key = (size, round(strength, 2))
    if key in _VIGNETTE_CACHE:
        return _VIGNETTE_CACHE[key]
    base = Image.radial_gradient("L").resize(size)           # 0 al centro, 255 ai bordi
    mask = base.point(lambda v: int(v * strength))
    _VIGNETTE_CACHE[key] = mask
    return mask


def _vertical_gradient(size, top, bottom):
    w, h = size
    grad = Image.new("RGB", (1, h))
    tp, bt = hex_to_rgb(top), hex_to_rgb(bottom)
    px = grad.load()
    for y in range(h):
        t = y / max(1, h - 1)
        px[0, y] = tuple(int(lerp(tp[i], bt[i], t)) for i in range(3))
    return grad.resize((w, h))


def generate_portrait(seed, size=(300, 360), accent=None, caption="", subcaption="",
                      matched=True):
    """
    Crea un ritratto stilizzato in stile "fotogramma di sorveglianza".
    È una silhouette astratta generata proceduralmente: NON è una persona reale.
    Deterministico rispetto a `seed`.
    """
    if not PIL_OK:
        return None
    accent = accent or THEME["accent"]
    w, h = size
    rng = random.Random(int(hashlib.md5(str(seed).encode()).hexdigest(), 16))

    # Palette di sfondo (blu notte / verde militare / seppia archivio)
    palettes = [
        ("#0a1424", "#132a44"), ("#0c1a16", "#173a2c"),
        ("#1a1410", "#3a2c1c"), ("#101024", "#241a3a"),
        ("#08121a", "#123044"),
    ]
    top, bottom = rng.choice(palettes)
    img = _vertical_gradient((w, h), top, bottom)

    acc = hex_to_rgb(accent)

    # --- Silhouette busto testa+spalle su layer separato, poi sfocata -------
    # (figura astratta "ritratto redatto": NON è una persona reale)
    cx = w // 2 + rng.randint(-12, 12)
    head_rx = int(w * rng.uniform(0.16, 0.19))
    head_ry = int(head_rx * rng.uniform(1.18, 1.32))   # testa più alta che larga
    head_cy = int(h * 0.40)
    neutral = (150, 158, 182)
    sil = tuple(int(lerp(hex_to_rgb(bottom)[i], neutral[i], 0.52)) for i in range(3))
    sil_dark = tuple(int(c * 0.55) for c in sil)
    rim = tuple(int(lerp(sil[i], 255, 0.6)) for i in range(3))
    lit_left = rng.random() < 0.5

    sil_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sil_layer)
    # spalle
    sw = int(w * rng.uniform(0.66, 0.84))
    sh_top = head_cy + int(head_ry * 0.7)
    sd.ellipse([cx - sw // 2, sh_top, cx + sw // 2, h + int(h * 0.4)], fill=sil + (255,))
    # collo
    nw = int(head_rx * 0.75)
    sd.polygon([(cx - nw, sh_top + 4), (cx + nw, sh_top + 4),
                (cx + nw - 4, head_cy), (cx - nw + 4, head_cy)], fill=sil + (255,))
    # testa
    sd.ellipse([cx - head_rx, head_cy - head_ry, cx + head_rx, head_cy + head_ry],
               fill=sil + (255,))
    # capelli (metà superiore, tono scuro)
    sd.pieslice([cx - head_rx - 2, head_cy - head_ry - 4,
                 cx + head_rx + 2, head_cy + int(head_ry * 0.35)],
                start=180, end=360, fill=sil_dark + (255,))
    # ombra sul lato non illuminato
    if lit_left:
        sd.chord([cx, head_cy - head_ry, cx + head_rx, head_cy + head_ry],
                 -90, 90, fill=sil_dark + (110,))
    else:
        sd.chord([cx - head_rx, head_cy - head_ry, cx, head_cy + head_ry],
                 90, 270, fill=sil_dark + (110,))
    # rim light (bordo illuminato)
    arc_box = [cx - head_rx, head_cy - head_ry, cx + head_rx, head_cy + head_ry]
    if lit_left:
        sd.arc(arc_box, 100, 250, fill=rim + (230,), width=3)
    else:
        sd.arc(arc_box, -70, 80, fill=rim + (230,), width=3)
    sil_layer = sil_layer.filter(ImageFilter.GaussianBlur(1.4))
    img = Image.alpha_composite(img.convert("RGBA"), sil_layer).convert("RGB")
    draw = ImageDraw.Draw(img, "RGBA")

    # Grana / rumore (veloce, in C)
    try:
        noise = Image.effect_noise((w, h), 26).convert("L")
        img = Image.composite(img, Image.new("RGB", (w, h), (12, 14, 20)),
                              noise.point(lambda v: 235))
        img = Image.blend(img, Image.merge("RGB", (noise, noise, noise)), 0.06)
    except Exception:
        pass

    draw = ImageDraw.Draw(img, "RGBA")

    # Scanline CRT
    for y in range(0, h, 3):
        draw.line([(0, y), (w, y)], fill=(0, 0, 0, 60))

    # Vignettatura
    dark = Image.new("RGB", (w, h), (0, 0, 0))
    img = Image.composite(dark, img, _vignette_mask((w, h), 0.85))
    draw = ImageDraw.Draw(img, "RGBA")

    # Box di "face-lock" con angoli (riconoscimento facciale)
    bx0, by0 = cx - head_rx - 10, head_cy - head_ry - 8
    bx1, by1 = cx + head_rx + 10, head_cy + head_ry + 14
    tick = 16
    for (px, py, sx, sy) in [(bx0, by0, 1, 1), (bx1, by0, -1, 1),
                             (bx0, by1, 1, -1), (bx1, by1, -1, -1)]:
        draw.line([(px, py), (px + sx * tick, py)], fill=acc, width=2)
        draw.line([(px, py), (px, py + sy * tick)], fill=acc, width=2)
    # piccolo reticolo centrale sul volto
    fcy = head_cy - int(head_ry * 0.15)
    r = int(head_rx * 0.45)
    draw.ellipse([cx - r, fcy - r, cx + r, fcy + r], outline=acc + (150,), width=1)
    draw.line([(cx - r - 6, fcy), (cx + r + 6, fcy)], fill=acc + (110,), width=1)
    draw.line([(cx, fcy - r - 6), (cx, fcy + r + 6)], fill=acc + (110,), width=1)

    # Cornice HUD + angoli
    m = 6
    draw.rectangle([m, m, w - m, h - m], outline=acc + (120,), width=1)
    L = 22
    for (ax, ay, dx, dy) in [(m, m, 1, 1), (w - m, m, -1, 1),
                             (m, h - m, 1, -1), (w - m, h - m, -1, -1)]:
        draw.line([(ax, ay), (ax + dx * L, ay)], fill=acc, width=3)
        draw.line([(ax, ay), (ax, ay + dy * L)], fill=acc, width=3)

    fsmall = load_font(12, bold=True)
    fmono = load_font(11)
    # Etichette tecniche
    cam_id = f"CAM-{rng.randint(1,9)}{rng.choice('ABKZ')}{rng.randint(10,99)}"
    draw.text((m + 8, m + 6), cam_id, font=fmono, fill=acc)
    draw.text((w - m - 66, m + 6), "● REC", font=fsmall, fill=hex_to_rgb(THEME["red"]))
    ts = f"{rng.randint(0,23):02d}:{rng.randint(0,59):02d}:{rng.randint(0,59):02d}"
    draw.text((m + 8, h - m - 20), ts, font=fmono, fill=acc)
    conf = rng.randint(78, 99)
    tag = f"MATCH {conf}.{rng.randint(0,9)}%" if matched else "NO MATCH"
    col = hex_to_rgb(THEME["green"]) if matched else hex_to_rgb(THEME["red"])
    draw.text((w - m - 96, h - m - 20), tag, font=fsmall, fill=col)

    # Barra caption in basso
    if caption:
        bar_h = 34
        draw.rectangle([0, h - bar_h, w, h], fill=(0, 0, 0, 170))
        fcap = load_font(14, bold=True)
        draw.text((10, h - bar_h + 4), caption[:24], font=fcap, fill=hex_to_rgb(THEME["white"]))
        if subcaption:
            draw.text((10, h - bar_h + 20), subcaption[:34], font=fmono,
                      fill=hex_to_rgb(THEME["dim"]))

    return img


# ===========================================================================
#  LIVELLO DATI  —  dossier simulato deterministico
# ===========================================================================
FIRST_NAMES = ["Marco", "Luca", "Andrea", "Giulia", "Sara", "Elena", "Matteo",
               "Alex", "Nina", "Ivan", "Sofia", "Dario", "Karim", "Mila"]
LAST_NAMES = ["Rossi", "Bianchi", "Esposito", "Romano", "Ferrari", "Costa",
              "Moreau", "Keller", "Petrov", "Nakamura", "Vidal", "Okoye"]
CITIES = ["Roma, IT", "Milano, IT", "Napoli, IT", "Torino, IT", "London, UK",
          "Berlin, DE", "Paris, FR", "Zürich, CH", "Lisboa, PT", "Wien, AT"]
ROLES = ["Consulente", "Sviluppatore", "Analista", "Imprenditore", "Fotografo",
         "Ricercatore", "Broker", "Giornalista", "Ingegnere", "DJ"]
PLATFORMS = [("Instagram", "◎"), ("Facebook", "f"), ("X / Twitter", "✕"),
             ("LinkedIn", "in"), ("TikTok", "♪"), ("YouTube", "▶"),
             ("Telegram", "✈"), ("GitHub", "⌥")]
EMAIL_DOMAINS = ["gmail.com", "proton.me", "outlook.com", "icloud.com", "fastmail.com"]
PHOTO_TAGS = ["Profilo social", "Foto professionale", "Evento pubblico",
              "Foto di gruppo", "Conferenza", "Vacanza", "Documento",
              "Articolo stampa", "Serata", "Sede di lavoro", "Sport", "Viaggio"]


def _slug(name):
    parts = name.lower().split()
    return "".join(parts) if parts else "unknown"


def build_dossier(target):
    """Genera un dossier simulato, deterministico rispetto al nome."""
    target = (target or "Sconosciuto").strip()
    seed = int(hashlib.md5(target.lower().encode()).hexdigest(), 16)
    rng = random.Random(seed)

    n_identities = rng.randint(2, 4)
    identities = []
    for i in range(n_identities):
        if i == 0:
            name = target
            status = "IDENTITÀ PRIMARIA"
            conf = rng.randint(88, 99)
        else:
            if rng.random() < 0.5 and len(target.split()) >= 2:
                name = f"{target.split()[0]} {rng.choice(LAST_NAMES)}"
            else:
                name = f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"
            status = "IDENTITÀ SECONDARIA"
            conf = rng.randint(58, 84)
        first = name.split()[0].lower()
        identities.append({
            "index": i,
            "name": name,
            "status": status,
            "confidence": conf,
            "age": rng.randint(24, 57),
            "location": rng.choice(CITIES),
            "role": rng.choice(ROLES),
            "threat": rng.choice(["LOW", "LOW", "MEDIUM", "MEDIUM", "HIGH"]),
            "aliases": [f"{first}_{rng.randint(10,99)}",
                        f"{first}.{rng.choice(['ofc','real','x','hq'])}"],
            "social_score": rng.randint(45, 96),
            "biometrics": {
                "eyes": rng.choice(["Marroni", "Verdi", "Azzurri", "Nocciola"]),
                "height": f"{rng.randint(160, 195)} cm",
                "build": rng.choice(["Snella", "Media", "Atletica", "Robusta"]),
                "marks": rng.choice(["Nessuno", "Tatuaggio avambraccio",
                                     "Cicatrice sopracciglio", "Occhiali"]),
            },
        })

    # Foto: ognuna assegnata a un'identità (indice esatto -> filtro affidabile)
    photos = []
    n_photos = rng.randint(12, 20)
    for i in range(n_photos):
        owner = rng.randint(0, n_identities - 1)
        photos.append({
            "id": i,
            "identity": owner,
            "identity_name": identities[owner]["name"],
            "tag": rng.choice(PHOTO_TAGS),
            "date": f"20{rng.randint(20,25)}-{rng.randint(1,12):02d}-{rng.randint(1,28):02d}",
            "location": rng.choice(CITIES),
            "quality": rng.choice(["SD", "HD", "HD", "4K"]),
            "intel": rng.randint(4, 10),
            "source": rng.choice([p[0] for p in PLATFORMS] + ["Archivio stampa",
                                                              "Registro pubblico"]),
            "matched": rng.random() > 0.15,
        })

    socials = []
    for plat, glyph in rng.sample(PLATFORMS, rng.randint(5, len(PLATFORMS))):
        socials.append({
            "platform": plat, "glyph": glyph,
            "handle": "@" + _slug(target)[:14] + rng.choice(["", "_", str(rng.randint(1, 99))]),
            "followers": f"{rng.randint(1, 240)}K",
            "activity": rng.choice(["Molto alta", "Alta", "Media", "Bassa"]),
            "last_seen": f"{rng.randint(1, 20)}g fa",
            "verified": rng.random() < 0.35,
            "posts": rng.randint(40, 1200),
        })

    emails = []
    for dom in rng.sample(EMAIL_DOMAINS, rng.randint(2, 4)):
        emails.append({
            "address": f"{_slug(target)[:16]}@{dom}",
            "breached": rng.random() < 0.4,
            "leaks": rng.randint(0, 4),
            "type": rng.choice(["Personale", "Lavoro", "Backup"]),
        })

    footprint = {
        "domains": rng.randint(2, 11),
        "platforms": len(socials),
        "records": rng.randint(3, 9),
        "breaches": sum(1 for e in emails if e["breached"]),
        "exposure": rng.randint(40, 96),      # visibilità pubblica
        "privacy": rng.randint(12, 60),       # punteggio privacy
        "presence": rng.choice(["Estesa", "Molto alta", "Globale"]),
    }

    behavior = {
        "online": rng.choice(["Notturno", "Diurno", "Continuo", "Irregolare"]),
        "shopping": rng.choice(["Tech", "Lusso", "Viaggi", "Vario"]),
        "travel": rng.choice(["Frequente", "Internazionale", "Occasionale"]),
        "engagement": rng.choice(["Molto alto", "Alto", "Medio"]),
        "sentiment": rng.randint(-40, 70),
    }

    finance = {  # valori mascherati, chiaramente fittizi
        "cards": rng.randint(1, 5),
        "accounts": rng.randint(1, 4),
        "wallets": rng.randint(0, 3),
        "last4": f"•••• {rng.randint(1000,9999)}",
        "monthly": f"€{rng.randint(2,18)}.{rng.randint(0,9)}k",
    }

    threat_level = identities[0]["threat"]
    risk = min(99, int(footprint["exposure"] * 0.6 + (100 - footprint["privacy"]) * 0.4))

    return {
        "simulation": True,
        "target": target,
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "summary": {
            "threat": threat_level,
            "confidence": identities[0]["confidence"],
            "clearance": f"LEVEL {rng.randint(2,4)}",
            "risk": risk,
        },
        "identities": identities,
        "photos": photos,
        "socials": socials,
        "emails": emails,
        "footprint": footprint,
        "behavior": behavior,
        "finance": finance,
    }


# ===========================================================================
#  MOTORE INTRO CINEMATOGRAFICO (frame-based, NON bloccante)
# ===========================================================================
class CinematicIntro:
    """
    Intro a tutto schermo su un Canvas: matrix rain, campo di particelle,
    radar rotante, titolo con glitch, effetto macchina da scrivere, boot log
    e chiusura a serranda. Tutto guidato da un unico loop `after` (~30 fps),
    interrompibile e sicuro se la finestra viene chiusa.
    """
    FPS_MS = 33

    def __init__(self, canvas, target, on_done, accent=None):
        self.c = canvas
        self.target = (target or "UNKNOWN").upper()
        self.on_done = on_done
        self.accent = accent or THEME["accent"]
        self.frame = 0
        self.after_id = None
        self.running = True
        self.layers_ready = False
        self.matrix = []
        self.particles = []
        self.radar_angle = 0.0
        self.boot_log = []
        self.log_lines = [
            "conn secure://orion.grid  [OK]",
            "handshake AES-256-GCM ..... [OK]",
            "spoofing egress node CH-07 .. [OK]",
            "querying data lattice ....... [..]",
            "biometric hash lookup ....... [..]",
            "facial vector match ......... [OK]",
            "assembling visual dossier ... [..]",
            "decrypting media cache ...... [OK]",
            "access token elevated ....... [OK]",
        ]
        self.timeline = [
            ("◈ O R I O N", 46, self.accent, 26),
            ("GLOBAL INTELLIGENCE GRID", 22, THEME["dim"], 20),
            ("ESTABLISHING ENCRYPTED UPLINK", 20, THEME["green"], 24),
            (f"TARGET  ▸  {self.target}", 30, THEME["white"], 32),
            ("CROSS-REFERENCING DATA NODES", 20, self.accent, 24),
            ("◎ BIOMETRIC SIGNATURES MATCHED", 22, THEME["magenta"], 26),
            ("COMPILING VISUAL DOSSIER", 20, THEME["amber"], 24),
            ("◉ ACCESS GRANTED", 40, THEME["green"], 30),
        ]
        self.total = sum(p[3] for p in self.timeline) + 8
        self.shutter = 0
        self._tick()

    # ---- ciclo ----------------------------------------------------------
    def _dims(self):
        w = self.c.winfo_width()
        h = self.c.winfo_height()
        if w <= 1 or h <= 1:
            w, h = self.c.winfo_screenwidth(), self.c.winfo_screenheight()
        return w, h

    def _ensure_layers(self, w, h):
        if self.layers_ready:
            return
        cols = max(10, w // 22)
        self.matrix = []
        for i in range(cols):
            self.matrix.append({
                "x": i * 22 + 6,
                "y": random.randint(-h, 0),
                "speed": random.uniform(6, 20),
                "len": random.randint(6, 18),
                "chars": [random.choice(MATRIX_CHARS) for _ in range(20)],
            })
        self.particles = [{
            "x": random.uniform(0, w), "y": random.uniform(0, h),
            "vx": random.uniform(-0.3, 0.3), "vy": random.uniform(-1.2, -0.3),
            "r": random.uniform(1, 2.6),
        } for _ in range(70)]
        self.layers_ready = True

    def _tick(self):
        if not self.running or not self.c.winfo_exists():
            return
        try:
            w, h = self._dims()
            self._ensure_layers(w, h)
            self.c.delete("all")
            self.c.create_rectangle(0, 0, w, h, fill=THEME["bg"], outline="")
            self._draw_matrix(w, h)
            self._draw_radar(w, h)
            self._draw_particles(w, h)
            self._draw_scanlines(w, h)
            self._draw_timeline(w, h)
            self._draw_frame_hud(w, h)
        except tk.TclError:
            return

        self.frame += 1
        if self.frame >= self.total:
            self._close_shutter(w, h)
            return
        self.after_id = self.c.after(self.FPS_MS, self._tick)

    # ---- livelli --------------------------------------------------------
    def _draw_matrix(self, w, h):
        acc = self.accent
        for col in self.matrix:
            col["y"] += col["speed"]
            if col["y"] - col["len"] * 16 > h:
                col["y"] = random.randint(-h // 2, 0)
                col["speed"] = random.uniform(6, 20)
            x = col["x"]
            for k in range(col["len"]):
                y = col["y"] - k * 16
                if y < 0 or y > h:
                    continue
                if k == 0:
                    color = THEME["white"]
                elif k < 3:
                    color = acc
                else:
                    t = k / col["len"]
                    color = lerp_color(THEME["green"], THEME["bg"], t)
                ch = col["chars"][(k + self.frame) % len(col["chars"])]
                self.c.create_text(x, y, text=ch, fill=color,
                                   font=(MONO, 12), anchor="c")

    def _draw_radar(self, w, h):
        cx, cy = w // 2, int(h * 0.44)
        R = int(min(w, h) * 0.34)
        for rr in range(1, 5):
            r = R * rr / 4
            self.c.create_oval(cx - r, cy - r, cx + r, cy + r,
                               outline=lerp_color(self.accent, THEME["bg"], 0.72), width=1)
        self.c.create_line(cx - R, cy, cx + R, cy,
                           fill=lerp_color(self.accent, THEME["bg"], 0.8))
        self.c.create_line(cx, cy - R, cx, cy + R,
                           fill=lerp_color(self.accent, THEME["bg"], 0.8))
        self.radar_angle = (self.radar_angle + 0.13) % (2 * math.pi)
        for i in range(10):
            a = self.radar_angle - i * 0.05
            t = i / 10
            x = cx + R * math.cos(a)
            y = cy + R * math.sin(a)
            self.c.create_line(cx, cy, x, y,
                               fill=lerp_color(self.accent, THEME["bg"], t), width=2)
        bx = cx + R * math.cos(self.radar_angle)
        by = cy + R * math.sin(self.radar_angle)
        self.c.create_oval(bx - 3, by - 3, bx + 3, by + 3, fill=self.accent, outline="")

    def _draw_particles(self, w, h):
        for p in self.particles:
            p["x"] += p["vx"]
            p["y"] += p["vy"]
            if p["y"] < 0:
                p["y"] = h
                p["x"] = random.uniform(0, w)
            r = p["r"]
            self.c.create_oval(p["x"] - r, p["y"] - r, p["x"] + r, p["y"] + r,
                               fill=lerp_color(self.accent, THEME["bg"], 0.35), outline="")

    def _draw_scanlines(self, w, h):
        band = (self.frame * 6) % h
        self.c.create_rectangle(0, band, w, band + 60,
                                fill=lerp_color(THEME["bg"], self.accent, 0.06), outline="")

    def _draw_timeline(self, w, h):
        # fase corrente in base al frame
        f = self.frame - 8
        acc = 0
        phase = None
        local = 0
        for text, size, color, dur in self.timeline:
            if f < acc + dur:
                phase = (text, size, color, dur)
                local = f - acc
                break
            acc += dur
        if phase is None:
            phase = self.timeline[-1]
            local = phase[3]
        text, size, color, dur = phase

        reveal = max(0.0, min(1.0, local / max(1, dur * 0.55)))
        shown = text[:max(1, int(len(text) * reveal))]
        cursor = "▌" if (self.frame // 6) % 2 == 0 and reveal < 1 else ""
        cx, cy = w // 2, int(h * 0.44)

        # glitch RGB occasionale
        if (self.frame // 4) % 6 == 0:
            self.c.create_text(cx + 3, cy, text=shown, font=(MONO, size, "bold"),
                               fill=THEME["red"], anchor="c")
            self.c.create_text(cx - 3, cy, text=shown, font=(MONO, size, "bold"),
                               fill=self.accent, anchor="c")
        self.c.create_text(cx, cy, text=shown + cursor, font=(MONO, size, "bold"),
                           fill=color, anchor="c")

        # barra di progresso globale
        pw = int(w * 0.5)
        px = (w - pw) // 2
        py = int(h * 0.82)
        prog = min(1.0, self.frame / self.total)
        self.c.create_rectangle(px, py, px + pw, py + 10,
                                outline=self.accent, width=1)
        self.c.create_rectangle(px, py, px + int(pw * prog), py + 10,
                                fill=self.accent, outline="")
        self.c.create_text(px + pw + 44, py + 5, text=f"{int(prog*100):3d}%",
                           fill=self.accent, font=(MONO, 12, "bold"), anchor="c")

        # boot log
        idx = min(len(self.log_lines), self.frame // 14)
        vis = self.log_lines[:idx][-8:]
        for i, line in enumerate(vis):
            self.c.create_text(30, py + 40 + i * 16, text="> " + line,
                               fill=lerp_color(THEME["green"], THEME["bg"], 0.15 + i * 0.02),
                               font=(MONO, 10), anchor="w")

    def _draw_frame_hud(self, w, h):
        m = 16
        L = 34
        for (ax, ay, dx, dy) in [(m, m, 1, 1), (w - m, m, -1, 1),
                                 (m, h - m, 1, -1), (w - m, h - m, -1, -1)]:
            self.c.create_line(ax, ay, ax + dx * L, ay, fill=self.accent, width=2)
            self.c.create_line(ax, ay, ax, ay + dy * L, fill=self.accent, width=2)
        self.c.create_text(m + 6, m - 2, anchor="nw", font=(MONO, 10),
                           fill=self.accent, text="ORION//INTEL  ● LIVE FEED")
        self.c.create_text(w - m - 6, m - 2, anchor="ne", font=(MONO, 10),
                           fill=THEME["dim"],
                           text=datetime.now().strftime("%H:%M:%S"))
        self.c.create_text(w // 2, h - 8, anchor="s", font=(MONO, 9),
                           fill=THEME["dim"],
                           text="◦ SIMULAZIONE — dati generati casualmente, nessun dato reale ◦")

    # ---- chiusura -------------------------------------------------------
    def _close_shutter(self, w, h):
        if not self.running or not self.c.winfo_exists():
            return
        self.shutter += 1
        steps = 12
        cover = int((h / 2) * (self.shutter / steps))
        self.c.create_rectangle(0, 0, w, cover, fill=THEME["black"], outline="")
        self.c.create_rectangle(0, h - cover, w, h, fill=THEME["black"], outline="")
        self.c.create_line(0, cover, w, cover, fill=self.accent, width=2)
        self.c.create_line(0, h - cover, w, h - cover, fill=self.accent, width=2)
        if self.shutter >= steps:
            self.stop()
            if callable(self.on_done):
                self.on_done()
            return
        self.after_id = self.c.after(self.FPS_MS, lambda: self._close_shutter(w, h))

    def stop(self):
        self.running = False
        if self.after_id:
            try:
                self.c.after_cancel(self.after_id)
            except Exception:
                pass
            self.after_id = None


# ===========================================================================
#  APPLICAZIONE PRINCIPALE
# ===========================================================================
class SpyOSINTApp:
    def __init__(self, root):
        self.root = root
        self.root.title("◈ ORION // SPY OSINT CINEMA PRO — SIMULATORE")
        self.root.configure(bg=THEME["bg"])
        self.root.geometry("1500x920")
        self.root.minsize(1120, 720)
        self._maximize(self.root)

        self.results = None
        self.current_target = ""
        self.search_active = False
        self.surveillance_level = 1
        self._img_refs = []          # anti garbage-collector per PhotoImage
        self._title_phase = 0.0

        self._setup_db()
        self._build_style()
        self._build_ui()
        self._animate_title()
        self._tick_clock()

    # ---- utilità finestra ----------------------------------------------
    @staticmethod
    def _maximize(win):
        for attempt in (lambda: win.state("zoomed"),
                        lambda: win.attributes("-zoomed", True)):
            try:
                attempt()
                return
            except Exception:
                continue

    # ---- database (cache opzionale) ------------------------------------
    def _setup_db(self):
        try:
            self.conn = sqlite3.connect("orion_cache.db", check_same_thread=False)
            self.conn.execute(
                "CREATE TABLE IF NOT EXISTS cache "
                "(target TEXT PRIMARY KEY, data TEXT, ts DATETIME DEFAULT CURRENT_TIMESTAMP)")
            self.conn.commit()
        except Exception as e:
            print("DB non disponibile:", e)
            self.conn = None

    def _cache_put(self, target, data):
        if not self.conn:
            return
        try:
            self.conn.execute("INSERT OR REPLACE INTO cache(target, data) VALUES(?,?)",
                              (target.lower(), json.dumps(data)))
            self.conn.commit()
        except Exception:
            pass

    def _cache_get(self, target):
        if not self.conn:
            return None
        try:
            row = self.conn.execute("SELECT data FROM cache WHERE target=?",
                                    (target.lower(),)).fetchone()
            return json.loads(row[0]) if row else None
        except Exception:
            return None

    # ---- stile ttk ------------------------------------------------------
    def _build_style(self):
        st = ttk.Style()
        try:
            st.theme_use("clam")
        except Exception:
            pass
        st.configure("Orion.Horizontal.TProgressbar",
                     troughcolor=THEME["panel2"], background=THEME["accent"],
                     borderwidth=0, thickness=14)
        st.configure("Orion.TNotebook", background=THEME["bg"], borderwidth=0)
        st.configure("Orion.TNotebook.Tab", background=THEME["panel"],
                     foreground=THEME["dim"], padding=[18, 8],
                     font=(UI, 10, "bold"), borderwidth=0)
        st.map("Orion.TNotebook.Tab",
               background=[("selected", THEME["panel2"])],
               foreground=[("selected", THEME["accent"])])

    # ---- costruzione UI -------------------------------------------------
    def _build_ui(self):
        # Banner simulazione (onestà: è un gioco)
        banner = tk.Frame(self.root, bg="#20140a")
        banner.pack(fill="x")
        tk.Label(banner,
                 text="⚠  MODALITÀ SIMULAZIONE — Nessuna ricerca reale. "
                      "Tutti i dati sono generati casualmente a scopo di intrattenimento.",
                 bg="#20140a", fg=THEME["amber"], font=(UI, 10, "bold")).pack(pady=4)

        main = tk.Frame(self.root, bg=THEME["bg"])
        main.pack(fill="both", expand=True, padx=16, pady=(10, 16))

        # Header
        header = tk.Frame(main, bg=THEME["bg"])
        header.pack(fill="x", pady=(0, 12))
        self.title_label = tk.Label(header, text="◈  O R I O N   //   SPY OSINT CINEMA PRO",
                                    font=(MONO, 22, "bold"), bg=THEME["bg"], fg=THEME["accent"])
        self.title_label.pack(side="left")
        self.clock_label = tk.Label(header, text="", font=(MONO, 12),
                                    bg=THEME["bg"], fg=THEME["dim"])
        self.clock_label.pack(side="right")

        self.status_label = tk.Label(main, text="● SISTEMA OPERATIVO — in attesa del bersaglio",
                                     font=(MONO, 10, "bold"), bg=THEME["bg"], fg=THEME["green"],
                                     anchor="w")
        self.status_label.pack(fill="x", pady=(0, 10))

        body = tk.Frame(main, bg=THEME["bg"])
        body.pack(fill="both", expand=True)

        left = tk.Frame(body, bg=THEME["bg"], width=380)
        left.pack(side="left", fill="y", padx=(0, 16))
        left.pack_propagate(False)
        right = tk.Frame(body, bg=THEME["bg"])
        right.pack(side="right", fill="both", expand=True)

        self._build_left(left)
        self._build_right(right)

    def _panel(self, parent, title, color):
        f = tk.LabelFrame(parent, text=" " + title + " ", font=(UI, 11, "bold"),
                          bg=THEME["panel"], fg=color, relief="flat", bd=0,
                          highlightbackground=THEME["line"], highlightthickness=1,
                          padx=14, pady=12)
        return f

    def _build_left(self, parent):
        ctrl = self._panel(parent, "🎯 MISSION CONTROL", THEME["accent"])
        ctrl.pack(fill="x", pady=(0, 14))

        tk.Label(ctrl, text="NOME BERSAGLIO", font=(UI, 9, "bold"),
                 bg=THEME["panel"], fg=THEME["dim"]).pack(anchor="w")
        row = tk.Frame(ctrl, bg=THEME["panel"])
        row.pack(fill="x", pady=(4, 12))
        self.input = tk.Entry(row, font=(MONO, 13), bg=THEME["bg2"], fg=THEME["accent"],
                              insertbackground=THEME["accent"], relief="flat",
                              highlightbackground=THEME["line"], highlightthickness=1)
        self.input.pack(side="left", fill="x", expand=True, ipady=6)
        self.input.bind("<Return>", lambda e: self.start_search())
        tk.Button(row, text="⌕", font=(UI, 13, "bold"), bg=THEME["accent"], fg="black",
                  relief="flat", width=3, command=self.start_search).pack(side="left", padx=(6, 0))

        self.launch_btn = tk.Button(ctrl, text="▶  AVVIA SCANSIONE OSINT",
                                    font=(UI, 12, "bold"), bg=THEME["accent"], fg="black",
                                    relief="flat", height=2, command=self.start_search)
        self.launch_btn.pack(fill="x", pady=(0, 6))
        brow = tk.Frame(ctrl, bg=THEME["panel"])
        brow.pack(fill="x")
        tk.Button(brow, text="🌐 DEEP SCAN", font=(UI, 10, "bold"), bg=THEME["panel2"],
                  fg=THEME["accent"], relief="flat",
                  command=self.deep_scan).pack(side="left", expand=True, fill="x", padx=(0, 4))
        tk.Button(brow, text="⏹ STOP", font=(UI, 10, "bold"), bg=THEME["panel2"],
                  fg=THEME["red"], relief="flat",
                  command=self.stop_search).pack(side="left", expand=True, fill="x", padx=(4, 0))

        self.progress = ttk.Progressbar(ctrl, style="Orion.Horizontal.TProgressbar",
                                        mode="determinate")
        self.progress.pack(fill="x", pady=(12, 4))
        self.progress_label = tk.Label(ctrl, text="pronto", font=(MONO, 9),
                                       bg=THEME["panel"], fg=THEME["green"], anchor="w")
        self.progress_label.pack(fill="x")

        # esempi
        ex = self._panel(parent, "⚡ BERSAGLI RAPIDI", THEME["magenta"])
        ex.pack(fill="x", pady=(0, 14))
        for name in ["Mario Rossi", "John Smith", "Anna Müller", "Luca Bianchi", "Marco Esposito"]:
            tk.Button(ex, text="🎯  " + name, font=(UI, 10), bg=THEME["card"],
                      fg=THEME["text"], relief="flat", anchor="w",
                      activebackground=THEME["panel2"], activeforeground=THEME["accent"],
                      command=lambda n=name: self.load_example(n)).pack(fill="x", pady=2)

        # galleria
        gal = self._panel(parent, "💀 CINEMATIC GALLERY", THEME["amber"])
        gal.pack(fill="x")
        tk.Label(gal, text="Intro a schermo intero + riconoscimento\nfacciale + identità multiple.",
                 font=(UI, 9), bg=THEME["panel"], fg=THEME["dim"], justify="left").pack(anchor="w")
        tk.Button(gal, text="💀  LANCIA CINEMATIC GALLERY", font=(UI, 12, "bold"),
                  bg=THEME["magenta"], fg="black", relief="flat", height=2,
                  command=self.open_gallery).pack(fill="x", pady=(8, 0))

    def _build_right(self, parent):
        self.notebook = ttk.Notebook(parent, style="Orion.TNotebook")
        self.notebook.pack(fill="both", expand=True)

        self.tab_overview = tk.Frame(self.notebook, bg=THEME["panel"])
        self.tab_social = tk.Frame(self.notebook, bg=THEME["panel"])
        self.tab_ident = tk.Frame(self.notebook, bg=THEME["panel"])
        self.tab_foot = tk.Frame(self.notebook, bg=THEME["panel"])
        self.tab_behav = tk.Frame(self.notebook, bg=THEME["panel"])
        self.notebook.add(self.tab_overview, text="📊 INTELLIGENCE")
        self.notebook.add(self.tab_social, text="👥 SOCIAL")
        self.notebook.add(self.tab_ident, text="🕵 IDENTITÀ")
        self.notebook.add(self.tab_foot, text="🌐 FOOTPRINT")
        self.notebook.add(self.tab_behav, text="📈 COMPORTAMENTO")

        self._build_overview(self.tab_overview)
        self.social_text = self._make_console(self.tab_social,
                                              "👥 SOCIAL MEDIA — avvia una scansione")
        self.ident_text = self._make_console(self.tab_ident,
                                             "🕵 IDENTITÀ MULTIPLE — avvia una scansione")
        self.foot_text = self._make_console(self.tab_foot,
                                            "🌐 DIGITAL FOOTPRINT — avvia una scansione")
        self.behav_text = self._make_console(self.tab_behav,
                                             "📈 ANALISI COMPORTAMENTALE — avvia una scansione")

    def _make_console(self, parent, placeholder):
        wrap = tk.Frame(parent, bg=THEME["panel"])
        wrap.pack(fill="both", expand=True, padx=12, pady=12)
        txt = scrolledtext.ScrolledText(wrap, bg=THEME["bg2"], fg=THEME["text"],
                                        font=(MONO, 10), insertbackground=THEME["accent"],
                                        relief="flat", padx=12, pady=10, wrap="word",
                                        highlightbackground=THEME["line"], highlightthickness=1)
        txt.pack(fill="both", expand=True)
        txt.tag_config("h", foreground=THEME["accent"], font=(MONO, 12, "bold"))
        txt.tag_config("k", foreground=THEME["dim"])
        txt.tag_config("v", foreground=THEME["white"])
        txt.tag_config("ok", foreground=THEME["green"])
        txt.tag_config("warn", foreground=THEME["amber"])
        txt.tag_config("bad", foreground=THEME["red"])
        txt.insert("1.0", placeholder)
        txt.config(state="disabled")
        return txt

    def _build_overview(self, parent):
        content = tk.Frame(parent, bg=THEME["panel"])
        content.pack(fill="both", expand=True, padx=12, pady=12)

        threat = tk.Frame(content, bg=THEME["card"], highlightbackground=THEME["line"],
                          highlightthickness=1)
        threat.pack(fill="x", pady=(0, 12))
        self.threat_label = tk.Label(threat, text="BERSAGLIO NON IDENTIFICATO",
                                     font=(MONO, 20, "bold"), bg=THEME["card"], fg=THEME["dim"])
        self.threat_label.pack(pady=(12, 4))
        self.confidence_label = tk.Label(threat,
                                         text="CONFIDENCE: —   |   CLEARANCE: —   |   RISK: —",
                                         font=(MONO, 11), bg=THEME["card"], fg=THEME["dim"])
        self.confidence_label.pack(pady=(0, 12))

        grid = tk.Frame(content, bg=THEME["panel"])
        grid.pack(fill="both", expand=True)

        bf = tk.Frame(grid, bg=THEME["panel"])
        bf.pack(side="left", fill="both", expand=True, padx=(0, 8))
        tk.Label(bf, text="📋 BRIEFING", font=(UI, 11, "bold"),
                 bg=THEME["panel"], fg=THEME["accent"], anchor="w").pack(fill="x")
        self.briefing_text = scrolledtext.ScrolledText(
            bf, bg=THEME["bg2"], fg=THEME["text"], font=(MONO, 10),
            insertbackground=THEME["accent"], relief="flat", padx=10, pady=8, wrap="word",
            highlightbackground=THEME["line"], highlightthickness=1)
        self.briefing_text.pack(fill="both", expand=True, pady=(6, 0))
        for tag, col, fnt in [("h", THEME["accent"], (MONO, 12, "bold")),
                              ("k", THEME["dim"], (MONO, 10)),
                              ("v", THEME["white"], (MONO, 10, "bold"))]:
            self.briefing_text.tag_config(tag, foreground=col, font=fnt)
        self.briefing_text.insert("1.0", "In attesa del bersaglio.\nInserisci un nome e avvia la scansione.")
        self.briefing_text.config(state="disabled")

        sf = tk.Frame(grid, bg=THEME["panel"], width=260)
        sf.pack(side="right", fill="both", padx=(8, 0))
        sf.pack_propagate(False)
        tk.Label(sf, text="📈 METRICHE", font=(UI, 11, "bold"),
                 bg=THEME["panel"], fg=THEME["magenta"], anchor="w").pack(fill="x", pady=(0, 6))
        self.stat_rows = {}
        for key, label, col in [("socials", "👥 PROFILI SOCIAL", THEME["accent"]),
                                ("emails", "📧 EMAIL", THEME["accent2"]),
                                ("photos", "💀 FOTO", THEME["magenta"]),
                                ("breaches", "⚠ DATA BREACH", THEME["red"]),
                                ("records", "📊 RECORD PUBBLICI", THEME["amber"]),
                                ("identities", "🎯 IDENTITÀ", THEME["accent"]),
                                ("exposure", "🌐 ESPOSIZIONE", THEME["green"]),
                                ("privacy", "🔐 PRIVACY", THEME["magenta"]),
                                ("risk", "📛 RISCHIO", THEME["red"])]:
            self.stat_rows[key] = self._stat_row(sf, label, col)

    def _stat_row(self, parent, label, color):
        f = tk.Frame(parent, bg=THEME["card"], highlightbackground=THEME["line"],
                     highlightthickness=1)
        f.pack(fill="x", pady=3)
        tk.Label(f, text=label, font=(UI, 8, "bold"), bg=THEME["card"],
                 fg=color, anchor="w").pack(fill="x", padx=8, pady=(4, 0))
        val = tk.Label(f, text="—", font=(MONO, 15, "bold"), bg=THEME["card"],
                       fg=THEME["white"], anchor="w")
        val.pack(fill="x", padx=8, pady=(0, 4))
        return val

    # ---- animazioni leggere UI -----------------------------------------
    def _animate_title(self):
        if not self.root.winfo_exists():
            return
        self._title_phase = (self._title_phase + 0.06) % (2 * math.pi)
        t = (math.sin(self._title_phase) + 1) / 2
        self.title_label.config(fg=lerp_color(THEME["accent"], THEME["magenta"], t * 0.5))
        self.root.after(90, self._animate_title)

    def _tick_clock(self):
        if not self.root.winfo_exists():
            return
        self.clock_label.config(text="⧗ " + datetime.now().strftime("%Y-%m-%d  %H:%M:%S"))
        self.root.after(1000, self._tick_clock)

    def _status(self, msg, color=None):
        self.status_label.config(text="● " + msg, fg=color or THEME["green"])

    def _progress(self, value, msg):
        self.progress["value"] = value
        self.progress_label.config(text=msg)
        self.root.update_idletasks()

    # ---- flusso di ricerca ---------------------------------------------
    def load_example(self, name):
        self.input.delete(0, tk.END)
        self.input.insert(0, name)
        self.start_search()

    def deep_scan(self):
        self.surveillance_level = 3
        self.start_search()

    def stop_search(self):
        self.search_active = False
        self.launch_btn.config(state="normal")
        self._status("SCANSIONE INTERROTTA", THEME["amber"])

    def start_search(self):
        target = self.input.get().strip()
        if not target:
            messagebox.showwarning("Bersaglio richiesto", "Inserisci un nome bersaglio.")
            return
        if not PIL_OK:
            messagebox.showerror("Pillow mancante",
                                 "Installa Pillow per la grafica:\n\npip install Pillow")
            return
        self.search_active = True
        self.current_target = target
        self.launch_btn.config(state="disabled")
        self._status(f"SCANSIONE OSINT ATTIVA: {target}", THEME["accent"])
        threading.Thread(target=self._run_search, args=(target,), daemon=True).start()

    def _run_search(self, target):
        steps = [
            (6, "Inizializzo i nodi di sorveglianza..."),
            (16, "Accesso alle banche dati globali..."),
            (28, "Deploy dei crawler sul deep web..."),
            (40, "Scansione delle piattaforme social..."),
            (52, "Analisi dei pattern di comunicazione..."),
            (64, "Mappatura dell'impronta digitale..."),
            (74, "Raccolta degli asset visivi..."),
            (84, "Cross-reference tra database..."),
            (92, "Valutazione della minaccia..."),
            (100, "Scansione completata. Dossier pronto."),
        ]
        for value, msg in steps:
            if not self.search_active:
                self.root.after(0, lambda: self.launch_btn.config(state="normal"))
                return
            self.root.after(0, self._progress, value, msg)
            time.sleep(0.12)

        data = self._cache_get(target) if self.surveillance_level < 3 else None
        if not data:
            data = build_dossier(target)
            self._cache_put(target, data)
        self.results = data
        self.surveillance_level = 1
        self.root.after(0, self._render, data)

    # ---- render dei risultati ------------------------------------------
    def _set_console(self, widget, chunks):
        widget.config(state="normal")
        widget.delete("1.0", tk.END)
        for text, tag in chunks:
            widget.insert(tk.END, text, tag)
        widget.config(state="disabled")

    def _render(self, data):
        try:
            self._render_overview(data)
            self._render_social(data)
            self._render_identities(data)
            self._render_footprint(data)
            self._render_behavior(data)
            n_photos = len(data["photos"])
            n_id = len(data["identities"])
            self._status(f"COMPLETATO: {data['target']} — {n_photos} foto / {n_id} identità",
                         THEME["green"])
        except Exception as e:
            messagebox.showerror("Errore visualizzazione", str(e))
        finally:
            self.launch_btn.config(state="normal")
            self.search_active = False

    def _render_overview(self, data):
        s = data["summary"]
        col = {"LOW": THEME["green"], "MEDIUM": THEME["amber"],
               "HIGH": THEME["red"]}.get(s["threat"], THEME["dim"])
        self.threat_label.config(
            text=f"IDENTITÀ MULTIPLE — MINACCIA {s['threat']}", fg=col)
        self.confidence_label.config(
            text=f"CONFIDENCE: {s['confidence']}%   |   CLEARANCE: {s['clearance']}   "
                 f"|   RISK: {s['risk']}/100", fg=THEME["accent"])

        idt = data["identities"]
        fp = data["footprint"]
        chunks = [(f"DOSSIER OSINT — {data['target']}\n", "h"),
                  ("═" * 46 + "\n\n", "k")]
        chunks += [("IDENTITÀ RILEVATE: ", "k"), (f"{len(idt)}\n", "v")]
        chunks += [("  ▸ PRIMARIA: ", "k"), (f"{idt[0]['name']}\n", "v")]
        chunks += [("  ▸ ALIAS: ", "k"), (", ".join(idt[0]['aliases']) + "\n", "v")]
        chunks += [("  ▸ LUOGO: ", "k"), (f"{idt[0]['location']}\n", "v")]
        chunks += [("  ▸ RUOLO: ", "k"), (f"{idt[0]['role']}\n\n", "v")]
        chunks += [("VISUAL INTEL:\n", "h")]
        chunks += [("  📧 email: ", "k"), (f"{len(data['emails'])} ", "v"),
                   (f"({fp['breaches']} compromesse)\n", "k")]
        chunks += [("  👥 social: ", "k"), (f"{len(data['socials'])} piattaforme\n", "v")]
        chunks += [("  💀 foto: ", "k"), (f"{len(data['photos'])} asset\n\n", "v")]
        chunks += [("IDENTITY MATRIX:\n", "h")]
        for i, it in enumerate(idt):
            chunks += [(f"  {i+1}. {it['name']} ", "v"),
                       (f"— {it['confidence']}% — "
                        f"{sum(1 for p in data['photos'] if p['identity']==i)} foto\n", "k")]
        chunks += [("\nMETRICHE:\n", "h")]
        chunks += [("  🌐 esposizione: ", "k"), (f"{fp['exposure']}/100\n", "v")]
        chunks += [("  🔐 privacy: ", "k"), (f"{fp['privacy']}/100\n", "v")]
        chunks += [("  ⚠ data breach: ", "k"), (f"{fp['breaches']}\n", "v")]
        self._set_console(self.briefing_text, chunks)

        vals = {
            "socials": str(len(data["socials"])),
            "emails": str(len(data["emails"])),
            "photos": str(len(data["photos"])),
            "breaches": str(fp["breaches"]),
            "records": str(fp["records"]),
            "identities": str(len(idt)),
            "exposure": f"{fp['exposure']}/100",
            "privacy": f"{fp['privacy']}/100",
            "risk": f"{s['risk']}/100",
        }
        for key, val in vals.items():
            self.stat_rows[key].config(text=val)

    def _render_social(self, data):
        chunks = [("👥 SOCIAL MEDIA INTELLIGENCE\n", "h"), ("═" * 46 + "\n\n", "k")]
        for p in data["socials"]:
            ver = ("✔ verificato", "ok") if p["verified"] else ("✘ non verificato", "k")
            chunks += [(f"{p['glyph']}  {p['platform']}\n", "h")]
            chunks += [("   handle: ", "k"), (f"{p['handle']}\n", "v")]
            chunks += [("   follower: ", "k"), (f"{p['followers']}", "v"),
                       (f"   post: {p['posts']}\n", "k")]
            chunks += [("   attività: ", "k"), (f"{p['activity']}", "v"),
                       (f"   visto: {p['last_seen']}   ", "k"), (ver[0] + "\n\n", ver[1])]
        chunks += [(f"\nTOTALE PIATTAFORME: {len(data['socials'])}\n", "warn")]
        self._set_console(self.social_text, chunks)

    def _render_identities(self, data):
        chunks = [("🕵 ANALISI IDENTITÀ MULTIPLE\n", "h"), ("═" * 46 + "\n\n", "k")]
        for i, it in enumerate(data["identities"]):
            tcol = {"LOW": "ok", "MEDIUM": "warn", "HIGH": "bad"}.get(it["threat"], "k")
            head = "PRIMARIA" if i == 0 else f"SECONDARIA #{i}"
            chunks += [(f"🎯 {head}: {it['name']}\n", "h")]
            chunks += [("   confidence: ", "k"), (f"{it['confidence']}%\n", "v")]
            chunks += [("   età: ", "k"), (f"{it['age']}   ", "v"),
                       ("luogo: ", "k"), (f"{it['location']}\n", "v")]
            chunks += [("   ruolo: ", "k"), (f"{it['role']}\n", "v")]
            chunks += [("   minaccia: ", "k"), (f"{it['threat']}\n", tcol)]
            b = it["biometrics"]
            chunks += [("   biometria: ", "k"),
                       (f"{b['height']}, {b['eyes']}, corporatura {b['build']}\n", "v")]
            chunks += [("   segni: ", "k"), (f"{b['marks']}\n", "v")]
            chunks += [("   alias: ", "k"), (", ".join(it["aliases"]) + "\n", "v")]
            chunks += [("   social score: ", "k"), (f"{it['social_score']}/100\n\n", "v")]
        self._set_console(self.ident_text, chunks)

    def _render_footprint(self, data):
        fp = data["footprint"]
        chunks = [("🌐 DIGITAL FOOTPRINT\n", "h"), ("═" * 46 + "\n\n", "k")]
        rows = [("domini registrati", fp["domains"]), ("piattaforme social", fp["platforms"]),
                ("record pubblici", fp["records"]), ("data breach", fp["breaches"]),
                ("esposizione", f"{fp['exposure']}/100"), ("privacy", f"{fp['privacy']}/100"),
                ("presenza online", fp["presence"])]
        for k, v in rows:
            chunks += [(f"  • {k}: ", "k"), (f"{v}\n", "v")]
        vuln = "ALTA" if fp["privacy"] < 40 else "MEDIA"
        vtag = "bad" if fp["privacy"] < 40 else "warn"
        chunks += [("\n⚠ VALUTAZIONE SICUREZZA:\n", "h")]
        chunks += [("  esposizione privacy: ", "k"), (f"{100 - fp['privacy']}%\n", "v")]
        chunks += [("  vulnerabilità: ", "k"), (f"{vuln}\n", vtag)]
        chunks += [("\n💀 RACCOMANDAZIONI:\n", "h"),
                   ("  ▸ sorveglianza multi-identità continua\n", "k"),
                   ("  ▸ analisi di tutti gli asset foto\n", "k"),
                   ("  ▸ aggiornare la valutazione minaccia\n", "k")]
        self._set_console(self.foot_text, chunks)

    def _render_behavior(self, data):
        b = data["behavior"]
        fin = data["finance"]
        chunks = [("📈 ANALISI COMPORTAMENTALE\n", "h"), ("═" * 46 + "\n\n", "k")]
        rows = [("attività online", b["online"]), ("abitudini d'acquisto", b["shopping"]),
                ("frequenza viaggi", b["travel"]), ("engagement sociale", b["engagement"])]
        for k, v in rows:
            chunks += [(f"  • {k}: ", "k"), (f"{v}\n", "v")]
        st = b["sentiment"]
        stag = "ok" if st > 20 else "bad" if st < -10 else "warn"
        chunks += [("  • sentiment: ", "k"), (f"{st:+d}\n\n", stag)]
        chunks += [("💰 PROFILO FINANZIARIO (simulato):\n", "h")]
        chunks += [("  • carte: ", "k"), (f"{fin['cards']}  {fin['last4']}\n", "v")]
        chunks += [("  • conti: ", "k"), (f"{fin['accounts']}\n", "v")]
        chunks += [("  • wallet crypto: ", "k"), (f"{fin['wallets']}\n", "v")]
        chunks += [("  • transazioni/mese: ", "k"), (f"{fin['monthly']}\n\n", "v")]
        chunks += [("🎯 PREDITTIVA:\n", "h"),
                   ("  ▸ priorità monitoraggio: MOLTO ALTA\n", "warn"),
                   ("  ▸ azione: sorveglianza multi-profilo\n", "k")]
        self._set_console(self.behav_text, chunks)

    # ===================================================================
    #  CINEMATIC GALLERY
    # ===================================================================
    def open_gallery(self):
        if not self.results:
            messagebox.showwarning("Nessun dato", "Esegui prima una scansione.")
            return
        if not PIL_OK:
            messagebox.showerror("Pillow mancante", "Installa Pillow: pip install Pillow")
            return

        win = tk.Toplevel(self.root)
        win.title("💀 CINEMATIC GALLERY")
        win.configure(bg=THEME["bg"])
        win.geometry("1500x900")
        try:
            win.attributes("-fullscreen", True)
        except Exception:
            self._maximize(win)

        canvas = tk.Canvas(win, bg=THEME["bg"], highlightthickness=0)
        canvas.pack(fill="both", expand=True)

        intro = CinematicIntro(canvas, self.results["target"],
                               on_done=lambda: self._build_gallery(win, canvas),
                               accent=THEME["accent"])

        def _skip(_=None):
            intro.stop()
            self._build_gallery(win, canvas)

        def _close(_=None):
            intro.stop()
            win.destroy()

        win.bind("<Escape>", _close)
        win.bind("<space>", _skip)
        win.bind("<Return>", _skip)
        win.focus_set()

    def _build_gallery(self, win, canvas):
        if not win.winfo_exists():
            return
        try:
            win.attributes("-fullscreen", False)
        except Exception:
            pass
        canvas.destroy()
        self._maximize(win)

        outer = tk.Frame(win, bg=THEME["bg"])
        outer.pack(fill="both", expand=True)

        data = self.results
        head = tk.Frame(outer, bg=THEME["bg"])
        head.pack(fill="x", padx=24, pady=(18, 8))
        tk.Label(head, text=f"💀  DOSSIER VISIVO — {data['target']}",
                 font=(MONO, 22, "bold"), bg=THEME["bg"], fg=THEME["accent"]).pack(side="left")
        tk.Button(head, text="✕  CHIUDI  (Esc)", font=(UI, 11, "bold"),
                  bg=THEME["panel2"], fg=THEME["red"], relief="flat",
                  command=win.destroy).pack(side="right")

        s = data["summary"]
        info = (f"🎯 {len(data['identities'])} identità   ·   "
                f"📸 {len(data['photos'])} asset   ·   "
                f"⚠ minaccia {s['threat']}   ·   confidence {s['confidence']}%")
        tk.Label(outer, text=info, font=(UI, 12), bg=THEME["bg"],
                 fg=THEME["dim"]).pack(anchor="w", padx=26)
        tk.Label(outer, text="SIMULAZIONE — ritratti generati proceduralmente, non persone reali.",
                 font=(UI, 9, "italic"), bg=THEME["bg"], fg=THEME["amber"]).pack(anchor="w", padx=26)

        nb = ttk.Notebook(outer, style="Orion.TNotebook")
        nb.pack(fill="both", expand=True, padx=16, pady=12)
        win.bind("<Escape>", lambda e: win.destroy())

        for it in data["identities"]:
            tab = tk.Frame(nb, bg=THEME["bg"])
            nb.add(tab, text=f"👤 {it['name']}")
            photos = [p for p in data["photos"] if p["identity"] == it["index"]]
            self._photo_grid(tab, photos, cols=3, header=it)

        tab_all = tk.Frame(nb, bg=THEME["bg"])
        nb.add(tab_all, text=f"💀 TUTTI ({len(data['photos'])})")
        self._photo_grid(tab_all, data["photos"], cols=5, header=None)

    def _scrollable(self, parent):
        container = tk.Frame(parent, bg=THEME["bg"])
        container.pack(fill="both", expand=True)
        canvas = tk.Canvas(container, bg=THEME["bg"], highlightthickness=0)
        sb = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=THEME["bg"])
        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        win_id = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win_id, width=e.width))
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        def _wheel(e):
            canvas.yview_scroll(int(-e.delta / 120) if e.delta else 0, "units")
        canvas.bind_all("<MouseWheel>", _wheel)
        return inner

    def _photo_grid(self, parent, photos, cols, header):
        inner = self._scrollable(parent)
        if header:
            it = header
            txt = (f"📋 {it['name']}   ·   confidence {it['confidence']}%   ·   "
                   f"{it['location']}   ·   {it['role']}   ·   minaccia {it['threat']}")
            tk.Label(inner, text=txt, font=(UI, 11), bg=THEME["bg"], fg=THEME["accent"],
                     anchor="w").pack(fill="x", padx=18, pady=(14, 8))

        grid = tk.Frame(inner, bg=THEME["bg"])
        grid.pack(fill="both", expand=True, padx=14, pady=8)
        for c in range(cols):
            grid.columnconfigure(c, weight=1)

        if not photos:
            tk.Label(grid, text="Nessun asset per questa identità.", font=(UI, 13),
                     bg=THEME["bg"], fg=THEME["dim"]).pack(pady=40)
            return

        for i, photo in enumerate(photos):
            self._photo_card(grid, photo).grid(row=i // cols, column=i % cols,
                                               padx=10, pady=10, sticky="n")

    def _photo_card(self, parent, photo):
        target = self.results["target"]
        seed = f"{target}|{photo['id']}"
        img = generate_portrait(seed, size=(240, 290), accent=THEME["accent"],
                                caption=photo["identity_name"],
                                subcaption=f"{photo['tag']} · {photo['location']}",
                                matched=photo["matched"])
        tkimg = ImageTk.PhotoImage(img)
        self._img_refs.append(tkimg)

        card = tk.Frame(parent, bg=THEME["card"], highlightbackground=THEME["line"],
                        highlightthickness=1, cursor="hand2")
        img_lbl = tk.Label(card, image=tkimg, bg=THEME["card"], bd=0)
        img_lbl.pack(padx=8, pady=(8, 4))

        meta = tk.Frame(card, bg=THEME["card"])
        meta.pack(fill="x", padx=8, pady=(0, 8))
        icol = (THEME["green"] if photo["intel"] >= 7
                else THEME["amber"] if photo["intel"] >= 5 else THEME["red"])
        tk.Label(meta, text=f"▮ INTEL {photo['intel']}/10", font=(MONO, 9, "bold"),
                 bg=THEME["card"], fg=icol).pack(side="left")
        tk.Label(meta, text=f"{photo['quality']} · {photo['date']}", font=(MONO, 8),
                 bg=THEME["card"], fg=THEME["dim"]).pack(side="right")

        def on_enter(_):
            card.config(highlightbackground=THEME["accent"], highlightthickness=2,
                        bg=THEME["panel2"])
            img_lbl.config(bg=THEME["panel2"])
            meta.config(bg=THEME["panel2"])
            for w in meta.winfo_children():
                w.config(bg=THEME["panel2"])

        def on_leave(_):
            card.config(highlightbackground=THEME["line"], highlightthickness=1,
                        bg=THEME["card"])
            img_lbl.config(bg=THEME["card"])
            meta.config(bg=THEME["card"])
            for w in meta.winfo_children():
                w.config(bg=THEME["card"])

        for w in (card, img_lbl, meta):
            w.bind("<Enter>", on_enter)
            w.bind("<Leave>", on_leave)
            w.bind("<Button-1>", lambda e, p=photo: self._photo_detail(p))
        return card

    def _photo_detail(self, photo):
        win = tk.Toplevel(self.root)
        win.title(f"💀 {photo['identity_name']} — {photo['tag']}")
        win.configure(bg=THEME["bg"])
        win.geometry("860x580")
        win.bind("<Escape>", lambda e: win.destroy())

        body = tk.Frame(win, bg=THEME["bg"])
        body.pack(fill="both", expand=True, padx=20, pady=20)

        # ----- ritratto grande + scansione facciale animata -----
        left = tk.Frame(body, bg=THEME["bg"])
        left.pack(side="left", fill="both")
        seed = f"{self.results['target']}|{photo['id']}"
        big = generate_portrait(seed, size=(400, 480), accent=THEME["accent"],
                                caption=photo["identity_name"],
                                subcaption=f"{photo['tag']} · {photo['location']}",
                                matched=photo["matched"])
        tkbig = ImageTk.PhotoImage(big)
        self._img_refs.append(tkbig)
        cv = tk.Canvas(left, width=400, height=480, bg=THEME["black"],
                       highlightthickness=1, highlightbackground=THEME["line"])
        cv.pack()
        cv.create_image(0, 0, image=tkbig, anchor="nw")
        FaceScan(cv, 400, 480, THEME["accent"], photo["matched"])

        # ----- dossier -----
        right = tk.Frame(body, bg=THEME["bg"])
        right.pack(side="left", fill="both", expand=True, padx=(20, 0))
        tk.Label(right, text="🔍 ANALISI ASSET", font=(MONO, 15, "bold"),
                 bg=THEME["bg"], fg=THEME["accent"]).pack(anchor="w", pady=(0, 10))
        txt = scrolledtext.ScrolledText(right, bg=THEME["bg2"], fg=THEME["text"],
                                        font=(MONO, 11), relief="flat", padx=12, pady=10,
                                        wrap="word", highlightbackground=THEME["line"],
                                        highlightthickness=1)
        txt.pack(fill="both", expand=True)
        txt.tag_config("h", foreground=THEME["accent"], font=(MONO, 12, "bold"))
        txt.tag_config("k", foreground=THEME["dim"])
        txt.tag_config("v", foreground=THEME["white"])
        rows = [("h", "DATI ASSET\n"),
                ("k", "identità: "), ("v", photo["identity_name"] + "\n"),
                ("k", "tipo: "), ("v", photo["tag"] + "\n"),
                ("k", "data: "), ("v", photo["date"] + "\n"),
                ("k", "luogo: "), ("v", photo["location"] + "\n"),
                ("k", "qualità: "), ("v", photo["quality"] + "\n"),
                ("k", "fonte: "), ("v", photo["source"] + "\n\n"),
                ("h", "METRICHE\n"),
                ("k", "intel value: "), ("v", f"{photo['intel']}/10\n"),
                ("k", "match biometrico: "), ("v", ("SÌ" if photo["matched"] else "NO") + "\n"),
                ("k", "classificazione: "), ("v", "Open Source (SIM)\n\n"),
                ("h", "ANALISI\n"),
                ("k", "riconoscimento facciale: "), ("v", "disponibile\n"),
                ("k", "metadati: "), ("v", "estratti\n"),
                ("k", "geolocalizzazione: "), ("v", "verificata\n")]
        for tag, text in rows:
            txt.insert(tk.END, text, tag)
        txt.config(state="disabled")

        tk.Button(right, text="✕  Chiudi", font=(UI, 11, "bold"), bg=THEME["panel2"],
                  fg=THEME["red"], relief="flat", command=win.destroy).pack(pady=(10, 0))


class FaceScan:
    """Overlay animato di 'riconoscimento facciale' su un Canvas con ritratto."""
    def __init__(self, canvas, w, h, accent, matched):
        self.c = canvas
        self.w, self.h = w, h
        self.accent = accent
        self.matched = matched
        self.y = 0
        self.dir = 1
        self.sweeps = 0
        self.locked = False
        self.frame = 0
        self._tick()

    def _tick(self):
        if not self.c.winfo_exists():
            return
        self.frame += 1
        self.c.delete("scan")
        acc = self.accent

        # angoli e cornice pulsante
        pulse = (math.sin(self.frame * 0.2) + 1) / 2
        bw = 1 + int(pulse * 2)
        L = 30
        for (ax, ay, dx, dy) in [(14, 14, 1, 1), (self.w - 14, 14, -1, 1),
                                 (14, self.h - 14, 1, -1),
                                 (self.w - 14, self.h - 14, -1, -1)]:
            self.c.create_line(ax, ay, ax + dx * L, ay, fill=acc, width=bw, tags="scan")
            self.c.create_line(ax, ay, ax, ay + dy * L, fill=acc, width=bw, tags="scan")

        if not self.locked:
            # linea di scansione
            self.c.create_rectangle(10, self.y, self.w - 10, self.y + 3,
                                    fill=acc, outline="", tags="scan")
            self.c.create_rectangle(10, self.y - 26, self.w - 10, self.y,
                                    fill=lerp_color(self.accent, THEME["bg"], 0.8),
                                    outline="", stipple="gray25", tags="scan")
            self.c.create_text(self.w - 18, self.y + 10, anchor="e",
                               fill=acc, font=(MONO, 9, "bold"),
                               text=f"SCAN {int(self.y/self.h*100)}%", tags="scan")
            self.y += 7 * self.dir
            if self.y >= self.h - 10:
                self.dir = -1
                self.sweeps += 1
            elif self.y <= 10:
                self.dir = 1
                self.sweeps += 1
            if self.sweeps >= 3:
                self.locked = True
        else:
            # esito
            label = "◉ IDENTITY MATCH" if self.matched else "✕ NO MATCH"
            col = THEME["green"] if self.matched else THEME["red"]
            self.c.create_rectangle(0, self.h // 2 - 22, self.w, self.h // 2 + 22,
                                    fill=THEME["black"], outline=col, tags="scan")
            conf = 90 + (self.frame % 10) if self.matched else 0
            self.c.create_text(self.w // 2, self.h // 2, fill=col,
                               font=(MONO, 18, "bold"),
                               text=f"{label}  {conf}.{self.frame%10}%" if self.matched else label,
                               tags="scan")
        self.c.after(40, self._tick)


# ===========================================================================
def main():
    print("◈ ORION // SPY OSINT CINEMA PRO — SIMULATORE")
    print("  ⚠  Gioco a scopo dimostrativo: nessuna ricerca reale, dati casuali.")
    if not PIL_OK:
        print("  ✗ Pillow non installato → grafica limitata.  pip install Pillow")
    try:
        root = tk.Tk()
        SpyOSINTApp(root)
        root.mainloop()
    except tk.TclError as e:
        print("Impossibile aprire la GUI (display non disponibile?):", e)
    except Exception as e:
        print("Errore fatale:", e)


if __name__ == "__main__":
    main()
