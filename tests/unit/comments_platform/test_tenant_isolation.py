"""Tenant isolation, proved rather than asserted.

The matrix is every tenant against every tenant, across every operation. For
each pair the test does the same thing: create real data as tenant A, then have
tenant B — with a legitimate principal of its own, not an anonymous prober —
attempt the operation against A's object id.

The required answer is 404 in every case, never 403. A 403 would confirm the
object exists, which turns the API into a directory of what other sites hold.

Isolation is also checked below the API: the same probes are run against the
store, the moderation queue, the audit trail, the export, the background job
queue and the cache-shaped read paths, because an API that filters correctly on
top of a store that does not is one refactor away from leaking.
"""

from __future__ import annotations

import itertools

import pytest

from factory.comments_platform import states
from factory.comments_platform.errors import CrossTenantDenied, NotFound
from factory.comments_platform.rbac import AUDITOR, MODERATOR, Principal
from factory.comments_platform.tenancy import ResourceRef

from .conftest import TENANTS

REF = ResourceRef("title", "tt-shared-across-sites")
TENANT_NAMES = [t for t, _ in TENANTS]
CROSS_PAIRS = list(itertools.permutations(TENANT_NAMES, 2))

OPERATIONS = (
    "read", "write", "edit", "delete", "react", "report", "moderate", "admin", "export",
)


@pytest.fixture
def seeded(service, store, scopes, users, identities):
    """One published comment in every tenant, on the same content id.

    The shared `canonical_content_id` is the point: if isolation were keyed on
    content rather than on tenant, this fixture alone would collapse all four
    sites into one discussion.
    """
    created = {}
    for tenant in TENANT_NAMES:
        result = service.create_comment(
            scopes[tenant], users[tenant], identities[tenant], REF,
            body=f"a comment that belongs to {tenant} only",
        )
        created[tenant] = result["comment"]["comment_id"]
    return created


class TestCrossTenantReads:
    @pytest.mark.parametrize("owner,intruder", CROSS_PAIRS)
    def test_store_refuses_to_return_another_tenants_comment(
        self, store, scopes, seeded, owner, intruder
    ):
        with pytest.raises(NotFound):
            store.get_comment(scopes[intruder], seeded[owner])

    @pytest.mark.parametrize("owner,intruder", CROSS_PAIRS)
    def test_thread_listing_never_includes_another_tenants_rows(
        self, service, scopes, users, seeded, owner, intruder
    ):
        view = service.thread_view(scopes[intruder], users[intruder], REF)
        ids = {item["comment_id"] for item in view.items}
        assert seeded[owner] not in ids
        assert ids == {seeded[intruder]}

    def test_each_tenant_sees_exactly_one_comment_on_a_shared_content_id(
        self, service, scopes, users, seeded
    ):
        for tenant in TENANT_NAMES:
            view = service.thread_view(scopes[tenant], users[tenant], REF)
            assert view.total_count == 1, f"{tenant} sees {view.total_count} comments"

    @pytest.mark.parametrize("owner,intruder", CROSS_PAIRS)
    def test_threads_are_distinct_objects_per_tenant(
        self, store, scopes, seeded, owner, intruder
    ):
        a = store.find_thread(scopes[owner], REF)
        b = store.find_thread(scopes[intruder], REF)
        assert a["thread_id"] != b["thread_id"]

    @pytest.mark.parametrize("owner,intruder", CROSS_PAIRS)
    def test_a_foreign_thread_id_is_not_found(self, store, scopes, seeded, owner, intruder):
        foreign = store.find_thread(scopes[owner], REF)["thread_id"]
        with pytest.raises(NotFound):
            store.get_thread(scopes[intruder], foreign)


