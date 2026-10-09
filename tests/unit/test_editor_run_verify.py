"""REQ-SEO-REGULAR: полный запуск фонового редактора доказывается следами, а не самоотчётом."""

from __future__ import annotations

import json

from seo_operator import editor_run

RUN = "20261008T1500Z"
OWNER = editor_run.owner_for(RUN)
BODY = "«Некромант: Я катастрофа» — китайский анимационный сериал 2026 года в жанре фэнтези."


def _setup(tmp_path, *, publish=True, write=True):
    events = tmp_path / "queue_events.jsonl"
    rows = [
        {"at": "2026-10-08T15:00:10Z", "event": "task_claimed", "task_id": "t1", "owner": OWNER}
    ]
    if write:
        rows.append(
            {
                "at": "2026-10-08T15:03:00Z",
                "event": "task_result",
                "task_id": "t1",
                "owner": OWNER,
                "outcome": "TEXT_WRITTEN",
                "gate": {"status": "READY_VERIFIED"},
            }
        )
    events.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    site = tmp_path / "overlays" / "animedia.space"
    site.mkdir(parents=True)
    (site / "title-overlays.json").write_text(
        json.dumps({"items": [{"slug": "nekromant", "body": BODY}]}), encoding="utf-8"
    )
    hist = (
        [{"at": "2026-10-08T15:02:00Z", "op": "publish", "slug": "nekromant", "author": OWNER}]
        if publish
        else []
    )
    (site / "history.jsonl").write_text("\n".join(json.dumps(r) for r in hist), encoding="utf-8")
    return events, {"animedia": (tmp_path / "overlays", "/title/{slug}/")}


def calls(_s, _u):
    return [{"tool": "editorial_facts", "outcome": "ok"}]


def test_all_five_traces_make_a_complete_run(tmp_path):
    events, roots = _setup(tmp_path)
    page = lambda url: (200, f"<html><body><p>{BODY}</p></body></html>")
    r = editor_run.verify(
        RUN,
        "2026-10-08T15:00:00Z",
        "2026-10-08T15:10:00Z",
        events_path=events,
        roots=roots,
        bridge_calls=calls,
        fetch=page,
    )
    assert r["complete"] is True
    assert r["publications"][0]["url"] == "https://animedia.space/title/nekromant/"


def test_claimed_and_reported_but_not_on_the_page_is_incomplete(tmp_path):
    events, roots = _setup(tmp_path)
    stale = lambda url: (
        200,
        "<html><body><p>Описание пока не передано источником</p></body></html>",
    )
    r = editor_run.verify(
        RUN,
        "2026-10-08T15:00:00Z",
        "2026-10-08T15:10:00Z",
        events_path=events,
        roots=roots,
        bridge_calls=calls,
        fetch=stale,
    )
    assert r["steps"]["public_page_verified"] is False
    assert r["complete"] is False


def test_no_publication_record_is_incomplete_whatever_the_result_says(tmp_path):
    events, roots = _setup(tmp_path, publish=False)
    r = editor_run.verify(
        RUN,
        "2026-10-08T15:00:00Z",
        "2026-10-08T15:10:00Z",
        events_path=events,
        roots=roots,
        bridge_calls=calls,
        fetch=lambda u: (200, BODY),
    )
    assert r["steps"]["published"] is False and r["complete"] is False


# ------------------------------------------------------------------ шлюз
import datetime as dt

NOW = dt.datetime(2026, 10, 8, 15, 0, tzinfo=dt.timezone.utc)


