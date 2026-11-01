"""Traffico finto: serve a provare l'interfaccia senza dongle e senza antenna."""
import logging
import random
import time

from . import db, geo
from .bus import BUS
from .runtime import STOP

log = logging.getLogger("guardia.demo")

BATTUTE = [
    ("CC", "Centrale a 21, andate in via Nomentana civico 88 per incidente stradale."),
    ("PS", "Volante 7, intervento in piazza Vittorio Emanuele II per schiamazzi."),
    ("PL", "Pronto intervento, via del Corso altezza civico 12, auto in sosta vietata."),
    ("CC", "Ricevuto, in avvicinamento. Traffico intenso su via Salaria."),
    ("PS", "Richiedo pattuglia di supporto in via Cavour, soggetto molesto."),
    ("VVF", "Squadra 3, intervento in lungotevere Marzio per principio di incendio."),
    ("CC", "Centrale, soggetto in fuga a piedi verso viale Trastevere."),
    ("PS", "Situazione rientrata in piazza del Popolo, nessun ferito."),
    ("PL", "Segnalazione su via Nazionale, veicolo senza revisione."),
    ("CC", "Rientro in caserma, via di Macchia Saponara."),
    ("VVF", "Autoscala in arrivo, via Tiburtina, persona bloccata in ascensore."),
    ("PS", "Controllo documenti in piazza Bologna, tutto regolare."),
]


def worker(cfg):
    """Righe gia' complete (testo e posizione): non passano dal trascrittore."""
    freqs = {c["unit"]: c["freq"] for c in cfg["freqs"]}
    pos = {}
    while not STOP.is_set():
        unit, testo = random.choice(BATTUTE)
        g = geo.localizza(testo, cfg)
        if g:
            posto, lat, lon = g[0], g[1], g[2]
        else:
            # senza rete il geocoder non risponde: le unita' si muovono comunque sulla mappa
            posto = (geo.nomi(testo) or [None])[0]
            lat, lon = pos.get(unit, (cfg["lat"], cfg["lon"]))
            lat += random.uniform(-0.0025, 0.0025)
            lon += random.uniform(-0.0035, 0.0035)
        pos[unit] = (lat, lon)
        tid = db.add_demo(time.time(), freqs.get(unit, 0), unit, testo,
                          round(random.uniform(0.7, 0.95), 2), posto, lat, lon,
                          round(random.uniform(2, 7), 1), geo.allarme(testo, cfg))
        riga = db.event(tid)
        if riga:
            BUS.publish("event", riga, ricorda=False)
        STOP.wait(random.uniform(4, 9))
