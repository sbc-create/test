"""Передача задания от координатора готовящей стороне.

ПОВОД ИЗМЕРЕННЫЙ, 24.10. Роль `qwen` не вправе брать задания — `queue-next`
ей закрыт решением владельца 09.10, и это правильно. Но узнать, что ей
поручено, она не могла НИЧЕМ: `editorial_queue_find` требует адрес карточки
(то есть ответ надо уже знать), а `editorial_queue_status` отдаёт сводные
числа без перечня (`leases_active: 0` и всё). Передача держалась на том, что
координатор назовёт адрес словами в задании, — это не механизм.

Отдельно проверяется, что просроченная аренда НЕ выдаётся за поручение:
измерено 24.10 — из 16 открытых записей 13 были просрочены, у 11 владелец
пуст. Послать готовить по отпущенному заданию значит отдать одну работу
дважды.
"""
from __future__ import annotations

import json
import pathlib
import sys

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
if str(КОРЕНЬ) not in sys.path:
    sys.path.insert(0, str(КОРЕНЬ))

from factory.qwen import mcp, queue_bridge  # noqa: E402

СЕЙЧАС = "2026-10-24T15:00:00Z"


def _аренда(**kw) -> dict:
    а = {"task_id": "t1", "site": "d.site", "work_id": "slug-1",
         "canonical_url": "https://d.site/title/slug-1",
         "owner": "editor/claude-auto/run-1",
         "acquired_at": "2026-10-24T14:30:00Z",
         "expires_at": "2026-10-24T15:15:00Z", "attempts": 0}
    а.update(kw)
    return а


def _подставить(monkeypatch, tmp_path, аренды, записи=()):
    ф = tmp_path / "leases.json"
    ф.write_text(json.dumps({"leases": list(аренды)}), encoding="utf-8")
    р = tmp_path / "registry.json"
    р.write_text(json.dumps({"items": list(записи)}), encoding="utf-8")
    monkeypatch.setattr(queue_bridge, "ФАЙЛ_АРЕНД", ф)
    monkeypatch.setattr(queue_bridge, "РЕЕСТР_ЗАПИСЕЙ", р)


def test_действующая_аренда_показывается_как_поручение(monkeypatch, tmp_path):
    _подставить(monkeypatch, tmp_path, [_аренда()])
    и = queue_bridge.выданные("d.site", сейчас=СЕЙЧАС)
    assert и["assigned_count"] == 1, и
    assert и["expired_count"] == 0
    assert и["assigned"][0]["task_id"] == "t1"
    assert и["assigned"][0]["owner"] == "editor/claude-auto/run-1"


def test_просроченная_аренда_поручением_не_считается(monkeypatch, tmp_path):
    """Срок вышел — задание уже отпущено, готовить по нему нельзя."""
    _подставить(monkeypatch, tmp_path,
                [_аренда(expires_at="2026-10-24T14:45:00Z")])
    и = queue_bridge.выданные("d.site", сейчас=СЕЙЧАС)
    assert и["assigned_count"] == 0, и
    assert и["expired_count"] == 1
    assert "отпущено" in и["note"]


def test_закрытая_аренда_не_показывается(monkeypatch, tmp_path):
    _подставить(monkeypatch, tmp_path,
                [_аренда(closed_at="2026-10-24T14:40:00Z")])
    и = queue_bridge.выданные("d.site", сейчас=СЕЙЧАС)
    assert и["assigned_count"] == 0 and и["expired_count"] == 0


def test_задание_и_заголовок_берутся_из_реестра(monkeypatch, tmp_path):
    """Готовящей стороне нужен БРИФ, а не только адрес."""
    запись = {"target_site": "d.site", "title_id": "slug-1",
              "headline": "Произведение", "content_type": "TITLE_DESCRIPTION",
              "status": "NEEDS_SOURCES",
              "provenance": {"brief": {"что_нужно": "описать каталог"}}}
    _подставить(monkeypatch, tmp_path, [_аренда()], [запись])
    с = queue_bridge.выданные("d.site", сейчас=СЕЙЧАС)["assigned"][0]
    assert с["headline"] == "Произведение"
    assert с["content_type"] == "TITLE_DESCRIPTION"
    assert с["brief"] == {"что_нужно": "описать каталог"}
    assert с["registry_status"] == "NEEDS_SOURCES"


def test_отбор_по_витрине(monkeypatch, tmp_path):
    _подставить(monkeypatch, tmp_path,
                [_аренда(), _аренда(task_id="t2", site="другая.site")])
    assert queue_bridge.выданные("d.site", сейчас=СЕЙЧАС)["assigned_count"] == 1
    assert queue_bridge.выданные(сейчас=СЕЙЧАС)["assigned_count"] == 2


def test_нет_журнала_аренд_это_пусто_а_не_падение(monkeypatch, tmp_path):
    monkeypatch.setattr(queue_bridge, "ФАЙЛ_АРЕНД", tmp_path / "нет.json")
    monkeypatch.setattr(queue_bridge, "РЕЕСТР_ЗАПИСЕЙ", tmp_path / "нет2.json")
    и = queue_bridge.выданные("d.site", сейчас=СЕЙЧАС)
    assert и["assigned_count"] == 0 and и["expired_count"] == 0


def test_инструмент_читающий_и_доступен_готовящей_стороне():
    """Прав не расширяет: ни операции, ни записи — значит доступен `qwen`."""
    assert "editorial_queue_assigned" in mcp.ИНСТРУМЕНТЫ
    assert "editorial_queue_assigned" not in mcp.ПИШУЩИЕ
    assert mcp.ОПЕРАЦИЯ_ИНСТРУМЕНТА.get("editorial_queue_assigned") is None


def test_инструмент_виден_в_режиме_только_чтения(monkeypatch):
    monkeypatch.setattr(mcp, "ТОЛЬКО_ЧТЕНИЕ", True)
    assert "editorial_queue_assigned" in mcp.доступные()
