"""Zona PASS2 regressions: search phrase ranking, playback states, description."""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

ИСХОДНИК = Path(__file__).resolve().parents[2] / "automation" / "host" / "lords-frontend.py"


def _каталог() -> dict:
    items = [
        {"slug": "zvezdnye-voyny-1", "title": "Звёздные войны", "kind": "Фильм",
         "year": 1977, "poster": "https://poster.example/a.webp",
         "url": "/title/zvezdnye-voyny-1/", "published_at": "2026-01-01T00:00:00Z"},
        {"slug": "zvezdnye-voyny-empire", "title": "Звёздные войны: Империя наносит ответный удар",
         "kind": "Фильм", "year": 1980, "poster": "https://poster.example/b.webp",
         "url": "/title/zvezdnye-voyny-empire/", "published_at": "2026-01-02T00:00:00Z"},
        {"slug": "voy", "title": "Вой", "kind": "Фильм", "year": 2010,
         "poster": "https://poster.example/c.webp", "url": "/title/voy/",
         "published_at": "2026-01-03T00:00:00Z"},
        {"slug": "voy-2", "title": "Вой", "kind": "Фильм", "year": 2022,
         "poster": "https://poster.example/d.webp", "url": "/title/voy-2/",
         "published_at": "2026-01-04T00:00:00Z"},
        {"slug": "voyna-shery", "title": "Война Шеры", "kind": "Сериал", "year": 2021,
         "poster": "https://poster.example/e.webp", "url": "/title/voyna-shery/",
         "published_at": "2026-01-05T00:00:00Z"},
        {"slug": "v-lovushke", "title": "В ловушке", "kind": "Фильм", "year": 2024,
         "poster": "https://poster.example/f.webp", "url": "/title/v-lovushke/",
         "published_at": "2026-01-06T00:00:00Z"},
        {"slug": "film-short-long", "title": "Фильм с кратким и полным", "kind": "Фильм",
         "year": 2023, "poster": "https://poster.example/g.webp",
         "url": "/title/film-short-long/", "published_at": "2026-01-07T00:00:00Z"},
        {"slug": "film-only-full", "title": "Фильм только с полным", "kind": "Фильм",
         "year": 2023, "poster": "https://poster.example/h.webp",
         "url": "/title/film-only-full/", "published_at": "2026-01-08T00:00:00Z"},
    ]
    return {"version": 2, "count": len(items), "items": items, "site": "zona-01",
            "schema": "nova-catalog/2.0.0", "revision": "pass2",
            "builtAt": "2026-09-19T00:00:00Z"}


def _подробности() -> dict:
    long_a = ("А" * 50 + " Это полный синопсис первого фильма. " + "Б" * 50) * 3
    long_b = ("А" * 50 + " Это полный синопсис второго фильма. " + "В" * 50) * 3
    return {
        "schema": "nova-details/1.0.0", "site": "zona-01", "details_total": 8,
        "source": "test", "items_total": 8,
        "details": {
            "zvezdnye-voyny-1": {
                "id": "019e0001-0000-0000-0000-000000000001",
                "description": "Сага о джедаях.",
                "sources": [{"provider": "kp", "source_id": "1",
                             "availability_status": "available"}],
                "external_ids": {"kp": "1"},
            },
            "zvezdnye-voyny-empire": {
                "id": "019e0001-0000-0000-0000-000000000002",
                "description": "Продолжение саги.",
                "sources": [{"provider": "kp", "source_id": "2",
                             "availability_status": "available"}],
                "external_ids": {"kp": "2"},
            },
            "voy": {
                "id": "019e0001-0000-0000-0000-000000000003",
                "sources": [{"provider": "kp", "source_id": "3",
                             "availability_status": "available"}],
                "external_ids": {"kp": "3"},
            },
            "voy-2": {
                "id": "019e0001-0000-0000-0000-000000000004",
                "description": long_a,
                "short_description": "",
                "sources": [{"provider": "kp", "source_id": "4",
                             "availability_status": "available"}],
                "external_ids": {"kp": "4"},
            },
            "voyna-shery": {
                "id": "019e0001-0000-0000-0000-000000000005",
                "sources": [{"provider": "kp", "source_id": "5",
                             "availability_status": "available"}],
                "external_ids": {"kp": "5"}, "seasons": [{"n": 1, "eps": 2, "avail": 2}],
            },
            "v-lovushke": {
                "id": "019eb600-0b8b-7998-9439-37cdbcd5f718",
                "sources": [{"provider": "kp", "source_id": "12733648",
                             "availability_status": "available"}],
                "external_ids": {"kp": "12733648", "imdb": "28002547"},
            },
            "film-short-long": {
                "id": "019e0001-0000-0000-0000-000000000007",
                "short_description": "Коротко о фильме.",
                "description": long_b,
                "sources": [{"provider": "kp", "source_id": "7",
                             "availability_status": "available"}],
                "external_ids": {"kp": "7"},
            },
            "film-only-full": {
                "id": "019e0001-0000-0000-0000-000000000008",
                "description": long_a,
                "sources": [{"provider": "kp", "source_id": "8",
                             "availability_status": "available"}],
                "external_ids": {"kp": "8"},
            },
        },
    }


