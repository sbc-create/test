"""Фикстуры проверок контура качества SEO-контента.

Все хранилища эфемерные и живут в `tmp_path`. Общий Changeset Store здесь не
открывается ни на чтение состояния, ни на запись — у контура своя база, и
отдельная проверка подтверждает это измерением, а не обещанием.

Построители пакетов лежат в `factory.seo_content.testing`: тесты собираются в
режиме importlib, и модуль из каталога тестов оттуда не импортируется.
"""
from __future__ import annotations

import json
import pathlib

import pytest

from factory.seo_content import identity as ID
from factory.seo_content import store as ST
from factory.seo_content.pipeline import ContentPipeline, SiteContext

ФИКСТУРЫ = pathlib.Path(__file__).parent / "fixtures"


@pytest.fixture()
def витрина() -> SiteContext:
    return SiteContext(site_id="seo-test-0001",
                       site_url="https://seo-test-0001.invalid",
                       own_angle="разбор устройства произведения")


@pytest.fixture()
def маршрут_тайтла() -> ID.Route:
    return ID.Route(url="/title/tihaya-gavan/",
                    resolved_entity_id="title-0001",
                    canonical="/title/tihaya-gavan/",
                    breadcrumbs=("Главная", "Сериалы", "Тихая гавань"))


@pytest.fixture()
def соединение(tmp_path):
    соед = ST.открыть(tmp_path / "seo-drafts.sqlite3")
    yield соед
    соед.close()


@pytest.fixture()
def конвейер() -> ContentPipeline:
    return ContentPipeline()


@pytest.fixture(scope="session")
def golden() -> dict:
    return json.loads((ФИКСТУРЫ / "golden.json").read_text("utf-8"))


@pytest.fixture(scope="session")
def holdout() -> dict:
    return json.loads((ФИКСТУРЫ / "holdout.json").read_text("utf-8"))
