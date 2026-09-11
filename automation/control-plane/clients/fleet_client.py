"""Референсный клиент Control Plane для Python. Только чтение.

Мутаций здесь нет намеренно: помощник, умеющий писать, появится после IAM и
policy (FLEET-CORE-003). Клиент, дающий писать раньше прав, — это обход
политики, встроенный в библиотеку.
"""
from __future__ import annotations

import json, random, time, urllib.error, urllib.request, uuid
from typing import Any, Iterator

ВЕРСИЯ = "fleet-client-py/1.0.0"
ПОВТОРЯЕМЫЕ_КОДЫ = {429, 502, 503, 504}
ТЕРМИНАЛЬНЫЕ = {"SUCCEEDED", "FAILED", "BLOCKED", "CANCELLED"}


class ContractError(RuntimeError):
    """Ответ не соответствует контракту."""


class FleetClient:
    def __init__(self, base: str = "http://127.0.0.1:8790", *,
                 timeout: float = 15.0, retries: int = 3,
                 correlation_id: str | None = None):
        self.base = base.rstrip("/")
        self.timeout = timeout
        self.retries = retries
        self.correlation_id = correlation_id or str(uuid.uuid4())

    # ---------------------------------------------------------------- низ
    def _get(self, путь: str) -> tuple[int, Any, dict]:
        задержка = 0.1
        последняя = None
        for попытка in range(1, self.retries + 1):
            зпр = urllib.request.Request(self.base + путь, headers={
                "Accept": "application/json",
                "User-Agent": ВЕРСИЯ,
                # Контекст прослеживания обязателен: без него ответ службы
                # невозможно связать с вызвавшим его запросом.
                "X-Correlation-ID": self.correlation_id})
            try:
                with urllib.request.urlopen(зпр, timeout=self.timeout) as о:
                    return о.status, json.loads(о.read() or b"{}"), dict(о.headers)
            except urllib.error.HTTPError as e:
                if e.code not in ПОВТОРЯЕМЫЕ_КОДЫ:
                    # Неповторяемую ошибку повторять бессмысленно и вредно:
                    # 404 не станет 200 от настойчивости.
                    return e.code, self._тело(e), dict(e.headers)
                последняя = e
            except Exception as e:  # noqa: BLE001
                последняя = e
            if попытка < self.retries:
                # Экспоненциальная задержка с джиттером: без джиттера все
                # клиенты повторяют синхронно и добивают упавшую службу.
                time.sleep(min(задержка, 2.0) * (1 + random.random() * 0.3))
                задержка *= 2
        raise ContractError(f"{путь}: {type(последняя).__name__}")

    @staticmethod
    def _тело(e) -> Any:
        try:
            return json.loads(e.read() or b"{}")
        except Exception:  # noqa: BLE001
            return {}

    # -------------------------------------------------------------- поиск
    def manifest(self) -> dict:
        к, т, _ = self._get("/api/v1/contracts/manifest")
        if к != 200:
            raise ContractError("манифест недоступен")
        return т

    def capabilities(self) -> dict:
        к, т, _ = self._get("/api/v1/capabilities")
        return т if к == 200 else {}

    def capability(self, cid: str) -> dict | None:
        к, т, _ = self._get(f"/api/v1/capabilities/{cid}")
        return т if к == 200 else None

    def schema(self, schema_id: str) -> dict | None:
        к, т, _ = self._get(f"/api/v1/contracts/schemas/{schema_id}")
        return т if к == 200 else None

    def control_plane_version(self) -> dict:
        к, т, _ = self._get("/api/v1/control-plane/version")
        return т

    # -------------------------------------------------------------- сайты
    def sites(self, *, environment: str | None = None,
              lifecycle_state: str | None = None) -> list[dict]:
        q = []
        if environment:
            q.append(f"environment={environment}")
        if lifecycle_state:
            q.append(f"lifecycle_state={lifecycle_state}")
        путь = "/api/v1/sites" + ("?" + "&".join(q) if q else "")
        к, т, _ = self._get(путь)
        if к != 200:
            raise ContractError(f"/api/v1/sites -> {к}")
        return т.get("items", [])

    def active_production_sites(self) -> list[dict]:
        """Девять сайтов берутся из реестра, а не из списка в коде.

        Источник — `/api/v1/registry/snapshot`, каноническая проекция ACTIVE
        production. Фильтры `/api/v1/sites?environment=&lifecycle_state=`
        объявлены в OpenAPI, но провайдером ПОКА НЕ РЕАЛИЗОВАНЫ: он вернёт
        весь реестр, и потребитель посчитал бы одиннадцать записей девятью,
        включив демо и синтетику. Пока фильтры не реализованы, единственный
        честный источник числа девять — снимок.
        """
        снимок, _ = self.snapshot()
        return снимок.get("sites", [])

    def snapshot(self) -> tuple[dict, str | None]:
        к, т, h = self._get("/api/v1/registry/snapshot")
        if к != 200:
            raise ContractError(f"snapshot -> {к}")
        return т, h.get("ETag")

    # -------------------------------------------------------------- события
    def events(self, after: int = 0, limit: int = 100) -> dict:
        к, т, _ = self._get(f"/api/v1/events?after={after}&limit={limit}")
        if к != 200:
            raise ContractError(f"events -> {к}")
        return т

    def replay(self, after: int = 0, *, page: int = 100) -> Iterator[dict]:
        """Полный проход по ленте с durable-курсором на стороне вызывающего."""
        курсор = after
        while True:
            порция = self.events(курсор, page)
            элементы = порция.get("items") or []
            if not элементы:
                return
            for e in элементы:
                yield e
            новый = порция.get("next_cursor")
            if новый is None or новый == курсор:
                return
            курсор = новый

    # ------------------------------------------------------------ проверка
    @staticmethod
    def validate(запись: dict, обязательные: tuple[str, ...]) -> None:
        """Отсутствие обязательного поля — отказ; лишнее поле — не отказ.

        Терпимость к неизвестному обязательна: без неё любое аддитивное
        расширение производителя ломает всех потребителей разом.
        """
        нет = [п for п in обязательные if п not in запись]
        if нет:
            raise ContractError(f"нет обязательных полей: {нет}")
