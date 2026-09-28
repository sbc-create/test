"""REQ-SITE-ADMIN-ENTRY: своя точка входа у каждого сайта.

Админка одна на массив: вход по `/admin`, витрина выбирается параметром
запроса. Для флота этого мало, и мало по существу — у сайта нет ни своего
адреса, ни своего оформления, а сессия, полученная где угодно, действует везде.

Три правила, каждое написано на конкретный способ соврать.

**Адрес принадлежит сайту.** `/s/<siteId>/admin` — вход именно этого сайта.
Общий вход с выбором витрины оставляет тенанта в руках у того, кто правит
строку запроса.

**Сессия не переходит между сайтами.** Полученная на одном сайте, на соседнем
она не значит ничего. Иначе изоляция держится на том, что никто не подставил
чужой адрес к своей печенье.

**Чужой оператор не входит.** Оператор витрины A, пришедший на вход витрины B,
получает тот же отказ, что и человек с неверным паролем: различие сообщало бы,
что учётная запись существует.
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

САЙТ_A = "lords-01"
САЙТ_B = "lords-02"
ТОКЕН = "boot"
ПАРОЛЬ = "длинный-пароль-для-проверки-1"
REPO = Path(__file__).resolve().parents[2]

ENV = {
    "SITE_ENGINE_CONTROL_WRITES": "1",
    "SITE_ENGINE_CONTROL_TOKENS": (
        f"{ТОКЕН}=read,jobs:write,config:write,audit:read,review:write,operators:write"
    ),
    "SITE_ENGINE_CATALOG_DIR": "var/lords/lords/catalog-cache",
}


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setattr(PATHS, "root", tmp_path)
    профили = tmp_path / "config" / "site-profiles"
    профили.mkdir(parents=True)
    образец = json.loads(
        (REPO / "config" / "site-profiles" / "lords-01.json").read_text(encoding="utf-8")
    )
    for сайт, имя in ((САЙТ_A, "Первая витрина"), (САЙТ_B, "Вторая витрина")):
        d = dict(образец)
        d.update(
            {
                "site_id": сайт,
                "domains": [f"{сайт}.test"],
                "canonical_host": f"{сайт}.test",
                "brand": {"name": имя, "colors": {"primary": "#1f4fd8"}},
            }
        )
        (профили / f"{сайт}.json").write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    кэш = tmp_path / "var" / "lords" / "lords" / "catalog-cache"
    кэш.mkdir(parents=True)
    for сайт in (САЙТ_A, САЙТ_B):
        (кэш / f"{сайт}.json").write_text(
            json.dumps({"fetched_at_ms": 0, "source": "t", "items": []}, ensure_ascii=False),
            encoding="utf-8",
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
    итог = {}
    for сайт, адрес in ((САЙТ_A, "a@test"), (САЙТ_B, "b@test")):
        _, секрет = каталог.invite(
            email=адрес, roles=["admin"], created_by="владелец", site_id=сайт
        )
        итог[сайт] = каталог.accept_invite(secret=секрет, password=ПАРОЛЬ)
    _, секрет = каталог.invite(
        email="super@test", roles=["admin"], created_by="владелец", super_admin=True
    )
    итог["super"] = каталог.accept_invite(secret=секрет, password=ПАРОЛЬ)
    return итог


def войти(app, сайт: str, email: str, пароль: str = ПАРОЛЬ):
    return app.handle(
        "POST", f"/s/{сайт}/admin/login", form={"email": email, "password": пароль}
    )


def печенье(ответ) -> dict:
    из_заголовка = ответ.headers.get("Set-Cookie", "")
    имя, _, остальное = из_заголовка.partition("=")
    return {имя: остальное.split(";")[0]}


class TestАдресСайта:
    def test_страница_входа_сайта_открывается(self, app, люди):
        ответ = app.handle("GET", f"/s/{САЙТ_A}/admin")
        assert ответ.status == 200
        assert 'name="password"' in ответ.html

    def test_оформление_сайта_на_странице_входа(self, app, люди):
        """Вход без имени сайта — это общий вход, а не вход этого сайта."""
        html = app.handle("GET", f"/s/{САЙТ_A}/admin").html
        assert "Первая витрина" in html
        assert "Вторая витрина" not in html

    def test_неизвестный_сайт_даёт_404(self, app, люди):
        assert app.handle("GET", "/s/нет-такой/admin").status == 404

    def test_вход_своего_оператора(self, app, люди):
        ответ = войти(app, САЙТ_A, "a@test")
        assert ответ.status in (302, 303)
        assert ответ.headers["Location"].startswith(f"/s/{САЙТ_A}/admin")

    def test_чужой_оператор_не_входит(self, app, люди):
        """Тот же отказ, что и при неверном пароле: различие сообщало бы,
        что учётная запись существует у соседа."""
        ответ = войти(app, САЙТ_A, "b@test")
        assert ответ.status == 403
        неверный = войти(app, САЙТ_A, "a@test", "не тот пароль")
        assert ответ.status == неверный.status

    def test_супер_администратор_входит_на_любой(self, app, люди):
        for сайт in (САЙТ_A, САЙТ_B):
            assert войти(app, сайт, "super@test").status in (302, 303)


class TestСессииНеПересекаются:
    def test_сессия_одного_сайта_не_годится_на_другом(self, app, люди):
        ответ = войти(app, САЙТ_A, "a@test")
        cookies = печенье(ответ)
        свой = app.handle("GET", f"/s/{САЙТ_A}/admin", cookies=cookies)
        assert "Выйти" in свой.html
        чужой = app.handle("GET", f"/s/{САЙТ_B}/admin", cookies=cookies)
        assert "Выйти" not in чужой.html, "сессия перешла на соседний сайт"
        assert 'name="password"' in чужой.html

    def test_печенья_разных_сайтов_живут_рядом(self, app, люди):
        """Вход на второй сайт не выбрасывает с первого."""
        a = печенье(войти(app, САЙТ_A, "a@test"))
        b = печенье(войти(app, САЙТ_B, "b@test"))
        assert set(a) != set(b), "одно имя печенья на все сайты стирает соседнюю сессию"
        вместе = {**a, **b}
        assert "Выйти" in app.handle("GET", f"/s/{САЙТ_A}/admin", cookies=вместе).html
        assert "Выйти" in app.handle("GET", f"/s/{САЙТ_B}/admin", cookies=вместе).html

    def test_выход_не_трогает_соседнюю_сессию(self, app, люди):
        a = печенье(войти(app, САЙТ_A, "a@test"))
        b = печенье(войти(app, САЙТ_B, "b@test"))
        вместе = {**a, **b}
        csrf_страница = app.handle("GET", f"/s/{САЙТ_A}/admin", cookies=вместе).html
        метка = 'name="_csrf" value="'
        csrf = csrf_страница.split(метка, 1)[1].split('"', 1)[0]
        app.handle(
            "POST", f"/s/{САЙТ_A}/admin/logout", form={"_csrf": csrf}, cookies=вместе
        )
        assert "Выйти" in app.handle("GET", f"/s/{САЙТ_B}/admin", cookies=вместе).html


class TestРазделыСайта:
    def test_разделы_открываются_под_адресом_сайта(self, app, люди):
        cookies = печенье(войти(app, САЙТ_A, "a@test"))
        for раздел in ("", "/content", "/users", "/settings", "/audit"):
            ответ = app.handle("GET", f"/s/{САЙТ_A}/admin{раздел}", cookies=cookies)
            assert ответ.status == 200, f"{раздел}: {ответ.status}"

    def test_в_разделах_нет_выбора_чужой_витрины(self, app, люди):
        cookies = печенье(войти(app, САЙТ_A, "a@test"))
        html = app.handle("GET", f"/s/{САЙТ_A}/admin/content", cookies=cookies).html
        assert САЙТ_B not in html, "на странице сайта виден соседний"

    def test_ссылки_ведут_внутрь_своего_сайта(self, app, люди):
        cookies = печенье(войти(app, САЙТ_A, "a@test"))
        html = app.handle("GET", f"/s/{САЙТ_A}/admin", cookies=cookies).html
        assert f'href="/s/{САЙТ_A}/admin/content"' in html
        assert 'href="/admin/content"' not in html, "ссылка уводит в общий контур"
