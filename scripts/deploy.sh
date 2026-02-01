#!/usr/bin/env bash
# Деплой: перезапуск API и бота после git pull
# Запускать из корня проекта: ./scripts/deploy.sh

set -e
cd "$(dirname "$0")/.."

chmod +x scripts/*.sh 2>/dev/null || true

sudo systemctl restart finadvisor-api.service
sudo systemctl restart finadvisorbot.service

sudo systemctl status finadvisor-api.service finadvisorbot.service --no-pager -l || true
