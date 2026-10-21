#!/usr/bin/env python3
"""Путь 1 из приёмки MOD-116: обогащает ли поставщик записи без постера.

Приёмка MOD-116 называет три честных пути закрытия, и первый не требует
ничего: «поставщик обогащает запись позже — тогда постер приедет сам. Признак: у
этих `external_id` в ответе поставщика появляется непустой `poster_url`.
Проверяется повторным чтением кеша, сверять по `fetched_at_ms`». Этот проход и
есть та проверка, чтобы ждать не на словах, а по измерению.

Запись опознаётся ТОЛЬКО по `external_id`. У поставщика нет поля `slug`, а
сверка по названию — это сопоставление, то есть отдельный класс ошибок: две
записи с одним названием дали бы ответ про чужую.

Что печатается:

* `ПОЯВИЛСЯ` — у записи в ответе поставщика непустой `poster_url`. Это и есть
  путь 1, сработавший сам;
* `пусто` — запись найдена, постера по-прежнему нет;
* `не измерено` — записи с таким `external_id` в ответе нет вовсе. Это не
  «пусто»: пропавшая запись — отдельный вопрос, и нулём он не подменяется.

Различающий контроль ВСТРОЕН и печатается всегда: доля записей, которых
поставщик не трогал со дня создания, считается и среди записей БЕЗ постера, и
среди записей С постером. Если доли равны, признак «поставщик к записи не
возвращается» ничего не различает, и вывод про путь 1 делать нельзя.

    python3 automation/local/poster-provider-watch.py --family lords-02
    python3 automation/local/poster-provider-watch.py --family lords-02 \\
        --rows /home/claude/wt-portable-site-cell-01/var/seo-audit/\\
lordserial33-missing-posters-20261020.json
"""
from __future__ import annotations

import argparse
import ast
import collections
import datetime as dt
import json
import sys
from pathlib import Path

#: Ответ поставщика по семейству. Пути те же, что в `poster-cause-per-card.py`.
ПОСТАВЩИК = {
    "lords-01": "/srv/site-factory/repo/var/lords/lords/catalog-cache/lords-01.json",
    "lords-02": "/srv/site-factory/repo/var/lords/lords/catalog-cache/lords-02.json",
    "lords-03": "/srv/site-factory/repo/var/lords/lords/catalog-cache/lords-03.json",
}


def _внешние(значение) -> dict:
    """`external_ids` приходит то словарём, то его строковой записью."""
    if isinstance(значение, dict):
        return значение
    if isinstance(значение, str) and значение.strip().startswith("{"):
        try:
            разобрано = ast.literal_eval(значение)
        except (ValueError, SyntaxError):
            return {}
        return разобрано if isinstance(разобрано, dict) else {}
    return {}


