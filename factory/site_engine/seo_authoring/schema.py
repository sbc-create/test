"""Каноническое предложение SEO-контента: строгая схема и её проверка.

Схема закрыта для неизвестных полей намеренно. Открытая схема принимает
опечатку в имени поля как «дополнительные данные», и предложение проходит
дальше без того, что автор считал переданным.

Поля разделены на три группы, и различие между ними — не оформление:

* **заявленные** приходят от заказчика и проверяются;
* **выводимые** сервер получает из реестра и политики. Значение из запроса
  для них служит только сверкой: расхождение — отказ, а не переопределение.
  Иначе окружение, владельца и аудиторию назначал бы отправитель;
* **вычисляемые** сервер считает сам и в запросе не принимает вовсе.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

RESOURCE_KIND = "seo.content.proposal"
SCHEMA_VERSION = "seo.content.proposal/1.0.0"
RESOURCE_VERSION = "1"

#: Поверхности, для которых предложение вообще имеет смысл.
ПОВЕРХНОСТИ = ("title", "description", "h1", "intro", "faq", "breadcrumbs")

#: Виды сущностей страницы.
ВИДЫ_СУЩНОСТЕЙ = ("anime.title", "anime.episode", "catalog.page",
                  "collection.page", "static.page")

#: Значения, которые отправитель НЕ вправе назначать. Присланные — только
#: для сверки с выведенными сервером.
ВЫВОДИМЫЕ = ("target_environment", "owner_service", "audience", "site_kind")

#: Поля, вычисляемые сервером. В запросе их наличие — ошибка, а не подсказка.
ВЫЧИСЛЯЕМЫЕ = ("proposal_id", "accepted_at", "changeset_id", "resource_version")

ОБЯЗАТЕЛЬНЫЕ = (
    "schema_version", "resource_kind", "site_id", "entity_id", "entity_kind",
    "surface", "locale", "fact_pack_ref", "source_snapshot_sha256",
    "artifact_ref", "artifact_digest", "model_version", "prompt_version",
    "policy_version", "requested_by", "correlation_id", "causation_id",
    "idempotency_key", "operations",
)

ДОПУСТИМЫЕ = ОБЯЗАТЕЛЬНЫЕ + ВЫВОДИМЫЕ + (
    "draft_revision_id", "draft_revision_digest", "intent_id", "rationale",
)

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ИД = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{1,127}$")
_ЛОКАЛЬ = re.compile(r"^[a-z]{2}(-[A-Z]{2})?$")
# Косая черта допустима: в проекте принята форма `policy/1.0.0`, и запрет
# заставил бы подгонять значение под проверку вместо обратного.
_ВЕРСИЯ = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_./+-]{0,63}$")


class ProposalRejected(ValueError):
    """Предложение отклонено до любого эффекта."""

    def __init__(self, code: str, detail: str, status: int = 422):
        super().__init__(detail)
        self.error_code, self.detail, self.status = code, detail, status


def канон(данные: Any) -> str:
    return json.dumps(данные, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))


def отпечаток(данные: Any) -> str:
    return hashlib.sha256(канон(данные).encode("utf-8")).hexdigest()


def json_schema() -> dict[str, Any]:
    """Строгая схема для набора контрактов.

    Собирается из тех же констант, по которым работает проверка. Отдельно
    написанная схема разошлась бы с кодом на первой же правке, и рядом
    оказались бы два разных представления об одном и том же.
    """
    строка = {"type": "string", "minLength": 1, "maxLength": 256}
    сумма = {"type": "string", "pattern": "^[0-9a-f]{64}$"}
    свойства: dict[str, Any] = {
        "schema_version": {"const": SCHEMA_VERSION},
        "resource_kind": {"const": RESOURCE_KIND},
        "resource_version": {"const": RESOURCE_VERSION,
                             "description": "Вычисляется сервером."},
        "proposal_id": dict(строка, description="Вычисляется сервером; "
                                                "в запросе не принимается."),
        "changeset_id": dict(строка, description="Вычисляется сервером."),
        "accepted_at": {"type": "string", "format": "date-time",
                        "description": "Вычисляется сервером."},
        "site_id": dict(строка, pattern=_ИД.pattern,
                        description="Единственный ключ витрины; домен ключом "
                                    "не является."),
        "entity_id": dict(строка, pattern=_ИД.pattern,
                          description="Канонический идентификатор сущности."),
        "entity_kind": {"enum": list(ВИДЫ_СУЩНОСТЕЙ)},
        "surface": {"enum": list(ПОВЕРХНОСТИ)},
        "locale": {"type": "string", "pattern": _ЛОКАЛЬ.pattern},
        "fact_pack_ref": dict(строка, description="Ссылка на набор фактов реестра."),
        "source_snapshot_sha256": dict(
            сумма, description="Отпечаток фактов, по которым составлен текст. "
                               "Расхождение с текущим снимком — отказ."),
        "artifact_ref": dict(строка, description="Ссылка на содержимое черновика."),
        "artifact_digest": dict(сумма, description="Отпечаток содержимого."),
        "draft_revision_id": dict(строка),
        "draft_revision_digest": сумма,
        "intent_id": dict(строка),
        "model_version": {"type": "string", "pattern": _ВЕРСИЯ.pattern},
        "prompt_version": {"type": "string", "pattern": _ВЕРСИЯ.pattern},
        "policy_version": {"type": "string", "pattern": _ВЕРСИЯ.pattern},
        "requested_by": dict(строка, description="Заявленный заказчик; "
                                                 "сверяется с опознанным."),
        "correlation_id": dict(строка),
        "causation_id": dict(строка),
        "idempotency_key": dict(строка),
        "rationale": {"type": "string", "maxLength": 2048},
        "operations": {
            "type": "array", "minItems": 1, "maxItems": 32,
            "items": {
                "type": "object", "additionalProperties": False,
                "required": ["op", "path", "value_digest"],
                "properties": {
                    "op": {"enum": ["set", "replace"]},
                    # Один сегмент: поверхности SEO плоские. Разрешить
                    # вложенность значило бы разрешить и то, что от файлового
                    # пути неотличимо.
                    "path": {"enum": [f"/{s}" for s in ПОВЕРХНОСТИ],
                             "description": "Указатель на объявленную "
                                            "поверхность, а не путь в "
                                            "файловой системе."},
                    "value_digest": сумма,
                },
            },
        },
    }
    for поле in ВЫВОДИМЫЕ:
        свойства[поле] = dict(
            строка, description="Выводится сервером из реестра и политики; "
                                "присланное значение только сверяется.")
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "SeoContentProposal.v1",
        "description": (
            "Предложение авторского SEO-контента. Схема закрыта для "
            "неизвестных полей: открытая приняла бы опечатку в имени поля "
            "как дополнительные данные, и предложение прошло бы дальше без "
            "того, что автор считал переданным."),
        "type": "object",
        "additionalProperties": False,
        "required": list(ОБЯЗАТЕЛЬНЫЕ),
        "properties": свойства,
    }


def _проверить_на_внедрение(заявка: dict[str, Any]) -> None:
    """Свободные строки проверяются теми же образцами, что и заявка набора.

    Второго определения «опасного» быть не должно: два перечня расходятся на
    первой же правке, и одно из них молча перестаёт ловить то, что ловит
    другое. Поля-указатели сюда не попадают — их форма задана перечнем
    поверхностей и проверена отдельно.
    """
    from factory.site_engine.changeset.planner import ОПАСНЫЕ_ОБРАЗЦЫ

    свободные = ("fact_pack_ref", "artifact_ref", "rationale", "entity_id",
                 "requested_by", "correlation_id", "causation_id",
                 "idempotency_key", "draft_revision_id", "intent_id")
    for поле in свободные:
        значение = заявка.get(поле)
        if not isinstance(значение, str):
            continue
        for образец, что in ОПАСНЫЕ_ОБРАЗЦЫ:
            if образец.search(значение):
                raise ProposalRejected(
                    "PAYLOAD_REJECTED", f"{поле}: обнаружено — {что}")


def проверить(заявка: dict[str, Any]) -> dict[str, Any]:
    """Проверить заявку до любого эффекта. Возвращает нормализованную копию."""
    if not isinstance(заявка, dict):
        raise ProposalRejected("PAYLOAD_TYPE_INVALID", "ожидается объект")

    лишние = sorted(set(заявка) - set(ДОПУСТИМЫЕ))
    вычисляемые = sorted(set(заявка) & set(ВЫЧИСЛЯЕМЫЕ))
    if вычисляемые:
        raise ProposalRejected(
            "FIELD_NOT_ACCEPTED",
            f"поля вычисляются сервером и в запросе не принимаются: {вычисляемые}")
    if лишние:
        raise ProposalRejected("FIELD_UNKNOWN", f"неизвестные поля: {лишние}")

    нет = [k for k in ОБЯЗАТЕЛЬНЫЕ if k not in заявка]
    if нет:
        raise ProposalRejected("FIELD_REQUIRED", f"не заданы поля: {нет}")

    if заявка["schema_version"] != SCHEMA_VERSION:
        raise ProposalRejected(
            "SCHEMA_VERSION_UNSUPPORTED",
            f"версия схемы {заявка['schema_version']!r}; поддерживается "
            f"{SCHEMA_VERSION!r}")
    if заявка["resource_kind"] != RESOURCE_KIND:
        raise ProposalRejected(
            "RESOURCE_KIND_UNKNOWN",
            f"вид ресурса {заявка['resource_kind']!r} не обслуживается")

    for поле in ("site_id", "entity_id", "fact_pack_ref", "artifact_ref",
                 "requested_by", "correlation_id", "causation_id",
                 "idempotency_key"):
        значение = заявка[поле]
        if not isinstance(значение, str) or not значение.strip():
            raise ProposalRejected("FIELD_INVALID", f"{поле}: пустое значение")
    for поле in ("site_id", "entity_id"):
        if not _ИД.fullmatch(заявка[поле]):
            raise ProposalRejected("FIELD_INVALID",
                                   f"{поле}: недопустимый идентификатор")
    for поле in ("source_snapshot_sha256", "artifact_digest"):
        if not _SHA256.fullmatch(str(заявка[поле])):
            raise ProposalRejected("DIGEST_INVALID",
                                   f"{поле}: не отпечаток sha256")
    if заявка["entity_kind"] not in ВИДЫ_СУЩНОСТЕЙ:
        raise ProposalRejected("ENTITY_KIND_UNKNOWN",
                               f"вид сущности {заявка['entity_kind']!r} неизвестен")
    if заявка["surface"] not in ПОВЕРХНОСТИ:
        raise ProposalRejected("SURFACE_UNKNOWN",
                               f"поверхность {заявка['surface']!r} неизвестна")
    if not _ЛОКАЛЬ.fullmatch(str(заявка["locale"])):
        raise ProposalRejected("LOCALE_INVALID",
                               f"локаль {заявка['locale']!r} не разобрана")
    for поле in ("model_version", "prompt_version", "policy_version"):
        if not _ВЕРСИЯ.fullmatch(str(заявка[поле])):
            raise ProposalRejected("VERSION_INVALID", f"{поле}: неразобранная версия")

    _проверить_на_внедрение(заявка)

    операции = заявка["operations"]
    if not isinstance(операции, list) or not operations_ок(операции):
        raise ProposalRejected("OPERATIONS_INVALID",
                               "operations: ожидается непустой список правок "
                               "вида {op, path, value_digest}")
    return dict(заявка)


def operations_ок(операции: list) -> bool:
    if not операции or len(операции) > 32:
        return False
    допустимые = {f"/{s}" for s in ПОВЕРХНОСТИ}
    for о in операции:
        if not isinstance(о, dict) or set(о) != {"op", "path", "value_digest"}:
            return False
        if о["op"] not in ("set", "replace"):
            return False
        if not isinstance(о["path"], str) or о["path"] not in допустимые:
            return False
        if not _SHA256.fullmatch(str(о["value_digest"])):
            return False
    return True
