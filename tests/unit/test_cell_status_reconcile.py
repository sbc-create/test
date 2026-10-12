"""Сверка паспорта ячейки со следами исполнителя: что она вправе написать.

Инструмент трогает паспорт сайта, поэтому проверяется не только «переводит
отставший статус», но и границы, за которые он не выходит:

* по умолчанию не пишет вовсе;
* ставит ровно `live` и только по подтверждённой НЕ сухой активации;
* `not_extracted` не перезаписывает: это слово о происхождении витрины, а не о
  её жизни, и затереть его значило бы потерять сведение;
* записей в реестре не создаёт и `live` без следов не снимает — отсутствие
  следа не доказывает отсутствия активации.

Сеть и живой реестр не нужны: и следы, и реестр подставные.
"""
from __future__ import annotations

import importlib.util
import io
import json
from contextlib import redirect_stdout
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
ИСТОЧНИК = КОРЕНЬ / "automation" / "local" / "cell-status-reconcile.py"


def _модуль():
    спец = importlib.util.spec_from_file_location("reconcile", ИСТОЧНИК)
    м = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(м)
    return м


@pytest.fixture(scope="module")
def м():
    return _модуль()


def след(каталог: Path, имя: str, **поля) -> None:
    каталог.mkdir(parents=True, exist_ok=True)
    основа = {"operation": "activate", "status": "ok", "dry_run": False,
              "finished_at": "2026-10-12T10:00:00+00:00"}
    (каталог / f"{имя}.json").write_text(
        json.dumps({**основа, **поля}, ensure_ascii=False), encoding="utf-8")


def реестр(путь: Path, записи: list[tuple[str, str]]) -> Path:
    """Минимальный реестр: (site_id, status). Форму разбирает сам реестр."""
    путь.parent.mkdir(parents=True, exist_ok=True)
    путь.write_text(json.dumps({"schema_version": 1, "cells": [
        {"site_id": и, "domain": f"{и}.example.invalid", "status": с,
         "repo": {"path": f"var/site-repos/{и}"}}
        for и, с in записи]}, ensure_ascii=False), encoding="utf-8")
    return путь


def прогон(м, следы: Path, рег: Path, *, писать: bool = False):
    арг = ["--results", str(следы), "--registry", str(рег)]
    if писать:
        арг.append("--confirm-writes")
    буфер = io.StringIO()
    with redirect_stdout(буфер):
        код = м.главное(арг)
    return код, буфер.getvalue()


def статусы(рег: Path) -> dict[str, str]:
    данные = json.loads(рег.read_text(encoding="utf-8"))
    return {я["site_id"]: я.get("status") for я in данные["cells"]}


def test_по_умолчанию_не_пишет(м, tmp_path):
    следы = tmp_path / "results"
    след(следы, "a", site_id="a")
    рег = реестр(tmp_path / "реестр.json", [("a", "staged")])
    код, вывод = прогон(м, следы, рег)
    assert код == 1, "отставший паспорт — это расхождение"
    assert "нужен --confirm-writes" in вывод
    assert статусы(рег) == {"a": "staged"}, "записал без разрешения"


def test_переводит_отставший_статус(м, tmp_path):
    следы = tmp_path / "results"
    след(следы, "a", site_id="a")
    след(следы, "b", site_id="b")
    рег = реестр(tmp_path / "реестр.json", [("a", "staged"), ("b", "planned")])
    код, вывод = прогон(м, следы, рег, писать=True)
    assert код == 0, вывод
    assert статусы(рег) == {"a": "live", "b": "live"}


def test_повторный_прогон_ничего_не_находит(м, tmp_path):
    следы = tmp_path / "results"
    след(следы, "a", site_id="a")
    рег = реестр(tmp_path / "реестр.json", [("a", "staged")])
    прогон(м, следы, рег, писать=True)
    код, вывод = прогон(м, следы, рег)
    assert код == 0
    assert "паспорт от следов не отстал" in вывод


