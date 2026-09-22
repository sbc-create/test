"""API contract: routing, CORS, CSRF, error shapes and what never leaks."""

from __future__ import annotations

import json

import pytest

from factory.comments_platform.api import (
    API_PREFIX,
    SECURITY_HEADERS,
    CommentsApi,
    Request,
    openapi_document,
)
from factory.comments_platform.errors import PUBLIC_ERROR_CODES
from factory.comments_platform.identity import IdentityResolver

LORDS_HOST = "lords-main.example"
LORDS_ORIGIN = "https://lords-main.example"
ZONA_HOST = "zona-main.example"


@pytest.fixture
def api(service, open_registry, secrets_resolver):
    return CommentsApi(service, open_registry, IdentityResolver(secrets_resolver, None))


class BearerUpstream:
    """The shape a site's own auth contour supplies: opaque subject or None.

    Real deployments hand the platform something that has already verified a
    session. This stands in for that, and nothing more — the platform never
    learns what the token contained.
    """

    def authenticated_subject(self, request_context):
        header = str(request_context.get("authorization", ""))
        if header.startswith("Bearer "):
            return header[len("Bearer "):] or None
        return None


@pytest.fixture
def api_with_auth(service, open_registry, secrets_resolver):
    return CommentsApi(
        service, open_registry, IdentityResolver(secrets_resolver, BearerUpstream())
    )


def get(path, **kw):
    kw.setdefault("host", LORDS_HOST)
    kw.setdefault("cookies", {"cp_guest": "guest-token-" + "x" * 20})
    return Request(method="GET", path=path, **kw)


def post(path, body, *, host=LORDS_HOST, csrf=True, **kw):
    cookies = {"cp_guest": "guest-token-" + "x" * 20}
    headers = dict(kw.pop("headers", {}))
    if csrf:
        cookies["cp_csrf"] = "csrf-value"
        headers["X-CP-CSRF"] = "csrf-value"
    return Request(
        method="POST", path=path, host=host, body=body,
        cookies=cookies, headers=headers, **kw
    )


def create(api, body="a comment written through the API"):
    return api.handle(
        post(
            f"{API_PREFIX}/comments",
            {"resource_type": "title", "canonical_content_id": "tt-api", "body": body},
        )
    )


class TestRouting:
    def test_unknown_path_is_not_found(self, api):
        assert api.handle(get("/api/comments/v1/nope")).status == 404

    def test_a_different_api_version_is_not_found(self, api):
        assert api.handle(get("/api/comments/v2/threads")).status == 404

    def test_thread_read_returns_a_page(self, api):
        create(api)
        response = api.handle(
            get(
                f"{API_PREFIX}/threads",
                query={"resource_type": "title", "canonical_content_id": "tt-api"},
            )
        )
        assert response.status == 200
        assert response.body["total_count"] == 1
        assert len(response.body["items"]) == 1

    def test_count_endpoint(self, api):
        create(api)
        response = api.handle(
            get(
                f"{API_PREFIX}/threads/count",
                query={"resource_type": "title", "canonical_content_id": "tt-api"},
            )
        )
        assert response.body == {"count": 1}

    def test_create_returns_201_when_published(self, api):
        assert create(api).status == 201

    def test_create_returns_202_when_held(self, api):
        response = create(api, body="BUY NOW CHEAP CLICK https://spam.test/x")
        assert response.status == 202
        assert response.body["moderation"]["held"] is True

    def test_missing_query_parameters_are_a_validation_error(self, api):
        response = api.handle(get(f"{API_PREFIX}/threads"))
        assert response.status == 400
        assert response.body["error"]["code"] == "ValidationFailed"

    def test_a_non_object_body_is_refused(self, api):
        request = post(f"{API_PREFIX}/comments", None)
        assert api.handle(request).status == 400


