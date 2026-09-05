"""Сводка по массиву витрин: что происходит прямо сейчас.

Правило, которому подчинён весь модуль: **счётчик считает или отсутствует.**
Заглушка, всегда показывающая ноль, хуже отсутствия счётчика — она выглядит
как измерение и им не является, и оператор принимает по ней решения.

Отсюда три следствия.

Недоступный источник даёт `null` и отдельную тревогу, а не ноль. «Витрин с
пустым каталогом: 0» при нечитаемом каталоге — ложь, которую невозможно
заметить.

Свежесть считается от времени файла каталога, а не от времени ответа: HTTP 200
с каталогом суточной давности — это отказ, а не здоровье. Именно так витрины
месяцами показывали старый каталог, отвечая 200.

Тревоги выводятся из порогов, а не перечисляются вручную. Список, который
пишут руками, отстаёт от системы на одну правку.
"""

from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
from typing import Any

CONTRACT_VERSION = "admin-overview/1.0.0"

#: Каталог старше этого считается устаревшим. Значение то же, что у порога
#: свежести в content_health: два разных порога на один вопрос расходятся.
FRESHNESS_SLO_SECONDS = 15 * 60
#: Ниже этой доли воспроизведения витрина попадает в тревоги.
PLAYBACK_COVERAGE_FLOOR = 0.90
#: Столько заданий в очереди означает, что исполнитель не справляется.
QUEUE_BACKLOG_ALERT = 25


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _iso(момент: dt.datetime) -> str:
    return момент.strftime("%Y-%m-%dT%H:%M:%SZ")


