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

На сервере:

```bash
cd /root/FinAdvisor_AI_bot
git pull
./scripts/deploy.sh
```

Проверка логов:

```bash
sudo journalctl -u finadvisorbot.service -f
```

## 3. Если меняли код фронта

Только тогда пересобрать фронт:

```bash
cd /root/FinAdvisor_AI_bot
./scripts/build_frontend.sh
sudo systemctl restart finadvisor-api.service
```

## Скрипты

| Скрипт | Назначение |
|--------|------------|
| `scripts/deploy.sh` | После git pull — перезапуск API и бота |
| `scripts/build_frontend.sh` | Только когда меняли frontend — сборка и рестарт API |
| `scripts/run_bot_venv.sh`, `scripts/run_api_venv.sh` | Вызываются systemd, вручную не запускать |
