"""Обвязка приёмки ZONE-TPL-001.

Контур изменений импортируется из ВЫЛОЖЕННОГО релиза — того же артефакта,
что обслуживает управляющий слой. Хранилища эфемерные, ключ подписи
отдельный, цель поддельная. Ни одна запись не попадает в канонические
хранилища.
"""
from __future__ import annotations

import datetime as _d
import json
import os
import socket
import subprocess
import threading
import time
import urllib.request
from pathlib import Path

import pytest

РЕЛИЗ = Path("/srv/site-factory/control-api/current").resolve()

# Контур изменений живёт в выложенном релизе, а витрина — в этой ветке.
#
# Одного sys.path мало: пакет `factory.site_engine` уже загружен отсюда, и
# подпакета `changeset` в нём нет. Поэтому к ПУТИ УЖЕ ЗАГРУЖЕННОГО пакета
# добавляется каталог релиза — так обе половины остаются собой: код витрины
# берётся из ветки, контур изменений из выложенного артефакта, и ни одна не
# подменяет другую.
import sys as _sys
if str(РЕЛИЗ) not in _sys.path:
    _sys.path.insert(0, str(РЕЛИЗ))

def _срастить(имя: str) -> None:
    import importlib
    модуль = importlib.import_module(имя)
    ветвь = РЕЛИЗ / имя.replace(".", "/")
    if ветвь.is_dir() and str(ветвь) not in list(модуль.__path__):
        модуль.__path__.append(str(ветвь))

for _пакет in ("factory", "factory.site_engine"):
    _срастить(_пакет)

#: Окружение изолированного стенда. В этом контуре объявлены test,
#: non-production и production; «staging» как отдельное имя не объявлено, и
#: изолированная выкладка здесь называется non-production. Вводить четвёртое
#: имя ради совпадения со словом в задании значило бы расширить перечень
#: окружений, которым разрешено автоматическое применение.
ОКРУЖЕНИЕ_СТЕНДА = "non-production"


def свободный_порт() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class ЭфемерныйРеестр:
    def __init__(self) -> None:
        self._сайты: dict[str, dict] = {}
        self._версия = 1

    def добавить(self, site_id: str, домен: str, *,
                 environment: str = ОКРУЖЕНИЕ_СТЕНДА) -> dict:
        self._версия += 1
        з = {"site_id": site_id, "environment": environment,
             "lifecycle_state": "DRAFT", "canonical_domain": домен,
             "registry_version": self._версия}
        self._сайты[site_id] = з
        return з

    def сменить_окружение(self, site_id, окружение, *, поднять_версию=False):
        if поднять_версию:
            self._версия += 1
        self._сайты[site_id]["environment"] = окружение

    def версия(self):
        return self._версия

    def сайт(self, site_id):
        return self._сайты.get(site_id)

    def сайты(self):
        return list(self._сайты.values())


class РеестрHTTP:
    def __init__(self, реестр) -> None:
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
    def база(self):
        return f"http://127.0.0.1:{self.порт}"

    def закрыть(self):
        self.сервер.shutdown(); self.сервер.server_close()


def подготовить_ключи(каталог: Path) -> dict:
    import hashlib as _h
    import secrets as _s
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
        з = _s.token_urlsafe(24)
        (каталог / f"approval-caller-{имя}").write_text(з, encoding="utf-8")
        токены[имя] = з
        отпечатки[имя] = _h.sha256(з.encode()).hexdigest()
    (каталог / "approval-caller-fingerprints").write_text(
        json.dumps({"callers": отпечатки}), encoding="utf-8")
    return {"kid": kid, "caller_tokens": токены}


class ТестовыйSigner:
    def __init__(self, ключи: Path, changeset_db: Path, registry: str) -> None:
        self.порт = свободный_порт()
        окр = dict(os.environ, PYTHONPATH=str(РЕЛИЗ),
                   CREDENTIALS_DIRECTORY=str(ключи),
                   CHANGESET_DB=str(changeset_db),
                   CONTROL_API_BASE=registry,
                   APPROVAL_SIGNER_PORT=str(self.порт), PYTHONUNBUFFERED="1")
        self.журнал = (ключи.parent / "signer.log").open("w")
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
    def база(self):
        return f"http://127.0.0.1:{self.порт}"

    def закрыть(self):
        self.процесс.terminate()
        try:
            self.процесс.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.процесс.kill()
        self.журнал.close()


def через_час() -> str:
    return (_d.datetime.now(_d.timezone.utc)
            + _d.timedelta(hours=1)).isoformat().replace("+00:00", "Z")


ВИТРИНЫ = (("zona-01", "zonafilm.space.invalid"),
           ("animedia-01", "animedia.icu.invalid"),
           ("animedia-02", "animedia.space.invalid"))


@pytest.fixture()
def стенд(tmp_path, monkeypatch):
    import sys
    sys.path.insert(0, str(РЕЛИЗ))
    changeset_db = tmp_path / "cs.sqlite3"
    monkeypatch.setenv("CHANGESET_DB", str(changeset_db))
    реестр = ЭфемерныйРеестр()
    for site_id, домен in ВИТРИНЫ:
        реестр.добавить(site_id, домен)
    прокси = РеестрHTTP(реестр)
    monkeypatch.setenv("CONTROL_API_BASE", прокси.база)
    ключи = подготовить_ключи(tmp_path / "credentials")
    monkeypatch.setenv("CREDENTIALS_DIRECTORY", str(tmp_path / "credentials"))
    monkeypatch.setenv("APPROVAL_CALLER", "control-api")
    signer = ТестовыйSigner(tmp_path / "credentials", changeset_db, прокси.база)
    monkeypatch.setenv("APPROVAL_SIGNER_BASE", signer.база)
    from factory.site_engine.changeset import store as S
    соед = S.открыть(changeset_db)
    try:
        yield {"соед": соед, "реестр": реестр, "signer": signer,
               "ключи": ключи, "tmp": tmp_path, "registry_base": прокси.база}
    finally:
        соед.close(); signer.закрыть(); прокси.закрыть()
