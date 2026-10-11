#!/usr/bin/env python3
"""Почему у части записей нет жанров: не спросили у источника или источник не дал.

Разница решает, что делать, и её надо измерять, а не предполагать:

* **файла в кэше подробностей нет** — про запись ни разу не спрашивали. Это
  незакрытое покрытие: его закрывает добор (`nova-detail-backfill.py`), и
  скорость известна — бюджет прогона;
* **файл есть, жанров в нём нет** — источник их не отдаёт. Добор не поможет,
  и выдумывать жанры нельзя; запись остаётся без таксономии, и проверка
  качества обязана отличать этот случай от первого.

Инструмент только читает: снимок витрины, кэш подробностей и отчёт добора.

    python3 automation/local/genre-coverage-audit.py                # animedia-01
    python3 automation/local/genre-coverage-audit.py --site lords-01
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

КЭШ = Path("/srv/site-factory/repo/var/lords/detail-cache")
ОТЧЁТ_ДОБОРА = Path("/srv/site-factory/repo/var/lords/detail-backfill-report.json")
ВИТРИНЫ = {
    "animedia-01": Path("/srv/animedia-icu/data/animedia-01-details.json"),
    "animedia-02": Path("/srv/animedia-space/data/animedia-02-details.json"),
    "lords-01": Path("/srv/lordfilm47-space/data/lords-01-details.json"),
    "lords-02": Path("/srv/lordserial33-biz/data/lords-02-details.json"),
    "zona-01": Path("/srv/zonafilm-space/data/zona-01-details.json"),
}


def записи(путь: Path) -> dict:
    документ = json.loads(путь.read_text(encoding="utf-8"))
    return документ.get("details") or документ


def разобрать(подробности: dict) -> dict:
    без_жанров = {с: з for с, з in подробности.items()
                  if not (з.get("genres") or [])}
    не_спрошены, пусто_у_источника, нечитаемые = [], [], []
    for слаг, з in без_жанров.items():
        файл = КЭШ / f"{з.get('id')}.json"
        if not файл.is_file():
            не_спрошены.append(слаг)
            continue
        try:
            документ = json.loads(файл.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            нечитаемые.append(слаг)
            continue
        тело = документ.get("detail") or документ.get("item") or документ
        if isinstance(тело, dict) and not (тело.get("genres") or []):
            пусто_у_источника.append(слаг)
        else:
            # Жанры в кэше есть, а на витрине нет: это уже не покрытие, а
            # потеря при сборке — случай, который надо разбирать отдельно.
            нечитаемые.append(слаг)
    return {"всего": len(подробности), "без_жанров": len(без_жанров),
            "не_спрошены": не_спрошены,
            "пусто_у_источника": пусто_у_источника,
            "расхождение_кэш_витрина": нечитаемые}


def главное(аргв: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(description="покрытие жанров и его причина")
    р.add_argument("--site", default="animedia-01", choices=sorted(ВИТРИНЫ))
    р.add_argument("--json", action="store_true")
    а = р.parse_args(аргв)
    путь = ВИТРИНЫ[а.site]
    if not путь.is_file():
        print(f"снимка витрины нет: {путь}", file=sys.stderr)
        return 2
    итог = разобрать(записи(путь))
    итог["site"] = а.site
    if ОТЧЁТ_ДОБОРА.is_file():
        отчёт = json.loads(ОТЧЁТ_ДОБОРА.read_text(encoding="utf-8"))
        после = отчёт.get("after") or {}
        итог["добор"] = {
            "бюджет": отчёт.get("budget"),
            "запросов_в_прогоне": отчёт.get("requests_made"),
            "в_кэше": после.get("cached"),
            "всего_в_каталоге": после.get("titles"),
            "не_в_кэше": (после.get("titles") or 0) - (после.get("cached") or 0),
            "прогон": отчёт.get("finished_at"),
        }
    if а.json:
        print(json.dumps(итог, ensure_ascii=False, indent=2))
        return 0
    print(f"витрина {итог['site']}: записей {итог['всего']}, "
          f"без жанров {итог['без_жанров']}")
    print(f"   не спрошены у источника:      {len(итог['не_спрошены'])}")
    print(f"   источник жанров не отдал:     {len(итог['пусто_у_источника'])}")
    print(f"   расхождение кэша и витрины:   {len(итог['расхождение_кэш_витрина'])}")
    for имя, список in (("не спрошены", итог["не_спрошены"]),
                        ("пусто у источника", итог["пусто_у_источника"]),
                        ("расхождение", итог["расхождение_кэш_витрина"])):
        if список:
            print(f"   примеры ({имя}): {', '.join(список[:5])}")
    д = итог.get("добор")
    if д:
        print(f"\nдобор подробностей: прогон {д['прогон']}, бюджет {д['бюджет']}, "
              f"запросов {д['запросов_в_прогоне']}")
        print(f"   в кэше {д['в_кэше']} из {д['всего_в_каталоге']}; "
              f"НЕ в кэше {д['не_в_кэше']}")
        if д["не_в_кэше"] and д["бюджет"]:
            суток = (д["не_в_кэше"] + д["бюджет"] - 1) // д["бюджет"]
            print(f"   при нынешнем бюджете покрытие закроется за ~{суток} сут "
                  "(без учёта новых записей)")
    if итог["расхождение_кэш_витрина"]:
        print("\nВНИМАНИЕ: есть записи, где жанры в кэше ЕСТЬ, а на витрине нет — "
              "это потеря при сборке, а не покрытие")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(главное())
