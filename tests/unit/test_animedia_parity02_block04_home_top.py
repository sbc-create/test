"""BLOCK_04: home top shelf order and empty ad collapse."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tests.unit.test_animedia_visual_finalization import _load, _вид  # noqa: E402


@pytest.fixture
def fe(tmp_path):
    return _load(tmp_path, version="1.2.4")


def test_hero_before_h1(fe):
    mod, catalog, details = fe
    html = _вид(mod, catalog, details).главная()
    ahero = html.find('class="ahero"')
    h1 = html.find('class="zh zh--home"')
    assert ahero > 0 and h1 > ahero


def test_empty_ad_slots_collapsed_css(fe):
    mod, _, _ = fe
    css = mod.АНИМЕДИА_СТИЛЬ
    assert ".zad-home" in css
    assert "height:0" in css


def test_no_invented_telegram_url(fe):
    mod, catalog, details = fe
    html = _вид(mod, catalog, details).главная()
    assert "t.me/" not in html
    assert "telegram.me/" not in html
    assert 'href="#"' not in html
