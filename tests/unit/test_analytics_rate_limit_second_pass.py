"""REQ-ANALYTICS-429: домен, упавший на квоте, дособирается вторым проходом.

B034. Измерено 18.10: из 462 показателей не измерены 156, и 14 из них — по
частоте запросов (`metrika: HTTP 429`) у zonafilm12.site и zonafilm.space.
Из сравнения недели эти домены выпали целиком, притом что остальные 306
показателей собрались. Один проход теряет домены тем вероятнее, чем дальше они
стоят в реестре, и потеря выглядит как отсутствие трафика.

Свойства второго прохода, от которых зависит его смысл:

* повторяются ТОЛЬКО отказы по квоте. «Счётчик не создан» и «сеть недоступна»
  за минуту не меняются, а повтор по ним тратит ту самую квоту, которой не
  хватило;
* пауза перед повтором больше окна транспорта (он уже повторял пять раз с
  задержкой до 30 с), иначе повтор попадёт в тот же лимит;
* результат принимается, только если измерил БОЛЬШЕ: иначе остаётся первый, а
  отчёт говорит, что попыток было две;
* отчёт несёт блок о повторе ВСЕГДА: «повторов не было» и «повтор не помог» —
  разные состояния.
"""
from __future__ import annotations

import pytest

from factory.errors import BlockedAnalyticsAccess
from seo_operator import analytics_collect as АС


class _Сбор:
    """Подделка результата `collect_domain` с нужным составом показателей."""

    def __init__(self, домен: str, измерено: int, причина: str = ""):
        self.domain = домен
        self.measurements = []
        for н in range(измерено):
            self.measurements.append(
                АС.Measurement(key=f"m{н}", title="t", measured=True,
                               value=1, source="s"))
        if причина:
            self.measurements.append(
                АС.Measurement(key="mx", title="t", measured=False,
                               reason=причина, source="s"))

    def as_dict(self) -> dict:
        return {"domain": self.domain,
                "measured_count": sum(1 for м in self.measurements if м.measured),
                "total_count": len(self.measurements),
                "measurements": [м.as_dict() for м in self.measurements]}


@pytest.fixture
def стенд(monkeypatch):
    """Реестр из трёх доменов и управляемый `collect_domain`."""
    домены = [{"domain": "a.site"}, {"domain": "b.site"}, {"domain": "c.site"}]
    monkeypatch.setattr(АС.registry, "load", lambda: {"properties": домены})
    monkeypatch.setattr(АС, "YandexAnalyticsProvider", lambda **к: object())
    состояние = {"вызовы": [], "паузы": []}

    def собрать(план: dict):
        def collect_domain(provider, entry, *, date1, date2):
            домен = entry["domain"]
            состояние["вызовы"].append(домен)
            шаги = план.get(домен)
            if isinstance(шаги, list):
                шаг = шаги.pop(0) if шаги else шаги
            else:
                шаг = шаги
            if isinstance(шаг, Exception):
                raise шаг
            return шаг
        monkeypatch.setattr(АС, "collect_domain", collect_domain)
    состояние["план"] = собрать
    состояние["сон"] = lambda сек: состояние["паузы"].append(сек)
    return состояние


def test_повтор_только_по_квоте(стенд):
    """Отрицательный контроль: 'счётчик не создан' и 'сеть недоступна' не повторяются."""
    стенд["план"]({
        "a.site": _Сбор("a.site", 3),
        "b.site": _Сбор("b.site", 0, "счётчик Метрики не создан"),
        "c.site": _Сбор("c.site", 1, "webmaster: сеть недоступна (URLError)"),
    })
    отчёт = АС.collect(sleep=стенд["сон"])
    assert стенд["вызовы"] == ["a.site", "b.site", "c.site"], "второго прохода нет"
    assert отчёт["rate_limit_retry"]["domains"] == []
    assert стенд["паузы"] == [], "паузы без повтора быть не должно"


def test_домен_под_квотой_дособирается(стенд):
    стенд["план"]({
        "a.site": _Сбор("a.site", 3),
        "b.site": [_Сбор("b.site", 1, "metrika: HTTP 429"), _Сбор("b.site", 4)],
        "c.site": _Сбор("c.site", 2),
    })
    отчёт = АС.collect(sleep=стенд["сон"])
    assert стенд["вызовы"] == ["a.site", "b.site", "c.site", "b.site"]
    b = [д for д in отчёт["domains"] if д["domain"] == "b.site"][0]
    assert b["measured_count"] == 4, "принят результат второго прохода"
    запись = отчёт["rate_limit_retry"]["results"]["b.site"]
    assert запись == {"before": 1, "after": 4, "helped": True,
                      "note": "второй проход измерил больше — принят"}


