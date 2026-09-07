"""Настройки витрины как экран, а не как запрос.

Проверка разрешённых настроек существовала и раньше, но жила только на пути
записи. Оператор узнавал границы, наткнувшись на отказ. Здесь те же самые
правила читаются наперёд: что можно менять, в каких пределах, что отклоняется и
почему, что уже стоит и как вернуть назад.

Источник границ — тот же словарь, что применяет проверку. Второй список,
написанный для экрана, разошёлся бы с проверкой на первом же изменении и врал
бы оператору, оставаясь при этом «документацией».

Значение секрета сюда не попадает никогда. Панель показывает ссылку на
хранилище — имя и адрес, — потому что оператору нужно знать, что подключено,
а не чем именно.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from factory import audit
from factory.site_engine.settings_contract import (
    REFUSED_SETTINGS,
    SAFE_SETTINGS,
    config_version,
    profile_path,
)

#: Как изменение доходит до посетителя. Различие не косметическое: флаг можно
#: сначала включить одной витрине и посмотреть, а число хранимых выпусков
#: действует сразу и целиком, и «канареечного» состояния у него не бывает.
ВЫКАТ: dict[str, str] = {
    "keep_releases": "immediate",
    "cache_policy": "immediate",
    "feature_flags": "canary",
}

ОПИСАНИЕ: dict[str, str] = {
    "keep_releases": "Сколько выпусков хранить для отката.",
    "cache_policy": "Время жизни кэша по областям, в секундах.",
    "feature_flags": "Возможности витрины, включаемые по одной.",
}

ТИП: dict[str, str] = {
    "keep_releases": "integer",
    "cache_policy": "map<string,integer>",
    "feature_flags": "map<string,boolean>",
}

#: Ключи профиля, содержимое которых считается секретом целиком.
СЕКРЕТНЫЕ_РАЗДЕЛЫ = ("secrets", "credentials")
#: Схемы ссылок на внешние хранилища секретов.
СХЕМЫ_ССЫЛОК = ("vault://", "secret://", "env:", "ref://")

СКРЫТО = "значение не читается панелью"


class SettingsViewError(Exception):
    """Витрины нет или её профиль нечитаем."""


def границы(ключ: str) -> str:
    """Границы одной настройки словами, одинаково для API и для экрана."""
    правило = SAFE_SETTINGS.get(ключ)
    if правило is None:
        return ""
    if "min" in правило and "max" in правило:
        return f"от {правило['min']} до {правило['max']}"
    return ""


def _ссылки_на_секреты(профиль: dict[str, Any]) -> list[dict[str, str]]:
    """Ссылки — да, значения — нет.

    Разбирается и вложенный раздел секретов, и одиночное поле, значение которого
    само выглядит ссылкой на хранилище: в профилях встречаются оба способа, и
    пропустить второй значило бы показать оператору половину подключений.
    """
    найдено: list[dict[str, str]] = []
    for раздел in СЕКРЕТНЫЕ_РАЗДЕЛЫ:
        узел = профиль.get(раздел)
        if not isinstance(узел, dict):
            continue
        for ключ, значение in sorted(узел.items()):
            if isinstance(значение, dict):
                ссылка = str(значение.get("ref") or значение.get("reference") or "")
                хранилище = str(значение.get("store") or _хранилище(ссылка))
            else:
                ссылка = str(значение)
                хранилище = _хранилище(ссылка)
            найдено.append(
                {
                    "key": ключ,
                    "store": хранилище,
                    "ref": ссылка if ссылка.startswith(СХЕМЫ_ССЫЛОК) else "",
                    "value": СКРЫТО,
                }
            )
    for ключ, значение in sorted(профиль.items()):
        if ключ in СЕКРЕТНЫЕ_РАЗДЕЛЫ or not isinstance(значение, str):
            continue
        if значение.startswith(СХЕМЫ_ССЫЛОК):
            найдено.append(
                {
                    "key": ключ,
                    "store": _хранилище(значение),
                    "ref": значение,
                    "value": СКРЫТО,
                }
            )
    return найдено


def _хранилище(ссылка: str) -> str:
    схема, _, _ = ссылка.partition(":")
    return схема or "неизвестно"


def _обратно(разница: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Изменения, возвращающие прежнее состояние: что присвоить и что убрать.

    Для вложенных словарей возвращается прежний словарь целиком: применение
    сливает вложенные ключи, и частичный откат оставил бы добавленный ключ на
    месте — «откат», после которого состояние всё ещё другое.

    Настройка, которой раньше не было, откатывается удалением. Раньше такой
    случай объявлялся неоткатываемым: путь записи умел только присваивать, и
    оператор, добавивший поле, не мог убрать его из панели вообще.
    """
    назад: dict[str, Any] = {}
    убрать: list[str] = []
    for ключ, пара in разница.items():
        было = пара.get("before")
        if было is None:
            убрать.append(ключ)
            continue
        назад[ключ] = было
    return назад, убрать


def откат(site_id: str, root: Path, *, версия: str) -> dict[str, Any]:
    """Последнее применённое изменение настроек — если с тех пор ничего не меняли.

    Сверка версии обязательна. Откатывать по записи, поверх которой уже легло
    чужое изменение, значило бы молча стереть это чужое изменение.
    """
    записи = [
        з
        for з in audit.read_all()
        if з.get("site_id") == site_id and з.get("action") == "control.settings.patch"
    ]
    if not записи:
        return {"available": False, "reason": "настройки этой витрины ещё не меняли"}
    последняя = записи[-1]
    дополнительно = последняя.get("extra") or {}
    разница = дополнительно.get("diff") or {}
    назад, убрать = _обратно(разница)
    if not назад and not убрать:
        return {"available": False, "reason": "прежнее значение не записано"}
    if дополнительно.get("version_after") != версия:
        return {
            "available": False,
            "reason": "после этого изменения конфигурацию правили ещё раз",
            "recordedAt": последняя.get("ts", ""),
        }
    return {
        "available": True,
        "changes": назад,
        "remove": убрать,
        "diff": разница,
        "recordedAt": последняя.get("ts", ""),
        "actor": последняя.get("actor", ""),
        "version": версия,
    }


def представление(site_id: str, root: Path, *, can_write: bool) -> dict[str, Any]:
    """Полное состояние экрана настроек одной витрины."""
    путь = profile_path(site_id, root)
    if not путь.exists():
        raise SettingsViewError(f"нет профиля витрины {site_id}")
    try:
        профиль = json.loads(путь.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SettingsViewError(f"профиль витрины {site_id} нечитаем") from exc

    версия = config_version(путь)
    поля = []
    for ключ in sorted(SAFE_SETTINGS):
        правило = SAFE_SETTINGS[ключ]
        поле: dict[str, Any] = {
            "key": ключ,
            "type": ТИП.get(ключ, правило["type"].__name__),
            "description": ОПИСАНИЕ.get(ключ, ""),
            "value": профиль.get(ключ),
            "present": ключ in профиль,
            "rollout": ВЫКАТ.get(ключ, "immediate"),
            "limits": границы(ключ),
        }
        if "min" in правило:
            поле["min"] = правило["min"]
        if "max" in правило:
            поле["max"] = правило["max"]
        поля.append(поле)

    return {
        "siteId": site_id,
        "version": версия,
        "canWrite": bool(can_write),
        "fields": поля,
        "refused": [{"key": k, "reason": v} for k, v in sorted(REFUSED_SETTINGS.items())],
        "secretRefs": _ссылки_на_секреты(профиль),
        "rollback": откат(site_id, root, версия=версия),
    }
