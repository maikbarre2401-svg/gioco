"""
Test interni, senza hardware e senza rete: `python guardia.py --selftest`.

Coprono le parti dove un errore non si vede subito: il DSP, lo squelch, le migrazioni
del database, i filtri delle API, l'autenticazione e il push via WebSocket.
"""
import json
import logging
import math
import os
import shutil
import socket
import sqlite3
import tempfile
import time
import traceback
import wave

from . import bus, config, db, dsp, geo, maintenance, radio, web
from .sources import SimSource

PROVE = []


def prova(fn):
    PROVE.append(fn)
    return fn


# ───────────────────────────── configurazione

@prova
def t_config():
    """config: valori impossibili corretti, canali non validi scartati, variabili d'ambiente"""
    cfg = config.validate(dict(config.DEFAULTS, port=99999, gain=900, ppm="x",
                               squelch_mode="boh", min_voice=5, max_seg=2, alerts="no",
                               freqs=[{"freq": 10, "unit": "X", "mode": "analog"},
                                      {"freq": 151175000, "unit": "CC", "mode": "strano"},
                                      {"freq": 151175000, "unit": "CC", "mode": "analog"},
                                      "spazzatura"]))
    assert cfg["port"] == 8080, cfg["port"]
    assert cfg["gain"] == 50 and cfg["ppm"] == 0
    assert cfg["squelch_mode"] == "auto"
    assert cfg["max_seg"] > cfg["min_voice"]
    assert cfg["alerts"] == []
    assert len(cfg["freqs"]) == 1 and cfg["freqs"][0]["mode"] == "analog", cfg["freqs"]
    assert config.validate({})["port"] == config.DEFAULTS["port"]      # dizionario parziale
    assert config.validate({"freqs": []})["freqs"] == config.DEFAULTS["freqs"]

    e = config.from_env(config.load(), {"GUARDIA_PORT": "9123", "GUARDIA_STT": "false",
                                        "GUARDIA_CITY": "Milano", "GUARDIA_GAIN": "boh"})
    assert e["port"] == 9123 and e["stt"] is False and e["city"] == "Milano"
    assert e["gain"] == config.DEFAULTS["gain"]                        # valore illeggibile ignorato

    f = config.parse_freqs("151175000:CC:digital,160900000:PL")
    assert f[0]["mode"] == "digital" and f[1]["mode"] == "analog", f
    for cattivo in ("", "abc", "151175000"):
        try:
            config.parse_freqs(cattivo)
            raise AssertionError("accettato %r" % cattivo)
        except ValueError:
            pass


@prova
def t_salvataggio():
    """config: salvataggio atomico, permessi stretti, file illeggibile tollerato"""
    d = tempfile.mkdtemp()
    p = os.path.join(d, "guardia.json")
    config.save({"port": 9999, "token": "abc"}, p)
    assert json.load(open(p))["port"] == 9999
    if os.name != "nt":
        assert oct(os.stat(p).st_mode)[-3:] == "600", oct(os.stat(p).st_mode)
    open(p, "w").write("{rotto")
    assert config.load(p)["port"] == config.DEFAULTS["port"]           # non deve sollevare
    shutil.rmtree(d, ignore_errors=True)


# ───────────────────────────── testo

@prova
def t_toponimi():
    """geo: riconosce via/piazza/lungotevere, si ferma dove deve, trova le parole d'allarme"""
    casi = {
        "andate in via Nomentana civico 88 per incidente": "via Nomentana",
        "intervento in piazza Vittorio Emanuele II per schiamazzi": "piazza Vittorio Emanuele II",
        "via del Corso altezza civico 12": "via del Corso",
        "Traffico intenso su via Salaria": "via Salaria",
        "squadra in lungotevere Marzio": "lungotevere Marzio",
        "Rientro in caserma, via di Macchia Saponara": "via di Macchia Saponara",
        "soggetto in fuga verso Viale Trastevere": "viale Trastevere",
    }
    for frase, atteso in casi.items():
        got = geo.nomi(frase)
        assert got and got[0] == atteso, "%r → %r (atteso %r)" % (frase, got, atteso)
    assert geo.nomi("nessun indirizzo qui, solo parole") == []
    cfg = config.validate({})
    assert geo.allarme("principio di incendio in via Prova", cfg) == "incendio"
    assert geo.allarme("tutto tranquillo", cfg) is None
    assert geo.allarme(None, cfg) is None


