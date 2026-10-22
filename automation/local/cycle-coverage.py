#!/usr/bin/env python3
"""Какие АКТИВНЫЕ домены регулярный цикл фактически не трогает. Только чтение.

ЗАЧЕМ ОТДЕЛЬНАЯ МЕРА. «Цикл установлен и таймеры срабатывают» не означает, что
цикл видит все сайты. Измерено 2026-10-22 в 08:0xZ: юниты
`automation/host/seo-regular/*.service` работают с
`WorkingDirectory=/home/claude/wt-portable-site-cell-01`, и реестр ячеек ТОЙ
копии содержит 25 ячеек без восьми витрин K2, тогда как в этой копии их 33 с K2.
Поэтому прогон 05:25Z прочитал 21 домен, проверил 21 и ни одной витрины K2 —
восемь живых сайтов не получали ни проверки доступности, ни сверки режима
индексации, ни карты, ни аналитики. По одному взгляду на `regular status` это
НЕ видно: он показывает «таймеры включены, срабатывали сегодня».

Мера сравнивает три множества:

1. **активные домены** — `config/active-domains.json`, список из задания
   владельца (он же единственный версионируемый источник);
2. **домены, которые цикл ОБЪЯВИЛ** — шаг `discover` последнего прогона;
3. **домены, которые цикл ПРОВЕРИЛ** — шаг `availability` того же прогона.

Различать второе и третье обязательно: домен может быть объявлен и не проверен
(исчерпан бюджет запросов), и это другой дефект, чем «его нет в реестре».

Исходы раздельные:

* ``ПОЛНО``          — каждый активный домен объявлен и проверен;
* ``ВНЕ ЦИКЛА``      — активный домен не объявлен: цикл о нём не знает;
* ``НЕ ПРОВЕРЕН``    — объявлен, но проверки в прогоне нет;
* ``НЕ ИЗМЕРЕНО``    — состояние цикла не прочитано.

    python3 automation/local/cycle-coverage.py
    python3 automation/local/cycle-coverage.py --json
    python3 automation/local/cycle-coverage.py --root /путь/к/копии/цикла

Коды: 0 — полно; 1 — есть домены вне цикла или непроверенные; 2 — не измерено.
"""
from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import sys

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
СПИСОК = КОРЕНЬ / "config" / "active-domains.json"
#: Где живёт состояние цикла. Берётся из `config/active-domains.json`
#: (`shared_components.regular_cycle.owner`), а не угадывается.
КОПИИ = pathlib.Path("/home/claude")

ПОЛНО = "ПОЛНО"
ВНЕ_ЦИКЛА = "ВНЕ ЦИКЛА"
НЕ_ПРОВЕРЕН = "НЕ ПРОВЕРЕН"
НЕ_ИЗМЕРЕНО = "НЕ ИЗМЕРЕНО"


def активные(путь: pathlib.Path = СПИСОК) -> list[dict]:
    д = json.loads(путь.read_text(encoding="utf-8"))
    return list(д.get("domains") or [])


def владелец_цикла(путь: pathlib.Path = СПИСОК) -> str:
    д = json.loads(путь.read_text(encoding="utf-8"))
    общие = д.get("shared_components") or {}
    return str((общие.get("regular_cycle") or {}).get("owner") or "")


def последний_прогон(корень: pathlib.Path) -> pathlib.Path | None:
    """Самый свежий каталог прогона режима `check` или `daily`.

    Берётся именно он, а не `state.json`: состояние накапливается и помнит
    домены, которых в последнем прогоне уже не было, то есть показало бы
    охват вчерашнего реестра как сегодняшний.
    """
    прогоны = корень / "runs"
    if not прогоны.is_dir():
        return None
    годные = [п for п in прогоны.iterdir()
              if п.is_dir() and (п.name.startswith("check-")
                                 or п.name.startswith("daily-"))]
    if not годные:
        return None
    return max(годные, key=lambda п: п.stat().st_mtime)


def домены_шага(прогон: pathlib.Path, шаг: str) -> set[str] | None:
    ф = прогон / f"{шаг}.json"
    if not ф.is_file():
        return None
    try:
        д = json.loads(ф.read_text(encoding="utf-8"))
    except ValueError:
        return None
    записи = д if isinstance(д, list) else (д.get("availability") or [])
    return {str(з.get("domain")) for з in записи if з.get("domain")}


def проверенные_домены(прогон: pathlib.Path) -> tuple[set[str], str]:
    """Домены, проверенные в этом прогоне, и ОТКУДА это известно.

    Суточный прогон доступность не перепроверяет: он берёт результат проверки,
    если той меньше семи часов, и кладёт её внутрь `check.json` под ключом
    `availability` с пометкой `reused`. Первая редакция этой меры читала
    только `availability.json`, не находила его в суточном прогоне и объявляла
    НЕ ПРОВЕРЕННЫМИ все 17 домéнов — то есть давала ложную находку на
    исправном цикле. Поэтому источник называется в выводе.
    """
    прямо = домены_шага(прогон, "availability")
    if прямо:
        return прямо, "availability"
    ф = прогон / "check.json"
    if ф.is_file():
        try:
            д = json.loads(ф.read_text(encoding="utf-8"))
        except ValueError:
            д = {}
        записи = (д.get("availability") or []) if isinstance(д, dict) else []
        if записи:
            источник = ("check.json (переиспользованная проверка)"
                        if (isinstance(д, dict) and д.get("reused"))
                        else "check.json")
            return ({str(з.get("domain")) for з in записи
                     if з.get("domain")}, источник)
    return set(), "не найдено"


