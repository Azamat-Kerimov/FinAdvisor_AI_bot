# Деплой FinAdvisor (Linux, /root/FinAdvisor_AI_bot)

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

На сервере, **из корня проекта**:

```bash
cd /root/FinAdvisor_AI_bot
git pull
./scripts/deploy.sh
```

Если `git pull` пишет *Your local changes ... would be overwritten by merge*:

```bash
cd /root/FinAdvisor_AI_bot
git restore scripts/
git pull
./scripts/deploy.sh
```

Проверка логов:

```bash
sudo journalctl -u finadvisorbot.service -f
```

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

**Вариант Б — сборка на своём ПК, заливка dist на сервер** (если на сервере сборка зависает или «Killed»):

1. На своём ПК (в клонированном репозитории):
   ```bash
   cd frontend && npm install && npm run build && cd ..
   ```
2. Загрузить только `frontend/dist` на сервер:
   ```bash
   scp -r frontend/dist root@vm2511041557:~/FinAdvisor_AI_bot/frontend/
   ```
3. На сервере перезапустить API:
   ```bash
   sudo systemctl restart finadvisor-api.service
   ```

## Скрипты

| Скрипт | Назначение |
|--------|------------|
| `scripts/deploy.sh` | После git pull — перезапуск API и бота |
| `scripts/build_frontend.sh` | Сборка фронта (сначала проверка файлов, затем npm install/build) |
| `scripts/check_frontend_files.sh` | Проверка наличия всех файлов фронтенда (запускать локально перед push) |
| `scripts/run_bot_venv.sh`, `scripts/run_api_venv.sh` | Вызываются systemd, вручную не запускать |