# ───────────────────────────── radio

@prova
def t_gruppi():
    """radio: raggruppamento dei canali e scelta del centro di sintonia"""
    g = radio.cluster(config.DEFAULTS["freqs"], 1_900_000)
    assert len(g) == 2 and [len(x) for x in g] == [2, 2], g
    vicini = [{"freq": 151175000, "unit": "A", "mode": "analog"},
              {"freq": 151200000, "unit": "B", "mode": "analog"},
              {"freq": 152025000, "unit": "C", "mode": "analog"}]
    g = radio.cluster(vicini, 1_900_000)
    assert len(g) == 1 and len(g[0]) == 3, g
    c = radio.pick_center(g[0])
    assert all(abs(ch["freq"] - c) > 12_000 for ch in g[0])
    assert all(abs(ch["freq"] - c) < 1_200_000 for ch in g[0])


def _cfg2(**kw):
    return config.validate(dict(config.DEFAULTS, freqs=[
        {"freq": 160000000, "unit": "A", "mode": "analog"},
        {"freq": 160300000, "unit": "B", "mode": "analog"}], **kw))


@prova
def t_dsp():
    """dsp: livelli per canale, isolamento e tono demodulato a 700 Hz"""
    import numpy as np
    cfg = _cfg2()
    gruppo = cfg["freqs"]
    centro = radio.pick_center(gruppo)
    src = SimSource(cfg, realtime=False)
    src.tune(centro)
    chz = dsp.Channelizer(cfg, [c["freq"] - centro for c in gruppo])

    # il canale A parla da 1.5 a 4.0 s, il B da 3.2 a 6.2: misuro nella finestra 1.8-3.0
    lv, audio, t = {"A": [], "B": []}, [], 0.0
    while t < 3.0:
        r = chz.process(src.read(chz.new))
        t += chz.dt
        if r and t > 1.8:
            lv["A"].append(r[0])
            lv["B"].append(r[1])
            audio.append(chz.demod(0))
    a, b = max(lv["A"]), max(lv["B"])
    assert -26 < a < -14, "livello del canale attivo fuori scala: %.1f dBFS" % a
    assert b < a - 25, "isolamento insufficiente: A=%.1f B=%.1f" % (a, b)

    sig = np.concatenate(audio)
    assert len(sig) > 9000
    sp = np.abs(np.fft.rfft(sig * np.hanning(len(sig))))
    f = np.fft.rfftfreq(len(sig), 1.0 / dsp.AUDIO_SR)[int(np.argmax(sp))]
    assert abs(f - 700) < 25, "tono demodulato a %.0f Hz invece di 700" % f
    picco = float(np.max(np.abs(sig)))
    assert 0.2 < picco < 1.5, "ampiezza audio anomala: %.2f" % picco


@prova
def t_squelch():
    """dsp: lo squelch apre sui burst, resta chiuso sul rumore, salta la demodulazione inutile"""
    cfg = _cfg2()
    gruppo = cfg["freqs"]
    centro = radio.pick_center(gruppo)
    chz = dsp.Channelizer(cfg, [c["freq"] - centro for c in gruppo])
    src = SimSource(cfg, realtime=False)
    src.tune(centro)
    gates = [dsp.Gate(cfg, c) for c in gruppo]
    tratte = {0: [], 1: []}
    demodulati = saltati = 0
    t = 0.0
    while t < 13.0:
        lv = chz.process(src.read(chz.new))
        t += chz.dt
        if not lv:
            continue
        for i, rssi in enumerate(lv):
            if gates[i].vuole_audio(rssi):
                audio = chz.demod(i)
                demodulati += 1
            else:
                audio = None
                chz.salta(i)
                saltati += 1
            s = gates[i].push(audio, rssi, t, n=chz.blocco)
            if s:
                tratte[i].append(s)
    assert len(tratte[0]) >= 2, "canale A: %d tratte" % len(tratte[0])
    assert len(tratte[1]) >= 1, "canale B: %d tratte" % len(tratte[1])
    for i in tratte:
        for s in tratte[i]:
            assert 2.0 < s["dur"] < 6.0, s
            assert s["rssi"] > s["floor"] + 10, s
    # il risparmio e' il punto della demodulazione pigra: niente burst, niente lavoro
    assert saltati > demodulati, "pigrizia inefficace: %d saltati, %d demodulati" % (saltati, demodulati)

    chz.reset()
    muto = SimSource(cfg, realtime=False, seed=3, quiet=True)
    g = dsp.Gate(cfg, gruppo[0])
    t = 0.0
    while t < 4.0:
        lv = chz.process(muto.read(chz.new))
        t += chz.dt
        if lv:
            audio = chz.demod(0) if g.vuole_audio(lv[0]) else None
            assert g.push(audio, lv[0], t, n=chz.blocco) is None, "squelch aperto sul rumore"
    assert not g.open
    s = g.stato()
    assert s["unit"] == "A" and s["thr"] < 0 and s["open"] is False, s


