"""Шлюз не запускает модель при исчерпанной квоте поставщика.

Повод измерен 25.10. Запуски 07:20Z, 07:50Z и 09:35Z стартовали модель при
исчерпанной НЕДЕЛЬНОЙ квоте и получили «You've hit your weekly limit · resets
4pm (UTC)». Токенов это не стоило: `costUSD` 0, чтение кэша 0, один оборот —
API отказал до расхода. Потеря не денежная, и выдавать её за денежную нельзя;
но каждый такой запуск занимает слот цикла и пишет в журнал `INCOMPLETE`, из-за
которого включается нарастающий backoff «сбоев подряд» — исправная пауза по
квоте превращается в наказание за неё.

Время сброса берётся из строки самого поставщика (он печатает «(UTC)»), а не
назначается. Строки без часа держат сутки: это безопаснее, чем ломиться каждые
20 минут, и короче недели.
"""
from __future__ import annotations

import datetime as dt
import pathlib
import sys

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(КОРЕНЬ))

from seo_operator import editor_run  # noqa: E402

ХВОСТ = "You've hit your weekly limit · resets 4pm (UTC)"


def запуск(хвост: str, когда: str = "2026-10-25T09:35:11Z", стартовал: bool = True) -> dict:
    return {"run_id": "r1", "model_started": стартовал, "finished_at": когда,
            "verdict": "INCOMPLETE",
            "self_report": {"terminal_reason": "api_error", "result_tail": хвост}}


def т(метка: str) -> dt.datetime:
    return dt.datetime.fromisoformat(метка.replace("Z", "+00:00"))


def test_до_сброса_держит_и_называет_время() -> None:
    держать, почему, до = editor_run.квота_исчерпана([запуск(ХВОСТ)], т("2026-10-25T10:00:00Z"))
    assert держать is True
    assert до == т("2026-10-25T16:00:00Z")
    assert "weekly" in почему and "16:00" in почему


def test_после_сброса_не_держит() -> None:
    держать, _, _ = editor_run.квота_исчерпана([запуск(ХВОСТ)], т("2026-10-25T16:30:00Z"))
    assert держать is False


def test_сброс_уже_прошедшим_часом_переносится_на_сутки_вперёд() -> None:
    """Отказ в 17:00Z со сбросом «4pm» означает 16:00 СЛЕДУЮЩЕГО дня."""
    _, _, до = editor_run.квота_исчерпана(
        [запуск(ХВОСТ, "2026-10-25T17:00:00Z")], т("2026-10-25T18:00:00Z"))
    assert до == т("2026-10-26T16:00:00Z")


def test_без_часа_держит_сутки() -> None:
    держать, _, до = editor_run.квота_исчерпана(
        [запуск("You've hit your usage limit")], т("2026-10-25T10:00:00Z"))
    assert держать is True and до == т("2026-10-26T09:35:11Z")


@pytest.mark.parametrize("хвост", [
    "Текст партии записан, 2 описания опубликованы",
    "",
    "error: connection reset by peer",
])
def test_обычный_запуск_квоту_не_держит(хвост) -> None:
    держать, _, _ = editor_run.квота_исчерпана([запуск(хвост)], т("2026-10-25T10:00:00Z"))
    assert держать is False


def test_смотрится_последний_запуск_со_стартом_модели() -> None:
    """Запуски без старта модели (отказ шлюза) историю квоты не заслоняют."""
    runs = [запуск(ХВОСТ, "2026-10-25T09:35:11Z"),
            запуск("", "2026-10-25T09:40:00Z", стартовал=False)]
    держать, _, _ = editor_run.квота_исчерпана(runs, т("2026-10-25T10:00:00Z"))
    assert держать is True


def test_успешный_запуск_после_лимита_снимает_держание() -> None:
    runs = [запуск(ХВОСТ, "2026-10-25T09:35:11Z"),
            запуск("партия завершена", "2026-10-25T16:10:00Z")]
    держать, _, _ = editor_run.квота_исчерпана(runs, т("2026-10-25T16:20:00Z"))
    assert держать is False


def test_пустой_журнал_не_держит() -> None:
    assert editor_run.квота_исчерпана([], т("2026-10-25T10:00:00Z"))[0] is False


# --- решение шлюза ----------------------------------------------------------

def test_шлюз_отвечает_состоянием_quota_и_не_зовёт_работу(monkeypatch, tmp_path) -> None:
    (tmp_path / "runs.jsonl").write_text(
        __import__("json").dumps(запуск(ХВОСТ)) + "\n", encoding="utf-8")

    def не_должен_вызваться(*а, **к):
        raise AssertionError("при исчерпанной квоте работа не подбирается")

    monkeypatch.setattr(editor_run, "_work", не_должен_вызваться)
    решение = editor_run.gate(
        т("2026-10-25T10:00:00Z"), state=tmp_path,
        resources_fn=lambda: {"ok": True, "problems": [], "measured": {}})
    assert решение["run"] is False and решение["state"] == "quota"
    assert решение["next_at"] == "2026-10-25T16:00:00Z"


def test_квота_проверяется_до_ресурсов(monkeypatch, tmp_path) -> None:
    """Порядок важен: при исчерпанной квоте причина — квота, а не память."""
    (tmp_path / "runs.jsonl").write_text(
        __import__("json").dumps(запуск(ХВОСТ)) + "\n", encoding="utf-8")
    monkeypatch.setattr(editor_run, "_work", lambda *а, **к: {"run": True, "reason": "есть"})
    решение = editor_run.gate(
        т("2026-10-25T10:00:00Z"), state=tmp_path,
        resources_fn=lambda: {"ok": False, "problems": ["памяти мало"], "measured": {}})
    assert решение["state"] == "quota", "причина простоя названа неверно"