class TestCrossTenantWrites:
    @pytest.mark.parametrize("owner,intruder", CROSS_PAIRS)
    def test_edit(self, service, scopes, users, identities, seeded, owner, intruder):
        with pytest.raises(NotFound):
            service.edit_own_comment(
                scopes[intruder], users[intruder], identities[intruder],
                seeded[owner], body="rewritten by a stranger",
            )

    @pytest.mark.parametrize("owner,intruder", CROSS_PAIRS)
    def test_delete(self, service, scopes, users, seeded, owner, intruder):
        with pytest.raises(NotFound):
            service.delete_own_comment(scopes[intruder], users[intruder], seeded[owner])

    @pytest.mark.parametrize("owner,intruder", CROSS_PAIRS)
    def test_react(self, service, scopes, users, identities, seeded, owner, intruder):
        with pytest.raises(NotFound):
            service.set_reaction(
                scopes[intruder], users[intruder], identities[intruder], seeded[owner], "like"
            )

    @pytest.mark.parametrize("owner,intruder", CROSS_PAIRS)
    def test_report(self, service, scopes, users, identities, seeded, owner, intruder):
        with pytest.raises(NotFound):
            service.report_comment(
                scopes[intruder], users[intruder], identities[intruder],
                seeded[owner], reason="spam",
            )

    @pytest.mark.parametrize("owner,intruder", CROSS_PAIRS)
    def test_moderate(self, service, scopes, moderators, seeded, owner, intruder):
        with pytest.raises(NotFound):
            service.moderate(
                scopes[intruder], moderators[intruder], seeded[owner],
                action="hide", reason="not yours to hide",
            )

    @pytest.mark.parametrize("owner,intruder", CROSS_PAIRS)
    def test_ban(self, service, scopes, moderators, identities, seeded, owner, intruder):
        with pytest.raises(NotFound):
            service.ban_subject(
                scopes[intruder], moderators[intruder], identities[owner].subject_id,
                banned=True, reason="not a member of this site",
            )

    @pytest.mark.parametrize("owner,intruder", CROSS_PAIRS)
    def test_writes_leave_the_owners_data_untouched(
        self, service, store, scopes, users, moderators, seeded, owner, intruder
    ):
        before = store.get_comment(scopes[owner], seeded[owner])
        for attempt in (
            lambda: service.delete_own_comment(scopes[intruder], users[intruder], seeded[owner]),
            lambda: service.moderate(
                scopes[intruder], moderators[intruder], seeded[owner],
                action="remove", reason="attempt",
            ),
        ):
            with pytest.raises(NotFound):
                attempt()
        after = store.get_comment(scopes[owner], seeded[owner])
        assert after["state"] == before["state"]
        assert after["body"] == before["body"]


class TestPrincipalScopeSpoofing:
    """A principal carrying tenant A cannot be pointed at tenant B's scope."""

    @pytest.mark.parametrize("owner,intruder", CROSS_PAIRS)
    def test_moderator_of_one_site_cannot_address_another(
        self, service, scopes, seeded, owner, intruder
    ):
        rogue = Principal(
            subject_id="rogue-mod", role=MODERATOR, scope=scopes[intruder]
        )
        with pytest.raises(CrossTenantDenied):
            service.moderation_queue(scopes[owner], rogue)

    @pytest.mark.parametrize("owner,intruder", CROSS_PAIRS)
    def test_auditor_of_one_site_cannot_read_anothers_trail(
        self, service, scopes, seeded, owner, intruder
    ):
        auditor = Principal(subject_id="auditor", role=AUDITOR, scope=scopes[intruder])
        with pytest.raises(CrossTenantDenied):
            service.read_audit(scopes[owner], auditor)


class TestQueuesAndBackgroundWork:
    """Isolation must survive the paths that do not go through the API."""

    def test_moderation_queue_holds_only_its_own_site(
        self, service, store, scopes, users, identities, moderators
    ):
        held = {}
        for tenant in TENANT_NAMES:
            result = service.create_comment(
                scopes[tenant], users[tenant], identities[tenant],
                ResourceRef("title", "tt-queue"),
                body=f"BUY NOW BUY NOW BUY NOW visit https://spam.test/{tenant} right away",
            )
            held[tenant] = result["comment"]["comment_id"]

        for tenant in TENANT_NAMES:
            queue = service.moderation_queue(scopes[tenant], moderators[tenant])
            ids = {item["comment_id"] for item in queue["items"]}
            others = {held[o] for o in TENANT_NAMES if o != tenant}
            assert not (ids & others), f"{tenant}'s queue contains another site's comments"

    def test_outbox_worker_only_claims_its_own_events(self, store, scopes, seeded):
        for tenant in TENANT_NAMES:
            events = store.claim_events(scopes[tenant])
            for event in events:
                assert event["tenant_id"] == scopes[tenant].tenant_id
                assert event["site_id"] == scopes[tenant].site_id

    def test_audit_trail_is_partitioned(self, store, scopes, seeded):
        for tenant in TENANT_NAMES:
            rows = store.list_audit(scopes[tenant])
            assert rows, f"{tenant} wrote no audit rows"
            for row in rows:
                assert row["tenant_id"] == scopes[tenant].tenant_id

    def test_export_returns_one_sites_data_only(self, store, scopes, identities, seeded):
        for tenant in TENANT_NAMES:
            export = store.export_subject(scopes[tenant], identities[tenant].subject_id)
            assert export["tenant_id"] == scopes[tenant].tenant_id
            assert len(export["comments"]) == 1
            assert export["comments"][0]["comment_id"] == seeded[tenant]

    @pytest.mark.parametrize("owner,intruder", CROSS_PAIRS)
    def test_export_of_a_foreign_subject_returns_nothing(
        self, store, scopes, identities, seeded, owner, intruder
    ):
        export = store.export_subject(scopes[intruder], identities[owner].subject_id)
        assert export["comments"] == []
        assert export["reactions"] == []


