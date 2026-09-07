"""REQ-SEO-FACTS: описательные сведения доезжают до контракта, а не теряются.

HANDOFF-046 от SEO: «описательных полей нет в каталоге — все четырнадцать
отсутствуют у всех записей». Измерение это подтвердило только наполовину.
Списочный ответ поставщика их правда не несёт: в снимке 53 257 записей есть
`year` (94,84 %) и разреженные `tags` (2,39 %), и больше ничего. Но detail их
несёт, обогащение по нему уже работает, и 12 022 ответа лежат на диске с
настоящими странами, жанрами, хронометражом и съёмочной группой.

Терялись они на последнем шаге: выгрузка контракта читала только кэш списка и
никогда не смотрела в кэш detail. Сведения были получены, сохранены и не
доезжали до потребителя ни в каком виде — а контракту и класть их было некуда.

Отсюда три правила, закреплённые здесь.

**Состояние отличает «не ходили» от «нет у источника».** Слить их в одно «нет»
значит предложить SEO ждать того, чего не будет, или бросить ждать того, что
придёт само.

**Сведения не появляются без происхождения.** Факт, происхождение которого
неизвестно, нельзя ни перепроверить, ни объяснить правообладателю.

**Ревизия меняется, когда меняются сведения.** Иначе потребитель, который
правильно кэширует по ревизии, не увидит ни жанров, ни описания, и охват
вырастет только в отчёте.
"""

from __future__ import annotations

import json

import pytest

from factory.site_engine import seo_binding as sb
from factory.site_engine.adapters import lords_seo_binding as ad

СНИМОК = "2026-09-07T00:00:00+00:00"


def запись(**over) -> dict:
    основа = {
        "external_id": "e-1",
        "name": "Одно название",
        "type": "movie",
        "is_series": False,
        "year": 2024,
        "external_ids": {"kinopoisk": "1"},
        "playback": {"aggregator": "kp", "title_id": "1"},
    }
    основа.update(over)
    return основа


def связать(записи):
    return ad.build(записи, site_id="lords-01", snapshot_at=СНИМОК,
                    provenance="стенд")


class TestСостояниеСведений:
    def test_необогащённая_запись_не_объявляется_пустой_у_источника(self):
        b = связать([запись()])[0]
        assert b.facts_state is sb.FactsState.NOT_ENRICHED, (
            "за записью не ходили, а контракт утверждает, что у источника ничего нет")
        assert b.descriptive_facts == {"year": 2024}, (
            "год из списка потерян: он единственное описательное поле, которое там есть")

    def test_опрошенная_и_пустая_запись_называется_прямо(self):
        b = связать([запись(**{ad.ПРИЗНАК_ДОПОЛНЕНИЯ: 1788690000.0, "year": None})])[0]
        assert b.facts_state is sb.FactsState.ABSENT_AT_SOURCE
        assert b.descriptive_facts == {}

    def test_один_год_не_выдаётся_за_дополнение(self):
        b = связать([запись(**{ad.ПРИЗНАК_ДОПОЛНЕНИЯ: 1.0})])[0]
        assert b.facts_state is sb.FactsState.ABSENT_AT_SOURCE, (
            "год из списка засчитан как результат дополнения")
        assert b.descriptive_facts == {"year": 2024}

    def test_сведения_переносятся_с_происхождением(self):
        b = связать([запись(genres=["драма"], countries=["США"], duration=124,
                            **{ad.ПРИЗНАК_ДОПОЛНЕНИЯ: 1.0})])[0]
        assert b.facts_state is sb.FactsState.ENRICHED
        assert b.descriptive_facts["genres"] == ["драма"]
        assert b.descriptive_facts["countries"] == ["США"]
        assert b.descriptive_facts["duration"] == 124
        assert b.facts_provenance, "сведения без происхождения непроверяемы"

    def test_пустые_значения_не_считаются_сведениями(self):
        b = связать([запись(year=None, genres=[], countries=[], description="",
                            **{ad.ПРИЗНАК_ДОПОЛНЕНИЯ: 1.0})])[0]
        assert b.facts_state is sb.FactsState.ABSENT_AT_SOURCE, (
            "пустой список жанров засчитан как жанры")
        assert b.descriptive_facts == {}

    def test_имена_полей_переведены_в_имена_контракта(self):
        b = связать([запись(seasons_count=3, original_name="Original",
                            premiere_date="2024-01-01")])[0]
        assert set(b.descriptive_facts) <= set(sb.DESCRIPTIVE_FACTS)
        assert b.descriptive_facts["seasonsCount"] == 3
        assert b.descriptive_facts["originalName"] == "Original"
        assert b.descriptive_facts["premiereDate"] == "2024-01-01"


