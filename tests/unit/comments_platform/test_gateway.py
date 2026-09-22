"""The loopback gateway, exercised over a real socket.

These run against an actual `ThreadingHTTPServer` rather than calling the API
object directly, because the properties at stake live in the plumbing: cookie
parsing, `Host` handling, body size limits, what the access log records, and
whether an ordinary visitor's request is refused before it reaches anything.

The whole Stage 1 owner scenario is rehearsed here end to end — write, read
back, edit, reply, delete — on an isolated temporary database. This is the
rehearsal the brief asks for; the owner's own test happens on the live site,
with the owner's own words, and nothing in this file writes to production.
"""

from __future__ import annotations

import json
import secrets as pysecrets
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from factory.comments_platform import cohorts
from factory.comments_platform import flags as flags_module
from factory.comments_platform.api import API_PREFIX
from factory.comments_platform.gateway import CredentialSecretResolver, build_server
from factory.comments_platform.store import CommentsStore
from factory.comments_platform.tenancy import TenantScope

REPO = Path(__file__).resolve().parents[3]
CONFIG = REPO / "config" / "comments-platform" / "sites.json"

PILOT_HOST = "animedia.icu"
SECOND_HOST = "animedia.space"
PILOT = TenantScope("animedia", "animedia-01")
SECOND = TenantScope("animedia", "animedia-02")

# A real content id from the live catalogue, used only as a thread key here.
CONTENT_ID = "master-lda-i-plameni-2"


@pytest.fixture
def credentials(tmp_path):
    """A LoadCredential-shaped directory. Keys are random, as in production."""
    directory = tmp_path / "creds"
    directory.mkdir()
    for tenant in ("animedia",):
        for purpose in ("subject", "network", "cohort"):
            # Hex, exactly as `openssl rand -hex 32` produces it. An earlier
            # version of this fixture wrote raw bytes and exposed a real defect:
            # the resolver stripped whitespace from binary material, so a key
            # that happened to start or end with 0x20 or 0x0a shortened below
            # the length check and the service refused to start — for some keys
            # and not others.
            (directory / f"{tenant}.{purpose}").write_text(pysecrets.token_hex(32))
    return directory


