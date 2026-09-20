"""SSR helpers: inject community read-model into title/card HTML fragments."""

from __future__ import annotations

import html
from typing import Any

from factory.community.readmodel import compact_card_badge, get_title_ratings


def render_external_badges(external: list[dict[str, Any]]) -> str:
    if not external:
        return ""
    parts = []
    for e in external:
        if e.get("score") is None:
            continue
        label = html.escape(str(e.get("label") or e.get("source")))
        score = html.escape(str(e["score"]))
        votes = e.get("vote_count")
        vote_html = ""
        if votes is not None:
            vote_html = f' <span class="cr-votes">({html.escape(str(votes))})</span>'
        parts.append(
            f'<span class="cr-badge" data-source="{html.escape(str(e.get("source")))}">'
            f"{label}: {score}{vote_html}</span>"
        )
    if not parts:
        return ""
    return '<div class="cr-external" role="group" aria-label="Внешние оценки">' + "".join(parts) + "</div>"


def render_title_block(view: dict[str, Any]) -> str:
    """Detailed title breakdown. Empty string if nothing to show (no empty shell)."""
    native = view.get("native") or {}
    brand = view.get("public_brand")
    external = view.get("external") or []
    if not external and native.get("absent") and not (brand and brand.get("score")):
        return ""

    chunks = [render_external_badges(external)]
    space = view.get("rating_space_id")
    if space == "yummy" and brand and brand.get("score") is not None:
        tip = html.escape(brand.get("tooltip") or "")
        chunks.append(
            '<div class="cr-native" role="group" aria-label="Оценка Yummy">'
            f'<span class="cr-label">{html.escape(brand["label"])}</span> '
            f'<span class="cr-score">{html.escape(str(brand["score"]))}</span> '
            f'<span class="cr-count">({int(brand.get("vote_count") or 0)})</span> '
            f'<button type="button" class="cr-info" title="{tip}" aria-label="О расчёте">i</button>'
            "</div>"
        )
    elif space == "animedia":
        if native.get("absent"):
            chunks.append(
                '<div class="cr-native" role="group" aria-label="Оценка Animedia">'
                '<span class="cr-label">Оценка Animedia</span> '
                f'<span class="cr-score cr-score--absent">{html.escape(native.get("absent_label") or "Пользовательских оценок пока нет")}</span>'
                "</div>"
            )
        else:
            chunks.append(
                '<div class="cr-native" role="group" aria-label="Оценка Animedia">'
                '<span class="cr-label">Оценка Animedia</span> '
                f'<span class="cr-score">{html.escape(str(native.get("score")))}</span> '
                f'<span class="cr-count">({int(native.get("vote_count") or 0)})</span>'
                "</div>"
            )
    body = "".join(c for c in chunks if c)
    if not body:
        return ""
    return f'<section class="cr-block" data-community-rating data-writes="0">{body}</section>'


def render_card_badge(view: dict[str, Any]) -> str:
    badge = compact_card_badge(view)
    if not badge:
        return ""
    return (
        f'<span class="cr-card-badge" data-kind="{html.escape(badge["kind"])}">'
        f'{html.escape(badge["label"])} {html.escape(str(badge["score"]))}</span>'
    )


def enrich_detail_dict(detail: dict[str, Any], *, rating_space_id: str) -> dict[str, Any]:
    """Attach community_ratings view-model; never invent AggregateRating."""
    subject = str(detail.get("id") or detail.get("canonical_title_id") or "")
    if not subject:
        return detail
    view = get_title_ratings(rating_space_id=rating_space_id, subject_id=subject)
    out = dict(detail)
    out["community_ratings"] = view
    # merge shikimori into ratings_by_source for existing renderer compatibility
    rbs = dict(out.get("ratings_by_source") or {})
    for e in view.get("external") or []:
        if e.get("source") == "shikimori" and e.get("score") is not None:
            rbs["shikimori"] = {
                "source": "shikimori",
                "value": float(e["score"].replace(",", ".")) if isinstance(e["score"], str) else e["score"],
                "scale": 10.0,
                "votes": e.get("vote_count"),
                "label": "Shikimori",
                "community_projection": True,
                "not_native_vote": True,
            }
    out["ratings_by_source"] = rbs
    out["aggregate_rating_schema_org"] = False
    return out
