"""REQ-SEO-REGULAR: переданный черновик комментария — работа для шлюза редактора.

Что ловится. Передача черновика (`submit_comment`) появилась 10 октября, а шлюз
считал работой только две вещи: свободное задание очереди на домене цикла и
кандидата без результата. Переданный черновик не входил ни в одно из них,
поэтому при исчерпанных кандидатах шлюз отвечал `no_work`, запуска редактора не
происходило вовсе — и готовый, уже проверенный готовящей стороной текст лежал
бы, пока редактора не позовёт другая причина. При этом промпт редактора велит
разбирать переданное ПЕРВЫМ: обещание было, механизма не было.

Сторожится ровно это: передача поднимает запуск сама, попадает в ответ шлюза, и
недоступность слоя фабрики шлюз не роняет — иначе подсказка о черновиках стоила
бы остановки всего цикла публикаций.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

from seo_operator import editor_run

СЕЙЧАС = dt.datetime(2026, 10, 10, 20, 0, tzinfo=dt.timezone.utc)
ПЕРЕДАННЫЙ = {
    "site": "yummyani.org", "slug": "van-pis", "draft_id": "cd-51b768ab59db",
    "chars": 300, "body_digest": "1df9c4e6",
    "submitted_at": "2026-10-10T17:17:58Z", "submitted_by": "qwen/канал/run-1",
    "note": "проверить факты", "url": "https://yummyani.org/anime/van-pis",
}


def _пусто(tmp_path) -> dict:
    """Стенд без всякой другой работы: ни заданий, ни кандидатов."""
    реестр = tmp_path / "registry.json"
    реестр.write_text(json.dumps({"items": []}), encoding="utf-8")
    кандидаты = tmp_path / "candidates.json"
    кандидаты.write_text(json.dumps({"candidates": []}), encoding="utf-8")
    события = tmp_path / "queue_events.jsonl"
    события.write_text("", encoding="utf-8")
    аренды = tmp_path / "leases.json"
    аренды.write_text(json.dumps({"leases": []}), encoding="utf-8")
    состояние = tmp_path / "state"
    состояние.mkdir()
    return {"registry": реестр, "candidates": кандидаты, "events": события,
            "leases": аренды, "state": состояние}


def _работа(стенд, **ещё):
    return editor_run._work(СЕЙЧАС, refresh=False, recent={}, **стенд, **ещё)


def test_без_работы_и_без_передач_запуска_нет(tmp_path, monkeypatch):
    """Опорное поведение: оно не должно измениться."""
    monkeypatch.setattr(editor_run, "переданные_черновики", lambda: [])
    итог = _работа(_пусто(tmp_path))
    assert итог["run"] is False
    assert "работы нет" in итог["reason"]


def test_переданный_черновик_поднимает_запуск(tmp_path, monkeypatch):
    """Главное свойство: передача сама становится причиной запуска."""
    monkeypatch.setattr(editor_run, "переданные_черновики", lambda: [ПЕРЕДАННЫЙ])
    итог = _работа(_пусто(tmp_path))
    assert итог["run"] is True, итог
    assert "передано черновиков на проверку: 1" in итог["reason"]
    assert итог["handoffs"] == [ПЕРЕДАННЫЙ]
    assert итог["next"] == [], "переданное не подмешивается в кандидатов"


def test_передача_идёт_раньше_кандидатов(tmp_path, monkeypatch):
    """Готовый текст ждёт только решения, а кандидат — ещё и написания."""
    стенд = _пусто(tmp_path)
    стенд["candidates"].write_text(json.dumps({"candidates": [
        {"url": "https://yummyani.org/anime/naruto"}]}), encoding="utf-8")
    monkeypatch.setattr(editor_run, "переданные_черновики", lambda: [ПЕРЕДАННЫЙ])
    итог = _работа(стенд)
    assert итог["run"] is True
    assert "передано черновиков" in итог["reason"], итог["reason"]


def test_недоступный_слой_фабрики_не_роняет_шлюз(monkeypatch):
    """Остановка цикла из-за отсутствующей подсказки хуже отсутствия подсказки."""
    def падает(*а, **к):
        raise RuntimeError("слой фабрики недоступен")

    monkeypatch.setattr("factory.qwen.comments.ожидают_проверки", падает)
    assert editor_run.переданные_черновики() == []


def test_переданное_попадает_в_next_json(tmp_path, monkeypatch, capsys):
    """Редактор читает next.json, и черновики обязаны быть в нём отдельным полем."""
    from seo_operator import cli

    monkeypatch.setattr(editor_run, "STATE", tmp_path)
    monkeypatch.setattr(editor_run, "gate",
                        lambda **к: {"run": True, "state": "run",
                                     "reason": "передано черновиков на проверку: 1",
                                     "handoffs": [ПЕРЕДАННЫЙ], "next": []})
    код = cli.main(["editor-gate"])
    assert код == 10, capsys.readouterr()
    файл = json.loads((tmp_path / "next.json").read_text(encoding="utf-8"))
    assert файл["handoffs"] == [ПЕРЕДАННЫЙ]
    assert файл["candidates"] == []
    assert "domains" in файл and файл["domains"], "перечень доменов не потерян"
