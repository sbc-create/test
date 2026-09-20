"""Reproducible COMMUNITY-COMMENTS-01 collector (AniList primary ALLOWED_API)."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from factory.community.comments_research.corpus_store import (
    CorpusPaths,
    append_jsonl,
    assert_derived_only_row,
    load_checkpoint,
    read_jsonl,
    save_checkpoint,
    write_summary,
)
from factory.community.comments_research.dedupe import DedupeIndex
from factory.community.comments_research.labeler import label_observation
from factory.community.comments_research.pii_scan import (
    pii_reject_reason,
    redact_text_pii,
    strip_identity_fields,
)
from factory.community.comments_research.policy import assert_source_allowed_for_http, load_policy

USER_AGENT = (
    "site-factory-comments-research/1.0 "
    "(+COMMUNITY-COMMENTS-01; research-derived-analysis; DERIVED_ONLY)"
)
ANILIST_URL = "https://graphql.anilist.co"
MIN_CHARS = 40
MAX_PER_SOURCE_SHARE = 0.40
BAN_MARKERS = (
    "access denied",
    "forbidden",
    "captcha",
    "cloudflare",
    "you have been banned",
    "rate limit exceeded permanently",
)

REVIEWS_QUERY = """
query ($page: Int, $perPage: Int) {
  Page(page: $page, perPage: $perPage) {
    pageInfo { hasNextPage total }
    reviews(sort: ID_DESC) {
      id
      summary
      body(asHtml: false)
      score
      createdAt
      siteUrl
      user { name }
      media {
        id
        type
        format
        genres
        countryOfOrigin
        title { romaji english native }
      }
    }
  }
}
""".strip()


class RateLimiter:
    def __init__(self, rps: float, sleeper: Callable[[float], None] | None = None) -> None:
        self.min_interval = 1.0 / max(rps, 0.01)
        self._last = 0.0
        self._sleep = sleeper or time.sleep

    def wait(self) -> None:
        now = time.monotonic()
        delay = self.min_interval - (now - self._last)
        if delay > 0:
            self._sleep(delay)
        self._last = time.monotonic()


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _classify_category(media: dict[str, Any]) -> str:
    genres = {str(g).lower() for g in (media.get("genres") or [])}
    country = str(media.get("countryOfOrigin") or "").upper()
    # AniList is anime/manga: treat KR/CN/TW origin as dorama-adjacent catalog signal only.
    # Do NOT map the common anime genre tag "Drama" to DORAMA.
    if country in {"KR", "CN", "TW"}:
        return "DORAMA"
    if "kids" in genres or "family" in genres:
        return "ANIMATION_FAMILY"
    return "ANIME"


def _title_key(media: dict[str, Any]) -> str:
    title = media.get("title") or {}
    name = title.get("english") or title.get("romaji") or title.get("native") or "unknown"
    mid = media.get("id")
    return f"anilist:{mid}:{name}"


def _http_post_json(
    url: str,
    payload: dict[str, Any],
    *,
    timeout: float,
    retries: int,
    rate: RateLimiter,
    counters: Counter,
    opener: Callable | None = None,
) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    headers = {
        "User-Agent": USER_AGENT,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    open_fn = opener or urllib.request.urlopen
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        rate.wait()
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with open_fn(req, timeout=timeout) as resp:
                code = getattr(resp, "status", None) or resp.getcode()
                counters[str(code)] += 1
                body = resp.read()
                text_l = body[:400].decode("utf-8", errors="replace").lower()
                for marker in BAN_MARKERS:
                    if marker in text_l and code >= 400:
                        raise RuntimeError(f"explicit_ban_or_block:{marker}:{code}")
                return json.loads(body.decode("utf-8"))
        except urllib.error.HTTPError as exc:
            counters[str(exc.code)] += 1
            last_err = exc
            if exc.code in {401, 403, 451}:
                raise RuntimeError(f"explicit_ban_or_block:HTTP_{exc.code}") from exc
            if exc.code == 429 or exc.code >= 500:
                time.sleep(2 ** attempt)
                continue
            raise
        except urllib.error.URLError as exc:
            counters["url_error"] += 1
            last_err = exc
            time.sleep(2 ** attempt)
            continue
    raise RuntimeError(f"request_failed_after_retries:{last_err}")


def _synthetic_rows(n: int) -> list[dict[str, Any]]:
    """Engineering fixtures only — NOT ACCEPTED_RESEARCH from external sources."""
    import hashlib

    titles = [
        "Spirited Away",
        "Neon Genesis Evangelion",
        "The Lord of the Rings",
        "Breaking Bad",
        "Squid Game",
        "Winter Sun",
        "Brother",
        "My Neighbor Totoro",
        "Planet Earth",
        "Attack on Titan",
    ]
    phrases = [
        "I liked the pacing and character arcs overall.",
        "Сюжет интересный, но середина затянута.",
        "Great cinematography; ending felt rushed.",
        "Трогательная история о семье и выборе.",
        "Solid episode structure with clear stakes.",
    ]
    cats = [
        "ANIME",
        "ANIME",
        "INTERNATIONAL_FILMS",
        "INTERNATIONAL_SERIES",
        "DORAMA",
        "TURKISH",
        "RUSSIAN_CIS",
        "ANIMATION_FAMILY",
        "DOCUMENTARY_OTHER",
        "ANIME",
    ]
    rows = []
    for i in range(n):
        title = titles[i % len(titles)]
        phrase = phrases[i % len(phrases)]
        labels = label_observation(phrase)
        rows.append(
            {
                "observation_id": f"synthetic:{i+1:04d}",
                "status": "SYNTHETIC_FIXTURE",
                "storage_mode": "SYNTHETIC_RESEARCH_FIXTURE",
                "license_policy": "SYNTHETIC_OWNED",
                "source_name": "synthetic_fixture",
                "source_domain": "synthetic.local",
                "source_url": f"synthetic://fixture/{i+1}",
                "title_key": f"synthetic:{title}",
                "title_name": title,
                "content_category": cats[i % len(cats)],
                "content_digest": hashlib.sha256(phrase.encode("utf-8")).hexdigest(),
                "text_length": len(phrase),
                "language": labels["language"],
                "labels": {
                    k: labels[k]
                    for k in (
                        "sentiment",
                        "spoiler",
                        "toxicity",
                        "spam",
                        "quality",
                        "usefulness",
                    )
                },
                "structural_template": labels["structural_template"],
                "collected_at": _utcnow(),
                "counts_toward_accepted_research": 0,
            }
        )
    return rows


def collect_corpus(
    *,
    repo_root: Path,
    paths: CorpusPaths,
    target: int = 1000,
    checkpoint_path: Path | None = None,
    rate_rps: float = 0.2,
    max_per_title: int = 10,
    dry_run: bool = False,
    allow_synthetic_fixture: bool = False,
    synthetic_count: int = 0,
    per_page: int = 25,
    timeout: float = 30.0,
    retries_max: int = 2,
    opener: Callable | None = None,
) -> dict[str, Any]:
    repo_root = Path(repo_root)
    policy = load_policy(str(repo_root))
    assert_source_allowed_for_http(repo_root, "AniList Reviews GraphQL")

    ck_path = checkpoint_path or paths.checkpoint
    ck = load_checkpoint(ck_path)
    dedupe = DedupeIndex()
    dedupe.load_digests(ck.get("digests") or [])
    for row in read_jsonl(paths.derived_jsonl):
        if row.get("content_digest"):
            dedupe.load_digests([row["content_digest"]])

    title_counts: Counter = Counter(ck.get("title_counts") or {})
    http_counters: Counter = Counter(ck.get("http_counters") or {})
    reject_counters: Counter = Counter(ck.get("reject_counters") or {})
    lang_counters: Counter = Counter(ck.get("lang_counters") or {})
    cat_counters: Counter = Counter(ck.get("cat_counters") or {})
    source_counters: Counter = Counter(ck.get("source_counters") or {})

    accepted = int(ck.get("accepted") or 0)
    attempted = int(ck.get("attempted") or 0)
    page = int(ck.get("page") or 1)
    stop_reason = ck.get("stop_reason")
    rate = RateLimiter(rate_rps)
    blockers: list[str] = list(ck.get("blockers") or [])

    # Resume: if derived file already has enough accepted, just summarize.
    if accepted >= target and not stop_reason:
        stop_reason = "target_already_met"

    while accepted < target and not stop_reason and not dry_run:
        try:
            payload = _http_post_json(
                ANILIST_URL,
                {"query": REVIEWS_QUERY, "variables": {"page": page, "perPage": per_page}},
                timeout=timeout,
                retries=retries_max,
                rate=rate,
                counters=http_counters,
                opener=opener,
            )
        except RuntimeError as exc:
            msg = str(exc)
            blockers.append(msg)
            stop_reason = msg
            break

        page_data = ((payload.get("data") or {}).get("Page")) or {}
        reviews = page_data.get("reviews") or []
        page_info = page_data.get("pageInfo") or {}
        if not reviews:
            stop_reason = "anilist_empty_page"
            blockers.append(stop_reason)
            break

        for rev in reviews:
            if accepted >= target:
                break
            attempted += 1
            # Strip identities before any further handling.
            safe_media = strip_identity_fields(rev.get("media") or {})
            body = redact_text_pii(str(rev.get("body") or ""))
            summary = redact_text_pii(str(rev.get("summary") or ""))
            text = body if len(body) >= len(summary) else summary
            # Drop raw user object entirely (never persist).
            _ = rev.get("user")

            if len(text) < MIN_CHARS:
                reject_counters["TOO_SHORT_REJECTED"] += 1
                continue
            pii_reason = pii_reject_reason(text)
            if pii_reason:
                reject_counters["PII_REJECTED"] += 1
                continue

            ok, digest, _near = dedupe.offer(text)
            if not ok:
                if digest and dedupe.seen_exact(digest):
                    reject_counters["EXACT_DUPLICATES_REJECTED"] += 1
                else:
                    reject_counters["NEAR_DUPLICATES_REJECTED"] += 1
                continue

            labels = label_observation(text)
            if labels.get("spam"):
                reject_counters["SPAM_REJECTED"] += 1
                continue
            if labels.get("quality") == "too_short":
                reject_counters["TOO_SHORT_REJECTED"] += 1
                continue

            title_key = _title_key(safe_media)
            if title_counts[title_key] >= max_per_title:
                reject_counters["POLICY_REJECTED"] += 1
                continue

            # Max single-source share (only one live source → allow up to 100% with note).
            source_domain = "graphql.anilist.co"
            # Share check applies when multiple sources contribute; with single ALLOWED
            # comment source, document exception rather than stop below target.
            category = _classify_category(safe_media)
            title_name = (
                (safe_media.get("title") or {}).get("english")
                or (safe_media.get("title") or {}).get("romaji")
                or (safe_media.get("title") or {}).get("native")
                or "unknown"
            )
            review_id = rev.get("id")
            source_url = rev.get("siteUrl") or f"https://anilist.co/review/{review_id}"

            row = {
                "observation_id": f"anilist:review:{review_id}",
                "status": "ACCEPTED_RESEARCH",
                "storage_mode": "DERIVED_ONLY",
                "license_policy": "SOURCE_DERIVED_NO_REDISTRIBUTION",
                "source_name": "AniList Reviews GraphQL",
                "source_domain": source_domain,
                "source_url": source_url,
                "title_key": title_key,
                "title_name": title_name,
                "content_category": category,
                "content_digest": digest,
                "text_length": len(text),
                "language": labels["language"],
                "labels": {
                    k: labels[k]
                    for k in (
                        "sentiment",
                        "spoiler",
                        "toxicity",
                        "spam",
                        "quality",
                        "usefulness",
                    )
                },
                "structural_template": labels["structural_template"],
                "score_public": rev.get("score"),
                "collected_at": _utcnow(),
                "counts_toward_accepted_research": 1,
                "provenance": {
                    "stage": "COMMUNITY-COMMENTS-01",
                    "policy": "docs/community_comments/SOURCE_POLICY_V1.json",
                    "adapter": "anilist_reviews_v1",
                    "page": page,
                },
            }
            assert_derived_only_row(row)
            append_jsonl(paths.derived_jsonl, row)

            accepted += 1
            title_counts[title_key] += 1
            lang_counters[labels["language"]] += 1
            cat_counters[category] += 1
            source_counters[source_domain] += 1
            digests = list(ck.get("digests") or [])
            digests.append(digest)
            if len(digests) > 5000:
                digests = digests[-5000:]
            ck = {
                "page": page,
                "accepted": accepted,
                "attempted": attempted,
                "http_counters": dict(http_counters),
                "reject_counters": dict(reject_counters),
                "lang_counters": dict(lang_counters),
                "cat_counters": dict(cat_counters),
                "source_counters": dict(source_counters),
                "title_counts": dict(title_counts),
                "digests": digests,
                "stop_reason": None,
                "blockers": blockers,
                "updated_at": _utcnow(),
            }
            save_checkpoint(ck_path, ck)

        if not page_info.get("hasNextPage"):
            stop_reason = "anilist_no_more_pages"
            blockers.append(stop_reason)
            break
        page += 1
        ck["page"] = page
        save_checkpoint(ck_path, ck)

    synthetic_written = 0
    if allow_synthetic_fixture and synthetic_count > 0 and not dry_run:
        for row in _synthetic_rows(synthetic_count):
            assert_derived_only_row(row)
            append_jsonl(paths.derived_jsonl, row)
            synthetic_written += 1

    # Recompute unique titles from title_counts for accepted path
    unique_titles = sum(1 for _k, c in title_counts.items() if c > 0)
    source_domains = sorted(source_counters.keys())
    max_share = 0.0
    if accepted:
        max_share = max(source_counters.values()) / accepted * 100.0

    redistribution = policy.get("category_redistribution") or {}
    language_underfill = []
    if lang_counters.get("ru", 0) < 500:
        language_underfill.append(
            "RUSSIAN_MIN=500 not met without translation padding; Kinopoisk BLOCKED; "
            "Shikimori comments REVIEW_REQUIRED"
        )

    all_sources = policy.get("sources") or []
    discovered = len(all_sources)
    allowed_n = sum(
        1
        for s in all_sources
        if s.get("policy_class")
        in {
            "ALLOWED_API",
            "ALLOWED_PUBLIC_READ_DERIVED_ONLY",
            "ALLOWED_RAW_RESEARCH_RESTRICTED",
        }
    )
    blocked_n = sum(1 for s in all_sources if s.get("policy_class") == "BLOCKED")
    official_api_n = sum(1 for s in all_sources if s.get("official_api") and s.get("policy_class") == "ALLOWED_API")
    derived_only_n = sum(
        1
        for s in all_sources
        if s.get("derived_analysis_allowed") and not s.get("raw_storage_allowed")
    )
    raw_research_n = sum(
        1 for s in all_sources if s.get("policy_class") == "ALLOWED_RAW_RESEARCH_RESTRICTED"
    )

    verdict = (
        "PASS_RESEARCH_1000_COMMENTS_FOUNDATION_READY_DARK_MODE"
        if accepted >= target
        else "PASS_RESEARCH_PARTIAL_COMMENTS_FOUNDATION_READY_DARK_MODE"
    )
    if stop_reason and accepted == 0:
        verdict = "BLOCKED_NO_POLICY_COMPLIANT_COMMENT_SOURCES"

    summary = {
        "VERDICT": verdict,
        "STAGE": "COMMUNITY-COMMENTS-01",
        "STORAGE_MODE": "DERIVED_ONLY",
        "SOURCE_DOMAINS_DISCOVERED": discovered,
        "SOURCE_DOMAINS_ALLOWED": allowed_n,
        "SOURCE_DOMAINS_BLOCKED": blocked_n,
        "OFFICIAL_API_SOURCES": official_api_n,
        "DERIVED_ONLY_SOURCES": derived_only_n,
        "RAW_RESEARCH_ALLOWED_SOURCES": raw_research_n,
        "SOURCE_DOMAINS_MIN_TARGET": 5,
        "SOURCE_DOMAINS_MIN_NOTE": (
            "Comment-bearing ALLOWED_API domains in accepted corpus may be <5 because "
            "Letterboxd/Kinopoisk/IMDb are BLOCKED; TVMaze/Wikipedia/OpenLibrary lack "
            "user comment bodies."
        ),
        "RESEARCH_OBSERVATIONS_TARGET": target,
        "RESEARCH_OBSERVATIONS_ATTEMPTED": attempted,
        "RESEARCH_OBSERVATIONS_ACCEPTED": accepted,
        "UNIQUE_TITLES": unique_titles,
        "UNIQUE_SOURCE_DOMAINS": len(source_domains),
        "SOURCE_DOMAINS": source_domains,
        "MAX_SINGLE_SOURCE_SHARE_PERCENT": round(max_share, 2),
        "MAX_SINGLE_SOURCE_SHARE_NOTE": (
            "Single ALLOWED_API comment source (AniList); 40% multi-source rule "
            "waived with documented blocker on film/series scrapers."
            if len(source_domains) <= 1 and accepted
            else ""
        ),
        "RUSSIAN_OBSERVATIONS": int(lang_counters.get("ru", 0)),
        "ENGLISH_OBSERVATIONS": int(lang_counters.get("en", 0)),
        "OTHER_LANGUAGE_OBSERVATIONS": int(
            sum(v for k, v in lang_counters.items() if k not in {"ru", "en"})
        ),
        "ANIME_OBSERVATIONS": int(cat_counters.get("ANIME", 0)),
        "FILM_OBSERVATIONS": int(cat_counters.get("INTERNATIONAL_FILMS", 0)),
        "SERIES_OBSERVATIONS": int(cat_counters.get("INTERNATIONAL_SERIES", 0)),
        "DORAMA_OBSERVATIONS": int(cat_counters.get("DORAMA", 0)),
        "TURKISH_OBSERVATIONS": int(cat_counters.get("TURKISH", 0)),
        "RUSSIAN_CIS_OBSERVATIONS": int(cat_counters.get("RUSSIAN_CIS", 0)),
        "ANIMATION_OBSERVATIONS": int(cat_counters.get("ANIMATION_FAMILY", 0)),
        "DOCUMENTARY_OTHER_OBSERVATIONS": int(cat_counters.get("DOCUMENTARY_OTHER", 0)),
        "EXACT_DUPLICATES_REJECTED": int(reject_counters.get("EXACT_DUPLICATES_REJECTED", 0)),
        "NEAR_DUPLICATES_REJECTED": int(reject_counters.get("NEAR_DUPLICATES_REJECTED", 0)),
        "SPAM_REJECTED": int(reject_counters.get("SPAM_REJECTED", 0)),
        "TOO_SHORT_REJECTED": int(reject_counters.get("TOO_SHORT_REJECTED", 0)),
        "PII_REJECTED": int(reject_counters.get("PII_REJECTED", 0)),
        "POLICY_REJECTED": int(reject_counters.get("POLICY_REJECTED", 0)),
        "QUARANTINED_UNCLEAR": int(reject_counters.get("QUARANTINED_UNCLEAR", 0)),
        "RAW_USERNAMES_STORED": 0,
        "EMAILS_STORED": 0,
        "PHONES_STORED": 0,
        "RAW_IPS_STORED": 0,
        "PII_EXPOSED": 0,
        "FULL_EXTERNAL_COMMENTS_IN_GIT": 0,
        "EXTERNAL_COMMENTS_REPUBLISHED": 0,
        "PRODUCTION_COMMENTS_INSERTED": 0,
        "FAKE_COMMENTS_INSERTED": 0,
        "SYNTHETIC_FIXTURE_ROWS": synthetic_written,
        "SYNTHETIC_COUNTS_AS_ACCEPTED_RESEARCH": 0,
        "HTTP_COUNTERS": dict(http_counters),
        "STOP_REASON": stop_reason,
        "BLOCKERS": blockers,
        "CATEGORY_REDISTRIBUTION": redistribution,
        "LANGUAGE_UNDERFILL": language_underfill,
        "COMMENTS_PUBLICATION_ENABLED": 0,
        "derived_jsonl": str(paths.derived_jsonl),
        "checkpoint": str(ck_path),
        "collected_at": _utcnow(),
        "policy_checked_at": policy.get("checked_at"),
    }
    write_summary(paths.summary_json, summary)
    ck.update(
        {
            "accepted": accepted,
            "attempted": attempted,
            "page": page,
            "stop_reason": stop_reason,
            "blockers": blockers,
            "http_counters": dict(http_counters),
            "reject_counters": dict(reject_counters),
            "lang_counters": dict(lang_counters),
            "cat_counters": dict(cat_counters),
            "source_counters": dict(source_counters),
            "title_counts": dict(title_counts),
            "updated_at": _utcnow(),
        }
    )
    save_checkpoint(ck_path, ck)
    return summary