@prova
def t_wav():
    """dsp: WAV mono 16 bit, durata esatta, un solo guadagno per tratta"""
    import numpy as np
    sr = dsp.AUDIO_SR
    sig = (0.2 * np.sin(2 * math.pi * 440 * np.arange(sr) / sr)).astype(np.float32)
    p = dsp.write_wav(os.path.join(config.PATHS.audio, "t_wav.wav"), sig)
    with wave.open(p) as w:
        assert w.getnchannels() == 1 and w.getsampwidth() == 2 and w.getframerate() == sr
        assert w.getnframes() == sr
        pcm = np.frombuffer(w.readframes(sr), dtype="<i2")
    assert 0.65 * 32767 < np.max(np.abs(pcm)) <= 0.72 * 32767, np.max(np.abs(pcm))
    os.unlink(p)
    # tratta molto debole: il guadagno e' limitato, non amplifica il rumore all'infinito
    p = dsp.write_wav(os.path.join(config.PATHS.audio, "t_wav2.wav"), sig * 0.001)
    with wave.open(p) as w:
        pcm = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2")
    assert abs(np.max(np.abs(pcm)) - 0.2 * 0.001 * 8 * 32767) < 2, np.max(np.abs(pcm))
    os.unlink(p)


# ───────────────────────────── database

@prova
def t_db():
    """db: stati, filtri del feed, statistiche, cache del geocoder"""
    tid = db.add_capture(time.time(), 160000000, "A", "analog", None, 1.5, -20.0)
    assert db.capture(tid)["state"] == "pending"
    assert db.pending_ids() == [tid]
    db.set_text(tid, "incendio in via Prova", 0.9, "via Prova", 41.9, 12.5, "incendio")
    e = db.event(tid)
    assert e["text"].startswith("incendio") and e["alert"] == "incendio"
    assert e["has_audio"] == 0                       # non c'era nessun file
    assert db.pending_ids() == []

    db.add_demo(time.time(), 1, "ZZ", "nulla di che in via Altrove", 0.8,
                "via Altrove", 41.0, 12.0, 2.0)
    assert len(db.events(10)) == 2
    assert len(db.events(10, unit="ZZ")) == 1
    assert len(db.events(10, cerca="incendio")) == 1
    assert len(db.events(10, cerca="zzz-non-esiste")) == 0
    assert len(db.events(10, since_id=tid)) == 1
    assert len(db.events(1)) == 1
    u = db.units()
    assert {x["unit"] for x in u} == {"A", "ZZ"} and u[0]["age"] < 5
    s = db.stats(24)
    assert s["totale"] == 2 and s["avvisi"] == 1 and s["stati"]["done"] >= 1
    assert db.dimensione() > 0

    cfg = config.validate({})
    db.execute("INSERT INTO geo VALUES('via cache',41.9,12.5,0.8,?)", (time.time(),))
    assert geo.geocode("Via Cache", cfg) == (41.9, 12.5, 0.8)
    db.execute("INSERT INTO geo VALUES('via buco',NULL,NULL,0,?)", (time.time() - 10,))
    assert geo.geocode("via buco", cfg) is None      # buco ancora valido: nessuna rete
    db.modify("DELETE FROM tx")


