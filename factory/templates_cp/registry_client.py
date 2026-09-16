"""Единственный источник сайтов для Templates — versioned Site Registry API.

Почему клиент, а не список
--------------------------

До этого модуля Templates знали о сайтах из `config/FLEET-REGISTRY.json`.
Файл в репозитории — это снимок чужого состояния: он устаревает молча, и
новый сайт появляется в работе только после правки кода. Ключом связи там
был домен, а домен — изменяемый атрибут: смена canonical_domain выглядела
бы как исчезновение одного сайта и появление другого.

Здесь источник один и живой: `/api/v1/sites` с серверным фильтром. Ключ —
`site_id`. Отбор production делает сервер, а не клиент: получить весь список
и отфильтровать у себя значит воспроизвести серверное правило второй раз и
однажды разойтись с ним.

Свежесть объявляется, а не подразумевается
------------------------------------------

Ответ несёт `registry_version` и контрольную сумму снимка. Локальная
проекция — только кэш: она умеет ответить, когда Registry недоступен, но
обязана называть себя STALE. Выдавать устаревшую проекцию за свежие данные
запрещено: на ней нельзя ни планировать, ни применять.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any

#: Базовый адрес Control Plane. Значение приходит из окружения службы:
#: зашитый адрес — это тот же статический список, только на один элемент.
БАЗА_ПО_УМОЛЧАНИЮ = "http://127.0.0.1:8790"

#: Маршруты берутся из объявленного контракта, а не собираются на месте.
МАРШРУТ_САЙТЫ = "/api/v1/sites"
МАРШРУТ_ВЕРСИЯ = "/api/v1/registry/version"
МАРШРУТ_СНИМОК = "/api/v1/registry/snapshot"
МАРШРУТ_СОБЫТИЯ = "/api/v1/events"
МАРШРУТ_КОНТРАКТЫ = "/api/v1/contracts/manifest"
МАРШРУТ_ВОЗМОЖНОСТИ = "/api/v1/capabilities"


class RegistryUnavailable(RuntimeError):
    """Registry недоступен. Планирование и применение запрещены."""


@dataclass(frozen=True)
class Сайт:
    site_id: str
    family: str | None
    canonical_domain: str | None
    aliases: tuple[str, ...]
    environment: str | None
    lifecycle_state: str | None
    сырое: dict[str, Any] = field(repr=False, default_factory=dict)

    @staticmethod
    def из_записи(з: dict[str, Any]) -> "Сайт":
        домены = з.get("domains") or []
        канон = з.get("canonical_domain") or (домены[0] if домены else None)
        псевдонимы = tuple(d for d in домены if d != канон)
        return Сайт(site_id=з["site_id"], family=з.get("family") or з.get("site_family"),
                    canonical_domain=канон, aliases=псевдонимы,
                    environment=з.get("environment"),
                    lifecycle_state=з.get("lifecycle_state"), сырое=з)


@dataclass(frozen=True)
class Снимок:
    registry_version: int
    checksum: str | None
    etag: str | None
    сайты: tuple[Сайт, ...]
    свежий: bool = True

    @property
    def идентификаторы(self) -> frozenset[str]:
        return frozenset(с.site_id for с in self.сайты)


class RegistryClient:
    """Чтение Registry только через объявленные маршруты."""

    def __init__(self, база: str = БАЗА_ПО_УМОЛЧАНИЮ, таймаут: float = 15.0,
                 открывашка=None) -> None:
        self.база = база.rstrip("/")
        self.таймаут = таймаут
        # Открывашка внедряется, чтобы тесты работали без сети и без
        # подмены глобального urllib: подмена глобали в одном тесте
        # незаметно меняет поведение соседнего.
        self._открыть = открывашка or urllib.request.urlopen

    # --- низкий уровень -------------------------------------------------
    def _получить(self, путь: str) -> tuple[dict[str, Any], dict[str, str]]:
        зпр = urllib.request.Request(self.база + путь,
                                     headers={"Accept": "application/json"})
        try:
            with self._открыть(зпр, timeout=self.таймаут) as о:
                тело = о.read()
                заголовки = dict(getattr(о, "headers", {}) or {})
                return json.loads(тело.decode("utf-8")), заголовки
        except urllib.error.HTTPError as ош:
            raise RegistryUnavailable(
                f"{путь}: HTTP {ош.code}") from ош
        except Exception as ош:                       # сеть, разбор, таймаут
            raise RegistryUnavailable(f"{путь}: {type(ош).__name__}") from ош

    # --- контракт -------------------------------------------------------
    def версия_контракта(self) -> str:
        д, _ = self._получить(МАРШРУТ_КОНТРАКТЫ)
        return str(д.get("version"))

    def возможности(self) -> dict[str, str]:
        """capability_id → status. Источник правды о том, что объявлено."""
        д, _ = self._получить(МАРШРУТ_ВОЗМОЖНОСТИ)
        return {c["capability_id"]: c.get("status", "UNKNOWN")
                for c in д.get("capabilities", [])}

    def registry_version(self) -> int:
        д, _ = self._получить(МАРШРУТ_ВЕРСИЯ)
        return int(д["registry_version"])

    # --- сайты ----------------------------------------------------------
    def производственные(self) -> Снимок:
        """Только production + ACTIVE, отобранные СЕРВЕРОМ.

        Фильтр передаётся запросом. Клиентская фильтрация здесь была бы
        вторым местом, где живёт правило «что считается production», и
        рано или поздно эти два места разошлись бы.
        """
        запрос = urllib.parse.urlencode(
            {"environment": "production", "lifecycle_state": "ACTIVE"})
        д, заг = self._получить(f"{МАРШРУТ_САЙТЫ}?{запрос}")
        элементы = д.get("items", д if isinstance(д, list) else [])
        сайты = tuple(Сайт.из_записи(з) for з in элементы)
        чужие = [с.site_id for с in сайты
                 if (с.environment and с.environment != "production")
                 or (с.lifecycle_state and с.lifecycle_state != "ACTIVE")]
        if чужие:
            # Сервер вернул не то, что просили: молча отфильтровать — значит
            # скрыть расхождение контракта и работать с чужим множеством.
            raise RegistryUnavailable(
                f"серверный фильтр вернул посторонние записи: {чужие}")
        return Снимок(registry_version=int(д.get("registry_version") or self.registry_version()),
                      checksum=д.get("checksum"), etag=заг.get("ETag"),
                      сайты=сайты)

    def снимок(self) -> Снимок:
        д, заг = self._получить(МАРШРУТ_СНИМОК)
        сайты = tuple(Сайт.из_записи(з) for з in д.get("sites", []))
        return Снимок(registry_version=int(д["registry_version"]),
                      checksum=д.get("checksum"), etag=д.get("etag") or заг.get("ETag"),
                      сайты=сайты)

    # --- события --------------------------------------------------------
    def события(self, курсор: str | None = None, предел: int = 200) -> dict[str, Any]:
        параметры: dict[str, Any] = {"limit": предел}
        if курсор:
            параметры["cursor"] = курсор
        д, _ = self._получить(f"{МАРШРУТ_СОБЫТИЯ}?{urllib.parse.urlencode(параметры)}")
        return д
