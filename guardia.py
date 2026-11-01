#!/usr/bin/env python3
"""
guardia.py — sala operativa radio self-hosted, un file solo. Windows/Linux.

AVVIO
  python guardia.py            # prima esecuzione: crea venv e installa le dipendenze (3-10 min)
  python guardia.py            # poi: avvia (demo se il dongle non risponde)
  python guardia.py --ppm 42 --gain 24 --freqs 151175000:CC:digital,160900000:PL:analog
  python guardia.py --check

WINDOWS + SDR REALE
  Serve Zadig (https://zadig.akeo.ie): Options > List All Devices > Bulk-In Interface
  > sostituisci il driver con WinUSB. Poi riattacca il dongle e rilancia.

LINUX
  python3 guardia.py --install   # apt + sink audio + dsd-fme

NOTA sul modo 'digital': la cattura invia l'audio demodulato via UDP a 127.0.0.1:7355
e registra l'uscita del sink PulseAudio 'dsd_out'. Serve quindi dsd-fme in ascolto su
quella porta (vedi --install), altrimenti usa 'analog'.
"""
import argparse, hmac, json, logging, os, queue, random, re, shutil, signal
import socket, sqlite3, subprocess, sys, threading, time, wave

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
REQ = ["numpy", "scipy", "pyrtlsdr", "faster-whisper", "fastapi", "uvicorn[standard]", "requests"]

# limiti sintonizzabili del classico RTL-SDR R820T (24 MHz – 1.766 GHz)
FREQ_MIN, FREQ_MAX = 24_000_000, 1_766_000_000
VALID_MODES = {"analog", "digital"}
GEO_HOLE_TTL = 6 * 3600          # un indirizzo non trovato viene ritentato dopo 6 ore
RADIO_MAX_FAILS = 10             # errori radio consecutivi oltre i quali si rinuncia

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname).1s [%(threadName)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("guardia")

DEFAULTS = {
    "port": 8080, "token": "", "ppm": 0, "gain": 28, "squelch": 7.0,
    "min_voice": 0.8, "max_seg": 12, "model": "small", "retention_hours": 48,
    "lat": 41.9028, "lon": 12.4964, "radius_km": 25, "city": "Roma",
    "viewbox": "12.30,41.70,12.75,42.10",
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

def local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80)); return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()

def ensure_env():
    if sys.prefix == sys.base_prefix:
        if not os.path.exists(VPY):
            print("· creo l'ambiente virtuale...", flush=True)
            run_live([sys.executable, "-m", "venv", VENV])
            if not os.path.exists(VPY):
                print("!! venv non creata. Reinstalla Python spuntando 'pip' e 'Add python.exe to PATH'.")
                sys.exit(1)
        os.execv(VPY, [VPY] + sys.argv)

    missing = []
    for pkg in REQ:
        mod = pkg.split("[")[0].replace("-", "_")
        try:
            __import__(mod)
        except Exception:
            missing.append(pkg)
    if not missing:
        return

    print("\n" + "=" * 60)
    print("  INSTALLAZIONE DIPENDENZE — può durare 3-10 minuti.")
    print("  Vedrai l'avanzamento: NON è bloccato, lascia finire.")
    print("  Pacchetti: " + " ".join(missing))
    print("=" * 60 + "\n", flush=True)

    run_live([sys.executable, "-m", "pip", "install", "--upgrade", "pip", "wheel"])
    rc = run_live([sys.executable, "-m", "pip", "install", "--prefer-binary"] + missing)
    if rc != 0:
        print("\n!! Installazione fallita. Lancia a mano per leggere l'errore reale:\n")
        print('   "%s" -m pip install --prefer-binary %s\n' % (VPY, " ".join(missing)))
        sys.exit(1)
    print("\n· dipendenze pronte.\n", flush=True)

