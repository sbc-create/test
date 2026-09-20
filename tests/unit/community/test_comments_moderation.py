"""Moderation queue actions, RBAC, reports, edit history, soft delete."""

from __future__ import annotations

import pytest

from factory.community.comments.admin import CommentsAdmin, assert_forbidden_capabilities
from factory.community.comments.flags import forbid_admin_capability
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
        admin.queue(scopes={"read"}, status="PENDING")


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
    assert out["comment"]["published_at"] == ""
    assert out["comment"]["status"] == "PENDING"


def test_quarantine_reject_remove_restore(admin_svc):
    admin, svc = admin_svc
    cid = svc.create(
        site_space="yummy",
        title_id="t1",
        identity_id=mint_identity_id(),
        body="Цепочка модерационных действий над комментарием.",
        bypass_write_flag_for_tests=True,
    )["comment"]["comment_id"]
    mod = mint_identity_id()
    assert (
        admin.apply(
            scopes={"moderation"}, comment_id=cid, action="quarantine", moderator_identity_id=mod
        )["comment"]["status"]
        == "QUARANTINED"
    )
    assert (
        admin.apply(
            scopes={"moderation"}, comment_id=cid, action="reject", moderator_identity_id=mod
        )["comment"]["status"]
        == "REJECTED"
    )
    assert (
        admin.apply(
            scopes={"moderation"}, comment_id=cid, action="restore", moderator_identity_id=mod
        )["comment"]["status"]
        == "PENDING"
    )
    assert (
        admin.apply(
            scopes={"moderation"}, comment_id=cid, action="remove", moderator_identity_id=mod
        )["comment"]["status"]
        == "REMOVED_BY_MODERATOR"
    )
    assert admin.apply(
        scopes={"moderation"}, comment_id=cid, action="mark_spoiler", moderator_identity_id=mod
    )["comment"]["spoiler"] in (1, True)


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
    assert row["status"] == "DELETED_BY_USER"
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
