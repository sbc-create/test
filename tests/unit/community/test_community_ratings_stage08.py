"""COMMUNITY-RATINGS-08 — widget injection, exposure metrics, observability.

Two things are under test here that earlier stages got wrong:

* the widget was never on the page, so the 1% cohort had zero exposure;
* the monitor read its own empty in-process counters and published the zeros
  as if they were measurements.

Both are covered by behaviour, not by file existence.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from factory.community import metrics, metrics_store, widget_inject
from factory.community.cohort import cohort_bucket, decide_cohort

ASSETS = Path(__file__).resolve().parents[3] / "factory" / "community" / "frontend"

FLAGS_LIVE = {
    "PUBLIC_WRITE_ENABLED": 1,
    "PUBLIC_WRITE_ROLLOUT_PERCENT": 1,
    "KILL_SWITCH": 0,
    "READ_ONLY": 0,
}


def _readmodel(tmp: Path, rows: list[tuple[str, str]]) -> Path:
    db = tmp / "readmodel.sqlite3"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE entity (entity_id TEXT PRIMARY KEY, slug TEXT)")
    conn.executemany("INSERT INTO entity(entity_id, slug) VALUES(?,?)", rows)
    conn.commit()
    conn.close()
    return db


def _flags_file(tmp: Path, flags: dict) -> Path:
    p = tmp / "flags.json"
    p.write_text(json.dumps(flags), encoding="utf-8")
    return p


class CohortGateTests(unittest.TestCase):
    """0%, 1% and an excluded visitor — the gate the whole stage rests on."""

    SALT = b"test-salt"

    def test_zero_percent_admits_nobody(self) -> None:
        for i in range(200):
            d = decide_cohort(f"id-{i}", rollout_percent=0, salt=self.SALT)
            self.assertFalse(d.eligible)

    def test_one_percent_admits_only_bucket_zero(self) -> None:
        admitted = excluded = 0
        for i in range(2000):
            ident = f"id-{i}"
            d = decide_cohort(ident, rollout_percent=1, salt=self.SALT)
            bucket = cohort_bucket(ident, salt=self.SALT)
            self.assertEqual(d.eligible, bucket < 1)
            admitted += int(d.eligible)
            excluded += int(not d.eligible)
        # A 1% gate must actually admit roughly 1% — not nobody, not everybody.
        self.assertGreater(admitted, 0)
        self.assertGreater(excluded, admitted * 50)

    def test_cohort_is_stable_across_requests(self) -> None:
        for i in range(50):
            ident = f"stable-{i}"
            first = decide_cohort(ident, rollout_percent=1, salt=self.SALT)
            for _ in range(5):
                again = decide_cohort(ident, rollout_percent=1, salt=self.SALT)
                self.assertEqual(first.eligible, again.eligible)
                self.assertEqual(first.bucket, again.bucket)

    def test_bucket_does_not_depend_on_ip_or_fingerprint(self) -> None:
        # The bucket is a function of the opaque identity alone. Nothing else
        # is accepted as input, so nothing else can leak into the decision.
        a = cohort_bucket("identity-a", salt=self.SALT)
        b = cohort_bucket("identity-a", salt=self.SALT)
        self.assertEqual(a, b)
        self.assertNotEqual(cohort_bucket("identity-b", salt=self.SALT), None)


class WidgetVisibilityTests(unittest.TestCase):
    """Widget hidden vs visible, decided server-side before a byte is sent."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmpdir.name)
        self.rm = _readmodel(self.tmp, [("019e820c-1c30-7466-9e8f-801577489ce1", "padshiy-master")])
        self.addCleanup(self.tmpdir.cleanup)

    def plan(self, path: str, flags: dict) -> bytes | None:
        return widget_inject.plan_injection(
            path, flags_path=_flags_file(self.tmp, flags), readmodel=self.rm
        )

    def test_visible_on_known_title_when_enabled(self) -> None:
        out = self.plan("/anime/padshiy-master", FLAGS_LIVE)
        self.assertIsNotNone(out)
        self.assertIn(b"cr-widget-loader", out)
        self.assertIn(b"nova:019e820c-1c30-7466-9e8f-801577489ce1", out)

    def test_hidden_when_kill_switch_on(self) -> None:
        flags = dict(FLAGS_LIVE, KILL_SWITCH=1)
        self.assertIsNone(self.plan("/anime/padshiy-master", flags))

    def test_hidden_when_read_only(self) -> None:
        flags = dict(FLAGS_LIVE, READ_ONLY=1)
        self.assertIsNone(self.plan("/anime/padshiy-master", flags))

    def test_hidden_when_writes_disabled(self) -> None:
        flags = dict(FLAGS_LIVE, PUBLIC_WRITE_ENABLED=0)
        self.assertIsNone(self.plan("/anime/padshiy-master", flags))

    def test_hidden_at_zero_percent(self) -> None:
        flags = dict(FLAGS_LIVE, PUBLIC_WRITE_ROLLOUT_PERCENT=0)
        self.assertIsNone(self.plan("/anime/padshiy-master", flags))

    def test_hidden_on_unknown_slug(self) -> None:
        # Guessing a subject id would attach votes to the wrong title.
        self.assertIsNone(self.plan("/anime/not-in-readmodel", FLAGS_LIVE))

    def test_hidden_off_title_routes(self) -> None:
        for path in ("/", "/catalog", "/search?q=x", "/api/community/ratings/session",
                     "/assets/community/community_rating.js", "/anime/", "/anime/a/b"):
            self.assertIsNone(self.plan(path, FLAGS_LIVE), path)

    def test_subject_is_never_guessed_from_slug(self) -> None:
        subject = widget_inject.resolve_subject("/anime/padshiy-master", readmodel=self.rm)
        self.assertEqual(subject, "nova:019e820c-1c30-7466-9e8f-801577489ce1")
        self.assertIsNone(widget_inject.resolve_subject("/anime/ghost", readmodel=self.rm))

    def test_loader_tag_escapes_subject(self) -> None:
        tag = widget_inject.loader_tag('nova:"><script>alert(1)</script>')
        self.assertNotIn(b'"><script>alert(1)', tag)
        self.assertIn(b"&quot;", tag)


