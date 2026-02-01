#!/usr/bin/env bash
# Деплой после git pull: зависимости, миграции, сборка фронта, перезапуск API и nginx.
# Запуск на сервере из корня репозитория: bash scripts/deploy.sh

set -e
cd "$(dirname "$0")/.."
PROJECT_ROOT="$PWD"

echo "[deploy] Корень проекта: $PROJECT_ROOT"

# 1. Python venv и зависимости
if [ ! -d "$PROJECT_ROOT/venv" ]; then
  echo "[deploy] Создаю venv..."
  python3 -m venv "$PROJECT_ROOT/venv"
fi
. "$PROJECT_ROOT/venv/bin/activate"
echo "[deploy] pip install..."
pip install -q -r requirements.txt

# 2. Миграции БД (требуется .env с DATABASE_URL / DB_*)
if [ -f "$PROJECT_ROOT/.env" ]; then
  echo "[deploy] Миграции..."
  python scripts/run_migrations.py || true
else
  echo "[deploy] Файл .env не найден — миграции пропущены. Скопируйте .env.example в .env и настройте."
fi

# 3. Frontend: зависимости и сборка
echo "[deploy] Frontend: npm install и build..."
cd "$PROJECT_ROOT/frontend"
npm ci 2>/dev/null || npm install
npm run build
cd "$PROJECT_ROOT"

# 4. Systemd: подставляем путь проекта и копируем unit
echo "[deploy] Обновляю finadvisor-api.service..."
escaped_root="${PROJECT_ROOT//\//\\/}"
sed "s|/root/FinAdvisor_AI_bot|$PROJECT_ROOT|g" "$PROJECT_ROOT/finadvisor-api.service" | sudo tee /etc/systemd/system/finadvisor-api.service > /dev/null
sudo systemctl daemon-reload
sudo systemctl restart finadvisor-api
echo "[deploy] Сервис finadvisor-api перезапущен."

# 5. Nginx: подставляем путь и копируем конфиг
NGINX_AVAILABLE="/etc/nginx/sites-available/finadvisor-ai.ru"
if [ -f "$PROJECT_ROOT/config/nginx-finadvisor.conf" ]; then
  echo "[deploy] Обновляю конфиг nginx..."
  sed "s|/root/FinAdvisor_AI_bot|$PROJECT_ROOT|g" "$PROJECT_ROOT/config/nginx-finadvisor.conf" | sudo tee "$NGINX_AVAILABLE" > /dev/null
  if [ ! -L /etc/nginx/sites-enabled/finadvisor-ai.ru ]; then
    sudo ln -sf "$NGINX_AVAILABLE" /etc/nginx/sites-enabled/finadvisor-ai.ru
  fi
  if sudo nginx -t 2>/dev/null; then
    sudo systemctl reload nginx
    echo "[deploy] Nginx перезагружен."
  else
    echo "[deploy] Nginx: проверка конфига не прошла (nginx -t). Исправьте конфиг вручную."
  fi
else
  echo "[deploy] config/nginx-finadvisor.conf не найден — nginx не обновлялся."
fi

echo "[deploy] Готово. Откройте сайт в браузере."
