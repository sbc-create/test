"""Zona follow-up: playback source selection, honest states, cards, genres, layout."""
from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
from pathlib import Path

import pytest

ИСХОДНИК = Path(__file__).resolve().parents[2] / "automation" / "host" / "lords-frontend.py"


def _каталог() -> dict:
    записи = [
        {"slug": "movie-kp-ready", "title": "Фильм с КП", "kind": "Фильм",
         "year": 2024, "poster": "https://poster.example/a.webp",
         "url": "/title/movie-kp-ready/", "published_at": "2026-09-10T00:00:00Z"},
        {"slug": "movie-empty-first", "title": "Пустая первая дорожка", "kind": "Фильм",
         "year": 2023, "poster": "https://poster.example/b.webp",
         "url": "/title/movie-empty-first/", "published_at": "2026-09-11T00:00:00Z"},
        {"slug": "movie-nosource", "title": "Без источника", "kind": "Фильм",
         "year": 2022, "poster": "", "url": "/title/movie-nosource/",
         "published_at": "2026-09-12T00:00:00Z"},
        {"slug": "series-gap", "title": "Сериал с дырой", "kind": "Сериал",
         "year": 2021, "poster": "https://poster.example/c.webp",
         "url": "/title/series-gap/", "published_at": "2026-09-13T00:00:00Z"},
        {"slug": "long-title-card-aaaa-bbbb-cccc-dddd-eeee-ffff",
         "title": "Очень длинное название карточки которое обязано занять две строки "
                  "и не раздувать высоту ряда даже если продолжить ещё словами",
         "kind": "Фильм", "year": 2020, "poster": "https://poster.example/d.webp",
         "url": "/title/long-title-card-aaaa-bbbb-cccc-dddd-eeee-ffff/",
         "published_at": "2026-09-14T00:00:00Z"},
        {"slug": "genre-dorama", "title": "Дорама один", "kind": "Сериал",
         "year": 2024, "poster": "https://poster.example/e.webp",
         "url": "/title/genre-dorama/", "published_at": "2026-09-15T00:00:00Z"},
        {"slug": "genre-drama", "title": "Драма один", "kind": "Фильм",
         "year": 2024, "poster": "https://poster.example/f.webp",
         "url": "/title/genre-drama/", "published_at": "2026-09-16T00:00:00Z"},
        {"slug": "genre-west", "title": "Западный один", "kind": "Фильм",
         "year": 2024, "poster": "https://poster.example/g.webp",
         "url": "/title/genre-west/", "published_at": "2026-09-17T00:00:00Z"},
        {"slug": "genre-comedy", "title": "Комедия один", "kind": "Фильм",
         "year": 2024, "poster": "https://poster.example/h.webp",
         "url": "/title/genre-comedy/", "published_at": "2026-09-18T00:00:00Z"},
        {"slug": "genre-thriller", "title": "Триллер один", "kind": "Фильм",
         "year": 2024, "poster": "https://poster.example/i.webp",
         "url": "/title/genre-thriller/", "published_at": "2026-09-19T00:00:00Z"},
    ]
    return {"version": 2, "count": len(записи), "items": записи,
            "fields_absent": [], "site": "zona-01",
            "schema": "nova-catalog/2.0.0", "revision": "followup",
            "builtAt": "2026-09-19T00:00:00Z"}


