"""AMD.online HTML detail-page parser (sanitized fixtures / gated live).

Общий score берётся из опубликованного AMD значения, не пересчитывается
из компонентных оценок.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlparse

from factory.ratings.adapters.amd_selectors import (
    CANONICAL_ORIGIN,
    COMPONENT_AREAS,
    PARSER_VERSION,
    PERMISSION_VERSION,
    SOURCE_KEY,
    URL_ID_RE,
)


class AmdParseError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


@dataclass
class AmdDetail:
    source_key: str = SOURCE_KEY
    source_id: str = ""
    source_url: str = ""
    canonical_url: str = ""
    title_ru: str = ""
    title_original: str = ""
    aliases: list[str] = field(default_factory=list)
    year: int | None = None
    type: str = ""
    season: str | None = None
    status: str = ""
    studio: str = ""
    score: Decimal | None = None
    vote_count: int | None = None
    story_score: Decimal | None = None
    characters_score: Decimal | None = None
    art_score: Decimal | None = None
    voice_score: Decimal | None = None
    fetched_at_utc: str = ""
    http_status: int = 200
    content_digest_sha256: str = ""
    parser_version: str = PARSER_VERSION
    robots_digest: str = ""
    permission_version: str = PERMISSION_VERSION
    sitemap_lastmod_advisory: str | None = None
    quality_flags: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        def _d(v: Decimal | None):
            return None if v is None else str(v)

        return {
            "source_key": self.source_key,
            "source_id": self.source_id,
            "source_url": self.source_url,
            "canonical_url": self.canonical_url,
            "title_ru": self.title_ru,
            "title_original": self.title_original,
            "aliases": list(self.aliases),
            "year": self.year,
            "type": self.type,
            "season": self.season,
            "status": self.status,
            "studio": self.studio,
            "score": _d(self.score),
            "vote_count": self.vote_count,
            "story_score": _d(self.story_score),
            "characters_score": _d(self.characters_score),
            "art_score": _d(self.art_score),
            "voice_score": _d(self.voice_score),
            "fetched_at_utc": self.fetched_at_utc,
            "http_status": self.http_status,
            "content_digest_sha256": self.content_digest_sha256,
            "parser_version": self.parser_version,
            "robots_digest": self.robots_digest,
            "permission_version": self.permission_version,
            "sitemap_lastmod_advisory": self.sitemap_lastmod_advisory,
            "quality_flags": list(self.quality_flags),
        }


_URL_RE = re.compile(URL_ID_RE)


def parse_canonical_url(url: str) -> str:
    url = (url or "").strip()
    m = _URL_RE.match(url)
    if not m:
        raise AmdParseError("INVALID_URL", f"not amd detail canonical: {url!r}")
    parsed = urlparse(url)
    if parsed.hostname not in ("amd.online", "www.amd.online"):
        raise AmdParseError("INVALID_ORIGIN", f"host not amd.online: {parsed.hostname}")
    return f"{CANONICAL_ORIGIN}/{m.group('id')}-{m.group('slug')}.html"


def url_source_id(url: str) -> str:
    m = _URL_RE.match(parse_canonical_url(url))
    assert m
    return m.group("id")


def _dec(raw: str | None) -> Decimal | None:
    if raw is None:
        return None
    text = str(raw).strip().replace(",", ".")
    if not text:
        return None
    try:
        value = Decimal(text)
    except InvalidOperation as exc:
        raise AmdParseError("NOT_NUMERIC", f"bad decimal {raw!r}") from exc
    return value


def _vote_count(raw: str | None) -> int | None:
    if raw is None:
        return None
    digits = re.sub(r"[^\d]", "", str(raw))
    if not digits:
        return None
    return int(digits)


def _class_text(html: str, class_name: str) -> str | None:
    # class="... name ..." then capture inner text of that element (non-greedy)
    pat = rf'class="[^"]*\b{re.escape(class_name)}\b[^"]*"[^>]*>([^<]*)'
    m = re.search(pat, html, re.I)
    return m.group(1).strip() if m else None


def _h1(html: str) -> str:
    m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.I | re.S)
    if not m:
        return ""
    return re.sub(r"<[^>]+>", "", m.group(1)).strip()


def _data_id(html: str) -> str | None:
    # Prefer data-id near multirating
    m = re.search(r'class="[^"]*multirating[^"]*"[^>]*data-id="(\d+)"', html, re.I)
    if m:
        return m.group(1)
    m = re.search(r'data-id="(\d+)"[^>]*class="[^"]*multirating', html, re.I)
    if m:
        return m.group(1)
    m = re.search(r'data-id="(\d+)"', html)
    return m.group(1) if m else None


def _component(html: str, area: str) -> Decimal | None:
    m = re.search(
        rf'data-area="{re.escape(area)}"[^>]*data-rate="([\d.]+)"',
        html,
        re.I,
    )
    if m:
        return _dec(m.group(1))
    m = re.search(
        rf'data-area="{re.escape(area)}"[^>]*>\s*([\d.]+)',
        html,
        re.I,
    )
    if m:
        return _dec(m.group(1))
    return None


def validate_scores(detail: AmdDetail) -> None:
    if detail.score is not None and not (Decimal("1") <= detail.score <= Decimal("10")):
        raise AmdParseError("OUT_OF_RANGE", f"score={detail.score}")
    if detail.vote_count is not None and detail.vote_count < 0:
        raise AmdParseError("OUT_OF_RANGE", f"vote_count={detail.vote_count}")
    for name in ("story_score", "characters_score", "art_score", "voice_score"):
        val = getattr(detail, name)
        if val is not None and not (Decimal("1") <= val <= Decimal("10")):
            raise AmdParseError("OUT_OF_RANGE", f"{name}={val}")


def parse_detail_html(
    html: str,
    *,
    source_url: str,
    fetched_at_utc: str = "",
    http_status: int = 200,
    robots_digest: str = "",
) -> AmdDetail:
    canonical = parse_canonical_url(source_url)
    uid = url_source_id(canonical)
    digest = hashlib.sha256(html.encode("utf-8", errors="replace")).hexdigest()
    data_id = _data_id(html)
    if data_id is None:
        raise AmdParseError("MISSING_DATA_ID", "rating block data-id absent")
    if data_id != uid:
        raise AmdParseError(
            "ID_MISMATCH",
            f"url id {uid} != data-id {data_id}",
        )

    score_raw = _class_text(html, "multirating-itog-rateval")
    votes_raw = _class_text(html, "multirating-itog-votes")
    score = _dec(score_raw) if score_raw not in (None, "") else None
    vote_count = _vote_count(votes_raw)

    flags: list[str] = []
    if score is None:
        flags.append("SCORE_MISSING")
    if score is not None and vote_count is None:
        flags.append("VOTE_COUNT_MISSING")

    comps = {field: _component(html, area) for area, field in COMPONENT_AREAS.items()}
    detail = AmdDetail(
        source_id=uid,
        source_url=source_url,
        canonical_url=canonical,
        title_ru=_h1(html),
        title_original=(_class_text(html, "amd-sub") or "").strip(),
        score=score,
        vote_count=vote_count,
        story_score=comps["story_score"],
        characters_score=comps["characters_score"],
        art_score=comps["art_score"],
        voice_score=comps["voice_score"],
        fetched_at_utc=fetched_at_utc,
        http_status=http_status,
        content_digest_sha256=digest,
        robots_digest=robots_digest,
        quality_flags=flags,
    )
    validate_scores(detail)
    return detail
