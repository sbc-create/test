"""Состояние воспроизведения каталога: покрытие, причины, проблемные карточки.

Отвечает на вопрос, который до сих пор задавали глазами: сколько карточек
обещают просмотр и сколько его действительно дают, а по каждой недостающей —
на каком звене потеряно видео и что с этим делать.

Считается по тем же данным, из которых строятся страницы: кэш каталога и
результаты проб воспроизводимости. Отдельного «своего» представления здесь нет
намеренно — иначе админка показывала бы не то, что видит зритель.
"""
from __future__ import annotations

import json
import os
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from factory.site_engine.api import reasons

# Поддерживаемые агрегаторы берутся из контракта, а не дублируются здесь:
# расхождение между тем, что мы шлём, и тем, что считаем, — источник неверной
# статистики, которую никто не перепроверяет.
DEFAULT_SUPPORTED = ("kp", "mali", "mdl", "imdb")

# Свежесть проекции: обещание витрины. Больше — карточка считается устаревшей.
FRESHNESS_SLO_SECONDS = 15 * 60


# Расположение кэша каталога и файла проб — настройка развёртывания, а не
# знание ядра. Ядро обслуживает разные семейства витрин, и зашитый в него путь
# одного семейства делал бы его неуниверсальным: различия сайтов живут в
# профилях и адаптерах.
ENV_CATALOG_DIR = "SITE_ENGINE_CATALOG_DIR"
ENV_PROBE_FILE = "SITE_ENGINE_PLAYABILITY_FILE"


@dataclass
class Источники:
    catalog_dir: Path | None
    probe_file: Path | None = None

    @property
    def configured(self) -> bool:
        return self.catalog_dir is not None

    @classmethod
    def from_env(cls, root: Path | str, env: dict[str, str] | None = None) -> Источники:
        """Источники из настроек. Без настройки — честное «не задано».

        Догадка о пути хуже отказа: она даёт правдоподобную пустую сводку,
        которую примут за отсутствие проблем.
        """
        env = env if env is not None else dict(os.environ)
        каталог = str(env.get(ENV_CATALOG_DIR, "")).strip()
        пробы = str(env.get(ENV_PROBE_FILE, "")).strip()
        if not каталог:
            return cls(catalog_dir=None, probe_file=None)
        основа = Path(root)
        путь = Path(каталог)
        if not путь.is_absolute():
            путь = основа / путь
        файл = None
        if пробы:
            файл = Path(пробы)
            if not файл.is_absolute():
                файл = основа / файл
        return cls(catalog_dir=путь, probe_file=файл)


def _загрузить_пробы(path: Path | None) -> dict[str, Any]:
    if not path or not path.is_file():
        return {}
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return d if isinstance(d, dict) else {}


def _возраст(отметка: str | None, сейчас: float) -> float | None:
    if not отметка:
        return None
    try:
        t = time.strptime(отметка[:19], "%Y-%m-%dT%H:%M:%S")
    except (ValueError, TypeError):
        return None
    return max(0.0, сейчас - time.mktime(t) + time.timezone)


def оценить(item: dict, пробы: dict, *, supported=DEFAULT_SUPPORTED) -> str:
    """Код причины для одной карточки."""
    pb = item.get("playback") if isinstance(item.get("playback"), dict) else None
    исход = None
    if pb and pb.get("aggregator") and pb.get("title_id"):
        запись = пробы.get(f"{pb['aggregator']}:{pb['title_id']}")
        if isinstance(запись, dict):
            исход = "EMPTY" if запись.get("playable") is False else None
    return reasons.classify_descriptor(item.get("external_ids"), pb,
                                       supported=tuple(supported), probe=исход)


