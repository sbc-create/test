"""Moderation queue actions, RBAC, reports, edit history, soft delete."""

from __future__ import annotations

import pytest

from factory.community.comments.admin import CommentsAdmin, assert_forbidden_capabilities
from factory.community.comments.flags import comments_dark_flags, forbid_admin_capability
from factory.community.comments.service import CommentsService
from factory.community.identity_v1 import mint_identity_id
from factory.community.store import CommunityStore


@pytest.fixture()
def admin_svc(tmp_path):
    store = CommunityStore(tmp_path / "cmod.sqlite")
    svc = CommentsService(store)
    yield CommentsAdmin(svc), svc
    store.close()


def test_forbidden_capabilities_locked():
    assert_forbidden_capabilities()
    with pytest.raises(PermissionError):
        forbid_admin_capability("ADMIN_FAKE_COMMENT_INSERT")
    with pytest.raises(PermissionError):
        forbid_admin_capability("ADMIN_IMPERSONATE_USER")
    with pytest.raises(PermissionError):
        forbid_admin_capability("ADMIN_SILENT_TEXT_REWRITE")


def test_rbac_required(admin_svc):
    admin, _ = admin_svc
    with pytest.raises(PermissionError):
        admin.queue(scopes={"read"}, status="HELD_FOR_REVIEW")


def test_approve_stays_dark(admin_svc):
    admin, svc = admin_svc
    created = svc.create(
        site_space="yummy",
        title_id="t1",
        identity_id=mint_identity_id(),
        body="Комментарий на модерацию без публикации.",
        bypass_write_flag_for_tests=True,
    )
    cid = created["comment"]["comment_id"]
    out = admin.apply(
        scopes={"moderation"},
        comment_id=cid,
        action="approve",
        moderator_identity_id=mint_identity_id(),
        reason_code="OK",
    )
    assert out["status"] == 200
    # Ledger may set published_at for PUBLISHED_UNREVIEWED; public flag stays off.
    assert comments_dark_flags()["COMMENTS_PUBLICATION_ENABLED"] == 0
    assert out["comment"]["status"] == "VISIBLE_QWEN_APPROVED"


def test_hide_unhide_delete_restore_spoiler(admin_svc):
    admin, svc = admin_svc
    cid = svc.create(
        site_space="yummy",
        title_id="t1",
        identity_id=mint_identity_id(),
        body="Цепочка модерационных действий над комментарием.",
        bypass_write_flag_for_tests=True,
    )["comment"]["comment_id"]
    mod = mint_identity_id()
    # Stage01 quarantine/reject aliases → HIDDEN_BY_ADMIN
    assert (
        admin.apply(
            scopes={"moderation"}, comment_id=cid, action="quarantine", moderator_identity_id=mod
        )["comment"]["status"]
        == "HIDDEN_BY_ADMIN"
    )
    assert (
        admin.apply(
            scopes={"moderation"}, comment_id=cid, action="unhide", moderator_identity_id=mod
        )["comment"]["status"]
        == "VISIBLE_QWEN_APPROVED"
    )
    assert (
        admin.apply(
            scopes={"moderation"}, comment_id=cid, action="hide", moderator_identity_id=mod
        )["comment"]["status"]
        == "HIDDEN_BY_ADMIN"
    )
    assert (
        admin.apply(
            scopes={"moderation"}, comment_id=cid, action="restore", moderator_identity_id=mod
        )["comment"]["status"]
        == "HELD_FOR_REVIEW"
    )
    assert (
        admin.apply(
            scopes={"moderation"}, comment_id=cid, action="remove", moderator_identity_id=mod
        )["comment"]["status"]
        == "DELETED_BY_ADMIN"
    )
    # Recreate for spoiler path on a visible comment
    cid2 = svc.create(
        site_space="yummy",
        title_id="t1",
        identity_id=mint_identity_id(),
        body="Спойлерный комментарий для админской пометки.",
        bypass_write_flag_for_tests=True,
    )["comment"]["comment_id"]
    admin.apply(
        scopes={"moderation"}, comment_id=cid2, action="approve", moderator_identity_id=mod
    )
    spoilered = admin.apply(
        scopes={"moderation"}, comment_id=cid2, action="mark_spoiler", moderator_identity_id=mod
    )["comment"]
    assert spoilered["spoiler"] in (1, True)
    cleared = admin.apply(
        scopes={"moderation"}, comment_id=cid2, action="clear_spoiler", moderator_identity_id=mod
    )["comment"]
    assert cleared["spoiler"] in (0, False)


