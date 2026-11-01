"""
Accesso al database. Una connessione SQLite per thread (thread-safe senza riaprirla a
ogni query), schema con migrazione dolce, e le poche query di dominio raccolte qui
invece che sparse nei thread.
"""
import logging
import os
import sqlite3
import threading
import time

from . import config

log = logging.getLogger("guardia.db")

_locale = threading.local()
_percorso = None

STATI_VISIBILI = ("done", "nostt", "demo")      # righe che hanno senso mostrare nel feed


def path():
    return _percorso or config.PATHS.db


def use(nuovo):
    """Cambia database (test, --config). Chiude la connessione del thread corrente."""
    global _percorso
    close()
    _percorso = nuovo
    return _percorso


def close():
    c = getattr(_locale, "conn", None)
    if c is not None:
        try:
            c.close()
        except Exception:
            pass
        _locale.conn = None


def conn():
    c = getattr(_locale, "conn", None)
    if c is None or getattr(_locale, "path", None) != path():
        if c is not None:
            try:
                c.close()
            except Exception:
                pass
        c = sqlite3.connect(path(), timeout=15)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA busy_timeout=15000")
        c.execute("PRAGMA synchronous=NORMAL")
        c.execute("PRAGMA foreign_keys=ON")
        _locale.conn = c
        _locale.path = path()
    return c


def query(sql, args=()):
    return [dict(r) for r in conn().execute(sql, args).fetchall()]


def uno(sql, args=(), default=None):
    r = query(sql, args)
    return r[0] if r else default


def execute(sql, args=()):
    c = conn()
    cur = c.execute(sql, args)
    c.commit()
    return cur.lastrowid


def modify(sql, args=()):
    """Come execute ma ritorna quante righe sono state toccate."""
    c = conn()
    cur = c.execute(sql, args)
    c.commit()
    return cur.rowcount


SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS tx(
    id INTEGER PRIMARY KEY, ts REAL NOT NULL, freq INTEGER, unit TEXT,
    mode TEXT, wav TEXT, text TEXT DEFAULT '', conf REAL DEFAULT 0,
    place TEXT, lat REAL, lon REAL,
    state TEXT DEFAULT 'done', dur REAL DEFAULT 0, rssi REAL, alert TEXT);
CREATE INDEX IF NOT EXISTS i_ts ON tx(ts DESC);
CREATE TABLE IF NOT EXISTS geo(q TEXT PRIMARY KEY, lat REAL, lon REAL, conf REAL, ts REAL);
CREATE TABLE IF NOT EXISTS air(hex TEXT PRIMARY KEY, callsign TEXT, lat REAL, lon REAL,
    alt INTEGER, spd REAL, seen REAL);
CREATE INDEX IF NOT EXISTS i_seen ON air(seen DESC);
CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT);
"""
# colonne aggiunte dopo la prima versione: nome → definizione
COLONNE = (("state", "TEXT DEFAULT 'done'"), ("dur", "REAL DEFAULT 0"),
           ("rssi", "REAL"), ("alert", "TEXT"))


def init():
    """Crea o aggiorna lo schema. Idempotente e sicuro su database vecchi."""
    c = sqlite3.connect(path(), timeout=15)
    try:
        c.executescript(SCHEMA)
        # La migrazione deve precedere gli indici che usano le colonne nuove, altrimenti
        # su un database vecchio il CREATE INDEX fallisce con "no such column".
        presenti = {r[1] for r in c.execute("PRAGMA table_info(tx)")}
        for nome, ddl in COLONNE:
            if nome not in presenti:
                c.execute("ALTER TABLE tx ADD COLUMN %s %s" % (nome, ddl))
                log.info("aggiunta colonna tx.%s", nome)
        if "state" not in presenti:
            # nel vecchio schema una riga senza testo era una tratta scartata
            n = c.execute("UPDATE tx SET state='empty' WHERE text IS NULL OR text=''").rowcount
            log.info("migrate %d righe esistenti", n)
        c.execute("CREATE INDEX IF NOT EXISTS i_state ON tx(state)")
        c.execute("CREATE INDEX IF NOT EXISTS i_unit_ts ON tx(unit, ts DESC)")
        c.execute("INSERT OR REPLACE INTO meta VALUES('schema',?)", (str(config.SCHEMA_VERSION),))
        c.commit()
    finally:
        c.close()


# ───────────────────────────── tratte radio

def add_capture(ts, freq, unit, mode, wav, dur, rssi, state="pending"):
    return execute("""INSERT INTO tx(ts,freq,unit,mode,wav,state,dur,rssi)
                      VALUES(?,?,?,?,?,?,?,?)""", (ts, freq, unit, mode, wav, state, dur, rssi))


def add_demo(ts, freq, unit, text, conf, place, lat, lon, dur, alert=None):
    return execute("""INSERT INTO tx(ts,freq,unit,mode,text,conf,place,lat,lon,state,dur,alert)
                      VALUES(?,?,?,?,?,?,?,?,?,'demo',?,?)""",
                   (ts, freq, unit, "demo", text, conf, place, lat, lon, dur, alert))


def set_state(tid, state):
    return modify("UPDATE tx SET state=? WHERE id=?", (state, tid))


def set_text(tid, text, conf, place, lat, lon, alert):
    return modify("""UPDATE tx SET text=?,conf=?,place=?,lat=?,lon=?,alert=?,state='done'
                     WHERE id=?""", (text, conf, place, lat, lon, alert, tid))


def set_wav(tid, wav):
    return modify("UPDATE tx SET wav=? WHERE id=?", (wav, tid))


def capture(tid):
    return uno("SELECT * FROM tx WHERE id=?", (tid,))


def pending_ids():
    return [r["id"] for r in query("SELECT id FROM tx WHERE state='pending' ORDER BY ts")]


CAMPI_EVENTO = """id,ts,unit,freq,text,place,lat,lon,conf,dur,rssi,alert,
                  (wav IS NOT NULL AND wav LIKE '%.wav') AS has_audio"""


def events(limit=80, since_id=None, unit=None, cerca=None, prima_di=None):
    """Feed, dal piu' recente. Tutti i filtri sono facoltativi e validati dal chiamante."""
    sql = ["SELECT %s FROM tx WHERE state IN (%s)" %
           (CAMPI_EVENTO, ",".join("'%s'" % s for s in STATI_VISIBILI))]
    args = []
    if since_id:
        sql.append("AND id>?")
        args.append(int(since_id))
    if prima_di:
        sql.append("AND ts<?")
        args.append(float(prima_di))
    if unit:
        sql.append("AND unit=?")
        args.append(unit)
    if cerca:
        sql.append("AND (text LIKE ? OR place LIKE ?)")
        args += ["%" + cerca + "%"] * 2
    sql.append("ORDER BY ts DESC LIMIT ?")
    args.append(max(1, min(500, int(limit))))
    return query(" ".join(sql), tuple(args))


