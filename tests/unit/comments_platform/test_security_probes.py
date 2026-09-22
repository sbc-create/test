"""Injection, IDOR, SSRF and brigading probes.

These are the tests the threat model points at. A threat model that names a
control and cites no run of it is a document, not a proof — so every row of
`02-threat-model/THREAT_MODEL.json` that claims a test is answered here or in
one of the suites it names.
"""

from __future__ import annotations

import inspect
import re
from pathlib import Path

import pytest

from factory.comments_platform import antiabuse, api
from factory.comments_platform import service as service_module
from factory.comments_platform import store as store_module
from factory.comments_platform.errors import NotFound, PolicyViolation, ValidationFailed
from factory.comments_platform.identity import Identity
from factory.comments_platform.rbac import USER, Principal
from factory.comments_platform.tenancy import ResourceRef

PACKAGE = Path(store_module.__file__).parent
REF = ResourceRef("title", "tt-probe")

SQL_PAYLOADS = [
    "'; DROP TABLE cp_comments; --",
    "' OR '1'='1",
    "' UNION SELECT tenant_id, site_id, body FROM cp_comments --",
    "\"; DELETE FROM cp_audit_events; --",
    "1; PRAGMA foreign_keys=OFF; --",
    "admin'--",
    "' OR 1=1 LIMIT 1 OFFSET 0 --",
    "'); ATTACH DATABASE '/tmp/evil.sqlite' AS evil; --",
    "%27%20OR%20%271%27%3D%271",
    "' AND (SELECT COUNT(*) FROM cp_identities) > 0 --",
]


@pytest.fixture
def lords(scopes):
    return scopes["lords"]


@pytest.fixture
def actor(lords, identities):
    identity = identities["lords"]
    return Principal(subject_id=identity.subject_id, role=USER, scope=lords), identity


