"""Клиент реестра. Только versioned API, никакого доступа к чужой базе.

Прямое чтение `registry.sqlite3` из контура изменений выглядело бы удобнее и
работало бы быстрее. Оно же сделало бы схему реестра частью нашего контракта:
любое её изменение ломало бы нас молча, а владелец об этом не узнал бы.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


class RegistryUnavailable(RuntimeError):
    pass


class RegistryClient:
    def __init__(self, база: str | None = None, *, таймаут: float = 10.0):
        self.база = (база or os.environ.get("CONTROL_API_BASE")
                     or "http://127.0.0.1:8790").rstrip("/")
        self.таймаут = таймаут

    def _гет(self, путь: str) -> Any:
        try:
            with urllib.request.urlopen(self.база + путь, timeout=self.таймаут) as о:
                return json.loads(о.read() or b"{}")
        except urllib.error.HTTPError as e:
            raise RegistryUnavailable(f"{путь}: HTTP {e.code}") from e
        except (urllib.error.URLError, OSError, ValueError) as e:
            raise RegistryUnavailable(f"{путь}: {e}") from e

    def версия(self) -> int:
        return int(self._гет("/api/v1/registry/version")["registry_version"])

    def сайт(self, site_id: str) -> dict | None:
        """Один сайт по идентификатору.

        Домен сюда не подходит и подходить не должен: ключом служит site_id,
        и поиск по домену вернул бы «не найдено» ровно тогда, когда кто-то
        перепутал ключ, — что и требуется.
        """
        д = self._гет("/api/v1/sites?site_id=" + urllib.parse.quote(site_id))
        элементы = д.get("items") or д.get("sites") or []
        for э in элементы:
            if э.get("site_id") == site_id:
                return э
        return None

    def сайты(self) -> list[dict]:
        д = self._гет("/api/v1/sites?limit=1000")
        return д.get("items") or д.get("sites") or []
