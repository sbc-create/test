"""Digest релиза не зависит от umask того, кто собирал.

Дефект, который закрывает этот тест, найден на живом выпуске zona-02: сборка
из чистого clone (umask 022) и сборка из рабочего каталога (umask 002) дали
разные digest при одном и том же коммите и одном и том же содержимом. В архив
попадал полный режим файла, а он приходит от umask.

Свойство, ради которого digest существует, проверяется между машиной сборки и
машиной проверки — и ровно там оно не выполнялось. Прежняя проверка
воспроизводимости этого не ловила: она собирала дважды в одном процессе, то
есть при одном umask.
"""
from __future__ import annotations

import json
import os
import subprocess
import tarfile
from pathlib import Path

from factory.cell import release as release_mod


def _проект(корень: Path, umask: int) -> Path:
    """Проект сайта, разложенный так, как его разложил бы checkout при umask."""
    репо = корень / "site"
    (репо / "config").mkdir(parents=True)
    (репо / "site-manifest.json").write_text(
        json.dumps({"schema_version": "1.0", "site_id": "site-x",
                    "domain": "site-x.test", "template": {}, "modules": []}),
        encoding="utf-8")
    (репо / "pins.lock.json").write_text(
        json.dumps({"pins": {"common_core": "abc123"}}), encoding="utf-8")
    (репо / "config" / "site.json").write_text('{"site_id": "site-x"}', encoding="utf-8")
    (репо / "run.sh").write_text("#!/bin/sh\necho ok\n", encoding="utf-8")
    (репо / "run.sh").chmod(0o755)
    for команда in (["init", "-q", "-b", "main"],
                    ["config", "user.name", "t"], ["config", "user.email", "t@t"],
                    ["add", "-A"], ["commit", "-q", "-m", "init"]):
        subprocess.run(["git", "-C", str(репо), *команда], check=True, capture_output=True)
    for путь in репо.rglob("*"):
        if путь.is_file() and ".git" not in путь.parts:
            исполняемый = путь.stat().st_mode & 0o100
            путь.chmod((0o777 if исполняемый else 0o666) & ~umask)
    return репо


def _собрать(корень: Path, umask: int) -> str:
    прежний = os.umask(umask)
    try:
        репо = _проект(корень, umask)
        return release_mod.build(site_id="site-x", repo=репо,
                                 output_dir=корень / "out").digest
    finally:
        os.umask(прежний)


def test_digest_одинаков_при_разных_umask(tmp_path: Path) -> None:
    строгий = _собрать(tmp_path / "umask-022", 0o022)
    мягкий = _собрать(tmp_path / "umask-002", 0o002)
    assert строгий == мягкий, (
        f"digest зависит от umask: {строгий} против {мягкий}. Две сборки "
        "одного коммита обязаны дать одно значение, иначе digest подтверждает "
        "только момент упаковки, а не «то же ли это самое»."
    )


def test_права_в_архиве_канонические(tmp_path: Path) -> None:
    """В архиве ровно два режима. Значащ один бит — исполняемость."""
    репо = _проект(tmp_path / "canon", 0o022)
    рел = release_mod.build(site_id="site-x", repo=репо, output_dir=tmp_path / "out")
    with tarfile.open(рел.artifact) as архив:
        режимы = {ч.name: ч.mode for ч in архив.getmembers() if ч.isfile()}
    assert set(режимы.values()) <= {0o644, 0o755}, режимы
    assert режимы["run.sh"] == 0o755, "исполняемый бит обязан сохраниться"
    assert режимы["site-manifest.json"] == 0o644
