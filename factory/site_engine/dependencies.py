"""Карта зависимостей: событие → затронутые ресурсы.

Смысл в отрицании. Выход одной серии меняет страницу тайтла, полку новых серий
и одну-две страницы листинга — а не шестьдесят одну тысячу страниц. Пока такой
карты нет, единственный честный ответ на вопрос «что перестраивать» — «всё», и
цикл стоит семь часов.

Правило, которое здесь труднее всего соблюсти: **не обновлять ресурс, если
событие на него не влияет**. Соблазн добавить лишнее велик — «на всякий
случай», — и каждое такое добавление возвращает нас к полной пересборке
маленькими шагами.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from factory.site_engine.contracts import ContentEvent, EventType

#: Сколько страниц листинга может задеть одна запись. Карточка попадает на свою
#: страницу каталога и, если сортировка по свежести, на первую. Больше двух не
#: бывает: перестановка внутри списка не меняет остальных страниц.
LISTING_PAGES_PER_TITLE = 2


@dataclass(frozen=True)
class Resource:
    """Один затронутый ресурс и причина, по которой он затронут."""

    kind: str
    path: str
    reason: str

    def __str__(self) -> str:
        return f"{self.kind}:{self.path}"


@dataclass
class Plan:
    """Что именно будет сделано. Считается до работы, а не по её следам."""

    event_id: str
    event_type: str
    canonical_title_id: str
    site_ids: tuple[str, ...]
    resources: tuple[Resource, ...] = ()
    cache_tags: tuple[str, ...] = ()

    @property
    def page_count(self) -> int:
        return sum(1 for r in self.resources if r.kind == "page")

    def as_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "canonical_title_id": self.canonical_title_id,
            "sites": list(self.site_ids),
            "pages": self.page_count,
            "resources": [
                {"kind": r.kind, "path": r.path, "reason": r.reason} for r in self.resources
            ],
            "cache_tags": list(self.cache_tags),
        }


@dataclass(frozen=True)
class SiteContext:
    """Что нужно знать о сайте, чтобы посчитать план.

    Передаётся снаружи: карта зависимостей не ходит ни в каталог, ни в файловую
    систему. Модуль, который сам добывает себе данные, невозможно проверить.
    """

    site_id: str
    title_path: str
    listing_paths: tuple[str, ...] = ()
    has_schedule: bool = False
    has_announcements: bool = False
    has_news_shelf: bool = True
    sitemap_shard: str = "sitemap-1.xml"
    seasons: tuple[int, ...] = ()


def _title_resources(ctx: SiteContext, reason: str) -> list[Resource]:
    return [Resource("page", f"/title/{ctx.title_path}/", reason)]


def plan_for(
    event: ContentEvent,
    contexts: Iterable[SiteContext],
) -> Plan:
    """План обновления для одного события.

    Каждый ресурс сопровождается причиной. Причина — не украшение: по ней видно,
    почему ресурс попал в план, и заметно, если он попал зря.
    """
    contexts = list(contexts)
    ресурсы: list[Resource] = []
    kind = event.event_type

    for ctx in contexts:
        if kind in (
            EventType.EPISODE_ADDED,
            EventType.SEASON_ADDED,
            EventType.TITLE_UPDATED,
            EventType.VOICEOVER_ADDED,
            EventType.RATING_UPDATED,
            EventType.PLAYBACK_AVAILABLE,
            EventType.PLAYBACK_UNAVAILABLE,
        ):
            ресурсы += _title_resources(ctx, f"карточка тайтла меняется при {kind.value}")

        if kind is EventType.TITLE_CREATED:
            ресурсы += _title_resources(ctx, "карточка появляется впервые")
            ресурсы.append(
                Resource("page", "/", "новый тайтл попадает на полку новинок")
            )
            for path in ctx.listing_paths[:LISTING_PAGES_PER_TITLE]:
                ресурсы.append(Resource("page", path, "карточка добавляется в листинг"))
            ресурсы.append(
                Resource("sitemap", f"/{ctx.sitemap_shard}", "появился новый адрес")
            )

        if kind is EventType.EPISODE_ADDED:
            if ctx.has_news_shelf:
                ресурсы.append(
                    Resource("page", "/", "полка новых серий показывает прибавку")
                )
            for path in ctx.listing_paths[:LISTING_PAGES_PER_TITLE]:
                ресурсы.append(
                    Resource("page", path, "карточка поднимается в списке обновлений")
                )
            сезон = event.payload.get("season")
            if сезон is not None and сезон in ctx.seasons:
                ресурсы.append(
                    Resource("page", f"/title/{ctx.title_path}/season-{сезон}/",
                             "страница сезона показывает новую серию")
                )

        if kind is EventType.SEASON_ADDED:
            сезон = event.payload.get("season")
            if сезон is not None:
                ресурсы.append(
                    Resource("page", f"/title/{ctx.title_path}/season-{сезон}/",
                             "появилась страница сезона")
                )
            ресурсы.append(
                Resource("sitemap", f"/{ctx.sitemap_shard}", "появился новый адрес")
            )

        if kind is EventType.RATING_UPDATED:
            ресурсы.append(
                Resource("data", f"ratings/{event.canonical_title_id}",
                         "оценка хранится отдельно от карточки")
            )

        # Расписание и анонсы обновляются только там, где включены: сайт без
        # них не должен получать в план несуществующую страницу.
        if kind is EventType.SCHEDULE_UPDATED and ctx.has_schedule:
            ресурсы.append(Resource("page", "/schedule/", "расписание изменилось"))

        if kind is EventType.ANNOUNCEMENT_UPDATED and ctx.has_announcements:
            ресурсы.append(Resource("page", "/announcements/", "анонсы изменились"))

        if kind in (EventType.PLAYBACK_AVAILABLE, EventType.PLAYBACK_UNAVAILABLE):
            ресурсы.append(
                Resource("page", "/", "полка «можно смотреть» меняет состав")
            )

        # SEO-документ обновляется вместе с карточкой: метаданные описывают её,
        # и расхождение между ними заметно только поисковику, то есть поздно.
        if any(r.kind == "page" and r.path.startswith(f"/title/{ctx.title_path}")
               for r in ресурсы):
            ресурсы.append(
                Resource("seo", f"/title/{ctx.title_path}/",
                         "метаданные описывают изменившуюся карточку")
            )

    # Один и тот же ресурс мог попасть в план по нескольким причинам: оставляем
    # первое упоминание, причина от этого не теряется.
    уникальные: list[Resource] = []
    видели: set[tuple[str, str]] = set()
    for r in ресурсы:
        ключ = (r.kind, r.path)
        if ключ not in видели:
            видели.add(ключ)
            уникальные.append(r)

    return Plan(
        event_id=event.event_id,
        event_type=kind.value,
        canonical_title_id=event.canonical_title_id,
        site_ids=tuple(c.site_id for c in contexts),
        resources=tuple(уникальные),
        cache_tags=event.cache_tags(),
    )


def dry_run(event: ContentEvent, contexts: Iterable[SiteContext]) -> dict:
    """Сухой прогон: что было бы сделано, без единой записи."""
    план = plan_for(event, contexts)
    return план.as_dict() | {"dry_run": True}
