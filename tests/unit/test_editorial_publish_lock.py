"""Замок публикации сайта: два публикующих не стирают записи друг друга.

Файл правок заменяется целиком, состав собирается из прочитанного. Без замка
два процесса (фоновый редактор через MCP и сессия) читали одинаковый состав, и
доставка второго стирала запись первого. 19.10 16:25Z публикация сессии ушла
через 52 с после старта редактора — совпадение по сайту было делом случая.
"""
from __future__ import annotations

import json
import multiprocessing as mp
import time
from pathlib import Path

import pytest

from factory.qwen import editorial


def _публикатор(каталог: str, имя: str, пауза: float) -> None:
    """Прочитать → подождать → записать целиком: схема `публиковать`."""
    к = Path(каталог)
    with editorial._замок_публикации(к, ждать_с=30):
        файл = к / "store.json"
        состав = json.loads(файл.read_text(encoding="utf-8"))
        time.sleep(пауза)
        состав.append(имя)
        файл.write_text(json.dumps(состав), encoding="utf-8")


def test_два_процесса_не_теряют_записи(tmp_path):
    (tmp_path / "store.json").write_text("[]", encoding="utf-8")
    ctx = mp.get_context("fork")
    процессы = [ctx.Process(target=_публикатор, args=(str(tmp_path), f"p{i}", 0.3)) for i in range(3)]
    for п in процессы:
        п.start()
    for п in процессы:
        п.join(30)
        assert п.exitcode == 0
    assert sorted(json.loads((tmp_path / "store.json").read_text(encoding="utf-8"))) == ["p0", "p1", "p2"]


def _держать(каталог: str, событие, сколько: float) -> None:
    with editorial._замок_публикации(Path(каталог), ждать_с=5):
        событие.set()
        time.sleep(сколько)


def test_занятый_сайт_даёт_отказ_а_не_запись_поверх(tmp_path):
    ctx = mp.get_context("fork")
    занято = ctx.Event()
    держатель = ctx.Process(target=_держать, args=(str(tmp_path), занято, 4))
    держатель.start()
    assert занято.wait(10)
    with pytest.raises(editorial.ОперацияОтклонена, match="занят другой публикацией"):
        with editorial._замок_публикации(tmp_path, ждать_с=1):
            pass
    держатель.join(15)


def test_замок_освобождается_после_ошибки(tmp_path):
    with pytest.raises(ValueError):
        with editorial._замок_публикации(tmp_path, ждать_с=1):
            raise ValueError("сбой доставки")
    with editorial._замок_публикации(tmp_path, ждать_с=1):
        pass


def test_публикация_снятие_и_откат_идут_под_замком():
    """Все три пути, заменяющие состав целиком, берут замок до чтения состава."""
    import inspect

    for функция in (editorial.публиковать, editorial.снять, editorial.откатить):
        код = inspect.getsource(функция)
        assert "_замок_публикации(" in код, функция.__name__
        assert код.index("_замок_публикации(") < код.index("_текущее(s)"), функция.__name__
