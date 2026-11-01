#!/usr/bin/env python3
"""
guardia.py — sala operativa radio self-hosted, un file solo. Windows / Linux / macOS.

AVVIO
    python guardia.py                 1a volta: crea la venv e installa le dipendenze (1-5 min)
    python guardia.py                 poi: avvia (passa in demo se il dongle non risponde)
    python guardia.py --freqs 151175000:CC:digital,160900000:PL:analog --gain 24 --ppm 42

MODI
    --check      diagnostica dell'ambiente (pacchetti, binari, dongle)
    --selftest   test interni: DSP, squelch, regex, DB, API. Nessun hardware richiesto.
    --sim        pipeline radio completa su un dongle simulato (per provare senza SDR)
    --demo       solo interfaccia, traffico finto, nessuna radio
    --install    (Linux) apt + sink PulseAudio + dsd-fme
    --service    (Linux) scrive la unit systemd

WINDOWS + SDR REALE
    Serve Zadig (https://zadig.akeo.ie): Options > List All Devices > "Bulk-In, Interface (0)",
    sostituisci il driver con WinUSB. Poi riattacca il dongle e rilancia.

LINUX
    python3 guardia.py --install

RICEZIONE
    Un solo dongle non può stare su più frequenze lontane. I canali vengono raggruppati:
    quelli che stanno nei ~1.9 MHz di banda del dongle sono ascoltati TUTTI in parallelo
    (una FFT per blocco, N canali estratti), i gruppi restanti a rotazione. Lo squelch è
    per canale e misurato dopo il filtro di canale, non sulla banda larga.

MODO 'digital'
    L'audio demodulato viene spedito via UDP a 127.0.0.1:7355 e si registra l'uscita del
    sink PulseAudio 'dsd_out'. Serve quindi dsd-fme in ascolto su quella porta (--install),
    altrimenti il canale viene trattato come 'analog' e lo dice nel log.

NOTA — ascolto e registrazione di comunicazioni radio sono regolati dalla legge locale:
usalo sulle frequenze che ti è consentito ricevere.
"""
import argparse
import hmac
import json
import logging
import math
import os
import queue
import random
import re
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import threading
import time
import wave
from collections import deque

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE, "guardia.db")
AUDIO = os.path.join(BASE, "audio")
CFG_PATH = os.path.join(BASE, "guardia.json")
VENV = os.path.join(BASE, ".venv")
IS_WIN = os.name == "nt"
VPY = os.path.join(VENV, "Scripts", "python.exe") if IS_WIN else os.path.join(VENV, "bin", "python")
STOP = threading.Event()

# dipendenze: niente scipy (il DSP è tutto numpy/FFT), così l'installazione è molto più leggera
REQ_CORE = ["numpy", "fastapi", "uvicorn[standard]", "requests"]
REQ_RADIO = ["pyrtlsdr"]
REQ_STT = ["faster-whisper"]
REQ = REQ_CORE + REQ_RADIO + REQ_STT

# limiti sintonizzabili del classico RTL-SDR R820T (24 MHz – 1.766 GHz)
FREQ_MIN, FREQ_MAX = 24_000_000, 1_766_000_000
VALID_MODES = {"analog", "digital"}
GEO_HOLE_TTL = 6 * 3600      # un indirizzo non trovato viene ritentato dopo 6 ore
GEO_MIN_INTERVAL = 1.1       # policy Nominatim: max 1 richiesta/secondo, globale
RADIO_MAX_FAILS = 10         # errori radio consecutivi oltre i quali si rinuncia
SCHEMA_VERSION = 2

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname).1s [%(threadName)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("guardia")

DEFAULTS = {
    "host": "0.0.0.0", "port": 8080, "token": "",
    # radio
    "ppm": 0, "gain": 28, "sample_rate": 2_400_000, "deviation": 2500.0, "channel_bw": 7000.0,
    # squelch: 'auto' segue il rumore di fondo del singolo canale, 'manual' usa 'squelch' in dBFS
    "squelch_mode": "auto", "squelch": -30.0, "squelch_margin": 7.0, "squelch_hysteresis": 3.0,
    # segmentazione
    "hang": 0.7, "preroll": 0.3, "min_voice": 0.8, "max_seg": 12.0, "dwell": 2.5,
    # trascrizione
    "stt": True, "model": "small", "stt_lang": "it",
    # manutenzione / mappa
    "retention_hours": 48, "lat": 41.9028, "lon": 12.4964, "radius_km": 25, "city": "Roma",
    "viewbox": "12.30,41.70,12.75,42.10", "geocode": True, "adsb": True, "adsb_interval": 8.0,
    "freqs": [{"freq": 151175000, "unit": "CC", "mode": "digital"},
              {"freq": 152025000, "unit": "PS", "mode": "digital"},
              {"freq": 160900000, "unit": "PL", "mode": "analog"},
              {"freq": 161300000, "unit": "VVF", "mode": "analog"}],
}

# ─────────────────────────────── ambiente


def have(b):
    return shutil.which(b) is not None


def sh(cmd):
    return subprocess.run(cmd, shell=isinstance(cmd, str), capture_output=True, text=True)


def run_live(cmd):
    """Come sh() ma con l'output a schermo: obbligatorio per pip, che è lento."""
    print("  $ " + (cmd if isinstance(cmd, str) else " ".join(cmd)), flush=True)
    return subprocess.run(cmd, shell=isinstance(cmd, str)).returncode


def win_dll_path():
    """
    Su Windows pyrtlsdr cerca librtlsdr.dll nelle cartelle di sistema e nel PATH, non
    accanto allo script: con questo basta copiare i DLL qui (o in ./dll) e funziona.
    """
    if not (IS_WIN and hasattr(os, "add_dll_directory")):
        return
    for d in (BASE, os.path.join(BASE, "dll")):
        if os.path.isdir(d):
            try:
                os.add_dll_directory(d)
            except OSError:
                pass


def dongle_hint(err):
    """Spiega l'errore del dongle: libreria assente e driver assente sono problemi diversi."""
    msg = str(err)
    if "librtlsdr" in msg or "DLL" in msg.upper() or "cannot open shared object" in msg:
        print("!! manca la libreria librtlsdr (il driver del dongle e' un'altra cosa):")
        if IS_WIN:
            print("   scarica i binari Windows da github.com/rtlsdrblog/rtl-sdr-blog/releases")
            print("   e copia librtlsdr.dll e libusb-1.0.dll accanto a guardia.py")
        else:
            print("   sudo apt install rtl-sdr librtlsdr0      (oppure python guardia.py --install)")
    elif IS_WIN:
        print("!! su Windows serve Zadig/WinUSB sul dongle (vedi la docstring o --check)")
    else:
        print("!! controlla che il dongle sia collegato e non in uso da un altro programma")


def port_free(host, port):
    """Prova a occupare la porta prima di avviare uvicorn, per dare un errore comprensibile."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if not IS_WIN:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)   # come fa uvicorn
        s.bind(("" if host in ("0.0.0.0", "") else host, int(port)))
        return True
    except OSError:
        return False
    finally:
        s.close()


def local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def missing_pkgs(pkgs):
    out = []
    for pkg in pkgs:
        mod = pkg.split("[")[0].replace("-", "_")
        try:
            __import__(mod)
        except Exception:
            out.append(pkg)
    return out


def pip_install(pkgs, label=""):
    if not pkgs:
        return True
    print("\n" + "=" * 62)
    print("  INSTALLAZIONE DIPENDENZE %s— può durare qualche minuto." % (label and label + " "))
    print("  Vedrai l'avanzamento: NON è bloccato, lascia finire.")
    print("  Pacchetti: " + " ".join(pkgs))
    print("=" * 62 + "\n", flush=True)
    run_live([sys.executable, "-m", "pip", "install", "--upgrade", "pip", "wheel"])
    rc = run_live([sys.executable, "-m", "pip", "install", "--prefer-binary"] + pkgs)
    if rc != 0:
        print("\n!! Installazione fallita. Lancia a mano per leggere l'errore reale:\n")
        print('   "%s" -m pip install --prefer-binary %s\n' % (sys.executable, " ".join(pkgs)))
        return False
    print("\n· dipendenze pronte.\n", flush=True)
    return True


def ensure_env(pkgs=None, hard=True):
    """Crea la venv al primo avvio, poi installa ciò che manca. Idempotente."""
    if sys.prefix == sys.base_prefix and not os.environ.get("GUARDIA_NO_VENV"):
        if not os.path.exists(VPY):
            print("· creo l'ambiente virtuale...", flush=True)
            run_live([sys.executable, "-m", "venv", VENV])
        if not os.path.exists(VPY):
            print("!! venv non creata. Reinstalla Python spuntando 'pip' e 'Add python.exe to PATH',")
            print("   oppure riavvia con GUARDIA_NO_VENV=1 per usare il Python di sistema.")
            sys.exit(1)
        os.execv(VPY, [VPY] + sys.argv)

    need = missing_pkgs(pkgs or REQ_CORE)
    if need and not pip_install(need) and hard:
        sys.exit(1)
    return not need


def do_install():
    print("== INSTALLAZIONE ==")
    if not IS_WIN and have("apt"):
        run_live(["sudo", "apt", "update"])
        run_live(["sudo", "apt", "install", "-y", "rtl-sdr", "sqlite3", "ffmpeg", "curl",
                  "cmake", "build-essential", "libpulse-dev", "pulseaudio", "python3-venv"])
    if have("pactl"):
        if "dsd_out" not in sh("pactl list short sinks").stdout:
            sh("pactl load-module module-null-sink sink_name=dsd_out rate=48000 channels=1")
        print("· sink PulseAudio 'dsd_out' pronto")
    d = os.path.join(BASE, "dsd-fme")
    if not IS_WIN and not have("dsd-fme") and not os.path.isdir(d):
        run_live(["git", "clone", "https://github.com/lwvmobile/dsd-fme", d])
    if os.path.isdir(d) and not have("dsd-fme"):
        sh(["git", "-C", d, "checkout", "pulseaudio"])
        os.makedirs(os.path.join(d, "build"), exist_ok=True)
        run_live("cd '%s/build' && cmake .. && make -j$(nproc) && sudo make install" % d)
    if IS_WIN:
        print("· Windows: ffmpeg opzionale → winget install Gyan.FFmpeg")
        print("· Per l'SDR reale serve Zadig/WinUSB sul dongle (vedi docstring).")
    ensure_env(REQ, hard=False)
    print("\nfatto. Avvia con: python guardia.py")


def do_check():
    win_dll_path()
    print("== DIAGNOSTICA ==")
    print("  python   " + sys.executable)
    print("  venv     " + ("sì" if sys.prefix != sys.base_prefix else "NO"))
    for pkg in REQ:
        mod = pkg.split("[")[0].replace("-", "_")
        try:
            __import__(mod)
            print("  ok       " + pkg)
        except Exception:
            print("  MANCA    " + pkg)
    for b in ["rtl_test", "ffmpeg", "parec", "pactl", "dsd-fme"]:
        print(("  ok       " if have(b) else "  assente  ") + b)
    if have("pactl"):
        print(("  ok       " if "dsd_out" in sh("pactl list short sinks").stdout
               else "  assente  ") + "sink dsd_out")
    try:
        from rtlsdr import RtlSdr
        sdr = RtlSdr()
        try:
            print("  ok       dongle RTL-SDR (tuner %s)" % getattr(sdr, "tuner_type", "?"))
        finally:
            sdr.close()
    except Exception as e:
        print("  MANCA    dongle (" + str(e)[:70] + ")")
        dongle_hint(e)
    print("  db       %s (%s)" % (DB_PATH, "presente" if os.path.exists(DB_PATH) else "nuovo"))


def do_service():
    if IS_WIN:
        print("Windows: usa il Task Scheduler, oppure avvia con: pythonw guardia.py")
        return
    py = VPY if os.path.exists(VPY) else sys.executable
    unit = """[Unit]
Description=Guardia
After=network.target sound.target

[Service]
User=%s
WorkingDirectory=%s
ExecStart=%s %s/guardia.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
""" % (os.environ.get("USER", "pi"), BASE, py, BASE)
    with open("/tmp/guardia.service", "w") as f:
        f.write(unit)
    sh(["sudo", "cp", "/tmp/guardia.service", "/etc/systemd/system/guardia.service"])
    sh(["sudo", "systemctl", "daemon-reload"])
    print("fatto: sudo systemctl enable --now guardia")


# ─────────────────────────────── config


def load_cfg():
    cfg = json.loads(json.dumps(DEFAULTS))
    if os.path.exists(CFG_PATH):
        try:
            with open(CFG_PATH, encoding="utf-8") as f:
                cfg.update(json.load(f))
        except Exception as e:
            log.warning("config illeggibile (%s), uso i valori di default", e)
    return cfg


def save_cfg(cfg):
    """Scrittura atomica + permessi ristretti: il file contiene il token di accesso."""
    tmp = CFG_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    os.replace(tmp, CFG_PATH)
    try:
        os.chmod(CFG_PATH, 0o600)
    except OSError:
        pass


def _num(cfg, key, lo, hi, default):
    """Clampa un numerico, segnalando i valori impossibili invece di crashare dopo."""
    try:
        v = float(cfg.get(key, default))
    except (TypeError, ValueError):
        log.warning("%s=%r non numerico → %s", key, cfg.get(key), default)
        v = float(default)
    if not (lo <= v <= hi):
        log.warning("%s=%g fuori range [%g,%g] → %g", key, v, lo, hi, min(max(v, lo), hi))
        v = min(max(v, lo), hi)
    cfg[key] = v
    return v


def validate_cfg(cfg):
    """Corregge/segnala i valori impossibili. Scarta le frequenze fuori banda."""
    if not (0 < int(cfg.get("port", 0)) < 65536):
        log.warning("porta %r non valida → 8080", cfg.get("port"))
        cfg["port"] = 8080
    cfg["port"] = int(cfg["port"])
    cfg["gain"] = int(_num(cfg, "gain", 0, 50, 28))
    cfg["ppm"] = int(_num(cfg, "ppm", -200, 200, 0))
    _num(cfg, "sample_rate", 1_000_000, 2_880_000, 2_400_000)
    cfg["sample_rate"] = int(round(cfg["sample_rate"] / 48000.0)) * 48000  # multiplo dell'audio
    _num(cfg, "deviation", 500, 75_000, 2500)
    _num(cfg, "channel_bw", 2000, 100_000, 7000)
    _num(cfg, "squelch", -90, 0, -30)
    _num(cfg, "squelch_margin", 1, 40, 7)
    _num(cfg, "squelch_hysteresis", 0, 20, 3)
    _num(cfg, "hang", 0.1, 10, 0.7)
    _num(cfg, "preroll", 0, 3, 0.3)
    _num(cfg, "min_voice", 0.1, 30, 0.8)
    _num(cfg, "max_seg", 1, 300, 12)
    _num(cfg, "dwell", 0.5, 60, 2.5)
    _num(cfg, "retention_hours", 1, 24 * 365, 48)
    _num(cfg, "adsb_interval", 2, 3600, 8)
    _num(cfg, "lat", -90, 90, 41.9028)
    _num(cfg, "lon", -180, 180, 12.4964)
    _num(cfg, "radius_km", 1, 250, 25)
    if cfg["squelch_mode"] not in ("auto", "manual"):
        log.warning("squelch_mode=%r sconosciuto → auto", cfg["squelch_mode"])
        cfg["squelch_mode"] = "auto"
    if cfg["max_seg"] <= cfg["min_voice"]:
        log.warning("max_seg <= min_voice: porto max_seg a %g", cfg["min_voice"] * 4)
        cfg["max_seg"] = cfg["min_voice"] * 4

    good, seen = [], set()
    for ch in cfg.get("freqs") or []:
        try:
            f = int(ch["freq"])
            mode = str(ch.get("mode", "analog")).lower()
            unit = str(ch.get("unit", "??")).strip()[:12] or "??"
            if not (FREQ_MIN <= f <= FREQ_MAX):
                log.warning("frequenza %s fuori banda, scartata", f)
                continue
            if mode not in VALID_MODES:
                log.warning("modo '%s' sconosciuto su %s → analog", mode, f)
                mode = "analog"
            if (f, unit) in seen:
                log.warning("canale duplicato %s/%s ignorato", f, unit)
                continue
            seen.add((f, unit))
            good.append({"freq": f, "unit": unit, "mode": mode})
        except (KeyError, ValueError, TypeError):
            log.warning("canale malformato ignorato: %r", ch)
    if not good:
        log.error("nessuna frequenza valida: uso i default")
        good = json.loads(json.dumps(DEFAULTS["freqs"]))
    cfg["freqs"] = good
    return cfg


# ─────────────────────────────── db
# una connessione SQLite per thread: thread-safe e senza riaprirla a ogni query
_local = threading.local()


def _conn():
    c = getattr(_local, "conn", None)
    if c is None:
        c = sqlite3.connect(DB_PATH, timeout=15)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA busy_timeout=15000")
        c.execute("PRAGMA synchronous=NORMAL")
        _local.conn = c
    return c


def db_init():
    c = sqlite3.connect(DB_PATH, timeout=15)
    try:
        c.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS tx(
                id INTEGER PRIMARY KEY, ts REAL NOT NULL, freq INTEGER, unit TEXT,
                mode TEXT, wav TEXT, text TEXT DEFAULT '', conf REAL DEFAULT 0,
                place TEXT, lat REAL, lon REAL,
                state TEXT DEFAULT 'done', dur REAL DEFAULT 0, rssi REAL);
            CREATE INDEX IF NOT EXISTS i_ts ON tx(ts DESC);
            CREATE TABLE IF NOT EXISTS geo(q TEXT PRIMARY KEY, lat REAL, lon REAL, conf REAL, ts REAL);
            CREATE TABLE IF NOT EXISTS air(hex TEXT PRIMARY KEY, callsign TEXT, lat REAL, lon REAL,
                alt INTEGER, spd REAL, seen REAL);
            CREATE INDEX IF NOT EXISTS i_seen ON air(seen DESC);
            CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT);
        """)
        # Migrazione dolce da schemi più vecchi: aggiungo solo le colonne che mancano.
        # Deve stare PRIMA degli indici che usano quelle colonne, altrimenti su un DB
        # vecchio il CREATE INDEX fallisce con "no such column".
        cols = {r[1] for r in c.execute("PRAGMA table_info(tx)")}
        for name, ddl in (("state", "TEXT DEFAULT 'done'"), ("dur", "REAL DEFAULT 0"),
                          ("rssi", "REAL")):
            if name not in cols:
                c.execute("ALTER TABLE tx ADD COLUMN %s %s" % (name, ddl))
                log.info("db: aggiunta colonna tx.%s", name)
        if "state" not in cols:
            # nel vecchio schema una riga senza testo era una tratta scartata
            n = c.execute("UPDATE tx SET state='empty' WHERE text IS NULL OR text=''").rowcount
            log.info("db: migrate %d righe esistenti", n)
        c.execute("CREATE INDEX IF NOT EXISTS i_state ON tx(state)")
        c.execute("INSERT OR REPLACE INTO meta VALUES('schema',?)", (str(SCHEMA_VERSION),))
        c.commit()
    finally:
        c.close()


