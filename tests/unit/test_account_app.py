"""REQ-ACCOUNT-UI: путь зрителя целиком через маршруты.

Проверяется не наличие страниц, а жизненный цикл: регистрация → подтверждение
→ вход → профиль → выход → вход → смена пароля → завершение сессий → выгрузка
→ удаление. И отдельно — злоупотребления: подделанная форма, чужая сессия,
повторное использование ссылки, вход без подтверждения.
"""
from __future__ import annotations

import pytest

from factory.site_engine import account_ui as ui
from factory.site_engine.account_app import AccountApp
from factory.site_engine.accounts import AccountDirectory, AccountState
from factory.site_engine.mail import CaptureMailer, SmtpMailer

ПАРОЛЬ = "пароль-зрителя-1"
НОВЫЙ = "совершенно-новый-пароль"
АДРЕС = "viewer@example.test"


@pytest.fixture
def почта():
    return CaptureMailer()


@pytest.fixture
def app(tmp_path, почта):
    каталог = AccountDirectory(tmp_path, mailer=почта)
    return AccountApp(каталог, site_id="s1", enabled=True,
                      allow_capture_mailer=True, secure_cookie=False)


def токен(почта, purpose="verify"):
    письмо = почта.last(purpose)
    assert письмо is not None, f"письма {purpose} не было"
    return письмо.body.split("token=")[1].split()[0]


def куки_из(ответ):
    значение = ответ.headers.get("Set-Cookie", "")
    return {ui.ACCOUNT_COOKIE: значение.split(";")[0].split("=", 1)[1]}


def войти(app, email=АДРЕС, пароль=ПАРОЛЬ):
    ответ = app.handle("POST", "/account/login",
                       form={"email": email, "password": пароль})
    assert ответ.status == 303, ответ.status
    куки = куки_из(ответ)
    csrf = app.sessions.csrf_token(куки[ui.ACCOUNT_COOKIE])
    return куки, csrf


def зарегистрировать(app, почта):
    app.handle("POST", "/account/register",
               form={"email": АДРЕС, "password": ПАРОЛЬ, "consent": "1",
                     "displayName": "Зритель"})
    app.handle("GET", "/account/verify", form={"token": токен(почта)})


# --------------------------------------------------------------------------
# Включение
# --------------------------------------------------------------------------
class TestВключение:
    def test_без_готовой_доставки_регистрация_не_включается(self, tmp_path, почта):
        выкл = AccountApp(AccountDirectory(tmp_path, mailer=почта), site_id="s1",
                          enabled=True)
        assert выкл.enabled is False
        ответ = выкл.handle("GET", "/account/register")
        assert ответ.status == 503
        assert "доставка писем" in ответ.html

    def test_настроенный_smtp_включает(self, tmp_path):
        вкл = AccountApp(
            AccountDirectory(tmp_path, mailer=SmtpMailer(host="h", port=25,
                                                         sender="s@x")),
            site_id="s1", enabled=True)
        assert вкл.enabled and вкл.status()["productionEligible"]

    def test_заглушка_отличима_от_настоящей_доставки(self, app):
        st = app.status()
        assert st["enabled"] and st["productionEligible"] is False
        assert "не годится" in st["blocker"]

    def test_без_флага_витрины_страниц_нет(self, tmp_path, почта):
        выкл = AccountApp(AccountDirectory(tmp_path, mailer=почта), site_id="s1",
                          enabled=False)
        assert выкл.handle("GET", "/account/register").status == 404