class InjectionPlacementTests(unittest.TestCase):
    """Exactly one node, last in <body>, and never inside the app tree."""

    PAGE = (
        b"<!doctype html><html><head><title>t</title></head>"
        b'<body><div id="__next"><main>card</main></div></body></html>'
    )

    def test_injected_immediately_before_body_end(self) -> None:
        payload = widget_inject.loader_tag("nova:abc")
        out = widget_inject.inject_into_document(self.PAGE, payload)
        self.assertIn(payload + b"</body>", out)
        # The application's own tree is byte-identical.
        self.assertIn(b'<div id="__next"><main>card</main></div>', out)

    def test_nothing_added_to_head(self) -> None:
        payload = widget_inject.loader_tag("nova:abc")
        out = widget_inject.inject_into_document(self.PAGE, payload)
        head = out.split(b"</head>")[0]
        self.assertNotIn(b"cr-widget-loader", head)

    def test_exactly_one_node_injected(self) -> None:
        payload = widget_inject.loader_tag("nova:abc")
        out = widget_inject.inject_into_document(self.PAGE, payload)
        self.assertEqual(out.count(b"cr-widget-loader"), 1)
        self.assertEqual(len(out), len(self.PAGE) + len(payload))

    def test_document_without_body_end_is_untouched(self) -> None:
        raw = b"<html><p>no body close"
        self.assertEqual(widget_inject.inject_into_document(raw, b"<script></script>"), raw)


class StreamInjectorTests(unittest.TestCase):
    """Streaming must produce the same bytes as the whole-document variant."""

    PAGE = b"<html><body>" + b"x" * 5000 + b"</body></html>"

    def _stream(self, chunk_size: int, payload: bytes) -> bytes:
        inj = widget_inject.StreamInjector(payload)
        out = b""
        for i in range(0, len(self.PAGE), chunk_size):
            out += inj.feed(self.PAGE[i : i + chunk_size])
        return out + inj.finish()

    def test_matches_whole_document_injection_at_every_chunk_size(self) -> None:
        payload = widget_inject.loader_tag("nova:abc")
        expected = widget_inject.inject_into_document(self.PAGE, payload)
        for size in (1, 2, 3, 7, 64, 999, 4096, 100000):
            self.assertEqual(self._stream(size, payload), expected, f"chunk={size}")

    def test_split_across_the_body_tag_still_injects_once(self) -> None:
        payload = b"<!--P-->"
        inj = widget_inject.StreamInjector(payload)
        out = inj.feed(b"<html><body>abc</bo") + inj.feed(b"dy></html>") + inj.finish()
        self.assertEqual(out, b"<html><body>abc" + payload + b"</body></html>")
        self.assertEqual(out.count(payload), 1)

    def test_no_bytes_lost_when_body_end_never_arrives(self) -> None:
        inj = widget_inject.StreamInjector(b"<!--P-->")
        raw = b"<html><p>streamed with no close"
        out = b"".join(inj.feed(raw[i : i + 5]) for i in range(0, len(raw), 5))
        out += inj.finish()
        self.assertEqual(out, raw)
        self.assertFalse(inj.done)

    def test_holds_back_less_than_the_marker_length(self) -> None:
        # Constant memory is the reason streaming survives this change.
        inj = widget_inject.StreamInjector(b"P")
        inj.feed(b"y" * 100000)
        self.assertLess(len(inj._tail), len(widget_inject.BODY_END))

    def test_length_delta_is_exactly_the_payload(self) -> None:
        payload = widget_inject.loader_tag("nova:abc")
        self.assertEqual(len(self._stream(512, payload)), len(self.PAGE) + len(payload))