def test_report_and_dismiss(admin_svc):
    admin, svc = admin_svc
    cid = svc.create(
        site_space="yummy",
        title_id="t1",
        identity_id=mint_identity_id(),
        body="Комментарий который пожалуют и отклонят жалобу.",
        bypass_write_flag_for_tests=True,
    )["comment"]["comment_id"]
    rep = svc.report(
        comment_id=cid,
        identity_id=mint_identity_id(),
        reason_code="SPAM",
        bypass_write_flag_for_tests=True,
    )
    assert rep["status"] == 201
    out = admin.apply(
        scopes={"moderation"},
        comment_id=cid,
        action="dismiss_report",
        moderator_identity_id=mint_identity_id(),
        report_id=rep["report_id"],
    )
    assert out["status"] == 200
    row = svc.store.conn.execute(
        "SELECT status FROM community_content_reports WHERE report_id=?",
        (rep["report_id"],),
    ).fetchone()
    assert row["status"] == "DISMISSED"


def test_edit_history_immutable(admin_svc):
    _, svc = admin_svc
    iid = mint_identity_id()
    created = svc.create(
        site_space="yummy",
        title_id="t1",
        identity_id=iid,
        body="Версия один исходный текст комментария.",
        bypass_write_flag_for_tests=True,
    )
    cid = created["comment"]["comment_id"]
    svc.edit(
        comment_id=cid,
        identity_id=iid,
        body="Версия два изменённый текст комментария.",
        bypass_write_flag_for_tests=True,
    )
    revs = svc.revisions(cid)
    assert len(revs) == 2
    assert revs[0]["body"] != revs[1]["body"]
    assert revs[0]["version"] == 1
    assert revs[1]["version"] == 2


def test_soft_delete_keeps_row(admin_svc):
    _, svc = admin_svc
    iid = mint_identity_id()
    cid = svc.create(
        site_space="yummy",
        title_id="t1",
        identity_id=iid,
        body="Мягкое удаление автором без hard delete.",
        bypass_write_flag_for_tests=True,
    )["comment"]["comment_id"]
    svc.delete_by_user(comment_id=cid, identity_id=iid, bypass_write_flag_for_tests=True)
    row = svc.store.conn.execute(
        "SELECT status, deleted_at FROM community_comments WHERE comment_id=?", (cid,)
    ).fetchone()
    assert row is not None
    assert row["status"] in ("DELETED_BY_USER", "DELETED_BY_AUTHOR")
    assert row["deleted_at"]


def test_fake_insert_action_forbidden(admin_svc):
    admin, svc = admin_svc
    cid = svc.create(
        site_space="yummy",
        title_id="t1",
        identity_id=mint_identity_id(),
        body="Попытка forbidden admin action должна падать.",
        bypass_write_flag_for_tests=True,
    )["comment"]["comment_id"]
    with pytest.raises(PermissionError):
        admin.apply(
            scopes={"moderation"},
            comment_id=cid,
            action="fake_insert",
            moderator_identity_id=mint_identity_id(),
        )


def test_admin_queue_exposes_qwen_fields_not_identity(admin_svc):
    admin, svc = admin_svc
    cid = svc.create(
        site_space="yummy",
        title_id="t1",
        identity_id=mint_identity_id(),
        body="Комментарий для очереди с полями qwen.",
        bypass_write_flag_for_tests=True,
    )["comment"]["comment_id"]
    svc.store.conn.execute(
        """UPDATE community_comments
           SET qwen_decision_json=?, status='HELD_FOR_REVIEW', moderation_status='HELD_FOR_REVIEW'
           WHERE comment_id=?""",
        (
            '{"action":"HOLD_FOR_REVIEW","labels":["UNKNOWN"],"confidence":0.4,'
            '"reason_codes":["LOW_CONFIDENCE"]}',
            cid,
        ),
    )
    rows = admin.queue(scopes={"moderation"}, status="HELD_FOR_REVIEW")
    assert rows
    hit = next(r for r in rows if r["comment_id"] == cid)
    assert hit["qwen_action"] == "HOLD_FOR_REVIEW"
    assert "UNKNOWN" in hit["qwen_labels"]
    assert "identity_id" not in hit
    assert hit["identity_redacted"]


def test_ban_and_unban_opaque_device(admin_svc):
    admin, svc = admin_svc
    target = mint_identity_id()
    cid = svc.create(
        site_space="yummy",
        title_id="t1",
        identity_id=target,
        body="Комментарий автора которого забанят по opaque device.",
        bypass_write_flag_for_tests=True,
    )["comment"]["comment_id"]
    mod = mint_identity_id()
    out = admin.apply(
        scopes={"moderation"},
        comment_id=cid,
        action="ban_device",
        moderator_identity_id=mod,
        reason_code="ABUSE",
    )
    assert out["status"] == 200
    row = svc.store.conn.execute(
        "SELECT kind FROM community_sanctions WHERE actor_id=? AND kind='DEVICE_BAN'",
        (target,),
    ).fetchone()
    assert row is not None
    admin.apply(
        scopes={"moderation"},
        comment_id=cid,
        action="unban_device",
        moderator_identity_id=mod,
        target_identity_id=target,
    )
    expired = svc.store.conn.execute(
        "SELECT expires_at FROM community_sanctions WHERE actor_id=? AND kind='DEVICE_BAN'",
        (target,),
    ).fetchone()
    assert expired["expires_at"]

