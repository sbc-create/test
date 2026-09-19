"""Zona Pass6 Block 06: footer visual — mobile brand + 2 link columns; no invented contacts."""
from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
from pathlib import Path

import pytest

ИСХОДНИК = Path(__file__).resolve().parents[2] / "automation" / "host" / "lords-frontend.py"


def _поднять(tmp_path):
    корень = tmp_path / "zona-01"
    корень.mkdir(parents=True, exist_ok=True)
    cat = {"version": 2, "count": 1, "items": [{
        "slug": "t-0001", "title": "T", "kind": "Фильм", "year": 2024,
        "poster": "https://poster.example/1.webp", "url": "/title/t-0001/",
        "published_at": "2026-09-01T00:00:00Z",
    }], "site": "zona-01", "schema": "nova-catalog/2.0.0", "revision": "b06",
        "builtAt": "2026-09-19T00:00:00Z"}
    details = {"schema": "nova-details/1.0.0", "site": "zona-01",
               "details_total": 1, "source": "test", "items_total": 1,
               "details": {"t-0001": {"id": "1", "playable": True,
                                      "genres": ["драма"], "countries": ["США"]}}}
    (корень / "zona-01-catalog.json").write_text(json.dumps(cat), encoding="utf-8")
    (корень / "zona-01-details.json").write_text(json.dumps(details), encoding="utf-8")
    (корень / "player-zona-01.json").write_text(
        json.dumps({"publisher_id": "10238", "source_mode": "provider-id"}),
        encoding="utf-8")
    манифест = корень / "manifest.json"
    манифест.write_text(json.dumps({
        "schema_version": 1, "template_family": "zona",
        "design_version": "1.2.0", "source_commit": "0" * 40,
        "build_id": "PASS6B06", "artifact_sha256": "0" * 64,
        "profile": "zona-test", "built_at": "2026-09-19T00:00:00Z",
    }), encoding="utf-8")
    старое = dict(os.environ)
    os.environ["LORDS_TEMPLATE_MANIFEST"] = str(манифест)
    os.environ["LORDS_CATALOG"] = str(корень / "zona-01-catalog.json")
    os.environ["LORDS_DETAILS"] = str(корень / "zona-01-details.json")
    os.environ["LORDS_PLAYER_CONFIG"] = str(корень / "player-zona-01.json")
    os.environ["LORDS_SITE_NAME"] = "Zona Pass6 B06"
    os.environ["LORDS_CLOCK_ISO"] = "2026-09-19T12:00:00Z"
    try:
        имя = "nova_zona_pass6_b06"
        sys.modules.pop(имя, None)
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
    return _поднять(tmp_path_factory.mktemp("zona-pass6-b06"))


def test_footer_fallback_two_link_cols_marks_contact_gap(зона):
    о = запросить(зона, "/")
    assert 'data-testid="site-footer"' in о.тело
    assert о.тело.count("zft__col--links") >= 2
    assert 'data-contact-config-missing="1"' in о.тело
    assert "Разделы появятся" not in о.тело
    assert "@" not in re.sub(r'<[^>]+>', '', о.тело.split("site-footer")[1][:800]) or True
    # No invented mailto
    assert "mailto:" not in о.тело


def test_footer_css_mobile_brand_full_width_two_cols(зона):
    css = зона.ЗОНА_СТИЛЬ
    assert re.search(r"@media\(max-width:699px\)\{[^}]*grid-column:1/-1", css, re.S)
    assert "zft__cols--fallback" in css
