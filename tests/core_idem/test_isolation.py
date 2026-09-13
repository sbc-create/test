"""Защита от работы испытаний по общему хранилищу.

Проверяется каждый вектор отдельно: совпадение строки, разрешение пути,
inode и каталог. Общий тест «как-нибудь отказало» скрыл бы, что один из
векторов перестал ловиться.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from factory.site_engine.changeset import isolation as I


def test_общий_путь_напрямую_отвергнут():
    with pytest.raises(I.SharedStoreRefused) as ош:
        I.требовать_эфемерное(I.ОБЩЕЕ)
    assert ош.value.признак == "dsn"
    assert ош.value.error_code == "SHARED_STORE_REFUSED"


def test_символическая_ссылка_на_общий_файл_отвергнута(tmp_path):
    ссылка = tmp_path / "link.sqlite3"
    ссылка.symlink_to(I.ОБЩЕЕ)
    with pytest.raises(I.SharedStoreRefused) as ош:
        I.требовать_эфемерное(str(ссылка))
    assert ош.value.признак == "realpath"


def test_жёсткая_ссылка_отвергнута_по_inode(tmp_path, monkeypatch):
    """Разные имена одного файла строкой не различаются.

    Жёсткую ссылку на общий файл создать нельзя без прав, поэтому проверка
    ставится на подставном «общем» файле: важно, что сравнение идёт по
    устройству и inode, а не по имени.
    """
    общий = tmp_path / "shared.sqlite3"
    общий.write_bytes(b"x")
    твёрдая = tmp_path / "hard.sqlite3"
    os.link(общий, твёрдая)
    with pytest.raises(I.SharedStoreRefused) as ош:
        I.требовать_эфемерное(str(твёрдая), общее=str(общий))
    assert ош.value.признак in ("inode", "directory")


def test_сосед_в_каталоге_общего_хранилища_отвергнут():
    with pytest.raises(I.SharedStoreRefused) as ош:
        I.требовать_эфемерное(
            "/srv/site-factory/changeset-store/anything-else.sqlite3")
    assert ош.value.признак == "directory"


def test_незаданный_путь_отвергнут(monkeypatch):
    """Молчаливый возврат к значению по умолчанию — та самая ошибка."""
    monkeypatch.delenv("CHANGESET_DB", raising=False)
    with pytest.raises(I.SharedStoreRefused) as ош:
        I.требовать_эфемерное()
    assert ош.value.признак == "unset"


def test_эфемерный_путь_принимается(tmp_path):
    путь = tmp_path / "cs.sqlite3"
    assert I.требовать_эфемерное(str(путь)) == str(путь.resolve())


def test_эфемерное_окружение_не_правит_процесс(tmp_path):
    было = dict(os.environ)
    окр = I.эфемерное_окружение(tmp_path / "run")
    assert os.environ == было, "окружение процесса изменено"
    assert set(окр) >= {"CHANGESET_DB", "AUDIT_LEDGER_DB", "SEO_SURFACE_DB"}
    for значение in окр.values():
        assert str(tmp_path) in значение
