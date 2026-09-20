"""B09 exact episode page order and labeled counts."""
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


def test_exact_episode_order(fe):
    mod, catalog, details = fe
    вид = _вид(mod, catalog, details)
    item = next(з for з in catalog["items"] if з["slug"] == "alpha-anime")
    html = вид.серия(item, details["details"]["alpha-anime"], 1, 3)
    assert 'data-b09="exact"' in html
    h1 = re.search(r'<h1 class="zh zh--ep">(.*?)</h1>', html)
    assert h1 and "1 сезон, 3 серия" in h1.group(1)
    body = html.split('<main id="main">', 1)[-1]
    assert body.find("zh--ep") < body.find('data-b09="player"')
    assert body.find('data-b09="player"') < body.find("zepnav")
    assert body.find("zepnav") < body.find('data-b09="parent"')
    assert "Доступно" in body and "серий" in body


def test_no_abstract_total_label(fe):
    mod, catalog, details = fe
    вид = _вид(mod, catalog, details)
    item = next(з for з in catalog["items"] if з["slug"] == "alpha-anime")
    html = вид.серия(item, details["details"]["alpha-anime"], 1, 2)
    assert not re.search(r"\bВсего\s+\d+\b", html)
