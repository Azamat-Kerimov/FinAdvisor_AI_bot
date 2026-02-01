#!/usr/bin/env bash
# Запуск Telegram-бота (подписка + Web App)
# Требуется .env с BOT_TOKEN, DB_*

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

echo "Запуск бота (polling)..."
exec "$PYTHON" bot.py
