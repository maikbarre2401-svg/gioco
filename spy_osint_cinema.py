#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ORION // SPY OSINT CINEMA PRO  —  by MAIKGOST
Simulatore d'intelligence dall'estetica cinematografica (gioco / demo UI).

⚠️  SIMULAZIONE / GIOCO
    Questo programma NON esegue nessuna ricerca reale, non contatta internet
    e non raccoglie dati su nessuna persona. TUTTI i dati (nomi, foto, email,
    profili, ecc.) sono generati in modo casuale e deterministico dal testo
    digitato, a puro scopo di intrattenimento. I ritratti sono silhouette
    astratte generate dal codice: NON sono persone reali.

Creato da MAIKGOST.
Requisiti: Python 3.8+, tkinter (di serie), Pillow (`pip install Pillow`).
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
from datetime import datetime, timedelta
from tkinter import messagebox, scrolledtext, ttk

try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageTk
    PIL_OK = True
except Exception:  # pragma: no cover
    PIL_OK = False


# ===========================================================================
#  IDENTITÀ CREATORE  (firma presente in tutta l'app)
# ===========================================================================
CREATOR = "MAIKGOST"
CREATOR_TAG = f"created by {CREATOR}"
APP_NAME = "ORION // SPY OSINT CINEMA PRO"


# ===========================================================================
#  TEMA
# ===========================================================================
THEME = {
    "bg": "#05060b", "bg2": "#090c16", "panel": "#0f1320", "panel2": "#151a2b",
    "card": "#12172a", "line": "#1e2444", "accent": "#00e5ff", "accent2": "#3ba9ff",
    "magenta": "#ff2bd6", "green": "#39ff14", "amber": "#ffb020", "red": "#ff3b5c",
    "text": "#e2e8ff", "dim": "#8791b8", "white": "#ffffff", "black": "#000000",
}
MONO = "Consolas"
UI = "Segoe UI"
MATRIX_CHARS = "アカサタナハマヤラабвг0123456789ABCDEF$#@%&<>/*ΞΨΛØ§"


# ===========================================================================
#  COLORE / FONT
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
_TTF = ["consola.ttf", "Consolas.ttf", "cour.ttf", "arial.ttf", "Arial.ttf",
        "DejaVuSansMono.ttf", "DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/Library/Fonts/Arial.ttf"]


def load_font(size, bold=False):
    if not PIL_OK:
        return None
    key = (size, bold)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    cands = (["consolab.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"] if bold else []) + _TTF
    font = None
    for name in cands:
        try:
            font = ImageFont.truetype(name, size)
            break
        except Exception:
            continue
    if font is None:
        try:
            font = ImageFont.load_default(size)
        except Exception:
            font = ImageFont.load_default()
    _FONT_CACHE[key] = font
    return font


# ===========================================================================
#  GRAFICA PILLOW  —  logo, radar chart, ritratti
# ===========================================================================
_VIGNETTE_CACHE = {}


def _vignette_mask(size, strength=0.85):
    key = (size, round(strength, 2))
    if key in _VIGNETTE_CACHE:
        return _VIGNETTE_CACHE[key]
    mask = Image.radial_gradient("L").resize(size).point(lambda v: int(v * strength))
    _VIGNETTE_CACHE[key] = mask
    return mask


def _vgrad(size, top, bottom):
    w, h = size
    g = Image.new("RGB", (1, h))
    tp, bt = hex_to_rgb(top), hex_to_rgb(bottom)
    px = g.load()
    for y in range(h):
        t = y / max(1, h - 1)
        px[0, y] = tuple(int(lerp(tp[i], bt[i], t)) for i in range(3))
    return g.resize((w, h))


def render_logo(width=560, height=120):
    """Banner logo con glow + tagline 'created by MAIKGOST'."""
    if not PIL_OK:
        return None
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    f_big = load_font(46, bold=True)
    f_tag = load_font(15, bold=True)
    f_sub = load_font(13, bold=True)
    gd.text((14, 18), "◈ ORION", font=f_big, fill=hex_to_rgb(THEME["accent"]) + (255,))
    glow = glow.filter(ImageFilter.GaussianBlur(6))
    img = Image.alpha_composite(img, glow)
    d = ImageDraw.Draw(img)
    d.text((14, 18), "◈ ORION", font=f_big, fill=hex_to_rgb(THEME["white"]) + (255,))
    d.text((16, 70), "SPY OSINT CINEMA PRO", font=f_tag, fill=hex_to_rgb(THEME["accent"]) + (255,))
    d.text((width - 200, 30), "◤ " + CREATOR_TAG, font=f_sub,
           fill=hex_to_rgb(THEME["magenta"]) + (255,))
    d.line([(16, 96), (width - 20, 96)], fill=hex_to_rgb(THEME["line"]) + (255,), width=1)
    return img


def render_radar_chart(axes, size=260, accent=None):
    """Spider/radar chart delle metriche. axes = [(label, valore0-100), ...]."""
    if not PIL_OK:
        return None
    accent = accent or THEME["accent"]
    S = size
    scale = 3  # supersampling per bordi lisci
    img = Image.new("RGB", (S * scale, S * scale), hex_to_rgb(THEME["bg2"]))
    d = ImageDraw.Draw(img, "RGBA")
    cx = cy = S * scale // 2
    R = int(S * scale * 0.36)
    n = len(axes)
    acc = hex_to_rgb(accent)

    for ring in range(1, 5):
        rr = R * ring / 4
        pts = [(cx + rr * math.cos(2 * math.pi * k / n - math.pi / 2),
                cy + rr * math.sin(2 * math.pi * k / n - math.pi / 2)) for k in range(n)]
        d.polygon(pts, outline=hex_to_rgb(THEME["line"]) + (255,))
    fnt = load_font(13 * scale, bold=True)
    poly = []
    for k, (label, val) in enumerate(axes):
        a = 2 * math.pi * k / n - math.pi / 2
        d.line([(cx, cy), (cx + R * math.cos(a), cy + R * math.sin(a))],
               fill=hex_to_rgb(THEME["line"]) + (255,))
        rr = R * max(0, min(100, val)) / 100
        poly.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
        lx = cx + (R + 22 * scale) * math.cos(a)
        ly = cy + (R + 22 * scale) * math.sin(a)
        anchor = "mm"
        d.text((lx, ly), label, font=fnt, fill=hex_to_rgb(THEME["dim"]) + (255,), anchor=anchor)
    d.polygon(poly, fill=acc + (70,), outline=acc + (255,))
    for p in poly:
        d.ellipse([p[0] - 4 * scale, p[1] - 4 * scale, p[0] + 4 * scale, p[1] + 4 * scale],
                  fill=acc + (255,))
    d.text((10 * scale, S * scale - 12 * scale), "by " + CREATOR, font=load_font(10 * scale),
           fill=hex_to_rgb(THEME["dim"]) + (150,), anchor="lm")
    return img.resize((S, S), Image.LANCZOS)


