#!/usr/bin/env bash
# Запуск бота (вызывается systemd, venv в каталоге проекта)

set -e
cd "$(dirname "$0")/.."
. venv/bin/activate
exec python bot.py
