# Деплой FinAdvisor (systemd)

Ошибка **502 Bad Gateway** и **python: not found** возникают, когда systemd запускает сервисы без активации venv: в PATH нет `python`, поэтому процесс не стартует.

## Решение: unit-файлы с полным путём к Python

Сервисы запускают **скрипты** `scripts/run_bot_venv.sh` и `scripts/run_api_venv.sh`. Они ищут окружение в каталоге проекта: сначала `venv`, затем `.venv`.

После **git pull** дайте скриптам права на выполнение: `chmod +x scripts/*.sh`

### Ошибка «не найден venv/bin/activate или .venv/bin/activate»

Значит в каталоге проекта **нет** папки `venv` и нет `.venv`. Systemd не видит то окружение, которое вы активируете вручную в SSH — нужно создать venv **внутри проекта**:

```bash
cd /root/FinAdvisor_AI_bot
python3 -m venv venv
. venv/bin/activate
pip install -r requirements.txt
chmod +x scripts/*.sh
```

После этого перезапустите сервисы:

```bash
sudo systemctl restart finadvisor-api.service
sudo systemctl restart finadvisorbot.service
```

### Если проект в другом каталоге

Проект не в `/root/FinAdvisor_AI_bot` — откройте оба `.service` и замените путь `/root/FinAdvisor_AI_bot` на свой (например `/home/user/FinAdvisor_AI_bot`).

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

Если окружение в нестандартной папке (не `venv` и не `.venv`), отредактируйте `scripts/run_bot_venv.sh` и `scripts/run_api_venv.sh`, добавив проверку своей папки по образцу существующих.

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
