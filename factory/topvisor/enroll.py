"""Скрытый ввод учётных данных Topvisor.

Живёт в репозитории, а не отдельным файлом на сервере, потому что это часть
автоматизации: разовый скрипт в /usr/local нельзя ни просмотреть в истории
изменений, ни покрыть тестом, ни восстановить после переустановки хоста.
Значения, разумеется, в репозиторий не попадают — только способ их принять.

Ввод читается с терминала без эха. В аргументы командной строки значения не
передаются, поэтому их нет ни в истории оболочки, ни в списке процессов.
"""
from __future__ import annotations

import getpass
import grp
import os
import re
import sys
from pathlib import Path

from factory.topvisor.credentials import API_KEY_FILE, USER_ID_FILE, secret_dir

GROUP = "ubuntu"
FILE_MODE = 0o440
DIR_MODE = 0o750

FIELDS = (
    (USER_ID_FILE, "TOPVISOR_USER_ID", re.compile(r"^[0-9]{1,20}$"), "только цифры"),
    (API_KEY_FILE, "TOPVISOR_API_KEY", re.compile(r"^[A-Za-z0-9._:-]{16,256}$"),
     "16–256 знаков: латиница, цифры и . _ : -"),
)


def ask(prompt: str) -> str:
    """Приглашение уходит в stderr, значение не отображается и не возвращается наружу."""
    return getpass.getpass(prompt, stream=sys.stderr).strip()


def main(argv: list[str] | None = None) -> int:
    if os.geteuid() != 0:
        print("нужен sudo: файлы принадлежат root", file=sys.stderr)
        return 2
    if not sys.stdin.isatty():
        print("нужен терминал: значения читаются скрытым вводом, не из потока", file=sys.stderr)
        return 2
    try:
        gid = grp.getgrnam(GROUP).gr_gid
    except KeyError:
        print(f"нет группы {GROUP}", file=sys.stderr)
        return 2

    directory = secret_dir()
    directory.mkdir(parents=True, exist_ok=True)
    os.chown(directory, 0, gid)
    os.chmod(directory, DIR_MODE)

    for filename, label, pattern, hint in FIELDS:
        value = ask(f"{label} (ввод скрыт): ")
        if not value:
            print(f"{label}: пусто — это не разрешение работать без значения", file=sys.stderr)
            return 1
        if not pattern.match(value):
            # В сообщении только правило, самого значения нет.
            print(f"{label}: не подходит под правило ({hint})", file=sys.stderr)
            return 1
        target = directory / filename
        temporary = directory / f".{filename}.tmp"
        handle = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, FILE_MODE)
        try:
            os.write(handle, value.encode("utf-8"))
        finally:
            os.close(handle)
        os.chown(temporary, 0, gid)
        os.chmod(temporary, FILE_MODE)
        os.replace(temporary, target)
        del value
        print(f"{label}: сохранено ({filename}, 0440, root:{GROUP})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
