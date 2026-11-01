"""
Elaborazione del segnale, solo numpy (niente scipy: installazione molto piu' leggera).

Canalizzatore FFT: una sola FFT per blocco e N canali estratti in parallelo. Per ogni
canale: traslazione in banda base (selezione dei bin), filtro di canale (sagoma in
frequenza), decimazione a 48 kHz, discriminatore FM e de-enfasi.

Overlap-save: i primi campioni di ogni blocco, contaminati dalla convoluzione circolare,
vengono scartati. Senza, a ogni blocco si sentirebbe un click.

La demodulazione e' pigra: il livello di un canale costa una IFFT e una media, la
demodulazione costa molto di piu'. Sui canali che tacciono (quasi sempre tutti) la si
salta del tutto — su un Raspberry e' la differenza tra reggere quattro canali e non reggerli.
"""
import logging
import math
import os
import wave

log = logging.getLogger("guardia.dsp")

AUDIO_SR = 48000


def lowpass_taps(cutoff, sr, ntaps=127, beta=7.0):
    """FIR passa-basso a finestra di Kaiser (sinc * kaiser), guadagno unitario in continua."""
    import numpy as np
    n = np.arange(ntaps) - (ntaps - 1) / 2.0
    h = np.sinc(2.0 * cutoff / sr * n) * np.kaiser(ntaps, beta)
    return h / h.sum()


class Fir:
    """FIR streaming con stato: continuita' garantita tra blocchi consecutivi."""

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
        y = np.convolve(buf, self.h, "valid")           # len(y) == len(x)
        if self.k:
            self.zi = buf[len(buf) - self.k:].copy()
        if self.M == 1:
            return y
        out = y[self.phase::self.M]
        self.phase = (self.phase - len(y)) % self.M
        return out


class Channelizer:
    NOUT = 960          # campioni audio per FFT (20 ms)
    NDROP = 192         # scartati per overlap-save (4 ms)
    TAU = 300e-6        # de-enfasi europea

    def __init__(self, cfg, offsets):
        import numpy as np
        self.np = np
        self.sr = int(cfg["sample_rate"])
        self.decim = self.sr // AUDIO_SR
        if self.decim < 1 or self.sr % AUDIO_SR:
            raise ValueError("sample_rate deve essere un multiplo di 48000")
        self.nfft = self.NOUT * self.decim          # campioni IQ per FFT
        self.ovl = self.NDROP * self.decim          # riportati dal blocco precedente
        self.new = self.nfft - self.ovl             # campioni nuovi per iterazione
        self.blocco = self.NOUT - self.NDROP        # campioni audio prodotti per iterazione
        self.dt = self.blocco / float(AUDIO_SR)
        self.dev = float(cfg["deviation"])
        self.bin_hz = self.sr / float(self.nfft)
        self.offsets = [float(o) for o in offsets]
        self.n = len(self.offsets)

        meta = self.NOUT // 2
        sel = np.arange(-meta, self.NOUT - meta)
        # sagoma di canale: piatta fino a channel_bw, poi raccordo a coseno rialzato
        bw = float(cfg["channel_bw"])
        trans = max(1000.0, bw * 0.4)
        t = np.clip((np.abs(sel * self.bin_hz) - bw) / trans, 0.0, 1.0)
        taper = 0.5 * (1.0 + np.cos(np.pi * t))
        # sagoma e indici pre-ruotati: una ifftshift in meno per canale a ogni blocco
        self.taper = np.fft.ifftshift(taper)
        self.idx = [np.fft.ifftshift((int(round(o / self.bin_hz)) + sel) % self.nfft).astype(np.intp)
                    for o in self.offsets]

        # de-enfasi: il polo singolo y[n]=a*x[n]+(1-a)*y[n-1] come FIR esponenziale
        a = (1.0 / AUDIO_SR) / (self.TAU + 1.0 / AUDIO_SR)
        ntaps = int(math.ceil(math.log(1e-4) / math.log(1.0 - a)))
        hd = a * (1.0 - a) ** np.arange(ntaps)
        self.deemph = [Fir(hd / hd.sum()) for _ in self.offsets]

        self.buf = np.zeros(self.nfft, dtype=np.complex128)   # riusato a ogni blocco
        self.riempito = 0
        self.z = [None] * self.n                              # banda base per canale
        self.last = np.zeros(self.n, dtype=np.complex128)
        self.dc = np.zeros(self.n)
        self.k_fm = AUDIO_SR / (2.0 * math.pi * self.dev)

    def reset(self):
        """Dopo una risintonizzazione lo stato dei filtri non e' piu' valido."""
        self.buf[:] = 0
        self.riempito = 0
        self.last[:] = 0
        self.dc[:] = 0
        self.z = [None] * self.n
        for f in self.deemph:
            f.reset()

    def process(self, iq):
        """Un blocco IQ nuovo → lista di livelli in dBFS, o None se serve altro segnale."""
        np = self.np
        iq = np.asarray(iq)
        if len(iq) != self.new:
            # tollerante: accumula finche' non ha abbastanza campioni
            spazio = self.nfft - self.riempito
            n = min(len(iq), spazio)
            self.buf[self.riempito:self.riempito + n] = iq[:n]
            self.riempito += n
            if self.riempito < self.nfft:
                return None
        else:
            self.buf[:self.ovl] = self.buf[self.nfft - self.ovl:]
            self.buf[self.ovl:] = iq
            self.riempito = self.nfft

        X = np.fft.fft(self.buf)
        livelli = []
        for i, idx in enumerate(self.idx):
            z = np.fft.ifft(X[idx] * self.taper)[self.NDROP:] / self.decim
            self.z[i] = z
            livelli.append(10.0 * math.log10(float(np.mean(z.real ** 2 + z.imag ** 2)) + 1e-20))
        if len(iq) != self.new:                 # percorso di accumulo: riparte da capo
            self.buf[:self.ovl] = self.buf[self.nfft - self.ovl:]
            self.riempito = self.ovl
        return livelli

    def demod(self, i):
        """Audio del canale i per l'ultimo blocco. Da chiamare solo se serve davvero."""
        np = self.np
        z = self.z[i]
        if z is None:
            return None
        # discriminatore FM, con l'ultimo campione del blocco precedente per continuita'
        w = np.concatenate((self.last[i:i + 1], z))
        self.last[i] = z[-1]
        a = np.angle(w[1:] * np.conj(w[:-1])) * self.k_fm
        a = self.deemph[i](a)
        self.dc[i] += 0.05 * (float(np.mean(a)) - self.dc[i])   # scentratura del tuner
        return (a - self.dc[i]).astype(np.float32)

    def salta(self, i):
        """Il canale tace: niente demodulazione, ma lo stato resta coerente."""
        z = self.z[i]
        if z is not None:
            self.last[i] = z[-1]