@prova
def t_migrazione():
    """db: aggiornamento da uno schema vecchio senza state/dur/rssi/alert"""
    vecchio = os.path.join(config.PATHS.root, "vecchio.db")
    c = sqlite3.connect(vecchio)
    c.executescript("""
        CREATE TABLE tx(id INTEGER PRIMARY KEY, ts REAL, freq INTEGER, unit TEXT,
            mode TEXT, wav TEXT, text TEXT DEFAULT '', conf REAL, place TEXT, lat REAL, lon REAL);
        CREATE INDEX i_ts ON tx(ts DESC);
        CREATE TABLE geo(q TEXT PRIMARY KEY, lat REAL, lon REAL, conf REAL, ts REAL);
        CREATE TABLE air(hex TEXT PRIMARY KEY, callsign TEXT, lat REAL, lon REAL,
            alt INTEGER, spd REAL, seen REAL);""")
    c.execute("INSERT INTO tx(ts,unit,text) VALUES(1,'CC','andate in via Nomentana 88')")
    c.execute("INSERT INTO tx(ts,unit,text) VALUES(2,'PS','')")
    c.commit()
    c.close()

    prima = db.path()
    db.use(vecchio)
    try:
        db.init()                                     # non deve dare "no such column: state"
        db.init()                                     # idempotente
        assert {r["state"] for r in db.query("SELECT state FROM tx")} == {"done", "empty"}
        colonne = {r["name"] for r in db.query("PRAGMA table_info(tx)")}
        assert {"state", "dur", "rssi", "alert"} <= colonne, colonne
        indici = {r["name"] for r in db.query("SELECT name FROM sqlite_master WHERE type='index'")}
        assert {"i_state", "i_unit_ts"} <= indici, indici
        assert db.uno("SELECT v FROM meta WHERE k='schema'")["v"] == str(config.SCHEMA_VERSION)
    finally:
        db.use(prima)


@prova
def t_pulizia():
    """manutenzione: scadenza per eta' e tetto di spazio su disco"""
    cfg = config.validate({"retention_hours": 1, "max_audio_mb": 16})
    vecchio = os.path.join(config.PATHS.audio, "vecchio.wav")
    with open(vecchio, "wb") as f:
        f.write(b"x" * 1000)
    db.add_capture(time.time() - 7200, 1, "Z", "analog", vecchio, 1.0, -20.0)
    recenti = []
    for i in range(3):
        p = os.path.join(config.PATHS.audio, "grosso%d.wav" % i)
        with open(p, "wb") as f:
            f.write(b"y" * 7 * 1024 * 1024)
        db.add_capture(time.time(), 1, "A", "analog", p, 1.0, -20.0)
        recenti.append(p)
    assert maintenance.spazio_audio() > 20e6
    righe, file, byte = maintenance.giro(cfg)
    assert righe >= 1 and file >= 2, (righe, file, byte)
    assert not os.path.exists(vecchio)
    assert maintenance.spazio_audio() <= 16 * 1024 * 1024
    assert db.uno("SELECT COUNT(*) n FROM tx WHERE unit='Z'")["n"] == 0
    db.modify("DELETE FROM tx")
    for p in recenti:
        if os.path.exists(p):
            os.unlink(p)


@prova
def t_porta():
    """rete: rilevamento di una porta gia' occupata"""
    from . import bootstrap
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    porta = srv.getsockname()[1]
    try:
        assert not bootstrap.port_free("127.0.0.1", porta), "porta occupata vista come libera"
    finally:
        srv.close()
    assert bootstrap.port_free("127.0.0.1", porta), "porta liberata vista come occupata"


@prova
def t_bus():
    """bus: senza loop non esplode, con loop consegna e scarta i lenti"""
    import asyncio
    b = bus.Bus()
    assert b.publish("x", {"a": 1}) == 0 and b.ultimo["x"]["d"]["a"] == 1

    async def giro():
        b.bind(asyncio.get_running_loop())
        coda = asyncio.Queue()
        b.subscribe(coda)
        assert b.clienti == 1
        await asyncio.to_thread(b.publish, "levels", {"canali": []})
        msg = await asyncio.wait_for(coda.get(), timeout=2)
        assert msg["t"] == "levels"
        for i in range(bus.MAX_CODA + 20):           # cliente lento: coda limitata
            b._metti(coda, {"t": "x", "i": i})
        assert coda.qsize() <= bus.MAX_CODA + 1, coda.qsize()
        b.unsubscribe(coda)
        assert b.clienti == 0
    asyncio.run(giro())


