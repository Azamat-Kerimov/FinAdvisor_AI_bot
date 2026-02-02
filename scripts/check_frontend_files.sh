#!/usr/bin/env bash
# Проверка наличия всех файлов фронтенда перед деплоем.
# Запускать из корня проекта: ./scripts/check_frontend_files.sh
# Если все файлы на месте — exit 0, иначе — exit 1 и список отсутствующих.

set -e
cd "$(dirname "$0")/.."

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
  echo "Ошибка: отсутствуют файлы:$MISSING"
  exit 1
fi
echo "Все необходимые файлы фронтенда на месте."
