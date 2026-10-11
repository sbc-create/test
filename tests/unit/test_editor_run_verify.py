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
                        # Домен ВНЕ цикла редактора: задание на нём работой не
                        # считается. Здесь по очереди стояли yummyani.biz и
                        # zonafilm.cc — и каждый из них в ночь 9→10 октября
                        # вошёл в цикл, после чего проверка начинала измерять не
                        # то, что проверяет. Поэтому стоит стендовый домен: он в
                        # цикле не окажется никогда, и смысл проверки —
                        # «чужая аренда и завершённый кандидат работой не
                        # считаются» — остаётся при любом росте сети.
                        "target_site": "t-outside.localhost",
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
        registry=registry,
        leases=leases,
        events=events,
        candidates=cands,
        state=state,
        recent={},
        # Шлюз читает /proc; в тесте ресурсы заданы, чтобы итог не зависел от
        # нагрузки машины, на которой идёт прогон.
        conf=editor_run.cadence(tmp_path / "нет-файла.json"),
        resources_fn=lambda: {"ok": True, "problems": [], "measured": {}},
    )


def _runs_log(f, *rows):
    (f["state"] / "runs.jsonl").write_text(
        "\n".join(json.dumps({"model_started": True, **r}) for r in rows), encoding="utf-8"
    )


def test_gate_waits_twenty_minutes_after_the_batch_finished(tmp_path):
    """Владелец 2026-10-10: пауза отсчитывается от ЗАВЕРШЕНИЯ партии, не от начала."""
    f = _gate_files(tmp_path)
    _runs_log(f, {"started_at": "2026-10-08T14:20:00Z", "finished_at": "2026-10-08T14:45:00Z",
                  "verdict": "COMPLETE"})
    decision = editor_run.gate(NOW, **f)  # 15 минут после завершения
    assert decision["run"] is False and decision["state"] == "paused", decision
    assert decision["next_at"] == "2026-10-08T15:05:00Z"
    later = editor_run.gate(NOW + dt.timedelta(minutes=5), **f)
    assert later["run"] is True and later["state"] == "run", later


def test_gate_without_finished_at_counts_from_start(tmp_path):
    f = _gate_files(tmp_path, last_start="2026-10-08T14:50:00Z")
    assert editor_run.gate(NOW, **f)["state"] == "paused"


def test_missed_batches_are_not_caught_up(tmp_path):
    """После долгого простоя — одна партия по общему правилу, не очередь пропущенных."""
    f = _gate_files(tmp_path)
    _runs_log(f, {"started_at": "2026-10-08T03:00:00Z", "finished_at": "2026-10-08T03:15:00Z",
                  "verdict": "COMPLETE"})
    assert editor_run.gate(NOW, **f)["run"] is True
    _runs_log(f, {"started_at": "2026-10-08T03:00:00Z", "finished_at": "2026-10-08T03:15:00Z",
                  "verdict": "COMPLETE"},
              {"started_at": "2026-10-08T15:00:00Z", "finished_at": "2026-10-08T15:12:00Z",
               "verdict": "COMPLETE"})
    nxt = editor_run.gate(NOW + dt.timedelta(minutes=13), **f)
    assert nxt["state"] == "paused" and nxt["next_at"] == "2026-10-08T15:32:00Z"


def test_consecutive_failures_grow_the_pause_up_to_the_cap(tmp_path):
    f = _gate_files(tmp_path)
    end = "2026-10-08T14:30:00Z"
    fail = {"started_at": "2026-10-08T14:10:00Z", "finished_at": end, "verdict": "INCOMPLETE"}
    ok = {"started_at": "2026-10-08T13:00:00Z", "finished_at": "2026-10-08T13:20:00Z",
          "verdict": "NO_PUBLICATION"}
    _runs_log(f, ok, fail)  # один сбой — обычные 20 минут
    assert editor_run.gate(NOW, **f)["run"] is True
    _runs_log(f, ok, fail, fail)  # два подряд — 40 минут
    d = editor_run.gate(NOW, **f)
    assert d["state"] == "backoff" and d["next_at"] == "2026-10-08T15:10:00Z", d
    _runs_log(f, *([fail] * 10))  # потолок 4 часа
    assert editor_run.gate(NOW, **f)["next_at"] == "2026-10-08T18:30:00Z"
    _runs_log(f, *([fail] * 10), {**ok, "started_at": "2026-10-08T14:20:00Z",
                                  "finished_at": "2026-10-08T14:30:00Z"})
    assert editor_run.gate(NOW, **f)["run"] is True  # успех сбрасывает счёт


