"""REQ-EDITOR-GATE-STATS: отказы шлюза считаются раздельно по причине.

Шлюз отказывает по разным причинам, и смешивать их нельзя: удержание доли —
это расписание, нехватка памяти — ёмкость хоста, пауза после партии — ритм.
Без разделения «редактор работает» и «редактор почти не запускается» выглядят
одинаково.

Измерено 19.10 по живому журналу за сутки: 244 такта, 23 запуска (9.4 %), из
отказов 111 «пауза», 86 «удержание доли», 9 «ресурсы». То есть треть тактов
уходит на удержание доли «lords» — следствие паузы публикаций, а не нехватки
работы.
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import json
import pathlib

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
_путь = КОРЕНЬ / "automation/local/editor-gate-stats.py"
_спец = importlib.util.spec_from_file_location("editor_gate_stats", _путь)
ИНСТР = importlib.util.module_from_spec(_спец)
_спец.loader.exec_module(ИНСТР)

СЕЙЧАС = dt.datetime(2026, 10, 19, 12, 0, tzinfo=dt.timezone.utc)


def _журнал(tmp_path: pathlib.Path, записи: list[dict]) -> pathlib.Path:
    п = tmp_path / "gate.jsonl"
    п.write_text("\n".join(json.dumps(з, ensure_ascii=False) for з in записи) + "\n",
                 encoding="utf-8")
    return п


def _такт(минут_назад: int, *, run=False, state="", reason="", mem=None) -> dict:
    шлюз = {"run": run}
    if state:
        шлюз["state"] = state
    if reason:
        шлюз["reason"] = reason
    if mem is not None:
        шлюз["resources"] = {"mem_available_mib": mem}
    return {"at": (СЕЙЧАС - dt.timedelta(minutes=минут_назад)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"), "gate": шлюз}


def test_запуски_и_отказы_считаются_раздельно(tmp_path):
    п = _журнал(tmp_path, [
        _такт(10, run=True),
        _такт(15, state="paused"),
        _такт(20, state="allocation_hold"),
        _такт(25, state="allocation_hold"),
        _такт(30, state="resources", mem=1500),
    ])
    и = ИНСТР.разобрать(2, журнал=п, сейчас=СЕЙЧАС)
    assert и["измерено"] is True
    assert и["тактов"] == 5 and и["запусков"] == 1
    assert и["состояния"]["allocation_hold"] == 2
    assert и["состояния"]["ЗАПУСК"] == 1
    assert и["память_мин"] == 1500


def test_память_читается_и_из_причины(tmp_path):
    """Старые записи несут число только в тексте причины."""
    п = _журнал(tmp_path, [
        _такт(5, state="resources",
              reason="недостаточно ресурсов: памяти доступно 1789 МиБ < 2048 МиБ"),
    ])
    и = ИНСТР.разобрать(2, журнал=п, сейчас=СЕЙЧАС)
    assert и["память_мин"] == 1789


def test_окно_отсекает_старое(tmp_path):
    п = _журнал(tmp_path, [_такт(10, run=True), _такт(500, run=True)])
    и = ИНСТР.разобрать(2, журнал=п, сейчас=СЕЙЧАС)
    assert и["тактов"] == 1


def test_нет_записей_за_период_не_измерено(tmp_path):
    п = _журнал(tmp_path, [_такт(500, run=True)])
    и = ИНСТР.разобрать(1, журнал=п, сейчас=СЕЙЧАС)
    assert и["измерено"] is False and "записей за" in и["почему"]


def test_нет_журнала_не_измерено(tmp_path):
    и = ИНСТР.разобрать(1, журнал=tmp_path / "нет.jsonl", сейчас=СЕЙЧАС)
    assert и["измерено"] is False and "не прочитан" in и["почему"]


def test_битые_строки_не_ломают_разбор(tmp_path):
    п = tmp_path / "gate.jsonl"
    п.write_text(json.dumps(_такт(5, run=True)) + "\nне json\n{\n", encoding="utf-8")
    и = ИНСТР.разобрать(2, журнал=п, сейчас=СЕЙЧАС)
    assert и["тактов"] == 1


def test_живой_журнал_читается(capsys):
    """Отрицательный контроль инструмента: на живом хосте он что-то считает."""
    код = ИНСТР.main(["--hours", "24"])
    вывод = capsys.readouterr().out
    assert код == 0, вывод
    assert "тактов" in вывод and "запусков" in вывод
