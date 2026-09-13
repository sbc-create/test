"""Кто именно описывается: сущность, сезон, серия.

Модуль существует из-за одной повторяющейся ошибки: пять разных чисел
принимают за одно и то же.

* номер серии внутри сезона;
* сквозной (абсолютный) номер;
* номер, которым серию пронумеровал источник;
* число в адресе страницы;
* число, которое видит зритель.

Они совпадают часто и потому кажутся одним числом. Стоит каталогу
досчитаться до двухсот десяти, а списку оборваться на сотне — и совпадение
кончается. Регрессия, ради которой написан модуль:

    https://yummyani.site/anime/raskolotaya-bitvoy-sineva-nebes-5/season/5/episode/100

Тайтл заявляет 210 серий, интерфейс обрывался на сотой. Число в адресе не
доказывает, какая это серия: адрес — это ключ маршрута, а не утверждение о
нумерации. Поэтому здесь ни одно из пяти чисел не выводится из другого
арифметикой; совпадение обязано быть объявлено маршрутом и проверено.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from .factpack import SEOFactPack

#: Какое из чисел использует адрес. Объявляет маршрут, а не догадка.
NUMBERING_SCHEMES = ("in_season", "absolute", "source", "display")

ПОЛЕ_СХЕМЫ = {
    "in_season": "/episode_in_season_number",
    "absolute": "/episode_absolute_number",
    "source": "/episode_source_number",
    "display": "/episode_display_number",
}


class IdentityCode:
    """Коды исхода. Машинные, стабильные, попадают в отчёт как есть."""

    OK = "OK"
    URL_RESOLVES_TO_OTHER_EPISODE = "URL_RESOLVES_TO_OTHER_EPISODE"
    URL_NUMBERING_SCHEME_UNDECLARED = "URL_NUMBERING_SCHEME_UNDECLARED"
    URL_NUMBER_MISMATCH = "URL_NUMBER_MISMATCH"
    EPISODE_BEYOND_ACTUAL = "EPISODE_BEYOND_ACTUAL"
    EPISODE_NOT_REACHABLE = "EPISODE_NOT_REACHABLE"
    SEASON_NUMBER_MISMATCH = "SEASON_NUMBER_MISMATCH"
    TITLE_MISMATCH = "TITLE_MISMATCH"
    ENTITY_TYPE_MISMATCH = "ENTITY_TYPE_MISMATCH"
    DECLARED_ACTUAL_DIVERGENCE = "DECLARED_ACTUAL_DIVERGENCE"
    NUMBERS_UNRESOLVED = "NUMBERS_UNRESOLVED"


#: Единственный исход, поднимаемый наружу как блокирующий конфликт серии.
EPISODE_IDENTITY_CONFLICT = "EPISODE_IDENTITY_CONFLICT"


@dataclass(frozen=True, slots=True)
class Route:
    """Привязка адреса к сущности. Приходит от маршрутизатора витрины.

    `resolved_entity_id` — то, что витрина фактически отдаёт по этому адресу.
    Не вычисляется здесь и не выводится из `url`: иначе проверка сверяла бы
    догадку с той же догадкой.
    """

    url: str
    resolved_entity_id: str | None
    url_number: int | None = None
    numbering_scheme: str | None = None
    season_url_number: int | None = None
    #: На каком номере обрывается перечень серий в интерфейсе. `None` — не
    #: обрывается. Именно это поле описывает дефект «210 заявлено, 100 видно».
    listing_truncated_at: int | None = None
    canonical: str | None = None
    breadcrumbs: tuple[str, ...] = ()
    #: Адреса родительских сущностей. Нужны разметке, чтобы сезон и серия
    #: были связаны с тайтлом устойчивым `@id`, а не висели сами по себе.
    title_path: str | None = None
    season_path: str | None = None


@dataclass
class IdentityReport:
    code: str = IdentityCode.OK
    problems: list[str] = field(default_factory=list)
    #: Числа, которые удалось развести. Отсутствующее число — `None`, а не 0.
    numbers: dict[str, Any] = field(default_factory=dict)
    #: Номер, который единственно допустимо показывать зрителю.
    display_number: int | None = None

    @property
    def ok(self) -> bool:
        return self.code == IdentityCode.OK and not self.problems

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "ok": self.ok, "problems": list(self.problems),
                "numbers": dict(self.numbers),
                "display_number": self.display_number}


def _число(pack: SEOFactPack, путь: str) -> int | None:
    значение = pack.value(путь)
    if значение is None:
        return None
    try:
        return int(значение)
    except (TypeError, ValueError):
        return None


def resolve_episode_identity(pack: SEOFactPack, route: Route) -> IdentityReport:
    """Развести пять чисел и решить, об одной ли они серии.

    Возврат `EPISODE_IDENTITY_CONFLICT` означает: генерация обязана
    остановиться. Не «выбрать вероятное», не «взять число из адреса» —
    остановиться, потому что выбор здесь и есть выдумывание.
    """
    отчёт = IdentityReport()
    if pack.entity_type != "episode":
        отчёт.code = IdentityCode.ENTITY_TYPE_MISMATCH
        отчёт.problems.append(
            f"пакет описывает {pack.entity_type}, а проверяется серия")
        return отчёт

    числа = {
        "in_season": _число(pack, "/episode_in_season_number"),
        "absolute": _число(pack, "/episode_absolute_number"),
        "source": _число(pack, "/episode_source_number"),
        "display": _число(pack, "/episode_display_number"),
        "url": route.url_number,
    }
    отчёт.numbers = dict(числа)

    # 1. Адрес обязан вести к этой же сущности. Это проверка маршрута, а не
    #    арифметики: совпадение чисел ничего не доказывает.
    if route.resolved_entity_id is not None and \
            route.resolved_entity_id != pack.episode_id:
        отчёт.code = IdentityCode.URL_RESOLVES_TO_OTHER_EPISODE
        отчёт.problems.append(
            f"{route.url} отдаёт {route.resolved_entity_id!r}, а описывается "
            f"{pack.episode_id!r}")
        return отчёт

    # 2. Какое из чисел стоит в адресе — объявляет маршрут. Догадка
    #    запрещена: именно она и породила дефект «100 = сотая серия».
    if route.url_number is not None:
        if route.numbering_scheme not in NUMBERING_SCHEMES:
            отчёт.code = IdentityCode.URL_NUMBERING_SCHEME_UNDECLARED
            отчёт.problems.append(
                f"{route.url}: адрес несёт число {route.url_number}, но не "
                f"объявлено, какая это нумерация; число в адресе само по себе "
                f"не доказывает номер серии")
            return отчёт
        ожидаемое = числа[route.numbering_scheme]
        if ожидаемое is None:
            отчёт.code = IdentityCode.NUMBERS_UNRESOLVED
            отчёт.problems.append(
                f"адрес объявляет нумерацию {route.numbering_scheme}, но "
                f"факта {ПОЛЕ_СХЕМЫ[route.numbering_scheme]} в пакете нет")
            return отчёт
        if ожидаемое != route.url_number:
            отчёт.code = IdentityCode.URL_NUMBER_MISMATCH
            отчёт.problems.append(
                f"{route.url}: в адресе {route.url_number}, а "
                f"{route.numbering_scheme} этой серии — {ожидаемое}")
            return отчёт

    # 3. Показывать можно только объявленный отображаемый номер. Подставить
    #    вместо него номер из адреса — та же ошибка с другой стороны.
    отчёт.display_number = числа["display"] if числа["display"] is not None \
        else числа["in_season"]
    if отчёт.display_number is None:
        отчёт.code = IdentityCode.NUMBERS_UNRESOLVED
        отчёт.problems.append(
            "ни отображаемого, ни внутрисезонного номера нет: показать серию "
            "под номером нечем")
        return отчёт

    # 4. Сезон.
    сезон = _число(pack, "/season_number")
    if route.season_url_number is not None and сезон is not None and \
            route.season_url_number != сезон:
        отчёт.code = IdentityCode.SEASON_NUMBER_MISMATCH
        отчёт.problems.append(
            f"{route.url}: сезон в адресе {route.season_url_number}, в "
            f"фактах {сезон}")
        return отчёт

    # 5. Заявлено против фактического. Расхождение — не повод выбрать
    #    большее: это состояние данных, и текст о нём врать не должен.
    заявлено = _число(pack, "/declared_episode_count")
    фактически = _число(pack, "/actual_episode_count")
    if заявлено is not None and фактически is not None and заявлено != фактически:
        отчёт.problems.append(
            f"каталог заявляет {заявлено} серий, фактически доступно "
            f"{фактически}: утверждать любое из чисел как единственное нельзя")
        отчёт.code = IdentityCode.DECLARED_ACTUAL_DIVERGENCE

    if фактически is not None and отчёт.display_number > фактически:
        отчёт.code = IdentityCode.EPISODE_BEYOND_ACTUAL
        отчёт.problems.append(
            f"серия {отчёт.display_number} за пределами фактически доступных "
            f"{фактически}")
        return отчёт

    # 6. Обрыв перечня. Ровно случай «210 заявлено, 100 видно»: страница
    #    существует, а дойти до неё по интерфейсу нельзя.
    if route.listing_truncated_at is not None and \
            отчёт.display_number > route.listing_truncated_at:
        отчёт.code = IdentityCode.EPISODE_NOT_REACHABLE
        отчёт.problems.append(
            f"перечень обрывается на {route.listing_truncated_at}, а серия "
            f"{отчёт.display_number} за обрывом: страница есть, пути к ней нет")
        return отчёт

    return отчёт


def resolve_title_identity(pack: SEOFactPack, route: Route) -> IdentityReport:
    отчёт = IdentityReport()
    if pack.entity_type != "title":
        отчёт.code = IdentityCode.ENTITY_TYPE_MISMATCH
        отчёт.problems.append(f"пакет описывает {pack.entity_type}")
        return отчёт
    if route.resolved_entity_id is not None and \
            route.resolved_entity_id != pack.title_id:
        отчёт.code = IdentityCode.TITLE_MISMATCH
        отчёт.problems.append(
            f"{route.url} отдаёт {route.resolved_entity_id!r}, описывается "
            f"{pack.title_id!r}")
    return отчёт


def resolve_season_identity(pack: SEOFactPack, route: Route) -> IdentityReport:
    отчёт = IdentityReport()
    if pack.entity_type != "season":
        отчёт.code = IdentityCode.ENTITY_TYPE_MISMATCH
        отчёт.problems.append(f"пакет описывает {pack.entity_type}")
        return отчёт
    if route.resolved_entity_id is not None and \
            route.resolved_entity_id != pack.season_id:
        отчёт.code = IdentityCode.TITLE_MISMATCH
        отчёт.problems.append(
            f"{route.url} отдаёт {route.resolved_entity_id!r}, описывается "
            f"{pack.season_id!r}")
        return отчёт
    сезон = _число(pack, "/season_number")
    if route.season_url_number is not None and сезон is not None and \
            route.season_url_number != сезон:
        отчёт.code = IdentityCode.SEASON_NUMBER_MISMATCH
        отчёт.problems.append(
            f"сезон в адресе {route.season_url_number}, в фактах {сезон}")
    return отчёт


def resolve(pack: SEOFactPack, route: Route) -> IdentityReport:
    return {"title": resolve_title_identity, "season": resolve_season_identity,
            "episode": resolve_episode_identity}[pack.entity_type](pack, route)


# --- устаревшие номера в готовом тексте -----------------------------------

_НОМЕР_СЕРИИ = re.compile(
    r"(?:(\d{1,4})\s*[-‐-―]?\s*(?:я|й|ая|ой)?\s*сери(?:я|и|ю|е|ей)"
    r"|сери(?:я|и|ю|е|ей)\s*[№#]?\s*(\d{1,4}))", re.I)
_НОМЕР_СЕЗОНА = re.compile(
    r"(?:(\d{1,3})\s*[-‐-―]?\s*(?:й|ый|ой)?\s*сезон"
    r"|сезон\s*[№#]?\s*(\d{1,3}))", re.I)


def _номера(текст: str, шаблон: re.Pattern) -> list[int]:
    найдено: list[int] = []
    for м in шаблон.finditer(текст or ""):
        for г in м.groups():
            if г:
                найдено.append(int(г))
    return найдено


def stale_number_scan(поверхности: Mapping[str, Any], *,
                      episode_number: int | None,
                      season_number: int | None) -> list[str]:
    """Найти номер, отставший от разрешённой личности.

    Требование задания: после разрешения личности нигде не должно остаться
    «100 серия» — ни в заголовке, ни в описании, ни в H1, ни в тексте, ни в
    хлебных крошках, ни в canonical, ни в OpenGraph, ни в JSON-LD. Поэтому
    проверяются все поверхности сразу, а не одна витрина.
    """
    беды: list[str] = []
    for имя, значение in sorted(поверхности.items()):
        if значение is None:
            continue
        текст = значение if isinstance(значение, str) else str(значение)
        if episode_number is not None:
            чужие = [n for n in _номера(текст, _НОМЕР_СЕРИИ)
                     if n != episode_number]
            if чужие:
                беды.append(
                    f"{имя}: номер серии {sorted(set(чужие))} вместо "
                    f"{episode_number}")
        if season_number is not None:
            чужие = [n for n in _номера(текст, _НОМЕР_СЕЗОНА)
                     if n != season_number]
            if чужие:
                беды.append(
                    f"{имя}: номер сезона {sorted(set(чужие))} вместо "
                    f"{season_number}")
    return беды


def url_number(url: str, сегмент: str = "episode") -> int | None:
    """Число, стоящее в адресе после названного сегмента.

    Извлечение — не утверждение о номере серии. Оно нужно ровно затем,
    чтобы сверить адрес с объявленной нумерацией, а не чтобы заменить её.
    """
    м = re.search(rf"/{re.escape(сегмент)}/(\d{{1,5}})(?:/|$|\?)", url or "")
    return int(м.group(1)) if м else None


def parent_paths(route: Route) -> tuple[str | None, str | None]:
    """Адреса тайтла и сезона: объявленные маршрутом либо выведенные из него.

    Вывод из адреса — не догадка о личности, а разбор собственного же пути:
    `/title/x/season/5/episode/12` содержит `/title/x/` и
    `/title/x/season/5/` буквально. Если маршрут объявил пути сам, берутся
    объявленные.
    """
    если_путь = route.canonical or route.url or ""
    тайтл = route.title_path
    сезон = route.season_path
    if тайтл is None:
        м = re.match(r"^(/[^/]+/[^/]+/)", если_путь)
        тайтл = м.group(1) if м else None
    if сезон is None:
        м = re.match(r"^(/[^/]+/[^/]+/season/\d+/?)", если_путь)
        сезон = (м.group(1).rstrip("/") + "/") if м else None
    return тайтл, сезон
