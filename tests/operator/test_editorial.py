"""Editorial lifecycle tests: sourcing, announcements, stale promises, dedup."""

from __future__ import annotations

from datetime import date

import pytest

from seo_operator.editorial import (
    Announcement,
    AnnouncementState,
    BacklogItem,
    Claim,
    EditorialCalendar,
    EditorialSource,
    SourceTrust,
    UnsourcedClaimError,
    detect_cross_site_duplication,
    find_expired_pins,
    find_stale_promises,
)

OFFICIAL = EditorialSource(
    "src-official",
    "Официальный канал студии",
    "https://studio.example/news",
    SourceTrust.OFFICIAL,
    rights_confirmed=True,
)
RUMOUR = EditorialSource(
    "src-forum", "Форум", "https://forum.example", SourceTrust.UNCONFIRMED, rights_confirmed=False
)
NO_RIGHTS = EditorialSource(
    "src-press",
    "Издание",
    "https://press.example",
    SourceTrust.PRESS_CONFIRMED,
    rights_confirmed=False,
)


class TestSourcing:
    def test_claim_from_official_source_is_allowed(self):
        claim = Claim("release_date", "2026-09-01", OFFICIAL)
        assert claim.value == "2026-09-01"

    def test_claim_from_rumour_is_rejected(self):
        """The core anti-fabrication guard."""
        with pytest.raises(UnsourcedClaimError, match="публикация запрещена"):
            Claim("release_date", "2026-09-01", RUMOUR)

    def test_confirmed_source_without_rights_is_rejected(self):
        with pytest.raises(UnsourcedClaimError):
            Claim("synopsis", "текст", NO_RIGHTS)


class TestAnnouncementLifecycle:
    def make(self, release="2026-09-01", **kw):
        return Announcement(
            site_id="site-a",
            entity_id="title-42",
            title_claim=Claim("title", "Название", OFFICIAL),
            release_date_claim=Claim("release_date", release, OFFICIAL),
            **kw,
        )

    def test_announce_to_release(self):
        ann = self.make()
        assert ann.state is AnnouncementState.ANNOUNCED
        ann.transition(AnnouncementState.RELEASED, source=OFFICIAL, note="вышло")
        assert ann.state is AnnouncementState.RELEASED
        assert ann.history[-1]["from"] == "announced"

    def test_transition_requires_confirmed_source(self):
        ann = self.make()
        with pytest.raises(UnsourcedClaimError):
            ann.transition(AnnouncementState.CANCELLED, source=RUMOUR)

    def test_delay_and_cancel_are_recorded(self):
        ann = self.make()
        ann.transition(AnnouncementState.DELAYED, source=OFFICIAL, note="перенос")
        ann.transition(AnnouncementState.CANCELLED, source=OFFICIAL, note="отмена")
        assert [h["to"] for h in ann.history] == ["delayed", "cancelled"]

    def test_stale_promise_detected_after_date_passes(self):
        ann = self.make(release="2026-08-01")
        assert ann.is_stale_promise(date(2026, 8, 22)) is True
        assert find_stale_promises([ann], date(2026, 8, 22)) == [ann]

    def test_released_item_is_not_a_stale_promise(self):
        ann = self.make(release="2026-08-01")
        ann.transition(AnnouncementState.RELEASED, source=OFFICIAL)
        assert ann.is_stale_promise(date(2026, 8, 22)) is False

    def test_future_announcement_is_not_stale(self):
        ann = self.make(release="2026-12-01")
        assert ann.is_stale_promise(date(2026, 8, 22)) is False

    def test_expired_pin_detected(self):
        ann = self.make(pinned_until="2026-08-10")
        assert find_expired_pins([ann], date(2026, 8, 22)) == [ann]

    def test_active_pin_not_flagged(self):
        ann = self.make(pinned_until="2026-09-30")
        assert find_expired_pins([ann], date(2026, 8, 22)) == []


class TestCalendar:
    def test_schedule_and_find_due(self):
        cal = EditorialCalendar("site-a")
        item = BacklogItem("site-a", "Подборка осенних премьер", "Подборки", "informational")
        cal.schedule(item, date(2026, 8, 25))
        assert cal.due(date(2026, 8, 22)) == [item]

    def test_item_from_another_site_is_rejected(self):
        cal = EditorialCalendar("site-a")
        item = BacklogItem("site-b", "Чужой материал", "Подборки", "informational")
        with pytest.raises(ValueError, match="нельзя ставить"):
            cal.schedule(item, date(2026, 8, 25))

    def test_item_outside_horizon_not_due(self):
        cal = EditorialCalendar("site-a")
        item = BacklogItem("site-a", "Далёкий материал", "Подборки", "informational")
        cal.schedule(item, date(2026, 10, 1))
        assert cal.due(date(2026, 8, 22)) == []


def test_cross_site_duplicate_titles_detected():
    """Identical planned content across sites must be caught before publishing."""
    items = [
        BacklogItem("site-a", "Топ-10 новинок сезона", "Подборки", "informational"),
        BacklogItem("site-b", "Топ-10 новинок сезона", "Подборки", "informational"),
        BacklogItem("site-c", "Уникальный материал", "Обзоры", "informational"),
    ]
    dupes = detect_cross_site_duplication(items)
    assert len(dupes) == 1
    assert sorted(dupes[0][1]) == ["site-a", "site-b"]


def test_distinct_titles_across_sites_are_fine():
    items = [
        BacklogItem("site-a", "Материал А", "Подборки", "informational"),
        BacklogItem("site-b", "Материал Б", "Подборки", "informational"),
    ]
    assert detect_cross_site_duplication(items) == []
