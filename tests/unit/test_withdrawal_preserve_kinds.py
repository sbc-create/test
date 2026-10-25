"""Каталог и текущее состояние — разные доказательства сохранности.

Повод — собственная ошибка 25.10. Проверка сохранности перед остановкой служб
пересчитала отпечатки через полтора часа после сохранения и объявила: «данные
разошлись, остановку не выполнять» — девять файлов из описанных. Разбор по
видам показал обратное: КАТАЛОГ (`*-catalog.json`, `*-details.json`) совпал у
всех четырёх домéнов, а менялись файлы, которые РАБОТАЮЩАЯ служба пишет на
ходу — номера серий, события и состояние эпизодов.

Смешав два вида, проверка выдала живую работу за порчу данных и предложила
отменить порученную владельцем остановку. Поэтому различение закреплено:
отпечаток каталога — доказательство сохранности, отпечаток состояния — отметка
времени, и окончательный снимок состояния берётся ПОСЛЕ остановки службы.
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
_путь = КОРЕНЬ / "automation/local/withdrawal-preserve.py"
_спец = importlib.util.spec_from_file_location("withdrawal_preserve", _путь)
СОХР = importlib.util.module_from_spec(_спец)
_спец.loader.exec_module(СОХР)


@pytest.mark.parametrize("имя,ожидание", [
    ("lords-01-catalog.json", "каталог"),
    ("lords-01-details.json", "каталог"),
    ("animedia-02-admission.json", "каталог"),
    ("editorial-overrides.json", "каталог"),
    ("lords-01-details.nums.json", "состояние"),
    ("animedia-02-episode-events.json", "состояние"),
    ("animedia-02-episode-state.json", "состояние"),
    ("lords-01-episode-sync.json", "состояние"),
])
def test_вид_файла_различается(имя, ожидание) -> None:
    assert СОХР.вид_файла(имя) == ожидание


def test_манифест_называет_вид_каждого_файла(tmp_path, monkeypatch) -> None:
    данные = tmp_path / "data"
    данные.mkdir()
    (данные / "proba-01-catalog.json").write_text('{"items": []}', encoding="utf-8")
    (данные / "proba-01-episode-state.json").write_text("{}", encoding="utf-8")
    описано = СОХР.данные_каталога("proba-01", (str(данные),))
    виды = {pathlib.Path(о["path"]).name: о["kind"] for о in описано}
    assert виды == {"proba-01-catalog.json": "каталог",
                    "proba-01-episode-state.json": "состояние"}


def test_нечитаемый_файл_остаётся_не_измеренным(tmp_path) -> None:
    """«Нет прав» — честный ответ, а не повод оборвать сохранение."""
    данные = tmp_path / "data"
    данные.mkdir()
    ф = данные / "proba-01-catalog.json"
    ф.write_text("{}", encoding="utf-8")
    ф.chmod(0o000)
    try:
        описано = СОХР.данные_каталога("proba-01", (str(данные),))
    finally:
        ф.chmod(0o644)
    assert описано and str(описано[0]["sha256"]).startswith("НЕ ПРОЧИТАН")
