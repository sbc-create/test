"""Публичная регистрация каждой витрины отдельно.

Хранилище учётных записей уже разделено по витринам: личность посетителя — это
пара «витрина + адрес». Снаружи же контур был один: адрес `/account/*` и одна
витрина на процесс, заданная переменной среды. Для флота этого мало — включать
регистрацию перезапуском службы с другой переменной значит включать её сразу
везде и выключать так же.

Три правила, каждое написано на конкретный способ соврать.

**Адрес принадлежит витрине.** `/s/<siteId>/account/*`. Один адрес на все
витрины означает, что посетитель регистрируется неизвестно где, а оператор не
может показать ему ссылку своего сайта.

**Признак включения — настройка витрины.** Он читается из профиля при каждом
обращении: смена настройки действует сразу, без перезапуска. Настройка,
требующая перезапуска, на практике не выключается вовсе.

**Готовность доставки настройкой не подменяется.** Включённый признак при
неготовом отправителе — это регистрация, после которой письмо не придёт.
Признак и готовность проверяются отдельно, и состояние называет, чего не
хватает.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from factory.site_engine.account_app import AccountApp
from factory.site_engine.accounts import AccountDirectory

ПРИЗНАК = "public_registration_enabled"


class FleetAccounts:
    """Публичный контур всех витрин массива под адресами вида `/s/<id>/account`."""

    def __init__(
        self,
        root: Path | str,
        *,
        mail_dir: Path | str | None = None,
        allow_capture_mailer: bool = False,
        secure_cookie: bool = True,
    ) -> None:
        self._root = Path(root)
        self._allow_capture = bool(allow_capture_mailer)
        self._secure = bool(secure_cookie)
        self._mail_dir = Path(mail_dir) if mail_dir else None
        # Приложения витрин создаются лениво и переживают запросы: сессии
        # посетителей живут в них, и пересоздание на каждый запрос выбрасывало
        # бы всех вошедших.
        self._кэш: dict[str, AccountApp] = {}

    # ---- профиль витрины ------------------------------------------------
    def _профиль(self, site_id: str) -> dict[str, Any] | None:
        if not site_id or "/" in site_id or ".." in site_id:
            return None
        путь = self._root / "config" / "site-profiles" / f"{site_id}.json"
        if not путь.is_file():
            return None
        try:
            return json.loads(путь.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def enabled(self, site_id: str) -> bool:
        """Включена ли регистрация на витрине. Читается каждый раз."""
        профиль = self._профиль(site_id)
        if профиль is None:
            return False
        return bool(профиль.get(ПРИЗНАК))

    def status(self, site_id: str) -> dict[str, Any]:
        """Состояние контура витрины с причиной, если он закрыт."""
        профиль = self._профиль(site_id)
        if профиль is None:
            return {"siteId": site_id, "enabled": False, "reason": "витрины нет среди профилей"}
        объявлено = bool(профиль.get(ПРИЗНАК))
        if not объявлено:
            return {
                "siteId": site_id,
                "enabled": False,
                "reason": f"настройка {ПРИЗНАК} витрины выключена",
            }
        приложение = self._приложение(site_id)
        if приложение is None or not приложение.enabled:
            return {
                "siteId": site_id,
                "enabled": False,
                "reason": (
                    "признак включён, но отправитель писем не готов: регистрация, "
                    "после которой письмо не придёт, хуже выключенной"
                ),
            }
        return {"siteId": site_id, "enabled": True, "reason": ""}

    def _приложение(self, site_id: str) -> AccountApp | None:
        if not self.enabled(site_id):
            return None
        готовое = self._кэш.get(site_id)
        if готовое is not None:
            return готовое
        отправитель = None
        if self._mail_dir is not None:
            from factory.site_engine.mail import CaptureMailer

            отправитель = CaptureMailer(self._mail_dir)
        каталог = AccountDirectory(self._root, mailer=отправитель)
        приложение = AccountApp(
            каталог,
            site_id=site_id,
            enabled=True,
            secure_cookie=self._secure,
            allow_capture_mailer=self._allow_capture,
        )
        self._кэш[site_id] = приложение
        return приложение

    # ---- маршруты -------------------------------------------------------
    def handle(
        self,
        method: str,
        path: str,
        *,
        form: dict[str, str] | None = None,
        cookies: dict[str, str] | None = None,
        user_agent: str = "",
    ):
        from factory.site_engine.account_app import Response

        части = [p for p in path.strip("/").split("/") if p]
        if части[:1] != ["s"] or len(части) < 3 or части[2] != "account":
            return Response(status=404, html="<p>Нет такой страницы.</p>")
        сайт = части[1]
        if self._профиль(сайт) is None:
            return Response(status=404, html="<p>Нет такой витрины.</p>")
        приложение = self._приложение(сайт)
        if приложение is None:
            # Отказ называет причину: закрытый контур и несуществующая витрина
            # различаются, и посетителю полезно знать, что сайт существует, а
            # регистрация на нём не ведётся.
            состояние = self.status(сайт)
            return Response(
                status=403,
                html=f"<p>Регистрация на этой витрине не ведётся: {состояние['reason']}.</p>",
            )
        # Внутренний путь приложения не знает о префиксе витрины: он один на
        # все витрины, и знание о префиксе размазалось бы по всем его формам.
        внутренний = "/" + "/".join(части[2:])
        return приложение.handle(
            method, внутренний, form=form, cookies=cookies, user_agent=user_agent
        )
