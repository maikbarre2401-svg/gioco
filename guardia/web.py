"""
Interfaccia HTTP: API, WebSocket e pagina.

Scelte di fondo:
  * un token obbligatorio su tutto, confronto a tempo costante, freno sui tentativi;
  * nessun percorso del filesystem esce dalle API;
  * gli aggiornamenti vanno in push via WebSocket (una sola query per tutti i client,
    invece di una per client ogni tre secondi), con il polling come ripiego;
  * la pagina e i suoi file stanno su disco, non dentro una stringa Python.
"""
import asyncio
import csv
from contextlib import asynccontextmanager
import hashlib
import hmac
import io
import json
import logging
import os
import time

from . import config, db
from .bus import BUS
from .runtime import STATO, STOP

log = logging.getLogger("guardia.web")

CSP = ("default-src 'self'; "
       "script-src 'self' 'unsafe-inline' https://unpkg.com https://cdnjs.cloudflare.com; "
       "style-src 'self' 'unsafe-inline' https://unpkg.com; "
       "worker-src blob:; child-src blob:; img-src 'self' data: blob: https:; "
       "connect-src 'self' https: ws: wss:; media-src 'self'; frame-ancestors 'none'; "
       "base-uri 'none'; form-action 'none'")

# chiavi modificabili dall'interfaccia mentre il programma gira: tutte prese dai thread
# a ogni giro, quindi hanno effetto immediato senza riavviare nulla
LIVE_KEYS = {"squelch_mode", "squelch", "squelch_margin", "squelch_hysteresis", "hang",
             "preroll", "min_voice", "max_seg", "dwell", "alerts", "basemap",
             "adsb_interval", "retention_hours", "max_audio_mb", "geocode", "stt"}
PERIODO_STATO = 3.0


def versione_ui():
    """Impronta dei file dell'interfaccia: serve a invalidare la cache del browser."""
    h = hashlib.sha1()
    for base, _, files in os.walk(config.UI):
        for f in sorted(files):
            p = os.path.join(base, f)
            try:
                st = os.stat(p)
                h.update(("%s%d%d" % (f, st.st_size, st.st_mtime_ns)).encode())
            except OSError:
                pass
    return h.hexdigest()[:10]