def test_gate_defers_on_resources_and_names_the_reason(tmp_path):
    f = _gate_files(tmp_path)
    f["resources_fn"] = lambda: editor_run.resources(
        editor_run.CADENCE_DEFAULTS["resources"],
        reader={
            "/proc/meminfo": "MemTotal: 31000000 kB\nMemAvailable:  1048576 kB\n",
            "/proc/pressure/memory": "some avg10=1 avg60=2 avg300=1 total=1\n"
            "full avg10=0.5 avg60=7.25 avg300=1 total=1\n",
            "/proc/loadavg": "0.5 0.5 0.5 1/100 1\n",
        }.get,
    )
    d = editor_run.gate(NOW, **f)
    assert d["run"] is False and d["state"] == "resources", d
    assert "1024 МиБ" in d["reason"] and "7.25" in d["reason"], d
    assert d["resources"]["mem_available_mib"] == 1024


def test_resources_pass_when_measurements_are_within_limits():
    r = editor_run.resources(
        editor_run.CADENCE_DEFAULTS["resources"],
        reader={"/proc/meminfo": "MemAvailable:  4194304 kB\n",
                "/proc/pressure/memory": "full avg10=0.1 avg60=0.15 avg300=0.1 total=1\n",
                "/proc/loadavg": "0.1 0.1 0.1 1/1 1\n"}.get,
    )
    assert r["ok"] and r["measured"]["mem_available_mib"] == 4096, r


def test_cadence_file_overrides_defaults(tmp_path):
    p = tmp_path / "editor-run.json"
    p.write_text(json.dumps({"pause_after_batch_s": 1800, "resources": {"load1_per_cpu_max": 2}}))
    c = editor_run.cadence(p)
    assert c["pause_after_batch_s"] == 1800 and c["resources"]["load1_per_cpu_max"] == 2
    assert c["resources"]["mem_available_min_mib"] == 2048


def test_committed_cadence_is_twenty_minutes():
    assert editor_run.cadence()["pause_after_batch_s"] == 1200


def test_current_state_reports_pause_and_next_time_in_msk(tmp_path):
    state = tmp_path / "runs"
    state.mkdir()
    (state / "runs.jsonl").write_text(json.dumps(
        {"model_started": True, "started_at": "2026-10-08T14:20:00Z",
         "finished_at": "2026-10-08T14:45:00Z", "verdict": "COMPLETE"}), encoding="utf-8")
    (state / "gate.jsonl").write_text(json.dumps(
        {"at": "2026-10-08T14:55:00Z", "gate_rc": 0,
         "gate": {"run": False, "state": "paused", "reason": "пауза"}}), encoding="utf-8")
    s = editor_run.current_state(state, NOW)
    assert s["state"] == "paused" and s["batch_running"] is False
    assert s["earliest_next_msk"] == "2026-10-08 18:05"
    assert s["last_gate"]["gate"]["state"] == "paused"


def test_current_state_sees_a_running_batch(tmp_path):
    import fcntl

    state = tmp_path / "runs"
    state.mkdir()
    with open(state / "run.lock", "w") as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        assert editor_run.current_state(state, NOW)["state"] == "running"
    assert editor_run.current_state(state, NOW)["state"] != "running"


