#!/usr/bin/env python3
"""Чтение СОБРАННЫХ показателей аналитики. Только чтение, без API и секрета.

Зачем этот модуль и почему он не второй сборщик
-----------------------------------------------

Сборщик уже есть и работает: юнит `analytics-cabinet.service` (`User=claude`,
`LoadCredential=yandex_oauth:/etc/site-factory/secrets/yandex_oauth_token`,
таймер `*-*-* 06:10:00 UTC`, `Persistent=true`) раз в сутки запускает
`bin/seo-operator analytics-collect` и кладёт снимок в
`artifacts/analytics/analytics-<дата>.json`. Измерено 2026-10-05: снимок за
этот день собран в 06:14:47Z, 187 показателей из 266 измерены, 79 не измерены
С НАЗВАННОЙ ПРИЧИНОЙ.

Чего не было — ЧТЕНИЯ этих данных операцией, доступной редактору SEO. Мост
отдавал только `analytics_readiness` (состояние записи в реестре), поэтому
ответ «фактические посещения не получены» был верен про чат и неверен про
фабрику: данные лежали на диске. Этот модуль закрывает именно разрыв доставки
и ничего не собирает сам.

Почему период разрешается здесь
------------------------------

Сборщик хранит период так, как его понимает API Метрики — относительными
метками (`7daysAgo`, `yesterday`). Для отчёта этого мало: «конкретный
завершённый период» обязан называться датами. Разрешение считается от
`collected_at` снимка и ПОМЕЧАЕТСЯ как вычисленное — выдавать его за ответ API
нельзя, API таких полей не возвращает.

Секрета модуль не касается: он читает готовый файл. Поэтому его может вызывать
служба моста, которой `LoadCredential` не выдан, — и это осознанное
разделение, а не упущение.
"""
from __future__ import annotations

import datetime as _dt
import json
import pathlib
import re
from typing import Any

#: Где лежат снимки сборщика. Тот же путь, что пишет `analytics-collect`.
КАТАЛОГ = pathlib.Path(__file__).resolve().parents[2] / "artifacts" / "analytics"

#: Имя снимка: `analytics-YYYY-MM-DD.json`.
ИМЯ = re.compile(r"^analytics-(\d{4}-\d{2}-\d{2})\.json$")

#: Относительные метки периода Метрики -> сдвиг в днях от даты сбора.
#: `yesterday` — день до сбора; `NdaysAgo` — ровно N дней до сбора.
_МЕТКИ = {"today": 0, "yesterday": 1}


class НетСнимка(RuntimeError):
    """Снимков сборщика нет. Это отсутствие данных, а не нулевые значения."""


def снимки() -> list[tuple[str, pathlib.Path]]:
    """Все снимки, новые первыми. Дата берётся из имени файла."""
    если = []
    if not КАТАЛОГ.is_dir():
        return если
    for п in КАТАЛОГ.iterdir():
        м = ИМЯ.match(п.name)
        if м and п.is_file():
            если.append((м.group(1), п))
    return sorted(если, reverse=True)


def последний() -> tuple[str, pathlib.Path]:
    всё = снимки()
    if not всё:
        raise НетСнимка(
            f"снимков сборщика нет в {КАТАЛОГ}. Сбор выполняет юнит "
            "analytics-cabinet.service по таймеру; отсутствие снимка означает, "
            "что он не запускался или отказал — это не нулевая посещаемость")
    return всё[0]


def _сдвиг(метка: str) -> int | None:
    """Сколько дней назад от даты сбора. None — метку не разобрать."""
    т = str(метка or "").strip()
    if т in _МЕТКИ:
        return _МЕТКИ[т]
    м = re.fullmatch(r"(\d+)daysAgo", т)
    return int(м.group(1)) if м else None


