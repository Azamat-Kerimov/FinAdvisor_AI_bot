# Запуск и деплой FinAdvisor

Полная пошаговая инструкция для сервера: **deploy/README.md**.

Кратко:
- **После git pull:** `./scripts/deploy.sh`
- **Если меняли фронт:** `./scripts/build_frontend.sh` и `sudo systemctl restart finadvisor-api.service`
- **Перед пушем (локально):** `./scripts/check_frontend_files.sh` — проверка, что все файлы фронтенда на месте
