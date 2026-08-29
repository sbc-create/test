"""Тег аналитики обязан ссылаться на существующий файл.

Счётчик может быть верным, тег единственным, разрешение выданным — и при этом
не отправляться ни разу, если `/assets/analytics.js` в релизе нет. Ровно так и
было на трёх живых доменах: тег стоял, файл отдавал 404, обращений к Метрике
ноль. Наличие кода на странице успехом не считается.
"""
from __future__ import annotations

import re

import pytest
import yaml

from factory.lords import fixtures as fx
from factory.lords import render
from factory.paths import PATHS

SITES = ("lords-01", "lords-02", "lords-03")


def package(site_id: str) -> dict:
    return yaml.safe_load(PATHS.site_package(site_id).read_text(encoding="utf-8"))


@pytest.mark.parametrize("site_id", SITES)
def test_the_referenced_analytics_asset_actually_exists(site_id):
    site = render.render_site(package(site_id), catalog=fx.build_catalog())
    home = site.pages["/"].body
    referenced = re.findall(r'<script src="([^"]+)"[^>]*data-analytics-provider', home)
    assert referenced, "тег аналитики не встроился"
    for path in referenced:
        assert path in site.pages, f"тег ссылается на {path}, которого в релизе нет"
        assert site.pages[path].body.strip(), f"{path} пуст"


@pytest.mark.parametrize("site_id", SITES)
def test_the_shipped_client_carries_the_authorization_branch(site_id):
    site = render.render_site(package(site_id), catalog=fx.build_catalog())
    body = site.pages["/assets/analytics.js"].body
    assert "collectionAuthorized" in body, "выложен клиент без поддержки разрешения"
    assert "data-collection-authorized" in body
    # Проверка hostname обязана остаться: без неё копия сайта слала бы визиты
    # в тот же счётчик.
    assert "allowedHosts.indexOf(hostname)" in body
    assert "webvisor: false" in body


def test_the_asset_is_not_shipped_when_analytics_is_off():
    """Ненужный файл в релиз не кладём."""
    pkg = package("lords-01")
    pkg = {**pkg, "analytics": {**(pkg.get("analytics") or {}), "enabled": False}}
    site = render.render_site(pkg, catalog=fx.build_catalog())
    assert "/assets/analytics.js" not in site.pages
