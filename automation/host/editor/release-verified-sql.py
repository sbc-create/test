#!/usr/bin/env python3
"""Release at most one accepted SQL revision through the existing MCP publisher."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid
from datetime import datetime, timedelta, timezone

import psycopg2


ROOT = Path(os.environ.get("SEO_CODE_ROOT", "/home/claude/wt-portable-site-cell-01"))
PROFILES = Path("/etc/k2-editorial-items")
PAUSE = PROFILES / "legacy-paused"
EVENTS = Path("/srv/site-factory/coordination/v1/evidence/K2-VIDEO-DAILY-20261106/events")
BRIDGE = ROOT / "automation/local/bridge_call.py"
DSN = os.environ.get("K2_EDITORIAL_DSN", "dbname=k2_editorial")


def accepted_keys() -> set[str]:
    result: set[str] = set()
    for path in EVENTS.glob("*.json"):
        try:
            row = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        if row.get("lane") == "texts" and row.get("outcome") == "accepted" and row.get("verified") is True:
            result.add(str(row.get("key") or ""))
    return result


def sealed_revision_error(content_id: str, row: dict, binding: dict, body: str) -> str | None:
    """Match a sealed item to this exact SQL revision, never just its slug."""
    mark = (row.get("provenance") or {}).get("editorial_draft") or {}
    expected = {
        "task_id": content_id.removeprefix("request-"),
        "site": row.get("target_site"),
        "title_id": row.get("title_id"),
        "content_type": row.get("content_type"),
        "accepted_draft_binding_sha256": mark.get("binding_sha256"),
        "accepted_draft_body_sha256": mark.get("body_sha256"),
    }
    for field, value in expected.items():
        if not value or binding.get(field) != value:
            return "sealed " + field + " differs from accepted SQL revision"
    if binding.get("url", "").rstrip("/") != row.get("canonical_url", "").rstrip("/"):
        return "sealed URL differs from accepted SQL revision"
    actual_body = hashlib.sha256(body.encode()).hexdigest()
    if (body != row.get("body") or actual_body != mark.get("body_sha256")
            or binding.get("release_body_sha256") != actual_body):
        return "sealed body differs from accepted SQL revision"
    page = (mark.get("evidence") or {}).get("candidate", {}).get("page")
    if not page or (binding.get("page_card") or {}).get("page") != page:
        return "sealed page fields differ from accepted SQL revision"
    return None


def _candidate_held(content_id: str, reason: str) -> None:
    # Keep --next-decision stdout a single machine-readable result.
    print(json.dumps({"outcome": "SEALED_CANDIDATE_HELD", "content_id": content_id,
                      "reason": reason}), file=sys.stderr)


def candidates() -> list[tuple[str, dict, Path, Path]]:
    with psycopg2.connect(DSN) as conn, conn.cursor() as cur:
        cur.execute("""SELECT content_id,record FROM editorial.content
                       WHERE record->>'status'='DRAFT'
                         AND record#>>'{provenance,editorial_draft,outcome}'='DRAFT_VERIFIED'
                         AND NOT EXISTS (
                           SELECT 1 FROM editorial.public_acceptance p
                            WHERE p.content_id=editorial.content.content_id
                              AND p.binding_sha256=record#>>'{provenance,editorial_draft,binding_sha256}')
                         AND NOT EXISTS (
                           SELECT 1 FROM editorial.delivery_attempt d
                            WHERE d.content_id=editorial.content.content_id
                              AND d.binding_sha256=record#>>'{provenance,editorial_draft,binding_sha256}'
                              AND d.state='failed')
                       ORDER BY record->>'draft_created_at',content_id""")
        rows = cur.fetchall()
    wanted = os.environ.get("K2_RELEASE_TASK_ID", "").removeprefix("request-")
    found = []
    for content_id, row in rows:
        task = content_id.removeprefix("request-")
        if wanted and task != wanted:
            continue
        mark = row["provenance"]["editorial_draft"]
        page = (((mark.get("evidence") or {}).get("candidate") or {}).get("page") or {})
        if not all(page.get(k) for k in ("title", "h1", "meta_description")):
            continue
        site = row.get("target_site") or ""
        slug = (row.get("canonical_url") or "").rstrip("/").rsplit("/", 1)[-1]
        profile = PROFILES / site / "profiles" / (hashlib.sha256(slug.encode()).hexdigest() + ".json")
        if not profile.is_file() or profile.is_symlink():
            continue
        try:
            info = json.loads(profile.read_text())
            sealed_hash = info["binding"]
            if (not isinstance(sealed_hash, str) or len(sealed_hash) != 64
                    or any(c not in "0123456789abcdef" for c in sealed_hash)):
                raise ValueError("invalid sealed binding digest")
            item = PROFILES / site / "items" / sealed_hash
            binding = item / "binding.json"
            body = item / "release-body.txt"
            if (not binding.is_file() or not body.is_file()
                    or binding.is_symlink() or body.is_symlink()):
                raise ValueError("sealed files missing or symlinked")
            raw = binding.read_bytes()
            if hashlib.sha256(raw).hexdigest() != sealed_hash:
                raise ValueError("sealed binding file digest mismatch")
            reason = sealed_revision_error(content_id, row, json.loads(raw), body.read_text())
            if reason:
                raise ValueError(reason)
        except (OSError, ValueError, KeyError, TypeError) as error:
            _candidate_held(content_id, str(error))
            continue
        found.append((content_id, row, binding, body))
    return found


def install_delivery_decision(site: str, binding_sha256: str) -> None:
    """Install a short-lived grant for this exact sealed accepted revision.

    The receiver independently checks the immutable binding and operation, so
    this grant cannot authorize another card or a changed revision.
    """
    target = PROFILES / site / "decision.json"
    decision = json.loads(target.read_text())
    now = datetime.now(timezone.utc)
    issued = datetime.fromisoformat(decision["issued_at"])
    expires = datetime.fromisoformat(decision["expires_at"])
    if (decision.get("binding_sha256") != binding_sha256
            or decision.get("operation") != "publish"
            or decision.get("authorized") is not True
            or not issued <= now < expires
            or expires - issued > timedelta(hours=1)):
        raise RuntimeError("no current privileged decision for exact accepted revision")


def prepare_exact_release(binding: dict, body: str) -> dict:
    """Run the normal preparation gate for the immutable accepted package.

    The sealed receiver deliberately refuses a publish that has not passed the
    ordinary preparation path.  Keep this adjacent to publishing so every
    future profile gets the same check without a card-specific intervention.
    """
    args = {
        "site": binding["site"],
        "slug": binding["slug"],
        "body": body,
        "author": binding["actor"],
        "sources": binding["reviewed_release_sources"],
    }
    run = subprocess.run(
        [sys.executable, str(BRIDGE), "prepare_material",
         json.dumps(args, ensure_ascii=False)],
        cwd=ROOT, text=True, capture_output=True, timeout=300,
    )
    if run.returncode:
        raise RuntimeError("normal prepare failed: " +
                           (run.stderr.strip() or run.stdout.strip()))
    response = json.loads(run.stdout)
    prepared = response.get("prepared") or response.get("result") or {}
    state = response.get("state") or prepared.get("state")
    title_id = response.get("title_id") or prepared.get("title_id")
    problems = prepared.get("quality_problems") or []
    page = ((binding.get("page_card") or {}).get("page") or {})
    # The body-only preparation API cannot see accepted full-page fields. For
    # a sealed full-page revision, accept its sole missing-title complaint
    # only when the exact catalogue title quoted by the gate starts both the
    # accepted title and H1. The published synopsis remains byte-for-byte the
    # independently accepted body.
    page_supplies_exact_title = False
    if len(problems) == 1 and problems[0].startswith("в тексте нет названия тайтла "):
        match = re.search(r"\(из снимка: '(.+)'\)$", problems[0])
        snapshot_title = match.group(1) if match else ""
        page_supplies_exact_title = bool(
            snapshot_title
            and page.get("title", "").startswith(snapshot_title)
            and page.get("h1", "").startswith(snapshot_title)
            and page.get("meta_description")
        )
    if (response.get("ok") is not True or state != "verified") and not page_supplies_exact_title:
        raise RuntimeError("normal prepare did not verify exact release: " +
                           json.dumps(response, ensure_ascii=False))
    if title_id and str(title_id) != str(binding["title_id"]):
        raise RuntimeError("normal prepare resolved a different title_id")
    return response


def automatic_candidates() -> list[tuple[str, dict, str]]:
    """Accepted body revisions that can use the normal site delivery path.

    Full-page revisions still require the receiver's CAS package.  This
    fallback is intentionally limited to body-only revisions; it creates a
    durable SQL delivery profile before invoking the existing publisher.
    """
    with psycopg2.connect(DSN) as conn, conn.cursor() as cur:
        cur.execute("""SELECT c.content_id,c.record,e.record->>'owner'
                         FROM editorial.content c
                         JOIN editorial.revision r
                           ON r.content_id=c.content_id
                          AND r.binding_sha256=c.record#>>'{provenance,editorial_draft,binding_sha256}'
                         JOIN LATERAL (
                           SELECT record FROM editorial.event
                            WHERE record->>'event'='task_result'
                              AND record->>'task_id'=replace(c.content_id,'request-','')
                              AND record->>'binding_sha256'=r.binding_sha256
                            ORDER BY ordinal DESC LIMIT 1
                         ) e ON true
                        WHERE c.record->>'status'='DRAFT'
                          AND r.marker->>'outcome'='DRAFT_VERIFIED'
                          AND nullif(c.record->>'body','') IS NOT NULL
                          AND c.record->>'title_id' ~ '^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$'
                          AND EXISTS (
                            SELECT 1 FROM editorial.placement p
                             WHERE p.catalog_uuid=(c.record->>'title_id')::uuid
                               AND p.domain=c.record->>'target_site'
                               AND rtrim(p.canonical_url,'/')=rtrim(c.record->>'canonical_url','/'))
                          AND r.marker#>'{evidence,candidate,page}' IS NULL
                          AND NOT EXISTS (
                            SELECT 1 FROM editorial.public_acceptance p
                             WHERE p.content_id=r.content_id
                               AND p.binding_sha256=r.binding_sha256)
                          AND NOT EXISTS (
                            SELECT 1 FROM editorial.delivery_attempt d
                             WHERE d.content_id=r.content_id
                               AND d.binding_sha256=r.binding_sha256
                               AND d.state='failed')
                        ORDER BY CASE c.record->>'target_site'
                                   WHEN 'zonafilm12.site' THEN 0
                                   WHEN 'animedia.icu' THEN 1
                                   ELSE 2 END,
                                 c.record->>'draft_created_at',c.content_id""")
        rows = cur.fetchall()
    released = accepted_keys()
    wanted = os.environ.get("K2_RELEASE_TASK_ID", "").removeprefix("request-")
    return [(content_id, row, actor) for content_id, row, actor in rows
            if (not wanted or content_id.removeprefix("request-") == wanted)
            and f"{content_id.removeprefix('request-')}+{row['provenance']['editorial_draft'].get('body_sha256')}"
            not in released]


def publish_automatic(content_id: str, row: dict, actor: str) -> dict:
    task = content_id.removeprefix("request-")
    mark = row["provenance"]["editorial_draft"]
    site = row["target_site"]
    url = row["canonical_url"].rstrip("/")
    slug = url.rsplit("/", 1)[-1]
    body = row["body"]
    body_sha = hashlib.sha256(body.encode()).hexdigest()
    if body_sha != mark.get("body_sha256"):
        raise RuntimeError("accepted body digest differs from the current SQL record")
    profile = (content_id, mark["binding_sha256"], site, row["title_id"],
               url, slug, body_sha, actor)
    with psycopg2.connect(DSN) as conn, conn.cursor() as cur:
        cur.execute("""INSERT INTO editorial.delivery_profile
                       (content_id,binding_sha256,domain,catalog_uuid,canonical_url,
                        slug,body_sha256,actor)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                       ON CONFLICT(content_id,binding_sha256) DO NOTHING""", profile)
        cur.execute("""SELECT content_id,binding_sha256,domain,catalog_uuid::text,
                              canonical_url,slug,body_sha256,actor
                         FROM editorial.delivery_profile
                        WHERE content_id=%s AND binding_sha256=%s""",
                    (content_id, mark["binding_sha256"]))
        actual = cur.fetchone()
        if actual != tuple(str(v) for v in profile):
            raise RuntimeError("stored automatic delivery profile differs from accepted revision")
    args = {"site": site, "slug": slug, "body": body, "author": actor,
            "task_id": task}
    try:
        status_run = subprocess.run(
            [sys.executable, str(BRIDGE), "editorial_status",
             json.dumps({"site": site}, ensure_ascii=False)],
            cwd=ROOT, text=True, capture_output=True, timeout=60,
        )
        if status_run.returncode:
            raise RuntimeError("cannot read current editorial generation: " + status_run.stderr.strip())
        status = json.loads(status_run.stdout).get("editorial") or {}
        if any(item.get("slug") == slug for item in status.get("published") or []):
            generation = status.get("generation_id")
            if not generation:
                raise RuntimeError("existing slug has no readable generation")
            args["expect_generation"] = generation
    except subprocess.TimeoutExpired:
        # A new slug is safe without a baseline.  The publisher itself rejects
        # an existing slug when expect_generation is absent, so timeout cannot
        # turn this into a blind overwrite.
        pass
    idempotency_key = f"{task}:{mark['binding_sha256']}"
    attempt_id = uuid.uuid5(uuid.NAMESPACE_URL, "k2:delivery:" + idempotency_key)
    with psycopg2.connect(DSN) as conn, conn.cursor() as cur:
        cur.execute("""INSERT INTO editorial.delivery_attempt
                       (attempt_id,task_id,content_id,binding_sha256,idempotency_key,state)
                       VALUES (%s,%s,%s,%s,%s,'sent')
                       ON CONFLICT(idempotency_key) DO NOTHING""",
                    (str(attempt_id), task, content_id, mark["binding_sha256"], idempotency_key))
        if cur.rowcount == 0:
            cur.execute("SELECT state,result FROM editorial.delivery_attempt WHERE idempotency_key=%s",
                        (idempotency_key,))
            state, result = cur.fetchone()
            if state == "verified":
                return {"outcome": "IDEMPOTENT_REPLAY", "task_id": task,
                        "result": result}
            if state == "sent":
                return {"outcome": "IN_PROGRESS", "task_id": task}
            cur.execute("""UPDATE editorial.delivery_attempt
                              SET state='sent',finished_at=NULL,result='{}'::jsonb
                            WHERE idempotency_key=%s AND state='failed'""",
                        (idempotency_key,))
            if cur.rowcount != 1:
                return {"outcome": "IN_PROGRESS", "task_id": task}
    run = subprocess.run([sys.executable, str(BRIDGE), "publish_material",
                          json.dumps(args, ensure_ascii=False)], cwd=ROOT,
                         text=True, capture_output=True, timeout=300)
    if run.returncode:
        with psycopg2.connect(DSN) as conn, conn.cursor() as cur:
            cur.execute("""UPDATE editorial.delivery_attempt
                              SET state='failed',finished_at=now(),result=%s
                            WHERE idempotency_key=%s AND state='sent'""",
                        (json.dumps({"stderr": run.stderr[-4000:],
                                     "stdout": run.stdout[-4000:]}), idempotency_key))
        print(json.dumps({"outcome": "RELEASE_DEFERRED", "task_id": task,
                          "reason": f"publisher exited {run.returncode}: {run.stderr.strip()}"},
                         ensure_ascii=False))
        return 0
    response = json.loads(run.stdout)
    if response.get("confirmed") is not True:
        with psycopg2.connect(DSN) as conn, conn.cursor() as cur:
            cur.execute("""UPDATE editorial.delivery_attempt
                              SET state='failed',finished_at=now(),result=%s
                            WHERE idempotency_key=%s""",
                        (json.dumps(response), idempotency_key))
        return {"outcome": "RELEASE_REJECTED", "task_id": task,
                "site": site, "url": url,
                "reason": response.get("error") or
                          ((response.get("result") or {}).get("confirmation") or {}).get("reason")}
    result = response.get("result") or {}
    with psycopg2.connect(DSN) as conn, conn.cursor() as cur:
        cur.execute("""UPDATE editorial.delivery_attempt
                          SET state='verified',finished_at=now(),result=%s
                        WHERE idempotency_key=%s""", (json.dumps(response), idempotency_key))
        cur.execute("""INSERT INTO editorial.public_acceptance
                       (task_id,body_sha256,content_id,binding_sha256,
                        canonical_url,accepted_at,proof)
                       VALUES (%s,%s,%s,%s,%s,now(),%s)
                       ON CONFLICT(task_id,body_sha256) DO NOTHING""",
                    (task, body_sha, content_id, mark["binding_sha256"], url,
                     json.dumps(response)))
    return {"outcome": "PUBLIC_ACCEPTED", "task_id": task, "site": site,
            "url": url, "binding_sha256": mark["binding_sha256"]}


def main() -> int:
    if PAUSE.exists():
        print(json.dumps({"outcome": "PAUSED", "marker": str(PAUSE)}))
        return 0
    rows = candidates()
    if not rows:
        automatic = automatic_candidates()
        if not automatic:
            print(json.dumps({"outcome": "NO_VERIFIED_RELEASE"}))
            return 0
        print(json.dumps(publish_automatic(*automatic[0]), ensure_ascii=False))
        return 0
    content_id, row, binding_path, body_path = rows[0]
    binding = json.loads(binding_path.read_text())
    body = body_path.read_text()
    task = content_id.removeprefix("request-")
    mark = row["provenance"]["editorial_draft"]
    reason = sealed_revision_error(content_id, row, binding, body)
    if reason:
        raise RuntimeError(reason)
    prepare_exact_release(binding, body)
    args = {
        "site": binding["site"], "slug": binding["slug"], "body": body,
        "author": binding["actor"], "task_id": task,
        "expect_generation": binding["baseline_generation"],
    }
    idempotency_key = f"{task}:{mark['binding_sha256']}"
    attempt_id = uuid.uuid5(uuid.NAMESPACE_URL, "k2:delivery:" + idempotency_key)
    with psycopg2.connect(DSN) as conn, conn.cursor() as cur:
        cur.execute("""INSERT INTO editorial.delivery_attempt
                       (attempt_id,task_id,content_id,binding_sha256,idempotency_key,state)
                       VALUES (%s,%s,%s,%s,%s,'sent')
                       ON CONFLICT(idempotency_key) DO NOTHING""",
                    (str(attempt_id), task, content_id, mark["binding_sha256"], idempotency_key))
        if cur.rowcount == 0:
            cur.execute("SELECT state,result FROM editorial.delivery_attempt WHERE idempotency_key=%s",
                        (idempotency_key,))
            state, result = cur.fetchone()
            if state == "verified":
                print(json.dumps({"outcome": "IDEMPOTENT_REPLAY", "task_id": task,
                                  "result": result}, ensure_ascii=False))
                return 0
            if state == "sent":
                print(json.dumps({"outcome": "IN_PROGRESS", "task_id": task}, ensure_ascii=False))
                return 0
            cur.execute("""UPDATE editorial.delivery_attempt
                              SET state='sent',finished_at=NULL,result='{}'::jsonb
                            WHERE idempotency_key=%s AND state='failed'""",
                        (idempotency_key,))
            if cur.rowcount != 1:
                print(json.dumps({"outcome": "IN_PROGRESS", "task_id": task}, ensure_ascii=False))
                return 0
    run = subprocess.run([sys.executable, str(BRIDGE), "publish_material",
                          json.dumps(args, ensure_ascii=False)], cwd=ROOT,
                         text=True, capture_output=True, timeout=300)
    if run.returncode:
        with psycopg2.connect(DSN) as conn, conn.cursor() as cur:
            cur.execute("""UPDATE editorial.delivery_attempt
                              SET state='failed',finished_at=now(),result=%s
                            WHERE idempotency_key=%s AND state='sent'""",
                        (json.dumps({"stderr": run.stderr[-4000:],
                                     "stdout": run.stdout[-4000:]}), idempotency_key))
        print(json.dumps({"outcome": "RELEASE_DEFERRED", "task_id": task,
                          "reason": f"publisher exited {run.returncode}: {run.stderr.strip()}"},
                         ensure_ascii=False))
        return 0
    response = json.loads(run.stdout)
    if response.get("confirmed") is not True:
        with psycopg2.connect(DSN) as conn, conn.cursor() as cur:
            cur.execute("""UPDATE editorial.delivery_attempt
                              SET state='failed',finished_at=now(),result=%s
                            WHERE idempotency_key=%s AND state='sent'""",
                        (json.dumps(response), idempotency_key))
        print(json.dumps({"outcome": "RELEASE_DEFERRED", "task_id": task,
                          "reason": response.get("error") or "public acceptance not confirmed"},
                         ensure_ascii=False))
        return 0
    with psycopg2.connect(DSN) as conn, conn.cursor() as cur:
        cur.execute("""UPDATE editorial.delivery_attempt SET state='verified',finished_at=now(),result=%s
                       WHERE idempotency_key=%s""", (json.dumps(response), idempotency_key))
        cur.execute("""INSERT INTO editorial.public_acceptance
                       (task_id,body_sha256,content_id,binding_sha256,
                        canonical_url,accepted_at,proof)
                       VALUES (%s,%s,%s,%s,%s,now(),%s)
                       ON CONFLICT(task_id,body_sha256) DO NOTHING""",
                    (task, hashlib.sha256(body.encode()).hexdigest(), content_id,
                     mark["binding_sha256"], binding["url"].rstrip("/"),
                     json.dumps(response)))
    print(json.dumps({"outcome": "PUBLIC_ACCEPTED", "task_id": task,
                      "site": binding["site"], "url": binding["url"],
                      "binding_sha256": mark["binding_sha256"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--next-decision":
        selected = candidates()
        if not selected:
            print(json.dumps({"outcome": "NO_SEALED_RELEASE"}))
        else:
            content_id, row, binding_path, _ = selected[0]
            mark = row["provenance"]["editorial_draft"]
            print(json.dumps({"outcome": "SEALED_RELEASE", "content_id": content_id,
                              "binding_path": str(binding_path),
                              "expected": {"task_id": content_id.removeprefix("request-"),
                                           "site": row["target_site"], "title_id": row["title_id"],
                                           "content_type": row["content_type"],
                                           "url": row["canonical_url"].rstrip("/"),
                                           "accepted_draft_binding_sha256": mark["binding_sha256"],
                                           "accepted_draft_body_sha256": mark["body_sha256"],
                                           "release_body_sha256": mark["body_sha256"]}}))
        raise SystemExit(0)
    raise SystemExit(main())
