"""REQ-EDITOR-OUTCOMES: доли исходов считаются по прогонам и не выдают выводов из шума.

«Редактор работает» и «редактор пишет тексты» — разные утверждения. За ночь
18→19.10 из 83 исходов 45 были `SOURCES_MISSING`. Чтобы судить о правке
источников (MOD-85), доли нужно сравнивать до и после — и воздерживаться от
вывода, пока материала мало.

Закрепляется:

* исходы берутся из `*.run.json` (`outcomes`), а не из `runs.jsonl`, где их нет;
* `--split` делит период и печатает обе половины;
* на малом числе заданий инструмент прямо говорит, что вывода нет;
* нет прогонов или не разобрано время — код 2, а не пустая таблица.
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import json
import pathlib

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
_путь = КОРЕНЬ / "automation/local/editor-outcomes.py"
_спец = importlib.util.spec_from_file_location("editor_outcomes", _путь)
ИНСТР = importlib.util.module_from_spec(_спец)
_спец.loader.exec_module(ИНСТР)


def _прогон(каталог: pathlib.Path, метка: str, исходы: list[str],
            адреса: list[str] | None = None) -> None:
    (каталог / f"{метка}.run.json").write_text(json.dumps({
        "run_id": метка,
        "outcomes": [{"task_id": f"t{i}", "outcome": и} for i, и in enumerate(исходы)],
        "self_report": {"urls": адреса or []},
    }), encoding="utf-8")


def test_исходы_и_публикации_считаются(tmp_path):
    _прогон(tmp_path, "20261019T010000Z", ["TEXT_WRITTEN", "SOURCES_MISSING"],
            ["https://a.test/anime/x"])
    _прогон(tmp_path, "20261019T020000Z", ["SOURCES_MISSING"])
    с = ИНСТР.свод(ИНСТР.прогоны(tmp_path, None, None))
    assert с["прогонов"] == 2 and с["заданий"] == 3 and с["публикаций"] == 1
    assert с["исходы"]["SOURCES_MISSING"] == 2
    assert с["доли"]["SOURCES_MISSING"] == 66.7


def test_окно_отсекает_прогоны(tmp_path):
    _прогон(tmp_path, "20261018T010000Z", ["TEXT_WRITTEN"])
    _прогон(tmp_path, "20261019T010000Z", ["TEXT_WRITTEN"])
    с = dt.datetime(2026, 10, 19, tzinfo=dt.timezone.utc)
    assert len(ИНСТР.прогоны(tmp_path, с, None)) == 1


def test_журнал_runs_не_используется(tmp_path):
    """В runs.jsonl исходов заданий нет: считать по нему — уже сделанная ошибка."""
    (tmp_path / "runs.jsonl").write_text(
        json.dumps({"run_id": "x", "verdict": "COMPLETE"}) + "\n", encoding="utf-8")
    _прогон(tmp_path, "20261019T010000Z", ["TEXT_WRITTEN"])
    с = ИНСТР.свод(ИНСТР.прогоны(tmp_path, None, None))
    assert с["заданий"] == 1


def test_битый_файл_не_ломает_счёт(tmp_path):
    _прогон(tmp_path, "20261019T010000Z", ["TEXT_WRITTEN"])
    (tmp_path / "20261019T020000Z.run.json").write_text("не json", encoding="utf-8")
    assert ИНСТР.свод(ИНСТР.прогоны(tmp_path, None, None))["прогонов"] == 1


def test_нет_прогонов_код_2(tmp_path, capsys):
    assert ИНСТР.main(["--dir", str(tmp_path)]) == 2
    assert "НЕ ИЗМЕРЕНО" in capsys.readouterr().out


def test_неразобранное_время_код_2(tmp_path, capsys):
    _прогон(tmp_path, "20261019T010000Z", ["TEXT_WRITTEN"])
    assert ИНСТР.main(["--dir", str(tmp_path), "--since", "вчера"]) == 2
    assert "не разобрано" in capsys.readouterr().out


def test_split_печатает_обе_половины(tmp_path, capsys):
    _прогон(tmp_path, "20261019T010000Z", ["SOURCES_MISSING"] * 20 + ["TEXT_WRITTEN"] * 20)
    _прогон(tmp_path, "20261019T080000Z", ["TEXT_WRITTEN"] * 40)
    assert ИНСТР.main(["--dir", str(tmp_path), "--split", "2026-10-19T06:30Z"]) == 0
    вывод = capsys.readouterr().out
    assert "до 2026-10-19T06:30Z" in вывод and "после 2026-10-19T06:30Z" in вывод
    assert "ВЫВОДА НЕТ" not in вывод


def test_на_малом_числе_вывода_нет(tmp_path, capsys):
    """Главная защита: девять заданий ничего не доказывают."""
    _прогон(tmp_path, "20261019T010000Z", ["SOURCES_MISSING"] * 45)
    _прогон(tmp_path, "20261019T080000Z", ["SOURCES_MISSING"] * 4 + ["TEXT_WRITTEN"] * 5)
    assert ИНСТР.main(["--dir", str(tmp_path), "--split", "2026-10-19T06:30Z"]) == 0
    assert "ВЫВОДА НЕТ" in capsys.readouterr().out


def test_живые_прогоны_читаются(capsys):
    код = ИНСТР.main(["--since", "2026-10-18T00:00Z"])
    вывод = capsys.readouterr().out
    assert код == 0, вывод
    assert "прогонов" in вывод