class TestКонтрактНеДаётСоврать:
    def _правильная(self, **over):
        основа = {
            "site_id": "s", "content_id": "c", "external_ids": {},
            "route_id": "/title/x/", "page_type": "title",
            "canonical_path": "/title/x/",
            "content_kind": sb.ContentKind.MOVIE,
            "content_kind_state": sb.KindState.RESOLVED,
            "content_kind_provenance": "поставщик",
            "playback_state": sb.PlaybackState.UNKNOWN,
            "playback_reason_code": sb.ReasonCode.MISSING_PROVIDER_ID,
            "playback_observed_at": "", "content_revision": "rev",
            "binding_state": sb.BindingState.BOUND,
            "reason_codes": (sb.ReasonCode.OK,), "provenance": "стенд",
            "snapshot_at": СНИМОК,
        }
        основа.update(over)
        return sb.RouteBinding(**основа)

    def test_дополнение_без_единого_сведения_отвергается(self):
        with pytest.raises(sb.ContractViolation):
            self._правильная(facts_state=sb.FactsState.ENRICHED)

    def test_сведения_без_происхождения_отвергаются(self):
        with pytest.raises(sb.ContractViolation):
            self._правильная(facts_state=sb.FactsState.ENRICHED,
                             descriptive_facts={"year": 2024})

    def test_год_из_списка_совместим_с_отсутствием_дополнения(self):
        b = self._правильная(facts_state=sb.FactsState.ABSENT_AT_SOURCE,
                             descriptive_facts={"year": 2024},
                             facts_provenance="стенд")
        assert b.descriptive_facts == {"year": 2024}, (
            "год из списка нельзя выбросить только потому, что detail ничего не дал")

    def test_поле_вне_контракта_отвергается(self):
        with pytest.raises(sb.ContractViolation):
            self._правильная(facts_state=sb.FactsState.ENRICHED,
                             descriptive_facts={"budget": 1000},
                             facts_provenance="стенд")


class TestРевизияИВыгрузка:
    def test_появление_сведений_меняет_ревизию(self):
        было = sb.revision_of(запись())
        стало = sb.revision_of(запись(genres=["драма"]))
        assert было != стало, (
            "запись дополнили, а ревизия прежняя — потребитель по кэшу ничего не увидит")

    def test_сводка_несёт_знаменатель_по_состояниям(self):
        связи = связать([
            запись(external_id="a", genres=["драма"], **{ad.ПРИЗНАК_ДОПОЛНЕНИЯ: 1.0}),
            запись(external_id="b", name="Другое"),
            запись(external_id="c", name="Третье", year=None,
                   **{ad.ПРИЗНАК_ДОПОЛНЕНИЯ: 1.0}),
        ])
        итог = sb.envelope(связи, site_id="lords-01", snapshot_at=СНИМОК,
                           provenance="стенд")
        assert итог["byFactsState"] == {"ENRICHED": 1, "NOT_ENRICHED": 1,
                                        "ABSENT_AT_SOURCE": 1}
        assert sum(итог["byFactsState"].values()) == итог["records"]

    def test_сведения_видны_в_словаре_записи(self):
        b = связать([запись(genres=["драма"], **{ad.ПРИЗНАК_ДОПОЛНЕНИЯ: 1.0})])[0]
        d = b.as_dict()
        assert d["descriptiveFacts"]["genres"] == ["драма"]
        assert d["factsState"] == "ENRICHED"
        assert d["factsProvenance"]
        assert "latest" not in json.dumps(d)


