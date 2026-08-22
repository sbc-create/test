"""Редакция: provenance, календарь, свежесть витрин, дубли между tenant, discovery."""
from datetime import date, timedelta

import pytest

from seo_operator.editorial import calendar as cal
from seo_operator.editorial import discovery, duplicates, homepage
from seo_operator.editorial.provenance import (FactClaim, check_text_for_speculation,
                                               release_date_statement, required_disclosure,
                                               validate_claims)


# --- provenance ---------------------------------------------------------------

def test_unsourced_fact_is_a_violation():
    report = validate_claims([FactClaim("release_date", "2026-09-05", source=None)])
    assert not report.ok
    assert "release_date" in report.omitted_fields


def test_low_confidence_fact_is_omitted_not_guessed():
    report = validate_claims([FactClaim("cast", ["X"], source="feed", confidence="low")])
    assert report.ok
    assert "cast" in report.omitted_fields and "cast" not in report.publishable_fields


def test_confirmed_fact_is_publishable():
    report = validate_claims([FactClaim("release_date", "2026-09-05", source="studio",
                                        confidence="confirmed")])
    assert report.publishable_fields == ["release_date"]


def test_unconfirmed_date_renders_honestly():
    claim = FactClaim("release_date", "2026-09-05", source="rumor", confidence="low")
    assert release_date_statement(claim) == "дата не объявлена"


def test_confirmed_date_renders_exactly():
    claim = FactClaim("release_date", "2026-09-05", source="studio", confidence="confirmed")
    assert release_date_statement(claim) == "2026-09-05"


@pytest.mark.parametrize("text", [
    "Вероятно выйдет осенью", "Ожидается в 2027 году", "По слухам сериал продлён",
    "Предположительно 12 серий", "Скорее всего премьера в марте",
])
def test_speculation_is_flagged(text):
    assert check_text_for_speculation(text)


def test_promotion_must_be_disclosed():
    out = required_disclosure({"is_promotion": True})
    assert out and "Реклама" in out[0]


def test_ai_authorship_is_disclosed():
    assert required_disclosure({"generated_by": "operator"})


# --- календарь ----------------------------------------------------------------

def _entry(**kw):
    base = dict(external_id="stellar-drift", site_id="demo-fixture", title_ru="Звёздный дрейф",
                title_original="Stellar Drift", status=cal.Status.ANNOUNCED,
                release_date="2026-09-05", release_date_confirmed=True,
                source="studio", source_confidence="confirmed",
                rights_ref="rights://demo/stellar-drift", checked_at="2026-08-22T00:00:00Z")
    base.update(kw)
    return cal.CalendarEntry(**base)


def test_released_titles_are_promoted_automatically():
    e = _entry(release_date="2026-08-01")
    changed = cal.promote_released([e], today=date(2026, 8, 22))
    assert changed and e.status is cal.Status.RELEASED


def test_stale_announcement_expires_and_unpins():
    e = _entry(release_date="2026-08-01", pinned_until="2026-12-01")
    e.status = cal.Status.ANNOUNCED
    changed = cal.expire_stale([e], today=date(2026, 8, 22))
    assert changed and e.status is cal.Status.EXPIRED
    assert e.pinned_until is None, "Просроченный анонс обязан сниматься с витрины"


def test_future_announcement_is_kept():
    e = _entry(release_date="2026-12-01")
    assert cal.expire_stale([e], today=date(2026, 8, 22)) == []


def test_invalid_transition_is_rejected():
    e = _entry(status=cal.Status.RELEASED)
    with pytest.raises(cal.InvalidTransition):
        cal.transition(e, cal.Status.ANNOUNCED, "нельзя вернуть назад")


def test_cancelled_entry_drops_pin():
    e = _entry(pinned_until="2026-12-01")
    cal.transition(e, cal.Status.CANCELLED, "студия отменила")
    assert e.pinned_until is None


def test_announcement_requires_rights():
    ok, why = cal.announceable(_entry(rights_ref=None))
    assert not ok and "rights_ref" in why


def test_unconfirmed_date_blocks_dated_announcement():
    ok, why = cal.announceable(_entry(release_date_confirmed=False))
    assert not ok and "дата не подтверждена" in why


def test_ready_entry_is_announceable():
    ok, _ = cal.announceable(_entry())
    assert ok


# --- свежесть главной ---------------------------------------------------------

def test_expired_pin_is_reported():
    plan = homepage.default_plan("demo-fixture")
    plan.modules[2].pinned_items = ["stellar-drift"]
    plan.modules[2].pin_expires = {"stellar-drift": "2026-08-01"}
    issues = homepage.audit_freshness(plan, {}, today=date(2026, 8, 22))
    assert any("истёк" in i.problem for i in issues)


def test_pin_without_expiry_is_reported():
    plan = homepage.default_plan("demo-fixture")
    plan.modules[2].pinned_items = ["stellar-drift"]
    issues = homepage.audit_freshness(plan, {}, today=date(2026, 8, 22))
    assert any("без даты истечения" in i.problem for i in issues)


def test_released_title_must_leave_coming_soon():
    plan = homepage.default_plan("demo-fixture")
    plan.modules[2].pinned_items = ["stellar-drift"]
    plan.modules[2].pin_expires = {"stellar-drift": "2026-12-01"}
    entries = {"stellar-drift": _entry(status=cal.Status.RELEASED)}
    issues = homepage.audit_freshness(plan, entries, today=date(2026, 8, 22))
    assert any("остаётся в «Скоро»" in i.problem for i in issues)


