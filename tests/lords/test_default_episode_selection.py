"""Default episode selection on generic series title routes.

Regression locked by LORDS-DEFAULT-EPISODE hotfix:

* episodes present ⇒ selected episode is non-null after SSR
* `data-state=awaiting` / «Выберите серию» must not appear when seasons exist
* hub and exact episode routes share the same descriptor contract for S1E1
* canonical order is first playable, never last-available / API array order
"""

from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import re
import sys

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ИСХОДНИК = КОРЕНЬ / "automation" / "host" / "lords-frontend.py"
if str(ИСХОДНИК.parent) not in sys.path:
    sys.path.insert(0, str(ИСХОДНИК.parent))


def _каталог() -> dict:
    return {
        "version": 2,
        "count": 3,
        "items": [
            {
                "slug": "pylnye-utesy",
                "title": "Пыльные утёсы",
                "kind": "Сериал",
                "year": 2026,
                "poster": "https://poster.example/dusty.webp",
                "url": "/title/pylnye-utesy/",
                "published_at": "2026-09-01T00:00:00Z",
                "published_at_estimated": False,
            },
            {
                "slug": "multi-season",
                "title": "Много сезонов",
                "kind": "Сериал",
                "year": 2024,
                "poster": "https://poster.example/multi.webp",
                "url": "/title/multi-season/",
                "published_at": "2026-09-02T00:00:00Z",
                "published_at_estimated": False,
            },
            {
                "slug": "film-playable",
                "title": "Играющий фильм",
                "kind": "Фильм",
                "year": 2023,
                "poster": "https://poster.example/film.webp",
                "url": "/title/film-playable/",
                "published_at": "2026-09-03T00:00:00Z",
                "published_at_estimated": False,
            },
        ],
        "fields_absent": ["genres"],
        "site": "lords-01",
        "schema": "nova-catalog/2.0.0",
        "revision": "test",
        "builtAt": "2026-09-19T00:00:00Z",
    }


def _подробности() -> dict:
    return {
        "schema": "nova-details/1.0.0",
        "site": "lords-01",
        "details_total": 3,
        "source": "test",
        "items_total": 3,
        "details": {
            "pylnye-utesy": {
                "id": "01a0b620-fef9-7b30-8e8a-0d068c6fe870",
                "description": "Синтетический сериал с тремя сериями.",
                "original_name": "Dusty Bluffs",
                "countries": ["США"],
                "genres": ["комедия"],
                "genre_codes": ["comedy"],
                "seasons": [{"n": 1, "eps": 3, "avail": 3}],
                "seasons_count": 1,
                "external_ids": {"imdb": "29253644"},
                "is_series": True,
            },
            "multi-season": {
                "id": "01999999-aaaa-bbbb-cccc-ddddeeeeffff",
                "description": "Два сезона.",
                "seasons": [
                    {"n": 2, "eps": 2, "avail": 2},
                    {"n": 1, "eps": 4, "avail": 4},
                ],
                "external_ids": {"kp": "424242"},
                "is_series": True,
            },
            "film-playable": {
                "id": "0191511d-84b5-71de-91aa-9f28e25c0ec7",
                "description": "Фильм без сезонов.",
                "external_ids": {"kp": "111"},
                "is_series": False,
            },
        },
    }


