#!/bin/bash
# Скрипт для обновления файлов на сервере

echo "=== Обновление FinAdvisor Web App ==="

# Переход в директорию проекта
cd /root/FinAdvisor_AI_bot || exit 1

# Обновление из git
echo "1. Обновление кода из репозитория..."
git pull origin main || git pull origin master

# Проверка версии в index.html
echo "2. Проверка версии в index.html..."
VERSION=$(grep -o 'v=[0-9]\+\.[0-9]\+' webapp/index.html | head -1)
echo "   Текущая версия: $VERSION"

if [[ "$VERSION" != "v=6.0" ]]; then
    echo "   ⚠️  ВНИМАНИЕ: Версия не 6.0! Проверьте файл webapp/index.html"
    echo "   Ожидаемая версия: v=6.0"
    echo "   Найденная версия: $VERSION"
fi

# Проверка наличия всех файлов
echo "3. Проверка наличия файлов..."
echo "   CSS файлы:"
ls -1 webapp/static/css/ | wc -l
echo "   JS файлы:"
ls -1 webapp/static/js/ | wc -l

# Перезапуск API сервера
echo "4. Перезапуск API сервера..."
sudo systemctl restart finadvisor-api.service
sleep 2

# Проверка статуса
echo "5. Проверка статуса сервиса..."
sudo systemctl status finadvisor-api.service --no-pager -l | head -15

echo ""
echo "=== Обновление завершено ==="
echo ""
echo "Следующие шаги:"
echo "1. Откройте сайт в режиме инкогнито (Ctrl+Shift+N)"
echo "2. Или выполните жесткую перезагрузку (Ctrl+Shift+R)"
echo "3. Проверьте консоль браузера (F12) на наличие ошибок"
