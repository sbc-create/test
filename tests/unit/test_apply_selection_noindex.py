"""apply-selection-noindex.py: выборка без своей страницы — noindex; своя страница не задета."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _загрузить(имя: str):
    спец = importlib.util.spec_from_file_location(имя.replace("-", "_"), ROOT / "automation" / "host" / f"{имя}.py")
    м = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(м)
    return м


ключи = _загрузить("apply-unknown-keys-noindex")
выборка = _загрузить("apply-selection-noindex")

БАЗА = '''from http.server import BaseHTTPRequestHandler


class Обработчик(BaseHTTPRequestHandler):
    def __init__(self):
        self.path = "/"

    def send_response(self, код):
        pass

    def end_headers(self):
        pass

    def _отдать(self, тело: bytes, тип="text/html; charset=utf-8", код=200):
        self.send_response(код)
        self.send_header("Content-Type", тип)
        self.send_header("Content-Length", str(len(тело)))
        self.тело = тело
'''


def _собрать(семья):
    текст, _ = ключи.привести(БАЗА, семья)
    текст, n = выборка.привести(текст, семья)
    assert n == 1
    п: dict = {}
    exec(текст, п)  # noqa: S102
    return текст, п


@pytest.mark.parametrize("путь, закрыть", [
    ("/catalog/", False), ("/catalog/?page=3", False),
    ("/catalog/?genre=боевик", False), ("/catalog/?year=2024&page=2", False),
    ("/catalog/?yf=2020", True), ("/catalog/?eps=1", True), ("/catalog/?type=movie", True),
    ("/catalog/?ongoing=1", True), ("/catalog/?sort=rating", True), ("/catalog/?view=dense", True),
    ("/catalog/?genre=боевик&year=2024", True), ("/title/x/", False),
])
def test_animego(путь, закрыть):
    _, п = _собрать("animego")
    assert п["_выборка_без_страницы"](путь) is закрыть


@pytest.mark.parametrize("путь, закрыть", [
    ("/catalog/?genre=anime", False), ("/catalog/?type=tv", False), ("/movies/", False),
    ("/catalog/?sort=title", True), ("/movies/?sort=year&page=2", True),
])
def test_animedia(путь, закрыть):
    _, п = _собрать("animedia")
    assert п["_выборка_без_страницы"](путь) is закрыть


def test_handler_closes_selection_and_rerun_is_a_no_op():
    текст, п = _собрать("animego")
    обр = п["Обработчик"]()
    обр._headers_buffer = []
    обр.request_version = "HTTP/1.1"
    обр.path = "/catalog/?yf=2020"
    обр._отдать(b'<html><head><meta name="robots" content="index, follow"></head></html>')
    assert b'content="noindex, follow"' in обр.тело
    assert выборка.привести(текст, "animego") == (текст, 0)
    with pytest.raises(ValueError):
        выборка.привести(БАЗА, "animego")  # без правила лишних ключей ставить не к чему
