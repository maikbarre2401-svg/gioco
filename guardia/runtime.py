"""Stato condiviso del processo: evento di arresto e informazioni di servizio."""
import threading
import time

STOP = threading.Event()


class Stato:
    """Poche cose che tutti vogliono sapere: da dove arriva l'audio e come sta andando."""

    def __init__(self):
        self.t0 = time.time()
        self.mode = "?"
        self.radio = {"gruppi": 0, "canali": 0, "tratte": 0, "errori": 0,
                      "ultima": None, "centro": None, "dsd": False}
        self.stt = {"coda": 0, "modello": None, "pronte": 0, "fallite": 0}

    def uptime(self):
        return round(time.time() - self.t0, 1)


STATO = Stato()
