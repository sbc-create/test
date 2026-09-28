"""REQ-ADMIN-USERS-ACCESS: экран людей и доступа целиком, а не по частям.

Каталог операторов был закрыт раньше и переписывать его нечего. Проверялся он,
однако, только на своём уровне и одним браузерным сценарием — самого экрана в
модульных проверках не было вовсе. Разница существенная: правило, работающее в
каталоге, но не доведённое до экрана, оператор не увидит.

Три места, где экран может соврать при исправном каталоге.

**Сессия без имени.** Список показывал усечённый идентификатор оператора.
Отозвать «сессию 4f2ab1c0e5d3» осмысленно нельзя: неизвестно, чью.

**Отказ без причины.** Снятие последнего администратора и повышение себе роли
каталог запрещает. Если экран показывает пустое сообщение, запрет выглядит
поломкой, и следующим шагом его пробуют обойти.

**Отзыв, который ничего не отзывает.** Отозванная сессия обязана перестать
пускать сразу же, а не после истечения срока.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory.paths import PATHS
from factory.site_engine.admin import ADMIN_COOKIE, CSRF_FIELD
from factory.site_engine.admin.app import AdminApp
from factory.site_engine.api import create_api
from factory.site_engine.api.control import ControlApi
from factory.site_engine.store import InMemoryStore

SITE = "js-site"
ТОКЕН = "tok-boot"
ENV_CONTROL = {
    "SITE_ENGINE_CONTROL_WRITES": "1",
    "SITE_ENGINE_CONTROL_TOKENS": f"{ТОКЕН}=read,jobs:write,audit:read,config:write,operators:write",
}
ENV_READ = {"SITE_ENGINE_API_ENABLED": "1", "SITE_ENGINE_ENVIRONMENT": "test"}
REPO = Path(__file__).resolve().parents[2]
ПАРОЛЬ = "длинный-пароль-для-проверки-1"


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setattr(PATHS, "root", tmp_path)
    профили = tmp_path / "config" / "site-profiles"
    профили.mkdir(parents=True)
    образец = json.loads(
        (REPO / "config" / "site-profiles" / "lords-01.json").read_text(encoding="utf-8")
    )
    образец.update({"site_id": SITE, "domains": ["js.test"], "canonical_host": "js.test"})
    (профили / f"{SITE}.json").write_text(json.dumps(образец, ensure_ascii=False), encoding="utf-8")
    for под in ("queue/inbox", "var/locks", "var/audit", "var/state"):
        (tmp_path / под).mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture
def app(sandbox):
    read = create_api(
        [SITE], root=sandbox, loader=lambda p: (InMemoryStore(p.site_id), "т"), env=ENV_READ
    )
    return AdminApp(read, ControlApi(root=sandbox, env=ENV_CONTROL))


def _csrf(app, cookies) -> str:
    html = app.handle("GET", "/admin/users", cookies=cookies).html
    метка = f'name="{CSRF_FIELD}" value="'
    return html.split(метка, 1)[1].split('"', 1)[0]


def _cookie(ответ) -> dict:
    return {ADMIN_COOKIE: ответ.headers["Set-Cookie"].split(";")[0].split("=", 1)[1]}


def _пригласить(app, cookies, email: str, роль: str) -> str:
    ответ = app.handle(
        "POST",
        "/admin/users/invites",
        form={CSRF_FIELD: _csrf(app, cookies), "email": email, "role": роль},
        cookies=cookies,
    )
    метка = 'secret='
    assert метка in ответ.html, ответ.html[:400]
    return ответ.html.split(метка, 1)[1].split("<", 1)[0].strip()


def _принять(app, секрет: str, email: str) -> None:
    ответ = app.handle(
        "POST",
        "/admin/invite/accept",
        form={"secret": секрет, "password": ПАРОЛЬ},
    )
    assert ответ.status in (200, 302, 303), ответ.status


def _войти(app, email: str, пароль: str = ПАРОЛЬ):
    return app.handle("POST", "/admin/login", form={"email": email, "password": пароль})


@pytest.fixture
def администратор(app):
    """Первый администратор — через окно начальной настройки, как в жизни."""
    старт = _cookie(app.handle("POST", "/admin/login", form={"token": ТОКЕН}))
    секрет = _пригласить(app, старт, "chief@test", "admin")
    _принять(app, секрет, "chief@test")
    ответ = _войти(app, "chief@test")
    assert ответ.status in (302, 303), ответ.status
    return _cookie(ответ)


@pytest.fixture
def редактор(app, администратор):
    секрет = _пригласить(app, администратор, "ed@test", "editor")
    _принять(app, секрет, "ed@test")
    return _cookie(_войти(app, "ed@test"))


class TestСессии:
    def test_в_списке_видно_чья_сессия(self, app, администратор, редактор):
        сессии = _раздел_сессий(app, администратор)
        assert "ed@test" in сессии, "по усечённому идентификатору нельзя понять, чью сессию отзывать"
        assert "chief@test" in сессии

    def test_отзыв_одной_сессии_перестаёт_пускать_сразу(self, app, администратор, редактор):
        сессии = _раздел_сессий(app, администратор)
        кусок = сессии.split("ed@test", 1)[1]
        sid = кусок.split('name="sessionId" value="', 1)[1].split('"', 1)[0]
        app.handle(
            "POST",
            "/admin/users/sessions/revoke",
            form={CSRF_FIELD: _csrf(app, администратор), "sessionId": sid},
            cookies=администратор,
        )
        ответ = app.handle("GET", "/admin/users", cookies=редактор)
        assert ответ.status in (200, 403)
        assert "ed@test" not in ответ.html or "password" in ответ.html

    def test_отзыв_всех_сессий_убирает_их_из_списка(self, app, администратор, редактор):
        оператор_id = _id_по_адресу(app, администратор, "ed@test")
        app.handle(
            "POST",
            f"/admin/users/{оператор_id}/revoke-sessions",
            form={CSRF_FIELD: _csrf(app, администратор)},
            cookies=администратор,
        )
        html = app.handle("GET", "/admin/users", cookies=администратор).html
        сессии = html.split("Активные сессии", 1)[1]
        assert "ed@test" not in сессии


def _раздел_сессий(app, cookies) -> str:
    """Только таблица сессий: та же строка на другом экране ничего не доказывает."""
    html = app.handle("GET", "/admin/users", cookies=cookies).html
    assert "Активные сессии" in html
    return html.split("Активные сессии", 1)[1]


def _id_по_адресу(app, cookies, email: str) -> str:
    html = app.handle("GET", "/admin/users", cookies=cookies).html
    кусок = html.split(email, 1)[1]
    return кусок.split("/admin/users/", 1)[1].split("/", 1)[0]


class TestЗапреты:
    def test_последнего_администратора_не_разжаловать_и_причина_видна(self, app, администратор):
        свой = _id_по_адресу(app, администратор, "chief@test")
        ответ = app.handle(
            "POST",
            f"/admin/users/{свой}/roles",
            form={CSRF_FIELD: _csrf(app, администратор), "role": "viewer"},
            cookies=администратор,
        )
        assert ответ.status in (302, 303)
        html = app.handle("GET", "/admin/users", cookies=администратор).html
        assert "admin" in html
        assert "последн" in html.lower() or "себе" in html.lower()

    def test_себе_роль_поднять_нельзя(self, app, администратор, редактор):
        свой = _id_по_адресу(app, администратор, "ed@test")
        app.handle(
            "POST",
            f"/admin/users/{свой}/roles",
            form={CSRF_FIELD: _csrf(app, редактор), "role": "admin"},
            cookies=редактор,
        )
        html = app.handle("GET", "/admin/users", cookies=администратор).html
        строка = html.split("ed@test", 1)[1].split("</tr>", 1)[0]
        # Проверяется присвоенная роль, а не наличие слова: в выпадающем списке
        # «admin» есть всегда — это перечень возможных ролей, а не текущая.
        assert "<code>admin</code>" not in строка
        assert "<code>editor</code>" in строка

    def test_редактор_не_видит_чужих_сессий_и_приглашений(self, app, администратор, редактор):
        html = app.handle("GET", "/admin/users", cookies=редактор).html
        assert "chief@test" in html
        assert 'name="sessionId"' not in html
        assert "Создать приглашение" not in html

    def test_заблокированный_не_входит(self, app, администратор, редактор):
        оператор_id = _id_по_адресу(app, администратор, "ed@test")
        app.handle(
            "POST",
            f"/admin/users/{оператор_id}/block",
            form={CSRF_FIELD: _csrf(app, администратор), "reason": "проверка"},
            cookies=администратор,
        )
        assert _войти(app, "ed@test").status == 403

    def test_разблокировка_возвращает_вход(self, app, администратор, редактор):
        оператор_id = _id_по_адресу(app, администратор, "ed@test")
        for действие, форма in (("block", {"reason": "проверка"}), ("unblock", {})):
            app.handle(
                "POST",
                f"/admin/users/{оператор_id}/{действие}",
                form={CSRF_FIELD: _csrf(app, администратор), **форма},
                cookies=администратор,
            )
        assert _войти(app, "ed@test").status in (302, 303)


class TestЖурнал:
    def test_действия_над_людьми_попадают_в_журнал(self, app, администратор, редактор):
        оператор_id = _id_по_адресу(app, администратор, "ed@test")
        app.handle(
            "POST",
            f"/admin/users/{оператор_id}/block",
            form={CSRF_FIELD: _csrf(app, администратор), "reason": "проверка"},
            cookies=администратор,
        )
        журнал = app.handle("GET", "/admin/audit", cookies=администратор).html
        assert "operators" in журнал or "block" in журнал
        assert "chief@test" in журнал, "в журнале должно быть видно, кто именно действовал"
