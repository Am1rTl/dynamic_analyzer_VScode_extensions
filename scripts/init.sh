#!/bin/bash
#
# init.sh — подготавливает изолированную среду для VSCode и запускает
# мониторинг расширений вместе с веб-интерфейсом анализатора.
#
# Использование: sudo ./scripts/init.sh
#
# Сценарий создаёт отдельного пользователя vscext, накатывает ACL/iptables
# правила и поднимает сопутствующие сервисы (kernel logger, strace,
# resource monitor, Flask dashboard).

set -e

# ---- Настройки -------------------------------------------------------------

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SANDBOX_USER="${VSCEXT_USER:-vscext}"
HOST_USER="${VSCEXT_HOST_USER:-${SUDO_USER:-${USER:-amir}}}"
HOST_HOME="/home/${HOST_USER}"
SANDBOX_HOME="/home/${SANDBOX_USER}"
VSCODE_ARCHIVE="${VSCEXT_ARCHIVE:-${HOST_HOME}/Загрузки/code-stable-x64-1741787903.tar.gz}"
VSCODE_BIN="${SANDBOX_HOME}/asd/VSCode-linux-x64/code"
DASHBOARD_HOST="${VSCEXT_DASHBOARD_HOST:-127.0.0.1}"
DASHBOARD_PORT="${VSCEXT_DASHBOARD_PORT:-5000}"
DASHBOARD_URL="http://${DASHBOARD_HOST}:${DASHBOARD_PORT}/"

# ---- 1. Пользователь-песочница --------------------------------------------

if id "${SANDBOX_USER}" &>/dev/null; then
    echo "[init] Пользователь ${SANDBOX_USER} уже существует, пересоздаю..."
    sudo userdel -r "${SANDBOX_USER}" 2>/dev/null || true
fi

echo "[init] Создаю пользователя ${SANDBOX_USER}..."
sudo useradd -m -s /bin/bash "${SANDBOX_USER}"

# ---- 2. Права на файлы расширений -----------------------------------------

echo "[init] Настраиваю ACL для ${HOST_HOME}..."
sudo mkdir -p "${HOST_HOME}/.vscode/extensions"
sudo setfacl -d -m "u:${SANDBOX_USER}:rwx" "${HOST_HOME}/.vscode/"
sudo setfacl -R -m "u:${SANDBOX_USER}:rwx" "${HOST_HOME}"

# Доступ к дисплею
xhost +SI:localuser:"${SANDBOX_USER}" 2>/dev/null || true

# ---- 3. Каталоги и логи ---------------------------------------------------

echo "[init] Готовлю каталоги логов..."
sudo rm -rf /tmp/asd
mkdir -p /tmp/asd
sudo chown "${USER}":"${USER}" /tmp/asd 2>/dev/null || true

touch /tmp/asda
chmod 666 /tmp/asda

# Логи web-дашборда (он пишет в CWD; запускаем из web_dashboard/)
mkdir -p "${REPO_ROOT}/web_dashboard/data"
touch "${REPO_ROOT}/web_dashboard/data/process_info.log" \
      "${REPO_ROOT}/web_dashboard/data/files_read.log" \
      "${REPO_ROOT}/web_dashboard/data/files_write.log"
chmod 666 "${REPO_ROOT}/web_dashboard/data/"*.log

# Состояние правил
echo "{}" > "${REPO_ROOT}/web_dashboard/data/rules.json"
chmod 666 "${REPO_ROOT}/web_dashboard/data/rules.json"

# ---- 4. Установка VSCode в песочницу --------------------------------------

if [ -f "${VSCODE_ARCHIVE}" ]; then
    echo "[init] Устанавливаю VSCode в ${SANDBOX_HOME}/asd ..."
    sudo mkdir -p "${SANDBOX_HOME}/asd"
    sudo cp "${VSCODE_ARCHIVE}" "${SANDBOX_HOME}/asd/"
    sudo tar -xzvf "${SANDBOX_HOME}/asd/$(basename "${VSCODE_ARCHIVE}")" -C "${SANDBOX_HOME}/asd/"
else
    echo "[init] Архив ${VSCODE_ARCHIVE} не найден, пропускаю установку VSCode."
fi

# ---- 5. Запуск kernel logger (читает /dev/kmsg) ---------------------------

echo "[init] Запускаю kernel logger..."
( cd "${REPO_ROOT}" && sudo python scripts/kernel_log_reader.py ) &

# ---- 6. iptables: логирование трафика песочницы ---------------------------

echo "[init] Применяю iptables правило логирования трафика ${SANDBOX_USER}..."
sudo iptables -I OUTPUT -m owner --uid-owner "$(id -u "${SANDBOX_USER}")" \
    -j LOG --log-prefix "VSCode : " --log-level 4

# ---- 7. Запуск сервисов мониторинга и дашборда ----------------------------

echo "[init] Запускаю сервисы мониторинга и Flask dashboard..."

(
    cd "${REPO_ROOT}/web_dashboard"
    sudo python "${REPO_ROOT}/web_dashboard/modules/strace.py" &
    python       "${REPO_ROOT}/web_dashboard/modules/strace_log.py" &
    python       "${REPO_ROOT}/web_dashboard/modules/get_sys_info.py" &
    sudo python  "${REPO_ROOT}/web_dashboard/app.py" &
    (command -v firefox-esr >/dev/null && firefox-esr "${DASHBOARD_URL}") || \
    (command -v xdg-open   >/dev/null && xdg-open   "${DASHBOARD_URL}") || \
    echo "[init] Откройте ${DASHBOARD_URL} в браузере."
)

# ---- 8. Запуск VSCode под песочницей --------------------------------------

if [ -x "${VSCODE_BIN}" ]; then
    echo "[init] Запускаю VSCode под ${SANDBOX_USER}..."
    sudo -u "${SANDBOX_USER}" \
        "${VSCODE_BIN}" --extensions-dir "${HOST_HOME}/.vscode/extensions/" &
else
    echo "[init] VSCode не найден в ${VSCODE_BIN}, запустите его вручную под ${SANDBOX_USER}."
fi

echo "[init] Готово. Дашборд: ${DASHBOARD_URL}"