def _поднять(tmp_path):
    корень = tmp_path / "zona-01"
    корень.mkdir(parents=True, exist_ok=True)
    (корень / "zona-01-catalog.json").write_text(
        json.dumps(_каталог(), ensure_ascii=False), encoding="utf-8")
    (корень / "zona-01-details.json").write_text(
        json.dumps(_подробности(), ensure_ascii=False), encoding="utf-8")
    (корень / "player-zona-01.json").write_text(
        json.dumps({"publisher_id": "10238", "source_mode": "provider-id"}),
        encoding="utf-8")
    манифест = корень / "manifest.json"
    манифест.write_text(json.dumps({
        "schema_version": 1, "template_family": "zona",
        "design_version": "1.2.0", "source_commit": "0" * 40,
        "build_id": "PASS2", "artifact_sha256": "0" * 64,
        "profile": "zona-test", "built_at": "2026-09-19T00:00:00Z",
    }), encoding="utf-8")
    прежние = dict(sys.modules)
    старое = dict(os.environ)
    os.environ["LORDS_TEMPLATE_MANIFEST"] = str(манифест)
    os.environ["LORDS_CATALOG"] = str(корень / "zona-01-catalog.json")
    os.environ["LORDS_DETAILS"] = str(корень / "zona-01-details.json")
    os.environ["LORDS_PLAYER_CONFIG"] = str(корень / "player-zona-01.json")
    os.environ["LORDS_SITE_NAME"] = "Zona Pass2"
    try:
        имя = "nova_zona_pass2"
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
    модуль.Обработчик.подробности = модуль.Подробности(str(корень / "zona-01-details.json"))
    модуль.Обработчик.индекс = модуль.построить_индекс(
        модуль.Обработчик.данные, модуль.Обработчик.подробности)
    return модуль


def запросить(модуль, путь: str):
    from tests.lords.test_nova_frontend_families import запросить as _з
    return _з(модуль, путь)


@pytest.fixture(scope="module")
def зона(tmp_path_factory):
    return _поднять(tmp_path_factory.mktemp("zona-pass2"))


class TestUnicodeTokens:
    def test_yot_not_split(self, зона):
        assert зона.токены("звездные войны") == ["звездные", "войны"]
        assert зона.нормализовать("Вой") == "вой"
        assert зона.нормализовать("войны") == "войны"


class TestSearchRanking:
    def test_star_wars_phrase_before_voy(self, зона):
        res = зона.Обработчик.данные.искать("звездные войны", предел=20)
        titles = [z["title"] for z in res]
        assert titles[0].startswith("Звёздные войны") or titles[0].startswith("Звездные войны")
        top5 = titles[:5]
        assert "Вой" not in top5
        assert "Война Шеры" not in top5

    def test_yo_and_punctuation(self, зона):
        a = [z["slug"] for z in зона.Обработчик.данные.искать("ЗВЁЗДНЫЕ — войны", предел=10)]
        b = [z["slug"] for z in зона.Обработчик.данные.искать("звездные войны", предел=10)]
        assert a[0] == b[0]

    def test_single_token_voy_still_finds_voy(self, зона):
        res = зона.Обработчик.данные.искать("вой", предел=10)
        assert any(z["slug"].startswith("voy") for z in res)

    def test_search_page_heading(self, зона):
        о = запросить(зона, "/search/?q=%D0%B7%D0%B2%D0%B5%D0%B7%D0%B4%D0%BD%D1%8B%D0%B5%20%D0%B2%D0%BE%D0%B9%D0%BD%D1%8B")
        assert "Результаты поиска:" in о.тело
        assert 'value="' in о.тело or "value='" in о.тело


