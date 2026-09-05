"""Просмотр каталога: поиск, отбор и карточка.

Отбор выполняется на сервере. Фильтр, применённый в браузере поверх первой
страницы, отвечает на вопрос «что нашлось среди двадцати пяти», а оператор
задаёт вопрос «что есть во всём каталоге» — и по ответу на первый принимает
решения, думая, что получил ответ на второй.

Порядок устойчивый: по внешнему идентификатору. Сортировка по времени
обновления соблазнительна, но тогда страница меняется под руками при каждом
фоновом обновлении каталога, и оператор дважды видит одну запись и пропускает
другую.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

CONTRACT_VERSION = "admin-content/1.0.0"

MAX_LIMIT = 200
DEFAULT_LIMIT = 25

#: Поля, по которым разрешена сортировка. Закрытый перечень: имя поля приходит
#: из адресной строки, и подставлять его в доступ к данным как есть нельзя.
SORTABLE = {"externalId": "external_id", "title": "name", "year": "year"}


class ContentError(RuntimeError):
    """Запрос к каталогу невыполним."""


def _каталог(root: Path, env, site_id: str) -> list[dict]:
    env = env if env is not None else os.environ
    подкаталог = str(env.get("SITE_ENGINE_CATALOG_DIR", "")).strip()
    if not подкаталог:
        raise ContentError("источник каталога не настроен")
    if not site_id or "/" in site_id or ".." in site_id:
        raise ContentError(f"негодная витрина {site_id!r}")
    # Путь может быть абсолютным: каталог поставщика законно живёт
    # вне репозитория, и приклеивать к нему корень значило бы
    # искать var/... внутри /srv/....
    основа = Path(подкаталог)
    if not основа.is_absolute():
        основа = Path(root) / основа
    путь = основа / f"{site_id}.json"
    if not путь.is_file():
        raise ContentError(f"каталога витрины {site_id} нет")
    try:
        данные = json.loads(путь.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as ошибка:
        raise ContentError(f"каталог витрины {site_id} не читается") from ошибка
    return [i for i in (данные.get("items") or []) if isinstance(i, dict)]


def _вид(запись: dict) -> str:
    from factory.site_engine import catalog_identity

    решение = catalog_identity.decide(
        provider_type=запись.get("type"), tags=запись.get("tags") or ()
    )
    return решение.kind.value


def _причина(запись: dict) -> str:
    from factory.site_engine.api import reasons

    if запись.get("playback_blocked_reason"):
        return str(запись["playback_blocked_reason"])
    return reasons.classify_descriptor(запись.get("external_ids"), запись.get("playback"))


def _состояние_рейтинга(запись: dict) -> str:
    if запись.get("kinopoisk_rating") is not None or запись.get("imdb_rating") is not None:
        return "AVAILABLE"
    # Отсутствие числа — не ноль и не «нет оценок»: разрешённого источника
    # может не быть вовсе, и это разные вещи.
    return "SOURCE_UNAVAILABLE"


def строка(запись: dict, site_id: str) -> dict[str, Any]:
    pb = запись.get("playback") if isinstance(запись.get("playback"), dict) else None
    return {
        "siteId": site_id,
        "externalId": запись.get("external_id"),
        "title": запись.get("name"),
        "year": запись.get("year"),
        "contentKind": _вид(запись),
        "playbackAggregator": (pb or {}).get("aggregator"),
        "playbackReason": _причина(запись),
        "ratingState": _состояние_рейтинга(запись),
        "externalIds": {k: str(v) for k, v in (запись.get("external_ids") or {}).items() if v},
    }


def список(
    root: Path,
    *,
    site_id: str,
    env=None,
    q: str = "",
    kind: str = "",
    reason: str = "",
    sort: str = "externalId",
    desc: bool = False,
    offset: int = 0,
    limit: int = DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Страница каталога с отбором на сервере."""
    if not isinstance(limit, int) or not (1 <= limit <= MAX_LIMIT):
        raise ContentError(f"limit — целое от 1 до {MAX_LIMIT}")
    if not isinstance(offset, int) or offset < 0:
        raise ContentError("offset — неотрицательное целое")
    if sort not in SORTABLE:
        raise ContentError(f"сортировка {sort!r} не разрешена; " f"допустимы {sorted(SORTABLE)}")

    записи = _каталог(Path(root), env, site_id)
    строки = [строка(з, site_id) for з in записи]

    искомое = (q or "").strip().lower()
    отобрано = [
        s
        for s in строки
        if (
            not искомое
            or искомое in str(s["title"] or "").lower()
            or искомое in str(s["externalId"] or "").lower()
        )
        and (not kind or s["contentKind"] == kind)
        and (not reason or s["playbackReason"] == reason)
    ]

    ключ = SORTABLE[sort]
    поле = {"external_id": "externalId", "name": "title", "year": "year"}[ключ]
    # Второй ключ — внешний идентификатор: он уникален, и без него записи с
    # одинаковым названием переставляются между запросами.
    отобрано.sort(
        key=lambda s: ((s[поле] is None), s[поле] or "", s["externalId"] or ""), reverse=desc
    )

    по_видам: dict[str, int] = {}
    по_причинам: dict[str, int] = {}
    for s in строки:
        по_видам[s["contentKind"]] = по_видам.get(s["contentKind"], 0) + 1
        по_причинам[s["playbackReason"]] = по_причинам.get(s["playbackReason"], 0) + 1

    return {
        "siteId": site_id,
        "total": len(отобрано),
        "totalAll": len(строки),
        "offset": offset,
        "limit": limit,
        "sort": sort,
        "desc": desc,
        "query": q,
        "kind": kind,
        "reason": reason,
        "byKind": по_видам,
        "byReason": по_причинам,
        "items": отобрано[offset : offset + limit],
        "contractVersion": CONTRACT_VERSION,
    }


