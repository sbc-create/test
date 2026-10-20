"""Разделение ждущих черновиков на три состояния, а не одно число.

Смысл инструмента в разделении: «ждёт под паузой», «ждёт с названной причиной»
и «ждёт БЕЗ причины» требуют разного, и сведение их в одно число спрятало бы
третье — единственное, что требует работы. Поэтому проверяется именно оно.

Отрицательные контроли, названные заранее:

* опубликованный слаг не считается ждущим — иначе очередь не кончалась бы;
* черновик под паузой НЕ попадает в «без причины»: причина у него внешняя;
* отзыв делает черновик «с названной причиной» независимо от вердикта —
  отказ это тоже обработка, а не ожидание;
* код возврата 3 даётся только при наличии черновиков без причины.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
_с = importlib.util.spec_from_file_location(
    "draft_backlog", КОРЕНЬ / "automation/local/draft-backlog.py")
ИНСТР = importlib.util.module_from_spec(_с)
_с.loader.exec_module(ИНСТР)


def _хранилище(tmp_path, домен, черновики, журнал=()):
    к = tmp_path / "srv" / домен
    к.mkdir(parents=True, exist_ok=True)
    (к / "drafts.json").write_text(
        json.dumps({"site": домен, "items": черновики}, ensure_ascii=False),
        encoding="utf-8")
    (к / "history.jsonl").write_text(
        "\n".join(json.dumps(з, ensure_ascii=False) for з in журнал),
        encoding="utf-8")
    return к


def _настроить(monkeypatch, tmp_path):
    monkeypatch.setattr(ИНСТР, "ЖУРНАЛЫ", str(tmp_path / "srv/*/history.jsonl"))
    monkeypatch.setattr(ИНСТР, "ЧЕРНОВИКИ", str(tmp_path / "srv/*/drafts.json"))


ЧЕРНОВИК = {"slug": "a", "body": "x", "body_digest": "d",
            "prepared_at": "2026-10-01T00:00:00Z", "state": "verified",
            "quality_problems": []}


def test_черновик_без_причины_виден(monkeypatch, tmp_path, capsys):
    _хранилище(tmp_path, "animeg0.site", {"a": ЧЕРНОВИК})
    _настроить(monkeypatch, tmp_path)
    assert ИНСТР.main([]) == 3
    вывод = capsys.readouterr().out
    assert "БЕЗ причины              1" in вывод
    assert "animeg0.site" in вывод


def test_отзыв_переводит_в_с_причиной(monkeypatch, tmp_path, capsys):
    """Отказ — это обработка, а не ожидание."""
    _хранилище(tmp_path, "animeg0.site", {"a": ЧЕРНОВИК},
               [{"op": "review", "slug": "a", "verdict": "rejected",
                 "notes": ["причина"], "at": "2026-10-20T00:00:00Z"}])
    _настроить(monkeypatch, tmp_path)
    assert ИНСТР.main([]) == 0
    assert "с названной причиной     1" in capsys.readouterr().out


def test_пауза_не_считается_отсутствием_причины(monkeypatch, tmp_path, capsys):
    _хранилище(tmp_path, "zonafilm.space", {"a": ЧЕРНОВИК})
    _настроить(monkeypatch, tmp_path)
    assert ИНСТР.main([]) == 0
    вывод = capsys.readouterr().out
    assert "в паузе                  1" in вывод
    assert "БЕЗ причины              0" in вывод


def test_опубликованный_не_ждёт(monkeypatch, tmp_path, capsys):
    _хранилище(tmp_path, "animeg0.site", {"a": ЧЕРНОВИК},
               [{"op": "publish", "slug": "a", "at": "2026-10-20T00:00:00Z"}])
    _настроить(monkeypatch, tmp_path)
    assert ИНСТР.main([]) == 0
    assert "ждёт публикации: 0" in capsys.readouterr().out


def test_порог_часов_применяется(monkeypatch, tmp_path, capsys):
    свежий = dict(ЧЕРНОВИК, prepared_at="2099-01-01T00:00:00Z")
    _хранилище(tmp_path, "animeg0.site", {"a": свежий})
    _настроить(monkeypatch, tmp_path)
    # «подготовлен в будущем» даёт отрицательный возраст — порог его отсекает
    assert ИНСТР.main(["--hours", "24"]) == 0


def test_пауза_объявлена_перечнем():
    assert "zonafilm12.site" in ИНСТР.ПАУЗА
    assert "animeg0.site" not in ИНСТР.ПАУЗА
