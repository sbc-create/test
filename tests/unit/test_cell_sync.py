"""Доставка обновлений: курсор, дубли, удаления, атомарность, честная свежесть.

Доказывает: REQ-CELL-SYNC, REQ-CELL-FRESHNESS.
"""
from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest

from factory.cell import sync
from factory.cell.sync import SchemaRejected, UpstreamUnavailable, utc_now

SITE = "pilot-cell"
PROFILE = "pilot-video"


def _event(seq: int, uuid: str, kind: str = "upsert", **kw) -> dict:
    base = {
        "event_id": f"e-{seq}", "seq": seq, "kind": kind, "title_uuid": uuid,
        "content_revision": seq,
    }
    if kind == "upsert":
        base["payload"] = {"title": f"Тайтл {seq}"}
    base.update(kw)
    return base


class Catalog:
    """Приёмник партии. Применяет всё или ничего."""

    def __init__(self) -> None:
        self.titles: dict[str, dict] = {}
        self.batches: list[int] = []
        self.fail_next = False

    def apply(self, batch):
        if self.fail_next:
            self.fail_next = False
            raise RuntimeError("запись не удалась")
        staged = dict(self.titles)
        for event in batch:
            if event.kind == "delete":
                staged.pop(event.title_uuid, None)
            else:
                staged[event.title_uuid] = event.payload
        self.titles = staged
        self.batches.append(len(batch))


@pytest.fixture()
def cursor(tmp_path: Path) -> Path:
    return tmp_path / "checkpoint.json"


def test_first_pull_applies_everything_and_records_the_position(cursor: Path):
    catalog = Catalog()
    feed = [_event(1, "a"), _event(2, "b")]
    result = sync.pull(site_id=SITE, profile=PROFILE, fetch=lambda seq: feed,
                       checkpoint_path=cursor, apply_batch=catalog.apply)
    assert result.applied == 2
    assert result.seq == 2
    assert set(catalog.titles) == {"a", "b"}
    assert sync.load_checkpoint(cursor, SITE).seq == 2


def test_repeated_delivery_creates_no_duplicates(cursor: Path):
    catalog = Catalog()
    feed = [_event(1, "a"), _event(2, "b")]
    sync.pull(site_id=SITE, profile=PROFILE, fetch=lambda seq: feed,
              checkpoint_path=cursor, apply_batch=catalog.apply)
    again = sync.pull(site_id=SITE, profile=PROFILE, fetch=lambda seq: feed,
                      checkpoint_path=cursor, apply_batch=catalog.apply)
    assert again.applied == 0
    assert again.duplicates == 2
    assert len(catalog.titles) == 2


def test_deletion_reaches_the_local_copy(cursor: Path):
    catalog = Catalog()
    sync.pull(site_id=SITE, profile=PROFILE, fetch=lambda s: [_event(1, "a")],
              checkpoint_path=cursor, apply_batch=catalog.apply)
    assert "a" in catalog.titles
    result = sync.pull(site_id=SITE, profile=PROFILE,
                       fetch=lambda s: [_event(2, "a", kind="delete")],
                       checkpoint_path=cursor, apply_batch=catalog.apply)
    assert result.deleted == 1
    assert "a" not in catalog.titles


def test_absence_from_the_feed_is_not_a_deletion(cursor: Path):
    catalog = Catalog()
    sync.pull(site_id=SITE, profile=PROFILE, fetch=lambda s: [_event(1, "a")],
              checkpoint_path=cursor, apply_batch=catalog.apply)
    sync.pull(site_id=SITE, profile=PROFILE, fetch=lambda s: [_event(2, "b")],
              checkpoint_path=cursor, apply_batch=catalog.apply)
    assert "a" in catalog.titles, "запись пропала без события удаления"


