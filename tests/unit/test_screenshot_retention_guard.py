"""Правило хранения снимков проверяется, а не объявляется памяткой.

Повод измеренный, 23.10: 25 579 изображений на 10,01 ГиБ, 84 % — одни и те же
снимки приёмки, размноженные по каждому каталогу релиза и каждой рабочей копии;
из-за места встала суточная публикация каталогов (MOD-144). Памятка этого не
предотвращает: копит сборка и прогон, а не человек.

Проверяется ПОВЕДЕНИЕ сторожа на подготовленных каталогах: порог сработал,
порог не сработал на исправном состоянии, оформление сайта снимком не
считается, отсутствие данных не выдаётся за порядок.
"""
from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import time

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ИНСТРУМЕНТ = КОРЕНЬ / "automation" / "local" / "screenshot-retention-guard.py"
_спец = importlib.util.spec_from_file_location("srg", ИНСТРУМЕНТ)
СТОРОЖ = importlib.util.module_from_spec(_спец)
_спец.loader.exec_module(СТОРОЖ)


def _снимок(путь: pathlib.Path, байт: int = 2048, возраст_суток: int = 0):
    путь.parent.mkdir(parents=True, exist_ok=True)
    путь.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * байт)
    if возраст_суток:
        когда = time.time() - возраст_суток * 86400
        os.utime(путь, (когда, когда))


def _прогон(*аргв: str) -> tuple[int, dict]:
    г = subprocess.run([sys.executable, str(ИНСТРУМЕНТ), *аргв, "--json"],
                       capture_output=True, text=True, timeout=180)
    return г.returncode, json.loads(г.stdout)


def test_снимок_отличается_от_оформления():
    """Логотип и постер шаблона — не снимки приёмки, иначе сторож врёт."""
    assert СТОРОЖ.снимок("/srv/x/releases/ab/artifacts/evidence/home.png")
    assert СТОРОЖ.снимок("/home/claude/wt-y/var/shots/catalog-768.png")
    assert not СТОРОЖ.снимок("/srv/x/templates/brand/logo.png")
    assert not СТОРОЖ.снимок("/srv/x/public/poster/01a1.webp")
    assert not СТОРОЖ.снимок("/srv/x/artifacts/report.json")


def test_много_снимков_в_релизе_это_превышение(tmp_path):
    релиз = tmp_path / "site" / "releases" / "aabbccdd" / "artifacts" / "evidence"
    for n in range(5):
        _снимок(релиз / f"home-{n}.png")
    код, итог = _прогон("--root", str(tmp_path), "--per-release", "3")
    assert итог["исход"] == "ПРЕВЫШЕНО", итог
    assert итог["нарушения"]["релизы_с_снимками"], итог
    assert код == 1


def test_в_пределах_порога_исправно(tmp_path):
    """Контроль: без него сторож мог бы всегда находить превышение."""
    релиз = tmp_path / "site" / "releases" / "aabbccdd" / "artifacts" / "evidence"
    for n in range(2):
        _снимок(релиз / f"home-{n}.png")
    код, итог = _прогон("--root", str(tmp_path), "--per-release", "3")
    assert итог["исход"] == "ИСПРАВНО", итог
    assert код == 0


def test_пустой_корень_не_выдаётся_за_порядок(tmp_path):
    """«Снимков не найдено» говорится словами, а не молча как ИСПРАВНО."""
    код, итог = _прогон("--root", str(tmp_path))
    assert итог["исход"] == "ИСПРАВНО"
    assert "не найдено" in итог.get("почему", ""), итог
    assert код == 0


def test_несуществующий_корень_это_не_измерено(tmp_path):
    г = subprocess.run([sys.executable, str(ИНСТРУМЕНТ),
                        "--root", str(tmp_path / "нет-такого")],
                       capture_output=True, text=True, timeout=120)
    assert "НЕ ИЗМЕРЕНО" in г.stdout, г.stdout
    assert г.returncode == 2
