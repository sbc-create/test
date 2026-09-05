"""Маршрутизация админки.

Правило, которому подчинён весь модуль: панель не выполняет действий сама.
Она разбирает форму, вызывает Control API тем же путём, каким его вызвала бы
внешняя автоматика, и показывает ответ. Ни очередь, ни блокировки, ни профили
отсюда не видны — если бы были видны, у панели появился бы второй, расходящийся
путь исполнения.

Отсюда же следует поведение при отказах: панель ничего не «сглаживает». Отказ по
праву, конфликт версии и отклонённая настройка показываются оператору так, как
их вернул API, включая идентификатор связи, — иначе оператор не сможет найти
свой запрос в журнале.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field

from factory.site_engine.admin import ADMIN_COOKIE, CSRF_FIELD, ui
from factory.site_engine.admin.session import SessionStore


@dataclass
class AdminResponse:
    status: int
    html: str = ""
    headers: dict[str, str] = field(default_factory=dict)


def _целое(сырое, по_умолчанию):
    """Число из формы. Мусор — это значение по умолчанию, а не отказ.

    Смещение страницы приходит из адресной строки, и падать на «?offset=абв»
    значит отдавать 500 за чужую опечатку.
    """
    try:
        return int(str(сырое))
    except (TypeError, ValueError):
        return по_умолчанию


def _redirect(location: str, *, extra: dict[str, str] | None = None) -> AdminResponse:
    """Перенаправление после записи.

    Без него обновление страницы повторяет действие, а оператор об этом не
    предупреждён. Ключ идемпотентности защищает от повтора на уровне API, но
    полагаться только на него значит требовать его от каждой формы.
    """
    headers = {"Location": location}
    if extra:
        headers.update(extra)
    return AdminResponse(status=303, headers=headers)


class AdminApp:
    def __init__(
        self,
        read_api,
        control_api,
        *,
        sessions: SessionStore | None = None,
        now=time.time,
        secure_cookie: bool = False,
    ) -> None:
        self._read = read_api
        self._control = control_api
        self._sessions = sessions if sessions is not None else SessionStore(now=now)
        self._secure = secure_cookie

    @property
    def sessions(self) -> SessionStore:
        return self._sessions

    # ---- вспомогательное -------------------------------------------------

    def _cookie_header(self, sid: str, *, drop: bool = False) -> str:
        parts = [
            f"{ADMIN_COOKIE}={'' if drop else sid}",
            "Path=/admin",
            "HttpOnly",
            # Strict, а не Lax: у панели нет сценария перехода со стороннего
            # сайта, а Lax пропускает межсайтовые GET-переходы.
            "SameSite=Strict",
        ]
        if self._secure:
            parts.append("Secure")
        parts.append("Max-Age=0" if drop else "Max-Age=28800")
        return "; ".join(parts)

    def _call(self, method: str, path: str, session, body: dict | None = None):
        """Единственная дверь к Control API.

        Вместе с запросом передаётся контекст следа: без него цепочка
        обрывается на границе панели, и по идентификатору видно, что оператор
        что-то нажал, но не видно, чем это кончилось внутри.
        """
        заголовки = {"Authorization": f"Bearer {session.token}"}
        операция = getattr(self, "_operation", None)
        if операция is not None:
            заголовки.update(операция.headers)
        return self._control.handle(method, path, body=body or {}, headers=заголовки)

    def _scopes(self, session) -> list[str]:
        principal = self._control.principal_for(session.token)
        return sorted(principal.scopes) if principal else []

    def _flash_from(self, response, *, success: str) -> dict:
        body = response.body if isinstance(response.body, dict) else {}
        if 200 <= response.status < 300:
            return {"ok": True, "message": success, "detail": body}
        error = body.get("error", {})
        message = f"{response.status} {error.get('code', 'error')}: {error.get('message', '')}"
        return {"ok": False, "message": message, "detail": body}

    # ---- маршруты --------------------------------------------------------

    def handle(
        self,
        method: str,
        path: str,
        *,
        form: dict[str, str] | None = None,
        cookies: dict[str, str] | None = None,
    ) -> AdminResponse:
        form = form or {}
        cookies = cookies or {}
        # Отрезок панели — корень следа операторского действия.
        изменяющий = method.upper() == "POST"
        начать = getattr(self._control, "begin_client_operation", None)
        self._operation = (
            начать(method, path, service="admin", mutating=изменяющий)
            if начать is not None
            else None
        )
        session = self._sessions.get(cookies.get(ADMIN_COOKIE))
        parts = [p for p in path.strip("/").split("/") if p]

        if parts[:1] != ["admin"]:
            return AdminResponse(
                status=404, html=ui.page("Не найдено", "<p>Нет такой страницы.</p>")
            )
        rest = parts[1:]

        if method == "POST" and rest == ["login"]:
            return self._login(form)

        # Принятие приглашения идёт БЕЗ сессии: приглашённый ещё не может войти.
        # Единственное, что его пускает, — одноразовый секрет из приглашения.
        # CSRF здесь не применим по той же причине (сессии нет), а замена ему —
        # сам секрет: он неугадываем и одноразов.
        if rest[:1] == ["invite"]:
            return self._invite_route(method, rest[1:], form)

        if session is None:
            # Неавторизованная запись не должна отвечать формой входа с кодом
            # 200: автоматика примет это за успех.
            status = 200 if method == "GET" else 403
            начальная = not self._есть_активные_операторы(self._directory())
            return AdminResponse(status=status, html=ui.login(bootstrap=начальная))

        if method == "POST" and not self._sessions.csrf_valid(session.sid, form.get(CSRF_FIELD)):
            return AdminResponse(
                status=403,
                html=ui.page(
                    "Отказ",
                    '<div class="flash bad">Форма устарела или '
                    "подделана. Обновите страницу и повторите.</div>",
                ),
            )

        if method == "POST" and rest == ["logout"]:
            self._control.drop_session_principal(session.token)
            self._sessions.destroy(session.sid)
            return _redirect("/admin", extra={"Set-Cookie": self._cookie_header("", drop=True)})

        if getattr(session, "operator_id", "") and session.token:
            from factory.site_engine.operators import scopes_for

            self._control.update_session_principal(session.token, scopes=scopes_for(session.roles))

        csrf = self._sessions.csrf_token(session.sid)
        label = f"токен {session.token_fingerprint()}"
        flash = getattr(session, "flash", None)
        if flash is not None:
            session.flash = None

        if method == "GET" and rest == []:
            return self._record(self._dashboard(session, flash, label, csrf))
        if method == "GET" and rest == ["audit"]:
            return self._record(self._audit(session, flash, label, csrf, form))
        if method == "GET" and rest == ["releases"]:
            return self._record(self._программа(session, "releases", flash, label, csrf))
        if method == "GET" and rest == ["incidents"]:
            return self._record(self._программа(session, "incidents", flash, label, csrf))
        if method == "GET" and rest == ["overview"]:
            ответ = self._call("GET", "/api/v1/overview", session, {})
            if ответ.status != 200:
                return self._record(
                    AdminResponse(
                        status=ответ.status,
                        html=ui.page("Сводка", '<div class="flash bad">Сводка недоступна.</div>'),
                    )
                )
            return self._record(
                AdminResponse(
                    status=200,
                    html=ui.overview(ответ.body, flash=flash, session_label=label, csrf=csrf),
                )
            )
        if method == "GET" and rest == ["jobs"]:
            ответ = self._call("GET", "/api/v1/jobs", session, {"limit": 50})
            if ответ.status != 200:
                return self._record(
                    AdminResponse(
                        status=ответ.status,
                        html=ui.page("Задания", '<div class="flash bad">Задания недоступны.</div>'),
                    )
                )
            return self._record(
                AdminResponse(
                    status=200,
                    html=ui.jobs(ответ.body, flash=flash, session_label=label, csrf=csrf),
                )
            )
        if method == "GET" and rest == ["sites"]:
            ответ = self._call("GET", "/api/v1/sites-status", session, {})
            if ответ.status != 200:
                return self._record(
                    AdminResponse(
                        status=ответ.status,
                        html=ui.page("Витрины", '<div class="flash bad">Витрины недоступны.</div>'),
                    )
                )
            return self._record(
                AdminResponse(
                    status=200,
                    html=ui.sites_list(ответ.body, flash=flash, session_label=label, csrf=csrf),
                )
            )
        if rest[:1] == ["new-site"]:
            return self._record(
                self._new_site_route(session, method, rest[1:], form, flash, label, csrf)
            )
        if rest[:1] == ["settings"]:
            return self._record(
                self._settings_route(session, method, rest[1:], form, flash, label, csrf)
            )
        if rest[:1] == ["content"]:
            return self._record(
                self._content_route(session, method, rest[1:], form, flash, label, csrf)
            )
        if rest[:1] == ["users"]:
            return self._record(
                self._users_route(session, method, rest[1:], form, flash, label, csrf)
            )
        if rest[:1] == ["review"]:
            return self._record(
                self._review_route(session, method, rest[1:], form, flash, label, csrf)
            )
        if rest[:1] == ["sites"] and len(rest) >= 2:
            site_id = rest[1]
            tail = rest[2:]
            if method == "GET" and not tail:
                return self._site(session, site_id, flash, label, csrf)
            if method == "POST" and tail == ["jobs"]:
                return self._record(self._job(session, site_id, form))
            if method == "POST" and tail == ["cache"]:
                return self._cache(session, site_id, form)
            if method == "POST" and tail == ["settings"]:
                return self._settings(session, site_id, form)
        return AdminResponse(status=404, html=ui.page("Не найдено", "<p>Нет такой страницы.</p>"))

    # ------------------------------------------------------------------
    # Каталог
    # ------------------------------------------------------------------
    def _витрины(self, session) -> list[str]:
        ответ = self._read.handle("/api/v1/sites")
        if ответ.status != 200:
            return []
        строки = ответ.body.get("sites") or ответ.body.get("items") or []
        return [
            s.get("siteId") or s.get("site_id") or s.get("id")
            for s in строки
            if isinstance(s, dict)
        ]

    def _первая_с_каталогом(self, session, витрины: list[str]) -> str:
        """Первая витрина, у которой каталог действительно читается."""
        for site in витрины:
            ответ = self._call("GET", "/api/v1/content", session, {"siteId": site, "limit": 1})
            if ответ.status == 200:
                return site
        return ""

    def _content_route(
        self,
        session,
        method: str,
        tail: list[str],
        form: dict[str, str],
        flash,
        label: str,
        csrf: str,
    ) -> AdminResponse:
        """Каталог и карточка. Отбор уходит в API, а не выполняется здесь."""
        витрины = [s for s in self._витрины(session) if s]

        if method == "GET" and not tail:
            site = (form.get("siteId") or "").strip()
            if not site:
                # По умолчанию берётся первая витрина С ДОСТУПНЫМ каталогом, а
                # не первая по алфавиту: у части профилей каталога нет вовсе, и
                # раздел открывался ошибкой вместо содержимого.
                site = self._первая_с_каталогом(session, витрины)
            if not site:
                return AdminResponse(
                    status=200,
                    html=ui.page(
                        "Каталог",
                        '<div class="flash warn">Ни у одной витрины нет доступного '
                        "каталога. Проверьте SITE_ENGINE_CATALOG_DIR и то, что "
                        "обновление содержимого отработало.</div>",
                        session_label=label,
                        csrf=csrf,
                    ),
                )
            тело = {
                "siteId": site,
                "q": form.get("q") or "",
                "kind": form.get("kind") or "",
                "reason": form.get("reason") or "",
                "sort": form.get("sort") or "externalId",
                "offset": _целое(form.get("offset"), 0),
                "limit": ui.REVIEW_PAGE,
            }
            ответ = self._call("GET", "/api/v1/content", session, тело)
            if ответ.status != 200:
                return AdminResponse(
                    status=ответ.status,
                    html=ui.page(
                        "Каталог",
                        f'<div class="flash bad">{ui._e(str(ответ.body))}</div>',
                        session_label=label,
                        csrf=csrf,
                    ),
                )
            return AdminResponse(
                status=200,
                html=ui.content_list(
                    ответ.body, витрины=витрины, flash=flash, session_label=label, csrf=csrf
                ),
            )

        if method == "GET" and len(tail) == 2:
            ответ = self._call("GET", f"/api/v1/content/{tail[0]}/{tail[1]}", session, {})
            if ответ.status != 200:
                return AdminResponse(
                    status=ответ.status,
                    html=ui.page(
                        "Запись",
                        '<div class="flash bad">Записи нет.</div>',
                        session_label=label,
                        csrf=csrf,
                    ),
                )
            return AdminResponse(
                status=200,
                html=ui.content_item(ответ.body, flash=flash, session_label=label, csrf=csrf),
            )

        return AdminResponse(status=404, html=ui.page("Не найдено", "<p>Нет такой страницы.</p>"))

    # ------------------------------------------------------------------
    # Люди
    # ------------------------------------------------------------------
    def _users_route(
        self,
        session,
        method: str,
        tail: list[str],
        form: dict[str, str],
        flash,
        label: str,
        csrf: str,
    ) -> AdminResponse:
        """Экран людей. Панель ничего не решает: всё через Control API."""
        может = self._есть_права(session, "operators:write")
        свой = getattr(session, "operator_id", "")

        if method == "GET" and not tail:
            люди = self._call("GET", "/api/v1/operators", session, {"limit": 100})
            if люди.status != 200:
                return AdminResponse(
                    status=люди.status,
                    html=ui.page("Люди", '<div class="flash bad">Список недоступен.</div>'),
                )
            приглашения = (
                (
                    self._call("GET", "/api/v1/operators/invites", session, {}).body.get("items")
                    or []
                )
                if может
                else []
            )
            сессии = (
                (
                    self._call("GET", "/api/v1/operators/sessions", session, {}).body.get("items")
                    or []
                )
                if может
                else []
            )
            return AdminResponse(
                status=200,
                html=ui.users(
                    люди.body,
                    приглашения,
                    сессии,
                    flash=flash,
                    session_label=label,
                    csrf=csrf,
                    может=может,
                    свой_id=свой,
                ),
            )

        if method == "POST" and tail == ["invites"]:
            ответ = self._call(
                "POST",
                "/api/v1/operators/invites",
                session,
                {"email": form.get("email") or "", "roles": [form.get("role") or "viewer"]},
            )
            if ответ.status == 201:
                # Ответ отдаётся сразу, без перенаправления: секрет не должен
                # задерживаться в сессии между запросами.
                return AdminResponse(
                    status=200,
                    html=ui.invite_created(
                        ответ.body, ответ.body.get("secret", ""), session_label=label, csrf=csrf
                    ),
                )
            session.flash = self._flash_from(ответ, success="")
            return _redirect("/admin/users")

        if method == "POST" and len(tail) == 3 and tail[0] == "invites":
            ответ = self._call("POST", f"/api/v1/operators/invites/{tail[1]}", session, {})
            session.flash = self._flash_from(ответ, success="Приглашение отозвано")
            return _redirect("/admin/users")

        if method == "POST" and tail == ["sessions", "revoke"]:
            ответ = self._call(
                "POST",
                "/api/v1/operators/sessions/revoke",
                session,
                {"sessionId": form.get("sessionId") or ""},
            )
            session.flash = self._flash_from(ответ, success="Сессия отозвана")
            return _redirect("/admin/users")

        if method == "POST" and len(tail) == 2:
            operator_id, действие = tail
            тело: dict = {
                "actorOperatorId": свой,
                "actorRoles": list(getattr(session, "roles", ())),
            }
            if действие == "roles":
                тело["roles"] = [form.get("role") or "viewer"]
            if действие == "block":
                тело["reason"] = form.get("reason") or ""
            ответ = self._call("POST", f"/api/v1/operators/{operator_id}/{действие}", session, тело)
            session.flash = self._flash_from(
                ответ,
                success={
                    "roles": "Роль изменена",
                    "block": "Оператор заблокирован",
                    "unblock": "Оператор разблокирован",
                    "revoke-sessions": "Сессии отозваны",
                }.get(действие, "Готово"),
            )
            return _redirect("/admin/users")

        return AdminResponse(status=404, html=ui.page("Не найдено", "<p>Нет такой страницы.</p>"))

    # ------------------------------------------------------------------
    # Очередь разбора
    # ------------------------------------------------------------------
    def _может_решать(self, session) -> bool:
        return "review:write" in self._scopes(session)

    def _сверка(self, session, item_id: str):
        """Сверка «было/стало». Недоступна — карточка всё равно открывается."""
        ответ = self._call("GET", f"/api/v1/review-queue/{item_id}/preview", session, {})
        return ответ.body if ответ.status == 200 else None

    def _review_route(
        self,
        session,
        method: str,
        tail: list[str],
        form: dict[str, str],
        flash,
        label: str,
        csrf: str,
    ) -> AdminResponse:
        """Разделы очереди. Панель ничего не решает сама — только вызывает API.

        Право проверяется и здесь, и в API. Проверка в панели не защита, а
        удобство: она прячет кнопку, которой пользователь всё равно не смог бы
        воспользоваться. Защита — в API, и она остаётся, даже если панель
        обойти.
        """
        может = self._может_решать(session)

        if method == "GET" and not tail:
            тело = {
                "limit": ui.REVIEW_PAGE,
                "offset": _целое(form.get("offset"), 0),
                "state": form.get("state") or "",
            }
            ответ = self._call("GET", "/api/v1/review-queue", session, тело)
            if ответ.status != 200:
                return AdminResponse(
                    status=ответ.status,
                    html=ui.page(
                        "Очередь", f'<div class="flash bad">{ui._e(str(ответ.body))}</div>'
                    ),
                )
            return AdminResponse(
                status=200,
                html=ui.review_list(
                    ответ.body,
                    фильтры={"state": form.get("state") or ""},
                    flash=flash,
                    session_label=label,
                    csrf=csrf,
                    может_решать=может,
                ),
            )

        if method == "GET" and tail == ["batch"]:
            тело = {
                "mode": "dryRun",
                "conflictCode": form.get("conflictCode") or "",
                "fromValue": form.get("fromValue") or "",
                "toValue": form.get("toValue") or "",
                "sample": 10,
            }
            ответ = self._call("POST", "/api/v1/review-queue/batch", session, тело)
            if ответ.status != 200:
                return AdminResponse(
                    status=ответ.status,
                    html=ui.page(
                        "Сухой прогон", f'<div class="flash bad">{ui._e(str(ответ.body))}</div>'
                    ),
                )
            return AdminResponse(
                status=200, html=ui.review_batch(ответ.body, session_label=label, csrf=csrf)
            )

        if method == "POST" and tail == ["batch"]:
            тело = {
                "mode": "apply",
                "conflictCode": form.get("conflictCode") or "",
                "fromValue": form.get("fromValue") or "",
                "toValue": form.get("toValue") or "",
                "expectedFingerprint": form.get("expectedFingerprint") or "",
                "note": form.get("note") or "",
            }
            ответ = self._call("POST", "/api/v1/review-queue/batch", session, тело)
            session.flash = self._flash_from(
                ответ,
                success=f"Применено к {ответ.body.get('changed', 0)} записям, "
                f"партия {ответ.body.get('batchId', '')}",
            )
            return _redirect("/admin/review")

        if method == "GET" and len(tail) == 1:
            ответ = self._call("GET", f"/api/v1/review-queue/{tail[0]}", session, {})
            if ответ.status != 200:
                return AdminResponse(
                    status=ответ.status,
                    html=ui.page(
                        "Запись", '<div class="flash bad">Записи нет или доступ закрыт.</div>'
                    ),
                )
            return AdminResponse(
                status=200,
                html=ui.review_item(
                    ответ.body,
                    flash=flash,
                    session_label=label,
                    csrf=csrf,
                    может_решать=может,
                    сверка=self._сверка(session, tail[0]),
                ),
            )

        if method == "POST" and len(tail) == 2:
            item_id, действие = tail
            тело: dict = {"note": form.get("note") or ""}
            if действие in ("approve", "publish"):
                версия = _целое(form.get("expectedVersion"), None)
                if версия is not None:
                    тело["expectedVersion"] = версия
            if действие == "decide":
                тело["value"] = form.get("value") or ""
                тело["dismiss"] = bool(form.get("dismiss"))
                версия = _целое(form.get("expectedVersion"), None)
                if версия is not None:
                    тело["expectedVersion"] = версия
            ответ = self._call("POST", f"/api/v1/review-queue/{item_id}/{действие}", session, тело)
            session.flash = self._flash_from(
                ответ,
                success={
                    "claim": "Запись взята в работу",
                    "decide": "Решение записано",
                    "approve": "Решение утверждено",
                    "publish": "Опубликовано на витрину",
                    "unpublish": "Снято с витрины",
                    "revert": "Решение отменено",
                }.get(действие, "Готово"),
            )
            return _redirect(f"/admin/review/{item_id}")

        return AdminResponse(status=404, html=ui.page("Не найдено", "<p>Нет такой страницы.</p>"))

    def _record(self, ответ: AdminResponse) -> AdminResponse:
        """Закрыть отрезок панели.

        Возвращается тот же ответ: запись следа не должна менять поведение,
        иначе диагностика начинает влиять на диагностируемое.
        """
        операция = getattr(self, "_operation", None)
        if операция is not None:
            операция.finish(ответ.status)
        return ответ

    def _directory(self):
        from factory.site_engine.operators import OperatorDirectory

        каталог = OperatorDirectory(self._control._root)
        self._sessions.attach_directory(каталог)
        return каталог

    def _есть_активные_операторы(self, каталог) -> bool:
        return каталог.list()["byState"].get("ACTIVE", 0) > 0

    def _login(self, form: dict[str, str]) -> AdminResponse:
        """Вход по учётной записи. Токен — только пока каталог пуст.

        Окно начальной настройки закрывается само: как только появился хотя бы
        один активный оператор, вход по токену отвергается. Постоянный обходной
        путь рядом с каталогом людей обесценивал бы и блокировку, и отзыв, и
        журнал — в нём было бы видно «токен», а не человека.
        """
        from factory.site_engine.operators import OperatorError

        каталог = self._directory()
        email = (form.get("email") or "").strip()
        пароль = form.get("password") or ""

        if email:
            try:
                оператор = каталог.authenticate(email=email, password=пароль)
            except OperatorError:
                return self._отказ_входа()
            from factory.site_engine.operators import scopes_for

            токен_сессии = self._control.mint_session_principal(
                label=оператор.email, scopes=scopes_for(оператор.roles)
            )
            session = self._sessions.create(
                токен_сессии,
                label=оператор.email,
                operator_id=оператор.operator_id,
                email=оператор.email,
                roles=оператор.roles,
            )
            каталог.register_session(sid=session.sid, operator_id=оператор.operator_id)
            return _redirect("/admin", extra={"Set-Cookie": self._cookie_header(session.sid)})

        токен = (form.get("token") or "").strip()
        if not токен or self._есть_активные_операторы(каталог):
            # Пустая форма, неверный токен и закрытое окно начальной настройки
            # отвечают одинаково. Любое различие сообщает, существует ли
            # учётная запись и открыт ли ещё вход по токену.
            return self._отказ_входа()
        return self._login_by_token(токен)

    @staticmethod
    def _отказ_входа() -> AdminResponse:
        """Единственный ответ на любой неудачный вход.

        Раньше пустой токен и неверный токен отвечали одинаково, а адрес с
        паролем — иначе. Этого достаточно, чтобы отличить существующую учётную
        запись от несуществующей по коду ответа.
        """
        return AdminResponse(status=403, html=ui.login(error="Неверный адрес или пароль."))

    def _invite_route(self, method: str, tail: list[str], form: dict[str, str]) -> AdminResponse:
        from factory.site_engine.operators import OperatorError

        каталог = self._directory()
        if method == "GET" and not tail:
            return AdminResponse(
                status=200, html=ui.accept_invite(secret=(form.get("secret") or "").strip())
            )
        if method == "POST" and tail == ["accept"]:
            try:
                каталог.accept_invite(
                    secret=(form.get("secret") or "").strip(), password=form.get("password") or ""
                )
            except OperatorError as ошибка:
                # Текст ошибки здесь конкретен намеренно: секрет уже
                # предъявлен, перебирать нечего, а приглашённому нужно понять,
                # истёк ли срок или он уже воспользовался ссылкой.
                return AdminResponse(
                    status=400,
                    html=ui.accept_invite(
                        error=str(ошибка), secret=(form.get("secret") or "").strip()
                    ),
                )
            return _redirect("/admin")
        return AdminResponse(status=404, html=ui.page("Не найдено", "<p>Нет такой страницы.</p>"))

    def _есть_права(self, session, право: str) -> bool:
        return право in self._scopes(session)

    def _login_by_token(self, токен: str) -> AdminResponse:
        """Вход времени начальной настройки: только пока каталог людей пуст."""
        token = токен
        principal = self._control.principal_for(token) if token else None
        if principal is None:
            return self._отказ_входа()
        session = self._sessions.create(token)
        return _redirect("/admin", extra={"Set-Cookie": self._cookie_header(session.sid)})

    def _dashboard(self, session, flash, label, csrf) -> AdminResponse:
        response = self._read.handle("/api/v1/sites")
        if response.status != 200:
            problem = (
                "Читающий слой недоступен: проверьте SITE_ENGINE_API_ENABLED и "
                "SITE_ENGINE_ENVIRONMENT (допустимо local, test, staging)."
            )
            return AdminResponse(
                status=200,
                html=ui.dashboard(
                    [], flash=flash, session_label=label, csrf=csrf, read_problem=problem
                ),
            )
        sites = response.body.get("items", [])
        # Состояние контрактов берётся у Control API, а не вычисляется здесь:
        # иначе панель начала бы отвечать на вопрос, на который уже отвечает API.
        matrix = self._call("GET", "/api/v1/compatibility", session)
        by_site = {}
        if matrix.status == 200:
            by_site = {row["siteId"]: row for row in matrix.body.get("sites", [])}
        return AdminResponse(
            status=200,
            html=ui.dashboard(
                sites, flash=flash, session_label=label, csrf=csrf, compat_by_site=by_site
            ),
        )

    def _site(self, session, site_id, flash, label, csrf) -> AdminResponse:
        info = self._read.handle(f"/api/v1/sites/{site_id}")
        if info.status != 200:
            return AdminResponse(
                status=info.status,
                html=ui.page(
                    "Витрина",
                    f'<div class="flash bad">Витрина {site_id} недоступна '
                    f"({info.status}).</div>",
                    session_label=label,
                    csrf=csrf,
                ),
            )
        config = self._read.handle(f"/api/v1/sites/{site_id}/config")
        coverage = self._read.handle(f"/api/v1/sites/{site_id}/coverage")
        совместимость = self._call("GET", f"/api/v1/compatibility/{site_id}", session)
        return AdminResponse(
            status=200,
            html=ui.site_detail(
                site_id,
                info=info.body,
                config=config.body if config.status == 200 else {},
                coverage=coverage.body if coverage.status == 200 else {},
                scopes=self._scopes(session),
                compatibility=совместимость.body if совместимость.status == 200 else None,
                flash=flash,
                session_label=label,
                csrf=csrf,
            ),
        )

    def _job(self, session, site_id, form) -> AdminResponse:
        dry = bool(form.get("dryRun"))
        body = {
            "action": (form.get("action") or "").strip(),
            "environment": (form.get("environment") or "staging").strip(),
            "dryRun": dry,
        }
        response = self._call("POST", f"/api/v1/sites/{site_id}/jobs", session, body)
        session.flash = self._flash_from(
            response,
            success="Проверка выполнена, ничего не изменено."
            if dry
            else "Задание поставлено в очередь.",
        )
        return _redirect(f"/admin/sites/{site_id}")

    def _cache(self, session, site_id, form) -> AdminResponse:
        dry = bool(form.get("dryRun"))
        raw_keys = (form.get("keys") or "").strip()
        keys = [k.strip() for k in raw_keys.split(",") if k.strip()] if raw_keys else []
        body = {"scope": (form.get("scope") or "").strip(), "keys": keys, "dryRun": dry}
        response = self._call("POST", f"/api/v1/sites/{site_id}/cache/invalidate", session, body)
        session.flash = self._flash_from(
            response, success="Проверка выполнена." if dry else "Инвалидация запланирована."
        )
        return _redirect(f"/admin/sites/{site_id}")

    def _settings(self, session, site_id, form) -> AdminResponse:
        key = (form.get("key") or "").strip()
        raw = (form.get("value") or "").strip()
        dry = bool(form.get("dryRun"))
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            session.flash = {
                "ok": False,
                "message": "Значение не разобрано как JSON.",
                "detail": {"value": raw},
            }
            return _redirect(f"/admin/sites/{site_id}")

        path = f"/api/v1/sites/{site_id}/settings"
        if dry:
            response = self._call("PATCH", path, session, {"changes": {key: value}, "dryRun": True})
            session.flash = self._flash_from(
                response, success="Проверка выполнена, ничего не изменено."
            )
            return _redirect(f"/admin/sites/{site_id}")

        # Сначала пробный вызов — за версией, затем боевой со сверкой. Панель
        # следует тому же порядку, который предписывает операторам инструкция:
        # если между двумя вызовами вмешается кто-то ещё, будет отказ, а не
        # тихая перезапись чужой правки.
        peek = self._call("PATCH", path, session, {"changes": {key: value}, "dryRun": True})
        if peek.status != 200:
            session.flash = self._flash_from(peek, success="")
            return _redirect(f"/admin/sites/{site_id}")
        version = peek.body.get("currentVersion", "")
        response = self._call(
            "PATCH", path, session, {"changes": {key: value}, "expectedVersion": version}
        )
        session.flash = self._flash_from(response, success="Настройка применена.")
        return _redirect(f"/admin/sites/{site_id}")

    # ------------------------------------------------------------------
    # Новая витрина
    # ------------------------------------------------------------------
    def _new_site_route(
        self, session, method: str, tail: list[str], form: dict, flash, label: str, csrf: str
    ) -> AdminResponse:
        """Мастер заведения витрины. Панель ничего не решает: всё через API."""
        может = self._есть_права(session, "sites:create")

        if method == "POST" and not tail:
            ответ = self._call(
                "POST", "/api/v1/site-requests", session, {"siteId": form.get("siteId") or ""}
            )
            session.flash = self._flash_from(ответ, success="Заявка заведена.")
            куда = (
                f"/admin/new-site?request={ответ.body['requestId']}"
                if ответ.status == 201
                else "/admin/new-site"
            )
            return _redirect(куда)

        if method == "POST" and len(tail) == 1:
            шаг = (form.get("step") or "").strip()
            ответы = {
                к: v for к, v in form.items() if к not in {CSRF_FIELD, "step"}
            }
            ответ = self._call(
                "PATCH", f"/api/v1/site-requests/{tail[0]}", session, {"step": шаг, "answers": ответы}
            )
            session.flash = self._flash_from(ответ, success=f"Шаг «{шаг}» принят.")
            return _redirect(f"/admin/new-site?request={tail[0]}")

        if method != "GET":
            return AdminResponse(status=404, html=ui.page("Не найдено", "<p>Нет такой страницы.</p>"))

        список = self._call("GET", "/api/v1/site-requests", session, {})
        заявки = (список.body.get("items") or []) if список.status == 200 else []
        rid = (form.get("request") or "").strip() or (tail[0] if tail else "")
        заявка = план = None
        беда = ""
        if rid:
            подробно = self._call(
                "GET", f"/api/v1/site-requests/{rid}", session, {"withPlan": True}
            )
            if подробно.status == 200:
                заявка = подробно.body
                план = заявка.get("plan")
            else:
                # Молчаливая пустая страница на месте неудавшегося чтения — это
                # та же ложь, что пустой список вместо недоступного источника:
                # заявка выглядит несуществующей, хотя её просто не прочитали.
                беда = f"заявка не прочитана: {подробно.status} " + str(
                    (подробно.body.get("error") or {}).get("code", "")
                )
        return AdminResponse(
            status=200,
            html=ui.new_site(
                заявки,
                заявка,
                план,
                может=может,
                # Отказ чтения важнее успеха предыдущего шага: сообщение
                # «шаг принят» поверх неудавшегося чтения — ровно та подмена,
                # из-за которой пустая страница выглядела нормальной.
                flash=({"ok": False, "message": беда} if беда else flash),
                session_label=label,
                csrf=csrf,
            ),
        )

    # ------------------------------------------------------------------
    # Настройки
    # ------------------------------------------------------------------
    def _settings_route(
        self, session, method: str, tail: list[str], form: dict, flash, label: str, csrf: str
    ) -> AdminResponse:
        """Отдельный раздел настроек: схема, сравнение, применение, откат."""
        витрины = [s for s in self._витрины(session) if s]
        site = (form.get("site") or "").strip() or (витрины[0] if витрины else "")
        if not site:
            return AdminResponse(
                status=200,
                html=ui.page(
                    "Настройки",
                    '<div class="flash warn">Ни одной витрины не видно.</div>',
                    session_label=label,
                    csrf=csrf,
                ),
            )

        if method == "GET" and not tail:
            return self._settings_page(session, site, flash, label, csrf)
        if method == "POST" and not tail:
            return self._settings_apply(session, site, form, flash, label, csrf)
        if method == "POST" and tail == ["rollback"]:
            ответ = self._call(
                "POST",
                f"/api/v1/settings/{site}/rollback",
                session,
                {"dryRun": bool(form.get("dryRun"))},
            )
            session.flash = self._flash_from(ответ, success="Прежние значения возвращены.")
            return _redirect(f"/admin/settings?site={site}")
        return AdminResponse(status=404, html=ui.page("Не найдено", "<p>Нет такой страницы.</p>"))

    def _settings_state(self, session, site: str):
        return self._call("GET", f"/api/v1/settings/{site}", session, {})

    def _settings_page(
        self, session, site: str, flash, label: str, csrf: str, предпросмотр=None
    ) -> AdminResponse:
        ответ = self._settings_state(session, site)
        if ответ.status != 200:
            return AdminResponse(
                status=ответ.status,
                html=ui.page(
                    "Настройки",
                    f'<div class="flash bad">Настройки недоступны: {ответ.status}.</div>',
                    session_label=label,
                    csrf=csrf,
                ),
            )
        return AdminResponse(
            status=200,
            html=ui.settings(
                ответ.body,
                [s for s in self._витрины(session) if s],
                предпросмотр=предпросмотр,
                flash=flash,
                session_label=label,
                csrf=csrf,
            ),
        )

    def _settings_apply(
        self, session, site: str, form: dict, flash, label: str, csrf: str
    ) -> AdminResponse:
        ключ = (form.get("key") or "").strip()
        сырое = (form.get("value") or "").strip()
        сухой = bool(form.get("dryRun"))
        значение = self._как_значение(сырое)
        путь = f"/api/v1/sites/{site}/settings"

        if сухой:
            ответ = self._call(
                "PATCH", путь, session, {"changes": {ключ: значение}, "dryRun": True}
            )
            if ответ.status != 200:
                session.flash = self._flash_from(ответ, success="")
                return _redirect(f"/admin/settings?site={site}")
            # Сравнение показывается на самой странице, а не строкой сообщения:
            # ответ «что станет другим» нужен рядом с текущими значениями.
            return self._settings_page(
                session, site, None, label, csrf, предпросмотр=ответ.body.get("diff") or {}
            )

        # Версия берётся из формы, а не из свежего чтения. Свежее чтение перед
        # записью сделало бы сверку версий бессмысленной: она бы всегда
        # совпадала, и чужая правка между показом страницы и отправкой формы
        # была бы затёрта молча.
        версия = (form.get("expectedVersion") or "").strip()
        тело = {"changes": {ключ: значение}}
        if версия:
            тело["expectedVersion"] = версия
        ответ = self._call("PATCH", путь, session, тело)
        session.flash = self._flash_from(ответ, success="Настройка применена.")
        return _redirect(f"/admin/settings?site={site}")

    @staticmethod
    def _как_значение(сырое: str):
        """Число, логическое значение или JSON — но не молчаливая строка.

        Поле ввода одно на все настройки: и на число, и на словарь. Разобрать
        как JSON и при неудаче оставить строкой правильнее, чем требовать от
        оператора кавычек вокруг восьмёрки.
        """
        try:
            return json.loads(сырое)
        except json.JSONDecodeError:
            return сырое

    #: Поля отбора журнала. Замкнутый список: произвольные параметры из строки
    #: запроса уходили бы в API как есть и однажды стали бы чужим фильтром.
    ОТБОР_ЖУРНАЛА = ("actor", "siteId", "action", "correlationId", "result", "since", "until")

    def _программа(self, session, раздел: str, flash, label: str, csrf: str) -> AdminResponse:
        """Выпуски и происшествия. Панель только читает координацию программы."""
        заголовок = {"releases": "Выпуски", "incidents": "Происшествия"}[раздел]
        ответ = self._call("GET", f"/api/v1/{раздел}", session, {})
        if ответ.status != 200:
            return AdminResponse(
                status=ответ.status,
                html=ui.page(
                    заголовок,
                    f'<div class="flash bad">Раздел недоступен: {ответ.status}.</div>',
                    session_label=label,
                    csrf=csrf,
                ),
            )
        рисовать = ui.releases if раздел == "releases" else ui.incidents
        return AdminResponse(
            status=200,
            html=рисовать(ответ.body, flash=flash, session_label=label, csrf=csrf),
        )

    def _audit(self, session, flash, label, csrf, form: dict | None = None) -> AdminResponse:
        отбор = {
            имя: значение.strip()
            for имя in self.ОТБОР_ЖУРНАЛА
            if (значение := (form or {}).get(имя, "").strip())
        }
        response = self._call("GET", "/api/v1/audit", session, {"limit": 50, **отбор})
        if response.status != 200:
            причина = (response.body.get("error") or {}).get("message", "")
            return AdminResponse(
                status=response.status,
                html=ui.page(
                    "Журнал",
                    f'<div class="flash bad">Журнал недоступен: {response.status}. '
                    f"{ui._e(причина)}</div>",
                    session_label=label,
                    csrf=csrf,
                ),
            )
        return AdminResponse(
            status=200,
            html=ui.audit(
                response.body.get("entries", []),
                total=response.body.get("total", 0),
                matched=response.body.get("matched"),
                отбор=отбор,
                session_label=label,
                csrf=csrf,
                flash=flash,
            ),
        )