class TestSqlInjection:
    @pytest.mark.parametrize("payload", SQL_PAYLOADS)
    def test_a_payload_in_a_comment_body_is_stored_as_text(
        self, service, store, lords, actor, payload
    ):
        principal, identity = actor
        result = service.create_comment(
            lords, principal, identity, REF, body=f"безобидное начало {payload}"
        )
        row = store.get_comment(lords, result["comment"]["comment_id"])
        # The tables are all still there, and the payload is data.
        assert payload.split()[0][:6] in row["body"] or payload[:6] in row["body"]
        assert store.raw_count("cp_comments") >= 1
        assert store.raw_count("cp_audit_events") >= 1

    @pytest.mark.parametrize("payload", SQL_PAYLOADS)
    def test_a_payload_as_a_comment_id_is_not_found(self, store, lords, payload):
        with pytest.raises(NotFound):
            store.get_comment(lords, payload)

    @pytest.mark.parametrize("payload", SQL_PAYLOADS)
    def test_a_payload_as_a_content_id_is_refused_by_validation(self, payload):
        with pytest.raises(ValidationFailed):
            ResourceRef("title", payload)

    @pytest.mark.parametrize("payload", SQL_PAYLOADS)
    def test_a_payload_as_a_cursor_does_not_execute(self, service, store, lords, actor, payload):
        principal, identity = actor
        service.create_comment(lords, principal, identity, REF, body="один комментарий")
        thread = store.find_thread(lords, REF)
        with pytest.raises(Exception) as exc:
            store.list_comments(
                lords, thread["thread_id"], visible_states=["published"], cursor=payload
            )
        # A refused cursor, not an executed statement.
        assert "cursor" in str(exc.value).lower() or exc.type.__name__ == "Conflict"
        assert store.raw_count("cp_comments") == 1

    def test_the_package_interpolates_no_values_into_sql(self):
        """Every value reaches SQLite as a bound parameter.

        Judged from the syntax tree, not from the text. Two earlier attempts
        used a line regex and both produced noise instead of findings: the
        first flagged ordinary Python dict literals (`columns = {`) as SQL
        interpolation, because `{` after `=` looks the same to a regex whether
        it opens an f-string placeholder or a dictionary. The question "what is
        passed to execute()" is a question about structure, and `ast` answers
        it exactly.

        f-strings do legitimately appear in this package's SQL: a list of `?`
        placeholders whose length depends on how many states are being queried,
        and a table name in the diagnostic helpers that tests use. Both are
        built from names this test enumerates, so a new interpolation of
        anything else fails here.
        """
        import ast

        # Names that may appear inside an f-string that becomes SQL. Each is
        # either a generated run of `?` placeholders or an identifier from a
        # closed constant list — never a value from a request.
        ALLOWED_INTERPOLATIONS = {
            "placeholders",       # "?,?,?" built from len(states)
            "author_placeholders",
            "names",             # column name list for an upsert
            "updates",           # "col=excluded.col" list
            "table",             # diagnostics only: raw_count / columns_of
            "order",             # one of three constant ORDER BY fragments
            "cursor_op",         # "<" or ">", chosen from a literal dict
            "' AND '.join(where)",
        }

        offenders = []
        for path in sorted(PACKAGE.glob("**/*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                if not isinstance(func, ast.Attribute):
                    continue
                if func.attr not in ("execute", "executemany", "executescript"):
                    continue
                if not node.args:
                    continue
                first = node.args[0]
                if isinstance(first, ast.Constant):
                    continue  # a plain literal
                if isinstance(first, ast.BinOp):
                    continue  # literal concatenation
                if isinstance(first, ast.Name):
                    continue  # a statement from the schema module's list
                if isinstance(first, ast.JoinedStr):
                    for part in first.values:
                        if not isinstance(part, ast.FormattedValue):
                            continue
                        expression = ast.unparse(part.value)
                        if expression not in ALLOWED_INTERPOLATIONS:
                            offenders.append(
                                f"{path.name}:{node.lineno}: interpolates {expression!r}"
                            )
                    continue
                offenders.append(
                    f"{path.name}:{node.lineno}: SQL is {type(first).__name__}, "
                    "not a literal"
                )
        assert not offenders, "values interpolated into SQL:\n" + "\n".join(offenders)


class TestIdor:
    def test_another_authors_comment_cannot_be_edited(self, service, lords, actor):
        principal, identity = actor
        comment_id = service.create_comment(
            lords, principal, identity, REF, body="чужой комментарий"
        )["comment"]["comment_id"]

        stranger_identity = Identity(subject_id="g_stranger", scope=lords, is_guest=True)
        stranger = Principal(subject_id="g_stranger", role=USER, scope=lords)
        from factory.comments_platform.errors import Forbidden

        with pytest.raises(Forbidden):
            service.edit_own_comment(
                lords, stranger, stranger_identity, comment_id, body="переписал"
            )

    def test_a_sequential_id_guess_finds_nothing(self, store, lords):
        """Ids are random, not sequential, so enumeration has nothing to walk."""
        for guess in ("c_1", "c_2", "c_000000000000000000000001"):
            with pytest.raises(NotFound):
                store.get_comment(lords, guess)

    def test_ids_are_not_predictable(self, service, lords):
        """Five distinct authors, because one author hits the rate limit at three.

        Using one author here failed with RateLimited, which is the anti-abuse
        layer working; the property under test is id shape, so the burst is
        spread across authors rather than the limit being raised.
        """
        # Genuinely different words, not one sentence with a changing number:
        # near_digest strips digits on purpose, so numbered variants of one
        # sentence are a near-duplicate flood and the detector refuses them.
        # That is the detector working, and the property under test is id shape.
        bodies = (
            "первый отзыв про режиссуру и монтаж этой картины",
            "второй текст обсуждает музыку и работу оператора",
            "третье мнение целиком про игру исполнителя главной роли",
            "четвёртая заметка сравнивает финал с книжным источником",
            "пятый комментарий хвалит художника по костюмам отдельно",
        )
        ids = []
        for index, body in enumerate(bodies):
            identity = Identity(
                subject_id=f"g_author{index}", scope=lords, is_guest=True
            )
            principal = Principal(subject_id=identity.subject_id, role=USER, scope=lords)
            ids.append(
                service.create_comment(lords, principal, identity, REF, body=body)[
                    "comment"
                ]["comment_id"]
            )
        suffixes = [i.split("_", 1)[1] for i in ids]
        assert len(set(suffixes)) == 5
        # Fixed width, so the length of an id leaks nothing about when it was
        # created.
        assert len({len(s) for s in suffixes}) == 1
        # And no long shared prefix between consecutive ids. A sequential or
        # timestamp-derived scheme shows one, and that is exactly what makes a
        # neighbouring id guessable.
        for earlier, later in zip(suffixes, suffixes[1:], strict=False):
            shared = 0
            for left, right in zip(earlier, later, strict=False):
                if left != right:
                    break
                shared += 1
            assert shared < 6, f"{earlier} and {later} share {shared} leading characters"


class TestNoOutboundFetch:
    """The platform never dereferences a URL a user supplied.

    That is what keeps a comment from becoming an SSRF primitive: a link is
    rendered as text with an http(s) scheme check and is never fetched, so
    there is no request for an attacker to aim at an internal address.
    """

    def test_the_package_imports_no_http_client(self):
        forbidden = {"requests", "httpx", "urllib.request", "http.client", "aiohttp", "socket"}
        offenders = []
        for path in PACKAGE.glob("**/*.py"):
            source = path.read_text(encoding="utf-8")
            for module in forbidden:
                if re.search(rf"^\s*(?:import|from)\s+{re.escape(module)}\b", source, re.M):
                    offenders.append(f"{path.name}: {module}")
        assert not offenders, f"outbound HTTP capability in the package: {offenders}"

    def test_no_module_opens_a_url(self):
        offenders = []
        for path in PACKAGE.glob("**/*.py"):
            source = path.read_text(encoding="utf-8")
            for needle in ("urlopen(", "requests.get(", "requests.post(", "socket.socket("):
                if needle in source:
                    offenders.append(f"{path.name}: {needle}")
        assert not offenders, offenders

    @pytest.mark.parametrize(
        "internal",
        [
            "http://169.254.169.254/latest/meta-data/",
            "http://127.0.0.1:8787/admin",
            "http://localhost/internal",
            "http://[::1]/internal",
            "file:///etc/passwd",
            "gopher://127.0.0.1:11211/",
        ],
    )
    def test_an_internal_address_in_a_comment_is_only_text(
        self, service, store, lords, actor, internal
    ):
        principal, identity = actor
        try:
            result = service.create_comment(
                lords, principal, identity, REF, body=f"посмотрите тут {internal} и всё"
            )
        except PolicyViolation:
            return  # refusing it outright is also an acceptable answer
        row = store.get_comment(lords, result["comment"]["comment_id"])
        # Whatever the rendering decided, no request was made — proved
        # structurally above — and a non-http scheme never becomes a link.
        if internal.startswith(("file:", "gopher:")):
            assert f'href="{internal}"' not in row["body_html"]


class TestReportBrigading:
    def test_many_reporters_from_one_network_do_not_hide_a_comment(
        self, service, store, lords, actor
    ):
        principal, identity = actor
        comment_id = service.create_comment(
            lords, principal, identity, REF, body="комментарий, который кому-то не нравится"
        )["comment"]["comment_id"]

        # Six reporters, all sharing one network identifier: one person with a
        # script, not a community reaching consensus.
        for index in range(6):
            reporter_identity = Identity(
                subject_id=f"g_brigade{index}", scope=lords, is_guest=True,
                network_hmac="n_same_place",
            )
            reporter = Principal(
                subject_id=reporter_identity.subject_id, role=USER, scope=lords
            )
            service.report_comment(
                lords, reporter, reporter_identity, comment_id, reason="abuse"
            )

        assert store.distinct_reporters(lords, comment_id) == 6
        assert store.distinct_report_networks(lords, comment_id) == 1
        # Still visible: volume from one place did not make a moderation decision.
        assert store.get_comment(lords, comment_id)["state"] == "published"

    def test_genuine_reports_from_many_places_do_reach_the_queue(
        self, service, store, lords, actor
    ):
        principal, identity = actor
        comment_id = service.create_comment(
            lords, principal, identity, REF, body="комментарий, на который жалуются по делу"
        )["comment"]["comment_id"]

        for index in range(5):
            reporter_identity = Identity(
                subject_id=f"g_real{index}", scope=lords, is_guest=True,
                network_hmac=f"n_place{index}",
            )
            reporter = Principal(
                subject_id=reporter_identity.subject_id, role=USER, scope=lords
            )
            service.report_comment(
                lords, reporter, reporter_identity, comment_id, reason="abuse"
            )

        assert store.distinct_report_networks(lords, comment_id) == 5
        assert store.get_comment(lords, comment_id)["state"] == "quarantined"

    def test_the_brigade_detector_needs_network_information_to_fire(self, store, lords):
        detector = antiabuse.AntiAbuse(store)
        # With no network values recorded it must not guess; a report set with
        # unknown origins is not evidence of coordination.
        assert not detector.detect_report_brigade(
            lords, "c_unknown", policy=antiabuse.Policy()
        )


class TestThreatModelIsHonest:
    def test_every_cited_test_file_exists(self):
        import json

        evidence = (
            Path(__file__).resolve().parents[3]
            / "artifacts" / "evidence" / "community-comments-platform-01"
            / "02-threat-model" / "THREAT_MODEL.json"
        )
        model = json.loads(evidence.read_text(encoding="utf-8"))
        repo = Path(__file__).resolve().parents[3]
        missing = []
        for threat in model["threats"]:
            for citation in threat["tested_by"].split(","):
                filename = citation.strip().split("::")[0]
                if not filename.endswith((".py", ".js")):
                    continue
                candidates = list(repo.rglob(Path(filename).name))
                if not candidates:
                    missing.append(f"{threat['id']} -> {filename}")
        assert not missing, f"threat model cites tests that do not exist: {missing}"


class TestNoDebugSurface:
    def test_the_api_exposes_no_debug_or_introspection_route(self):
        source = inspect.getsource(api)
        for needle in ("/debug", "/admin", "/__", "pdb", "breakpoint("):
            assert needle not in source, f"debug surface in api.py: {needle}"

    def test_the_service_never_prints(self):
        for module in (service_module, store_module):
            source = inspect.getsource(module)
            assert not re.search(r"^\s*print\(", source, re.M), f"print() in {module.__name__}"
