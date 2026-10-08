"""REQ-SEO-REGULAR: вкладка отчёта показывает отчёт дня в 10:00 МСК и не повторяет старые."""

from __future__ import annotations

import datetime as dt
import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "seo_report_view",
    Path(__file__).resolve().parents[2] / "automation" / "local" / "seo-report-view.py",
)
view = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(view)

UTC = dt.timezone.utc


def at(text: str) -> dt.datetime:
    return dt.datetime.fromisoformat(text).replace(tzinfo=UTC)


def test_report_waits_until_ten_moscow():
    # отчёт 2026-10-09 готов в 05:54 UTC, показ — в 07:00 UTC (10:00 МСК)
    assert view.decide(["2026-10-09"], at("2026-10-09T06:30:00"), "2026-10-08") == {}
    assert view.decide(["2026-10-09"], at("2026-10-09T07:00:30"), "2026-10-08") == {
        "show": "2026-10-09"
    }


def test_shown_report_is_not_repeated():
    assert view.decide(["2026-10-08", "2026-10-09"], at("2026-10-09T12:00:00"), "2026-10-09") == {}


def test_backlog_is_not_dumped_only_the_latest_is_shown():
    got = view.decide(
        ["2026-10-07", "2026-10-08", "2026-10-09"], at("2026-10-09T07:01:00"), "2026-10-06"
    )
    assert got == {"show": "2026-10-09"}


def test_missing_report_is_named_after_ten_past_ten():
    assert view.decide(["2026-10-08"], at("2026-10-09T07:05:00"), "2026-10-08") == {}
    assert view.decide(["2026-10-08"], at("2026-10-09T07:11:00"), "2026-10-08") == {
        "late": "2026-10-09"
    }


def test_late_report_is_shown_when_it_appears():
    assert view.decide(["2026-10-09"], at("2026-10-09T09:30:00"), "2026-10-08") == {
        "show": "2026-10-09"
    }
