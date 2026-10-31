#!/usr/bin/env python3
"""Salva lo stato di Frank a fine sessione."""
import datetime
import json
import pathlib

STATE = pathlib.Path(".claude/frank_state.json")
SEED = pathlib.Path(".claude/frank_state.seed.json")
LOG = pathlib.Path(".claude/frank_history.log")


def _load() -> dict:
    for path in (STATE, SEED):
        if path.exists():
            return json.loads(path.read_text())
    return {}


def remember() -> None:
    s = _load()
    s.setdefault("history", []).append(
        {
            "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "note": "sessione chiusa",
        }
    )
    s["last_run"] = s["history"][-1]["ts"]
    STATE.write_text(json.dumps(s, indent=2))
    with LOG.open("a") as fh:
        fh.write(f"{s['last_run']} — Frank si è ricordato.\n")


if __name__ == "__main__":
    remember()