def разрешить_период(период: dict, собрано: str) -> dict:
    """Относительные метки -> конкретные даты. Помечено как ВЫЧИСЛЕННОЕ.

    `collected_at` — время сбора в UTC. От него и считается: сборщик спрашивал
    API в этот момент, значит относительные метки означали дни вокруг него.
    """
    итог: dict[str, Any] = {"raw": dict(период or {}),
                            "resolved_from": "collected_at",
                            "resolved_note": (
                                "даты ВЫЧИСЛЕНЫ из относительных меток периода "
                                "и времени сбора; API их не возвращает")}
    try:
        день = _dt.datetime.strptime(собрано[:10], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        итог["resolved"] = None
        итог["resolved_reason"] = f"время сбора не разобрано: {собрано!r}"
        return итог
    с1, с2 = _сдвиг((период or {}).get("date1")), _сдвиг((период or {}).get("date2"))
    if с1 is None or с2 is None:
        итог["resolved"] = None
        итог["resolved_reason"] = (
            "метки периода не разобраны: "
            f"{(период or {}).get('date1')!r}, {(период or {}).get('date2')!r}")
        return итог
    от, до = день - _dt.timedelta(days=с1), день - _dt.timedelta(days=с2)
    итог["resolved"] = {"from": от.isoformat(), "to": до.isoformat(),
                        "days": (до - от).days + 1}
    return итог


def _покрытие(запись: dict) -> dict:
    изм = [и for и in запись.get("measurements") or [] if и.get("measured")]
    нет = [и for и in запись.get("measurements") or [] if not и.get("measured")]
    return {
        "measured": len(изм),
        "total": len(запись.get("measurements") or []),
        "not_measured": [
            {"key": и.get("key"), "title": и.get("title"),
             "reason": и.get("reason")} for и in нет],
    }


def по_домену(домен: str, *, дата: str = "") -> dict:
    """Собранные показатели ОДНОГО домена из снимка. Только чтение.

    Отсутствие домена в снимке — названная причина, а не пустые значения: это
    разные утверждения, и смешивать их нельзя.
    """
    if дата:
        путь = КАТАЛОГ / f"analytics-{дата}.json"
        if not путь.is_file():
            raise НетСнимка(f"снимка за {дата} нет: {путь}")
        метка = дата
    else:
        метка, путь = последний()
    снимок = json.loads(путь.read_text(encoding="utf-8"))
    собрано = str(снимок.get("collected_at") or "")
    период = разрешить_период(снимок.get("period") or {}, собрано)
    цель = (домен or "").strip().lower()
    запись = next((з for з in снимок.get("domains") or []
                   if str(з.get("domain", "")).lower() == цель), None)
    общее = {
        "source": "yandex_metrika+webmaster via seo-operator analytics-collect",
        "snapshot": {"date": метка, "path": str(путь),
                     "collected_at": собрано,
                     "read_only": bool(снимок.get("read_only"))},
        "period": период,
        "domain": домен,
    }
    if запись is None:
        домены = sorted(str(з.get("domain")) for з in снимок.get("domains") or [])
        return {**общее, "ok": False, "status": "DOMAIN_NOT_IN_SNAPSHOT",
                "reason": (f"домена {домен} нет в снимке за {метка}: собрано "
                           f"{len(домены)} доменов. Это отсутствие записи, а не "
                           "нулевая посещаемость"),
                "domains_in_snapshot": домены}
    покрытие = _покрытие(запись)
    return {**общее, "ok": покрытие["measured"] > 0,
            "status": ("MEASURED" if покрытие["measured"] else "NOTHING_MEASURED"),
            "counter_id": запись.get("counter_id"),
            "webmaster_host_id": запись.get("webmaster_host_id"),
            "coverage": покрытие,
            "measurements": [
                {к: и.get(к) for к in ("key", "title", "source", "value",
                                       "sampled", "sample_share")}
                for и in запись.get("measurements") or [] if и.get("measured")],
            }


def сводка() -> dict:
    """Снимок целиком: покрытие по каждому домену. Для сверки с реестром."""
    метка, путь = последний()
    снимок = json.loads(путь.read_text(encoding="utf-8"))
    собрано = str(снимок.get("collected_at") or "")
    домены = []
    for з in снимок.get("domains") or []:
        п = _покрытие(з)
        домены.append({
            "domain": з.get("domain"), "counter_id": з.get("counter_id"),
            "webmaster_host_id": з.get("webmaster_host_id"),
            "measured": п["measured"], "total": п["total"],
            "not_measured_keys": [н["key"] for н in п["not_measured"]],
        })
    return {
        "source": "yandex_metrika+webmaster via seo-operator analytics-collect",
        "snapshot": {"date": метка, "path": str(путь), "collected_at": собрано,
                     "read_only": bool(снимок.get("read_only"))},
        "period": разрешить_период(снимок.get("period") or {}, собрано),
        "summary": снимок.get("summary") or {},
        "domains": sorted(домены, key=lambda з: str(з["domain"])),
        "snapshots_available": [д for д, _ in снимки()][:14],
    }
