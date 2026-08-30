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
    return {
        "openapi": "3.1.0",
        "info": {
            "title": "Site Engine API",
            "version": API_VERSION,
            "description": (
                "Только чтение. Выключен по умолчанию и недоступен в production: "
                "включение — осознанное действие, а не поведение по умолчанию."
            ),
        },
        "paths": paths,
        "components": {"schemas": {"Error": ОШИБКА, "TitleBrief": КРАТКО}},
    }


def write(path: Path | str = "schemas/site-engine/openapi-v1.json") -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(spec(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target
