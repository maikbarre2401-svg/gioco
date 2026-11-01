"""
Il thread di ascolto.

Un dongle non puo' stare su frequenze lontane, ma puo' stare su tutte quelle che entrano
nella sua banda: i canali vengono raggruppati e ogni gruppo e' ascoltato in parallelo con
un canalizzatore FFT; i gruppi restanti a rotazione. Lo squelch e' per canale e misurato
dopo il filtro di canale, non sulla banda larga.
"""
import logging
import os
import shutil
import socket
import subprocess
import time
import threading

from . import config, db
from .bus import BUS
from .dsp import Channelizer, Gate, write_wav
from .runtime import STATO, STOP
from .sources import RtlSource, SourceError

log = logging.getLogger("guardia.radio")

SPAN_MAX = 1_900_000        # larghezza utile per un gruppo a 2.4 Msps
MAX_ERRORI = 10             # errori consecutivi oltre i quali si rinuncia
PORTA_DSD = 7355
PERIODO_LIVELLI = 0.4       # ogni quanto spedire i livelli all'interfaccia


def have(b):
    return shutil.which(b) is not None


def cluster(freqs, span):
    """Raggruppa i canali che stanno insieme nella banda del dongle (lista di liste)."""
    gruppi, corrente = [], []
    for c in sorted(freqs, key=lambda c: c["freq"]):
        if corrente and c["freq"] - corrente[0]["freq"] > span:
            gruppi.append(corrente)
            corrente = []
        corrente.append(c)
    if corrente:
        gruppi.append(corrente)
    return gruppi


def pick_center(gruppo, dc_off=150_000):
    """Centro di sintonia, spostato per non mettere nessun canale sullo spike DC del dongle."""
    mid = (gruppo[0]["freq"] + gruppo[-1]["freq"]) / 2.0
    for extra in (0, 37_000, -37_000, 71_000, -71_000):
        c = mid + dc_off + extra
        if all(abs(ch["freq"] - c) > 12_000 for ch in gruppo):
            return c
    return mid + dc_off


class DigitalTap:
    """
    Inoltro verso dsd-fme: l'audio demodulato esce in UDP, l'uscita decodificata rientra
    registrando il sink PulseAudio. Un canale per volta, perche' dsd-fme ne decodifica uno.
    """
    MIN_BYTE = 48000 * 2 * 0.5      # mezzo secondo: sotto, dsd-fme non stava decodificando

    def __init__(self):
        self.udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.attivo = None          # (indice canale, Popen, file, percorso)

    @staticmethod
    def disponibile():
        if not (have("parec") and (have("dsd-fme") or have("dsd")) and have("pactl")):
            return False
        try:
            r = subprocess.run("pactl list short sinks", shell=True, capture_output=True,
                               text=True, timeout=5)
            return "dsd_out" in r.stdout
        except Exception:
            return False

    @property
    def canale(self):
        return self.attivo[0] if self.attivo else None

    def start(self, i, ch):
        if self.attivo is not None:
            return
        percorso = os.path.join(config.PATHS.audio,
                                "%d_%d.raw" % (int(time.time() * 1000), ch["freq"]))
        try:
            fh = open(percorso, "wb")
            p = subprocess.Popen(["parec", "-d", "dsd_out.monitor", "--format=s16le",
                                  "--rate=48000", "--channels=1", "--raw"],
                                 stdout=fh, stderr=subprocess.DEVNULL)
            self.attivo = (i, p, fh, percorso)
        except Exception as e:
            log.warning("parec non avviato: %s", e)
            self.attivo = None

    def feed(self, pcm16):
        try:
            self.udp.sendto(pcm16, ("127.0.0.1", PORTA_DSD))
        except OSError:
            pass

    def stop(self):
        if not self.attivo:
            return None
        _, p, fh, percorso = self.attivo
        self.attivo = None
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
        return percorso

    def buono(self, percorso):
        try:
            return bool(percorso) and os.path.getsize(percorso) > self.MIN_BYTE
        except OSError:
            return False

    def close(self):
        self.stop()
        try:
            self.udp.close()
        except Exception:
            pass