def do_install():
    print("== INSTALLAZIONE ==")
    if not IS_WIN:
        run_live(["sudo", "apt", "update"])
        run_live(["sudo", "apt", "install", "-y", "rtl-sdr", "sqlite3", "ffmpeg", "curl",
                  "cmake", "build-essential", "libpulse-dev", "pulseaudio", "python3-venv"])
        if have("pactl"):
            sh("pactl load-module module-null-sink sink_name=dsd_out rate=48000 channels=1")
        if not have("dsd-fme") and not os.path.isdir(os.path.join(BASE, "dsd-fme")):
            run_live(["git", "clone", "https://github.com/lwvmobile/dsd-fme"])
            d = os.path.join(BASE, "dsd-fme")
            if os.path.isdir(d):
                sh(["git", "-C", d, "checkout", "pulseaudio"])
                os.makedirs(os.path.join(d, "build"), exist_ok=True)
                run_live("cd '%s/build' && cmake .. && make -j$(nproc) && sudo make install" % d)
    else:
        print("· Windows: ffmpeg opzionale →  winget install Gyan.FFmpeg")
        print("· Per l'SDR reale serve Zadig/WinUSB sul dongle (vedi docstring).")
    ensure_env()
    print("\nfatto. Avvia con: python guardia.py")

def do_check():
    print("== DIAGNOSTICA ==")
    print("  python  " + sys.executable)
    for pkg in REQ:
        mod = pkg.split("[")[0].replace("-", "_")
        try:
            __import__(mod); print("  ok      " + pkg)
        except Exception:
            print("  MANCA   " + pkg)
    for b in ["rtl_test", "ffmpeg", "parec", "pactl", "dsd-fme"]:
        print(("  ok      " if have(b) else "  assente ") + b)
    try:
        from rtlsdr import RtlSdr
        RtlSdr().close(); print("  ok      dongle RTL-SDR")
    except Exception as e:
        print("  MANCA   dongle (" + str(e)[:60] + ")")
        if IS_WIN:
            print("          → su Windows serve Zadig/WinUSB sul dongle")

def do_service():
    if IS_WIN:
        print("Windows: usa il Task Scheduler, oppure avvia con: pythonw guardia.py")
        return
    unit = f"""[Unit]
Description=Guardia
After=network.target sound.target
[Service]
User={os.environ.get('USER', 'pi')}
WorkingDirectory={BASE}
ExecStart={VPY} {BASE}/guardia.py
Restart=always
RestartSec=5
[Install]
WantedBy=multi-user.target
"""
    open("/tmp/guardia.service", "w").write(unit)
    sh(["sudo", "cp", "/tmp/guardia.service", "/etc/systemd/system/guardia.service"])
    sh(["sudo", "systemctl", "daemon-reload"])
    print("fatto: sudo systemctl enable --now guardia")

# ─────────────────────────────── config/db
def load_cfg():
    cfg = json.loads(json.dumps(DEFAULTS))
    if os.path.exists(CFG_PATH):
        try:
            cfg.update(json.load(open(CFG_PATH)))
        except Exception as e:
            log.warning("config illeggibile (%s), uso i valori di default", e)
    return cfg

def save_cfg(cfg):
    json.dump(cfg, open(CFG_PATH, "w"), indent=2)

def validate_cfg(cfg):
    """Corregge/segnala i valori impossibili. Scarta le frequenze fuori banda."""
    if not (0 < cfg["port"] < 65536):
        log.warning("porta %s non valida → 8080", cfg["port"]); cfg["port"] = 8080
    cfg["gain"] = max(0, min(50, cfg["gain"]))
    cfg["retention_hours"] = max(1, cfg["retention_hours"])
    good = []
    for ch in cfg["freqs"]:
        try:
            f = int(ch["freq"]); mode = ch.get("mode", "analog")
            if not (FREQ_MIN <= f <= FREQ_MAX):
                log.warning("frequenza %s fuori banda, scartata", f); continue
            if mode not in VALID_MODES:
                log.warning("modo '%s' sconosciuto su %s → analog", mode, f); mode = "analog"
            good.append({"freq": f, "unit": str(ch.get("unit", "??")), "mode": mode})
        except (KeyError, ValueError, TypeError):
            log.warning("canale malformato ignorato: %r", ch)
    if not good:
        log.error("nessuna frequenza valida: uso i default"); good = DEFAULTS["freqs"]
    cfg["freqs"] = good
    return cfg

