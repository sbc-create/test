"""REQ-ADMIN-HTTP: панель подаётся и подаётся с защитными заголовками.

Заголовки проверяются здесь, а не в модуле приложения: их ставит транспорт, и
проверка на уровне AdminApp подтвердила бы то, чего пользователь не получает.
"""

import json
import shutil
import tempfile
import threading
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

from factory.site_engine.admin import ADMIN_COOKIE
from factory.site_engine.admin.app import AdminApp
from factory.site_engine.api import create_api
from factory.site_engine.api.control import ControlApi
from factory.site_engine.api.server import ServerConfig, build_server
from factory.site_engine.store import InMemoryStore

ROOT = Path(__file__).resolve().parents[2]
ТОКЕН = "adm"
ЧТЕНИЕ = {"SITE_ENGINE_API_ENABLED": "1", "SITE_ENGINE_ENVIRONMENT": "test"}
УПРАВЛЕНИЕ = {
    "SITE_ENGINE_CONTROL_WRITES": "1",
    "SITE_ENGINE_CONTROL_TOKENS": f"{ТОКЕН}=read,jobs:write,audit:read",
}


class _НеСледоватьЗаПеренаправлением(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def _песочница() -> Path:
    """Отдельный корень на каждый подъём службы.

    Прежде здесь стоял настоящий корень репозитория, и исход теста зависел от
    того, что осталось на диске от других прогонов: каталог операторов живёт в
    var/state, и заведённая где-то учётная запись закрывала вход по токену.
    Тест, который так себя ведёт, ничего не гарантирует.
    """
    корень = Path(tempfile.mkdtemp(prefix="admin-http-"))
    (корень / "config" / "site-profiles").mkdir(parents=True)
    shutil.copy(
        ROOT / "config" / "site-profiles" / "lords-01.json",
        корень / "config" / "site-profiles" / "lords-01.json",
    )
    for под in (
        "queue/inbox",
        "queue/processing",
        "queue/done",
        "queue/failed",
        "queue/quarantine",
        "var/locks",
        "var/audit",
        "var/state",
    ):
        (корень / под).mkdir(parents=True, exist_ok=True)
    return корень


def _apis(корень: Path):
    read = create_api(
        ["lords-01"], root=корень, loader=lambda p: (InMemoryStore(p.site_id), "т"), env=ЧТЕНИЕ
    )
    return read, ControlApi(root=корень, env=УПРАВЛЕНИЕ)


def _поднять(admin: bool):
    корень = _песочница()
    read, control = _apis(корень)
    app = AdminApp(read, control) if admin else None
    srv = build_server(ServerConfig(host="127.0.0.1", port=0), read, control, app)
    поток = threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
    поток.start()
    return srv, поток, f"http://127.0.0.1:{srv.server_address[1]}"


@pytest.fixture
def панель():
    srv, поток, база = _поднять(admin=True)
    try:
        yield база
    finally:
        srv.shutdown()
        поток.join(timeout=5)
        srv.server_close()


def запрос(url, *, метод="GET", форма=None, заголовки=None):
    данные = urllib.parse.urlencode(форма).encode() if форма is not None else None
    req = urllib.request.Request(url, data=данные, method=метод, headers=заголовки or {})
    opener = urllib.request.build_opener(_НеСледоватьЗаПеренаправлением)
    try:
        with opener.open(req, timeout=10) as о:
            return о.status, о.read().decode("utf-8", "replace"), dict(о.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace"), dict(e.headers)


def test_без_включённой_админки_маршрута_нет():
    srv, поток, база = _поднять(admin=False)
    try:
        код, тело, _ = запрос(база + "/admin")
        assert код == 404
        assert json.loads(тело)["error"]["code"] == "not_found"
    finally:
        srv.shutdown()
        поток.join(timeout=5)
        srv.server_close()


def test_страница_входа_отдаётся(панель):
    код, тело, _ = запрос(панель + "/admin")
    assert код == 200 and 'name="password"' in тело


def test_защитные_заголовки_на_месте(панель):
    _, _, з = запрос(панель + "/admin")
    assert з.get("X-Frame-Options") == "DENY"
    assert з.get("Referrer-Policy") == "no-referrer"
    assert з.get("Cache-Control") == "no-store"
    assert "default-src 'none'" in з.get("Content-Security-Policy", "")


def test_панель_запрещает_индексацию(панель):
    _, тело, _ = запрос(панель + "/admin")
    assert 'name="robots" content="noindex,nofollow"' in тело


def test_вход_по_http_выдаёт_cookie_и_перенаправляет(панель):
    код, _, з = запрос(панель + "/admin/login", метод="POST", форма={"token": ТОКЕН})
    assert код == 303
    assert з.get("Location") == "/admin"
    assert ADMIN_COOKIE in з.get("Set-Cookie", "")


def test_неверный_токен_по_http(панель):
    код, тело, з = запрос(панель + "/admin/login", метод="POST", форма={"token": "нет"})
    # Единый отказ на любой неудачный вход: 403. Разные коды на разные
    # причины отличали бы существующую учётную запись от несуществующей.
    assert код == 403 and ADMIN_COOKIE not in з.get("Set-Cookie", "")


def test_список_витрин_после_входа(панель):
    _, _, з = запрос(панель + "/admin/login", метод="POST", форма={"token": ТОКЕН})
    cookie = з["Set-Cookie"].split(";")[0]
    код, тело, _ = запрос(панель + "/admin", заголовки={"Cookie": cookie})
    assert код == 200 and "lords-01" in тело


def test_слишком_большая_форма_отклонена(панель):
    код, _, _ = запрос(панель + "/admin/login", метод="POST", форма={"token": "x" * 70000})
    assert код == 413
