"""Производитель контракта `seo-route-binding` для витрин yummyani.

Отличие от витрин Lords принципиальное и упрощает дело. Там адрес приходилось
вычислять функцией движка и воспроизводить её правило разведения совпадений.
Здесь витрина **сама объявляет**, какой адрес какому произведению принадлежит:
таблица `PublicTitleRoute` хранит слаг, идентификатор произведения у
поставщика и признак каноничности.

Это не догадка и не воспроизведение вычисления — это чтение объявления.
Поэтому у витрин yummyani нет ни коллизий адресов, ни зависимости адреса от
порядка записей источника: обе беды Lords происходят из того, что адрес там
выводится, а не объявляется.

Измерено 2026-09-06: `yummyani.site` — 7 303 маршрута, `yummyani.org` и
`yummyani.biz` — по 7 291. **Все 7 303 идентификатора нашлись в кэше каталога,
которым ядро уже располагает** — то есть отдельный доступ к каталогу витрины
для связи не нужен, и блокер `YUMMYANI-CATALOG-READ` связь не задерживал.

Вложенные адреса — сезона и серии — таблица не хранит, и адаптер их не
выдумывает. Он выдаёт связи страниц произведений, а принадлежность вложенного
адреса произведению определяется отдельно и явно (`resolve_path`): это
структура адресов витрины, а не догадка о ней.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

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

#: Префикс адресов страниц произведений на витринах этой семьи.
TITLE_PREFIX = "/anime/"

#: Типы страниц, которые адаптер умеет различать по форме адреса. Список
#: закрыт: форма, которой здесь нет, типом не считается и уходит с причиной.
PAGE_TYPES: tuple[str, ...] = ("title", "season", "episode")


def route_of(slug: str) -> str:
    """Путь страницы произведения по слагу из таблицы маршрутов."""
    return f"{TITLE_PREFIX}{slug}/"


def page_type_of(path: str) -> tuple[str, str]:
    """Тип страницы и слаг произведения по адресу.

    Возвращает пару «тип, слаг». Пустой тип означает, что адрес не относится
    к странице произведения: это не ошибка, а другой раздел витрины.
    """
    части = [c for c in (path or "").split("/") if c]
    if len(части) < 2 or части[0] != TITLE_PREFIX.strip("/"):
        return "", ""
    слаг = части[1]
    хвост = части[2:]
    if not хвост:
        return "title", слаг
    if хвост[:1] == ["season"] and len(хвост) == 2:
        return "season", слаг
    if хвост[:1] == ["season"] and хвост[2:3] == ["episode"] and len(хвост) == 4:
        return "episode", слаг
    return "", слаг


def _rating_of(entry: dict) -> tuple[RatingState, float | None]:
    """Оценка. Отсутствие числа не превращается в ноль ни на каком шаге."""
    for поле in ("kinopoisk_rating", "imdb_rating"):
        сырое = entry.get(поле)
        if сырое is None:
            continue
        try:
            return RatingState.RATED, float(str(сырое).replace(",", "."))
        except (TypeError, ValueError):
            return RatingState.UNKNOWN, None
    return RatingState.UNRATED, None


def _external_ids(entry: dict) -> dict[str, str]:
    ids = entry.get("external_ids")
    if not isinstance(ids, dict):
        return {}
    return {str(k): str(v) for k, v in ids.items() if str(k) in ID_NAMESPACES}


def bind_route(route: dict, entry: dict | None, *, site_id: str,
               snapshot_at: str, provenance: str) -> RouteBinding:
    """Одна строка таблицы маршрутов как запись контракта."""
    слаг = str(route.get("slug") or "").strip()
    content_id = str(route.get("providerTitleId") or "").strip()
    путь = route_of(слаг)
    причины: list[ReasonCode] = []

    if entry is None:
        # Маршрут есть, произведения в каталоге нет. Это не пустая страница и
        # не ошибка адреса: это расхождение витрины с каталогом, и решать его
        # догадкой нельзя.
        причины.append(ReasonCode.MISSING_CONTENT_ID if not content_id
                       else ReasonCode.KIND_MISSING)
        return RouteBinding(
            site_id=site_id, content_id=content_id, external_ids={},
            route_id=путь, page_type="title", canonical_path=путь,
            content_kind=ContentKind.UNKNOWN,
            content_kind_state=KindState.MISSING,
            content_kind_provenance="произведения нет в каталоге",
            playback_state=PlaybackState.UNKNOWN,
            playback_reason_code=ReasonCode.MISSING_PROVIDER_ID,
            playback_observed_at="", content_revision="",
            binding_state=BindingState.KIND_UNRESOLVED,
            reason_codes=tuple(причины), provenance=provenance,
            snapshot_at=snapshot_at, display_title=слаг)

    решение = decide(provider_type=entry.get("type"),
                     tags=entry.get("tags") or (), entity_id=content_id)
    состояние_вида, вид, происхождение = kind_state_of(решение)
    состояние_видео, код_видео = playback_of(entry)
    оценка, число = _rating_of(entry)

    if not route.get("canonical", True):
        # Неканонический маршрут остаётся маршрутом, но своей страницей не
        # является: показывать по нему собственную страницу значит заводить
        # дубль руками.
        причины.append(ReasonCode.ROUTE_AMBIGUOUS)
        связь = BindingState.ROUTE_COLLISION
    elif состояние_вида is KindState.CONFLICTED:
        причины.append(ReasonCode.KIND_CONFLICTED)
        связь = BindingState.KIND_UNRESOLVED
    elif состояние_вида is KindState.MISSING:
        причины.append(ReasonCode.KIND_MISSING)
        связь = BindingState.KIND_UNRESOLVED
    else:
        причины.append(ReasonCode.OK)
        связь = BindingState.BOUND
    причины.append(код_видео)

    return RouteBinding(
        site_id=site_id, content_id=content_id,
        external_ids=_external_ids(entry), route_id=путь, page_type="title",
        canonical_path=путь, content_kind=вид,
        content_kind_state=состояние_вида,
        content_kind_provenance=происхождение,
        is_animation=решение.is_animation,
        kind_candidates=tuple(dict.fromkeys(
            (решение.provider_kind, *решение.tag_kinds)))
        if состояние_вида is KindState.CONFLICTED else (),
        display_title=str(entry.get("name") or слаг),
        playback_state=состояние_видео, playback_reason_code=код_видео,
        playback_observed_at=(snapshot_at
                              if состояние_видео is PlaybackState.PLAYABLE
                              else ""),
        rating_state=оценка, rating_value=число,
        content_revision=revision_of(entry), binding_state=связь,
        reason_codes=tuple(dict.fromkeys(причины)), provenance=provenance,
        snapshot_at=snapshot_at)


def build(routes: Sequence[dict], catalog: Sequence[dict], *, site_id: str,
          snapshot_at: str, provenance: str) -> list[RouteBinding]:
    """Все маршруты витрины как записи контракта."""
    по_id = {str(x.get("external_id") or ""): x for x in catalog}
    return [bind_route(r, по_id.get(str(r.get("providerTitleId") or "")),
                       site_id=site_id, snapshot_at=snapshot_at,
                       provenance=provenance)
            for r in routes]


def resolve_path(path: str, bindings: dict[str, RouteBinding]
                 ) -> tuple[RouteBinding | None, str]:
    """Связь и тип страницы по адресу очереди.

    Вложенные адреса — сезона и серии — принадлежат тому же произведению, что
    и страница-родитель, и берут её связь. Это структура адресов витрины, а не
    догадка: `/anime/x/season/1/episode/2` не может принадлежать чему-либо,
    кроме `x`, потому что слаг в адресе один и он же ключ таблицы маршрутов.

    Право обещать просмотр наследуется вместе со связью: поток принадлежит
    произведению, а не отдельной странице сезона.
    """
    тип, слаг = page_type_of(path)
    if not тип:
        return None, ""
    return bindings.get(route_of(слаг)), тип


def export(routes_path: str | Path, catalog_path: str | Path, *,
           site_id: str) -> dict[str, Any]:
    """Выгрузка контракта из снимка маршрутов и кэша каталога."""
    снимок = json.loads(Path(routes_path).read_text("utf-8"))
    каталог = json.loads(Path(catalog_path).read_text("utf-8"))
    записи = каталог["items"] if isinstance(каталог, dict) else каталог
    происхождение = f"{снимок.get('source', 'routes')}+{Path(catalog_path).name}"
    связи = build(снимок.get("items") or [], записи, site_id=site_id,
                  snapshot_at=str(снимок.get("fetchedAt") or ""),
                  provenance=происхождение)
    return envelope(связи, site_id=site_id,
                    snapshot_at=str(снимок.get("fetchedAt") or ""),
                    provenance=происхождение)
