# Деплой FinAdvisor (Linux, /root/FinAdvisor_AI_bot)

## Выкат в прод (пошагово)

Выполнять **по порядку**. Локально — терминал (Cursor или CMD) **из корня репозитория** (папка, где лежат `api.py`, `bot.py`, `frontend/`, `deploy/`). VPS — по SSH (IP: **109.70.24.22**).

| Шаг | Где | Действие |
|-----|-----|----------|
| 0 | **Локально** | Перейти в папку проекта (корень репозитория). В CMD: `cd /d "C:\Users\Azama_mdmsx1j\OneDrive\Desktop\Бизнесы\1. Проекты ИИ-агентов\Финансовый консультант\репозиторий GitHub\FinAdvisor_AI_bot"`. В терминале Cursor эта папка обычно уже открыта (View → Terminal). Проверка: в списке файлов есть `api.py`, папки `frontend`, `deploy`. |
| 1 | **Локально** | Убедиться, что активна ветка **main**: `git branch` (звёздочка у `main`). Если нет — переключиться: `git checkout main`. Затем закоммитить и отправить: `git add .` → `git commit -m "описание"` → `git push origin main` |
| 2 | **Локально** | Собрать фронт: `cd frontend` → `npm install` (если менялся package.json) → `npm run build` → `cd ..` (команды из той же папки проекта; после `cd ..` вы снова в корне) |
| 3 | **VPS** | Подтянуть код: `cd /root/FinAdvisor_AI_bot` → `git fetch` → `git reset --hard origin/main` → `git clean -fd -e .env -e venv` |
| 4 | **VPS** | Перезапустить бэкенд: `sudo systemctl restart finadvisor-api finadvisorbot` |
| 5 | **Локально** | Залить собранный фронт на VPS: `scp -r frontend/dist root@109.70.24.22:~/FinAdvisor_AI_bot/frontend/` |
| 6 | **VPS** | Перезапустить API после заливки dist: `sudo systemctl restart finadvisor-api` |

После шага 6 сайт и бот работают с новой версией. Логи бота: `sudo journalctl -u finadvisorbot -f`.

**Где вводить команды шага 1–2:** в терминале Cursor (View → Terminal или Ctrl+`) или в обычном CMD. **Рабочая папка** — корень проекта (та папка, где есть `api.py`, `frontend/`, `deploy/`). В Cursor по умолчанию терминал открывается в корне открытого проекта.

---

## 1. Один раз: установка на сервере

```bash
cd /root/FinAdvisor_AI_bot

python3 -m venv venv
. venv/bin/activate
pip install -r requirements.txt

cd frontend && npm install && npm run build && cd ..

chmod +x scripts/*.sh

sudo cp deploy/finadvisor-api.service deploy/finadvisorbot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable finadvisor-api.service finadvisorbot.service
sudo systemctl start finadvisor-api.service finadvisorbot.service
```

Создайте `.env` в корне проекта (см. `.env.example`). Формат: `KEY=value` без пробелов вокруг `=`.

## 2. После каждого обновления кода

На сервере, **из корня проекта**. VPS — только цель деплоя: код только из GitHub, локальные правки не сохраняем (см. **PROJECT_RULES.md**).

**Предпочтительно** (приводит репозиторий в точное состояние GitHub, без конфликтов):

```bash
cd /root/FinAdvisor_AI_bot
git fetch
git reset --hard origin/main
git clean -fd -e .env -e venv
chmod +x scripts/*.sh
./scripts/deploy.sh
```

Если используете обычный pull:

```bash
cd /root/FinAdvisor_AI_bot
git pull
./scripts/deploy.sh
```

Если git сообщает о локальных изменениях — **не сохраняйте их**, приведите репозиторий к GitHub:

```bash
git restore .
git pull
# или: git fetch && git reset --hard origin/main && git clean -fd -e .env -e venv
```

Проверка логов:

```bash
sudo journalctl -u finadvisorbot.service -f
```

**Если после `git clean` появился 502 или сервисы не стартуют** — мог удалиться каталог `venv/`. Восстановите его один раз:

```bash
cd /root/FinAdvisor_AI_bot
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
sudo systemctl restart finadvisor-api finadvisorbot
```

Дальше используйте `git clean -fd -e .env -e venv`, чтобы venv не удалялся.

## 3. Фронт: сборка и «Соберите фронт» на сайте

Если при открытии сайта видите «FinAdvisor API» и «Фронт не собран» — на сервере нет папки `frontend/dist`.

**Вариант А — сборка на сервере** (если хватает RAM, обычно 10–60 сек):

```bash
cd /root/FinAdvisor_AI_bot
./scripts/build_frontend.sh
sudo systemctl restart finadvisor-api.service
```

Перед сборкой скрипт проверяет наличие всех нужных файлов фронтенда. Если видите **«Ошибка: отсутствуют файлы»** — эти файлы не попали в репозиторий. На **локальной машине** (где правите код) выполните:

```bash
git add frontend/src/components/
git status
git commit -m "Add missing frontend components"
git push
```

Затем на сервере: `git pull` и снова `./scripts/build_frontend.sh`. Локально перед пушем можно проверить: `./scripts/check_frontend_files.sh`.

**Вариант Б — сборка на своём ПК, заливка dist на сервер** (обязательно, если на сервере `npm install` даёт «Killed» из‑за нехватки RAM):

1. На своём ПК (в корне клона репозитория):
   ```bash
   cd frontend
   npm install
   npm run build
   cd ..
   ```
2. С ПК загрузить только `frontend/dist` на сервер (подставьте свой хост):
   ```bash
   scp -r frontend/dist root@109.70.24.22:~/FinAdvisor_AI_bot/frontend/
   ```
3. На VPS перезапустить API:
   ```bash
   sudo systemctl restart finadvisor-api
   ```
   После этого сайт должен открываться с актуальным фронтом.

## Тестовая БД (локально)

Если тестовая БД (например `FinAdvisor_Beta`) не совпадает по схеме с продом, примените схему из репозитория.

**Вариант 1 — Python (подходит для Windows, без psql):** из корня проекта, с настроенным `.env` (DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT):

```cmd
venv\Scripts\python scripts/apply_schema.py
```

**Вариант 2 — psql (Linux / если установлен клиент PostgreSQL):**

```bash
psql -U postgres -d FinAdvisor_Beta -f scripts/schema_finadvisor.sql
```

Скрипт создаёт все нужные таблицы (`CREATE TABLE IF NOT EXISTS`) и при необходимости добавляет минимальные категории. Для теста с `X-Test-User-Id=1` в БД должен быть пользователь с `id=1` и с подпиской (например вручную: `INSERT INTO users (id, tg_id, username, premium_until) VALUES (1, 0, 'test', NOW() + INTERVAL '1 year');`).

## Скрипты

| Скрипт | Назначение |
|--------|------------|
| `scripts/schema_finadvisor.sql` | Схема БД для тестовой/новой БД |
| `scripts/apply_schema.py` | Применить схему к БД из .env (удобно на Windows без psql) |
| `scripts/deploy.sh` | После git pull — перезапуск API и бота |
| `scripts/build_frontend.sh` | Сборка фронта (сначала проверка файлов, затем npm install/build) |
| `scripts/check_frontend_files.sh` | Проверка наличия всех файлов фронтенда (запускать локально перед push) |
| `scripts/run_bot_venv.sh`, `scripts/run_api_venv.sh` | Вызываются systemd, вручную не запускать |