def build_app(cfg, stato=None):
    from fastapi import FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
    from fastapi.responses import (FileResponse, HTMLResponse, JSONResponse,
                                   RedirectResponse, StreamingResponse)
    from fastapi.staticfiles import StaticFiles

    stato = stato or STATO
    ver = versione_ui()
    tentativi = {}

    @asynccontextmanager
    async def lifespan(app):
        BUS.bind(asyncio.get_running_loop())
        task = asyncio.create_task(diffondi_stato())
        log.info("interfaccia pronta")
        try:
            yield
        finally:
            task.cancel()

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan,
                  title="guardia")

    # ───────────────────────────── sicurezza

    def autorizzato(req):
        tok = (req.query_params.get("t") or req.headers.get("x-token")
               or req.cookies.get("t") or "")
        auth = req.headers.get("authorization") or ""
        if not tok and auth.lower().startswith("bearer "):
            tok = auth[7:].strip()
        return bool(cfg["token"]) and hmac.compare_digest(str(tok), str(cfg["token"]))

    def esigi(req):
        if autorizzato(req):
            return
        ip = req.client.host if req.client else "?"
        tentativi[ip] = tentativi.get(ip, 0) + 1
        if tentativi[ip] > 5:
            time.sleep(0.5)        # freno elementare contro i tentativi a forza bruta
        raise HTTPException(401, "token mancante o errato")

    @app.middleware("http")
    async def intestazioni(request, call_next):
        try:
            resp = await call_next(request)
        except Exception:
            log.exception("errore servendo %s", request.url.path)
            resp = JSONResponse({"errore": "errore interno"}, status_code=500)
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["Content-Security-Policy"] = CSP
        if request.url.path == "/":
            # la pagina porta dentro il token: non deve finire in nessuna cache
            resp.headers["Cache-Control"] = "no-store"
        return resp

    # ───────────────────────────── pagina e file statici

    if os.path.isdir(config.UI):
        app.mount("/ui", StaticFiles(directory=config.UI), name="ui")

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request):
        if request.query_params.get("t"):
            if not autorizzato(request):
                return HTMLResponse(pagina_token(), status_code=401)
            r = RedirectResponse("/", status_code=302)
            r.set_cookie("t", request.query_params["t"], max_age=86400 * 365,
                         httponly=True, samesite="lax", path="/")
            return r
        if not autorizzato(request):
            return HTMLResponse(pagina_token(), status_code=401)
        try:
            with open(os.path.join(config.UI, "index.html"), encoding="utf-8") as f:
                html = f.read()
        except OSError as e:
            log.error("pagina non leggibile: %s", e)
            raise HTTPException(500, "interfaccia non installata")
        # il token entra nella pagina solo per chi e' gia' autenticato
        return HTMLResponse(html.replace("__CFG__", json.dumps({
            "lon": cfg["lon"], "lat": cfg["lat"], "zoom": 15, "basemap": cfg["basemap"],
            "token": cfg["token"], "mode": stato.mode, "version": ver,
        })).replace("__V__", ver))

    @app.get("/manifest.webmanifest")
    def manifest():
        return JSONResponse({
            "name": "Guardia — sala operativa", "short_name": "Guardia",
            "start_url": "/", "display": "standalone", "orientation": "any",
            "background_color": "#060a0f", "theme_color": "#060a0f",
            "icons": [{"src": "/ui/icon.svg", "sizes": "any", "type": "image/svg+xml",
                       "purpose": "any maskable"}]},
            headers={"Cache-Control": "public, max-age=86400"})

    # ───────────────────────────── dati

    def istantanea():
        return {"now": time.time(), "mode": stato.mode,
                "units": db.units(), "air": db.air(),
                "levels": (BUS.ultimo.get("levels") or {}).get("d"),
                "clients": BUS.clienti}

    @app.get("/api/state")
    def api_state(request: Request):
        esigi(request)
        return istantanea()

    @app.get("/api/events")
    def api_events(request: Request, limit: int = Query(80, ge=1, le=500),
                   since_id: int = Query(0, ge=0), unit: str = Query("", max_length=12),
                   q: str = Query("", max_length=80), before: float = Query(0, ge=0)):
        esigi(request)
        return {"events": db.events(limit=limit, since_id=since_id or None,
                                    unit=unit.strip() or None, cerca=q.strip() or None,
                                    prima_di=before or None)}

    @app.get("/api/stats")
    def api_stats(request: Request, ore: int = Query(24, ge=1, le=720)):
        esigi(request)
        s = db.stats(ore)
        from . import maintenance
        s["disco"] = {"audio_mb": round(maintenance.spazio_audio() / 1e6, 1),
                      "db_mb": round(db.dimensione() / 1e6, 1),
                      "tetto_mb": cfg["max_audio_mb"]}
        return s

    @app.get("/api/audio/{tid}")
    def api_audio(tid: int, request: Request):
        esigi(request)
        r = db.uno("SELECT wav FROM tx WHERE id=?", (tid,))
        p = r["wav"] if r else None
        if not p or not p.endswith(".wav") or not os.path.exists(p):
            raise HTTPException(404)
        # difesa in profondita': solo file dentro la cartella audio
        if os.path.realpath(p) != os.path.join(os.path.realpath(config.PATHS.audio),
                                               os.path.basename(p)):
            raise HTTPException(404)
        return FileResponse(p, media_type="audio/wav",
                            headers={"Cache-Control": "private, max-age=3600"})

    @app.get("/api/export.csv")
    def api_export(request: Request, ore: int = Query(24, ge=1, le=8760),
                   unit: str = Query("", max_length=12)):
        esigi(request)
        da, filtro = time.time() - ore * 3600, unit.strip()
        righe = db.query(
            "SELECT ts,unit,freq,mode,dur,rssi,conf,alert,place,lat,lon,text FROM tx "
            "WHERE ts>? AND state IN ('done','nostt','demo') "
            + ("AND unit=? " if filtro else "") + "ORDER BY ts DESC",
            (da, filtro) if filtro else (da,))

        def genera():
            buf = io.StringIO()
            w = csv.writer(buf, delimiter=";")
            w.writerow(["data", "unita", "frequenza_mhz", "modo", "durata_s", "dbfs",
                        "confidenza", "allarme", "luogo", "lat", "lon", "testo"])
            for r in righe:
                w.writerow([time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(r["ts"])),
                            r["unit"], "%.4f" % ((r["freq"] or 0) / 1e6), r["mode"],
                            r["dur"], r["rssi"], r["conf"], r["alert"] or "",
                            r["place"] or "", r["lat"] or "", r["lon"] or "",
                            (r["text"] or "").replace("\n", " ")])
                yield buf.getvalue()
                buf.seek(0)
                buf.truncate(0)

        nome = time.strftime("guardia-%Y%m%d-%H%M.csv")
        return StreamingResponse(genera(), media_type="text/csv; charset=utf-8",
                                 headers={"Content-Disposition": 'attachment; filename="%s"' % nome})

    @app.get("/api/settings")
    def api_settings(request: Request):
        esigi(request)
        return {k: cfg[k] for k in sorted(LIVE_KEYS) if k in cfg}

    @app.post("/api/settings")
    async def api_settings_set(request: Request):
        esigi(request)
        try:
            dati = await request.json()
            if not isinstance(dati, dict):
                raise ValueError("serve un oggetto")
        except Exception as e:
            raise HTTPException(400, "JSON non valido: %s" % e)
        ignote = set(dati) - LIVE_KEYS
        if ignote:
            raise HTTPException(400, "chiavi non modificabili: %s" % ", ".join(sorted(ignote)))
        prova = dict(cfg)
        prova.update(dati)
        config.validate(prova)
        cambiate = {k: prova[k] for k in dati if prova[k] != cfg.get(k)}
        cfg.update({k: prova[k] for k in dati})          # i thread leggono questo dizionario
        try:
            su_disco = config.load()
            su_disco.update({k: cfg[k] for k in LIVE_KEYS if k in cfg})
            su_disco["token"] = cfg["token"]
            config.save(su_disco)
        except Exception as e:
            log.warning("impostazioni non salvate su disco: %s", e)
        if cambiate:
            log.info("impostazioni aggiornate: %s", cambiate)
            BUS.publish("settings", {k: cfg[k] for k in sorted(LIVE_KEYS) if k in cfg})
        return {"ok": True, "cambiate": cambiate,
                "settings": {k: cfg[k] for k in sorted(LIVE_KEYS) if k in cfg}}

    @app.get("/health")
    def health():
        return {"ok": True, "version": ver, "mode": stato.mode, "uptime": stato.uptime(),
                "radio": stato.radio, "stt": stato.stt, "clients": BUS.clienti,
                "db": db.stats(24)["stati"]}

    # ───────────────────────────── push

    async def diffondi_stato():
        """Una sola fotografia per tutti i collegati, invece di una query per client."""
        while not STOP.is_set():
            try:
                if BUS.clienti:
                    dati = await asyncio.to_thread(istantanea)
                    BUS.publish("state", dati)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log.debug("diffusione stato: %s", e)
            await asyncio.sleep(PERIODO_STATO)

    @app.websocket("/ws")
    async def ws(sock: WebSocket):
        tok = sock.query_params.get("t") or sock.cookies.get("t") or ""
        if not (cfg["token"] and hmac.compare_digest(str(tok), str(cfg["token"]))):
            await sock.close(code=4401)
            return
        await sock.accept()
        coda = asyncio.Queue()
        BUS.subscribe(coda)
        try:
            await sock.send_json({"t": "hello", "ts": time.time(),
                                  "d": {"mode": stato.mode, "version": ver}})
            stato_iniziale = await asyncio.to_thread(istantanea)
            await sock.send_json({"t": "state", "ts": time.time(), "d": stato_iniziale})
            for tipo in ("levels", "settings"):
                if tipo in BUS.ultimo:
                    await sock.send_json(BUS.ultimo[tipo])
            while True:
                try:
                    msg = await asyncio.wait_for(coda.get(), timeout=20)
                except asyncio.TimeoutError:
                    await sock.send_json({"t": "ping", "ts": time.time(), "d": None})
                    continue
                await sock.send_json(msg)
        except WebSocketDisconnect:
            pass
        except Exception as e:
            log.debug("websocket chiuso: %s", e)
        finally:
            BUS.unsubscribe(coda)

    return app


def pagina_token():
    return """<!doctype html><meta charset="utf-8"><title>Guardia</title>
<body style="background:#060a0f;color:#e8eef6;font:15px system-ui;padding:40px">
<h2 style="letter-spacing:.1em">GUARDIA</h2>
<p>Serve il token di accesso: apri l'indirizzo con <code>?t=IL_TUO_TOKEN</code>.</p>
<p style="color:#64748b">Lo trovi stampato all'avvio del programma e in <code>guardia.json</code>.</p>
</body>"""