def _gate_files(tmp_path, *, last_start=None, task_leased=False, candidate_done=False):
    state = tmp_path / "runs"
    state.mkdir()
    if last_start:
        (state / "runs.jsonl").write_text(
            json.dumps({"started_at": last_start, "model_started": True}), encoding="utf-8"
        )
    registry = tmp_path / "registry.json"
    registry.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "content_id": "request-t1",
                        "target_site": "animedia.space",
                        "status": "NEEDS_UPDATE",
                    },
                    {
                        "content_id": "request-y1",
                        "target_site": "yummyani.site",
                        "status": "NEEDS_UPDATE",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    leases = tmp_path / "leases.json"
    leases.write_text(
        json.dumps(
            {
                "leases": [{"task_id": "t1", "expires_at": "2026-10-08T15:30:00Z"}]
                if task_leased
                else []
            }
        ),
        encoding="utf-8",
    )
    events = tmp_path / "events.jsonl"
    rows = [
        {
            "event": "task_registered",
            "task_id": "c1",
            "canonical_url": "https://animedia.space/title/x",
        }
    ]
    if candidate_done:
        rows.append({"event": "task_result", "task_id": "c1", "outcome": "SOURCES_MISSING"})
    events.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    cands = tmp_path / "cands.json"
    cands.write_text(
        json.dumps({"candidates": [{"url": "https://animedia.space/title/x/"}]}), encoding="utf-8"
    )
    return dict(
        registry=registry, leases=leases, events=events, candidates=cands, state=state, recent={}
    )


def test_gate_runs_the_model_at_most_hourly(tmp_path):
    f = _gate_files(tmp_path, last_start="2026-10-08T14:20:00Z")
    assert editor_run.gate(NOW, **f)["run"] is False  # 40 минут назад


def test_gate_finds_a_free_animedia_task(tmp_path):
    assert editor_run.gate(NOW, **_gate_files(tmp_path))["run"] is True


def test_gate_ignores_leased_tasks_and_finished_candidates(tmp_path):
    f = _gate_files(tmp_path, task_leased=True, candidate_done=True)
    decision = editor_run.gate(NOW, **f)
    assert decision["run"] is False, decision  # чужая аренда и Yummy не в счёт


def test_rotation_starts_with_the_least_published_domain_and_alternates():
    cands = [
        {"domain": "animedia.icu", "url": "https://animedia.icu/title/a/"},
        {"domain": "animedia.icu", "url": "https://animedia.icu/title/b/"},
        {"domain": "animedia.icu", "url": "https://animedia.icu/title/c/"},
        {"domain": "animedia.space", "url": "https://animedia.space/title/d/"},
        {"domain": "lordfilm47.space", "url": "https://lordfilm47.space/title/e/"},
    ]
    got = editor_run.rotate(cands, {"animedia.icu": 10, "animedia.space": 3})
    assert [c["url"].split("/")[-2] for c in got] == ["e", "d", "a", "b", "c"]


def test_gate_puts_the_rotated_order_into_next(tmp_path):
    f = _gate_files(tmp_path, task_leased=True)
    f["candidates"].write_text(
        json.dumps(
            {
                "candidates": [
                    {"domain": "animedia.icu", "url": "https://animedia.icu/title/a/"},
                    {"domain": "animedia.icu", "url": "https://animedia.icu/title/b/"},
                    {"domain": "animedia.space", "url": "https://animedia.space/title/c/"},
                ]
            }
        ),
        encoding="utf-8",
    )
    f["recent"] = {"animedia.icu": 5}
    decision = editor_run.gate(NOW, **f)
    assert [c["url"] for c in decision["next"]][:2] == [
        "https://animedia.space/title/c/",
        "https://animedia.icu/title/a/",
    ]


def test_queue_delivered_publication_counts_as_published(tmp_path):
    """Lords/Zona: копия опубликованного — published.json, наложения нет (2026-10-09)."""
    events, _ = _setup(tmp_path, publish=False)
    site = tmp_path / "lords" / "lordfilm47.space"
    site.mkdir(parents=True)
    (site / "published.json").write_text(
        json.dumps({"items": [{"slug": "nekromant", "body": BODY}]}), encoding="utf-8"
    )
    (site / "history.jsonl").write_text(
        json.dumps({"at": "2026-10-08T15:02:00Z", "op": "publish", "slug": "nekromant",
                    "author": OWNER}),
        encoding="utf-8",
    )
    r = editor_run.verify(
        RUN,
        "2026-10-08T15:00:00Z",
        "2026-10-08T15:10:00Z",
        events_path=events,
        roots={"lords": (tmp_path / "lords", "/title/{slug}/")},
        bridge_calls=calls,
        fetch=lambda url: (200, f"<html><body><main><p>{BODY}</p></main></body></html>"),
    )
    assert r["steps"]["published"] and r["steps"]["public_page_verified"], r
