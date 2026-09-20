"""B04 schedule honest empty — BLOCKWISE-PARITY-03."""
from __future__ import annotations

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


def test_home_has_no_schedule_block(fe):
    mod, catalog, details = fe
    html = _вид(mod, catalog, details).главная()
    body = html.split("<main", 1)[-1]
    assert "Сегодня выйдет" not in body
    assert 'data-b04="populated"' not in body
    assert 'data-b04="empty"' not in body


def test_schedule_route_honest_empty(fe):
    mod, catalog, details = fe
    html = _вид(mod, catalog, details).расписание()
    assert 'data-b04="empty"' in html
    assert "Расписание пока недоступно" in html
    assert "ещё не подключен" in html
    assert "sched__d" not in html
    assert "max-height:260px" in mod.АНИМЕДИА_СТИЛЬ