def карточка(root: Path, *, site_id: str, external_id: str, env=None) -> dict[str, Any]:
    """Полная карточка: идентификаторы, происхождение, состояния, история."""
    if not external_id or "/" in external_id or ".." in external_id:
        raise ContentError("негодный идентификатор записи")
    записи = _каталог(Path(root), env, site_id)
    запись = next((з for з in записи if з.get("external_id") == external_id), None)
    if запись is None:
        raise ContentError(f"записи {external_id} нет в каталоге витрины {site_id}")

    from factory.site_engine import catalog_identity

    решение = catalog_identity.decide(
        provider_type=запись.get("type"), tags=запись.get("tags") or ()
    )
    основа = строка(запись, site_id)

    # История берётся из того, что источник действительно сообщает. Выдумывать
    # события нельзя: витрина не хранит журнала изменений записи.
    история = [
        {"at": запись.get("created_at"), "event": "появилась у поставщика"},
        {"at": запись.get("updated_at"), "event": "обновлена у поставщика"},
    ]
    решение_очереди = None
    try:
        from factory.site_engine.review_queue import ReviewQueue, item_id_for

        элемент = ReviewQueue(Path(root)).get(
            item_id_for(f"{site_id}:{external_id}", "contentKind")
        )
        решение_очереди = {
            "state": элемент.state.value,
            "decidedValue": элемент.decided_value,
            "decidedBy": элемент.decided_by,
            "itemId": элемент.item_id,
        }
        for h in элемент.history:
            история.append(
                {
                    "at": h.get("at"),
                    "event": f"разбор: {h.get('action')} {h.get('value', '')}",
                    "actor": h.get("actor"),
                }
            )
    except Exception:  # noqa: BLE001
        решение_очереди = None

    return {
        **основа,
        "providerType": запись.get("type"),
        "tags": list(запись.get("tags") or []),
        "isAnimation": решение.is_animation,
        "kindConflicts": list(решение.conflicts),
        "kindReason": решение.reason,
        "sourceRefs": [
            {
                "source": "cdnvideohub-catalog-cache",
                "sourceEntityId": external_id,
                "updatedAt": запись.get("updated_at"),
            }
        ],
        "ratings": {"kinopoisk": запись.get("kinopoisk_rating"), "imdb": запись.get("imdb_rating")},
        "seasons": запись.get("seasons_count"),
        "episodes": запись.get("episodes_count"),
        # Длительность источник не отдаёт. None, а не ноль: ноль ушёл бы в
        # разметку как PT0M, то есть утверждением «идёт нисколько».
        "duration": запись.get("duration"),
        "seoState": ("READY" if основа["playbackReason"] == "OK" else "NO_PLAYBACK"),
        "review": решение_очереди,
        "timeline": [с for с in история if с.get("at")],
        "contractVersion": CONTRACT_VERSION,
    }