def q(sql, args=()):
    return [dict(r) for r in _conn().execute(sql, args).fetchall()]


def x(sql, args=()):
    c = _conn()
    cur = c.execute(sql, args)
    c.commit()
    return cur.lastrowid


# ─────────────────────────────── http condiviso
_session = None
_session_lock = threading.Lock()
UA = {"User-Agent": "guardia.py/2.0 (self-hosted scanner)"}


def http():
    """Una sola requests.Session riusata (keep-alive) invece di una nuova per chiamata."""
    global _session
    if _session is None:
        with _session_lock:
            if _session is None:
                import requests
                s = requests.Session()
                s.headers.update(UA)
                _session = s
    return _session


# ─────────────────────────────── geocodifica
# "via Nomentana", "piazza Vittorio Emanuele II", "lungotevere Marzio", "via di Macchia Saponara"
PAT = re.compile(
    r"\b(?i:(via|viale|piazza|piazzale|vicolo|largo|corso|lungotevere|strada|circonvallazione))"
    r"\s+((?:(?:di|del|della|dei|degli|delle|de|da)\s+)?"
    r"[A-ZÀ-Ü][\w'’.-]+"
    r"(?:\s+(?:di|del|della|dei|degli|delle|de|da|san|santa|sant'|santo)\s*[A-ZÀ-Ü][\w'’.-]+)?"
    r"(?:\s+(?:[A-ZÀ-Ü][\w'’.-]+|[IVXLC]{1,5}\b)){0,3})")

_geo_lock = threading.Lock()
_geo_last = [0.0]


def geocode(place, cfg):
    """Nominatim con cache su DB, cache dei 'buchi' e rate-limit globale a 1 req/s."""
    if not cfg.get("geocode", True):
        return None
    key = place.lower().strip()
    hit = q("SELECT lat,lon,conf,ts FROM geo WHERE q=?", (key,))
    if hit:
        h = hit[0]
        if h["lat"] is not None:
            return h["lat"], h["lon"], h["conf"]
        # 'buco' noto: non riprovo finché il TTL non scade
        if time.time() - (h["ts"] or 0) < GEO_HOLE_TTL:
            return None
    try:
        with _geo_lock:  # la policy è 1 richiesta/secondo per client, non per thread
            wait = GEO_MIN_INTERVAL - (time.time() - _geo_last[0])
            if wait > 0:
                if STOP.wait(wait):
                    return None
            _geo_last[0] = time.time()
            r = http().get("https://nominatim.openstreetmap.org/search",
                           params={"q": "%s, %s" % (place, cfg["city"]), "format": "jsonv2",
                                   "limit": 1, "viewbox": cfg["viewbox"], "bounded": 1},
                           timeout=8)
        r.raise_for_status()
        js = r.json()
        if not js:
            # memorizzo il buco (con timestamp) per non martellare Nominatim a ogni frase
            x("INSERT OR REPLACE INTO geo VALUES(?,?,?,?,?)", (key, None, None, 0.0, time.time()))
            return None
        lat, lon = float(js[0]["lat"]), float(js[0]["lon"])
        conf = min(0.95, 0.45 + float(js[0].get("importance", 0.3) or 0.3))
        x("INSERT OR REPLACE INTO geo VALUES(?,?,?,?,?)", (key, lat, lon, conf, time.time()))
        return lat, lon, conf
    except Exception as e:
        # errore di rete: non lo memorizzo come buco, verrà ritentato
        log.debug("geocode fallito per '%s': %s", place, e)
        return None


def extract_place(text, cfg):
    """Primo toponimo riconosciuto e geocodificato. (nome, lat, lon, conf) oppure None."""
    for m in PAT.finditer(text or ""):
        place = "%s %s" % (m.group(1).lower(), m.group(2).strip().rstrip(" ,.;:"))
        place = re.sub(r"\s+", " ", place)
        g = geocode(place, cfg)
        if g:
            return (place, g[0], g[1], g[2])
    return None


# ─────────────────────────────── DSP (solo numpy: nessuna dipendenza da scipy)


