"""Владение полями: разные источники не затирают друг друга.

Доказывает: REQ-CELL-OWNERSHIP, REQ-CELL-CONTENTREV.
"""
from __future__ import annotations

import pytest

from factory.cell import ownership
from factory.cell.ownership import (
    Change,
    NotFieldOwner,
    Owner,
    Record,
    RevisionConflict,
)

UUID = "3f2a7c10-0000-4000-8000-000000000001"


def _record() -> Record:
    return Record(title_uuid=UUID, site_id="pilot-cell")


def _catalog(**fields) -> Change:
    return Change(title_uuid=UUID, owner=Owner.CATALOG, fields=fields, source="ingest")


def _seo(**fields) -> Change:
    return Change(title_uuid=UUID, owner=Owner.SEO, fields=fields, source="changeset")


def test_catalog_update_does_not_erase_the_seo_text():
    rec = _record()
    ownership.apply(rec, _catalog(title="Название", year=2024, episodes=12))
    ownership.apply(rec, _seo(seo_description="Описание от редактора"))
    # Источник прислал новую серию.
    ownership.apply(rec, _catalog(episodes=13))
    assert rec.value("episodes") == 13
    assert rec.value("seo_description") == "Описание от редактора"


def test_seo_edit_does_not_reset_episodes_or_rating():
    rec = _record()
    ownership.apply(rec, _catalog(episodes=13, seasons=2))
    ownership.apply(rec, Change(title_uuid=UUID, owner=Owner.EXTERNAL_RATINGS,
                                fields={"rating_external": 8.4}, source="kp"))
    ownership.apply(rec, _seo(seo_title="Смотреть онлайн"))
    assert rec.value("episodes") == 13
    assert rec.value("seasons") == 2
    assert rec.value("rating_external") == 8.4
    assert rec.value("seo_title") == "Смотреть онлайн"


def test_owner_cannot_write_another_owners_field():
    rec = _record()
    with pytest.raises(NotFieldOwner, match="принадлежит catalog"):
        ownership.apply(rec, _seo(episodes=99))
    with pytest.raises(NotFieldOwner, match="принадлежит seo"):
        ownership.apply(rec, _catalog(seo_description="каталог пишет SEO"))


def test_unknown_field_gets_an_owner_before_a_value():
    rec = _record()
    with pytest.raises(NotFieldOwner, match="не числится"):
        ownership.apply(rec, _catalog(unheard_of="значение"))


def test_manual_edit_outranks_both_automatons():
    rec = _record()
    ownership.apply(rec, _catalog(title="Из источника"))
    ownership.apply(rec, Change(title_uuid=UUID, owner=Owner.MANUAL,
                                fields={"title": "Как решил редактор"},
                                reason="источник путает франшизу"))
    # Следующее обновление каталога закреплённое значение не трогает.
    ownership.apply(rec, _catalog(title="Снова из источника"))
    assert rec.value("title") == "Как решил редактор"
    assert any(c["resolution"] == "skipped_pinned" for c in rec.conflicts)


def test_pin_is_released_only_explicitly():
    rec = _record()
    ownership.apply(rec, Change(title_uuid=UUID, owner=Owner.MANUAL,
                                fields={"title": "Ручное"}, reason="так решено"))
    ownership.unpin(rec, "title")
    ownership.apply(rec, _catalog(title="Из источника"))
    assert rec.value("title") == "Из источника"


def test_stale_revision_is_recorded_as_a_conflict_not_silently_applied():
    rec = _record()
    ownership.apply(rec, _catalog(title="раз"))
    ownership.apply(rec, _catalog(title="два"))
    stale = Change(title_uuid=UUID, owner=Owner.SEO,
                   fields={"seo_text": "писал от старой ревизии"},
                   expected_revision=0, reason="долгая сессия")
    with pytest.raises(RevisionConflict) as exc:
        ownership.apply(rec, stale)
    assert exc.value.actual == 2
    assert rec.value("seo_text") is None
    assert rec.conflicts[-1]["resolution"] == "not_applied"


def test_write_on_the_expected_revision_goes_through():
    rec = _record()
    ownership.apply(rec, _catalog(title="раз"))
    ownership.apply(rec, Change(title_uuid=UUID, owner=Owner.SEO,
                                fields={"seo_text": "вовремя"}, expected_revision=1))
    assert rec.value("seo_text") == "вовремя"


def test_change_must_address_a_uuid_not_a_name():
    with pytest.raises(ownership.OwnershipError):
        Change(title_uuid="", owner=Owner.CATALOG, fields={"title": "x"})


def test_change_for_another_title_is_refused():
    rec = _record()
    other = Change(title_uuid="different-uuid", owner=Owner.CATALOG,
                   fields={"title": "чужое"})
    with pytest.raises(ownership.OwnershipError):
        ownership.apply(rec, other)


def test_code_deploy_does_not_roll_content_back():
    ownership.guard_content_revision(incoming=5, current=5, operation="deploy")
    ownership.guard_content_revision(incoming=6, current=5, operation="deploy")
    with pytest.raises(RevisionConflict, match="не откатывает содержимое"):
        ownership.guard_content_revision(incoming=4, current=7, operation="rollback")


def test_round_trip_through_a_document_keeps_owners_and_pins():
    rec = _record()
    ownership.apply(rec, _catalog(title="раз", episodes=3))
    ownership.apply(rec, Change(title_uuid=UUID, owner=Owner.MANUAL,
                                fields={"title": "ручное"}, reason="решено"))
    restored = Record.from_dict(rec.to_dict())
    assert restored.view() == rec.view()
    assert restored.fields["title"].pinned is True
    assert restored.fields["episodes"].owner is Owner.CATALOG


def test_metadata_change_is_not_a_new_episode():
    """Смена описания не должна выглядеть как выход серии.

    Проверяется через владение: число серий принадлежит каталогу и меняется
    только его заявкой.
    """
    rec = _record()
    ownership.apply(rec, _catalog(episodes=12, title="раз"))
    before = rec.value("episodes")
    ownership.apply(rec, _catalog(title="раз, исправленное написание"))
    assert rec.value("episodes") == before