# connessione SQLite dedicata a ciascun thread: thread-safe e senza riaprire a ogni query
_local = threading.local()

def _conn():
    c = getattr(_local, "conn", None)
    if c is None:
        c = sqlite3.connect(DB_PATH, timeout=10)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA busy_timeout=10000")
        _local.conn = c
    return c

def db_init():
    c = sqlite3.connect(DB_PATH)
    c.executescript("""
    PRAGMA journal_mode=WAL;
    CREATE TABLE IF NOT EXISTS tx(id INTEGER PRIMARY KEY, ts REAL, freq INTEGER, unit TEXT,
      mode TEXT, wav TEXT, text TEXT DEFAULT '', conf REAL, place TEXT, lat REAL, lon REAL);
    CREATE INDEX IF NOT EXISTS i_ts ON tx(ts DESC);
    CREATE TABLE IF NOT EXISTS geo(q TEXT PRIMARY KEY, lat REAL, lon REAL, conf REAL, ts REAL);
    CREATE TABLE IF NOT EXISTS air(hex TEXT PRIMARY KEY, callsign TEXT, lat REAL, lon REAL,
      alt INTEGER, spd REAL, seen REAL);
    """)
    c.commit(); c.close()

def q(sql, args=()):
    return [dict(r) for r in _conn().execute(sql, args).fetchall()]

def x(sql, args=()):
    c = _conn()
    cur = c.execute(sql, args); c.commit(); return cur.lastrowid

# ─────────────────────────────── http condiviso
_session = None
_session_lock = threading.Lock()
UA = {"User-Agent": "guardia.py/1.1 (self-hosted)"}

def http():
    """requests.Session unica e riusata (keep-alive) invece di una nuova per chiamata."""
    global _session
    if _session is None:
        with _session_lock:
            if _session is None:
                import requests
                s = requests.Session(); s.headers.update(UA); _session = s
    return _session

# ─────────────────────────────── geocodifica
PAT = re.compile(
    r"\b(via|viale|piazza|piazzale|vicolo|largo|corso|lungotevere|strada|circonvallazione)"
    r"\s+((?:[A-ZÀ-Ù][\w'’\.]*)(?:\s+(?:di|del|della|dei|degli|delle|de|da|san|santa)\s+[\w'’\.]+)?"
    r"(?:\s+[A-ZÀ-Ù][\w'’\.]*){0,3})")

def geocode(place, cfg):
    key = place.lower().strip()
    hit = q("SELECT lat,lon,conf,ts FROM geo WHERE q=?", (key,))
    if hit:
        h = hit[0]
        if h["lat"] is None:
            # 'buco' noto: non riprovo Nominatim finché il TTL non scade
            if time.time() - (h["ts"] or 0) < GEO_HOLE_TTL:
                return None
            # scaduto: proseguo e ritento sotto
        else:
            return h["lat"], h["lon"], h["conf"]
    try:
        r = http().get("https://nominatim.openstreetmap.org/search",
                       params={"q": f"{place}, {cfg['city']}", "format": "jsonv2", "limit": 1,
                               "viewbox": cfg["viewbox"], "bounded": 1},
                       timeout=8).json()
        time.sleep(1.05)   # policy Nominatim: max 1 richiesta/secondo
        if not r:
            # memorizzo il buco (con timestamp) per non martellare Nominatim a ogni frase
            x("INSERT OR REPLACE INTO geo VALUES(?,?,?,?,?)", (key, None, None, 0.0, time.time()))
            return None
        lat, lon = float(r[0]["lat"]), float(r[0]["lon"])
        conf = min(0.95, 0.45 + float(r[0].get("importance", 0.3)))
        x("INSERT OR REPLACE INTO geo VALUES(?,?,?,?,?)", (key, lat, lon, conf, time.time()))
        return lat, lon, conf
    except Exception as e:
        # errore di rete: non lo memorizzo come buco, verrà ritentato
        log.debug("geocode fallito per '%s': %s", place, e)
        return None

