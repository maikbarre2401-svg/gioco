"""
Trascrizione vocale (faster-whisper) e arricchimento della riga: toponimo e parola d'allarme.

Le tratte nascono 'pending' nel database e il risultato e' uno di questi stati:
    done    testo riconosciuto
    empty   nessun parlato intelligibile (resta nel database, fuori dal feed)
    nostt   whisper non disponibile: resta l'audio, ascoltabile
    error   file illeggibile o conversione fallita
Cosi' una tratta non si perde se il programma viene chiuso a meta' lavoro.
"""
import logging
import math
import os
import queue
import shutil
import subprocess
import sys

from . import db, geo
from .bus import BUS
from .runtime import STATO, STOP

log = logging.getLogger("guardia.stt")

MIN_CARATTERI = 10           # sotto, e' rumore interpretato come sillabe
SUGGERIMENTO = "Centrale, volante, intervenite, via, civico, targa."


def to_wav16k(src):
    """Converte il raw del sink dsd-fme in WAV 16 kHz. Ritorna il percorso o None."""
    if not shutil.which("ffmpeg"):
        log.warning("ffmpeg assente: non posso convertire %s", os.path.basename(src))
        return None
    try:
        if os.path.getsize(src) < 48000 * 2 * 0.3:
            return None
    except OSError:
        return None
    dst = src[:-4] + ".wav"
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "s16le", "-ar", "48000",
                        "-ac", "1", "-i", src, "-ar", "16000", dst],
                       capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(dst):
        log.warning("ffmpeg fallito su %s: %s", os.path.basename(src), r.stderr.strip()[:120])
        return None
    try:
        os.unlink(src)
    except OSError:
        pass
    return dst


def carica_modello(cfg):
    if not cfg.get("stt", True):
        log.info("trascrizione disattivata: tengo solo l'audio")
        return None
    try:
        from faster_whisper import WhisperModel
    except Exception as e:
        log.warning("faster-whisper non disponibile (%s): tengo solo l'audio", str(e)[:90])
        log.warning("  installalo con: %s -m pip install faster-whisper", sys.executable)
        return None
    try:
        log.info("carico whisper '%s' (il primo avvio scarica i pesi)...", cfg["model"])
        m = WhisperModel(cfg["model"], device="cpu", compute_type="int8")
        STATO.stt["modello"] = cfg["model"]
        log.info("whisper pronto")
        return m
    except Exception as e:
        log.error("modello '%s' non caricabile: %s", cfg["model"], str(e)[:140])
        log.error("  prova un modello piu' piccolo:  --model tiny")
        return None


def trascrivi(model, wav, cfg):
    """(testo, confidenza). Non solleva: un errore marca la riga e si tira avanti."""
    segs, _ = model.transcribe(wav, language=cfg.get("stt_lang") or "it", vad_filter=True,
                               beam_size=1, initial_prompt=SUGGERIMENTO)
    segs = list(segs)
    testo = " ".join(s.text.strip() for s in segs).strip()
    lp = [s.avg_logprob for s in segs if s.avg_logprob is not None]
    conf = round(math.exp(sum(lp) / len(lp)), 3) if lp else 0.0
    return testo, conf


def worker(cfg, txq):
    model = carica_modello(cfg)
    for tid in db.pending_ids():            # tratte rimaste in sospeso da un'esecuzione precedente
        txq.put(tid)
    while not STOP.is_set():
        try:
            tid = txq.get(timeout=1)
        except queue.Empty:
            continue
        STATO.stt["coda"] = txq.qsize()
        try:
            lavora(model, cfg, tid)
        except Exception as e:              # nessun errore deve uccidere il thread
            log.warning("tratta %s non elaborata: %s", tid, e)
            db.set_state(tid, "error")
            STATO.stt["fallite"] += 1


def lavora(model, cfg, tid):
    riga = db.capture(tid)
    if not riga or riga["state"] != "pending":
        return
    src = riga["wav"]
    if not src or not os.path.exists(src):
        db.set_state(tid, "error")
        return
    if src.endswith(".raw"):
        dst = to_wav16k(src)
        if not dst:
            db.set_state(tid, "error")
            return
        src = dst
        db.set_wav(tid, src)                # ora e' riproducibile dal browser
    if model is None:
        db.set_state(tid, "nostt")
        pubblica(tid)
        return
    testo, conf = trascrivi(model, src, cfg)
    if len(testo) < MIN_CARATTERI:
        db.modify("UPDATE tx SET state='empty', conf=? WHERE id=?", (conf, tid))
        return
    g = geo.localizza(testo, cfg)
    allarme = geo.allarme(testo, cfg)
    db.set_text(tid, testo, conf, g[0] if g else None, g[1] if g else None,
                g[2] if g else None, allarme)
    STATO.stt["pronte"] += 1
    log.info("%s[%.2f] %s", ("!! " if allarme else "→ "), conf, testo[:90])
    pubblica(tid)


def pubblica(tid):
    riga = db.event(tid)
    if riga:
        BUS.publish("event", riga, ricorda=False)
