#!/usr/bin/env bash
# Запуск API (вызывается systemd, venv в каталоге проекта)

set -e
cd "$(dirname "$0")/.."
. venv/bin/activate
exec python -m uvicorn api:app --host 0.0.0.0 --port 8000
