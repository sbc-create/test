"""Суточная квота комментариев считается измерением, а не в голове.

Повод. Запуск 2026-10-10 сообщил «101 из 100». Проверено: за сутки UTC в
журналах хранилищ накладок 102 операции `publish-comment` и 1 снятие, то есть
101 — самоотчёт был верен, а перебор настоящий. Причина не в пределе:

* остаток считался ОДИН раз перед партией, а партия публикует до шести;
* публикуют разные исполнители: семь записей тех же суток сделал не прогон
  редактора (`prepared_by` без формы `<роль>/<автоматизация>/<прогон>`), и
  учесть их перед партией было нечем;
* ручной счёт нечем перепроверить.

Поэтому остаток теперь измеряется инструментом, а промпт требует спрашивать его
перед каждой публикацией. Предел не менялся — менялся способ узнать остаток.

Здесь сторожится само правило счёта: окно — сутки UTC, считаются публикации
минус снятия, записи других суток и других операций не берутся.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
СЦЕНАРИЙ = КОРЕНЬ / "automation" / "local" / "comment-quota-audit.py"


def _модуль():
    спец = importlib.util.spec_from_file_location("comment_quota_audit", СЦЕНАРИЙ)
    м = importlib.util.module_from_spec(спец)
    sys.modules["comment_quota_audit"] = м
    спец.loader.exec_module(м)
    return м


def _журнал(каталог: Path, домен: str, строки: list[dict]) -> None:
    место = каталог / "семейство" / "runtime" / "overlays" / домен
    место.mkdir(parents=True, exist_ok=True)
    (место / "history.jsonl").write_text(
        "\n".join(json.dumps(с, ensure_ascii=False) for с in строки) + "\n",
        encoding="utf-8")


@pytest.fixture()
def стенд(tmp_path, monkeypatch):
    м = _модуль()
    monkeypatch.setattr(м, "КОРНИ", tmp_path)
    return м, tmp_path


def test_считает_публикации_минус_снятия(стенд):
    м, корень = стенд
    _журнал(корень, "a.site", [
        {"at": "2026-10-10T01:00:00Z", "op": "publish-comment", "prepared_by": "editor/auto/run-1"},
        {"at": "2026-10-10T02:00:00Z", "op": "publish-comment", "prepared_by": "editor/auto/run-1"},
        {"at": "2026-10-10T03:00:00Z", "op": "unpublish-comment", "prepared_by": "editor/auto/run-1"},
    ])
    публикации, снятия = м.записи("2026-10-10")
    assert (len(публикации), len(снятия)) == (2, 1)


def test_чужие_сутки_не_берутся(стенд):
    м, корень = стенд
    _журнал(корень, "a.site", [
        {"at": "2026-10-09T23:59:59Z", "op": "publish-comment"},
        {"at": "2026-10-10T00:00:01Z", "op": "publish-comment"},
        {"at": "2026-10-11T00:00:01Z", "op": "publish-comment"},
    ])
    публикации, _ = м.записи("2026-10-10")
    assert len(публикации) == 1, "окно — сутки UTC, а не скользящие 24 часа"


def test_чужие_операции_не_берутся(стенд):
    """Подготовка, передача и решение публикациями не являются."""
    м, корень = стенд
    _журнал(корень, "a.site", [
        {"at": "2026-10-10T01:00:00Z", "op": "publish-comment"},
        {"at": "2026-10-10T01:10:00Z", "op": "submit-comment"},
        {"at": "2026-10-10T01:20:00Z", "op": "review-comment"},
        {"at": "2026-10-10T01:30:00Z", "op": "publish-post"},
    ])
    публикации, снятия = м.записи("2026-10-10")
    assert (len(публикации), len(снятия)) == (1, 0)


def test_остаток_и_признак_перебора(стенд, capsys):
    м, корень = стенд
    _журнал(корень, "a.site", [
        {"at": f"2026-10-10T{ч:02d}:00:00Z", "op": "publish-comment",
         "prepared_by": "editor/auto/run-1"} for ч in range(4)
    ])
    код = м.главное(["--day", "2026-10-10", "--limit", "3", "--quiet"])
    свод = json.loads(capsys.readouterr().out.strip())
    assert свод["counted"] == 4 and свод["remaining"] == 0
    assert свод["over_limit"] is True
    assert код == 1, "выработанный предел обязан давать ненулевой код"


def test_места_есть_код_ноль(стенд, capsys):
    м, корень = стенд
    _журнал(корень, "a.site", [
        {"at": "2026-10-10T01:00:00Z", "op": "publish-comment"}])
    код = м.главное(["--day", "2026-10-10", "--limit", "100", "--quiet"])
    свод = json.loads(capsys.readouterr().out.strip())
    assert свод["remaining"] == 99 and свод["over_limit"] is False
    assert код == 0


def test_исполнители_вне_прогонов_видны(стенд, capsys):
    """Именно они и остались неучтёнными при ручном счёте."""
    м, корень = стенд
    _журнал(корень, "a.site", [
        {"at": "2026-10-10T01:00:00Z", "op": "publish-comment",
         "prepared_by": "editor/claude-auto/run-20261010T041501Z"},
        {"at": "2026-10-10T02:00:00Z", "op": "publish-comment",
         "prepared_by": "Редакция"},
    ])
    м.главное(["--day", "2026-10-10"])
    вывод = capsys.readouterr().out
    assert "НЕ прогон" in вывод
    assert "Редакция" in вывод


def test_промпт_требует_измерение_а_не_ручной_счёт():
    """Инструмент без указания его спросить остатка не держит."""
    промпт = (КОРЕНЬ / "docs" / "editor" / "EDITOR_RUN_PROMPT.md").read_text(
        encoding="utf-8")
    assert "comment-quota-audit.py" in промпт
    assert "remaining" in промпт
    assert "ПЕРЕД КАЖДОЙ публикацией" in промпт
