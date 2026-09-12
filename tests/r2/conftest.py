"""Обвязка фокусных проверок R2. Каноническое состояние не затрагивается."""
from __future__ import annotations

import datetime as _d
import threading
from pathlib import Path

import pytest

from factory.site_engine.approval import testing as ПОДПИСЬ_ТЕСТ
from factory.site_engine.changeset import store as S


class ЭфемерныйРеестр:
    def __init__(self) -> None:
        self._сайты: dict[str, dict] = {}
        self._версия = 1

    def добавить(self, site_id: str, *, environment: str = "test",
                 lifecycle: str = "DRAFT") -> dict:
        self._версия += 1
        з = {"site_id": site_id, "environment": environment,
             "lifecycle_state": lifecycle,
             "canonical_domain": f"{site_id}.test",
             "registry_version": self._версия}
        self._сайты[site_id] = з
        return з

    def версия(self) -> int:
        return self._версия

    def сайт(self, site_id: str) -> dict | None:
        return self._сайты.get(site_id)

    def сайты(self) -> list[dict]:
        return list(self._сайты.values())


def через_час() -> str:
    return (_d.datetime.now(_d.timezone.utc)
            + _d.timedelta(hours=1)).isoformat().replace("+00:00", "Z")


class _РеестрHTTP:
    """Эфемерный реестр по HTTP.

    Служба подписи обязана читать версию реестра САМА и из того же источника,
    что и контур. Разрешить ей в тестах пропускать эту проверку значило бы
    проверять не ту службу, которая потом работает.
    """

    def __init__(self, реестр: ЭфемерныйРеестр) -> None:
        import json
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

        import socket
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            self.порт = s.getsockname()[1]
        self.сервер = ThreadingHTTPServer(("127.0.0.1", self.порт), Обработчик)
        self.поток = threading.Thread(target=self.сервер.serve_forever,
                                      daemon=True)
        self.поток.start()

    @property
    def база(self) -> str:
        return f"http://127.0.0.1:{self.порт}"

    def закрыть(self) -> None:
        self.сервер.shutdown()
        self.сервер.server_close()


@pytest.fixture()
def стенд(tmp_path, monkeypatch):
    """Эфемерный контур: свой ChangeSet Store, свои ключи, своя служба подписи."""
    monkeypatch.setenv("CHANGESET_DB", str(tmp_path / "cs.sqlite3"))
    реестр = ЭфемерныйРеестр()
    сервер = _РеестрHTTP(реестр)
    monkeypatch.setenv("CONTROL_API_BASE", сервер.база)
    try:
        with ПОДПИСЬ_ТЕСТ.эфемерный_signer(tmp_path / "credentials",
                                           monkeypatch) as с:
            соед = S.открыть(tmp_path / "cs.sqlite3")
            yield {"соед": соед, "signer": с, "tmp": tmp_path,
                   "реестр": реестр, "registry_base": сервер.база}
            соед.close()
    finally:
        сервер.закрыть()
