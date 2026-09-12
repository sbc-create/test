"""Фикстуры испытаний контура изменений.

Всё разрушающее выполняется на эфемерных базах и детерминированном адаптере.
Канонические Registry и Audit Ledger здесь не участвуют ни на чтение, ни на
запись.
"""
from __future__ import annotations

import pytest

from factory.site_engine.changeset import engine as E
from factory.site_engine.changeset import store as S
from factory.site_engine.changeset.fake_adapter import FakeAdapter
from factory.site_engine.changeset.testing import FakeRegistry


@pytest.fixture()
def бд(tmp_path, monkeypatch):
    monkeypatch.setenv("CHANGESET_DB", str(tmp_path / "changesets.sqlite3"))
    # Подпись проверяется НАСТОЯЩИМ путём: эфемерные ключи в каталоге
    # credentials и живая служба подписи. Заглушка проверяла бы не то, что
    # работает в контуре.
    from factory.site_engine.approval import testing as ПОДПИСЬ_ТЕСТ
    with ПОДПИСЬ_ТЕСТ.эфемерный_signer(tmp_path / "credentials", monkeypatch):
        соед = S.открыть(tmp_path / "changesets.sqlite3")
        yield соед
        соед.close()


@pytest.fixture()
def адаптер(tmp_path):
    return FakeAdapter(tmp_path / "fake.sqlite3")


@pytest.fixture()
def реестр():
    return FakeRegistry()


@pytest.fixture()
def двигатель(бд, адаптер, реестр):
    # Требование журнала снимается только здесь: проверяется механизм, а не
    # доставка в журнал. Для неё есть отдельные испытания.
    return E.Engine(бд, адаптер=адаптер, реестр=реестр, требовать_журнал=False)