def _каталог_витрины(root: Path, env: dict[str, str] | None, site_id: str):
    """Файл каталога витрины и его возраст. None — источник недоступен."""
    env = env if env is not None else os.environ
    подкаталог = str(env.get("SITE_ENGINE_CATALOG_DIR", "")).strip()
    if not подкаталог:
        return None, None
    # Путь может быть абсолютным: каталог поставщика законно живёт
    # вне репозитория, и приклеивать к нему корень значило бы
    # искать var/... внутри /srv/....
    основа = Path(подкаталог)
    if not основа.is_absolute():
        основа = Path(root) / основа
    путь = основа / f"{site_id}.json"
    if not путь.is_file():
        return None, None
    try:
        данные = json.loads(путь.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, None
    возраст = max(0, int(_now().timestamp() - путь.stat().st_mtime))
    return данные, возраст


def _профили(root: Path) -> list[str]:
    каталог = Path(root) / "config" / "site-profiles"
    if not каталог.is_dir():
        return []
    return sorted(п.stem for п in каталог.glob("*.json"))


def сводка_витрины(root: Path, site_id: str, *, env=None) -> dict[str, Any]:
    """Показатели одной витрины. Недоступный источник — null, а не ноль."""
    данные, возраст = _каталог_витрины(root, env, site_id)
    итог: dict[str, Any] = {
        "siteId": site_id,
        "titles": None,
        "playable": None,
        "playbackCoverage": None,
        "withoutIdentifier": None,
        "blockedByContract": None,
        "ratingNumeric": None,
        "freshnessSeconds": возраст,
        "freshnessState": "UNKNOWN",
        "source": None,
    }
    if данные is None:
        return итог

    записи = [i for i in (данные.get("items") or []) if isinstance(i, dict)]
    itог_playable = 0
    без_идентификатора = 0
    запрещено = 0
    с_числом = 0
    for запись in записи:
        pb = запись.get("playback")
        if isinstance(pb, dict) and pb.get("aggregator") and pb.get("title_id"):
            itог_playable += 1
        elif запись.get("playback_blocked_reason"):
            запрещено += 1
        elif not (запись.get("external_ids") or {}):
            без_идентификатора += 1
        if запись.get("kinopoisk_rating") is not None or запись.get("imdb_rating") is not None:
            с_числом += 1

    итог.update(
        {
            "titles": len(записи),
            "playable": itог_playable,
            "playbackCoverage": (itог_playable / len(записи)) if записи else 0.0,
            "withoutIdentifier": без_идентификатора,
            "blockedByContract": запрещено,
            "ratingNumeric": с_числом,
            "source": данные.get("source"),
            "freshnessState": (
                "FRESH" if возраст is not None and возраст <= FRESHNESS_SLO_SECONDS else "STALE"
            ),
        }
    )
    return итог


def _тревоги(
    витрины: list[dict], очередь: dict | None, конфликты: int | None
) -> list[dict[str, Any]]:
    """Тревоги выводятся из порогов. Список руками отстаёт на одну правку."""
    итог: list[dict[str, Any]] = []
    for в in витрины:
        if в["titles"] is None:
            итог.append(
                {
                    "code": "CATALOG_UNREADABLE",
                    "severity": "high",
                    "subject": в["siteId"],
                    "detail": "источник каталога недоступен: показатели "
                    "витрины не измерены, а не равны нулю",
                }
            )
            continue
        if в["titles"] == 0:
            итог.append(
                {
                    "code": "EMPTY_CATALOG",
                    "severity": "critical",
                    "subject": в["siteId"],
                    "detail": "каталог пуст: витрина отвечает, но показывать " "ей нечего",
                }
            )
            continue
        if в["freshnessState"] == "STALE":
            итог.append(
                {
                    "code": "STALE_CATALOG",
                    "severity": "high",
                    "subject": в["siteId"],
                    "detail": f"каталог не обновлялся {в['freshnessSeconds']} с "
                    f"при пороге {FRESHNESS_SLO_SECONDS} с",
                }
            )
        if (в["playbackCoverage"] or 0) < PLAYBACK_COVERAGE_FLOOR:
            итог.append(
                {
                    "code": "LOW_PLAYBACK_COVERAGE",
                    "severity": "medium",
                    "subject": в["siteId"],
                    "detail": f"воспроизведение у {в['playbackCoverage']:.1%} "
                    f"карточек при пороге "
                    f"{PLAYBACK_COVERAGE_FLOOR:.0%}",
                }
            )
    if очередь is None:
        итог.append(
            {
                "code": "QUEUE_UNREADABLE",
                "severity": "medium",
                "subject": "queue",
                "detail": "очередь недоступна",
            }
        )
    elif очередь.get("inbox", 0) >= QUEUE_BACKLOG_ALERT:
        итог.append(
            {
                "code": "QUEUE_BACKLOG",
                "severity": "medium",
                "subject": "queue",
                "detail": f"в очереди {очередь['inbox']} заданий при пороге "
                f"{QUEUE_BACKLOG_ALERT}",
            }
        )
    if конфликты:
        итог.append(
            {
                "code": "IDENTITY_CONFLICTS",
                "severity": "low",
                "subject": "review-queue",
                "detail": f"{конфликты} записей ждут разбора",
            }
        )
    return итог


def сводка(root: Path, *, env=None) -> dict[str, Any]:
    """Сводка по всем витринам плюс очередь, разбор и тревоги."""
    корень = Path(root)
    витрины = [сводка_витрины(корень, s, env=env) for s in _профили(корень)]

    очередь: dict | None
    try:
        from factory import queue as queue_mod

        очередь = queue_mod.counts()
    except Exception:  # noqa: BLE001
        очередь = None

    конфликты: int | None
    try:
        from factory.site_engine.review_queue import ReviewQueue

        свод = ReviewQueue(корень).list(limit=1)
        конфликты = свод["byState"].get("OPEN", 0) + свод["byState"].get("IN_REVIEW", 0)
    except Exception:  # noqa: BLE001
        конфликты = None

    итоги = {
        "titles": sum(в["titles"] or 0 for в in витрины),
        "playable": sum(в["playable"] or 0 for в in витрины),
        "sitesMeasured": sum(1 for в in витрины if в["titles"] is not None),
        "sitesTotal": len(витрины),
    }
    итоги["playbackCoverage"] = итоги["playable"] / итоги["titles"] if итоги["titles"] else None

    return {
        "generatedAt": _iso(_now()),
        "contractVersion": CONTRACT_VERSION,
        "totals": итоги,
        "sites": витрины,
        "queue": очередь,
        "identityConflicts": конфликты,
        "alerts": _тревоги(витрины, очередь, конфликты),
        "thresholds": {
            "freshnessSeconds": FRESHNESS_SLO_SECONDS,
            "playbackCoverage": PLAYBACK_COVERAGE_FLOOR,
            "queueBacklog": QUEUE_BACKLOG_ALERT,
        },
    }
