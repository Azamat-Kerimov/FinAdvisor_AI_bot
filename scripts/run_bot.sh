#!/usr/bin/env bash
# Запуск Telegram-бота (подписка + Web App)
# Требуется .env с BOT_TOKEN, DB_*

set -e
cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
    echo "Файл .env не найден. Скопируйте .env.example в .env и заполните."
    exit 1
fi

echo "Запуск бота (polling)..."
exec python bot.py
