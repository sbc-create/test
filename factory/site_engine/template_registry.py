"""Реестр шаблонов: что именно можно выложить и чем это доказано.

Добавление шаблона — регистрация **проверенного пакета**, а не загрузка кода в
production. Разница видна на одном вопросе: «чем доказано, что этот пакет
работает». Если ответа нет, пакет не регистрируется — не потому, что он плох, а
потому что неизвестно.

У записи реестра пять обязательных частей, и каждая закрывает свой способ
ошибиться:

**Версия и отпечаток.** Версия — для людей, отпечаток — для сверки. Версия без
отпечатка позволяет выложить под тем же именем другое содержимое; отпечаток без
версии не даёт понять, что новее.

**Совместимость.** С каким договором витрины пакет работает. Пакет, собранный
под прежний договор, выложится и будет отвечать двумястами, а сломается на
первой странице, где договор изменился.

**Способности.** Что шаблон умеет: поиск на сервере, переключение тем,
разбивку на страницы. Витрина не должна обещать посетителю того, чего пакет не
умеет.

**Результат контрактных проверок.** Не «проверено», а когда, чем и с каким
итогом. «Проверено» без даты означает «когда-то».

**Совместимость отката.** На какую версию можно вернуться. Откат на версию,
несовместимую с текущим содержимым, — это вторая авария поверх первой.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ВЕРСИЯ = "template-registry/1.0.0"

#: Файл реестра. Настройка, а не код: регистрация пакета — решение, а не правка
#: программы.
РЕЕСТР = "config/template-registry.yaml"

#: Обязательные поля записи. Пустое или отсутствующее поле — отказ регистрации,
#: а не запись с пропуском: запись с пропуском выглядит как проверенная.
ОБЯЗАТЕЛЬНЫЕ = (
    "family", "version", "digest", "renderer_revision", "contract",
    "capabilities", "contract_tests",
)

#: Поля, которые обязаны присутствовать, но вправе быть пустыми. Самая первая
#: зарегистрированная версия семейства откатываться некуда — как и первый релиз
#: витрины. Требовать от неё непустой список значило бы требовать выдумать его.
ОБЯЗАТЕЛЬНЫЕ_ПУСТЫЕ = ("rollback_compatible_with",)

#: Способности, которые витрина вправе обещать посетителю. Перечень закрытый:
#: способность, которой нет в списке, невозможно ни проверить, ни отключить.
СПОСОБНОСТИ = frozenset({
    "server-search", "theme-switch", "pagination", "facets", "player",
    "collections", "episode-pages", "schema-org",
})


class RegistryError(Exception):
    """Пакет не может быть зарегистрирован. Причина названа."""


@dataclass
class Запись:
    family: str
    version: str
    digest: str
    renderer_revision: str
    contract: str
    capabilities: tuple[str, ...] = ()
    contract_tests: dict[str, Any] = field(default_factory=dict)
    rollback_compatible_with: tuple[str, ...] = ()
    preview: str = ""
    notes: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "family": self.family,
            "version": self.version,
            "digest": self.digest,
            "rendererRevision": self.renderer_revision,
            "contract": self.contract,
            "capabilities": list(self.capabilities),
            "contractTests": dict(self.contract_tests),
            "rollbackCompatibleWith": list(self.rollback_compatible_with),
            "preview": self.preview,
            "notes": self.notes,
        }


def _беды_записи(сырое: dict[str, Any]) -> list[str]:
    беды: list[str] = []
    for поле in ОБЯЗАТЕЛЬНЫЕ:
        if not сырое.get(поле):
            беды.append(f"нет поля {поле}")
    for поле in ОБЯЗАТЕЛЬНЫЕ_ПУСТЫЕ:
        if поле not in сырое:
            беды.append(f"нет поля {поле}: пустой список — это ответ, отсутствие — нет")
    отпечаток = str(сырое.get("digest") or "")
    if отпечаток and (len(отпечаток) != 64 or
                      not all(с in "0123456789abcdef" for с in отпечаток.lower())):
        беды.append(f"отпечаток не sha256: {отпечаток[:16]}…")
    ревизия = str(сырое.get("renderer_revision") or "")
    if ревизия and len(ревизия) != 40:
        беды.append("ревизия отрисовщика должна быть полным SHA: короткая ссылка "
                    "через день означает другое содержимое")
    способности = сырое.get("capabilities") or []
    чужие = [с for с in способности if с not in СПОСОБНОСТИ]
    if чужие:
        беды.append(f"неизвестные способности: {sorted(чужие)}")
    проверки = сырое.get("contract_tests") or {}
    if проверки:
        if not проверки.get("at"):
            беды.append("результат контрактных проверок без времени: «проверено» "
                        "без даты означает «когда-то»")
        if проверки.get("passed") is not True:
            беды.append("контрактные проверки не пройдены — пакет не регистрируется")
        if not проверки.get("suite"):
            беды.append("не сказано, чем проверялось")
    return беды


def запись_из(сырое: dict[str, Any]) -> Запись:
    беды = _беды_записи(сырое)
    if беды:
        raise RegistryError("; ".join(беды))
    return Запись(
        family=str(сырое["family"]),
        version=str(сырое["version"]),
        digest=str(сырое["digest"]),
        renderer_revision=str(сырое["renderer_revision"]),
        contract=str(сырое["contract"]),
        capabilities=tuple(сырое.get("capabilities") or ()),
        contract_tests=dict(сырое.get("contract_tests") or {}),
        rollback_compatible_with=tuple(сырое.get("rollback_compatible_with") or ()),
        preview=str(сырое.get("preview") or ""),
        notes=str(сырое.get("notes") or ""),
    )


def прочитать(root: Path | str) -> dict[str, Any]:
    """Реестр целиком: годные записи и отдельно — отвергнутые с причиной.

    Отвергнутая запись не выбрасывается молча: тот, кто её добавил, обязан
    увидеть, чем именно она не годится.
    """
    import yaml

    путь = Path(root) / РЕЕСТР
    try:
        сырое = yaml.safe_load(путь.read_text(encoding="utf-8")) or {}
    except FileNotFoundError:
        return {"registryVersion": ВЕРСИЯ, "templates": [], "rejected": [],
                "registryError": f"реестра нет: {РЕЕСТР}"}
    except (OSError, yaml.YAMLError) as ошибка:
        return {"registryVersion": ВЕРСИЯ, "templates": [], "rejected": [],
                "registryError": f"реестр не читается: {ошибка}"}

    годные, отвергнутые = [], []
    for элемент in сырое.get("templates") or []:
        try:
            годные.append(запись_из(элемент).as_dict())
        except RegistryError as отказ:
            отвергнутые.append({
                "family": элемент.get("family"),
                "version": элемент.get("version"),
                "reason": str(отказ),
            })
    return {
        "registryVersion": ВЕРСИЯ,
        "templates": годные,
        "rejected": отвергнутые,
        "registryError": "",
    }


def для_семейства(root: Path | str, family: str) -> list[dict[str, Any]]:
    return [з for з in прочитать(root)["templates"] if з["family"] == family]


def можно_откатиться(root: Path | str, family: str, *, с_версии: str,
                     на_версию: str) -> tuple[bool, str]:
    """Разрешён ли откат между версиями и почему нет, если нет."""
    записи = {з["version"]: з for з in для_семейства(root, family)}
    текущая = записи.get(с_версии)
    цель = записи.get(на_версию)
    if текущая is None:
        return False, f"версия {с_версии} не зарегистрирована"
    if цель is None:
        return False, f"версия {на_версию} не зарегистрирована: откатываться некуда"
    if на_версию not in текущая["rollbackCompatibleWith"]:
        return False, (
            f"{с_версии} не объявляет {на_версию} совместимой для отката: "
            "возврат на несовместимую версию — вторая авария поверх первой")
    return True, ""


def проверить_способность(root: Path | str, family: str, version: str,
                          способность: str) -> bool:
    """Обещает ли витрина то, что умеет пакет."""
    for з in для_семейства(root, family):
        if з["version"] == version:
            return способность in з["capabilities"]
    return False


def как_json(root: Path | str) -> str:
    return json.dumps(прочитать(root), ensure_ascii=False, indent=2)
