#!/usr/bin/env python3
"""Запускает команду приложения с секретами в окружении, но не в логе.

Значения (DSN с паролем, PAYLOAD_SECRET) берутся из файлов 0600 в `var/` и
передаются дочернему процессу через environment. Они не печатаются, не попадают
в аргументы командной строки (их видно в `ps`) и не коммитятся.

Использование:
    python3 tests/tools/with_app_env.py --scope anime -- npx tsx script.ts
"""
from __future__ import annotations

import argparse
import os
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from factory.database import load_credentials  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SECRET_FILE = ROOT / "var" / "secrets" / "payload_secret"


def payload_secret() -> str:
    """Локальный секрет подписи сессий. Генерируется один раз, не хранится в git."""
    if SECRET_FILE.exists():
        return SECRET_FILE.read_text(encoding="utf-8").strip()
    SECRET_FILE.parent.mkdir(parents=True, exist_ok=True)
    value = secrets.token_urlsafe(48)
    SECRET_FILE.write_text(value, encoding="utf-8")
    SECRET_FILE.chmod(0o600)
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", default="anime", help="Имя набора учётных данных в var/db")
    parser.add_argument("--push", action="store_true", help="Разрешить Payload синхронизировать схему (только staging)")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    command = [item for item in args.command if item != "--"]
    if not command:
        parser.error("не задана команда для запуска")

    credentials, password = load_credentials(args.scope)
    env = dict(os.environ)
    env["DATABASE_URI"] = credentials.dsn(password)
    env["PAYLOAD_SECRET"] = payload_secret()
    if args.push:
        env["PAYLOAD_DB_PUSH"] = "true"
    # Каталоги загрузок — состояние стенда, а не исходники: всегда под var/.
    for name, relative in (("MEDIA_DIR", "var/media"), ("CATALOG_MEDIA_DIR", "var/catalog-media")):
        directory = ROOT / relative
        directory.mkdir(parents=True, exist_ok=True)
        env.setdefault(name, str(directory))
    env.setdefault("NODE_OPTIONS", "--no-deprecation")

    os.execvpe(command[0], command, env)


if __name__ == "__main__":
    raise SystemExit(main())
