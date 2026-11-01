"""
guardia — sala operativa radio self-hosted.

Il pacchetto e' diviso per responsabilita':

    config      percorsi, valori di default, caricamento e validazione
    bootstrap   venv, dipendenze, diagnostica, installazione di sistema (solo stdlib)
    db          schema, migrazioni, accesso concorrente
    dsp         canalizzatore FFT, squelch, scrittura audio (solo numpy)
    sources     sorgenti IQ: dongle reale e dongle simulato
    radio       thread di ascolto: sintonia, gate per canale, registrazione
    stt         trascrizione vocale e riconoscimento dei toponimi
    geo         geocodifica con cache e rate-limit
    adsb        aeromobili nelle vicinanze
    demo        traffico finto per provare l'interfaccia
    maintenance pulizia di disco e database
    bus         diffusione degli eventi verso l'interfaccia (WebSocket)
    web         API HTTP e pagina
    app         avvio, ciclo di vita, riga di comando
    selftest    test interni, senza hardware
"""
__version__ = "3.0"
__all__ = ["__version__"]
