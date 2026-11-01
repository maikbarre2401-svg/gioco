"""Una sola sessione HTTP riusata (keep-alive) per tutte le chiamate verso l'esterno."""
import threading

from . import __version__

UA = {"User-Agent": "guardia.py/%s (self-hosted scanner)" % __version__}
_sessione = None
_lock = threading.Lock()


def session():
    global _sessione
    if _sessione is None:
        with _lock:
            if _sessione is None:
                import requests
                from requests.adapters import HTTPAdapter
                s = requests.Session()
                s.headers.update(UA)
                # poche connessioni, riusate: un solo pool basta e avanza
                s.mount("https://", HTTPAdapter(pool_connections=4, pool_maxsize=8))
                _sessione = s
    return _sessione


def close():
    global _sessione
    if _sessione is not None:
        try:
            _sessione.close()
        except Exception:
            pass
        _sessione = None