def test_failed_batch_leaves_the_cursor_where_it_was(cursor: Path):
    catalog = Catalog()
    catalog.fail_next = True
    with pytest.raises(RuntimeError):
        sync.pull(site_id=SITE, profile=PROFILE, fetch=lambda s: [_event(1, "a")],
                  checkpoint_path=cursor, apply_batch=catalog.apply)
    assert sync.load_checkpoint(cursor, SITE).seq == 0
    assert catalog.titles == {}
    # Та же партия приезжает снова и применяется.
    result = sync.pull(site_id=SITE, profile=PROFILE, fetch=lambda s: [_event(1, "a")],
                       checkpoint_path=cursor, apply_batch=catalog.apply)
    assert result.applied == 1


def test_batch_is_applied_whole_or_not_at_all(cursor: Path):
    catalog = Catalog()
    catalog.fail_next = True
    feed = [_event(1, "a"), _event(2, "b"), _event(3, "c")]
    with pytest.raises(RuntimeError):
        sync.pull(site_id=SITE, profile=PROFILE, fetch=lambda s: feed,
                  checkpoint_path=cursor, apply_batch=catalog.apply)
    assert catalog.titles == {}, "половина партии применена"


def test_resume_continues_from_the_last_applied_position(cursor: Path):
    catalog = Catalog()
    sync.pull(site_id=SITE, profile=PROFILE,
              fetch=lambda s: [_event(1, "a"), _event(2, "b")],
              checkpoint_path=cursor, apply_batch=catalog.apply)
    # Прогон продолжается после перезапуска: курсор прочитан с диска.
    result = sync.pull(site_id=SITE, profile=PROFILE,
                       fetch=lambda s: [_event(3, "c")],
                       checkpoint_path=cursor, apply_batch=catalog.apply)
    assert result.applied == 1
    assert result.seq == 3
    assert set(catalog.titles) == {"a", "b", "c"}


def test_missed_cycles_are_caught_up_in_one_pull(cursor: Path):
    catalog = Catalog()
    sync.pull(site_id=SITE, profile=PROFILE, fetch=lambda s: [_event(1, "a")],
              checkpoint_path=cursor, apply_batch=catalog.apply)
    # Несколько циклов пропущено; накопленное доезжает целиком.
    missed = [_event(n, f"t{n}") for n in range(2, 12)]
    result = sync.pull(site_id=SITE, profile=PROFILE, fetch=lambda s: missed,
                       checkpoint_path=cursor, apply_batch=catalog.apply)
    assert result.applied == 10
    assert result.seq == 11


def test_only_the_profiles_catalog_reaches_the_site(cursor: Path):
    catalog = Catalog()
    feed = [
        _event(1, "mine", profiles=[PROFILE]),
        _event(2, "someone-elses", profiles=["other-profile"]),
    ]
    result = sync.pull(site_id=SITE, profile=PROFILE, fetch=lambda s: feed,
                       checkpoint_path=cursor, apply_batch=catalog.apply)
    assert result.applied == 1
    assert result.skipped_profile == 1
    assert set(catalog.titles) == {"mine"}


def test_unreachable_upstream_is_reported_not_counted_as_zero(cursor: Path):
    catalog = Catalog()
    sync.pull(site_id=SITE, profile=PROFILE, fetch=lambda s: [_event(1, "a")],
              checkpoint_path=cursor, apply_batch=catalog.apply)

    def broken(seq):
        raise ConnectionError("центр недоступен")

    with pytest.raises(UpstreamUnavailable, match="снимке ревизии 1"):
        sync.pull(site_id=SITE, profile=PROFILE, fetch=broken,
                  checkpoint_path=cursor, apply_batch=catalog.apply)
    # Последний проверенный снимок продолжает работать.
    assert set(catalog.titles) == {"a"}
    state = sync.load_checkpoint(cursor, SITE)
    assert state.content_revision == 1
    assert state.consecutive_failures == 1


def test_retries_are_limited(cursor: Path):
    attempts = []

    def flaky(seq):
        attempts.append(seq)
        raise ConnectionError("нет связи")

    with pytest.raises(UpstreamUnavailable):
        sync.pull(site_id=SITE, profile=PROFILE, fetch=flaky,
                  checkpoint_path=cursor, apply_batch=Catalog().apply, max_attempts=3)
    assert len(attempts) == 3, "повторы обязаны иметь границу"


