"""Мост из выпуска (MOD-198): опознание кода и токен доверия.

* В выпуске `git -C` по каталогу выпуска не годится: коммит берётся из
  SEO_RELEASE_COMMIT, а каталог выпуска не выдаётся за рабочее дерево.
* Токен доверия пишет мост и читает клиент bridge_call.py — оба от одного
  корня SEO_STATE_ROOT, иначе редактор молча терял бы права проверяющей стороны.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from factory.qwen import mcp

КОПИЯ = Path(__file__).resolve().parents[2]


def test_выпуск_называет_коммит_источника_а_не_дерево(monkeypatch):
    monkeypatch.setenv("SEO_RELEASE_COMMIT", "0123456789abcdef")
    в = mcp._версия_кода()
    assert в["commit"] == "0123456789ab" and в["worktree"] is None and в["release"]


def test_без_переменной_прежнее_поведение(monkeypatch):
    monkeypatch.delenv("SEO_RELEASE_COMMIT", raising=False)
    в = mcp._версия_кода()
    assert в["worktree"] == str(КОПИЯ) and "release" not in в


def test_токен_мост_и_клиент_читают_из_одного_корня(monkeypatch, tmp_path):
    monkeypatch.delenv("FACTORY_BRIDGE_TRUSTED_TOKEN_FILE", raising=False)
    monkeypatch.delenv("FACTORY_BRIDGE_TRUSTED_TOKEN", raising=False)
    monkeypatch.setenv("SEO_STATE_ROOT", str(tmp_path))
    assert mcp.путь_токена() == tmp_path / "var" / "bridge-trusted-token"
    (tmp_path / "var").mkdir()
    (tmp_path / "var" / "bridge-trusted-token").write_text("проба\n", encoding="utf-8")
    # bridge_call.py исполняет вызов на верхнем уровне, поэтому функция токена
    # берётся из текста модуля без сетевого вызова.
    текст = (КОПИЯ / "automation" / "local" / "bridge_call.py").read_text(encoding="utf-8")
    начало = текст.index("def токен()")
    конец = текст.index("\n\n\n", начало)
    проба = ("import os, pathlib\n__file__ = %r\n" % str(КОПИЯ / "automation" / "local" / "bridge_call.py")
             + текст[начало:конец] + "\nprint(токен())\n")
    r = subprocess.run([sys.executable, "-c", проба], capture_output=True, text=True,
                       env={**os.environ, "SEO_STATE_ROOT": str(tmp_path)}, timeout=30)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "проба"
