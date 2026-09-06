"""Контракт `seo-route-binding` для витрин, объявляющих маршруты сами.

Витрины yummyani отличаются от Lords тем, что не заставляют вычислять адрес:
таблица `PublicTitleRoute` объявляет соответствие «слаг — произведение».
Проверки ниже требуют, чтобы адаптер это объявление читал, а не подменял
собственными правилами — включая случаи, где объявление противоречиво или
неполно.
"""
from __future__ import annotations

import pytest

from factory.site_engine import seo_binding as sb
from factory.site_engine.adapters import yummy_seo_binding as ay
from factory.site_engine.content_kind import ContentKind

СНИМОК = "2026-09-06T05:51:46+00:00"
ПРОИСХОЖДЕНИЕ = "container:test:PublicTitleRoute"


def маршрут(slug="proizvedenie", pid="01a00000-0000-7000-8000-000000000001",
            canonical=True):
    return {"slug": slug, "providerTitleId": pid, "canonical": canonical,
            "updatedAt": СНИМОК}


def запись(pid="01a00000-0000-7000-8000-000000000001", **kwargs):
    основа = {
        "external_id": pid, "name": "Произведение", "type": "tv",
        "is_series": True, "tags": [], "year": 2026,
        "playback": {"aggregator": "kp", "title_id": "1"},
        "external_ids": {"kp": "1"},
    }
    основа.update(kwargs)
    return основа


def связать(маршруты, каталог):
    return ay.build(маршруты, каталог, site_id="yummyani-site",
                    snapshot_at=СНИМОК, provenance=ПРОИСХОЖДЕНИЕ)


def одна(**kwargs):
    return связать([маршрут()], [запись(**kwargs)])[0]


# --- адрес берётся из объявления --------------------------------------------

def test_адрес_берётся_из_таблицы_а_не_вычисляется():
    """Слаг таблицы может не совпадать с транслитерацией названия."""
    b = связать([маршрут(slug="sovsem-drugoy-adres")],
                [запись(name="Название, из которого такой слаг не выводится")])[0]
    assert b.canonical_path == "/anime/sovsem-drugoy-adres/"
    assert b.binding_state is sb.BindingState.BOUND


def test_идентичность_не_зависит_от_адреса():
    b = одна()
    assert b.content_id == "01a00000-0000-7000-8000-000000000001"
    assert b.content_revision


def test_неканонический_маршрут_своей_страницей_не_является():
    """Показывать по нему собственную страницу — значит заводить дубль руками."""
    b = связать([маршрут(canonical=False)], [запись()])[0]
    assert b.binding_state is sb.BindingState.ROUTE_COLLISION
    assert sb.ReasonCode.ROUTE_AMBIGUOUS in b.reason_codes
    assert b.may_promise_playback is False


def test_маршрут_без_произведения_в_каталоге_уходит_в_разбор():
    """Расхождение витрины с каталогом решать догадкой нельзя."""
    b = связать([маршрут(pid="00000000-0000-0000-0000-000000000000")],
                [запись()])[0]
    assert b.binding_state is sb.BindingState.KIND_UNRESOLVED
    assert b.content_kind is ContentKind.UNKNOWN
    assert b.schema_type == ""


def test_у_витрины_с_объявленными_маршрутами_коллизий_адреса_нет():
    """Два маршрута — два разных адреса по построению таблицы."""
    связи = связать([маршрут(slug="a", pid="p-1"), маршрут(slug="b", pid="p-2")],
                    [запись(pid="p-1"), запись(pid="p-2", name="Второе")])
    assert len({b.canonical_path for b in связи}) == 2
    assert all(b.binding_state is sb.BindingState.BOUND for b in связи)


# --- вид и просмотр ----------------------------------------------------------

@pytest.mark.parametrize("тип,теги,ожидаемый", [
    ("movie", [], ContentKind.MOVIE),
    ("tv", [], ContentKind.SERIES),
    ("tv", ["ona"], ContentKind.ONA),
    ("tv", ["ova"], ContentKind.OVA),
])
def test_вид_приходит_из_каталога(тип, теги, ожидаемый):
    b = одна(type=тип, tags=теги)
    assert b.content_kind is ожидаемый
    assert b.content_kind_state is sb.KindState.RESOLVED


