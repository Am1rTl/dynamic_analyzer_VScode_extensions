"""
run.py — запуск статического анализатора VSCode-расширения.

Использование:
    python -m static.run <path/to/extension>
    python static/run.py <path/to/extension>
"""

import argparse
import sys
from pathlib import Path

# Разрешаем запуск как `python static/run.py`
sys.path.insert(0, str(Path(__file__).resolve().parent))

from analyzer import VSCodeExtensionAnalyzer  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Статический анализатор VSCode-расширений."
    )
    parser.add_argument(
        "extension_path",
        nargs="?",
        default=str(Path.home() / ".vscode" / "extensions"),
        help="Путь к директории расширения. По умолчанию ~/.vscode/extensions.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    analyzer = VSCodeExtensionAnalyzer(args.extension_path)
    results = analyzer.analyze()
    print(analyzer.generate_report(results))


if __name__ == "__main__":
    main()

