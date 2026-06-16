# Dynamic Analyzer for VSCode Extensions

> Набор инструментов для статического и динамического анализа расширений
> Visual Studio Code, в комплекте с веб-панелью для просмотра логов,
> редактирования правил и управления изолированным запуском VSCode.

Проект объединяет три уровня защиты от потенциально вредоносных расширений:

1. **Статический анализ** — построчное сканирование `package.json`,
   `.js`/`.ts` файлов расширения на наличие опасных API
   (`child_process`, `eval`, `fs.rmdir`, `http.request`, …).
2. **Динамический мониторинг** — наблюдение за процессом VSCode и его
   дочерними процессами в реальном времени: блокировка по правилам,
   изоляция в отдельном пользователе, лимиты cgroup/iptables/ACL.
3. **Web-дашборд** — Flask-приложение, которое агрегирует всё
   вышеперечисленное: показывает установленные расширения, рисует
   графики CPU/RAM, визуализирует сетевой и файловый трафик, позволяет
   редактировать правила и применять их в один клик.

---

## 📂 Структура репозитория

```
.
├── static/                       # Статический анализатор (поиск опасных паттернов)
│   ├── analyzer.py               #   класс VSCodeExtensionAnalyzer
│   └── run.py                    #   CLI-обёртка с argparse
│
├── dynamic/                      # Динамический мониторинг процессов
│   ├── monitor.py                #   класс VSCodeSecurityMonitor (psutil)
│   ├── run.py                    #   CLI-обёртка
│   └── isolated_run.py           #   запуск VSCode в cgroup-песочнице
│
├── web_dashboard/                # Flask-приложение + сервисы мониторинга
│   ├── app.py                    #   маршруты: /, /about, /rules, /logs, …
│   ├── modules/                  #   переиспользуемые модули
│   │   ├── strace.py             #     слежение за syscalls через strace
│   │   ├── strace_log.py         #     парсинг strace-логов в файловые списки
│   │   ├── get_sys_info.py       #     CPU/RAM по основному процессу и детям
│   │   ├── rule_manager.py       #     iptables + ACL + ulimit
│   │   └── format_logs.py        #     парсинг /tmp/asda → читаемые логи
│   ├── templates/                #   Jinja2-шаблоны страниц
│   └── data/                     #   runtime-состояние (rules.json и т.п.)
│
├── scripts/                      # Вспомогательные утилиты
│   ├── init.sh                   #   поднять всё: пользователь vscext, сервисы, дашборд
│   ├── stop.sh                   #   потушить все фоновые процессы
│   ├── kernel_log_reader.py      #   читает /dev/kmsg → /tmp/asda
│   └── wait_edits.py             #   утилита для отладки (следит за файлом)
│
├── configs/
│   ├── rules.json                # правила для динамического монитора
│   ├── config.example.json       # пример конфигурации для isolated_run.py
│   └── example_rules.json        # снимок сохранённых web-правил
│
├── docs/                         # дополнительные материалы
├── requirements.txt
├── .gitignore
└── README.md                     # ← вы здесь
```

---

## 🚀 Быстрый старт

### 1. Установка зависимостей

```bash
# Системные пакеты (для динамической части; Debian/Ubuntu/Kali)
sudo apt-get install -y python3 python3-pip iptables acl strace

# Python-зависимости
pip install -r requirements.txt
```

> Полный сценарий песочницы требует `sudo` и работает только на Linux
> (используются `iptables`, `setfacl`, `cgroup v1`).

### 2. Статический анализ расширения

```bash
# Анализ конкретного расширения
python3 static/run.py ~/.vscode/extensions/ms-python.python-2024.1.0

# Анализ всей папки extensions
python3 static/run.py ~/.vscode/extensions
```

В отчёте будут перечислены:

- подозрительные зависимости (`shell`, `exec`, `puppeteer`, …);
- файлы и номера строк с `child_process`, `eval`, `fetch`, `fs.writeFile`;
- HTTP(S) URL, к которым обращается расширение.

### 3. Динамический мониторинг

```bash
python3 dynamic/run.py --rules configs/rules.json
```

Монитор:

1. Найдёт установленные расширения в `~/.vscode/extensions` и
   `~/.vscode-server/extensions`.
2. Запустит фоновый поток, который ежесекундно проверяет процессы.
3. Заблокирует подозрительные по правилам из `configs/rules.json`
   (например, запуск `cmd.exe` или подключение к запрещённому порту).
4. Пишет лог в `logs/vscode_security_monitor.log`.

Изоляция на уровне пользователя/cgroup:

```bash
sudo python3 dynamic/isolated_run.py
```

