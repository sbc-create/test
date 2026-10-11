"""apply-unknown-keys-noindex.py: неизвестный/повторённый ключ — noindex в теле и заголовке; известные — без изменений."""

from __future__ import annotations

import importlib.util
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
спец = importlib.util.spec_from_file_location(
    "apply_unknown_keys_noindex", ROOT / "automation" / "host" / "apply-unknown-keys-noindex.py"
)
инструмент = importlib.util.module_from_spec(спец)
спец.loader.exec_module(инструмент)

ОБРАЗЕЦ = '''from http.server import BaseHTTPRequestHandler


class Обработчик(BaseHTTPRequestHandler):
    def __init__(self):
        self.path = "/"
        self.заголовки = []
        self.тело = b""

    def send_response(self, код):
        self.код = код

    def end_headers(self):
        pass

    def _отдать(self, тело: bytes, тип="text/html; charset=utf-8", код=200):
        self.send_response(код)
        self.send_header("Content-Type", тип)
        self.send_header("Content-Length", str(len(тело)))
        self.send_header("X-Robots-Tag", "index, follow")
        self.тело = тело
'''


def _собрать():
    новый, n = инструмент.привести(ОБРАЗЕЦ, "lords")
    assert n == 1
    п: dict = {}
    exec(новый, п)  # noqa: S102
    обр = п["Обработчик"]()
    # BaseHTTPRequestHandler.send_header пишет в буфер — подменяем приёмник.
    обр._headers_buffer = []
    обр.request_version = "HTTP/1.1"
    return новый, п, обр


def _отдать(п, обр, путь, тело=b'<html><head><meta name="robots" content="index, follow"></head></html>', код=200):
    обр.path = путь
    обр._headers_buffer = []
    обр._отдать(тело, код=код)
    заголовки = b"".join(обр._headers_buffer).decode("latin-1")
    return обр.тело.decode("utf-8"), заголовки


@pytest.mark.parametrize("путь, закрыть", [
    ("/catalog/?genre=drama&page=2", False),
    ("/catalog/", False),
    ("/catalog/?nosuchkey=1", True),
    ("/catalog/?genre=drama&genre=komediya", True),
    ("/title/x/?utm_source=ya", True),
])
def test_unknown_or_repeated_key_closes_index(путь, закрыть):
    _, п, обр = _собрать()
    тело, заголовки = _отдать(п, обр, путь)
    assert ('content="noindex, follow"' in тело) is закрыть
    assert ("X-Robots-Tag: noindex, follow" in заголовки) is закрыть
    if not закрыть:
        assert "X-Robots-Tag: index, follow" in заголовки


def test_content_length_matches_rewritten_body_and_404_untouched():
    _, п, обр = _собрать()
    тело, заголовки = _отдать(п, обр, "/catalog/?x=1")
    assert f"Content-Length: {len(тело.encode('utf-8'))}" in заголовки
    тело404, заг404 = _отдать(п, обр, "/catalog/?x=1", код=404)
    assert "noindex" not in тело404 and "X-Robots-Tag: index, follow" in заг404


def test_never_relaxes_and_rerun_is_a_no_op():
    новый, п, обр = _собрать()
    assert п["_закрытые_роботы"]("noindex, nofollow") == "noindex, nofollow"
    тело = b'<html><head><meta name="robots" content="noindex, nofollow"></head></html>'
    assert п["_закрыть_индекс_в_теле"](тело) == тело
    assert инструмент.привести(новый, "lords") == (новый, 0)
    with pytest.raises(ValueError):
        инструмент.привести(ОБРАЗЕЦ.replace("self.send_response(код)", "self.send_response(код )"), "lords")
