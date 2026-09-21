"""Общая обвязка тестов единого модуля оценок.

Каждый тест получает свою временную БД. Ни один тест не открывает
production-базу: путь передаётся явно, значения по умолчанию не
используются, и это проверяется отдельным тестом.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from factory.community.service import CommunityVotesService
from factory.community.store import CommunityStore
from factory.unified_ratings.community import CommunityRatings
from factory.unified_ratings.store import UnifiedStore
from factory.unified_ratings.titles import CanonicalTitle, TitleRegistry


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "unified.sqlite"


@pytest.fixture
def store(db_path: Path) -> UnifiedStore:
    store = UnifiedStore(db_path)
    yield store
    store.close()


@pytest.fixture
def registry(store: UnifiedStore) -> TitleRegistry:
    return TitleRegistry(store)


@pytest.fixture
def sample_titles() -> list[CanonicalTitle]:
    return [
        CanonicalTitle(
            title_id="nova:t-001",
            content_kind="tv",
            title_ru="Ковбой Бибоп",
            title_original="Cowboy Bebop",
            release_year=1998,
            episode_count=26,
            external_ids={"myanimelist": "1", "imdb": "0213338"},
            catalog_source="nova",
        ),
        CanonicalTitle(
            title_id="nova:t-002",
            content_kind="movie",
            title_ru="Тайна пятого сезона",
            title_original="Fifth Season Mystery",
            release_year=2016,
            external_ids={"myanimelist": "2", "kinopoisk": "12345"},
            catalog_source="nova",
        ),
    ]


@pytest.fixture
def seeded(registry: TitleRegistry, sample_titles: list[CanonicalTitle]) -> TitleRegistry:
    registry.upsert_many(sample_titles)
    registry.map_tenant_subject(
        tenant_id="yummy", subject_id="s-001", title_id="nova:t-001"
    )
    registry.map_tenant_subject(
        tenant_id="animedia", subject_id="a-001", title_id="nova:t-001"
    )
    registry.map_tenant_subject(
        tenant_id="yummy", subject_id="s-002", title_id="nova:t-002"
    )
    return registry


@pytest.fixture
def community(store: UnifiedStore, seeded: TitleRegistry, tmp_path: Path) -> CommunityRatings:
    """Голоса пишутся в отдельную тестовую БД ledger, не в production."""
    ledger = CommunityStore(tmp_path / "community.sqlite")
    service = CommunityVotesService(ledger)
    yield CommunityRatings(store, service, registry=seeded)
    ledger.close()
