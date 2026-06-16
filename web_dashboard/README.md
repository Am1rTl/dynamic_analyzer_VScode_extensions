# `web_dashboard/` — Flask-приложение и сервисы мониторинга

Точка входа: `app.py`. Поднимает веб-интерфейс на `127.0.0.1:5000` и
применяет правила безопасности, которые пользователь задаёт через UI.

## Быстрый старт

```bash
cd web_dashboard
sudo python3 app.py
# откройте http://127.0.0.1:5000/
```

> `sudo` нужен для `rule_manager.py`, который дёргает `iptables` и
> `setfacl`. Без `sudo` правила сохранятся в JSON, но применены не будут.

## Структура

```
web_dashboard/
├── app.py                  # Flask: маршруты /, /about, /rules, /set_rule, /logs, /guide
├── modules/                # переиспользуемые Python-модули
│   ├── strace.py           #   strace -p <pid> -e trace=open,read,write → /tmp/asd
│   ├── strace_log.py       #   читает /tmp/asd → files_read.log / files_write.log
│   ├── get_sys_info.py     #   CPU/RAM основного процесса + детей → process_info.log
│   ├── rule_manager.py     #   iptables / setfacl / ulimit
│   └── format_logs.py      #   парсер /tmp/asda → табличка для /logs
├── templates/              # Jinja2-шаблоны
└── data/                   # runtime-состояние (rules.json, *.log)
```

## Маршруты

| URL | Что делает |
|-----|-----------|
| `GET /` | Список установленных расширений + поиск по marketplace. |
| `GET /about/<ext_id>` | Детальная страница расширения. |
| `GET /rules` | Список текущих правил (страница-просмотр). |
| `GET /set_rule` | Конструктор правил (UI). |
| `POST /save_data` | Сохраняет JSON-правила и применяет их. |
| `GET /clear_rules` | Сбрасывает сохранённые правила. |
| `GET /get_saved_rules` | Возвращает текущий JSON правил. |
| `GET /logs` | Графики CPU/RAM + сетевые соединения + файловые списки. |
| `GET /get_chart_data` | JSON для графиков на `/logs`. |
| `GET /guide` | Краткая справка. |
| `GET /install_extension/<id>` | `code --install-extension <id>`. |
| `DELETE /delete_ext/<id>` | `code --uninstall-extension <id>`. |
| `GET /check_extension/<id>` | Установлено ли расширение. |
| `POST /search_extension` | Поиск по marketplace. |