def test_not_extracted_не_перезаписывается(м, tmp_path):
    следы = tmp_path / "results"
    след(следы, "a", site_id="a")
    рег = реестр(tmp_path / "реестр.json", [("a", "not_extracted")])
    код, вывод = прогон(м, следы, рег, писать=True)
    assert статусы(рег) == {"a": "not_extracted"}
    assert "противоречие" in вывод
    assert код == 0, "противоречие — не отказ инструмента, а предмет решения"


def test_сухая_активация_следом_не_считается(м, tmp_path):
    следы = tmp_path / "results"
    след(следы, "a", site_id="a", dry_run=True)
    рег = реестр(tmp_path / "реестр.json", [("a", "staged")])
    код, вывод = прогон(м, следы, рег, писать=True)
    assert статусы(рег) == {"a": "staged"}
    assert код == 2, "следов подтверждённой активации нет вовсе"


def test_неудачная_активация_следом_не_считается(м, tmp_path):
    следы = tmp_path / "results"
    след(следы, "a", site_id="a", status="failed")
    след(следы, "b", site_id="b", status="rejected")
    след(следы, "c", site_id="c")
    рег = реестр(tmp_path / "реестр.json",
                 [("a", "staged"), ("b", "staged"), ("c", "staged")])
    прогон(м, следы, рег, писать=True)
    assert статусы(рег) == {"a": "staged", "b": "staged", "c": "live"}


def test_чужая_операция_следом_не_считается(м, tmp_path):
    следы = tmp_path / "results"
    след(следы, "a", site_id="a", operation="editorial")
    след(следы, "b", site_id="b")
    рег = реестр(tmp_path / "реестр.json", [("a", "staged"), ("b", "staged")])
    прогон(м, следы, рег, писать=True)
    assert статусы(рег) == {"a": "staged", "b": "live"}


def test_битый_след_не_роняет_и_не_считается(м, tmp_path):
    следы = tmp_path / "results"
    следы.mkdir(parents=True)
    (следы / "битый.json").write_text("не json", encoding="utf-8")
    след(следы, "b", site_id="b")
    рег = реестр(tmp_path / "реестр.json", [("b", "staged")])
    код, _вывод = прогон(м, следы, рег, писать=True)
    assert код == 0
    assert статусы(рег) == {"b": "live"}


def test_запись_в_реестре_не_создаётся(м, tmp_path):
    следы = tmp_path / "results"
    след(следы, "неизвестный", site_id="неизвестный")
    след(следы, "b", site_id="b")
    рег = реестр(tmp_path / "реестр.json", [("b", "staged")])
    код, вывод = прогон(м, следы, рег, писать=True)
    assert код == 0
    assert статусы(рег) == {"b": "live"}
    assert "записи в реестре нет" in вывод
    assert "неизвестный" in вывод


def test_live_без_следов_не_снимается(м, tmp_path):
    """Отсутствие следа не доказывает отсутствия активации."""
    следы = tmp_path / "results"
    след(следы, "b", site_id="b")
    рег = реестр(tmp_path / "реестр.json", [("b", "staged"), ("старая", "live")])
    код, вывод = прогон(м, следы, рег, писать=True)
    assert статусы(рег)["старая"] == "live"
    assert "следов активации нет" in вывод
    assert код == 0


def test_нет_следов_вовсе_это_исход_два(м, tmp_path):
    """Нечем сверять — отдельный исход, а не «расхождений нет»."""
    рег = реестр(tmp_path / "реестр.json", [("a", "staged")])
    код, _вывод = прогон(м, tmp_path / "пусто", рег)
    assert код == 2
    assert статусы(рег) == {"a": "staged"}


def test_ставится_ровно_live(м, tmp_path):
    """Никаких придуманных слов: статус один и он объявлен постоянной."""
    assert м.ЖИВАЯ == "live"
    assert "not_extracted" in м.НЕ_ТРОГАТЬ
