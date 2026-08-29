"""Разделение двух разрешений: сбор статистики и правовая публикация.

Счётчик на публичном домене, который владелец явно назвал, и объявление сайта
production с указанием правообладателя — разные решения. Раньше они были одним:
поле `environment` держало и то и другое, поэтому отсутствие юридических
сведений выключало явно разрешённый счётчик на живом сайте.

Ослабления защиты здесь нет. Список разрешённых hostname остаётся главным
предохранителем: он не даёт собирать статистику ни с копии сайта, ни с чужого
домена, и разрешение на сбор его не отменяет — это проверяется отдельно.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from factory.analytics import client_codegen
from factory.analytics.snippet import analytics_script_tag

LORDS_SITES = {
    "lords-01": ("lordfilm47.space", 112010269),
    "lords-02": ("lordserial33.biz", 112010274),
    "lords-03": ("1lordserials1.online", 112010277),
}


def tag(**overrides):
    params = dict(
        counter_id=112010269,
        allowed_hosts=["lordfilm47.space"],
        environment="staging",
        enabled=True,
    )
    params.update(overrides)
    return analytics_script_tag(**params)


# -- сервер ------------------------------------------------------------------

def test_authorized_collection_emits_the_tag_outside_production():
    """Владелец разрешил счётчик на публичном домене — тег обязан появиться."""
    markup = tag(collection_authorized=True)
    assert 'data-counter-id="112010269"' in markup
    assert markup.startswith("<script")


def test_without_authorization_staging_stays_silent():
    """Поведение по умолчанию не меняется: без явного разрешения тега нет."""
    assert tag() == ""
    assert tag(collection_authorized=False) == ""


def test_authorization_does_not_bypass_the_host_allowlist():
    """Разрешение на сбор не разрешает собирать с произвольного домена."""
    assert tag(collection_authorized=True, allowed_hosts=[]) == ""


def test_authorization_does_not_revive_a_disabled_counter():
    assert tag(collection_authorized=True, enabled=False) == ""
    assert tag(collection_authorized=True, counter_id=None) == ""


def test_authorization_is_reported_to_the_client():
    assert 'data-collection-authorized="true"' in tag(collection_authorized=True)


def test_production_still_works_without_the_new_flag():
    assert 'data-counter-id="112010269"' in tag(environment="production")


# -- клиент ------------------------------------------------------------------

def test_client_honours_authorization_and_still_checks_hostname():
    source = client_codegen.render_js()
    assert "collectionAuthorized" in source, "клиент обязан читать разрешение"
    assert "data-collection-authorized" in source
    # Проверка hostname остаётся: без неё копия сайта слала бы визиты в тот же счётчик.
    assert "allowedHosts.indexOf(hostname)" in source


def test_client_never_enables_webvisor():
    assert "webvisor: false" in client_codegen.render_js()


# -- пакеты ------------------------------------------------------------------

@pytest.mark.parametrize("site_id", sorted(LORDS_SITES))
def test_lords_packages_authorize_their_own_counter(site_id):
    from factory.paths import PATHS

    package = yaml.safe_load(PATHS.site_package(site_id).read_text(encoding="utf-8"))
    domain, counter = LORDS_SITES[site_id]
    analytics = package.get("analytics") or {}
    assert package.get("domain") == domain
    assert analytics.get("counter_id") == counter
    assert analytics.get("enabled") is True
    assert analytics.get("collection_authorized") is True, "владелец разрешил счётчик на этом домене"
    # Подпись разрешения в пакет не пишется: владелец разрешил изменить ровно
    # один флаг, и добавлять рядом ещё одно поле от его имени значило бы выйти
    # за границы данного разрешения. След разрешения живёт в истории изменений.
    assert analytics.get("allowed_hosts") == [domain], "собственный домен и ничей больше"
    assert analytics.get("webvisor") in (None, False)


def test_no_foreign_counter_appears_in_any_lords_package():
    from factory.paths import PATHS

    every = {c for _, c in LORDS_SITES.values()}
    for site_id, (_, counter) in LORDS_SITES.items():
        package = yaml.safe_load(PATHS.site_package(site_id).read_text(encoding="utf-8"))
        found = (package.get("analytics") or {}).get("counter_id")
        assert found == counter
        assert found not in (every - {counter}), "чужой счётчик в пакете"


def test_legal_fields_are_still_not_invented():
    """Разделение гейтов не должно превратиться в выдумывание правообладателя."""
    from factory.paths import PATHS

    for site_id in LORDS_SITES:
        package = yaml.safe_load(PATHS.site_package(site_id).read_text(encoding="utf-8"))
        legal = package.get("legal") or {}
        assert not legal.get("owner"), "правообладатель неизвестен и выдуман быть не может"
        assert not legal.get("documents"), "юридические документы неизвестны"
