"""Совместимость витрины с версией движка.

Одна кодовая база обслуживает витрины разных типов. Отсюда вопрос, который
раньше никто не задавал явно: что происходит, когда движок ушёл вперёд, а
профиль витрины написан под прежний контракт. Молчаливый ответ «работает как
получится» — худший из возможных: расхождение обнаруживается на витрине, а не
при выкладке.

Поэтому профиль объявляет контракт (`cms_contract`), движок объявляет свой, и
их соотношение имеет три исхода:

* **ok** — старшая часть совпала, младшая у витрины не выше движковой;
* **degraded** — витрина просит младшую версию выше: чего-то из ожидаемого
  движок не умеет. Управлять можно, но знать об этом надо;
* **incompatible** — разошлись старшие части. Управление запрещается: правка
  конфигурации под чужой контракт делает витрину хуже, а не лучше.

Профиль без объявления считается совместимым: обратная совместимость важнее
формальной строгости, иначе введение контракта разом остановило бы весь массив.
Но такая витрина помечается `unversioned`, чтобы её было видно.

Разобранная с ошибкой версия считается несовместимой, а не пропускается.
Отказ громкий и обратимый; пропуск тихий и нет.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# Контракт, который реализует этот движок. Поднимается вместе с изменением
# наблюдаемого поведения, а не с каждым коммитом.
ENGINE_CONTRACT = "1.2.0"

_SEMVER = re.compile(r"^(\d+)\.(\d+)(?:\.(\d+))?$")

STATE_OK = "ok"
STATE_UNVERSIONED = "unversioned"
STATE_DEGRADED = "degraded"
STATE_INCOMPATIBLE = "incompatible"

MANAGEABLE = frozenset({STATE_OK, STATE_UNVERSIONED, STATE_DEGRADED})


@dataclass(frozen=True)
class Compatibility:
    state: str
    engine: str
    declared: str | None
    reason: str

    @property
    def manageable(self) -> bool:
        return self.state in MANAGEABLE

    def as_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "engine": self.engine,
            "declared": self.declared,
            "manageable": self.manageable,
            "reason": self.reason,
        }


def parse(version: str) -> tuple[int, int, int] | None:
    match = _SEMVER.match(str(version).strip())
    if not match:
        return None
    major, minor, patch = match.groups()
    return int(major), int(minor), int(patch or 0)


def evaluate(profile: dict[str, Any], *, engine: str = ENGINE_CONTRACT) -> Compatibility:
    """Соотношение контракта витрины и движка."""
    engine_parts = parse(engine)
    if engine_parts is None:
        # Испорченная версия самого движка — не повод объявить всё исправным.
        return Compatibility(STATE_INCOMPATIBLE, engine, None,
                             "версия движка не разобрана")
    raw_declared = profile.get("cms_contract")
    # Значение из одних пробелов приравнивается к отсутствию: оно не несёт
    # сведений о версии. Строка вроде "последняя" — другое дело: там есть
    # намерение, которое движок исполнить не может, и отказ обязан быть закрытым.
    declared = raw_declared.strip() if isinstance(raw_declared, str) else raw_declared
    if declared in (None, ""):
        return Compatibility(
            STATE_UNVERSIONED, engine, None,
            "профиль не объявляет контракт; считается совместимым по обратной совместимости",
        )
    site_parts = parse(declared)
    if site_parts is None:
        return Compatibility(
            STATE_INCOMPATIBLE, engine, str(declared),
            f"контракт {declared!r} не разобран как версия вида МАЖОР.МИНОР[.ПАТЧ]",
        )
    if site_parts[0] != engine_parts[0]:
        направление = "новее" if site_parts[0] > engine_parts[0] else "старее"
        return Compatibility(
            STATE_INCOMPATIBLE, engine, str(declared),
            f"старшая версия витрины {направление} движковой: {declared} против {engine}",
        )
    if site_parts[1] > engine_parts[1]:
        return Compatibility(
            STATE_DEGRADED, engine, str(declared),
            f"витрина рассчитывает на {declared}, движок предоставляет {engine}: "
            "часть ожидаемого поведения отсутствует",
        )
    return Compatibility(STATE_OK, engine, str(declared), "контракты согласованы")
