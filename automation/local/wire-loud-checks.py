#!/usr/bin/env python3
"""Упавшая проверка перестаёт молчать: её вывод печатается. Перенос по ячейкам.

    python3 automation/local/wire-loud-checks.py --repo var/site-repos/<проект> [--dry-run]
    python3 automation/local/wire-loud-checks.py --all [--dry-run]

Зачем. `check()` в `checks/run.sh` глушил и stdout, и stderr: падение печаталось
одним словом FAIL, и причина не доходила ни до журнала CI, ни до отчёта.
Измерено 2026-10-07 на zonafilm.cc: прогон CI упал на `canonical-requested`, а в
журнале прогона — ровно одна строка «canonical-requested FAIL» и ничего больше;
та же проверка на дереве из одних версионных файлов и с вычищенным окружением
проходила, то есть воспроизвести отказ было нечем.

Это уже исправленный дефект — но в другом месте. `factory/cell/site_checks/run.sh`
получил громкий вывод ещё в lords-01 (`docs/LORDS_TEMPLATE_FIXES.md` §7,
«Упавшая проверка молчала»), а в `checks/run.sh` самих репозиториев сайтов
правка не приехала. Здесь она переносится.

Что меняется: только обёртка `check()`. Набор проверок, их порядок и код выхода
прогона остаются теми же; у прошедшей проверки вывод по-прежнему не печатается —
иначе прогон превратился бы в стену текста, в которой падение опять не найти.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
РЕПОЗИТОРИИ = КОРЕНЬ / "var" / "site-repos"

ТИХАЯ = """check() {
  local name="$1"; shift
  if "$@" >/dev/null 2>&1; then
    say "$name" "PASS"
  else
    say "$name" "FAIL"
    fail=1
  fi
}"""

ГРОМКАЯ = """check() {
  local name="$1"; shift
  # Вывод упавшей проверки ПЕЧАТАЕТСЯ. Прежде он глушился целиком, и падение в
  # журнале CI выглядело одним словом FAIL: причина не доходила ни до журнала,
  # ни до отчёта, и отказ, который не воспроизводится локально, разобрать было
  # нечем. У прошедшей проверки вывод по-прежнему молчит — иначе падение
  # потерялось бы в стене текста.
  local out
  if out="$("$@" 2>&1)"; then
    say "$name" "PASS"
  else
    say "$name" "FAIL"
    printf '%s\\n' "$out" | tail -n 40 | sed 's/^/    | /'
    fail=1
  fi
}"""

#: Вторая встречающаяся форма: с выравниванием на 30 знаков и без local out.
ТИХАЯ_2 = """check() {
  local name="$1"; shift
  if "$@" >/dev/null 2>&1; then say "$name" "PASS"; else say "$name" "FAIL"; fail=1; fi
}"""


def главная(argv: list[str]) -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--repo", action="append", default=[])
    р.add_argument("--all", action="store_true")
    р.add_argument("--dry-run", action="store_true")
    о = р.parse_args(argv[1:])

    цели: list[pathlib.Path] = []
    if о.all:
        цели += [п for п in sorted(РЕПОЗИТОРИИ.iterdir())
                 if (п / ".git").is_dir() and not п.name.startswith("yummy")]
    for р_ in о.repo:
        п_ = pathlib.Path(р_)
        цели.append(п_ if п_.is_absolute() else КОРЕНЬ / п_)
    if not цели:
        print(__doc__)
        return 2

    сделано = пропущено = 0
    for цель in цели:
        прогон = цель / "checks" / "run.sh"
        if not прогон.is_file():
            print(f"{цель.name:24} checks/run.sh нет")
            continue
        т = прогон.read_text(encoding="utf-8")
        # Уже громкая обёртка узнаётся по делу, а не по тексту пояснения: у
        # ячеек Lords она стоит давно и без этого комментария, и требовать
        # комментарий значило бы объявлять «не сделано» уже сделанное.
        if ("Вывод упавшей проверки ПЕЧАТАЕТСЯ" in т
                or ('local out' in т and 'printf \'%s' in т)):
            print(f"{цель.name:24} уже громкая")
            пропущено += 1
            continue
        for тихая in (ТИХАЯ, ТИХАЯ_2):
            if тихая in т:
                т = т.replace(тихая, ГРОМКАЯ, 1)
                break
        else:
            print(f"{цель.name:24} ОТКАЗ: обёртки check() в известном виде нет")
            continue
        if not о.dry_run:
            прогон.write_text(т, encoding="utf-8")
        сделано += 1
        print(f"{цель.name:24} {'переписана' if not о.dry_run else 'переписала бы'}")
    print(f"\nпереключено {сделано}, уже громких {пропущено}"
          + ("  (сухой прогон)" if о.dry_run else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(главная(sys.argv))
