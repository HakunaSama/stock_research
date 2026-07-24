#!/usr/bin/env bash
# Backend container entrypoint.
#
# 1. Seed two demo runs (000100 / 002185) on first boot so the UI has real
#    artifacts to show even before anyone triggers an online research run.
#    Uses the deterministic FakeLLM — no API key needed, safe to run offline.
#    (K-line still tries the live free source; it degrades gracefully.)
# 2. Launch uvicorn serving the FastAPI app.
set -euo pipefail

DATA_DIR="${STOCK_DATA_DIR:-/data}"

# Seed only if the data dir has no run artifacts yet (idempotent across restarts).
if ! ls "${DATA_DIR}"/*/context.json >/dev/null 2>&1; then
  echo "[entrypoint] seeding demo runs into ${DATA_DIR} ..."
  python3 seed_runs.py "${DATA_DIR}" || echo "[entrypoint] seed failed (continuing; UI will show empty)"
else
  echo "[entrypoint] existing runs found in ${DATA_DIR}, skipping seed"
fi

echo "[entrypoint] starting uvicorn on 0.0.0.0:8000 ..."
exec uvicorn webapp.app:app --host 0.0.0.0 --port 8000 --workers 1
