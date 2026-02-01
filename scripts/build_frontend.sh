#!/usr/bin/env bash
# Сборка React-фронтенда (FinAdvisor Web App)
# Результат: frontend/dist — эти файлы отдаёт api.py по корню сайта

set -e
cd "$(dirname "$0")/.."

echo "Установка зависимостей frontend..."
cd frontend
if [ ! -d node_modules ]; then
    npm install
else
    npm ci 2>/dev/null || npm install
fi
echo "Сборка (tsc + vite build)..."
npm run build
cd ..
echo "Готово. Фронт собран в frontend/dist"