class Radio(threading.Thread):
    daemon = True
    name = "radio"

    def __init__(self, cfg, txq, source=None):
        super().__init__(name=self.name)
        import numpy as np
        self.np = np
        self.cfg, self.txq = cfg, txq
        self.src = source if source is not None else RtlSource(cfg)
        span = min(SPAN_MAX, int(cfg["sample_rate"] * 0.79))
        self.groups = cluster(cfg["freqs"], span)
        self.centri = [pick_center(g) for g in self.groups]
        self.chz = [Channelizer(cfg, [ch["freq"] - c for ch in g])
                    for g, c in zip(self.groups, self.centri)]
        # i gate vivono quanto il programma: senza, lo squelch si ricalibrerebbe a ogni
        # turno di scansione, buttando via mezzo secondo di ascolto ogni volta
        self.gates = [[Gate(cfg, ch) for ch in g] for g in self.groups]
        self.tap = DigitalTap()
        self.dsd = DigitalTap.disponibile()
        self.errori = 0
        self._ultimi_livelli = 0.0

        STATO.radio.update(gruppi=len(self.groups), canali=len(cfg["freqs"]), dsd=self.dsd)
        for g, c in zip(self.groups, self.centri):
            log.info("gruppo @%.3f MHz: %s", c / 1e6,
                     ", ".join("%s %.4f" % (x["unit"], x["freq"] / 1e6) for x in g))
        if len(self.groups) > 1:
            log.info("%d gruppi: scansione a rotazione (%.1fs ciascuno)",
                     len(self.groups), cfg["dwell"])
        digitali = [c["unit"] for c in cfg["freqs"] if c["mode"] == "digital"]
        if digitali and not self.dsd:
            log.warning("modo 'digital' richiesto su %s ma dsd-fme/parec/sink non ci sono: "
                        "tratto i canali come analogici", ",".join(digitali))

    def close(self):
        self.tap.close()
        try:
            self.src.close()
        except Exception:
            pass

    # ───────────────────────────── registrazione

    def store(self, ch, seg, raw=None):
        """Scrive l'audio e inserisce la riga 'pending' per il trascrittore."""
        base = "%d_%d" % (int(time.time() * 1000), ch["freq"])
        wav = write_wav(os.path.join(config.PATHS.audio, base + ".wav"), seg["audio"])
        if wav is None:
            return None
        percorso, modo = wav, ch["mode"]
        if raw is not None:
            if self.tap.buono(raw):
                os.unlink(wav)
                percorso = raw
            else:
                for p in (raw,):
                    try:
                        os.unlink(p)
                    except OSError:
                        pass
                modo = ch["mode"] + "/fallback"
        tid = db.add_capture(time.time() - seg["dur"], ch["freq"], ch["unit"], modo,
                             percorso, seg["dur"], seg["rssi"])
        STATO.radio["tratte"] += 1
        STATO.radio["ultima"] = time.time()
        log.info("%s %.4f  %.1fs  %.0f→%.0f dBFS  %s", ch["unit"], ch["freq"] / 1e6,
                 seg["dur"], seg["floor"], seg["rssi"], os.path.basename(percorso))
        BUS.publish("capture", {"id": tid, "unit": ch["unit"], "freq": ch["freq"],
                                "dur": seg["dur"], "rssi": seg["rssi"]}, ricorda=False)
        self.txq.put(tid)
        return tid

    def livelli(self, gi, gates, forza=False):
        ora = time.time()
        if not forza and ora - self._ultimi_livelli < PERIODO_LIVELLI:
            return
        self._ultimi_livelli = ora
        BUS.publish("levels", {"gruppo": gi, "centro": self.centri[gi],
                               "canali": [g.stato() for g in gates]})

    # ───────────────────────────── ciclo

    def serve(self, gi):
        """Ascolta un gruppo per 'dwell' secondi (senza limiti se e' l'unico)."""
        np = self.np
        gruppo, chz, gates = self.groups[gi], self.chz[gi], self.gates[gi]
        self.src.tune(self.centri[gi])
        chz.reset()
        for g in gates:
            g.rearm()
        ruota = len(self.groups) > 1
        scadenza = time.time() + float(self.cfg["dwell"]) if ruota else None
        while not STOP.is_set():
            lv = chz.process(self.src.read(chz.new))
            if lv is None:
                continue
            ora = time.time()
            for i, rssi in enumerate(lv):
                ch, gate = gruppo[i], gates[i]
                # demodulazione pigra: i canali che tacciono non costano quasi nulla
                audio = chz.demod(i) if gate.vuole_audio(rssi) else None
                if audio is None:
                    chz.salta(i)
                seg = gate.push(audio, rssi, ora, n=chz.blocco)
                if gate.opened_now:
                    log.debug("%s aperto (%.0f dBFS, soglia %.0f)", ch["unit"], rssi,
                              gate.threshold())
                    if ch["mode"] == "digital" and self.dsd:
                        self.tap.start(i, ch)
                    self.livelli(gi, gates, forza=True)
                if gate.open and audio is not None and self.tap.canale == i:
                    self.tap.feed(np.clip(audio * 14000.0, -32768, 32767).astype("<i2").tobytes())
                if seg is not None:
                    raw = self.tap.stop() if self.tap.canale == i else None
                    self.store(ch, seg, raw)
                    self.livelli(gi, gates, forza=True)
                elif not gate.open and self.tap.canale == i:
                    raw = self.tap.stop()
                    try:
                        os.unlink(raw)
                    except (OSError, TypeError):
                        pass
            self.livelli(gi, gates)
            # non taglio una trasmissione in corso solo perche' e' scaduto il turno
            if scadenza and ora >= scadenza and not any(g.open for g in gates):
                return

    def run(self):
        try:
            while not STOP.is_set():
                for gi in range(len(self.groups)):
                    if STOP.is_set():
                        break
                    try:
                        self.serve(gi)
                        self.errori = 0
                    except SourceError as e:
                        self.errori += 1
                        STATO.radio["errori"] += 1
                        log.warning("sorgente persa (%d/%d): %s", self.errori, MAX_ERRORI, e)
                        if self.errori >= MAX_ERRORI:
                            log.error("il dongle non risponde piu': fermo la cattura")
                            return
                        STOP.wait(min(30, 2 ** self.errori))
                        try:
                            self.src.reopen()
                            log.info("dongle riaperto")
                        except Exception as e2:
                            log.warning("riapertura fallita: %s", e2)
                    except Exception as e:
                        self.errori += 1
                        STATO.radio["errori"] += 1
                        log.warning("errore radio (%d/%d): %s", self.errori, MAX_ERRORI, e)
                        if self.errori >= MAX_ERRORI:
                            log.error("troppi errori consecutivi: fermo la cattura")
                            return
                        STOP.wait(2)
        finally:
            self.close()
            log.info("radio chiusa")