def test_a_transient_failure_is_retried_and_succeeds(cursor: Path):
    catalog = Catalog()
    calls = {"n": 0}

    def flaky(seq):
        calls["n"] += 1
        if calls["n"] < 2:
            raise ConnectionError("моргнула сеть")
        return [_event(1, "a")]

    result = sync.pull(site_id=SITE, profile=PROFILE, fetch=flaky,
                       checkpoint_path=cursor, apply_batch=catalog.apply)
    assert result.applied == 1


def test_malformed_event_is_rejected_before_anything_is_applied(cursor: Path):
    catalog = Catalog()
    feed = [_event(1, "a"), {"event_id": "bad", "seq": 2}]
    with pytest.raises(SchemaRejected):
        sync.pull(site_id=SITE, profile=PROFILE, fetch=lambda s: feed,
                  checkpoint_path=cursor, apply_batch=catalog.apply)
    assert catalog.titles == {}, "партия применялась до проверки схемы"


def test_freshness_names_the_state_and_the_reason(cursor: Path):
    catalog = Catalog()
    now = utc_now()
    assert sync.freshness(cursor, SITE, now=now)["state"] == "unmeasured"

    sync.pull(site_id=SITE, profile=PROFILE, fetch=lambda s: [_event(1, "a")],
              checkpoint_path=cursor, apply_batch=catalog.apply, now=now)
    assert sync.freshness(cursor, SITE, now=now)["state"] == "fresh"

    stale = sync.freshness(cursor, SITE, now=now + timedelta(hours=7))
    assert stale["state"] == "stale"
    assert stale["reason"]

    stuck = sync.freshness(cursor, SITE, now=now + timedelta(hours=30))
    assert stuck["state"] == "stuck"
    assert stuck["lag_seconds"] > 0


def test_a_cursor_belongs_to_one_site(cursor: Path, tmp_path: Path):
    catalog = Catalog()
    sync.pull(site_id=SITE, profile=PROFILE, fetch=lambda s: [_event(1, "a")],
              checkpoint_path=cursor, apply_batch=catalog.apply)
    with pytest.raises(sync.SyncError, match="принадлежит сайту"):
        sync.load_checkpoint(cursor, "neighbour-cell")


def test_an_old_event_never_overwrites_newer_data(cursor: Path):
    """Событие старее курсора не применяется, даже если выпало из памяти.

    Память ограничена. Если бы признаком дубля был только идентификатор,
    вытесненное и заново присланное старое событие вернуло бы прежнее значение
    поверх нового — и выглядело бы это как «синхронизация откатила правку».
    """
    catalog = Catalog()
    old = _event(1, "a")
    old["payload"] = {"title": "старое значение"}
    new = _event(5, "a")
    new["payload"] = {"title": "новое значение"}
    sync.pull(site_id=SITE, profile=PROFILE, fetch=lambda s: [old, new],
              checkpoint_path=cursor, apply_batch=catalog.apply)
    assert catalog.titles["a"]["title"] == "новое значение"

    # Память курсора искусственно опустошается: событие больше не «знакомо».
    state = sync.load_checkpoint(cursor, SITE)
    state.applied_events = []
    sync.save_checkpoint(cursor, state)

    result = sync.pull(site_id=SITE, profile=PROFILE, fetch=lambda s: [old],
                       checkpoint_path=cursor, apply_batch=catalog.apply)
    assert result.applied == 0
    assert result.duplicates == 1
    assert catalog.titles["a"]["title"] == "новое значение", "старое событие вернулось"


def test_cursor_memory_does_not_grow_without_bound(cursor: Path):
    checkpoint = sync.Checkpoint(site_id=SITE, memory=10)
    for i in range(100):
        checkpoint.remember(f"e-{i}")
    assert len(checkpoint.applied_events) == 10
    assert checkpoint.seen("e-99")
