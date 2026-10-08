"""REQ-SEO-REGULAR: полный запуск фонового редактора доказывается следами, а не самоотчётом."""
from __future__ import annotations

import json

from seo_operator import editor_run

RUN = "20261008T1500Z"
OWNER = editor_run.owner_for(RUN)
BODY = "«Некромант: Я катастрофа» — китайский анимационный сериал 2026 года в жанре фэнтези."


def _setup(tmp_path, *, publish=True, write=True):
    events = tmp_path / "queue_events.jsonl"
    rows = [{"at": "2026-10-08T15:00:10Z", "event": "task_claimed", "task_id": "t1", "owner": OWNER}]
    if write:
        rows.append({"at": "2026-10-08T15:03:00Z", "event": "task_result", "task_id": "t1", "owner": OWNER,
                     "outcome": "TEXT_WRITTEN", "gate": {"status": "READY_VERIFIED"}})
    events.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    site = tmp_path / "overlays" / "animedia.space"
    site.mkdir(parents=True)
    (site / "title-overlays.json").write_text(json.dumps({"items": [{"slug": "nekromant", "body": BODY}]}),
                                              encoding="utf-8")
    hist = [{"at": "2026-10-08T15:02:00Z", "op": "publish", "slug": "nekromant", "author": OWNER}] if publish else []
    (site / "history.jsonl").write_text("\n".join(json.dumps(r) for r in hist), encoding="utf-8")
    return events, {"animedia": (tmp_path / "overlays", "/title/{slug}/")}


def calls(_s, _u):
    return [{"tool": "editorial_facts", "outcome": "ok"}]


def test_all_five_traces_make_a_complete_run(tmp_path):
    events, roots = _setup(tmp_path)
    page = lambda url: (200, f"<html><body><p>{BODY}</p></body></html>")
    r = editor_run.verify(RUN, "2026-10-08T15:00:00Z", "2026-10-08T15:10:00Z", events_path=events,
                          roots=roots, bridge_calls=calls, fetch=page)
    assert r["complete"] is True
    assert r["publications"][0]["url"] == "https://animedia.space/title/nekromant/"


def test_claimed_and_reported_but_not_on_the_page_is_incomplete(tmp_path):
    events, roots = _setup(tmp_path)
    stale = lambda url: (200, "<html><body><p>Описание пока не передано источником</p></body></html>")
    r = editor_run.verify(RUN, "2026-10-08T15:00:00Z", "2026-10-08T15:10:00Z", events_path=events,
                          roots=roots, bridge_calls=calls, fetch=stale)
    assert r["steps"]["public_page_verified"] is False
    assert r["complete"] is False


def test_no_publication_record_is_incomplete_whatever_the_result_says(tmp_path):
    events, roots = _setup(tmp_path, publish=False)
    r = editor_run.verify(RUN, "2026-10-08T15:00:00Z", "2026-10-08T15:10:00Z", events_path=events,
                          roots=roots, bridge_calls=calls, fetch=lambda u: (200, BODY))
    assert r["steps"]["published"] is False and r["complete"] is False
