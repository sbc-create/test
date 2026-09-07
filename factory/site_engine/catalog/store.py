"""Нормализованное хранилище — единственный владелец сведений о содержимом.

Кто угодно может читать. Писать может только `content-ingestion`, и это не
соглашение, а проверяемое свойство: запись требует токена, который выдаётся
прогону обхода.

Хранилище намеренно не знает про базу данных. Реализация в памяти достаточна
для API-каркаса и для тестов, а промышленная реализация подключается тем же
интерфейсом — ровно ради этого он и отделён.
"""
from __future__ import annotations

import threading
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from factory.site_engine.contracts import ContractError, CoverageReport, Title, utc_now


class TitleNotFound(ContractError):
    pass


class WriteNotPermitted(ContractError):
    """Писать в чужое хранилище нельзя, даже с добрыми намерениями."""


@dataclass(frozen=True)
class WriteToken:
    """Право на запись, выданное конкретному прогону обхода.

    Существует, чтобы «один модуль не пишет напрямую в файлы или таблицы
    другого» было выражено кодом. Витрина такого токена не получает нигде.
    """

    run_id: str
    site_id: str


@dataclass(frozen=True)
class Page:
    """Страница выдачи. Молчаливое усечение запрещено, поэтому `total` обязателен."""

    items: tuple[Title, ...]
    total: int
    offset: int
    limit: int

    @property
    def has_more(self) -> bool:
        return self.offset + len(self.items) < self.total


@runtime_checkable
class NormalizedStore(Protocol):
    def get(self, canonical_id: str) -> Title: ...
    def query(self, *, offset: int = 0, limit: int = 24, **filters) -> Page: ...
    def count(self) -> int: ...


MAX_LIMIT = 100


class InMemoryStore:
    """Реализация в памяти. Потокобезопасна, потому что обход идёт в фоне."""

    def __init__(self, site_id: str) -> None:
        self.site_id = site_id
        self._titles: dict[str, Title] = {}
        self._order: list[str] = []
        self._lock = threading.RLock()
        self._source_total: int | None = None

    # ----------------------------------------------------------------- чтение
    def get(self, canonical_id: str) -> Title:
        try:
            return self._titles[canonical_id]
        except KeyError:
            raise TitleNotFound(f"тайтла {canonical_id} нет в хранилище {self.site_id}") from None

    def count(self) -> int:
        return len(self._titles)

    def query(
        self,
        *,
        offset: int = 0,
        limit: int = 24,
        genre: str | None = None,
        year: int | None = None,
        kind: str | None = None,
        watchable: bool | None = None,
    ) -> Page:
        if offset < 0:
            raise ContractError("offset не может быть отрицательным")
        if limit < 1:
            raise ContractError("limit меньше единицы бессмысленен")
        # Верхний предел есть и он назван. Молча отдать меньше запрошенного —
        # это и есть тихое усечение, из-за которого каталог однажды выглядел
        # полным на четверти записей.
        limit = min(limit, MAX_LIMIT)
        with self._lock:
            titles = [self._titles[key] for key in self._order]
        if genre:
            titles = [t for t in titles if genre in t.genres]
        if year is not None:
            titles = [t for t in titles if t.year == year]
        if kind:
            titles = [t for t in titles if t.kind == kind]
        if watchable is not None:
            titles = [
                t for t in titles if bool(t.playback and t.playback.available) is watchable
            ]
        total = len(titles)
        return Page(items=tuple(titles[offset : offset + limit]), total=total,
                    offset=offset, limit=limit)

    def coverage(self) -> CoverageReport:
        return CoverageReport(
            site_id=self.site_id,
            source_total=self._source_total,
            local_total=len(self._titles),
            observed_at=utc_now(),
        )

    # ------------------------------------------------------------------ запись
    def put(self, token: WriteToken, titles: Iterable[Title]) -> int:
        self._check(token)
        written = 0
        with self._lock:
            for title in titles:
                if title.canonical_id not in self._titles:
                    self._order.append(title.canonical_id)
                self._titles[title.canonical_id] = title
                written += 1
        return written

    def declare_source_total(self, token: WriteToken, total: int | None) -> None:
        """Сколько записей обещает источник. Без этого числа полнота недоказуема."""
        self._check(token)
        self._source_total = total

    def _check(self, token: WriteToken) -> None:
        if not isinstance(token, WriteToken) or token.site_id != self.site_id:
            raise WriteNotPermitted(
                f"запись в хранилище {self.site_id} без токена его прогона обхода"
            )

    def __iter__(self) -> Iterator[Title]:
        with self._lock:
            return iter([self._titles[key] for key in self._order])
