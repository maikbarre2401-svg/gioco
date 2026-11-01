"""Avvio: riga di comando, ciclo di vita dei thread, server."""
import argparse
import logging
import logging.handlers
import os
import queue
import signal
import threading
import time

from . import __version__, bootstrap, config, db
from .runtime import STATO, STOP

log = logging.getLogger("guardia")

FORMATO = "%(asctime)s %(levelname).1s [%(threadName)s] %(message)s"


def configura_log(verbose=False, quiet=False, su_file=None):
    livello = logging.DEBUG if verbose else (logging.WARNING if quiet else logging.INFO)
    root = logging.getLogger()
    root.setLevel(livello)
    for h in list(root.handlers):
        root.removeHandler(h)
    c = logging.StreamHandler()
    c.setFormatter(logging.Formatter(FORMATO, datefmt="%H:%M:%S"))
    root.addHandler(c)
    if su_file:
        try:
            f = logging.handlers.RotatingFileHandler(su_file, maxBytes=2 << 20, backupCount=3,
                                                     encoding="utf-8")
            f.setFormatter(logging.Formatter(FORMATO, datefmt="%Y-%m-%d %H:%M:%S"))
            root.addHandler(f)
        except OSError as e:
            print("!! log su file non attivo (%s)" % e)
    for rumoroso in ("httpx", "httpcore", "urllib3", "faster_whisper", "multipart"):
        logging.getLogger(rumoroso).setLevel(logging.WARNING)


def parser():
    p = argparse.ArgumentParser(
        prog="guardia",
        description="Sala operativa radio self-hosted: scanner SDR, trascrizione, mappa 3D.",
        epilog="esempio: guardia.py --freqs 151175000:CC:digital,160900000:PL:analog --gain 24")
    p.add_argument("--version", action="version", version="guardia " + __version__)
    m = p.add_argument_group("modi")
    m.add_argument("--demo", action="store_true", help="solo interfaccia, traffico finto")
    m.add_argument("--sim", action="store_true", help="catena radio completa su dongle simulato")
    m.add_argument("--check", action="store_true", help="diagnostica dell'ambiente")
    m.add_argument("--selftest", action="store_true", help="test interni, senza hardware")
    m.add_argument("--install", action="store_true", help="(Linux) dipendenze di sistema")
    m.add_argument("--service", action="store_true", help="(Linux) unit systemd")
    r = p.add_argument_group("radio")
    r.add_argument("--freqs", help="FREQ:UNITA:modo,FREQ:UNITA:modo")
    r.add_argument("--ppm", type=int)
    r.add_argument("--gain", type=int)
    r.add_argument("--squelch", type=float, help="soglia fissa in dBFS (implica manual)")
    r.add_argument("--squelch-mode", choices=["auto", "manual"])
    r.add_argument("--dwell", type=float, help="secondi per gruppo di canali")
    r.add_argument("--model", help="modello whisper: tiny/base/small/medium")
    r.add_argument("--no-stt", action="store_true", help="niente trascrizione, solo audio")
    w = p.add_argument_group("interfaccia e dati")
    w.add_argument("--host")
    w.add_argument("--port", type=int)
    w.add_argument("--token")
    w.add_argument("--basemap", help="'vector' (default), 'osm' o un template raster")
    w.add_argument("--lat", type=float)
    w.add_argument("--lon", type=float)
    w.add_argument("--config", metavar="CARTELLA",
                   help="dove tenere guardia.json, guardia.db e audio/")
    w.add_argument("--log-file", metavar="FILE")
    w.add_argument("-v", "--verbose", action="store_true")
    w.add_argument("-q", "--quiet", action="store_true")
    return p


CHIAVI_CLI = ["host", "port", "token", "ppm", "gain", "squelch", "squelch_mode", "dwell",
              "model", "lat", "lon", "basemap"]


def prepara_config(a):
    """File + variabili d'ambiente + riga di comando, in quest'ordine di precedenza."""
    disco = config.from_env(config.load())
    nuovo_token = not disco.get("token")
    if nuovo_token:
        disco["token"] = os.urandom(8).hex()
    # gli override da riga di comando valgono SOLO per questa esecuzione: scriverli nel
    # file faceva riapparire un --port di ieri in un avvio senza argomenti
    cfg = dict(disco)
    for k in CHIAVI_CLI:
        v = getattr(a, k, None)
        if v is not None:
            cfg[k] = v
    if a.squelch is not None and a.squelch_mode is None:
        cfg["squelch_mode"] = "manual"
    if a.no_stt:
        cfg["stt"] = False
    if a.freqs:
        cfg["freqs"] = config.parse_freqs(a.freqs)
    config.validate(cfg)
    if nuovo_token or not os.path.exists(config.PATHS.cfg):
        config.save(config.validate(dict(disco)))      # il file resta dell'utente
    return cfg


