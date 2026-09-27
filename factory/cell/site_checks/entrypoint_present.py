"""Точка входа существует и названа в конфигурации."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
cfg = json.loads((ROOT / "config" / "site.json").read_text(encoding="utf-8"))
entry = ROOT / "src" / cfg["entrypoint"]
if not entry.is_file():
    print(f"нет точки входа {entry}", file=sys.stderr)
    sys.exit(1)