@pytest.fixture
def running_gateway(tmp_path, credentials):
    db = tmp_path / "comments.sqlite"
    store = CommentsStore(db)
    store.create_schema()
    for scope in (PILOT, SECOND):
        store.upsert_site(scope, module_version="0.1.0-mvp", artifact_checksum="0" * 64)
        store.upsert_policy(scope, policy_version="v1", rate_per_minute=60, rate_per_hour=600)
    store._conn.commit()
    store.close()

    server = build_server(
        host="127.0.0.1", port=0, store_path=str(db), config_path=str(CONFIG),
        secrets=CredentialSecretResolver(credentials), artifact_checksum="test-artifact",
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        yield base, CredentialSecretResolver(credentials)
    finally:
        server.shutdown()
        server.server_close()


def call(base, method, path, *, host=PILOT_HOST, body=None, cookies=None, headers=None):
    url = base + path
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Host", host)
    if data:
        request.add_header("Content-Type", "application/json")
    for name, value in (headers or {}).items():
        request.add_header(name, value)
    if cookies:
        request.add_header("Cookie", "; ".join(f"{k}={v}" for k, v in cookies.items()))
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            raw = response.read()
            return response.status, (json.loads(raw) if raw and response.headers.get(
                "Content-Type", "").startswith("application/json") else raw), dict(response.headers)
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            parsed = json.loads(raw)
        except ValueError:
            parsed = raw
        return exc.code, parsed, dict(exc.headers)


def owner_cookies(secrets, scope=PILOT):
    token = cohorts.issue_cohort_token(
        secrets, scope, cohort=cohorts.OWNER_TEST, subject_id="owner", ttl_seconds=3600
    )
    csrf = pysecrets.token_urlsafe(16)
    return {
        cohorts.COHORT_COOKIE: token,
        "cp_guest": "owner-guest-token-" + "x" * 20,
        "cp_csrf": csrf,
    }, {"X-CP-CSRF": csrf}


class TestOrdinaryVisitor:
    def test_reading_is_refused_with_503(self, running_gateway):
        base, _ = running_gateway
        status, body, _ = call(
            base, "GET",
            f"{API_PREFIX}/threads?resource_type=title&canonical_content_id={CONTENT_ID}",
        )
        assert status == 503
        assert body["error"]["code"] == "FeatureDisabled"

    def test_writing_directly_to_the_api_is_refused(self, running_gateway):
        """The probe that matters: a visitor who found the endpoint anyway."""
        base, _ = running_gateway
        csrf = pysecrets.token_urlsafe(16)
        status, body, _ = call(
            base, "POST", f"{API_PREFIX}/comments",
            body={"resource_type": "title", "canonical_content_id": CONTENT_ID,
                  "body": "комментарий от постороннего"},
            cookies={"cp_guest": "visitor-token-" + "x" * 20, "cp_csrf": csrf},
            headers={"X-CP-CSRF": csrf},
        )
        assert status == 503
        assert body["error"]["code"] == "FeatureDisabled"

    def test_the_refusal_says_nothing_about_the_pilot(self, running_gateway):
        base, _ = running_gateway
        status, body, _ = call(
            base, "GET",
            f"{API_PREFIX}/threads?resource_type=title&canonical_content_id={CONTENT_ID}",
        )
        flat = json.dumps(body)
        for leak in ("owner", "cohort", "animedia-01", "tenant"):
            assert leak not in flat

    def test_an_invented_cohort_cookie_does_not_help(self, running_gateway):
        base, _ = running_gateway
        status, _, _ = call(
            base, "GET",
            f"{API_PREFIX}/threads?resource_type=title&canonical_content_id={CONTENT_ID}",
            cookies={cohorts.COHORT_COOKIE: "owner_test.owner.9999999999"},
        )
        assert status == 503


class TestOwnerScenario:
    def test_the_whole_owner_flow(self, running_gateway):
        """Write, read back, edit, reply, then delete — the owner's checklist."""
        base, secrets = running_gateway
        jar, headers = owner_cookies(secrets)

        # 1. The thread starts empty but is served.
        status, body, _ = call(
            base, "GET",
            f"{API_PREFIX}/threads?resource_type=title&canonical_content_id={CONTENT_ID}",
            cookies=jar,
        )
        assert status == 200
        assert body["total_count"] == 0

        # 2. Write a comment.
        status, created, _ = call(
            base, "POST", f"{API_PREFIX}/comments",
            body={"resource_type": "title", "canonical_content_id": CONTENT_ID,
                  "body": "первый тестовый комментарий владельца"},
            cookies=jar, headers=headers,
        )
        # 202, not 201: the pilot site runs pre-moderation, so the owner's
        # comment is accepted and held rather than published immediately. The
        # owner is also the moderator, and the status is shown in the widget.
        assert status == 202, created
        assert created["moderation"]["held"] is True
        comment_id = created["comment"]["comment_id"]

        # 3. Read it back — the reload step in the owner's checklist.
        status, body, _ = call(
            base, "GET",
            f"{API_PREFIX}/threads?resource_type=title&canonical_content_id={CONTENT_ID}",
            cookies=jar,
        )
        assert status == 200
        assert any(item["comment_id"] == comment_id for item in body["items"])

        # 4. Edit it.
        status, edited, _ = call(
            base, "PATCH", f"{API_PREFIX}/comments/{comment_id}",
            body={"body": "исправленный текст того же комментария"},
            cookies=jar, headers=headers,
        )
        assert status == 200, edited
        assert edited["comment"]["revision"] == 2

        # 5. Reply to it.
        status, reply, _ = call(
            base, "POST", f"{API_PREFIX}/comments",
            body={"resource_type": "title", "canonical_content_id": CONTENT_ID,
                  "parent_id": comment_id, "body": "ответ на собственный комментарий"},
            cookies=jar, headers=headers,
        )
        assert status in (201, 202), reply
        assert reply["comment"]["parent_id"] == comment_id
        assert reply["comment"]["depth"] == 1

        # 6. Delete the original.
        status, deleted, _ = call(
            base, "DELETE", f"{API_PREFIX}/comments/{comment_id}",
            cookies=jar, headers=headers,
        )
        assert status == 200, deleted
        assert deleted["state"] == "removed"

        # 7. The author still sees it, marked removed — a comment that simply
        #    vanishes leaves the person wondering whether the site lost it.
        status, body, _ = call(
            base, "GET",
            f"{API_PREFIX}/threads?resource_type=title&canonical_content_id={CONTENT_ID}",
            cookies=jar,
        )
        mine = {item["comment_id"]: item for item in body["items"]}
        assert mine[comment_id]["state"] == "removed"

        # 8. And it is gone for anybody else in the cohort, along with its text.
        other_jar = dict(jar)
        other_jar["cp_guest"] = "a-different-owner-session-" + "y" * 20
        status, body, _ = call(
            base, "GET",
            f"{API_PREFIX}/threads?resource_type=title&canonical_content_id={CONTENT_ID}",
            cookies=other_jar,
        )
        assert comment_id not in {item["comment_id"] for item in body["items"]}
        assert "исправленный текст" not in json.dumps(body, ensure_ascii=False)

    def test_a_double_click_does_not_create_two_comments(self, running_gateway):
        base, secrets = running_gateway
        jar, headers = owner_cookies(secrets)
        payload = {"resource_type": "title", "canonical_content_id": CONTENT_ID,
                   "body": "комментарий, отправленный дважды подряд"}
        idem = {**headers, "Idempotency-Key": "owner-double-click"}

        first = call(base, "POST", f"{API_PREFIX}/comments", body=payload,
                     cookies=jar, headers=idem)
        second = call(base, "POST", f"{API_PREFIX}/comments", body=payload,
                      cookies=jar, headers=idem)
        assert first[1]["comment"]["comment_id"] == second[1]["comment"]["comment_id"]

        # The pilot runs pre-moderation, so the comment is held and therefore
        # not in the public count. What must be true either way is that a
        # second identical submit produced no second row.
        status, body, _ = call(
            base, "GET",
            f"{API_PREFIX}/threads?resource_type=title&canonical_content_id={CONTENT_ID}",
            cookies=jar,
        )
        assert body["total_count"] == 0
        assert len(body["items"]) == 1
        assert body["items"][0]["state"] == "pending"

    def test_csrf_is_still_required_for_the_owner(self, running_gateway):
        base, secrets = running_gateway
        jar, _ = owner_cookies(secrets)
        status, body, _ = call(
            base, "POST", f"{API_PREFIX}/comments",
            body={"resource_type": "title", "canonical_content_id": CONTENT_ID, "body": "без csrf"},
            cookies=jar,
        )
        assert status == 403


class TestTokenDoesNotReachTheSecondDomain:
    def test_a_pilot_cookie_presented_on_animedia_space_is_refused(self, running_gateway):
        base, secrets = running_gateway
        jar, headers = owner_cookies(secrets, PILOT)
        status, body, _ = call(
            base, "GET",
            f"{API_PREFIX}/threads?resource_type=title&canonical_content_id={CONTENT_ID}",
            host=SECOND_HOST, cookies=jar,
        )
        assert status == 503, body

    def test_even_a_cookie_minted_for_the_second_domain_is_refused(self, running_gateway):
        """The site is outside PILOT_SITES, so a valid token changes nothing."""
        base, secrets = running_gateway
        jar, headers = owner_cookies(secrets, SECOND)
        status, _, _ = call(
            base, "GET",
            f"{API_PREFIX}/threads?resource_type=title&canonical_content_id={CONTENT_ID}",
            host=SECOND_HOST, cookies=jar,
        )
        assert status == 503


class TestAssets:
    @pytest.mark.parametrize("name", ["comments-widget.js", "comments-widget.css"])
    def test_the_pinned_widget_files_are_served(self, running_gateway, name):
        base, _ = running_gateway
        status, body, headers = call(base, "GET", f"{API_PREFIX}/assets/{name}")
        assert status == 200
        assert len(body) > 1000
        assert headers["ETag"].strip('"')
        assert headers["X-Robots-Tag"] == "noindex, nofollow"

    def test_an_etag_match_is_answered_304(self, running_gateway):
        base, _ = running_gateway
        _, _, headers = call(base, "GET", f"{API_PREFIX}/assets/comments-widget.js")
        status, _, _ = call(
            base, "GET", f"{API_PREFIX}/assets/comments-widget.js",
            headers={"If-None-Match": headers["ETag"]},
        )
        assert status == 304

    @pytest.mark.parametrize("name", [
        "../../../etc/passwd", "..%2f..%2fetc%2fpasswd", ".env", "gateway.py", "store.py",
    ])
    def test_path_traversal_and_source_files_are_refused(self, running_gateway, name):
        base, _ = running_gateway
        status, _, _ = call(base, "GET", f"{API_PREFIX}/assets/{name}")
        assert status == 404

    def test_assets_are_served_without_a_cohort(self, running_gateway):
        """The widget file itself is not secret; what it may do is gated."""
        base, _ = running_gateway
        status, _, _ = call(base, "GET", f"{API_PREFIX}/assets/comments-widget.css")
        assert status == 200


class TestHealth:
    def test_health_reports_what_is_running(self, running_gateway):
        base, _ = running_gateway
        status, body, _ = call(base, "GET", f"{API_PREFIX}/healthz")
        assert status == 200
        assert body["status"] == "ok"
        assert body["artifact_checksum"] == "test-artifact"
        assert body["site"]["site_id"] == "animedia-01"
        assert body["site"]["public"]["COMMENTS_READ_ENABLED"] == 0
        assert body["site"]["owner_test"]["COMMENTS_READ_ENABLED"] == 1

    def test_health_holds_no_secret(self, running_gateway):
        base, secrets = running_gateway
        _, body, _ = call(base, "GET", f"{API_PREFIX}/healthz")
        flat = json.dumps(body).lower()
        for forbidden in ("key", "token", "secret", "credential", "cookie"):
            assert forbidden not in flat


class TestHardening:
    def test_an_oversized_body_is_refused_before_processing(self, running_gateway):
        base, secrets = running_gateway
        jar, headers = owner_cookies(secrets)
        status, body, _ = call(
            base, "POST", f"{API_PREFIX}/comments",
            body={"resource_type": "title", "canonical_content_id": CONTENT_ID,
                  "body": "x" * 200_000},
            cookies=jar, headers=headers,
        )
        assert status == 413

    def test_a_malformed_body_is_a_400_not_a_500(self, running_gateway):
        base, secrets = running_gateway
        jar, headers = owner_cookies(secrets)
        request = urllib.request.Request(
            base + f"{API_PREFIX}/comments", data=b"{not json at all", method="POST"
        )
        request.add_header("Host", PILOT_HOST)
        request.add_header("Content-Type", "application/json")
        request.add_header("Cookie", "; ".join(f"{k}={v}" for k, v in jar.items()))
        for k, v in headers.items():
            request.add_header(k, v)
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                status = response.status
        except urllib.error.HTTPError as exc:
            status = exc.code
        assert status == 400

    def test_an_unknown_host_is_404_and_names_no_site(self, running_gateway):
        base, _ = running_gateway
        status, body, _ = call(
            base, "GET",
            f"{API_PREFIX}/threads?resource_type=title&canonical_content_id={CONTENT_ID}",
            host="attacker.example",
        )
        assert status == 404
        flat = json.dumps(body)
        for site in ("animedia", "lords", "zona", "yummy"):
            assert site not in flat

    def test_the_gateway_refuses_a_non_loopback_bind(self):
        from factory.comments_platform.gateway import main

        with pytest.raises(SystemExit) as exc:
            main(["--host", "0.0.0.0", "--port", "9150", "--store", "/tmp/x",
                  "--config", str(CONFIG), "--credentials", "/tmp"])
        assert "loopback" in str(exc.value)

    def test_missing_credentials_refuse_to_start(self, tmp_path):
        with pytest.raises(SystemExit):
            CredentialSecretResolver(tmp_path / "does-not-exist")

    def test_a_short_credential_is_refused(self, tmp_path):
        directory = tmp_path / "creds"
        directory.mkdir()
        (directory / "animedia.cohort").write_text(pysecrets.token_hex(8))
        resolver = CredentialSecretResolver(directory)
        with pytest.raises(SystemExit):
            resolver.tenant_key("animedia", "cohort")

    def test_a_non_hex_credential_is_refused_with_the_fix_command(self, tmp_path):
        directory = tmp_path / "creds"
        directory.mkdir()
        (directory / "animedia.cohort").write_text("this is not hex at all, sorry")
        resolver = CredentialSecretResolver(directory)
        with pytest.raises(SystemExit) as exc:
            resolver.tenant_key("animedia", "cohort")
        assert "openssl rand -hex 32" in str(exc.value)

    def test_whitespace_around_a_hex_key_is_tolerated(self, tmp_path):
        """`echo` adds a newline; that must not shorten the key."""
        directory = tmp_path / "creds"
        directory.mkdir()
        key = pysecrets.token_hex(32)
        (directory / "animedia.cohort").write_text(f"  {key}\n")
        resolver = CredentialSecretResolver(directory)
        assert len(resolver.tenant_key("animedia", "cohort")) == 32


class TestKillSwitch:
    def test_the_switch_closes_the_owner_cohort_over_http(self, running_gateway):
        base, secrets = running_gateway
        jar, _ = owner_cookies(secrets)
        flags_module.KillSwitch.engage_global()
        try:
            status, _, _ = call(
                base, "GET",
                f"{API_PREFIX}/threads?resource_type=title&canonical_content_id={CONTENT_ID}",
                cookies=jar,
            )
            assert status == 503
        finally:
            flags_module.KillSwitch.release_global()

        status, _, _ = call(
            base, "GET",
            f"{API_PREFIX}/threads?resource_type=title&canonical_content_id={CONTENT_ID}",
            cookies=jar,
        )
        assert status == 200
