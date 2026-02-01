#!/usr/bin/env bash
# Полный деплой на сервере: сборка фронта + перезапуск API и бота
# Запускайте из корня проекта после git pull

set -e
cd "$(dirname "$0")/.."

# Права на выполнение для скриптов (в т.ч. run_*_venv.sh для systemd)
chmod +x scripts/*.sh 2>/dev/null || true

echo "=== 1. Сборка фронта (чтобы сайт открывался) ==="
bash scripts/build_frontend.sh

if [ ! -f frontend/dist/index.html ]; then
    echo "Ошибка: после сборки не найден frontend/dist/index.html"
    exit 1
fi
echo "OK: frontend/dist готов"

echo ""
echo "=== 2. Перезапуск сервисов ==="
sudo systemctl restart finadvisor-api.service
sudo systemctl restart finadvisorbot.service

echo ""
echo "=== 3. Статус ==="
sudo systemctl status finadvisor-api.service finadvisorbot.service --no-pager -l || true

echo ""
echo "Готово. Проверьте:"
echo "  - Сайт: откройте WEB_APP_URL в браузере"
echo "  - Бот: отправьте /start в Telegram"
echo "  - Логи: sudo journalctl -u finadvisor-api.service -u finadvisorbot.service -f"
