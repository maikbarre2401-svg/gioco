"""
Diffusione degli eventi dai thread di lavoro all'interfaccia.

I produttori (radio, demo, trascrittore) sono thread normali, i consumatori sono
WebSocket dentro il loop asyncio di uvicorn: il passaggio avviene con
call_soon_threadsafe, l'unico modo corretto di svegliare asyncio da un altro thread.
Se nessuno e' collegato, pubblicare non costa quasi nulla.
"""
import logging
import threading
import time

log = logging.getLogger("guardia.bus")
MAX_CODA = 200


class Bus:
    def __init__(self):
        self._loop = None
        self._code = set()
        self._lock = threading.Lock()
        self.ultimo = {}          # ultimo messaggio per tipo: serve ai nuovi collegati

    def bind(self, loop):
        """Chiamato all'avvio del server: senza loop i messaggi vengono solo memorizzati."""
        self._loop = loop

    def subscribe(self, coda):
        with self._lock:
            self._code.add(coda)
        return coda

    def unsubscribe(self, coda):
        with self._lock:
            self._code.discard(coda)

    @property
    def clienti(self):
        with self._lock:
            return len(self._code)

    def publish(self, tipo, dati, ricorda=True):
        msg = {"t": tipo, "ts": time.time(), "d": dati}
        if ricorda:
            self.ultimo[tipo] = msg
        with self._lock:
            code = list(self._code)
        if not code or self._loop is None:
            return 0
        inviati = 0
        for coda in code:
            try:
                self._loop.call_soon_threadsafe(self._metti, coda, msg)
                inviati += 1
            except RuntimeError:
                pass          # loop chiuso: il client verra' rimosso dal suo handler
        return inviati

    @staticmethod
    def _metti(coda, msg):
        if coda.qsize() >= MAX_CODA:       # cliente lento: meglio perdere il piu' vecchio
            try:
                coda.get_nowait()
            except Exception:
                return
        try:
            coda.put_nowait(msg)
        except Exception:
            pass


BUS = Bus()