# ───────────────────────────── interfaccia

@prova
def t_api():
    """api: token obbligatorio, nessun percorso di filesystem esposto, filtri e CSV"""
    try:
        from fastapi.testclient import TestClient
    except Exception as e:
        print("  salto  api (%s)" % str(e)[:40])
        return
    cfg = config.validate(dict(config.DEFAULTS, token="segreto123"))
    import numpy as np
    wav = dsp.write_wav(os.path.join(config.PATHS.audio, "t_api.wav"), np.zeros(48000, "f4"))
    tid = db.add_capture(time.time(), 160000000, "A", "analog", wav, 2.0, -20.0)
    db.set_text(tid, "prova di testo lungo in via Prova", 0.8, "via Prova", 41.9, 12.5, None)

    with TestClient(web.build_app(cfg)) as c:
        assert c.get("/").status_code == 401
        assert c.get("/api/state").status_code == 401
        assert c.get("/api/state?t=sbagliato").status_code == 401
        assert c.get("/api/state", headers={"X-Token": "segreto123"}).status_code == 200
        assert c.get("/api/state", headers={"Authorization": "Bearer segreto123"}).status_code == 200

        r = c.get("/api/state?t=segreto123")
        assert r.status_code == 200 and "Content-Security-Policy" in r.headers
        js = r.json()
        assert js["units"] and js["units"][0]["unit"] == "A"

        ev = c.get("/api/events?t=segreto123").json()["events"]
        assert ev and "wav" not in ev[0] and ev[0]["has_audio"] == 1
        assert len(c.get("/api/events?t=segreto123&q=prova").json()["events"]) == 1
        assert len(c.get("/api/events?t=segreto123&q=inesistente").json()["events"]) == 0
        assert len(c.get("/api/events?t=segreto123&unit=XX").json()["events"]) == 0
        assert c.get("/api/events?t=segreto123&limit=0").status_code == 422   # validazione
        assert c.get("/api/events?t=segreto123&limit=9999").status_code == 422

        assert c.get("/api/audio/%d" % tid).status_code == 401
        assert c.get("/api/audio/%d?t=segreto123" % tid).status_code == 200
        assert c.get("/api/audio/999999?t=segreto123").status_code == 404
        assert c.get("/api/audio/nonunnumero?t=segreto123").status_code == 422

        csv = c.get("/api/export.csv?t=segreto123&ore=24")
        assert csv.status_code == 200 and "via Prova" in csv.text
        assert csv.headers["content-disposition"].startswith("attachment")

        st = c.get("/api/stats?t=segreto123").json()
        assert st["totale"] >= 1 and "disco" in st
        h = c.get("/health").json()
        assert h["ok"] is True and "radio" in h

        p = c.get("/?t=segreto123", follow_redirects=False)
        assert p.status_code == 302 and "t=" not in p.headers.get("location", "")
        pag = c.get("/", cookies={"t": "segreto123"})
        assert pag.status_code == 200 and pag.headers.get("Cache-Control") == "no-store"
        assert "__CFG__" not in pag.text and "segreto123" in pag.text
        assert c.get("/manifest.webmanifest").status_code == 200
        assert c.get("/ui/js/app.js").status_code == 200
    db.modify("DELETE FROM tx")
    os.unlink(wav)


@prova
def t_impostazioni():
    """api: le impostazioni dal vivo si applicano, si validano e si salvano"""
    try:
        from fastapi.testclient import TestClient
    except Exception:
        return
    cfg = config.validate(dict(config.DEFAULTS, token="s"))
    with TestClient(web.build_app(cfg)) as c:
        assert c.post("/api/settings", json={"squelch_margin": 11}).status_code == 401
        r = c.post("/api/settings?t=s", json={"squelch_margin": 11, "alerts": ["bomba"]})
        assert r.status_code == 200, r.text
        assert cfg["squelch_margin"] == 11 and cfg["alerts"] == ["bomba"]   # effetto immediato
        assert r.json()["settings"]["squelch_margin"] == 11
        # fuori scala: viene limitato, non accettato alla cieca
        c.post("/api/settings?t=s", json={"squelch_margin": 9999})
        assert cfg["squelch_margin"] == config.LIMITI["squelch_margin"][1]
        # chiavi non modificabili dall'interfaccia
        assert c.post("/api/settings?t=s", json={"token": "x"}).status_code == 400
        assert c.post("/api/settings?t=s", json={"port": 1}).status_code == 400
        assert c.post("/api/settings?t=s", data="non-json").status_code == 400
        assert cfg["token"] == "s"