def lowpass_taps(cutoff, sr, ntaps=127, beta=7.0):
    """FIR passa-basso finestra di Kaiser (sinc * kaiser), guadagno unitario in continua."""
    import numpy as np
    n = np.arange(ntaps) - (ntaps - 1) / 2.0
    h = np.sinc(2.0 * cutoff / sr * n) * np.kaiser(ntaps, beta)
    return h / h.sum()


class Fir:
    """FIR streaming con stato: continuità garantita tra blocchi consecutivi."""

    def __init__(self, h, decim=1, cplx=False):
        import numpy as np
        self.np = np
        self.h = np.asarray(h, dtype=np.float64)
        self.M = max(1, int(decim))
        self.k = len(self.h) - 1
        self.zi = np.zeros(self.k, dtype=np.complex128 if cplx else np.float64)
        self.phase = 0

    def reset(self):
        self.zi[:] = 0
        self.phase = 0

    def __call__(self, x):
        np = self.np
        buf = np.concatenate((self.zi, x)) if self.k else x
        y = np.convolve(buf, self.h, "valid")          # len(y) == len(x)
        if self.k:
            self.zi = buf[len(buf) - self.k:].copy()
        if self.M == 1:
            return y
        out = y[self.phase::self.M]
        self.phase = (self.phase - len(y)) % self.M
        return out


class Channelizer:
    """
    Canalizzatore FFT: una sola FFT per blocco e N canali estratti in parallelo.

    Per ogni canale: traslazione in banda base (selezione dei bin), filtro di canale
    (taper in frequenza), decimazione a 48 kHz, discriminatore FM e de-enfasi.
    Overlap-save: i primi campioni di ogni blocco, contaminati dalla convoluzione
    circolare, vengono scartati — nessun click a ogni blocco come con il filtraggio
    blocco-per-blocco.
    """
    AUDIO_SR = 48000
    NOUT = 960          # campioni audio per FFT (20 ms)
    NDROP = 192         # scartati per overlap-save (4 ms)
    TAU = 300e-6        # de-enfasi europea

    def __init__(self, cfg, offsets):
        import numpy as np
        self.np = np
        self.sr = int(cfg["sample_rate"])
        self.decim = self.sr // self.AUDIO_SR
        if self.decim < 1 or self.sr % self.AUDIO_SR:
            raise ValueError("sample_rate deve essere un multiplo di 48000")
        self.nfft = self.NOUT * self.decim          # campioni IQ per FFT
        self.ovl = self.NDROP * self.decim          # riportati dal blocco precedente
        self.new = self.nfft - self.ovl             # campioni nuovi per iterazione
        self.dt = (self.NOUT - self.NDROP) / float(self.AUDIO_SR)
        self.dev = float(cfg["deviation"])
        self.bin_hz = self.sr / float(self.nfft)
        self.offsets = [float(o) for o in offsets]

        half = self.NOUT // 2
        self.sel = np.arange(-half, self.NOUT - half)
        self.bins = [int(round(o / self.bin_hz)) for o in self.offsets]
        # filtro di canale: piatto fino a channel_bw, poi raccordo a coseno rialzato
        f = np.abs(self.sel * self.bin_hz)
        bw = float(cfg["channel_bw"])
        trans = max(1000.0, bw * 0.4)
        t = np.clip((f - bw) / trans, 0.0, 1.0)
        self.taper = 0.5 * (1.0 + np.cos(np.pi * t))

        # de-enfasi: il polo singolo y[n]=α·x[n]+(1-α)·y[n-1] come FIR esponenziale
        a = (1.0 / self.AUDIO_SR) / (self.TAU + 1.0 / self.AUDIO_SR)
        n = int(math.ceil(math.log(1e-4) / math.log(1.0 - a)))
        hd = a * (1.0 - a) ** np.arange(n)
        self.deemph = [Fir(hd / hd.sum()) for _ in self.offsets]
        self.tail = np.zeros(0, dtype=np.complex128)
        self.last = np.zeros(len(self.offsets), dtype=np.complex128)
        self.dc = np.zeros(len(self.offsets))

    def reset(self):
        """Dopo una risintonizzazione lo stato dei filtri non è più valido."""
        self.tail = self.np.zeros(0, dtype=self.np.complex128)
        self.last[:] = 0
        self.dc[:] = 0
        for f in self.deemph:
            f.reset()

    def process(self, iq):
        """Un blocco IQ nuovo → [(rssi_dBFS, audio float32), ...] oppure None se serve altro."""
        np = self.np
        buf = np.concatenate((self.tail, iq)) if len(self.tail) else np.asarray(iq)
        if len(buf) < self.nfft:
            self.tail = buf
            return None
        blk = buf[len(buf) - self.nfft:]
        self.tail = blk[len(blk) - self.ovl:].copy()
        X = np.fft.fft(blk)
        out = []
        for i, k0 in enumerate(self.bins):
            Y = X[(k0 + self.sel) % self.nfft] * self.taper
            z = np.fft.ifft(np.fft.ifftshift(Y)) / self.decim
            z = z[self.NDROP:]
            rssi = 10.0 * math.log10(float(np.mean(np.abs(z) ** 2)) + 1e-20)
            # discriminatore FM, con l'ultimo campione del blocco precedente per continuità
            w = np.concatenate((self.last[i:i + 1], z))
            self.last[i] = z[-1]
            d = np.angle(w[1:] * np.conj(w[:-1]))
            a = d * (self.AUDIO_SR / (2.0 * math.pi * self.dev))
            a = self.deemph[i](a)
            self.dc[i] += 0.05 * (float(np.mean(a)) - self.dc[i])   # scentratura del tuner
            out.append((rssi, (a - self.dc[i]).astype(np.float32)))
        return out


class Gate:
    """Squelch + segmentatore per un singolo canale (macchina a stati con hang e pre-roll)."""

    CAL_BLOCKS = 32          # ~0.5 s di calibrazione prima di abilitare l'apertura

    def __init__(self, cfg, ch, sr=Channelizer.AUDIO_SR):
        self.cfg, self.ch, self.sr = cfg, ch, sr
        self.cal = []
        self.floor = None
        self.open = False
        self.buf = []
        self.pre = deque()
        self.pre_n = 0
        self.t0 = 0.0
        self.peak = -120.0
        self.quiet = 0.0
        self.opened_now = False

    def rearm(self):
        """Nuovo turno sullo stesso gruppo: butto il pre-roll vecchio, tengo la calibrazione."""
        self.open = False
        self.opened_now = False
        self.buf = []
        self.pre.clear()
        self.pre_n = 0
        self.quiet = 0.0

    def threshold(self):
        if self.cfg["squelch_mode"] == "manual" or self.floor is None:
            return float(self.cfg["squelch"])
        return self.floor + float(self.cfg["squelch_margin"])

    def _track(self, rssi):
        """
        Rumore di fondo: scende in fretta, risale piano, mai mentre il canale è aperto.
        All'avvio si calibra sul MINIMO dei primi blocchi: se partissimo dal primo valore
        e quel blocco fosse una trasmissione, la soglia resterebbe inchiodata in alto.
        """
        if self.cal is not None:
            self.cal.append(rssi)
            if len(self.cal) < self.CAL_BLOCKS:
                return
            self.floor = min(self.cal)
            self.cal = None
            return
        if rssi < self.floor:
            self.floor += 0.30 * (rssi - self.floor)
        elif not self.open:
            self.floor += 0.002 * (rssi - self.floor)

    def push(self, audio, rssi, now):
        """Ritorna il segmento concluso (dict) o None. Imposta .opened_now a inizio tratta."""
        dt = len(audio) / float(self.sr)
        self._track(rssi)
        thr = self.threshold()
        self.opened_now = False
        if self.cal is not None:      # ancora in calibrazione: nessuna apertura
            return None
        if not self.open:
            self.pre.append(audio)
            self.pre_n += len(audio)
            lim = int(float(self.cfg["preroll"]) * self.sr)
            while self.pre and self.pre_n - len(self.pre[0]) > lim:
                self.pre_n -= len(self.pre.popleft())
            if rssi <= thr:
                return None
            self.open = self.opened_now = True
            self.t0, self.quiet, self.peak = now, 0.0, rssi
            self.buf = list(self.pre)
            self.pre.clear()
            self.pre_n = 0
            return None
        self.buf.append(audio)
        self.peak = max(self.peak, rssi)
        self.quiet = self.quiet + dt if rssi < thr - float(self.cfg["squelch_hysteresis"]) else 0.0
        dur = sum(len(b) for b in self.buf) / float(self.sr)
        if self.quiet >= float(self.cfg["hang"]) or dur >= float(self.cfg["max_seg"]):
            return self.finish()
        return None

    def finish(self):
        import numpy as np
        self.open = False
        buf, self.buf = self.buf, []
        if not buf:
            return None
        audio = np.concatenate(buf)
        dur = len(audio) / float(self.sr)
        # il pre-roll non è voce: non deve far passare le tratte troppo corte
        if dur - float(self.cfg["preroll"]) < float(self.cfg["min_voice"]):
            return None
        return {"audio": audio, "dur": round(dur, 2), "rssi": round(self.peak, 1),
                "floor": round(self.floor if self.floor is not None else -120.0, 1)}


