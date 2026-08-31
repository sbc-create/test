"""OpenAPI v1 Control Plane, порождаемый из таблиц маршрутизатора.

Спецификация, написанная отдельно от кода, расходится с ним на второй неделе.
Здесь она собирается из тех же `READ_RESOURCES` и `COMMAND_ROUTES`, по которым
работает `handle`: маршрут, которого нет в таблице, не попадёт и в документ, а
добавленный попадёт сам.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from factory.site_engine.access import Permission, Role, ROLE_PERMISSIONS
from factory.site_engine.api.control_plane import (
    API_VERSION,
    COMMAND_ROUTES,
    DEFAULT_PER_PAGE,
    MAX_PER_PAGE,
    READ_RESOURCES,
)
from factory.site_engine.commands import CommandKind, CommandState, REQUIRED_PERMISSION

ОПИСАНИЯ: dict[str, str] = {
    "sites": "Сайты фабрики",
    "site-profiles": "Профили сайтов",
    "content": "Нормализованный контент",
    "content-events": "События изменения контента",
    "sources": "Источники данных и адаптеры",
    "shelves": "Полки витрин",
    "schedules": "Расписание выхода",
    "announcements": "Анонсы",
    "ratings": "Оценки",
    "media": "Медиа и кэш изображений",
    "seo-documents": "SEO-документы",
    "jobs": "Фоновые задания",
    "publications": "Публикации релизов",
    "deployments": "Выкладки",
    "audit-events": "Журнал аудита",
    "commands": "Команды",
}


def _общие_параметры() -> list[dict[str, Any]]:
    return [
        {"name": "page", "in": "query", "required": False,
         "schema": {"type": "integer", "minimum": 1, "default": 1},
         "description": "Номер страницы"},
        {"name": "per_page", "in": "query", "required": False,
         "schema": {"type": "integer", "minimum": 1, "maximum": MAX_PER_PAGE,
                    "default": DEFAULT_PER_PAGE},
         "description": "Размер страницы"},
        {"name": "q", "in": "query", "required": False, "schema": {"type": "string"},
         "description": "Поиск по подстроке в полях верхнего уровня"},
        {"name": "sort", "in": "query", "required": False, "schema": {"type": "string"},
         "description": "Поле сортировки"},
        {"name": "order", "in": "query", "required": False,
         "schema": {"type": "string", "enum": ["asc", "desc"], "default": "asc"}},
        {"name": "site_id", "in": "query", "required": False, "schema": {"type": "string"},
         "description": "Ограничение области; проверяется правами"},
        {"name": "X-Correlation-Id", "in": "header", "required": False,
         "schema": {"type": "string"}, "description": "Идентификатор для связи записей"},
        {"name": "X-Principal-Id", "in": "header", "required": True,
         "schema": {"type": "string"}, "description": "Действующее лицо"},
    ]


def _ошибки() -> dict[str, Any]:
    return {
        "401": {"description": "Лицо не опознано",
                "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}}},
        "403": {"description": "Нет права или сайт вне области",
                "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}}},
        "404": {"description": "Маршрут или объект не найден",
                "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}}},
        "409": {"description": "Состояние или версия не позволяют выполнить",
                "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}}},
        "501": {"description": "Источник ресурса не подключён",
                "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}}},
    }


def spec() -> dict[str, Any]:
    пути: dict[str, Any] = {
        f"/api/{API_VERSION}/health": {
            "get": {"summary": "Состояние API", "security": [],
                    "responses": {"200": {"description": "Работает"}}}
        },
        f"/api/{API_VERSION}/ready": {
            "get": {"summary": "Готовность API", "security": [],
                    "responses": {"200": {"description": "Готов"},
                                  "503": {"description": "Источники не подключены"}}}
        },
    }

    for ресурс, право in sorted(READ_RESOURCES.items()):
        пути[f"/api/{API_VERSION}/{ресурс}"] = {
            "get": {
                "summary": ОПИСАНИЯ.get(ресурс, ресурс),
                "description": f"Требуется право `{право.value}`.",
                "parameters": _общие_параметры(),
                "responses": {
                    "200": {"description": "Страница выдачи",
                            "content": {"application/json": {
                                "schema": {"$ref": "#/components/schemas/Page"}}}},
                    **_ошибки(),
                },
            }
        }
        пути[f"/api/{API_VERSION}/{ресурс}/{{id}}"] = {
            "get": {
                "summary": f"{ОПИСАНИЯ.get(ресурс, ресурс)}: один объект",
                "description": f"Требуется право `{право.value}`.",
                "parameters": [
                    {"name": "id", "in": "path", "required": True, "schema": {"type": "string"}},
                    *_общие_параметры(),
                ],
                "responses": {"200": {"description": "Объект"}, **_ошибки()},
            }
        }

    for ресурс, вид in sorted(COMMAND_ROUTES.items(), key=lambda kv: kv[0]):
        путь = f"/api/{API_VERSION}/{ресурс}"
        запись = пути.setdefault(путь, {})
        запись["post"] = {
            "summary": f"Команда {вид.value}",
            "description": (
                f"Требуется право `{REQUIRED_PERMISSION[вид].value}`. "
                "Повторная подача с тем же `idempotency_key` не выполняет работу дважды."
            ),
            "requestBody": {"required": True, "content": {"application/json": {
                "schema": {"$ref": "#/components/schemas/CommandRequest"}}}},
            "responses": {
                "202": {"description": "Команда принята",
                        "content": {"application/json": {
                            "schema": {"$ref": "#/components/schemas/CommandResponse"}}}},
                "200": {"description": "Повтор: команда уже была принята"},
                **_ошибки(),
            },
        }

    пути[f"/api/{API_VERSION}/commands"]["post"] = {
        "summary": "Подать любую команду по имени вида",
        "requestBody": {"required": True, "content": {"application/json": {
            "schema": {"$ref": "#/components/schemas/CommandRequest"}}}},
        "responses": {"202": {"description": "Принята"}, "200": {"description": "Повтор"},
                      **_ошибки()},
    }

    return {
        "openapi": "3.0.3",
        "info": {
            "title": "Site Factory Control Plane",
            "version": "1.0.0",
            "description": (
                "Единая точка входа CMS. Обращений к API поставщика здесь нет и быть "
                "не может: движки отдают уже нормализованные данные."
            ),
        },
        "servers": [{"url": "http://127.0.0.1:8710", "description": "Изолированный canary"}],
        "security": [{"PrincipalHeader": []}],
        "components": {
            "securitySchemes": {
                "PrincipalHeader": {"type": "apiKey", "in": "header", "name": "X-Principal-Id"}
            },
            "schemas": {
                "Error": {
                    "type": "object",
                    "required": ["error"],
                    "properties": {"error": {
                        "type": "object",
                        "required": ["code", "message"],
                        "properties": {"code": {"type": "string"}, "message": {"type": "string"}},
                    }},
                },
                "Page": {
                    "type": "object",
                    "required": ["items", "page"],
                    "properties": {
                        "items": {"type": "array", "items": {"type": "object"}},
                        "page": {
                            "type": "object",
                            "properties": {
                                "number": {"type": "integer"},
                                "size": {"type": "integer"},
                                "total_items": {"type": "integer"},
                                "total_pages": {"type": "integer"},
                                "has_next": {"type": "boolean"},
                            },
                        },
                        "correlation_id": {"type": "string"},
                    },
                },
                "CommandRequest": {
                    "type": "object",
                    "properties": {
                        "kind": {"type": "string", "enum": [k.value for k in CommandKind]},
                        "site_id": {"type": "string", "nullable": True},
                        "payload": {"type": "object"},
                        "idempotency_key": {"type": "string"},
                        "expected_version": {"type": "integer", "nullable": True},
                        "reason": {"type": "string"},
                        "confirmed": {"type": "boolean",
                                      "description": "Обязательно для опасных команд"},
                    },
                },
                "CommandResponse": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "object",
                            "properties": {
                                "command_id": {"type": "string"},
                                "kind": {"type": "string"},
                                "state": {"type": "string",
                                          "enum": [s.value for s in CommandState]},
                                "actor": {"type": "string"},
                                "site_id": {"type": "string", "nullable": True},
                            },
                        },
                        "repeated": {"type": "boolean"},
                    },
                },
                "Role": {"type": "string", "enum": [r.value for r in Role]},
                "Permission": {"type": "string", "enum": [p.value for p in Permission]},
            },
        },
        "x-roles": {
            role.value: sorted(p.value for p in perms)
            for role, perms in ROLE_PERMISSIONS.items()
        },
        "paths": пути,
    }


def write(path: Path | str = "schemas/site-engine/control-plane-v1.json") -> Path:
    цель = Path(path)
    цель.parent.mkdir(parents=True, exist_ok=True)
    цель.write_text(json.dumps(spec(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return цель
