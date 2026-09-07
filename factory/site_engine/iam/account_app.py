"""Публичный контур учётной записи: маршруты и сессии зрителя.

Собственное хранилище сессий, собственная cookie, собственный секрет CSRF.
Ничего общего с операторской панелью: общий объект однажды позволил бы
зрителю оказаться там, куда его не звали.

Регистрация включается флагом профиля витрины И только при готовой доставке
писем. Второе условие проверяется у самого адаптера, а не у настройки: иначе
достаточно было бы поставить флаг, чтобы «включить» подтверждение, которого
не будет.
"""
from __future__ import annotations

import dataclasses
import hmac
import secrets
import time
from hashlib import sha256
from typing import Any

from factory.site_engine import account_ui as ui
from factory.site_engine.accounts import (
    CONSENT_VERSION,
    AccountDirectory,
    AccountError,
)

SESSION_TTL_SECONDS = 30 * 24 * 60 * 60
SESSION_IDLE_SECONDS = 7 * 24 * 60 * 60


@dataclasses.dataclass
class Response:
    status: int
    html: str = ""
    headers: dict[str, str] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass
class _Session:
    sid: str
    account_id: str
    site_id: str
    created_at: float
    last_seen: float
    message: dict | None = None


class AccountSessions:
    """Сессии зрителей в памяти процесса, с проверкой по каталогу."""

    def __init__(self, directory: AccountDirectory, *, now=time.time) -> None:
        self._now = now
        self._directory = directory
        self._sessions: dict[str, _Session] = {}
        self._csrf_secret = secrets.token_bytes(32)

    def create(self, *, account_id: str, site_id: str) -> _Session:
        сейчас = float(self._now())
        sid = secrets.token_urlsafe(32)
        сессия = _Session(sid=sid, account_id=account_id, site_id=site_id,
                          created_at=сейчас, last_seen=сейчас)
        self._sessions[sid] = сессия
        return сессия

    def get(self, sid: str | None, *, site_id: str):
        if not sid:
            return None, None
        сессия = self._sessions.get(sid)
        if сессия is None:
            return None, None
        сейчас = float(self._now())
        if (сейчас - сессия.created_at > SESSION_TTL_SECONDS
                or сейчас - сессия.last_seen > SESSION_IDLE_SECONDS):
            self._sessions.pop(sid, None)
            return None, None
        # Проверка по каталогу на каждом запросе: отозванная, заблокированная
        # или удалённая запись обязана терять доступ немедленно, а не по
        # истечении срока сессии.
        запись = self._directory.session_valid(sid, site_id=site_id)
        if запись is None:
            self._sessions.pop(sid, None)
            return None, None
        сессия.last_seen = сейчас
        return сессия, запись

    def destroy(self, sid: str | None) -> None:
        if sid:
            self._sessions.pop(sid, None)

    def csrf_token(self, sid: str) -> str:
        return hmac.new(self._csrf_secret, sid.encode("utf-8"), sha256).hexdigest()

    def csrf_valid(self, sid: str, candidate: str | None) -> bool:
        if not candidate:
            return False
        return hmac.compare_digest(
            self.csrf_token(sid).encode("utf-8"),
            candidate.encode("utf-8", errors="surrogatepass"))


