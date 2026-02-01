# Деплой FinAdvisor (systemd)

Ошибка **502 Bad Gateway** и **python: not found** возникают, когда systemd запускает сервисы без активации venv: в PATH нет `python`, поэтому процесс не стартует.

## Решение: unit-файлы с полным путём к Python

В unit-файлах используется **активация venv через bash** (`. venv/bin/activate`), а не прямой вызов `venv/bin/python3`. Так сервисы работают и когда в venv есть только `python`, и когда путь к venv другой (например `.venv` — тогда замените `venv` на `.venv` в обоих файлах).

### Если проект или venv в другом месте

- Проект не в `/root/FinAdvisor_AI_bot` — замените этот путь в обоих `.service` на свой (например `/home/user/FinAdvisor_AI_bot`).
- Виртуальное окружение в папке `.venv`, а не `venv` — в `ExecStart` во всех `.service` замените `venv/bin/activate` на `.venv/bin/activate`.

### Полный деплой (сборка фронта + перезапуск)

После **git pull** на сервере запустите один скрипт — он соберёт фронт и перезапустит оба сервиса (сайт начнёт отдавать React, бот — отвечать):

```bash
./scripts/deploy_server.sh
```

### Установка unit-файлов и перезапуск (один раз)

На сервере, из корня проекта:

```bash
# Скопировать unit-файлы в systemd (при необходимости поправьте путь в файлах)
sudo cp deploy/finadvisor-api.service deploy/finadvisorbot.service /etc/systemd/system/

# Перечитать конфигурацию systemd
sudo systemctl daemon-reload

# Включить и запустить сервисы
sudo systemctl enable finadvisor-api.service finadvisorbot.service
sudo systemctl restart finadvisor-api.service
sudo systemctl restart finadvisorbot.service

# Проверить статус
sudo systemctl status finadvisor-api.service finadvisorbot.service
```

Дальше для перезапуска после обновления кода достаточно:

```bash
sudo systemctl restart finadvisor-api.service
sudo systemctl restart finadvisorbot.service
```

### Проверка логов

Если бот падает (status=1/FAILURE), смотрите **последние строки** — там будет причина (переменные .env или БД):

```bash
sudo journalctl -u finadvisorbot.service -n 40 --no-pager
```

В логах ищите: «Ошибка: в .env не заданы переменные» или «Ошибка подключения к БД». Для живого вывода:

```bash
sudo journalctl -u finadvisor-api.service -f
sudo journalctl -u finadvisorbot.service -f
```

Если в логах «Failed to locate executable» или «No such file», проверьте, что venv есть и в нём есть `activate`:

```bash
ls -la /root/FinAdvisor_AI_bot/venv/bin/activate
# или, если окружение в .venv:
ls -la /root/FinAdvisor_AI_bot/.venv/bin/activate
```

Если папка окружения называется `.venv`, во всех `.service` в строке `ExecStart` замените `venv/bin/activate` на `.venv/bin/activate`, затем снова `daemon-reload` и `restart`.

---

### Если на сервере «Killed» при сборке фронта (мало RAM)

Скрипт сборки ограничивает память Node (768 MB). Если `npm install` или `npm run build` всё равно убиваются:

1. **Соберите фронт локально** (на своём ПК, где достаточно памяти):
   ```bash
   cd frontend && npm install && npm run build && cd ..
   ```
2. **Залейте только папку `frontend/dist`** на сервер (scp, rsync или архив):
   ```bash
   scp -r frontend/dist root@ваш-сервер:~/FinAdvisor_AI_bot/frontend/
   ```
3. На сервере **не запускайте** `./scripts/build_frontend.sh`, а только перезапустите сервисы:
   ```bash
   sudo systemctl restart finadvisor-api.service finadvisorbot.service
   ```
