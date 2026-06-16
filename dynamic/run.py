"""
run.py — упрощённый запуск динамического монитора VSCode.

Использование:
    python -m dynamic.run [--rules configs/rules.json]
"""

import argparse
import sys
import time
from pathlib import Path

# Разрешаем запуск как `python dynamic/run.py`
sys.path.insert(0, str(Path(__file__).resolve().parent))

from monitor import VSCodeSecurityMonitor  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="VSCode dynamic security monitor")
    parser.add_argument(
        "--rules",
        default=str(Path(__file__).resolve().parent.parent / "configs" / "rules.json"),
        help="Путь к JSON с правилами безопасности.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    monitor = VSCodeSecurityMonitor(rules_file=args.rules)

    monitor.print_monitored_extensions()

    print("\nЗапуск мониторинга... (Ctrl+C для остановки)")
    try:
        monitor.start_monitoring()
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        monitor.stop_monitoring()
        print("\nМониторинг остановлен")


if __name__ == "__main__":
    main()