def extract_place(text, cfg):
    for m in PAT.finditer(text):
        place = f"{m.group(1)} {m.group(2).strip().rstrip(',.')}"
        g = geocode(place, cfg)
        if g:
            return (place, *g)
    return None

# ─────────────────────────────── radio
class Radio(threading.Thread):
    daemon = True
    name = "radio"
    SR, DEC, OFF, TAU = 2_400_000, 50, 150_000, 300e-6

    def __init__(self, cfg, txq):
        super().__init__()
        import numpy as np
        from rtlsdr import RtlSdr
        self.np, self.cfg, self.txq = np, cfg, txq
        self.sdr = RtlSdr()
        self.sdr.sample_rate = self.SR
        self.sdr.gain = cfg["gain"]
        self.sdr.freq_correction = cfg["ppm"]
        self.udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.alpha = (1 / 48000) / (self.TAU + 1 / 48000)
        self.read_dt = 32768 / self.SR     # durata reale di una read da 32768 campioni (~13,6 ms)
        self.dsd = have("dsd-fme") and have("parec")

    def close(self):
        for obj in (getattr(self, "sdr", None), getattr(self, "udp", None)):
            try:
                obj.close()
            except Exception:
                pass

    def rssi(self, iq):
        return float(10 * self.np.log10(self.np.mean(self.np.abs(iq) ** 2) + 1e-12))

    def demod(self, iq):
        np = self.np
        from scipy.signal import decimate, lfilter
        t = np.arange(len(iq)) / self.SR
        iq = iq * np.exp(-2j * np.pi * self.OFF * t)
        a = np.angle(iq[1:] * np.conj(iq[:-1]))
        a = decimate(a, self.DEC, ftype="fir", zero_phase=True)
        a -= a.mean()
        # de-emphasis: filtro IIR a singolo polo y[n]=α·x[n]+(1-α)·y[n-1], vettorizzato
        y = lfilter([self.alpha], [1.0, -(1.0 - self.alpha)], a)
        y = y / (np.max(np.abs(y)) + 1e-9) * 14000
        return np.clip(y, -32768, 32767).astype("<i2")

    def capture(self, ch):
        self.sdr.center_freq = ch["freq"] + self.OFF
        t0 = time.time()
        while time.time() - t0 < 2 and not STOP.is_set():
            if self.rssi(self.sdr.read_samples(8192)) > self.cfg["squelch"]:
                break
        else:
            return None

        digital = ch["mode"] == "digital" and self.dsd
        mon = raw = None
        if digital:
            raw = os.path.join(AUDIO, f"{int(time.time()*1000)}_{ch['freq']}.raw")
            mon = subprocess.Popen(["parec", "-d", "dsd_out.monitor", "--format=s16le",
                                    "--rate=48000", "--channels=1", "--raw"],
                                   stdout=open(raw, "wb"), stderr=subprocess.DEVNULL)

        chunks, t0, quiet = [], time.time(), 0.0
        while time.time() - t0 < self.cfg["max_seg"] and not STOP.is_set():
            iq = self.sdr.read_samples(32768)
            lvl = self.rssi(iq)
            pcm = self.demod(iq)
            if digital:
                self.udp.sendto(pcm.tobytes(), ("127.0.0.1", 7355))
            chunks.append(pcm.tobytes())
            quiet = quiet + self.read_dt if lvl < self.cfg["squelch"] - 3 else 0.0
            if quiet > 0.6 and time.time() - t0 > self.cfg["min_voice"]:
                break
        if mon:
            time.sleep(0.15); mon.terminate(); mon.wait()

        if time.time() - t0 < self.cfg["min_voice"] or not chunks:
            if raw and os.path.exists(raw):
                os.unlink(raw)
            return None
        if raw:
            return raw

        p = os.path.join(AUDIO, f"{int(time.time()*1000)}_{ch['freq']}.wav")
        w = wave.open(p, "wb"); w.setnchannels(1); w.setsampwidth(2)
        w.setframerate(48000); w.writeframes(b"".join(chunks)); w.close()
        return p

    def run(self):
        fails = 0
        try:
            while not STOP.is_set():
                for ch in self.cfg["freqs"]:
                    if STOP.is_set():
                        break
                    try:
                        path = self.capture(ch)
                        fails = 0
                    except Exception as e:
                        fails += 1
                        log.warning("errore cattura (%d/%d): %s", fails, RADIO_MAX_FAILS, e)
                        if fails >= RADIO_MAX_FAILS:
                            log.error("troppi errori radio consecutivi: fermo la cattura")
                            return
                        STOP.wait(2); continue
                    if path:
                        self.txq.put(x("INSERT INTO tx(ts,freq,unit,mode,wav,conf) VALUES(?,?,?,?,?,0)",
                                       (time.time(), ch["freq"], ch["unit"], ch["mode"], path)))
        finally:
            self.close()

