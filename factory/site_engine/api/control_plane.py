"""Control Plane API v1: чтение движков и команды к ним.

Разделение чтения и записи здесь не украшение. Чтение отвечает данными и ничего
не меняет; запись не отвечает данными — она принимает команду, проверяет право,
записывает в аудит и возвращает идентификатор. Смешение этих двух ролей и есть
то, из-за чего «сохранить форму» однажды становится «выложить в production».

Секреты сюда не попадают по построению: API отдаёт только то, что собрал сам, а
собирает он из профилей, каталога и журналов, где секретов нет.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from factory.site_engine import audit as audit_mod
from factory.site_engine.access import AccessDenied, Permission, Principal, require
from factory.site_engine.api.app import ApiResponse, api_enabled, error
from factory.site_engine.commands import (
    CommandKind,
    CommandLog,
    CommandRejected,
    CommandState,
    payload_digest,
)

API_VERSION = "v1"

#: Ресурсы только для чтения: имя → право, которым они закрыты.
READ_RESOURCES: dict[str, Permission] = {
    "sites": Permission.SITES_READ,
    "site-profiles": Permission.SITES_READ,
    "content": Permission.CONTENT_READ,
    "content-events": Permission.CONTENT_READ,
    "sources": Permission.SITES_READ,
    "shelves": Permission.SITES_READ,
    "schedules": Permission.CONTENT_READ,
    "announcements": Permission.CONTENT_READ,
    "ratings": Permission.CONTENT_READ,
    "media": Permission.CONTENT_READ,
    "seo-documents": Permission.SITES_READ,
    "jobs": Permission.JOBS_READ,
    "publications": Permission.JOBS_READ,
    "deployments": Permission.JOBS_READ,
    "audit-events": Permission.AUDIT_READ,
    "commands": Permission.JOBS_READ,
}

#: Куда какая команда подаётся. Путь и вид команды связаны явно, чтобы нельзя
#: было подать «выкладку» туда, где ждут «обновить полку».
COMMAND_ROUTES: dict[str, CommandKind] = {
    "jobs": CommandKind.INGESTION_RUN,
    "publications": CommandKind.RELEASE_PUBLISH,
    "rollbacks": CommandKind.ROLLBACK_RUN,
}

MAX_PER_PAGE = 200
DEFAULT_PER_PAGE = 25


@dataclass
class Page:
    """Страница выдачи. Курсор не выдумывается: он равен смещению."""

    items: list[dict[str, Any]]
    total: int
    page: int
    per_page: int

    def as_dict(self) -> dict[str, Any]:
        всего_страниц = max(1, -(-self.total // self.per_page))
        return {
            "items": self.items,
            "page": {
                "number": self.page,
                "size": self.per_page,
                "total_items": self.total,
                "total_pages": всего_страниц,
                "has_next": self.page < всего_страниц,
            },
        }


def paginate(items: list[dict[str, Any]], params: dict[str, Any]) -> Page:
    try:
        номер = max(1, int(params.get("page", 1)))
    except (TypeError, ValueError):
        номер = 1
    try:
        размер = int(params.get("per_page", DEFAULT_PER_PAGE))
    except (TypeError, ValueError):
        размер = DEFAULT_PER_PAGE
    размер = max(1, min(MAX_PER_PAGE, размер))
    начало = (номер - 1) * размер
    return Page(items[начало:начало + размер], len(items), номер, размер)


def apply_filter(items: list[dict[str, Any]], params: dict[str, Any]) -> list[dict[str, Any]]:
    """Фильтр по подстроке и по точному совпадению полей.

    `q` ищет по значениям верхнего уровня; `field=value` сверяет точно. Оба
    работают по уже собранному представлению, а не по хранилищу: API не должен
    уметь то, чего не умеет его же выдача.
    """
    итог = items
    строка = str(params.get("q") or "").strip().lower()
    if строка:
        итог = [
            i for i in итог
            if any(строка in str(v).lower() for v in i.values() if isinstance(v, (str, int)))
        ]
    for ключ, значение in params.items():
        if ключ in {"q", "page", "per_page", "sort", "order"}:
            continue
        итог = [i for i in итог if str(i.get(ключ, "")) == str(значение)]
    return итог


def apply_sort(items: list[dict[str, Any]], params: dict[str, Any]) -> list[dict[str, Any]]:
    поле = params.get("sort")
    if not поле:
        return items
    обратно = str(params.get("order", "asc")).lower() == "desc"
    return sorted(items, key=lambda i: (i.get(поле) is None, str(i.get(поле, ""))), reverse=обратно)


def correlation_id(headers: dict[str, str] | None, path: str) -> str:
    """Идентификатор запроса. Если его не прислали — считается от пути и времени."""
    headers = headers or {}
    для_связи = headers.get("X-Correlation-Id") or headers.get("x-correlation-id")
    if для_связи:
        return str(для_связи)[:64]
    return hashlib.sha256(f"{path}|{id(headers)}".encode()).hexdigest()[:16]


@dataclass
class ControlPlaneApi:
    """Единая точка входа CMS. Провайдера не знает и знать не должен."""

    read_api: Any
    commands: CommandLog
    audit: audit_mod.AuditLog
    principals: dict[str, Principal]
    collectors: dict[str, Callable[[], list[dict[str, Any]]]] = field(default_factory=dict)
    env: dict[str, str] | None = None

    # ------------------------------------------------------------------ вход
    def handle(
        self,
        method: str,
        path: str,
        *,
        principal_id: str | None = None,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> ApiResponse:
        if not api_enabled(self.env):
            return error(404, "not_found", "маршрут не найден")
        params = params or {}
        body = body or {}
        связь = correlation_id(headers, path)

        части = [p for p in path.strip("/").split("/") if p]
        if части[:2] != ["api", API_VERSION]:
            return self._with_correlation(error(404, "not_found", "маршрут не найден"), связь)
        остаток = части[2:]

        if остаток in (["health"], ["ready"]):
            return self._with_correlation(self._health(остаток[0]), связь)

        лицо = self.principals.get(principal_id or "")
        if лицо is None:
            # Неизвестное лицо получает 401, а не 403: разница между «кто ты» и
            # «тебе нельзя» важна для разбора инцидента.
            return self._with_correlation(
                error(401, "unauthenticated", "лицо не опознано"), связь
            )

        if not остаток:
            return self._with_correlation(error(404, "not_found", "маршрут не найден"), связь)

        ресурс = остаток[0]
        метод = method.upper()

        if метод == "GET":
            return self._with_correlation(self._read(ресурс, остаток[1:], лицо, params), связь)
        if метод == "POST":
            return self._with_correlation(
                self._command(ресурс, остаток[1:], лицо, body, связь), связь
            )
        return self._with_correlation(
            error(405, "method_not_allowed", f"метод {метод} не поддерживается"), связь
        )

    # ------------------------------------------------------------------ чтение
    def _read(
        self, ресурс: str, хвост: list[str], лицо: Principal, params: dict[str, Any]
    ) -> ApiResponse:
        право = READ_RESOURCES.get(ресурс)
        if право is None:
            return error(404, "not_found", "маршрут не найден")
        try:
            require(лицо, право, params.get("site_id"))
        except AccessDenied as отказ:
            return error(403, "forbidden", str(отказ))

        собиратель = self.collectors.get(ресурс)
        if собиратель is None:
            return error(501, "not_implemented", f"{ресурс}: источник не подключён")
        записи = собиратель()

        if хвост:
            искомый = хвост[0]
            for запись in записи:
                if str(запись.get("id", запись.get("site_id", ""))) == искомый:
                    return ApiResponse(200, запись)
            return error(404, "not_found", f"{ресурс}/{искомый} не найден")

        отобранные = apply_sort(apply_filter(записи, params), params)
        return ApiResponse(200, paginate(отобранные, params).as_dict())

    # ------------------------------------------------------------------ запись
    def _command(
        self,
        ресурс: str,
        хвост: list[str],
        лицо: Principal,
        body: dict[str, Any],
        связь: str,
    ) -> ApiResponse:
        вид_строкой = body.get("kind")
        вид = COMMAND_ROUTES.get(ресурс)
        if ресурс == "commands" and вид_строкой:
            try:
                вид = CommandKind(вид_строкой)
            except ValueError:
                return error(400, "unknown_command", f"вид команды {вид_строкой} неизвестен")
        if вид is None:
            return error(404, "not_found", "маршрут не найден")

        site_id = body.get("site_id")
        ключ = body.get("idempotency_key") or payload_digest(
            {"kind": вид.value, "site_id": site_id, "payload": body.get("payload") or {}}
        )
        try:
            команда, повтор = self.commands.submit(
                kind=вид,
                principal=лицо,
                site_id=site_id,
                payload=body.get("payload") or {},
                idempotency_key=ключ,
                reason=str(body.get("reason") or ""),
                expected_version=body.get("expected_version"),
                confirmed=bool(body.get("confirmed")),
            )
        except CommandRejected as отказ:
            # Отказ по праву и отказ по состоянию различаются кодом: первый —
            # про лицо, второй — про объект.
            код = 403 if "нет права" in str(отказ) else 409
            return error(код, "command_rejected", str(отказ))

        if not повтор:
            self.audit.record(
                audit_mod.event(
                    actor=лицо.principal_id,
                    action=f"command.submit:{вид.value}",
                    subject=команда.command_id,
                    reason=команда.reason,
                    site_ids=(site_id,) if site_id else (),
                    after={"state": команда.state.value, "kind": вид.value},
                    correlation_id=связь,
                )
            )
        return ApiResponse(
            200 if повтор else 202,
            {"command": команда.as_dict(), "repeated": повтор},
        )

    # ------------------------------------------------------------------ прочее
    def _health(self, вид: str) -> ApiResponse:
        готов = bool(self.principals) and bool(self.collectors)
        if вид == "ready" and not готов:
            return error(503, "not_ready", "источники не подключены")
        return ApiResponse(
            200,
            {
                "status": "ok" if готов else "degraded",
                "version": API_VERSION,
                "resources": sorted(self.collectors),
                "commands": len(self.commands),
                "audit_events": len(self.audit),
            },
        )

    @staticmethod
    def _with_correlation(ответ: ApiResponse, связь: str) -> ApiResponse:
        тело = ответ.body
        if isinstance(тело, dict):
            тело = dict(тело)
            тело.setdefault("correlation_id", связь)
            return ApiResponse(ответ.status, тело)
        return ответ


def json_dump(ответ: ApiResponse) -> str:
    return json.dumps(ответ.body, ensure_ascii=False, sort_keys=True)
