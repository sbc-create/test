"""Регрессия: плеер «пропадает» на новинках при рассинхроне catalog/details.

На lordserial33.biz 2026-09-18 каталог обновился в 20:45, а sidecar
подробностей остался от 04:06. Тридцать пять slug главной открывали
`data-state=nosource` без `<video-player>`. Посетитель воспринимал это как
«плеера нет».

Контракт после фикса:
  * главная «Новинки» берёт только записи с playable-источником в details;
  * сериал на хабе тайтла — `awaiting` без `<video-player>` и без скрипта;
  * после выбора серии — ровно один `<video-player>` и скрипт провайдера.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import types
from pathlib import Path

import pytest

from factory.paths import PATHS

ARTIFACT = PATHS.root / "automation/host/lords-frontend.py"
UUID = "01915254-4513-7657-ad4b-d75fae15b061"


def _seo_stub():
    модуль = types.ModuleType("seo_layer")
    модуль.обогатить = lambda тело, тип, **кв: тело
    return модуль


@pytest.fixture
def frontend(tmp_path, monkeypatch):
    каталог = tmp_path / "lords-02-catalog.json"
    подробности = tmp_path / "lords-02-details.json"
    плеер = tmp_path / "player-lords-02.json"
    манифест = tmp_path / "manifest.json"

    каталог.write_text(json.dumps({
        "revision": "catalog-new",
        "builtAt": "2026-09-18T20:45:03Z",
        "items": [
            {"slug": "new-no-details", "title": "Новинка без sidecar",
             "kind": "Сериал", "year": 2026, "poster": "https://p/1.webp",
             "published_at": "2026-09-18T20:00:00Z", "url": "/title/new-no-details/"},
            {"slug": "ready-series", "title": "Готовый сериал",
             "kind": "Сериал", "year": 2023, "poster": "https://p/2.webp",
             "published_at": "2026-09-17T10:00:00Z", "url": "/title/ready-series/"},
            {"slug": "ready-film", "title": "Готовый фильм",
             "kind": "Фильм", "year": 2024, "poster": "https://p/3.webp",
             "published_at": "2026-09-16T10:00:00Z", "url": "/title/ready-film/"},
        ],
    }, ensure_ascii=False), encoding="utf-8")
    подробности.write_text(json.dumps({
        "catalog_revision": "catalog-old",
        "catalog_built_at": "2026-09-18T03:19:01Z",
        "details_total": 2,
        "details": {
            "ready-series": {
                "id": UUID,
                "external_ids": {"kp": "1"},
                "seasons": [{"n": 1, "eps": 3, "avail": 3}],
            },
            "ready-film": {
                "id": UUID.replace("0191", "0192"),
                "external_ids": {"kp": "2"},
            },
        },
    }, ensure_ascii=False), encoding="utf-8")
    плеер.write_text(json.dumps({
        "publisher_id": "10238", "source_mode": "provider-id",
    }), encoding="utf-8")
    манифест.write_text(json.dumps({
        "schema_version": 1, "template_family": "lords", "design_version": "1.1.0",
        "source_commit": "0" * 40, "build_id": "test", "artifact_sha256": "a" * 64,
        "profile": "lords-new", "built_at": "2026-09-18T00:00:00Z",
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
        # reload artifact fresh for env
        for name in list(sys.modules):
            if name.startswith("nova_player_skew"):
                sys.modules.pop(name, None)
        спец = importlib.util.spec_from_file_location("nova_player_skew", ARTIFACT)
        модуль = importlib.util.module_from_spec(спец)
        спец.loader.exec_module(модуль)
    finally:
        if старое is None:
            sys.modules.pop("seo_layer", None)
        else:
            sys.modules["seo_layer"] = старое
        if added and путь in sys.path:
            sys.path.remove(путь)

    данные = модуль.Данные(str(каталог))
    дет = модуль.Подробности(str(подробности))
    # player config was read at import — force reload from our file
    модуль.ПЛЕЕР.clear()
    модуль.ПЛЕЕР.update(json.loads(плеер.read_text(encoding="utf-8")))
    индекс = модуль.построить_индекс(данные, дет)
    вид = модуль.ВидЛордс(модуль.СЕМЕЙСТВА_1_1["lords"], данные, дет, индекс, "Lordserial")
    return модуль, вид, данные, дет


def test_home_novelties_skip_titles_without_details(frontend):
    модуль, вид, данные, дет = frontend
    свежие = модуль.новинки_с_источником(данные, дет, 12)
    slugs = [з["slug"] for з in свежие]
    assert "new-no-details" not in slugs
    assert "ready-series" in slugs
    assert "ready-film" in slugs
    html = вид.главная()
    assert "/title/new-no-details/" not in html
    assert "/title/ready-series/" in html


def test_series_hub_awaits_episode_without_video_player(frontend):
    модуль, вид, данные, дет = frontend
    запись = next(з for з in данные.items if з["slug"] == "ready-series")
    деталь = дет.get("ready-series")
    html = вид.тайтл(запись, деталь)
    assert 'data-state="awaiting"' in html
    assert "<video-player" not in html
    assert "data-player-script" not in html
    assert "Выберите серию" in html
    assert 'href="/title/ready-series/season-1/episode-1/"' in html


def test_episode_page_mounts_single_video_player(frontend):
    модуль, вид, данные, дет = frontend
    запись = next(з for з in данные.items if з["slug"] == "ready-series")
    деталь = дет.get("ready-series")
    html = вид.серия(запись, деталь, 1, 1)
    assert html.count("<video-player") == 1
    assert 'episode="1"' in html
    assert "data-player-script" in html
    assert 'data-state="playable"' in html


def test_film_title_mounts_player_without_episode_gate(frontend):
    модуль, вид, данные, дет = frontend
    запись = next(з for з in данные.items if з["slug"] == "ready-film")
    деталь = дет.get("ready-film")
    html = вид.тайтл(запись, деталь)
    assert "<video-player" in html
    assert 'data-state="playable"' in html
    assert "awaiting" not in html


def test_missing_details_diagnoses_sidecar_gap(frontend):
    модуль, вид, данные, дет = frontend
    запись = next(з for з in данные.items if з["slug"] == "new-no-details")
    html = вид.тайтл(запись, дет.get("new-no-details"))
    assert 'data-state="nosource"' in html
    assert "Подробности записи ещё не в снимке" in html
    assert "<video-player" not in html