def сводка(root: Path | str, *, site: str | None = None,
           supported=DEFAULT_SUPPORTED, now: float | None = None,
           env: dict[str, str] | None = None,
           sources: Источники | None = None) -> dict[str, Any]:
    """Покрытие и разбивка по причинам для одной витрины или всех."""
    сейчас = now if now is not None else time.time()
    ист = sources if sources is not None else Источники.from_env(root, env)
    пробы = _загрузить_пробы(ист.probe_file)
    результат: dict[str, Any] = {"generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                              time.gmtime(сейчас)),
                                 "reasonVersion": reasons.VERSION,
                                 "freshnessSloSeconds": FRESHNESS_SLO_SECONDS,
                                 "sites": {}}
    if not ист.configured:
        результат["problem"] = f"источник каталога не задан: укажите {ENV_CATALOG_DIR}"
        return результат
    if not ист.catalog_dir.is_dir():
        результат["problem"] = "каталог не найден по заданному пути"
        return результат

    файлы = sorted(ист.catalog_dir.glob("*.json"))
    if site:
        файлы = [p for p in файлы if p.stem == site]
    for path in файлы:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            результат["sites"][path.stem] = {"problem": "кэш каталога не прочитан"}
            continue
        items = data.get("items") or []
        всего = len(items)
        причины = Counter()
        по_типу = defaultdict(Counter)
        по_агрегатору = Counter()
        по_месяцу = defaultdict(Counter)
        for t in items:
            код = оценить(t, пробы, supported=supported)
            причины[код] += 1
            тип = "series" if t.get("is_series") else ("movie" if t.get("is_series") is False
                                                       else "unknown")
            по_типу[тип][код] += 1
            pb = t.get("playback") or {}
            по_агрегатору[pb.get("aggregator") or "none"] += 1
            по_месяцу[(t.get("created_at") or "")[:7] or "unknown"][код] += 1
        играбельных = причины.get("OK", 0)
        # Устаревание проекции не отменяет наличие дескрипторов, но обязано
        # быть видно как отдельный сигнал: карточки могут «играть» по старым
        # данным, а новых поступлений при этом не появляться вовсе.
        # Возраст берётся из поля, если оно есть, иначе из времени изменения
        # файла. Второе надёжнее: поле может отсутствовать или отстать, а файл
        # переписывается каждой переработкой. Именно так и обнаружилось, что
        # каталог не обновлялся сутки, пока таймер числился активным.
        возраст = _возраст(data.get("updated_at") or data.get("generated_at"), сейчас)
        if возраст is None:
            try:
                возраст = max(0.0, сейчас - path.stat().st_mtime)
            except OSError:
                возраст = None
        если_устарело = (возраст is not None and возраст > FRESHNESS_SLO_SECONDS)
        результат["sites"][path.stem] = {
            "total": всего,
            "playable": играбельных,
            "coverage": round(играбельных / всего, 6) if всего else None,
            "missing": всего - играбельных,
            "reasons": dict(причины),
            "byType": {k: dict(v) for k, v in по_типу.items()},
            "byAggregator": dict(по_агрегатору),
            "recentMonths": {k: dict(v) for k, v in
                             sorted(по_месяцу.items(), reverse=True)[:6]},
            "projectionAgeSeconds": round(возраст) if возраст is not None else None,
            "projectionStale": если_устарело,
            "cacheFileMtime": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                            time.gmtime(path.stat().st_mtime)),
        }
    итог = Counter()
    всего_всех = играбельных_всех = 0
    for s in результат["sites"].values():
        if "problem" in s:
            continue
        итог.update(s["reasons"])
        всего_всех += s["total"]
        играбельных_всех += s["playable"]
    результат["fleet"] = {
        "total": всего_всех, "playable": играбельных_всех,
        "coverage": round(играбельных_всех / всего_всех, 6) if всего_всех else None,
        "missing": всего_всех - играбельных_всех,
        "reasons": dict(итог),
    }
    return результат


def проблемные(root: Path | str, site: str, *, code: str | None = None,
               limit: int = 50, supported=DEFAULT_SUPPORTED,
               env: dict[str, str] | None = None,
               sources: Источники | None = None) -> dict[str, Any]:
    """Карточки без воспроизведения с указанием звена и способа устранения."""
    ист = sources if sources is not None else Источники.from_env(root, env)
    пробы = _загрузить_пробы(ист.probe_file)
    if not ист.configured:
        return {"problem": f"источник каталога не задан: укажите {ENV_CATALOG_DIR}",
                "site": site}
    path = ист.catalog_dir / f"{site}.json"
    if not path.is_file():
        return {"problem": "витрина не найдена", "site": site}
    data = json.loads(path.read_text(encoding="utf-8"))
    строки = []
    for t in data.get("items") or []:
        код = оценить(t, пробы, supported=supported)
        if код == "OK":
            continue
        if code and код != code.upper():
            continue
        r = reasons.get(код)
        строки.append({
            "externalId": t.get("external_id"),
            "name": t.get("name"),
            "year": t.get("year"),
            "type": "series" if t.get("is_series") else "movie",
            "externalIds": t.get("external_ids") or {},
            "playback": t.get("playback"),
            "createdAt": t.get("created_at"),
            "updatedAt": t.get("updated_at"),
            "reason": код,
            "stage": r.stage,
            "terminal": r.terminal,
            "public": r.public,
            "operator": r.operator,
            "remediation": r.remediation,
            "automatic": r.automatic,
        })
        if len(строки) >= limit:
            break
    return {"site": site, "filter": code, "total": len(строки), "items": строки,
            "reasonVersion": reasons.VERSION}
