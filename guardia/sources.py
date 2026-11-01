"""Sorgenti IQ: il dongle vero e un dongle simulato per provare tutto senza hardware."""
import logging
import math
import threading
import time

log = logging.getLogger("guardia.sources")


class SourceError(RuntimeError):
    """Errore recuperabile della sorgente: il chiamante puo' tentare la riapertura."""


class RtlSource:
    """Dongle RTL-SDR reale. Si riapre da sola se il dispositivo sparisce e ritorna."""

    def __init__(self, cfg):
        self.cfg = cfg
        self.sr = int(cfg["sample_rate"])
        self.sdr = None
        self.freq = None
        self._lock = threading.Lock()
        self.open()

    def open(self):
        from rtlsdr import RtlSdr
        self.sdr = RtlSdr()
        self.sdr.sample_rate = self.sr
        try:
            self.sdr.gain = int(self.cfg["gain"])
        except Exception as e:
            log.warning("gain %s rifiutato (%s), uso l'automatico", self.cfg["gain"], e)
            try:
                self.sdr.gain = "auto"
            except Exception:
                pass
        if self.cfg["ppm"]:
            try:
                self.sdr.freq_correction = int(self.cfg["ppm"])
            except Exception as e:      # librtlsdr rifiuta il valore se e' gia' quello
                log.debug("ppm non applicato: %s", e)
        if self.freq:
            self.sdr.center_freq = int(self.freq)
        log.info("dongle aperto (%.1f Msps, gain %s)", self.sr / 1e6, self.sdr.gain)

    def reopen(self):
        self.close()
        time.sleep(1.0)
        self.open()

    def tune(self, hz):
        self.freq = int(hz)
        try:
            self.sdr.center_freq = self.freq
            # scarto ~50 ms: il PLL si assesta e nel buffer USB c'e' ancora il canale vecchio
            self.sdr.read_samples(int(self.sr * 0.05) // 512 * 512)
        except Exception as e:
            raise SourceError("sintonia fallita: %s" % e)

    def read(self, n):
        try:
            return self.sdr.read_samples(n)
        except Exception as e:
            raise SourceError("lettura fallita: %s" % e)

    def close(self):
        with self._lock:
            if self.sdr is not None:
                try:
                    self.sdr.close()
                except Exception:
                    pass
                self.sdr = None


class SimSource:
    """
    Dongle simulato: rumore gaussiano + burst FM modulati a 700 Hz sui canali configurati.
    Serve a --sim e al selftest, cosi' tutta la catena si prova senza hardware.
    """

    def __init__(self, cfg, realtime=True, seed=7, quiet=False):
        import numpy as np
        self.np = np
        self.cfg = cfg
        self.sr = int(cfg["sample_rate"])
        self.dev = float(cfg["deviation"])
        self.rng = np.random.default_rng(seed)
        self.chans = list(cfg["freqs"])
        self.center = self.chans[0]["freq"]
        self.n0 = 0
        self.realtime = realtime
        self.quiet = quiet
        self.t_start = time.time()
        self.sigma = 10 ** (-45 / 20.0) / math.sqrt(2.0)   # rumore ~ -45 dBFS su tutta la banda
        self.amp = 10 ** (-20 / 20.0)                      # portante ~ -20 dBFS
        self.fase = {}
        self.stop = None

    def bursts(self, i, ta, tb):
        """Pianificazione deterministica: il canale i parla D secondi ogni P secondi."""
        if self.quiet:
            return
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
        t = (self.n0 + np.arange(n)) / self.sr
        iq = (self.rng.normal(0, self.sigma, n) +
              1j * self.rng.normal(0, self.sigma, n)).astype(np.complex128)
        for i, ch in enumerate(self.chans):
            off = ch["freq"] - self.center
            if abs(off) > self.sr * 0.49:
                continue
            env = np.zeros(n)
            for t0, t1 in self.bursts(i, t[0], t[-1]):
                r = 0.005   # rampa di 5 ms: senza, l'accensione e' a banda larga
                e = np.clip(np.minimum((t - t0) / r, (t1 - t) / r), 0.0, 1.0)
                env = np.maximum(env, 0.5 * (1.0 - np.cos(math.pi * e)))
            if not env.any():
                continue
            inst = off + self.dev * np.sin(2 * math.pi * 700.0 * t)
            ph = self.fase.get(i, 0.0) + 2 * math.pi * np.cumsum(inst) / self.sr
            self.fase[i] = float(ph[-1] % (2 * math.pi))
            iq += self.amp * env * np.exp(1j * ph)
        self.n0 += n
        if self.realtime:
            lag = self.n0 / self.sr - (time.time() - self.t_start)
            if lag > 0:
                if self.stop is not None:
                    self.stop.wait(lag)
                else:
                    time.sleep(lag)
        return iq

    def reopen(self):
        pass

    def close(self):
        pass