def исход_домена(домен: str, объявлены: set[str],
                 проверены: set[str]) -> str:
    """Исход по одному домену. Чистая функция."""
    if домен not in объявлены:
        return ВНЕ_ЦИКЛА
    if домен not in проверены:
        return НЕ_ПРОВЕРЕН
    return ПОЛНО


def свести(исходы: dict[str, str]) -> str:
    if not исходы:
        return НЕ_ИЗМЕРЕНО
    if any(и == ВНЕ_ЦИКЛА for и in исходы.values()):
        return ВНЕ_ЦИКЛА
    if any(и == НЕ_ПРОВЕРЕН for и in исходы.values()):
        return НЕ_ПРОВЕРЕН
    return ПОЛНО


def проверить(корень_цикла: pathlib.Path | None = None,
              список: pathlib.Path = СПИСОК) -> dict:
    домены = активные(список)
    владелец = владелец_цикла(список)
    корень = корень_цикла or (КОПИИ / владелец / "var" / "seo-regular")
    прогон = последний_прогон(корень)
    if прогон is None:
        return {"исход": НЕ_ИЗМЕРЕНО, "корень_цикла": str(корень),
                "владелец_цикла": владелец, "активных": len(домены),
                "почему": "каталогов прогонов нет — состояние цикла не прочитано"}
    объявлены = домены_шага(прогон, "discover")
    проверены, источник_проверки = проверенные_домены(прогон)
    if объявлены is None:
        return {"исход": НЕ_ИЗМЕРЕНО, "корень_цикла": str(корень),
                "прогон": прогон.name, "активных": len(домены),
                "почему": "в прогоне нет шага discover"}
    исходы = {з["domain"]: исход_домена(з["domain"], объявлены, проверены)
              for з in домены}
    по_семьям: dict[str, list[str]] = {}
    for з in домены:
        if исходы[з["domain"]] != ПОЛНО:
            по_семьям.setdefault(з["family"], []).append(з["domain"])
    время = datetime.datetime.fromtimestamp(
        прогон.stat().st_mtime, datetime.timezone.utc).isoformat(
            timespec="seconds").replace("+00:00", "Z")
    return {
        "исход": свести(исходы),
        "владелец_цикла": владелец,
        "корень_цикла": str(корень),
        "прогон": прогон.name,
        "время_прогона": время,
        "активных": len(домены),
        "объявлено_циклом": len(объявлены),
        "проверено_циклом": len(проверены),
        "источник_проверки": источник_проверки,
        "вне_цикла": sorted(д for д, и in исходы.items() if и == ВНЕ_ЦИКЛА),
        "не_проверены": sorted(д for д, и in исходы.items()
                               if и == НЕ_ПРОВЕРЕН),
        "лишние_в_цикле": sorted(объявлены - {з["domain"] for з in домены}),
        "по_семьям": {к: sorted(v) for к, v in sorted(по_семьям.items())},
        "исходы": исходы,
    }


def main(аргв: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--root", default="",
                   help="каталог состояния цикла; по умолчанию берётся из"
                        " shared_components.regular_cycle.owner")
    р.add_argument("--json", action="store_true")
    а = р.parse_args(аргв)

    итоги = проверить(pathlib.Path(а.root) if а.root else None)
    if а.json:
        print(json.dumps(итоги, ensure_ascii=False, indent=1))
    elif итоги["исход"] == НЕ_ИЗМЕРЕНО:
        print(f"{НЕ_ИЗМЕРЕНО}: {итоги.get('почему', '')}", file=sys.stderr)
    else:
        print(f"охват регулярного цикла: {итоги['исход']}")
        print(f"   цикл живёт в {итоги['владелец_цикла']},"
              f" прогон {итоги['прогон']} ({итоги['время_прогона']})")
        print(f"   активных домéнов {итоги['активных']},"
              f" цикл объявил {итоги['объявлено_циклом']},"
              f" проверил {итоги['проверено_циклом']}"
              f" (источник: {итоги['источник_проверки']})")
        if итоги["вне_цикла"]:
            print(f"   ВНЕ ЦИКЛА ({len(итоги['вне_цикла'])}):"
                  f" {', '.join(итоги['вне_цикла'])}")
        if итоги["не_проверены"]:
            print(f"   объявлены, но НЕ ПРОВЕРЕНЫ"
                  f" ({len(итоги['не_проверены'])}):"
                  f" {', '.join(итоги['не_проверены'])}")
        if итоги["лишние_в_цикле"]:
            print(f"   цикл проверяет домены вне активного списка:"
                  f" {', '.join(итоги['лишние_в_цикле'])}")
        for семья, домены in итоги["по_семьям"].items():
            print(f"      семья {семья}: {len(домены)} вне работы")
        print("   «таймеры включены» охватом НЕ является: цикл читает реестр"
              " ТОЙ копии, в которой работает")

    if итоги["исход"] == НЕ_ИЗМЕРЕНО:
        return 2
    return 0 if итоги["исход"] == ПОЛНО else 1


if __name__ == "__main__":
    sys.exit(main())