def test_конфликт_вида_уходит_в_разбор():
    b = одна(type="movie", tags=["ona"])
    assert b.content_kind_state is sb.KindState.CONFLICTED
    assert b.content_kind is ContentKind.UNKNOWN
    assert len(b.kind_candidates) >= 2


def test_только_imdb_права_обещать_просмотр_не_даёт():
    b = одна(playback=None, external_ids={"imdb": "tt1"})
    assert b.playback_state is sb.PlaybackState.BLOCKED_BY_CONTRACT
    assert b.may_promise_playback is False


def test_отсутствие_оценки_не_превращается_в_ноль():
    b = одна(kinopoisk_rating=None, imdb_rating=None)
    assert b.rating_state is sb.RatingState.UNRATED
    assert b.rating_value is None


# --- вложенные адреса --------------------------------------------------------

@pytest.mark.parametrize("путь,тип", [
    ("/anime/x/", "title"),
    ("/anime/x", "title"),
    ("/anime/x/season/1", "season"),
    ("/anime/x/season/1/episode/12", "episode"),
])
def test_тип_страницы_по_форме_адреса(путь, тип):
    получен, слаг = ay.page_type_of(путь)
    assert получен == тип
    assert слаг == "x"


@pytest.mark.parametrize("путь", [
    "/catalog/", "/posts/2120", "/anime/x/season/1/episode/12/extra",
    "/anime/x/nechto", "/", "",
])
def test_чужая_форма_адреса_типом_не_считается(путь):
    тип, _ = ay.page_type_of(путь)
    assert тип == ""


def test_вложенный_адрес_наследует_связь_произведения():
    """Поток принадлежит произведению, а не отдельной странице сезона."""
    b = одна()
    по_пути = {b.canonical_path: b}
    for путь, тип in (("/anime/proizvedenie/season/1", "season"),
                      ("/anime/proizvedenie/season/1/episode/7", "episode")):
        связь, получен = ay.resolve_path(путь, по_пути)
        assert связь is b, путь
        assert получен == тип


def test_вложенный_адрес_несуществующего_произведения_связи_не_даёт():
    связь, тип = ay.resolve_path("/anime/net-takogo/season/1", {})
    assert связь is None
    assert тип == "season"


# --- свойства выгрузки -------------------------------------------------------

def test_порядок_маршрутов_не_меняет_отпечаток():
    маршруты = [маршрут(slug=f"s-{i}", pid=f"p-{i}") for i in range(20)]
    каталог = [запись(pid=f"p-{i}", name=f"Работа {i}") for i in range(20)]
    прямо = sb.digest(связать(маршруты, каталог))
    обратно = sb.digest(связать(list(reversed(маршруты)), каталог))
    assert прямо == обратно


def test_повторная_выгрузка_идемпотентна():
    маршруты = [маршрут(slug=f"s-{i}", pid=f"p-{i}") for i in range(10)]
    каталог = [запись(pid=f"p-{i}") for i in range(10)]
    первая = sb.envelope(связать(маршруты, каталог), site_id="yummyani-site",
                         snapshot_at=СНИМОК, provenance=ПРОИСХОЖДЕНИЕ)
    вторая = sb.envelope(связать(маршруты, каталог), site_id="yummyani-site",
                         snapshot_at=СНИМОК, provenance=ПРОИСХОЖДЕНИЕ)
    assert первая == вторая


def test_каждая_запись_несёт_код_причины():
    связи = связать([маршрут(), маршрут(slug="b", pid="нет-такого")],
                    [запись()])
    assert all(b.reason_codes for b in связи)


def test_в_ядре_контракта_нет_имён_витрин_этой_семьи():
    """Знание о витрине живёт в адаптере; ядро о ней не знает."""
    import inspect

    from factory.site_engine.boundaries import code_without_prose

    код = code_without_prose(inspect.getsource(sb)).lower()
    for имя in ("yummy", "anime", "lords"):
        assert имя not in код, f"имя витрины в поведении ядра: {имя}"


def test_секретов_в_контракте_нет():
    import json

    payload = json.dumps(одна().as_dict(), ensure_ascii=False).lower()
    for запрещённое in ("token", "secret", "password", "m3u8", "aggregator",
                        "title_id", "postgres"):
        assert запрещённое not in payload, запрещённое
