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
    REFUSED_SETTINGS,
    SAFE_SETTINGS,
)
from factory.site_engine.api.ratelimit import DEFAULT_LIMITS

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
    "/api/v1/sites/{siteId}/titles/{titleId}/episodes": {
        "summary": "Сезоны и счётчики",
        "returns": "object",
    },
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
                "environment": {
                    "type": "string",
                    "enum": sorted(ALLOWED_ENVIRONMENTS),
                    "default": "staging",
                },
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
                        "Изменяемые настройки: "
                        + ", ".join(sorted(SAFE_SETTINGS))
                        + ". Отклоняются намеренно: "
                        + "; ".join(f"{k} — {v}" for k, v in sorted(REFUSED_SETTINGS.items()))
                    ),
                    "properties": {
                        "keep_releases": {
                            "type": "integer",
                            "minimum": SAFE_SETTINGS["keep_releases"]["min"],
                            "maximum": SAFE_SETTINGS["keep_releases"]["max"],
                        },
                        "cache_policy": {
                            "type": "object",
                            "additionalProperties": {"type": "integer"},
                        },
                        "feature_flags": {
                            "type": "object",
                            "additionalProperties": {"type": "boolean"},
                        },
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
        "errors": {
            "409": "конфигурация изменилась с момента чтения",
            "422": "настройка вне списка, вне диапазона или отклонена намеренно",
        },
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
                "keys": {
                    "type": "array",
                    "items": {"type": "string"},
                    "maxItems": 100,
                    "description": "Для scope=title обязателен непустой список.",
                },
                "dryRun": {"type": "boolean", "default": False},
            },
        },
        "success": ("202", "инвалидация поставлена в очередь"),
        "errors": {"400": "негодная область или пустой keys при scope=title"},
    },
    "/api/v1/content-health": {
        "method": "get",
        "summary": "Покрытие воспроизведения по массиву и причины его отсутствия",
        "scope": "read",
        "idempotent": False,
        "body": None,
        "success": ("200", "покрытие, разбивка по причинам, типам, агрегаторам и месяцам"),
        "errors": {"404": "маршрут выключен"},
    },
    "/api/v1/content-health/{siteId}": {
        "method": "get",
        "summary": "То же по одной витрине плюс проблемные карточки со стадией и способом устранения",
        "scope": "read",
        "idempotent": False,
        "body": None,
        "success": ("200", "сводка витрины и список карточек без воспроизведения"),
        "errors": {"400": "негодный идентификатор витрины или limit"},
    },
    "/api/v1/reasons": {
        "method": "get",
        "summary": "Справочник кодов причин: звено, повторяемость, сообщения, устранение",
        "scope": "read",
        "idempotent": False,
        "body": None,
        "success": ("200", "версионированный справочник"),
        "errors": {"404": "маршрут выключен"},
    },
    "/api/v1/playback-policy": {
        "method": "get",
        "summary": "Действующий перечень playback identifier, основа контракта и флаги",
        "scope": "read",
        "idempotent": False,
        "body": None,
        "success": ("200", "перечень, основа, версия политики и состояние флагов"),
        "errors": {"409": "настройка противоречит контракту поставщика"},
    },
    "/api/v1/jobs": {
        "method": "get",
        "summary": "Задания: очередь и результаты; принятое отличается от выполненного",
        "scope": "read",
        "idempotent": False,
        "body": {
            "type": "object",
            "properties": {
                "siteId": {"type": "string"},
                "state": {"type": "string"},
                "offset": {"type": "integer"},
                "limit": {"type": "integer"},
            },
        },
        "success": ("200", "счётчики очереди и список заданий с состояниями"),
        "errors": {"400": "негодный предел"},
    },
    "/api/v1/sites-status": {
        "method": "get",
        "summary": "Состояние всех витрин: контракты, флаги, свежесть, здоровье",
        "scope": "read",
        "idempotent": False,
        "body": None,
        "success": ("200", "список витрин с состоянием"),
        "errors": {},
    },
    "/api/v1/site-status/{siteId}": {
        "method": "get",
        "summary": "Состояние витрины; здоровье считается по содержимому каталога",
        "scope": "read",
        "idempotent": False,
        "body": None,
        "success": ("200", "профиль, контракты, свежесть и здоровье"),
        "errors": {"404": "профиля витрины нет"},
    },
    "/api/v1/overview": {
        "method": "get",
        "summary": "Сводка по массиву: витрины, свежесть, покрытие, очередь, тревоги",
        "scope": "read",
        "idempotent": False,
        "body": None,
        "success": ("200", "показатели и тревоги, выведенные из порогов"),
        "errors": {},
    },
    "/api/v1/content": {
        "method": "get",
        "summary": "Каталог витрины: поиск, отбор и постраничная выдача на сервере",
        "scope": "read",
        "idempotent": False,
        "body": {
            "type": "object",
            "required": ["siteId"],
            "properties": {
                "siteId": {"type": "string"},
                "q": {"type": "string"},
                "kind": {"type": "string"},
                "reason": {"type": "string"},
                "sort": {"type": "string", "enum": ["externalId", "title", "year"]},
                "desc": {"type": "boolean"},
                "offset": {"type": "integer"},
                "limit": {"type": "integer"},
            },
        },
        "success": ("200", "страница каталога со счётчиками по видам и причинам"),
        "errors": {"400": "негодная витрина, сортировка или предел"},
    },
    "/api/v1/content/{siteId}/{externalId}": {
        "method": "get",
        "summary": "Карточка: идентификаторы, происхождение, состояния, история",
        "scope": "read",
        "idempotent": False,
        "body": None,
        "success": ("200", "полная карточка записи"),
        "errors": {"404": "записи нет в каталоге витрины"},
    },
    "/api/v1/review-queue": {
        "method": "get",
        "summary": "Очередь разбора спорных записей: оба утверждения и доказательства",
        "scope": "read",
        "idempotent": False,
        "body": None,
        "success": ("200", "страница очереди со счётчиками по состояниям"),
        "errors": {"400": "негодный limit или offset"},
    },
    "/api/v1/review-queue/{itemId}": {
        "method": "get",
        "summary": "Одна спорная запись целиком: утверждения, источники, история",
        "scope": "read",
        "idempotent": False,
        "body": None,
        "success": ("200", "запись очереди"),
        "errors": {"400": "негодный идентификатор", "404": "записи нет"},
    },
    "/api/v1/review-queue/{itemId}/decide": {
        "method": "post",
        "summary": "Решение редактора по спорной записи",
        "scope": "review:write",
        "idempotent": True,
        "body": {
            "type": "object",
            "properties": {
                "value": {
                    "type": "string",
                    "description": "одно из утверждений записи; третье значение запрещено",
                },
                "expectedVersion": {"type": "integer"},
                "note": {"type": "string"},
                "dismiss": {"type": "boolean"},
            },
        },
        "success": ("200", "запись с записанным решением"),
        "errors": {
            "400": "значение вне утверждений записи",
            "409": "запись изменилась: конфликт версии",
        },
    },
    "/api/v1/review-queue/{itemId}/preview": {
        "method": "get",
        "summary": "Сверка «было/стало» перед публикацией решения",
        "scope": "read",
        "idempotent": False,
        "body": None,
        "success": ("200", "прежний и новый вид, признак публикации"),
        "errors": {"404": "записи нет"},
    },
    "/api/v1/review-queue/{itemId}/approve": {
        "method": "post",
        "summary": "Утверждение решения вторым человеком",
        "scope": "review:write",
        "idempotent": True,
        "body": {
            "type": "object",
            "properties": {"expectedVersion": {"type": "integer"}, "note": {"type": "string"}},
        },
        "success": ("200", "запись в состоянии APPROVED"),
        "errors": {"409": "утверждение собственного решения или конфликт версии"},
    },
    "/api/v1/review-queue/{itemId}/publish": {
        "method": "post",
        "summary": "Применение решения к витрине через наложение",
        "scope": "review:write",
        "idempotent": True,
        "body": {"type": "object", "properties": {"expectedVersion": {"type": "integer"}}},
        "success": ("200", "запись в состоянии PUBLISHED"),
        "errors": {"409": "решение не утверждено или конфликт версии"},
    },
    "/api/v1/review-queue/{itemId}/unpublish": {
        "method": "post",
        "summary": "Точечный откат: наложение снимается, решение остаётся",
        "scope": "review:write",
        "idempotent": True,
        "body": {"type": "object", "properties": {"note": {"type": "string"}}},
        "success": ("200", "запись в состоянии APPROVED"),
        "errors": {"409": "откатывать нечего"},
    },
    "/api/v1/review-queue/{itemId}/claim": {
        "method": "post",
        "summary": "Взять спорную запись в работу",
        "scope": "review:write",
        "idempotent": False,
        "body": None,
        "success": ("200", "запись в состоянии IN_REVIEW"),
        "errors": {"409": "запись уже в работе или решена"},
    },
    "/api/v1/review-queue/{itemId}/revert": {
        "method": "post",
        "summary": "Отмена решения: запись возвращается в OPEN",
        "scope": "review:write",
        "idempotent": False,
        "body": {"type": "object", "properties": {"note": {"type": "string"}}},
        "success": ("200", "запись в состоянии OPEN"),
        "errors": {"409": "отменять нечего"},
    },
    "/api/v1/review-queue/batch": {
        "method": "post",
        "summary": "Групповое решение: сухой прогон, применение по отпечатку, откат партии",
        "scope": "review:write",
        "idempotent": False,
        "body": {
            "type": "object",
            "required": ["mode"],
            "properties": {
                "mode": {"type": "string", "enum": ["dryRun", "apply", "revert"]},
                "conflictCode": {"type": "string"},
                "fromValue": {"type": "string"},
                "toValue": {"type": "string"},
                "expectedFingerprint": {
                    "type": "string",
                    "description": "отпечаток состава и версий из сухого прогона",
                },
                "batchId": {"type": "string"},
            },
        },
        "success": ("200", "итог сухого прогона, применения или отката"),
        "errors": {"400": "негодный mode", "409": "набор изменился между прогоном и применением"},
    },
    "/api/v1/operators": {
        "method": "get",
        "summary": "Операторы: роли, состояние, второй фактор",
        "scope": "read",
        "idempotent": False,
        "body": None,
        "success": ("200", "страница каталога операторов"),
        "errors": {"400": "негодный limit"},
    },
    "/api/v1/operators/invites": {
        "method": "post",
        "summary": "Приглашение оператора; одноразовый секрет возвращается один раз",
        "scope": "operators:write",
        "idempotent": False,
        "body": {
            "type": "object",
            "required": ["email", "roles"],
            "properties": {
                "email": {"type": "string"},
                "roles": {"type": "array", "items": {"type": "string"}},
            },
        },
        "success": ("201", "приглашение и одноразовый секрет"),
        "errors": {"400": "негодный адрес или роль", "409": "адрес уже активен"},
    },
    "/api/v1/operators/sessions": {
        "method": "get",
        "summary": "Активные сессии операторов",
        "scope": "operators:write",
        "idempotent": False,
        "body": None,
        "success": ("200", "список сессий без идентификаторов cookie"),
        "errors": {},
    },
    "/api/v1/operators/sessions/revoke": {
        "method": "post",
        "summary": "Отзыв одной сессии; действует немедленно",
        "scope": "operators:write",
        "idempotent": True,
        "body": {
            "type": "object",
            "required": ["sessionId"],
            "properties": {"sessionId": {"type": "string"}},
        },
        "success": ("200", "сессия отозвана"),
        "errors": {"404": "сессии нет или она уже отозвана"},
    },
    "/api/v1/operators/{operatorId}/roles": {
        "method": "post",
        "summary": "Смена ролей; отзывает выданные сессии оператора",
        "scope": "operators:write",
        "idempotent": True,
        "body": {
            "type": "object",
            "required": ["roles"],
            "properties": {
                "roles": {"type": "array", "items": {"type": "string"}},
                "actorOperatorId": {"type": "string"},
            },
        },
        "success": ("200", "оператор с новыми ролями"),
        "errors": {"409": "последний администратор или повышение собственных полномочий"},
    },
    "/api/v1/operators/{operatorId}/block": {
        "method": "post",
        "summary": "Блокировка оператора; сессии гаснут немедленно",
        "scope": "operators:write",
        "idempotent": True,
        "body": {
            "type": "object",
            "required": ["reason"],
            "properties": {"reason": {"type": "string"}, "actorOperatorId": {"type": "string"}},
        },
        "success": ("200", "заблокированный оператор"),
        "errors": {"409": "последний администратор или блокировка самого себя"},
    },
    "/api/v1/operators/{operatorId}/unblock": {
        "method": "post",
        "summary": "Разблокировка оператора",
        "scope": "operators:write",
        "idempotent": True,
        "body": None,
        "success": ("200", "оператор вернулся в строй"),
        "errors": {"409": "оператор не заблокирован"},
    },
    "/api/v1/operators/{operatorId}/revoke-sessions": {
        "method": "post",
        "summary": "Отзыв всех сессий оператора",
        "scope": "operators:write",
        "idempotent": True,
        "body": None,
        "success": ("200", "число отозванных сессий"),
        "errors": {},
    },
    "/api/v1/traces/{traceId}": {
        "method": "get",
        "summary": "Путь запроса по идентификатору следа",
        "scope": "audit:read",
        "idempotent": False,
        "body": None,
        "success": ("200", "отрезки следа по звеньям с длительностями"),
        "errors": {"404": "след не найден: запрос мог не попасть в выборку"},
    },
    "/api/v1/compatibility": {
        "method": "get",
        "summary": "Матрица совместимости витрин с версией движка",
        "scope": "read",
        "idempotent": False,
        "body": None,
        "success": ("200", "состояние по каждой витрине: ok, unversioned, degraded, incompatible"),
        "errors": {"404": "маршрут выключен"},
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
            параметры.append(
                {"name": "siteId", "in": "path", "required": True, "schema": {"type": "string"}}
            )
        if "{titleId}" in путь:
            параметры.append(
                {"name": "titleId", "in": "path", "required": True, "schema": {"type": "string"}}
            )
        if описание["returns"] == "page":
            параметры += [
                {
                    "name": "offset",
                    "in": "query",
                    "required": False,
                    "schema": {"type": "integer", "minimum": 0},
                },
                {
                    "name": "limit",
                    "in": "query",
                    "required": False,
                    "schema": {"type": "integer", "minimum": 1, "maximum": MAX_LIMIT},
                },
            ]
        ответы = {
            "200": {"description": "успех"},
            "404": {
                "description": "нет такого маршрута, сайта или тайтла",
                "content": {"application/json": {"schema": ОШИБКА}},
            },
        }
        if описание["returns"] == "page":
            ответы["400"] = {
                "description": "негодные параметры страницы",
                "content": {"application/json": {"schema": ОШИБКА}},
            }
        paths[путь] = {
            "get": {"summary": описание["summary"], "parameters": параметры, "responses": ответы}
        }
    for путь, описание in ЗАПИСЬ.items():
        параметры = []
        if "{siteId}" in путь:
            параметры.append(
                {"name": "siteId", "in": "path", "required": True, "schema": {"type": "string"}}
            )
        if "{jobId}" in путь:
            параметры.append(
                {"name": "jobId", "in": "path", "required": True, "schema": {"type": "string"}}
            )
        параметры.append(
            {
                "name": "X-Correlation-Id",
                "in": "header",
                "required": False,
                "schema": {"type": "string"},
                "description": "Возвращается во всех ответах, включая отказы.",
            }
        )
        if описание["idempotent"]:
            параметры.append(
                {
                    "name": "Idempotency-Key",
                    "in": "header",
                    "required": False,
                    "schema": {"type": "string", "maxLength": 128},
                    "description": "Повтор возвращает прежний ответ; тот же ключ с другим телом — 409.",
                }
            )
        код, текст = описание["success"]
        ответы = {код: {"description": текст}}
        for код_ошибки, текст_ошибки in описание["errors"].items():
            ответы[код_ошибки] = {
                "description": текст_ошибки,
                "content": {"application/json": {"schema": ОШИБКА}},
            }
        ответы["401"] = {
            "description": "нет или не распознан токен",
            "content": {"application/json": {"schema": ОШИБКА}},
        }
        ответы["403"] = {
            "description": f"у токена нет области {описание['scope']}",
            "content": {"application/json": {"schema": ОШИБКА}},
        }
        пределы = ", ".join(
            f"{вид} {п.capacity}/{int(п.per_seconds)}с" for вид, п in sorted(DEFAULT_LIMITS.items())
        )
        ответы["429"] = {
            "description": f"превышен предел частоты ({пределы}); "
            "пределы раздельные по среде, витрине, "
            "действующему лицу и операции",
            "content": {"application/json": {"schema": ОШИБКА}},
        }
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
                "выключателей. Права выдаются по областям ("
                + ", ".join(sorted(KNOWN_SCOPES))
                + "); токен без нужной области получает 403, а не тихий отказ."
            ),
        },
        "paths": paths,
        "components": {
            "schemas": {"Error": ОШИБКА, "TitleBrief": КРАТКО},
            "securitySchemes": {
                "bearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "description": "Токен из SITE_ENGINE_CONTROL_TOKENS.",
                }
            },
        },
    }


def write(path: Path | str = "schemas/site-engine/openapi-v1.json") -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(spec(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target
