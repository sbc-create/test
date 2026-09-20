"""Comments API — dark mode, CSRF/Origin, create/edit/delete/list."""

from __future__ import annotations

import pytest

from factory.community.antifraud import AntifraudGuard
from factory.community.comments.api import CommunityCommentsAPI
from factory.community.comments.flags import comments_dark_flags
from factory.community.comments.service import CommentsService
from factory.community.identity_v1 import issue_token, mint_identity_id, set_cookie_header
from factory.community.store import CommunityStore

ORIGIN = "https://yummyani.site"


@pytest.fixture()
def api(tmp_path):
    store = CommunityStore(tmp_path / "capi.sqlite")
    service = CommentsService(store)
    guard = AntifraudGuard()
    yield CommunityCommentsAPI(service, guard), store
    store.close()


def _cookie(identity_id: str | None = None) -> str:
    iid = identity_id or mint_identity_id()
    return set_cookie_header(issue_token(identity_id=iid))


def test_flags_endpoint_dark(api):
    api_obj, _ = api
    out = api_obj.flags()
    assert out["status"] == 200
    assert out["flags"]["COMMENTS_PUBLICATION_ENABLED"] == 0
    assert out["identity_cookie"] == "yummy_cr_vid"


def test_create_denied_when_write_flag_off(api):
    api_obj, _ = api
    assert comments_dark_flags()["COMMENTS_API_WRITE_ENABLED"] == 0
    out = api_obj.create_comment(
        site_space="yummy",
        title_id="title-a",
        body="Нормальный комментарий про сериал.",
        origin=ORIGIN,
        csrf_token="tok",
        session_csrf="tok",
        cookie_header=_cookie(),
    )
    assert out["status"] == 403
    assert out["code"] == "CommentsWriteDisabled"


def test_create_edit_delete_with_test_bypass(api):
    api_obj, store = api
    cookie = _cookie()
    created = api_obj.create_comment(
        site_space="yummy",
        title_id="title-a",
        body="Первый осмысленный комментарий без HTML.",
        origin=ORIGIN,
        csrf_token="tok",
        session_csrf="tok",
        cookie_header=cookie,
        bypass_write_flag_for_tests=True,
    )
    assert created["status"] == 201
    cid = created["comment"]["comment_id"]
    assert created["comment"]["status"] in (
        "PENDING",
        "QUARANTINED",
        "PUBLISHED_UNREVIEWED",
        "PENDING_MODERATION_DEGRADED",
        "HELD_FOR_REVIEW",
    )

    edited = api_obj.edit_comment(
        comment_id=cid,
        body="Обновлённый текст комментария без тегов.",
        origin=ORIGIN,
        csrf_token="tok",
        session_csrf="tok",
        cookie_header=cookie,
        bypass_write_flag_for_tests=True,
    )
    assert edited["status"] == 200
    assert edited["comment"]["version"] == 2
    assert edited["comment"]["edited_at"]

    deleted = api_obj.delete_comment(
        comment_id=cid,
        origin=ORIGIN,
        csrf_token="tok",
        session_csrf="tok",
        cookie_header=cookie,
        bypass_write_flag_for_tests=True,
    )
    assert deleted["status"] == 200
    assert deleted["comment"]["status"] in ("DELETED_BY_USER", "DELETED_BY_AUTHOR")
    assert deleted["comment"]["deleted_at"]


def test_csrf_origin_rejected(api):
    api_obj, _ = api
    bad = api_obj.create_comment(
        site_space="yummy",
        title_id="title-a",
        body="Попытка с чужого origin.",
        origin="https://evil.example",
        csrf_token="a",
        session_csrf="b",
        cookie_header=_cookie(),
        bypass_write_flag_for_tests=True,
    )
    assert bad["status"] == 403


def test_list_hidden_when_public_read_off(api):
    api_obj, _ = api
    out = api_obj.list_comments(site_space="yummy", title_id="title-a")
    assert out["status"] == 200
    assert out["comments"] == []
    assert out.get("dark") is True


def test_list_admin_preview(api):
    api_obj, _ = api
    api_obj.create_comment(
        site_space="yummy",
        title_id="title-a",
        body="Виден только в admin preview режиме.",
        origin=ORIGIN,
        csrf_token="tok",
        session_csrf="tok",
        cookie_header=_cookie(),
        bypass_write_flag_for_tests=True,
    )
    out = api_obj.list_comments(
        site_space="yummy", title_id="title-a", admin_preview=True
    )
    assert out["status"] == 200
    assert len(out["comments"]) >= 1


def test_reject_client_supplied_identity(api):
    api_obj, _ = api
    out = api_obj.create_comment(
        site_space="yummy",
        title_id="title-a",
        body="Клиентский user_id должен быть отвергнут.",
        origin=ORIGIN,
        csrf_token="tok",
        session_csrf="tok",
        cookie_header=_cookie(),
        client_body={"user_id": "attacker"},
        bypass_write_flag_for_tests=True,
    )
    assert out["status"] in (400, 401, 403)
