#!/usr/bin/env python3
"""Отчёт о подключении аналитики: что службы сделали на самом деле.

Зачем отдельная команда. Отчёты служб лежат в четырёх файлах разного формата, и
владельцу нужен один ответ на вопрос «подключилось или нет». Читать journalctl
для этого не нужно: службы пишут результат в файлы, доступные без root.

Что здесь НЕ делается: ни одного запроса к API, ни одной записи. Команда только
читает уже полученные ответы, поэтому безопасна для повторного запуска.

Секреты. Весь текст перед печатью проходит :mod:`factory.redaction`: даже если
чужой инструмент однажды положит значение в отчёт, наружу оно не выйдет. Сам
отчёт секретов не содержит по построению — там публичные идентификаторы.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(КОРЕНЬ))

from factory.redaction import redact  # noqa: E402

АНАЛИТИКА = КОРЕНЬ / "var" / "analytics"
ТОПВИЗОР = КОРЕНЬ / "var" / "topvisor"
РЕЕСТР = КОРЕНЬ / "config" / "analytics.json"

#: Файлы, которые пишут установленные службы. Пути взяты из ExecStart юнитов.
ОТЧЁТЫ = (
    ("Метрика: сбор статистики", АНАЛИТИКА / "cabinet-latest.json"),
    ("Метрика: ошибки сбора", КОРЕНЬ / "var" / "analytics-cabinet-stderr.log"),
    ("Topvisor: доступ", ТОПВИЗОР / "check-latest.txt"),
    ("Topvisor: план", ТОПВИЗОР / "plan-latest.json"),
    ("Topvisor: применение", ТОПВИЗОР / "connect-latest.txt"),
    ("Topvisor: проверка после", ТОПВИЗОР / "check-after-connect.txt"),
)


def _печать(строка: str) -> None:
    print(redact(строка))


def _счётчики_по_отчётам() -> list[dict]:
    строки = []
    for файл in sorted(АНАЛИТИКА.glob("connect-*.json")):
        домен = файл.name[len("connect-"):-len(".json")]
        текст = файл.read_text(encoding="utf-8", errors="replace")
        try:
            данные = json.loads(текст)
        except ValueError:
            строки.append({"domain": домен, "state": "отчёт не разобран",
                           "detail": текст.strip().splitlines()[-1][:160] if текст.strip() else "пусто"})
            continue
        записи = данные.get("results") or данные.get("properties") or []
        своя = next((з for з in записи if з.get("domain") == домен), None) or (записи[0] if записи else {})
        строки.append({
            "domain": домен,
            "state": str(своя.get("status") or данные.get("status") or "нет поля status"),
            "counter_id": своя.get("counter_id"),
            "site": (своя.get("site2") or {}).get("site") if isinstance(своя.get("site2"), dict) else своя.get("site"),
            "detail": "; ".join(str(п) for п in (своя.get("problems") or []))[:200]
                      or str(своя.get("reason") or ""),
        })
    return строки


def main(argv: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    р.add_argument("--tail", type=int, default=12,
                   help="сколько последних строк текстового отчёта показать")
    а = р.parse_args(argv)

    _печать("=== Что службы записали ===")
    for имя, путь in ОТЧЁТЫ:
        if not путь.exists():
            _печать(f"  {имя:28} нет файла ({путь.relative_to(КОРЕНЬ)}) — служба не запускалась")
            continue
        размер = путь.stat().st_size
        _печать(f"  {имя:28} {путь.relative_to(КОРЕНЬ)}  {размер} Б")

    _печать("\n=== Счётчики Метрики по отчётам служб ===")
    строки = _счётчики_по_отчётам()
    if not строки:
        _печать("  ни одного файла connect-<домен>.json: analytics-connect@ не запускался")
    for с in строки:
        _печать(f"  {с['domain']:24} status={с['state']:12} counter_id={с.get('counter_id')} "
                f"домен счётчика={с.get('site')}")
        if с.get("detail"):
            _печать(f"      {с['detail']}")

    _печать("\n=== Реестр аналитики (что записано в конфигурацию) ===")
    реестр = json.loads(РЕЕСТР.read_text(encoding="utf-8"))["properties"]
    for з in реестр:
        if з.get("counter_id") or з.get("counter_state") != "planned":
            _печать(f"  {з['domain']:24} counter_id={з.get('counter_id')} "
                    f"state={з.get('counter_state')} name={з.get('counter_name')!r}")

    for имя, путь in ОТЧЁТЫ:
        if путь.suffix == ".txt" and путь.exists() and путь.stat().st_size:
            _печать(f"\n=== {имя}: последние {а.tail} строк ===")
            for строка in путь.read_text(encoding="utf-8", errors="replace").splitlines()[-а.tail:]:
                _печать("  " + строка)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
