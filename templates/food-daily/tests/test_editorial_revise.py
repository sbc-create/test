"""Редакционная правка новой версией и изолированная база варианта (временная база, без var/)."""

import json

import pytest

from fooddaily import editorial
from fooddaily.store import Store, VersionConflict

FACTS = {"steps": ["Варить 5–7 минут.", "Добавить картофель и варить ещё 7–10 минут."], "servings": 2}


def make_store(tmp_path):
    st = Store(tmp_path / "db" / "food-daily.sqlite3")
    st.db.execute(
        "INSERT INTO records (record_id, site_id, host, source_url, fetched_at, facts_json, status) "
        "VALUES ('rec-1', 'food-daily', 'h', 'https://example.invalid/r', '2026-10-13T00:00:00Z', ?, 'extracted')",
        (json.dumps(FACTS, ensure_ascii=False),),
    )
    st.ensure_content(content_id="fd-1", slug="sup", dedupe_key="sup:1")
    payload = {
        "draft": {"title": "Суп", "tips": [{"text": "Старая подсказка.", "verified": False}], "editor_notes": []},
        "facts": {"ingredients": [], "servings": 2},
        "source": {"url": "https://example.invalid/r", "host": "h", "fetched_at": "2026-10-13T00:00:00Z"},
    }
    st.add_version(
        "fd-1", payload, base_version=0, source_ids=["rec-1"], producer={"mode": "t"}, actor="t", reason="v1"
    )
    st.set_publish("fd-1", "preview", actor="t")
    return st


def test_revise_adds_version_and_keeps_history(tmp_path):
    st = make_store(tmp_path)
    tip = {
        "text": "По шагам источника варят 5–7 минут, затем ещё 7–10 минут.",
        "verified": False,
        "source_steps": [0, 1],
    }
    out = editorial.revise(st, "fd-1", {"tips": [tip]}, base_version=1, actor="claude-session", reason="правка")
    assert out["version"] == 2
    assert [v["recipe_version"] for v in st.versions("fd-1")] == [1, 2]
    assert json.loads(st.version("fd-1", 2)["payload_json"])["draft"]["tips"] == [tip]
    assert json.loads(st.version("fd-1", 1)["payload_json"])["draft"]["tips"][0]["text"] == "Старая подсказка."
    assert st.current("fd-1")["review_status"] == "ai_draft" and st.current("fd-1")["publish_status"] == "preview"
    assert any(a["action"] == "version_added" for a in st.audit_for("fd-1"))


def test_revise_refuses_stale_base_unsupported_numbers_and_fields(tmp_path):
    st = make_store(tmp_path)
    editorial.revise(st, "fd-1", {"tips": []}, base_version=1, actor="c", reason="r")
    with pytest.raises(VersionConflict):
        editorial.revise(
            st, "fd-1", {"tips": [{"text": "Иное.", "verified": False}]}, base_version=1, actor="c", reason="r"
        )
    with pytest.raises(ValueError, match="12"):
        editorial.revise(st, "fd-1", {"tips": [{"text": "Варите 12 минут."}]}, base_version=2, actor="c", reason="r")
    with pytest.raises(ValueError, match="facts"):
        editorial.revise(st, "fd-1", {"facts": {}}, base_version=2, actor="c", reason="r")
    assert st.current("fd-1")["current_version"] == 2


def test_editor_notes_stay_out_of_snapshot(tmp_path, monkeypatch):
    st = make_store(tmp_path)
    editorial.revise(
        st,
        "fd-1",
        {"tips": [], "editor_notes": ["Убрано со страницы: подсказка без опоры."]},
        base_version=1,
        actor="c",
        reason="r",
    )
    monkeypatch.setattr(editorial, "SNAPSHOT", tmp_path / "snap.json")
    monkeypatch.setattr(editorial, "ROOT", tmp_path)
    editorial.snapshot(st)
    item = json.loads((tmp_path / "snap.json").read_text())["items"][0]
    assert "editor_notes" not in item["draft"] and item["draft"]["tips"] == [] and item["version"] == 2


def test_clone_db_refuses_existing_and_mismatch(tmp_path, monkeypatch):
    src = make_store(tmp_path).path
    monkeypatch.setattr(editorial, "SNAPSHOT", tmp_path / "snap.json")
    monkeypatch.setattr(editorial, "ROOT", tmp_path)
    editorial.snapshot(Store(src))
    out = editorial.clone_db(src, tmp_path / "clone" / "food-daily.sqlite3")
    assert out["items_checked"] == 1
    with pytest.raises(FileExistsError):
        editorial.clone_db(src, tmp_path / "clone" / "food-daily.sqlite3")
    snap = json.loads((tmp_path / "snap.json").read_text())
    snap["items"][0]["version"] = 9
    (tmp_path / "snap.json").write_text(json.dumps(snap))
    with pytest.raises(ValueError, match="не совпадает"):
        editorial.clone_db(src, tmp_path / "clone2" / "food-daily.sqlite3")


def test_rename_versions_slug_and_collapses_redirect_chain(tmp_path, monkeypatch):
    st = make_store(tmp_path)
    red = tmp_path / "redirects.json"
    red.write_text(json.dumps({"/recept/staryj/": "/recept/sup/"}))
    monkeypatch.setattr(editorial, "REDIRECTS", red)
    out = editorial.rename(st, "fd-1", "sup-novyj", base_version=1, actor="c", reason="r")
    assert out["version"] == 2 and st.current("fd-1")["slug"] == "sup-novyj"
    assert json.loads(st.version("fd-1")["payload_json"])["draft"]["slug"] == "sup-novyj"
    assert json.loads(red.read_text()) == {
        "/recept/staryj/": "/recept/sup-novyj/",
        "/recept/sup/": "/recept/sup-novyj/",
    }
    assert any(a["action"] == "slug_renamed" for a in st.audit_for("fd-1"))
    with pytest.raises(ValueError):
        editorial.rename(st, "fd-1", "Плохой адрес", base_version=2, actor="c", reason="r")
    with pytest.raises(ValueError):
        editorial.rename(st, "fd-1", "sup-novyj", base_version=2, actor="c", reason="r")
