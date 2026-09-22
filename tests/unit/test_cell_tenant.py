"""Локальные данные сайта: изоляция, модерация, голоса, согласованный снимок.

Доказывает: REQ-CELL-TENANT, REQ-CELL-LOCALDATA, REQ-CELL-SNAPSHOT.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from factory.cell import tenant
from factory.cell.tenant import CrossTenantAccess, InvalidVote, TenantError, TenantStore

TITLE = "3f2a7c10-0000-4000-8000-000000000001"


@pytest.fixture()
def store(tmp_path: Path) -> TenantStore:
    s = tenant.open_store("pilot-cell", tmp_path / "data" / "site.sqlite3")
    s.add_identity("u-1", "Первый")
    s.add_identity("u-2", "Второй")
    yield s
    s.close()


def test_comment_reply_edit_and_premoderation(store: TenantStore):
    root = store.add_comment(title_uuid=TITLE, identity_id="u-1", body="первый")
    assert root.status == "pending"
    assert store.comments(title_uuid=TITLE, status="approved") == []

    approved = store.moderate(root.comment_id, status="approved", actor="moder")
    assert approved.status == "approved"

    reply = store.add_comment(title_uuid=TITLE, identity_id="u-2", body="ответ",
                              parent_id=root.comment_id)
    assert reply.parent_id == root.comment_id

    edited = store.edit_comment(root.comment_id, body="исправил", actor="u-1")
    assert edited.body == "исправил"
    # Правка возвращает запись на премодерацию: иначе одобренное можно было бы
    # заменить чем угодно уже после проверки.
    assert edited.status == "pending"


def test_rejected_comment_is_not_shown_but_is_not_lost(store: TenantStore):
    c = store.add_comment(title_uuid=TITLE, identity_id="u-1", body="спам")
    store.moderate(c.comment_id, status="rejected", actor="moder")
    assert store.comments(title_uuid=TITLE, status="approved") == []
    assert store.comment(c.comment_id).status == "rejected"


def test_empty_comment_is_refused(store: TenantStore):
    with pytest.raises(TenantError):
        store.add_comment(title_uuid=TITLE, identity_id="u-1", body="   ")


@pytest.mark.parametrize("score", [1, 5, 10])
def test_vote_in_range_is_accepted(store: TenantStore, score: int):
    v = store.vote(title_uuid=TITLE, identity_id="u-1", score=score)
    assert v.score == score


@pytest.mark.parametrize("score", [0, 11, -1, 100])
def test_vote_out_of_range_is_refused(store: TenantStore, score: int):
    with pytest.raises(InvalidVote):
        store.vote(title_uuid=TITLE, identity_id="u-1", score=score)


def test_revote_replaces_rather_than_adds(store: TenantStore):
    store.vote(title_uuid=TITLE, identity_id="u-1", score=3)
    store.vote(title_uuid=TITLE, identity_id="u-1", score=9)
    rating = store.user_rating(TITLE)
    assert rating["votes"] == 1
    assert rating["average"] == 9.0


def test_user_rating_is_separate_from_external(store: TenantStore):
    store.vote(title_uuid=TITLE, identity_id="u-1", score=8)
    store.vote(title_uuid=TITLE, identity_id="u-2", score=6)
    assert store.user_rating(TITLE) == {
        "title_uuid": TITLE, "votes": 2, "average": 7.0, "kind": "user"}


def test_data_survives_a_restart(tmp_path: Path):
    path = tmp_path / "data" / "site.sqlite3"
    first = tenant.open_store("pilot-cell", path)
    first.add_identity("u-1", "Первый")
    c = first.add_comment(title_uuid=TITLE, identity_id="u-1", body="переживёт")
    first.vote(title_uuid=TITLE, identity_id="u-1", score=7)
    first.close()

    second = tenant.open_store("pilot-cell", path)
    assert second.comment(c.comment_id).body == "переживёт"
    assert second.user_rating(TITLE)["average"] == 7.0
    second.close()


def test_forged_site_id_does_not_open_someone_elses_data(tmp_path: Path):
    path = tmp_path / "data" / "site.sqlite3"
    owner = tenant.open_store("pilot-cell", path)
    owner.add_identity("u-1", "Первый")
    owner.add_comment(title_uuid=TITLE, identity_id="u-1", body="моё")
    owner.close()
    # Подменённый манифест называет базу своей. База с этим не согласна.
    with pytest.raises(CrossTenantAccess, match="принадлежит сайту"):
        tenant.open_store("neighbour-cell", path)


def test_cross_tenant_argument_is_refused(store: TenantStore):
    with pytest.raises(CrossTenantAccess):
        store.comments(site_id="neighbour-cell")
    with pytest.raises(CrossTenantAccess):
        store.vote(title_uuid=TITLE, identity_id="u-1", score=5, site_id="neighbour-cell")
    with pytest.raises(CrossTenantAccess):
        store.add_comment(title_uuid=TITLE, identity_id="u-1", body="х",
                          site_id="neighbour-cell")


def test_neighbour_store_never_sees_our_rows(tmp_path: Path):
    a = tenant.open_store("cell-a", tmp_path / "a" / "site.sqlite3")
    b = tenant.open_store("cell-b", tmp_path / "b" / "site.sqlite3")
    a.add_identity("u-1", "Первый")
    a.add_comment(title_uuid=TITLE, identity_id="u-1", body="только у A")
    a.vote(title_uuid=TITLE, identity_id="u-1", score=10)
    assert b.comments(title_uuid=TITLE) == []
    assert b.user_rating(TITLE)["votes"] == 0
    a.close()
    b.close()


def test_export_carries_only_this_tenant(tmp_path: Path):
    a = tenant.open_store("cell-a", tmp_path / "a" / "site.sqlite3")
    a.add_identity("u-1", "Первый")
    a.add_comment(title_uuid=TITLE, identity_id="u-1", body="моё")
    payload = a.export_rows()
    sites = {row["site_id"] for rows in payload.values() for row in rows}
    assert sites == {"cell-a"}
    a.close()


def test_import_refuses_a_foreign_row(tmp_path: Path):
    a = tenant.open_store("cell-a", tmp_path / "a" / "site.sqlite3")
    a.add_identity("u-1", "Первый")
    payload = a.export_rows()
    a.close()
    b = tenant.open_store("cell-b", tmp_path / "b" / "site.sqlite3")
    with pytest.raises(CrossTenantAccess):
        b.import_rows(payload, expected_site_id="cell-b")
    with pytest.raises(CrossTenantAccess):
        b.import_rows(payload, expected_site_id="cell-a")
    b.close()


def test_snapshot_of_a_live_database_is_consistent(tmp_path: Path):
    """Снимок снимается Online Backup API прямо во время записи.

    Обычное копирование файла здесь дало бы базу в середине транзакции.
    """
    path = tmp_path / "data" / "site.sqlite3"
    store = tenant.open_store("pilot-cell", path)
    store.add_identity("u-1", "Первый")
    for i in range(200):
        store.add_comment(title_uuid=TITLE, identity_id="u-1", body=f"комментарий {i}")

    snapshot = store.snapshot(tmp_path / "snap" / "site.sqlite3")
    # Пишем после снимка: снимок не должен «дозаписаться» задним числом.
    store.add_comment(title_uuid=TITLE, identity_id="u-1", body="после снимка")
    counts_now = store.row_counts()
    store.close()

    restored = tenant.restore(snapshot, tmp_path / "restored" / "site.sqlite3",
                              expected_site_id="pilot-cell")
    assert restored.integrity_ok()
    assert restored.row_counts()["comments"] == 200
    assert counts_now["comments"] == 201
    restored.close()


def test_restore_refuses_to_present_data_as_another_tenant(tmp_path: Path):
    path = tmp_path / "data" / "site.sqlite3"
    store = tenant.open_store("pilot-cell", path)
    snapshot = store.snapshot(tmp_path / "snap.sqlite3")
    store.close()
    with pytest.raises(CrossTenantAccess):
        tenant.restore(snapshot, tmp_path / "restored.sqlite3",
                       expected_site_id="neighbour-cell")


def test_checksum_and_counts_travel_with_the_data(tmp_path: Path):
    src = tenant.open_store("cell-a", tmp_path / "a" / "site.sqlite3")
    src.add_identity("u-1", "Первый")
    src.add_comment(title_uuid=TITLE, identity_id="u-1", body="раз")
    src.vote(title_uuid=TITLE, identity_id="u-1", score=4)
    payload = src.export_rows()
    counts, checksum = src.row_counts(), src.checksum()
    src.close()

    dst = tenant.open_store("cell-a", tmp_path / "b" / "site.sqlite3")
    dst.import_rows(payload, expected_site_id="cell-a")
    assert dst.row_counts() == counts
    assert dst.checksum() == checksum
    dst.close()


def test_reply_to_a_foreign_comment_is_impossible(tmp_path: Path):
    a = tenant.open_store("cell-a", tmp_path / "a" / "site.sqlite3")
    a.add_identity("u-1", "Первый")
    root = a.add_comment(title_uuid=TITLE, identity_id="u-1", body="у A")
    a.close()
    b = tenant.open_store("cell-b", tmp_path / "b" / "site.sqlite3")
    b.add_identity("u-2", "Второй")
    with pytest.raises(TenantError):
        b.add_comment(title_uuid=TITLE, identity_id="u-2", body="ответ",
                      parent_id=root.comment_id)
    b.close()


def test_database_lives_outside_the_release_directory(tmp_path: Path):
    """Данные не внутри сменяемой папки релиза.

    Проверяется тем, что база открывается по своему пути и переживает удаление
    каталога релиза целиком.
    """
    release_dir = tmp_path / "releases" / "r1"
    release_dir.mkdir(parents=True)
    data_path = tmp_path / "data" / "site.sqlite3"
    store = tenant.open_store("pilot-cell", data_path)
    store.add_identity("u-1", "Первый")
    store.add_comment(title_uuid=TITLE, identity_id="u-1", body="переживу релиз")
    store.close()

    import shutil
    shutil.rmtree(tmp_path / "releases")

    again = tenant.open_store("pilot-cell", data_path)
    assert len(again.comments(title_uuid=TITLE)) == 1
    again.close()


def test_schema_rejects_an_out_of_range_score_at_the_database_level(tmp_path: Path):
    """Диапазон 1–10 закреплён в схеме, а не только в проверке Python.

    Иначе любой другой писатель в ту же базу обошёл бы правило.
    """
    path = tmp_path / "site.sqlite3"
    store = tenant.open_store("pilot-cell", path)
    store.add_identity("u-1", "Первый")
    store.close()
    raw = sqlite3.connect(str(path))
    with pytest.raises(sqlite3.IntegrityError):
        raw.execute(
            "INSERT INTO votes (site_id, title_uuid, identity_id, score, created_at, "
            "updated_at) VALUES ('pilot-cell', ?, 'u-1', 42, 'now', 'now')", (TITLE,))
    raw.close()
