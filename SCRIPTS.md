# Запуск и деплой FinAdvisor

**Правила проекта (Git, VPS, деплой):** **PROJECT_RULES.md**

Полная пошаговая инструкция для сервера: **deploy/README.md**.

Кратко:
- **После git pull:** `./scripts/deploy.sh`
- **Если меняли фронт:** `./scripts/build_frontend.sh` и `sudo systemctl restart finadvisor-api.service`
- **Перед пушем (локально):** `./scripts/check_frontend_files.sh` — проверка, что все файлы фронтенда на месте

**Миграция БД (профиль, чек-листы, цель месяца):** один раз применить `scripts/migrate_users_profile.sql`:
```bash
psql -U postgres -d FinAdvisor_Beta -f scripts/migrate_users_profile.sql
```
(замените `FinAdvisor_Beta` на имя вашей БД)
