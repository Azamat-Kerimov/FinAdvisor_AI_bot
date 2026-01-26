# FinAdvisor Telegram Web App

Мини-приложение для Telegram с полным функционалом финансового консультанта.

## Установка

1. Установите зависимости:
```bash
pip install -r requirements.txt
```

2. Настройте переменные окружения в `.env`:
```
WEB_APP_URL=https://your-domain.com
```

3. Запустите API сервер:
```bash
python api.py
```

Или с помощью uvicorn:
```bash
uvicorn api:app --host 0.0.0.0 --port 8000
```

4. Настройте бота для работы с Web App:
   - В BotFather создайте Web App или используйте существующего бота
   - Укажите URL вашего Web App (например: `https://your-domain.com`)

## Структура проекта

```
.
├── api.py                 # FastAPI сервер с API endpoints
├── bot.py                 # Telegram бот
├── webapp/
│   ├── index.html        # Главная страница Web App
│   └── static/
│       ├── css/
│       │   └── style.css  # Стили
│       └── js/
│           └── app.js     # JavaScript логика
└── requirements.txt       # Зависимости
```

## Функционал

- ✅ Статистика за текущий месяц
- ✅ Добавление и просмотр транзакций
- ✅ Управление целями
- ✅ Просмотр активов и долгов
- ✅ AI консультации
- ✅ Адаптивный дизайн для Telegram

## API Endpoints

- `GET /api/stats` - Статистика за месяц
- `GET /api/transactions` - Список транзакций
- `POST /api/transactions` - Создать транзакцию
- `GET /api/goals` - Список целей
- `POST /api/goals` - Создать цель
- `GET /api/assets` - Список активов
- `POST /api/assets` - Создать актив
- `GET /api/liabilities` - Список долгов
- `POST /api/liabilities` - Создать долг
- `GET /api/consultation` - Получить AI консультацию

## Безопасность

Web App использует валидацию `initData` от Telegram для аутентификации пользователей. Все запросы проверяются на подлинность.

## Развертывание

1. Разверните API сервер на вашем хостинге (например, на Heroku, Railway, или VPS)
2. Настройте домен и SSL сертификат
3. Укажите URL в BotFather
4. Обновите `WEB_APP_URL` в `.env`
