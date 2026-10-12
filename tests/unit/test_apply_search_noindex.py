"""apply-search-noindex.py: внутренний поиск — noindex; прочие страницы не задеты; поверх правил ключей и выборок."""

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
выборки = _загрузить("apply-selection-noindex")
поиск = _загрузить("apply-search-noindex")

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


@pytest.mark.parametrize("семья, с_выборками", [("lords", False), ("animego", True), ("animedia", True)])
@pytest.mark.parametrize("путь, закрыть", [
    ("/search/?q=наруто", True), ("/search/", True), ("/search", True),
    ("/catalog/", False), ("/title/x/", False), ("/genre/drama/", False),
])
def test_search_is_closed_others_untouched(семья, с_выборками, путь, закрыть):
    текст, _ = ключи.привести(БАЗА, семья)
    if с_выборками:
        текст, _ = выборки.привести(текст, семья)
    текст, n = поиск.привести(текст)
    assert n == 1
    п: dict = {}
    exec(текст, п)  # noqa: S102
    обр = п["Обработчик"]()
    обр._headers_buffer = []
    обр.request_version = "HTTP/1.1"
    обр.path = путь
    обр._отдать(b'<html><head><meta name="robots" content="index, follow"></head></html>')
    assert (b'content="noindex, follow"' in обр.тело) is закрыть
    assert поиск.привести(текст) == (текст, 0)


def test_refused_without_keys_rule():
    with pytest.raises(ValueError):
        поиск.привести(БАЗА)
