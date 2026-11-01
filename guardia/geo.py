"""
Riconoscimento dei toponimi nel parlato e geocodifica con Nominatim.

Tre accortezze che fanno la differenza su un servizio pubblico gratuito: cache su
database, cache anche dei 'buchi' (indirizzi che non esistono, altrimenti si ritenta a
ogni frase) e un rate-limit globale, non per thread, perche' la policy e' per client.
"""
import logging
import re
import threading
import time

from . import db, net
from .runtime import STOP

log = logging.getLogger("guardia.geo")

TTL_BUCO = 6 * 3600          # un indirizzo non trovato viene ritentato dopo 6 ore
MIN_INTERVALLO = 1.1         # policy Nominatim: al massimo 1 richiesta al secondo
URL = "https://nominatim.openstreetmap.org/search"

# "via Nomentana", "piazza Vittorio Emanuele II", "lungotevere Marzio", "via di Macchia Saponara"
PAT = re.compile(
    r"\b(?i:(via|viale|piazza|piazzale|vicolo|largo|corso|lungotevere|strada|circonvallazione))"
    r"\s+((?:(?:di|del|della|dei|degli|delle|de|da)\s+)?"
    r"[A-ZÀ-Ü][\w'’.-]+"
    r"(?:\s+(?:di|del|della|dei|degli|delle|de|da|san|santa|sant'|santo)\s*[A-ZÀ-Ü][\w'’.-]+)?"
    r"(?:\s+(?:[A-ZÀ-Ü][\w'’.-]+|[IVXLC]{1,5}\b)){0,3})")

_lock = threading.Lock()
_ultima = [0.0]
_pausa = [0.0]               # fino a quando sospendere dopo un 429/403


def nomi(testo):
    """Tutti i toponimi riconosciuti nel testo, normalizzati."""
    out = []
    for m in PAT.finditer(testo or ""):
        nome = "%s %s" % (m.group(1).lower(), m.group(2).strip().rstrip(" ,.;:"))
        nome = re.sub(r"\s+", " ", nome)
        if nome not in out:
            out.append(nome)
    return out


def geocode(posto, cfg):
    """(lat, lon, conf) oppure None. Non solleva mai: un errore di rete non ferma nulla."""
    if not cfg.get("geocode", True):
        return None
    chiave = posto.lower().strip()
    hit = db.uno("SELECT lat,lon,conf,ts FROM geo WHERE q=?", (chiave,))
    if hit:
        if hit["lat"] is not None:
            return hit["lat"], hit["lon"], hit["conf"]
        if time.time() - (hit["ts"] or 0) < TTL_BUCO:
            return None                      # 'buco' noto e ancora valido
    try:
        with _lock:
            if time.time() < _pausa[0]:
                return None                  # il servizio ci ha chiesto di rallentare
            attesa = MIN_INTERVALLO - (time.time() - _ultima[0])
            if attesa > 0 and STOP.wait(attesa):
                return None
            _ultima[0] = time.time()
            r = net.session().get(URL, timeout=8, params={
                "q": "%s, %s" % (posto, cfg["city"]), "format": "jsonv2", "limit": 1,
                "viewbox": cfg["viewbox"], "bounded": 1})
        if r.status_code in (429, 403):
            _pausa[0] = time.time() + 300
            log.warning("Nominatim ha risposto %s: sospendo la geocodifica per 5 minuti",
                        r.status_code)
            return None
        r.raise_for_status()
        js = r.json()
        if not js:
            db.execute("INSERT OR REPLACE INTO geo VALUES(?,?,?,?,?)",
                       (chiave, None, None, 0.0, time.time()))
            return None
        lat, lon = float(js[0]["lat"]), float(js[0]["lon"])
        conf = min(0.95, 0.45 + float(js[0].get("importance", 0.3) or 0.3))
        db.execute("INSERT OR REPLACE INTO geo VALUES(?,?,?,?,?)",
                   (chiave, lat, lon, conf, time.time()))
        return lat, lon, conf
    except Exception as e:
        log.debug("geocode fallito per '%s': %s", posto, e)
        return None          # errore di rete: non lo memorizzo come buco, si ritentera'


def localizza(testo, cfg):
    """Primo toponimo del testo che si riesce a collocare: (nome, lat, lon, conf) o None."""
    for nome in nomi(testo):
        g = geocode(nome, cfg)
        if g:
            return (nome, g[0], g[1], g[2])
    return None


def allarme(testo, cfg):
    """Prima parola d'allarme trovata nel testo, o None."""
    if not testo:
        return None
    basso = testo.lower()
    for parola in cfg.get("alerts") or []:
        if parola in basso:
            return parola
    return None
