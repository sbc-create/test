"""Описательные сведения доезжают не до функции, а до страницы ответа.

Выгрузка отдаётся потребителю постранично, и между сборкой связи и страницей
ответа есть слой, который выбирает поля. Проверка, что сведения переживают
этот слой: иначе контракт объявляет поле, а маршрут его не отдаёт.
"""

from __future__ import annotations

import json

import pytest

from factory.site_engine import seo_binding as sb
from factory.site_engine.api import seo_bindings as api


@pytest.fixture
def песочница(tmp_path):
    (tmp_path / "config").mkdir()
    (tmp_path / "var" / "lords" / "lords" / "catalog-cache").mkdir(parents=True)
    (tmp_path / "var" / "lords" / "detail-cache").mkdir(parents=True)

    (tmp_path / "config" / "seo-binding-sources.yaml").write_text(
        "version: \"1.0.0\"\n"
        "sites:\n"
        "  lords-01:\n"
        "    producer: computed-routes\n"
        "    catalog: var/lords/lords/catalog-cache/lords-01.json\n"
        "    detailCache: var/lords/detail-cache\n",
        encoding="utf-8")

    записи = [{
        "external_id": "e-1", "name": "Одно название", "type": "movie",
        "is_series": False, "year": 2024,
        "external_ids": {"kinopoisk": "1"},
        "playback": {"aggregator": "kp", "title_id": "1"},
    }]
    (tmp_path / "var" / "lords" / "lords" / "catalog-cache" / "lords-01.json").write_text(
        json.dumps({"items": записи, "fetched_at_ms": 1788690000000}, ensure_ascii=False),
        encoding="utf-8")
    (tmp_path / "var" / "lords" / "detail-cache" / "e-1.json").write_text(
        json.dumps({"detail": {"_fetched_at": 1.0, "genres": ["драма"],
                               "countries": ["США"], "voice_studios": ["Студия"]}},
                   ensure_ascii=False), encoding="utf-8")
    return tmp_path


def test_страница_ответа_несёт_сведения_и_их_происхождение(песочница):
    итог = api.выгрузка(песочница, "lords-01")
    assert итог["schemaVersion"] == sb.SCHEMA_VERSION
    связь = итог["bindings"][0]
    assert связь["factsState"] == "ENRICHED"
    assert связь["descriptiveFacts"]["genres"] == ["драма"]
    assert связь["descriptiveFacts"]["voiceStudios"] == ["Студия"]
    assert связь["factsProvenance"], "сведения пришли без происхождения"


def test_сводка_несёт_счёт_по_состояниям(песочница):
    итог = api.выгрузка(песочница, "lords-01")
    assert итог["byFactsState"] == {"ENRICHED": 1, "NOT_ENRICHED": 0,
                                    "ABSENT_AT_SOURCE": 0}


def test_кэш_замечает_пополнение_кэша_деталей(песочница):
    первый = api.выгрузка(песочница, "lords-01")
    (песочница / "var" / "lords" / "detail-cache" / "e-2.json").write_text(
        json.dumps({"detail": {"_fetched_at": 2.0, "genres": ["комедия"]}}),
        encoding="utf-8")
    второй = api.выгрузка(песочница, "lords-01")
    assert первый is not второй, (
        "кэш отдал прежний ответ: пополнение кэша деталей осталось незамеченным")
