"""Фикстуры испытаний канонического предложения SEO-контента.

Все хранилища эфемерные. Канонические Registry, ChangeSet Store и Audit
Ledger в этих проверках не участвуют ни на чтение состояния, ни на запись:
подменяется окружение, а не код — работают те же production-классы.
"""
from __future__ import annotations

import pytest

from factory.site_engine.changeset import engine as CE
from factory.site_engine.changeset import store as CS
from factory.site_engine.seo_authoring import подключить_адаптер
from factory.site_engine.seo_authoring.adapter import SeoContentAdapter
from factory.site_engine.seo_authoring.service import (
    ArtifactStore, SeoProposalService)
from factory.site_engine.seo_authoring.testing import (
    DeterministicQwen, FakeRegistry)


@pytest.fixture()
def бд(tmp_path, monkeypatch):
    monkeypatch.setenv("CHANGESET_DB", str(tmp_path / "changesets.sqlite3"))
    monkeypatch.setenv("CHANGESET_APPROVAL_KEY", "arc003-ключ-испытания-0123456789")
    # Связка ключей одобрения требует, чтобы вызывающий назвал себя. Это
    # настройка окружения соседнего потока, а не свойство контура изменений.
    monkeypatch.setenv("APPROVAL_CALLER", "control-plane")
    соед = CS.открыть(tmp_path / "changesets.sqlite3")
    yield соед
    соед.close()


@pytest.fixture()
def реестр():
    return FakeRegistry()


@pytest.fixture()
def артефакты():
    return ArtifactStore()


@pytest.fixture()
def модель():
    return DeterministicQwen()


@pytest.fixture()
def поверхность(tmp_path):
    """Адаптер SEO поверх эфемерного хранилища поверхности."""
    return SeoContentAdapter(tmp_path / "seo-surface.sqlite3")


@pytest.fixture()
def служба(бд, реестр, артефакты):
    return SeoProposalService(бд, реестр=реестр, артефакты=артефакты)


@pytest.fixture()
def двигатель(бд, поверхность, реестр):
    # Требование журнала снимается: доставка в журнал проверяется отдельной
    # suite, а здесь проверяется механизм.
    return CE.Engine(бд, адаптер=поверхность, реестр=реестр,
                     требовать_журнал=False)
