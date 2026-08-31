"""Адаптеры рендереров: перевод нормализованного контента в страницы.

Рендерер данными не владеет и событий не создаёт. Оба ограничения выражены
интерфейсом: сюда приходит готовое, отсюда уходят страницы.

Реестр нужен по той же причине, что и у поставщиков: сейчас `factory.build` и
`factory.validation` импортируют `factory.lords` напрямую, то есть ядро знает
про конкретный тип сайта. Реестр разрывает эту связь, не переписывая витрину.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from factory.site_engine.contracts import ContractError
from factory.site_engine.profiles import SiteProfile


class RenderFailed(ContractError):
    pass


@dataclass(frozen=True)
class RenderedPage:
    path: str
    kind: str
    bytes_written: int


@runtime_checkable
class RendererAdapter(Protocol):
    name: str
    render_mode: str

    def supports(self, profile: SiteProfile) -> bool: ...
    def describe(self) -> dict[str, Any]: ...


_REGISTRY: dict[str, RendererAdapter] = {}


def register(adapter: RendererAdapter) -> RendererAdapter:
    if adapter.name in _REGISTRY:
        raise ContractError(f"рендерер {adapter.name} уже зарегистрирован")
    _REGISTRY[adapter.name] = adapter
    return adapter


def get(name: str) -> RendererAdapter:
    try:
        return _REGISTRY[name]
    except KeyError:
        raise ContractError(
            f"рендерер {name} не зарегистрирован; известны: {sorted(_REGISTRY) or 'ни одного'}"
        ) from None


def for_profile(profile: SiteProfile) -> RendererAdapter:
    """Рендерер выбирается по профилю, а не по имени сайта в коде."""
    matches = [a for a in _REGISTRY.values() if a.supports(profile)]
    if not matches:
        raise ContractError(
            f"для профиля {profile.site_id} (режим {profile.render_mode}) "
            "нет подходящего рендерера"
        )
    if len(matches) > 1:
        raise ContractError(
            f"профилю {profile.site_id} соответствуют несколько рендереров: "
            f"{sorted(a.name for a in matches)}"
        )
    return matches[0]


def registered() -> tuple[str, ...]:
    return tuple(sorted(_REGISTRY))


def clear_registry() -> None:
    _REGISTRY.clear()
