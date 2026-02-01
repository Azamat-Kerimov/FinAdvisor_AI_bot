#!/usr/bin/env bash
# Включить новый интерфейс (React): сборка frontend/dist и переключение nginx на него.
# Запуск на сервере из корня репозитория: bash scripts/use-react-frontend.sh

set -e
cd "$(dirname "$0")/.."
PROJECT_ROOT="$PWD"

echo "[react] Корень проекта: $PROJECT_ROOT"

# 1. Сборка React-приложения
echo "[react] Сборка frontend..."
cd "$PROJECT_ROOT/frontend"
npm ci 2>/dev/null || npm install
npm run build
cd "$PROJECT_ROOT"

# 2. Обновить конфиг nginx: главная страница — frontend/dist (React), /api/ — FastAPI
NGINX_AVAILABLE="/etc/nginx/sites-available/finadvisor-ai.ru"
if [ ! -f "$PROJECT_ROOT/config/nginx-finadvisor.conf" ]; then
  echo "[react] Ошибка: config/nginx-finadvisor.conf не найден."
  exit 1
fi

echo "[react] Обновляю nginx (сайт будет отдавать React из frontend/dist)..."
sed "s|/root/FinAdvisor_AI_bot|$PROJECT_ROOT|g" "$PROJECT_ROOT/config/nginx-finadvisor.conf" | sudo tee "$NGINX_AVAILABLE" > /dev/null
sudo ln -sf "$NGINX_AVAILABLE" /etc/nginx/sites-enabled/finadvisor-ai.ru 2>/dev/null || true

if sudo nginx -t 2>/dev/null; then
  sudo systemctl reload nginx
  echo "[react] Nginx перезагружен. Открывайте сайт — должен отображаться новый React-интерфейс."
else
  echo "[react] Nginx: проверка не прошла. Выполните: sudo nginx -t"
  exit 1
fi
