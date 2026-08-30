"""Обрыв каталога не должен выглядеть как успешное обновление.

Обход останавливался на двухсотой странице и возвращал результат как ни в чём
не бывало. Поле `stopped_by` при этом честно записывало «max_pages», но его
никто не проверял: 48 315 записей из 53 115 просто не существовали для витрины,
и ни один гейт об этом не говорил.

Отдельно проверяется размер страницы: контракт разрешает сто записей, а обход
просил двадцать четыре — вчетверо больше запросов ради вчетверо меньших данных.
"""
from __future__ import annotations

import pytest

from factory.lords import content_live
from factory.lords.content_live import SourceError


class FakeFetcher:
    """Источник с известным числом страниц."""

    def __init__(self, contract, pages: int, per_page: int = 100):
        self.contract = contract
        self.pages = pages
        self.per_page = per_page
        self.requested_sizes: list[str] = []
        self.calls = 0

    def get_json(self, url: str) -> dict:
        self.calls += 1
        # Запоминаем, какой размер страницы попросили.
        for part in url.split("?", 1)[-1].split("&"):
            if part.startswith(f"{self.contract.size_param}="):
                self.requested_sizes.append(part.split("=", 1)[1])
        page = self.calls
        items = [{"id": f"t{page}-{i}", "name": f"Запись {page}-{i}"} for i in range(self.per_page)]
        has_more = page < self.pages
        return {
            "items": items,
            "has_more": has_more,
            "next_cursor": f"cursor-{page}" if has_more else "",
            "total": self.pages * self.per_page,
        }


@pytest.fixture()
def contract():
    return content_live.load_live_contract()


class TestPageSize:
    def test_walk_asks_for_the_largest_allowed_page(self, contract):
        """Контракт разрешает сто записей — просить меньше значит платить
        вчетверо большим числом запросов за тот же каталог."""
        fetcher = FakeFetcher(contract, pages=2)
        content_live.walk_pages(fetcher, "https://example.test/titles")
        assert fetcher.requested_sizes, "размер страницы не передан вовсе"
        assert fetcher.requested_sizes[0] == str(contract.max_size)


class TestTruncationIsNotSuccess:
    def test_reaching_the_page_limit_raises(self, contract):
        """Достижение защитного предела — не конец каталога."""
        fetcher = FakeFetcher(contract, pages=contract.max_pages + 50)
        with pytest.raises(SourceError) as caught:
            content_live.walk_pages(fetcher, "https://example.test/titles")
        assert "обрыв" in str(caught.value).lower() or "предел" in caught.value.reason.lower()

    def test_natural_end_is_not_an_error(self, contract):
        fetcher = FakeFetcher(contract, pages=3)
        walk = content_live.walk_pages(fetcher, "https://example.test/titles")
        assert walk.stopped_by == "has_more"
        assert len(walk.items) == 300

    def test_catalog_larger_than_the_old_cap_is_walked_whole(self, contract):
        """Прежний предел давал ровно 4800 записей. Каталог больше — не обрыв."""
        fetcher = FakeFetcher(contract, pages=100)
        walk = content_live.walk_pages(fetcher, "https://example.test/titles")
        assert len(walk.items) == 10_000
        assert len(walk.items) > 4800

    def test_more_than_two_hundred_pages(self, contract):
        assert contract.max_pages > 200, "предела в 200 страниц не хватает на этот каталог"
        fetcher = FakeFetcher(contract, pages=250)
        walk = content_live.walk_pages(fetcher, "https://example.test/titles")
        assert walk.stopped_by == "has_more"
        assert len(walk.items) == 25_000

    def test_cursor_absent_ends_the_walk(self, contract):
        class NoCursor(FakeFetcher):
            def get_json(self, url):
                self.calls += 1
                return {"items": [{"id": "a", "name": "Запись"}], "has_more": True, "next_cursor": ""}

        walk = content_live.walk_pages(NoCursor(contract, pages=1), "https://example.test/titles")
        assert walk.stopped_by == "cursor_absent"


class TestLimitCoversTheRealCatalog:
    def test_the_limit_leaves_room_for_the_measured_catalog(self, contract):
        """Каталог источника — 53 115 записей на момент замера.

        Предел обязан оставлять запас: упереться в него значит снова обрезать
        каталог, теперь уже с ошибкой вместо тишины, но всё равно обрезать.
        """
        measured = 53_115
        capacity = contract.max_pages * contract.max_size
        assert capacity > measured * 1.2, (
            f"предел {capacity} записей при каталоге {measured} — запаса нет"
        )