class TestDescriptionContract:
    def test_no_same_page_full_duplicate(self, зона):
        о = запросить(зона, "/title/film-only-full/")
        assert 'id="synopsis"' in о.тело
        assert 'data-expand-plot' in о.тело
        # Full text once in hero clamp — not repeated after player.
        assert о.тело.count('id="synopsis"') == 1
        assert 'data-expand-plot' in о.тело
        # Fixture repeats the phrase inside one description string (*3); ensure
        # it is not duplicated as a second visible SEO block after the player.
        after_player = о.тело.split('id="watch"', 1)[-1]
        assert "Это полный синопсис первого фильма" not in after_player.split("<script", 1)[0]

    def test_distinct_short_in_hero(self, зона):
        о = запросить(зона, "/title/film-short-long/")
        assert "Коротко о фильме." in о.тело
        assert 'data-expand-plot' in о.тело or 'id="synopsis"' in о.тело
        main = о.тело.split('<main id="main">', 1)[-1].split('id="watch"', 1)[0]
        assert "Коротко о фильме." in main


class TestPlayerContract:
    def test_user_message_no_provider_jargon(self, зона):
        assert "Видео временно недоступно" in зона.СКРИПТ_ПЛЕЕРА_КЛИЕНТ
        assert "Провайдер не отдал" not in зона.СКРИПТ_ПЛЕЕРА_КЛИЕНТ
        assert "nextOrFail" in зона.СКРИПТ_ПЛЕЕРА_КЛИЕНТ
        assert "postMessage" in зона.СКРИПТ_ПЛЕЕРА_КЛИЕНТ or "addEventListener('message'" in зона.СКРИПТ_ПЛЕЕРА_КЛИЕНТ

    def test_playing_via_provider_postmessage(self, зона):
        assert "eventType" in зона.СКРИПТ_ПЛЕЕРА_КЛИЕНТ
        assert "timeupdate" in зона.СКРИПТ_ПЛЕЕРА_КЛИЕНТ
        assert "player.cdnvideohub.com" in зона.СКРИПТ_ПЛЕЕРА_КЛИЕНТ

    def test_playing_not_shadow_ready(self, зона):
        assert "shadowRoot)||node.children" not in зона.СКРИПТ_ПЛЕЕРА_КЛИЕНТ

    def test_player_stage_css(self, зона):
        assert "aspect-ratio:16/9" in зона.ЗОНА_СТИЛЬ
        assert "max-width:1200px" in зона.ЗОНА_СТИЛЬ
        assert "position:absolute;inset:0" in зона.ЗОНА_СТИЛЬ.replace("\n", "")

    def test_imdb_not_playback_candidate(self, зона):
        д = {
            "id": "019eb600-0b8b-7998-9439-37cdbcd5f718",
            "sources": [{"provider": "kp", "source_id": "12733648",
                         "availability_status": "available"}],
            "external_ids": {"kp": "12733648", "imdb": "28002547"},
        }
        c = зона.кандидаты_источника(д)
        assert c[0] == ("kp", "12733648")
        assert all(a != "imdb" for a, _ in c)

    def test_banner_disabled(self, зона):
        о = запросить(зона, "/title/v-lovushke/")
        assert 'is-show-banner="false"' in о.тело

    def test_v_lovushke_candidates_prefer_kp(self, зона):
        д = зона.Обработчик.подробности.get("v-lovushke")
        c = зона.кандидаты_источника(д)
        assert c[0] == ("kp", "12733648")

    def test_footer_four_zones(self, зона):
        о = запросить(зона, "/")
        assert "Разделы" in о.тело
        assert "Помощь" in о.тело or "Документы" in о.тело
        assert "Zona ·" in о.тело

    def test_sticky_offset(self, зона):
        assert "padding-top:88px" in зона.ЗОНА_СТИЛЬ or "padding-top:93px" in зона.ЗОНА_СТИЛЬ
