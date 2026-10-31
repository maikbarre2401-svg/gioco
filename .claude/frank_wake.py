#!/usr/bin/env python3
"""Hook UserPromptSubmit / SessionStart: inietta lo stato di Frank.

Un hook non deve mai far crashare la sessione: qualsiasi errore viene
catturato e riportato come testo, uscendo sempre con codice 0.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import frank_core as core

if __name__ == "__main__":
    try:
        print(core.wake())
    except Exception as exc:  # noqa: BLE001
        print(f"[FRANK] risveglio fallito: {exc}")
    sys.exit(0)
