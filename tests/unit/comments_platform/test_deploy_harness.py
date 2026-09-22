"""Targeted tests for the deploy harness — the part that got Stage 1 wrong.

Scoped deliberately. The comments module itself did not change in this cycle;
re-running 904 unit tests and 43 browser tests to validate a shell fix would be
noise. What is tested here is the logic that misjudged a live site:

* the redirect-chain evaluator, against a local fixture server that reproduces
  the exact shapes seen on animedia.icu — a trailing-slash 308, a 404 with no
  gateway, a gateway 503, a loop, a host change, a downgrade;
* the shell scripts' structural guarantees: a rollback trap, idempotence, no
  backup written into an nginx directory.

Nothing here touches production, nginx, systemd or any live site.
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
HARNESS = REPO / "automation" / "host"
CHECKER = HARNESS / "comments_endpoint_check.py"
APPLY = HARNESS / "animedia-comments-stage1-apply.sh"
ROLLBACK = HARNESS / "animedia-comments-stage1-rollback.sh"


def load_checker():
    spec = importlib.util.spec_from_file_location("comments_endpoint_check", CHECKER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    # Registered before exec: @dataclass resolves `cls.__module__` through
    # sys.modules, and a module absent from it fails with an opaque
    # AttributeError on NoneType during class creation.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


cec = load_checker()


# --- a fixture server that reproduces the real shapes ----------------------

class _Fixture(BaseHTTPRequestHandler):
    """Routes named after what animedia.icu actually did."""

    def log_message(self, *a):  # keep the test output readable
        pass

    def _send(self, code, headers=None):
        self.send_response(code)
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        host = self.headers.get("Host", "")
        path = self.path

        # The site's trailing-slash normalisation: 308 to the same host, then
        # an ordinary 404. This is what the first apply misread as a failure.
        if path == "/site/slash":
            return self._send(308, {"Location": f"http://{host}/site/slash/"})
        if path == "/site/slash/":
            return self._send(404)

        # The gateway refusing an ordinary visitor.
        if path == "/gateway/closed":
            return self._send(503, {"X-Comments-Module-Version": "0.1.0-mvp"})
        # The gateway serving a read — the thing that must never happen.
        if path == "/gateway/open":
            return self._send(200, {"X-Comments-Module-Version": "0.1.0-mvp"})
        # A redirect that ends at the gateway serving a read.
        if path == "/gateway/redirect-open":
            return self._send(308, {"Location": f"http://{host}/gateway/open"})

        if path == "/loop/a":
            return self._send(308, {"Location": f"http://{host}/loop/b"})
        if path == "/loop/b":
            return self._send(308, {"Location": f"http://{host}/loop/a"})

        if path == "/escape/host":
            return self._send(302, {"Location": "http://evil.example/anything"})
        if path == "/escape/downgrade":
            return self._send(302, {"Location": "http://127.0.0.1:1/x"})

        if path == "/chain/three":
            return self._send(308, {"Location": f"http://{host}/chain/two"})
        if path == "/chain/two":
            return self._send(308, {"Location": f"http://{host}/chain/one"})
        if path == "/chain/one":
            return self._send(404)

        return self._send(404)

    def do_POST(self):
        if self.path == "/gateway/closed":
            return self._send(503, {"X-Comments-Module-Version": "0.1.0-mvp"})
        # The site runtime answers 501 to POST; that is closed, not open.
        return self._send(501)


@pytest.fixture(scope="module")
def fixture_base():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Fixture)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()


# --- the evaluator ---------------------------------------------------------

class TestTrailingSlashRedirect:
    def test_a_same_host_308_then_404_is_closed(self, fixture_base):
        """The exact shape the first apply read as a failure."""
        result = cec.follow(f"{fixture_base}/site/slash")
        assert result.verdict == "CLOSED"
        assert result.codes == "308 -> 404"
        ok, message = cec.expect_closed_visitor(result)
        assert ok, message

    def test_and_it_is_also_proof_that_no_gateway_is_there(self, fixture_base):
        result = cec.follow(f"{fixture_base}/site/slash")
        ok, message = cec.expect_no_gateway(result)
        assert ok, message

    def test_a_direct_404_needs_no_hop(self, fixture_base):
        result = cec.follow(f"{fixture_base}/site/slash/")
        assert result.codes == "404"
        assert result.verdict == "CLOSED"


class TestGatewayAnswers:
    def test_a_gateway_503_is_closed_and_identified_as_the_gateway(self, fixture_base):
        result = cec.follow(f"{fixture_base}/gateway/closed")
        assert result.verdict == "CLOSED"
        assert result.final.served_by_gateway is True
        ok, _ = cec.expect_closed_visitor(result)
        assert ok
        # After a rollback the same answer must fail the no-gateway check.
        ok, message = cec.expect_no_gateway(result)
        assert not ok
        assert "gateway" in message

    def test_a_gateway_200_is_open_and_fails_the_visitor_check(self, fixture_base):
        result = cec.follow(f"{fixture_base}/gateway/open")
        assert result.verdict == "OPEN"
        ok, message = cec.expect_closed_visitor(result)
        assert not ok
        assert "OPEN" in message

    def test_a_redirect_that_ends_open_is_still_open(self, fixture_base):
        """A safe first hop must not launder an open endpoint."""
        result = cec.follow(f"{fixture_base}/gateway/redirect-open")
        assert result.codes == "308 -> 200"
        assert result.verdict == "OPEN"
        ok, _ = cec.expect_closed_visitor(result)
        assert not ok


class TestUnsafeChains:
    def test_a_loop_is_detected_rather_than_followed(self, fixture_base):
        result = cec.follow(f"{fixture_base}/loop/a")
        assert result.verdict == "REDIRECT_LOOP"
        ok, _ = cec.expect_closed_visitor(result)
        assert not ok

    def test_a_host_change_is_refused(self, fixture_base):
        result = cec.follow(f"{fixture_base}/escape/host")
        assert result.verdict == "HOST_CHANGED"
        assert "evil.example" in result.reason
        ok, _ = cec.expect_closed_visitor(result)
        assert not ok

    def test_a_long_chain_is_bounded(self, fixture_base):
        result = cec.follow(f"{fixture_base}/chain/three")
        assert result.codes == "308 -> 308 -> 404"
        assert result.verdict == "CLOSED"

    def test_an_unreachable_endpoint_is_not_mistaken_for_closed_visitor(self):
        result = cec.follow("http://127.0.0.1:1/nothing")
        assert result.verdict == "UNREACHABLE"
        ok, _ = cec.expect_closed_visitor(result)
        assert not ok
        # But for a rollback check, nothing listening is an acceptable answer.
        ok, _ = cec.expect_no_gateway(result)
        assert ok


class TestMethods:
    def test_post_to_the_site_is_closed_not_open(self, fixture_base):
        result = cec.follow(f"{fixture_base}/site/slash", method="POST")
        assert result.verdict == "CLOSED"
        assert result.final.code == 501

    def test_post_to_a_closed_gateway_is_closed(self, fixture_base):
        result = cec.follow(f"{fixture_base}/gateway/closed", method="POST")
        assert result.verdict == "CLOSED"


class TestCommandLine:
    def test_exit_status_carries_the_verdict(self, fixture_base):
        ok = subprocess.run(
            [sys.executable, str(CHECKER), f"{fixture_base}/site/slash",
             "--expect", "closed-visitor"], capture_output=True, text=True)
        assert ok.returncode == 0
        assert json.loads(ok.stdout)["ok"] is True

        bad = subprocess.run(
            [sys.executable, str(CHECKER), f"{fixture_base}/gateway/open",
             "--expect", "closed-visitor"], capture_output=True, text=True)
        assert bad.returncode == 1
        assert json.loads(bad.stdout)["ok"] is False

    def test_report_mode_is_machine_readable(self, fixture_base):
        run = subprocess.run(
            [sys.executable, str(CHECKER), f"{fixture_base}/chain/three"],
            capture_output=True, text=True)
        payload = json.loads(run.stdout)
        assert payload["codes"] == "308 -> 308 -> 404"
        assert len(payload["hops"]) == 3


# --- structural guarantees of the shell scripts ----------------------------

APPLY_TEXT = APPLY.read_text(encoding="utf-8")
ROLLBACK_TEXT = ROLLBACK.read_text(encoding="utf-8")


class TestApplyScriptStructure:
    def test_it_is_syntactically_valid(self):
        assert subprocess.run(["bash", "-n", str(APPLY)]).returncode == 0

    def test_it_installs_a_rollback_trap(self):
        """The first apply mutated four things, failed, and left them in place."""
        assert "trap " in APPLY_TEXT
        assert "MUTATED" in APPLY_TEXT

    def test_it_probes_through_nginx_and_not_the_origin_port(self):
        """The defect that produced VERIFICATION FAILED.

        The comments location lives in nginx. A probe of 127.0.0.1:9121 reaches
        the site runtime, where that location does not exist, so it can only
        ever see the site's own answer.
        """
        visitor_probes = [
            line for line in APPLY_TEXT.splitlines()
            if "comments_endpoint_check" in line or "--expect" in line
        ]
        assert visitor_probes, "no endpoint check invoked at all"
        assert "9121" not in "\n".join(visitor_probes), (
            "a comments endpoint is still probed on the site runtime port"
        )

    def test_it_uses_the_chain_checker_rather_than_a_bare_status_compare(self):
        assert "comments_endpoint_check.py" in APPLY_TEXT
        assert not re.search(r'\[\s*"\$visitor"\s*=\s*"503"\s*\]', APPLY_TEXT), (
            "a bare 503 comparison cannot tell a slash redirect from an open gate"
        )

    def test_it_does_not_write_a_backup_into_an_nginx_directory(self):
        """The pattern that produced the Yummy server_name conflicts.

        `include /etc/nginx/sites-enabled/*` has no extension filter, so a
        `.bak` beside a config is loaded as a second server block. Backups
        belong outside any directory nginx globs.
        """
        for line in APPLY_TEXT.splitlines():
            if "before-comments-stage1" in line and "cp " in line:
                assert "/etc/nginx" not in line.split("before-comments-stage1")[0].split()[-1], (
                    f"backup written inside an nginx directory: {line.strip()}"
                )

    def test_it_verifies_the_release_by_more_than_the_build_header(self):
        """The build id comes from template-manifest-*.json, a separate file.

        Moving the release symlink cannot change it, so a check that compares
        only that header proves nothing about which artifact is running.
        """
        for needle in ("readlink", "artifact_sha256", "cmdline", "MainPID"):
            assert needle in APPLY_TEXT, f"release verification does not inspect {needle}"

    def test_it_diagnoses_file_descriptors_before_mutating(self):
        """`Too many open files` appeared during the first run, unexplained.

        The preflight has to come before anything is changed, or the diagnosis
        arrives too late to inform the decision to proceed.
        """
        fd_at = APPLY_TEXT.find("inotify")
        # The counter is incremented, not assigned, so look for the increment.
        first_mutation = APPLY_TEXT.find("MUTATED=$((MUTATED + 1))")
        assert fd_at != -1, "no FD/inotify preflight"
        assert first_mutation != -1, "no mutation counter found"
        assert fd_at < first_mutation, "FD preflight runs after the first mutation"

    def test_it_records_foreign_nginx_warnings_without_fixing_them(self):
        assert "yummy" in APPLY_TEXT.lower()
        for line in APPLY_TEXT.splitlines():
            low = line.lower()
            if "yummy" in low:
                assert not any(w in low for w in ("rm ", "sed -i", "mv ", "> /etc")), (
                    f"the script modifies Yummy: {line.strip()}"
                )

    def test_it_states_that_the_database_is_preserved(self):
        assert "preserv" in APPLY_TEXT.lower() or "сохран" in APPLY_TEXT.lower()


class TestRollbackScriptStructure:
    def test_it_is_syntactically_valid(self):
        assert subprocess.run(["bash", "-n", str(ROLLBACK)]).returncode == 0

    def test_every_removal_tolerates_an_absent_target(self):
        """A second run must be a no-op, not an error.

        Checked on the actual statements rather than by counting `if [ -f`:
        the script guards in several different ways, and a count would pass or
        fail for reasons unrelated to whether it is safe to re-run.
        """
        for target in ("comments.conf", "animedia-comments.conf", "comments-gateway.service"):
            assert target in ROLLBACK_TEXT

        bare_rm = [
            line.strip() for line in ROLLBACK_TEXT.splitlines()
            if re.match(r"\s*rm\s", line) and not re.match(r"\s*rm\s+-[rf]*f", line)
        ]
        assert not bare_rm, f"a removal without -f cannot be repeated: {bare_rm}"

    def test_every_systemctl_call_tolerates_a_missing_unit(self):
        risky = []
        for line in ROLLBACK_TEXT.splitlines():
            stripped = line.strip()
            if not stripped.startswith("systemctl "):
                continue
            # daemon-reload and list-unit-files are safe unconditionally.
            if any(w in stripped for w in ("daemon-reload", "list-unit-files")):
                continue
            if "|| true" not in stripped:
                risky.append(stripped)
        assert not risky, f"these fail when the unit is already gone: {risky}"

    def test_it_exits_cleanly_when_nothing_was_ever_applied(self):
        """Called with no state file, it must say so and succeed."""
        assert "no state file" in ROLLBACK_TEXT
        assert "exit 0" in ROLLBACK_TEXT

    def test_it_restores_the_template_manifest_too(self):
        """Otherwise the public build id keeps naming the rolled-back release."""
        assert "template-manifest" in ROLLBACK_TEXT

    def test_it_never_drops_the_comments_database(self):
        for line in ROLLBACK_TEXT.splitlines():
            if "rm " in line and "comments.sqlite" in line:
                pytest.fail(f"rollback deletes the database: {line.strip()}")
        assert "comments.sqlite" in ROLLBACK_TEXT or "var/comments" in ROLLBACK_TEXT

    def test_it_uses_the_chain_checker_for_its_final_verification(self):
        assert "comments_endpoint_check.py" in ROLLBACK_TEXT
        assert "no-gateway" in ROLLBACK_TEXT

    def test_it_does_not_touch_the_second_domain(self):
        for line in ROLLBACK_TEXT.splitlines():
            low = line.lower()
            if "animedia-02" in low or "animedia.space" in low:
                assert not any(w in low for w in ("ln -sfn", "systemctl restart", "rm -f")), (
                    f"rollback acts on the second domain: {line.strip()}"
                )
