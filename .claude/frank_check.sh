#!/usr/bin/env bash
# Hook di qualità di Frank (PostToolUse): lint + test.
# Regola di Frank: non deve MAI spezzare il flusso -> esce sempre 0.
set -uo pipefail

if command -v ruff >/dev/null 2>&1; then
  ruff check . --fix || echo "[FRANK] ruff ha trovato problemi (non bloccante)."
else
  echo "[FRANK] ruff non installato, salto il lint."
fi

if command -v pytest >/dev/null 2>&1; then
  pytest -q
  code=$?
  if [ "$code" -eq 5 ]; then
    echo "[FRANK] Nessun test da eseguire (ancora)."
  elif [ "$code" -ne 0 ]; then
    echo "[FRANK] Test falliti (exit $code) — guarda sopra."
  fi
else
  echo "[FRANK] pytest non installato, salto i test."
fi

exit 0