class TestScopeCannotBeSupplied:
    @pytest.mark.parametrize("field", ["tenant_id", "site_id", "tenant", "site"])
    def test_a_body_naming_a_tenant_is_refused(self, api, field):
        response = api.handle(
            post(
                f"{API_PREFIX}/comments",
                {
                    "resource_type": "title", "canonical_content_id": "tt-api",
                    "body": "hello", field: "zona",
                },
            )
        )
        assert response.status == 400

    @pytest.mark.parametrize("field", ["tenant_id", "site_id"])
    def test_a_query_naming_a_tenant_is_refused(self, api, field):
        response = api.handle(
            get(f"{API_PREFIX}/threads", query={field: "zona", "resource_type": "title"})
        )
        assert response.status == 400

    def test_the_host_decides_the_site(self, api, store, scopes):
        create(api)
        # The same content id read through the other site's host is empty.
        response = api.handle(
            Request(
                method="GET", path=f"{API_PREFIX}/threads", host=ZONA_HOST,
                query={"resource_type": "title", "canonical_content_id": "tt-api"},
                cookies={"cp_guest": "guest-token-" + "x" * 20},
            )
        )
        assert response.status == 200
        assert response.body["total_count"] == 0
        assert response.body["items"] == []

    def test_an_unknown_host_is_not_found_and_names_no_site(self, api):
        response = api.handle(
            Request(method="GET", path=f"{API_PREFIX}/threads", host="attacker.example")
        )
        assert response.status == 404
        flat = json.dumps(response.body)
        for site in ("lords", "zona", "animedia", "yummy"):
            assert site not in flat


class TestCors:
    def test_an_allowed_origin_is_echoed_exactly(self, api):
        response = api.handle(
            get(
                f"{API_PREFIX}/threads",
                headers={"Origin": LORDS_ORIGIN},
                query={"resource_type": "title", "canonical_content_id": "tt-api"},
            )
        )
        assert response.headers["Access-Control-Allow-Origin"] == LORDS_ORIGIN
        assert response.headers["Vary"] == "Origin"

    @pytest.mark.parametrize(
        "origin",
        [
            "https://evil.test",
            "https://lords-main.example.evil.test",
            "http://lords-main.example",
            "null",
            "https://lords-main.example:8443",
        ],
    )
    def test_a_disallowed_origin_gets_no_cors_header_at_all(self, api, origin):
        response = api.handle(
            get(
                f"{API_PREFIX}/threads",
                headers={"Origin": origin},
                query={"resource_type": "title", "canonical_content_id": "tt-api"},
            )
        )
        assert "Access-Control-Allow-Origin" not in response.headers

    def test_no_wildcard_is_ever_emitted(self, api):
        response = api.handle(
            get(
                f"{API_PREFIX}/threads",
                headers={"Origin": LORDS_ORIGIN},
                query={"resource_type": "title", "canonical_content_id": "tt-api"},
            )
        )
        assert response.headers.get("Access-Control-Allow-Origin") != "*"

    def test_preflight_is_answered(self, api):
        response = api.handle(
            Request(
                method="OPTIONS", path=f"{API_PREFIX}/comments", host=LORDS_HOST,
                headers={"Origin": LORDS_ORIGIN},
            )
        )
        assert response.status == 204
        assert "Access-Control-Allow-Methods" in response.headers


