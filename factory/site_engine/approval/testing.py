"""Эфемерная служба подписи для испытаний.

Существует, чтобы тесты шли ПО ТОМУ ЖЕ пути, что и рабочий контур: ключи в
каталоге credentials, подпись через сетевой вызов, проверка — локально по
публичному ключу. Подменять подпись заглушкой было бы удобнее и проверяло бы
не то, что потом работает.

Ключи создаются на каждый запуск и живут только в предоставленном каталоге.
"""
from __future__ import annotations

import contextlib
import json
import os
import secrets
import socket
import threading
from pathlib import Path

from factory.site_engine.approval import keyring as K
from factory.site_engine.approval import service as S


def подготовить_каталог(каталог: Path) -> dict[str, str]:
    """Создать эфемерные ключи и токен. Возвращает kid и путь."""
    каталог.mkdir(parents=True, exist_ok=True)
    kid, pem, публичный = K.создать_ключ()
    (каталог / S.ПРИВАТНЫЙ).write_text(pem, encoding="utf-8")
    (каталог / S.НАБОР).write_text(
        K.НаборКлючей([K.Ключ(kid, публичный, "ACTIVE")]).в_json(),
        encoding="utf-8")
    (каталог / S.ТОКЕН).write_text(secrets.token_urlsafe(24), encoding="utf-8")
    return {"kid": kid, "dir": str(каталог)}


def _свободный_порт() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@contextlib.contextmanager
def эфемерный_signer(каталог: Path, monkeypatch=None):
    """Поднять службу подписи на время теста."""
    сведения = подготовить_каталог(каталог)
    порт = _свободный_порт()
    установить = (monkeypatch.setenv if monkeypatch else os.environ.__setitem__)
    установить("CREDENTIALS_DIRECTORY", str(каталог))
    установить("APPROVAL_SIGNER_BASE", f"http://127.0.0.1:{порт}")

    S.Обработчик.состояние = S.Состояние()
    from http.server import ThreadingHTTPServer
    сервер = ThreadingHTTPServer(("127.0.0.1", порт), S.Обработчик)
    поток = threading.Thread(target=сервер.serve_forever, daemon=True)
    поток.start()
    try:
        yield {**сведения, "port": порт}
    finally:
        сервер.shutdown()
        сервер.server_close()


def отозвать_активный(каталог: Path) -> str:
    """Пометить действующий ключ отозванным. Возвращает его kid."""
    путь = каталог / S.НАБОР
    набор = K.НаборКлючей.из_json(путь.read_text("utf-8"))
    активный = набор.активный
    ключи = [K.Ключ(к.kid, к.публичный,
                    "REVOKED" if к.kid == активный.kid else к.состояние)
             for к in набор.ключи.values()]
    путь.write_text(K.НаборКлючей(ключи).в_json(), encoding="utf-8")
    return активный.kid