# ─────────────────────────────── demo
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
    # la demo genera righe già complete (testo + posizione): NON passano dal transcriber
    freqs = {c["unit"]: c["freq"] for c in cfg["freqs"]}
    while not STOP.is_set():
        unit, text = random.choice(DEMO)
        g = extract_place(text, cfg)
        x("""INSERT INTO tx(ts,freq,unit,mode,text,conf,place,lat,lon)
             VALUES(?,?,?,?,?,?,?,?,?)""",
          (time.time(), freqs.get(unit, 0), unit, "demo", text,
           random.uniform(-0.6, -0.15), g[0] if g else None,
           g[1] if g else None, g[2] if g else None))
        STOP.wait(random.uniform(4, 9))

# ─────────────────────────────── whisper
def transcriber(cfg, txq):
    from faster_whisper import WhisperModel
    log.info("carico il modello whisper '%s' (il primo avvio scarica i pesi)...", cfg["model"])
    model = WhisperModel(cfg["model"], device="cpu", compute_type="int8")
    log.info("whisper pronto.")
    while not STOP.is_set():
        try:
            tid = txq.get(timeout=1)
        except queue.Empty:
            continue
        row = q("SELECT wav,text FROM tx WHERE id=?", (tid,))
        if not row or not row[0]["wav"]:
            continue
        if row[0].get("text"):   # già trascritta: non la tocco
            continue
        src = row[0]["wav"]; wav = src
        if src.endswith(".raw"):
            if not have("ffmpeg"):
                x("UPDATE tx SET text=NULL WHERE id=?", (tid,)); continue
            wav = src[:-4] + ".wav"
            r = sh(f'ffmpeg -y -loglevel error -f s16le -ar 48000 -ac 1 -i "{src}" -ar 16000 "{wav}"')
            if r.returncode != 0 or not os.path.exists(wav):
                log.warning("ffmpeg fallito su %s: %s", src, r.stderr.strip()[:120])
                x("UPDATE tx SET text=NULL WHERE id=?", (tid,)); continue
            try:
                os.unlink(src)
            except OSError:
                pass
            # d'ora in poi la riga punta al wav riproducibile dal browser
            x("UPDATE tx SET wav=? WHERE id=?", (wav, tid))
        try:
            segs, _ = model.transcribe(wav, language="it", vad_filter=True, beam_size=1,
                                       initial_prompt="Centrale, volante, intervenite, via, civico, targa.")
            text = " ".join(s.text.strip() for s in segs).strip()
            if len(text) < 10:
                x("UPDATE tx SET text=NULL WHERE id=?", (tid,)); continue
            g = extract_place(text, cfg)
            x("UPDATE tx SET text=?,place=?,lat=?,lon=? WHERE id=?",
              (text, g[0] if g else None, g[1] if g else None, g[2] if g else None, tid))
        except Exception as e:
            log.warning("trascrizione fallita: %s", e); x("UPDATE tx SET text=NULL WHERE id=?", (tid,))

