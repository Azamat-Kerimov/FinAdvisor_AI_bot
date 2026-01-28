# Решение проблемы 401 Unauthorized для /api/stats

## Проблема
Запрос к `/api/stats` возвращает `401 Unauthorized`, что приводит к ошибке загрузки статистики.

## Причина
Endpoint `/api/stats` требует авторизацию через Telegram Web App (`init-data`), но `init-data` либо не передается, либо не читается правильно.

## Решение

### Шаг 1: Обновите код на сервере

```bash
cd /root/FinAdvisor_AI_bot
git pull origin main
sudo systemctl restart finadvisor-api.service
```

### Шаг 2: Проверьте логи в браузере

1. Откройте сайт через Telegram Web App
2. Откройте DevTools (F12) → Console
3. Проверьте сообщения:
   - "Telegram Web App обнаружен"
   - "initData доступен: true"
   - "initData длина: [число]"
   - "Отправка запроса с init-data заголовком"

### Шаг 3: Проверьте логи на сервере

```bash
sudo journalctl -u finadvisor-api.service -f
```

При запросе к `/api/stats` должны быть логи:
- Если `init-data` отсутствует: "Missing init-data header in request"
- Если есть ошибка валидации: "Error in get_user_id: [описание ошибки]"

### Шаг 4: Проверьте конфигурацию nginx

Убедитесь, что nginx правильно проксирует заголовки:

```bash
sudo cat /etc/nginx/sites-available/finadvisor-ai.ru | grep -A 5 "location /"
```

Должно быть:
```nginx
location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

**ВАЖНО:** Nginx должен проксировать ВСЕ заголовки, включая кастомные заголовки с дефисами.

### Шаг 5: Если проблема сохраняется

Проверьте, что Telegram Web App правильно инициализирован:

1. Откройте DevTools → Console
2. Выполните:
   ```javascript
   console.log(window.Telegram?.WebApp?.initData);
   ```
3. Если `initData` пустой или `undefined`, проблема в инициализации Telegram Web App

### Шаг 6: Альтернативное решение (временное)

Если нужно протестировать без Telegram, можно временно сделать `/api/stats` публичным:

В `api.py` измените:
```python
@app.get("/api/stats")
async def get_stats(user_id: int = Depends(get_user_id)):
```

На:
```python
@app.get("/api/stats")
async def get_stats(user_id: Optional[int] = None):
    # Для тестирования без Telegram
    if user_id is None:
        # Возвращаем тестовые данные или ошибку
        return {
            "total_income": 0,
            "total_expense": 0,
            "income_by_category": {},
            "expense_by_category": {}
        }
```

Но это НЕ рекомендуется для продакшена!

## Проверка результата

После выполнения всех шагов:

1. Откройте сайт через Telegram Web App
2. Статистика должна загружаться без ошибок
3. В Console не должно быть ошибок 401
4. В Network все запросы должны быть 200 OK