class AccountApp:
    """Маршруты `/account/*` одной витрины."""

    def __init__(self, directory: AccountDirectory, *, site_id: str,
                 enabled: bool = False, secure_cookie: bool = True,
                 allow_capture_mailer: bool = False) -> None:
        """`allow_capture_mailer` — только для тестов и локальной проверки.

        Отдельным явным ключом, а не настройкой окружения: путь, которым
        включается регистрация без настоящей доставки, обязан быть виден в
        коде вызывающего. Признак попадает в `status()`, поэтому «включено с
        заглушкой» отличимо от «включено по-настоящему» на любом экране.
        """
        self.directory = directory
        self.site_id = site_id
        self.secure_cookie = secure_cookie
        доставка_готова = getattr(directory.mailer, "production_ready", False)
        self.capture_allowed = bool(allow_capture_mailer)
        # Флаг витрины И готовность доставки. Второе — свойство адаптера,
        # настройкой его не подменить.
        self.enabled = bool(enabled) and (доставка_готова or self.capture_allowed)
        self.flag_requested = bool(enabled)
        self.sessions = AccountSessions(directory)

    # ---- служебное ------------------------------------------------------
    def _cookie(self, sid: str, *, drop: bool = False) -> str:
        части = [f"{ui.ACCOUNT_COOKIE}={'' if drop else sid}", "Path=/",
                 "HttpOnly", "SameSite=Lax"]
        if self.secure_cookie:
            части.append("Secure")
        части.append("Max-Age=0" if drop else f"Max-Age={SESSION_TTL_SECONDS}")
        return "; ".join(части)

    @staticmethod
    def _redirect(куда: str, *, extra: dict[str, str] | None = None) -> Response:
        заголовки = {"Location": куда}
        if extra:
            заголовки.update(extra)
        return Response(status=303, headers=заголовки)

    # ---- маршрутизация --------------------------------------------------
    def handle(self, method: str, path: str, *, form: dict[str, str] | None = None,
               cookies: dict[str, str] | None = None,
               user_agent: str = "") -> Response:
        form = form or {}
        cookies = cookies or {}
        части = [p for p in path.strip("/").split("/") if p]
        if части[:1] != ["account"]:
            return Response(status=404, html=ui.page("Не найдено", "<p>Нет.</p>"))
        хвост = части[1:]

        if not self.enabled:
            # Причина называется, а не прячется: «страница не найдена» на
            # выключенной регистрации заставляет искать несуществующую поломку.
            return Response(status=404 if not self.flag_requested else 503,
                            html=ui.disabled())

        сессия, запись = self.sessions.get(cookies.get(ui.ACCOUNT_COOKIE),
                                           site_id=self.site_id)
        csrf = self.sessions.csrf_token(сессия.sid) if сессия else ""
        сообщение = None
        if сессия is not None and сессия.message is not None:
            сообщение, сессия.message = сессия.message, None

        # Записывающие действия без сессии допустимы только там, где сессии
        # ещё нет: вход, регистрация, восстановление. Всё остальное требует
        # и сессии, и совпадающего CSRF.
        без_сессии = {("POST", ("register",)), ("POST", ("login",)),
                      ("POST", ("forgot",)), ("POST", ("resend",)),
                      ("POST", ("reset",))}
        if method == "POST" and (method, tuple(хвост)) not in без_сессии:
            if сессия is None:
                return Response(status=403, html=ui.login(
                    csrf="", сообщение={"kind": "bad", "text": "Нужно войти."}))
            if not self.sessions.csrf_valid(сессия.sid, form.get(ui.CSRF_FIELD)):
                return Response(status=403, html=ui.page(
                    "Отказ", '<div class="msg bad">Форма устарела или подделана.'
                             "</div>"))

        обработчик = getattr(self, f"_{'_'.join(хвост) or 'root'}".replace("-", "_"),
                             None)
        if обработчик is None:
            return Response(status=404, html=ui.page("Не найдено", "<p>Нет.</p>"))
        return обработчик(method, form, сессия, запись, csrf, сообщение,
                          user_agent)

    # ---- страницы --------------------------------------------------------
    def _root(self, method, form, сессия, запись, csrf, сообщение, ua):
        if сессия is None:
            return self._redirect("/account/login")
        return Response(status=200, html=ui.profile(
            запись.as_dict(), self.directory.list_sessions(
                account_id=запись.account_id), csrf=csrf, сообщение=сообщение))

    def _register(self, method, form, сессия, запись, csrf, сообщение, ua):
        if method == "GET":
            return Response(status=200, html=ui.register(
                csrf="", сообщение=сообщение, consent_version=CONSENT_VERSION))
        try:
            итог = self.directory.register(
                site_id=self.site_id, email=form.get("email") or "",
                password=form.get("password") or "",
                consent=bool(form.get("consent")),
                display_name=form.get("displayName") or "")
        except AccountError as ошибка:
            return Response(status=400, html=ui.register(
                csrf="", сообщение={"kind": "bad", "text": str(ошибка)},
                consent_version=CONSENT_VERSION))
        return Response(status=200, html=ui.register(
            csrf="", сообщение={"kind": "ok", "text": итог["message"]},
            consent_version=CONSENT_VERSION))

    def _verify(self, method, form, сессия, запись, csrf, сообщение, ua):
        try:
            self.directory.verify(site_id=self.site_id,
                                  token=form.get("token") or "")
        except AccountError as ошибка:
            return Response(status=400, html=ui.login(
                csrf="", сообщение={"kind": "bad", "text": str(ошибка)}))
        return Response(status=200, html=ui.login(
            csrf="", сообщение={"kind": "ok",
                                "text": "Адрес подтверждён. Теперь можно войти."}))

    def _login(self, method, form, сессия, запись, csrf, сообщение, ua):
        if method == "GET":
            return Response(status=200, html=ui.login(csrf="", сообщение=сообщение))
        try:
            найдена = self.directory.authenticate(
                site_id=self.site_id, email=form.get("email") or "",
                password=form.get("password") or "")
        except AccountError:
            return Response(status=403, html=ui.login(
                csrf="", сообщение={"kind": "bad",
                                    "text": "Неверный адрес или пароль."}))
        новая = self.sessions.create(account_id=найдена.account_id,
                                     site_id=self.site_id)
        self.directory.register_session(sid=новая.sid,
                                        account_id=найдена.account_id,
                                        site_id=self.site_id, user_agent=ua)
        return self._redirect("/account",
                              extra={"Set-Cookie": self._cookie(новая.sid)})

    def _logout(self, method, form, сессия, запись, csrf, сообщение, ua):
        if сессия is not None:
            self.directory.revoke_session(
                sha256(сессия.sid.encode("utf-8")).hexdigest()[:16],
                account_id=сессия.account_id)
            self.sessions.destroy(сессия.sid)
        return self._redirect("/account/login",
                              extra={"Set-Cookie": self._cookie("", drop=True)})

    def _forgot(self, method, form, сессия, запись, csrf, сообщение, ua):
        поля = ('<label for="em">Адрес</label>'
                '<input id="em" name="email" type="email" required>')
        if method == "GET":
            return Response(status=200, html=ui.simple_form(
                title="Восстановление", heading="Восстановление пароля",
                action="/account/forgot", csrf="", поля=поля, кнопка="Отправить",
                подсказка="Ответ одинаков для любого адреса."))
        итог = self.directory.request_reset(site_id=self.site_id,
                                            email=form.get("email") or "")
        return Response(status=200, html=ui.simple_form(
            title="Восстановление", heading="Восстановление пароля",
            action="/account/forgot", csrf="", поля=поля, кнопка="Отправить",
            сообщение={"kind": "ok", "text": итог["message"]}))

    def _resend(self, method, form, сессия, запись, csrf, сообщение, ua):
        поля = ('<label for="em">Адрес</label>'
                '<input id="em" name="email" type="email" required>')
        if method == "GET":
            return Response(status=200, html=ui.simple_form(
                title="Подтверждение", heading="Отправить подтверждение снова",
                action="/account/resend", csrf="", поля=поля, кнопка="Отправить"))
        итог = self.directory.resend_verification(site_id=self.site_id,
                                                  email=form.get("email") or "")
        return Response(status=200, html=ui.simple_form(
            title="Подтверждение", heading="Отправить подтверждение снова",
            action="/account/resend", csrf="", поля=поля, кнопка="Отправить",
            сообщение={"kind": "ok", "text": итог["message"]}))

    def _reset(self, method, form, сессия, запись, csrf, сообщение, ua):
        токен = form.get("token") or ""
        поля = (f'<input type="hidden" name="token" value="{ui._e(токен)}">'
                '<label for="pw">Новый пароль</label>'
                '<input id="pw" name="password" type="password" minlength="12" '
                'autocomplete="new-password" required>')
        if method == "GET":
            return Response(status=200, html=ui.simple_form(
                title="Новый пароль", heading="Новый пароль",
                action="/account/reset", csrf="", поля=поля, кнопка="Сменить",
                подсказка="Смена завершит все начатые сессии."))
        try:
            self.directory.reset_password(site_id=self.site_id, token=токен,
                                          password=form.get("password") or "")
        except AccountError as ошибка:
            return Response(status=400, html=ui.simple_form(
                title="Новый пароль", heading="Новый пароль",
                action="/account/reset", csrf="", поля=поля, кнопка="Сменить",
                сообщение={"kind": "bad", "text": str(ошибка)}))
        return Response(status=200, html=ui.login(
            csrf="", сообщение={"kind": "ok", "text": "Пароль изменён. Войдите."}))

    # ---- действия в профиле ----------------------------------------------
    def _profile(self, method, form, сессия, запись, csrf, сообщение, ua):
        self.directory.update_profile(запись.account_id,
                                      display_name=form.get("displayName") or "")
        сессия.message = {"kind": "ok", "text": "Профиль сохранён."}
        return self._redirect("/account")

    def _password(self, method, form, сессия, запись, csrf, сообщение, ua):
        try:
            self.directory.change_password(запись.account_id,
                                           current=form.get("current") or "",
                                           new=form.get("new") or "")
        except AccountError as ошибка:
            сессия.message = {"kind": "bad", "text": str(ошибка)}
            return self._redirect("/account")
        self.sessions.destroy(сессия.sid)
        return self._redirect("/account/login",
                              extra={"Set-Cookie": self._cookie("", drop=True)})

    def _sessions_revoke(self, method, form, сессия, запись, csrf, сообщение, ua):
        self.directory.revoke_session(form.get("sessionId") or "",
                                      account_id=запись.account_id)
        сессия.message = {"kind": "ok", "text": "Сессия завершена."}
        return self._redirect("/account")

    def _sessions_revoke_all(self, method, form, сессия, запись, csrf, сообщение, ua):
        self.directory.revoke_all_sessions(запись.account_id)
        self.sessions.destroy(сессия.sid)
        return self._redirect("/account/login",
                              extra={"Set-Cookie": self._cookie("", drop=True)})

    def _export(self, method, form, сессия, запись, csrf, сообщение, ua):
        return Response(status=200, html=ui.export_view(
            self.directory.export(запись.account_id), csrf=csrf))

    def _delete(self, method, form, сессия, запись, csrf, сообщение, ua):
        if (form.get("confirm") or "").strip().upper() != "УДАЛИТЬ":
            сессия.message = {"kind": "bad",
                              "text": "Подтверждение не совпало. Ничего не удалено."}
            return self._redirect("/account")
        self.directory.delete(запись.account_id)
        self.sessions.destroy(сессия.sid)
        return self._redirect("/account/login",
                              extra={"Set-Cookie": self._cookie("", drop=True)})

    # ---- сведения для наблюдения ------------------------------------------
    def status(self) -> dict[str, Any]:
        return {"siteId": self.site_id, "enabled": self.enabled,
                "flagRequested": self.flag_requested,
                "captureMailerAllowed": self.capture_allowed,
                "productionEligible": self.enabled and not self.capture_allowed,
                "mailer": getattr(self.directory.mailer, "name", "?"),
                "mailerProductionReady": getattr(
                    self.directory.mailer, "production_ready", False),
                "consentVersion": CONSENT_VERSION,
                "blocker": ("складывающий адаптер: для production не годится"
                            if self.enabled and self.capture_allowed
                            else "" if self.enabled else
                            "доставка писем не готова к production: без "
                            "подтверждения адреса и восстановления пароля "
                            "учётную запись нельзя ни подтвердить, ни вернуть")}