def _поднять(tmp_path, *, source_mode: str = "provider-id"):
    корень = tmp_path / "site"
    корень.mkdir(parents=True, exist_ok=True)
    (корень / "lords-01-catalog.json").write_text(
        json.dumps(_каталог(), ensure_ascii=False), encoding="utf-8")
    (корень / "lords-01-details.json").write_text(
        json.dumps(_подробности(), ensure_ascii=False), encoding="utf-8")
    манифест = корень / "manifest.json"
    манифест.write_text(json.dumps({
        "schema_version": 1,
        "template_family": "lords",
        "design_version": "1.1.0",
        "source_commit": "0" * 40,
        "build_id": "TEST-DEFAULT-EP",
        "artifact_sha256": "0" * 64,
        "profile": "lords-test",
        "built_at": "2026-09-19T00:00:00Z",
    }, ensure_ascii=False), encoding="utf-8")
    (корень / "player-lords-01.json").write_text(
        json.dumps({"publisher_id": "10238", "source_mode": source_mode}),
        encoding="utf-8")

    прежние = dict(sys.modules)
    старое = dict(os.environ)
    os.environ["LORDS_TEMPLATE_MANIFEST"] = str(манифест)
    os.environ["LORDS_CATALOG"] = str(корень / "lords-01-catalog.json")
    os.environ["LORDS_SITE_NAME"] = "Lordfilm"
    os.environ.pop("LORDS_DETAILS", None)
    os.environ.pop("LORDS_PLAYER_CONFIG", None)
    try:
        имя = f"nova_default_ep_{tmp_path.name}"
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
    модуль.Обработчик.данные = модуль.Данные(str(корень / "lords-01-catalog.json"))
    модуль.Обработчик.подробности = модуль.Подробности(str(корень / "lords-01-details.json"))
    модуль.Обработчик.индекс = модуль.построить_индекс(
        модуль.Обработчик.данные, модуль.Обработчик.подробности)
    return модуль


def запросить(модуль, путь: str):
    собрано = {"статус": 200, "тело": b"", "заголовки": {}}

    class Заглушка(модуль.Обработчик):
        def __init__(self):
            self.path = путь
            self.command = "GET"
            self.headers = {"Host": "lordfilm47.space"}

        def _отдать(self, тело, тип="text/html; charset=utf-8", код=200):
            собрано["статус"] = код
            собрано["тело"] = тело
            собрано["заголовки"]["Content-Type"] = тип

        def send_response(self, код):
            собрано["статус"] = код

        def send_header(self, имя, значение):
            собрано["заголовки"][имя] = значение

        def end_headers(self):
            pass

    Заглушка().do_GET()
    return собрано["статус"], собрано["тело"].decode("utf-8") if собрано["тело"] else ""


@pytest.fixture
def витрина(tmp_path):
    return _поднять(tmp_path)


class TestВыборПоУмолчанию:
    def test_первая_playable_а_не_последняя(self, витрина):
        деталь = витрина.Обработчик.подробности.get("pylnye-utesy")
        assert витрина.выбрать_доступную_серию(деталь) == (1, 1)

    def test_мультисезон_канонический_первый(self, витрина):
        деталь = витрина.Обработчик.подробности.get("multi-season")
        assert витрина.выбрать_доступную_серию(деталь) == (1, 1)

    def test_непоследовательные_номера_сезонов(self, витрина):
        деталь = {"seasons": [
            {"n": 5, "eps": 2, "avail": 2},
            {"n": 2, "eps": 3, "avail": 3},
        ]}
        assert витрина.выбрать_доступную_серию(деталь) == (2, 1)

    def test_первая_серия_недоступна_берётся_следующий_сезон(self, витрина):
        """S1 без avail, S2 playable → S2E1, не слепой episode=1 сезона 1."""
        деталь = {"seasons": [
            {"n": 1, "eps": 4, "avail": 0},
            {"n": 2, "eps": 3, "avail": 3},
        ]}
        assert витрина.выбрать_доступную_серию(деталь) == (2, 1)

    def test_устаревший_default_id_не_нужен_fallback_детерминирован(self, витрина):
        деталь = {
            "seasons": [
                {"n": 3, "eps": 1, "avail": 0},
                {"n": 1, "eps": 2, "avail": 0},
            ],
        }
        assert витрина.выбрать_доступную_серию(деталь) == (1, 1)

    def test_нет_playable_и_released(self, витрина):
        деталь = {"seasons": [{"n": 1, "eps": 0, "avail": 0}]}
        сезон, эпизод = витрина.выбрать_доступную_серию(деталь)
        assert сезон == 1 and эпизод is None


