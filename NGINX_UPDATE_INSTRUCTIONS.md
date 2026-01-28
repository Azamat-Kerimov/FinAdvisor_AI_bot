# Инструкция по обновлению конфигурации nginx

## Проблема
Nginx не проксирует заголовок `init-data` к FastAPI, что вызывает ошибку "Invalid hash".

## Решение

### Шаг 1: Отредактируйте конфигурацию nginx

```bash
sudo nano /etc/nginx/sites-available/finadvisor-ai.ru
```

### Шаг 2: Добавьте блок для /api/ ПЕРЕД блоком location /

Найдите блок `location /` и ПЕРЕД ним добавьте:

```nginx
    # ВАЖНО: проксируем /api/ к FastAPI и передаем ВСЕ заголовки, включая init-data
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # КРИТИЧНО: передаем все заголовки, включая кастомные с дефисами
        proxy_pass_request_headers on;
        # Явно передаем init-data заголовок (nginx конвертирует дефисы в подчеркивания)
        proxy_set_header init-data $http_init_data;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        ...
    }
```

**ВАЖНО:** Блок `location /api/` должен быть ПЕРЕД блоком `location /`, так как nginx обрабатывает более специфичные location первыми.

### Шаг 3: Проверьте конфигурацию

```bash
sudo nginx -t
```

Должно быть: `nginx: configuration file /etc/nginx/nginx.conf test is successful`

### Шаг 4: Перезапустите nginx

```bash
sudo systemctl reload nginx
```

### Шаг 5: Обновите код и перезапустите API

```bash
cd /root/FinAdvisor_AI_bot
git pull origin main
sudo systemctl restart finadvisor-api.service
```

### Шаг 6: Проверьте логи

```bash
sudo journalctl -u finadvisor-api.service -f
```

При запросе к `/api/stats` должны быть логи:
- Если заголовок не передается: "Missing init-data header in request" и список доступных заголовков
- Если заголовок передается, но хеш неверный: "Hash mismatch"

### Шаг 7: Проверьте в браузере

1. Откройте сайт через Telegram Web App
2. Откройте DevTools (F12) → Network
3. Найдите запрос к `/api/stats`
4. Вкладка Headers → Request Headers
5. Должен быть заголовок `init-data: [длинная строка]`
6. Статистика должна загружаться без ошибок 401

## Полный пример конфигурации

```nginx
server {
    server_name finadvisor-ai.ru www.finadvisor-ai.ru;

    # ВАЖНО: блок /api/ должен быть ПЕРЕД блоком /
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_pass_request_headers on;
        proxy_set_header init-data $http_init_data;
    }

    location /static/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Accept-Encoding "";
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    listen 443 ssl;
    # ... остальная конфигурация SSL ...
}
```

## Если проблема сохраняется

Проверьте логи API сервера - там будет список всех доступных заголовков, что поможет понять, передается ли `init-data`:

```bash
sudo journalctl -u finadvisor-api.service -n 100 | grep "Available headers"
```

Если заголовка нет в списке, проблема в nginx конфигурации.
Если заголовок есть, но все равно ошибка "Invalid hash", проблема в валидации на сервере.
