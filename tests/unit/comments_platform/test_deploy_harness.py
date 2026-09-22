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

        # A preflight that grants CORS to whoever asked — the thing that must
        # never be observed from an origin outside the site's allowlist.
        if path == "/preflight/permissive":
            return self._send(204, {"Access-Control-Allow-Origin": "*"})
        if path == "/preflight/strict":
            return self._send(204)

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

    def do_OPTIONS(self):
        return self.do_GET()

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


class TestPreflight:
    def test_a_preflight_without_a_cors_grant_passes(self, fixture_base):
        result = cec.follow(f"{fixture_base}/preflight/strict", method="OPTIONS",
                            origin="https://not-animedia.example")
        ok, message = cec.expect_preflight_not_permissive(result, result.last_headers)
        assert ok, message

    def test_a_preflight_granting_cors_to_a_foreign_origin_fails(self, fixture_base):
        result = cec.follow(f"{fixture_base}/preflight/permissive", method="OPTIONS",
                            origin="https://not-animedia.example")
        ok, message = cec.expect_preflight_not_permissive(result, result.last_headers)
        assert not ok
        assert "Access-Control-Allow-Origin" in message

    def test_a_204_preflight_is_neither_open_nor_closed(self, fixture_base):
        """It answers a question about origins, not about permissions."""
        result = cec.follow(f"{fixture_base}/preflight/strict", method="OPTIONS")
        assert result.final.code == 204
        assert 204 not in cec.OPEN_CODES
        assert 204 in cec.PREFLIGHT_CODES


class TestBothUrlSpellings:
    def test_the_apply_script_probes_slash_and_no_slash(self):
        """The gateway strips a trailing slash in its router, so the two
        spellings are one endpoint. A gate that held for one only would have a
        hole in it."""
        assert "/threads?" in APPLY_TEXT
        assert "/threads/?" in APPLY_TEXT
        assert "/comments\"" in APPLY_TEXT or "/comments " in APPLY_TEXT
        assert "/comments/\"" in APPLY_TEXT or "/comments/ " in APPLY_TEXT

    def test_the_apply_script_probes_a_preflight(self):
        assert "preflight-not-permissive" in APPLY_TEXT
        assert "not-animedia.example" in APPLY_TEXT

    def test_the_apply_script_asserts_nginx_include_hygiene(self):
        assert "include hygiene" in APPLY_TEXT
        assert "sites-enabled" in APPLY_TEXT


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


HYGIENE = HARNESS / "nginx_backup_hygiene.sh"
HYGIENE_TEXT = HYGIENE.read_text(encoding="utf-8")


class TestNginxBackupHygiene:
    """The rule that an nginx backup never lands in a directory nginx globs.

    This is the defect that blocked Stage 1: an earlier apply wrote
    `/etc/nginx/lords/animedia-01.conf.before-comments-stage1`, and the
    successor script refused to start while it was there — a stop that no
    unprivileged session could clear, because moving the file needs the root
    the blocked script was holding.

    The rules live in one sourced file so apply and rollback cannot drift, and
    they are exercised here against a real directory tree rather than asserted
    about by grep.
    """

    def _run(self, tmp_path, script: str) -> subprocess.CompletedProcess:
        lords = tmp_path / "etc" / "lords"
        enabled = tmp_path / "etc" / "sites-enabled"
        backups = tmp_path / "backups"
        for d in (lords, enabled, backups):
            d.mkdir(parents=True, exist_ok=True)
        return subprocess.run(
            ["bash", "-c", f'''
set -uo pipefail
die() {{ printf 'DIE: %s\\n' "$*" >&2; exit 9; }}
BACKUP_DIR="{backups}"
NGINX_GLOB_DIRS="{lords} {enabled}"
. "{HYGIENE}"
{script}
'''],
            capture_output=True, text=True,
        )

    def test_both_scripts_source_the_same_rules(self):
        for name, text in (("apply", APPLY_TEXT), ("rollback", ROLLBACK_TEXT)):
            assert "nginx_backup_hygiene.sh" in text, (
                f"{name} does not source the shared hygiene rules"
            )

    def test_a_stray_is_moved_out_of_nginx_and_not_deleted(self, tmp_path):
        stray = tmp_path / "etc" / "lords" / "animedia-01.conf.before-comments-stage1"
        stray.parent.mkdir(parents=True, exist_ok=True)
        stray.write_text("server { listen 443; }\n", encoding="utf-8")

        result = self._run(tmp_path, "nginx_quarantine")
        assert result.returncode == 0, result.stderr

        assert not stray.exists(), "the stray is still inside the nginx directory"
        copies = list((tmp_path / "backups").glob(
            "animedia-01.conf.before-comments-stage1.quarantined.*"))
        assert len(copies) == 1, f"expected one quarantined copy, got {copies}"
        assert copies[0].read_text(encoding="utf-8") == "server { listen 443; }\n", (
            "quarantine changed the file it was supposed to preserve"
        )

    def test_it_leaves_configs_and_foreign_backups_alone(self, tmp_path):
        lords = tmp_path / "etc" / "lords"
        lords.mkdir(parents=True, exist_ok=True)
        live = lords / "animedia-01.conf"
        foreign = lords / "animedia-01.conf.bak.20260910T093255Z"
        live.write_text("real\n", encoding="utf-8")
        foreign.write_text("someone else's\n", encoding="utf-8")

        self._run(tmp_path, "nginx_quarantine")

        assert live.exists(), "quarantine moved a live config"
        assert foreign.exists(), (
            "quarantine moved a backup this harness did not create; those "
            "belong to whoever made them"
        )

    def test_quarantine_is_idempotent_and_never_overwrites(self, tmp_path):
        stray = tmp_path / "etc" / "lords" / "animedia-01.conf.before-comments-stage1"
        stray.parent.mkdir(parents=True, exist_ok=True)

        stray.write_text("first\n", encoding="utf-8")
        self._run(tmp_path, "nginx_quarantine")
        second = self._run(tmp_path, "nginx_quarantine")
        assert second.stdout.strip() == "", "a second run moved something again"

        stray.write_text("second\n", encoding="utf-8")
        self._run(tmp_path, "nginx_quarantine")

        copies = sorted((tmp_path / "backups").glob("*before-comments-stage1.quarantined*"))
        assert len(copies) == 2, f"a colliding name overwrote an earlier copy: {copies}"
        assert {c.read_text(encoding="utf-8") for c in copies} == {"first\n", "second\n"}

    def test_assert_clean_reports_a_dirty_tree(self, tmp_path):
        stray = tmp_path / "etc" / "sites-enabled" / "x.conf.prev"
        stray.parent.mkdir(parents=True, exist_ok=True)
        stray.write_text("x\n", encoding="utf-8")

        dirty = self._run(tmp_path, "nginx_assert_clean")
        assert dirty.returncode == 1, "a dirty tree was reported clean"
        assert "x.conf.prev" in dirty.stdout

        self._run(tmp_path, "nginx_quarantine")
        clean = self._run(tmp_path, "nginx_assert_clean")
        assert clean.returncode == 0, clean.stdout

    def test_a_backup_path_inside_etc_nginx_is_unreachable(self, tmp_path):
        """The guarantee is structural, not a convention to remember."""
        result = self._run(
            tmp_path,
            'BACKUP_DIR=/etc/nginx/lords; nginx_backup_path "animedia-01.conf.before"',
        )
        assert result.returncode == 9, (
            "a backup destination inside /etc/nginx was accepted"
        )
        assert "refusing" in result.stderr.lower()

    def test_a_backup_name_cannot_escape_the_backup_store(self, tmp_path):
        result = self._run(tmp_path, 'nginx_backup_path "../../etc/nginx/lords/x.conf"')
        assert result.returncode == 9, "a traversing backup name was accepted"

    def test_apply_writes_its_vhost_backup_through_the_guarded_helper(self):
        """A literal path would bypass the guard that makes this permanent."""
        assert 'VHOST_BACKUP=$(nginx_backup_path' in APPLY_TEXT, (
            "the vhost backup path is not produced by nginx_backup_path"
        )
        for line in APPLY_TEXT.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if "cp -a" in stripped and "/etc/nginx" in stripped.split("cp -a")[1]:
                dest = stripped.split()[-1]
                assert not dest.startswith("/etc/nginx"), (
                    f"apply copies a backup into an nginx directory: {stripped}"
                )

    def test_rollback_refuses_to_restore_from_inside_etc_nginx(self):
        assert "/etc/nginx/*)" in ROLLBACK_TEXT, (
            "rollback does not check where its recorded backup lives"
        )
        assert "REFUSED" in ROLLBACK_TEXT


