"""Эфемерная служба подписи для испытаний.

Тесты идут ПО ТОМУ ЖЕ пути, что и рабочий контур: ключи в каталоге
credentials, вызывающие опознаются по своим токенам, каноническое состояние
служба читает сама. Заглушка проверяла бы не то, что потом работает.
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


def подготовить_каталог(каталог: Path) -> dict[str, object]:
    """Эфемерные ключи и токены вызывающих. Живут только здесь."""
    каталог.mkdir(parents=True, exist_ok=True)
    kid, pem, публичный = K.создать_ключ()
    (каталог / S.ПРИВАТНЫЙ).write_text(pem, encoding="utf-8")
    (каталог / S.НАБОР).write_text(
        K.НаборКлючей([K.Ключ(kid, публичный, "ACTIVE")]).в_json(),
        encoding="utf-8")
    import hashlib
    вызывающие = {}
    значения = {}
    for имя in ("control-api", "changeset-worker"):
        значение = secrets.token_urlsafe(24)
        (каталог / f"approval-caller-{имя}").write_text(значение, encoding="utf-8")
        вызывающие[имя] = hashlib.sha256(значение.encode()).hexdigest()
        значения[имя] = значение
    (каталог / S.ВЫЗЫВАЮЩИЕ).write_text(
        json.dumps({"callers": вызывающие}), encoding="utf-8")
    return {"kid": kid, "dir": str(каталог), "caller_tokens": значения}


def _свободный_порт() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@contextlib.contextmanager
def эфемерный_signer(каталог: Path, monkeypatch=None, *,
                     вызывающий: str = "control-api"):
    """Поднять службу подписи на время теста."""
    сведения = подготовить_каталог(каталог)
    порт = _свободный_порт()
    установить = (monkeypatch.setenv if monkeypatch else os.environ.__setitem__)
    установить("CREDENTIALS_DIRECTORY", str(каталог))
    установить("APPROVAL_SIGNER_BASE", f"http://127.0.0.1:{порт}")
    установить("APPROVAL_CALLER", вызывающий)

    S.Обработчик.состояние = S.Состояние()
    from http.server import ThreadingHTTPServer
    сервер = ThreadingHTTPServer(("127.0.0.1", порт), S.Обработчик)
    поток = threading.Thread(target=сервер.serve_forever, daemon=True)
    поток.start()
    try:
        yield {**сведения, "port": порт,
               "base": f"http://127.0.0.1:{порт}"}
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
