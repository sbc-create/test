"""REQ-LORDS-SOURCE-OUTAGE: чужой отказ не выдаётся за собственную поломку.

3 сентября поставщик несколько минут отвечал 502. Цикл повёл себя правильно —
не опубликовал сомнительные данные и оставил витрину на прежнем релизе, — но
завершился как сломанный. При таком поведении настоящая поломка неотличима от
чужого отказа, и обе теряются среди ложных тревог.

Снисхождение действует, только пока последний удачный ответ ещё свеж. Как
только данные действительно стареют, отказ снова становится отказом.
"""

from __future__ import annotations

from factory.lords import content_live, live_build


def отчёт(status: str, age_ms, *, items: int = 53000) -> dict:
    сайт = {
        "status": status,
        "item_count": items,
        "cache_age_ms": age_ms,
        "sections_enabled": ["movies"],
        "playable_count": 10,
    }
    return {"sites": {"lords-01": dict(сайт), "lords-02": dict(сайт), "lords-03": dict(сайт)}}


class TestТерпимостьКОтказуИсточника:
    def test_свежий_кэш_при_недоступном_источнике_не_считается_поломкой(self):
        отч = отчёт(content_live.STALE, 5 * 60 * 1000)
        assert live_build.verify_report(отч), "статус STALE обязан оставаться замечанием"
        assert live_build.source_unavailable_but_fresh_enough(отч)

    def test_устаревший_кэш_снова_отказ(self):
        отч = отчёт(content_live.STALE, 2 * 60 * 60 * 1000)
        assert not live_build.source_unavailable_but_fresh_enough(отч)

    def test_неизвестный_возраст_кэша_снисхождения_не_даёт(self):
        # О том, чего не измерено, нельзя утверждать, что оно свежее.
        assert not live_build.source_unavailable_but_fresh_enough(отчёт(content_live.STALE, None))

    def test_пустой_каталог_снисхождения_не_даёт(self):
        отч = отчёт(content_live.STALE, 60 * 1000, items=0)
        assert not live_build.source_unavailable_but_fresh_enough(отч)

    def test_блокировка_источника_снисхождения_не_даёт(self):
        # BLOCKED_SOURCE означает, что и кэша нет: показывать нечего.
        отч = отчёт(content_live.BLOCKED_SOURCE, 60 * 1000)
        assert not live_build.source_unavailable_but_fresh_enough(отч)

    def test_если_хоть_один_сайт_не_на_кэше_снисхождения_нет(self):
        отч = отчёт(content_live.STALE, 60 * 1000)
        отч["sites"]["lords-02"]["status"] = content_live.BLOCKED_SOURCE
        assert not live_build.source_unavailable_but_fresh_enough(отч)

    def test_пустой_отчёт_снисхождения_не_даёт(self):
        assert not live_build.source_unavailable_but_fresh_enough({"sites": {}})