def test_неудачный_повтор_не_ухудшает_отчёт(стенд):
    """Если второй проход измерил не больше — остаётся первый, попыток две."""
    стенд["план"]({
        "a.site": [_Сбор("a.site", 2, "metrika: HTTP 429"),
                   _Сбор("a.site", 0, "metrika: HTTP 429")],
        "b.site": _Сбор("b.site", 1),
        "c.site": _Сбор("c.site", 1),
    })
    отчёт = АС.collect(sleep=стенд["сон"])
    a = [д for д in отчёт["domains"] if д["domain"] == "a.site"][0]
    assert a["measured_count"] == 2, "первый результат сохранён"
    запись = отчёт["rate_limit_retry"]["results"]["a.site"]
    assert запись["helped"] is False and запись["after"] == 0
    assert "попыток две" in запись["note"]


def test_отказ_второго_прохода_не_роняет_сбор(стенд):
    стенд["план"]({
        "a.site": [_Сбор("a.site", 2, "metrika: HTTP 429"),
                   BlockedAnalyticsAccess("metrika: HTTP 429",
                                          field="analytics.metrika",
                                          required_input="квота",
                                          blocks_stage="VALIDATING")],
        "b.site": _Сбор("b.site", 1),
        "c.site": _Сбор("c.site", 1),
    })
    отчёт = АС.collect(sleep=стенд["сон"])
    a = [д for д in отчёт["domains"] if д["domain"] == "a.site"][0]
    assert a["measured_count"] == 2
    запись = отчёт["rate_limit_retry"]["results"]["a.site"]
    assert запись["helped"] is False and запись["after"] is None
    assert "не состоялся" in запись["note"]


def test_пауза_больше_окна_транспорта(стенд):
    """Мгновенный повтор попал бы в тот же лимит: транспорт ждал до 30 с."""
    стенд["план"]({
        "a.site": [_Сбор("a.site", 1, "metrika: HTTP 429"), _Сбор("a.site", 2)],
        "b.site": _Сбор("b.site", 1),
        "c.site": _Сбор("c.site", 1),
    })
    АС.collect(sleep=стенд["сон"])
    assert стенд["паузы"] == [АС.ПАУЗА_ВТОРОГО_ПРОХОДА_С]
    assert АС.ПАУЗА_ВТОРОГО_ПРОХОДА_С > 30


def test_повтор_можно_выключить(стенд):
    """Сухому прогону и проверкам повтор не нужен — он только тратит время."""
    стенд["план"]({
        "a.site": _Сбор("a.site", 1, "metrika: HTTP 429"),
        "b.site": _Сбор("b.site", 1),
        "c.site": _Сбор("c.site", 1),
    })
    отчёт = АС.collect(retry_rate_limited=False, sleep=стенд["сон"])
    assert стенд["вызовы"] == ["a.site", "b.site", "c.site"]
    assert отчёт["rate_limit_retry"]["enabled"] is False
    assert стенд["паузы"] == []


def test_отчёт_всегда_несёт_блок_о_повторе(стенд):
    стенд["план"]({"a.site": _Сбор("a.site", 1),
                   "b.site": _Сбор("b.site", 1),
                   "c.site": _Сбор("c.site", 1)})
    отчёт = АС.collect(sleep=стенд["сон"])
    блок = отчёт["rate_limit_retry"]
    assert блок["enabled"] is True and блок["domains"] == []
    assert блок["results"] == {}, "«повторов не было» отличимо от «не помог»"


def test_итог_не_измеренных_остаётся_честным(стенд):
    стенд["план"]({
        "a.site": [_Сбор("a.site", 1, "metrika: HTTP 429"), _Сбор("a.site", 2)],
        "b.site": _Сбор("b.site", 0, "счётчик Метрики не создан"),
        "c.site": _Сбор("c.site", 1),
    })
    отчёт = АС.collect(sleep=стенд["сон"])
    # a: 2 измерено из 2 (второй проход), b: 0 из 1, c: 1 из 1.
    assert отчёт["summary"]["measured"] == 3
    assert отчёт["summary"]["not_measured"] == 1
    assert "Это не нули" in отчёт["summary"]["note"]
