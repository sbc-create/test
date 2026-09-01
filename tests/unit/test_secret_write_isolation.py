"""Тесты не пишут секреты в боевые пути — проверка самого запрета.

Регрессия к отказу 2026-08-31: прогон `pytest tests/unit` от root переписал
боевые файлы credential стенда Yami маркерами набора тестов. Проверяется не
намерение, а поведение единственной функции, через которую значение секрета
попадает на диск.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

from factory.secret_hub import consumers as consumers_mod
from factory.secret_hub.registry import load as load_config


class TestЗапретНаБоевыеПути:
    def test_запись_во_временный_каталог_разрешена(self, tmp_path):
        цель = tmp_path / "api-token"
        consumers_mod._write_atomically(цель, "значение-теста", 0o600)
        assert цель.read_text(encoding="utf-8") == "значение-теста"

    @pytest.mark.parametrize("боевой", [
        "/srv/sites/yummyani-staging/runtime/cdnvideohub/api-token",
        "/etc/site-factory/secrets/lords/lords-01/api-token",
        "/var/lib/site-factory-secret-hub/store.sqlite3",
    ])
    def test_запись_в_боевой_путь_отклоняется(self, боевой):
        """Ни один из трёх каталогов не должен быть достижим из прогона."""
        with pytest.raises(consumers_mod.ЗаписьСекретаИзТеста) as отказ:
            consumers_mod._write_atomically(Path(боевой), "не-должно-записаться", 0o600)
        assert "отклонена" in str(отказ.value)
        assert "не-должно-записаться" not in str(отказ.value), \
            "сообщение об отказе не имеет права печатать значение"

    def test_запрет_не_зависит_от_учётной_записи(self, monkeypatch):
        """Проверка не смотрит на uid: тест не пишет в боевое ни от кого.

        Отказ 31 августа случился от root, но право записи — следствие. От
        обычного пользователя та же попытка выглядела отказом файловой системы,
        то есть случайностью среды, а не запретом.
        """
        monkeypatch.setattr(os, "geteuid", lambda: 0)
        with pytest.raises(consumers_mod.ЗаписьСекретаИзТеста):
            consumers_mod._write_atomically(
                Path("/srv/sites/yummyani-staging/runtime/cdnvideohub/api-token"),
                "маркер", 0o600)

    def test_вне_прогона_запрет_молчит(self, tmp_path, monkeypatch):
        """Вне тестов функция обязана работать как прежде — иначе сломан выкат."""
        monkeypatch.delitem(sys.modules, "pytest", raising=False)
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
        assert consumers_mod._под_тестом() is False
        цель = tmp_path / "token"
        consumers_mod._write_atomically(цель, "боевое-значение", 0o600)
        assert цель.exists()

    def test_неопределённость_трактуется_как_отказ(self, monkeypatch):
        """fail-closed: не смогли проверить путь — не пишем."""
        def сломать():
            raise OSError("каталог недоступен")

        monkeypatch.setattr(tempfile, "gettempdir", сломать)
        with pytest.raises(consumers_mod.ЗаписьСекретаИзТеста) as отказ:
            consumers_mod._write_atomically(Path("/tmp/что-угодно"), "x", 0o600)
        assert "отклонена" in str(отказ.value)


class TestБоеваяКонфигурацияНедостижима:
    """Реестр направлений указывает на боевые каталоги — и это нормально.

    Ненормально было бы, если бы тест мог применить к ним значения. Проверяется,
    что путь из настоящего `config/secret-hub.json` запретом отклоняется.
    """

    def test_каталоги_реестра_совпадают_с_боевыми(self, repo_root):
        конфиг = load_config(repo_root / "config" / "secret-hub.json")
        каталоги = [
            Path(c.directory)
            for p in конфиг.portfolios for c in p.consumers
            if getattr(c, "directory", None)
        ]
        assert каталоги, "в реестре нет ни одного потребителя с каталогом"
        for каталог in каталоги:
            with pytest.raises(consumers_mod.ЗаписьСекретаИзТеста):
                consumers_mod._write_atomically(каталог / "api-token", "маркер", 0o600)