# --------------------------------------------------------------------------
# Жизненный цикл
# --------------------------------------------------------------------------
class TestЖизненныйЦикл:
    def test_путь_целиком(self, app, почта, tmp_path):
        # регистрация
        ответ = app.handle("POST", "/account/register",
                           form={"email": АДРЕС, "password": ПАРОЛЬ,
                                 "consent": "1", "displayName": "Зритель"})
        assert ответ.status == 200 and "письмо" in ответ.html

        # до подтверждения вход невозможен
        assert app.handle("POST", "/account/login",
                          form={"email": АДРЕС, "password": ПАРОЛЬ}).status == 403

        # подтверждение
        подтверждение = app.handle("GET", "/account/verify",
                                   form={"token": токен(почта)})
        assert подтверждение.status == 200 and "подтверждён" in подтверждение.html

        # вход и профиль
        куки, csrf = войти(app)
        профиль = app.handle("GET", "/account", cookies=куки)
        assert профиль.status == 200 and АДРЕС in профиль.html

        # правка профиля
        app.handle("POST", "/account/profile", cookies=куки,
                   form={ui.CSRF_FIELD: csrf, "displayName": "Другое имя"})
        assert "Другое имя" in app.handle("GET", "/account", cookies=куки).html

        # выход
        выход = app.handle("POST", "/account/logout", cookies=куки,
                           form={ui.CSRF_FIELD: csrf})
        assert выход.status == 303 and "Max-Age=0" in выход.headers["Set-Cookie"]
        assert app.handle("GET", "/account", cookies=куки).status == 303

        # снова вход и смена пароля
        куки, csrf = войти(app)
        смена = app.handle("POST", "/account/password", cookies=куки,
                           form={ui.CSRF_FIELD: csrf, "current": ПАРОЛЬ,
                                 "new": НОВЫЙ})
        assert смена.status == 303
        # старая сессия недействительна, старый пароль не подходит
        assert app.handle("GET", "/account", cookies=куки).status == 303
        assert app.handle("POST", "/account/login",
                          form={"email": АДРЕС, "password": ПАРОЛЬ}).status == 403

        # вход новым паролем, выгрузка и удаление
        куки, csrf = войти(app, пароль=НОВЫЙ)
        выгрузка = app.handle("POST", "/account/export", cookies=куки,
                              form={ui.CSRF_FIELD: csrf})
        assert выгрузка.status == 200 and "scrypt" not in выгрузка.html
        удаление = app.handle("POST", "/account/delete", cookies=куки,
                              form={ui.CSRF_FIELD: csrf, "confirm": "УДАЛИТЬ"})
        assert удаление.status == 303
        assert app.handle("GET", "/account", cookies=куки).status == 303

    def test_восстановление_пароля(self, app, почта):
        зарегистрировать(app, почта)
        app.handle("POST", "/account/forgot", form={"email": АДРЕС})
        ответ = app.handle("POST", "/account/reset",
                           form={"token": токен(почта, "reset"),
                                 "password": НОВЫЙ})
        assert ответ.status == 200 and "изменён" in ответ.html
        войти(app, пароль=НОВЫЙ)

    def test_повторная_отправка_подтверждения(self, app, почта):
        app.handle("POST", "/account/register",
                   form={"email": АДРЕС, "password": ПАРОЛЬ, "consent": "1"})
        ответ = app.handle("POST", "/account/resend", form={"email": АДРЕС})
        assert ответ.status == 200
        assert sum(1 for m in почта.sent if m.purpose == "verify") == 2

    def test_завершение_всех_сессий(self, app, почта):
        зарегистрировать(app, почта)
        первые, csrf = войти(app)
        вторые, _ = войти(app)
        ответ = app.handle("POST", "/account/sessions/revoke-all", cookies=первые,
                           form={ui.CSRF_FIELD: csrf})
        assert ответ.status == 303
        assert app.handle("GET", "/account", cookies=вторые).status == 303

    def test_завершение_одной_сессии(self, app, почта):
        зарегистрировать(app, почта)
        первые, csrf1 = войти(app)
        вторые, csrf2 = войти(app)
        сессии = app.directory.list_sessions(
            account_id=app.directory.by_email("s1", АДРЕС).account_id)
        чужая = [s for s in сессии
                 if s["sessionId"] != app.sessions._sessions[
                     вторые[ui.ACCOUNT_COOKIE]].sid[:16]][0]["sessionId"]
        app.handle("POST", "/account/sessions/revoke", cookies=вторые,
                   form={ui.CSRF_FIELD: csrf2, "sessionId": чужая})
        # Своя сессия жива, одна из двух закрыта.
        assert len(app.directory.list_sessions(
            account_id=app.directory.by_email("s1", АДРЕС).account_id)) == 1