def scegli_modo(a, cfg):
    """'radio', 'sim' o 'demo'. Se il dongle non c'e' si ripiega senza drammi."""
    if a.demo:
        return "demo", None
    if a.sim:
        bootstrap.ensure_env(["numpy"])
        from .sources import SimSource
        s = SimSource(cfg)
        s.stop = STOP
        log.info("dongle simulato: burst FM finti sui canali configurati")
        return "sim", s
    bootstrap.ensure_env(bootstrap.REQ_RADIO, hard=False)
    try:
        from rtlsdr import RtlSdr
        RtlSdr().close()
        return "radio", None
    except Exception as e:
        print("!! dongle non disponibile: " + str(e).strip()[:100])
        bootstrap.dongle_hint(e)
        print("!! parto in DEMO (interfaccia con traffico finto). Con --sim provi invece")
        print("   tutta la catena radio su un dongle simulato.")
        return "demo", None


def avvia_lavoratori(cfg, modo, sorgente):
    """Accende i thread che servono al modo scelto. Ritorna l'oggetto radio o None."""
    from . import adsb, demo, maintenance, stt
    txq = queue.Queue()
    radio = None

    if modo in ("radio", "sim"):
        from .radio import Radio
        try:
            radio = Radio(cfg, txq, source=sorgente)
            radio.start()
        except Exception as e:
            log.error("radio non avviabile (%s) → DEMO", str(e)[:140])
            modo = "demo"
    if modo == "demo":
        threading.Thread(target=demo.worker, args=(cfg,), name="demo", daemon=True).start()
    else:
        if cfg.get("stt", True):
            bootstrap.ensure_env(bootstrap.REQ_STT, hard=False)
        threading.Thread(target=stt.worker, args=(cfg, txq), name="whisper", daemon=True).start()
    if cfg.get("adsb", True):
        threading.Thread(target=adsb.worker, args=(cfg,), name="adsb", daemon=True).start()
    threading.Thread(target=maintenance.worker, args=(cfg,), name="pulizia", daemon=True).start()
    STATO.mode = modo
    return radio, modo


def banner(cfg, modo):
    ip = bootstrap.local_ip()
    canali = ", ".join("%.3f/%s/%s" % (c["freq"] / 1e6, c["unit"], c["mode"])
                       for c in cfg["freqs"])
    squelch = ("auto (rumore +%.0f dB)" % cfg["squelch_margin"]
               if cfg["squelch_mode"] == "auto" else "fisso %.0f dBFS" % cfg["squelch"])
    print("""
================================================
  GUARDIA %s  [%s]
  Telefono:  http://%s:%d/?t=%s
  Locale:    http://127.0.0.1:%d/?t=%s
  Canali:    %s
  Squelch:   %s
  Dati:      %s
  Ctrl+C per fermare
================================================
""" % (__version__, modo.upper(), ip, cfg["port"], cfg["token"], cfg["port"], cfg["token"],
       canali, squelch, config.PATHS.root), flush=True)


def main(argv=None):
    a = parser().parse_args(argv)
    configura_log(a.verbose, a.quiet, a.log_file)
    if a.config:
        config.PATHS.set_root(a.config)
        db.use(config.PATHS.db)

    if a.install:
        return bootstrap.do_install()
    if a.check:
        bootstrap.ensure_env([], hard=False)
        return bootstrap.do_check()
    if a.service:
        return bootstrap.do_service()
    if a.selftest:
        bootstrap.ensure_env(["numpy"])
        from .selftest import esegui
        return esegui()

    bootstrap.win_dll_path()
    bootstrap.ensure_env(bootstrap.REQ_CORE)
    try:
        cfg = prepara_config(a)
    except ValueError as e:
        print("!! --freqs malformato (%s). Usa FREQ:UNITA:modo,FREQ:UNITA:modo" % e)
        print("   es. 151175000:CC:digital,160900000:PL:analog")
        return 1

    if not bootstrap.port_free(cfg["host"], cfg["port"]):
        print("!! la porta %d e' gia' occupata." % cfg["port"])
        print("   Un'altra istanza di guardia e' ancora in esecuzione? Chiudila (Ctrl+C nella")
        print("   sua finestra), oppure usa un'altra porta:  python guardia.py --port 8081")
        if os.path.exists(config.PATHS.cfg):
            print("   La porta predefinita e' quella scritta in %s" % config.PATHS.cfg)
        return 1

    try:
        os.makedirs(config.PATHS.audio, exist_ok=True)
    except OSError as e:
        print("!! non posso creare %s: %s" % (config.PATHS.audio, e))
        return 1
    db.use(config.PATHS.db)
    db.init()

    def arresto(*_):
        if not STOP.is_set():
            log.info("arresto richiesto, chiudo...")
            STOP.set()
    for s in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(s, arresto)
        except (ValueError, OSError, AttributeError):
            pass          # non siamo nel thread principale: ci pensa uvicorn

    modo, sorgente = scegli_modo(a, cfg)
    radio, modo = avvia_lavoratori(cfg, modo, sorgente)
    banner(cfg, modo)

    from . import web
    import uvicorn
    try:
        uvicorn.run(web.build_app(cfg), host=cfg["host"], port=cfg["port"],
                    log_level="warning", ws_ping_interval=20, ws_ping_timeout=20)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        log.error("server fermato: %s", e)
        return 1
    finally:
        STOP.set()
        if radio:
            radio.close()
        from . import net
        net.close()
        db.close()
        time.sleep(0.3)
        print("\nchiuso.")
    return 0
