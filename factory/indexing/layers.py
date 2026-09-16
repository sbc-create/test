"""Все слои индексации вычисляются из одного снимка и одной revision.

Слоёв пять: заголовок ``X-Robots-Tag``, мета-тег ``robots``, ``canonical``,
``robots.txt`` и доступность карты сайта. Дефект, ради которого модуль написан,
— не «сайт закрыт» и не «сайт открыт», а **смешанное** состояние, когда часть
слоёв уже открыта, а часть ещё закрыта.

Так и случилось 2026-09-15 на ``yummyani.site``: мета-тег звал робота, а
заголовок и ``robots.txt`` запрещали. Снаружи сайт по-прежнему не
индексировался, и отчёт, считающий только «индексируется или нет», показывал
прежнее благополучие.

Поэтому здесь одна функция считает все пять слоёв сразу, из одного снимка. Если
хоть один слой не удалось вычислить, не публикуется ни один: половина
изменения хуже, чем его отсутствие, потому что половину невозможно откатить
осмысленно.
"""

from __future__ import annotations

from dataclasses import dataclass

from factory.indexing.policy import CLOSED, OPEN
from factory.indexing.state import IndexingState, StateSnapshot, state_for_host

#: Значение заголовка и мета-тега для закрытой витрины.
NOINDEX = "noindex, nofollow"
#: Значение мета-тега для открытой витрины. Заголовка у открытой нет вовсе:
#: отсутствие запрета и запрет «index» — разные вещи, и второй лишний.
INDEX = "index, follow"

ROBOTS_CLOSED = "User-agent: *\nDisallow: /\n"


class LayerError(RuntimeError):
    """Слой не вычислен. Публиковать частично запрещено."""


@dataclass(frozen=True)
class ServedLayers:
    """Что витрина обязана отдать при этом снимке."""

    domain: str
    site_id: str
    desired_state: str
    revision: int
    x_robots_tag: str | None
    meta_robots: str
    canonical: str
    robots_txt: str
    sitemap_available: bool
    source_event_id: str

    @property
    def open(self) -> bool:
        return self.desired_state == OPEN

    def consistent(self) -> bool:
        """Все пять слоёв говорят одно и то же."""
        if self.open:
            return (
                self.x_robots_tag is None
                and "noindex" not in self.meta_robots
                and "Disallow: /\n" not in self.robots_txt
                and self.sitemap_available
                and self.canonical.startswith(f"https://{self.domain}")
            )
        return (
            self.x_robots_tag == NOINDEX
            and "noindex" in self.meta_robots
            and "Disallow: /" in self.robots_txt
            and not self.sitemap_available
            and self.canonical.startswith(f"https://{self.domain}")
        )


def compute(состояние: IndexingState, *, path: str = "/") -> ServedLayers:
    """Пять слоёв одной витрины из одного состояния.

    ``canonical`` строится от собственного домена всегда, и для закрытой
    витрины тоже: канонизация на чужой домен — заряженное ружьё, которое
    выстрелит в день открытия.
    """
    if состояние.desired_state not in (OPEN, CLOSED):
        raise LayerError(f"{состояние.domain}: неизвестное состояние")
    открыт = состояние.desired_state == OPEN
    canonical = f"https://{состояние.domain}{path if path.startswith('/') else '/' + path}"
    return ServedLayers(
        domain=состояние.domain,
        site_id=состояние.site_id,
        desired_state=состояние.desired_state,
        revision=состояние.revision,
        x_robots_tag=None if открыт else NOINDEX,
        meta_robots=INDEX if открыт else NOINDEX,
        canonical=canonical,
        robots_txt="" if открыт else ROBOTS_CLOSED,
        sitemap_available=открыт,
        source_event_id=состояние.source_event_id,
    )


def publish(снимок: StateSnapshot, hosts: list[str]) -> dict[str, ServedLayers]:
    """Вычислить слои для всех витрин сразу — или не вычислить ни для одной.

    Атомарность здесь не украшение. Если один хост не удалось разложить на
    слои, а остальные удалось, то выкладка опубликует смешанное состояние
    флота: часть доменов по новому решению, часть по старому. Отличить это от
    нормальной работы потом нельзя.
    """
    итог: dict[str, ServedLayers] = {}
    for хост in hosts:
        состояние = state_for_host(снимок, хост)
        слои = compute(состояние)
        if слои.revision != снимок.revision:
            raise LayerError(
                f"{хост}: слои посчитаны по revision {слои.revision}, "
                f"а снимок имеет {снимок.revision}"
            )
        if not слои.consistent():
            raise LayerError(f"{хост}: слои разошлись между собой")
        итог[хост] = слои
    return итог
