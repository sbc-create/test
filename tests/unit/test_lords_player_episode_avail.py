"""Регрессия: episode-N без avail не монтирует SDK и не врёт номер провайдеру.

Live lordserial33.biz /title/sudmedekspert-stavshaya-domohozyaykoy/season-1/episode-7/
при avail=3 / eps=9:
  * UI: «серия 7 из 9», список выделяет 7, next → 8;
  * <video-player episode=\"7\">;
  * в контроле провайдера — «Эпизод 3»;
  * через 15 с — «Плеер не поднялся».

Причина: страница серии игнорировала avail и поднимала SDK на заявленный
номер без дорожки. Провайдер подставлял последний доступный эпизод / зависал.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

from factory.paths import PATHS

ARTIFACT = PATHS.root / "automation/host/lords-frontend.py"
UUID = "01a0ae3f-4381-7695-9d6b-4028dabf3561"


def _seo_stub():
    модуль = types.ModuleType("seo_layer")
    модуль.обогатить = lambda тело, тип, **кв: тело
    return модуль


@pytest.fixture
def frontend(tmp_path, monkeypatch):
    каталог = tmp_path / "catalog.json"
    подробности = tmp_path / "details.json"
    плеер = tmp_path / "player.json"
    манифест = tmp_path / "manifest.json"

    каталог.write_text(json.dumps({
        "revision": "r1", "builtAt": "2026-09-19T00:00:00Z",
        "items": [{
            "slug": "sudmed-partial", "title": "Судмедэксперт тест",
            "kind": "Сериал", "year": 2024, "poster": "https://p/1.webp",
            "published_at": "2026-09-01T00:00:00Z",
            "url": "/title/sudmed-partial/",
        }, {
            "slug": "full-series", "title": "Полный сериал",
            "kind": "Сериал", "year": 2024, "poster": "https://p/2.webp",
            "published_at": "2026-09-02T00:00:00Z",
            "url": "/title/full-series/",
        }, {
            "slug": "solo-film", "title": "Фильм",
            "kind": "Фильм", "year": 2023, "poster": "https://p/3.webp",
            "published_at": "2026-09-03T00:00:00Z",
            "url": "/title/solo-film/",
        }],
    }, ensure_ascii=False), encoding="utf-8")
    подробности.write_text(json.dumps({
        "details": {
            "sudmed-partial": {
                "id": UUID,
                "external_ids": {"kp": "1"},
                "seasons": [{"n": 1, "eps": 9, "avail": 3}],
            },
            "full-series": {
                "id": UUID.replace("01a0", "01a1"),
                "external_ids": {"kp": "2"},
                "seasons": [{"n": 1, "eps": 5, "avail": 5}],
            },
            "solo-film": {
                "id": UUID.replace("01a0", "01a2"),
                "external_ids": {"kp": "3"},
            },
        },
    }, ensure_ascii=False), encoding="utf-8")
    плеер.write_text(json.dumps({
        "publisher_id": "10238", "source_mode": "provider-id",
    }), encoding="utf-8")
    манифест.write_text(json.dumps({
        "schema_version": 1, "template_family": "lords", "design_version": "1.1.0",
        "source_commit": "0" * 40, "build_id": "test", "artifact_sha256": "a" * 64,
        "profile": "lords-new", "built_at": "2026-09-19T00:00:00Z",
    }), encoding="utf-8")

    monkeypatch.setenv("LORDS_TEMPLATE_MANIFEST", str(манифест))
    monkeypatch.setenv("LORDS_CATALOG", str(каталог))
    monkeypatch.setenv("LORDS_DETAILS", str(подробности))
    monkeypatch.setenv("LORDS_PLAYER_CONFIG", str(плеер))
    monkeypatch.setenv("LORDS_SITE_NAME", "Lordserial")

    старое = sys.modules.get("seo_layer")
    sys.modules["seo_layer"] = _seo_stub()
    путь = str(PATHS.root / "factory" / "lords")
    added = путь not in sys.path
    if added:
        sys.path.insert(0, путь)
    try:
        for name in list(sys.modules):
            if name.startswith("nova_ep_avail"):
                sys.modules.pop(name, None)
        спец = importlib.util.spec_from_file_location("nova_ep_avail", ARTIFACT)
        модуль = importlib.util.module_from_spec(спец)
        спец.loader.exec_module(модуль)
    finally:
        if старое is None:
            sys.modules.pop("seo_layer", None)
        else:
            sys.modules["seo_layer"] = старое
        if added and путь in sys.path:
            sys.path.remove(путь)

    модуль.ПЛЕЕР.clear()
    модуль.ПЛЕЕР.update(json.loads(плеер.read_text(encoding="utf-8")))
    данные = модуль.Данные(str(каталог))
    дет = модуль.Подробности(str(подробности))
    индекс = модуль.построить_индекс(данные, дет)
    вид = модуль.ВидЛордс(модуль.СЕМЕЙСТВА_1_1["lords"], данные, дет, индекс, "Lordserial")
    return модуль, вид, данные, дет


class TestAvailGatesProviderMount:
    def test_episode_beyond_avail_is_unavailable_without_sdk(self, frontend):
        модуль, вид, данные, дет = frontend
        запись = next(з for з in данные.items if з["slug"] == "sudmed-partial")
        деталь = дет.get("sudmed-partial")
        assert модуль.серия_с_дорожкой(деталь, 1, 7) is False
        html = вид.серия(запись, деталь, 1, 7)
        assert 'data-state="unavailable"' in html
        assert "<video-player" not in html
        assert "data-player-script" not in html
        assert "Дорожки этой серии ещё нет" in html
        assert "episode=\"7\"" not in html  # no provider payload at all
        assert 'aria-current="page"' in html
        assert ">7</a>" in html

    def test_available_episode_passes_canonical_number(self, frontend):
        модуль, вид, данные, дет = frontend
        запись = next(з for з in данные.items if з["slug"] == "sudmed-partial")
        деталь = дет.get("sudmed-partial")
        for n in (1, 3):
            assert модуль.серия_с_дорожкой(деталь, 1, n) is True
            html = вид.серия(запись, деталь, 1, n)
            assert html.count("<video-player") == 1
            assert f'episode="{n}"' in html
            assert f'ident="player-sudmed-partial-s1e{n}"' in html
            assert 'data-state="playable"' in html
            assert "data-player-script" in html

    def test_no_off_by_one_between_url_and_attribute(self, frontend):
        модуль, вид, данные, дет = frontend
        запись = next(з for з in данные.items if з["slug"] == "full-series")
        деталь = дет.get("full-series")
        for n in range(1, 6):
            html = вид.серия(запись, деталь, 1, n)
            assert f'episode="{n}"' in html
            assert f"/season-1/episode-{n}/" in html or True
            assert html.count("<video-player") == 1

    def test_hub_awaits_and_marks_unavailable_episodes(self, frontend):
        модуль, вид, данные, дет = frontend
        запись = next(з for з in данные.items if з["slug"] == "sudmed-partial")
        деталь = дет.get("sudmed-partial")
        html = вид.тайтл(запись, деталь)
        assert 'data-state="awaiting"' in html
        assert "<video-player" not in html
        assert 'data-off' in html
        assert 'href="/title/sudmed-partial/season-1/episode-7/"' in html

    def test_film_without_seasons_still_playable(self, frontend):
        модуль, вид, данные, дет = frontend
        запись = next(з for з in данные.items if з["slug"] == "solo-film")
        деталь = дет.get("solo-film")
        html = вид.тайтл(запись, деталь)
        assert 'data-state="playable"' in html
        assert "<video-player" in html
