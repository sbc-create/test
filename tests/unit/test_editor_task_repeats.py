"""REQ-EDITOR-REPEATS: повторная выдача задания считается, но не объявляется виной.

Повод: записка прогона 19.10 07:40Z говорит «6 заданий закрыты без текста: 4
повтора PAGE_ABSENT/SOURCES_MISSING», и это выглядело как заметная потеря
прогонов. Замер по 92 выдачам за 12 часов дал 7 повторов (7.6 %) — то есть
подозрение не подтвердилось, и главная причина незаписанного текста не повторы,
а отсутствие источников.

Закрепляется: повтор — это ОДИН task_id с ОДНИМ исходом в разных прогонах;
лишними считаются все выдачи серии кроме первой; нет прогонов — код 2.
"""
from __future__ import annotations

import datetime as dt
import json
import importlib.util
import pathlib

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
_путь = КОРЕНЬ / "automation/local/editor-task-repeats.py"
_спец = importlib.util.spec_from_file_location("editor_task_repeats", _путь)
ИНСТР = importlib.util.module_from_spec(_спец)
_спец.loader.exec_module(ИНСТР)


def _прогон(каталог: pathlib.Path, метка: str, пары: list[tuple[str, str]]) -> None:
    (каталог / f"{метка}.run.json").write_text(json.dumps({
        "run_id": метка,
        "outcomes": [{"task_id": з, "outcome": и} for з, и in пары],
    }), encoding="utf-8")


def test_повтор_одного_задания_с_одним_исходом(tmp_path):
    _прогон(tmp_path, "20261019T010000Z", [("T1", "SOURCES_MISSING")])
    _прогон(tmp_path, "20261019T020000Z", [("T1", "SOURCES_MISSING")])
    _прогон(tmp_path, "20261019T030000Z", [("T2", "TEXT_WRITTEN")])
    и = ИНСТР.разобрать(ИНСТР.собрать(tmp_path, None, None))
    assert и["выдач"] == 3
    assert и["задач_с_повторами"] == 1 and и["лишних_выдач"] == 1
    assert и["по_исходу"] == {"SOURCES_MISSING": 1}


def test_разные_исходы_одной_задачи_повтором_не_считаются(tmp_path):
    """Задача, которая в прошлый раз не нашла источник, а теперь написала текст,
    повторной выдачей не является: условия изменились."""
    _прогон(tmp_path, "20261019T010000Z", [("T1", "SOURCES_MISSING")])
    _прогон(tmp_path, "20261019T020000Z", [("T1", "TEXT_WRITTEN")])
    и = ИНСТР.разобрать(ИНСТР.собрать(tmp_path, None, None))
    assert и["лишних_выдач"] == 0


def test_серия_из_трёх_даёт_две_лишние(tmp_path):
    for час in ("01", "02", "03"):
        _прогон(tmp_path, f"202610{19}T{час}0000Z", [("T1", "PAGE_ABSENT")])
    и = ИНСТР.разобрать(ИНСТР.собрать(tmp_path, None, None))
    assert и["лишних_выдач"] == 2
    assert и["верх"][0]["выдач"] == 3


def test_порог_минимума(tmp_path):
    _прогон(tmp_path, "20261019T010000Z", [("T1", "PAGE_ABSENT")])
    _прогон(tmp_path, "20261019T020000Z", [("T1", "PAGE_ABSENT")])
    и = ИНСТР.разобрать(ИНСТР.собрать(tmp_path, None, None), минимум=3)
    assert и["лишних_выдач"] == 0


def test_окно_отсекает(tmp_path):
    _прогон(tmp_path, "20261018T010000Z", [("T1", "PAGE_ABSENT")])
    _прогон(tmp_path, "20261019T010000Z", [("T1", "PAGE_ABSENT")])
    с = dt.datetime(2026, 10, 19, tzinfo=dt.timezone.utc)
    и = ИНСТР.разобрать(ИНСТР.собрать(tmp_path, с, None))
    assert и["выдач"] == 1 and и["лишних_выдач"] == 0


def test_битый_файл_и_пустые_поля(tmp_path):
    _прогон(tmp_path, "20261019T010000Z", [("T1", "PAGE_ABSENT"), ("", "X"),
                                           ("T2", "")])
    (tmp_path / "20261019T020000Z.run.json").write_text("не json", encoding="utf-8")
    и = ИНСТР.разобрать(ИНСТР.собрать(tmp_path, None, None))
    assert и["выдач"] == 1


def test_нет_прогонов_код_2(tmp_path, capsys):
    assert ИНСТР.main(["--dir", str(tmp_path)]) == 2
    assert "НЕ ИЗМЕРЕНО" in capsys.readouterr().out


def test_повторов_нет_код_0(tmp_path, capsys):
    _прогон(tmp_path, "20261019T010000Z", [("T1", "TEXT_WRITTEN")])
    assert ИНСТР.main(["--dir", str(tmp_path)]) == 0
    вывод = capsys.readouterr().out
    assert "лишних выдач 0" in вывод
    assert "не дефект" in вывод


def test_живые_прогоны_читаются(capsys):
    код = ИНСТР.main(["--since", "2026-10-18T00:00Z"])
    вывод = capsys.readouterr().out
    assert код in (0, 1), вывод
    assert "выдач заданий" in вывод
