#!/usr/bin/env bash
# Сборка React-фронтенда (FinAdvisor Web App)
# Результат: frontend/dist — эти файлы отдаёт api.py по корню сайта
#
# На серверах с малым RAM (1–2 GB) npm install может быть убит (Killed).
# Ограничиваем память Node и используем более лёгкий install.

set -e
cd "$(dirname "$0")/.."

# Проверка наличия всех файлов, от которых зависит сборка (до npm install)
REQUIRED_FILES="
  frontend/src/components/transactions/TransactionsScreen.tsx
  frontend/src/components/capital/CapitalScreen.tsx
  frontend/src/components/consultation/ConsultationScreen.tsx
  frontend/src/components/dashboard/ExpenseChart.tsx
  frontend/src/components/dashboard/GoalsSummary.tsx
"
MISSING=""
for f in $REQUIRED_FILES; do
  if [ ! -f "$f" ]; then
    MISSING="${MISSING}\n  - $f"
  fi
done
if [ -n "$MISSING" ]; then
  echo "Ошибка: отсутствуют файлы фронтенда:$MISSING"
  echo ""
  echo "Добавьте их в репозиторий с локальной машины:"
  echo "  git add frontend/src/components/"
  echo "  git commit -m 'Add missing frontend components'"
  echo "  git push"
  echo "Затем на сервере: git pull && ./scripts/build_frontend.sh"
  exit 1
fi
echo "Проверка файлов: все на месте."

# Ограничение памяти для Node (MB) — снижает риск OOM Killer на слабых серверах
export NODE_OPTIONS="${NODE_OPTIONS:-} --max-old-space-size=768"

echo "Установка зависимостей frontend... (на слабом сервере может занять 10–30 мин)"
cd frontend
if [ ! -d node_modules ]; then
    npm install --prefer-offline --no-audit
else
    npm ci --prefer-offline --no-audit 2>/dev/null || npm install --prefer-offline --no-audit
fi
echo "Сборка (tsc + vite build)..."
npm run build
cd ..
echo "Готово. Фронт собран в frontend/dist"
