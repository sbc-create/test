"""Устойчивое хранение ежедневных отчётов и учёт доставки."""

from __future__ import annotations

import json
from datetime import date

from seo_operator.report_spool import (
    DELIVERED,
    DESTINATION_FIELD,
    PENDING,
    owner_action,
    pending,
    store,
)

DAY = date(2026, 9, 15)


def test_report_survives_a_missing_destination(tmp_path) -> None:
    """Потеря отчёта хуже ненастроенной доставки: там данные есть и ждут."""
    entry = store(
        tmp_path, run_id="r-1", day=DAY, markdown="# отчёт", payload={"findings": []}
    )
    assert entry.markdown_path.exists()
    assert entry.json_path.exists()
    assert entry.delivery_status == PENDING
    assert DESTINATION_FIELD in entry.detail


def test_owner_action_names_one_missing_field(tmp_path) -> None:
    store(tmp_path, run_id="r-1", day=DAY, markdown="#", payload={})
    action = owner_action(tmp_path)
    assert action is not None
    assert DESTINATION_FIELD in action
    assert action.count(DESTINATION_FIELD) == 1, "требуемое действие должно быть одно"


def test_delivered_report_is_not_pending(tmp_path) -> None:
    entry = store(
        tmp_path,
        run_id="r-1",
        day=DAY,
        markdown="#",
        payload={},
        destination="quin://team/seo",
    )
    assert entry.delivery_status == DELIVERED
    assert pending(tmp_path) == []
    assert owner_action(tmp_path) is None


def test_second_run_of_the_same_day_does_not_overwrite_the_first(tmp_path) -> None:
    """Повторный прогон пишется рядом, а не поверх.

    Раньше отчёт писался по --out одним и тем же именем, и вчерашний исчезал.
    Цикл, отработавший без читателя, не оставлял следа.
    """
    first = store(tmp_path, run_id="утро", day=DAY, markdown="# утро", payload={})
    second = store(tmp_path, run_id="вечер", day=DAY, markdown="# вечер", payload={})
    assert first.markdown_path != second.markdown_path
    assert first.markdown_path.read_text(encoding="utf-8") == "# утро"
    assert second.markdown_path.read_text(encoding="utf-8") == "# вечер"


def test_latest_points_at_the_last_run_without_being_the_only_copy(tmp_path) -> None:
    store(tmp_path, run_id="утро", day=DAY, markdown="# утро", payload={})
    store(tmp_path, run_id="вечер", day=DAY, markdown="# вечер", payload={})
    assert (tmp_path / "latest.md").read_text(encoding="utf-8") == "# вечер"
    assert (tmp_path / DAY.isoformat() / "SEO-DAILY-REPORT.утро.md").exists()


def test_days_are_kept_apart(tmp_path) -> None:
    store(tmp_path, run_id="r", day=date(2026, 9, 14), markdown="# вчера", payload={})
    store(tmp_path, run_id="r", day=DAY, markdown="# сегодня", payload={})
    assert (tmp_path / "2026-09-14" / "SEO-DAILY-REPORT.r.md").exists()
    assert (tmp_path / "2026-09-15" / "SEO-DAILY-REPORT.r.md").exists()
    assert len(pending(tmp_path)) == 2


def test_run_id_with_path_characters_cannot_escape_the_day_directory(tmp_path) -> None:
    entry = store(tmp_path, run_id="../../etc/passwd", day=DAY, markdown="#", payload={})
    assert entry.markdown_path.parent == tmp_path / DAY.isoformat()
    assert ".." not in entry.markdown_path.name


def test_delivery_state_is_written_into_the_payload(tmp_path) -> None:
    entry = store(tmp_path, run_id="r", day=DAY, markdown="#", payload={"findings": [1]})
    data = json.loads(entry.json_path.read_text(encoding="utf-8"))
    assert data["findings"] == [1]
    assert data["delivery"]["status"] == PENDING
    assert data["delivery"]["run_id"] == "r"


def test_pending_is_ordered_oldest_first(tmp_path) -> None:
    store(tmp_path, run_id="r", day=date(2026, 9, 13), markdown="#", payload={})
    store(tmp_path, run_id="r", day=date(2026, 9, 15), markdown="#", payload={})
    waiting = pending(tmp_path)
    assert [p.parent.name for p in waiting] == ["2026-09-13", "2026-09-15"]
    assert "2026-09-13" in owner_action(tmp_path)


def test_unreadable_report_does_not_break_the_listing(tmp_path) -> None:
    store(tmp_path, run_id="r", day=DAY, markdown="#", payload={})
    broken = tmp_path / DAY.isoformat() / "SEO-DAILY-REPORT.broken.json"
    broken.write_text("{не json", encoding="utf-8")
    assert len(pending(tmp_path)) == 1


def test_empty_spool_asks_for_nothing(tmp_path) -> None:
    assert pending(tmp_path) == []
    assert owner_action(tmp_path) is None
