"""OpenAPI-описание Site Engine API v1.

Описание порождается из кода, а не пишется рядом с ним: файл, который правят
отдельно от маршрутов, расходится с ними за одну итерацию. Тест сверяет,
что описанные маршруты и есть отвечающие.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from factory.site_engine.api.app import API_VERSION, MAX_LIMIT
from factory.site_engine.api.control import (
    ALLOWED_ENVIRONMENTS,
    ALLOWED_JOB_ACTIONS,
    KNOWN_SCOPES,
    RATE_LIMIT_PER_MINUTE,
    REFUSED_SETTINGS,
    SAFE_SETTINGS,
)

ОШИБКА = {
    "type": "object",
    "required": ["error"],
    "properties": {
        "error": {
            "type": "object",
            "required": ["code", "message"],
            "properties": {
                "code": {"type": "string"},
                "message": {"type": "string"},
            },
        }
    },
}

КРАТКО = {
    "type": "object",
    "required": ["canonical_id", "name", "available_episodes", "watchable"],
    "properties": {
        "canonical_id": {"type": "string"},
        "name": {"type": "string"},
        "year": {"type": ["integer", "null"]},
        "kind": {"type": ["string", "null"]},
        # `null` — «неизвестно, сколько серий», а не «серий нет».
        "available_episodes": {"type": ["integer", "null"]},
        "watchable": {"type": "boolean"},
        "rating": {"type": ["object", "null"]},
    },
}

ПУТИ: dict[str, dict[str, Any]] = {
    "/api/v1/health": {"summary": "Живость и состав", "returns": "object"},
    "/api/v1/sites": {"summary": "Список сайтов", "returns": "list"},
    "/api/v1/sites/{siteId}": {"summary": "Сайт", "returns": "object"},
    "/api/v1/sites/{siteId}/config": {"summary": "Конфигурация без секретов", "returns": "object"},
    "/api/v1/sites/{siteId}/shelves": {"summary": "Полки", "returns": "object"},
    "/api/v1/sites/{siteId}/titles": {"summary": "Каталог со страницами", "returns": "page"},
    "/api/v1/sites/{siteId}/titles/{titleId}": {"summary": "Тайтл", "returns": "object"},
    "/api/v1/sites/{siteId}/titles/{titleId}/episodes": {"summary": "Сезоны и счётчики",
                                                          "returns": "object"},
    "/api/v1/sites/{siteId}/titles/{titleId}/ratings": {"summary": "Оценки", "returns": "object"},
    "/api/v1/sites/{siteId}/coverage": {"summary": "Полнота каталога", "returns": "object"},
    "/api/v1/ingestion/status": {"summary": "Состояние обхода", "returns": "object"},
}


# Перечни берутся импортом из control.py, а не переписываются здесь. Список
# допустимых действий, продублированный в описании, расходится с проверяющим
# кодом на первой же правке — и расходится молча, потому что оба выглядят верно.
ЗАПИСЬ: dict[str, dict[str, Any]] = {
    "/api/v1/sites/{siteId}/jobs": {
        "method": "post",
        "summary": "Поставить задание по сайту",
        "scope": "jobs:write",
        "idempotent": True,
        "body": {
            "type": "object",
            "required": ["action"],
            "properties": {
                "action": {"type": "string", "enum": sorted(ALLOWED_JOB_ACTIONS)},
                "environment": {"type": "string", "enum": sorted(ALLOWED_ENVIRONMENTS),
                                "default": "staging"},
                "dryRun": {"type": "boolean", "default": False},
            },
        },
        "success": ("202", "задание поставлено в очередь"),
        "errors": {"400": "негодное действие или среда", "409": "сайт занят или задание уже есть"},
    },
    "/api/v1/jobs/{jobId}": {
        "method": "get",
        "summary": "Состояние задания",
        "scope": "read",
        "idempotent": False,
        "body": None,
        "success": ("200", "стадия задания и число попыток"),
        "errors": {"400": "негодный идентификатор", "404": "задания нет"},
    },
    "/api/v1/sites/{siteId}/settings": {
        "method": "patch",
        "summary": "Изменить обратимые настройки ядра",
        "scope": "config:write",
        "idempotent": True,
        "body": {
            "type": "object",
            "required": ["changes"],
            "properties": {
                "changes": {
                    "type": "object",
                    "description": (
                        "Изменяемые настройки: " + ", ".join(sorted(SAFE_SETTINGS))
                        + ". Отклоняются намеренно: "
                        + "; ".join(f"{k} — {v}" for k, v in sorted(REFUSED_SETTINGS.items()))
                    ),
                    "properties": {
                        "keep_releases": {"type": "integer", "minimum": SAFE_SETTINGS["keep_releases"]["min"],
                                          "maximum": SAFE_SETTINGS["keep_releases"]["max"]},
                        "cache_policy": {"type": "object", "additionalProperties": {"type": "integer"}},
                        "feature_flags": {"type": "object", "additionalProperties": {"type": "boolean"}},
                    },
                },
                "expectedVersion": {
                    "type": "string",
                    "description": "Версия из currentVersion. При расхождении — 409, а не тихая перезапись.",
                },
                "dryRun": {"type": "boolean", "default": False},
            },
        },
        "success": ("200", "применено, либо diff при dryRun"),
        "errors": {"409": "конфигурация изменилась с момента чтения",
                   "422": "настройка вне списка, вне диапазона или отклонена намеренно"},
    },
    "/api/v1/sites/{siteId}/cache/invalidate": {
        "method": "post",
        "summary": "Точечно сбросить кэш",
        "scope": "cache:write",
        "idempotent": True,
        "body": {
            "type": "object",
            "required": ["scope"],
            "properties": {
                "scope": {"type": "string", "enum": ["catalog", "homepage", "shelves", "title"]},
                "keys": {"type": "array", "items": {"type": "string"}, "maxItems": 100,
                         "description": "Для scope=title обязателен непустой список."},
                "dryRun": {"type": "boolean", "default": False},
            },
        },
        "success": ("202", "инвалидация поставлена в очередь"),
        "errors": {"400": "негодная область или пустой keys при scope=title"},
    },
    "/api/v1/metrics": {
        "method": "get",
        "summary": "Метрики процесса в текстовом формате Prometheus",
        "scope": "read",
        "idempotent": False,
        "body": None,
        "success": ("200", "текстовый формат Prometheus; счётчики обнуляются при перезапуске"),
        "errors": {"404": "маршрут выключен"},
    },
    "/api/v1/audit": {
        "method": "get",
        "summary": "Журнал операций, включая отказы",
        "scope": "audit:read",
        "idempotent": False,
        "body": None,
        "success": ("200", "записи журнала"),
        "errors": {"400": "негодный limit"},
    },
}


def spec() -> dict[str, Any]:
    paths: dict[str, Any] = {}
    for путь, описание in ПУТИ.items():
        параметры = []
        if "{siteId}" in путь:
            параметры.append({"name": "siteId", "in": "path", "required": True,
                              "schema": {"type": "string"}})
        if "{titleId}" in путь:
            параметры.append({"name": "titleId", "in": "path", "required": True,
                              "schema": {"type": "string"}})
        if описание["returns"] == "page":
            параметры += [
                {"name": "offset", "in": "query", "required": False,
                 "schema": {"type": "integer", "minimum": 0}},
                {"name": "limit", "in": "query", "required": False,
                 "schema": {"type": "integer", "minimum": 1, "maximum": MAX_LIMIT}},
            ]
        ответы = {
            "200": {"description": "успех"},
            "404": {"description": "нет такого маршрута, сайта или тайтла",
                    "content": {"application/json": {"schema": ОШИБКА}}},
        }
        if описание["returns"] == "page":
            ответы["400"] = {"description": "негодные параметры страницы",
                             "content": {"application/json": {"schema": ОШИБКА}}}
        paths[путь] = {"get": {"summary": описание["summary"], "parameters": параметры,
                               "responses": ответы}}
    for путь, описание in ЗАПИСЬ.items():
        параметры = []
        if "{siteId}" in путь:
            параметры.append({"name": "siteId", "in": "path", "required": True,
                              "schema": {"type": "string"}})
        if "{jobId}" in путь:
            параметры.append({"name": "jobId", "in": "path", "required": True,
                              "schema": {"type": "string"}})
        параметры.append({
            "name": "X-Correlation-Id", "in": "header", "required": False,
            "schema": {"type": "string"},
            "description": "Возвращается во всех ответах, включая отказы.",
        })
        if описание["idempotent"]:
            параметры.append({
                "name": "Idempotency-Key", "in": "header", "required": False,
                "schema": {"type": "string", "maxLength": 128},
                "description": "Повтор возвращает прежний ответ; тот же ключ с другим телом — 409.",
            })
        код, текст = описание["success"]
        ответы = {код: {"description": текст}}
        for код_ошибки, текст_ошибки in описание["errors"].items():
            ответы[код_ошибки] = {"description": текст_ошибки,
                                  "content": {"application/json": {"schema": ОШИБКА}}}
        ответы["401"] = {"description": "нет или не распознан токен",
                         "content": {"application/json": {"schema": ОШИБКА}}}
        ответы["403"] = {"description": f"у токена нет области {описание['scope']}",
                         "content": {"application/json": {"schema": ОШИБКА}}}
        ответы["429"] = {"description": f"не более {RATE_LIMIT_PER_MINUTE} запросов в минуту",
                         "content": {"application/json": {"schema": ОШИБКА}}}
        операция: dict[str, Any] = {
            "summary": описание["summary"],
            "parameters": параметры,
            "responses": ответы,
            "security": [{"bearerAuth": []}],
            "x-required-scope": описание["scope"],
        }
        if описание["body"] is not None:
            операция["requestBody"] = {
                "required": True,
                "content": {"application/json": {"schema": описание["body"]}},
            }
        paths.setdefault(путь, {})[описание["method"]] = операция
    return {
        "openapi": "3.1.0",
        "info": {
            "title": "Site Engine API",
            "version": API_VERSION,
            "description": (
                "Чтение и ограниченная запись. Слои включаются раздельно: "
                "SITE_ENGINE_API_ENABLED для чтения, SITE_ENGINE_CONTROL_WRITES "
                "для записи. Открытое чтение — это утечка, открытая запись — это "
                "чужой контроль над витриной; разные риски заслуживают разных "
                "выключателей. Права выдаются по областям (" + ", ".join(sorted(KNOWN_SCOPES))
                + "); токен без нужной области получает 403, а не тихий отказ."
            ),
        },
        "paths": paths,
        "components": {
            "schemas": {"Error": ОШИБКА, "TitleBrief": КРАТКО},
            "securitySchemes": {
                "bearerAuth": {"type": "http", "scheme": "bearer",
                               "description": "Токен из SITE_ENGINE_CONTROL_TOKENS."}
            },
        },
    }


def write(path: Path | str = "schemas/site-engine/openapi-v1.json") -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(spec(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target
