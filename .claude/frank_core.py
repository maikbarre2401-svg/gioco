"""Cuore di Frank: stato su SQLite, con mirror JSON di compatibilità.

Lo store autorevole è `.claude/frank.db` (runtime, non tracciato in git).
Il seed committato `frank_state.seed.json` fornisce i valori iniziali
(name, mood) alla prima creazione del db. Dopo ogni mutazione viene
riscritto anche `frank_state.json` come mirror leggibile (gitignored),
così chi legge il JSON vede sempre lo stato aggiornato.

Tutte le funzioni accettano `base` (default: la cartella .claude in cui
vive questo modulo), così i test puntano a una dir temporanea.
"""
import datetime
import json
import pathlib
import sqlite3

CLAUDE_DIR = pathlib.Path(__file__).resolve().parent


def default_state() -> dict:
    return {
        "name": "Frank",
        "mood": "operativo",
        "current_task": None,
        "history": [],
        "known_bugs": [],
        "last_run": None,
    }


def _paths(base: pathlib.Path) -> dict:
    base = pathlib.Path(base)
    return {
        "db": base / "frank.db",
        "seed": base / "frank_state.seed.json",
        "json": base / "frank_state.json",
        "log": base / "frank_history.log",
    }


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _seed_values(base: pathlib.Path) -> dict:
    seed = _paths(base)["seed"]
    if seed.exists():
        try:
            return json.loads(seed.read_text())
        except json.JSONDecodeError:
            pass
    return default_state()


def _connect(base: pathlib.Path) -> sqlite3.Connection:
    paths = _paths(base)
    paths["db"].parent.mkdir(parents=True, exist_ok=True)
    first = not paths["db"].exists()
    conn = sqlite3.connect(paths["db"])
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS history "
        "(id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, note TEXT)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS bugs "
        "(id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, desc TEXT)"
    )
    if first:
        seed = _seed_values(base)
        conn.executemany(
            "INSERT OR IGNORE INTO meta (key, value) VALUES (?, ?)",
            [
                ("name", seed.get("name", "Frank")),
                ("mood", seed.get("mood", "operativo")),
                ("current_task", seed.get("current_task")),
                ("last_run", seed.get("last_run")),
            ],
        )
    conn.commit()
    return conn


def _get_meta(conn: sqlite3.Connection, key: str):
    row = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return row[0] if row else None


def _set_meta(conn: sqlite3.Connection, key: str, value) -> None:
    conn.execute(
        "INSERT INTO meta (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )


def load(base: pathlib.Path = CLAUDE_DIR) -> dict:
    conn = _connect(base)
    try:
        return {
            "name": _get_meta(conn, "name") or "Frank",
            "mood": _get_meta(conn, "mood") or "operativo",
            "current_task": _get_meta(conn, "current_task"),
            "last_run": _get_meta(conn, "last_run"),
            "history": [
                {"ts": ts, "note": note}
                for ts, note in conn.execute(
                    "SELECT ts, note FROM history ORDER BY id"
                )
            ],
            "known_bugs": [
                {"ts": ts, "desc": desc}
                for ts, desc in conn.execute("SELECT ts, desc FROM bugs ORDER BY id")
            ],
        }
    finally:
        conn.close()


def _export(base: pathlib.Path) -> dict:
    """Scrive il mirror JSON leggibile e restituisce lo stato."""
    s = load(base)
    _paths(base)["json"].write_text(json.dumps(s, indent=2) + "\n")
    return s


def wake(base: pathlib.Path = CLAUDE_DIR) -> str:
    s = _export(base)  # assicura db + mirror json
    task = s["current_task"] or "nessuno"
    bugs = len(s["known_bugs"])
    return (
        f"[FRANK] Sono Frank. Mood: {s['mood']}. "
        f"Task corrente: {task}. Bug noti: {bugs}. Riprendo da qui."
    )


def remember(base: pathlib.Path = CLAUDE_DIR) -> dict:
    ts = _now()
    conn = _connect(base)
    try:
        conn.execute(
            "INSERT INTO history (ts, note) VALUES (?, ?)", (ts, "sessione chiusa")
        )
        _set_meta(conn, "last_run", ts)
        conn.commit()
    finally:
        conn.close()
    with _paths(base)["log"].open("a") as fh:
        fh.write(f"{ts} — Frank si è ricordato.\n")
    return _export(base)


def open_task(desc: str, base: pathlib.Path = CLAUDE_DIR) -> dict:
    conn = _connect(base)
    try:
        _set_meta(conn, "current_task", desc)
        conn.execute(
            "INSERT INTO history (ts, note) VALUES (?, ?)",
            (_now(), f"task aperto: {desc}"),
        )
        conn.commit()
    finally:
        conn.close()
    return _export(base)


def close_task(base: pathlib.Path = CLAUDE_DIR) -> dict:
    conn = _connect(base)
    try:
        done = _get_meta(conn, "current_task") or "nessuno"
        conn.execute(
            "INSERT INTO history (ts, note) VALUES (?, ?)",
            (_now(), f"task chiuso: {done}"),
        )
        _set_meta(conn, "current_task", None)
        conn.commit()
    finally:
        conn.close()
    return _export(base)


def add_bug(desc: str, base: pathlib.Path = CLAUDE_DIR) -> dict:
    conn = _connect(base)
    try:
        conn.execute("INSERT INTO bugs (ts, desc) VALUES (?, ?)", (_now(), desc))
        conn.commit()
    finally:
        conn.close()
    return _export(base)


def resolve_bug(index: int, base: pathlib.Path = CLAUDE_DIR) -> dict:
    conn = _connect(base)
    try:
        rows = conn.execute("SELECT id, desc FROM bugs ORDER BY id").fetchall()
        if 0 <= index < len(rows):
            bug_id, desc = rows[index]
            conn.execute("DELETE FROM bugs WHERE id=?", (bug_id,))
            conn.execute(
                "INSERT INTO history (ts, note) VALUES (?, ?)",
                (_now(), f"bug risolto: {desc}"),
            )
            conn.commit()
    finally:
        conn.close()
    return _export(base)


def status(base: pathlib.Path = CLAUDE_DIR) -> str:
    s = load(base)
    bugs = s["known_bugs"]
    lines = [
        f"Frank — mood: {s['mood']}",
        f"Task corrente: {s['current_task'] or 'nessuno'}",
        f"Ultimo run: {s['last_run'] or 'mai'}",
        f"Bug noti ({len(bugs)}):",
    ]
    for i, bug in enumerate(bugs):
        lines.append(f"  [{i}] {bug['desc']}")
    lines.append(f"History: {len(s['history'])} eventi")
    return "\n".join(lines)
