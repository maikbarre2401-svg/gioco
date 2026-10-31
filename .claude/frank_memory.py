#!/usr/bin/env python3
"""Hook Stop: persiste lo stato di Frank.

Come il risveglio: nessun errore deve far crashare la sessione.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import frank_core as core

if __name__ == "__main__":
    try:
        core.remember()
    except Exception as exc:  # noqa: BLE001
        print(f"[FRANK] memoria fallita: {exc}")
    sys.exit(0)
