"""Zona PASS3: overlay hidden CSS, state machine, home density, episodes."""
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
    items = [
        {"slug": "chasha-vesny", "title": "Чаша весны", "kind": "Сериал", "year": 2024,
         "poster": "https://poster.example/a.webp", "url": "/title/chasha-vesny/",
         "published_at": "2026-01-01T00:00:00Z"},
        {"slug": "film-a", "title": "Фильм А", "kind": "Фильм", "year": 2023,
         "poster": "https://poster.example/b.webp", "url": "/title/film-a/",
         "published_at": "2026-01-02T00:00:00Z"},
    ]
    return {"version": 2, "count": len(items), "items": items, "site": "zona-01",
            "schema": "nova-catalog/2.0.0", "revision": "pass3",
            "builtAt": "2026-09-19T00:00:00Z"}


def _подробности() -> dict:
    return {
        "schema": "nova-details/1.0.0", "site": "zona-01", "details_total": 2,
        "source": "test", "items_total": 2,
        "details": {
            "chasha-vesny": {
                "id": "019e0001-0000-0000-0000-000000000101",
                "description": ("Длинное описание сериала. " * 40).strip(),
                "original_name": "Spring Cup",
                "genres": ["драма", "мелодрама"],
                "genre_codes": ["drama", "melodrama"],
                "countries": ["Китай"],
                "sources": [{"provider": "kp", "source_id": "100",
                             "availability_status": "available"}],
                "external_ids": {"kp": "100"},
                "seasons": [{"n": 1, "eps": 30, "avail": 6}],
            },
            "film-a": {
                "id": "019e0001-0000-0000-0000-000000000102",
                "description": "Короткий фильм.",
                "sources": [{"provider": "kp", "source_id": "101",
                             "availability_status": "available"}],
                "external_ids": {"kp": "101"},
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
        "build_id": "PASS3", "artifact_sha256": "0" * 64,
        "profile": "zona-test", "built_at": "2026-09-19T00:00:00Z",
    }), encoding="utf-8")
    прежние = dict(sys.modules)
    старое = dict(os.environ)
    os.environ["LORDS_TEMPLATE_MANIFEST"] = str(манифест)
    os.environ["LORDS_CATALOG"] = str(корень / "zona-01-catalog.json")
    os.environ["LORDS_DETAILS"] = str(корень / "zona-01-details.json")
    os.environ["LORDS_PLAYER_CONFIG"] = str(корень / "player-zona-01.json")
    os.environ["LORDS_SITE_NAME"] = "Zona Pass3"
    try:
        имя = "nova_zona_pass3"
        спец = importlib.util.spec_from_file_location(имя, ИСХОДНИК)
        модуль = importlib.util.module_from_spec(спец)
        sys.modules[имя] = модуль
        спец.loader.exec_module(модуль)
    finally:
        os.environ.clear()
        os.environ.update(старое)
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
    return _поднять(tmp_path_factory.mktemp("zona-pass3"))


class TestOverlayHidden:
    def test_css_hidden_overrides_grid(self, зона):
        assert ".zpl__s[hidden]" in зона.ЗОНА_СТИЛЬ
        assert "display:none!important" in зона.ЗОНА_СТИЛЬ.replace(" ", "")

    def test_state_machine_guards(self, зона):
        s = зона.СКРИПТ_ПЛЕЕРА_КЛИЕНТ
        assert "generation" in s and "attempt" in s
        assert "hideOverlay" in s
        assert "ev.source" in s
        assert "playing && (k==='provider'" in s or "playing && (k==='provider'" in s.replace(" ","")
        assert "setProperty('display','none','important')" in s


class TestHomeDensity:
    def test_no_per_genre_shelves(self, зона):
        о = запросить(зона, "/")
        # Заголовок секции сократился до «Жанры» в более позднем проходе;
        # смысл теста — отсутствие отдельной полки на каждый жанр — не менялся.
        assert 'id="zgenres-h">Жанры</h2>' in о.тело
        # genre nav links present; no shelf titled just a genre as mega-row requirement
        assert о.тело.count('class="zsec"') <= 10
        assert "записей" not in о.тело.lower() or "В снимке" not in о.тело
        assert "утверждённого снимка каталога" not in о.тело

    def test_scrollbar_hidden(self, зона):
        assert "scrollbar-width:none" in зона.ЗОНА_СТИЛЬ
        assert "::-webkit-scrollbar{display:none" in зона.ЗОНА_СТИЛЬ.replace("\n", "")


class TestTitleEpisodes:
    def test_episode_grid_numbers(self, зона):
        о = запросить(зона, "/title/chasha-vesny/")
        assert 'class="zeps"' in о.тело
        assert ">7</span>" in о.тело or 'aria-disabled="true"' in о.тело
        assert "Серия заявлена, видео пока недоступно" in о.тело
        # available eps are links
        assert 'aria-label="Серия 1"' in о.тело
        assert "1 сезон(ов)" not in о.тело

    def test_description_in_hero_once(self, зона):
        о = запросить(зона, "/title/chasha-vesny/")
        assert о.тело.count("Длинное описание сериала") >= 1
        assert 'data-expand-plot' in о.тело
        assert о.тело.count('id="synopsis"') == 1
        # no second "О чём это" block after player
        assert о.тело.count("О чём это") == 0


class TestFooterGate:
    def test_contact_config_missing_marker(self, зона):
        о = запросить(зона, "/")
        assert 'data-contact-config-missing="1"' in о.тело
        assert "admin@zona.plus" not in о.тело
        # Маркер версии в подвале запрещён правилом владельца (B22).
        assert 'data-footer-technical-marker="0"' in о.тело
        assert "Zona · 1.2.0 ·" not in о.тело
        assert "Zona · v1.2.0 ·" not in о.тело


class TestPlayerRegression:
    def test_playing_blocks_error_overlay(self, зона):
        s = зона.СКРИПТ_ПЛЕЕРА_КЛИЕНТ
        assert "if(playing && (k==='provider'" in s.replace(" ", "") or (
            "playing && (k==='provider'" in s)

    def test_stale_generation_ignored(self, зона):
        s = зона.СКРИПТ_ПЛЕЕРА_КЛИЕНТ
        assert "myGen!==generation" in s
        assert "ev.source" in s

    def test_fallback_mounts_next(self, зона):
        s = зона.СКРИПТ_ПЛЕЕРА_КЛИЕНТ
        assert "mountAt(idx+1)" in s or "mountAt(idx + 1)" in s
        assert "destroy()" in s

    def test_single_active_player_mount(self, зона):
        s = зона.СКРИПТ_ПЛЕЕРА_КЛИЕНТ
        assert "destroy()" in s
        assert "createElement('video-player')" in s


class TestCollectionsHub:
    def test_no_public_internal_counts(self, зона):
        о = запросить(зона, "/collections/")
        assert "записей" not in о.тело.lower() or "53524" not in о.тело
        # Hub may be empty in tiny fixture; home must not leak snapshot jargon.
        home = запросить(зона, "/")
        assert "утверждённого снимка каталога" not in home.тело


class TestGenreNav:
    def test_action_chip_present(self, зона):
        о = запросить(зона, "/")
        assert "боевик" in о.тело
        assert "genre=action" in о.тело or "genre%3Daction" in о.тело or "genre=action" in о.тело.replace("&amp;", "&")