class AssetServingTests(unittest.TestCase):
    def test_known_assets_resolve(self) -> None:
        for path, expect in (
            ("/assets/community/community_rating.js", "application/javascript"),
            ("/assets/community/community_rating.css", "text/css"),
        ):
            name = widget_inject.asset_name(path)
            self.assertIsNotNone(name, path)
            body, ctype = widget_inject.read_asset(name, assets_dir=ASSETS)
            self.assertTrue(body)
            self.assertIn(expect, ctype)

    def test_unknown_and_traversal_paths_are_refused(self) -> None:
        for path in (
            "/assets/community/../../etc/passwd",
            "/assets/community/secret.env",
            "/assets/community/",
            "/assets/other/community_rating.js",
            "/community_rating.js",
        ):
            self.assertIsNone(widget_inject.asset_name(path), path)


class WidgetContractTests(unittest.TestCase):
    """The shipped asset must speak the live API and nothing else."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.js = (ASSETS / "community_rating.js").read_text(encoding="utf-8")
        cls.css = (ASSETS / "community_rating.css").read_text(encoding="utf-8")

    def test_uses_real_api_routes(self) -> None:
        for route in ("/api/community/ratings", "/session", "/preview", "/vote", "/widget-event"):
            self.assertIn(route, self.js)
        self.assertIn('"/titles/"', self.js)

    def test_never_sends_rating_space_in_body(self) -> None:
        # The gateway rejects a body-supplied rating_space_id outright.
        self.assertNotIn('rating_space_id:', self.js)
        self.assertNotIn('"rating_space_id"', self.js)

    def test_sends_csrf_and_idempotency_on_writes(self) -> None:
        self.assertIn("X-CSRF-Token", self.js)
        self.assertIn("Idempotency-Key", self.js)
        self.assertIn('credentials: "same-origin"', self.js)

    def test_absent_state_is_a_sentence_not_a_zero(self) -> None:
        self.assertIn("Пока нет пользовательских оценок", self.js)
        # Absent must null the score rather than fall back to 0.
        self.assertIn("this.state.score = this.state.absent ? null :", self.js)

    def test_no_client_side_score_arithmetic(self) -> None:
        # Preview and write both come from the server; duplicating the formula
        # in the browser is how preview and write drift apart.
        for forbidden in ("vote_sum", "/ count", "reduce(", "Math.round(sum"):
            self.assertNotIn(forbidden, self.js)

    def test_no_external_rating_source_in_widget(self) -> None:
        for forbidden in ("shikimori", "Shikimori", "mal", "aggregateRating", "schema.org"):
            self.assertNotIn(forbidden, self.js)

    def test_does_not_render_without_server_eligibility(self) -> None:
        self.assertIn("if (!eligible(session)) return null;", self.js)
        self.assertIn("PUBLIC_WRITE_ENABLED", self.js)
        self.assertIn("KILL_SWITCH", self.js)

    def test_mounts_only_after_load(self) -> None:
        # Mounting during hydration is what broke the client side before.
        self.assertIn('addEventListener("load"', self.js)
        self.assertIn("document.body.appendChild(host)", self.js)

    def test_accessibility_affordances_present(self) -> None:
        for marker in (
            "aria-label",
            "aria-expanded",
            "aria-controls",
            "aria-live",
            "radiogroup",
            "aria-checked",
            'role="status"',
        ):
            self.assertIn(marker, self.js, marker)
        # Keyboard users must be able to see where they are.
        self.assertIn(":focus-visible", self.css)
        self.assertIn("outline:", self.css)

    def test_layout_cannot_shift(self) -> None:
        # Fixed positioning keeps the widget out of document flow entirely.
        self.assertIn("position: fixed", self.css)
        self.assertIn("min-height", self.css)

    def test_responsive_rule_present(self) -> None:
        self.assertIn("@media (max-width: 520px)", self.css)
        self.assertIn("max-width: calc(100vw - 32px)", self.css)

    def test_failure_never_propagates_into_the_host_page(self) -> None:
        self.assertIn("never break the host page", self.js)
        self.assertIn(".catch(", self.js)


class MetricsStoreTests(unittest.TestCase):
    """The inter-process transport that replaces the empty-counter bug."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.path = Path(self.tmpdir.name) / "metrics.sqlite"
        self.addCleanup(self.tmpdir.cleanup)
        self.addCleanup(metrics_store.reset_cache)
        # The drop counter is deliberately process-global and cumulative in
        # production — once writes have been refused, every later count really
        # is a lower bound. Tests must therefore start from a clean slate.
        metrics_store.reset_drop_stats()
        self.addCleanup(metrics_store.reset_drop_stats)

    def test_counter_survives_a_fresh_reader_process_view(self) -> None:
        metrics_store.incr("cast_attempts", 3, path=self.path)
        metrics_store.reset_cache()  # simulate a different process
        raw = metrics_store.read_raw(self.path)
        self.assertEqual(raw["counters"]["cast_attempts"], 3)

    def test_missing_store_reports_unmeasured_not_zero(self) -> None:
        snap = metrics_store.snapshot(path=Path(self.tmpdir.name) / "absent.sqlite")
        self.assertFalse(snap["store_reachable"])
        self.assertEqual(snap["metrics"]["cast_attempts"], metrics_store.UNMEASURED)
        self.assertIn("cast_attempts", snap["unmeasured"])
        self.assertIsNotNone(snap["provenance"]["cast_attempts"]["reason"])

    def test_never_recorded_counter_is_unmeasured_not_zero(self) -> None:
        metrics_store.incr("session_bootstraps", 1, path=self.path)
        snap = metrics_store.snapshot(path=self.path)
        self.assertEqual(snap["metrics"]["session_bootstraps"], 1)
        # Nothing ever incremented this one — that is not the same as zero.
        self.assertEqual(snap["metrics"]["rate_limit_violations"], metrics_store.UNMEASURED)

    def test_a_recorded_zero_is_measured(self) -> None:
        metrics_store.incr("rate_limited", 0, path=self.path)
        snap = metrics_store.snapshot(path=self.path)
        self.assertEqual(snap["metrics"]["rate_limit_violations"], 0)
        self.assertEqual(snap["provenance"]["rate_limit_violations"]["status"], "MEASURED")

    def test_unmeasured_cannot_be_substituted_by_zero(self) -> None:
        snap = metrics_store.snapshot(path=self.path)
        for name in snap["unmeasured"]:
            self.assertNotEqual(snap["metrics"][name], 0, name)
            self.assertEqual(snap["metrics"][name], metrics_store.UNMEASURED, name)

    def test_exposed_visitors_counts_distinct_identities(self) -> None:
        metrics_store.incr("eligible_cohort_impressions", 5, path=self.path)
        for ident in ("a", "a", "b", "a", "c"):
            metrics_store.mark_unique("exposed_visitor", ident, path=self.path)
        snap = metrics_store.snapshot(path=self.path)
        self.assertEqual(snap["metrics"]["exposed_visitors"], 3)

    def test_identity_is_not_stored_in_the_clear(self) -> None:
        metrics_store.mark_unique("exposed_visitor", "secret-identity-42", path=self.path)
        blob = self.path.read_bytes()
        self.assertNotIn(b"secret-identity-42", blob)

    def test_latency_is_unmeasured_until_sampled(self) -> None:
        metrics_store.incr("cast_attempts", 1, path=self.path)
        snap = metrics_store.snapshot(path=self.path)
        self.assertEqual(snap["metrics"]["latency_p50_ms"], metrics_store.UNMEASURED)
        metrics_store.observe_latency_ms(12.0, path=self.path)
        metrics_store.observe_latency_ms(30.0, path=self.path)
        snap = metrics_store.snapshot(path=self.path)
        self.assertIsInstance(snap["metrics"]["latency_p50_ms"], float)
        self.assertEqual(snap["provenance"]["latency_p50_ms"]["status"], "MEASURED")

    def test_latency_ring_is_bounded(self) -> None:
        for i in range(metrics_store.MAX_LATENCY_SAMPLES + 250):
            metrics_store.observe_latency_ms(float(i), path=self.path)
        raw = metrics_store.read_raw(self.path)
        self.assertLessEqual(len(raw["latency_samples"]), metrics_store.MAX_LATENCY_SAMPLES + 1)

    def test_every_contract_metric_is_present(self) -> None:
        snap = metrics_store.snapshot(path=self.path)
        required = {
            "session_bootstraps", "eligible_cohort_impressions", "widget_rendered",
            "exposed_visitors", "cast_attempts", "accepted_casts", "updates", "retracts",
            "rejected_writes", "api_errors", "rate_limit_violations", "quarantine_events",
            "duplicate_active_votes", "preview_write_mismatches",
            "aggregate_rebuild_mismatches", "latency_p50_ms", "latency_p95_ms",
            "kill_switch_state",
        }
        self.assertEqual(required - set(snap["metrics"]), set())

    def test_every_metric_carries_provenance(self) -> None:
        snap = metrics_store.snapshot(path=self.path, kill_switch_state=0, rollout_percent=1)
        for name in snap["metrics"]:
            prov = snap["provenance"][name]
            self.assertIn("source", prov, name)
            self.assertIn("status", prov, name)
            if prov["status"] == "MEASURED":
                self.assertTrue(prov.get("window") or prov.get("last_update"), name)