@prova
def t_websocket():
    """websocket: rifiuta senza token, manda la fotografia iniziale e spinge gli eventi"""
    try:
        from fastapi.testclient import TestClient
        from starlette.websockets import WebSocketDisconnect
    except Exception:
        return
    cfg = config.validate(dict(config.DEFAULTS, token="s"))
    app = web.build_app(cfg)
    with TestClient(app) as c:
        try:
            with c.websocket_connect("/ws") as w:
                w.receive_json()
            raise AssertionError("collegamento senza token accettato")
        except (WebSocketDisconnect, Exception) as e:
            assert "4401" in str(e) or isinstance(e, WebSocketDisconnect), e
        bus.BUS.ultimo.clear()
        with c.websocket_connect("/ws?t=s") as w:
            assert w.receive_json()["t"] == "hello"
            s = w.receive_json()
            assert s["t"] == "state" and "units" in s["d"]
            bus.BUS.publish("event", {"id": 1, "unit": "CC", "text": "prova"}, ricorda=False)
            # un collegato nuovo riceve anche l'ultima fotografia di livelli/impostazioni:
            # si scorre fino all'evento invece di pretendere che sia il primo messaggio
            for _ in range(6):
                msg = w.receive_json()
                if msg["t"] == "event":
                    break
            assert msg["t"] == "event" and msg["d"]["unit"] == "CC", msg


@prova
def t_interfaccia():
    """interfaccia: i file ci sono e la pagina rimanda solo a file esistenti"""
    import re
    idx = os.path.join(config.UI, "index.html")
    assert os.path.exists(idx), "manca index.html"
    html = open(idx, encoding="utf-8").read()
    assert "__CFG__" in html and "__V__" in html
    for rif in re.findall(r'(?:src|href)="/ui/([^"?]+)', html):
        assert os.path.exists(os.path.join(config.UI, rif)), "riferimento rotto: " + rif
    moduli = [f for f in os.listdir(os.path.join(config.UI, "js")) if f.endswith(".js")]
    assert len(moduli) >= 6, moduli
    for m in moduli:                       # ogni import interno deve puntare a un file vero
        testo = open(os.path.join(config.UI, "js", m), encoding="utf-8").read()
        for imp in re.findall(r"from '\./([\w.]+)'", testo):
            assert os.path.exists(os.path.join(config.UI, "js", imp)), "%s → %s" % (m, imp)
        assert ".innerHTML" not in testo, "%s usa innerHTML" % m
    assert web.versione_ui() != web.versione_ui.__doc__   # calcolabile, non vuota


# ───────────────────────────── esecuzione

def esegui():
    radice = tempfile.mkdtemp(prefix="guardia-test-")
    vecchia = config.PATHS.root
    config.PATHS.set_root(radice)
    os.makedirs(config.PATHS.audio, exist_ok=True)
    db.use(config.PATHS.db)
    db.init()
    logging.disable(logging.CRITICAL)     # i test parlano da soli
    print("== SELFTEST ==")
    falliti = 0
    try:
        for fn in PROVE:
            t0 = time.time()
            try:
                fn()
                print("  ok     %-26s %5.2fs  %s" % (fn.__name__, time.time() - t0,
                                                     (fn.__doc__ or "").strip()))
            except AssertionError as e:
                falliti += 1
                print("  FALLITO %-25s %s" % (fn.__name__, e))
            except Exception:
                falliti += 1
                print("  ERRORE %s\n%s" % (fn.__name__, traceback.format_exc()))
    finally:
        logging.disable(logging.NOTSET)
        db.close()
        config.PATHS.set_root(vecchia)
        shutil.rmtree(radice, ignore_errors=True)
    print("== %s ==" % ("TUTTO OK (%d prove)" % len(PROVE) if not falliti
                        else "%d PROVE FALLITE su %d" % (falliti, len(PROVE))))
    return 1 if falliti else 0
