"""apply-search-index-prebuild.py: указатель строится до сервера; ошибка сборки не роняет запуск."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
спец = importlib.util.spec_from_file_location(
    "apply_search_index_prebuild", ROOT / "automation" / "host" / "apply-search-index-prebuild.py")
инструмент = importlib.util.module_from_spec(спец)
спец.loader.exec_module(инструмент)

ОБРАЗЕЦ = '''порядок = []


class Данные:
    def __init__(self, падать=False):
        self.падать = падать

    def _построить_указатель(self):
        if self.падать:
            raise RuntimeError("сборка не удалась")
        порядок.append("указатель")


class Обработчик:
    данные = None
    подробности = None
    индекс = None


def построить_индекс(д, п):
    порядок.append("индекс")


def ThreadingHTTPServer(адрес, обработчик):
    порядок.append("сервер")


class Арг:
    host, port = "127.0.0.1", 0


def main(падать=False):
    args = Арг()
    Обработчик.данные = Данные(падать)
    Обработчик.индекс = построить_индекс(Обработчик.данные, Обработчик.подробности)
    сервер = ThreadingHTTPServer((args.host, args.port), Обработчик)
'''


def _собрать():
    новый, n = инструмент.привести(ОБРАЗЕЦ)
    assert n == 1
    п: dict = {}
    exec(новый, п)  # noqa: S102
    return новый, п


def test_index_is_built_before_server_starts():
    _, п = _собрать()
    п["main"]()
    assert п["порядок"] == ["индекс", "указатель", "сервер"]


def test_build_failure_does_not_stop_start():
    _, п = _собрать()
    п["main"](падать=True)
    assert п["порядок"] == ["индекс", "сервер"]


def test_rerun_is_a_no_op_and_refusals():
    новый, _ = _собрать()
    assert инструмент.привести(новый) == (новый, 0)
    with pytest.raises(ValueError):
        инструмент.привести(ОБРАЗЕЦ.replace("def _построить_указатель", "def _другое"))
    with pytest.raises(ValueError):
        инструмент.привести(ОБРАЗЕЦ.replace("    сервер = ThreadingHTTPServer", "    s = ThreadingHTTPServer"))
