"""Семейство выпуска определяется и тогда, когда ворота работают от root.

Измерено 2026-10-06 на yummy-site (2dd6b3faf4f7): исполнитель от root получил
от Git `dubious ownership` на рабочей копии `claude`, семейство вышло пустым, и
выпуск Yummy отклонили требованием читателя Animedia/Lords. Здесь Git от root
эмулируется: без `-c safe.directory=<репозиторий>` он отвечает кодом 128.
"""
from __future__ import annotations

import json
import subprocess

import pytest

from factory.cell import protected


def _репозиторий(tmp_path):
    репо = tmp_path / "site"
    (репо / "src").mkdir(parents=True)
    (репо / "config").mkdir()
    (репо / "config" / "site.json").write_text(json.dumps({"entrypoint": "yummy-frontend.py"}))
    (репо / "src" / "yummy-frontend.py").write_text("print('ok')\n")
    def git(*а):
        subprocess.run(["git", *а], cwd=репо, check=True, capture_output=True)
    git("init", "-q")
    git("-c", "user.email=t@t", "-c", "user.name=t", "add", ".")
    git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "x")
    коммит = subprocess.run(["git", "rev-parse", "HEAD"], cwd=репо, capture_output=True,
                            text=True, check=True).stdout.strip()
    return репо, коммит


def _как_root(monkeypatch, репо):
    настоящий = subprocess.run

    def run(cmd, *а, **кв):
        if isinstance(cmd, list) and cmd[:1] == ["git"] and f"safe.directory={репо}" not in " ".join(cmd):
            return subprocess.CompletedProcess(cmd, 128, "", f"fatal: detected dubious ownership in repository at '{репо}'")
        return настоящий(cmd, *а, **кв)

    monkeypatch.setattr(protected.subprocess, "run", run)


def test_семейство_yummy_определяется_от_root(tmp_path, monkeypatch):
    репо, коммит = _репозиторий(tmp_path)
    _как_root(monkeypatch, репо)
    assert protected._адаптер_выпуска(репо, коммит) == "yummy"
    # У Yummy читателя правок в репозитории ячейки нет по устройству семейства.
    assert protected.читатели("editorial", "yummy") == ()


def test_точка_входа_из_дерева_от_root(tmp_path, monkeypatch):
    репо, _ = _репозиторий(tmp_path)
    (репо / "config" / "site.json").write_text("{}")
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qam", "y"],
                   cwd=репо, check=True, capture_output=True)
    коммит = subprocess.run(["git", "rev-parse", "HEAD"], cwd=репо, capture_output=True,
                            text=True, check=True).stdout.strip()
    _как_root(monkeypatch, репо)
    assert protected._адаптер_выпуска(репо, коммит) == "yummy"


def test_нечитаемый_репозиторий_называется_а_не_пустое_семейство(tmp_path, monkeypatch):
    репо, коммит = _репозиторий(tmp_path)

    def run(cmd, *а, **кв):
        return subprocess.CompletedProcess(cmd, 128, "", "fatal: detected dubious ownership")

    monkeypatch.setattr(protected.subprocess, "run", run)
    with pytest.raises(protected.РепозиторийНедоступен):
        protected._адаптер_выпуска(репо, коммит)


def test_неизвестный_отказ_git_не_становится_пустым_семейством(tmp_path, monkeypatch):
    """Перечислять виды поломок Git нельзя — их больше, чем мы знаем.

    Первая версия исправления называла причины НЕДОСТУПНОСТИ (dubious
    ownership, not a git repository, Permission denied) и оставляла ту же дыру
    классом ниже: битый объект, ошибка ввода-вывода или обрезанный pack снова
    проваливались в «семейство пустое». Перечень закрыт у «нет пути», а не у
    «git не ответил».
    """
    import subprocess as _sp

    from factory.cell import protected

    class Ответ:
        returncode = 128
        stdout = ""
        stderr = "fatal: unable to read tree 0123456789abcdef: broken pack"

    monkeypatch.setattr(protected.subprocess, "run", lambda *а, **к: Ответ())
    with pytest.raises(protected.РепозиторийНедоступен, match="не смог прочитать"):
        protected._git_выпуска(tmp_path, "show", "HEAD:config/site.json")


def test_отсутствие_пути_остаётся_законным_ответом(tmp_path, monkeypatch):
    """«Такого файла в коммите нет» — законный ответ, а не недоступность."""
    from factory.cell import protected

    class Ответ:
        returncode = 128
        stdout = ""
        stderr = ("fatal: path 'config/site.json' does not exist in "
                  "'0123456789abcdef'")

    monkeypatch.setattr(protected.subprocess, "run", lambda *а, **к: Ответ())
    r = protected._git_выпуска(tmp_path, "show", "HEAD:config/site.json")
    assert r.returncode == 128