def generate_portrait(seed, size=(240, 290), accent=None, caption="", subcaption="",
                      matched=True):
    """Ritratto 'da sorveglianza' procedurale (silhouette astratta, NON reale)."""
    if not PIL_OK:
        return None
    accent = accent or THEME["accent"]
    w, h = size
    rng = random.Random(int(hashlib.md5(str(seed).encode()).hexdigest(), 16))
    palettes = [("#0a1424", "#132a44"), ("#0c1a16", "#173a2c"), ("#1a1410", "#3a2c1c"),
                ("#101024", "#241a3a"), ("#08121a", "#123044"), ("#160a12", "#3a1830")]
    top, bottom = rng.choice(palettes)
    img = _vgrad((w, h), top, bottom)
    acc = hex_to_rgb(accent)

    # --- Silhouette busto (layer separato, sfocato) ---
    cx = w // 2 + rng.randint(-12, 12)
    head_rx = int(w * rng.uniform(0.16, 0.19))
    head_ry = int(head_rx * rng.uniform(1.18, 1.32))
    head_cy = int(h * 0.40)
    neutral = (150, 158, 182)
    sil = tuple(int(lerp(hex_to_rgb(bottom)[i], neutral[i], 0.52)) for i in range(3))
    sil_dark = tuple(int(c * 0.55) for c in sil)
    rim = tuple(int(lerp(sil[i], 255, 0.6)) for i in range(3))
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
    draw = ImageDraw.Draw(img, "RGBA")

    # grana
    try:
        noise = Image.effect_noise((w, h), 26).convert("L")
        img = Image.blend(img, Image.merge("RGB", (noise, noise, noise)), 0.06)
        draw = ImageDraw.Draw(img, "RGBA")
    except Exception:
        pass

    # glitch bars occasionali
    if rng.random() < 0.5:
        for _ in range(rng.randint(1, 3)):
            gy = rng.randint(int(h * 0.25), int(h * 0.7))
            gh = rng.randint(2, 6)
            dxg = rng.randint(4, 14) * rng.choice([-1, 1])
            strip = img.crop((0, gy, w, gy + gh))
            img.paste(strip, (dxg, gy))
            draw = ImageDraw.Draw(img, "RGBA")
            draw.rectangle([0, gy, w, gy + gh], fill=acc + (26,))

    # scanline
    for y in range(0, h, 3):
        draw.line([(0, y), (w, y)], fill=(0, 0, 0, 60))

    # barra REDACTED sugli occhi (rinforza: non è una persona reale)
    if rng.random() < 0.45:
        ey = head_cy - int(head_ry * 0.12)
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
        draw.line([(px, py), (px + sx * tick, py)], fill=acc, width=2)
        draw.line([(px, py), (px, py + sy * tick)], fill=acc, width=2)
    fcy = head_cy - int(head_ry * 0.15)
    r = int(head_rx * 0.45)
    draw.ellipse([cx - r, fcy - r, cx + r, fcy + r], outline=acc + (150,), width=1)
    draw.line([(cx - r - 6, fcy), (cx + r + 6, fcy)], fill=acc + (110,), width=1)
    draw.line([(cx, fcy - r - 6), (cx, fcy + r + 6)], fill=acc + (110,), width=1)

    # cornice + angoli
    m = 6
    draw.rectangle([m, m, w - m, h - m], outline=acc + (120,), width=1)
    L = 22
    for (ax, ay, dx, dy) in [(m, m, 1, 1), (w - m, m, -1, 1),
                             (m, h - m, 1, -1), (w - m, h - m, -1, -1)]:
        draw.line([(ax, ay), (ax + dx * L, ay)], fill=acc, width=3)
        draw.line([(ax, ay), (ax, ay + dy * L)], fill=acc, width=3)

    # HUD testo
    fmono = load_font(11)
    fsmall = load_font(12, bold=True)
    bar = 34 if caption else 0
    cam = f"CAM-{rng.randint(1,9)}{rng.choice('ABKZ')}{rng.randint(10,99)}"
    draw.text((m + 8, m + 6), cam, font=fmono, fill=acc)
    draw.text((w - m - 66, m + 6), "● REC", font=fsmall, fill=hex_to_rgb(THEME["red"]))
    lat = rng.uniform(35, 60); lon = rng.uniform(-8, 25)
    draw.text((m + 8, m + 24), f"{lat:.4f}N {lon:.4f}E", font=fmono, fill=acc + (170,))
    # mini-barcode in alto, sotto le coordinate
    bx = m + 8
    for i in range(26):
        if rng.random() < 0.5:
            draw.line([(bx + i * 3, m + 42), (bx + i * 3, m + 50)], fill=acc + (200,), width=2)
    # riga inferiore appena SOPRA la caption bar
    ry = h - bar - 20
    ts = f"{rng.randint(0,23):02d}:{rng.randint(0,59):02d}:{rng.randint(0,59):02d}"
    draw.text((m + 8, ry), ts, font=fmono, fill=acc)
    tag = f"MATCH {rng.randint(78,99)}.{rng.randint(0,9)}%" if matched else "NO MATCH"
    col = hex_to_rgb(THEME["green"]) if matched else hex_to_rgb(THEME["red"])
    draw.text((w - m - 96, ry), tag, font=fsmall, fill=col)

    # caption bar + watermark creatore
    if caption:
        draw.rectangle([0, h - bar, w, h], fill=(0, 0, 0, 190))
        draw.text((10, h - bar + 4), caption[:20], font=load_font(14, bold=True),
                  fill=hex_to_rgb(THEME["white"]))
        if subcaption:
            draw.text((10, h - bar + 20), subcaption[:30], font=fmono,
                      fill=hex_to_rgb(THEME["dim"]))
    draw.text((w - 8, h - 6), CREATOR, font=fmono,
              fill=hex_to_rgb(THEME["white"]) + (150,), anchor="rs")
    return img


# ===========================================================================
#  DATI  —  dossier simulato deterministico
# ===========================================================================
FIRST = ["Marco", "Luca", "Andrea", "Giulia", "Sara", "Elena", "Matteo", "Alex",
         "Nina", "Ivan", "Sofia", "Dario", "Karim", "Mila", "Noa", "Leo"]
LAST = ["Rossi", "Bianchi", "Esposito", "Romano", "Ferrari", "Costa", "Moreau",
        "Keller", "Petrov", "Nakamura", "Vidal", "Okoye", "Haas", "Silva"]
CITIES = [("Roma, IT", 0.62, 0.66), ("Milano, IT", 0.60, 0.58), ("Napoli, IT", 0.63, 0.70),
          ("Torino, IT", 0.57, 0.58), ("London, UK", 0.52, 0.46), ("Berlin, DE", 0.60, 0.45),
          ("Paris, FR", 0.54, 0.50), ("Zürich, CH", 0.58, 0.53), ("Lisboa, PT", 0.46, 0.62),
          ("Wien, AT", 0.62, 0.51), ("New York, US", 0.28, 0.52), ("Dubai, AE", 0.72, 0.66)]
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
    return "".join(name.lower().split()) or "unknown"


def build_dossier(target):
    target = (target or "Sconosciuto").strip()
    seed = int(hashlib.md5(target.lower().encode()).hexdigest(), 16)
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
    base = datetime.now()
    for _ in range(rng.randint(6, 9)):
        base = base - timedelta(days=rng.randint(20, 200))
        timeline.append({"date": base.strftime("%Y-%m-%d"), "event": rng.choice(EVENTS),
                         "sev": rng.choice(["info", "warn", "bad"])})

    risk = min(99, int(footprint["exposure"] * 0.6 + (100 - footprint["privacy"]) * 0.4))
    return {
        "simulation": True, "creator": CREATOR, "target": target,
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "summary": {"threat": identities[0]["threat"], "confidence": identities[0]["confidence"],
                    "clearance": f"LEVEL {rng.randint(2,4)}", "risk": risk},
        "identities": identities, "photos": photos, "socials": socials, "emails": emails,
        "footprint": footprint, "behavior": behavior, "finance": finance, "timeline": timeline,
    }


