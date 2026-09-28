"""REQ-REVIEW-BUILD: очередь разбора наполняется из каталога.

Очередь разбора умеет читать, решать, утверждать, публиковать и откатывать — но
**ничто её не наполняет**. Записи в ней появились однажды и вручную; пересчёт
каталога их не обновляет, а новый конфликт в новых данных не доходит до
редактора вовсе.

Для флота это существенно: у каждой витрины своя очередь, и заводить её руками
на каждом сайте — то же самое, что не иметь очереди.

Три правила.

**Решение редактора переживает пересборку.** Иначе повторный обход стирает
работу людей, и очередь становится опасной.

**Пересборка не выдумывает конфликтов.** В очередь попадает только то, что
названо противоречием: вид, спорный по данным поставщика, или название,
объявляющее эпизод при виде «фильм».

**Очередь принадлежит витрине.** Пересборка одной витрины не трогает записи
другой.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory.paths import PATHS

САЙТ = "js-site"
СОСЕД = "js-other"
REPO = Path(__file__).resolve().parents[2]
ENV = {"SITE_ENGINE_CATALOG_DIR": "var/lords/lords/catalog-cache"}

ЗАПИСИ = [
    {
        "external_id": "01a00000-0000-7000-8000-000000000001",
        "name": "Обычный фильм",
        "type": "movie",
        "tags": [],
    },
    {
        # Название объявляет эпизод, вид — фильм: противоречие записи самой себе.
        "external_id": "01a00000-0000-7000-8000-000000000002",
        "name": "Храбрые ведьмы: Эпизод 13",
        "type": "movie",
        "tags": [],
    },
    {
        # Тип поставщика против тега: спор в самих данных.
        "external_id": "01a00000-0000-7000-8000-000000000003",
        "name": "Спорная запись",
        "type": "movie",
        "tags": ["ova"],
    },
]


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setattr(PATHS, "root", tmp_path)
    профили = tmp_path / "config" / "site-profiles"
    профили.mkdir(parents=True)
    for сайт in (САЙТ, СОСЕД):
        (профили / f"{сайт}.json").write_text(
            json.dumps({"site_id": сайт, "domains": [f"{сайт}.test"]}, ensure_ascii=False),
            encoding="utf-8",
        )
    кэш = tmp_path / "var" / "lords" / "lords" / "catalog-cache"
    кэш.mkdir(parents=True)
    for сайт in (САЙТ, СОСЕД):
        (кэш / f"{сайт}.json").write_text(
            json.dumps({"fetched_at_ms": 0, "source": "t", "items": ЗАПИСИ}, ensure_ascii=False),
            encoding="utf-8",
        )
    for под in ("var/state", "var/audit", "var/locks"):
        (tmp_path / под).mkdir(parents=True, exist_ok=True)
    return tmp_path


class TestПересборка:
    def test_спорные_записи_попадают_в_очередь(self, sandbox):
        from factory.site_engine import review_build
        from factory.site_engine.review_queue import ReviewQueue

        итог = review_build.rebuild(sandbox, САЙТ, env=ENV)
        assert итог["created"] >= 2, итог
        очередь = ReviewQueue(sandbox).list(limit=50)
        коды = {э["conflictCode"] for э in очередь["items"]}
        assert "KIND_CONTRADICTS_TITLE" in коды
        assert итог["scanned"] == len(ЗАПИСИ)

    def test_бесспорная_запись_в_очередь_не_попадает(self, sandbox):
        from factory.site_engine import review_build
        from factory.site_engine.review_queue import ReviewQueue

        review_build.rebuild(sandbox, САЙТ, env=ENV)
        очередь = ReviewQueue(sandbox).list(limit=50)
        сущности = {э["internalEntityId"] for э in очередь["items"]}
        assert f"{САЙТ}:{ЗАПИСИ[0]['external_id']}" not in сущности

    def test_у_записи_есть_оба_утверждения_и_основание(self, sandbox):
        from factory.site_engine import review_build
        from factory.site_engine.review_queue import ReviewQueue

        review_build.rebuild(sandbox, САЙТ, env=ENV)
        элемент = ReviewQueue(sandbox).list(limit=50)["items"][0]
        assert len(элемент["claims"]) >= 2, "спор без двух сторон — не спор"
        assert элемент["recommendationReason"], "рекомендация без основания бесполезна"

    def test_решение_переживает_пересборку(self, sandbox):
        from factory.site_engine import review_build
        from factory.site_engine.review_queue import ReviewQueue

        review_build.rebuild(sandbox, САЙТ, env=ENV)
        очередь = ReviewQueue(sandbox)
        элемент = очередь.list(limit=50)["items"][0]
        # Выбирается одно из утверждений источников: третье значение очередь
        # не принимает, и это правильно — третье было бы догадкой.
        значение = элемент["claims"][1]["value"]
        очередь.decide(
            элемент["itemId"], value=значение, actor="редактор",
            expected_version=элемент["version"], note="проверка",
        )
        повтор = review_build.rebuild(sandbox, САЙТ, env=ENV)
        assert повтор["created"] == 0, "повторная сборка не создаёт записей заново"
        после = очередь.get(элемент["itemId"])
        assert после.decided_value == значение, "пересборка стёрла решение редактора"

    def test_очередь_принадлежит_витрине(self, sandbox):
        from factory.site_engine import review_build
        from factory.site_engine.review_queue import ReviewQueue

        review_build.rebuild(sandbox, САЙТ, env=ENV)
        было = len(ReviewQueue(sandbox).list(limit=100)["items"])
        review_build.rebuild(sandbox, СОСЕД, env=ENV)
        стало = ReviewQueue(sandbox).list(limit=100)["items"]
        свои = [э for э in стало if э["siteId"] == САЙТ]
        assert len(свои) == было, "пересборка соседа тронула чужие записи"
        assert any(э["siteId"] == СОСЕД for э in стало)

    def test_нечитаемый_каталог_это_отказ_а_не_пустая_очередь(self, sandbox):
        from factory.site_engine import review_build

        with pytest.raises(review_build.ReviewBuildError):
            review_build.rebuild(sandbox, "нет-такой", env=ENV)


class TestМаршрут:
    def test_пересборка_доступна_через_api(self, sandbox):
        from factory.site_engine.api.control import ControlApi

        api = ControlApi(
            root=sandbox,
            env={
                "SITE_ENGINE_CONTROL_WRITES": "1",
                "SITE_ENGINE_CONTROL_TOKENS": "t=read,review:write",
                **ENV,
            },
        )
        ответ = api.handle(
            "POST", "/api/v1/review-queue/rebuild",
            headers={"Authorization": "Bearer t"}, body={"siteId": САЙТ},
        )
        assert ответ.status == 200, ответ.body
        assert ответ.body["created"] >= 2

    def test_без_права_разбора_отказ(self, sandbox):
        from factory.site_engine.api.control import ControlApi

        api = ControlApi(
            root=sandbox,
            env={
                "SITE_ENGINE_CONTROL_WRITES": "1",
                "SITE_ENGINE_CONTROL_TOKENS": "ro=read",
                **ENV,
            },
        )
        ответ = api.handle(
            "POST", "/api/v1/review-queue/rebuild",
            headers={"Authorization": "Bearer ro"}, body={"siteId": САЙТ},
        )
        assert ответ.status == 403
