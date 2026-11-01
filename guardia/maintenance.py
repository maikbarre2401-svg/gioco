"""
Pulizia periodica: il disco non e' infinito, specie su una scheda SD.

Due limiti indipendenti: l'eta' (retention_hours) e lo spazio occupato dall'audio
(max_audio_mb). Il secondo e' quello che salva un Raspberry da riempirsi in una notte
di traffico intenso.
"""
import logging
import os
import time

from . import config, db
from .runtime import STOP

log = logging.getLogger("guardia.maintenance")

PERIODO = 600


def file_audio():
    """[(percorso, dimensione, mtime)] ordinati dal piu' vecchio."""
    out = []
    try:
        with os.scandir(config.PATHS.audio) as it:
            for e in it:
                try:
                    if e.is_file():
                        st = e.stat()
                        out.append((e.path, st.st_size, st.st_mtime))
                except OSError:
                    pass
    except OSError:
        return []
    out.sort(key=lambda r: r[2])
    return out


def spazio_audio():
    return sum(r[1] for r in file_audio())


def giro(cfg):
    """Un giro di pulizia. Ritorna (righe eliminate, file eliminati, byte liberati)."""
    limite = time.time() - float(cfg["retention_hours"]) * 3600
    file_eliminati = byte = 0

    for wav in db.scadute(limite):              # audio delle righe scadute
        try:
            byte += os.path.getsize(wav)
            os.unlink(wav)
            file_eliminati += 1
        except OSError:
            pass
    righe = db.elimina_prima_di(limite)
    db.pulisci_cache(limite)

    resti = []
    for percorso, dim, mtime in file_audio():   # file orfani
        if mtime < limite:
            try:
                os.unlink(percorso)
                file_eliminati += 1
                byte += dim
            except OSError:
                pass
        else:
            resti.append((percorso, dim))

    # tetto di spazio: si buttano i piu' vecchi finche' si rientra
    tetto = float(cfg["max_audio_mb"]) * 1024 * 1024
    totale = sum(d for _, d in resti)
    if totale > tetto:
        log.warning("audio a %.0f MB oltre il tetto di %.0f MB: elimino i piu' vecchi",
                    totale / 1e6, tetto / 1e6)
        for percorso, dim in resti:
            if totale <= tetto:
                break
            try:
                os.unlink(percorso)
                db.modify("UPDATE tx SET wav=NULL WHERE wav=?", (percorso,))
                totale -= dim
                file_eliminati += 1
                byte += dim
            except OSError:
                pass
    if righe or file_eliminati:
        log.info("pulizia: %d righe, %d file, %.1f MB liberati", righe, file_eliminati, byte / 1e6)
    return righe, file_eliminati, byte


def worker(cfg):
    while not STOP.is_set():
        try:
            giro(cfg)
        except Exception as e:
            log.warning("pulizia fallita: %s", e)
        STOP.wait(PERIODO)
