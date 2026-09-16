"""Артефакт шаблона собирается в чужом дереве без доверия к нему.

Дефект LORDS-RELEASE-ADOPT-GIT-PRIVILEGED-33. Фаза `switch` идёт от root, а
рабочее дерево принадлежит `claude`. `git archive` в такой связке отказывается
работать с каталогом чужого владельца: `adopt` не собирал архив, манифест не
записывался, и выкладка откатывалась уже после подмены ссылки — при полностью
целой трёхчасовой отрисовке.

Лечение — понижение прав, а не `safe.directory`: привилегированный процесс не
начинает доверять чужому дереву, он перестаёт быть привилегированным на время
чтения. Проверки ниже закрепляют именно это направление, потому что обратное
(root доверяет чужому каталогу) выглядит работающим и снимает защиту молча.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from factory.lords import template_artifact as та


@pytest.fixture()
def репозиторий(tmp_path: Path) -> Path:
    корень = tmp_path / "repo"
    корень.mkdir()

    def git(*args: str) -> str:
        return subprocess.run(["git", "-C", str(корень), *args],
                              capture_output=True, text=True, check=True).stdout.strip()

    git("init", "-q")
    git("config", "user.email", "release@example.invalid")
    git("config", "user.name", "release")
    (корень / "файл.txt").write_text("содержимое\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "-m", "первый")
    return корень


def _ревизия(корень: Path) -> str:
    return subprocess.run(["git", "-C", str(корень), "rev-parse", "HEAD"],
                          capture_output=True, text=True, check=True).stdout.strip()


class TestРешениеОПонижении:
    def test_непривилегированный_процесс_права_не_понижает(self, репозиторий):
        добавка, объяснение = та.понижение_прав(репозиторий)
        assert добавка == {}
        assert "не root" in объяснение

    def test_root_в_своём_дереве_понижать_не_к_кому(self, репозиторий, monkeypatch):
        monkeypatch.setattr(os, "geteuid", lambda: 0)
        настоящий = os.stat

        class _Стат:
            st_uid = 0

        monkeypatch.setattr(os, "stat", lambda путь, *a, **k: (
            _Стат() if str(путь) == str(репозиторий) else настоящий(путь, *a, **k)))
        добавка, объяснение = та.понижение_прав(репозиторий)
        assert добавка == {}
        assert "root" in объяснение

    def test_root_в_чужом_дереве_переходит_под_владельца(self, репозиторий, monkeypatch):
        """Ровно тот случай, который ронял выкладку."""
        monkeypatch.setattr(os, "geteuid", lambda: 0)
        настоящий = os.stat
        мой = os.getuid()

        class _Стат:
            st_uid = мой

        monkeypatch.setattr(os, "stat", lambda путь, *a, **k: (
            _Стат() if str(путь) == str(репозиторий) else настоящий(путь, *a, **k)))
        добавка, объяснение = та.понижение_прав(репозиторий)
        assert "preexec_fn" in добавка, "понижение прав не подготовлено"
        assert callable(добавка["preexec_fn"])
        assert str(мой) in объяснение and "не от root" in объяснение

    def test_недоступное_дерево_называется_отказом_а_не_молчанием(self, tmp_path, monkeypatch):
        monkeypatch.setattr(os, "geteuid", lambda: 0)
        with pytest.raises(та.ArtifactError):
            та.понижение_прав(tmp_path / "нет-такого-дерева")


class TestСборкаАрхива:
    def test_обычный_путь_не_сломан(self, репозиторий, tmp_path):
        цель = tmp_path / "хранилище" / "архив.tar.gz"
        собрано = та.собрать(репозиторий, _ревизия(репозиторий), цель)
        assert цель.is_file() and цель.stat().st_size > 0
        assert len(собрано["digest"]) == 64
        assert собрано["revision"] == _ревизия(репозиторий)

    def test_отпечаток_совпадает_с_файлом(self, репозиторий, tmp_path):
        цель = tmp_path / "архив.tar.gz"
        собрано = та.собрать(репозиторий, _ревизия(репозиторий), цель)
        from factory.lords.release_manifest import отпечаток_файла
        assert собрано["digest"] == отпечаток_файла(цель)

    def test_ветка_вместо_полного_sha_отвергается(self, репозиторий, tmp_path):
        """Артефакт «из ветки» через день означал бы другое содержимое."""
        with pytest.raises(та.ArtifactError):
            та.собрать(репозиторий, "main", tmp_path / "архив.tar.gz")

    def test_временный_файл_не_остаётся_после_отказа(self, репозиторий, tmp_path):
        цель = tmp_path / "архив.tar.gz"
        with pytest.raises(та.ArtifactError):
            та.собрать(репозиторий, "0" * 40, цель)
        assert not цель.exists()
        assert not цель.with_suffix(цель.suffix + ".tmp").exists()
