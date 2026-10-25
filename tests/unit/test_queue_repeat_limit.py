"""Предел повторов отказа: проверка ОБЫЧНЫМ КОДОМ до обращения к модели.

Повод измерен и стоит денег. За 7 суток (18–25.10) фоновый редактор разобрал
1 463 материала за $224,79 ($0,154 за материал), и 922 разбора кончились
`SOURCES_MISSING`. Разбор журнала очереди
(`automation/local/queue-repeat-audit.py --transitions`): из 294 заданий с этим
исходом текст позже дали 22 — двадцать после РОВНО ОДНОГО отказа, одно после
двух, одно после десяти; 1 778 отказов из 2 086 пришлись на адреса, где отказ
уже был. Срок очереди (`next_attempt_at`) с правилом удержания
(`seo_operator/regular.py::RESULT_HOLD`) не согласован, и это расхождение сам
промпт редактора называет причиной: «повторный сбор фактов стоил ~8 из ~50
ходов партии».

Здесь закреплено поведение моста: задание, по которому отказ уже повторялся до
предела, исполнителю не выдаётся, освобождается и названо в ответе. Молчаливое
«заданий нет» запрещено: тогда простой нельзя отличить от исправной работы.
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import sys

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(КОРЕНЬ))

from factory.qwen import queue_bridge  # noqa: E402
from seo_operator import regular  # noqa: E402


def журнал(tmp_path: pathlib.Path, события: list[dict]) -> pathlib.Path:
    п = tmp_path / "queue_events.jsonl"
    п.write_text("\n".join(json.dumps(з, ensure_ascii=False) for з in события) + "\n",
                 encoding="utf-8")
    return п


def итог(ключ: str, исход: str, когда: str = "2026-10-20T10:00:00Z",
         адрес: str = "https://animedia.space/title/x") -> dict:
    return {"event": "task_result", "task_id": ключ, "outcome": исход,
            "at": когда, "canonical_url": адрес}


# --- счёт подряд идущих отказов ---------------------------------------------

def test_отказы_подряд_считаются(tmp_path) -> None:
    ж = журнал(tmp_path, [итог("t1", "SOURCES_MISSING", "2026-10-18T10:00:00Z"),
                          итог("t1", "SOURCES_MISSING", "2026-10-19T10:00:00Z"),
                          итог("t1", "SOURCES_MISSING", "2026-10-20T10:00:00Z")])
    с = queue_bridge.подряд_отказов(ж)
    assert с["t1"]["подряд"] == 3
    assert с["t1"]["исход"] == "SOURCES_MISSING"


def test_другой_исход_обнуляет_счёт(tmp_path) -> None:
    """Счёт именно ПОДРЯД: иначе один давний отказ держал бы адрес навсегда."""
    ж = журнал(tmp_path, [итог("t1", "SOURCES_MISSING", "2026-10-18T10:00:00Z"),
                          итог("t1", "SOURCE_UNAVAILABLE", "2026-10-19T10:00:00Z"),
                          итог("t1", "SOURCES_MISSING", "2026-10-20T10:00:00Z")])
    assert queue_bridge.подряд_отказов(ж)["t1"]["подряд"] == 1


@pytest.mark.parametrize("событие", ["task_reopened", "task_result_annulled"])
def test_переоткрытие_снимает_счёт(tmp_path, событие) -> None:
    ж = журнал(tmp_path, [итог("t1", "SOURCES_MISSING", "2026-10-18T10:00:00Z"),
                          итог("t1", "SOURCES_MISSING", "2026-10-19T10:00:00Z"),
                          {"event": событие, "task_id": "t1",
                           "at": "2026-10-19T12:00:00Z"}])
    assert "t1" not in queue_bridge.подряд_отказов(ж)


def test_нечитаемый_журнал_не_придерживает_ничего(tmp_path) -> None:
    """Нет журнала — нет основания придержать. Сбой чтения не останавливает работу."""
    assert queue_bridge.подряд_отказов(tmp_path / "нет.jsonl") == {}


# --- придержание -------------------------------------------------------------

ЗАДАНИЕ = {"task_id": "t1", "canonical_url": "https://animedia.space/title/x"}


def test_отказ_сверх_предела_не_выдаётся(tmp_path) -> None:
    ж = журнал(tmp_path, [итог("t1", "SOURCES_MISSING", "2026-10-18T10:00:00Z"),
                          итог("t1", "SOURCES_MISSING", "2026-10-19T10:00:00Z")])
    к_работе, придержано = queue_bridge.придержать(
        [dict(ЗАДАНИЕ)], журнал=ж, реестр_изменён=None)
    assert к_работе == []
    assert придержано[0]["outcome"] == "SOURCES_MISSING"
    assert придержано[0]["в_ряд"] == 2 and придержано[0]["предел"] == 2
    assert "предел 2" in придержано[0]["почему"]


def test_один_отказ_повтор_разрешает(tmp_path) -> None:
    """Двадцать из 22 успехов пришли ПОСЛЕ одного отказа — его повтор платит."""
    ж = журнал(tmp_path, [итог("t1", "SOURCES_MISSING", "2026-10-19T10:00:00Z")])
    к_работе, придержано = queue_bridge.придержать(
        [dict(ЗАДАНИЕ)], журнал=ж, реестр_изменён=None)
    assert [з["task_id"] for з in к_работе] == ["t1"] and придержано == []


def test_временная_недоступность_источника_терпит_больше(tmp_path) -> None:
    """17 успехов `SOURCE_UNAVAILABLE` рассыпаны по 1–5 повторам: предел выше."""
    assert (queue_bridge.ПРЕДЕЛ_ПОВТОРОВ["SOURCE_UNAVAILABLE"]
            > queue_bridge.ПРЕДЕЛ_ПОВТОРОВ["SOURCES_MISSING"])
    ж = журнал(tmp_path, [итог("t1", "SOURCE_UNAVAILABLE", f"2026-10-1{i}T10:00:00Z")
                          for i in range(1, 5)])
    к_работе, придержано = queue_bridge.придержать(
        [dict(ЗАДАНИЕ)], журнал=ж, реестр_изменён=None)
    assert к_работе and not придержано


def test_новый_реестр_источников_открывает_пересмотр(tmp_path) -> None:
    ж = журнал(tmp_path, [итог("t1", "SOURCES_MISSING", "2026-10-18T10:00:00Z"),
                          итог("t1", "SOURCES_MISSING", "2026-10-19T10:00:00Z")])
    позже = dt.datetime(2026, 10, 20, tzinfo=dt.timezone.utc)
    к_работе, придержано = queue_bridge.придержать(
        [dict(ЗАДАНИЕ)], журнал=ж, реестр_изменён=позже)
    assert к_работе and not придержано


def test_старый_реестр_источников_пересмотра_не_даёт(tmp_path) -> None:
    ж = журнал(tmp_path, [итог("t1", "SOURCES_MISSING", "2026-10-18T10:00:00Z"),
                          итог("t1", "SOURCES_MISSING", "2026-10-19T10:00:00Z")])
    раньше = dt.datetime(2026, 10, 9, tzinfo=dt.timezone.utc)
    к_работе, придержано = queue_bridge.придержать(
        [dict(ЗАДАНИЕ)], журнал=ж, реестр_изменён=раньше)
    assert not к_работе and придержано


def test_страница_отсутствует_реестром_источников_не_открывается(tmp_path) -> None:
    """`PAGE_ABSENT` — не про источники: новый реестр страницу не создаёт."""
    ж = журнал(tmp_path, [итог("t1", "PAGE_ABSENT", "2026-10-18T10:00:00Z"),
                          итог("t1", "PAGE_ABSENT", "2026-10-19T10:00:00Z")])
    позже = dt.datetime(2026, 10, 20, tzinfo=dt.timezone.utc)
    к_работе, придержано = queue_bridge.придержать(
        [dict(ЗАДАНИЕ)], журнал=ж, реестр_изменён=позже)
    assert not к_работе and придержано


def test_успешный_исход_предела_не_имеет(tmp_path) -> None:
    """`TEXT_WRITTEN` держит задание сроком очереди, а не счётом отказов."""
    ж = журнал(tmp_path, [итог("t1", "TEXT_WRITTEN", "2026-10-19T10:00:00Z")] * 3)
    к_работе, придержано = queue_bridge.придержать(
        [dict(ЗАДАНИЕ)], журнал=ж, реестр_изменён=None)
    assert к_работе and not придержано


# --- согласие с правилом удержания ------------------------------------------

def test_исходы_предела_известны_правилу_удержания() -> None:
    """Предел не вводит своих исходов: разойдясь, два перечня держали бы разное."""
    лишние = set(queue_bridge.ПРЕДЕЛ_ПОВТОРОВ) - set(regular.RESULT_HOLD)
    assert not лишние, f"исходы вне RESULT_HOLD: {sorted(лишние)}"


def test_пересмотр_по_источникам_совпадает_с_правилом() -> None:
    assert (tuple(queue_bridge.ПЕРЕСМОТР_ПО_ИСТОЧНИКАМ)
            == tuple(regular.REVIEW_ON_NEW_SOURCES))


# --- выдача заданий ----------------------------------------------------------

@pytest.fixture()
def мост(monkeypatch, tmp_path):
    """Мост с подменённой очередью: сам `_вызвать` в проверках не ходит наружу."""
    monkeypatch.setattr(queue_bridge.actors, "проверить", lambda *a, **k: None)
    monkeypatch.setattr(queue_bridge, "брать_задания_вправе", lambda owner: (True, ""))
    monkeypatch.setattr(queue_bridge, "доставка_описаний", lambda site: (True, ""))
    monkeypatch.setattr(queue_bridge, "_реестр_изменён", lambda *a, **k: None)
    monkeypatch.setattr(queue_bridge, "ЖУРНАЛ_ОЧЕРЕДИ", tmp_path / "нет.jsonl")
    return monkeypatch


def очередь(monkeypatch, партии: list[list[dict]], журнал_: dict,
            вызовы: list[dict], освобождено: list[str]) -> None:
    def ложный(задание, **_):
        вызовы.append(задание)
        if задание["op"] == "release":
            освобождено.append(задание["task_id"])
            return {"released": True}
        return {"tasks": партии.pop(0) if партии else []}
    monkeypatch.setattr(queue_bridge, "_вызвать", ложный)
    monkeypatch.setattr(queue_bridge, "подряд_отказов", lambda *a, **k: журнал_)


def test_придержанное_задание_освобождается_и_заменяется(мост) -> None:
    вызовы: list[dict] = []
    освобождено: list[str] = []
    очередь(мост,
            [[{"task_id": "плохое", "canonical_url": "https://animedia.space/title/x"}],
             [{"task_id": "хорошее", "canonical_url": "https://animedia.space/title/y"}]],
            {"плохое": {"исход": "SOURCES_MISSING", "подряд": 4,
                        "at": "2026-10-19T10:00:00Z"}},
            вызовы, освобождено)
    ответ = queue_bridge.взять(site="animedia.space", owner="editor/claude-auto/run-1")
    assert [з["task_id"] for з in ответ["tasks"]] == ["хорошее"]
    assert ответ["claimed"] == 1
    assert освобождено == ["плохое"], "придержанное задание осталось в аренде"
    assert ответ["withheld"][0]["task_id"] == "плохое"


def test_все_задания_придержаны_называются_и_отправляют_к_кандидатам(мост) -> None:
    вызовы: list[dict] = []
    освобождено: list[str] = []
    очередь(мост,
            [[{"task_id": "п1"}], [{"task_id": "п2"}], [{"task_id": "п3"}]],
            {к: {"исход": "SOURCES_MISSING", "подряд": 3, "at": "2026-10-19T10:00:00Z"}
             for к in ("п1", "п2", "п3")},
            вызовы, освобождено)
    ответ = queue_bridge.взять(site="animedia.space", owner="editor/claude-auto/run-1")
    assert ответ["tasks"] == [] and ответ["claimed"] == 0
    assert len(ответ["withheld"]) == 3 and освобождено == ["п1", "п2", "п3"]
    assert "кандидат" in ответ["next_action"]
    # Круги ограничены: запросов выдачи не больше объявленного числа.
    assert sum(1 for в in вызовы if в["op"] == "next") <= queue_bridge.КРУГОВ_ВЫДАЧИ


def test_выдача_без_повторов_не_делает_лишних_запросов(мост) -> None:
    вызовы: list[dict] = []
    очередь(мост, [[{"task_id": "t1"}]], {}, вызовы, [])
    ответ = queue_bridge.взять(site="animedia.space", owner="editor/claude-auto/run-1")
    assert [з["task_id"] for з in ответ["tasks"]] == ["t1"]
    assert "withheld" not in ответ
    assert sum(1 for в in вызовы if в["op"] == "next") == 1
