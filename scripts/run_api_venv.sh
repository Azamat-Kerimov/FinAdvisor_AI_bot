#!/usr/bin/env bash
# Запуск API с автоопределением venv или .venv (для systemd)

set -e
cd "$(dirname "$0")/.."

if [ -f venv/bin/activate ]; then
    . venv/bin/activate
elif [ -f .venv/bin/activate ]; then
    . .venv/bin/activate
else
    echo "Ошибка: не найден venv/bin/activate или .venv/bin/activate в $(pwd)" >&2
    exit 1
fi

exec python -m uvicorn api:app --host 0.0.0.0 --port 8000
