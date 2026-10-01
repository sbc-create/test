#!/usr/bin/env python3
"""Подключение счётчика Метрики в репозитории витрины — один шаг, не шесть правок.

Зачем отдельный инструмент
--------------------------

Счётчик объявляется в `config/site.json` витрины (поле
`environment.LORDS_METRIKA_COUNTER`), а не в drop-in юнита на хосте: иначе
выпуск теряет его, что однажды и произошло сразу у четырёх доменов. Само
объявление — одна строка, но делать её руками по домену значит шесть раз
повторить один и тот же шанс опечататься в девятизначном числе, причём ошибка
видна только по чужой статистике.

Что инструмент не делает
------------------------

Не придумывает идентификаторы. Источник — `config/analytics.json`, куда их
пишет только `factory analytics apply`. Нет счётчика — нет записи: строка
«ещё не создан» честнее подставленного значения.

Не коммитит и не выкладывает. Это делает штатный выпуск, у которого свои
проверки происхождения.

Отказы, а не тихие перезаписи
-----------------------------

* счётчик уже указан у другого домена — смешение двух аудиторий необратимо;
* в site.json стоит другое непустое значение — перезапись только с `--replace`;
* витрина проксирует сторонее приложение (`LORDS_LEGACY_UPSTREAM`) — разметку
  отдаёт приложение выше по потоку, и переменная была бы мёртвой настройкой.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
АНАЛИТИКА = КОРЕНЬ / "config" / "analytics.json"
РЕЕСТР = КОРЕНЬ / "config" / "site-cells.json"
ПЕРЕМЕННАЯ = "LORDS_METRIKA_COUNTER"
ПРОКСИ = "LORDS_LEGACY_UPSTREAM"

ОК = "ок"
УЖЕ = "уже подключён"
НЕТ_СЧЁТЧИКА = "счётчика ещё нет"
НЕТ_РЕПОЗИТОРИЯ = "нет рабочей копии"
ПРОКСИ_ВИТРИНА = "проксирует приложение"
КОНФЛИКТ = "конфликт"


def _прочитать(путь: Path) -> dict:
    return json.loads(путь.read_text(encoding="utf-8"))


def _счётчики() -> dict[str, str]:
    итог = {}
    for з in _прочитать(АНАЛИТИКА)["properties"]:
        ид = з.get("counter_id")
        if ид:
            итог[з["domain"]] = str(ид)
    return итог


def _ячейки() -> list[dict]:
    return _прочитать(РЕЕСТР)["cells"]


def _записать(путь: Path, данные: dict) -> None:
    """Атомарно и с тем же завершающим переводом строки, что у исходника."""
    временный = путь.with_suffix(".json.tmp")
    временный.write_text(json.dumps(данные, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    временный.replace(путь)


def подключить(
    ячейка: dict, счётчики: dict[str, str], *, применять: bool, заменять: bool
) -> tuple[str, str]:
    домен = ячейка["domain"]
    ид = счётчики.get(домен)
    if not ид:
        return НЕТ_СЧЁТЧИКА, f"{домен}: в реестре аналитики нет counter_id"

    чужие = [d for d, значение in счётчики.items() if значение == ид and d != домен]
    if чужие:
        return КОНФЛИКТ, f"счётчик {ид} указан ещё у {', '.join(чужие)}"

    путь = КОРЕНЬ / ((ячейка.get("repo") or {}).get("path") or "")
    файл = путь / "config" / "site.json"
    if not файл.is_file():
        return НЕТ_РЕПОЗИТОРИЯ, f"{файл} отсутствует"

    конфиг = _прочитать(файл)
    окружение = конфиг.setdefault("environment", {})
    if окружение.get(ПРОКСИ):
        return ПРОКСИ_ВИТРИНА, f"разметку отдаёт {окружение[ПРОКСИ]}"

    текущее = str(окружение.get(ПЕРЕМЕННАЯ) or "").strip()
    if текущее == ид:
        return УЖЕ, f"{ПЕРЕМЕННАЯ}={ид}"
    if текущее and not заменять:
        return КОНФЛИКТ, (
            f"в site.json стоит {текущее}, в реестре {ид}; " "перезапись только с --replace"
        )

    if применять:
        окружение[ПЕРЕМЕННАЯ] = ид
        _записать(файл, конфиг)
    return ОК, (
        f"{ПЕРЕМЕННАЯ}: {текущее or 'пусто'} → {ид}"
        + ("" if применять else " (без --apply не записано)")
    )


def main(argv: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    р.add_argument(
        "--site",
        action="append",
        default=[],
        help="site_id; можно повторить. По умолчанию — все ячейки",
    )
    р.add_argument(
        "--apply", action="store_true", help="записать изменения; без флага только показывает"
    )
    р.add_argument(
        "--replace", action="store_true", help="перезаписать уже стоящее другое значение"
    )
    р.add_argument("--json", action="store_true")
    а = р.parse_args(argv)

    счётчики = _счётчики()
    ячейки = [c for c in _ячейки() if not а.site or c["site_id"] in а.site]
    неизвестные = set(а.site) - {c["site_id"] for c in _ячейки()}
    if неизвестные:
        print(f"нет таких ячеек: {', '.join(sorted(неизвестные))}", file=sys.stderr)
        return 2

    строки = []
    for ячейка in sorted(ячейки, key=lambda c: c["site_id"]):
        состояние, подробность = подключить(ячейка, счётчики, применять=а.apply, заменять=а.replace)
        строки.append(
            {
                "site_id": ячейка["site_id"],
                "domain": ячейка["domain"],
                "state": состояние,
                "detail": подробность,
            }
        )

    if а.json:
        print(json.dumps({"applied": а.apply, "rows": строки}, ensure_ascii=False, indent=2))
    else:
        ш = max(len(s["domain"]) for s in строки) if строки else 0
        for s in строки:
            print(f"{s['domain']:<{ш}}  {s['state']:<20} {s['detail']}")
        итог = {}
        for s in строки:
            итог[s["state"]] = итог.get(s["state"], 0) + 1
        print("\nитого: " + ", ".join(f"{k} — {v}" for k, v in sorted(итог.items())))

    # Конфликт — единственное, что требует решения человека.
    return 1 if any(s["state"] == КОНФЛИКТ for s in строки) else 0


if __name__ == "__main__":
    raise SystemExit(main())
