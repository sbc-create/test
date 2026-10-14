#!/usr/bin/env python3
"""Несут ли собранные бандлы восьми витрин ТЕКУЩИЙ код своих репозиториев.

Зачем отдельная проверка. Доставка кода на узел K2 идёт бандлами
(`automation/local/refresh-k2-bundles.sh`), и бандл — файл: он остаётся лежать
и выглядеть свежим после того, как в репозитории витрины появились новые
коммиты. Доставить отставший бандл значит выложить версию БЕЗ исправлений, и
отчёт при этом честно скажет «код доставлен, сумма сошлась».

Поэтому сверяется не запись о бандлах, а сами файлы: голова репозитория против
голов, которые объявляет сам бандл (`git bundle list-heads`). Найдено
2026-10-14: запись `var/k2-data/bundle-heads.json` называла головы, собранные
ДО сегодняшних правок интерфейса, то есть читалась как доказательство, не
будучи им. Теперь запись пишет эта проверка, и только по измерению.

    python3 automation/local/k2-bundle-freshness.py
    python3 automation/local/k2-bundle-freshness.py --site lords-10 --site lords-13

Код выхода: 0 — все сошлись; 3 — есть расхождение или незакоммиченные правки;
2 — проверять нечего (нет репозитория или бандла).
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
БАНДЛЫ = КОРЕНЬ / "var" / "k2-data" / "bundles"
ЗАПИСЬ = КОРЕНЬ / "var" / "k2-data" / "bundle-heads.json"
ВИТРИНЫ = [f"lords-{н}" for н in range(10, 18)]


def _вывод(команда: list[str]) -> tuple[int, str]:
    г = subprocess.run(команда, capture_output=True, text=True, timeout=120,
                       cwd=str(КОРЕНЬ))
    return г.returncode, (г.stdout or "").strip()


def состояние(site_id: str) -> dict:
    репо = КОРЕНЬ / "var" / "new-sites" / site_id
    бандл = БАНДЛЫ / f"{site_id}.bundle"
    отчёт: dict = {"site": site_id, "репозиторий": str(репо.relative_to(КОРЕНЬ))}
    if not (репо / ".git").exists():
        отчёт["итог"] = "нет репозитория витрины"
        return отчёт
    код, голова = _вывод(["git", "-C", str(репо), "rev-parse", "--short=12", "HEAD"])
    if код != 0 or not голова:
        отчёт["итог"] = "голова репозитория не читается"
        return отчёт
    _, когда = _вывод(["git", "-C", str(репо), "show", "-s", "--format=%cI", "HEAD"])
    _, грязь = _вывод(["git", "-C", str(репо), "status", "--porcelain"])
    отчёт.update({"голова": голова, "дата головы": когда,
                  "незакоммиченных файлов": len(грязь.splitlines()) if грязь else 0})
    if not бандл.is_file():
        отчёт["итог"] = "бандл не собран"
        return отчёт
    код, строки = _вывод(["git", "bundle", "list-heads", str(бандл)])
    if код != 0:
        отчёт["итог"] = "бандл не читается"
        return отчёт
    в_бандле = sorted({л.split()[0][:12] for л in строки.splitlines() if л.split()})
    отчёт.update({"бандл": str(бандл.relative_to(КОРЕНЬ)),
                  "байт": бандл.stat().st_size,
                  "в бандле": в_бандле,
                  "совпало": голова in в_бандле})
    if not отчёт["совпало"]:
        отчёт["итог"] = "РАСХОЖДЕНИЕ: бандл несёт не текущий код витрины"
    elif отчёт["незакоммиченных файлов"]:
        отчёт["итог"] = ("бандл сошёлся с головой, но в репозитории есть "
                         "незакоммиченные правки — в бандл они не попали")
    else:
        отчёт["итог"] = "бандл несёт текущий код"
    return отчёт


def main() -> int:
    р = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--site", action="append", default=[],
                   help="site_id витрины; можно повторять (по умолчанию все восемь)")
    а = р.parse_args()
    витрины = а.site or ВИТРИНЫ
    отчёты = [состояние(с) for с in витрины]
    ЗАПИСЬ.parent.mkdir(parents=True, exist_ok=True)
    ЗАПИСЬ.write_text(json.dumps(отчёты, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    for о in отчёты:
        print(f"{о['site']:9} {о.get('голова', '—'):12} {о['итог']}")
    print(f"запись: {ЗАПИСЬ.relative_to(КОРЕНЬ)}")
    # Код выхода различает ТРИ состояния, и не «на всякий случай»: «нечего
    # проверять» и «проверено, не сходится» требуют разных действий — собрать
    # бандл против разобраться, почему код разъехался.
    НЕЧЕГО = {"нет репозитория витрины", "голова репозитория не читается",
              "бандл не собран", "бандл не читается"}
    if any(о["итог"] in НЕЧЕГО for о in отчёты):
        return 2
    if all(о.get("совпало") and not о.get("незакоммиченных файлов") for о in отчёты):
        return 0
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
