"""Сверка живого build с журналом исполнителя: четыре состояния и поиск реестра.

Повод для инструмента. 11 октября две витрины были названы выложенными, когда
выкладка ещё не начиналась: сценарий ждал зелёного CI, его журнал был пуст, и
«закоммичено и поставлено в очередь» прочиталось как «выложено». Ошибка
безобидна ровно до того момента, когда по ней включают строгую проверку или
снимают паузу публикаций.

Поэтому источников ДВА и ни один не выводится из другого: заголовок
`x-site-factory-build-id` живого ответа и журнал исполнителя. Состояний
четыре, и различие между двумя из них стоило отдельной правки:

* **новее журнала** — витрина отдаёт то, чего в журнале нет. Обычное
  состояние сразу после выкладки: заявка закрылась минуту назад, запись не
  дописана. В беды НЕ идёт, иначе инструмент кричал бы на норму;
* **отстала** — исполнитель закрыл выпуск новее того, что живёт. Вот это
  разбирать.

Повод для правки поиска реестра — своя же ошибка: первая редакция искала
реестр только от расположения скрипта и при неудаче печатала «реестр ячеек не
прочитан» без пути. SEO-сессия запустила инструмент вне моего рабочего дерева
и получила отказ без того, что нужно для разбора, — то есть я нарушил
собственное правило дня («не измерено» обязано называть причину) в том самом
инструменте, которым его внедрял.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
СЦЕНАРИЙ = КОРЕНЬ / "automation" / "local" / "live-build-status.py"


def _модуль():
    спец = importlib.util.spec_from_file_location("live_build_status", СЦЕНАРИЙ)
    м = importlib.util.module_from_spec(спец)
    sys.modules["live_build_status"] = м
    спец.loader.exec_module(м)
    return м


def реестр(каталог: Path, ячейки: list[dict]) -> Path:
    (каталог / "config").mkdir(parents=True, exist_ok=True)
    путь = каталог / "config" / "site-cells.json"
    путь.write_text(json.dumps({"schema_version": 1, "cells": ячейки},
                               ensure_ascii=False), encoding="utf-8")
    return путь


# --- поиск реестра --------------------------------------------------------

def test_реестр_находится_по_явному_корню(tmp_path):
    м = _модуль()
    реестр(tmp_path, [{"domain": "x.test", "site_id": "x-01"}])
    пары, причина = м.домены_реестра(tmp_path)
    assert пары == {"x.test": "x-01"}
    assert "ячеек 1" in причина


def test_реестр_находится_от_расположения_скрипта(monkeypatch, tmp_path):
    """Инструмент должен работать, запущенный из любого каталога."""
    м = _модуль()
    monkeypatch.chdir(tmp_path)
    пары, причина = м.домены_реестра(None)
    assert пары, причина
    assert "site-cells.json" in причина


def test_отказ_называет_проверенные_пути(tmp_path, monkeypatch):
    """Отказ без пути бесполезен — ровно то, на чём спотыкнулась SEO-сессия."""
    м = _модуль()
    monkeypatch.setattr(м, "ИМЯ_РЕЕСТРА",
                        Path("config") / "нет-такого-реестра.json")
    monkeypatch.chdir(tmp_path)
    пары, причина = м.домены_реестра(tmp_path)
    assert пары == {}
    assert "не найден" in причина
    assert "искал:" in причина
    assert "нет-такого-реестра.json" in причина


def test_битый_реестр_отличается_от_отсутствующего(tmp_path):
    м = _модуль()
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "site-cells.json").write_text("{не json",
                                                         encoding="utf-8")
    пары, причина = м.домены_реестра(tmp_path)
    assert пары == {}
    assert "не разбирается как JSON" in причина


def test_реестр_без_пар_называется_отдельно(tmp_path):
    """Прочитан, но пуст — это не «не найден»: действия разные."""
    м = _модуль()
    реестр(tmp_path, [])
    пары, причина = м.домены_реестра(tmp_path)
    assert пары == {}
    assert "ни одной пары" in причина


def test_ячейка_без_домена_или_site_id_пропускается(tmp_path):
    м = _модуль()
    реестр(tmp_path, [{"domain": "x.test"}, {"site_id": "y-01"},
                      {"domain": "z.test", "site_id": "z-01"}])
    пары, _п = м.домены_реестра(tmp_path)
    assert пары == {"z.test": "z-01"}


# --- четыре состояния -----------------------------------------------------

@pytest.fixture
def модуль(monkeypatch, tmp_path):
    м = _модуль()
    monkeypatch.setattr(м, "РЕЗУЛЬТАТЫ", tmp_path / "results")
    (tmp_path / "results").mkdir()
    return м


def выпуск(модуль, site_id: str, commit: str, когда: str,
           статус: str = "ok", этап: str = "live_verified") -> None:
    путь = модуль.РЕЗУЛЬТАТЫ / f"{site_id}-code-{commit[:8]}.json"
    путь.write_text(json.dumps({
        "site_id": site_id, "commit": commit, "status": статус,
        "outcome": {"stage": этап},
        "finished_at": когда}, ensure_ascii=False), encoding="utf-8")


def test_совпало(модуль, monkeypatch):
    выпуск(модуль, "x-01", "aaaaaaaaaaaa1111", "2026-10-11T19:00:00Z")
    monkeypatch.setattr(модуль, "живой_build",
                        lambda д, таймаут=25: ("aaaaaaaaaaaa-x-01", "код 200"))
    и = модуль.разбор("x.test", "x-01")
    assert и["состояние"] == "совпало"
    assert "последний закрытый" in и["вывод"]


def test_новее_журнала_не_беда(модуль, monkeypatch):
    """Выкладка прошла минуту назад, запись не дописана — это норма."""
    выпуск(модуль, "x-01", "aaaaaaaaaaaa1111", "2026-10-11T19:00:00Z")
    monkeypatch.setattr(модуль, "живой_build",
                        lambda д, таймаут=25: ("bbbbbbbbbbbb-x-01", "код 200"))
    и = модуль.разбор("x.test", "x-01")
    assert и["состояние"] == "новее журнала"
    assert "заявка свежая" in и["вывод"]
    assert "ОТСТАЛА" not in и["вывод"]


def test_витрина_отстала_это_беда(модуль, monkeypatch):
    """Исполнитель закрыл новее, чем живёт: выпуск не подхватился."""
    выпуск(модуль, "x-01", "aaaaaaaaaaaa1111", "2026-10-11T19:00:00Z")
    выпуск(модуль, "x-01", "bbbbbbbbbbbb2222", "2026-10-11T19:30:00Z")
    monkeypatch.setattr(модуль, "живой_build",
                        lambda д, таймаут=25: ("aaaaaaaaaaaa-x-01", "код 200"))
    и = модуль.разбор("x.test", "x-01")
    assert и["состояние"] == "отстала"
    assert "ВИТРИНА ОТСТАЛА" in и["вывод"]


def test_витрина_не_ответила_это_не_измерено(модуль, monkeypatch):
    выпуск(модуль, "x-01", "aaaaaaaaaaaa1111", "2026-10-11T19:00:00Z")
    monkeypatch.setattr(модуль, "живой_build",
                        lambda д, таймаут=25: ("", "витрина не ответила (curl 28)"))
    и = модуль.разбор("x.test", "x-01")
    assert и["состояние"] == "не измерено"
    assert "НЕ ИЗМЕРЕНО" in и["вывод"]
    assert "curl 28" in и["вывод"]


def test_журнал_пуст_а_витрина_живёт(модуль, monkeypatch):
    monkeypatch.setattr(модуль, "живой_build",
                        lambda д, таймаут=25: ("aaaaaaaaaaaa-x-01", "код 200"))
    и = модуль.разбор("x.test", "x-01")
    assert и["состояние"] == "вне журнала"
    assert "заявок на код в журнале нет вовсе" in и["вывод"]


def test_суффикс_build_не_обязан_совпадать_с_site_id(модуль, monkeypatch):
    """У части витрин суффикс свой: `animedia-space` против `animedia-02`.

    Сверка идёт по ПРЕФИКСУ-коммиту; равенство строк дало бы ложную «отставшую
    витрину» у двух Animedia.
    """
    выпуск(модуль, "animedia-02", "cccccccccccc3333", "2026-10-11T19:00:00Z")
    monkeypatch.setattr(
        модуль, "живой_build",
        lambda д, таймаут=25: ("cccccccccccc-animedia-space", "код 200"))
    и = модуль.разбор("animedia.space", "animedia-02")
    assert и["состояние"] == "совпало", и["вывод"]


def test_домен_вне_реестра_даёт_код_2(tmp_path, capsys):
    """Имя site_id не угадывается: домена нет в реестре — значит нет."""
    м = _модуль()
    реестр(tmp_path, [{"domain": "x.test", "site_id": "x-01"}])
    код = м.главное(["--root", str(tmp_path), "чужой.test"])
    assert код == 2
    assert "вне реестра" in capsys.readouterr().err
