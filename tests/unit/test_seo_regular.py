"""REQ-SEO-REGULAR: регулярный прогон SEO-модуля по сети.

Проверяются свойства фонового запуска (блокировка, продолжение слота, бюджет,
повторы, журнал) и правила наблюдения: повторно прочитанный снимок не является
новым наблюдением, неделя сравнивается с непересекающейся неделей, о
сохраняющейся проблеме не уведомляют второй раз.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

from seo_operator import regular
from seo_operator.regular import Budget, Response

NOW = dt.datetime(2026, 10, 8, 5, 40, tzinfo=dt.timezone.utc)


class FakeHttp:
    """Ответы по адресу; неизвестный адрес — 404. Считает обращения."""

    def __init__(self, pages: dict[str, tuple[int | None, dict, bytes]] | None = None):
        self.pages = pages or {}
        self.calls: list[str] = []
        self.budget = Budget(60, 1000)
        self.journal = None

    def get(self, url: str, *, timeout: float | None = None) -> Response:
        self.budget.take_request()
        self.calls.append(url)
        status, headers, body = self.pages.get(url, (404, {}, b""))
        return Response(url, status, headers, body, 0.05)


HOME_OPEN = (
    200,
    {"x-robots-tag": "index, follow"},
    b'<html><head><link rel="canonical" href="https://a.example/"></head><body>ok</body></html>',
)
ROBOTS_OK = (200, {}, b"User-agent: *\nDisallow: /api/\nSitemap: https://a.example/sitemap.xml\n")


def _snapshot(day: str, visits: float, search: float, *, domain: str = "a.example") -> dict:
    return {
        "collected_at": f"{day}T06:15:00Z",
        "period": {"date1": "7daysAgo", "date2": "yesterday"},
        "domains": [
            {
                "domain": domain,
                "measurements": [
                    {"key": "visits", "measured": True, "value": visits},
                    {"key": "visitors", "measured": True, "value": visits - 1},
                    {
                        "key": "search_engines",
                        "measured": True,
                        "value": [{"dimensions": [{"name": "Yandex"}], "metrics": [search]}],
                    },
                    {
                        "key": "pages_in_search",
                        "measured": False,
                        "value": "не измерено",
                        "reason": "сайт не привязан к Вебмастеру",
                    },
                ],
            }
        ],
    }


@pytest.fixture
def env(tmp_path, monkeypatch):
    cells = tmp_path / "site-cells.json"
    cells.write_text(
        json.dumps(
            {
                "cells": [
                    {
                        "domain": "a.example",
                        "site_id": "a-01",
                        "indexing": {"open_authorized": True},
                    },
                    {"domain": "site-a.localhost", "site_id": "site-a"},
                ]
            }
        ),
        encoding="utf-8",
    )
    analytics = tmp_path / "analytics.json"
    analytics.write_text(
        json.dumps(
            {
                "properties": [
                    {"domain": "a.example", "counter_id": 1, "webmaster": {"host_id": None}}
                ]
            }
        ),
        encoding="utf-8",
    )
    indexing = tmp_path / "indexing"
    indexing.mkdir()
    (indexing / "a.example.json").write_text(
        json.dumps({"desired_state": "OPEN"}), encoding="utf-8"
    )
    snaps = tmp_path / "snapshots"
    snaps.mkdir()
    (snaps / "analytics-2026-10-01.json").write_text(
        json.dumps(_snapshot("2026-10-01", 100, 40)), encoding="utf-8"
    )
    (snaps / "analytics-2026-10-07.json").write_text(
        json.dumps(_snapshot("2026-10-07", 130, 55)), encoding="utf-8"
    )
    (snaps / "analytics-2026-10-08.json").write_text(
        json.dumps(_snapshot("2026-10-08", 140, 60)), encoding="utf-8"
    )
    monkeypatch.setattr(regular, "OVERLAY_ROOTS", {})
    sources = {
        "cells": cells,
        "analytics_registry": analytics,
        "analytics_snapshots": snaps,
        "indexing_states": indexing,
        "queue_registry": tmp_path / "registry.json",
        "queue_events": tmp_path / "queue_events.jsonl",
        "content_operator_state": tmp_path / "state.json",
        "defects": tmp_path / "defects.json",
        "changes_ledger": tmp_path / "seo-changes.json",
        "changes_ledger_runs": tmp_path / "editor-ledger.jsonl",
        "facts_snapshots": tmp_path / "facts",
        "coverage_sites": tmp_path / "coverage-sites.json",
        "coverage_blockers": tmp_path / "coverage-blockers.json",
    }
    sources["coverage_sites"].write_text(
        json.dumps(
            [
                {"domain": c["domain"], "site_id": c["site_id"], "operations": ["publish"]}
                for c in json.loads(cells.read_text(encoding="utf-8"))["cells"]
            ]
        ),
        encoding="utf-8",
    )
    return {"root": tmp_path / "state", "sources": sources, "tmp": tmp_path}


def _journal(root: Path) -> list[dict]:
    out = []
    for f in sorted((root / "journal").glob("*.jsonl")):
        out += [json.loads(line) for line in f.read_text(encoding="utf-8").splitlines()]
    return out


# ------------------------------------------------------------------ слоты


def test_slot_ids_are_stable_within_a_slot():
    # слот начинается в момент расписания: 05:25, 11:25, 17:25, 23:25 UTC
    assert regular.slot_id("check", NOW) == "check-2026-10-08T0525"
    assert regular.slot_id("check", NOW.replace(hour=5, minute=20)) == "check-2026-10-07T2325"
    # ручной запуск в 12:06 и плановый в 17:25 — разные слоты (случай 2026-10-08)
    assert regular.slot_id("check", NOW.replace(hour=12, minute=6)) == "check-2026-10-08T1125"
    assert (
        regular.slot_id("check", NOW.replace(hour=17, minute=25, second=4))
        == "check-2026-10-08T1725"
    )
    # 23:30 UTC 7 октября — это уже 8 октября по Москве
    late = dt.datetime(2026, 10, 7, 23, 30, tzinfo=dt.timezone.utc)
    assert regular.slot_id("daily", late) == "daily-2026-10-08"
    assert regular.slot_id("weekly", NOW) == "weekly-2026-W41"


# ----------------------------------------------------- фоновый запуск


def test_second_concurrent_run_exits_without_work(env):
    root = env["root"]
    root.mkdir(parents=True)
    regular.FileLock(root / "run.lock").acquire("other")
    http = FakeHttp({"https://a.example/": HOME_OPEN, "https://a.example/robots.txt": ROBOTS_OK})
    result = regular.run("check", root=root, now=NOW, sources=env["sources"], http=http)
    assert result["state"] == "LOCK_BUSY"
    assert result["exit_code"] == regular.EXIT_TEMPFAIL
    assert http.calls == []
    assert any(e["event"] == "lock_busy" for e in _journal(root))


def test_check_run_records_each_action_and_finishes(env):
    http = FakeHttp({"https://a.example/": HOME_OPEN, "https://a.example/robots.txt": ROBOTS_OK})
    result = regular.run(
        "check",
        root=env["root"],
        now=NOW,
        sources=env["sources"],
        http=http,
        trigger="systemd-timer",
    )
    assert result["state"] == "DONE", result
    assert result["exit_code"] == 0
    events = [e["event"] for e in _journal(env["root"])]
    assert events[0] == "run_started" and events[-1] == "run_finished"
    assert "domain_checked" in events
    # тестовые имена в обход не попадают
    assert all("localhost" not in url for url in http.calls)
    state = json.loads((env["root"] / "state.json").read_text(encoding="utf-8"))
    assert state["last_check"]["run_id"] == "check-2026-10-08T0525"
    assert state["runs"][-1]["trigger"] == "systemd-timer"


def test_rerun_of_a_finished_slot_does_nothing(env):
    http = FakeHttp({"https://a.example/": HOME_OPEN, "https://a.example/robots.txt": ROBOTS_OK})
    regular.run("check", root=env["root"], now=NOW, sources=env["sources"], http=http)
    calls = len(http.calls)
    again = regular.run("check", root=env["root"], now=NOW, sources=env["sources"], http=http)
    assert again["state"] == "ALREADY_DONE"
    assert len(http.calls) == calls


def test_interrupted_slot_resumes_from_first_unfinished_step(env, monkeypatch):
    http = FakeHttp({"https://a.example/": HOME_OPEN, "https://a.example/robots.txt": ROBOTS_OK})
    calls = {"n": 0}
    original = regular.step_analytics

    def broken(ctx):
        calls["n"] += 1
        raise RuntimeError("процесс прерван посреди шага")

    plan = [
        (name, broken if name == "analytics" else func) for name, func in regular.PLANS["check"]
    ]
    monkeypatch.setitem(regular.PLANS, "check", plan)
    monkeypatch.setattr(regular.time, "sleep", lambda _s: None)
    first = regular.run("check", root=env["root"], now=NOW, sources=env["sources"], http=http)
    assert first["state"] == "FAILED"
    assert calls["n"] == 2  # шаг повторён один раз перед отказом
    requests_after_first = len(http.calls)

    plan = [(name, original if name == "analytics" else func) for name, func in plan]
    monkeypatch.setitem(regular.PLANS, "check", plan)
    second = regular.run("check", root=env["root"], now=NOW, sources=env["sources"], http=http)
    assert second["state"] == "DONE"
    assert second["steps"]["discover"] == "resumed_skip"
    assert second["steps"]["availability"] == "resumed_skip"
    # проверка доступности не повторялась: новых запросов к главной нет
    assert http.calls[requests_after_first:].count("https://a.example/") == 0


def test_budget_exhaustion_is_partial_and_the_slot_continues(env, monkeypatch):
    http = FakeHttp({"https://a.example/": HOME_OPEN, "https://a.example/robots.txt": ROBOTS_OK})
    monkeypatch.setenv("SEO_REGULAR_MAX_REQUESTS", "1")
    first = regular.run("check", root=env["root"], now=NOW, sources=env["sources"], http=http)
    assert first["state"] == "PARTIAL"
    assert first["exit_code"] == regular.EXIT_TEMPFAIL
    assert any(e["event"] == "budget_exceeded" for e in _journal(env["root"]))
    monkeypatch.setenv("SEO_REGULAR_MAX_REQUESTS", "100")
    second = regular.run("check", root=env["root"], now=NOW, sources=env["sources"], http=http)
    assert second["state"] == "DONE"
    assert second["steps"]["discover"] == "resumed_skip"


def test_transient_errors_are_retried_with_growing_delay():
    sleeps: list[float] = []
    answers = iter([503, 503, 200])

    class Resp:
        def __init__(self, code):
            self.status = code
            self.headers = {}

        def read(self, _n):
            return b"ok"

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def opener(_req, timeout):
        code = next(answers)
        if code != 200:
            import urllib.error

            raise urllib.error.HTTPError("https://a.example/", code, "busy", {}, None)
        return Resp(code)

    http = regular.Http(
        Budget(60, 10), opener=opener, sleep=sleeps.append, backoff=2.0, min_interval=0
    )
    resp = http.get("https://a.example/")
    assert resp.status == 200
    assert resp.attempts == 3
    assert [s for s in sleeps if s >= 1] == [2.0, 4.0]


# --------------------------------------------------- правила наблюдения


def test_rereading_the_same_snapshot_is_not_a_new_observation(env):
    snaps = env["sources"]["analytics_snapshots"]
    first = regular.analytics_freshness(snaps, {}, NOW)
    assert first["domains"]["a.example"]["observation"] == "NEW_OBSERVATION"
    second = regular.analytics_freshness(snaps, first["seen_update"], NOW + dt.timedelta(hours=6))
    assert second["domains"]["a.example"]["observation"] == "SAME_SNAPSHOT_REREAD"
    assert second["seen_update"] == {}


def test_stale_snapshot_is_named_stale(env):
    later = NOW + dt.timedelta(hours=40)
    assert (
        regular.analytics_freshness(env["sources"]["analytics_snapshots"], {}, later)["status"]
        == "STALE"
    )


def test_week_over_week_compares_non_overlapping_windows(env):
    wow = regular.week_over_week(env["sources"]["analytics_snapshots"], dt.date(2026, 10, 8))
    assert wow["base"] == "analytics-2026-10-01.json"  # не вчерашний снимок
    row = wow["domains"]["a.example"]
    assert row["visits"] == {"now": 140, "before": 100, "delta": 40}
    assert row["search_visits"]["delta"] == 20
    resolved = wow["current_period"]["resolved"]
    assert resolved == {"from": "2026-10-01", "to": "2026-10-07", "days": 7}
    assert wow["base_period"]["resolved"]["to"] == "2026-09-30"


def test_week_over_week_without_base_week_is_not_measured_not_zero(env):
    (env["sources"]["analytics_snapshots"] / "analytics-2026-10-01.json").unlink()
    wow = regular.week_over_week(env["sources"]["analytics_snapshots"], dt.date(2026, 10, 8))
    assert wow["status"] == "NOT_MEASURED"
    assert "2026-10-01" in wow["reason"]


# ------------------------------------------------------------ проверки


def test_open_state_with_noindex_answer_is_an_indexing_mismatch():
    http = FakeHttp(
        {
            "https://a.example/": (200, {"x-robots-tag": "noindex, nofollow"}, b"<html></html>"),
            "https://a.example/robots.txt": ROBOTS_OK,
        }
    )
    res = regular.check_domain(http, {"domain": "a.example", "indexing_desired": "OPEN"})
    assert res["observed_indexing"] == "CLOSED"
    assert [i["code"] for i in res["issues"]] == ["INDEXING_MISMATCH"]


def test_foreign_canonical_on_home_is_critical():
    http = FakeHttp(
        {
            "https://a.example/": (200, {}, b'<link rel="canonical" href="https://b.example/">'),
            "https://a.example/robots.txt": ROBOTS_OK,
        }
    )
    res = regular.check_domain(http, {"domain": "a.example", "indexing_desired": "OPEN"})
    assert "CANONICAL_FOREIGN_HOST" in [i["code"] for i in res["issues"]]


def test_robots_disallow_all_only_for_the_wildcard_group():
    assert regular.robots_disallows_all("User-agent: *\nDisallow: /\n")
    assert not regular.robots_disallows_all(
        "User-agent: BadBot\nDisallow: /\n\nUser-agent: *\nDisallow: /api/\n"
    )


def test_new_critical_issue_notifies_once(env):
    down = FakeHttp({"https://a.example/robots.txt": ROBOTS_OK})
    down.pages["https://a.example/"] = (None, {}, b"")
    first = regular.run("check", root=env["root"], now=NOW, sources=env["sources"], http=down)
    assert first["exit_code"] == regular.EXIT_NEW_CRITICAL
    later = NOW + dt.timedelta(hours=6)
    second = regular.run("check", root=env["root"], now=later, sources=env["sources"], http=down)
    assert second["state"] == "DONE"
    assert second["exit_code"] == 0  # та же проблема — без второго уведомления
    diff = json.loads(
        (env["root"] / "runs" / second["run_id"] / "diff.json").read_text(encoding="utf-8")
    )
    assert diff["new"] == [] and len(diff["persisting"]) == 1


def test_stalled_updates_need_four_equal_days():
    same = {"status": "MEASURED", "urls": 100, "max_lastmod": "2026-08-21T00:00:00Z"}
    history = {f"2026-10-0{d}": same for d in (5, 6, 7)}
    assert regular.stalled_updates(history, "2026-10-07") is None
    history["2026-10-08"] = same
    stalled = regular.stalled_updates(history, "2026-10-08")
    assert stalled["code"] == "UPDATES_STALLED"
    history["2026-10-08"] = {**same, "urls": 101}
    assert regular.stalled_updates(history, "2026-10-08") is None


def test_queue_hygiene_finds_relative_and_absolute_twins(env):
    """Воспроизводит yummyani.org/anime/ledyanaya-stena-2: два живых задания."""
    registry = env["sources"]["queue_registry"]
    registry.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "content_id": "request-fa19",
                        "target_site": "yummyani.org",
                        "canonical_url": "https://yummyani.org/anime/ledyanaya-stena-2",
                        "status": "BLOCKED_INSUFFICIENT_FACTS",
                    },
                    {
                        "content_id": "request-b749",
                        "target_site": "yummyani.org",
                        "canonical_url": "/anime/ledyanaya-stena-2",
                        "status": "READY_VERIFIED",
                    },
                    {
                        "content_id": "request-done",
                        "target_site": "yummyani.org",
                        "canonical_url": "https://yummyani.org/anime/x",
                        "status": "PUBLISHED",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    events = env["sources"]["queue_events"]
    events.write_text(
        "\n".join(
            json.dumps(e)
            for e in [
                {
                    "at": "2026-10-08T01:00:00Z",
                    "event": "task_claimed",
                    "owner": "seo-analysis-2026-10-08",
                    "task_id": "b749",
                    "canonical_url": "https://yummyani.org/anime/ledyanaya-stena-2",
                },
                {
                    "at": "2026-10-08T02:00:00Z",
                    "event": "task_claimed",
                    "owner": "editor-01",
                    "task_id": "b749",
                    "canonical_url": "https://yummyani.org/anime/ledyanaya-stena-2",
                },
            ]
        ),
        encoding="utf-8",
    )
    res = regular.queue_hygiene(registry, events, since=NOW - dt.timedelta(days=1))
    assert len(res["live_duplicates"]) == 1
    assert {t["content_id"] for t in res["live_duplicates"][0]["tasks"]} == {
        "request-fa19",
        "request-b749",
    }
    assert [t["content_id"] for t in res["relative_urls"]] == ["request-b749"]
    assert [c["owner"] for c in res["seo_side_claims"]] == ["seo-analysis-2026-10-08"]
    assert res["urls_claimed_by_several_owners"] == 1


def test_publication_is_rechecked_only_after_its_text_changed(env, tmp_path, monkeypatch):
    root = tmp_path / "overlays"
    (root / "a.example").mkdir(parents=True)
    store = root / "a.example" / "title-overlays.json"
    store.write_text(
        json.dumps(
            {
                "generated_at": "2026-10-07T09:00:00Z",
                "items": [
                    {
                        "slug": "x",
                        "body": "Текст описания карточки для проверки видимости на странице.",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(regular, "OVERLAY_ROOTS", {"animedia": (root, "/title/{slug}/")})
    page = (
        200,
        {},
        "<html><body><p>Текст описания карточки для проверки видимости на странице."
        "</p></body></html>".encode(),
    )
    http = FakeHttp(
        {
            "https://a.example/": HOME_OPEN,
            "https://a.example/robots.txt": ROBOTS_OK,
            "https://a.example/title/x/": page,
        }
    )
    regular.run("check", root=env["root"], now=NOW, sources=env["sources"], http=http)
    assert http.calls.count("https://a.example/title/x/") == 1
    later = NOW + dt.timedelta(hours=6)
    regular.run("check", root=env["root"], now=later, sources=env["sources"], http=http)
    assert http.calls.count("https://a.example/title/x/") == 1  # текст тот же — не перепроверяется
    store.write_text(
        json.dumps(
            {
                "generated_at": "2026-10-08T09:00:00Z",
                "items": [{"slug": "x", "body": "Новый текст, которого на странице ещё нет."}],
            }
        ),
        encoding="utf-8",
    )
    third = regular.run(
        "check",
        root=env["root"],
        now=later + dt.timedelta(hours=6),
        sources=env["sources"],
        http=http,
    )
    pubs = json.loads(
        (env["root"] / "runs" / third["run_id"] / "publications.json").read_text(encoding="utf-8")
    )
    assert pubs["checked"][0]["verdict"] == "TEXT_NOT_VISIBLE"
    diff = json.loads(
        (env["root"] / "runs" / third["run_id"] / "diff.json").read_text(encoding="utf-8")
    )
    assert [i["code"] for i in diff["new"]] == ["PUBLICATION_TEXT_NOT_VISIBLE:/title/x/"]


def test_daily_reuses_a_recent_check_and_writes_one_report(env):
    http = FakeHttp({"https://a.example/": HOME_OPEN, "https://a.example/robots.txt": ROBOTS_OK})
    regular.run("check", root=env["root"], now=NOW, sources=env["sources"], http=http)
    home_calls = http.calls.count("https://a.example/")
    daily = regular.run(
        "daily",
        root=env["root"],
        now=NOW + dt.timedelta(minutes=10),
        sources=env["sources"],
        http=http,
    )
    assert daily["state"] == "DONE", daily
    assert http.calls.count("https://a.example/") == home_calls  # проверка не повторялась
    reports = list((env["root"] / "reports" / "daily").glob("*.md"))
    assert [r.name for r in reports] == ["2026-10-08.md"]
    text = reports[0].read_text(encoding="utf-8")
    assert "SEO-модуль: найдено → исправлено → проверено → осталось" in text
    assert "повторно не выполнялась: да" in text
    assert "2026-09-24…2026-09-30 → 2026-10-01…2026-10-07" in text
    assert "Учтён снимок аналитики от 2026-10-08" in text
    assert "Доставка владельцу: **не выполняется" in text  # сохранённый файл — не доставка


def test_weekly_result_enters_the_next_daily_report_once(env):
    http = FakeHttp({"https://a.example/": HOME_OPEN, "https://a.example/robots.txt": ROBOTS_OK})
    weekly = regular.run("weekly", root=env["root"], now=NOW, sources=env["sources"], http=http)
    assert weekly["state"] == "DONE"
    regular.run("daily", root=env["root"], now=NOW, sources=env["sources"], http=http)
    first = (env["root"] / "reports" / "daily" / "2026-10-08.md").read_text(encoding="utf-8")
    assert "## Неделя `weekly-2026-W41`" in first
    regular.run(
        "daily", root=env["root"], now=NOW + dt.timedelta(days=1), sources=env["sources"], http=http
    )
    second = (env["root"] / "reports" / "daily" / "2026-10-09.md").read_text(encoding="utf-8")
    assert "## Неделя `weekly" not in second


def test_status_separates_scheduled_from_manual_runs(env, tmp_path):
    systemd = tmp_path / "systemd"
    (systemd / "timers.target.wants").mkdir(parents=True)
    stamps = tmp_path / "stamps"
    stamps.mkdir()
    for mode in regular.MODES:
        timer = systemd / f"seo-regular-{mode}.timer"
        timer.write_text("[Timer]\nOnCalendar=*-*-* 05:25:00 UTC\n", encoding="utf-8")
        (systemd / "timers.target.wants" / timer.name).symlink_to(timer)
    http = FakeHttp({"https://a.example/": HOME_OPEN, "https://a.example/robots.txt": ROBOTS_OK})
    regular.run(
        "check", root=env["root"], now=NOW, sources=env["sources"], http=http, trigger="manual"
    )
    before = regular.status(env["root"], systemd_dir=systemd, stamps=stamps)
    assert before["modes"]["check"]["scheduled_runs_done"] == 0
    assert before["modes"]["check"]["last_manual_run"]["trigger"] == "manual"
    assert before["confirmed"] is False  # ручной запуск расписание не подтверждает
    regular.run(
        "check",
        root=env["root"],
        now=NOW + dt.timedelta(hours=6),
        sources=env["sources"],
        http=http,
        trigger="systemd-timer",
    )
    after = regular.status(env["root"], systemd_dir=systemd, stamps=stamps)
    assert after["modes"]["check"]["scheduled_runs_done"] == 1
    assert after["modes"]["check"]["on_calendar"] == ["*-*-* 05:25:00 UTC"]
    assert after["confirmed"] is True


def test_never_resolved_name_is_blocked_not_critical():
    """lordserials22.site под serverHold: известное внешнее состояние."""

    class DnsFail(FakeHttp):
        def get(self, url, *, timeout=None):
            self.calls.append(url)
            return Response(
                url, None, {}, b"", 0.01, error="URLError: [Errno -2] Name or service not known"
            )

    res = regular.check_domain(DnsFail(), {"domain": "lordserials22.site"})
    assert [(i["code"], i["severity"]) for i in res["issues"]] == [("DNS_UNRESOLVED", "blocked")]
    res = regular.check_domain(DnsFail(), {"domain": "a.example"}, was_reachable=True)
    assert [(i["code"], i["severity"]) for i in res["issues"]] == [("DNS_UNRESOLVED", "critical")]


def test_old_lastmod_and_slow_sitemap_are_findings():
    """zonafilm.cc 2026-10-08: самый свежий lastmod 2026-09-27."""
    snap = {
        "status": "MEASURED",
        "urls": 53916,
        "max_lastmod": "2026-09-27T00:00:00Z",
        "slowest_url": "https://zonafilm.cc/sitemap-1.xml",
        "slowest_seconds": 0.4,
    }
    codes = [f["code"] for f in regular.sitemap_findings(snap, NOW)]
    assert codes == ["SITEMAP_LASTMOD_OLD"]
    snap.update(max_lastmod="2026-10-08T00:00:00Z", slowest_seconds=48.0)
    assert [f["code"] for f in regular.sitemap_findings(snap, NOW)] == ["SITEMAP_SLOW"]


def test_revision_chain_is_not_a_duplicate(env):
    registry = env["sources"]["queue_registry"]
    registry.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "content_id": "batch10-17-3x3-glaza",
                        "target_site": "yummyani.site",
                        "canonical_url": "https://yummyani.site/anime/3x3-glaza",
                        "status": "DRAFT_REPAIR",
                    },
                    {
                        "content_id": "buffer-batch10-17-3x3-glaza-rev1",
                        "target_site": "yummyani.site",
                        "canonical_url": "https://yummyani.site/anime/3x3-glaza",
                        "status": "BLOCKED_QUALITY",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    res = regular.queue_hygiene(registry, env["sources"]["queue_events"], since=NOW)
    assert res["live_duplicates"] == []


def test_notable_changes_need_both_share_and_volume():
    wow = {
        "domains": {
            "animeg0.site": {
                "visits": {"now": 60, "before": 640},
                "search_visits": {"now": 0, "before": 0},
            },
            "lordserial33.biz": {"visits": {"now": 39, "before": 40}, "search_visits": {}},
            "small.example": {"visits": {"now": 2, "before": 10}, "search_visits": {}},
        }
    }
    found = regular.notable_changes(wow)
    assert [(n["domain"], n["metric"]) for n in found] == [("animeg0.site", "visits")]


def test_counter_on_page_must_match_the_registry():
    page = (
        200,
        {},
        b'<script>ym(111881038, "init")</script><img src="https://mc.yandex.ru/watch/111881038">',
    )
    http = FakeHttp({"https://a.example/": page, "https://a.example/robots.txt": ROBOTS_OK})
    ok = regular.check_domain(http, {"domain": "a.example", "counter_id": 111881038})
    assert ok["counters_on_page"] == [111881038]
    assert not [i for i in ok["issues"] if i["code"].startswith("COUNTER")]
    wrong = regular.check_domain(http, {"domain": "a.example", "counter_id": 111881037})
    assert [i["code"] for i in wrong["issues"]] == ["COUNTER_MISMATCH"]


def test_publication_gets_a_baseline_and_a_later_evaluation(env, tmp_path, monkeypatch):
    snaps = env["sources"]["analytics_snapshots"]
    data = _snapshot("2026-10-08", 140, 60)
    data["domains"][0]["measurements"].append(
        {
            "key": "landing_pages",
            "measured": True,
            "top_n": 20,
            "value": [{"dimensions": [{"name": "/"}], "metrics": [26.0]}],
        }
    )
    (snaps / "analytics-2026-10-08.json").write_text(json.dumps(data), encoding="utf-8")
    root = tmp_path / "overlays"
    (root / "a.example").mkdir(parents=True)
    (root / "a.example" / "title-overlays.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-10-08T09:00:00Z",
                "items": [
                    {"slug": "x", "body": "Текст описания карточки, который виден на странице."}
                ],
            }
        ),
        encoding="utf-8",
    )
    (root / "a.example" / "history.jsonl").write_text(
        json.dumps({"at": "2026-10-08T09:00:00Z", "op": "publish", "slug": "x"}), encoding="utf-8"
    )
    monkeypatch.setattr(regular, "OVERLAY_ROOTS", {"animedia": (root, "/title/{slug}/")})
    page = (200, {}, "<p>Текст описания карточки, который виден на странице.</p>".encode())
    http = FakeHttp(
        {
            "https://a.example/": HOME_OPEN,
            "https://a.example/robots.txt": ROBOTS_OK,
            "https://a.example/title/x/": page,
        }
    )
    regular.run("check", root=env["root"], now=NOW, sources=env["sources"], http=http)
    state = json.loads((env["root"] / "state.json").read_text(encoding="utf-8"))
    baseline = state["changes"]["https://a.example/title/x/"]["baseline"]
    assert baseline["snapshot"] == "analytics-2026-10-08.json"
    assert baseline["landing_pages"] == {"outside_top_n": 20}  # не ноль
    later = json.loads(json.dumps(data))
    later["collected_at"] = "2026-10-16T06:15:00Z"
    later["domains"][0]["measurements"][-1]["value"] = [
        {"dimensions": [{"name": "/title/x"}], "metrics": [7.0]}
    ]
    (snaps / "analytics-2026-10-16.json").write_text(json.dumps(later), encoding="utf-8")
    weekly = regular.run(
        "weekly",
        root=env["root"],
        now=NOW + dt.timedelta(days=8),
        sources=env["sources"],
        http=http,
    )
    assert weekly["state"] == "DONE", weekly
    evaluated = json.loads(
        (env["root"] / "runs" / weekly["run_id"] / "evaluate.json").read_text(encoding="utf-8")
    )
    assert evaluated[0]["horizon"] == 7
    assert evaluated[0]["after"]["landing_pages"] == {"value": 7.0}
    # до правки страница была вне первых 20 — сравнивать не с чем, вердикта нет
    assert evaluated[0]["verdict"] == "NOT_MEASURABLE"


def test_baseline_is_never_taken_from_a_snapshot_after_publication(env):
    snaps = sorted(env["sources"]["analytics_snapshots"].glob("analytics-*.json"))
    early = regular._baseline(
        snaps, "a.example", "https://a.example/title/x/", "2026-09-20T10:00:00Z"
    )
    assert early == {"not_measured": "снимка аналитики на 2026-09-20 или раньше нет"}
    mid = regular._baseline(
        snaps, "a.example", "https://a.example/title/x/", "2026-10-05T10:00:00Z"
    )
    assert mid["snapshot"] == "analytics-2026-10-01.json"


def test_weekly_priorities_ignore_noise_and_keep_real_drops(env):
    snaps = env["sources"]["analytics_snapshots"]
    old = _snapshot("2026-10-01", 640, 1, domain="a.example")
    new = _snapshot("2026-10-08", 60, 0, domain="a.example")
    noise_old = _snapshot("2026-10-01", 34, 1, domain="b.example")["domains"][0]
    noise_new = _snapshot("2026-10-08", 40, 0, domain="b.example")["domains"][0]
    old["domains"].append(noise_old)
    new["domains"].append(noise_new)
    (snaps / "analytics-2026-10-01.json").write_text(json.dumps(old), encoding="utf-8")
    (snaps / "analytics-2026-10-08.json").write_text(json.dumps(new), encoding="utf-8")
    http = FakeHttp()
    regular.run("weekly", root=env["root"], now=NOW, sources=env["sources"], http=http)
    pri = json.loads(
        (env["root"] / "runs" / "weekly-2026-W41" / "priorities.json").read_text(encoding="utf-8")
    )
    assert [p["domain"] for p in pri["priorities"]] == ["a.example"]
    assert "640 → 60" in pri["priorities"][0]["reason"]


def test_drop_is_decomposed_by_traffic_source(env):
    """animeg0.site 2026-10-08: 640 → 60, из них Cached page traffic 447 → 0."""
    snaps = env["sources"]["analytics_snapshots"]

    def with_sources(day, visits, rows):
        data = _snapshot(day, visits, 0)
        data["domains"][0]["measurements"].append(
            {
                "key": "traffic_sources",
                "measured": True,
                "top_n": 20,
                "value": [{"dimensions": [{"name": k}], "metrics": [v]} for k, v in rows.items()],
            }
        )
        return data

    (snaps / "analytics-2026-10-01.json").write_text(
        json.dumps(
            with_sources(
                "2026-10-01",
                640,
                {"Cached page traffic": 447, "Direct traffic": 186, "Internal traffic": 7},
            )
        ),
        encoding="utf-8",
    )
    (snaps / "analytics-2026-10-08.json").write_text(
        json.dumps(
            with_sources(
                "2026-10-08", 60, {"Direct traffic": 57, "Link traffic": 2, "Internal traffic": 1}
            )
        ),
        encoding="utf-8",
    )
    wow = regular.week_over_week(snaps, dt.date(2026, 10, 8))
    top = wow["domains"]["a.example"]["sources"][0]
    assert top == {"source": "Cached page traffic", "before": 447, "now": 0.0, "delta": -447}
    notable = regular.notable_changes(wow)
    assert notable[0]["main_source"]["source"] == "Cached page traffic"


def test_report_names_an_older_snapshot_when_todays_has_not_arrived(env):
    (env["sources"]["analytics_snapshots"] / "analytics-2026-10-08.json").unlink()
    http = FakeHttp({"https://a.example/": HOME_OPEN, "https://a.example/robots.txt": ROBOTS_OK})
    regular.run("daily", root=env["root"], now=NOW, sources=env["sources"], http=http)
    text = (env["root"] / "reports" / "daily" / "2026-10-08.md").read_text(encoding="utf-8")
    assert "Учтён снимок аналитики от 2026-10-07" in text
    assert "Снимка за 2026-10-08 на момент отчёта нет" in text


def test_publication_time_comes_from_the_history_not_the_store(tmp_path, monkeypatch):
    """animedia.icu 2026-10-08: generated_at хранилища сдвинулся правкой соседа."""
    site = tmp_path / "overlays" / "a.example"
    site.mkdir(parents=True)
    (site / "title-overlays.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-10-08T12:03:59Z",
                "items": [
                    {
                        "slug": "old",
                        "body": "Старый текст карточки, опубликованный первого октября.",
                    },
                    {
                        "slug": "new",
                        "body": "Новый текст карточки, опубликованный восьмого октября.",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    (site / "history.jsonl").write_text(
        "\n".join(
            json.dumps(r)
            for r in [
                {"at": "2026-10-01T18:31:58Z", "op": "publish", "slug": "old"},
                {"at": "2026-10-08T12:03:59Z", "op": "publish", "slug": "new"},
            ]
        ),
        encoding="utf-8",
    )
    items = {
        i["slug"]: i
        for i in regular.published_items({"animedia": (tmp_path / "overlays", "/title/{slug}/")})
    }
    assert items["old"]["published_at"] == "2026-10-01T18:31:58Z"
    assert items["new"]["published_at"] == "2026-10-08T12:03:59Z"


def test_unknown_publication_time_gives_no_baseline(env, tmp_path, monkeypatch):
    root = tmp_path / "overlays"
    (root / "a.example").mkdir(parents=True)
    (root / "a.example" / "title-overlays.json").write_text(
        json.dumps(
            {
                "items": [
                    {
                        "slug": "x",
                        "body": "Текст без записи в журнале публикаций, виден на странице.",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(regular, "OVERLAY_ROOTS", {"animedia": (root, "/title/{slug}/")})
    page = (200, {}, "<p>Текст без записи в журнале публикаций, виден на странице.</p>".encode())
    http = FakeHttp(
        {
            "https://a.example/": HOME_OPEN,
            "https://a.example/robots.txt": ROBOTS_OK,
            "https://a.example/title/x/": page,
        }
    )
    regular.run("check", root=env["root"], now=NOW, sources=env["sources"], http=http)
    state = json.loads((env["root"] / "state.json").read_text(encoding="utf-8"))
    assert state["changes"]["https://a.example/title/x/"]["baseline"] == {
        "not_measured": "время публикации неизвестно"
    }


def test_visited_url_with_404_becomes_an_issue(env):
    snaps = env["sources"]["analytics_snapshots"]
    data = _snapshot("2026-10-08", 140, 60)
    data["domains"][0]["measurements"].append(
        {
            "key": "popular_pages",
            "measured": True,
            "top_n": 20,
            "value": [
                {"dimensions": [{"name": "/title/x/season-1/episode-244/"}], "metrics": [3.0]}
            ],
        }
    )
    (snaps / "analytics-2026-10-08.json").write_text(json.dumps(data), encoding="utf-8")
    http = FakeHttp({"https://a.example/": HOME_OPEN, "https://a.example/robots.txt": ROBOTS_OK})
    regular.run("daily", root=env["root"], now=NOW, sources=env["sources"], http=http)
    text = (env["root"] / "reports" / "daily" / "2026-10-08.md").read_text(encoding="utf-8")
    assert "VISITED_URL_404:/title/x/season-1/episode-244/" in text


def test_editor_process_finds_loops_and_dead_end_tasks(env):
    events = env["sources"]["queue_events"]
    rows = [
        {
            "at": f"2026-10-08T0{i % 5}:00:00Z",
            "event": "task_claimed",
            "task_id": "92436c43",
            "site": "yummyani.site",
            "owner": f"editor-{i}",
        }
        for i in range(6)
    ]
    rows.append(
        {
            "at": "2026-10-08T04:30:00Z",
            "event": "task_result",
            "task_id": "92436c43",
            "site": "yummyani.site",
            "outcome": "SOURCE_UNAVAILABLE",
            "gate": {},
        }
    )
    events.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    env["sources"]["queue_registry"].write_text(
        json.dumps(
            {
                "items": [
                    {
                        "content_id": "request-2b08",
                        "target_site": "an1mego.site",
                        "status": "NEEDS_UPDATE",
                        "content_type": "TITLE_DESCRIPTION",
                    },
                    {
                        "content_id": "request-b9a9",
                        "target_site": "animedia.icu",
                        "status": "NEEDS_UPDATE",
                        "content_type": "TITLE_DESCRIPTION",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    cells = {
        "yummyani.site": "yummy-site",
        "an1mego.site": "animego-02",
        "animedia.icu": "animedia-01",
    }
    out = regular.editor_process(
        events, env["sources"]["queue_registry"], cells, since=NOW - dt.timedelta(days=1)
    )
    assert out["claims"] == 6 and out["results"] == 1
    assert out["looping"][0]["task_id"] == "92436c43"
    assert out["outcomes"] == {"yummy:SOURCE_UNAVAILABLE": 1}
    assert [t["content_id"] for t in out["dead_end_tasks"]] == ["request-2b08"]


def _m(page, domain):
    return {
        "landing_pages": {"value": page} if page is not None else {"outside_top_n": 20},
        "domain_visits": domain,
    }


def test_judge_corrects_for_the_domain_and_needs_volume():
    # страница +50%, домен +50% — правка ни при чём
    assert regular.judge(_m(20, 100), _m(30, 150))["verdict"] == "NO_CLEAR_CHANGE"
    # страница +100% при ровном домене
    assert regular.judge(_m(20, 100), _m(40, 100))["verdict"] == "GAIN_OBSERVED"
    # страница -60% при ровном домене — подозрение на регрессию
    assert regular.judge(_m(20, 100), _m(8, 100))["verdict"] == "REGRESSION_SUSPECTED"
    # 3 → 6 входов: «рост вдвое» на таком объёме не вывод
    assert regular.judge(_m(3, 100), _m(6, 100))["verdict"] == "INSUFFICIENT_VOLUME"
    assert regular.judge(_m(None, 100), _m(6, 100))["verdict"] == "NOT_MEASURABLE"


def test_evaluation_waits_for_windows_after_publication(env):
    snaps = env["sources"]["analytics_snapshots"]
    changes = {
        "https://a.example/title/x/": {
            "domain": "a.example",
            "published_at": "2026-10-08T12:00:00Z",
            "baseline": {"snapshot": "analytics-2026-10-08.json", **_m(20, 140)},
        }
    }
    assert regular.evaluate_changes(changes, snaps) == []  # +7 ждёт снимка 2026-10-16
    data = _snapshot("2026-10-16", 140, 60)
    data["domains"][0]["measurements"].append(
        {
            "key": "landing_pages",
            "measured": True,
            "top_n": 20,
            "value": [{"dimensions": [{"name": "/title/x"}], "metrics": [40.0]}],
        }
    )
    (snaps / "analytics-2026-10-16.json").write_text(json.dumps(data), encoding="utf-8")
    found = regular.evaluate_changes(changes, snaps)
    assert [(e["horizon"], e["verdict"]) for e in found] == [(7, "GAIN_OBSERVED")]


def test_report_shows_the_five_change_categories(env):
    env["sources"]["changes_ledger"].write_text(
        json.dumps(
            {
                "version": 1,
                "changes": [
                    {
                        "id": "CHG-20261008-01",
                        "url": "https://a.example/title/x/",
                        "kind": "written",
                        "element": "description",
                        "problem": "заглушка вместо описания",
                        "evidence": "data-b07-desc=gap",
                        "hypothesis": "описание даёт содержательный сниппет",
                        "published_at": "2026-10-08T12:00:00Z",
                        "path": "мост",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    http = FakeHttp({"https://a.example/": HOME_OPEN, "https://a.example/robots.txt": ROBOTS_OK})
    regular.run("daily", root=env["root"], now=NOW, sources=env["sources"], http=http)
    text = (env["root"] / "reports" / "daily" / "2026-10-08.md").read_text(encoding="utf-8")
    for title in (
        "Написано: 1",
        "Оптимизировано: 0",
        "Опубликовано и проверено на сайте: 0",
        "Эффект пока не установлен: 1",
        "Результат измерен: 0",
    ):
        assert f"**{title}**" in text, title
    assert "2026-10-16, 2026-10-23" in text  # даты проверок +7 и +14


def test_control_page_cancels_a_title_wide_rise():
    """Пилот animedia.space против той же карточки на icu: рост у обоих — не эффект правки."""
    base, after = _m(10, 100), _m(25, 100)
    assert regular.judge(base, after)["verdict"] == "GAIN_OBSERVED"
    same_rise = (_m(10, 100), _m(24, 100))
    assert regular.judge(base, after, same_rise)["verdict"] == "NO_CLEAR_CHANGE"
    flat_control = (_m(10, 100), _m(10, 100))
    assert regular.judge(base, after, flat_control)["verdict"] == "GAIN_OBSERVED"


def test_editor_candidates_rank_gaps_and_space_duplicates_by_title_traffic(tmp_path):
    snap = tmp_path / "analytics-2026-10-08.json"
    snap.write_text(
        json.dumps(
            {
                "domains": [
                    {
                        "domain": "animedia.space",
                        "measurements": [
                            {
                                "key": "popular_pages",
                                "measured": True,
                                "value": [
                                    {
                                        "dimensions": [{"name": "/title/gap/season-1/episode-1/"}],
                                        "metrics": [9.0],
                                    },
                                    {"dimensions": [{"name": "/title/dup/"}], "metrics": [4.0]},
                                    {"dimensions": [{"name": "/title/done/"}], "metrics": [20.0]},
                                ],
                            }
                        ],
                    },
                    {
                        "domain": "animedia.icu",
                        "measurements": [
                            {
                                "key": "popular_pages",
                                "measured": True,
                                "value": [
                                    {"dimensions": [{"name": "/title/dup/"}], "metrics": [5.0]}
                                ],
                            }
                        ],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    facts = tmp_path / "facts"
    facts.mkdir()
    same = {"name": "Дубль", "description": "Один и тот же синопсис."}
    for sid in ("animedia-01", "animedia-02"):
        (facts / f"{sid}-details.json").write_text(
            json.dumps(
                {
                    "details": {
                        "gap": {"name": "Без описания", "description": None},
                        "dup": same,
                        "done": same,
                    }
                }
            ),
            encoding="utf-8",
        )
    found = regular.editor_candidates(snap, facts, {("animedia.space", "done")})
    assert [(c["site"], c["slug"], c["reason"]) for c in found] == [
        ("animedia.space", "gap", "GAP"),
        ("animedia.space", "dup", "DUPLICATE"),
    ]
    # на icu дубль не трогается: там контроль пилота
    assert all(c["site"] != "animedia.icu" or c["reason"] == "GAP" for c in found)


def test_editor_candidates_give_one_own_description_per_work_in_the_network(tmp_path):
    snap = tmp_path / "analytics-2026-10-09.json"
    rows = [{"dimensions": [{"name": "/title/gap/"}], "metrics": [5.0]}]
    snap.write_text(
        json.dumps(
            {
                "domains": [
                    {
                        "domain": d,
                        "measurements": [{"key": "popular_pages", "measured": True, "value": rows}],
                    }
                    for d in ("animedia.icu", "animedia.space")
                ]
            }
        ),
        encoding="utf-8",
    )
    facts = tmp_path / "facts"
    facts.mkdir()
    shiki = {"shikimori": {"match_state": "external_id_exact+title_verified", "value": 8}}
    for sid in ("animedia-01", "animedia-02"):
        (facts / f"{sid}-details.json").write_text(
            json.dumps(
                {
                    "details": {
                        "gap": {"name": "Без описания", "description": None},
                        "done-elsewhere": {"description": None, "ratings_by_source": shiki},
                        "free": {"description": None, "ratings_by_source": shiki},
                    }
                }
            ),
            encoding="utf-8",
        )
    found = regular.editor_candidates(snap, facts, {("animedia.icu", "done-elsewhere")})
    slugs = [c["slug"] for c in found]
    # пробел есть на обоих доменах — кандидат один; уже написанное на icu на space не идёт
    assert slugs.count("gap") == 1 and slugs.count("free") == 1
    assert "done-elsewhere" not in slugs


def test_hourly_summary_makes_no_requests_and_says_delivery_is_not_done(env):
    http = FakeHttp()
    r = regular.run("hourly", root=env["root"], now=NOW, sources=env["sources"], http=http)
    assert r["state"] == "DONE" and http.calls == []
    text = (env["root"] / "hourly" / "2026-10-08T05.md").read_text(encoding="utf-8")
    assert "канал отменён владельцем" in text


def test_skipped_slot_is_visible_in_history(env):
    http = FakeHttp({"https://a.example/": HOME_OPEN, "https://a.example/robots.txt": ROBOTS_OK})
    regular.run("check", root=env["root"], now=NOW, sources=env["sources"], http=http)
    regular.run(
        "check",
        root=env["root"],
        now=NOW,
        sources=env["sources"],
        http=http,
        trigger="systemd-timer",
    )
    state = json.loads((env["root"] / "state.json").read_text(encoding="utf-8"))
    assert state["runs"][-1]["state"] == "ALREADY_DONE"
    assert state["runs"][-1]["trigger"] == "systemd-timer"


def test_daily_report_lists_editor_publications_with_sources_actually_read(tmp_path):
    runs = tmp_path / "editor-runs"
    runs.mkdir()
    (runs / "runs.jsonl").write_text(
        json.dumps(
            {
                "run_id": "R1",
                "trigger": "systemd-timer",
                "verdict": "COMPLETE",
                "started_at": "2026-10-08T03:00:00Z",
                "finished_at": "2026-10-08T03:05:00Z",
            }
        )
        + "\n"
        + json.dumps(
            {
                "run_id": "R2",
                "trigger": "systemd-timer",
                "verdict": "NO_PUBLICATION",
                "started_at": "2026-10-08T04:00:00Z",
                "finished_at": "2026-10-08T04:02:00Z",
                "self_report": {"note": "нет синопсиса"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (runs / "R1.verify.json").write_text(
        json.dumps(
            {
                "publications": [
                    {"url": "https://a.example/title/x/", "at": "2026-10-08T03:02:00Z"},
                    {"url": "https://a.example/title/y/", "at": "2026-10-08T03:04:00Z"},
                ]
            }
        ),
        encoding="utf-8",
    )
    (runs / "sources.jsonl").write_text(
        "\n".join(
            json.dumps(r)
            for r in [
                {
                    "at": "2026-10-08T03:01:00Z",
                    "url": "https://shikimori.io/api/animes/1",
                    "status": 200,
                },
                {"at": "2026-10-08T05:00:00Z", "url": "https://other.example", "status": 200},
            ]
        ),
        encoding="utf-8",
    )
    day = regular.editor_day(runs, NOW - dt.timedelta(days=1))
    assert day["published"][0]["sources"] == ["https://shikimori.io/api/animes/1"]
    # источник первой публикации не приписывается второй (окно 03:02–03:04 пусто)
    assert day["published"][1]["sources"] == ["только каталог сети (внешних обращений нет)"]
    assert day["problems"][0]["note"] == "нет синопсиса"
    assert day["verdicts"] == {"COMPLETE": 1, "NO_PUBLICATION": 1}


def test_daily_writes_the_single_latest_report(env):
    http = FakeHttp({"https://a.example/": HOME_OPEN, "https://a.example/robots.txt": ROBOTS_OK})
    regular.run("daily", root=env["root"], now=NOW, sources=env["sources"], http=http)
    latest = (env["root"] / "reports" / "LATEST.md").read_text(encoding="utf-8")
    assert latest == (env["root"] / "reports" / "daily" / "2026-10-08.md").read_text(
        encoding="utf-8"
    )
    assert "не выполняется — канал доставки отменён владельцем" in latest
    # Покрытие редактора: опубликованного текста нет — сайт не «работает».
    assert "## Покрытие редактора по доменам" in latest
    assert "| a.example | нет подходящих заданий |" in latest
    assert "Редактор работает на 0 из" in latest


def test_publication_metrics_separates_new_texts_edits_and_visibility(tmp_path):
    root = tmp_path / "ov"
    a, b = root / "a.example", root / "b.example"
    a.mkdir(parents=True)
    b.mkdir(parents=True)

    def rec(at, slug, digest):
        return json.dumps({"at": at, "op": "publish", "slug": slug, "body_digest": digest * 64})

    a.joinpath("history.jsonl").write_text(
        "\n".join(
            [
                rec("2026-10-07T10:00:00Z", "old", "0"),  # до периода
                rec("2026-10-08T09:00:00Z", "old", "1"),  # правка уже опубликованного
                rec("2026-10-08T10:00:00Z", "new", "2"),  # новый текст
                rec("2026-10-08T11:00:00Z", "new", "3"),  # его вторая версия — правка
                rec("2026-10-08T12:00:00Z", "copy", "4"),  # тот же текст, что на b
            ]
        ),
        encoding="utf-8",
    )
    b.joinpath("history.jsonl").write_text(rec("2026-10-08T12:30:00Z", "copy", "4"), "utf-8")
    verdicts = {
        "https://a.example/t/new/": {"verdict": "VISIBLE", "digest": "3" * 16},
        "https://a.example/t/old/": {"verdict": "VISIBLE", "digest": "0" * 16},  # старый текст
        "https://a.example/t/copy/": {"verdict": "TEXT_NOT_VISIBLE", "digest": "4" * 16},
    }
    pm = regular.publication_metrics(
        dt.datetime(2026, 10, 8, 8, 0, tzinfo=dt.timezone.utc),
        verdicts,
        roots={"x": (root, "/t/{slug}/")},
    )
    ra = pm["a.example"]
    assert ra["new_texts"] == ["https://a.example/t/new/"]  # copy повторяет текст b
    assert len(ra["urls"]) == 3 and ra["edits"] == 2
    assert ra["visible"] == ["https://a.example/t/new/"]
    assert ra["not_visible"] == ["https://a.example/t/copy/"]
    assert ra["unchecked"] == ["https://a.example/t/old/"]  # вердикт был у прежнего текста
    assert pm["b.example"]["new_texts"] == [] and pm["b.example"]["unchecked"]
