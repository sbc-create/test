"""Чтение страниц стенда: отказ — состояние, а не исключение.

Функция была выписана дословно дважды, в `lords_live_defects` и
`lords_release_baseline`. Совпадали и сроки, и обработка отказов; совпадали
случайно.

Расхождение здесь тихое и дорогое: аудит, у которого отказ HTTP превращается в
пустую строку, а у соседнего — в исключение, даёт разные отчёты об одном и том
же стенде, и разница читается как разница витрин.

Отдельно закреплено различие, которое легко потерять при переписывании: `None`
в коде ответа означает, что ответа не было вовсе — соединение не состоялось,
имя не разрешилось, вышел срок. Ответ сервера с кодом 404 или 500 — это
ответ, и тело у него значимо.
"""

from __future__ import annotations

import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import unquote

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import stand_probe  # noqa: E402


class _Обработчик(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 — имя задано базовым классом
        # Путь приходит закодированным — именно это и делает проверяемая
        # функция. Сравнивать с незакодированным здесь значило бы не заметить,
        # что кодирование пропало.
        путь = unquote(self.path)
        if путь.startswith("/нет"):
            тело = "не найдено".encode("utf-8")
            self.send_response(404)
        elif путь.startswith("/кир"):
            тело = "кириллический путь".encode("utf-8")
            self.send_response(200)
        else:
            тело = "страница".encode("utf-8")
            self.send_response(200)
        self.send_header("Content-Length", str(len(тело)))
        self.end_headers()
        self.wfile.write(тело)

    def log_message(self, *args):  # noqa: D102 — тишина в выводе теста
        return


@pytest.fixture(scope="module")
def стенд():
    server = HTTPServer(("127.0.0.1", 0), _Обработчик)
    поток = threading.Thread(target=server.serve_forever, daemon=True)
    поток.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        поток.join(timeout=5)


class TestОтветыСервера:
    def test_успешный_ответ(self, стенд):
        код, тело = stand_probe.fetch(стенд, "/")
        assert код == 200
        assert тело == "страница"

    def test_ответ_с_кодом_ошибки_несёт_тело(self, стенд):
        """404 — это ответ, и его тело значимо: по нему судят о странице."""
        код, тело = stand_probe.fetch(стенд, "/нет")
        assert код == 404
        assert тело == "не найдено"

    def test_кириллический_путь_кодируется(self, стенд):
        """Без кодирования запрос не уходит вовсе, а адреса витрин кириллические."""
        код, тело = stand_probe.fetch(стенд, "/кир")
        assert код == 200
        assert тело == "кириллический путь"


class TestОтсутствиеОтвета:
    def test_закрытый_порт_даёт_none(self):
        код, причина = stand_probe.fetch("http://127.0.0.1:59999", "/")
        assert код is None, "отсутствие ответа спутано с ответом сервера"
        assert причина, "причина отказа не названа"

    def test_причина_обрезана(self):
        """Длинная причина в отчёте вытесняет то, ради чего отчёт составлен."""
        _, причина = stand_probe.fetch("http://127.0.0.1:59999", "/")
        assert len(причина) <= 160


class TestКопийБольшеНет:
    @pytest.mark.parametrize("имя", ("lords_live_defects.py", "lords_release_baseline.py"))
    def test_сценарий_не_держит_своей_копии(self, имя):
        текст = (ROOT / "scripts" / имя).read_text(encoding="utf-8")
        assert "def fetch(base: str" not in текст, f"{имя}: копия вернулась"
        assert "from stand_probe import fetch" in текст, имя
