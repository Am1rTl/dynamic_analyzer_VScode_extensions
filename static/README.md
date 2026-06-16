# `static/` — статический анализатор расширений

Сканирует `package.json` и `.js`/`.ts` файлы расширения на наличие
опасных API и подозрительных зависимостей. Не требует запущенного
VSCode — анализирует файлы расширения «как есть».

## Запуск

```bash
# Из корня репозитория
python3 static/run.py <путь-к-расширению>

# Если путь не указан — анализирует ~/.vscode/extensions целиком
python3 static/run.py
```

## Файлы

| Файл | Назначение |
|------|-----------|
| `analyzer.py` | Класс `VSCodeExtensionAnalyzer` — поиск паттернов, чтение `package.json`, генерация отчёта. |
| `run.py` | CLI-обёртка: парсит аргументы, вызывает `analyze()` и печатает `generate_report()`. |

## Что ищется

- `child_process.exec`, `spawn(`, `shellExecute` — выполнение shell-команд.
- `fs.writeFile`, `fs.unlink`, `fs.rmdir`, `fs.mkdir` — файловые операции.
- `http.request`, `https.request`, `net.connect`, `fetch(` — сетевые вызовы
  (плюс автоматически собираются все URL).
- `eval(`, `Function(`, `new Function` — динамическая компиляция JS.
- Зависимости из `package.json`, в имени которых встречаются `shell`,
  `exec`, `spawn`, `child_process`, `puppeteer`, `selenium`, `crypto` и т. п.
