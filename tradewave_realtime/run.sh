#!/usr/bin/env bash
# Dev launcher for TradeWave Realtime.
set -e
cd "$(dirname "$0")"
source .venv/bin/activate
export FLASK_APP=run.py
# Idempotent seed (admins + starter knowledge), then launch.
flask seed || true
exec python run.py