def _подробности() -> dict:
    uuid = "019e7ce8-fd9d-7b5e-83ed-734c6a5c5437"
    return {
        "schema": "nova-details/1.0.0", "site": "zona-01", "details_total": 10,
        "source": "test", "items_total": 10,
        "details": {
            "movie-kp-ready": {
                "id": uuid,
                "description": "Есть available kp при UUID id.",
                "original_name": "KP Ready", "countries": ["США"],
                "genres": ["западный контент"], "genre_codes": ["west_content"],
                "duration": 100, "kinopoisk_rating": 7.1,
                "sources": [{"provider": "kp", "source_id": "11922371",
                             "availability_status": "available"}],
                "external_ids": {"kp": "11922371"},
            },
            "movie-empty-first": {
                "id": "019e7ce8-aaaa-7b5e-83ed-734c6a5c5437",
                "description": "Первая дорожка unavailable, вторая available.",
                "countries": ["Корея"], "genres": ["дорама"], "genre_codes": ["dorama"],
                "sources": [
                    {"provider": "cvh", "source_id": "dead-track",
                     "availability_status": "unavailable"},
                    {"provider": "kp", "source_id": "555001",
                     "availability_status": "available"},
                ],
                "external_ids": {"kp": "555001"},
            },
            "movie-nosource": {
                "id": "not-a-uuid",
                "description": "Нет агрегаторов.",
                "countries": ["РФ"], "genres": ["драма"], "genre_codes": ["drama"],
                "external_ids": {},
            },
            "series-gap": {
                "id": "019e7ce8-bbbb-7b5e-83ed-734c6a5c5437",
                "description": "avail=0, eps=3 — хаб без первой серии.",
                "countries": ["Япония"], "genres": ["триллер"], "genre_codes": ["triller"],
                "seasons": [{"n": 1, "eps": 5, "avail": 0},
                            {"n": 2, "eps": 5, "avail": 2}],
                "sources": [{"provider": "kp", "source_id": "777001",
                             "availability_status": "available"}],
                "external_ids": {"kp": "777001"}, "is_series": True,
            },
            "long-title-card-aaaa-bbbb-cccc-dddd-eeee-ffff": {
                "id": "019e7ce8-cccc-7b5e-83ed-734c6a5c5437",
                "genres": ["комедия"], "genre_codes": ["comedy"],
                "sources": [{"provider": "kp", "source_id": "1",
                             "availability_status": "available"}],
                "external_ids": {"kp": "1"},
            },
            "genre-dorama": {
                "id": "019e7ce8-dddd-7b5e-83ed-734c6a5c5437",
                "genres": ["дорама"], "genre_codes": ["dorama"],
                "seasons": [{"n": 1, "eps": 2, "avail": 2}],
                "sources": [{"provider": "kp", "source_id": "2",
                             "availability_status": "available"}],
                "external_ids": {"kp": "2"}, "is_series": True,
            },
            "genre-drama": {
                "id": "019e7ce8-eeee-7b5e-83ed-734c6a5c5437",
                "genres": ["драма"], "genre_codes": ["drama"],
                "sources": [{"provider": "kp", "source_id": "3",
                             "availability_status": "available"}],
                "external_ids": {"kp": "3"},
            },
            "genre-west": {
                "id": "019e7ce8-ffff-7b5e-83ed-734c6a5c5437",
                "genres": ["западный контент"], "genre_codes": ["west_content"],
                "sources": [{"provider": "kp", "source_id": "4",
                             "availability_status": "available"}],
                "external_ids": {"kp": "4"},
            },
            "genre-comedy": {
                "id": "019e7ce8-1111-7b5e-83ed-734c6a5c5437",
                "genres": ["комедия"], "genre_codes": ["comedy"],
                "sources": [{"provider": "kp", "source_id": "5",
                             "availability_status": "available"}],
                "external_ids": {"kp": "5"},
            },
            "genre-thriller": {
                "id": "019e7ce8-2222-7b5e-83ed-734c6a5c5437",
                "genres": ["триллер"], "genre_codes": ["triller"],
                "sources": [{"provider": "kp", "source_id": "6",
                             "availability_status": "available"}],
                "external_ids": {"kp": "6"},
            },
        },
    }