# ─────────────────────────────── manutenzione (retention disco + DB)
def janitor(cfg):
    while not STOP.is_set():
        cutoff = time.time() - cfg["retention_hours"] * 3600
        try:
            for r in q("SELECT wav FROM tx WHERE ts<? AND wav IS NOT NULL", (cutoff,)):
                try:
                    os.unlink(r["wav"])
                except OSError:
                    pass
            x("DELETE FROM tx WHERE ts<?", (cutoff,))
            x("DELETE FROM geo WHERE conf<=0 AND ts<?", (cutoff,))   # scadono solo i 'buchi'
            for f in os.listdir(AUDIO):                               # file audio orfani
                p = os.path.join(AUDIO, f)
                try:
                    if os.path.isfile(p) and os.path.getmtime(p) < cutoff:
                        os.unlink(p)
                except OSError:
                    pass
        except Exception as e:
            log.warning("janitor: %s", e)
        STOP.wait(600)

# ─────────────────────────────── adsb
def adsb_thread(cfg):
    url = "https://api.adsb.lol/v2/lat/{}/lon/{}/dist/{}".format(
        cfg["lat"], cfg["lon"], cfg["radius_km"])
    while not STOP.is_set():
        try:
            resp = http().get(url, timeout=10)
            resp.raise_for_status()
            for a in resp.json().get("ac", []):
                h = (a.get("hex") or "").lower()
                alt, spd = a.get("alt_baro"), a.get("gs") or 0
                if not h.startswith("33") or not isinstance(alt, int):
                    continue
                if alt > 4000 or spd > 140:
                    continue
                x("INSERT OR REPLACE INTO air VALUES(?,?,?,?,?,?,?)",
                  (h, (a.get("flight") or "").strip(), a.get("lat"), a.get("lon"),
                   alt, spd, time.time()))
        except Exception as e:
            log.debug("adsb: %s", e)
        STOP.wait(6)

