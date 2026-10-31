"""Cuore di Frank: stato, memoria, task e bug.

Tutte le funzioni accettano `base` (default: la cartella .claude in cui
vive questo modulo), così i test possono puntare a una dir temporanea.
Lo stato runtime (frank_state.json) non è tracciato in git: il seed
committato (frank_state.seed.json) è la base da cui ripartire.
"""
import datetime
import json
import pathlib

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


def _paths(base: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path, pathlib.Path]:
    base = pathlib.Path(base)
    return (
        base / "frank_state.json",
        base / "frank_state.seed.json",
        base / "frank_history.log",
    )


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def load(base: pathlib.Path = CLAUDE_DIR) -> dict:
    """Stato runtime se c'è, altrimenti il seed, altrimenti default."""
    state, seed, _ = _paths(base)
    for path in (state, seed):
        if path.exists():
            try:
                return json.loads(path.read_text())
            except json.JSONDecodeError:
                continue
    return default_state()


def save(state: dict, base: pathlib.Path = CLAUDE_DIR) -> None:
    state_path, _, _ = _paths(base)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2) + "\n")


def _log(line: str, base: pathlib.Path = CLAUDE_DIR) -> None:
    _, _, log = _paths(base)
    with log.open("a") as fh:
        fh.write(line + "\n")


def wake(base: pathlib.Path = CLAUDE_DIR) -> str:
    state_path, _, _ = _paths(base)
    s = load(base)
    if not state_path.exists():
        save(s, base)  # materializza lo stato (da seed o default)
    task = s.get("current_task") or "nessuno"
    bugs = len(s.get("known_bugs", []))
    return (
        f"[FRANK] Sono Frank. Mood: {s.get('mood', 'operativo')}. "
        f"Task corrente: {task}. Bug noti: {bugs}. Riprendo da qui."
    )


def remember(base: pathlib.Path = CLAUDE_DIR) -> dict:
    s = load(base)
    s.setdefault("history", []).append({"ts": _now(), "note": "sessione chiusa"})
    s["last_run"] = s["history"][-1]["ts"]
    save(s, base)
    _log(f"{s['last_run']} — Frank si è ricordato.", base)
    return s


def open_task(desc: str, base: pathlib.Path = CLAUDE_DIR) -> dict:
    s = load(base)
    s["current_task"] = desc
    s.setdefault("history", []).append({"ts": _now(), "note": f"task aperto: {desc}"})
    save(s, base)
    return s


def close_task(base: pathlib.Path = CLAUDE_DIR) -> dict:
    s = load(base)
    done = s.get("current_task") or "nessuno"
    s.setdefault("history", []).append({"ts": _now(), "note": f"task chiuso: {done}"})
    s["current_task"] = None
    save(s, base)
    return s


def add_bug(desc: str, base: pathlib.Path = CLAUDE_DIR) -> dict:
    s = load(base)
    s.setdefault("known_bugs", []).append({"ts": _now(), "desc": desc})
    save(s, base)
    return s


def resolve_bug(index: int, base: pathlib.Path = CLAUDE_DIR) -> dict:
    s = load(base)
    bugs = s.setdefault("known_bugs", [])
    if 0 <= index < len(bugs):
        removed = bugs.pop(index)
        desc = removed.get("desc", removed) if isinstance(removed, dict) else removed
        s.setdefault("history", []).append(
            {"ts": _now(), "note": f"bug risolto: {desc}"}
        )
    save(s, base)
    return s


def _bug_desc(bug) -> str:
    return bug.get("desc", str(bug)) if isinstance(bug, dict) else str(bug)


def status(base: pathlib.Path = CLAUDE_DIR) -> str:
    s = load(base)
    bugs = s.get("known_bugs", [])
    lines = [
        f"Frank — mood: {s.get('mood', 'operativo')}",
        f"Task corrente: {s.get('current_task') or 'nessuno'}",
        f"Ultimo run: {s.get('last_run') or 'mai'}",
        f"Bug noti ({len(bugs)}):",
    ]
    for i, bug in enumerate(bugs):
        lines.append(f"  [{i}] {_bug_desc(bug)}")
    lines.append(f"History: {len(s.get('history', []))} eventi")
    return "\n".join(lines)
