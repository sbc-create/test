"""SiteAdminContract v1: договор админки отдельного сайта.

Флот — это не пять админок, а одна реализация с пятью адаптерами. Договор
существует, чтобы это различие было проверяемым: семейство шаблона получает
перечень возможностей и областей прав, а не собственную копию логики. Пять
копий бизнес-логики расходятся на первом же исправлении, и расходятся молча.

Два правила, каждое написано на конкретный способ соврать.

**Перечень семейств берётся из схемы пакета.** Той самой, по которой пакет
потом проверяется. Свой список в коде означал бы, что адаптер находится для
семейства, которого схема не знает, — и обнаружится это при выкладке.

**Возможность без области права не объявляется.** «Админка умеет править
контент» без указания, каким правом это ограничено, — обещание, а не договор.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

VERSION = "site-admin/1.0.0"

СХЕМА_ПАКЕТА = "schemas/site-package.schema.json"

#: Корень репозитория относительно этого файла. Перечень семейств читается из
#: схемы, а схема лежит в поставке рядом с кодом.
_КОРЕНЬ = Path(__file__).resolve().parents[2]


class ContractError(Exception):
    """Семейства нет в договоре или договор противоречив."""


def _семейства() -> tuple[str, ...]:
    путь = _КОРЕНЬ / СХЕМА_ПАКЕТА
    try:
        схема = json.loads(путь.read_text(encoding="utf-8"))
    except (OSError, ValueError) as ошибка:
        raise ContractError(f"схема пакета не читается: {ошибка}") from ошибка
    try:
        перечень = схема["properties"]["tenant"]["properties"]["theme"]["enum"]
    except (KeyError, TypeError) as ошибка:
        raise ContractError("в схеме пакета нет перечня tenant.theme") from ошибка
    return tuple(str(з) for з in перечень)


TEMPLATE_FAMILIES: tuple[str, ...] = _семейства()

#: Что обязана уметь админка сайта. Область права указана у каждой возможности:
#: без неё «умеет» ничем не ограничено.
CAPABILITIES: dict[str, dict[str, str]] = {
    "auth": {
        "scope": "read",
        "summary": "вход, выход, отзыв сессий и восстановление доступа",
    },
    "users": {
        "scope": "operators:write",
        "summary": "приглашения, роли и блокировка в пределах своего сайта",
    },
    "content": {
        "scope": "review:write",
        "summary": "карточки, категории, жанры, страны и редакционный поток",
    },
    "layout": {
        "scope": "config:write",
        "summary": "блоки главной, меню, навигация и оформление",
    },
    "seo": {
        "scope": "config:write",
        "summary": "поля SEO, канонический адрес, индексация, карта сайта, предпросмотр",
    },
    "public-registration": {
        "scope": "config:write",
        "summary": "публичная регистрация и её признак включения на сайте",
    },
    "settings": {
        "scope": "config:write",
        "summary": "домен, оформление и ссылки на интеграции",
    },
    "publish": {
        "scope": "jobs:write",
        "summary": "предпросмотр, публикация, канарейка и точечный откат",
    },
    "jobs": {
        "scope": "jobs:write",
        "summary": "задания, исполнитель, кэш, здоровье содержимого и причины недоступного видео",
    },
    "audit": {
        "scope": "audit:read",
        "summary": "журнал действий, происшествия, метрики и диагностика",
    },
}

#: Возможности, которых у семейства может не быть. Остальные обязательны: их
#: отсутствие означает не «адаптер проще», а «админка неполна».
НЕОБЯЗАТЕЛЬНЫЕ = frozenset({"public-registration"})


def capabilities_for(family: str) -> tuple[str, ...]:
    """Возможности семейства. Пока одинаковы у всех: логика общая по замыслу."""
    if family not in TEMPLATE_FAMILIES:
        raise ContractError(f"семейства {family!r} нет в схеме пакета")
    return tuple(sorted(CAPABILITIES))


def adapter_for(family: str) -> dict[str, Any]:
    """Описание адаптера семейства.

    Адаптер описывает различия отрисовки и ничего не знает о бизнес-логике:
    именно поэтому у всех пяти он одинаков по перечню возможностей и отличается
    только семейством. Первый же адаптер с собственной логикой сделает договор
    украшением.
    """
    возможности = capabilities_for(family)
    return {
        "family": family,
        "contractVersion": VERSION,
        "capabilities": list(возможности),
        "scopes": sorted({CAPABILITIES[в]["scope"] for в in возможности}),
        "optional": sorted(НЕОБЯЗАТЕЛЬНЫЕ),
    }


def contract() -> dict[str, Any]:
    """Договор целиком — для выдачи наружу и для сверки адаптеров."""
    return {
        "contractVersion": VERSION,
        "templateFamilies": list(TEMPLATE_FAMILIES),
        "capabilities": {и: dict(о) for и, о in sorted(CAPABILITIES.items())},
        "optional": sorted(НЕОБЯЗАТЕЛЬНЫЕ),
        "adapters": [adapter_for(с) for с in TEMPLATE_FAMILIES],
    }
