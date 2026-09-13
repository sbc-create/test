"""Пакет фактов: неизменяемость, происхождение, конфликт, отпечаток."""
from __future__ import annotations

import dataclasses

import pytest

from factory.seo_content.testing import ВРЕМЯ, пакет_тайтла, факт
from factory.seo_content.factpack import (ConflictStatus, Fact, FactPackError,
                                          SEOFactPack, from_event)


class TestЗначениеБезИсточникаНевозможно:
    def test_факт_без_источника_не_создаётся(self):
        with pytest.raises(FactPackError) as e:
            Fact(fact_id="f1", source_id="", provider="p", retrieved_at=ВРЕМЯ,
                 snapshot_hash="h", field_path="/year", value=2020,
                 confidence=1.0)
        assert e.value.code == "FACT_PROVENANCE_INCOMPLETE"

    def test_событие_без_источника_не_собирается(self):
        событие = {"event_type": "title.created", "event_id": "e",
                   "site_id": "s", "entity_id": "t", "title_id": "t",
                   "facts": [{"field_path": "/year", "value": 2020}]}
        with pytest.raises(FactPackError) as e:
            from_event(событие)
        assert e.value.code == "FACT_PROVENANCE_INCOMPLETE"
        assert "без source_id" in e.value.detail or "source_id" in e.value.detail

    def test_поля_без_факта_просто_нет(self):
        p = пакет_тайтла()
        assert p.value("/episode_display_number") is None
        assert p.fact_id_for("/episode_display_number") is None

    def test_неизвестный_путь_отвергается(self):
        with pytest.raises(FactPackError) as e:
            факт("f1", "/rating_from_model", 9.5)
        assert e.value.code == "FIELD_PATH_UNKNOWN"


class TestКонфликтИсточников:
    def test_два_значения_одного_поля_не_дают_значения(self):
        факты = [ф for ф in пакет_тайтла().facts if ф.field_path != "/year"]
        факты += [факт("f-y1", "/year", 2014, source_id="a"),
                  факт("f-y2", "/year", 2015, source_id="b")]
        p = dataclasses.replace(пакет_тайтла(), facts=tuple(факты))
        assert p.value("/year") is None
        assert "/year" in p.conflicts()

    def test_явный_конфликт_скрывает_значение_даже_при_совпадении(self):
        факты = [ф for ф in пакет_тайтла().facts if ф.field_path != "/year"]
        факты += [факт("f-y1", "/year", 2014, source_id="a",
                       conflict="CONFLICT")]
        p = dataclasses.replace(пакет_тайтла(), facts=tuple(факты))
        assert p.value("/year") is None
        assert "/year" in p.conflicts()

    def test_вытесненный_снимок_не_участвует(self):
        факты = [ф for ф in пакет_тайтла().facts if ф.field_path != "/year"]
        факты += [факт("f-old", "/year", 2014, source_id="a",
                       conflict="SUPERSEDED"),
                  факт("f-new", "/year", 2019, source_id="a")]
        p = dataclasses.replace(пакет_тайтла(), facts=tuple(факты))
        assert p.value("/year") == 2019
        assert p.conflicts() == ()


class TestОтпечатокИРевизии:
    def test_одинаковое_содержимое_даёт_одинаковый_отпечаток(self):
        assert пакет_тайтла().sha256 == пакет_тайтла().sha256

    def test_событие_не_входит_в_отпечаток(self):
        """Повторная доставка того же содержимого другим событием обязана
        дать тот же отпечаток: иначе дубль события породил бы новую ревизию
        текста без изменения фактов."""
        а = пакет_тайтла()
        б = dataclasses.replace(а, event_id="ev-другое")
        assert а.sha256 == б.sha256

    def test_правка_факта_меняет_отпечаток(self):
        а = пакет_тайтла()
        факты = [ф for ф in а.facts if ф.field_path != "/year"]
        факты.append(факт("f-year", "/year", 2020))
        б = dataclasses.replace(а, facts=tuple(факты))
        assert а.sha256 != б.sha256

    def test_новая_ревизия_не_трогает_прежнюю(self):
        а = пакет_тайтла()
        отпечаток = а.sha256
        б = а.with_facts(а.facts[:3], event_type="title.updated",
                         event_id="ev-2")
        assert б.version == а.version + 1
        assert а.sha256 == отпечаток

    def test_пакет_неизменяем(self):
        p = пакет_тайтла()
        with pytest.raises(dataclasses.FrozenInstanceError):
            p.site_id = "другой"


class TestСобытия:
    @pytest.mark.parametrize("тип,сущность", [
        ("title.created", "title"), ("title.updated", "title"),
        ("season.created", "season"), ("season.updated", "season"),
        ("episode.created", "episode"), ("episode.updated", "episode"),
    ])
    def test_каждое_событие_определяет_сущность(self, тип, сущность):
        событие = {"event_type": тип, "event_id": "e", "site_id": "s",
                   "entity_id": "x", "title_id": "t", "season_id": "s1",
                   "episode_id": "e1",
                   "facts": [{"fact_id": "f1", "source_id": "a",
                              "provider": "p", "retrieved_at": ВРЕМЯ,
                              "snapshot_hash": "h",
                              "field_path": "/canonical_title_ru",
                              "value": "Х"}]}
        assert from_event(событие).entity_type == сущность

    def test_правка_метаданных_обязана_назвать_сущность(self):
        """`metadata.corrected` адресуется той сущности, которую правят.
        Догадаться за отправителя нельзя: правка года тайтла и правка номера
        серии — разные записи."""
        событие = {"event_type": "metadata.corrected", "event_id": "e",
                   "site_id": "s", "entity_id": "x", "title_id": "t",
                   "facts": []}
        with pytest.raises(FactPackError) as err:
            from_event(событие)
        assert err.value.code == "ENTITY_TYPE_REQUIRED"

    def test_правка_метаданных_с_сущностью_проходит(self):
        событие = {"event_type": "metadata.corrected", "entity_type": "title",
                   "event_id": "e", "site_id": "s", "entity_id": "x",
                   "title_id": "t", "version": 2, "facts": []}
        p = from_event(событие)
        assert p.entity_type == "title" and p.version == 2


class TestИсточникиИЛицензии:
    def test_лицензия_известна_по_каждому_источнику(self):
        p = пакет_тайтла()
        for источник in p.sources():
            assert источник["source_license"]

    def test_отсутствие_лицензии_не_означает_свободно(self):
        ф = Fact(fact_id="f", source_id="s", provider="p", retrieved_at=ВРЕМЯ,
                 snapshot_hash="h", field_path="/year", value=2020,
                 confidence=1.0)
        assert ф.source_license == "UNKNOWN"