def прочитать_ответ(путь: Path) -> tuple[list[dict], str] | None:
    try:
        d = json.loads(путь.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    записи = d.get("items") or d.get("records") or []
    мс = d.get("fetched_at_ms")
    когда = ""
    if isinstance(мс, (int, float)):
        когда = dt.datetime.fromtimestamp(мс / 1000, dt.timezone.utc).isoformat()
    return записи, когда


def есть_постер(з: dict) -> bool:
    return bool(str(з.get("poster_url") or "").strip())


def не_трогали(з: dict) -> bool:
    """Поставщик не возвращался к записи со дня её создания."""
    создана = str(з.get("created_at") or "")[:10]
    обновлена = str(з.get("updated_at") or "")[:10]
    return bool(создана) and создана == обновлена


def разобрать_список(путь: Path) -> list[tuple[str, str]]:
    """`(имя для печати, external_id)` из переданного линией SEO списка."""
    d = json.loads(путь.read_text(encoding="utf-8"))
    строки = d["rows"] if isinstance(d, dict) else d
    пары = []
    for с in строки:
        ид = str(с.get("work_id") or с.get("external_id") or "").strip()
        имя = str(с.get("url") or с.get("slug") or ид).rstrip("/").rsplit("/", 1)[-1]
        if ид:
            пары.append((имя, ид))
    return пары


def проверить(записи: list[dict], карточки: list[tuple[str, str]]) -> dict:
    по_ид = {}
    for з in записи:
        и = str(з.get("external_id") or "").strip()
        if и:
            по_ид.setdefault(и, з)
    итог = {"появился": [], "пусто": [], "не_измерено": []}
    for имя, ид in карточки:
        з = по_ид.get(ид)
        if з is None:
            итог["не_измерено"].append(имя)
        elif есть_постер(з):
            итог["появился"].append((имя, str(з.get("poster_url")).strip()))
        else:
            итог["пусто"].append(имя)
    return итог


def сводка(записи: list[dict]) -> dict:
    без = [з for з in записи if not есть_постер(з)]
    с = [з for з in записи if есть_постер(з)]
    внешние = sum(1 for з in без
                  if _внешние(з.get("external_ids")).get("kinopoisk")
                  or _внешние(з.get("external_ids")).get("imdb"))
    месяцы = collections.Counter(str(з.get("created_at") or "")[:7] for з in без)
    return {
        "записей": len(записи), "без_постера": len(без),
        "с_внешним_идентификатором": внешние,
        "не_трогали_без_постера": sum(1 for з in без if не_трогали(з)),
        "не_трогали_с_постером": sum(1 for з in с if не_трогали(з)),
        "с_постером": len(с),
        "по_месяцу_создания": dict(sorted(месяцы.items())),
    }


def main(аргв: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--family", default="lords-02", choices=sorted(ПОСТАВЩИК))
    р.add_argument("--source", help="путь к ответу поставщика (для проверки)")
    р.add_argument("--rows", help="переданный список карточек (JSON)")
    р.add_argument("--json", action="store_true")
    а = р.parse_args(аргв)

    путь = Path(а.source or ПОСТАВЩИК[а.family])
    прочитано = прочитать_ответ(путь)
    if прочитано is None:
        print(f"НЕ ИЗМЕРЕНО: ответ поставщика не прочитан: {путь}")
        return 2
    записи, когда = прочитано
    if not записи:
        print(f"НЕ ИЗМЕРЕНО: в ответе поставщика нет записей: {путь}")
        return 2
    с = сводка(записи)
    карточки = разобрать_список(Path(а.rows)) if а.rows else []
    проверка = проверить(записи, карточки) if карточки else None

    if а.json:
        print(json.dumps({"снят": когда, "сводка": с, "карточки": проверка},
                         ensure_ascii=False, indent=1))
        return 0

    print(f"ответ поставщика {а.family}: снят {когда or '—'},"
          f" записей {с['записей']}, без постера {с['без_постера']}"
          f" ({с['без_постера'] / с['записей'] * 100:.2f} %)")
    доля_без = с["не_трогали_без_постера"] / max(с["без_постера"], 1) * 100
    доля_с = с["не_трогали_с_постером"] / max(с["с_постером"], 1) * 100
    print(f"   с внешним идентификатором (kinopoisk или imdb):"
          f" {с['с_внешним_идентификатором']} из {с['без_постера']}")
    print(f"   не трогали со дня создания: без постера"
          f" {с['не_трогали_без_постера']} ({доля_без:.1f} %),"
          f" с постером {с['не_трогали_с_постером']} ({доля_с:.1f} %)")
    if abs(доля_без - доля_с) < 5:
        print("   РАЗЛИЧАЮЩИЙ КОНТРОЛЬ НЕ ПРОЙДЕН: доли равны, признак"
              " «поставщик не возвращается» ничего не различает")
    else:
        print(f"   различающий контроль пройден: разница {доля_без - доля_с:+.1f}"
              f" процентного пункта")
    старые = sum(н for м, н in с["по_месяцу_создания"].items() if м < "2026-07")
    print(f"   из них созданы раньше июля 2026: {старые} — у них на обогащение"
          f" было больше трёх месяцев")

    if проверка is None:
        return 0
    print(f"\nпереданные карточки: {len(карточки)}")
    for имя, адрес in проверка["появился"]:
        print(f"   ПОЯВИЛСЯ     {имя[:46]:<46} {адрес[:60]}")
    for имя in проверка["пусто"]:
        print(f"   пусто        {имя[:46]}")
    for имя in проверка["не_измерено"]:
        print(f"   не измерено  {имя[:46]} — записи с таким external_id в ответе нет")
    print(f"\nитог пути 1: появился постер у {len(проверка['появился'])} из"
          f" {len(карточки)}; пусто {len(проверка['пусто'])};"
          f" не измерено {len(проверка['не_измерено'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
