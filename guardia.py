#!/usr/bin/env python3
"""
guardia.py — sala operativa radio self-hosted. Windows / Linux / macOS.

AVVIO
    python guardia.py                 1a volta: crea la venv e installa le dipendenze
    python guardia.py                 poi: avvia (passa in demo se il dongle non risponde)
    python guardia.py --freqs 151175000:CC:digital,160900000:PL:analog --gain 24 --ppm 42

MODI
    --check      diagnostica dell'ambiente (pacchetti, binari, dongle)
    --selftest   test interni: DSP, squelch, database, API, WebSocket. Nessun hardware
    --sim        pipeline radio completa su un dongle simulato
    --demo       solo interfaccia, traffico finto, nessuna radio
    --install    (Linux) apt + sink PulseAudio + dsd-fme
    --service    (Linux) scrive la unit systemd

WINDOWS + SDR REALE
    Due cose distinte: il driver (Zadig > Options > List All Devices > "Bulk-In,
    Interface (0)" > WinUSB) e la libreria (librtlsdr.dll e libusb-1.0.dll da
    github.com/rtlsdrblog/rtl-sdr-blog/releases, copiate accanto a questo file).

RICEZIONE
    Un solo dongle non puo' stare su piu' frequenze lontane. I canali vengono raggruppati:
    quelli che stanno nei ~1.9 MHz di banda sono ascoltati TUTTI in parallelo (una FFT per
    blocco, N canali estratti), i gruppi restanti a rotazione. Lo squelch e' per canale e
    misurato dopo il filtro di canale, non sulla banda larga.

MODO 'digital'
    L'audio demodulato viene spedito via UDP a 127.0.0.1:7355 e si registra l'uscita del
    sink PulseAudio 'dsd_out'. Serve dsd-fme in ascolto su quella porta (--install),
    altrimenti il canale viene trattato come 'analog' e il log lo dice.

NOTA — ascolto e registrazione di comunicazioni radio sono regolati dalla legge locale:
usalo sulle frequenze che ti e' consentito ricevere.

Il codice vive nel pacchetto ./guardia/ accanto a questo file; qui c'e' solo l'avvio.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from guardia.app import main
except ImportError as e:
    if "guardia" not in str(e):
        raise
    print("!! manca la cartella 'guardia/' accanto a guardia.py (%s)." % e)
    print("   Scarica di nuovo il progetto per intero: non basta copiare questo file.")
    sys.exit(1)

if __name__ == "__main__":
    sys.exit(main() or 0)