class TestGenericSeriesHub:
    def test_episodes_present_forbids_null_selection(self, витрина):
        """episodes.length > 0 ⇒ selectedEpisodeId != null (awaiting forbidden)."""
        статус, тело = запросить(витрина, "/title/pylnye-utesy/")
        assert статус == 200
        assert 'data-player data-state="awaiting"' not in тело
        assert "Выберите серию" not in тело
        assert "До выбора серии запросов к провайдеру нет" not in тело
        assert тело.count("<video-player") == 1
        assert 'episode="1"' in тело
        assert 'season="1"' in тело
        assert 'aria-current="page"' in тело

    def test_hub_and_exact_episode_share_descriptor(self, витрина):
        _, hub = запросить(витрина, "/title/pylnye-utesy/")
        _, ep = запросить(витрина, "/title/pylnye-utesy/season-1/episode-1/")
        hub_agg = re.search(r'data-aggregator="([^"]+)"', hub)
        ep_agg = re.search(r'data-aggregator="([^"]+)"', ep)
        hub_id = re.search(r'data-title-id="([^"]+)"', hub)
        ep_id = re.search(r'data-title-id="([^"]+)"', ep)
        assert hub_agg and ep_agg and hub_agg.group(1) == ep_agg.group(1)
        assert hub_id and ep_id and hub_id.group(1) == ep_id.group(1)
        assert hub_agg.group(1) == "cvh"
        assert hub_id.group(1) == "01a0b620-fef9-7b30-8e8a-0d068c6fe870"

    def test_exact_s2e2_not_overwritten_by_hub_default(self, витрина):
        статус, тело = запросить(витрина, "/title/multi-season/season-2/episode-2/")
        assert статус == 200
        assert 'episode="2"' in тело
        assert 'season="2"' in тело
        assert 'data-player data-state="awaiting"' not in тело

    def test_movie_skips_episode_prompt(self, витрина):
        статус, тело = запросить(витрина, "/title/film-playable/")
        assert статус == 200
        assert "Выберите серию" not in тело
        assert тело.count("<video-player") == 1
        assert 'data-player data-state="awaiting"' not in тело


class TestRegressionNullSelection:
    def test_resolver_never_returns_null_when_avail_positive(self, витрина):
        деталь = {"seasons": [{"n": 1, "eps": 3, "avail": 3}]}
        сезон, эпизод = витрина.выбрать_доступную_серию(деталь)
        assert сезон is not None
        assert эпизод is not None
        assert витрина.ждёт_выбора_серии(
            {"kind": "Сериал", "slug": "x"}, деталь, эпизод) is False


class TestPlayerContractGuards:
    def test_single_player_instance_on_hub(self, витрина):
        _, тело = запросить(витрина, "/title/pylnye-utesy/")
        assert тело.count("<video-player") == 1
        # CSS also mentions the attribute name; count the mount element only.
        assert тело.count("<div data-player-host") == 1

    def test_no_autoplay_attribute(self, витрина):
        _, тело = запросить(витрина, "/title/pylnye-utesy/")
        assert "autoplay" not in тело.lower()

    def test_client_script_ignores_late_response(self, витрина):
        скрипт = витрина.СКРИПТ_ПЛЕЕРА_КЛИЕНТ
        assert "token" in скрипт
        assert "my!==token" in скрипт or "my !== token" in скрипт

    def test_client_script_single_host_mount(self, витрина):
        скрипт = витрина.СКРИПТ_ПЛЕЕРА_КЛИЕНТ
        assert "querySelector('[data-player]')" in скрипт
        assert "querySelectorAll('[data-player]')" not in скрипт

    def test_hub_skips_blind_episode_one_when_s1_empty(self, витрина):
        деталь = {"seasons": [
            {"n": 1, "eps": 2, "avail": 0},
            {"n": 2, "eps": 2, "avail": 2},
        ]}
        assert витрина.выбрать_доступную_серию(деталь) == (2, 1)