class TestAdapterBaseGate:
    """Applying a release built from a base the site no longer runs is a
    silent rollback of whatever replaced that base. It has to be refused."""

    def test_apply_compares_the_adapter_base_with_the_live_symlink(self):
        assert "rebased_onto" in APPLY_TEXT, (
            "apply does not read the base the adapter was built from"
        )
        assert "BASE_DECLARED" in APPLY_TEXT and "BASE_OF_RELEASE" in APPLY_TEXT
        assert "readlink -f" in APPLY_TEXT

    def test_the_configured_release_records_its_base(self):
        """The release the script points at must carry the field the gate reads."""
        match = re.search(r'^RELEASE_ID="([^"]+)"', APPLY_TEXT, re.M)
        assert match, "apply does not define RELEASE_ID"
        release_json = Path("/srv/lords/.frontend/releases") / match.group(1) / "RELEASE.json"
        if not release_json.exists():
            pytest.skip(f"release not present on this host: {release_json}")
        manifest = json.loads(release_json.read_text(encoding="utf-8"))
        base = (manifest.get("rebased_onto") or manifest.get("parent_release") or {})
        assert base.get("build_id"), "the release does not record the base it was built from"


class TestRehearsalTestsTheShippedRelease:
    """A rehearsal of a different artifact than the one being shipped is worse
    than no rehearsal: it reports confidence it has not earned.

    This is not hypothetical. The shadow contour carried a literal release path
    and kept exercising the adapter built from fac5643 for hours after apply
    had been rebuilt onto efdef56 — the two names differ by six characters in
    the middle of a long string, which is exactly the kind of drift that is
    invisible to a reader and fatal to a conclusion.
    """

    REHEARSAL_TEXT = (HARNESS / "comments_shadow_rehearsal.py").read_text(encoding="utf-8")

    def test_the_release_id_is_declared_in_exactly_one_place(self):
        hardcoded = re.findall(
            r'"/srv/lords/\.frontend/releases/[^"]+"', self.REHEARSAL_TEXT)
        assert hardcoded == [], (
            f"the rehearsal hardcodes a release path and can drift: {hardcoded}"
        )

    def test_the_rehearsal_resolves_the_same_release_apply_deploys(self):
        spec = importlib.util.spec_from_file_location(
            "_shadow", HARNESS / "comments_shadow_rehearsal.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        match = re.search(r'^RELEASE_ID="([^"]+)"', APPLY_TEXT, re.M)
        assert match, "apply does not define RELEASE_ID"
        assert module.RELEASE.name == match.group(1), (
            f"rehearsal would test {module.RELEASE.name}, "
            f"apply would deploy {match.group(1)}"
        )
