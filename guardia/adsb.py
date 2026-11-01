"""
Aeromobili nelle vicinanze (api.adsb.lol, pubblica e senza chiave).

Si tengono solo gli elicotteri plausibilmente in servizio: immatricolazione italiana,
bassi e lenti. Il resto e' traffico di linea e sulla mappa sarebbe solo rumore.
"""
import logging
import time

from . import db, net
from .runtime import STOP

log = logging.getLogger("guardia.adsb")

URL = "https://api.adsb.lol/v2/lat/%s/lon/%s/dist/%s"
ALT_MAX, VEL_MAX = 4000, 140
PAUSA_MAX = 120.0


def interessante(a):
    h = (a.get("hex") or "").lower()
    alt = a.get("alt_baro")
    vel = a.get("gs") or 0
    if not h.startswith("33") or not isinstance(alt, int):   # 33xxxx = Italia; 'ground' e' testo
        return None
    if alt > ALT_MAX or vel > VEL_MAX:
        return None
    if a.get("lat") is None or a.get("lon") is None:
        return None
    return (h, (a.get("flight") or "").strip(), a.get("lat"), a.get("lon"), alt, vel, time.time())


def worker(cfg):
    url = URL % (cfg["lat"], cfg["lon"], int(cfg["radius_km"]))
    pausa = float(cfg["adsb_interval"])
    while not STOP.is_set():
        try:
            r = net.session().get(url, timeout=10)
            if r.status_code == 429:
                pausa = min(PAUSA_MAX, pausa * 2)
                log.debug("rate limit: rallento a %.0fs", pausa)
            else:
                r.raise_for_status()
                righe = [x for x in (interessante(a) for a in r.json().get("ac", [])) if x]
                if righe:
                    db.air_upsert(righe)
                pausa = float(cfg["adsb_interval"])
        except Exception as e:
            pausa = min(PAUSA_MAX, max(pausa, 5.0) * 1.5)
            log.debug("%s (riprovo tra %.0fs)", e, pausa)
        STOP.wait(pausa)
