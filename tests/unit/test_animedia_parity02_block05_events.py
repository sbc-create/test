"""BLOCK_05: catalog-publish feed honesty; no invented episode air schedule."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tests.unit.test_animedia_home_pagination import (  # noqa: E402
    _ids,
    _load,
    _вид,
)
from tests.unit.test_animedia_visual_finalization import (  # noqa: E402
    _load as _load_visual,
    _вид as _вид_visual,
)


FORBIDDEN_AIR_LABELS = (
    "вышла серия",
    "вышел эпизод",
    "сегодня выйдет",
    "расписание выхода",
)


@pytest.fixture()
def fe(tmp_path):
    return _load(tmp_path, n_titles=25)


@pytest.fixture()
def fe_visual(tmp_path):
    return _load_visual(tmp_path, version="1.2.4")


def test_home_b03_empty_not_catalog_fallback(fe):
    mod, items, details = fe
    вид = _вид(mod, items, details)
    home = вид.главная()
    assert mod.АНИМЕДИА_ЭПИЗОД_ЗАГОЛОВОК == "Новые серии аниме"
    assert "Новые серии аниме" in home
    assert 'data-b03="empty"' in home
    assert "источник событий ещё не подключён" in home
    assert mod.АНИМЕДИА_EPISODE_EVENT_DATA_GAP == 1
    assert mod.TRUE_PROVIDER_PLAYABLE_EVENT_COUNT == 0
    low = home.lower()
    for label in FORBIDDEN_AIR_LABELS:
        assert label not in low


def test_space_h1_not_episode_air_claim(fe_visual):
    mod, catalog, details = fe_visual
    html = _вид_visual(mod, catalog, details, host="animedia.space").главная()
    assert "Новое в каталоге и популярное аниме" in html
    assert "Новые серии и популярное" not in html


def test_events_are_catalog_publish_not_air(fe):
    mod, items, details = fe
    вид = _вид(mod, items, details)
    events = вид._эпизод_события()
    assert events
    true_air = [e for e in events if e.get("event_kind") == "episode_air"]
    assert len(true_air) == 0
    for e in events:
        assert e["event_kind"] == "catalog_publish"
        assert "not episode air" in e["timestamp_semantics"]


def test_schedule_empty_state_honest(fe):
    mod, items, details = fe
    вид = _вид(mod, items, details)
    html = вид.расписание()
    assert "Расписание пока недоступно" in html
    assert "новое в каталоге" in html.lower()
    assert "новые эпизоды" not in html.lower()
    assert re.search(r'href="/new/"', html)


def test_pagination_sample_and_invalid_404(fe):
    mod, items, details = fe
    вид = _вид(mod, items, details)
    events = вид._эпизод_события()
    p1 = _ids(вид.список("/new", {}))
    p2 = _ids(вид.список("/new", {"page": ["2"]}))
    assert set(p1).isdisjoint(p2)
    mid = max(2, len(events) // (2 * 10))
    last = (len(events) + 9) // 10
    mid_ids = _ids(вид.список("/new", {"page": [str(mid)]}))
    last_ids = _ids(вид.список("/new", {"page": [str(last)]}))
    assert mid_ids
    assert last_ids
    bad = вид.список("/new", {"page": [str(last + 5)]})
    assert getattr(вид, "_http_status", 200) == 404
    assert "не найдена" in bad.lower() or "404" in bad
