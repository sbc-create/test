"""Повторы заданий: что считается нарушением, а что обычной работой очереди.

Повод. SEO-сессия сообщила, что очередь повторяет известные отказы по таймеру и
это прямой расход ходов редактора (8 адресов из ~50 в партии). Измерение
подтвердило расход, но назвало другой механизм: очередь СВОЁ обещание держит —
выдач раньше объявленного ею `next_attempt_at` ноль, — а расходится её
расписание с правилом удержания `RESULT_HOLD` из `seo_operator/regular.py`:
`SOURCES_MISSING` 24 ч против 336, `PAGE_ABSENT` 6 ч против 168.

Первая версия этого разбора дала 371 «нарушение» на 786 выдач, потому что
сравнивала каждую последующую выдачу с правилом и тащила в счёт обычный
перезахват аренды внутри прогона. Инфляция числа здесь хуже молчания: на такой
отчёт нельзя опереться. Поэтому нарушением считается только выдача раньше
срока, объявленного самой очередью, а расхождение расписания с правилом
показывается отдельной таблицей.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
СЦЕНАРИЙ = КОРЕНЬ / "automation" / "local" / "queue-repeat-audit.py"


def _модуль():
    спец = importlib.util.spec_from_file_location("queue_repeat_audit", СЦЕНАРИЙ)
    м = importlib.util.module_from_spec(спец)
    sys.modules["queue_repeat_audit"] = м
    спец.loader.exec_module(м)
    return м


def событие(**поля) -> dict:
    return поля


@pytest.fixture()
def модуль():
    return _модуль()


def test_выдача_раньше_объявленного_срока_это_нарушение(модуль):
    записи = [
        событие(event="task_result", at="2026-10-01T10:00:00Z", task_id="t1",
                outcome="SOURCES_MISSING",
                next_attempt_at="2026-10-02T10:00:00Z"),
        событие(event="task_claimed", at="2026-10-01T12:00:00Z", task_id="t1"),
    ]
    итог = модуль.разобрать(записи)
    assert len(итог["повторы"]) == 1
    (п,) = итог["повторы"]
    assert п["исход"] == "SOURCES_MISSING"
    assert п["через_ч"] == 2.0


def test_выдача_после_объявленного_срока_нарушением_не_считается(модуль):
    """Это обычная работа очереди, а не дефект."""
    записи = [
        событие(event="task_result", at="2026-10-01T10:00:00Z", task_id="t1",
                outcome="SOURCES_MISSING",
                next_attempt_at="2026-10-02T10:00:00Z"),
        событие(event="task_claimed", at="2026-10-02T11:00:00Z", task_id="t1"),
    ]
    assert модуль.разобрать(записи)["повторы"] == []


def test_перезахват_без_объявленного_срока_не_нарушение(модуль):
    """Нет `next_attempt_id` — нет и обещания, которое можно нарушить.

    Ровно здесь прежняя версия насчитала 371 нарушение: она сравнивала выдачу с
    правилом и считала нарушением любой перезахват внутри прогона.
    """
    записи = [
        событие(event="task_result", at="2026-10-01T10:00:00Z", task_id="t1",
                outcome="SOURCES_MISSING"),
        событие(event="task_claimed", at="2026-10-01T10:00:01Z", task_id="t1"),
        событие(event="task_claimed", at="2026-10-01T10:05:00Z", task_id="t1"),
    ]
    assert модуль.разобрать(записи)["повторы"] == []


def test_переоткрытие_снимает_удержание(модуль):
    """Переоткрытие законно: после него выдача — не повтор."""
    записи = [
        событие(event="task_result", at="2026-10-01T10:00:00Z", task_id="t1",
                outcome="SOURCES_MISSING",
                next_attempt_at="2026-10-15T10:00:00Z"),
        событие(event="task_reopened", at="2026-10-01T11:00:00Z", task_id="t1"),
        событие(event="task_claimed", at="2026-10-01T12:00:00Z", task_id="t1"),
    ]
    assert модуль.разобрать(записи)["повторы"] == []


def test_расхождение_расписания_с_правилом_видно_числом(модуль):
    записи = [
        событие(event="task_result", at="2026-10-01T10:00:00Z", task_id="t1",
                outcome="SOURCES_MISSING",
                next_attempt_at="2026-10-02T10:00:00Z"),
        событие(event="task_result", at="2026-10-01T10:00:00Z", task_id="t2",
                outcome="PAGE_ABSENT",
                next_attempt_at="2026-10-01T16:00:00Z"),
    ]
    итог = модуль.разобрать(записи)
    расх = итог["расхождения_срока"]
    assert расх["SOURCES_MISSING"] == {"правило_ч": 336, "объявлено_ч": 24.0,
                                       "случаев": 1}
    assert расх["PAGE_ABSENT"]["объявлено_ч"] == 6.0
    assert расх["PAGE_ABSENT"]["правило_ч"] == 168


def test_совпадение_расписания_с_правилом_расхождением_не_зовётся(модуль):
    записи = [
        событие(event="task_result", at="2026-10-01T10:00:00Z", task_id="t1",
                outcome="SOURCES_MISSING",
                next_attempt_at="2026-10-15T10:00:00Z"),
    ]
    assert модуль.разобрать(записи)["расхождения_срока"] == {}


def test_повторные_закрытия_тем_же_исходом_считаются(модуль):
    записи = [
        событие(event="task_result", at="2026-10-01T10:00:00Z", task_id="t1",
                outcome="SOURCES_MISSING", next_attempt_at="2026-10-02T10:00:00Z"),
        событие(event="task_result", at="2026-10-03T10:00:00Z", task_id="t1",
                outcome="SOURCES_MISSING", next_attempt_at="2026-10-04T10:00:00Z"),
        событие(event="task_result", at="2026-10-01T10:00:00Z", task_id="t2",
                outcome="SOURCES_MISSING", next_attempt_at="2026-10-02T10:00:00Z"),
    ]
    итог = модуль.разобрать(записи)
    assert итог["повторные_закрытия"]["SOURCES_MISSING"] == 1, (
        "повторно закрыто одно задание из двух")


def test_исход_без_удержания_в_счёт_не_идёт(модуль):
    """`TEXT_WRITTEN` закрывает адрес навсегда — ему удержание не нужно."""
    записи = [
        событие(event="task_result", at="2026-10-01T10:00:00Z", task_id="t1",
                outcome="TEXT_WRITTEN"),
        событие(event="task_claimed", at="2026-10-01T10:30:00Z", task_id="t1"),
    ]
    итог = модуль.разобрать(записи)
    assert итог["повторы"] == []
    assert итог["расхождения_срока"] == {}


def test_имена_событий_взяты_из_журнала():
    """Прежняя версия искала `task_issued` и молчала о дефекте, который искала."""
    текст = СЦЕНАРИЙ.read_text(encoding="utf-8")
    assert '"task_claimed"' in текст
    assert '"task_result"' in текст
    assert '"task_issued"' not in текст


def test_сроки_совпадают_с_правилом_оператора():
    """Расхождение между правилом и проверкой скрыло бы искомый дефект."""
    м = _модуль()
    правило = (КОРЕНЬ / "seo_operator" / "regular.py").read_text(encoding="utf-8")
    блок = правило[правило.index("RESULT_HOLD = {"):]
    блок = блок[:блок.index("}")]
    for исход, сутки in м.СРОКИ.items():
        assert f'"{исход}": dt.timedelta(days={сутки})' in блок, исход


def test_пустой_журнал_это_не_отсутствие_дефекта(модуль, tmp_path, capsys):
    модуль.ЖУРНАЛ = tmp_path / "нет.jsonl"
    код = модуль.главное([])
    assert код == 2, "нечитаемый журнал обязан давать отдельный исход"
    assert "не прочитан" in capsys.readouterr().err