def test_cancelled_title_is_flagged_for_removal():
    plan = homepage.default_plan("demo-fixture")
    plan.modules[2].pinned_items = ["stellar-drift"]
    plan.modules[2].pin_expires = {"stellar-drift": "2026-12-01"}
    entries = {"stellar-drift": _entry(status=cal.Status.CANCELLED)}
    issues = homepage.audit_freshness(plan, entries, today=date(2026, 8, 22))
    assert any(i.problem == "Материал отменён" for i in issues)


def test_reorder_produces_rollback_before_apply():
    plan = homepage.default_plan("demo-fixture")
    order = plan.order()
    new_order = [order[1], order[0]] + order[2:]
    new_plan, before, rollback = homepage.reorder(plan, new_order, "EXP-1")
    assert new_plan.order() == new_order
    assert before["module_order"] == order
    assert rollback["executable"] and rollback["restore_order"] == order


def test_reorder_rejects_module_loss():
    plan = homepage.default_plan("demo-fixture")
    with pytest.raises(ValueError):
        homepage.reorder(plan, plan.order()[:-1], "EXP-1")


# --- дубли --------------------------------------------------------------------

SAME = ("Второй сезон продолжает историю экипажа после финала первого сезона. "
        "Эпизоды выходят еженедельно, доступны озвучка и субтитры.")


def test_cross_tenant_text_duplication_blocks_publication():
    findings = duplicates.compare_texts([
        {"id": "a", "site_id": "s1", "text": SAME},
        {"id": "b", "site_id": "s2", "text": SAME},
    ])
    ok, reasons = duplicates.gate(findings)
    assert not ok and "cross_tenant" in reasons[0]


def test_distinct_texts_pass():
    findings = duplicates.compare_texts([
        {"id": "a", "site_id": "s1", "text": SAME},
        {"id": "b", "site_id": "s2", "text": "Разбор финала: что означает сцена после титров "
                                             "и как она связана с сюжетом манги."},
    ])
    assert duplicates.gate(findings)[0]


def test_identical_collections_across_tenants_blocked():
    findings = duplicates.compare_collections([
        {"id": "c1", "site_id": "s1", "item_ids": ["a", "b", "c", "d"]},
        {"id": "c2", "site_id": "s2", "item_ids": ["a", "b", "c", "d"]},
    ])
    assert findings and findings[0].blocking


def test_identical_homepage_layouts_blocked():
    order = ["hero", "new_releases", "coming_soon", "ongoing", "popular"]
    findings = duplicates.compare_layouts([
        {"site_id": "s1", "module_order": order},
        {"site_id": "s2", "module_order": order},
    ])
    assert findings and findings[0].blocking


def test_material_without_new_facts_is_not_published():
    ok, why = duplicates.distinct_value_check(
        {"text": "короткий текст", "facts": ["release_date"]},
        [{"id": "existing", "text": "другой текст", "facts": ["release_date"]}])
    assert not ok and "не добавляет" in why.lower()


def test_material_with_new_facts_is_publishable():
    ok, why = duplicates.distinct_value_check(
        {"text": "разбор структуры сезона", "facts": ["episode_count", "watch_order"]},
        [{"id": "existing", "text": "аннотация", "facts": ["release_date"]}])
    assert ok


# --- discovery ----------------------------------------------------------------

def test_discovery_finds_and_ranks_titles(isolated_state):
    from seo_operator import config
    site = config.get_site("demo-fixture")
    entries, opps = discovery.discover_from_fixture(
        site, {"priority_segments": ["new_releases"]}, today=date(2026, 8, 22))
    assert len(entries) == 5
    assert opps == sorted(opps, key=lambda o: -o.score)
    assert all(o.rationale for o in opps)


def test_discovery_blocks_titles_without_rights(isolated_state):
    from seo_operator import config
    site = config.get_site("demo-fixture")
    items = [{"external_id": "x", "title_ru": "Без прав", "title_original": "No Rights",
              "release_date": "2026-09-01", "release_date_confirmed": True,
              "status": "announced", "rights_ref": None, "source": "feed",
              "source_confidence": "high", "seasons": 1, "media_available": False}]
    _, opps = discovery.discover(site, items, {}, today=date(2026, 8, 22))
    assert opps[0].proposed_status == "hold"
    assert any("rights_ref" in b for b in opps[0].blockers)


def test_discovery_respects_forbidden_topics(isolated_state):
    from seo_operator import config
    site = config.get_site("demo-fixture")
    items = [{"external_id": "banned", "title_ru": "X", "title_original": "X",
              "release_date": None, "release_date_confirmed": False, "status": "available",
              "rights_ref": "r://x", "source": "feed", "source_confidence": "high",
              "seasons": 1, "media_available": True}]
    entries, opps = discovery.discover(site, items, {"forbidden_topics": ["banned"]})
    assert entries == [] and opps == []


def test_undated_announcement_is_labelled_honestly(isolated_state):
    from seo_operator import config
    site = config.get_site("demo-fixture")
    items = [{"external_id": "y", "title_ru": "Аноннс", "title_original": "Y",
              "release_date": "2026-11-01", "release_date_confirmed": False,
              "status": "announced", "rights_ref": "r://y", "source": "studio",
              "source_confidence": "high", "seasons": 1, "media_available": False}]
    entries, opps = discovery.discover(site, items, {}, today=date(2026, 8, 22))
    assert entries[0].status is cal.Status.UNDATED
    assert entries[0].date_display == "дата не объявлена"
    assert opps[0].proposed_status == "prepare_undated_announcement"
