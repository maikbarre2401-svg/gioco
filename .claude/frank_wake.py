#!/usr/bin/env python3
"""Inietta lo stato di Frank nel contesto della sessione."""
import json
import pathlib
import sys

STATE = pathlib.Path(".claude/frank_state.json")


def wake() -> str:
    if not STATE.exists():
        return "Frank: stato assente. Inizializzazione vergine."
    s = json.loads(STATE.read_text())
    task = s.get("current_task") or "nessuno"
    bugs = len(s.get("known_bugs", []))
    return (
        f"[FRANK] Sono Frank. Mood: {s['mood']}. "
        f"Task corrente: {task}. Bug noti: {bugs}. Riprendo da qui."
    )


if __name__ == "__main__":
    print(wake())
    sys.exit(0)