class TestCsrf:
    def test_a_cookie_authenticated_write_without_a_token_is_refused(self, api):
        response = api.handle(
            post(
                f"{API_PREFIX}/comments",
                {"resource_type": "title", "canonical_content_id": "tt-api", "body": "x"},
                csrf=False,
            )
        )
        assert response.status == 403
        assert response.body["error"]["code"] == "Forbidden"

    def test_a_mismatched_token_is_refused(self, api):
        request = post(
            f"{API_PREFIX}/comments",
            {"resource_type": "title", "canonical_content_id": "tt-api", "body": "x"},
        )
        request.headers = {"X-CP-CSRF": "not-the-cookie-value"}
        assert api.handle(request).status == 403

    def test_reads_do_not_need_a_token(self, api):
        response = api.handle(
            get(
                f"{API_PREFIX}/threads",
                query={"resource_type": "title", "canonical_content_id": "tt-api"},
            )
        )
        assert response.status == 200

    def test_token_auth_does_not_require_csrf(self, api_with_auth):
        """A cross-site form cannot set an Authorization header.

        Requiring CSRF on the token path as well would protect nothing and
        would eventually get switched off by somebody debugging a 403.
        """
        request = Request(
            method="POST", path=f"{API_PREFIX}/comments", host=LORDS_HOST,
            body={"resource_type": "title", "canonical_content_id": "tt-api", "body": "hi there"},
            headers={"Authorization": "Bearer opaque-upstream-subject"},
            cookies={},
        )
        assert api_with_auth.handle(request).status in (201, 202)

    def test_an_authenticated_subject_is_not_a_guest(self, api_with_auth):
        response = api_with_auth.handle(
            Request(
                method="POST", path=f"{API_PREFIX}/comments", host=LORDS_HOST,
                body={
                    "resource_type": "title", "canonical_content_id": "tt-api",
                    "body": "written while signed in",
                },
                headers={"Authorization": "Bearer opaque-upstream-subject"},
                cookies={},
            )
        )
        assert response.body["comment"]["author"]["subject_id"].startswith("u_")

    def test_the_upstream_token_never_appears_in_the_response(self, api_with_auth):
        token = "an-extremely-secret-session-value"
        response = api_with_auth.handle(
            Request(
                method="POST", path=f"{API_PREFIX}/comments", host=LORDS_HOST,
                body={
                    "resource_type": "title", "canonical_content_id": "tt-api",
                    "body": "a comment from a signed-in reader",
                },
                headers={"Authorization": f"Bearer {token}"},
                cookies={},
            )
        )
        assert token not in json.dumps(response.body)
        assert token not in json.dumps(response.headers)


class TestErrorsAreSafe:
    def test_every_error_carries_a_request_id(self, api):
        response = api.handle(get("/api/comments/v1/nope"))
        assert response.body["error"]["request_id"]
        assert response.headers["X-Request-Id"]

    def test_a_supplied_request_id_is_preserved(self, api):
        response = api.handle(
            get("/api/comments/v1/nope", headers={"X-Request-Id": "trace-me-42"})
        )
        assert response.body["error"]["request_id"] == "trace-me-42"

    def test_error_codes_stay_inside_the_published_set(self, api):
        probes = [
            get("/api/comments/v1/nope"),
            get(f"{API_PREFIX}/threads"),
            post(f"{API_PREFIX}/comments", {"body": ""}),
            post(f"{API_PREFIX}/comments", {"resource_type": "title",
                                            "canonical_content_id": "tt", "body": "x"},
                 csrf=False),
        ]
        for probe in probes:
            response = api.handle(probe)
            if response.status >= 400:
                assert response.body["error"]["code"] in PUBLIC_ERROR_CODES

    def test_an_unexpected_exception_does_not_leak_internals(self, api, monkeypatch):
        def explode(*args, **kwargs):
            raise RuntimeError("secret internal detail: /srv/path/to/db.sqlite")

        monkeypatch.setattr(api._service, "comment_count", explode)
        response = api.handle(
            get(
                f"{API_PREFIX}/threads/count",
                query={"resource_type": "title", "canonical_content_id": "tt-api"},
            )
        )
        assert response.status == 500
        flat = json.dumps(response.body)
        assert "secret internal detail" not in flat
        assert "sqlite" not in flat
        assert "Traceback" not in flat

    def test_cross_tenant_probing_returns_404_not_403(self, api, service, scopes,
                                                      users, identities):
        """The classic IDOR probe: another site's comment id, guessed or leaked."""
        from factory.comments_platform.tenancy import ResourceRef

        foreign = service.create_comment(
            scopes["zona"], users["zona"], identities["zona"],
            ResourceRef("title", "tt-api"), body="a zona comment",
        )["comment"]["comment_id"]

        response = api.handle(
            post(f"{API_PREFIX}/comments/{foreign}/reactions", {"reaction": "like"})
        )
        assert response.status == 404
        assert response.body["error"]["code"] == "NotFound"


