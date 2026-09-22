#!/usr/bin/env python3
"""Реестр событий «новая серия» для Animedia — из сравнения снимков.

Источник событий провайдера витрине не передан, и выдумывать даты выхода
нельзя. Но в снимке подробностей есть то, что меняется при появлении серии:
число доступных серий сезона (`avail`). Сравнение вчерашнего снимка с
сегодняшним даёт настоящее событие — «у такого-то сезона стало на N серий
больше», с отметкой времени самого снимка, а не часов машины.

Чего этот реестр не делает: не придумывает номер серии, которого нет в данных,
не подставляет год произведения вместо даты, не создаёт событий там, где число
серий не менялось. Первый запуск только запоминает состояние — событий ещё не
из чего выводить, и витрина честно показывает пустую ленту.

    python3 automation/host/animedia-episode-ledger.py --site animedia-01
    python3 automation/host/animedia-episode-ledger.py --site animedia-01 --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import tempfile
import time
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
РАНТАЙМ = Path(os.environ.get("ANIMEDIA_RUNTIME_ROOT", "/srv/lords/.frontend"))
#: Где живут состояние и реестр — рядом со снимком каталога. Витрина работает
#: от другого пользователя и внутрь репозитория не смотрит; путь, выведенный
#: от файла релиза, указывал в неизменяемый каталог релиза, и лента новых
#: серий оставалась пустой при живом реестре.
ХРАНИЛИЩЕ = РАНТАЙМ
#: Реестр читает витрина, состояние — только этот инструмент.
РЕЖИМ_РЕЕСТРА = 0o644
РЕЖИМ_СОСТОЯНИЯ = 0o600
#: Сколько событий хранить: лента показывает последние, а история нужна для
#: проверки порядка и для отчётов.
ПРЕДЕЛ_СОБЫТИЙ = 2000


def состояние_из_снимка(детали: dict) -> dict:
    """Число доступных серий по сезонам — то, что сравнивается между снимками."""
    состояние = {}
    for slug, деталь in (детали or {}).items():
        сезоны = деталь.get("seasons")
        if not isinstance(сезоны, list):
            continue
        по_сезонам = {}
        for с in сезоны:
            if not isinstance(с, dict):
                continue
            try:
                номер = int(с.get("n") or 0)
                доступно = int(с.get("avail") or 0)
                всего = int(с.get("eps") or 0)
            except (TypeError, ValueError):
                continue
            if номер:
                по_сезонам[str(номер)] = [доступно, всего]
        if по_сезонам:
            состояние[slug] = по_сезонам
    return состояние


def события(прежнее: dict, текущее: dict, момент: str, каталог: dict) -> list[dict]:
    """События «стало больше доступных серий» между двумя состояниями."""
    найдено = []
    for slug, сезоны in текущее.items():
        было = прежнее.get(slug) or {}
        for номер, (доступно, всего) in сезоны.items():
            прежде = (было.get(номер) or [0, 0])[0]
            if slug not in прежнее:
                # Новый тайтл — это событие каталога, а не выхода серии.
                continue
            if доступно > прежде:
                запись = каталог.get(slug) or {}
                найдено.append({
                    "slug": slug,
                    "title": запись.get("title") or slug,
                    "url": запись.get("url") or f"/title/{slug}/",
                    "season": int(номер),
                    "episode_from": прежде,
                    "episode_to": доступно,
                    "episodes_total": всего,
                    "episode_published_at": момент,
                    "detected_from": "snapshot-diff",
                })
    return найдено


def _записать_атомарно(путь: Path, данные: dict, режим: int = 0o644) -> None:
    путь.parent.mkdir(parents=True, exist_ok=True)
    с, врем = tempfile.mkstemp(dir=str(путь.parent), prefix=путь.name, suffix=".tmp")
    try:
        with os.fdopen(с, "w", encoding="utf-8") as ф:
            json.dump(данные, ф, ensure_ascii=False, indent=1)
            ф.write("\n")
        os.chmod(врем, режим)
        os.replace(врем, путь)
    except BaseException:
        Path(врем).unlink(missing_ok=True)
        raise


def main() -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--site", default="animedia-01")
    р.add_argument("--dry-run", action="store_true")
    a = р.parse_args()

    детали_файл = РАНТАЙМ / f"{a.site}-details.json"
    каталог_файл = РАНТАЙМ / f"{a.site}-catalog.json"
    if not детали_файл.is_file():
        raise SystemExit(f"нет снимка подробностей: {детали_файл}")
    сырое = json.loads(детали_файл.read_text(encoding="utf-8"))
    детали = сырое.get("details") or {}
    момент = str(сырое.get("catalog_built_at") or "") or time.strftime(
        "%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    ревизия = str(сырое.get("catalog_revision") or "")
    каталог_сырое = json.loads(каталог_файл.read_text(encoding="utf-8"))
    каталог = {з["slug"]: з for з in (каталог_сырое.get("items")
                                      if isinstance(каталог_сырое, dict) else каталог_сырое)}

    файл_состояния = ХРАНИЛИЩЕ / f"{a.site}-episode-state.json"
    файл_реестра = ХРАНИЛИЩЕ / f"{a.site}-episode-events.json"
    прежнее_всё = (json.loads(файл_состояния.read_text(encoding="utf-8"))
                   if файл_состояния.is_file() else {})
    прежнее = прежнее_всё.get("seasons") or {}
    прежняя_ревизия = str(прежнее_всё.get("catalog_revision") or "")

    текущее = состояние_из_снимка(детали)
    первый_запуск = not прежнее
    новые = [] if первый_запуск else события(прежнее, текущее, момент, каталог)
    if ревизия and ревизия == прежняя_ревизия:
        # Снимок тот же — сравнивать не с чем, событий нет по определению.
        новые = []

    реестр = (json.loads(файл_реестра.read_text(encoding="utf-8"))
              if файл_реестра.is_file() else {"schema_version": 1, "site": a.site,
                                              "events": []})
    были = {(с["slug"], с["season"], с["episode_to"]) for с in реестр.get("events", [])}
    добавлено = [с for с in новые if (с["slug"], с["season"], с["episode_to"]) not in были]
    реестр["events"] = (добавлено + реестр.get("events", []))[:ПРЕДЕЛ_СОБЫТИЙ]
    реестр["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    реестр["source"] = "snapshot-diff"
    реестр["catalog_revision"] = ревизия
    реестр["catalog_built_at"] = момент
    реестр["first_run_seeded"] = первый_запуск
    реестр["titles_tracked"] = len(текущее)

    отчёт = {"site": a.site, "first_run": первый_запуск,
             "titles_tracked": len(текущее), "events_new": len(добавлено),
             "events_total": len(реестр["events"]), "catalog_revision": ревизия,
             "catalog_built_at": момент,
             "state_file": str(файл_состояния), "ledger_file": str(файл_реестра)}
    if a.dry_run:
        print(json.dumps(отчёт, ensure_ascii=False, indent=1))
        return 0

    _записать_атомарно(файл_состояния, {"schema_version": 1, "site": a.site,
                                        "catalog_revision": ревизия,
                                        "catalog_built_at": момент,
                                        "updated_at": реестр["updated_at"],
                                        "seasons": текущее},
                       РЕЖИМ_СОСТОЯНИЯ)
    _записать_атомарно(файл_реестра, реестр, РЕЖИМ_РЕЕСТРА)
    print(json.dumps(отчёт, ensure_ascii=False, indent=1))
    if первый_запуск:
        print("первый запуск: состояние запомнено, событий ещё нет — "
              "лента новых серий честно пуста до следующего снимка")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
