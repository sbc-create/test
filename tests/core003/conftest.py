"""Стенд приёмки CORE-003: тот же артефакт, но изолированные хранилища.

Служба подписи поднимается ПОДПРОЦЕССОМ из выложенного релиза — не из
рабочего дерева и не заглушкой. Иначе проверялось бы не то, что работает:
упрощённая ветка кода и ручная подпись доказывают только сами себя.

Всё, что пишется, пишется в эфемерные хранилища. Ключ подписи отдельный, и
его публичная часть в боевом наборе доверия отсутствует.
"""
from __future__ import annotations

import datetime as _d
import json
import os
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

#: Выложенный релиз. Тот же артефакт, что обслуживает контур.
РЕЛИЗ = Path("/srv/site-factory/control-api/current").resolve()
ЭФЕМЕРНЫЙ_САЙТ = "ephemeral-core003-0001"


def свободный_порт() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class ЭфемерныйРеестр:
    def __init__(self) -> None:
        self._сайты: dict[str, dict] = {}
        self._версия = 1

    def добавить(self, site_id: str, *, environment: str = "test") -> dict:
        self._версия += 1
        з = {"site_id": site_id, "environment": environment,
             "lifecycle_state": "DRAFT",
             "canonical_domain": f"{site_id}.invalid",
             "registry_version": self._версия}
        self._сайты[site_id] = з
        return з

    def сменить_окружение(self, site_id: str, окружение: str, *,
                          поднять_версию: bool = True) -> None:
        """Сменить окружение записи.

        `поднять_версию=False` нужен, чтобы проверить ИМЕННО ворота
        production: при поднятой версии служба подписи отвергнет запрос
        раньше — по устареванию плана, — и проверка измерила бы другое.
        """
        if поднять_версию:
            self._версия += 1
        self._сайты[site_id]["environment"] = окружение

    def версия(self) -> int:
        return self._версия

    def сайт(self, site_id: str):
        return self._сайты.get(site_id)

    def сайты(self) -> list[dict]:
        return list(self._сайты.values())


class РеестрHTTP:
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

        self.порт = свободный_порт()
        self.сервер = ThreadingHTTPServer(("127.0.0.1", self.порт), Обработчик)
        threading.Thread(target=self.сервер.serve_forever, daemon=True).start()

    @property
    def база(self) -> str:
        return f"http://127.0.0.1:{self.порт}"

    def закрыть(self) -> None:
        self.сервер.shutdown()
        self.сервер.server_close()


def подготовить_ключи(каталог: Path) -> dict:
    """Отдельный тестовый ключ. В боевом наборе доверия его нет."""
    import secrets as _secrets
    import hashlib as _h
    import sys
    sys.path.insert(0, str(РЕЛИЗ))
    from factory.site_engine.approval import keyring as K
    каталог.mkdir(parents=True, exist_ok=True)
    kid, pem, публичный = K.создать_ключ()
    (каталог / "approval-signing-key").write_text(pem, encoding="utf-8")
    (каталог / "approval-verify-keys").write_text(
        K.НаборКлючей([K.Ключ(kid, публичный, "ACTIVE")]).в_json(),
        encoding="utf-8")
    токены, отпечатки = {}, {}
    for имя in ("control-api", "changeset-worker"):
        значение = _secrets.token_urlsafe(24)
        (каталог / f"approval-caller-{имя}").write_text(значение, encoding="utf-8")
        токены[имя] = значение
        отпечатки[имя] = _h.sha256(значение.encode()).hexdigest()
    (каталог / "approval-caller-fingerprints").write_text(
        json.dumps({"callers": отпечатки}), encoding="utf-8")
    return {"kid": kid, "public": публичный, "caller_tokens": токены}


class ТестовыйSigner:
    """Подпроцесс службы подписи из выложенного релиза."""

    def __init__(self, каталог_ключей: Path, changeset_db: Path,
                 registry_base: str) -> None:
        self.порт = свободный_порт()
        окр = dict(os.environ,
                   PYTHONPATH=str(РЕЛИЗ),
                   CREDENTIALS_DIRECTORY=str(каталог_ключей),
                   CHANGESET_DB=str(changeset_db),
                   CONTROL_API_BASE=registry_base,
                   APPROVAL_SIGNER_PORT=str(self.порт),
                   PYTHONUNBUFFERED="1")
        self.журнал = (каталог_ключей.parent / "signer.log").open("w")
        self.процесс = subprocess.Popen(
            [str(РЕЛИЗ / ".venv/bin/python"), "-m",
             "factory.site_engine.approval.service"],
            cwd=str(РЕЛИЗ), env=окр, stdout=self.журнал,
            stderr=subprocess.STDOUT)
        for _ in range(80):
            try:
                with urllib.request.urlopen(
                        f"http://127.0.0.1:{self.порт}/healthz", timeout=2):
                    break
            except Exception:
                time.sleep(0.1)
        else:
            raise RuntimeError("служба подписи не поднялась")

    @property
    def база(self) -> str:
        return f"http://127.0.0.1:{self.порт}"

    def закрыть(self) -> None:
        self.процесс.terminate()
        try:
            self.процесс.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.процесс.kill()
        self.журнал.close()


def через_час() -> str:
    return (_d.datetime.now(_d.timezone.utc)
            + _d.timedelta(hours=1)).isoformat().replace("+00:00", "Z")


@pytest.fixture()
def стенд(tmp_path, monkeypatch):
    import sys
    sys.path.insert(0, str(РЕЛИЗ))
    changeset_db = tmp_path / "cs.sqlite3"
    monkeypatch.setenv("CHANGESET_DB", str(changeset_db))
    реестр = ЭфемерныйРеестр()
    реестр.добавить(ЭФЕМЕРНЫЙ_САЙТ)
    прокси = РеестрHTTP(реестр)
    monkeypatch.setenv("CONTROL_API_BASE", прокси.база)
    ключи = подготовить_ключи(tmp_path / "credentials")
    monkeypatch.setenv("CREDENTIALS_DIRECTORY", str(tmp_path / "credentials"))
    signer = ТестовыйSigner(tmp_path / "credentials", changeset_db, прокси.база)
    monkeypatch.setenv("APPROVAL_SIGNER_BASE", signer.база)
    # Сам стенд выступает вызывающим control-api: подпись одобрения запрашивает
    # он. Имя личности — не секрет и задаётся конфигурацией, как в юните.
    monkeypatch.setenv("APPROVAL_CALLER", "control-api")
    from factory.site_engine.changeset import store as S
    соед = S.открыть(changeset_db)
    try:
        yield {"соед": соед, "реестр": реестр, "signer": signer,
               "ключи": ключи, "tmp": tmp_path, "site_id": ЭФЕМЕРНЫЙ_САЙТ,
               "registry_base": прокси.база}
    finally:
        соед.close()
        signer.закрыть()
        прокси.закрыть()