class TestSecurityHeaders:
    @pytest.mark.parametrize("header", sorted(SECURITY_HEADERS))
    def test_header_is_present_on_success(self, api, header):
        create(api)
        response = api.handle(
            get(
                f"{API_PREFIX}/threads",
                query={"resource_type": "title", "canonical_content_id": "tt-api"},
            )
        )
        assert header in response.headers

    @pytest.mark.parametrize("header", sorted(SECURITY_HEADERS))
    def test_header_is_present_on_error(self, api, header):
        assert header in api.handle(get("/api/comments/v1/nope")).headers

    def test_module_version_is_advertised(self, api):
        response = api.handle(get("/api/comments/v1/nope"))
        assert response.headers["X-Comments-Module-Version"]
        assert response.headers["X-Comments-Module-Version"] != "latest"


class TestNothingPrivateReachesTheClient:
    def test_a_held_comment_is_absent_from_the_public_page(
        self, api, service, scopes, users, identities, moderators
    ):

        created = create(api)
        comment_id = created.body["comment"]["comment_id"]
        service.moderate(
            scopes["lords"], moderators["lords"], comment_id,
            action="hide", reason="off topic",
        )
        response = api.handle(
            Request(
                method="GET", path=f"{API_PREFIX}/threads", host=LORDS_HOST,
                query={"resource_type": "title", "canonical_content_id": "tt-api"},
                cookies={"cp_guest": "a-completely-different-guest-token"},
            )
        )
        flat = json.dumps(response.body)
        assert comment_id not in flat
        assert "a comment written through the API" not in flat

    def test_no_tenant_or_site_appears_in_any_response(self, api):
        create(api)
        response = api.handle(
            get(
                f"{API_PREFIX}/threads",
                query={"resource_type": "title", "canonical_content_id": "tt-api"},
            )
        )
        flat = json.dumps(response.body)
        for leak in ("tenant_id", "site_id", "lords-main", "zona", "animedia", "yummy"):
            assert leak not in flat


class TestOpenApiMatchesTheImplementation:
    def test_every_documented_path_routes(self, api):
        doc = openapi_document()
        for path, methods in doc["paths"].items():
            concrete = path.replace("{comment_id}", "c_example")
            for method in methods:
                request = Request(
                    method=method.upper(), path=concrete, host=LORDS_HOST
                )
                handler, _ = api._route(request)
                assert handler is not None, f"{method.upper()} {path} is documented but unrouted"

    def test_every_routed_endpoint_is_documented(self, api):
        doc = openapi_document()
        documented = {
            (method.upper(), path) for path, methods in doc["paths"].items() for method in methods
        }
        routed = [
            ("GET", f"{API_PREFIX}/threads"),
            ("GET", f"{API_PREFIX}/threads/count"),
            ("POST", f"{API_PREFIX}/comments"),
            ("PATCH", f"{API_PREFIX}/comments/{{comment_id}}"),
            ("DELETE", f"{API_PREFIX}/comments/{{comment_id}}"),
            ("POST", f"{API_PREFIX}/comments/{{comment_id}}/reactions"),
            ("DELETE", f"{API_PREFIX}/comments/{{comment_id}}/reactions"),
            ("POST", f"{API_PREFIX}/comments/{{comment_id}}/reports"),
        ]
        for entry in routed:
            assert entry in documented, f"{entry} is implemented but undocumented"

    def test_contract_states_the_tenancy_rule(self):
        doc = openapi_document()
        assert doc["x-tenancy"]["cross_tenant_response"] == "404"
        assert "body" in doc["x-tenancy"]["never_accepted_from"]

    def test_contract_is_serialisable(self):
        assert json.loads(json.dumps(openapi_document()))