class TestВыгрузкаСливаетDetail:
    def _кэш(self, tmp_path, записи):
        каталог = tmp_path / "catalog.json"
        каталог.write_text(json.dumps({"items": записи, "fetched_at_ms": 1788690000000},
                                      ensure_ascii=False), encoding="utf-8")
        детали = tmp_path / "detail-cache"
        детали.mkdir()
        return каталог, детали

    def test_без_кэша_деталей_выгрузка_прежняя(self, tmp_path):
        каталог, _ = self._кэш(tmp_path, [запись()])
        итог = ad.export(каталог, site_id="lords-01")
        assert итог["bindings"][0]["factsState"] == "NOT_ENRICHED"
        assert "detail-cache" not in итог["provenance"]

    def test_сведения_из_кэша_доезжают_до_контракта(self, tmp_path):
        каталог, детали = self._кэш(tmp_path, [запись()])
        (детали / "e-1.json").write_text(json.dumps({
            "detail": {"_fetched_at": 1788690000.0, "genres": ["драма"],
                       "countries": ["США"], "duration": 124},
        }, ensure_ascii=False), encoding="utf-8")
        итог = ad.export(каталог, site_id="lords-01", detail_cache=детали)
        связь = итог["bindings"][0]
        assert связь["factsState"] == "ENRICHED"
        assert связь["descriptiveFacts"]["countries"] == ["США"]
        assert "detail-cache" in итог["provenance"], (
            "происхождение не называет второй источник сведений")

    def test_слияние_ничего_не_отнимает(self, tmp_path):
        каталог, детали = self._кэш(tmp_path, [запись(year=2024)])
        (детали / "e-1.json").write_text(json.dumps({
            "detail": {"_fetched_at": 1.0, "year": None, "genres": ["драма"],
                       "playback": {"aggregator": "подмена"}},
        }, ensure_ascii=False), encoding="utf-8")
        итог = ad.export(каталог, site_id="lords-01", detail_cache=детали)
        связь = итог["bindings"][0]
        assert связь["descriptiveFacts"]["year"] == 2024, "пустое поле detail затёрло год"
        assert связь["playbackReasonCode"] != "подмена"

    def test_detail_не_меняет_адрес_и_вид_произведения(self, tmp_path):
        """Ответ detail несёт `name`, `type`, `tags`, `is_series`.

        Это ровно то, из чего считаются адрес страницы и вид произведения.
        Слить их «как есть» значит поменять маршруты двенадцати тысячам
        записей и развести коллизии адресов из-за того, что второй ответ
        источника назвал фильм чуть иначе. Проверяется, что не меняет.
        """
        каталог, детали = self._кэш(tmp_path, [запись()])
        (детали / "e-1.json").write_text(json.dumps({
            "detail": {
                "_fetched_at": 1.0,
                "name": "Совсем другое название",
                "type": "series",
                "is_series": True,
                "tags": ["anime"],
                "genres": ["драма"],
            },
        }, ensure_ascii=False), encoding="utf-8")

        без = ad.export(каталог, site_id="lords-01")["bindings"][0]
        со = ad.export(каталог, site_id="lords-01", detail_cache=детали)["bindings"][0]

        assert со["routeId"] == без["routeId"], "detail переписал адрес страницы"
        assert со["displayTitle"] == без["displayTitle"], "detail переписал название"
        assert со["contentKind"] == без["contentKind"], "detail переписал вид произведения"
        assert со["descriptiveFacts"]["genres"] == ["драма"], "жанры при этом потеряны"

    def test_битый_файл_не_ломает_выгрузку_и_не_врёт_про_источник(self, tmp_path):
        каталог, детали = self._кэш(tmp_path, [запись()])
        (детали / "e-1.json").write_text("{не json", encoding="utf-8")
        итог = ad.export(каталог, site_id="lords-01", detail_cache=детали)
        assert итог["bindings"][0]["factsState"] == "NOT_ENRICHED", (
            "битый файл засчитан как опрошенный источник")

    def test_повторная_выгрузка_даёт_тот_же_отпечаток(self, tmp_path):
        каталог, детали = self._кэш(tmp_path, [запись()])
        (детали / "e-1.json").write_text(json.dumps({
            "detail": {"_fetched_at": 1.0, "genres": ["драма"]}}), encoding="utf-8")
        первый = ad.export(каталог, site_id="lords-01", detail_cache=детали)
        второй = ad.export(каталог, site_id="lords-01", detail_cache=детали)
        assert первый["digest"] == второй["digest"]