# --------------------------------------------------------------------------
# Злоупотребления
# --------------------------------------------------------------------------
class TestЗлоупотребления:
    def test_подделанная_форма_отклонена(self, app, почта):
        зарегистрировать(app, почта)
        куки, _ = войти(app)
        ответ = app.handle("POST", "/account/profile", cookies=куки,
                           form={ui.CSRF_FIELD: "подделка", "displayName": "X"})
        assert ответ.status == 403
        assert app.directory.by_email("s1", АДРЕС).display_name != "X"

    def test_действие_без_сессии_отклонено(self, app, почта):
        зарегистрировать(app, почта)
        assert app.handle("POST", "/account/profile",
                          form={"displayName": "X"}).status == 403

    def test_чужая_cookie_не_даёт_доступа(self, app, почта):
        зарегистрировать(app, почта)
        войти(app)
        assert app.handle("GET", "/account",
                          cookies={ui.ACCOUNT_COOKIE: "подобранная"}).status == 303

    def test_сессия_другой_витрины_не_подходит(self, tmp_path, почта):
        каталог = AccountDirectory(tmp_path, mailer=почта)
        первая = AccountApp(каталог, site_id="s1", enabled=True,
                            allow_capture_mailer=True, secure_cookie=False)
        зарегистрировать(первая, почта)
        куки, _ = войти(первая)
        вторая = AccountApp(каталог, site_id="s2", enabled=True,
                            allow_capture_mailer=True, secure_cookie=False)
        assert вторая.handle("GET", "/account", cookies=куки).status == 303

    def test_повторное_использование_ссылки_подтверждения(self, app, почта):
        app.handle("POST", "/account/register",
                   form={"email": АДРЕС, "password": ПАРОЛЬ, "consent": "1"})
        т = токен(почта)
        app.handle("GET", "/account/verify", form={"token": т})
        повтор = app.handle("GET", "/account/verify", form={"token": т})
        assert повтор.status == 400 and "не подходит" in повтор.html

    def test_удаление_без_подтверждения_не_удаляет(self, app, почта):
        зарегистрировать(app, почта)
        куки, csrf = войти(app)
        app.handle("POST", "/account/delete", cookies=куки,
                   form={ui.CSRF_FIELD: csrf, "confirm": "да"})
        assert app.directory.by_email("s1", АДРЕС).state is AccountState.ACTIVE

    def test_имя_с_разметкой_экранируется(self, app, почта):
        зарегистрировать(app, почта)
        куки, csrf = войти(app)
        app.handle("POST", "/account/profile", cookies=куки,
                   form={ui.CSRF_FIELD: csrf,
                         "displayName": "<script>alert(1)</script>"})
        html = app.handle("GET", "/account", cookies=куки).html
        assert "<script>alert(1)</script>" not in html and "&lt;script&gt;" in html

    def test_cookie_защищена(self, app, почта, tmp_path):
        зарегистрировать(app, почта)
        безопасная = AccountApp(app.directory, site_id="s1", enabled=True,
                                allow_capture_mailer=True, secure_cookie=True)
        ответ = безопасная.handle("POST", "/account/login",
                                  form={"email": АДРЕС, "password": ПАРОЛЬ})
        cookie = ответ.headers["Set-Cookie"]
        for признак in ("HttpOnly", "SameSite=Lax", "Secure", "Path=/"):
            assert признак in cookie, признак

    def test_страницы_помечены_noindex(self, app):
        assert "noindex" in app.handle("GET", "/account/register").html
        assert "noindex" in app.handle("GET", "/account/login").html

    def test_неизвестный_маршрут_не_ломает(self, app):
        assert app.handle("GET", "/account/чего-нет").status == 404
        assert app.handle("GET", "/совсем-не-туда").status == 404
