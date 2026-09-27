#!/usr/bin/env python3
"""Перенос фактических идентификаторов из отчётов служб в реестр ячеек.

Источник — только ответы API, записанные службами:

* ``var/analytics/connect-<домен>.json`` — счётчик Метрики (`analytics apply`);
* ``var/topvisor/check-latest.txt`` — список проектов аккаунта (`topvisor check`).

Почему инструмент, а не правка руками. Шесть девятизначных чисел и шесть
восьмизначных, перенесённые глазами, — это двенадцать шансов на опечатку, и
каждая означает отчёт по чужому проекту или счётчику. Здесь же ставится и
разделение состояний, которое руками легко потерять: идентификатор объекта в
сервисе и подтверждение его работы на сайте — разные поля.

Чего инструмент НЕ делает:

* не обращается к API — читает уже полученные ответы;
* не выдумывает идентификаторов: нет строки в отчёте — поле остаётся ``null``;
* не ставит ``metrika_verified_at`` и ``metrika_data_seen_at``. Первое означает
  подтверждённую отправку из браузера, второе — визит, увиденный в статистике.
  Ни то, ни другое из отчёта о создании счётчика не следует.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
РЕЕСТР = КОРЕНЬ / "config" / "site-cells.json"
ОТЧЁТЫ_МЕТРИКИ = КОРЕНЬ / "var" / "analytics"
ОТЧЁТ_TOPVISOR = КОРЕНЬ / "var" / "topvisor" / "check-latest.txt"

#: Строка списка проектов: «    #33762526 zonafilm12.site — название».
СТРОКА_ПРОЕКТА = re.compile(r"^\s*#(\d+)\s+(\S+)\s+—\s+(.*)$")


def _время(путь: Path) -> str:
    return datetime.fromtimestamp(путь.stat().st_mtime, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def счётчики() -> dict[str, dict]:
    """Домен → что ответила Метрика. Только из отчётов служб."""
    итог: dict[str, dict] = {}
    for файл in sorted(ОТЧЁТЫ_МЕТРИКИ.glob("connect-*.json")):
        домен = файл.name[len("connect-") : -len(".json")]
        try:
            данные = json.loads(файл.read_text(encoding="utf-8"))
        except ValueError:
            continue
        запись = next((з for з in данные.get("results") or [] if з.get("domain") == домен), None)
        if запись and запись.get("counter_id"):
            итог[домен] = {**запись, "_отчёт": файл, "_время": _время(файл)}
    return итог


def проекты() -> dict[str, dict]:
    """Домен → проект Topvisor из списка, который вернул API."""
    if not ОТЧЁТ_TOPVISOR.is_file():
        return {}
    итог: dict[str, dict] = {}
    время = _время(ОТЧЁТ_TOPVISOR)
    for строка in ОТЧЁТ_TOPVISOR.read_text(encoding="utf-8").splitlines():
        совпало = СТРОКА_ПРОЕКТА.match(строка)
        if совпало:
            ид, домен, название = совпало.groups()
            # При дубле оставляем первый и говорим об этом: выбор между двумя
            # проектами одного домена — решение владельца.
            итог.setdefault(
                домен, {"project_id": int(ид), "name": название.strip(), "_время": время}
            )
    return итог


def main(argv: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    р.add_argument("--apply", action="store_true", help="записать; без флага только показывает")
    а = р.parse_args(argv)

    реестр = json.loads(РЕЕСТР.read_text(encoding="utf-8"))
    метрика, топвизор = счётчики(), проекты()
    изменено = 0

    for ячейка in реестр["cells"]:
        домен = ячейка["domain"]
        м, т = метрика.get(домен), топвизор.get(домен)
        if not м and not т:
            continue
        блок = dict(ячейка.get("analytics") or {})
        было = json.dumps(блок, ensure_ascii=False, sort_keys=True)

        if м:
            блок["metrika_counter_id"] = int(м["counter_id"])
            блок.setdefault("metrika_verified_at", None)
            блок.setdefault("metrika_data_seen_at", None)
        if т:
            блок["topvisor_project_id"] = т["project_id"]
            # Проект прочитан из ответа API на `get/projects_2/projects` —
            # это и есть сверка «проект с таким доменом существует».
            блок["topvisor_verified_at"] = т["_время"]
            настройки = dict(блок.get("topvisor_settings") or {})
            настройки["name"] = т["name"]
            настройки["source"] = "get/projects_2/projects"
            блок["topvisor_settings"] = настройки

        части = []
        if м:
            домен_api = м.get("api_site")
            части.append(
                f"счётчик {м['counter_id']} создан службой, отчёт "
                f"{Path(м['_отчёт']).relative_to(КОРЕНЬ)} от {м['_время']}"
                + (
                    f"; домен счётчика по ответу API — {домен_api}"
                    if домен_api
                    else "; домен счётчика в отчёте отсутствует — перезапустите"
                    " analytics-connect@<домен>.service после исправления"
                )
            )
        if т:
            части.append(f"проект {т['project_id']} прочитан из списка аккаунта")
        части.append(
            "отправка события браузером и визит в статистике не подтверждены: "
            "это отдельные состояния и отдельные поля"
        )
        блок["note"] = ". ".join(части)

        if json.dumps(блок, ensure_ascii=False, sort_keys=True) != было:
            изменено += 1
            print(
                f"{домен:24} счётчик={блок.get('metrika_counter_id')} "
                f"проект={блок.get('topvisor_project_id')}"
            )
            if а.apply:
                ячейка["analytics"] = блок

    if а.apply and изменено:
        РЕЕСТР.write_text(json.dumps(реестр, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\nячеек с изменениями: {изменено}" + ("" if а.apply else " (без --apply не записано)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
