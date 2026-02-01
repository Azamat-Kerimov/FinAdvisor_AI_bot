#!/usr/bin/env bash
# Сборка React-фронтенда (FinAdvisor Web App)
# Результат: frontend/dist — эти файлы отдаёт api.py по корню сайта
#
# На серверах с малым RAM (1–2 GB) npm install может быть убит (Killed).
# Ограничиваем память Node и используем более лёгкий install.

set -e
cd "$(dirname "$0")/.."

# Ограничение памяти для Node (MB) — снижает риск OOM Killer на слабых серверах
export NODE_OPTIONS="${NODE_OPTIONS:-} --max-old-space-size=768"

echo "Установка зависимостей frontend..."
cd frontend
if [ ! -d node_modules ]; then
    npm install --prefer-offline --no-audit --progress=false
else
    npm ci --prefer-offline --no-audit 2>/dev/null || npm install --prefer-offline --no-audit --progress=false
fi
echo "Сборка (tsc + vite build)..."
npm run build
cd ..
echo "Готово. Фронт собран в frontend/dist"