Создаётся пользователь `vscode_sandbox`, накатываются `iptables`/`setfacl`/`cgroup`
правила из `configs/config.example.json`, и под этим пользователем
запускается `code`.

### 4. Web-дашборд

Самый простой путь — через скрипт-обёртку, который сделает почти всё сам:

```bash
sudo ./scripts/init.sh
```

Скрипт:

- создаст пользователя `vscext` (или `vscode_sandbox` для `isolated_run.py`);
- настроит ACL на домашнюю директорию;
- поставит `iptables` правило для логирования трафика песочницы;
- запустит `kernel_log_reader.py`, `strace.py`, `strace_log.py`,
  `get_sys_info.py` и Flask `app.py`;
- откроет `http://127.0.0.1:5000/` в Firefox.

Чтобы остановить всё:

```bash
sudo ./scripts/stop.sh
```

#### Ручной запуск дашборда

```bash
cd web_dashboard
sudo python3 app.py
# откройте http://127.0.0.1:5000/
```

> `sudo` нужен, потому что `rule_manager.py` на лету правит `iptables`
> и `setfacl`. Если запустить без `sudo`, страница «Настроить правила»
> покажет ошибки при применении правил, но сам UI продолжит работать.

---

## 🧩 Архитектура

### Статический анализатор (`static/`)

`VSCodeExtensionAnalyzer` (`static/analyzer.py`) применяет набор
регулярных выражений к каждому `.js`/`.ts` файлу расширения, минуя
`node_modules`. Категории:

| Категория | Примеры паттернов |
|-----------|-------------------|
| `shell_execution` | `child_process.exec`, `spawn(`, `shellExecute` |
| `file_operations` | `fs.writeFile`, `fs.unlink`, `fs.rmdir`, `fs.mkdir` |
| `network` | `http.request`, `https.request`, `net.connect`, `fetch(` |
| `eval_execution` | `eval(`, `Function(`, `new Function` |

Плюс отдельный чек `package.json` на «опасные» имена зависимостей
(`shell`, `exec`, `puppeteer`, `selenium`, `crypto` и т. п.).

### Динамический монитор (`dynamic/`)

`VSCodeSecurityMonitor` (`dynamic/monitor.py`) обходит дерево процессов
VSCode раз в секунду и для каждого проверяет:

- имя исполняемого файла — есть ли в `process_control.blocked_executables`;
- `memory_info().rss` — превышение `resource_limits.max_memory_usage_mb`;
- `cpu_percent()` — превышение `resource_limits.max_cpu_percent`;
- `connections()` — порт входит в `network_security.blocked_network_ports`;
- `open_files()` — путь/расширение из `filesystem_protection`.

При срабатывании процесс сначала `terminate()` (3 секунды), затем
`kill()`.

### Web-дашборд (`web_dashboard/`)

```
┌──────────────┐    ┌──────────────────┐    ┌────────────────┐
│  strace.py   │───▶│ /tmp/asd/*.log   │───▶│ strace_log.py  │──▶ files_read/write.log
└──────────────┘    └──────────────────┘    └────────────────┘

┌──────────────┐    ┌──────────────────┐
│ get_sys_info │───▶│ process_info.log │──▶ GET /logs (графики)
└──────────────┘    └──────────────────┘

┌──────────────┐    ┌──────────────────┐
│ kernel log   │───▶│ /tmp/asda        │──▶ format_logs.get_logs()
└──────────────┘    └──────────────────┘

┌──────────────────────────────────────────────────────┐
│ Flask app.py:                                       │
│  • /               список расширений + поиск        │
│  • /about/<id>     детали расширения                │
│  • /rules          управление правилами (iptables)  │
│  • /set_rule       редактор JSON-правил             │
│  • /logs           графики + файлы + сеть           │
│  • /guide          README-страница                   │
└──────────────────────────────────────────────────────┘
```

`RuleManager` (`web_dashboard/modules/rule_manager.py`) применяет
следующие группы правил через `subprocess.run([...])`:

| Поле в JSON | Что делает |
|-------------|------------|
| `networkAction` | `blockAll` / `allowAll` — общая политика `iptables` для uid `vscext` |
| `substringRules` | `iptables -m string` — поиск подстроки в пакетах |
| `portRules` | `iptables -p tcp/udp --dport` — блок/разрешение по портам |
| `ipRules` | `iptables -d` — блок/разрешение по IP |
| `readAction` / `writeAction` | `setfacl` на домашнюю директорию |
| `resourceAction` | `ulimit -u/-m` для лимита процессов/памяти |

---

## ⚙️ Конфигурация

### `configs/rules.json`

Используется динамическим монитором (`dynamic/monitor.py`). Структура
документирована в самом файле; ключевые секции:

- `process_control.blocked_executables` — что нельзя запускать
  расширениям;
