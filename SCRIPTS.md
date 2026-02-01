# Скрипты и запуск FinAdvisor

**На Linux-сервере** используйте скрипты `.sh` (не `.ps1` — это PowerShell для Windows):

```bash
chmod +x scripts/*.sh   # один раз
./scripts/run_bot.sh
./scripts/build_frontend.sh
./scripts/run_api.sh
```

**На Windows** — скрипты `.ps1`: `.\scripts\run_bot.ps1` и т.д.

---

## Чек-лист: бот не реагирует / сайт не открывается

### Бот не реагирует на /start и /status

| Проверка | Действие |
|----------|----------|
| Бот запущен? | Запустите в отдельном терминале: **Linux** `./scripts/run_bot.sh` или **Windows** `.\scripts\run_bot.ps1`, либо `python bot.py`. Должно появиться: *DB connected. Scheduler started. Bot ready.* |
| .env корректен? | В `.env` не должно быть пробелов вокруг `=`: пишите `BOT_TOKEN=xxx`, не `BOT_TOKEN = xxx`. Бот и API используют переменные `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, а не `DATABASE_URL`. |
| PostgreSQL доступен? | Убедитесь, что сервер БД запущен и доступен по `DB_HOST`/`DB_PORT`. |

Если бот запущен, но на какую-то команду не отвечает — в консоли бота может появиться ошибка; пользователю уйдёт сообщение «Произошла ошибка. Попробуйте позже.»

### Сайт показывает «FinAdvisor API / Соберите фронт»

| Причина | Решение |
|---------|---------|
| Фронт не собран | Выполните **Linux** `./scripts/build_frontend.sh` или **Windows** `.\scripts\build_frontend.ps1` (из корня проекта). В `frontend/dist` появятся `index.html` и `assets/`. |
| На сервере нет `frontend/dist` | При деплое на finadvisor-ai.ru нужно либо запускать API из корня проекта (где есть папка `frontend/dist`), либо отдавать содержимое `frontend/dist` через nginx/другой веб-сервер по корню домена. |

---

## Формат .env

В `.env` **не должно быть пробелов** вокруг `=`:

```env
BOT_TOKEN=8281205158:AAH...
DB_NAME=FinAdvisor_v3
DB_USER=postgres
DB_PASSWORD=kerimovtech
DB_HOST=localhost
DB_PORT=5432
WEB_APP_URL=https://finadvisor-ai.ru
```

Неправильно: `DATABASE_URL = postgresql://...` (пробелы ломают парсинг).  
Бот и API используют отдельные переменные `DB_*`, а не `DATABASE_URL`.

---

## Порядок запуска

### 1. Сборка фронта (один раз или после изменений в frontend)

**Linux (сервер):**
```bash
./scripts/build_frontend.sh
```

**Windows:**
```powershell
.\scripts\build_frontend.ps1
```

Или вручную: `cd frontend && npm install && npm run build && cd ..`

Собрать фронт и сразу запустить API одной командой: **Linux** `./scripts/build_and_run_api.sh` или **Windows** `.\scripts\build_and_run_api.ps1`

После сборки в `frontend/dist` появятся `index.html` и папка `assets/`. Их раздаёт API.

### 2. Запуск API (сайт + REST API)

Из корня проекта, с активированным venv и заполненным `.env`:

**Linux:** `./scripts/run_api.sh`  
**Windows:** `.\scripts\run_api.ps1`  
Или напрямую: `python -m uvicorn api:app --host 0.0.0.0 --port 8000`

Сайт будет доступен по адресу, на котором крутится API (например `http://localhost:8000` или ваш домен). Кнопка «Открыть FinAdvisor» в боте ведёт на `WEB_APP_URL` из `.env` — убедитесь, что по этому URL отдаётся тот же API (или прокси на порт 8000).

### 3. Запуск бота

В отдельном терминале, из корня проекта:

**Linux:** `./scripts/run_bot.sh`  
**Windows:** `.\scripts\run_bot.ps1`  
Или напрямую: `python bot.py`

Бот должен вывести что-то вроде: `DB connected. Scheduler started. Bot ready.` и начать реагировать на `/start` и `/status`.

---

## Кратко: все команды по порядку (Linux)

```bash
# В корне проекта, venv активирован
pip install -r requirements.txt
chmod +x scripts/*.sh

# Сборка фронта (чтобы сайт открывался)
./scripts/build_frontend.sh

# Терминал 1 — API (сайт + API)
./scripts/run_api.sh

# Терминал 2 — бот
./scripts/run_bot.sh
```

После этого:
- по `http://localhost:8000` (или ваш домен) открывается React-приложение;
- бот в Telegram отвечает на команды и кнопка «Открыть FinAdvisor» ведёт на `WEB_APP_URL`.

---

## Деплой на finadvisor-ai.ru

1. **Соберите фронт** на сервере или локально и скопируйте папку `frontend/dist` на сервер в ту же директорию, откуда запускается API (рядом с `api.py`).
2. **Запустите API** из корня проекта: `python -m uvicorn api:app --host 0.0.0.0 --port 8000`. Убедитесь, что в рабочей директории есть `frontend/dist/index.html`.
3. **Настройте nginx** (или другой прокси): запросы на `https://finadvisor-ai.ru` должны проксироваться на `http://127.0.0.1:8000`. API сам отдаёт React по `/` и статику из `/assets/`.
4. **Запустите бота** в отдельном процессе (systemd/screen): `python bot.py`. В `.env` на сервере должен быть `WEB_APP_URL=https://finadvisor-ai.ru`.
