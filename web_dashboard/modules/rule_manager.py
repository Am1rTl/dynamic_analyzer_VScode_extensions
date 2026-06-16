import json
import os
import subprocess
from typing import Dict, List, Optional

class RuleManager:
    def __init__(self, rules_file: str = "rules"):
        self.rules_file = rules_file
        self.current_rules = self.load_rules()

    def load_rules(self) -> Dict:
        try:
            with open(self.rules_file, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _clear_iptables_rules(self):
        """Очищает все правила iptables"""
        subprocess.run(['iptables', '-F'])  # Очистить все цепочки
        subprocess.run(['iptables', '-X'])  # Удалить пользовательские цепочки
        subprocess.run(['iptables', '-P', 'INPUT', 'ACCEPT'])  # Установить политику по умолчанию
        subprocess.run(['iptables', '-P', 'OUTPUT', 'ACCEPT'])
        subprocess.run(['iptables', '-P', 'FORWARD', 'ACCEPT'])

    def apply_network_rules(self, rules: Dict):
        """Применяет правила сетевой активности"""
        # Сначала очищаем все существующие правила
        self._clear_iptables_rules()
        
        action = rules.get('networkAction')
        if action == 'blockAll':
            # Блокировать весь трафик
            subprocess.run(['iptables', '-A', 'OUTPUT', '-m', 'owner', '--uid-owner', 'vscext', "-j", 'DROP'])
        elif action == 'allowAll':
            # Разрешить весь трафик
            subprocess.run(['iptables', '-P', 'OUTPUT', 'ACCEPT'])
        
        # Применить правила для подстрок
        substring_rules = rules.get('substringRules', [])
        for rule in substring_rules:
            action = 'DROP' if rule.get('action') == 'block' else 'ACCEPT'
            pattern = rule.get('pattern')
            if pattern:
                # Используем string match для проверки подстроки в пакетах
                subprocess.run([
                    'iptables', '-A', 'OUTPUT',
                    '-m', 'owner', '--uid-owner', 'vscext',
                    '-m', 'string', '--string', pattern,
                    '--algo', 'bm',  # Boyer-Moore алгоритм
                    '-j', action
                ])

        # Применить правила для портов
        port_rules = rules.get('portRules', [])
        for rule in port_rules:
            action = 'DROP' if rule.get('action') == 'block' else 'ACCEPT'
            port = rule.get('port')
            if port:
                # Правило для исходящего трафика на указанный порт
                subprocess.run([
                    'iptables', '-A', 'OUTPUT',
                    '-m', 'owner', '--uid-owner', 'vscext',
                    '-p', 'tcp', '--dport', str(port),
                    '-j', action
                ])
                subprocess.run([
                    'iptables', '-A', 'OUTPUT',
                    '-m', 'owner', '--uid-owner', 'vscext',
                    '-p', 'udp', '--dport', str(port),
                    '-j', action
                ])

        # Применить правила для IP-адресов
        ip_rules = rules.get('ipRules', [])
        for rule in ip_rules:
            action = 'DROP' if rule.get('action') == 'block' else 'ACCEPT'
            ip = rule.get('ip')
            if ip:
                # Правило для конкретного IP-адреса
                subprocess.run([
                    'iptables', '-A', 'OUTPUT',
                    '-m', 'owner', '--uid-owner', 'vscext',
                    '-d', ip,
                    '-j', action
                ])

    def apply_file_rules(self, rules: Dict):
        """Применяет правила для файловых операций"""
        read_action = rules.get('readAction')
        write_action = rules.get('writeAction')
        
        # Получаем правила для файлов
        files = rules.get('files', {})
        write_files = rules.get('writeFiles', {})
        
        # Получаем имя пользователя из /home (исключая vscext)
        home_users = [user for user in os.listdir('/home') if user != 'vscext']
        if not home_users:
            raise Exception("Не найден основной пользователь в /home")
        user = home_users[0]
        user_home = f'/home/{user}'
        
        # Применяем правила чтения
        if read_action == 'blockAll':
            # Блокируем все файлы для чтения
            subprocess.run(['setfacl', '-R', '-m', 'u:vscext:---', user_home])
        elif read_action == 'custom':
            # Сначала блокируем все
            subprocess.run(['setfacl', '-R', '-m', 'u:vscext:---', user_home])
            # Затем разрешаем только выбранные
            for file in files.get('values', []):
                if files['activeAction'] == 'Разрешить всё с':
                    subprocess.run(['setfacl', '-R', '-m', 'u:vscext:r-x', file])
                else:
                    subprocess.run(['setfacl', '-R', '-m', 'u:vscext:---', file])
        elif read_action == 'allowAll':
            # Разрешаем чтение всех файлов
            subprocess.run(['setfacl', '-R', '-m', 'u:vscext:r-x', user_home])
            
        # Применяем правила записи
        if write_action == 'blockAll':
            # Блокируем все файлы для записи
            subprocess.run(['setfacl', '-R', '-m', 'u:vscext:r-x', user_home])
        elif write_action == 'custom':
            # Сначала устанавливаем базовые права на чтение
            subprocess.run(['setfacl', '-R', '-m', 'u:vscext:r-x', user_home])
            # Затем обрабатываем правила для конкретных файлов
            for file in write_files.get('values', []):
                if write_files['activeAction'] == 'Разрешить всё с':
                    subprocess.run(['setfacl', '-R', '-m', 'u:vscext:rwx', file])
                else:
                    subprocess.run(['setfacl', '-R', '-m', 'u:vscext:r-x', file])
        elif write_action == 'allowAll':
            # Разрешаем запись всех файлов
            subprocess.run(['setfacl', '-R', '-m', 'u:vscext:rwx', user_home])

    def apply_resource_rules(self, rules: Dict):
        """Применяет правила использования ресурсов"""
        resource_action = rules.get('resourceAction')
        if resource_action == 'limit':
            # Установить ограничения на CPU и память
            subprocess.run(['ulimit', '-u', '50'])  # ограничить количество процессов
            subprocess.run(['ulimit', '-m', '1000000'])  # ограничить использование памяти

    def apply_rules(self):
        """Применяет все правила из конфигурации"""
        rules = self.load_rules()
        print("The rules are ", rules)
        self.apply_network_rules(rules)
        self.apply_file_rules(rules)
        self.apply_resource_rules(rules)
