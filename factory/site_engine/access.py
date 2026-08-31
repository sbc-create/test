"""Права доступа: кто что может.

Разрешения именуются по действию, а не по разделу интерфейса. Раздел можно
переставить, переименовать или разбить надвое; право «опубликовать в production»
от этого не меняется.

Отдельно от ролей стоит область: право, выданное на один сайт, не должно
молчаливо распространяться на остальные пять.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from factory.site_engine.contracts import ContractError


class Role(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    OPERATOR = "operator"
    EDITOR = "editor"
    SEO = "seo"
    VIEWER = "viewer"


#: Право = «действие:объект». Читается вслух и потому реже выдаётся по ошибке.
class Permission(str, Enum):
    SITES_READ = "sites:read"
    CONTENT_READ = "content:read"
    AUDIT_READ = "audit:read"
    JOBS_READ = "jobs:read"

    PROFILE_WRITE = "profile:write"
    SHELF_WRITE = "shelf:write"
    EDITORIAL_WRITE = "editorial:write"
    EDITORIAL_PUBLISH = "editorial:publish"
    SEO_WRITE = "seo:write"

    INGESTION_RUN = "ingestion:run"
    TITLE_REFRESH = "title:refresh"
    CACHE_INVALIDATE = "cache:invalidate"

    PUBLISH_CANARY = "publish:canary"
    PUBLISH_PRODUCTION = "publish:production"
    ROLLBACK_RUN = "rollback:run"

    SITE_CREATE = "site:create"
    USERS_MANAGE = "users:manage"


ЧТЕНИЕ = frozenset({
    Permission.SITES_READ, Permission.CONTENT_READ,
    Permission.JOBS_READ, Permission.AUDIT_READ,
})

ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.VIEWER: ЧТЕНИЕ,
    # Редактор правит тексты и полки, но не публикует в production и не
    # запускает выкладку: это разные решения с разной ценой ошибки.
    Role.EDITOR: ЧТЕНИЕ | {
        Permission.EDITORIAL_WRITE, Permission.EDITORIAL_PUBLISH,
        Permission.SHELF_WRITE,
    },
    # SEO правит свою область и ничего сверх неё. Прямого доступа к каталогу и
    # выкладке у него нет — граница между SEO и Site Engine держится правами,
    # а не договорённостью.
    Role.SEO: ЧТЕНИЕ | {Permission.SEO_WRITE},
    # Оператор запускает работу и откатывает, но не меняет содержание витрин.
    Role.OPERATOR: ЧТЕНИЕ | {
        Permission.INGESTION_RUN, Permission.TITLE_REFRESH,
        Permission.CACHE_INVALIDATE, Permission.PUBLISH_CANARY,
        Permission.ROLLBACK_RUN,
    },
    Role.ADMIN: ЧТЕНИЕ | {
        Permission.PROFILE_WRITE, Permission.SHELF_WRITE,
        Permission.EDITORIAL_WRITE, Permission.EDITORIAL_PUBLISH,
        Permission.SEO_WRITE, Permission.INGESTION_RUN,
        Permission.TITLE_REFRESH, Permission.CACHE_INVALIDATE,
        Permission.PUBLISH_CANARY, Permission.ROLLBACK_RUN,
        Permission.SITE_CREATE,
    },
    # Публикация в production принадлежит владельцу и никому больше.
    Role.OWNER: frozenset(Permission),
}


@dataclass(frozen=True)
class Principal:
    """Кто действует.

    `sites` пусто — значит все сайты. Непустое множество ограничивает область:
    администратор одного портала не управляет соседним.
    """

    principal_id: str
    roles: tuple[Role, ...]
    sites: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if not self.principal_id:
            raise ContractError("действующее лицо без идентификатора")
        if not self.roles:
            raise ContractError(f"{self.principal_id}: роли не заданы")

    @property
    def permissions(self) -> frozenset[Permission]:
        итог: set[Permission] = set()
        for role in self.roles:
            итог |= ROLE_PERMISSIONS.get(role, frozenset())
        return frozenset(итог)

    def covers(self, site_id: str | None) -> bool:
        return not self.sites or site_id is None or site_id in self.sites


class AccessDenied(ContractError):
    """Отказ в праве. Сообщение не раскрывает, что именно существует."""


def allows(principal: Principal, permission: Permission, site_id: str | None = None) -> bool:
    return permission in principal.permissions and principal.covers(site_id)


def require(principal: Principal, permission: Permission, site_id: str | None = None) -> None:
    """Проверка права. Отказ — исключение, а не значение, которое легко забыть."""
    if not allows(principal, permission, site_id):
        область = f" для {site_id}" if site_id else ""
        raise AccessDenied(f"нет права {permission.value}{область}")


def principal_from(raw: dict) -> Principal:
    """Разбор действующего лица из внешнего представления."""
    роли = tuple(Role(r) for r in (raw.get("roles") or ()))
    сайты = frozenset(raw.get("sites") or ())
    return Principal(principal_id=str(raw.get("id") or ""), roles=роли, sites=сайты)
