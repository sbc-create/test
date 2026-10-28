#!/usr/bin/env python3
"""MOD-225: объявить в наборе выпуска девять проверок, которые он не зовёт.

    python3 automation/host/apply-zona02-checks-wiring.py \
        --repo var/site-repos/zonafilm-cc [--check] [--dry-run]

Что измерено
------------

28.10, поиск по `checks/run.sh`: ни одна из девяти проверок, написанных за этот
день, в наборе выпуска НЕ объявлена — `player_goals` (T342), `gone_page` и
`empty_filter_route` (T344), `genre_facet_counts` (T345), `search_digits`,
`search_morphology`, `search_genre_hint`, `search_suggestions`, `search_typos`
(T343). Все девять прогонялись руками и по каждой сказано «проходит», но на
активации не сработала бы ни одна: `deploy/activate.sh` запускает именно
`checks/run.sh`.

Сторож `checks-all-ran` этого заметить НЕ МОГ: он сверяет число ОБЪЯВЛЕННЫХ
строк `check ` с числом исполнившихся, то есть ловит объявленную и не
исполнившуюся проверку, а необъявленной для него не существует.

Как вызываются
--------------

Каждая через обёртку «код 2 → 0»: все девять отвечают 2, когда снимка нет, и
без обёртки красили бы раннер CI. Это тот же вид вызова, что у восьми уже
объявленных проверок семейства.

Строки вставляются после ПОСЛЕДНЕЙ строки `check ` — структурно, а не по имени
чужой проверки.

Чего инструмент не делает: не меняет ни одной проверки, не трогает сторожей
раннера, не переставляет существующие вызовы и **отказывает**, если в
`checks/run.sh` есть незакоммиченные чужие изменения — проверить это он не
может, поэтому прямо требует запускать себя на чистом файле и называет причину
отказа при несовпадении числа строк `check `.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

ПРОВЕРКИ = (
    ("player-goals", "player_goals.py",
     "Цели пути до просмотра: карточка, намерение, готовность, реклама,\n"
     "# наблюдаемое начало. До T342 витрина не отправляла ни одной цели."),
    ("gone-page", "gone_page.py",
     "Адрес снятого произведения даёт поиск по словам адреса, а не тупик\n"
     "# (T344). Девять из одиннадцати посещённых 404 — одно снятое произведение."),
    ("empty-filter-route", "empty_filter_route.py",
     "Пустая выборка называет раздел, где условие работает (T344).\n"
     "# Код ответа остаётся 404: адреса правда нет."),
    ("genre-facet-counts", "genre_facet_counts.py",
     "Фильтр жанров раздела не предлагает тупиков (T345). Было 64 из 98\n"
     "# на /movies/ и 66 из 98 на /series/."),
    ("search-digits", "search_digits.py",
     "Точное название с цифрой первое (T343): «форсаж 7» давало его девятым."),
    ("search-morphology", "search_morphology.py",
     "Склонённый запрос находит произведение (T343): «дневники вампиров»."),
    ("search-genre-hint", "search_genre_hint.py",
     "Жанровый и годовой запрос ведут в раздел (T343): «мылодрамма»."),
    ("search-suggestions", "search_suggestions.py",
     "Похожее не выдаётся за найденное (T343): «Холод» на «Холоп 3»."),
    ("search-typos", "search_typos.py",
     "Одна-две опечатки находят произведение (T343): «брильянтовый»."),
)

ШАБЛОН = ('# {пояснение}\n'
          'check "{имя}"{отступ}bash -c \'python3 checks/{файл}; rc=$?; '
          '[ "$rc" -eq 2 ] && exit 0; exit "$rc"\'\n')


def _строки() -> str:
    куски = []
    for имя, файл, пояснение in ПРОВЕРКИ:
        отступ = " " * max(1, 24 - len(имя))
        куски.append(ШАБЛОН.format(имя=имя, файл=файл, пояснение=пояснение,
                                   отступ=отступ))
    return "".join(куски)


def применить(репо: pathlib.Path, писать: bool) -> tuple[str, str]:
    f = репо / "checks" / "run.sh"
    if not f.is_file():
        return "refuse", f"нет {f}"
    текст = f.read_text(encoding="utf-8")
    нет = [файл for _, файл, _ in ПРОВЕРКИ
           if not (репо / "checks" / файл).is_file()]
    if нет:
        return "refuse", f"в репозитории нет проверок: {', '.join(нет)}"
    уже = [файл for _, файл, _ in ПРОВЕРКИ if f"checks/{файл}" in текст]
    если_нет = [файл for _, файл, _ in ПРОВЕРКИ if f"checks/{файл}" not in текст]
    if not если_нет:
        return "skip", f"все {len(ПРОВЕРКИ)} проверок уже объявлены"
    строки = текст.splitlines(keepends=True)
    места = [i for i, с in enumerate(строки) if с.startswith("check ")]
    if not места:
        return "refuse", "в checks/run.sh нет ни одной строки `check `"
    if not писать:
        return "ok", (f"будет объявлено {len(если_нет)} проверок: "
                      + ", ".join(если_нет)
                      + (f"; уже были: {', '.join(уже)}" if уже else ""))
    добавка = "".join(
        ШАБЛОН.format(имя=имя, файл=файл, пояснение=пояснение,
                      отступ=" " * max(1, 24 - len(имя)))
        for имя, файл, пояснение in ПРОВЕРКИ if файл in если_нет)
    строки.insert(места[-1] + 1, добавка)
    f.write_text("".join(строки), encoding="utf-8")
    return "ok", f"объявлено проверок: {len(если_нет)} — " + ", ".join(если_нет)


def main() -> int:
    р = argparse.ArgumentParser()
    р.add_argument("--repo", required=True)
    р.add_argument("--check", action="store_true")
    р.add_argument("--dry-run", action="store_true")
    а = р.parse_args()
    репо = pathlib.Path(а.repo).resolve()
    исход, пояснение = применить(репо, писать=not (а.check or а.dry_run))
    print(f"[{исход:6s}] {репо.name}: {пояснение}")
    if исход == "refuse":
        return 2
    if а.check:
        return 1 if исход == "ok" else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
