"""Производитель контракта `seo-route-binding` для витрин Lords.

Адаптер знает две вещи, которых ядру знать не положено: как витрина Lords
строит адрес страницы и где лежит её кэш каталога. Само ядро
(`site_engine.seo_binding`) описывает форму контракта и его обещания и о
Lords не знает ничего — поэтому вторая семья витрин добавляется вторым
адаптером, а не правкой ядра.

**Маршрут не пересчитывается заново.** Адаптер вызывает
`factory.lords.live_catalog.slugify` — ту самую функцию, которой витрина
строит свои адреса, — и воспроизводит её же правило разведения совпадений:
второму и последующим совпадениям слага приписывается номер, в порядке
ответа источника. Без воспроизведения этого правила на боевом снимке
совпадало 139 адресов очереди SEO из 155; с ним — 155 из 155.

Правило имеет следствие, ради которого контракт и разделяет идентичность с
адресом: **адрес зависит от порядка записей**. Номерной адрес получают 5 603
записи из 53 232. Перестановка двух записей с одинаковым названием молча
меняет их адреса местами, и связь, построенная на адресе, порвалась бы
незаметно. Связь построена на `contentId`.
"""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from factory.lords.live_catalog import slugify
from factory.site_engine.catalog_identity import decide
from factory.site_engine.seo_binding import (
    ID_NAMESPACES,
    BindingState,
    ContentKind,
    KindState,
    PlaybackState,
    RatingState,
    ReasonCode,
    RouteBinding,
    envelope,
    kind_state_of,
    playback_of,
    revision_of,
)

#: Тип страницы, который производит этот адаптер. Список закрыт: раздел и
#: карточка эпизода адресуются иначе, и их выпуск — отдельная правка.
PAGE_TYPE = "title"


def route_of(name: str, external_id: str) -> str:
    """Базовый путь страницы. Ровно то, что вычисляет витрина."""
    slug = slugify(name) or slugify(external_id) or external_id.lower()
    return f"/title/{slug}/"


def _numbered(base: str, index: int) -> str:
    """Путь с номером, как его строит витрина при совпадении слагов."""
    if index == 0:
        return base
    return f"{base.rstrip('/')}-{index + 1}/"


def _rating_of(entry: dict) -> tuple[RatingState, float | None]:
    """Оценка. Отсутствие числа не превращается в ноль ни на каком шаге."""
    for поле in ("kinopoisk_rating", "imdb_rating"):
        сырое = entry.get(поле)
        if сырое is None:
            continue
        try:
            число = float(str(сырое).replace(",", "."))
        except (TypeError, ValueError):
            # Значение есть, но числом не является: это неизвестность, а не
            # ноль и не отсутствие оценки.
            return RatingState.UNKNOWN, None
        return RatingState.RATED, число
    return RatingState.UNRATED, None


def _external_ids(entry: dict) -> dict[str, str]:
    """Внешние идентификаторы, оставленные только из объявленных пространств.

    Идентификатор из неизвестного пространства не отбрасывается молча: он не
    попадает в контракт, и это видно по тому, что его там нет, а причина
    названа в `reason_codes` вызывающим. Принимать неизвестное пространство
    здесь значило бы дать ему права, которых ему никто не давал.
    """
    ids = entry.get("external_ids")
    if not isinstance(ids, dict):
        return {}
    return {str(k): str(v) for k, v in ids.items() if str(k) in ID_NAMESPACES}


