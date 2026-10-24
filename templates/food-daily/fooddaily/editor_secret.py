"""Создание учётной записи редактора preview.

Хеш scrypt хранится в файле вне репозитория (по умолчанию
~/.config/food-daily-preview/editor.json, права 0600; путь меняется
переменной FOOD_DAILY_EDITOR_SECRET). Пароль генерируется и записывается
в соседний файл editor-password.txt (0600) — в вывод, журнал и git он
не попадает. Повторный запуск без --rotate ничего не меняет.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets

from .server import EDITOR_SECRET


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="food-daily editor-init")
    ap.add_argument("--user", default="editor")
    ap.add_argument("--rotate", action="store_true")
    a = ap.parse_args(argv)
    if EDITOR_SECRET.exists() and not a.rotate:
        print(json.dumps({"secret_ref": f"file:{EDITOR_SECRET}", "created": False}))
        return 0
    EDITOR_SECRET.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(EDITOR_SECRET.parent, 0o700)
    pw = secrets.token_urlsafe(18)
    salt = secrets.token_bytes(16)
    h = hashlib.scrypt(pw.encode(), salt=salt, n=2**14, r=8, p=1).hex()
    for path, data in (
        (EDITOR_SECRET, json.dumps({"user": a.user, "salt": salt.hex(), "hash": h})),
        (EDITOR_SECRET.with_name("editor-password.txt"), pw + "\n"),
    ):
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(data)
    print(
        json.dumps(
            {
                "secret_ref": f"file:{EDITOR_SECRET}",
                "created": True,
                "user": a.user,
                "password_file": str(EDITOR_SECRET.with_name("editor-password.txt")),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
