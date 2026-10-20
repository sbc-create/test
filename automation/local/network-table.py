#!/usr/bin/env python3
"""Сводная таблица по сети: состояние, показатели, препятствие, следующий шаг.

Таблица СОБИРАЕТСЯ из уже существующих источников, а не заводит ещё один
реестр, который разойдётся с действительностью:

  config/site-cells.json     паспорт ячейки: домен, статус, режим индексации,
                             publisher_id, исключение из продвижения;
  config/analytics.json      счётчик, цели, состояние Вебмастера;
  var/seo/traffic-wow.json   визиты и поиск неделя к неделе
                             (automation/local/traffic-week-over-week.py);
  живой ответ домена         код и время главной.

Суждения («подтверждённая проблема», «следующий шаг») в автоматический вывод
НЕ подставляются: они пишутся руками в отчёте, а инструмент даёт факты, на
которые эти суждения опираются.

    python3 automation/local/network-table.py --out docs/NETWORK_STATE_20261017.md
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
ЯЧЕЙКИ = КОРЕНЬ / "config" / "site-cells.json"
АНАЛИТИКА = КОРЕНЬ / "config" / "analytics.json"
ТРАФИК = КОРЕНЬ / "var" / "seo" / "traffic-wow.json"

ЗАМОРОЖЕННЫЕ = {"lordserials22.site", "lordserials22.space",
                "lordserial101.site", "lordfilm077.site"}


def ячейки() -> dict[str, dict]:
    j = json.loads(ЯЧЕЙКИ.read_text(encoding="utf-8"))
    список = j.get("cells") or []
    записи = список.values() if isinstance(список, dict) else список
    return {з["domain"]: з for з in записи
            if isinstance(з, dict) and з.get("domain")}


def аналитика() -> dict[str, dict]:
    j = json.loads(АНАЛИТИКА.read_text(encoding="utf-8"))
    return {п["domain"]: п for п in (j.get("properties") or [])}


def трафик() -> dict[str, dict]:
    if not ТРАФИК.is_file():
        return {}
    j = json.loads(ТРАФИК.read_text(encoding="utf-8"))
    return {с["домен"]: с for с in (j.get("строки") or [])}


def живой(домен: str) -> dict:
    п = subprocess.run(
        ["curl", "-sS", "--max-time", "30", "-o", "/dev/null",
         "-w", "%{http_code} %{time_total}", f"https://{домен}/"],
        capture_output=True, text=True)
    части = (п.stdout or "0 0").split()
    return {"код": части[0], "сек": float(части[1]) if len(части) > 1 else -1.0}


def главная(аргв: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--out", default="")
    а = р.parse_args(аргв)

    я, ан, тр = ячейки(), аналитика(), трафик()
    домены = sorted(set(я) | set(ан))
    домены = [д for д in домены if not д.endswith(".localhost")
              and not д.endswith(".localhost.test")]
    with ThreadPoolExecutor(max_workers=6) as пул:
        ответы = dict(zip(домены, пул.map(живой, домены), strict=True))

    строки = []
    for д in домены:
        ячейка = я.get(д) or {}
        инд = ячейка.get("indexing") or {}
        промо = ячейка.get("promotion") or {}
        изд = ячейка.get("publisher") or {}
        а_ = ан.get(д) or {}
        вм = (а_.get("webmaster") or {})
        т = тр.get(д) or {}
        строки.append({
            "домен": д,
            "site_id": ячейка.get("site_id"),
            "заморожен": д in ЗАМОРОЖЕННЫЕ,
            "статус": ячейка.get("status"),
            "код": ответы[д]["код"],
            "сек": ответы[д]["сек"],
            "индексация": инд.get("desired_state"),
            "продвижение_исключено": (промо or {}).get("excluded"),
            "publisher_id": изд.get("publisher_id"),
            "счётчик": а_.get("counter_id"),
            "вебмастер": вм.get("verification_status"),
            "визиты_7дн": т.get("визиты_7дн"),
            "визиты_7дн_прежние": т.get("визиты_7дн_прежние"),
            "люди_в_сутки": т.get("люди_визитов_в_сутки"),
            "поиск": (sum((т.get("поиск_визитов") or {}).values())
                      if т.get("поиск_измерен") else None),
        })

    загол = (f"{'домен':22} {'site_id':11} {'код':>4} {'инд':7} {'счётчик':>10} "
             f"{'вебмастер':20} {'виз7':>7} {'было':>6} {'люди/сут':>9} {'поиск':>6}")
    print(загол)
    for с in строки:
        метка = "*" if с["заморожен"] else " "

        def чис(значение, знаков=0):
            return "—" if значение is None else f"{значение:.{знаков}f}"

        print(f"{метка}{с['домен']:21} {str(с['site_id'] or '—'):11} "
              f"{с['код']:>4} {str(с['индексация'] or '—'):7} "
              f"{str(с['счётчик'] or '—'):>10} {str(с['вебмастер'] or '—'):20} "
              f"{чис(с['визиты_7дн']):>7} {чис(с['визиты_7дн_прежние']):>6} "
              f"{чис(с['люди_в_сутки'], 1):>9} {чис(с['поиск']):>6}")
    print(f"\nдоменов: {len(строки)}; из них заморожено (помечены *): "
          f"{sum(1 for с in строки if с['заморожен'])}")

    выход = КОРЕНЬ / "var" / "seo" / "network-table.json"
    выход.parent.mkdir(parents=True, exist_ok=True)
    выход.write_text(json.dumps(строки, ensure_ascii=False, indent=1) + "\n",
                     encoding="utf-8")
    print(f"сохранено: {выход}")
    return 0


if __name__ == "__main__":
    sys.exit(главная())