def bind_entry(entry: dict, *, site_id: str, route: str,
               ambiguous: bool, snapshot_at: str,
               provenance: str) -> RouteBinding:
    """Одна запись каталога как запись контракта."""
    external_id = str(entry.get("external_id") or "").strip()
    name = str(entry.get("name") or "").strip()
    причины: list[ReasonCode] = []

    if not external_id or not name:
        причины.append(ReasonCode.MISSING_CONTENT_ID if not external_id
                       else ReasonCode.MISSING_TITLE)
        return RouteBinding(
            site_id=site_id, content_id=external_id, external_ids={},
            route_id="", page_type=PAGE_TYPE, canonical_path="",
            content_kind=ContentKind.UNKNOWN,
            content_kind_state=KindState.MISSING,
            content_kind_provenance="запись не адресуема",
            playback_state=PlaybackState.UNKNOWN,
            playback_reason_code=ReasonCode.MISSING_PROVIDER_ID,
            playback_observed_at="", content_revision=revision_of(entry),
            binding_state=BindingState.NOT_ADDRESSABLE,
            reason_codes=tuple(причины), provenance=provenance,
            snapshot_at=snapshot_at, display_title=name)

    решение = decide(provider_type=entry.get("type"), tags=entry.get("tags") or (),
                     entity_id=external_id)
    состояние_вида, вид, происхождение = kind_state_of(решение)
    состояние_видео, код_видео = playback_of(entry)
    оценка, число = _rating_of(entry)

    if ambiguous:
        причины.append(ReasonCode.ROUTE_AMBIGUOUS)
        связь = BindingState.ROUTE_COLLISION
    elif состояние_вида is KindState.CONFLICTED:
        причины.append(ReasonCode.KIND_CONFLICTED)
        связь = BindingState.KIND_UNRESOLVED
    elif состояние_вида is KindState.MISSING:
        причины.append(ReasonCode.KIND_MISSING)
        связь = BindingState.KIND_UNRESOLVED
    else:
        связь = BindingState.BOUND
        причины.append(ReasonCode.OK)
    причины.append(код_видео)

    return RouteBinding(
        site_id=site_id, content_id=external_id,
        external_ids=_external_ids(entry),
        route_id=route, page_type=PAGE_TYPE, canonical_path=route,
        content_kind=вид, content_kind_state=состояние_вида,
        content_kind_provenance=происхождение,
        is_animation=решение.is_animation,
        display_title=name,
        playback_state=состояние_видео, playback_reason_code=код_видео,
        playback_observed_at=snapshot_at if состояние_видео is PlaybackState.PLAYABLE else "",
        rating_state=оценка, rating_value=число,
        content_revision=revision_of(entry), binding_state=связь,
        reason_codes=tuple(dict.fromkeys(причины)), provenance=provenance,
        snapshot_at=snapshot_at)


def build(entries: Sequence[dict], *, site_id: str, snapshot_at: str,
          provenance: str) -> list[RouteBinding]:
    """Все записи каталога как записи контракта.

    Проход двойной, и это не расточительность: пока не пройден весь каталог,
    неизвестно, окажется ли адрес неоднозначным. Решать по ходу значило бы
    объявить первую запись однозначной, а вторую — коллизией, хотя
    неоднозначны обе.
    """
    маршруты: list[tuple[dict, str]] = []
    видели: dict[str, int] = {}
    for entry in entries:
        external_id = str(entry.get("external_id") or "").strip()
        name = str(entry.get("name") or "").strip()
        if not external_id or not name:
            маршруты.append((entry, ""))
            continue
        база = route_of(name, external_id)
        сколько = видели.get(база, 0)
        видели[база] = сколько + 1
        маршруты.append((entry, _numbered(база, сколько)))

    занято: dict[str, int] = {}
    for _, путь in маршруты:
        if путь:
            занято[путь] = занято.get(путь, 0) + 1

    return [bind_entry(entry, site_id=site_id, route=путь,
                       ambiguous=занято.get(путь, 0) > 1,
                       snapshot_at=snapshot_at, provenance=provenance)
            for entry, путь in маршруты]


def export(catalog_path: str | Path, *, site_id: str) -> dict[str, Any]:
    """Выгрузка контракта из кэша каталога витрины.

    Повторный вызов на неизменившемся кэше обязан дать тот же отпечаток: в
    него входит содержимое записей и не входит момент выгрузки.
    """
    путь = Path(catalog_path)
    сырьё = json.loads(путь.read_text("utf-8"))
    записи = сырьё["items"] if isinstance(сырьё, dict) else сырьё
    снят = (dt.datetime.fromtimestamp(сырьё["fetched_at_ms"] / 1000, dt.timezone.utc)
            .isoformat() if isinstance(сырьё, dict) and сырьё.get("fetched_at_ms")
            else "")
    связи = build(записи, site_id=site_id, snapshot_at=снят,
                  provenance=f"catalog-cache:{путь.name}")
    return envelope(связи, site_id=site_id, snapshot_at=снят,
                    provenance=f"catalog-cache:{путь.name}")
