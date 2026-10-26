"""Состояние счётчиков и ЦЕЛЕЙ по витринам: что измеримо, а что нет.

Признак «события идут» снаружи не измерим, и инструмент так и говорит. Но его
НЕВОЗМОЖНОСТЬ измерима локально: если в живом выпуске нет ни одного вызова
`reachGoal`, события идти не могут, сколько бы целей ни стояло в реестре.
Измерено 26.10 по 29 живым домéнам: цели могут идти у ОДНОГО
(1lordserials1.online), у 15 не могут, у 13 выпуска на этом узле нет.

Положительный и отрицательный случаи сверены с живыми страницами:
на 1lordserials1.online `__sfGoal` и `reachGoal` есть в разметке, на
zonafilm.cc есть `ym(` с верным номером 113110481, но ни одного вызова цели.
"""
from __future__ import annotations

import importlib.util
import pathlib

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
_сп = importlib.util.spec_from_file_location(
    "analytics_tags_state", КОРЕНЬ / "automation" / "local" / "analytics-tags-state.py")
инс = importlib.util.module_from_spec(_сп)
_сп.loader.exec_module(инс)

# --- Цели в живом выпуске: невозможность измерима, даже когда «идут» — нет ---

def test_след_целей_в_отдаваемом_коде_это_да(tmp_path, monkeypatch):
    """Положительный случай сверен с живой страницей 1lordserials1.online."""
    корень = tmp_path / "пример-ru" / "releases" / "abc"
    (корень / "src").mkdir(parents=True)
    (корень / "src" / "frontend.py").write_text(
        "window.__sfGoal && window.ym(C,'reachGoal',n)\n", encoding="utf-8")
    (tmp_path / "пример-ru" / "current").symlink_to(корень)
    monkeypatch.setattr(инс, "КОРЕНЬ_ВЫПУСКОВ", tmp_path)
    состояние, почему = инс.цели_в_выпуске("пример.ru")
    assert состояние == инс.ДА and "frontend.py" in почему


def test_след_только_в_проверках_не_считается(tmp_path, monkeypatch):
    """Проверочный сценарий посетителю не отдаётся.

    Измерено 26.10: у 1lordserials1.online след нашёлся сперва в
    checks/player_mount.py, и без отсечения витрина числилась бы готовой.
    """
    корень = tmp_path / "пример-ru" / "releases" / "abc"
    (корень / "checks").mkdir(parents=True)
    (корень / "checks" / "player_mount.py").write_text("__sfGoal\n", encoding="utf-8")
    (tmp_path / "пример-ru" / "current").symlink_to(корень)
    monkeypatch.setattr(инс, "КОРЕНЬ_ВЫПУСКОВ", tmp_path)
    состояние, почему = инс.цели_в_выпуске("пример.ru")
    assert состояние == инс.НЕТ and "НЕ МОГУТ" in почему


def test_приставка_site_в_имени_каталога_находится(tmp_path, monkeypatch):
    """На узле есть обе формы: `пример-ru` и `site-пример-ru`."""
    корень = tmp_path / "site-пример-ru" / "releases" / "abc"
    (корень / "src").mkdir(parents=True)
    (корень / "src" / "f.py").write_text("reachGoal\n", encoding="utf-8")
    (tmp_path / "site-пример-ru" / "current").symlink_to(корень)
    monkeypatch.setattr(инс, "КОРЕНЬ_ВЫПУСКОВ", tmp_path)
    assert инс.цели_в_выпуске("пример.ru")[0] == инс.ДА


def test_отсутствие_каталога_это_отдельный_исход(tmp_path, monkeypatch):
    """«Выпуска нет» — не то же, что «целей нет»: витрина может жить на другом узле."""
    monkeypatch.setattr(инс, "КОРЕНЬ_ВЫПУСКОВ", tmp_path)
    состояние, почему = инс.цели_в_выпуске("чужая.ru")
    assert состояние == инс.НЕТ_ВЫПУСКА and "не найден" in почему
