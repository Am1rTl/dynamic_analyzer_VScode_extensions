# `dynamic/` — динамический мониторинг процессов

Запускается как обычный Python-процесс и в фоне следит за всеми
процессами, связанными с VSCode. Блокирует подозрительную активность
по заранее заданным правилам.

## Запуск

```bash
# Из корня репозитория
python3 dynamic/run.py --rules configs/rules.json
```

Чтобы изолировать запуск VSCode в отдельном пользователе с
cgroup/iptables/ACL:

```bash
sudo python3 dynamic/isolated_run.py
```

## Файлы

| Файл | Назначение |
|------|-----------|
| `monitor.py` | Класс `VSCodeSecurityMonitor` — обход процессов, проверка по правилам, `terminate()` / `kill()`. |
| `run.py` | CLI-обёртка. Поддерживает `--rules PATH`. |
| `isolated_run.py` | Создание пользователя `vscode_sandbox`, настройка `iptables`/`setfacl`/`cgroup`, запуск VSCode под этим пользователем. |

## Где смотреть логи

- `logs/vscode_security_monitor.log` — основной лог монитора
  (создаётся автоматически при первом запуске).
- `dmesg` — iptables-логи трафика песочницы (если включено в `init.sh`).