# ─────────────────────────────── api
def build_app(cfg):
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
    app = FastAPI()

    @app.middleware("http")
    async def security_headers(request, call_next):
        resp = await call_next(request)
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "no-referrer"
        return resp

    def auth(req):
        tok = req.query_params.get("t") or req.cookies.get("t") or ""
        if cfg["token"] and hmac.compare_digest(tok, cfg["token"]):
            return
        raise HTTPException(401, "token mancante")

    def snap():
        now = time.time(); units, seen = [], set()
        for u in q("""SELECT unit,freq,text,place,lat,lon,ts,conf FROM tx
                      WHERE lat IS NOT NULL AND ts>? ORDER BY ts DESC""", (now - 300,)):
            if u["unit"] in seen:
                continue
            seen.add(u["unit"]); u["age"] = round(now - u["ts"], 1); units.append(u)
        return {"now": now, "units": units,
                "events": q("""SELECT id,ts,unit,freq,text,place,lat,lon,conf,wav FROM tx
                               WHERE text!='' ORDER BY ts DESC LIMIT 80"""),
                "air": q("SELECT * FROM air WHERE seen>?", (now - 45,))}

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request):
        if request.query_params.get("t"):
            r = RedirectResponse("/", status_code=302)
            r.set_cookie("t", request.query_params["t"], max_age=86400 * 365,
                         httponly=True, samesite="lax")
            return r
        return HTML.replace("__GUARDIA_CFG__", json.dumps(
            {"lon": cfg["lon"], "lat": cfg["lat"], "zoom": 15}))

    @app.get("/api/state")
    def state(request: Request):
        auth(request); return snap()

    @app.get("/api/audio/{tid}")
    def audio(tid: int, request: Request):
        auth(request)
        r = q("SELECT wav FROM tx WHERE id=?", (tid,))
        if not r or not r[0]["wav"] or not os.path.exists(r[0]["wav"]):
            raise HTTPException(404)
        return FileResponse(r[0]["wav"])

    @app.get("/health")
    def health():
        return {"ok": True}

    return app

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
.maplibregl-ctrl-group{background:#121a24!important}
.maplibregl-ctrl button{filter:invert(1) hue-rotate(180deg)}
</style></head><body>
<header><div><h1>SALA OPERATIVA 3D</h1><div class="sub" id="sub">connessione...</div></div>
<div class="live">LIVE</div></header>
<div id="wrap"><div id="m"></div>
<div id="leg"><b>UNITÀ</b>
 <span><i class="dot" style="background:#2563eb"></i>CC</span>
 <span><i class="dot" style="background:#dc2626"></i>PS</span>
 <span><i class="dot" style="background:#16a34a"></i>PL</span>
 <span><i class="dot" style="background:#d97706"></i>VVF</span>
 <span><i class="dot" style="background:#d97706;border-radius:50%"></i>elicottero</span>
</div></div>
<div id="feed"></div>
<script>
const CFG=__GUARDIA_CFG__;
const COL={CC:0x2563eb,PS:0xdc2626,PL:0x16a34a,VVF:0xd97706};
const COLW={CC:'#2563eb',PS:'#dc2626',PL:'#16a34a',VVF:'#d97706'};
const SCAR=5, SHELI=5;

// base scura CartoDB: keyless e affidabile, garantisce che la mappa funzioni sempre
const map=new maplibregl.Map({container:'m',center:[CFG.lon,CFG.lat],zoom:CFG.zoom,
 pitch:58,bearing:-18,maxPitch:82,antialias:true,attributionControl:false,
 style:{version:8,sources:{b:{type:'raster',tileSize:256,
   tiles:['https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png','https://b.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png']}},
   layers:[{id:'b',type:'raster',source:'b'}]}});
map.addControl(new maplibregl.NavigationControl({visualizePitch:true}),'top-right');
map.on('error',()=>{});   // ignora errori di sorgenti opzionali (es. edifici vettoriali)

// ───────── modelli 3D con Three.js (custom layer condiviso col contesto di MapLibre)
const V={cars:new Map(),helis:new Map(),scene:null,renderer:null,camera:null};
let useThree = (typeof THREE!=='undefined');

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
 [-1.4,1.4].forEach(sx=>{const s=new THREE.Mesh(new THREE.BoxGeometry(.2,.2,5),sm); s.position.set(sx,.2,0); g.add(s);});
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
   let a=arg; if(a&&!Array.isArray(a)) a=(a.defaultProjectionData&&a.defaultProjectionData.mainMatrix)||a;
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
   const dx=v.tlng-v.lng,dy=v.tlat-v.lat;
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
   const v=V.helis.get(a.hex)||addHeli(a); v.tlng=a.lon; v.tlat=a.lat; v.alt=Math.min(a.alt||120,300);});
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
 // modelli 3D dei veicoli
 if(useThree){ try{ map.addLayer(layer3d); }catch(e){ useThree=false; } }
});

