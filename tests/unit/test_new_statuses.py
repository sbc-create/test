"""REQ-STATUS: новые статусы второго blueprint выставляются реально.

Проверяется не «строка существует в коде», а то, что конкретный провал ворот
превращается именно в свой статус: иначе оператор получит общий QA_FAILED и
будет чинить не то.
"""
from __future__ import annotations

import copy
import inspect

import pytest

from factory import pipeline, validation
from factory.seo import uniqueness


def test_duplicate_gate_maps_to_blocked_seo_duplicate():
    """Провал ворот уникальности обязан давать BLOCKED_SEO_DUPLICATE."""
    source = inspect.getsource(pipeline.run_job)
    assert 'c.id == "cross-site-uniqueness"' in source
    assert "BLOCKED_SEO_DUPLICATE" in source
    marker = source.index('duplicate_failed = [c for c in failed')
    assert "BLOCKED_SEO_DUPLICATE" in source[marker:marker + 900], \
        "ветка уникальности не возвращает свой статус"


def test_player_gate_maps_to_blocked_player_contract():
    source = inspect.getsource(pipeline.run_job)
    marker = source.index('player_failed = [c for c in failed')
    assert "BLOCKED_PLAYER_CONTRACT" in source[marker:marker + 900], \
        "ветка контракта плеера не возвращает свой статус"


def test_unconfirmed_publication_rights_block_the_package():
    """Пакет без подтверждённых прав на публикацию получает BLOCKED_CONTENT_RIGHTS."""
    blockers: list = []
    validation._check_publication_rights({"content_source": {"rights_confirmed": False}}, blockers)
    assert blockers, "пакет без подтверждённых прав прошёл проверку"
    assert blockers[0].status == "BLOCKED_CONTENT_RIGHTS"

    ok: list = []
    validation._check_publication_rights({"content_source": {"rights_confirmed": True}}, ok)
    assert not ok, "подтверждённые права не должны блокировать"


def test_duplicate_pages_actually_fail_the_gate():
    """Ворота уникальности действительно краснеют на дубле — иначе статус недостижим."""
    text = "Один и тот же разбор, слово в слово повторённый на другом домене. " * 6
    pages = [
        uniqueness.PageObservation(site_id="a", path="/x/", page_type="title", indexable=True,
                                   title="Одинаково", description="Одинаково", h1="Одинаково",
                                   own_text=text, canonical="https://a/x/"),
        uniqueness.PageObservation(site_id="b", path="/y/", page_type="title", indexable=True,
                                   title="Одинаково", description="Одинаково", h1="Одинаково",
                                   own_text=text, canonical="https://b/y/"),
    ]
    report = uniqueness.check(pages)
    assert not report.passed
    assert {finding.rule for finding in report.critical} & {"CSU-1", "CSU-4"}
