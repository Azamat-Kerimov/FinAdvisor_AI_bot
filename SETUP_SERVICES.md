# Настройка автозапуска сервисов

## Текущая ситуация

У вас уже есть service файл для бота. Теперь нужно добавить отдельный service файл для API сервера.

## Шаг 1: Создайте service файл для API

Файл `finadvisor-api.service` уже создан в проекте. Скопируйте его на сервер:

```bash
sudo cp /root/FinAdvisor_AI_bot/finadvisor-api.service /etc/systemd/system/
```

## Шаг 2: Проверьте содержимое файла

Убедитесь, что файл `/etc/systemd/system/finadvisor-api.service` содержит:

```ini
[Unit]
Description=FinAdvisor Telegram Web App API Server
After=network.target postgresql.service

[Service]
Type=simple
User=root
WorkingDirectory=/root/FinAdvisor_AI_bot
Environment="PATH=/root/FinAdvisor_AI_bot/venv/bin"
EnvironmentFile=/root/FinAdvisor_AI_bot/.env
ExecStart=/root/FinAdvisor_AI_bot/venv/bin/uvicorn api:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

**Важно:** 
- Используется `python3` (как в вашем bot service)
- Добавлен `EnvironmentFile=/root/FinAdvisor_AI_bot/.env` (как в вашем bot service)
- Используется `uvicorn` напрямую (рекомендуется)

## Шаг 3: Активируйте сервис

```bash
# Перезагрузить конфигурацию systemd
sudo systemctl daemon-reload

# Включить автозапуск при загрузке системы
sudo systemctl enable finadvisor-api.service

# Запустить сервис
sudo systemctl start finadvisor-api.service

# Проверить статус
sudo systemctl status finadvisor-api.service
```

## Шаг 4: Проверка работы

```bash
# Проверить, что оба сервиса работают
sudo systemctl status finadvisorbot.service
sudo systemctl status finadvisor-api.service

# Проверить, что API отвечает
curl http://localhost:8000/

# Посмотреть логи API
sudo journalctl -u finadvisor-api.service -f
```

## Управление сервисами

### Бот (существующий):
```bash
sudo systemctl start finadvisorbot.service
sudo systemctl stop finadvisorbot.service
sudo systemctl restart finadvisorbot.service
sudo systemctl status finadvisorbot.service
```

### API (новый):
```bash
sudo systemctl start finadvisor-api.service
sudo systemctl stop finadvisor-api.service
sudo systemctl restart finadvisor-api.service
sudo systemctl status finadvisor-api.service
```

## Структура сервисов

Теперь у вас будет два независимых сервиса:

1. **finadvisorbot.service** - Telegram бот
2. **finadvisor-api.service** - Web App API сервер

Они работают независимо друг от друга, что удобно для управления.

## Проверка портов

```bash
# Проверить, что порты заняты
sudo netstat -tulpn | grep -E ':(8000|8443)'
# или
sudo ss -tulpn | grep -E ':(8000|8443)'
```

## Если нужно изменить порт API

Если порт 8000 занят, измените в service файле:
```ini
ExecStart=/root/FinAdvisor_AI_bot/venv/bin/uvicorn api:app --host 0.0.0.0 --port 8001
```

И обновите nginx конфигурацию соответственно.
