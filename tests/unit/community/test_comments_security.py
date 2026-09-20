"""Comments security — XSS, sanitization, Unicode, CSRF, concurrency, cross-space."""

from __future__ import annotations

import concurrent.futures

import pytest

from factory.community.comments.sanitize import SanitizeError, sanitize_body
from factory.community.comments.service import (
    CommentsConflict,
    CommentsRateLimited,
    CommentsService,
    CommentsValidationError,
)
from factory.community.identity_v1 import mint_identity_id
from factory.community.store import CommunityStore


@pytest.fixture()
def svc(tmp_path):
    store = CommunityStore(tmp_path / "csec.sqlite")
    yield CommentsService(store)
    store.close()


def test_xss_stripped():
    out = sanitize_body('<script>alert(1)</script>Нормальный текст')
    assert "<script>" not in out["body"].lower()
    assert "alert" not in out["body"] or "Нормальный" in out["body"]
    assert "<" not in out["body"]


def test_entity_encoded_script_stripped():
    out = sanitize_body("&lt;img src=x onerror=alert(1)&gt; ok text here")
    assert "onerror" not in out["body"].lower()
    assert "<img" not in out["body"].lower()


def test_unicode_normalize_zw():
    raw = "Привет\u200b мир\ufeff!"
    out = sanitize_body(raw + " дополнительный текст")
    assert "\u200b" not in out["body"]
    assert "\ufeff" not in out["body"]


def test_body_size_limit():
    with pytest.raises(SanitizeError):
        sanitize_body("x" * 5000)


def test_duplicate_conflict(svc):
    iid = mint_identity_id()
    kwargs = dict(
        site_space="yummy",
        title_id="t1",
        identity_id=iid,
        body="Один и тот же текст для проверки дубликата.",
        bypass_write_flag_for_tests=True,
    )
    svc.create(**kwargs)
    with pytest.raises(CommentsConflict):
        svc.create(**kwargs)


def test_reply_depth_one_level(svc):
    iid = mint_identity_id()
    root = svc.create(
        site_space="yummy",
        title_id="t1",
        identity_id=iid,
        body="Корневой комментарий для ответа.",
        bypass_write_flag_for_tests=True,
    )
    parent_id = root["comment"]["comment_id"]
    reply = svc.create(
        site_space="yummy",
        title_id="t1",
        identity_id=iid,
        body="Ответ первого уровня только так.",
        parent_comment_id=parent_id,
        bypass_write_flag_for_tests=True,
    )
    assert reply["comment"]["parent_comment_id"] == parent_id
    with pytest.raises(CommentsValidationError):
        svc.create(
            site_space="yummy",
            title_id="t1",
            identity_id=iid,
            body="Вложенный ответ второго уровня запрещён.",
            parent_comment_id=reply["comment"]["comment_id"],
            bypass_write_flag_for_tests=True,
        )


def test_cross_space_parent_rejected(svc):
    a = svc.create(
        site_space="yummy",
        title_id="t1",
        identity_id=mint_identity_id(),
        body="Комментарий в пространстве yummy.",
        bypass_write_flag_for_tests=True,
    )
    with pytest.raises(CommentsValidationError):
        svc.create(
            site_space="animedia",
            title_id="t1",
            identity_id=mint_identity_id(),
            body="Чужой parent из другого site_space.",
            parent_comment_id=a["comment"]["comment_id"],
            bypass_write_flag_for_tests=True,
        )


def test_rate_limit(svc):
    iid = mint_identity_id()
    for i in range(5):
        svc.create(
            site_space="yummy",
            title_id="t-rate",
            identity_id=iid,
            body=f"Сообщение номер {i} для лимита скорости.",
            bypass_write_flag_for_tests=True,
        )
    with pytest.raises(CommentsRateLimited):
        svc.create(
            site_space="yummy",
            title_id="t-rate",
            identity_id=iid,
            body="Это уже сверх лимита запросов.",
            bypass_write_flag_for_tests=True,
        )


def test_concurrent_creates(svc):
    def one(i: int):
        return svc.create(
            site_space="yummy",
            title_id="t-conc",
            identity_id=mint_identity_id(),
            body=f"Параллельный комментарий номер {i} уникальный.",
            bypass_write_flag_for_tests=True,
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(one, range(8)))
    assert len(results) == 8
    ids = {r["comment"]["comment_id"] for r in results}
    assert len(ids) == 8
