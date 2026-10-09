"""REQ-SEO-REGULAR: реестр покрытия отличает «работает» от «наблюдается»."""

from __future__ import annotations

import datetime as dt

from seo_operator import coverage

NOW = dt.datetime(2026, 10, 9, 8, 0, tzinfo=dt.timezone.utc)


def _site(domain, ops=("facts", "prepare", "publish")):
    return {"domain": domain, "site_id": domain, "family": "x", "operations": list(ops)}


def _ok(domain):
    return {"domain": domain, "home_status": 200, "issues": []}


def _item(domain, slug, digest="d1", at="2026-10-08T10:00:00Z"):
    return {
        "domain": domain,
        "slug": slug,
        "url": f"https://{domain}/title/{slug}/",
        "digest": digest,
        "published_at": at,
    }


def _build(sites, **kw):
    args = {
        "availability": [],
        "published": [],
        "verdicts": {},
        "queue_items": [],
        "candidates": [],
        "analytics_props": [],
        "blockers": {},
        "cells": {},
        "now": NOW,
    }
    args.update(kw)
    return {r["domain"]: r for r in coverage.build(sites, **args)}


def test_работает_только_с_видимой_публикацией_текущего_текста():
    it = _item("a.ru", "t")
    rows = _build(
        [_site("a.ru")],
        availability=[_ok("a.ru")],
        published=[it],
        verdicts={it["url"]: {"verdict": "VISIBLE", "digest": "d1"}},
    )
    assert rows["a.ru"]["status"] == coverage.WORKING
    assert rows["a.ru"]["last_visible"]["url"] == it["url"]


def test_вердикт_прежней_версии_текста_не_засчитывается():
    it = _item("a.ru", "t", digest="new")
    rows = _build(
        [_site("a.ru")],
        availability=[_ok("a.ru")],
        published=[it],
        verdicts={it["url"]: {"verdict": "VISIBLE", "digest": "old"}},
        queue_items=[{"canonical_url": "https://a.ru/x", "status": "NEEDS_UPDATE"}],
    )
    assert rows["a.ru"]["visible"] == 0 and rows["a.ru"]["unchecked"] == 1
    assert rows["a.ru"]["status"] == coverage.NOT_CONNECTED


def test_записано_но_не_видно_это_блокер_а_не_успех():
    it = _item("g.site", "t")
    rows = _build(
        [_site("g.site")],
        availability=[_ok("g.site")],
        published=[it],
        verdicts={it["url"]: {"verdict": "TEXT_NOT_VISIBLE", "digest": "d1"}},
    )
    assert rows["g.site"]["status"] == coverage.BLOCKED
    assert "не видна" in rows["g.site"]["blocker"]


def test_первая_видимая_публикация_сегодня_подключён_сейчас():
    it = _item("a.ru", "t", at="2026-10-09T07:30:00Z")
    rows = _build(
        [_site("a.ru")],
        availability=[_ok("a.ru")],
        published=[it],
        verdicts={it["url"]: {"verdict": "VISIBLE", "digest": "d1"}},
    )
    assert rows["a.ru"]["status"] == coverage.CONNECTED_NOW


def test_наблюдение_аналитикой_не_делает_сайт_рабочим():
    rows = _build(
        [_site("m.ru", ops=("facts",))],
        availability=[_ok("m.ru")],
        analytics_props=[{"domain": "m.ru", "analytics_enabled": True, "counter_id": 1}],
    )
    assert rows["m.ru"]["monitored"] is True
    assert rows["m.ru"]["status"] == coverage.BLOCKED
    assert "нет операции публикации" in rows["m.ru"]["blocker"]


def test_недоступный_домен_и_ручной_блокер_с_доказательством():
    rows = _build(
        [_site("dns.ru"), _site("b.ru"), _site("c.ru")],
        availability=[
            {"domain": "dns.ru", "home_status": None, "issues": [{"code": "DNS_UNRESOLVED"}]},
            _ok("b.ru"),
            _ok("c.ru"),
        ],
        blockers={"b.ru": {"blocker": "мост падает", "evidence": "§11"}},
    )
    assert "DNS_UNRESOLVED" in rows["dns.ru"]["blocker"]
    assert rows["b.ru"]["blocker"] == "мост падает" and rows["b.ru"]["blocker_evidence"] == "§11"
    assert rows["c.ru"]["status"] == coverage.NO_TASKS


def test_блокер_без_доказательства_не_принимается(tmp_path):
    p = tmp_path / "b.json"
    p.write_text(
        '{"blockers": {"a.ru": {"blocker": "x"}, "b.ru": {"blocker": "y", ' '"evidence": "z"}}}',
        encoding="utf-8",
    )
    assert list(coverage.load_blockers(p)) == ["b.ru"]


def test_тестовые_сайты_не_входят_в_реестр():
    rows = _build([_site("site-a.localhost"), _site("pilot.localhost.test")])
    assert rows == {}


def test_таблица_называет_невидимые_и_разницу_с_наблюдением():
    it = _item("g.site", "t")
    rows = coverage.build(
        [_site("g.site")],
        availability=[_ok("g.site")],
        published=[it],
        verdicts={it["url"]: {"verdict": "TEXT_NOT_VISIBLE", "digest": "d1"}},
        queue_items=[],
        candidates=[],
        analytics_props=[],
        blockers={},
        cells={},
        now=NOW,
    )
    text = "\n".join(coverage.render(rows))
    assert "(+1 не видны)" in text and "работает на 0 из 1" in text
