"""Экспорт OpenAPI-схемы в openapi.json.

Запуск:
    python scripts/export_openapi.py
"""

import json
from pathlib import Path

from app.main import app


def main() -> None:
    spec = app.openapi()
    output = Path("openapi.json")
    output.write_text(
        json.dumps(spec, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Экспортировано {len(spec.get('paths', {}))} путей в {output}")


if __name__ == "__main__":
    main()
