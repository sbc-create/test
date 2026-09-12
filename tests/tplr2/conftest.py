"""Эфемерная обвязка приёмки Templates Control Plane Adapter.

Всё, что пишется, пишется только сюда: свой ChangeSet Store, свой реестр по
HTTP, свой ключ подписи, поддельная цель. Канонические хранилища в этих
проверках не участвуют — доказывать идемпотентность ценой мусора в истории
системы недопустимо.
"""
from __future__ import annotations

import datetime as _d
import json
import socket
import threading
from pathlib import Path

import pytest

from factory.site_engine.approval import testing as ПОДПИСЬ_ТЕСТ
from factory.site_engine.changeset import store as S

#: Синтетический сайт, которого нет и не может быть в production.
ЭФЕМЕРНЫЙ_САЙТ = "ephemeral-tplr2-0001"


class ЭфемерныйРеестр:
    def __init__(self) -> None:
        self._сайты: dict[str, dict] = {}
        self._версия = 1

    def добавить(self, site_id: str, *, environment: str = "test",
                 lifecycle: str = "DRAFT") -> dict:
        self._версия += 1
        з = {"site_id": site_id, "environment": environment,
             "lifecycle_state": lifecycle,
             "canonical_domain": f"{site_id}.invalid",
             "registry_version": self._версия}
        self._сайты[site_id] = з
        return з

    def версия(self) -> int:
        return self._версия

    def сайт(self, site_id: str) -> dict | None:
        return self._сайты.get(site_id)

    def сайты(self) -> list[dict]:
        return list(self._сайты.values())


class РеестрHTTP:
    """Реестр по HTTP: служба подписи обязана читать версию сама."""

    def __init__(self, реестр: ЭфемерныйРеестр) -> None:
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

        class Обработчик(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_GET(self):
                if self.path.startswith("/api/v1/registry/version"):
                    тело = {"registry_version": реестр.версия()}
                elif self.path.startswith("/api/v1/sites"):
                    тело = {"items": реестр.сайты(),
                            "registry_version": реестр.версия()}
                else:
                    self.send_response(404); self.end_headers(); return
                сырое = json.dumps(тело).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(сырое)))
                self.end_headers()
                self.wfile.write(сырое)

        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            self.порт = s.getsockname()[1]
        self.сервер = ThreadingHTTPServer(("127.0.0.1", self.порт), Обработчик)
        threading.Thread(target=self.сервер.serve_forever, daemon=True).start()

    @property
    def база(self) -> str:
        return f"http://127.0.0.1:{self.порт}"

    def закрыть(self) -> None:
        self.сервер.shutdown()
        self.сервер.server_close()


def через_час() -> str:
    return (_d.datetime.now(_d.timezone.utc)
            + _d.timedelta(hours=1)).isoformat().replace("+00:00", "Z")


@pytest.fixture()
def стенд(tmp_path, monkeypatch):
    monkeypatch.setenv("CHANGESET_DB", str(tmp_path / "cs.sqlite3"))
    реестр = ЭфемерныйРеестр()
    реестр.добавить(ЭФЕМЕРНЫЙ_САЙТ)
    прокси = РеестрHTTP(реестр)
    monkeypatch.setenv("CONTROL_API_BASE", прокси.база)
    try:
        with ПОДПИСЬ_ТЕСТ.эфемерный_signer(tmp_path / "credentials",
                                           monkeypatch) as с:
            соед = S.открыть(tmp_path / "cs.sqlite3")
            yield {"соед": соед, "signer": с, "tmp": tmp_path,
                   "реестр": реестр, "site_id": ЭФЕМЕРНЫЙ_САЙТ}
            соед.close()
    finally:
        прокси.закрыть()
