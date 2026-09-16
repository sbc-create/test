"""Контракт коллекций: лента и полная страница обязаны совпадать."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from factory.lords import collection_contract as кк  # noqa: E402

СЕМЕЙСТВА = ("lords", "zona", "animedia", "yummy")


def запись(слаг, титул, вид, год, дата, постер="p.webp"):
    return {"slug": слаг, "title": титул, "kind": вид, "year": год,
            "published_at": дата, "poster": постер, "url": f"/title/{слаг}/"}


@pytest.fixture()
def снимок():
    items = [
        запись("f1", "Фильм один", "Фильм", 2026, "2026-09-10T10:00:00Z"),
        запись("s1", "Сериал один", "Сериал", 2026, "2026-09-09T10:00:00Z"),
        запись("f2", "Фильм два", "Фильм", 2025, "2026-09-08T10:00:00Z"),
        запись("a1", "Аниме одно", "Аниме", 2026, "2026-09-07T10:00:00Z"),
        запись("s2", "Сериал два", "Сериал", 2024, "2026-09-06T10:00:00Z"),
        запись("f3", "Фильм три", "Фильм", 2026, "2026-09-05T10:00:00Z"),
    ]
    подробности = {
        "f1": {"id": "id-f1", "imdb_rating": 8.4, "playable": True},
        "s1": {"id": "id-s1", "imdb_rating": 7.1, "playable": True},
        "f2": {"id": "id-f2", "kinopoisk_rating": 9.2, "playable": False},
        "a1": {"id": "id-a1", "playable": True},
        "s2": {"id": "id-s2", "imdb_rating": 5.0, "playable": True},
        "f3": {"id": "id-f3", "playable": False},
    }
    return кк.Снимок(items, подробности, revision="rev-1")


# --- схема контракта -------------------------------------------------------

@pytest.mark.parametrize("семейство", СЕМЕЙСТВА)
def test_у_каждой_спецификации_есть_обязательные_поля(семейство):
    for с in кк.спецификации(семейство):
        assert с.collection_key and с.family == семейство
        assert с.section_id and с.title and с.description
        assert с.source and с.view_all_path and с.canonical_path
        assert isinstance(с.filter_spec, dict)
        assert isinstance(с.sort_spec, dict)
        assert с.card_limit > 0
        assert с.empty_policy in (кк.СКРЫТЬ, кк.СООБЩЕНИЕ)


@pytest.mark.parametrize("семейство", СЕМЕЙСТВА)
def test_ключи_коллекций_уникальны(семейство):
    ключи = [с.collection_key for с in кк.спецификации(семейство)]
    assert len(ключи) == len(set(ключи))


@pytest.mark.parametrize("семейство", СЕМЕЙСТВА)
def test_ссылка_не_содержит_домена_и_не_ведёт_в_общий_каталог(семейство):
    """Главный дефект, ради которого контракт и появился."""
    for с in кк.спецификации(семейство):
        assert с.view_all_path.startswith("/"), с.collection_key
        assert "://" not in с.view_all_path
        assert not с.view_all_path.rstrip("/").endswith("/catalog"), с.collection_key
        assert с.view_all_path == f"/collection/{с.collection_key}/"


def test_коллекция_разрешается_в_словарь_со_всеми_полями(снимок):
    к = кк.разрешить("recently_added", снимок, "lords", предел=3)
    д = к.как_словарь()
    обязательные = {
        "contract_version", "collection_key", "family", "section_id", "title",
        "description", "source", "filter_spec", "sort_spec", "freshness_rule",
        "card_limit", "total", "items", "page", "view_all_path",
        "canonical_path", "generated_at", "data_revision", "empty_policy",
    }
    assert обязательные <= set(д)
    assert д["contract_version"] == кк.ВЕРСИЯ_КОНТРАКТА


def test_карточка_несёт_обязательные_поля(снимок):
    к = кк.разрешить("recently_added", снимок, "lords", предел=1)
    карта = к.items[0].как_словарь()
    assert {"entity_id", "canonical_path", "title", "poster", "badge",
            "release_at", "ratings", "video_available"} <= set(карта)
    assert карта["canonical_path"].startswith("/title/")


# --- связность ленты и полной страницы -------------------------------------

@pytest.mark.parametrize("ключ", ["recently_added", "recently_added_movies",
                                  "new_episodes", "top_rated",
                                  "current_season", "video_available"])
def test_лента_является_началом_полной_коллекции(снимок, ключ):
    лента = кк.разрешить(ключ, снимок, "lords", предел=3)
    полная = кк.разрешить(ключ, снимок, "lords")
    ленты = [к.entity_id for к in лента.items]
    полной = [к.entity_id for к in полная.items]
    assert ленты == полной[:len(ленты)], ключ
    assert set(ленты) <= set(полной)


@pytest.mark.parametrize("ключ", ["recently_added", "new_episodes", "top_rated"])
def test_одинаковая_ревизия_данных(снимок, ключ):
    лента = кк.разрешить(ключ, снимок, "lords", предел=2)
    полная = кк.разрешить(ключ, снимок, "lords")
    assert лента.data_revision == полная.data_revision == "rev-1"


def test_порядок_устойчив_между_вызовами(снимок):
    первый = [к.entity_id for к in кк.разрешить("recently_added", снимок, "lords").items]
    второй = [к.entity_id for к in кк.разрешить("recently_added", снимок, "lords").items]
    assert первый == второй


def test_без_дублей(снимок):
    for с in кк.спецификации("lords"):
        к = кк.разрешить(с.collection_key, снимок, "lords")
        ид = [э.entity_id for э in к.items]
        assert len(ид) == len(set(ид)), с.collection_key


# --- правильность фильтра и сортировки -------------------------------------

def test_фильтр_по_виду_действительно_фильтрует(снимок):
    к = кк.разрешить("recently_added_movies", снимок, "lords")
    assert {э.badge for э in к.items} == {"Фильм"}
    assert к.total == 3


def test_новые_эпизоды_это_только_сериалы(снимок):
    к = кк.разрешить("new_episodes", снимок, "lords")
    assert {э.badge for э in к.items} == {"Сериал"}


def test_сортировка_по_дате_убывающая(снимок):
    к = кк.разрешить("recently_added", снимок, "lords")
    даты = [э.release_at for э in к.items]
    assert даты == sorted(даты, reverse=True)


def test_высокие_оценки_отсортированы_и_только_с_оценкой(снимок):
    к = кк.разрешить("top_rated", снимок, "lords")
    оценки = [max(э.ratings.values()) for э in к.items]
    assert оценки == sorted(оценки, reverse=True)
    assert all(э.ratings for э in к.items)
    assert "id-a1" not in [э.entity_id for э in к.items]


def test_этого_года_берёт_самый_свежий_год(снимок):
    к = кк.разрешить("current_season", снимок, "lords")
    assert {э.entity_id for э in к.items} == {"id-f1", "id-s1", "id-a1", "id-f3"}


def test_с_видео_только_подтверждённые(снимок):
    к = кк.разрешить("video_available", снимок, "lords")
    assert all(э.video_available for э in к.items)
    assert "id-f2" not in [э.entity_id for э in к.items]


# --- пагинация -------------------------------------------------------------

def test_страницы_не_пересекаются_и_покрывают_всё(снимок):
    первая = кк.разрешить("recently_added", снимок, "lords", страница=1, на_странице=4)
    вторая = кк.разрешить("recently_added", снимок, "lords", страница=2, на_странице=4)
    a = [э.entity_id for э in первая.items]
    b = [э.entity_id for э in вторая.items]
    assert len(a) == 4 and len(b) == 2
    assert not set(a) & set(b)
    assert первая.total == вторая.total == 6


def test_страница_за_пределами_пуста(снимок):
    к = кк.разрешить("recently_added", снимок, "lords", страница=99, на_странице=4)
    assert к.items == []
    assert к.total == 6


# --- пустые и недоступные коллекции ----------------------------------------

def test_недоступная_коллекция_пуста_и_названа_причина():
    """Отсутствующий признак — факт контура, а не повод показать чужое."""
    с = кк.спецификация("animedia", "ongoing")
    assert с is not None
    assert not с.доступна
    assert с.unavailable_reason
    assert с.empty_policy == кк.СКРЫТЬ


def test_недоступная_коллекция_не_наполняется_похожими(снимок):
    к = кк.разрешить("ongoing", снимок, "animedia")
    assert к.items == []
    assert к.total == 0


def test_пустой_снимок_не_ломает_разрешение():
    пусто = кк.Снимок([], {}, revision="rev-0")
    к = кк.разрешить("recently_added", пусто, "lords", предел=12)
    assert к.items == [] and к.total == 0


def test_снимок_из_одной_записи(снимок):
    один = кк.Снимок([запись("x", "Одна", "Фильм", 2026, "2026-01-01T00:00:00Z")],
                     {"x": {"id": "id-x", "playable": True}}, revision="rev-2")
    к = кк.разрешить("recently_added", один, "lords", предел=12)
    assert к.total == 1 and len(к.items) == 1


def test_неизвестный_ключ_даёт_none(снимок):
    assert кк.разрешить("нет-такой", снимок, "lords") is None


# --- производительность контракта ------------------------------------------

def test_срезы_считаются_один_раз_а_не_на_каждый_блок():
    """Ради этого свойства снимок и заведён: блоки не обходят каталог заново."""
    items = [запись(f"s{i}", f"Т{i}", "Фильм" if i % 2 else "Сериал",
                    2020 + i % 6, f"2026-09-{(i % 28) + 1:02d}T00:00:00Z")
             for i in range(5000)]
    подробности = {f"s{i}": {"id": f"id-{i}", "playable": True} for i in range(5000)}
    с = кк.Снимок(items, подробности, revision="big")
    # Один и тот же объект среза возвращается повторно — пересортировки нет.
    assert с.по_дате() is с.по_дате()
    assert с.по_виду("Фильм") is с.по_виду("Фильм")
    ленты = [кк.разрешить(сп.collection_key, с, "lords", предел=12)
             for сп in кк.спецификации("lords")]
    assert all(len(к.items) <= 12 for к in ленты)