const seen=new Set();
async function tick(){try{
 const d=await (await fetch('/api/state')).json();
 (useThree?applyThree:applyDOM)(d);
 document.getElementById('sub').textContent=d.units.length+' unità · '+d.air.length+' aeromobili'+(useThree?' · 3D':' · 2D');
 const f=document.getElementById('feed');
 d.events.forEach(e=>{if(seen.has(e.id))return;seen.add(e.id);
  const r=document.createElement('div');r.className='row';
  r.innerHTML='<span class="u" style="color:'+(COLW[e.unit]||'#6ea8ff')+'">'+e.unit+'</span><div><span class="t">'+
   new Date(e.ts*1000).toLocaleTimeString('it-IT')+' · '+(e.freq/1e6).toFixed(3)+'</span><div>'+
   (e.text||'')+'</div>'+(e.place?'<div class="p">▸ '+e.place+'</div>':'')+'</div>';
  r.onclick=()=>{if(e.lat)map.flyTo({center:[e.lon,e.lat],zoom:16,pitch:62,essential:true});
   if(e.wav)new Audio('/api/audio/'+e.id).play().catch(()=>{});};
  f.prepend(r); while(f.children.length>120)f.removeChild(f.lastChild);});
}catch(_){document.getElementById('sub').textContent='offline';}}
setInterval(tick,3000);tick();
</script></body></html>"""

# ─────────────────────────────── main
def main():
    ap = argparse.ArgumentParser()
    for f in ["--demo", "--check", "--install", "--service"]:
        ap.add_argument(f, action="store_true")
    ap.add_argument("--port", type=int); ap.add_argument("--token")
    ap.add_argument("--ppm", type=int); ap.add_argument("--gain", type=int)
    ap.add_argument("--squelch", type=float); ap.add_argument("--model")
    ap.add_argument("--lat", type=float); ap.add_argument("--lon", type=float)
    ap.add_argument("--freqs")
    a = ap.parse_args()

    if a.install:
        return do_install()
    if a.check:
        return do_check()
    if a.service:
        return do_service()

    ensure_env()
    cfg = load_cfg()
    for k in ["port", "token", "ppm", "gain", "squelch", "model", "lat", "lon"]:
        if getattr(a, k) is not None:
            cfg[k] = getattr(a, k)
    if a.freqs:
        try:
            parsed = []
            for p in a.freqs.split(","):
                freq, unit, mode = p.split(":")
                parsed.append({"freq": int(freq), "unit": unit, "mode": mode})
            cfg["freqs"] = parsed
        except ValueError:
            print("!! --freqs malformato. Usa FREQ:UNITA:modo,FREQ:UNITA:modo"
                  "  (es. 151175000:CC:digital,160900000:PL:analog)")
            sys.exit(1)
    if not cfg["token"]:
        cfg["token"] = os.urandom(6).hex()
    validate_cfg(cfg)
    save_cfg(cfg)

    os.makedirs(AUDIO, exist_ok=True)
    db_init()
    txq = queue.Queue()

    # spegnimento pulito su Ctrl+C / kill: i thread (daemon) escono al prossimo STOP check
    def _shutdown(*_):
        if not STOP.is_set():
            log.info("arresto richiesto, chiudo...")
            STOP.set()
    try:
        signal.signal(signal.SIGINT, _shutdown)
        signal.signal(signal.SIGTERM, _shutdown)
    except (ValueError, OSError):
        pass   # non siamo nel thread principale: lascio fare a uvicorn

    radio = None
    demo = a.demo
    if not demo:
        try:
            from rtlsdr import RtlSdr
            RtlSdr().close()
        except Exception as e:
            print("!! dongle non disponibile (" + str(e)[:70] + ") → DEMO")
            if IS_WIN:
                print("!! su Windows serve Zadig/WinUSB sul dongle")
            demo = True

    if demo:
        threading.Thread(target=demo_thread, args=(cfg, txq), name="demo", daemon=True).start()
    else:
        try:
            radio = Radio(cfg, txq)
            radio.start()   # Radio è già un Thread: .start() ne esegue run()
        except Exception as e:
            print("!! radio non avviabile (" + str(e)[:70] + ") → DEMO")
            demo = True; radio = None
            threading.Thread(target=demo_thread, args=(cfg, txq), name="demo", daemon=True).start()
    threading.Thread(target=transcriber, args=(cfg, txq), name="whisper", daemon=True).start()
    threading.Thread(target=adsb_thread, args=(cfg,), name="adsb", daemon=True).start()
    threading.Thread(target=janitor, args=(cfg,), name="janitor", daemon=True).start()

    ip = local_ip()
    print(f"""
============================================
  GUARDIA {'[DEMO]' if demo else '[RADIO]'}
  Telefono:  http://{ip}:{cfg['port']}/?t={cfg['token']}
  Locale:    http://127.0.0.1:{cfg['port']}/?t={cfg['token']}
  Canali:    {', '.join(f"{c['freq']/1e6:.3f}/{c['unit']}/{c['mode']}" for c in cfg['freqs'])}
  Ctrl+C per fermare
============================================
""", flush=True)

    import uvicorn
    try:
        uvicorn.run(build_app(cfg), host="0.0.0.0", port=cfg["port"], log_level="warning")
    except KeyboardInterrupt:
        pass
    finally:
        STOP.set()
        if radio:
            radio.close()
        time.sleep(0.3)
        print("\nchiuso.")

if __name__ == "__main__":
    main()