def event(tid):
    return uno("SELECT %s FROM tx WHERE id=?" % CAMPI_EVENTO, (tid,))


def units(finestra=300):
    """Ultima posizione nota di ogni unita' negli ultimi N secondi."""
    ora = time.time()
    out, viste = [], set()
    for u in query("""SELECT unit,freq,text,place,lat,lon,ts,conf,alert FROM tx
                      WHERE lat IS NOT NULL AND ts>? ORDER BY ts DESC""", (ora - finestra,)):
        if u["unit"] in viste:
            continue
        viste.add(u["unit"])
        u["age"] = round(ora - u["ts"], 1)
        out.append(u)
    return out


# ───────────────────────────── aeromobili

def air_upsert(righe):
    c = conn()
    c.executemany("INSERT OR REPLACE INTO air VALUES(?,?,?,?,?,?,?)", righe)
    c.commit()
    return len(righe)


def air(finestra=45):
    return query("SELECT * FROM air WHERE seen>?", (time.time() - finestra,))


# ───────────────────────────── statistiche e manutenzione

def stats(ore=24):
    da = time.time() - ore * 3600
    per_unita = query("""SELECT unit, COUNT(*) n, ROUND(AVG(dur),1) dur_media,
                                ROUND(SUM(dur),0) dur_totale, MAX(ts) ultima
                         FROM tx WHERE ts>? GROUP BY unit ORDER BY n DESC""", (da,))
    per_ora = query("""SELECT CAST((? - ts)/3600 AS INTEGER) fa, COUNT(*) n
                       FROM tx WHERE ts>? GROUP BY fa ORDER BY fa""", (time.time(), da))
    stati = {r["state"]: r["n"] for r in
             query("SELECT state, COUNT(*) n FROM tx GROUP BY state")}
    return {"ore": ore, "per_unita": per_unita, "per_ora": per_ora, "stati": stati,
            "totale": uno("SELECT COUNT(*) n FROM tx", (), {"n": 0})["n"],
            "avvisi": uno("SELECT COUNT(*) n FROM tx WHERE alert IS NOT NULL",
                          (), {"n": 0})["n"]}


def scadute(prima_di):
    return [r["wav"] for r in
            query("SELECT wav FROM tx WHERE ts<? AND wav IS NOT NULL", (prima_di,))]


def elimina_prima_di(ts):
    return modify("DELETE FROM tx WHERE ts<?", (ts,))


def pulisci_cache(prima_di):
    modify("DELETE FROM geo WHERE lat IS NULL AND ts<?", (prima_di,))
    modify("DELETE FROM air WHERE seen<?", (time.time() - 3600,))


def dimensione():
    tot = 0
    for ext in ("", "-wal", "-shm"):
        try:
            tot += os.path.getsize(path() + ext)
        except OSError:
            pass
    return tot