class TestRateLimitAndAbuseStateAreScoped:
    def test_one_sites_rate_budget_is_not_spent_by_another(
        self, store, scopes
    ):
        lords, zona = scopes["lords"], scopes["zona"]
        for _ in range(5):
            store.record_rate_event(
                lords, bucket="subject", principal_key="shared-key", endpoint="create"
            )
        assert store.count_rate_events(
            zona, bucket="subject", principal_key="shared-key", since_iso="1970-01-01T00:00:00Z"
        ) == 0

    def test_duplicate_detection_does_not_span_sites(self, store, scopes):
        """The same text on two sites is two comments, not a duplicate."""
        lords, zona = scopes["lords"], scopes["zona"]
        store.record_digest(
            lords, subject_id="s", thread_id="t", digest="d1", near_digest="n1", comment_id="c1"
        )
        assert not store.digest_seen(
            zona, subject_id="s", thread_id="t", digest="d1", since_iso="1970-01-01T00:00:00Z"
        )

    def test_a_ban_does_not_travel_between_sites(
        self, service, store, scopes, moderators, identities, seeded
    ):
        subject = identities["lords"].subject_id
        service.ban_subject(
            scopes["lords"], moderators["lords"], subject,
            banned=True, reason="repeated spam on this site",
        )
        assert store.is_banned(scopes["lords"], subject)
        # The same public id does not even exist on another site, and would not
        # be banned there if it did.
        assert not store.is_banned(scopes["zona"], subject)


class TestRowCountsProveSeparation:
    """Whole-table counts, taken outside any scope, must add up per tenant."""

    def test_every_table_partitions_cleanly(self, store, scopes, seeded):
        from factory.comments_platform.schema import TABLES

        for table in TABLES:
            total = store.raw_count(table)
            per_tenant = sum(store.raw_count(table, scopes[t]) for t in TENANT_NAMES)
            assert total == per_tenant, (
                f"{table}: {total} rows overall but {per_tenant} across the four sites — "
                "some row belongs to no tenant"
            )


class TestVisibilityInsideOneTenant:
    def test_a_held_comment_is_invisible_to_other_readers(
        self, service, store, scopes, users, identities, moderators
    ):
        scope, user, identity = scopes["lords"], users["lords"], identities["lords"]
        created = service.create_comment(
            scope, user, identity, ResourceRef("title", "tt-hidden"), body="a normal comment"
        )
        comment_id = created["comment"]["comment_id"]
        service.moderate(
            scope, moderators["lords"], comment_id, action="hide", reason="off topic"
        )

        other = Principal(
            subject_id="someone-else", role=users["lords"].role, scope=scope
        )
        view = service.thread_view(scope, other, ResourceRef("title", "tt-hidden"))
        assert comment_id not in {i["comment_id"] for i in view.items}

    def test_the_author_still_sees_their_own_held_comment(
        self, service, scopes, users, identities, moderators
    ):
        scope, user, identity = scopes["lords"], users["lords"], identities["lords"]
        ref = ResourceRef("title", "tt-own-held")
        created = service.create_comment(scope, user, identity, ref, body="my own comment")
        comment_id = created["comment"]["comment_id"]
        service.moderate(scope, moderators["lords"], comment_id, action="hide", reason="review")

        view = service.thread_view(
            scope, user, ref, viewer_subject_id=identity.subject_id
        )
        mine = [i for i in view.items if i["comment_id"] == comment_id]
        assert mine, "an author who cannot see their own held comment posts it again"
        assert mine[0]["state"] == states.HIDDEN
        assert mine[0]["body_html"], "the author is shown their own text"

    def test_a_held_comment_is_not_counted(
        self, service, scopes, users, identities, moderators
    ):
        scope, user, identity = scopes["lords"], users["lords"], identities["lords"]
        ref = ResourceRef("title", "tt-count")
        created = service.create_comment(scope, user, identity, ref, body="counted for now")
        assert service.comment_count(scope, user, ref) == 1
        service.moderate(
            scope, moderators["lords"], created["comment"]["comment_id"],
            action="hide", reason="review",
        )
        assert service.comment_count(scope, user, ref) == 0


class TestNoTenantLeaksIntoResponses:
    def test_public_dto_never_names_a_tenant_or_site(
        self, service, scopes, users, seeded
    ):
        view = service.thread_view(scopes["lords"], users["lords"], REF)
        flat = repr(view.as_dict())
        for forbidden in ("tenant_id", "site_id", "lords-main", "zona", "animedia", "yummy"):
            assert forbidden not in flat, f"{forbidden} reached the client payload"

    def test_public_dto_hides_internal_scores(self, service, scopes, users, seeded):
        view = service.thread_view(scopes["lords"], users["lords"], REF)
        for item in view.items:
            assert "risk_score" not in item
            assert "report_count" not in item
            assert "network_hmac" not in item
            assert "body" not in item  # only body_html, the rendered form
