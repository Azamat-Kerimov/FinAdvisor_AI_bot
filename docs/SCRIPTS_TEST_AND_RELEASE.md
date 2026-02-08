# Скрипты: тестовый стенд (логи) и релиз на прод

## 1. Тестовый стенд — включить логирование действий

Выполнять **локально** (Windows CMD), в корне репозитория. В `.env` должны быть параметры **тестовой** БД (например `DB_NAME=FinAdvisor_Beta` или `FinAdvisor_test`).

### Шаг 1.1. Применить миграцию (таблица `user_actions`)

**CMD (локальный):**

```cmd
venv\Scripts\python scripts\apply_migration.py scripts\migrate_user_actions.sql
```

Если нет venv или удобнее через psql:

```cmd
psql -U postgres -d FinAdvisor_Beta -f scripts\migrate_user_actions.sql
```

*(Подставьте своего пользователя и имя тестовой БД из `.env`.)*

### Шаг 1.2. Запустить API в тестовом режиме

**CMD (локальный, отдельный терминал):**

```cmd
set APP_ENV=test
venv\Scripts\python -m uvicorn api:app --host 0.0.0.0 --port 8000
```

После этого при открытии приложения (с `X-Test-User-Id` или через Telegram) действия будут записываться в `user_actions`.

---

## 2. Тесты и вывод релиза на прод

### Шаг 2.1. Автотесты (обязательно перед деплоем)

Сначала в **отдельном терминале** запустите API с тестовой средой:

**CMD (локальный, терминал 1):**

```cmd
set APP_ENV=test
venv\Scripts\python -m uvicorn api:app --host 0.0.0.0 --port 8000
```

Затем в **другом терминале** запустите тесты:

**CMD (локальный, терминал 2, корень репозитория):**

```cmd
scripts\run_tests.cmd
```

Или без скрипта:

```cmd
venv\Scripts\python -m pytest _unpublished/tests/ -v
```

Все тесты должны пройти. При падении — исправить код и повторить.

---

### Шаг 2.2. Git, сборка фронта, заливка на VPS

**CMD (локальный, корень репозитория):**

```cmd
git branch
git add .
git commit -m "описание изменений"
git push origin main
cd frontend
npm install
npm run build
cd ..
scp -r frontend\dist root@109.70.24.22:~/FinAdvisor_AI_bot/frontend/
```

- Если `package.json` не менялся, `npm install` можно не выполнять.
- В PowerShell вместо `frontend\dist` укажите `frontend/dist`.

---

### Шаг 2.3. Обновление на VPS (прод)

**CMD (VPS, SSH на 109.70.24.22):**

```bash
cd /root/FinAdvisor_AI_bot
git fetch
git reset --hard origin/main
git clean -fd -e .env -e venv
sudo systemctl restart finadvisor-api finadvisorbot
```

---

### Шаг 2.4. Миграция на прод-БД (один раз)

Если таблица `user_actions` на прод-БД ещё не создана, один раз применить миграцию **на проде** (подключение к прод-БД):

- **Вариант А:** с локальной машины, если в отдельном `.env.prod` указаны параметры прод-БД:

  ```cmd
  set DB_NAME=имя_прод_бд
  set DB_USER=...
  set DB_PASSWORD=...
  set DB_HOST=109.70.24.22
  venv\Scripts\python scripts\apply_migration.py scripts\migrate_user_actions.sql
  ```

- **Вариант Б:** по SSH на VPS, если там есть доступ к БД (psql):

  ```bash
  cd /root/FinAdvisor_AI_bot
  psql -U postgres -d имя_прод_бд -f scripts/migrate_user_actions.sql
  ```

*(Имя прод-БД и пользователь — из `.env` на VPS.)*

После этого скрипты из пунктов 2.1–2.3 составляют полный цикл: тесты → релиз на прод.