def write_wav(path, audio, sr=Channelizer.AUDIO_SR):
    """WAV mono 16 bit con un solo guadagno per tratta (niente pumping blocco per blocco)."""
    import numpy as np
    peak = float(np.max(np.abs(audio))) if len(audio) else 0.0
    gain = min(8.0, 0.7 / peak) if peak > 1e-6 else 1.0
    pcm = np.clip(audio * gain * 32767.0, -32768, 32767).astype("<i2")
    tmp = path + ".part"
    with wave.open(tmp, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    os.replace(tmp, path)
    return path


# ─────────────────────────────── sorgenti IQ


class RtlSource:
    """Dongle reale."""

    def __init__(self, cfg):
        from rtlsdr import RtlSdr
        self.sdr = RtlSdr()
        self.sdr.sample_rate = int(cfg["sample_rate"])
        try:
            self.sdr.gain = int(cfg["gain"])
        except Exception as e:
            log.warning("gain %s rifiutato (%s), uso l'automatico", cfg["gain"], e)
            self.sdr.gain = "auto"
        if cfg["ppm"]:
            try:
                self.sdr.freq_correction = int(cfg["ppm"])
            except Exception as e:   # librtlsdr rifiuta il valore se è già quello
                log.debug("ppm non applicato: %s", e)
        self.sr = int(cfg["sample_rate"])

    def tune(self, hz):
        self.sdr.center_freq = int(hz)
        # scarto ~50 ms: il PLL si assesta e nel buffer USB c'è ancora il canale vecchio
        try:
            self.sdr.read_samples(int(self.sr * 0.05) // 512 * 512)
        except Exception:
            pass

    def read(self, n):
        return self.sdr.read_samples(n)

    def close(self):
        try:
            self.sdr.close()
        except Exception:
            pass


class SimSource:
    """
    Dongle simulato: rumore gaussiano + burst FM modulati a 700 Hz sui canali configurati.
    Serve a --sim e a --selftest, così tutta la catena si prova senza hardware.
    """

    def __init__(self, cfg, realtime=True, seed=7):
        import numpy as np
        self.np = np
        self.sr = int(cfg["sample_rate"])
        self.dev = float(cfg["deviation"])
        self.rng = np.random.default_rng(seed)
        self.chans = list(cfg["freqs"])
        self.center = self.chans[0]["freq"]
        self.n0 = 0
        self.realtime = realtime
        self.t_start = time.time()
        self.sigma = 10 ** (-45 / 20.0) / math.sqrt(2.0)   # rumore ≈ -45 dBFS su tutta la banda
        self.amp = 10 ** (-20 / 20.0)                      # portante ≈ -20 dBFS
        self.phase = {}

    def bursts(self, i, ta, tb):
        """Pianificazione deterministica: canale i parla per D secondi ogni P secondi."""
        p, d, o = 7.0 + 3.0 * i, 2.5 + 0.5 * i, 1.5 + 1.7 * i
        k0 = int(max(0, (ta - o - d) // p))
        for k in range(k0, int((tb - o) // p) + 2):
            t0 = o + k * p
            if t0 < tb and t0 + d > ta:
                yield t0, t0 + d

    def tune(self, hz):
        self.center = int(hz)

    def read(self, n):
        np = self.np
        idx = self.n0 + np.arange(n)
        t = idx / self.sr
        iq = (self.rng.normal(0, self.sigma, n) +
              1j * self.rng.normal(0, self.sigma, n)).astype(np.complex128)
        for i, ch in enumerate(self.chans):
            off = ch["freq"] - self.center
            if abs(off) > self.sr * 0.49:
                continue
            env = np.zeros(n)
            for t0, t1 in self.bursts(i, t[0], t[-1]):
                r = 0.005   # rampa di 5 ms: senza di essa l'accensione è a banda larga
                e = np.clip(np.minimum((t - t0) / r, (t1 - t) / r), 0.0, 1.0)
                env = np.maximum(env, 0.5 * (1.0 - np.cos(math.pi * e)))
            if not env.any():
                continue
            inst = off + self.dev * np.sin(2 * math.pi * 700.0 * t)
            ph = self.phase.get(i, 0.0) + 2 * math.pi * np.cumsum(inst) / self.sr
            self.phase[i] = float(ph[-1] % (2 * math.pi))
            iq += self.amp * env * np.exp(1j * ph)
        self.n0 += n
        if self.realtime:
            lag = self.n0 / self.sr - (time.time() - self.t_start)
            if lag > 0:
                STOP.wait(lag)
        return iq

    def close(self):
        pass


# ─────────────────────────────── radio


def cluster(freqs, span):
    """Raggruppa i canali che stanno insieme nella banda del dongle (lista di liste)."""
    groups, cur = [], []
    for c in sorted(freqs, key=lambda c: c["freq"]):
        if cur and c["freq"] - cur[0]["freq"] > span:
            groups.append(cur)
            cur = []
        cur.append(c)
    if cur:
        groups.append(cur)
    return groups


def pick_center(group, dc_off=150_000):
    """
    Centro di sintonia del gruppo, spostato per non mettere nessun canale sullo spike DC
    del dongle (e nemmeno troppo vicino).
    """
    mid = (group[0]["freq"] + group[-1]["freq"]) / 2.0
    for extra in (0, 37_000, -37_000, 71_000, -71_000):
        c = mid + dc_off + extra
        if all(abs(ch["freq"] - c) > 12_000 for ch in group):
            return c
    return mid + dc_off


class Radio(threading.Thread):
    daemon = True
    name = "radio"
    SPAN = 1_900_000          # larghezza utile per un gruppo a 2.4 Msps

    def __init__(self, cfg, txq, source=None):
        super().__init__(name=self.name)
        import numpy as np
        self.np = np
        self.cfg, self.txq = cfg, txq
        self.src = source or RtlSource(cfg)
        span = min(self.SPAN, int(cfg["sample_rate"] * 0.79))
        self.groups = cluster(cfg["freqs"], span)
        self.chz = [Channelizer(cfg, [ch["freq"] - pick_center(g) for ch in g])
                    for g in self.groups]
        # i gate vivono quanto il programma: senza questo lo squelch si ricalibrerebbe
        # a ogni turno di scansione, buttando via mezzo secondo di ascolto ogni volta
        self.gates = [[Gate(cfg, ch) for ch in g] for g in self.groups]
        self.udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.dsd = have("parec") and (have("dsd-fme") or have("dsd")) and self.sink_ok()
        self.tap = None           # (indice canale, Popen, file, path) del canale digitale attivo
        for g in self.groups:
            log.info("gruppo @%.3f MHz: %s", pick_center(g) / 1e6,
                     ", ".join("%s %.4f" % (c["unit"], c["freq"] / 1e6) for c in g))
        if len(self.groups) > 1:
            log.info("%d gruppi: scansione a rotazione (%.1fs ciascuno)",
                     len(self.groups), cfg["dwell"])
        digitali = [c for c in cfg["freqs"] if c["mode"] == "digital"]
        if digitali and not self.dsd:
            log.warning("modo 'digital' richiesto su %s ma dsd-fme/parec/sink non ci sono: "
                        "tratto i canali come analogici",
                        ",".join(c["unit"] for c in digitali))

    @staticmethod
    def sink_ok():
        if not have("pactl"):
            return False
        try:
            return "dsd_out" in sh("pactl list short sinks").stdout
        except Exception:
            return False

    def close(self):
        self.stop_tap()
        for obj in (self.src, self.udp):
            try:
                obj.close()
            except Exception:
                pass

    # ── inoltro verso dsd-fme (un canale digitale per volta: dsd-fme ne decodifica uno)
    def start_tap(self, i, ch):
        if not self.dsd or self.tap is not None:
            return
        path = os.path.join(AUDIO, "%d_%d.raw" % (int(time.time() * 1000), ch["freq"]))
        try:
            fh = open(path, "wb")
            p = subprocess.Popen(["parec", "-d", "dsd_out.monitor", "--format=s16le",
                                  "--rate=48000", "--channels=1", "--raw"],
                                 stdout=fh, stderr=subprocess.DEVNULL)
            self.tap = (i, p, fh, path)
        except Exception as e:
            log.warning("parec non avviato: %s", e)
            self.tap = None

    def stop_tap(self):
        if not self.tap:
            return None
        _, p, fh, path = self.tap
        self.tap = None
        try:
            time.sleep(0.15)
            p.terminate()
            p.wait(timeout=3)
        except Exception:
            try:
                p.kill()
            except Exception:
                pass
        try:
            fh.close()
        except Exception:
            pass
        return path

    def store(self, ch, seg, raw=None):
        """Scrive l'audio e inserisce la riga 'pending' per il trascrittore."""
        stem = "%d_%d" % (int(time.time() * 1000), ch["freq"])
        wav = write_wav(os.path.join(AUDIO, stem + ".wav"), seg["audio"])
        path, mode = wav, ch["mode"]
        if raw:
            # il sink ha prodotto abbastanza audio? altrimenti dsd-fme non stava decodificando
            ok = os.path.exists(raw) and os.path.getsize(raw) > 48000 * 2 * 0.5
            if ok:
                os.unlink(wav)
                path = raw
            else:
                for p in (raw,):
                    try:
                        os.unlink(p)
                    except OSError:
                        pass
                mode = ch["mode"] + "/fallback"
        tid = x("""INSERT INTO tx(ts,freq,unit,mode,wav,state,dur,rssi)
                   VALUES(?,?,?,?,?,'pending',?,?)""",
                (time.time() - seg["dur"], ch["freq"], ch["unit"], mode, path,
                 seg["dur"], seg["rssi"]))
        log.info("%s %.4f  %.1fs  %.0f→%.0f dBFS  %s", ch["unit"], ch["freq"] / 1e6,
                 seg["dur"], seg["floor"], seg["rssi"], os.path.basename(path))
        self.txq.put(tid)

    def serve(self, gi):
        """Ascolta un gruppo di canali in parallelo per 'dwell' secondi (o senza limiti se è l'unico)."""
        np = self.np
        group, chz = self.groups[gi], self.chz[gi]
        self.src.tune(pick_center(group))
        chz.reset()
        gates = self.gates[gi]
        for g in gates:
            g.rearm()
        rotate = len(self.groups) > 1
        deadline = time.time() + float(self.cfg["dwell"]) if rotate else None
        while not STOP.is_set():
            res = chz.process(self.src.read(chz.new))
            if res is None:
                continue
            now = time.time()
            for i, (rssi, audio) in enumerate(res):
                ch, gate = group[i], gates[i]
                seg = gate.push(audio, rssi, now)
                if gate.opened_now:
                    log.debug("%s aperto (%.0f dBFS, soglia %.0f)", ch["unit"], rssi,
                              gate.threshold())
                    if ch["mode"] == "digital":
                        self.start_tap(i, ch)
                if gate.open and self.tap and self.tap[0] == i:
                    pcm = np.clip(audio * 14000.0, -32768, 32767).astype("<i2")
                    try:
                        self.udp.sendto(pcm.tobytes(), ("127.0.0.1", 7355))
                    except OSError:
                        pass
                if seg is not None:
                    raw = self.stop_tap() if (self.tap and self.tap[0] == i) else None
                    self.store(ch, seg, raw)
                elif not gate.open and self.tap and self.tap[0] == i:
                    raw = self.stop_tap()
                    try:
                        os.unlink(raw)
                    except (OSError, TypeError):
                        pass
            # non taglio una trasmissione in corso solo perché è scaduto il turno
            if deadline and now >= deadline and not any(g.open for g in gates):
                return

    def run(self):
        fails = 0
        try:
            while not STOP.is_set():
                for gi in range(len(self.groups)):
                    if STOP.is_set():
                        break
                    try:
                        self.serve(gi)
                        fails = 0
                    except Exception as e:
                        fails += 1
                        log.warning("errore radio (%d/%d): %s", fails, RADIO_MAX_FAILS, e)
                        if fails >= RADIO_MAX_FAILS:
                            log.error("troppi errori radio consecutivi: fermo la cattura")
                            return
                        STOP.wait(2)
        finally:
            self.close()
            log.info("radio chiusa")


# ─────────────────────────────── demo (solo interfaccia, nessuna radio)
DEMO = [("CC", "Centrale a 21, andate in via Nomentana civico 88 per incidente stradale."),
        ("PS", "Volante 7, intervento in piazza Vittorio Emanuele II per schiamazzi."),
        ("PL", "Pronto intervento, via del Corso altezza civico 12, auto in sosta vietata."),
        ("CC", "Ricevuto, in avvicinamento. Traffico intenso su via Salaria."),
        ("PS", "Richiedo pattuglia di supporto in via Cavour, soggetto molesto."),
        ("VVF", "Squadra 3, intervento in lungotevere Marzio per principio di incendio."),
        ("CC", "Centrale, soggetto in fuga a piedi verso viale Trastevere."),
        ("PS", "Situazione rientrata in piazza del Popolo, nessun ferito."),
        ("PL", "Segnalazione su via Nazionale, veicolo senza revisione."),
        ("CC", "Rientro in caserma, via di Macchia Saponara.")]


def demo_thread(cfg, txq):
    """Righe già complete (testo + posizione): non passano dal trascrittore."""
    freqs = {c["unit"]: c["freq"] for c in cfg["freqs"]}
    pos = {}
    while not STOP.is_set():
        unit, text = random.choice(DEMO)
        g = extract_place(text, cfg)
        if g:
            place, lat, lon = g[0], g[1], g[2]
        else:
            # senza rete il geocoder non risponde: le unità si muovono comunque sulla mappa
            place = None
            lat, lon = pos.get(unit, (cfg["lat"], cfg["lon"]))
            lat += random.uniform(-0.0025, 0.0025)
            lon += random.uniform(-0.0035, 0.0035)
        pos[unit] = (lat, lon)
        x("""INSERT INTO tx(ts,freq,unit,mode,text,conf,place,lat,lon,state,dur)
             VALUES(?,?,?,?,?,?,?,?,?,'demo',?)""",
          (time.time(), freqs.get(unit, 0), unit, "demo", text,
           round(random.uniform(0.7, 0.95), 2), place, lat, lon, round(random.uniform(2, 7), 1)))
        STOP.wait(random.uniform(4, 9))


# ─────────────────────────────── trascrizione


def to_wav16k(src):
    """Converte il raw del sink dsd-fme in WAV 16 kHz. Ritorna il path o None."""
    if not have("ffmpeg"):
        log.warning("ffmpeg assente: non posso convertire %s", os.path.basename(src))
        return None
    if os.path.getsize(src) < 48000 * 2 * 0.3:
        return None
    dst = src[:-4] + ".wav"
    r = sh(['ffmpeg', '-y', '-loglevel', 'error', '-f', 's16le', '-ar', '48000', '-ac', '1',
            '-i', src, '-ar', '16000', dst])
    if r.returncode != 0 or not os.path.exists(dst):
        log.warning("ffmpeg fallito su %s: %s", os.path.basename(src), r.stderr.strip()[:120])
        return None
    try:
        os.unlink(src)
    except OSError:
        pass
    return dst


def transcriber(cfg, txq):
    model = None
    if cfg.get("stt", True):
        try:
            from faster_whisper import WhisperModel
            log.info("carico whisper '%s' (il primo avvio scarica i pesi)...", cfg["model"])
            model = WhisperModel(cfg["model"], device="cpu", compute_type="int8")
            log.info("whisper pronto")
        except Exception as e:
            log.warning("whisper non disponibile (%s): tengo solo l'audio", str(e)[:120])
            log.warning("  installa con: %s -m pip install faster-whisper", sys.executable)

    # tratte rimaste in sospeso da un'esecuzione precedente
    for r in q("SELECT id FROM tx WHERE state='pending' ORDER BY ts"):
        txq.put(r["id"])

    while not STOP.is_set():
        try:
            tid = txq.get(timeout=1)
        except queue.Empty:
            continue
        rows = q("SELECT wav,state FROM tx WHERE id=?", (tid,))
        if not rows or rows[0]["state"] != "pending":
            continue
        src = rows[0]["wav"]
        if not src or not os.path.exists(src):
            x("UPDATE tx SET state='error' WHERE id=?", (tid,))
            continue
        if src.endswith(".raw"):
            dst = to_wav16k(src)
            if not dst:
                x("UPDATE tx SET state='error' WHERE id=?", (tid,))
                continue
            src = dst
            x("UPDATE tx SET wav=? WHERE id=?", (src, tid))   # ora è riproducibile dal browser
        if model is None:
            x("UPDATE tx SET state='nostt' WHERE id=?", (tid,))
            continue
        try:
            segs, _ = model.transcribe(
                src, language=cfg.get("stt_lang") or "it", vad_filter=True, beam_size=1,
                initial_prompt="Centrale, volante, intervenite, via, civico, targa.")
            segs = list(segs)
            text = " ".join(s.text.strip() for s in segs).strip()
            lp = [s.avg_logprob for s in segs if s.avg_logprob is not None]
            conf = round(math.exp(sum(lp) / len(lp)), 3) if lp else 0.0
            if len(text) < 10:
                x("UPDATE tx SET state='empty',conf=? WHERE id=?", (conf, tid))
                continue
            g = extract_place(text, cfg)
            x("""UPDATE tx SET text=?,conf=?,place=?,lat=?,lon=?,state='done' WHERE id=?""",
              (text, conf, g[0] if g else None, g[1] if g else None, g[2] if g else None, tid))
            log.info("→ [%s] %s", round(conf, 2), text[:90])
        except Exception as e:
            log.warning("trascrizione fallita: %s", e)
            x("UPDATE tx SET state='error' WHERE id=?", (tid,))


# ─────────────────────────────── manutenzione (retention disco + DB)


def janitor_once(cfg):
    """Un giro di pulizia: audio scaduto, righe scadute, buchi del geocoder, file orfani."""
    cutoff = time.time() - float(cfg["retention_hours"]) * 3600
    for r in q("SELECT wav FROM tx WHERE ts<? AND wav IS NOT NULL", (cutoff,)):
        try:
            os.unlink(r["wav"])
        except OSError:
            pass
    c = _conn()
    n = c.execute("DELETE FROM tx WHERE ts<?", (cutoff,)).rowcount
    c.commit()
    x("DELETE FROM geo WHERE lat IS NULL AND ts<?", (cutoff,))   # scadono solo i 'buchi'
    x("DELETE FROM air WHERE seen<?", (time.time() - 3600,))
    for f in os.listdir(AUDIO):                                  # file audio orfani
        p = os.path.join(AUDIO, f)
        try:
            if os.path.isfile(p) and os.path.getmtime(p) < cutoff:
                os.unlink(p)
        except OSError:
            pass
    return n


def janitor(cfg):
    while not STOP.is_set():
        try:
            janitor_once(cfg)
        except Exception as e:
            log.warning("janitor: %s", e)
        STOP.wait(600)


# ─────────────────────────────── adsb


def adsb_thread(cfg):
    url = "https://api.adsb.lol/v2/lat/%s/lon/%s/dist/%s" % (
        cfg["lat"], cfg["lon"], int(cfg["radius_km"]))
    delay = float(cfg["adsb_interval"])
    while not STOP.is_set():
        try:
            resp = http().get(url, timeout=10)
            if resp.status_code == 429:
                delay = min(120.0, delay * 2)
                log.debug("adsb: rate limit, rallento a %.0fs", delay)
            else:
                resp.raise_for_status()
                n = 0
                for a in resp.json().get("ac", []):
                    h = (a.get("hex") or "").lower()
                    alt, spd = a.get("alt_baro"), a.get("gs") or 0
                    # 33xxxx = immatricolazione italiana; lento e basso ≈ elicottero in servizio
                    if not h.startswith("33") or not isinstance(alt, int):
                        continue
                    if alt > 4000 or spd > 140:
                        continue
                    x("INSERT OR REPLACE INTO air VALUES(?,?,?,?,?,?,?)",
                      (h, (a.get("flight") or "").strip(), a.get("lat"), a.get("lon"),
                       alt, spd, time.time()))
                    n += 1
                delay = float(cfg["adsb_interval"])
        except Exception as e:
            delay = min(120.0, max(delay, 5.0) * 1.5)
            log.debug("adsb: %s (riprovo in %.0fs)", e, delay)
        STOP.wait(delay)


# ─────────────────────────────── api

CSP = ("default-src 'self'; "
       "script-src 'self' 'unsafe-inline' https://unpkg.com https://cdnjs.cloudflare.com; "
       "style-src 'self' 'unsafe-inline' https://unpkg.com; "
       "worker-src blob:; child-src blob:; img-src 'self' data: blob: https:; "
       "connect-src 'self' https:; media-src 'self'; frame-ancestors 'none'; base-uri 'none'")


def build_app(cfg, info=None):
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    info = info or {}
    bad = {}

    @app.middleware("http")
    async def headers(request, call_next):
        resp = await call_next(request)
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["Content-Security-Policy"] = CSP
        return resp

    def ok(req):
        tok = req.query_params.get("t") or req.cookies.get("t") or ""
        return bool(cfg["token"]) and hmac.compare_digest(str(tok), str(cfg["token"]))

    def auth(req):
        if ok(req):
            return
        ip = req.client.host if req.client else "?"
        bad[ip] = bad.get(ip, 0) + 1
        if bad[ip] > 5:
            time.sleep(0.5)      # freno elementare contro i tentativi a forza bruta
        raise HTTPException(401, "token mancante o errato")

    def snap():
        now = time.time()
        units, seen = [], set()
        for u in q("""SELECT unit,freq,text,place,lat,lon,ts,conf FROM tx
                      WHERE lat IS NOT NULL AND ts>? ORDER BY ts DESC""", (now - 300,)):
            if u["unit"] in seen:
                continue
            seen.add(u["unit"])
            u["age"] = round(now - u["ts"], 1)
            units.append(u)
        ev = q("""SELECT id,ts,unit,freq,text,place,lat,lon,conf,dur,rssi,
                         (wav IS NOT NULL AND wav LIKE '%.wav') AS has_audio
                  FROM tx WHERE state IN ('done','nostt','demo') ORDER BY ts DESC LIMIT 80""")
        return {"now": now, "mode": info.get("mode", "?"), "units": units, "events": ev,
                "air": q("SELECT * FROM air WHERE seen>?", (now - 45,))}

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request):
        if request.query_params.get("t"):
            if not ok(request):
                return HTMLResponse(NOTOKEN, status_code=401)
            r = RedirectResponse("/", status_code=302)
            r.set_cookie("t", request.query_params["t"], max_age=86400 * 365,
                         httponly=True, samesite="lax", path="/")
            return r
        if not ok(request):
            return HTMLResponse(NOTOKEN, status_code=401)
        # il token finisce nella pagina solo per chi è già autenticato (fallback senza cookie)
        return HTML.replace("__GUARDIA_CFG__", json.dumps(
            {"lon": cfg["lon"], "lat": cfg["lat"], "zoom": 15,
             "token": cfg["token"], "mode": info.get("mode", "?")}))

    @app.get("/api/state")
    def state(request: Request):
        auth(request)
        return snap()

    @app.get("/api/audio/{tid}")
    def audio(tid: int, request: Request):
        auth(request)
        r = q("SELECT wav FROM tx WHERE id=?", (tid,))
        p = r[0]["wav"] if r else None
        if not p or not p.endswith(".wav") or not os.path.exists(p):
            raise HTTPException(404)
        if os.path.realpath(p) != os.path.join(os.path.realpath(AUDIO), os.path.basename(p)):
            raise HTTPException(404)      # difesa in profondità: solo file dentro ./audio
        return FileResponse(p, media_type="audio/wav")

    @app.get("/health")
    def health():
        n = q("SELECT COUNT(*) c FROM tx")[0]["c"]
        pend = q("SELECT COUNT(*) c FROM tx WHERE state='pending'")[0]["c"]
        return {"ok": True, "mode": info.get("mode", "?"), "tx": n, "pending": pend,
                "uptime": round(time.time() - info.get("t0", time.time()), 1)}

    return app


NOTOKEN = """<!doctype html><meta charset="utf-8"><title>Guardia</title>
<body style="background:#0b0f14;color:#e8eef6;font:15px system-ui;padding:40px">
<h2 style="letter-spacing:.1em">GUARDIA</h2>
<p>Serve il token di accesso: apri l'indirizzo con <code>?t=IL_TUO_TOKEN</code>.</p>
<p style="color:#7d8b9c">Lo trovi stampato all'avvio del programma e in <code>guardia.json</code>.</p>
</body>"""

HTML = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>Sala Operativa 3D</title>
<link href="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.css" rel="stylesheet">
<script src="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<style>
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
body{margin:0;background:#0b0f14;color:#e8eef6;font:14px system-ui,sans-serif;display:flex;flex-direction:column;height:100dvh}
header{display:flex;justify-content:space-between;align-items:center;padding:11px 14px;border-bottom:1px solid #1e2833;z-index:3}
h1{margin:0;font-size:12px;letter-spacing:.14em;font-weight:800}
.sub{font-size:10px;color:#7d8b9c;margin-top:2px}
.live{font-size:9px;font-weight:800;background:#b91c1c;color:#fff;padding:4px 9px;border-radius:99px;animation:pulse 1.6s infinite}
.live.off{background:#334155;animation:none}
@keyframes pulse{50%{opacity:.45}}
#wrap{flex:1;position:relative;min-height:240px}
#m{position:absolute;inset:0}
#leg{position:absolute;left:10px;bottom:10px;z-index:2;background:rgba(11,15,20,.78);
border:1px solid #1e2833;border-radius:10px;padding:8px 10px;font-size:10.5px;backdrop-filter:blur(6px)}
#leg b{display:block;font-size:9px;letter-spacing:.1em;color:#7d8b9c;margin-bottom:4px}
#leg span{display:inline-flex;align-items:center;gap:5px;margin-right:9px}
.dot{width:9px;height:9px;border-radius:2px;display:inline-block}
#feed{max-height:34vh;overflow:auto;border-top:1px solid #1e2833}
.row{display:flex;gap:9px;padding:9px 13px;border-bottom:1px solid #1e2833;font-size:12px;cursor:pointer}
.row:active{background:#111823}
.t{color:#7d8b9c;font-size:10.5px}
.u{font-weight:800;font-size:10.5px;min-width:38px}
.p{color:#14b8a6;font-size:10px;margin-top:3px}
.q{color:#7d8b9c;font-style:italic}
.maplibregl-ctrl-group{background:#121a24!important}
.maplibregl-ctrl button{filter:invert(1) hue-rotate(180deg)}
</style></head><body>
<header><div><h1>SALA OPERATIVA 3D</h1><div class="sub" id="sub">connessione...</div></div>
<div class="live" id="live">LIVE</div></header>
<div id="wrap"><div id="m"></div>
<div id="leg"><b>UNIT&Agrave;</b>
<span><i class="dot" style="background:#2563eb"></i>CC</span>
<span><i class="dot" style="background:#dc2626"></i>PS</span>
<span><i class="dot" style="background:#16a34a"></i>PL</span>
<span><i class="dot" style="background:#d97706"></i>VVF</span>
<span><i class="dot" style="background:#d97706;border-radius:50%"></i>elicottero</span>
</div></div>
<div id="feed"></div>
<script>
const CFG=__GUARDIA_CFG__;
const QS=CFG.token?('?t='+encodeURIComponent(CFG.token)):'';
const COL={CC:0x2563eb,PS:0xdc2626,PL:0x16a34a,VVF:0xd97706};
const COLW={CC:'#2563eb',PS:'#dc2626',PL:'#16a34a',VVF:'#d97706'};
const SCAR=5, SHELI=5;

// base scura CartoDB: senza API key e affidabile, garantisce che la mappa funzioni sempre
const map=new maplibregl.Map({container:'m',center:[CFG.lon,CFG.lat],zoom:CFG.zoom,
pitch:58,bearing:-18,maxPitch:82,antialias:true,attributionControl:false,
style:{version:8,sources:{b:{type:'raster',tileSize:256,
tiles:['https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png','https://b.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png'],
attribution:'&copy; OpenStreetMap, &copy; CARTO'}},
layers:[{id:'b',type:'raster',source:'b'}]}});
map.addControl(new maplibregl.NavigationControl({visualizePitch:true}),'top-right');
map.on('error',()=>{});   // ignora errori di sorgenti opzionali (es. edifici vettoriali)

// ───────── modelli 3D con Three.js (custom layer, condivide il contesto di MapLibre)
const V={cars:new Map(),helis:new Map(),scene:null,renderer:null,camera:null};
let useThree=(typeof THREE!=='undefined');

function baseMatrix(lng,lat,alt,s){
  const c=maplibregl.MercatorCoordinate.fromLngLat([lng,lat],alt||0);
  const sc=c.meterInMercatorCoordinateUnits()*s;
  return new THREE.Matrix4().makeTranslation(c.x,c.y,c.z)
    .scale(new THREE.Vector3(sc,-sc,sc))
    .multiply(new THREE.Matrix4().makeRotationAxis(new THREE.Vector3(1,0,0),Math.PI/2));
}
function buildCar(hex,truck){
  const g=new THREE.Group();
  const L=truck?7:4.8,H=truck?1.7:0.9,W=truck?2.4:2.2;
  const body=new THREE.Mesh(new THREE.BoxGeometry(W,H,L),
    new THREE.MeshStandardMaterial({color:hex,metalness:.3,roughness:.5}));
  body.position.y=0.55+H/2; g.add(body);
  const cab=new THREE.Mesh(new THREE.BoxGeometry(W*.92,.7,truck?2.6:2.2),
    new THREE.MeshStandardMaterial({color:0x0b0f14,metalness:.1,roughness:.25}));
  cab.position.set(0,0.55+H+0.35,truck?L*.22:-0.25); g.add(cab);
  const bar=new THREE.Mesh(new THREE.BoxGeometry(W*.62,.24,.5),
    new THREE.MeshStandardMaterial({color:0xffffff,emissive:0x3366ff,emissiveIntensity:1.4}));
  bar.position.set(0,0.55+H+0.78,truck?L*.22:0); g.add(bar); g.userData.bar=bar;
  const wm=new THREE.MeshStandardMaterial({color:0x0a0a0a});
  [[W/2,L*.3],[-W/2,L*.3],[W/2,-L*.3],[-W/2,-L*.3]].forEach(p=>{
    const w=new THREE.Mesh(new THREE.CylinderGeometry(.5,.5,.32,14),wm);
    w.rotation.z=Math.PI/2; w.position.set(p[0],.5,p[1]); g.add(w);});
  return g;
}
function buildHeli(){
  const g=new THREE.Group();
  const mat=new THREE.MeshStandardMaterial({color:0xd97706,metalness:.45,roughness:.5});
  const body=new THREE.Mesh(new THREE.SphereGeometry(2,18,12),mat);
  body.scale.set(1,.9,1.6); body.position.y=2.2; g.add(body);
  const boom=new THREE.Mesh(new THREE.CylinderGeometry(.42,.24,6,14),mat);
  boom.rotation.x=Math.PI/2; boom.position.set(0,2.6,-4.3); g.add(boom);
  const tail=new THREE.Mesh(new THREE.BoxGeometry(.2,1.6,.5),mat); tail.position.set(0,2.9,-7); g.add(tail);
  const rotor=new THREE.Group(); rotor.position.y=3.8;
  const bm=new THREE.MeshStandardMaterial({color:0x1a1a1a});
  const b1=new THREE.Mesh(new THREE.BoxGeometry(12,.12,.6),bm); rotor.add(b1);
  const b2=b1.clone(); b2.rotation.y=Math.PI/2; rotor.add(b2);
  g.add(rotor); g.userData.rotor=rotor;
  const sm=new THREE.MeshStandardMaterial({color:0x0a0a0a});
  [-1.4,1.4].forEach(sx=>{const s=new THREE.Mesh(new THREE.BoxGeometry(.2,.2,5),sm);
    s.position.set(sx,.2,0); g.add(s);});
  return g;
}
const layer3d={id:'vehicles',type:'custom',renderingMode:'3d',
  onAdd(m,gl){
    V.camera=new THREE.Camera(); V.scene=new THREE.Scene();
    V.scene.add(new THREE.AmbientLight(0xffffff,.95));
    const d=new THREE.DirectionalLight(0xffffff,.65); d.position.set(.4,-1,.8); V.scene.add(d);
    V.renderer=new THREE.WebGLRenderer({canvas:m.getCanvas(),context:gl,antialias:true});
    V.renderer.autoClear=false;
  },
  render(gl,arg){
    let a=arg;   // MapLibre 4 passa un oggetto, le versioni precedenti la matrice
    if(a&&!Array.isArray(a)) a=(a.defaultProjectionData&&a.defaultProjectionData.mainMatrix)||a;
    animate();
    V.camera.projectionMatrix=new THREE.Matrix4().fromArray(a);
    V.renderer.resetState();
    V.renderer.render(V.scene,V.camera);
    map.triggerRepaint();
  }};
function addCar(u){
  const outer=new THREE.Group(); outer.matrixAutoUpdate=false;
  const inner=new THREE.Group();
  const model=buildCar(COL[u.unit]||0x6ea8ff,u.unit==='VVF');
  inner.add(model); outer.add(inner); V.scene.add(outer);
  const v={outer,inner,bar:model.userData.bar,lng:u.lon,lat:u.lat,tlng:u.lon,tlat:u.lat,heading:0};
  V.cars.set(u.unit,v); return v;
}
function addHeli(a){
  const outer=new THREE.Group(); outer.matrixAutoUpdate=false;
  const model=buildHeli(); outer.add(model); V.scene.add(outer);
  const v={outer,rotor:model.userData.rotor,lng:a.lon,lat:a.lat,tlng:a.lon,tlat:a.lat,alt:120};
  V.helis.set(a.hex,v); return v;
}
function animate(){
  const t=Date.now();
  V.cars.forEach(v=>{
    v.lng+=(v.tlng-v.lng)*.12; v.lat+=(v.tlat-v.lat)*.12;
    const dx=v.tlng-v.lng, dy=v.tlat-v.lat;
    if(Math.hypot(dx,dy)>1e-6) v.heading=Math.atan2(dx,dy);
    v.inner.rotation.y=v.heading;
    v.outer.matrix.copy(baseMatrix(v.lng,v.lat,0,SCAR)); v.outer.matrixWorldNeedsUpdate=true;
    if(v.bar){const on=(t%700)<350; v.bar.material.emissive.setHex(on?0x3366ff:0xff2b2b);}
  });
  V.helis.forEach(v=>{
    v.lng+=(v.tlng-v.lng)*.1; v.lat+=(v.tlat-v.lat)*.1;
    v.outer.matrix.copy(baseMatrix(v.lng,v.lat,v.alt,SHELI)); v.outer.matrixWorldNeedsUpdate=true;
    if(v.rotor) v.rotor.rotation.y+=.7;
  });
}
function applyThree(d){
  const su=new Set();
  d.units.forEach(u=>{if(u.lat==null)return; su.add(u.unit);
    const v=V.cars.get(u.unit)||addCar(u); v.tlng=u.lon; v.tlat=u.lat;});
  V.cars.forEach((v,k)=>{if(!su.has(k)){V.scene.remove(v.outer);V.cars.delete(k);}});
  const sa=new Set();
  d.air.forEach(a=>{if(a.lat==null||a.lon==null)return; sa.add(a.hex);
    const v=V.helis.get(a.hex)||addHeli(a); v.tlng=a.lon; v.tlat=a.lat;
    v.alt=Math.min(a.alt||120,300);});
  V.helis.forEach((v,k)=>{if(!sa.has(k)){V.scene.remove(v.outer);V.helis.delete(k);}});
}
// ───────── fallback: marker DOM 2D se Three.js non è disponibile
const DM=new Map(),DH=new Map();
function applyDOM(d){
  d.units.forEach(u=>{if(u.lat==null)return; let m=DM.get(u.unit);
    if(!m){m=new maplibregl.Marker({color:COLW[u.unit]||'#6ea8ff'}).setLngLat([u.lon,u.lat]).addTo(map);DM.set(u.unit,m);}
    m.setLngLat([u.lon,u.lat]); m.getElement().style.opacity=Math.max(.25,1-u.age/300);});
  d.air.forEach(a=>{if(a.lat==null)return; let m=DH.get(a.hex);
    if(!m){m=new maplibregl.Marker({color:'#d97706'}).setLngLat([a.lon,a.lat]).addTo(map);DH.set(a.hex,m);}
    m.setLngLat([a.lon,a.lat]);});
}
map.on('load',()=>{
  // edifici 3D vettoriali (OpenFreeMap, senza API key): best-effort sopra la base scura
  try{
    map.addSource('ofm',{type:'vector',url:'https://tiles.openfreemap.org/planet'});
    map.addLayer({id:'b3d',source:'ofm','source-layer':'building',type:'fill-extrusion',minzoom:14,
      paint:{'fill-extrusion-color':['interpolate',['linear'],['coalesce',['get','render_height'],10],
        0,'#182233',60,'#243550',180,'#33496d'],
        'fill-extrusion-height':['coalesce',['get','render_height'],8],
        'fill-extrusion-base':['coalesce',['get','render_min_height'],0],
        'fill-extrusion-opacity':.82}});
  }catch(e){}
  if(useThree){ try{ map.addLayer(layer3d); }catch(e){ useThree=false; } }
});

// ───────── feed (nodi DOM, niente innerHTML: il testo arriva dalla trascrizione)
function mkrow(e){
  const r=document.createElement('div'); r.className='row';
  const u=document.createElement('span'); u.className='u';
  u.style.color=COLW[e.unit]||'#6ea8ff'; u.textContent=e.unit;
  const d=document.createElement('div');
  const t=document.createElement('span'); t.className='t';
  t.textContent=new Date(e.ts*1000).toLocaleTimeString('it-IT')+' · '+(e.freq/1e6).toFixed(3)+
    (e.dur?' · '+e.dur+'s':'')+(e.has_audio?' · ♪':'');
  const b=document.createElement('div');
  if(e.text){b.textContent=e.text;}else{b.className='q';b.textContent='— solo audio —';}
  d.append(t,b);
  if(e.place){const p=document.createElement('div');p.className='p';
    p.textContent='▸ '+e.place; d.append(p);}
  r.append(u,d);
  r.onclick=()=>{
    if(e.lat!=null) map.flyTo({center:[e.lon,e.lat],zoom:16,pitch:62,essential:true});
    if(e.has_audio) new Audio('/api/audio/'+e.id+QS).play().catch(()=>{});
  };
  return r;
}
const seen=new Set();
let fails=0;
async function tick(){
  try{
    const r=await fetch('/api/state'+QS,{cache:'no-store'});
    if(!r.ok) throw new Error('HTTP '+r.status);
    const d=await r.json();
    fails=0; document.getElementById('live').className='live';
    (useThree?applyThree:applyDOM)(d);
    document.getElementById('sub').textContent=
      d.units.length+' unità · '+d.air.length+' aeromobili · '+d.mode+(useThree?' · 3D':' · 2D');
    const f=document.getElementById('feed');
    d.events.forEach(e=>{if(seen.has(e.id))return; seen.add(e.id);
      f.prepend(mkrow(e)); while(f.children.length>120) f.removeChild(f.lastChild);});
  }catch(err){
    fails++;
    document.getElementById('live').className='live off';
    document.getElementById('sub').textContent=(fails>1?'offline':'errore')+' — '+err.message;
  }
}
setInterval(tick,3000); tick();
</script></body></html>"""


# ─────────────────────────────── selftest (nessun hardware richiesto)


def t_config():
    """config: valori impossibili corretti, canali non validi scartati"""
    cfg = validate_cfg(dict(DEFAULTS, port=99999, gain=900, ppm="x", squelch_mode="boh",
                            min_voice=5, max_seg=2, freqs=[
                                {"freq": 10, "unit": "X", "mode": "analog"},
                                {"freq": 151175000, "unit": "CC", "mode": "strano"},
                                {"freq": 151175000, "unit": "CC", "mode": "analog"},
                                "spazzatura"]))
    assert cfg["port"] == 8080, cfg["port"]
    assert cfg["gain"] == 50 and cfg["ppm"] == 0
    assert cfg["squelch_mode"] == "auto"
    assert cfg["max_seg"] > cfg["min_voice"]
    assert len(cfg["freqs"]) == 1, cfg["freqs"]
    assert cfg["freqs"][0]["mode"] == "analog"
    assert validate_cfg(dict(DEFAULTS, freqs=[]))["freqs"] == DEFAULTS["freqs"]


def t_regex():
    """regex toponimi: riconosce via/piazza/lungotevere e si ferma dove deve"""
    casi = {
        "andate in via Nomentana civico 88 per incidente": "via Nomentana",
        "intervento in piazza Vittorio Emanuele II per schiamazzi": "piazza Vittorio Emanuele II",
        "via del Corso altezza civico 12": "via del Corso",
        "Traffico intenso su via Salaria": "via Salaria",
        "squadra in lungotevere Marzio": "lungotevere Marzio",
        "Rientro in caserma, via di Macchia Saponara": "via di Macchia Saponara",
        "soggetto in fuga verso Viale Trastevere": "viale Trastevere",
    }
    for frase, atteso in casi.items():
        m = PAT.search(frase)
        assert m, "nessun match: " + frase
        got = ("%s %s" % (m.group(1).lower(), m.group(2).strip().rstrip(" ,.;:")))
        assert got == atteso, "%r != %r" % (got, atteso)
    assert not PAT.search("nessun indirizzo qui, solo parole")


def t_cluster():
    """raggruppamento canali e scelta del centro di sintonia"""
    g = cluster(DEFAULTS["freqs"], 1_900_000)
    assert len(g) == 2, g                     # 151/152 in un gruppo, 160.9/161.3 nell'altro
    assert [len(x) for x in g] == [2, 2], g
    vicini = [{"freq": 151175000, "unit": "A", "mode": "analog"},
              {"freq": 151200000, "unit": "B", "mode": "analog"},
              {"freq": 152025000, "unit": "C", "mode": "analog"}]
    g = cluster(vicini, 1_900_000)
    assert len(g) == 1 and len(g[0]) == 3, g
    c = pick_center(g[0])
    assert all(abs(ch["freq"] - c) > 12_000 for ch in g[0])
    assert all(abs(ch["freq"] - c) < 1_200_000 for ch in g[0])


def _two_ch_cfg(**kw):
    return validate_cfg(dict(DEFAULTS, freqs=[
        {"freq": 160000000, "unit": "A", "mode": "analog"},
        {"freq": 160300000, "unit": "B", "mode": "analog"}], **kw))


def t_dsp():
    """canalizzatore: livelli per canale e tono demodulato a 700 Hz"""
    import numpy as np
    cfg = _two_ch_cfg()
    group = cfg["freqs"]
    center = pick_center(group)
    src = SimSource(cfg, realtime=False)
    src.tune(center)
    chz = Channelizer(cfg, [c["freq"] - center for c in group])

    # il canale A parla da 1.5 a 4.0 s, il B da 3.2 a 6.2: misuro nella finestra 1.8-3.0
    lv, audio = {}, []
    t = 0.0
    while t < 3.0:
        r = chz.process(src.read(chz.new))
        t += chz.dt
        if r and t > 1.8:
            lv.setdefault("A", []).append(r[0][0])
            lv.setdefault("B", []).append(r[1][0])
            audio.append(r[0][1])
    a, b = max(lv["A"]), max(lv["B"])
    assert -26 < a < -14, "livello canale attivo fuori scala: %.1f dBFS" % a
    assert b < a - 25, "isolamento insufficiente: A=%.1f B=%.1f" % (a, b)

    sig = np.concatenate(audio)
    assert len(sig) > 9000
    sp = np.abs(np.fft.rfft(sig * np.hanning(len(sig))))
    f = np.fft.rfftfreq(len(sig), 1.0 / Channelizer.AUDIO_SR)[int(np.argmax(sp))]
    assert abs(f - 700) < 25, "tono demodulato a %.0f Hz invece di 700" % f
    pk = float(np.max(np.abs(sig)))
    assert 0.2 < pk < 1.5, "ampiezza audio anomala: %.2f" % pk


def t_gate():
    """squelch automatico: apre sui burst, resta chiuso sul rumore"""
    cfg = _two_ch_cfg()
    group = cfg["freqs"]
    center = pick_center(group)
    chz = Channelizer(cfg, [c["freq"] - center for c in group])
    src = SimSource(cfg, realtime=False)
    src.tune(center)
    gates = [Gate(cfg, c) for c in group]
    segs = {0: [], 1: []}
    t = 0.0
    while t < 13.0:
        r = chz.process(src.read(chz.new))
        t += chz.dt
        if not r:
            continue
        for i, (rssi, aud) in enumerate(r):
            s = gates[i].push(aud, rssi, t)
            if s:
                segs[i].append(s)
    assert len(segs[0]) >= 2, "canale A: %d tratte" % len(segs[0])
    assert len(segs[1]) >= 1, "canale B: %d tratte" % len(segs[1])
    for i in segs:
        for s in segs[i]:
            assert 2.0 < s["dur"] < 6.0, s
            assert s["rssi"] > s["floor"] + 10, s

    # stesso rumore ma senza nessuna trasmissione: lo squelch non deve aprire
    chz.reset()
    src2 = SimSource(cfg, realtime=False, seed=3)
    src2.bursts = lambda *a: iter(())
    g = Gate(cfg, group[0])
    t = 0.0
    while t < 4.0:
        r = chz.process(src2.read(chz.new))
        t += chz.dt
        if r:
            assert g.push(r[0][1], r[0][0], t) is None, "squelch aperto sul rumore"
    assert not g.open


def t_wav():
    """scrittura WAV: durata, formato e normalizzazione per tratta"""
    import numpy as np
    sr = Channelizer.AUDIO_SR
    sig = (0.2 * np.sin(2 * math.pi * 440 * np.arange(sr) / sr)).astype(np.float32)
    p = write_wav(os.path.join(AUDIO, "t_wav.wav"), sig)
    with wave.open(p) as w:
        assert w.getnchannels() == 1 and w.getsampwidth() == 2 and w.getframerate() == sr
        assert w.getnframes() == sr
        pcm = np.frombuffer(w.readframes(sr), dtype="<i2")
    assert 0.65 * 32767 < np.max(np.abs(pcm)) <= 0.72 * 32767, np.max(np.abs(pcm))
    os.unlink(p)
    # tratta molto debole: il guadagno è limitato, non amplifica il rumore all'infinito
    p = write_wav(os.path.join(AUDIO, "t_wav2.wav"), sig * 0.001)
    with wave.open(p) as w:
        pcm = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2")
    assert abs(np.max(np.abs(pcm)) - 0.2 * 0.001 * 8 * 32767) < 2, np.max(np.abs(pcm))
    os.unlink(p)


def t_db():
    """db: stati, cache del geocoder e retention"""
    tid = x("INSERT INTO tx(ts,freq,unit,mode,wav,state,dur) VALUES(?,?,?,?,?,'pending',1.5)",
            (time.time(), 160000000, "A", "analog", None))
    assert q("SELECT state FROM tx WHERE id=?", (tid,))[0]["state"] == "pending"
    x("UPDATE tx SET text=?,state='done' WHERE id=?", ("via Prova 1", tid))
    assert q("SELECT COUNT(*) c FROM tx WHERE state='done'")[0]["c"] >= 1

    cfg = dict(DEFAULTS, retention_hours=1)
    x("INSERT INTO geo VALUES('via cache',41.9,12.5,0.8,?)", (time.time(),))
    assert geocode("Via Cache", cfg) == (41.9, 12.5, 0.8)
    x("INSERT INTO geo VALUES('via buco',NULL,NULL,0,?)", (time.time() - 10,))
    assert geocode("via buco", cfg) is None          # buco ancora valido: nessuna rete

    old = os.path.join(AUDIO, "vecchio.wav")
    open(old, "wb").write(b"x")
    x("INSERT INTO tx(ts,freq,unit,mode,wav,state) VALUES(?,?,?,?,?,'done')",
      (time.time() - 7200, 1, "Z", "analog", old))
    assert janitor_once(cfg) >= 1
    assert not os.path.exists(old)
    assert q("SELECT COUNT(*) c FROM tx WHERE unit='Z'")[0]["c"] == 0


def t_api():
    """api: token obbligatorio, nessun path di filesystem esposto, header di sicurezza"""
    try:
        from fastapi.testclient import TestClient
    except Exception as e:
        print("  salto  api (%s)" % str(e)[:40])
        return
    cfg = validate_cfg(dict(DEFAULTS, token="segreto123"))
    wav = write_wav(os.path.join(AUDIO, "t_api.wav"), __import__("numpy").zeros(48000, "f4"))
    x("""INSERT INTO tx(ts,freq,unit,mode,wav,text,state,lat,lon,place)
         VALUES(?,?,?,?,?,?,'done',41.9,12.5,'via Prova')""",
      (time.time(), 160000000, "A", "analog", wav, "prova di testo lungo"))
    c = TestClient(build_app(cfg, {"mode": "test", "t0": time.time()}))
    assert c.get("/").status_code == 401
    assert c.get("/api/state").status_code == 401
    assert c.get("/api/state?t=sbagliato").status_code == 401
    r = c.get("/api/state?t=segreto123")
    assert r.status_code == 200, r.status_code
    js = r.json()
    assert js["events"] and "wav" not in js["events"][0], js["events"][0]
    assert js["events"][0]["has_audio"] == 1
    assert js["units"] and js["units"][0]["unit"] == "A"
    assert "Content-Security-Policy" in r.headers
    tid = js["events"][0]["id"]
    assert c.get("/api/audio/%d" % tid).status_code == 401
    assert c.get("/api/audio/%d?t=segreto123" % tid).status_code == 200
    assert c.get("/api/audio/999999?t=segreto123").status_code == 404
    assert c.get("/health").json()["ok"] is True
    p = c.get("/?t=segreto123", follow_redirects=False)
    assert p.status_code == 302 and "t=" not in p.headers.get("location", "")
    os.unlink(wav)


def t_migrate():
    """db: migrazione da uno schema vecchio senza state/dur/rssi"""
    global DB_PATH
    vecchio = os.path.join(os.path.dirname(DB_PATH), "vecchio.db")
    c = sqlite3.connect(vecchio)
    c.executescript("""
        CREATE TABLE tx(id INTEGER PRIMARY KEY, ts REAL, freq INTEGER, unit TEXT,
            mode TEXT, wav TEXT, text TEXT DEFAULT '', conf REAL, place TEXT, lat REAL, lon REAL);
        CREATE INDEX i_ts ON tx(ts DESC);
        CREATE TABLE geo(q TEXT PRIMARY KEY, lat REAL, lon REAL, conf REAL, ts REAL);
        CREATE TABLE air(hex TEXT PRIMARY KEY, callsign TEXT, lat REAL, lon REAL,
            alt INTEGER, spd REAL, seen REAL);
    """)
    c.execute("INSERT INTO tx(ts,unit,text) VALUES(1,'CC','andate in via Nomentana 88')")
    c.execute("INSERT INTO tx(ts,unit,text) VALUES(2,'PS','')")
    c.commit()
    c.close()

    prima, DB_PATH = DB_PATH, vecchio
    _local.__dict__.pop("conn", None)
    try:
        db_init()                       # non deve sollevare "no such column: state"
        db_init()                       # idempotente
        assert {r["state"] for r in q("SELECT state FROM tx")} == {"done", "empty"}
        assert q("SELECT dur,rssi FROM tx WHERE id=1")[0]["dur"] == 0
        idx = {r["name"] for r in q("SELECT name FROM sqlite_master WHERE type='index'")}
        assert "i_state" in idx, idx
        assert q("SELECT v FROM meta WHERE k='schema'")[0]["v"] == str(SCHEMA_VERSION)
    finally:
        _local.__dict__.pop("conn", None)
        DB_PATH = prima


def t_port():
    """porta: rilevamento di una porta già occupata"""
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    porta = srv.getsockname()[1]
    try:
        assert not port_free("127.0.0.1", porta), "porta occupata vista come libera"
    finally:
        srv.close()
    assert port_free("127.0.0.1", porta), "porta liberata vista come occupata"


TESTS = [t_config, t_regex, t_cluster, t_dsp, t_gate, t_wav, t_db, t_migrate, t_port, t_api]


def do_selftest():
    global DB_PATH, AUDIO
    import tempfile
    import traceback
    ensure_env(["numpy"])
    td = tempfile.mkdtemp(prefix="guardia-test-")
    DB_PATH = os.path.join(td, "test.db")
    AUDIO = os.path.join(td, "audio")
    os.makedirs(AUDIO, exist_ok=True)
    logging.disable(logging.CRITICAL)   # i test parlano da soli: zittisco tutti i logger
    db_init()
    print("== SELFTEST ==")
    bad = 0
    try:
        for fn in TESTS:
            t0 = time.time()
            try:
                fn()
                print("  ok     %-28s %.2fs  %s" % (fn.__name__, time.time() - t0,
                                                    fn.__doc__ or ""))
            except AssertionError as e:
                bad += 1
                print("  FAIL   %-28s %s" % (fn.__name__, e))
            except Exception:
                bad += 1
                print("  ERRORE %s\n%s" % (fn.__name__, traceback.format_exc()))
    finally:
        _local.__dict__.pop("conn", None)
        shutil.rmtree(td, ignore_errors=True)
    print("== %s ==" % ("TUTTO OK" if not bad else "%d TEST FALLITI" % bad))
    return 1 if bad else 0


# ─────────────────────────────── main


def parse_freqs(spec):
    """'FREQ:UNITA:modo,...' → lista di canali. Il modo è opzionale (default analog)."""
    out = []
    for p in spec.split(","):
        p = p.strip()
        if not p:
            continue
        bits = p.split(":")
        if len(bits) == 2:
            bits.append("analog")
        if len(bits) != 3:
            raise ValueError(p)
        out.append({"freq": int(float(bits[0])), "unit": bits[1], "mode": bits[2].lower()})
    if not out:
        raise ValueError("lista vuota")
    return out


def main():
    ap = argparse.ArgumentParser(
        description="Sala operativa radio self-hosted (scanner SDR + trascrizione + mappa 3D).",
        epilog="esempio: guardia.py --freqs 151175000:CC:digital,160900000:PL:analog --gain 24")
    ap.add_argument("--demo", action="store_true", help="solo interfaccia, traffico finto")
    ap.add_argument("--sim", action="store_true", help="catena radio completa su dongle simulato")
    ap.add_argument("--check", action="store_true", help="diagnostica ambiente")
    ap.add_argument("--selftest", action="store_true", help="test interni, senza hardware")
    ap.add_argument("--install", action="store_true", help="(Linux) dipendenze di sistema")
    ap.add_argument("--service", action="store_true", help="(Linux) unit systemd")
    ap.add_argument("--host"), ap.add_argument("--port", type=int), ap.add_argument("--token")
    ap.add_argument("--ppm", type=int), ap.add_argument("--gain", type=int)
    ap.add_argument("--squelch", type=float, help="soglia fissa in dBFS (implica --squelch-mode manual)")
    ap.add_argument("--squelch-mode", choices=["auto", "manual"])
    ap.add_argument("--dwell", type=float, help="secondi per gruppo di canali")
    ap.add_argument("--model", help="modello whisper: tiny/base/small/medium")
    ap.add_argument("--no-stt", action="store_true", help="niente trascrizione, solo audio")
    ap.add_argument("--lat", type=float), ap.add_argument("--lon", type=float)
    ap.add_argument("--freqs", help="FREQ:UNITA:modo,FREQ:UNITA:modo")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args()

    if a.install:
        return do_install()
    if a.check:
        ensure_env([], hard=False)
        return do_check()
    if a.service:
        return do_service()
    if a.verbose:
        log.setLevel(logging.DEBUG)
    if a.selftest:
        return do_selftest()

    win_dll_path()
    ensure_env(REQ_CORE)
    disco = load_cfg()
    nuovo_token = not disco.get("token")
    if nuovo_token:
        disco["token"] = os.urandom(8).hex()
    # gli override da riga di comando valgono SOLO per questa esecuzione: scriverli in
    # guardia.json faceva riapparire un --port di ieri in un avvio senza argomenti
    cfg = dict(disco)
    for k in ["host", "port", "token", "ppm", "gain", "squelch", "squelch_mode", "dwell",
              "model", "lat", "lon"]:
        v = getattr(a, k.replace("-", "_"), None)
        if v is not None:
            cfg[k] = v
    if a.squelch is not None and a.squelch_mode is None:
        cfg["squelch_mode"] = "manual"
    if a.no_stt:
        cfg["stt"] = False
    if a.freqs:
        try:
            cfg["freqs"] = parse_freqs(a.freqs)
        except ValueError as e:
            print("!! --freqs malformato (%s). Usa FREQ:UNITA:modo,FREQ:UNITA:modo" % e)
            print("   es. 151175000:CC:digital,160900000:PL:analog")
            return 1
    validate_cfg(cfg)
    if nuovo_token or not os.path.exists(CFG_PATH):
        save_cfg(validate_cfg(dict(DEFAULTS, **disco)))   # il file resta dell'utente

    if not port_free(cfg["host"], cfg["port"]):
        print("!! la porta %d e' gia' occupata." % cfg["port"])
        print("   Un'altra istanza di guardia e' ancora in esecuzione? Chiudila (Ctrl+C nella")
        print("   sua finestra), oppure usa un'altra porta:  python guardia.py --port 8081")
        if os.path.exists(CFG_PATH):
            print("   La porta predefinita e' quella scritta in %s" % CFG_PATH)
        return 1

    os.makedirs(AUDIO, exist_ok=True)
    db_init()
    txq = queue.Queue()

    # spegnimento pulito su Ctrl+C / kill: i thread (daemon) escono al prossimo check di STOP
    def _shutdown(*_):
        if not STOP.is_set():
            log.info("arresto richiesto, chiudo...")
            STOP.set()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, _shutdown)
        except (ValueError, OSError, AttributeError):
            pass    # non siamo nel thread principale: lascio fare a uvicorn

    mode, radio, source = "demo", None, None
    if a.sim:
        mode = "sim"
        ensure_env(["numpy"])
        source = SimSource(cfg)
        log.info("dongle simulato: burst FM finti sui canali configurati")
    elif not a.demo:
        ensure_env(REQ_RADIO, hard=False)
        try:
            from rtlsdr import RtlSdr
            RtlSdr().close()
            mode = "radio"
        except Exception as e:
            print("!! dongle non disponibile: " + str(e).strip()[:100])
            dongle_hint(e)
            print("!! parto in DEMO (interfaccia con traffico finto). Con --sim provi invece")
            print("   tutta la catena radio su un dongle simulato.")

    if mode in ("radio", "sim"):
        try:
            radio = Radio(cfg, txq, source=source)
            radio.start()
        except Exception as e:
            log.error("radio non avviabile (%s) → DEMO", str(e)[:120])
            mode, radio = "demo", None
    if mode == "demo":
        threading.Thread(target=demo_thread, args=(cfg, txq), name="demo", daemon=True).start()
    else:
        if cfg.get("stt", True):
            ensure_env(REQ_STT, hard=False)
        threading.Thread(target=transcriber, args=(cfg, txq), name="whisper",
                         daemon=True).start()
    if cfg.get("adsb", True):
        threading.Thread(target=adsb_thread, args=(cfg,), name="adsb", daemon=True).start()
    threading.Thread(target=janitor, args=(cfg,), name="janitor", daemon=True).start()

    ip = local_ip()
    canali = ", ".join("%.3f/%s/%s" % (c["freq"] / 1e6, c["unit"], c["mode"])
                       for c in cfg["freqs"])
    print("""
============================================
  GUARDIA  [%s]
  Telefono:  http://%s:%d/?t=%s
  Locale:    http://127.0.0.1:%d/?t=%s
  Canali:    %s
  Squelch:   %s
  Ctrl+C per fermare
============================================
""" % (mode.upper(), ip, cfg["port"], cfg["token"], cfg["port"], cfg["token"], canali,
       "auto (rumore +%.0f dB)" % cfg["squelch_margin"] if cfg["squelch_mode"] == "auto"
       else "fisso %.0f dBFS" % cfg["squelch"]), flush=True)

    import uvicorn
    try:
        uvicorn.run(build_app(cfg, {"mode": mode, "t0": time.time()}),
                    host=cfg["host"], port=cfg["port"], log_level="warning")
    except KeyboardInterrupt:
        pass
    finally:
        STOP.set()
        if radio:
            radio.close()
        time.sleep(0.3)
        print("\nchiuso.")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
