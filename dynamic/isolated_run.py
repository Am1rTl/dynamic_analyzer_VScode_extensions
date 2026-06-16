import os
import subprocess
import pwd
import shutil
import json
import psutil
from pathlib import Path

# Корень репозитория = dynamic/..
REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = REPO_ROOT / "configs" / "config.example.json"


def load_config(config_path: str | None = None):
    """Загружает конфигурацию из JSON-файла.

    По умолчанию берётся ``configs/config.example.json`` из корня репозитория.
    """
    path = Path(config_path) if config_path else DEFAULT_CONFIG
    try:
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        print(f"[ERROR] Файл конфигурации не найден: {path}")
        return {}

def create_sandbox_user(username="vscode_sandbox"):
    """Создает нового пользователя для изолированного запуска VSCode."""
    try:
        pwd.getpwnam(username)
        print(f"[INFO] Пользователь {username} уже существует.")
    except KeyError:
        print(f"[INFO] Создаю пользователя {username}...")
        subprocess.run(["sudo", "useradd", "-m", "-s", "/bin/bash", username], check=True)

def apply_network_restrictions(username, enable):
    """Настраивает iptables для блокировки или разрешения сети."""
    if not enable:
        print("[INFO] Блокирую сетевые соединения...")
        subprocess.run(["sudo", "iptables", "-A", "OUTPUT", "-m", "owner", "--uid-owner", username, "-j", "DROP"], check=True)

def apply_file_restrictions(username, enable):
    """Настраивает ACL для ограничения доступа к файлам."""
    if not enable:
        print("[INFO] Ограничиваю доступ к файлам...")
        home_dir = f"/home/{username}"
        subprocess.run(["sudo", "setfacl", "-m", "u:{}:r--".format(username), home_dir], check=True)

def apply_cgroup_restrictions(username, max_processes):
    """Настраивает cgroup для ограничения количества процессов."""
    print(f"[INFO] Ограничиваю число процессов до {max_processes}...")
    cgroup_path = f"/sys/fs/cgroup/pids/{username}"

    # Создаем cgroup, если он еще не существует
    subprocess.run(["sudo", "mkdir", "-p", cgroup_path], check=True)
    
    # Применяем ограничения на количество процессов
    try:
        subprocess.run(["sudo", "bash", "-c", f"echo {max_processes} > {cgroup_path}/pids.max"], check=True)
        subprocess.run(["sudo", "bash", "-c", f"echo $(id -u {username}) > {cgroup_path}/cgroup.procs"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Ошибка при настройке cgroup: {e}")
        # Выводим сообщение об ошибке и продолжаем выполнение


def is_extension_process(proc):
    """Проверяет, является ли процесс расширением VSCode."""
    try:
        # Проверяем, запущен ли процесс с использованием имени или других признаков VSCode
        if 'code' in proc.name():
            # Мы можем попробовать извлечь дополнительные признаки расширения по аргументам или файлам
            # Например, можно проверить команду, с которой был запущен процесс
            if "--extensionHost" in proc.cmdline():
                return True
    except psutil.NoSuchProcess:
        return False
    return False

def isolate_extension_processes(vscode_pid, username):
    """Изолирует только процессы, связанные с расширениями."""
    print("[INFO] Изолирую процессы, связанные с расширениями...")
    
    # Получаем все дочерние процессы VSCode
    for proc in psutil.Process(vscode_pid).children(recursive=True):
        if is_extension_process(proc):
            print(f"[INFO] Изолирую процесс расширения: {proc.pid}")
            subprocess.run(["sudo", "cgexec", "-g", "pids:{}/extension_group".format(username), "kill", "-STOP", str(proc.pid)])
            
            # Применяем ограничения на ресурсы
            apply_network_restrictions(username, False)
            apply_file_restrictions(username, False)
            apply_cgroup_restrictions(username, config.get("max_processes", 10))
            subprocess.run(["sudo", "cgexec", "-g", "pids:{}/extension_group".format(username), "kill", "-CONT", str(proc.pid)])

def launch_vscode(username):
    """Запускает VSCode под новым пользователем."""
    print("[INFO] Запускаю VSCode...")
    process = subprocess.Popen(["sudo", "-u", username, "code"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    # Ожидаем, пока запустится основной процесс VSCode
    vscode_pid = process.pid
    print(f"[INFO] PID VSCode: {vscode_pid}")
    
    # Изолируем дочерние процессы (расширения)
    isolate_extension_processes(vscode_pid, username)

if __name__ == "__main__":
    SANDBOX_USER = "vscode_sandbox"
    config = load_config()
    
    create_sandbox_user(SANDBOX_USER)
    apply_network_restrictions(SANDBOX_USER, config.get("network", True))
    apply_file_restrictions(SANDBOX_USER, config.get("file_access", True))
    apply_cgroup_restrictions(SANDBOX_USER, config.get("max_processes", 10))
    launch_vscode(SANDBOX_USER)