def test_gate_failure_is_not_a_regular_refusal(monkeypatch, capsys):
    """Поломка шлюза — код 3 и state=error; штатный отказ — 0, запуск — 10."""
    from seo_operator import cli

    def broken(**_kw):
        raise ValueError("registry.json: Expecting value")

    monkeypatch.setattr(editor_run, "gate", broken)
    assert cli.main(["editor-gate"]) == 3
    out = json.loads(capsys.readouterr().out)
    assert out["state"] == "error" and "ValueError" in out["reason"]
    monkeypatch.setattr(editor_run, "gate", lambda **_kw: {"run": False, "state": "paused",
                                                          "reason": "пауза"})
    assert cli.main(["editor-gate"]) == 0


def test_wrapper_maps_gate_codes():
    """editor-run.sh: 10 — запуск, 0 — штатный выход, иное — exit 70, не тихий 0."""
    import pathlib

    sh = (pathlib.Path(editor_run.__file__).resolve().parents[1]
          / "automation" / "host" / "editor" / "editor-run.sh").read_text(encoding="utf-8")
    assert "10) ;;" in sh and "0) exit 0 ;;" in sh and "exit 70" in sh
    assert '-ne 10 ]; then\n    exit 0' not in sh


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


def test_gate_gives_candidates_even_when_a_queue_task_is_free(tmp_path):
    f = _gate_files(tmp_path)  # свободное задание Animedia + кандидат без результата
    decision = editor_run.gate(NOW, **f)
    assert decision["run"] is True
    assert [c["url"] for c in decision["next"]] == ["https://animedia.space/title/x/"]


def test_allowed_domains_cover_gate_and_candidate_sites():
    from seo_operator import regular

    got = editor_run.allowed_domains()
    пауза = set(editor_run.PAUSED_PUBLISH)
    assert set(regular.EDITOR_SITES) - пауза <= set(got) and set(editor_run.EDITOR_DOMAINS) - пауза <= set(got)
    assert not пауза & set(got)


def test_gate_refreshes_when_a_catalog_domain_ran_out(tmp_path, monkeypatch):
    """2026-10-10: кандидаты Lords закрыты, Yummy остались — список всё равно пересчитывается."""
    f = _gate_files(tmp_path, candidate_done=True)  # animedia.space/title/x закрыт
    f["candidates"].write_text(json.dumps({"candidates": [
        {"url": "https://animedia.space/title/x/"},
        {"url": "https://yummyani.site/anime/y"},
    ]}), encoding="utf-8")
    called = []

    def fake_refresh(path, now):
        called.append(path)
        path.write_text(json.dumps({"candidates": [
            {"url": "https://yummyani.site/anime/y"},
            {"url": "https://animedia.icu/title/z/"},
        ]}), encoding="utf-8")
        return True

    monkeypatch.setattr(editor_run, "_refresh_candidates", fake_refresh)
    d = editor_run.gate(NOW, refresh=True, **f)
    assert called, "каталожные домены без кандидатов — пересчёт обязателен"
    assert "https://animedia.icu/title/z/" in [c["url"] for c in d["next"]]


def test_gate_does_not_refresh_while_every_catalog_domain_has_work(tmp_path, monkeypatch):
    from seo_operator import regular

    f = _gate_files(tmp_path)
    f["candidates"].write_text(json.dumps({"candidates": [
        {"url": f"https://{d}/title/a{i}/"} for i, d in enumerate(regular.EDITOR_SITES)
        if d not in editor_run.PAUSED_PUBLISH
    ]}), encoding="utf-8")
    monkeypatch.setattr(editor_run, "_refresh_candidates",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("лишний пересчёт")))
    assert editor_run.gate(NOW, refresh=True, **f)["run"] is True


def test_paused_domains_are_not_offered_to_the_editor(tmp_path):
    """11.10: публикация на Lords/Zona затирала поля editorial-overrides.json — домены на паузе."""
    f = _gate_files(tmp_path, task_leased=True)
    f["candidates"].write_text(json.dumps({"candidates": [
        {"url": "https://zonafilm.space/title/a/"}, {"url": "https://animedia.space/title/b/"}]}),
        encoding="utf-8")
    d = editor_run.gate(NOW, **f)
    assert [c["url"] for c in d["next"]] == ["https://animedia.space/title/b/"]
    assert "zonafilm.space" not in editor_run.allowed_domains()
    assert "animedia.space" in editor_run.allowed_domains()