class Gate:
    """Squelch + segmentatore per un singolo canale (macchina a stati con hang e pre-roll)."""
    CAL_BLOCKS = 32          # ~0.5 s di calibrazione prima di abilitare l'apertura
    PRE_DB = 6.0             # quanto sotto la soglia si inizia comunque a demodulare

    def __init__(self, cfg, ch, sr=AUDIO_SR):
        import numpy as np
        from collections import deque
        self.np = np
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
        self.rssi = -120.0
        self.tratte = 0

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

    def vuole_audio(self, rssi):
        """Serve demodulare questo blocco? Aperto, oppure gia' vicino alla soglia."""
        return self.open or rssi > self.threshold() - self.PRE_DB

    def _track(self, rssi):
        """
        Rumore di fondo: scende in fretta, risale piano, mai mentre il canale e' aperto.
        All'avvio si calibra sul MINIMO dei primi blocchi: se partisse dal primo valore e
        quel blocco fosse una trasmissione, la soglia resterebbe inchiodata in alto.
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

    def push(self, audio, rssi, now, n=None):
        """
        Ritorna il segmento concluso (dict) o None. audio=None significa "canale muto":
        nel pre-roll entra silenzio, che e' esattamente cio' che si sarebbe registrato.
        """
        n = len(audio) if audio is not None else (n or 0)
        dt = n / float(self.sr)
        self.rssi = rssi
        self._track(rssi)
        thr = self.threshold()
        self.opened_now = False
        if self.cal is not None:
            return None
        if audio is None:
            audio = self.np.zeros(n, dtype=self.np.float32)
        if not self.open:
            self.pre.append(audio)
            self.pre_n += n
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
        np = self.np
        self.open = False
        buf, self.buf = self.buf, []
        if not buf:
            return None
        audio = np.concatenate(buf)
        dur = len(audio) / float(self.sr)
        # il pre-roll non e' voce: non deve far passare le tratte troppo corte
        if dur - float(self.cfg["preroll"]) < float(self.cfg["min_voice"]):
            return None
        self.tratte += 1
        return {"audio": audio, "dur": round(dur, 2), "rssi": round(self.peak, 1),
                "floor": round(self.floor if self.floor is not None else -120.0, 1)}

    def stato(self):
        """Fotografia per l'interfaccia."""
        return {"unit": self.ch["unit"], "freq": self.ch["freq"], "mode": self.ch["mode"],
                "rssi": round(self.rssi, 1),
                "floor": round(self.floor, 1) if self.floor is not None else None,
                "thr": round(self.threshold(), 1), "open": self.open,
                "cal": self.cal is not None, "tratte": self.tratte}


def write_wav(path, audio, sr=AUDIO_SR):
    """WAV mono 16 bit con un solo guadagno per tratta (niente pumping blocco per blocco)."""
    import numpy as np
    picco = float(np.max(np.abs(audio))) if len(audio) else 0.0
    gain = min(8.0, 0.7 / picco) if picco > 1e-6 else 1.0
    pcm = np.clip(audio * gain * 32767.0, -32768, 32767).astype("<i2")
    tmp = path + ".part"
    try:
        with wave.open(tmp, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sr)
            w.writeframes(pcm.tobytes())
        os.replace(tmp, path)
    except OSError as e:
        log.error("scrittura audio fallita (%s): %s", path, e)
        try:
            os.unlink(tmp)
        except OSError:
            pass
        return None
    return path