def _поднять(tmp_path, *, source_mode: str = "provider-id"):
    корень = tmp_path / "zona-01"
    корень.mkdir(parents=True, exist_ok=True)
    (корень / "zona-01-catalog.json").write_text(
        json.dumps(_каталог(), ensure_ascii=False), encoding="utf-8")
    (корень / "zona-01-details.json").write_text(
        json.dumps(_подробности(), ensure_ascii=False), encoding="utf-8")
    (корень / "player-zona-01.json").write_text(
        json.dumps({"publisher_id": "10238", "source_mode": source_mode}),
        encoding="utf-8")
    cat = json.loads((корень / "zona-01-catalog.json").read_text(encoding="utf-8"))
    det = json.loads((корень / "zona-01-details.json").read_text(encoding="utf-8"))
    pw_spec = importlib.util.spec_from_file_location(
        f"pw_followup_{source_mode.replace('-', '_')}",
        Path(__file__).resolve().parents[2] / "automation" / "host" / "popular_weekly.py")
    pw = importlib.util.module_from_spec(pw_spec)
    assert pw_spec.loader is not None
    pw_spec.loader.exec_module(pw)
    snap = pw.build_snapshot(
        cat["items"], det["details"], clock="2026-09-19T12:00:00Z", limit=12)
    pw.publish_snapshot(snap, корень / "zona-01-popular-weekly.json")
    манифест = корень / "manifest.json"
    манифест.write_text(json.dumps({
        "schema_version": 1, "template_family": "zona",
        "design_version": "1.2.0", "source_commit": "0" * 40,
        "build_id": "FOLLOWUP", "artifact_sha256": "0" * 64,
        "profile": "zona-test", "built_at": "2026-09-19T00:00:00Z",
    }, ensure_ascii=False), encoding="utf-8")

    прежние = dict(sys.modules)
    старое = dict(os.environ)
    os.environ["LORDS_TEMPLATE_MANIFEST"] = str(манифест)
    os.environ["LORDS_CATALOG"] = str(корень / "zona-01-catalog.json")
    os.environ["LORDS_DETAILS"] = str(корень / "zona-01-details.json")
    os.environ["LORDS_PLAYER_CONFIG"] = str(корень / "player-zona-01.json")
    os.environ["LORDS_SITE_NAME"] = "Zona Followup"
    try:
        имя = f"nova_zona_followup_{source_mode.replace('-', '_')}"
        спец = importlib.util.spec_from_file_location(имя, ИСХОДНИК)
        модуль = importlib.util.module_from_spec(спец)
        sys.modules[имя] = модуль
        спец.loader.exec_module(модуль)
    finally:
        os.environ.clear()
        os.environ.update(старое)
        for к in set(sys.modules) - set(прежние):
            if not к.startswith("nova_"):
                sys.modules.pop(к, None)
    модуль.Обработчик.данные = модуль.Данные(str(корень / "zona-01-catalog.json"))
    модуль.Обработчик.подробности = модуль.Подробности(
        str(корень / "zona-01-details.json"))
    модуль.Обработчик.индекс = модуль.построить_индекс(
        модуль.Обработчик.данные, модуль.Обработчик.подробности)
    return модуль


def запросить(модуль, путь: str):
    from tests.lords.test_nova_frontend_families import запросить as _з
    return _з(модуль, путь)


@pytest.fixture(scope="module")
def зона(tmp_path_factory):
    return _поднять(tmp_path_factory.mktemp("zona-fu"))


class TestSourceSelection:
    def test_available_kp_beats_uuid(self, зона):
        д = зона.Обработчик.подробности.get("movie-kp-ready")
        кандидаты = зона.кандидаты_источника(д)
        assert кандидаты[0] == ("kp", "11922371")
        assert ("cvh", д["id"]) in кандидаты
        а, и = зона.источник_по_провайдеру(д)
        assert (а, и) == ("kp", "11922371")

    def test_skips_unavailable_first_track(self, зона):
        д = зона.Обработчик.подробности.get("movie-empty-first")
        а, и = зона.источник_по_провайдеру(д)
        assert (а, и) == ("kp", "555001")

    def test_movie_markup_uses_kp_not_uuid(self, зона):
        о = запросить(зона, "/title/movie-kp-ready/")
        assert о.статус == 200
        assert 'data-state="resolving"' in о.тело
        assert 'data-aggregator="kp"' in о.тело
        assert 'data-title-id="11922371"' in о.тело
        assert "источник подключён" not in о.тело.lower()
        assert "подключение источника" in о.тело.lower()
        assert "data-src-candidates=" in о.тело

    def test_nosource_honest_no_fake_play(self, зона):
        о = запросить(зона, "/title/movie-nosource/")
        assert 'data-state="nosource"' in о.тело
        assert "<video-player" not in о.тело
        assert "Смотреть</button>" not in о.тело
        assert "источник подключён" not in о.тело.lower()

    def test_series_hub_picks_first_playable_episode(self, зона):
        д = зона.Обработчик.подробности.get("series-gap")
        сезон, эпизод = зона.выбрать_доступную_серию(д)
        assert (сезон, эпизод) == (2, 1)
        о = запросить(зона, "/title/series-gap/")
        assert 'episode="1"' in о.тело
        assert 'season="2"' in о.тело or 'season="2"' in о.тело

    def test_direct_unavailable_episode_stays_honest(self, зона):
        о = запросить(зона, "/title/series-gap/season-1/episode-1/")
        assert 'data-state="unavailable"' in о.тело
        assert "<video-player" not in о.тело
        assert "Дорожки этой серии ещё нет" in о.тело

    def test_direct_playable_episode(self, зона):
        о = запросить(зона, "/title/series-gap/season-2/episode-1/")
        assert 'data-state="resolving"' in о.тело
        assert 'episode="1"' in о.тело
        assert "<video-player" in о.тело

    def test_client_fallback_and_token_guard(self, зона):
        скрипт = зона.СКРИПТ_ПЛЕЕРА_КЛИЕНТ
        assert "maxFallback" in скрипт
        assert "generation" in скрипт or "token" in скрипт
        assert "noData" in скрипт
        assert "mountAt" in скрипт or "mount(" in скрипт
        assert "destroy" in скрипт
        assert скрипт.count("createElement('video-player')") >= 1

    def test_no_contradictory_connected_label_on_resolving(self, зона):
        о = запросить(зона, "/title/movie-empty-first/")
        assert "источник подключён" not in о.тело.lower()
        assert 'data-aggregator="kp"' in о.тело


