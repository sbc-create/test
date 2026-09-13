"""Жизненный цикл локального стенда: поднялся, ответил, остановлен, следов нет.

Поводом стал код возврата 144 у фоновой задачи «Serve the final Lords
candidate». Разбор показал, что сервер был исправен: его убил сценарий
уборки, искавший процессы по подстроке `http.server` — и нашедший в том числе
СОБСТВЕННУЮ командную строку, потому что подстрока входит в неё же.

Отсюда требования, которые проверяются ниже: порт назначает система,
готовность определяется ответом, остановка адресуется идентификатором
процесса, а не совпадением строки, и после остановки не остаётся ни процесса,
ни занятого порта.
"""
from __future__ import annotations

import concurrent.futures
import pathlib
import urllib.request

import pytest

from scripts.lords_stand import Стенд, поднять, порт_занят, стенд, свободный_порт

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ВИТРИНА = КОРЕНЬ / "var" / "probe"


@pytest.fixture(scope="module", autouse=True)
def витрина_есть():
    if not (ВИТРИНА / "index.html").is_file():
        pytest.skip(f"собранной витрины нет: {ВИТРИНА}")


class TestОдинЗапуск:
    def test_поднимается_и_отвечает(self):
        with стенд(ВИТРИНА) as с:
            with urllib.request.urlopen(с.база + "/", timeout=10) as о:
                assert о.status == 200
            assert порт_занят(с.порт)

    def test_остановка_полная(self):
        с = поднять(ВИТРИНА)
        исход = с.остановить()
        assert исход["outcome"] == "EXPECTED_TERMINATION"
        assert исход["process_alive"] is False
        assert исход["port_released"] is True
        # Остановленный нами сервер уходит по SIGTERM: 15, то есть 143 в
        # терминах оболочки. Код 144 — это сигнал 16, и он означал бы, что
        # процесс убил кто-то другой.
        assert исход["signal"] in (15, None), исход
        assert исход["shell_code"] != 144, (
            "код 144 означает сигнал 16: стенд остановлен не нами")

    def test_порт_назначает_система(self):
        порты = {свободный_порт() for _ in range(5)}
        assert len(порты) >= 2, "порт не назначается системой заново"
        assert all(1024 < п < 65536 for п in порты)


class TestДесятьПодрядЧистых:
    """Одиночный удачный запуск ничего не доказывает про повторяемость."""

    def test_десять_последовательных(self):
        исходы = []
        for _ in range(10):
            с = поднять(ВИТРИНА)
            with urllib.request.urlopen(с.база + "/catalog/", timeout=10) as о:
                assert о.status == 200
            исходы.append(с.остановить())
        assert all(и["process_alive"] is False for и in исходы)
        assert all(и["port_released"] is True for и in исходы)
        assert all(и["shell_code"] != 144 for и in исходы)
        assert len({и["pid"] for и in исходы}) == 10, "процессы переиспользованы"


class TestДваРядом:
    def test_два_изолированных_экземпляра(self):
        """Порты не должны совпадать, и один не должен мешать другому."""
        с1 = поднять(ВИТРИНА)
        с2 = поднять(ВИТРИНА)
        try:
            assert с1.порт != с2.порт
            with concurrent.futures.ThreadPoolExecutor(2) as пул:
                коды = list(пул.map(
                    lambda б: urllib.request.urlopen(б + "/", timeout=10).status,
                    (с1.база, с2.база)))
            assert коды == [200, 200]
        finally:
            и1, и2 = с1.остановить(), с2.остановить()
        assert и1["port_released"] and и2["port_released"]
        assert not и1["process_alive"] and not и2["process_alive"]


class TestУборкаНеУбиваетСебя:
    """Отбор процессов по подстроке командной строки запрещён."""

    ПОДОЗРИТЕЛЬНЫЕ = ("http.server", "127.0.0.1")

    def test_в_сценариях_нет_отбора_процессов_по_подстроке(self):
        плохие = []
        for п in sorted((КОРЕНЬ / "scripts").glob("*.py")):
            т = п.read_text("utf-8")
            if "/proc" in т and any(с in т for с in self.ПОДОЗРИТЕЛЬНЫЕ):
                плохие.append(п.name)
        assert плохие == [], (
            f"сценарий ищет процессы по подстроке и найдёт сам себя: {плохие}")