# ===========================================================================
#  INTRO CINEMATOGRAFICO (breve, non bloccante)
# ===========================================================================
class CinematicIntro:
    FPS_MS = 30

    def __init__(self, canvas, target, on_done, accent=None):
        self.c = canvas
        self.target = (target or "UNKNOWN").upper()
        self.on_done = on_done
        self.accent = accent or THEME["accent"]
        self.frame = 0
        self.after_id = None
        self.running = True
        self.ready = False
        self.matrix = []
        self.particles = []
        self.radar_angle = 0.0
        self.log = ["conn secure://orion.grid  [OK]",
                    "operator: " + CREATOR.lower() + " ...... [OK]",
                    "biometric vector match ..... [OK]",
                    "decrypting media cache ..... [OK]",
                    "access token elevated ...... [OK]"]
        # intro breve: ~2.6s
        self.timeline = [
            ("◈ O R I O N", 46, self.accent, 12),
            (CREATOR_TAG.upper(), 20, THEME["magenta"], 10),
            (f"TARGET ▸ {self.target}", 30, THEME["white"], 14),
            ("◎ BIOMETRICS MATCHED", 22, THEME["green"], 12),
            ("◉ ACCESS GRANTED", 40, THEME["green"], 14),
        ]
        self.total = sum(p[3] for p in self.timeline) + 4
        self.shutter = 0
        self._tick()

    def _dims(self):
        w, h = self.c.winfo_width(), self.c.winfo_height()
        if w <= 1 or h <= 1:
            w, h = self.c.winfo_screenwidth(), self.c.winfo_screenheight()
        return w, h

    def _ensure(self, w, h):
        if self.ready:
            return
        for i in range(max(10, w // 24)):
            self.matrix.append({"x": i * 24 + 6, "y": random.randint(-h, 0),
                                "speed": random.uniform(9, 22), "len": random.randint(6, 16),
                                "chars": [random.choice(MATRIX_CHARS) for _ in range(20)]})
        self.particles = [{"x": random.uniform(0, w), "y": random.uniform(0, h),
                           "vx": random.uniform(-0.3, 0.3), "vy": random.uniform(-1.4, -0.4),
                           "r": random.uniform(1, 2.4)} for _ in range(55)]
        self.ready = True

    def _tick(self):
        if not self.running or not self.c.winfo_exists():
            return
        try:
            w, h = self._dims()
            self._ensure(w, h)
            self.c.delete("all")
            self.c.create_rectangle(0, 0, w, h, fill=THEME["bg"], outline="")
            self._matrix(w, h)
            self._radar(w, h)
            self._particles(w, h)
            self.c.create_rectangle(0, (self.frame * 7) % h, w, (self.frame * 7) % h + 60,
                                    fill=lerp_color(THEME["bg"], self.accent, 0.06), outline="")
            self._text(w, h)
            self._hud(w, h)
        except tk.TclError:
            return
        self.frame += 1
        if self.frame >= self.total:
            self._close(w, h)
            return
        self.after_id = self.c.after(self.FPS_MS, self._tick)

    def _matrix(self, w, h):
        for col in self.matrix:
            col["y"] += col["speed"]
            if col["y"] - col["len"] * 16 > h:
                col["y"] = random.randint(-h // 2, 0)
            x = col["x"]
            for k in range(col["len"]):
                y = col["y"] - k * 16
                if 0 <= y <= h:
                    color = (THEME["white"] if k == 0 else self.accent if k < 3
                             else lerp_color(THEME["green"], THEME["bg"], k / col["len"]))
                    ch = col["chars"][(k + self.frame) % len(col["chars"])]
                    self.c.create_text(x, y, text=ch, fill=color, font=(MONO, 12))

    def _radar(self, w, h):
        cx, cy = w // 2, int(h * 0.44)
        R = int(min(w, h) * 0.32)
        for rr in range(1, 5):
            r = R * rr / 4
            self.c.create_oval(cx - r, cy - r, cx + r, cy + r,
                               outline=lerp_color(self.accent, THEME["bg"], 0.72))
        self.radar_angle = (self.radar_angle + 0.16) % (2 * math.pi)
        for i in range(10):
            a = self.radar_angle - i * 0.05
            self.c.create_line(cx, cy, cx + R * math.cos(a), cy + R * math.sin(a),
                               fill=lerp_color(self.accent, THEME["bg"], i / 10), width=2)

    def _particles(self, w, h):
        for p in self.particles:
            p["x"] += p["vx"]; p["y"] += p["vy"]
            if p["y"] < 0:
                p["y"] = h; p["x"] = random.uniform(0, w)
            r = p["r"]
            self.c.create_oval(p["x"] - r, p["y"] - r, p["x"] + r, p["y"] + r,
                               fill=lerp_color(self.accent, THEME["bg"], 0.35), outline="")

    def _text(self, w, h):
        f = self.frame - 4
        acc = 0; phase = None; local = 0
        for t, s, col, dur in self.timeline:
            if f < acc + dur:
                phase, local = (t, s, col, dur), f - acc
                break
            acc += dur
        if phase is None:
            phase, local = self.timeline[-1], self.timeline[-1][3]
        text, size, color, dur = phase
        reveal = max(0.0, min(1.0, local / max(1, dur * 0.5)))
        shown = text[:max(1, int(len(text) * reveal))]
        cur = "▌" if (self.frame // 5) % 2 == 0 and reveal < 1 else ""
        cx, cy = w // 2, int(h * 0.44)
        if (self.frame // 3) % 5 == 0:
            self.c.create_text(cx + 3, cy, text=shown, font=(MONO, size, "bold"),
                               fill=THEME["red"])
            self.c.create_text(cx - 3, cy, text=shown, font=(MONO, size, "bold"),
                               fill=self.accent)
        self.c.create_text(cx, cy, text=shown + cur, font=(MONO, size, "bold"), fill=color)

        pw = int(w * 0.5); px = (w - pw) // 2; py = int(h * 0.82)
        prog = min(1.0, self.frame / self.total)
        self.c.create_rectangle(px, py, px + pw, py + 10, outline=self.accent)
        self.c.create_rectangle(px, py, px + int(pw * prog), py + 10, fill=self.accent, outline="")
        self.c.create_text(px + pw + 44, py + 5, text=f"{int(prog*100):3d}%",
                           fill=self.accent, font=(MONO, 12, "bold"))
        idx = min(len(self.log), self.frame // 7)
        for i, line in enumerate(self.log[:idx]):
            self.c.create_text(30, py + 40 + i * 16, text="> " + line, anchor="w",
                               fill=lerp_color(THEME["green"], THEME["bg"], 0.15), font=(MONO, 10))

    def _hud(self, w, h):
        m, L = 16, 34
        for (ax, ay, dx, dy) in [(m, m, 1, 1), (w - m, m, -1, 1),
                                 (m, h - m, 1, -1), (w - m, h - m, -1, -1)]:
            self.c.create_line(ax, ay, ax + dx * L, ay, fill=self.accent, width=2)
            self.c.create_line(ax, ay, ax, ay + dy * L, fill=self.accent, width=2)
        self.c.create_text(m + 6, m - 2, anchor="nw", font=(MONO, 10), fill=self.accent,
                           text=f"ORION//INTEL · {CREATOR}")
        self.c.create_text(w - m - 6, m - 2, anchor="ne", font=(MONO, 10), fill=THEME["dim"],
                           text="SPACE = salta")
        self.c.create_text(w // 2, h - 8, anchor="s", font=(MONO, 9), fill=THEME["dim"],
                           text=f"◦ SIMULAZIONE — dati casuali, nessun dato reale · by {CREATOR} ◦")

    def _close(self, w, h):
        if not self.running or not self.c.winfo_exists():
            return
        self.shutter += 1
        steps = 8
        cov = int((h / 2) * (self.shutter / steps))
        self.c.create_rectangle(0, 0, w, cov, fill=THEME["black"], outline="")
        self.c.create_rectangle(0, h - cov, w, h, fill=THEME["black"], outline="")
        self.c.create_line(0, cov, w, cov, fill=self.accent, width=2)
        self.c.create_line(0, h - cov, w, h - cov, fill=self.accent, width=2)
        if self.shutter >= steps:
            self.stop()
            if callable(self.on_done):
                self.on_done()
            return
        self.after_id = self.c.after(self.FPS_MS, lambda: self._close(w, h))

    def stop(self):
        self.running = False
        if self.after_id:
            try:
                self.c.after_cancel(self.after_id)
            except Exception:
                pass
            self.after_id = None


# ===========================================================================
#  ANIMATORI CANVAS: NETWORK GRAPH + GEO MAP
# ===========================================================================
class NetworkGraph:
    """Grafo relazioni animato (target ▸ identità ▸ entità)."""
    def __init__(self, canvas, data, accent=None):
        self.c = canvas
        self.accent = accent or THEME["accent"]
        self.frame = 0
        self.running = True
        self.after_id = None
        self.nodes, self.edges = self._layout(data)
        self._tick()

    def _layout(self, data):
        nodes = [{"dist": 0, "ang": 0, "r": 16, "col": THEME["white"],
                  "label": data["target"], "kind": "target"}]
        ids = data["identities"]
        for k, it in enumerate(ids):
            a = 2 * math.pi * k / max(1, len(ids))
            nodes.append({"dist": 150, "ang": a, "r": 11,
                          "col": THEME["accent"] if k == 0 else THEME["accent2"],
                          "label": it["name"], "kind": "id"})
            ent = ([("@" + s["platform"][:6], THEME["magenta"]) for s in data["socials"][:2]] +
                   [(e["type"], THEME["amber"]) for e in data["emails"][:1]] +
                   [(it["location"].split(",")[0], THEME["green"])])
            for j, (lab, col) in enumerate(ent):
                off = (j - (len(ent) - 1) / 2) * 0.34
                nodes.append({"dist": 250, "ang": a + off, "r": 6, "col": col,
                              "label": lab, "kind": "ent", "parent": len(nodes) - 1 - j})
        edges = []
        idx_map = [i for i, n in enumerate(nodes) if n["kind"] == "id"]
        for i in idx_map:
            edges.append((0, i))
        for i, n in enumerate(nodes):
            if n["kind"] == "ent":
                # collega all'identità più vicina in angolo
                best = min(idx_map, key=lambda m: abs(nodes[m]["ang"] - n["ang"]))
                edges.append((best, i))
        return nodes, edges

    def _pos(self, node, cx, cy, phase):
        a = node["ang"] + phase
        return cx + node["dist"] * math.cos(a), cy + node["dist"] * math.sin(a)

    def _tick(self):
        if not self.running or not self.c.winfo_exists():
            return
        try:
            w, h = self.c.winfo_width(), self.c.winfo_height()
            if w <= 1:
                w, h = 800, 600
            cx, cy = w // 2, h // 2
            phase = self.frame * 0.006
            self.c.delete("all")
            self.c.create_rectangle(0, 0, w, h, fill=THEME["bg"], outline="")
            # edges + packets
            for a, b in self.edges:
                x1, y1 = self._pos(self.nodes[a], cx, cy, phase)
                x2, y2 = self._pos(self.nodes[b], cx, cy, phase)
                self.c.create_line(x1, y1, x2, y2,
                                   fill=lerp_color(self.accent, THEME["bg"], 0.62))
                t = ((self.frame * 0.02) + (a * 7 + b) * 0.13) % 1.0
                px, py = lerp(x1, x2, t), lerp(y1, y2, t)
                self.c.create_oval(px - 2, py - 2, px + 2, py + 2, fill=self.accent, outline="")
            # nodes
            for n in self.nodes:
                x, y = self._pos(n, cx, cy, phase)
                pr = n["r"] + math.sin(self.frame * 0.1 + x) * 1.5
                self.c.create_oval(x - pr - 4, y - pr - 4, x + pr + 4, y + pr + 4,
                                   outline=lerp_color(n["col"], THEME["bg"], 0.5))
                self.c.create_oval(x - pr, y - pr, x + pr, y + pr, fill=n["col"], outline="")
                if n["kind"] != "ent":
                    self.c.create_text(x, y - pr - 10, text=n["label"], fill=THEME["text"],
                                       font=(MONO, 9, "bold"))
                else:
                    self.c.create_text(x, y + pr + 8, text=n["label"], fill=THEME["dim"],
                                       font=(MONO, 8))
            self.c.create_text(14, h - 12, anchor="w", fill=THEME["dim"], font=(MONO, 9),
                               text=f"RELATION MAP · SIM · by {CREATOR}")
        except tk.TclError:
            return
        self.frame += 1
        self.after_id = self.c.after(50, self._tick)

    def stop(self):
        self.running = False
        if self.after_id:
            try:
                self.c.after_cancel(self.after_id)
            except Exception:
                pass


class GeoMap:
    """Mappa stilizzata con ping geolocalizzati animati."""
    BLOBS = [[(0.14, 0.34), (0.30, 0.30), (0.34, 0.52), (0.22, 0.66), (0.10, 0.56)],
             [(0.44, 0.30), (0.66, 0.28), (0.64, 0.60), (0.50, 0.58), (0.46, 0.44)],
             [(0.70, 0.34), (0.86, 0.36), (0.88, 0.62), (0.74, 0.64)]]

    def __init__(self, canvas, data, accent=None):
        self.c = canvas
        self.accent = accent or THEME["accent"]
        self.frame = 0
        self.running = True
        self.after_id = None
        pts = []
        for it in data["identities"]:
            pts.append((it["geo"][0], it["geo"][1], it["name"], it["threat"]))
        self.points = pts
        self._tick()

    def _tick(self):
        if not self.running or not self.c.winfo_exists():
            return
        try:
            w, h = self.c.winfo_width(), self.c.winfo_height()
            if w <= 1:
                w, h = 800, 560
            self.c.delete("all")
            self.c.create_rectangle(0, 0, w, h, fill=THEME["bg2"], outline="")
            # griglia
            for gx in range(0, w, 46):
                self.c.create_line(gx, 0, gx, h, fill=lerp_color(THEME["bg2"], THEME["line"], 0.5))
            for gy in range(0, h, 46):
                self.c.create_line(0, gy, w, gy, fill=lerp_color(THEME["bg2"], THEME["line"], 0.5))
            # continenti
            for blob in self.BLOBS:
                self.c.create_polygon([(x * w, y * h) for x, y in blob],
                                      fill=THEME["panel"],
                                      outline=lerp_color(self.accent, THEME["bg"], 0.7))
            # archi tra i punti
            for i in range(len(self.points) - 1):
                x1, y1 = self.points[i][0] * w, self.points[i][1] * h
                x2, y2 = self.points[i + 1][0] * w, self.points[i + 1][1] * h
                mx, my = (x1 + x2) / 2, min(y1, y2) - 50
                self._curve(x1, y1, mx, my, x2, y2)
            # ping
            for (fx, fy, name, threat) in self.points:
                x, y = fx * w, fy * h
                col = {"LOW": THEME["green"], "MEDIUM": THEME["amber"],
                       "HIGH": THEME["red"]}.get(threat, self.accent)
                for k in range(3):
                    rad = 6 + ((self.frame * 2 + k * 16) % 48)
                    self.c.create_oval(x - rad, y - rad, x + rad, y + rad,
                                       outline=lerp_color(col, THEME["bg2"], rad / 54))
                self.c.create_oval(x - 4, y - 4, x + 4, y + 4, fill=col, outline=THEME["white"])
                self.c.create_text(x, y - 16, text=name, fill=THEME["text"], font=(MONO, 9, "bold"))
            self.c.create_text(14, h - 12, anchor="w", fill=THEME["dim"], font=(MONO, 9),
                               text=f"GEO-INT · posizioni simulate · by {CREATOR}")
        except tk.TclError:
            return
        self.frame += 1
        self.after_id = self.c.after(55, self._tick)

    def _curve(self, x1, y1, mx, my, x2, y2):
        prev = (x1, y1)
        n = 16
        for s in range(1, n + 1):
            t = s / n
            x = (1 - t) ** 2 * x1 + 2 * (1 - t) * t * mx + t * t * x2
            y = (1 - t) ** 2 * y1 + 2 * (1 - t) * t * my + t * t * y2
            self.c.create_line(prev[0], prev[1], x, y,
                               fill=lerp_color(self.accent, THEME["bg2"], 0.55))
            prev = (x, y)
        t = ((self.frame * 0.02)) % 1.0
        px = (1 - t) ** 2 * x1 + 2 * (1 - t) * t * mx + t * t * x2
        py = (1 - t) ** 2 * y1 + 2 * (1 - t) * t * my + t * t * y2
        self.c.create_oval(px - 3, py - 3, px + 3, py + 3, fill=self.accent, outline="")

    def stop(self):
        self.running = False
        if self.after_id:
            try:
                self.c.after_cancel(self.after_id)
            except Exception:
                pass


# ===========================================================================
#  APP PRINCIPALE
# ===========================================================================
class SpyOSINTApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"◈ {APP_NAME} — by {CREATOR}")
        self.root.configure(bg=THEME["bg"])
        self.root.geometry("1560x940")
        self.root.minsize(1180, 740)
        self._maximize(self.root)

        self.results = None
        self.current_target = ""
        self.search_active = False
        self.force_fresh = False
        self._img_refs = []
        self._title_phase = 0.0
        self.net_anim = None
        self.geo_anim = None

        self._setup_db()
        self._style()
        self._build_ui()
        self._animate_title()
        self._clock()

    @staticmethod
    def _maximize(win):
        for a in (lambda: win.state("zoomed"), lambda: win.attributes("-zoomed", True)):
            try:
                a(); return
            except Exception:
                continue

    def _setup_db(self):
        try:
            self.conn = sqlite3.connect("orion_cache.db", check_same_thread=False)
            self.conn.execute("CREATE TABLE IF NOT EXISTS cache(target TEXT PRIMARY KEY, "
                              "data TEXT, ts DATETIME DEFAULT CURRENT_TIMESTAMP)")
            self.conn.commit()
        except Exception:
            self.conn = None

    def _cache_put(self, t, d):
        if self.conn:
            try:
                self.conn.execute("INSERT OR REPLACE INTO cache(target,data) VALUES(?,?)",
                                  (t.lower(), json.dumps(d)))
                self.conn.commit()
            except Exception:
                pass

    def _cache_get(self, t):
        if self.conn:
            try:
                r = self.conn.execute("SELECT data FROM cache WHERE target=?",
                                      (t.lower(),)).fetchone()
                return json.loads(r[0]) if r else None
            except Exception:
                return None
        return None

    def _style(self):
        st = ttk.Style()
        try:
            st.theme_use("clam")
        except Exception:
            pass
        st.configure("Orion.Horizontal.TProgressbar", troughcolor=THEME["panel2"],
                     background=THEME["accent"], borderwidth=0, thickness=14)
        st.configure("Orion.TNotebook", background=THEME["bg"], borderwidth=0)
        st.configure("Orion.TNotebook.Tab", background=THEME["panel"], foreground=THEME["dim"],
                     padding=[16, 8], font=(UI, 10, "bold"), borderwidth=0)
        st.map("Orion.TNotebook.Tab", background=[("selected", THEME["panel2"])],
               foreground=[("selected", THEME["accent"])])

    # ---- UI -------------------------------------------------------------
    def _build_ui(self):
        banner = tk.Frame(self.root, bg="#20140a")
        banner.pack(fill="x")
        tk.Label(banner, text=f"⚠  SIMULAZIONE — nessuna ricerca reale, dati casuali a scopo "
                              f"di intrattenimento.   ◆  {APP_NAME}  ·  created by {CREATOR}",
                 bg="#20140a", fg=THEME["amber"], font=(UI, 10, "bold")).pack(pady=4)

        main = tk.Frame(self.root, bg=THEME["bg"])
        main.pack(fill="both", expand=True, padx=16, pady=(8, 14))

        header = tk.Frame(main, bg=THEME["bg"])
        header.pack(fill="x", pady=(0, 10))
        if PIL_OK:
            logo = render_logo()
            self._logo_img = ImageTk.PhotoImage(logo)
            tk.Label(header, image=self._logo_img, bg=THEME["bg"]).pack(side="left")
        else:
            tk.Label(header, text="◈ ORION", font=(MONO, 22, "bold"), bg=THEME["bg"],
                     fg=THEME["accent"]).pack(side="left")
        righth = tk.Frame(header, bg=THEME["bg"])
        righth.pack(side="right")
        self.clock_label = tk.Label(righth, text="", font=(MONO, 12), bg=THEME["bg"],
                                    fg=THEME["dim"])
        self.clock_label.pack(anchor="e")
        tk.Label(righth, text=f"◤ operator: {CREATOR}", font=(MONO, 11, "bold"),
                 bg=THEME["bg"], fg=THEME["magenta"]).pack(anchor="e")

        self.status_label = tk.Label(main, text="● SISTEMA OPERATIVO — in attesa del bersaglio",
                                     font=(MONO, 10, "bold"), bg=THEME["bg"], fg=THEME["green"],
                                     anchor="w")
        self.status_label.pack(fill="x", pady=(0, 8))

        body = tk.Frame(main, bg=THEME["bg"])
        body.pack(fill="both", expand=True)
        left = tk.Frame(body, bg=THEME["bg"], width=380)
        left.pack(side="left", fill="y", padx=(0, 14))
        left.pack_propagate(False)
        right = tk.Frame(body, bg=THEME["bg"])
        right.pack(side="right", fill="both", expand=True)
        self._build_left(left)
        self._build_right(right)

    def _panel(self, parent, title, color):
        return tk.LabelFrame(parent, text=" " + title + " ", font=(UI, 11, "bold"),
                             bg=THEME["panel"], fg=color, relief="flat", bd=0,
                             highlightbackground=THEME["line"], highlightthickness=1,
                             padx=14, pady=12)

    def _build_left(self, parent):
        ctrl = self._panel(parent, "🎯 MISSION CONTROL", THEME["accent"])
        ctrl.pack(fill="x", pady=(0, 12))
        tk.Label(ctrl, text="NOME BERSAGLIO", font=(UI, 9, "bold"), bg=THEME["panel"],
                 fg=THEME["dim"]).pack(anchor="w")
        row = tk.Frame(ctrl, bg=THEME["panel"])
        row.pack(fill="x", pady=(4, 10))
        self.input = tk.Entry(row, font=(MONO, 13), bg=THEME["bg2"], fg=THEME["accent"],
                              insertbackground=THEME["accent"], relief="flat",
                              highlightbackground=THEME["line"], highlightthickness=1)
        self.input.pack(side="left", fill="x", expand=True, ipady=6)
        self.input.bind("<Return>", lambda e: self.start_search())
        tk.Button(row, text="⌕", font=(UI, 13, "bold"), bg=THEME["accent"], fg="black",
                  relief="flat", width=3, command=self.start_search).pack(side="left", padx=(6, 0))
        self.launch_btn = tk.Button(ctrl, text="▶  AVVIA SCANSIONE OSINT", font=(UI, 12, "bold"),
                                    bg=THEME["accent"], fg="black", relief="flat", height=2,
                                    command=self.start_search)
        self.launch_btn.pack(fill="x", pady=(0, 6))
        brow = tk.Frame(ctrl, bg=THEME["panel"])
        brow.pack(fill="x")
        tk.Button(brow, text="🌐 DEEP SCAN", font=(UI, 10, "bold"), bg=THEME["panel2"],
                  fg=THEME["accent"], relief="flat", command=self.deep_scan).pack(
            side="left", expand=True, fill="x", padx=(0, 4))
        tk.Button(brow, text="⏹ STOP", font=(UI, 10, "bold"), bg=THEME["panel2"],
                  fg=THEME["red"], relief="flat", command=self.stop_search).pack(
            side="left", expand=True, fill="x", padx=(4, 0))
        self.progress = ttk.Progressbar(ctrl, style="Orion.Horizontal.TProgressbar",
                                        mode="determinate")
        self.progress.pack(fill="x", pady=(10, 4))
        self.progress_label = tk.Label(ctrl, text="pronto", font=(MONO, 9), bg=THEME["panel"],
                                       fg=THEME["green"], anchor="w")
        self.progress_label.pack(fill="x")

        # STRUMENTI
        tools = self._panel(parent, "🧰 STRUMENTI", THEME["green"])
        tools.pack(fill="x", pady=(0, 12))
        grid = tk.Frame(tools, bg=THEME["panel"])
        grid.pack(fill="x")
        specs = [("💀 GALLERY", THEME["magenta"], self.open_gallery),
                 ("🎞 SLIDESHOW", THEME["accent"], self.open_slideshow),
                 ("📄 ESPORTA", THEME["amber"], self.export_report),
                 ("📋 COPIA", THEME["accent2"], self.copy_summary),
                 ("🎲 CASUALE", THEME["green"], self.random_target),
                 ("🔁 RIGENERA", THEME["dim"], self.regenerate)]
        for i, (txt, col, cmd) in enumerate(specs):
            tk.Button(grid, text=txt, font=(UI, 10, "bold"), bg=THEME["card"], fg=col,
                      relief="flat", command=cmd, activebackground=THEME["panel2"]
                      ).grid(row=i // 2, column=i % 2, sticky="ew", padx=3, pady=3)
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)

        ex = self._panel(parent, "⚡ BERSAGLI RAPIDI", THEME["magenta"])
        ex.pack(fill="x")
        for name in ["Mario Rossi", "John Smith", "Anna Müller", "Luca Bianchi", "Marco Esposito"]:
            tk.Button(ex, text="🎯  " + name, font=(UI, 10), bg=THEME["card"], fg=THEME["text"],
                      relief="flat", anchor="w", activebackground=THEME["panel2"],
                      activeforeground=THEME["accent"],
                      command=lambda n=name: self.load_example(n)).pack(fill="x", pady=2)

    def _build_right(self, parent):
        self.notebook = ttk.Notebook(parent, style="Orion.TNotebook")
        self.notebook.pack(fill="both", expand=True)
        self.tab_overview = tk.Frame(self.notebook, bg=THEME["panel"])
        self.tab_social = tk.Frame(self.notebook, bg=THEME["panel"])
        self.tab_ident = tk.Frame(self.notebook, bg=THEME["panel"])
        self.tab_net = tk.Frame(self.notebook, bg=THEME["bg"])
        self.tab_geo = tk.Frame(self.notebook, bg=THEME["bg"])
        self.tab_time = tk.Frame(self.notebook, bg=THEME["panel"])
        self.tab_foot = tk.Frame(self.notebook, bg=THEME["panel"])
        self.tab_behav = tk.Frame(self.notebook, bg=THEME["panel"])
        for tab, label in [(self.tab_overview, "📊 INTELLIGENCE"), (self.tab_social, "👥 SOCIAL"),
                           (self.tab_ident, "🕵 IDENTITÀ"), (self.tab_net, "🕸 RETE"),
                           (self.tab_geo, "🗺 MAPPA"), (self.tab_time, "🕐 TIMELINE"),
                           (self.tab_foot, "🌐 FOOTPRINT"), (self.tab_behav, "📈 COMPORTAMENTO")]:
            self.notebook.add(tab, text=label)
        self._build_overview(self.tab_overview)
        self.social_text = self._console(self.tab_social, "👥 SOCIAL — avvia una scansione")
        self.ident_text = self._console(self.tab_ident, "🕵 IDENTITÀ — avvia una scansione")
        self.time_text = self._console(self.tab_time, "🕐 TIMELINE — avvia una scansione")
        self.foot_text = self._console(self.tab_foot, "🌐 FOOTPRINT — avvia una scansione")
        self.behav_text = self._console(self.tab_behav, "📈 COMPORTAMENTO — avvia una scansione")
        self.net_canvas = tk.Canvas(self.tab_net, bg=THEME["bg"], highlightthickness=0)
        self.net_canvas.pack(fill="both", expand=True)
        self.geo_canvas = tk.Canvas(self.tab_geo, bg=THEME["bg2"], highlightthickness=0)
        self.geo_canvas.pack(fill="both", expand=True)
        for cv, msg in [(self.net_canvas, "🕸 RELATION MAP"), (self.geo_canvas, "🗺 GEO MAP")]:
            cv.create_text(400, 250, text=f"{msg}\n\nAvvia una scansione.\nby {CREATOR}",
                           fill=THEME["dim"], font=(MONO, 14), justify="center")

    def _console(self, parent, placeholder):
        wrap = tk.Frame(parent, bg=THEME["panel"])
        wrap.pack(fill="both", expand=True, padx=12, pady=12)
        txt = scrolledtext.ScrolledText(wrap, bg=THEME["bg2"], fg=THEME["text"], font=(MONO, 10),
                                        insertbackground=THEME["accent"], relief="flat",
                                        padx=12, pady=10, wrap="word",
                                        highlightbackground=THEME["line"], highlightthickness=1)
        txt.pack(fill="both", expand=True)
        for tag, col, fnt in [("h", THEME["accent"], (MONO, 12, "bold")),
                              ("k", THEME["dim"], (MONO, 10)), ("v", THEME["white"], (MONO, 10, "bold")),
                              ("ok", THEME["green"], (MONO, 10)), ("warn", THEME["amber"], (MONO, 10)),
                              ("bad", THEME["red"], (MONO, 10))]:
            txt.tag_config(tag, foreground=col, font=fnt)
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
        self.confidence_label = tk.Label(threat, text="CONFIDENCE: —  |  CLEARANCE: —  |  RISK: —",
                                         font=(MONO, 11), bg=THEME["card"], fg=THEME["dim"])
        self.confidence_label.pack(pady=(0, 12))

        grid = tk.Frame(content, bg=THEME["panel"])
        grid.pack(fill="both", expand=True)
        bf = tk.Frame(grid, bg=THEME["panel"])
        bf.pack(side="left", fill="both", expand=True, padx=(0, 8))
        tk.Label(bf, text="📋 BRIEFING", font=(UI, 11, "bold"), bg=THEME["panel"],
                 fg=THEME["accent"], anchor="w").pack(fill="x")
        self.briefing_text = scrolledtext.ScrolledText(bf, bg=THEME["bg2"], fg=THEME["text"],
                                                       font=(MONO, 10), relief="flat", padx=10,
                                                       pady=8, wrap="word",
                                                       highlightbackground=THEME["line"],
                                                       highlightthickness=1)
        self.briefing_text.pack(fill="both", expand=True, pady=(6, 0))
        for tag, col, fnt in [("h", THEME["accent"], (MONO, 12, "bold")),
                              ("k", THEME["dim"], (MONO, 10)), ("v", THEME["white"], (MONO, 10, "bold"))]:
            self.briefing_text.tag_config(tag, foreground=col, font=fnt)
        self.briefing_text.insert("1.0", f"In attesa del bersaglio.\nby {CREATOR}")
        self.briefing_text.config(state="disabled")

        rf = tk.Frame(grid, bg=THEME["panel"], width=330)
        rf.pack(side="right", fill="y", padx=(8, 0))
        rf.pack_propagate(False)
        self.radar_label = tk.Label(rf, bg=THEME["panel"], text="◎ RADAR",
                                    fg=THEME["dim"], font=(MONO, 11))
        self.radar_label.pack(pady=(0, 8))
        tiles = tk.Frame(rf, bg=THEME["panel"])
        tiles.pack(fill="both", expand=True)
        self.stat_rows = {}
        specs = [("photos", "💀 FOTO", THEME["magenta"]), ("identities", "🎯 IDENTITÀ", THEME["accent"]),
                 ("socials", "👥 SOCIAL", THEME["accent2"]), ("emails", "📧 EMAIL", THEME["accent"]),
                 ("breaches", "⚠ BREACH", THEME["red"]), ("records", "📊 RECORD", THEME["amber"]),
                 ("exposure", "🌐 ESPOS.", THEME["green"]), ("privacy", "🔐 PRIVACY", THEME["magenta"]),
                 ("risk", "📛 RISCHIO", THEME["red"]), ("confidence", "✔ CONF.", THEME["accent"])]
        for i, (key, label, col) in enumerate(specs):
            self.stat_rows[key] = self._tile(tiles, label, col, i)
        tiles.columnconfigure(0, weight=1)
        tiles.columnconfigure(1, weight=1)

    def _tile(self, parent, label, color, i):
        f = tk.Frame(parent, bg=THEME["card"], highlightbackground=THEME["line"],
                     highlightthickness=1)
        f.grid(row=i // 2, column=i % 2, sticky="nsew", padx=3, pady=3)
        tk.Label(f, text=label, font=(UI, 8, "bold"), bg=THEME["card"], fg=color,
                 anchor="w").pack(fill="x", padx=8, pady=(5, 0))
        val = tk.Label(f, text="—", font=(MONO, 15, "bold"), bg=THEME["card"], fg=THEME["white"],
                       anchor="w")
        val.pack(fill="x", padx=8, pady=(0, 5))
        return val

    # ---- animazioni UI --------------------------------------------------
    def _animate_title(self):
        if not self.root.winfo_exists():
            return
        self._title_phase = (self._title_phase + 0.06) % (2 * math.pi)
        self.status_label.config(fg=lerp_color(THEME["green"], THEME["accent"],
                                               (math.sin(self._title_phase) + 1) / 2 * 0.5))
        self.root.after(120, self._animate_title)

    def _clock(self):
        if not self.root.winfo_exists():
            return
        self.clock_label.config(text="⧗ " + datetime.now().strftime("%Y-%m-%d  %H:%M:%S"))
        self.root.after(1000, self._clock)

    def _status(self, msg, color=None):
        self.status_label.config(text="● " + msg, fg=color or THEME["green"])

    def _progress(self, v, msg):
        self.progress["value"] = v
        self.progress_label.config(text=msg)
        self.root.update_idletasks()

    # ---- azioni strumenti ----------------------------------------------
    def load_example(self, name):
        self.input.delete(0, tk.END)
        self.input.insert(0, name)
        self.start_search()

    def deep_scan(self):
        self.surveillance_level = 3
        self.start_search()

    def random_target(self):
        name = f"{random.choice(FIRST)} {random.choice(LAST)}"
        self.load_example(name)

    def regenerate(self):
        if not self.current_target:
            messagebox.showinfo("Rigenera", "Prima esegui una scansione.")
            return
        self.force_fresh = True
        self.input.delete(0, tk.END)
        self.input.insert(0, self.current_target)
        self.start_search()

    def copy_summary(self):
        if not self.results:
            messagebox.showinfo("Copia", "Prima esegui una scansione.")
            return
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(self._report_text(self.results))
            self._status("SOMMARIO COPIATO NEGLI APPUNTI", THEME["green"])
        except Exception as e:
            messagebox.showerror("Copia", str(e))

    def export_report(self):
        if not self.results:
            messagebox.showinfo("Esporta", "Prima esegui una scansione.")
            return
        slug = _slug(self.results["target"])
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = os.path.join(os.getcwd(), f"dossier_{slug}_{stamp}")
        try:
            with open(base + ".txt", "w", encoding="utf-8") as f:
                f.write(self._report_text(self.results))
            with open(base + ".json", "w", encoding="utf-8") as f:
                json.dump(self.results, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("Esporta",
                                f"Dossier salvato (SIMULAZIONE):\n\n{base}.txt\n{base}.json\n\n"
                                f"created by {CREATOR}")
            self._status("DOSSIER ESPORTATO", THEME["green"])
        except Exception as e:
            messagebox.showerror("Esporta", str(e))

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
            messagebox.showerror("Pillow mancante", "Installa Pillow:\n\npip install Pillow")
            return
        self.search_active = True
        self.current_target = target
        self.launch_btn.config(state="disabled")
        self._status(f"SCANSIONE OSINT ATTIVA: {target}", THEME["accent"])
        if not hasattr(self, "surveillance_level"):
            self.surveillance_level = 1
        threading.Thread(target=self._run, args=(target,), daemon=True).start()

    def _run(self, target):
        steps = [(8, "Inizializzo i nodi..."), (22, "Accesso alle banche dati..."),
                 (38, "Deploy crawler deep web..."), (54, "Scansione social..."),
                 (68, "Mappatura footprint..."), (80, "Raccolta asset visivi..."),
                 (90, "Valutazione minaccia..."), (100, "Dossier pronto.")]
        for v, m in steps:
            if not self.search_active:
                self.root.after(0, lambda: self.launch_btn.config(state="normal"))
                return
            self.root.after(0, self._progress, v, m)
            time.sleep(0.09)
        data = None
        if not self.force_fresh and getattr(self, "surveillance_level", 1) < 3:
            data = self._cache_get(target)
        if not data:
            data = build_dossier(target)
            self._cache_put(target, data)
        self.results = data
        self.force_fresh = False
        self.surveillance_level = 1
        self.root.after(0, self._render, data)

    # ---- render ---------------------------------------------------------
    def _set(self, widget, chunks):
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
            self._render_timeline(data)
            self._render_footprint(data)
            self._render_behavior(data)
            # animatori canvas
            if self.net_anim:
                self.net_anim.stop()
            if self.geo_anim:
                self.geo_anim.stop()
            self.net_canvas.delete("all")
            self.geo_canvas.delete("all")
            self.net_anim = NetworkGraph(self.net_canvas, data, THEME["accent"])
            self.geo_anim = GeoMap(self.geo_canvas, data, THEME["accent"])
            self._status(f"COMPLETATO: {data['target']} — {len(data['photos'])} foto / "
                         f"{len(data['identities'])} identità · by {CREATOR}", THEME["green"])
        except Exception as e:
            messagebox.showerror("Errore", str(e))
        finally:
            self.launch_btn.config(state="normal")
            self.search_active = False

    def _render_overview(self, data):
        s = data["summary"]; fp = data["footprint"]; idt = data["identities"]
        col = {"LOW": THEME["green"], "MEDIUM": THEME["amber"],
               "HIGH": THEME["red"]}.get(s["threat"], THEME["dim"])
        self.threat_label.config(text=f"IDENTITÀ MULTIPLE — MINACCIA {s['threat']}", fg=col)
        self.confidence_label.config(
            text=f"CONFIDENCE: {s['confidence']}%  |  CLEARANCE: {s['clearance']}  "
                 f"|  RISK: {s['risk']}/100", fg=THEME["accent"])
        # radar
        avg_social = int(sum(i["social_score"] for i in idt) / len(idt))
        axes = [("ESPOS.", fp["exposure"]), ("RISK", s["risk"]), ("SOCIAL", avg_social),
                ("BREACH", min(100, fp["breaches"] * 25)),
                ("VISIB.", 100 - fp["privacy"]), ("CONF.", s["confidence"])]
        radar = render_radar_chart(axes, size=250, accent=THEME["accent"])
        if radar:
            self._radar_img = ImageTk.PhotoImage(radar)
            self.radar_label.config(image=self._radar_img, text="")
        chunks = [(f"DOSSIER OSINT — {data['target']}\n", "h"),
                  (f"created by {CREATOR}\n", "k"), ("═" * 44 + "\n\n", "k"),
                  ("IDENTITÀ RILEVATE: ", "k"), (f"{len(idt)}\n", "v"),
                  ("  ▸ PRIMARIA: ", "k"), (f"{idt[0]['name']}\n", "v"),
                  ("  ▸ ALIAS: ", "k"), (", ".join(idt[0]['aliases']) + "\n", "v"),
                  ("  ▸ LUOGO: ", "k"), (f"{idt[0]['location']}\n", "v"),
                  ("  ▸ RUOLO: ", "k"), (f"{idt[0]['role']}\n\n", "v"),
                  ("VISUAL INTEL:\n", "h"),
                  ("  📧 email: ", "k"), (f"{len(data['emails'])} ", "v"),
                  (f"({fp['breaches']} compromesse)\n", "k"),
                  ("  👥 social: ", "k"), (f"{len(data['socials'])} piattaforme\n", "v"),
                  ("  💀 foto: ", "k"), (f"{len(data['photos'])} asset\n\n", "v"),
                  ("IDENTITY MATRIX:\n", "h")]
        for i, it in enumerate(idt):
            chunks += [(f"  {i+1}. {it['name']} ", "v"),
                       (f"— {it['confidence']}% — "
                        f"{sum(1 for p in data['photos'] if p['identity']==i)} foto\n", "k")]
        self._set(self.briefing_text, chunks)
        vals = {"socials": len(data["socials"]), "emails": len(data["emails"]),
                "photos": len(data["photos"]), "breaches": fp["breaches"], "records": fp["records"],
                "identities": len(idt), "exposure": f"{fp['exposure']}/100",
                "privacy": f"{fp['privacy']}/100", "risk": f"{s['risk']}/100",
                "confidence": f"{s['confidence']}%"}
        for k, v in vals.items():
            self.stat_rows[k].config(text=str(v))

    def _render_social(self, data):
        chunks = [("👥 SOCIAL MEDIA INTELLIGENCE\n", "h"),
                  (f"created by {CREATOR}\n", "k"), ("═" * 44 + "\n\n", "k")]
        for p in data["socials"]:
            ver = ("✔ verificato", "ok") if p["verified"] else ("✘ non verificato", "k")
            chunks += [(f"{p['glyph']}  {p['platform']}\n", "h"),
                       ("   handle: ", "k"), (f"{p['handle']}\n", "v"),
                       ("   follower: ", "k"), (f"{p['followers']}", "v"),
                       (f"   post: {p['posts']}\n", "k"),
                       ("   attività: ", "k"), (f"{p['activity']}", "v"),
                       (f"   visto: {p['last_seen']}   ", "k"), (ver[0] + "\n\n", ver[1])]
        chunks += [(f"TOTALE: {len(data['socials'])} piattaforme · by {CREATOR}\n", "warn")]
        self._set(self.social_text, chunks)

    def _render_identities(self, data):
        chunks = [("🕵 ANALISI IDENTITÀ MULTIPLE\n", "h"),
                  (f"created by {CREATOR}\n", "k"), ("═" * 44 + "\n\n", "k")]
        for i, it in enumerate(data["identities"]):
            tcol = {"LOW": "ok", "MEDIUM": "warn", "HIGH": "bad"}.get(it["threat"], "k")
            head = "PRIMARIA" if i == 0 else f"SECONDARIA #{i}"
            b = it["biometrics"]
            chunks += [(f"🎯 {head}: {it['name']}\n", "h"),
                       ("   confidence: ", "k"), (f"{it['confidence']}%\n", "v"),
                       ("   età: ", "k"), (f"{it['age']}   ", "v"),
                       ("luogo: ", "k"), (f"{it['location']}\n", "v"),
                       ("   ruolo: ", "k"), (f"{it['role']}\n", "v"),
                       ("   minaccia: ", "k"), (f"{it['threat']}\n", tcol),
                       ("   biometria: ", "k"),
                       (f"{b['height']}, {b['eyes']}, {b['build']}\n", "v"),
                       ("   segni: ", "k"), (f"{b['marks']}\n", "v"),
                       ("   alias: ", "k"), (", ".join(it["aliases"]) + "\n\n", "v")]
        self._set(self.ident_text, chunks)

    def _render_timeline(self, data):
        chunks = [("🕐 TIMELINE ATTIVITÀ\n", "h"),
                  (f"created by {CREATOR}\n", "k"), ("═" * 44 + "\n\n", "k")]
        for ev in data["timeline"]:
            tag = {"info": "ok", "warn": "warn", "bad": "bad"}.get(ev["sev"], "k")
            glyph = {"info": "●", "warn": "▲", "bad": "✖"}.get(ev["sev"], "•")
            chunks += [(f"  {ev['date']}  ", "k"), (f"{glyph} {ev['event']}\n", tag)]
        chunks += [(f"\n{len(data['timeline'])} eventi ricostruiti (SIM) · by {CREATOR}\n", "warn")]
        self._set(self.time_text, chunks)

    def _render_footprint(self, data):
        fp = data["footprint"]
        chunks = [("🌐 DIGITAL FOOTPRINT\n", "h"),
                  (f"created by {CREATOR}\n", "k"), ("═" * 44 + "\n\n", "k")]
        for k, v in [("domini registrati", fp["domains"]), ("piattaforme social", fp["platforms"]),
                     ("record pubblici", fp["records"]), ("data breach", fp["breaches"]),
                     ("esposizione", f"{fp['exposure']}/100"), ("privacy", f"{fp['privacy']}/100"),
                     ("presenza online", fp["presence"])]:
            chunks += [(f"  • {k}: ", "k"), (f"{v}\n", "v")]
        vtag = "bad" if fp["privacy"] < 40 else "warn"
        chunks += [("\n⚠ SICUREZZA:\n", "h"),
                   ("  esposizione privacy: ", "k"), (f"{100 - fp['privacy']}%\n", "v"),
                   ("  vulnerabilità: ", "k"),
                   (("ALTA" if fp["privacy"] < 40 else "MEDIA") + "\n", vtag),
                   ("\n💀 RACCOMANDAZIONI:\n", "h"),
                   ("  ▸ sorveglianza multi-identità continua\n", "k"),
                   ("  ▸ analisi di tutti gli asset foto\n", "k"),
                   (f"  ▸ report generato da {CREATOR}\n", "k")]
        self._set(self.foot_text, chunks)

    def _render_behavior(self, data):
        b = data["behavior"]; fin = data["finance"]
        chunks = [("📈 ANALISI COMPORTAMENTALE\n", "h"),
                  (f"created by {CREATOR}\n", "k"), ("═" * 44 + "\n\n", "k")]
        for k, v in [("attività online", b["online"]), ("abitudini d'acquisto", b["shopping"]),
                     ("frequenza viaggi", b["travel"]), ("engagement sociale", b["engagement"])]:
            chunks += [(f"  • {k}: ", "k"), (f"{v}\n", "v")]
        st = b["sentiment"]
        stag = "ok" if st > 20 else "bad" if st < -10 else "warn"
        chunks += [("  • sentiment: ", "k"), (f"{st:+d}\n\n", stag),
                   ("💰 PROFILO FINANZIARIO (simulato):\n", "h"),
                   ("  • carte: ", "k"), (f"{fin['cards']}  {fin['last4']}\n", "v"),
                   ("  • conti: ", "k"), (f"{fin['accounts']}\n", "v"),
                   ("  • wallet crypto: ", "k"), (f"{fin['wallets']}\n", "v"),
                   ("  • transazioni/mese: ", "k"), (f"{fin['monthly']}\n\n", "v"),
                   ("🎯 PREDITTIVA:\n", "h"),
                   ("  ▸ priorità monitoraggio: MOLTO ALTA\n", "warn"),
                   (f"  ▸ analisi by {CREATOR}\n", "k")]
        self._set(self.behav_text, chunks)

    # ===================================================================
    #  GALLERY + SLIDESHOW
    # ===================================================================
    def open_gallery(self):
        if not self.results:
            messagebox.showwarning("Nessun dato", "Esegui prima una scansione.")
            return
        if not PIL_OK:
            messagebox.showerror("Pillow", "Installa Pillow: pip install Pillow")
            return
        win = tk.Toplevel(self.root)
        win.title(f"💀 CINEMATIC GALLERY — by {CREATOR}")
        win.configure(bg=THEME["bg"])
        win.geometry("1500x900")
        try:
            win.attributes("-fullscreen", True)
        except Exception:
            self._maximize(win)
        canvas = tk.Canvas(win, bg=THEME["bg"], highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        intro = CinematicIntro(canvas, self.results["target"],
                               on_done=lambda: self._gallery(win, canvas), accent=THEME["accent"])
        win.bind("<Escape>", lambda e: (intro.stop(), win.destroy()))
        win.bind("<space>", lambda e: (intro.stop(), self._gallery(win, canvas)))
        win.bind("<Return>", lambda e: (intro.stop(), self._gallery(win, canvas)))
        win.focus_set()

    def _gallery(self, win, canvas):
        if not win.winfo_exists():
            return
        try:
            win.attributes("-fullscreen", False)
        except Exception:
            pass
        canvas.destroy()
        self._maximize(win)
        data = self.results
        head = tk.Frame(win, bg=THEME["bg"])
        head.pack(fill="x", padx=24, pady=(16, 6))
        tk.Label(head, text=f"💀  DOSSIER VISIVO — {data['target']}", font=(MONO, 22, "bold"),
                 bg=THEME["bg"], fg=THEME["accent"]).pack(side="left")
        rc = tk.Frame(head, bg=THEME["bg"])
        rc.pack(side="right")
        tk.Button(rc, text="🎞 SLIDESHOW", font=(UI, 11, "bold"), bg=THEME["panel2"],
                  fg=THEME["accent"], relief="flat", command=self.open_slideshow).pack(side="left", padx=6)
        tk.Button(rc, text="✕ CHIUDI (Esc)", font=(UI, 11, "bold"), bg=THEME["panel2"],
                  fg=THEME["red"], relief="flat", command=win.destroy).pack(side="left")
        s = data["summary"]
        tk.Label(win, text=f"🎯 {len(data['identities'])} identità · 📸 {len(data['photos'])} asset "
                          f"· ⚠ {s['threat']} · conf {s['confidence']}%   ◆  created by {CREATOR}",
                 font=(UI, 12), bg=THEME["bg"], fg=THEME["dim"]).pack(anchor="w", padx=26)
        tk.Label(win, text="SIMULAZIONE — ritratti generati proceduralmente, non persone reali.",
                 font=(UI, 9, "italic"), bg=THEME["bg"], fg=THEME["amber"]).pack(anchor="w", padx=26)
        nb = ttk.Notebook(win, style="Orion.TNotebook")
        nb.pack(fill="both", expand=True, padx=16, pady=12)
        win.bind("<Escape>", lambda e: win.destroy())
        for it in data["identities"]:
            tab = tk.Frame(nb, bg=THEME["bg"])
            nb.add(tab, text=f"👤 {it['name']}")
            self._grid(tab, [p for p in data["photos"] if p["identity"] == it["index"]], 3, it)
        tab_all = tk.Frame(nb, bg=THEME["bg"])
        nb.add(tab_all, text=f"💀 TUTTI ({len(data['photos'])})")
        self._grid(tab_all, data["photos"], 5, None)

    def _scrollable(self, parent):
        cont = tk.Frame(parent, bg=THEME["bg"])
        cont.pack(fill="both", expand=True)
        canvas = tk.Canvas(cont, bg=THEME["bg"], highlightthickness=0)
        sb = ttk.Scrollbar(cont, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=THEME["bg"])
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        wid = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(wid, width=e.width))
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(
            int(-e.delta / 120) if e.delta else 0, "units"))
        return inner

    def _grid(self, parent, photos, cols, header):
        inner = self._scrollable(parent)
        if header:
            it = header
            tk.Label(inner, text=f"📋 {it['name']} · conf {it['confidence']}% · {it['location']} "
                                f"· {it['role']} · minaccia {it['threat']}", font=(UI, 11),
                     bg=THEME["bg"], fg=THEME["accent"], anchor="w").pack(fill="x", padx=18,
                                                                         pady=(14, 8))
        grid = tk.Frame(inner, bg=THEME["bg"])
        grid.pack(fill="both", expand=True, padx=14, pady=8)
        for c in range(cols):
            grid.columnconfigure(c, weight=1)
        if not photos:
            tk.Label(grid, text="Nessun asset per questa identità.", font=(UI, 13),
                     bg=THEME["bg"], fg=THEME["dim"]).pack(pady=40)
            return
        for i, photo in enumerate(photos):
            self._card(grid, photo).grid(row=i // cols, column=i % cols, padx=10, pady=10, sticky="n")

    def _card(self, parent, photo):
        seed = f"{self.results['target']}|{photo['id']}"
        img = generate_portrait(seed, (240, 290), THEME["accent"], photo["identity_name"],
                                f"{photo['tag']} · {photo['location']}", photo["matched"])
        tkimg = ImageTk.PhotoImage(img)
        self._img_refs.append(tkimg)
        card = tk.Frame(parent, bg=THEME["card"], highlightbackground=THEME["line"],
                        highlightthickness=1, cursor="hand2")
        lbl = tk.Label(card, image=tkimg, bg=THEME["card"], bd=0)
        lbl.pack(padx=8, pady=(8, 4))
        meta = tk.Frame(card, bg=THEME["card"])
        meta.pack(fill="x", padx=8, pady=(0, 8))
        icol = (THEME["green"] if photo["intel"] >= 7 else THEME["amber"]
                if photo["intel"] >= 5 else THEME["red"])
        tk.Label(meta, text=f"▮ INTEL {photo['intel']}/10", font=(MONO, 9, "bold"),
                 bg=THEME["card"], fg=icol).pack(side="left")
        tk.Label(meta, text=f"{photo['quality']} · {photo['date']}", font=(MONO, 8),
                 bg=THEME["card"], fg=THEME["dim"]).pack(side="right")

        def enter(_):
            for w in (card, lbl, meta):
                w.config(bg=THEME["panel2"])
            for w in meta.winfo_children():
                w.config(bg=THEME["panel2"])
            card.config(highlightbackground=THEME["accent"], highlightthickness=2)

        def leave(_):
            for w in (card, lbl, meta):
                w.config(bg=THEME["card"])
            for w in meta.winfo_children():
                w.config(bg=THEME["card"])
            card.config(highlightbackground=THEME["line"], highlightthickness=1)

        for w in (card, lbl, meta):
            w.bind("<Enter>", enter)
            w.bind("<Leave>", leave)
            w.bind("<Button-1>", lambda e, p=photo: self._detail(p))
        return card

    def _detail(self, photo):
        win = tk.Toplevel(self.root)
        win.title(f"💀 {photo['identity_name']} — {photo['tag']} · by {CREATOR}")
        win.configure(bg=THEME["bg"])
        win.geometry("880x600")
        win.bind("<Escape>", lambda e: win.destroy())
        body = tk.Frame(win, bg=THEME["bg"])
        body.pack(fill="both", expand=True, padx=20, pady=20)
        seed = f"{self.results['target']}|{photo['id']}"
        big = generate_portrait(seed, (400, 480), THEME["accent"], photo["identity_name"],
                                f"{photo['tag']} · {photo['location']}", photo["matched"])
        tkbig = ImageTk.PhotoImage(big)
        self._img_refs.append(tkbig)
        cv = tk.Canvas(body, width=400, height=480, bg=THEME["black"], highlightthickness=1,
                       highlightbackground=THEME["line"])
        cv.pack(side="left")
        cv.create_image(0, 0, image=tkbig, anchor="nw")
        FaceScan(cv, 400, 480, THEME["accent"], photo["matched"])
        right = tk.Frame(body, bg=THEME["bg"])
        right.pack(side="left", fill="both", expand=True, padx=(20, 0))
        tk.Label(right, text="🔍 ANALISI ASSET", font=(MONO, 15, "bold"), bg=THEME["bg"],
                 fg=THEME["accent"]).pack(anchor="w", pady=(0, 10))
        txt = scrolledtext.ScrolledText(right, bg=THEME["bg2"], fg=THEME["text"], font=(MONO, 11),
                                        relief="flat", padx=12, pady=10, wrap="word",
                                        highlightbackground=THEME["line"], highlightthickness=1)
        txt.pack(fill="both", expand=True)
        txt.tag_config("h", foreground=THEME["accent"], font=(MONO, 12, "bold"))
        txt.tag_config("k", foreground=THEME["dim"])
        txt.tag_config("v", foreground=THEME["white"])
        rows = [("h", "DATI ASSET\n"), ("k", "identità: "), ("v", photo["identity_name"] + "\n"),
                ("k", "tipo: "), ("v", photo["tag"] + "\n"), ("k", "data: "), ("v", photo["date"] + "\n"),
                ("k", "luogo: "), ("v", photo["location"] + "\n"), ("k", "qualità: "),
                ("v", photo["quality"] + "\n"), ("k", "fonte: "), ("v", photo["source"] + "\n\n"),
                ("h", "METRICHE\n"), ("k", "intel: "), ("v", f"{photo['intel']}/10\n"),
                ("k", "match: "), ("v", ("SÌ" if photo["matched"] else "NO") + "\n"),
                ("k", "classe: "), ("v", "Open Source (SIM)\n\n"),
                ("h", "ANALISI\n"), ("k", "riconoscimento facciale: "), ("v", "disponibile\n"),
                ("k", "metadati: "), ("v", "estratti\n"), ("k", "geo: "), ("v", "verificata\n\n"),
                ("k", f"— created by {CREATOR} —\n")]
        for tag, text in rows:
            txt.insert(tk.END, text, tag)
        txt.config(state="disabled")
        tk.Button(right, text="✕  Chiudi", font=(UI, 11, "bold"), bg=THEME["panel2"],
                  fg=THEME["red"], relief="flat", command=win.destroy).pack(pady=(10, 0))

    def open_slideshow(self):
        if not self.results or not self.results.get("photos"):
            messagebox.showinfo("Slideshow", "Prima esegui una scansione.")
            return
        Slideshow(self.root, self.results, self._img_refs)


class FaceScan:
    """Overlay animato di riconoscimento facciale su un Canvas con ritratto."""
    def __init__(self, canvas, w, h, accent, matched):
        self.c = canvas; self.w = w; self.h = h; self.accent = accent
        self.matched = matched; self.y = 0; self.dir = 1; self.sweeps = 0
        self.locked = False; self.frame = 0
        self._tick()

    def _tick(self):
        if not self.c.winfo_exists():
            return
        self.frame += 1
        self.c.delete("scan")
        acc = self.accent
        bw = 1 + int((math.sin(self.frame * 0.2) + 1))
        L = 30
        for (ax, ay, dx, dy) in [(14, 14, 1, 1), (self.w - 14, 14, -1, 1),
                                 (14, self.h - 14, 1, -1), (self.w - 14, self.h - 14, -1, -1)]:
            self.c.create_line(ax, ay, ax + dx * L, ay, fill=acc, width=bw, tags="scan")
            self.c.create_line(ax, ay, ax, ay + dy * L, fill=acc, width=bw, tags="scan")
        if not self.locked:
            self.c.create_rectangle(10, self.y, self.w - 10, self.y + 3, fill=acc, outline="",
                                    tags="scan")
            self.c.create_rectangle(10, self.y - 26, self.w - 10, self.y,
                                    fill=lerp_color(self.accent, THEME["bg"], 0.8), outline="",
                                    stipple="gray25", tags="scan")
            self.c.create_text(self.w - 18, self.y + 10, anchor="e", fill=acc,
                               font=(MONO, 9, "bold"),
                               text=f"SCAN {int(self.y/self.h*100)}%", tags="scan")
            self.y += 7 * self.dir
            if self.y >= self.h - 10:
                self.dir = -1; self.sweeps += 1
            elif self.y <= 10:
                self.dir = 1; self.sweeps += 1
            if self.sweeps >= 3:
                self.locked = True
        else:
            label = "◉ IDENTITY MATCH" if self.matched else "✕ NO MATCH"
            col = THEME["green"] if self.matched else THEME["red"]
            self.c.create_rectangle(0, self.h // 2 - 22, self.w, self.h // 2 + 22,
                                    fill=THEME["black"], outline=col, tags="scan")
            txt = f"{label}  9{self.frame%10}.{self.frame%10}%" if self.matched else label
            self.c.create_text(self.w // 2, self.h // 2, fill=col, font=(MONO, 18, "bold"),
                               text=txt, tags="scan")
            self.c.create_text(self.w // 2, self.h - 8, fill=THEME["dim"], font=(MONO, 8),
                               text=f"by {CREATOR}", tags="scan")
        self.c.after(40, self._tick)


class Slideshow:
    """Presentazione automatica dei ritratti a schermo intero."""
    def __init__(self, root, data, img_refs):
        self.data = data
        self.photos = data["photos"]
        self.i = 0
        self.refs = img_refs
        self.win = tk.Toplevel(root)
        self.win.title(f"🎞 SLIDESHOW — by {CREATOR}")
        self.win.configure(bg=THEME["black"])
        try:
            self.win.attributes("-fullscreen", True)
        except Exception:
            self.win.geometry("1000x800")
        self.cv = tk.Canvas(self.win, bg=THEME["black"], highlightthickness=0)
        self.cv.pack(fill="both", expand=True)
        self.running = True
        self.win.bind("<Escape>", lambda e: self.stop())
        self.win.bind("<Right>", lambda e: self._show(self.i + 1))
        self.win.bind("<Left>", lambda e: self._show(self.i - 1))
        self.win.focus_set()
        self._show(0)

    def _show(self, idx):
        if not self.running or not self.win.winfo_exists():
            return
        self.i = idx % len(self.photos)
        photo = self.photos[self.i]
        seed = f"{self.data['target']}|{photo['id']}"
        w = self.win.winfo_width() or 1000
        h = self.win.winfo_height() or 800
        pw = min(560, w - 80)
        ph = int(pw * 1.2)
        img = generate_portrait(seed, (pw, ph), THEME["accent"], photo["identity_name"],
                                f"{photo['tag']} · {photo['location']}", photo["matched"])
        tkimg = ImageTk.PhotoImage(img)
        self.refs.append(tkimg)
        self.cv.delete("all")
        self.cv.create_rectangle(0, 0, w, h, fill=THEME["black"], outline="")
        self.cv.create_image(w // 2, h // 2 - 20, image=tkimg)
        self.cv.image = tkimg
        self.cv.create_text(w // 2, h - 60, fill=THEME["accent"], font=(MONO, 16, "bold"),
                            text=f"{photo['identity_name']} — {photo['tag']}")
        self.cv.create_text(w // 2, h - 34, fill=THEME["dim"], font=(MONO, 11),
                            text=f"[{self.i+1}/{len(self.photos)}]  ·  Esc = esci  ·  ← → naviga  "
                                 f"·  created by {CREATOR}")
        self.after_id = self.win.after(2600, lambda: self._show(self.i + 1))

    def stop(self):
        self.running = False
        try:
            if hasattr(self, "after_id"):
                self.win.after_cancel(self.after_id)
        except Exception:
            pass
        if self.win.winfo_exists():
            self.win.destroy()


def main():
    print(f"◈ {APP_NAME} — by {CREATOR}")
    print("  ⚠  Gioco/simulazione: nessuna ricerca reale, dati casuali.")
    if not PIL_OK:
        print("  ✗ Pillow non installato → pip install Pillow")
    try:
        root = tk.Tk()
        SpyOSINTApp(root)
        root.mainloop()
    except tk.TclError as e:
        print("GUI non disponibile (display?):", e)
    except Exception as e:
        print("Errore fatale:", e)


if __name__ == "__main__":
    main()
