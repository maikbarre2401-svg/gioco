"""Percorsi, valori di default, caricamento/validazione/salvataggio della configurazione."""
import json
import logging
import os

log = logging.getLogger("guardia.config")

PKG = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(PKG)
UI = os.path.join(PKG, "ui")

FREQ_MIN, FREQ_MAX = 24_000_000, 1_766_000_000      # RTL-SDR R820T
VALID_MODES = {"analog", "digital"}
SCHEMA_VERSION = 3


class Paths:
    """Dove vivono i dati. Istanziabile altrove per i test o per --config."""

    def __init__(self, root=ROOT):
        self.set_root(root)

    def set_root(self, root):
        self.root = os.path.abspath(root)
        self.db = os.path.join(self.root, "guardia.db")
        self.audio = os.path.join(self.root, "audio")
        self.cfg = os.path.join(self.root, "guardia.json")
        self.venv = os.path.join(self.root, ".venv")
        return self


PATHS = Paths()

DEFAULTS = {
    # rete
    "host": "0.0.0.0", "port": 8080, "token": "",
    # radio
    "ppm": 0, "gain": 28, "sample_rate": 2_400_000, "deviation": 2500.0, "channel_bw": 7000.0,
    # squelch: 'auto' segue il rumore di fondo del singolo canale, 'manual' usa 'squelch' in dBFS
    "squelch_mode": "auto", "squelch": -30.0, "squelch_margin": 7.0, "squelch_hysteresis": 3.0,
    # segmentazione
    "hang": 0.7, "preroll": 0.3, "min_voice": 0.8, "max_seg": 12.0, "dwell": 2.5,
    # trascrizione
    "stt": True, "model": "small", "stt_lang": "it",
    # parole che accendono un avviso nel feed (minuscole, senza accenti superflui)
    "alerts": ["incendio", "ferito", "feriti", "rapina", "soccorso", "inseguimento",
               "esplosione", "coltello", "arma", "codice rosso"],
    # manutenzione
    "retention_hours": 48, "max_audio_mb": 2048,
    # mappa e servizi esterni
    "lat": 41.9028, "lon": 12.4964, "radius_km": 25, "city": "Roma",
    "viewbox": "12.30,41.70,12.75,42.10", "geocode": True,
    "adsb": True, "adsb_interval": 8.0,
    # 'vector' = stile scuro su OpenFreeMap (senza chiavi), 'osm', oppure un template
    # raster tuo, es. "https://tile.tuoserver.org/{z}/{x}/{y}.png"
    "basemap": "vector",
    "freqs": [{"freq": 151175000, "unit": "CC", "mode": "digital"},
              {"freq": 152025000, "unit": "PS", "mode": "digital"},
              {"freq": 160900000, "unit": "PL", "mode": "analog"},
              {"freq": 161300000, "unit": "VVF", "mode": "analog"}],
}

# chiave: (minimo, massimo). Un solo posto da aggiornare invece di una riga di codice
# di controllo per ciascun valore.
LIMITI = {
    "port": (1, 65535), "ppm": (-200, 200), "gain": (0, 50),
    "sample_rate": (1_000_000, 2_880_000), "deviation": (500, 75_000),
    "channel_bw": (2_000, 100_000), "squelch": (-90, 0), "squelch_margin": (1, 40),
    "squelch_hysteresis": (0, 20), "hang": (0.1, 10), "preroll": (0, 3),
    "min_voice": (0.1, 30), "max_seg": (1, 300), "dwell": (0.5, 60),
    "retention_hours": (1, 24 * 365), "max_audio_mb": (16, 1024 * 1024),
    "adsb_interval": (2, 3600), "lat": (-90, 90), "lon": (-180, 180),
    "radius_km": (1, 250),
}
INTERI = {"port", "ppm", "gain", "sample_rate", "retention_hours", "max_audio_mb", "radius_km"}


def load(path=None):
    """Default + file su disco. Un file illeggibile non impedisce l'avvio."""
    path = path or PATHS.cfg
    cfg = json.loads(json.dumps(DEFAULTS))
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                disco = json.load(f)
            if not isinstance(disco, dict):
                raise ValueError("il file non contiene un oggetto JSON")
            ignote = set(disco) - set(DEFAULTS)
            if ignote:
                log.warning("chiavi sconosciute in %s: %s", os.path.basename(path),
                            ", ".join(sorted(ignote)))
            cfg.update(disco)
        except Exception as e:
            log.warning("config illeggibile (%s), uso i valori di default", e)
    return cfg


