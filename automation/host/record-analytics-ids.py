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
import os
import re
from datetime import datetime, timezone
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
# Корни (MOD-198) — как у seo_operator.paths: отчёты пишут службы в корень
# состояния, реестр ячеек — живой, в рабочей копии.
СОСТОЯНИЕ = Path(os.environ.get("SEO_STATE_ROOT") or КОРЕНЬ)
РЕЕСТРЫ = Path(os.environ.get("SEO_REGISTRY_ROOT") or КОРЕНЬ)
РЕЕСТР = РЕЕСТРЫ / "config" / "site-cells.json"
ОТЧЁТЫ_МЕТРИКИ = СОСТОЯНИЕ / "var" / "analytics"
#: Отчёты Topvisor. Берётся САМЫЙ СВЕЖИЙ из двух: `check-latest.txt` пишется до
#: применения плана, `check-after-connect.txt` — после. Если читать только
#: первый, только что созданные проекты в реестр не попадут: ровно так два
#: проекта (#33768290 и #33768310) остались бы незаписанными.
ОТЧЁТЫ_TOPVISOR = (
    СОСТОЯНИЕ / "var" / "topvisor" / "check-after-connect.txt",
    СОСТОЯНИЕ / "var" / "topvisor" / "check-latest.txt",
)


def _свежий_отчёт() -> Path | None:
    существующие = [п for п in ОТЧЁТЫ_TOPVISOR if п.is_file() and п.stat().st_size]
    return max(существующие, key=lambda п: п.stat().st_mtime) if существующие else None


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
    отчёт = _свежий_отчёт()
    if отчёт is None:
        return {}
    итог: dict[str, dict] = {}
    время = _время(отчёт)
    for строка in отчёт.read_text(encoding="utf-8").splitlines():
        совпало = СТРОКА_ПРОЕКТА.match(строка)
        if совпало:
            ид, домен, название = совпало.groups()
            # При дубле оставляем первый и говорим об этом: выбор между двумя
            # проектами одного домена — решение владельца.
            итог.setdefault(
                домен, {"project_id": int(ид), "name": название.strip(), "_время": время}
            )
    return итог


ИЗМЕРЕНИЕ_TOPVISOR = СОСТОЯНИЕ / "var" / "topvisor" / "measure-latest.json"
ЯДРО_TOPVISOR = РЕЕСТРЫ / "config" / "topvisor-cores.json"


def измерения(путь: Path = ИЗМЕРЕНИЕ_TOPVISOR) -> dict[str, dict]:
    """Домен → фактические настройки из `topvisor measure`. Нет файла — пусто."""
    import sys  # noqa: PLC0415

    try:
        данные = json.loads(путь.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    sys.path.insert(0, str(КОРЕНЬ))
    from factory.topvisor.manifest import by_domain  # noqa: PLC0415

    try:
        ядро = json.loads(ЯДРО_TOPVISOR.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        ядро = {}
    итог = {}
    for с in данные.get("sites") or []:
        if not с.get("domain") or с.get("project_id") is None:
            continue
        spec = by_domain(с["domain"])
        итог[с["domain"]] = {
            "project_id": int(с["project_id"]),
            "measured_at": данные.get("measured_at"),
            "source": "factory.topvisor.cli measure (get/projects_2/projects с регионами)",
            "state": с.get("state"),
            "on_raw": с.get("on_raw"),
            "regions": [{k: р.get(k) for k in ("index", "searcher", "device", "region_name",
                                               "region_key", "depth", "enabled")}
                        for р in с.get("regions") or []],
            "keywords_total": с.get("keywords_total"),
            "last_check": с.get("last_check"),
            "strategy": spec.focus if spec else None,
            "core_version": ядро.get("version"),
        }
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
        if not м and not т and домен not in измерения():
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
        замер = измерения().get(домен)
        if замер:
            # Измерение `topvisor measure` — чтение аккаунта с регионами
            # (show_searchers_and_regions): это и есть «фактически применённые
            # настройки». Стратегия — из манифеста, ядро — версия реестра.
            настройки = dict(блок.get("topvisor_settings") or {})
            настройки.update(замер)
            блок["topvisor_settings"] = настройки
            блок["topvisor_project_id"] = замер["project_id"]
            блок["topvisor_verified_at"] = замер["measured_at"]

        части = []
        if м:
            домен_api = м.get("api_site")
            части.append(
                f"счётчик {м['counter_id']} создан службой, отчёт "
                f"{Path(м['_отчёт']).relative_to(СОСТОЯНИЕ)} от {м['_время']}"
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
