"""B01 shared shell/header/taxonomy gates — ANIMEDIA-BLOCKWISE-PARITY-03."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tests.unit.test_animedia_visual_finalization import _load, _вид  # noqa: E402

EV = ROOT / "artifacts/evidence/animedia-blockwise-parity-03-2026-09-20"
CONTRACT_SHA = (EV / "00-contract" / "CONTRACT_SHA256.txt").read_text(encoding="utf-8").strip()


@pytest.fixture
def fe(tmp_path):
    return _load(tmp_path, version="1.2.4")


def test_contract_digest_unchanged() -> None:
    assert CONTRACT_SHA == "5f2112e25ef974333c388bad405abfae3c3d460a713b028afa3c0e549b8eaeb3"


def test_nav_registry_links_only(fe):
    mod, catalog, details = fe
    html = _вид(mod, catalog, details).главная()
    header = html.split("</header>", 1)[0]
    assert 'href="/schedule/"' in header
    assert "Расписание" in header
    assert "Каталог" in header
    assert "Новое в каталоге" in header
    assert "Подборки" in header
    assert "Главная" in header
    # Top-100 route absent from B00 registry → must not render
    assert "Топ-100" not in header and "Топ‑100" not in header
    assert 'href="/new/?page=1"' not in header
    assert 'id="zhd-nav"' in header
    assert 'class="zhd__n"' in header


def test_taxonomy_counts_and_no_empty(fe):
    mod, catalog, details = fe
    html = _вид(mod, catalog, details).главная()
    assert 'class="zhd__cnt"' in html
    assert 'data-tax-toggle="genre"' in html
    assert 'data-tax-toggle="type"' in html
    assert 'href="/new/"' in html


def test_breadcrumb_uses_catalog_not_kind_aliases(fe):
    mod, catalog, details = fe
    html = _вид(mod, catalog, details).тайтл(
        catalog["items"][0], details["details"]["alpha-anime"]
    )
    assert 'class="zcr"' in html
    assert 'href="/catalog/"' in html
    assert 'href="/series/"' not in html
    assert 'href="/movies/"' not in html
    assert 'aria-current="page"' in html


def test_geometry_css_tokens(fe):
    mod, _, _ = fe
    css = mod.АНИМЕДИА_СТИЛЬ
    assert "min-width:280px" in css and "max-width:360px" in css
    assert "min-width:120px" in css and "max-width:155px" in css
    assert "min(360px,calc(100vw - 24px))" in css
    assert "min-width:min(720px" in css or "min-width:min(720px," in css
    assert "max-width:960px" in css
    assert ".zcr{" in css
    assert "max-height:72px" in css
    assert "max-height:88px" not in css


def test_drawer_a11y_script(fe):
    mod, _, _ = fe
    s = mod.СКРИПТ_АНИМЕДИА_ШАПКА
    assert "Escape" in s
    assert "zhd-lock" in s
    assert "lastFocus" in s
    assert "data-drawer-backdrop" in s


def test_parity02_header_still_passes(fe):
    mod, catalog, details = fe
    html = _вид(mod, catalog, details).главная()
    assert 'class="zhd__tax"' in html
    assert 'id="zhd-drawer"' in html
    assert "Premium" not in html
    assert 'href="#"' not in html
