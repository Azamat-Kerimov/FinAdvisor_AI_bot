# Деплой FinAdvisor (systemd)

Ошибка **502 Bad Gateway** и **python: not found** возникают, когда systemd запускает сервисы без активации venv: в PATH нет `python`, поэтому процесс не стартует.

## Решение: unit-файлы с полным путём к Python

В unit-файлах используется **активация venv через bash** (`. venv/bin/activate`), а не прямой вызов `venv/bin/python3`. Так сервисы работают и когда в venv есть только `python`, и когда путь к venv другой (например `.venv` — тогда замените `venv` на `.venv` в обоих файлах).

### Если проект или venv в другом месте

- Проект не в `/root/FinAdvisor_AI_bot` — замените этот путь в обоих `.service` на свой (например `/home/user/FinAdvisor_AI_bot`).
- Виртуальное окружение в папке `.venv`, а не `venv` — в `ExecStart` замените `venv/bin/activate` на `.venv/bin/activate` в обоих файлах.

### Установка и перезапуск

На сервере, из корня проекта:

```bash
# Скопировать unit-файлы в systemd (при необходимости поправьте путь в файлах)
sudo cp deploy/finadvisor-api.service deploy/finadvisorbot.service /etc/systemd/system/

# Перечитать конфигурацию systemd
sudo systemctl daemon-reload

# Включить автозапуск при загрузке (опционально)
sudo systemctl enable finadvisor-api.service finadvisorbot.service

# Запустить/перезапустить сервисы
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

Если папка окружения называется `.venv`, в обоих `.service` в строке `ExecStart` замените `venv/bin/activate` на `.venv/bin/activate`, затем снова `daemon-reload` и `restart`.