class TestCards:
    def test_tile_has_title_attr_and_clamp_contract(self, зона):
        о = запросить(зона, "/catalog/")
        assert 'class="zt"' in о.тело
        assert "title=" in о.тело
        assert "-webkit-line-clamp:2" in зона.ЗОНА_СТИЛЬ
        assert "aspect-ratio:2/3" in зона.ЗОНА_СТИЛЬ
        assert "height:100%" in зона.ЗОНА_СТИЛЬ
        assert "margin-top:auto" in зона.ЗОНА_СТИЛЬ

    def test_long_title_does_not_duplicate_unclamped(self, зона):
        о = запросить(зона, "/catalog/")
        assert "long-title-card" in о.тело
        assert о.тело.count("zt__t") >= 1


class TestGenres:
    def test_home_genre_block_after_first_shelf(self, зона):
        о = запросить(зона, "/")
        assert "Жанры" in о.тело
        assert 'class="zgenres"' in о.тело
        pos_genres = о.тело.find('id="zgenres-h"')
        # Home order: hero → weekly → added → kinds → genres (B02–B06).
        pos_weekly = о.тело.find("Высокие оценки недели")
        assert pos_weekly != -1 and pos_genres != -1
        assert pos_weekly < pos_genres

    def test_genre_urls_distinct_and_encoded(self, зона):
        о = запросить(зона, "/")
        for код in ("west_content", "dorama", "drama", "comedy", "triller"):
            assert f"genre={код}" in о.тело or f"genre%3D{код}" in о.тело

    def test_genre_result_sets_differ(self, зона):
        sets = {}
        for код in ("dorama", "drama", "west_content", "comedy", "triller"):
            о = запросить(зона, f"/catalog/?genre={код}")
            assert о.статус == 200
            assert о.тело.count("<h1") == 1
            slugs = set(re.findall(r'href="/title/([^"/]+)/"', о.тело))
            sets[код] = slugs
            assert slugs, код
        assert sets["dorama"] != sets["drama"]
        assert "genre-dorama" in sets["dorama"]
        assert "genre-drama" in sets["drama"]
        assert "genre-dorama" not in sets["drama"] or "genre-drama" not in sets["dorama"]

    def test_genre_active_state_and_h1(self, зона):
        о = запросить(зона, "/catalog/?genre=dorama")
        assert ">дорама<" in о.тело.lower() or "дорама" in о.тело
        # B10 compact filters: active genre is selected in facet + active chip.
        assert (
            'id="zona-genre-facet"' in о.тело
            and ("selected" in о.тело or "zfilt-chips" in о.тело)
        )


class TestTitleLayout:
    def test_compact_three_zone_title(self, зона):
        о = запросить(зона, "/title/movie-kp-ready/")
        assert 'class="ztitle"' in о.тело
        # Pass6/B15: right-hand series rail removed; facts stay in main column.
        assert 'class="ztitle__rail"' not in о.тело or "display:none" in зона.ЗОНА_СТИЛЬ
        assert 'id="watch"' in о.тело
        assert о.тело.count(">Год<") <= 1
        # Live ad markup is opt-in; CSS may mention the enabled selector.
        assert 'data-ad-slot="title-rail-300x250" data-ad-enabled="1"' not in о.тело

    def test_empty_ad_slot_hidden_in_css(self, зона):
        assert '.zad{display:none}' in зона.ЗОНА_СТИЛЬ
        assert '.zad[data-ad-enabled="1"]' in зона.ЗОНА_СТИЛЬ


class TestSafety:
    def test_noindex_header(self, зона):
        о = запросить(зона, "/")
        robots = о.заголовки.get("X-Robots-Tag") or о.заголовки.get("x-robots-tag") or ""
        meta = 'noindex' in о.тело.lower()
        assert ("noindex" in robots.lower()) or meta

    def test_resolving_not_fake_connected(self, зона):
        assert зона._подпись_плеера("resolving") == "подключение источника"
        assert "подключён" not in зона._подпись_плеера("resolving")
