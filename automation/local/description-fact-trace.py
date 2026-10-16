#!/usr/bin/env python3
"""Каждое слово собранного описания прослеживается до поля записи.

Зачем. «Строки у семи домена разные» результатом не является: описание обязано
соответствовать КОНКРЕТНОМУ произведению и проверенным данным. Этот инструмент
проверяет именно это, а не форму: он разбирает готовую строку на фрагменты и
требует, чтобы каждый фрагмент совпал со значением поля записи — по словарю
связок, которых в сборщике ровно десять.

Что считается нарушением:

  невозводимый фрагмент   кусок строки, который не выводится ни из одного поля
  чужой факт              значение, которого в записи нет (год, жанр, страна)
  служебный ярлык         «западный контент» и подобные ведра отбора каталога
  оценка без источника     число рейтинга без имени источника рядом
  выдуманное слово         любое слово вне полей записи и списка связок

Инструмент НЕ судит о красоте текста: он отвечает на вопрос «есть ли в
описании хоть что-то, чего нет в данных». Для чтения человеком печатаются
образцы с полями рядом.

    python3 automation/local/description-fact-trace.py --snapshot /srv/site-1lordserials1-online/data/lords-03-details.json --sample 300 --show 8
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(КОРЕНЬ / "automation" / "host"))

import description_assembly as СБОРКА  # noqa: E402

#: Связки сборщика — закрытый список. Всё остальное обязано приходить из полей.
СВЯЗКИ = {
    "года", "год", "в", "оригинале", "IMDb", "Кинопоиск", "мин", "премьера",
    "озвучка", "сезон", "сезона", "сезонов",
    "января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа",
    "сентября", "октября", "ноября", "декабря",
}


def поля_записи(з: dict) -> set[str]:
    """Все слова, которые законно могут появиться в описании этой записи."""
    слова: set[str] = set()

    def добавить(значение) -> None:
        if значение in (None, "", [], {}):
            return
        if isinstance(значение, (list, tuple)):
            for э in значение:
                добавить(э)
            return
        текст = str(значение)
        for слово in re.findall(r"[0-9A-Za-zА-Яа-яЁё’'\-]+", текст):
            слова.add(слово.lower())

    for поле in ("name", "original_name", "type", "year", "genres", "countries",
                 "imdb_rating", "kinopoisk_rating", "premiere_date",
                 "voice_studios", "duration", "description", "short_description"):
        добавить(з.get(поле))
    # Тип приходит по-английски, в описании он по-русски: это перевод
    # подтверждённого поля, и словарь перевода закрыт.
    добавить(list(СБОРКА.ТИПЫ.values()))
    добавить(СБОРКА._сезонов(з))
    return слова


def нарушения(строка: str, з: dict) -> list[str]:
    беды: list[str] = []
    законные = поля_записи(з) | {с.lower() for с in СВЯЗКИ}
    for слово in re.findall(r"[0-9A-Za-zА-Яа-яЁё’'\-]+", строка):
        м = слово.lower()
        if м in законные:
            continue
        # Число могло прийти из оценки «7,4» (в данных 7.4) или из даты.
        if re.fullmatch(r"\d+", м) and any(
                м in str(з.get(поле) or "") for поле in
                ("year", "imdb_rating", "kinopoisk_rating", "premiere_date",
                 "duration")):
            continue
        беды.append(f"слово вне данных: {слово!r}")
    низ = строка.lower()
    for ярлык in СБОРКА.НЕ_ЖАНРЫ:
        if ярлык in низ:
            беды.append(f"служебный ярлык каталога: {ярлык!r}")
    # Оценка без источника: число с запятой, перед которым нет имени источника.
    for м in re.finditer(r"(?<![\w,])\d+,\d(?!\d)", строка):
        до = строка[max(0, м.start() - 12):м.start()].lower()
        if "imdb" not in до and "кинопоиск" not in до:
            беды.append(f"оценка без источника: {м.group(0)}")
    return беды


def главное(аргв=None) -> int:
    р = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--snapshot", type=Path, required=True)
    р.add_argument("--sample", type=int, default=300)
    р.add_argument("--show", type=int, default=6)
    р.add_argument("--seed", type=int, default=20261016)
    р.add_argument("--domain", action="append", default=[])
    опции = р.parse_args(аргв)

    д = json.loads(опции.snapshot.read_text(encoding="utf-8"))
    детали = д.get("details") if isinstance(д, dict) else д
    ключи = list(детали)
    random.seed(опции.seed)
    random.shuffle(ключи)
    домены = опции.domain or list(СБОРКА.ПРОФИЛИ)

    строк = 0
    беды: list[str] = []
    образцы: list[tuple[str, str, dict]] = []
    for к in ключи[: опции.sample]:
        з = детали[к]
        if not isinstance(з, dict):
            continue
        for хост in домены:
            строка = СБОРКА.описание({"slug": з.get("id") or ""}, з, хост)
            if not строка:
                continue
            строк += 1
            найдено = нарушения(строка, з)
            if найдено:
                беды.append(f"{хост} | {з.get('name')} | {строка} | {найдено}")
            elif len(образцы) < опции.show and len(строка) > 90:
                образцы.append((хост, строка, з))

    print(f"снимок: {опции.snapshot}")
    print(f"записей в выборке: {min(опции.sample, len(ключи))}; "
          f"строк проверено: {строк}; доменов: {len(домены)}\n")
    print("ОБРАЗЦЫ ДЛЯ ЧТЕНИЯ (поля записи рядом):")
    for хост, строка, з in образцы:
        print(f"\n  {хост}")
        print(f"  {строка}")
        print(f"     name={з.get('name')!r} original={з.get('original_name')!r} "
              f"type={з.get('type')!r} year={з.get('year')!r}")
        print(f"     genres={з.get('genres')} countries={з.get('countries')} "
              f"imdb={з.get('imdb_rating')} premiere={з.get('premiere_date')}")
    print(f"\nнарушений: {len(беды)}")
    for б in беды[:12]:
        print(f"   {б}")
    return 1 if беды else 0


if __name__ == "__main__":
    raise SystemExit(главное())
