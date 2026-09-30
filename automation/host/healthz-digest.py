#!/usr/bin/env python3
"""Ответ /healthz о соответствии кода — ОДНИМ словом, и «нет ответа» ≠ «не совпало».

Зачем отдельный файл, а не строка внутри установщика
----------------------------------------------------

Этот разбор жил однострочником внутри `apply-episode-availability-root.sh`, в
одинарных кавычках оболочки. Внутри такой строки `\\"` остаётся ОБРАТНЫМ СЛЕШЕМ
с кавычкой, а Python 3.10 запрещает обратный слеш в выражении f-строки. Значит
фрагмент падал с `SyntaxError` ВСЕГДА — при любом состоянии витрины. Ошибку
глотал `2>/dev/null`, а `|| echo` подставлял «нет ответа».

Установщик печатал после этого: «файл на месте, но /healthz отвечает
runtime_digest_match=нет ответа — процесс исполняет не его». Две выложенные и
исправные витрины получили ОТКАЗ, а владелец — вывод о несовпадении кода,
которого никто не измерял. Отсутствие ответа выдали за установленное
несовпадение — это худший вид ошибки отчёта.

Поэтому разбор вынесен в файл: у него свой синтаксис, своя проверка
компиляцией и свой тест. Оболочка больше не несёт в себе чужой язык.

Что печатается
--------------

Ровно одно слово (плюс подробности после него) — и четыре исхода различимы:

    ok            поле есть и равно true
    mismatch      поле есть и равно false — вот это и значит «код не тот»
    no-field      ответ разобран, но поля runtime_digest_match в нём нет
    bad-json      ответ получен, но это не JSON
    no-answer     ответа нет: порт закрыт, таймаут, пустое тело

Код возврата: 0 только для `ok`. Остальное — ненулевой, но РАЗНЫЙ смысл, и
вызывающая сторона обязана их различать.

    python3 healthz-digest.py <порт> [<таймаут секунд>]
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request


def опросить(порт: str, таймаут: float) -> tuple[str, str]:
    адрес = f"http://127.0.0.1:{порт}/healthz"
    try:
        with urllib.request.urlopen(адрес, timeout=таймаут) as ответ:
            тело = ответ.read(1_000_000)
    except (urllib.error.URLError, OSError, ValueError) as ош:
        return "no-answer", f"{type(ош).__name__}: {ош}"
    if not тело.strip():
        return "no-answer", "пустое тело ответа"
    try:
        данные = json.loads(тело.decode("utf-8", "replace"))
    except ValueError as ош:
        return "bad-json", f"{ош}"
    if not isinstance(данные, dict):
        return "bad-json", f"ответ не объект, а {type(данные).__name__}"
    if "runtime_digest_match" not in данные:
        return "no-field", "в ответе нет runtime_digest_match"
    совпало = данные.get("runtime_digest_match")
    # Хеш ФАЙЛА витрины и хеш АРТЕФАКТА — разные величины, и путать их нельзя:
    # у ячейки с манифестом из нескольких файлов они не совпадают никогда, и
    # именно это однажды приняли за неверную выкладку. Печатаются оба вместе с
    # областью, по которой витрина их сравнивала.
    подробно = (f"build_id={данные.get('build_id')} "
                f"runtime_sha256={str(данные.get('runtime_sha256'))[:12]} "
                f"artifact_sha256={str(данные.get('artifact_sha256'))[:12]} "
                f"scope={данные.get('runtime_digest_scope') or 'runtime_file'}")
    return ("ok" if совпало is True else "mismatch"), подробно


def main(argv=None) -> int:
    а = list(sys.argv[1:] if argv is None else argv)
    if not а:
        print("no-answer порт не задан")
        return 2
    порт = а[0]
    таймаут = float(а[1]) if len(а) > 1 else 10.0
    исход, подробно = опросить(порт, таймаут)
    print(f"{исход} {подробно}".rstrip())
    return 0 if исход == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
