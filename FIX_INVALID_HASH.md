# Решение проблемы "Invalid hash" для Telegram Web App

## Проблема
Запросы к API возвращают `401 Unauthorized` с ошибкой "Invalid hash", хотя `init-data` передается (видно в консоли браузера).

## Причина
1. Nginx не проксирует заголовок `init-data` правильно
2. `init-data` может быть URL-закодирован и требует декодирования
3. Проблема с валидацией хеша на сервере

## Решение

### Шаг 1: Обновите конфигурацию nginx

```bash
sudo nano /etc/nginx/sites-available/finadvisor-ai.ru
```

Добавьте блок для `/api/`:

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
    # Явно передаем init-data заголовок
    proxy_set_header init-data $http_init_data;
}
```

**ВАЖНО:** Этот блок должен быть ПЕРЕД блоком `location /`, так как nginx обрабатывает более специфичные location первыми.

### Шаг 2: Проверьте конфигурацию

```bash
sudo nginx -t
```

### Шаг 3: Перезапустите nginx

```bash
sudo systemctl reload nginx
```

### Шаг 4: Обновите код на сервере

```bash
cd /root/FinAdvisor_AI_bot
git pull origin main
sudo systemctl restart finadvisor-api.service
```

### Шаг 5: Проверьте логи

```bash
sudo journalctl -u finadvisor-api.service -f
```

При запросе к `/api/stats` должны быть логи валидации (если включено логирование).

## Альтернативное решение: Используйте query параметр вместо заголовка

Если проблема с заголовками сохраняется, можно передавать `init-data` через query параметр:

В `api.js` измените:
```javascript
const headers = {
    'Content-Type': 'application/json',
    ...(initData && { 'init-data': initData }),
    ...options.headers
};
```

На:
```javascript
// Добавляем init-data в URL для GET запросов
let url = `${API_URL}${endpoint}`;
if (initData && (options.method === 'GET' || !options.method)) {
    url += (endpoint.includes('?') ? '&' : '?') + `init-data=${encodeURIComponent(initData)}`;
}

const headers = {
    'Content-Type': 'application/json',
    ...(initData && options.method !== 'GET' && { 'init-data': initData }),
    ...options.headers
};
```

И в `api.py` измените:
```python
async def get_user_id(
    init_data: Optional[str] = Header(None, alias="init-data"),
    init_data_query: Optional[str] = None
) -> int:
    """Получить user_id из Telegram Web App"""
    init_data = init_data or init_data_query
    if not init_data:
        ...
```

Но это менее безопасно и не рекомендуется.

## Проверка результата

После выполнения всех шагов:

1. Откройте сайт через Telegram Web App
2. Откройте DevTools (F12) → Network
3. Найдите запрос к `/api/stats`
4. Проверьте заголовки запроса - должен быть заголовок `init-data`
5. Статистика должна загружаться без ошибок 401

## Если проблема сохраняется

Проверьте, что заголовок передается правильно:

1. В DevTools → Network → выберите запрос к `/api/stats`
2. Вкладка Headers → Request Headers
3. Должен быть заголовок `init-data: [длинная строка]`

Если заголовка нет, проблема в передаче из JavaScript.
Если заголовок есть, но все равно 401, проблема в валидации на сервере.
