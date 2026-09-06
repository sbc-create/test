"""REQ-FLEET-CONSOLE: массив витрин у супер-администратора.

Локальная админка видит одну витрину — это цель. Но кто-то должен видеть все:
заводить витрины, переключаться между ними и отвечать за массив целиком. Пока
такого экрана нет, супер-администратор ходит по адресам витрин наугад и нигде
не видит массива.

Три правила.

**Массив виден одним экраном.** Список витрин с состоянием, признаком
регистрации и семейством шаблона. Список, который надо собирать переходами по
сайтам, на практике не собирают.

**Переключение явное и под запись.** Открытие витрины из массива — переход по
её адресу, и он записывается: по журналу должно быть видно, кто и куда смотрел.

**Локальный администратор массива не видит.** Ни экрана, ни ссылки: иначе
изоляция держится на том, что он не ввёл адрес руками.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory.paths import PATHS
from factory.site_engine.admin.app import AdminApp
from factory.site_engine.api import create_api
from factory.site_engine.api.control import ControlApi
from factory.site_engine.operators import OperatorDirectory
from factory.site_engine.store import InMemoryStore

САЙТ_A = "fc-a"
САЙТ_B = "fc-b"
ТОКЕН = "boot"
ПАРОЛЬ = "длинный-пароль-для-проверки-1"
REPO = Path(__file__).resolve().parents[2]
ENV = {
    "SITE_ENGINE_CONTROL_WRITES": "1",
    "SITE_ENGINE_CONTROL_TOKENS": (
        f"{ТОКЕН}=read,jobs:write,config:write,audit:read,review:write,operators:write"
    ),
}


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setattr(PATHS, "root", tmp_path)
    профили = tmp_path / "config" / "site-profiles"
    профили.mkdir(parents=True)
    # Профиль берётся настоящий: у витрины есть обязательные поля, и
    # выдуманный профиль проверял бы не то, что читает движок.
    образец = json.loads(
        (REPO / "config" / "site-profiles" / "lords-01.json").read_text(encoding="utf-8")
    )
    for сайт, регистрация in ((САЙТ_A, True), (САЙТ_B, False)):
        профиль = dict(образец)
        профиль.update(
            {
                "site_id": сайт,
                "domains": [f"{сайт}.test"],
                "canonical_host": f"{сайт}.test",
                "brand": {"name": f"Витрина {сайт}"},
                "public_registration_enabled": регистрация,
            }
        )
        (профили / f"{сайт}.json").write_text(
            json.dumps(профиль, ensure_ascii=False), encoding="utf-8"
        )
    for под in ("queue/inbox", "var/locks", "var/audit", "var/state"):
        (tmp_path / под).mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture
def app(sandbox):
    read = create_api(
        [САЙТ_A, САЙТ_B],
        root=sandbox,
        loader=lambda p: (InMemoryStore(p.site_id), "т"),
        env={"SITE_ENGINE_API_ENABLED": "1", "SITE_ENGINE_ENVIRONMENT": "test"},
    )
    return AdminApp(read, ControlApi(root=sandbox, env=ENV))


@pytest.fixture
def люди(sandbox):
    каталог = OperatorDirectory(sandbox)
    _, секрет = каталог.invite(
        email="super@test", roles=["admin"], created_by="стенд", super_admin=True
    )
    каталог.accept_invite(secret=секрет, password=ПАРОЛЬ)
    _, секрет = каталог.invite(
        email="local@test", roles=["admin"], created_by="стенд", site_id=САЙТ_A
    )
    каталог.accept_invite(secret=секрет, password=ПАРОЛЬ)
    return каталог


def войти(app, email, сайт=""):
    путь = f"/s/{сайт}/admin/login" if сайт else "/admin/login"
    r = app.handle("POST", путь, form={"email": email, "password": ПАРОЛЬ})
    заголовок = r.headers.get("Set-Cookie", "")
    имя, _, остальное = заголовок.partition("=")
    return {имя: остальное.split(";")[0]} if имя else {}


class TestЭкранМассива:
    def test_массив_виден_супер_администратору(self, app, люди):
        cookies = войти(app, "super@test")
        ответ = app.handle("GET", "/admin/fleet", cookies=cookies)
        assert ответ.status == 200
        assert САЙТ_A in ответ.html and САЙТ_B in ответ.html

    def test_показаны_состояние_и_признаки(self, app, люди):
        html = app.handle("GET", "/admin/fleet", cookies=войти(app, "super@test")).html
        assert "Витрина fc-a" in html, "название витрины берётся из её профиля"
        assert "регистрац" in html.lower()

    def test_ссылка_ведёт_в_контур_витрины(self, app, люди):
        html = app.handle("GET", "/admin/fleet", cookies=войти(app, "super@test")).html
        assert f'href="/s/{САЙТ_A}/admin"' in html

    def test_локальный_администратор_массива_не_видит(self, app, люди):
        cookies = войти(app, "local@test", САЙТ_A)
        ответ = app.handle("GET", f"/s/{САЙТ_A}/admin/fleet", cookies=cookies)
        assert ответ.status in (403, 404)

    def test_ссылки_на_массив_в_контуре_витрины_нет(self, app, люди):
        cookies = войти(app, "local@test", САЙТ_A)
        html = app.handle("GET", f"/s/{САЙТ_A}/admin", cookies=cookies).html
        assert "/admin/fleet" not in html


class TestПереключение:
    def test_переключение_записывается(self, app, люди):
        from factory import audit

        cookies = войти(app, "super@test")
        страница = app.handle("GET", "/admin/fleet", cookies=cookies).html
        csrf = страница.split('name="_csrf" value="', 1)[1].split('"', 1)[0]
        ответ = app.handle(
            "POST", "/admin/fleet/switch",
            form={"_csrf": csrf, "siteId": САЙТ_B}, cookies=cookies,
        )
        assert ответ.status in (302, 303)
        assert ответ.headers["Location"].startswith(f"/s/{САЙТ_B}/admin")
        записи = [з for з in audit.read_all() if з.get("action") == "control.tenant.switch"]
        assert записи and записи[-1]["site_id"] == САЙТ_B

    def test_переключение_на_несуществующую_отклонено(self, app, люди):
        cookies = войти(app, "super@test")
        страница = app.handle("GET", "/admin/fleet", cookies=cookies).html
        csrf = страница.split('name="_csrf" value="', 1)[1].split('"', 1)[0]
        ответ = app.handle(
            "POST", "/admin/fleet/switch",
            form={"_csrf": csrf, "siteId": "нет-такой"}, cookies=cookies,
        )
        assert ответ.status in (302, 303, 400, 404)
        if ответ.status in (302, 303):
            assert not ответ.headers["Location"].startswith("/s/нет-такой")
