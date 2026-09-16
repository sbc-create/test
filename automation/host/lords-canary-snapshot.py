#!/usr/bin/env python3
"""Тождество снимка каталога: сколько записей и какой отпечаток.

Отдельный файл, а не строка внутри сценария: питон в подстановке команд внутри
кавычек ломает разбор оболочки на ровном месте, и отлаживать это дороже, чем
завести файл.
"""
import hashlib
import json
import sys
from pathlib import Path


def main() -> int:
    path = Path(sys.argv[1])
    raw = json.loads(path.read_text(encoding="utf-8"))
    items = raw.get("items") if isinstance(raw, dict) else raw
    digest = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    print(f"{len(items or [])} {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