def from_env(cfg, env=None):
    """Sovrascrive con le variabili GUARDIA_<CHIAVE> (comode in docker/systemd)."""
    env = os.environ if env is None else env
    for k in DEFAULTS:
        v = env.get("GUARDIA_" + k.upper())
        if v is None:
            continue
        try:
            if isinstance(DEFAULTS[k], bool):
                cfg[k] = v.strip().lower() in ("1", "true", "si", "sì", "yes", "on")
            elif isinstance(DEFAULTS[k], (int, float)):
                cfg[k] = type(DEFAULTS[k])(float(v))
            elif isinstance(DEFAULTS[k], list):
                cfg[k] = json.loads(v)
            else:
                cfg[k] = v
        except Exception as e:
            log.warning("GUARDIA_%s=%r ignorata (%s)", k.upper(), v, e)
    return cfg


def save(cfg, path=None):
    """Scrittura atomica + permessi ristretti: il file contiene il token di accesso."""
    path = path or PATHS.cfg
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False, sort_keys=True)
    os.replace(tmp, path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return path


def _numero(cfg, chiave):
    lo, hi = LIMITI[chiave]
    default = DEFAULTS[chiave]
    try:
        v = float(cfg.get(chiave, default))
        if v != v:                                  # NaN
            raise ValueError("NaN")
    except (TypeError, ValueError):
        log.warning("%s=%r non e' un numero → %s", chiave, cfg.get(chiave), default)
        v = float(default)
    if not (lo <= v <= hi):
        nuovo = min(max(v, lo), hi)
        log.warning("%s=%g fuori dai limiti [%g, %g] → %g", chiave, v, lo, hi, nuovo)
        v = nuovo
    cfg[chiave] = int(round(v)) if chiave in INTERI else v


def canali(freqs):
    """Normalizza la lista dei canali, scartando quelli impossibili. Mai vuota."""
    buoni, visti = [], set()
    for ch in freqs or []:
        try:
            f = int(ch["freq"])
            modo = str(ch.get("mode", "analog")).lower()
            unita = str(ch.get("unit", "??")).strip()[:12] or "??"
            if not (FREQ_MIN <= f <= FREQ_MAX):
                log.warning("frequenza %s fuori banda, scartata", f)
                continue
            if modo not in VALID_MODES:
                log.warning("modo '%s' sconosciuto su %s → analog", modo, f)
                modo = "analog"
            if (f, unita) in visti:
                log.warning("canale duplicato %s/%s ignorato", f, unita)
                continue
            visti.add((f, unita))
            buoni.append({"freq": f, "unit": unita, "mode": modo})
        except (KeyError, ValueError, TypeError):
            log.warning("canale malformato ignorato: %r", ch)
    if not buoni:
        log.error("nessuna frequenza valida: uso i default")
        buoni = json.loads(json.dumps(DEFAULTS["freqs"]))
    return buoni


def validate(cfg):
    """
    Corregge e segnala i valori impossibili. Ritorna lo stesso oggetto, modificato.
    Accetta anche dizionari parziali: le chiavi mancanti prendono il default.
    """
    for chiave, default in DEFAULTS.items():
        cfg.setdefault(chiave, json.loads(json.dumps(default)))
    lo, hi = LIMITI["port"]
    try:
        porta = int(cfg["port"])
    except (TypeError, ValueError):
        porta = -1
    if not (lo <= porta <= hi):
        # su una porta sbagliata limitare al massimo non ha senso: meglio quella di casa
        log.warning("porta %r non valida → %s", cfg["port"], DEFAULTS["port"])
        cfg["port"] = DEFAULTS["port"]
    for chiave in LIMITI:
        _numero(cfg, chiave)
    cfg["sample_rate"] = int(round(cfg["sample_rate"] / 48000.0)) * 48000   # multiplo dell'audio
    if cfg["squelch_mode"] not in ("auto", "manual"):
        log.warning("squelch_mode=%r sconosciuto → auto", cfg["squelch_mode"])
        cfg["squelch_mode"] = "auto"
    if cfg["max_seg"] <= cfg["min_voice"]:
        log.warning("max_seg <= min_voice: porto max_seg a %g", cfg["min_voice"] * 4)
        cfg["max_seg"] = cfg["min_voice"] * 4
    if not isinstance(cfg.get("basemap"), str) or not cfg["basemap"].strip():
        log.warning("basemap=%r non valido → vector", cfg.get("basemap"))
        cfg["basemap"] = "vector"
    for chiave in ("stt", "geocode", "adsb"):
        cfg[chiave] = bool(cfg.get(chiave, DEFAULTS[chiave]))
    for chiave in ("host", "city", "viewbox", "model", "stt_lang", "token"):
        cfg[chiave] = str(cfg.get(chiave, DEFAULTS[chiave]))
    alerts = cfg.get("alerts") or []
    if not isinstance(alerts, list):
        log.warning("alerts non e' una lista → nessun avviso")
        alerts = []
    cfg["alerts"] = sorted({str(a).strip().lower() for a in alerts if str(a).strip()})
    cfg["freqs"] = canali(cfg.get("freqs"))
    return cfg


def parse_freqs(spec):
    """'FREQ:UNITA:modo,...' → lista di canali. Il modo e' opzionale (default analog)."""
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
