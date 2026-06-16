#!/bin/bash
#
# stop.sh — гасит все фоновые процессы, которые поднимает scripts/init.sh.

set +e

echo "[stop] Останавливаю сервисы..."

pkill -f "scripts/kernel_log_reader.py"  2>/dev/null
pkill -f "web_dashboard/app.py"          2>/dev/null
pkill -f "web_dashboard/modules/strace.py"       2>/dev/null
pkill -f "web_dashboard/modules/strace_log.py"   2>/dev/null
pkill -f "web_dashboard/modules/get_sys_info.py" 2>/dev/null

# Если есть пользователь vscext — остановим его процессы
if id vscext &>/dev/null; then
    pkill -u vscext 2>/dev/null
fi

echo "[stop] Готово."
