#!/usr/bin/env bash
# Сборка фронта и запуск API (React + FastAPI)
# Используйте для проверки сайта на Linux-сервере

set -e
cd "$(dirname "$0")/.."
PYTHON="${PYTHON:-$(command -v python3 || command -v python)}"

if [ ! -f .env ]; then
    echo "Файл .env не найден. Скопируйте .env.example в .env и заполните."
    exit 1
fi

if [ -z "$PYTHON" ]; then
    echo "Python не найден. Установите python3 или активируйте venv."
    exit 1
fi

echo "Сборка фронта..."
bash scripts/build_frontend.sh

echo "Запуск API на http://0.0.0.0:8000"
exec "$PYTHON" -m uvicorn api:app --host 0.0.0.0 --port 8000