class MetricsBridgeTests(unittest.TestCase):
    """The gateway's counters must actually land in the durable store."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.path = Path(self.tmpdir.name) / "metrics.sqlite"
        self.addCleanup(self.tmpdir.cleanup)
        self._orig = metrics_store.DEFAULT_STORE_PATH
        metrics_store.DEFAULT_STORE_PATH = self.path
        metrics_store.reset_cache()

        def restore() -> None:
            metrics_store.DEFAULT_STORE_PATH = self._orig
            metrics_store.reset_cache()

        self.addCleanup(restore)
        metrics.reset_for_tests()
        metrics_store.reset_drop_stats()
        self.addCleanup(metrics_store.reset_drop_stats)

    def test_incr_is_mirrored_to_the_store(self) -> None:
        metrics.incr("cast_accepted", 2)
        metrics_store.reset_cache()
        raw = metrics_store.read_raw(self.path)
        self.assertEqual(raw["counters"]["cast_accepted"], 2)

    def test_latency_is_mirrored_to_the_store(self) -> None:
        metrics.observe_latency_ms(7.5)
        metrics_store.reset_cache()
        self.assertEqual(metrics_store.read_raw(self.path)["latency_samples"], [7.5])

    def test_unique_marks_are_mirrored(self) -> None:
        metrics.mark_unique("exposed_visitor", "ident-1")
        metrics_store.reset_cache()
        self.assertEqual(metrics_store.read_raw(self.path)["uniques"]["exposed_visitor"], 1)

    def test_store_failure_does_not_break_the_request_path(self) -> None:
        metrics_store.DEFAULT_STORE_PATH = Path("/proc/nonexistent/metrics.sqlite")
        metrics_store.reset_cache()
        metrics.incr("cast_accepted")  # must not raise
        self.assertEqual(metrics.snapshot()["cast_accepted"], 1)


if __name__ == "__main__":
    unittest.main()


class DeployBundleParityTests(unittest.TestCase):
    """The host bundle is a verbatim copy of the canonical source.

    ``/srv/lords/.frontend`` has no ``factory`` package on its path, so the
    deployable files live under ``automation/host``. Two copies can drift; this
    is what stops them, and it is why ``SOURCE_ARTIFACT_RUNTIME_MATCH`` can be
    asserted rather than hoped for.
    """

    ROOT = Path(__file__).resolve().parents[3]
    HOST = ROOT / "automation" / "host"

    PAIRS = (
        (ROOT / "factory/community/widget_inject.py", HOST / "community_widget_inject.py"),
        (
            ROOT / "factory/community/frontend/community_rating.js",
            HOST / "community-assets/community_rating.js",
        ),
        (
            ROOT / "factory/community/frontend/community_rating.css",
            HOST / "community-assets/community_rating.css",
        ),
    )

    def test_host_bundle_matches_canonical_sources(self) -> None:
        for source, deployed in self.PAIRS:
            self.assertTrue(source.is_file(), source)
            self.assertTrue(deployed.is_file(), deployed)
            self.assertEqual(
                source.read_bytes(),
                deployed.read_bytes(),
                f"{deployed} has drifted from {source}",
            )

    def test_frontend_wires_the_injector(self) -> None:
        src = (self.HOST / "yummy-frontend.py").read_text(encoding="utf-8")
        self.assertIn("community_widget_inject.py", src)
        self.assertIn("plan_injection", src)
        self.assertIn("StreamInjector", src)
        self.assertIn("asset_name", src)

    def test_frontend_adjusts_content_length_for_the_injection(self) -> None:
        # A forwarded Content-Length that ignores the injected bytes truncates
        # the document by exactly that many bytes in the browser.
        src = (self.HOST / "yummy-frontend.py").read_text(encoding="utf-8")
        self.assertIn("int(длина) + len(вставка)", src)


class MetricsStoreConcurrencyTests(unittest.TestCase):
    """The gateway serves every request on its own thread.

    A cached sqlite connection with the default ``check_same_thread=True``
    refuses those calls; the write is swallowed so it cannot break a user
    request, and the counter silently reads low — a fresh silent-zero of
    exactly the kind this stage exists to remove.
    """

    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.path = Path(self.tmpdir.name) / "metrics.sqlite"
        self.addCleanup(self.tmpdir.cleanup)
        self.addCleanup(metrics_store.reset_cache)
        metrics_store.reset_drop_stats()
        self.addCleanup(metrics_store.reset_drop_stats)

    def test_counters_survive_writes_from_many_threads(self) -> None:
        import threading

        metrics_store.incr("warmup", 1, path=self.path)  # connection is cached here
        results: list[bool] = []
        lock = threading.Lock()

        def worker() -> None:
            ok = metrics_store.incr("cast_attempts", 1, path=self.path)
            with lock:
                results.append(ok)

        threads = [threading.Thread(target=worker) for _ in range(25)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertTrue(all(results), "a worker thread had its metric write refused")
        metrics_store.reset_cache()
        self.assertEqual(metrics_store.read_raw(self.path)["counters"]["cast_attempts"], 25)
        self.assertEqual(metrics_store.drop_stats()["dropped_writes"], 0)

    def test_unique_marks_and_latency_survive_other_threads(self) -> None:
        import threading

        metrics_store.incr("warmup", 1, path=self.path)
        errors: list[str] = []

        def worker(i: int) -> None:
            if not metrics_store.mark_unique("exposed_visitor", f"id-{i}", path=self.path):
                errors.append(f"unique {i}")
            if not metrics_store.observe_latency_ms(float(i), path=self.path):
                errors.append(f"latency {i}")

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [])
        metrics_store.reset_cache()
        raw = metrics_store.read_raw(self.path)
        self.assertEqual(raw["uniques"]["exposed_visitor"], 10)
        self.assertEqual(len(raw["latency_samples"]), 10)

    def test_a_refused_write_is_reported_not_hidden(self) -> None:
        metrics_store.incr("session_bootstraps", 4, path=self.path)
        # Point the writer at a path that cannot be created.
        self.assertFalse(metrics_store.incr("cast_attempts", 1, path=Path("/proc/nope/m.sqlite")))
        stats = metrics_store.drop_stats()
        self.assertEqual(stats["dropped_writes"], 1)
        self.assertIsNotNone(stats["last_write_error"])

        snap = metrics_store.snapshot(path=self.path)
        self.assertEqual(snap["dropped_writes_this_process"], 1)
        # Counts that did land are a floor, not a measurement, and say so.
        self.assertEqual(snap["provenance"]["session_bootstraps"]["status"], "PARTIAL")
        self.assertIn("lower bound", snap["provenance"]["session_bootstraps"]["reason"])


class GatewayDbFlagTests(unittest.TestCase):
    def test_store_accepts_a_string_path_with_missing_parents(self) -> None:
        # The gateway's --db flag passes a str; the constructor used to call
        # .parent on it and crash before the service ever started.
        from factory.community.store import CommunityStore

        with tempfile.TemporaryDirectory() as tmp:
            store = CommunityStore(str(Path(tmp) / "nested" / "ratings.sqlite"))
            try:
                self.assertTrue(store.path.is_file())
            finally:
                store.close()
