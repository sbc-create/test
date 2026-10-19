"""REQ-CELL-WARMUP-MEMORY: прогрев отказывает по памяти сам и с числами.

Повод, измеренный 19.10. Активация lords-01 упала с «процесс не работает» через
67.5 с. Причина не в коде: живой процесс витрины занимает **1 699 МиБ** (держит
в памяти каталог 20 МиБ и подробности 119 МиБ), а свободной памяти на хосте в
06:50Z было **1 764 МиБ** — на вторую копию места не оставалось. Счётчик
`oom_kill` хоста 38. Три активации меньших витрин в то же утро прошли при
2 317–3 648 МиБ.

Пока решение принимает ядро, в отчёте остаётся «процесс не работает», и причина
выглядит дефектом кода, которого нет. Поэтому прогрев проверяет память ДО
старта и отказывает своей причиной, где названы оба числа.

Третий исход обязателен: если измерить нечего (нет `MemAvailable`, нет живого
процесса), выпуск НЕ останавливается — отказ по незнанию хуже отсутствия
проверки.
"""
from __future__ import annotations

import pytest

from factory.cell import privileged


def test_памяти_хватает(monkeypatch):
    monkeypatch.setattr(privileged, "доступная_память_миб", lambda: 4000.0)
    monkeypatch.setattr(privileged, "память_живого", lambda port: 1700.0)
    и = privileged.память_под_прогрев(9110)
    assert и["measured"] is True and и["ok"] is True
    assert и["live_rss_mib"] == 1700 and и["required_mib"] == 1955


def test_памяти_не_хватает_и_числа_названы(monkeypatch):
    """Ровно случай lords-01 19.10: 1 764 свободно при живом процессе 1 699."""
    monkeypatch.setattr(privileged, "доступная_память_миб", lambda: 1764.0)
    monkeypatch.setattr(privileged, "память_живого", lambda port: 1699.0)
    и = privileged.память_под_прогрев(9110)
    assert и["ok"] is False
    assert "1954" in и["reason"] or "1954" in str(и["required_mib"])
    assert "1699" in и["reason"] and "1764" in и["reason"]


def test_ровно_на_границе_проходит(monkeypatch):
    monkeypatch.setattr(privileged, "доступная_память_миб", lambda: 1150.0)
    monkeypatch.setattr(privileged, "память_живого", lambda port: 1000.0)
    assert privileged.память_под_прогрев(9110)["ok"] is True


def test_нет_живого_процесса_выпуск_не_останавливается(monkeypatch):
    """Первая активация витрины: второй копии нет, мерить нечего."""
    monkeypatch.setattr(privileged, "доступная_память_миб", lambda: 500.0)
    monkeypatch.setattr(privileged, "память_живого", lambda port: None)
    и = privileged.память_под_прогрев(9110)
    assert и["measured"] is False and и["ok"] is True
    assert "не найден" in и["reason"]


def test_meminfo_не_прочитан_выпуск_не_останавливается(monkeypatch):
    monkeypatch.setattr(privileged, "доступная_память_миб", lambda: None)
    monkeypatch.setattr(privileged, "память_живого", lambda port: 1700.0)
    и = privileged.память_под_прогрев(9110)
    assert и["measured"] is False and и["ok"] is True
    assert "MemAvailable" in и["reason"]


def test_запас_настраивается(monkeypatch):
    monkeypatch.setattr(privileged, "доступная_память_миб", lambda: 1800.0)
    monkeypatch.setattr(privileged, "память_живого", lambda port: 1700.0)
    assert privileged.память_под_прогрев(9110, запас=1.0)["ok"] is True
    assert privileged.память_под_прогрев(9110, запас=1.15)["ok"] is False


def test_живой_хост_читается():
    """Отрицательный контроль: на этом хосте оба измерения работают."""
    свободно = privileged.доступная_память_миб()
    assert свободно is not None and свободно > 0
    # Порт, на котором заведомо никто не слушает, обязан дать None, а не ноль.
    assert privileged.память_живого(65123) is None


def test_память_живого_находит_процесс_по_порту(tmp_path):
    """Поиск идёт по строке запуска `--port <порт>`, каталог /proc подменяем."""
    proc = tmp_path / "4242"
    proc.mkdir()
    (proc / "cmdline").write_bytes(
        b"/usr/bin/python3\x00/srv/x/src/frontend.py\x00--port\x009110\x00")
    (proc / "status").write_text("Name:\tpython3\nVmRSS:\t 1739068 kB\n",
                                 encoding="utf-8")
    assert round(privileged.память_живого(9110, proc=tmp_path)) == 1698
    # Чужой порт — None, а не ноль: «не нашли» и «нулевой размер» разные вещи.
    assert privileged.память_живого(9111, proc=tmp_path) is None


@pytest.mark.parametrize("свободно,живой,ожидание", [
    (3648.0, 1087.0, True),   # lords-02 07:06Z — прошла
    (2317.0, 1155.0, True),   # animedia-01 07:19Z — прошла
    (3542.0, 1246.0, True),   # zona-02 07:41Z — прошла
    (1764.0, 1699.0, False),  # lords-01 06:52Z — упала
])
def test_утро_19_10_воспроизводится(monkeypatch, свободно, живой, ожидание):
    """Четыре настоящие активации: проверка обязана различать их так же."""
    monkeypatch.setattr(privileged, "доступная_память_миб", lambda: свободно)
    monkeypatch.setattr(privileged, "память_живого", lambda port: живой)
    assert privileged.память_под_прогрев(9110)["ok"] is ожидание