- `resource_limits` — лимиты RAM/CPU/диска/FD/потоков;
- `network_security.blocked_network_ports` / `blocked_network_hosts`;
- `filesystem_protection.blocked_paths` / `blocked_extensions`;
- `behavior_monitoring.suspicious_patterns` — эвристики для логов;
- `response_actions.on_violation` — реакция (`terminate` / `block` / `warning`);
- `logging` — настройки `logging`-модуля.

### `configs/config.example.json`

Используется `dynamic/isolated_run.py` для тонкой настройки песочницы
(`network`, `file_access`, `max_processes` и т. п.).

### Web-правила (создаются дашбордом)

Правятся через UI на странице `/set_rule` или руками
`web_dashboard/data/rules.json`. Пример снимка —
`configs/example_rules.json`.

---

## 🛠️ Скрипты

| Скрипт | Назначение |
|--------|-----------|
| `scripts/init.sh` | Полный bootstrap: пользователь `vscext`, ACL, iptables, сервисы, VSCode, дашборд. Параметризуется переменными окружения: `VSCEXT_USER`, `VSCEXT_HOST_USER`, `VSCEXT_ARCHIVE`, `VSCEXT_DASHBOARD_HOST`, `VSCEXT_DASHBOARD_PORT`. |
| `scripts/stop.sh` | Корректно гасит все фоновые процессы по `pkill -f`. |
| `scripts/kernel_log_reader.py` | Перенаправляет `cat /dev/kmsg > /tmp/asda` — нужно для графа сети на странице `/logs`. |
| `scripts/wait_edits.py` | Утилита для отладки: раз в секунду печатает, изменился ли файл `/tmp/asd`. |

---

## 🔍 Что показывает дашборд

| Страница | Что внутри |
|----------|-----------|
| `/` (`start.html`) | Список установленных расширений с превью из marketplace, поиск и установка. |
| `/about/<id>` | Полное описание расширения с маркетплейса + действия «установить/удалить». |
| `/rules` (`rules.html`) | Динамический список правил iptables/ACL. |
| `/set_rule` (`configure_rules.html`) | Конструктор правил с чекбоксами, применяется по кнопке «Сохранить». |
| `/logs` (`logs.html`) | CPU/RAM-графики + сетевой лог + список прочитанных/записанных файлов. |
| `/guide` (`guide.html`) | Краткая справка по интерфейсу. |

---

## 🧪 Разработка и отладка

### Полезные команды

```bash
# Проверить, что Flask-приложение вообще стартует
cd web_dashboard && python3 -c "import app; print(app.app.url_map)"

# Проверить статический анализатор
python3 static/run.py --help

# Проверить динамический монитор
python3 dynamic/run.py --help

# Сбросить сохранённые web-правила
rm web_dashboard/data/rules.json
```

### Переменные окружения для init.sh

| Переменная | Назначение | По умолчанию |
|------------|-----------|--------------|
| `VSCEXT_USER` | Имя пользователя-песочницы | `vscext` |
| `VSCEXT_HOST_USER` | Имя «основного» пользователя, чей `~/.vscode/extensions` используется | `${SUDO_USER}` или `${USER}` |
| `VSCEXT_ARCHIVE` | Путь к тарболу VSCode | `~/Загрузки/code-stable-x64-1741787903.tar.gz` |
| `VSCEXT_DASHBOARD_HOST` | Хост Flask | `127.0.0.1` |
| `VSCEXT_DASHBOARD_PORT` | Порт Flask | `5000` |

### Что не нужно коммитить

Все runtime-файлы дашборда (`web_dashboard/data/*.json`, `*.log`)
перечислены в `.gitignore` — они пересоздаются при первом запуске.

---

## 📝 Известные ограничения

- **Только Linux.** `iptables`, `setfacl`, `cgroup v1` — это всё POSIX-only.
  В коде есть Windows-ветка (`tasklist`), но она сейчас закомментирована.
- **Один пользователь-песочница.** Жёстко зашит `vscext`. Несколько
  одновременных песочниц не поддерживаются.
- **`strace` — узкое место.** На тяжёлых расширениях лог растёт очень
  быстро. Для продакшна стоит переходить на `bpf`/`auditd`.
- **Эвристики — это эвристики.** Статический анализатор ловит только
  прямые вызовы `eval`/`exec`; обфусцированный код может пройти мимо.
- **Кодировка логов.** `format_logs.py` ожидает английские колонки iptables;
  при локализации `dmesg`-подобный вывод нужно перепарсить.

---

## 📜 Лицензия

Проект распространяется «как есть» в учебных и исследовательских целях.
Все ссылки на marketplace.visualstudio.com принадлежат Microsoft.
