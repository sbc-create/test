"""Результат ПРОШЛОЙ попытки не выдаётся за итог текущей.

Случай измерен 2026-10-04. Идентификатор заявки на слой индексации
детерминированный (`<site>-idx-<mode>`), и результат прошлой попытки лежит в
каталоге исполнителя. Отклонённую заявку очередь перепоставляет правильно
(`requeued-after-failure`, `retry_after: rejected`), но ожидание читает
состояние СРАЗУ: файл результата уже есть — от прошлой попытки, — и `состояние`
отвечает `finished`. Ожидание принимает его за итог своей заявки и отдаёт
старый отказ.

Пока причина отказа не менялась, подмену не видно: текст совпадает. Опасна она
ровно тогда, когда причину устранили — первая же попытка после исправления
вернула бы прошлый отказ, и исправление выглядело бы не подействовавшим.

Поэтому `состояние` принимает `не_раньше`: результат старше поданной заявки —
это ещё не её результат.
"""
from __future__ import annotations

import json
import pathlib

import pytest

from factory.cell import queue as q


@pytest.fixture()
def база(tmp_path: pathlib.Path) -> pathlib.Path:
    (tmp_path / "requests").mkdir()
    (tmp_path / "results").mkdir()
    return tmp_path


def _результат(база: pathlib.Path, когда: str, статус: str = "rejected") -> None:
    (база / "results" / "lords-05-idx-open.json").write_text(json.dumps({
        "request_id": "lords-05-idx-open", "site_id": "lords-05",
        "operation": "indexing-nginx", "status": статус, "started_at": когда,
        "error": "открытие слоя nginx запрещено — в реестре ячеек "
                 "indexing.open_authorized не равно true",
    }, ensure_ascii=False), encoding="utf-8")


def _заявка(база: pathlib.Path, когда: str) -> None:
    (база / "requests" / "lords-05-idx-open.json").write_text(json.dumps({
        "request_id": "lords-05-idx-open", "site_id": "lords-05",
        "operation": "indexing-nginx", "mode": "OPEN", "commit": "",
        "submitted_at": когда,
        "stages": [{"stage": "received", "at": когда, "retry_after": "rejected"}],
    }, ensure_ascii=False), encoding="utf-8")


def test_старый_результат_не_считается_итогом_новой_заявки(база):
    _результат(база, "2026-10-04T08:36:00+00:00")
    _заявка(база, "2026-10-04T09:09:01+00:00")
    с = q.состояние("lords-05-idx-open", база=база,
                    не_раньше="2026-10-04T09:09:01+00:00")
    assert с["status"] == "queued", (
        "ожидание приняло результат прошлой попытки за итог текущей: "
        f"{с.get('status')!r}")
    assert с.get("stale_result"), "подмену нужно называть, а не скрывать"
    assert "08:36" in str(с["stale_result"].get("started_at"))


def test_свежий_результат_принимается(база):
    _результат(база, "2026-10-04T09:10:01+00:00")
    _заявка(база, "2026-10-04T09:09:01+00:00")
    с = q.состояние("lords-05-idx-open", база=база,
                    не_раньше="2026-10-04T09:09:01+00:00")
    assert с["status"] == "finished"
    assert с["result"]["status"] == "rejected", "исход обязан сохраниться как есть"


def test_без_не_раньше_поведение_прежнее(база):
    """Совместимость: `operation_result` показывает последний результат как есть."""
    _результат(база, "2026-10-04T08:36:00+00:00")
    _заявка(база, "2026-10-04T09:09:01+00:00")
    assert q.состояние("lords-05-idx-open", база=база)["status"] == "finished"


def test_нечитаемое_время_не_отбрасывает_результат(база):
    """Результат без `started_at` судить по времени нельзя — считаем свежим.

    Молчаливое «ещё не готово» на старых результатах подвесило бы ожидание на
    полный таймаут, а это та самая ошибка, из-за которой `состояние` появилось.
    """
    (база / "results" / "lords-05-idx-open.json").write_text(
        json.dumps({"request_id": "lords-05-idx-open", "status": "ok"}),
        encoding="utf-8")
    _заявка(база, "2026-10-04T09:09:01+00:00")
    с = q.состояние("lords-05-idx-open", база=база,
                    не_раньше="2026-10-04T09:09:01+00:00")
    assert с["status"] == "finished"


def test_ожидание_слоя_передаёт_время_подачи():
    """Исправление бесполезно, если ожидание о нём не знает."""
    текст = pathlib.Path("factory/qwen/indexing.py").read_text(encoding="utf-8")
    assert "не_раньше=заявка.submitted_at" in текст, (
        "ожидание слоя nginx читает состояние без времени подачи и снова "
        "примет прошлый отказ за итог текущей попытки")


def test_отказ_проверки_доступа_называет_инструмент_моста(tmp_path, monkeypatch):
    """Совет, недоступный читателю отказа, равен отсутствию совета.

    Оператор через MCP-мост получал «Повторить: python3 -m factory cell submit
    …» — команду, которой у него нет. Действие у него есть, и оно штатное:
    инструмент `refresh_executor_access`. Отказ обязан называть оба пути.
    """
    monkeypatch.setattr(q, "БАЗА", tmp_path)
    (tmp_path / "results").mkdir()
    with pytest.raises(q.RequestRejected) as ош:
        q.проверить_доступ_исполнителя("lords-01")
    текст = str(ош.value)
    assert "refresh_executor_access" in текст, текст
    assert "factory cell submit" in текст, "второй путь тоже обязан быть назван"
