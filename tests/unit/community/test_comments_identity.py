"""Identity reuse — SIGNED_PSEUDONYMOUS_DEVICE_V1, no second cookie."""

from __future__ import annotations

from factory.community.comments.api import CommunityCommentsAPI
from factory.community.comments.flags import isolation_invariants
from factory.community.comments.service import CommentsService
from factory.community.identity_v1 import (
    COOKIE_NAME,
    IDENTITY_MODE,
    issue_token,
    mint_identity_id,
    set_cookie_header,
    verify_token,
)
from factory.community.store import CommunityStore


def test_isolation_invariants_single_cookie():
    inv = isolation_invariants()
    assert inv["IDENTITY_MODE"] == IDENTITY_MODE
    assert inv["IDENTITY_COOKIE"] == COOKIE_NAME == "yummy_cr_vid"
    assert inv["SECOND_COOKIE_FORBIDDEN"] is True


def test_api_reuses_existing_identity(tmp_path):
    store = CommunityStore(tmp_path / "cid.sqlite")
    api = CommunityCommentsAPI(CommentsService(store))
    iid = mint_identity_id()
    cookie = set_cookie_header(issue_token(identity_id=iid))
    out = api.create_comment(
        site_space="yummy",
        title_id="t1",
        body="Комментарий с уже выданным identity cookie.",
        origin="https://yummyani.site",
        csrf_token="tok",
        session_csrf="tok",
        cookie_header=cookie,
        bypass_write_flag_for_tests=True,
    )
    assert out["status"] == 201
    assert out["comment"]["identity_id"] == iid
    assert "set_cookie" not in out or out.get("set_cookie") is None
    store.close()


def test_mint_uses_same_cookie_name(tmp_path):
    store = CommunityStore(tmp_path / "cid2.sqlite")
    api = CommunityCommentsAPI(CommentsService(store))
    out = api.create_comment(
        site_space="yummy",
        title_id="t1",
        body="Первый визит без cookie — mint того же имени.",
        origin="https://yummyani.site",
        csrf_token="tok",
        session_csrf="tok",
        cookie_header="",
        bypass_write_flag_for_tests=True,
    )
    assert out["status"] == 201
    token = out["set_cookie"]
    assert token.startswith("v1.")
    # set_cookie from resolve_or_mint is raw token; header builder uses COOKIE_NAME
    assert verify_token(token)
    assert COOKIE_NAME == "yummy_cr_vid"
    store.close()
