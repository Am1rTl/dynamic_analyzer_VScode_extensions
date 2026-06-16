import psutil
import time
import signal
import logging
import json
import os
import re
from pathlib import Path
from typing import Dict, List, Set, Optional
from threading import Thread

class VSCodeSecurityMonitor:
    def __init__(self, rules_file: str = "security_rules.json"):
        self.extensions_list = []
        self.rules_file = Path(rules_file)
        self.suspicious_processes: Set[int] = set()
        self.is_monitoring = False
        self.logger = self._setup_logger()
        self.rules = self._load_security_rules()
        self._discover_extensions()
        
    def _setup_logger(self) -> logging.Logger:
        """Настройка логирования."""
        logger = logging.getLogger("VSCodeSecurityMonitor")
        logger.setLevel(logging.INFO)
        
        # Создаем директорию для логов если её нет
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        handler = logging.FileHandler("logs/vscode_security_monitor.log")
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
        # Добавляем вывод в консоль
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        return logger

    def _load_security_rules(self) -> Dict:
        """Загрузка или создание правил безопасности."""
        default_rules = {
            "process_control": {
                "blocked_executables": [
                    "cmd.exe", "powershell.exe", "bash.exe", "python.exe",
                    "node.exe", "npm.exe", "wscript.exe", "cscript.exe"
                ],
                "allowed_executables": ["code.exe", "code-insiders.exe"],
                "max_child_processes": 5
            },
            "resource_limits": {
                "max_memory_usage_mb": 500,
                "max_cpu_percent": 50,
                "max_disk_read_mb_sec": 100,
                "max_disk_write_mb_sec": 50
            },
            "network_security": {
                "blocked_network_ports": [20, 21, 22, 23, 25, 53, 80, 443],
                "blocked_network_hosts": [
                    "raw.githubusercontent.com",
                    "pastebin.com",
                    "ngrok.io"
                ]
            },
            "filesystem_protection": {
                "blocked_paths": [
                    "C:\\Windows\\System32",
                    "/etc/",
                    "/usr/bin"
                ],
                "blocked_extensions": [
                    ".exe", ".dll", ".sys", ".bat", ".cmd", ".ps1", ".sh"
                ]
            }
        }

        if self.rules_file.exists():
            try:
                with open(self.rules_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.error(f"Ошибка загрузки правил: {e}")
                return default_rules
        else:
            # Создаем файл с правилами по умолчанию
            with open(self.rules_file, 'w') as f:
                json.dump(default_rules, f, indent=4)
            return default_rules

    def _discover_extensions(self):
        """Автоматическое обнаружение установленных расширений."""
        possible_extension_paths = [
            # Linux
            Path.home() / '.vscode' / 'extensions',
            Path.home() / '.vscode-server' / 'extensions',
            # Windows
            Path.home() / 'AppData' / 'Local' / 'Programs' / 'Microsoft VS Code' / 'resources' / 'app' / 'extensions',
            Path.home() / '.vscode-server' / 'extensions',
            # macOS
            Path.home() / 'Library' / 'Application Support' / 'Code' / 'User' / 'extensions',
        ]

        self.extensions_list = []
        
        for base_path in possible_extension_paths:
            if base_path.exists():
                self.logger.info(f"Сканирование директории расширений: {base_path}")
                
                try:
                    for extension_dir in base_path.iterdir():
                        if extension_dir.is_dir():
                            package_json = extension_dir / 'package.json'
                            
                            if package_json.exists():
                                try:
                                    with open(package_json, 'r', encoding='utf-8') as f:
                                        data = json.load(f)
                                        
                                    if 'publisher' in data and 'name' in data:
                                        extension_id = f"{data['publisher']}.{data['name']}"
                                        if extension_id not in self.extensions_list:
                                            self.extensions_list.append(extension_id)
                                            self.logger.info(f"Обнаружено расширение: {extension_id}")
                                            
                                except Exception as e:
                                    self.logger.warning(f"Ошибка чтения package.json для {extension_dir}: {e}")
                                    
                except PermissionError as e:
                    self.logger.error(f"Ошибка доступа к директории {base_path}: {e}")

        self.logger.info(f"Всего найдено расширений: {len(self.extensions_list)}")

    def _is_suspicious_process(self, proc: psutil.Process) -> bool:
        """Проверка процесса на подозрительную активность."""
        try:
            # Проверка имени исполняемого файла
            proc_name = proc.name().lower()
            if proc_name in self.rules["process_control"]["blocked_executables"]:
                self.logger.warning(f"Обнаружен заблокированный процесс: {proc_name}")
                return True

            # Проверка использования памяти
            memory_usage_mb = proc.memory_info().rss / 1024 / 1024
            if memory_usage_mb > self.rules["resource_limits"]["max_memory_usage_mb"]:
                self.logger.warning(f"Превышение использования памяти: {memory_usage_mb}MB")
                return True

            # Проверка использования CPU
            if proc.cpu_percent() > self.rules["resource_limits"]["max_cpu_percent"]:
                self.logger.warning(f"Превышение использования CPU: {proc.cpu_percent()}%")
                return True

            # Проверка сетевых соединений
            for conn in proc.connections():
                if conn.status == 'ESTABLISHED':
                    if conn.laddr.port in self.rules["network_security"]["blocked_network_ports"]:
                        self.logger.warning(f"Заблокированное сетевое соединение: port {conn.laddr.port}")
                        return True

            # Проверка открытых файлов
            for file in proc.open_files():
                file_path = Path(file.path)
                if any(file_path.match(pattern) for pattern in self.rules["filesystem_protection"]["blocked_paths"]):
                    self.logger.warning(f"Подозрительный доступ к файлу: {file.path}")
                    return True
                if file_path.suffix in self.rules["filesystem_protection"]["blocked_extensions"]:
                    self.logger.warning(f"Попытка доступа к заблокированному типу файла: {file.path}")
                    return True

            return False
            
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
            return False

    def _block_process(self, pid: int):
        """Блокировка подозрительного процесса."""
        try:
            process = psutil.Process(pid)
            self.logger.warning(f"Блокировка процесса {pid} ({process.name()})")
            
            # Сначала пробуем мягкое завершение
            process.terminate()
            
            # Даем процессу 3 секунды на завершение
            time.sleep(3)
            
            # Если процесс все еще жив, убиваем его
            if process.is_running():
                process.kill()
                
            self.suspicious_processes.add(pid)
            
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            self.logger.error(f"Ошибка при блокировке процесса {pid}: {e}")

    def _monitor_process_tree(self, parent_pid: int):
        """Рекурсивный мониторинг дерева процессов."""
        try:
            parent = psutil.Process(parent_pid)
            children = parent.children(recursive=True)
            
            # Проверяем родительский процесс
            if self._is_suspicious_process(parent):
                self._block_process(parent_pid)
                return
                
            # Проверяем дочерние процессы
            for child in children:
                if child.pid not in self.suspicious_processes:
                    if self._is_suspicious_process(child):
                        self._block_process(child.pid)
                        
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    def find_extension_processes(self) -> List[psutil.Process]:
        """Поиск процессов всех отслеживаемых расширений."""
        extension_processes = []
        for proc in psutil.process_iter(['name', 'cmdline']):
            try:
                cmdline = ' '.join(proc.cmdline())
                if any(ext_id in cmdline for ext_id in self.extensions_list):
                    extension_processes.append(proc)
                    self.logger.debug(f"Найден процесс расширения: {proc.name()} (PID: {proc.pid})")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return extension_processes

    def analyze_extension(self, extension_id: str) -> Dict:
        """Анализ конкретного расширения."""
        result = {
            'extension_id': extension_id,
            'status': 'unknown',
            'details': {},
            'warnings': []
        }

        # Поиск директории расширения
        for base_path in [Path.home() / '.vscode' / 'extensions']:
            if base_path.exists():
                for ext_dir in base_path.iterdir():
                    if ext_dir.is_dir():
                        package_json = ext_dir / 'package.json'
                        if package_json.exists():
                            try:
                                with open(package_json, 'r', encoding='utf-8') as f:
                                    data = json.load(f)
                                    if f"{data.get('publisher')}.{data.get('name')}" == extension_id:
                                        result['status'] = 'found'
                                        result['details'] = {
                                            'version': data.get('version'),
                                            'description': data.get('description'),
                                            'dependencies': data.get('dependencies', {}),
                                            'permissions': data.get('contributes', {})
                                        }
                                        
                                        # Анализ подозрительных зависимостей
                                        suspicious_deps = []
                                        for dep in data.get('dependencies', {}):
                                            if any(keyword in dep.lower() for keyword in ['shell', 'exec', 'spawn', 'crypto']):
                                                suspicious_deps.append(dep)
                                                
                                        if suspicious_deps:
                                            result['warnings'].append({
                                                'type': 'suspicious_dependencies',
                                                'details': suspicious_deps
                                            })
                                            
                                        # Анализ разрешений
                                        if 'commands' in data.get('contributes', {}):
                                            for cmd in data['contributes']['commands']:
                                                if any(keyword in str(cmd).lower() for keyword in ['execute', 'run', 'shell']):
                                                    result['warnings'].append({
                                                        'type': 'suspicious_command',
                                                        'details': cmd
                                                    })
                                                    
                            except Exception as e:
                                result['status'] = 'error'
                                result['details'] = {'error': str(e)}
                                
        return result

    def start_monitoring(self):
        """Запуск мониторинга процессов."""
        if not self.extensions_list:
            self.logger.warning("Нет обнаруженных расширений для мониторинга!")
            return
            
        self.is_monitoring = True
        self.logger.info("Запуск мониторинга расширений VSCode")
        
        def monitoring_loop():
            while self.is_monitoring:
                extension_processes = self.find_extension_processes()
                for proc in extension_processes:
                    self._monitor_process_tree(proc.pid)
                    
                # Периодическое обновление списка расширений
                if time.time() % 300 < 1:  # Каждые 5 минут
                    self._discover_extensions()
                    
                time.sleep(1)
                
        # Запуск мониторинга в отдельном потоке
        monitor_thread = Thread(target=monitoring_loop, daemon=True)
        monitor_thread.start()
        
        self.logger.info(f"Мониторинг запущен для {len(self.extensions_list)} расширений")

    def stop_monitoring(self):
        """Остановка мониторинга процессов."""
        self.is_monitoring = False
        self.logger.info("Остановка мониторинга расширений")

    def print_monitored_extensions(self):
        """Вывод списка отслеживаемых расширений."""
        print("\nОтслеживаемые расширения:")
        for ext_id in self.extensions_list:
            analysis = self.analyze_extension(ext_id)
            print(f"\n- {ext_id}")
            print(f"  Статус: {analysis['status']}")
            if analysis['status'] == 'found':
                print(f"  Версия: {analysis['details'].get('version')}")
                print(f"  Описание: {analysis['details'].get('description')}")
                if analysis['warnings']:
                    print("  Предупреждения:")
                    for warning in analysis['warnings']:
                        print(f"    - {warning['type']}: {warning['details']}")

def main():
    # Создаем монитор
    monitor = VSCodeSecurityMonitor()
    
    # Выводим информацию о найденных расширениях
    monitor.print_monitored_extensions()
    
    # Запускаем мониторинг
    monitor.start_monitoring()