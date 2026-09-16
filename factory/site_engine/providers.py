"""Адаптеры поставщиков: перевод чужого API в наш контракт.

Модуль знает про HTTP и чужие форматы и не знает ничего про витрины, полки и
SEO. Обратное направление — единственное, ради чего он существует.

Почему реестр, а не прямые вызовы: сейчас строка `cdnvideohub` встречается в
семи модулях `lords`, в `verify` и в `analytics.events`. Каждое такое место —
самостоятельное мнение о том, что умеет поставщик, и мнения расходятся. Реестр
делает такое расхождение невозможным.
"""
from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from factory.site_engine.contracts import (
    ContractError,
    ExternalIds,
    Provenance,
    Rating,
    Season,
    Title,
    utc_now,
)


class ProviderUnavailable(ContractError):
    """Источник не ответил. Не повод портить витрину."""


class ProviderContractBroken(ContractError):
    """Источник ответил не тем, что обещал.

    Отдельный тип нужен, чтобы отличать «поставщик лежит» от «поставщик
    изменил формат»: первое лечится повтором, второе — только человеком.
    """


@dataclass(frozen=True)
class ProviderCapabilities:
    """Что источник умеет на самом деле, а не по документации.

    Значения ниже проверены запросами. Их место в коде, а не в заметке: код,
    который спрашивает у возможностей, не может обратиться к маршруту, которого
    нет.
    """

    has_episode_list: bool = False
    has_playback_endpoint: bool = False
    has_updated_at: bool = False
    has_working_search: bool = False
    has_seasons: bool = True
    max_page_size: int = 24


@runtime_checkable
class ProviderAdapter(Protocol):
    """Публичный интерфейс поставщика. Всё остальное — его внутреннее дело."""

    name: str
    capabilities: ProviderCapabilities

    def walk_titles(self, *, limit: int | None = None) -> Iterator[Title]:
        """Полный обход каталога с курсорами."""

    def fetch_title(self, provider_id: str) -> Title:
        """Одна карточка по идентификатору поставщика."""

    def total_titles(self) -> int | None:
        """Сколько записей обещает источник. `None` — не сообщает."""


_REGISTRY: dict[str, ProviderAdapter] = {}


def register(adapter: ProviderAdapter) -> ProviderAdapter:
    if adapter.name in _REGISTRY:
        raise ContractError(f"адаптер {adapter.name} уже зарегистрирован")
    _REGISTRY[adapter.name] = adapter
    return adapter


def get(name: str) -> ProviderAdapter:
    try:
        return _REGISTRY[name]
    except KeyError:
        raise ContractError(
            f"адаптер {name} не зарегистрирован; известны: {sorted(_REGISTRY) or 'ни одного'}"
        ) from None


def registered() -> tuple[str, ...]:
    return tuple(sorted(_REGISTRY))


def clear_registry() -> None:
    """Только для тестов: реестр модульного уровня иначе течёт между ними."""
    _REGISTRY.clear()


def normalize_rating(source: str, value: Any, *, observed_at=None) -> Rating | None:
    """Оценка или `None` — но не ноль вместо отсутствия.

    Поставщик отдаёт `kinopoisk_rating` и `imdb_rating` разреженно: у
    большинства записей их нет. Ноль на витрине означал бы «оценили в ноль»,
    чего никто не делал.
    """
    if value in (None, "", 0, 0.0):
        return None
    try:
        number = round(float(value), 1)
    except (TypeError, ValueError):
        return None
    if not (Rating.MIN <= number <= Rating.MAX):
        return None
    return Rating(source=source, value=number, observed_at=observed_at or utc_now())


def normalize_external_ids(raw: dict[str, Any] | None) -> ExternalIds:
    """Кинопоиск приходит то как `kp`, то как `kinopoisk`.

    Одно и то же поле у двух представлений источника называется по-разному.
    Пока это не сведено в одном месте, половина записей молча теряет
    идентификатор — а по нему потом ищутся оценки.
    """
    raw = raw or {}
    kp = raw.get("kp") or raw.get("kinopoisk")
    return ExternalIds(
        kp=str(kp) if kp else None,
        imdb=str(raw["imdb"]) if raw.get("imdb") else None,
        tmdb=str(raw["tmdb"]) if raw.get("tmdb") else None,
        mdl=str(raw["mdl"]) if raw.get("mdl") else None,
        mal=str(raw["mal"]) if raw.get("mal") else None,
    )


def normalize_seasons(raw_seasons: list[dict[str, Any]] | None) -> tuple[Season, ...]:
    """Сезоны в том виде, в каком их сообщает источник.

    Списка серий нет — есть два счётчика. Достраивать список серий из счётчика
    значит выдумывать данные, поэтому `episodes` остаётся пустым.
    """
    out: list[Season] = []
    for raw in raw_seasons or []:
        number = raw.get("number")
        if number is None:
            continue
        out.append(
            Season(
                number=int(number),
                name=raw.get("name") or None,
                episodes_count=raw.get("episodes_count"),
                available_episodes_count=raw.get("available_episodes_count"),
            )
        )
    return tuple(out)


def canonical_id(provider: str, provider_id: str) -> str:
    """Канонический идентификатор — пара «поставщик + его идентификатор».

    Не транслитерация имени: пять из шести угаданных по имени адресов отдавали
    404, потому что правдоподобный слаг и существующий слаг — разные вещи.
    """
    if not provider or not provider_id:
        raise ContractError("канонический идентификатор требует и поставщика, и его id")
    return f"{provider}:{provider_id}"


def title_from_provider(
    *,
    provider: str,
    raw: dict[str, Any],
    observed_at=None,
) -> Title:
    """Общая нормализация карточки.

    `provider_timestamp` остаётся пустым: этот источник времени изменения не
    сообщает. Подставить сюда момент опроса было бы удобно и неверно.
    """
    provider_id = str(raw.get("id") or "")
    if not provider_id:
        raise ProviderContractBroken("в карточке нет идентификатора")
    name = (raw.get("name") or raw.get("title") or "").strip()
    if not name:
        raise ProviderContractBroken(f"в карточке {provider_id} нет имени")
    stamp = observed_at or utc_now()
    ratings = tuple(
        r
        for r in (
            normalize_rating("kinopoisk", raw.get("kinopoisk_rating"), observed_at=stamp),
            normalize_rating("imdb", raw.get("imdb_rating"), observed_at=stamp),
        )
        if r is not None
    )
    return Title(
        canonical_id=canonical_id(provider, provider_id),
        provider=provider,
        provider_id=provider_id,
        name=name,
        original_name=(raw.get("original_name") or None),
        year=raw.get("year"),
        kind=raw.get("type") or raw.get("kind"),
        genres=tuple(raw.get("genres") or ()),
        countries=tuple(raw.get("countries") or ()),
        external_ids=normalize_external_ids(raw.get("external_ids")),
        ratings=ratings,
        seasons=normalize_seasons(raw.get("seasons")),
        poster_url=raw.get("poster") or raw.get("poster_url"),
        observed_at=stamp,
        provider_timestamp=None,
    )


__all__ = [
    "ProviderAdapter",
    "ProviderCapabilities",
    "ProviderContractBroken",
    "ProviderUnavailable",
    "canonical_id",
    "clear_registry",
    "get",
    "normalize_external_ids",
    "normalize_rating",
    "normalize_seasons",
    "register",
    "registered",
    "title_from_provider",
    "Provenance",
]
