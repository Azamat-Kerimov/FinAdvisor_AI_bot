#!/usr/bin/env bash
# Запуск API (FastAPI + раздача React из frontend/dist)
# Перед первым запуском выполните: scripts/build_frontend.sh

set -e
cd "$(dirname "$0")/.."

if [ ! -f frontend/dist/index.html ]; then
    echo "Фронт не собран. Запустите: scripts/build_frontend.sh"
    exit 1
fi

echo "Запуск API на http://0.0.0.0:8000"
exec python -m uvicorn api:app --host 0.0.0.0 --port 8000
