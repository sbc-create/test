"""Server-side rendering of comments.

Three rules, and the module is mostly their enforcement.

**It renders nothing that is not published.** Not greyed out, not
`display:none`, not tucked into an embedded JSON island for the widget to
hydrate from. A pending comment present anywhere in the delivered bytes has
been published, whatever the CSS says, and crawlers read bytes.

**It never touches the site's SEO surface.** No robots directive, no canonical,
no sitemap entry, no hreflang, no rating JSON-LD. The comments module is a
guest on somebody else's page; a guest that rewrites the host's meta tags is a
defect with a long tail. :func:`seo_surface_untouched` states this in a form a
test can check.

**Googlebot and a person get the same bytes.** There is no user-agent branch in
this module, and :func:`render_thread` does not take one. Serving crawlers a
different rendering is cloaking, and the fact that it would be *more* content
rather than less does not change what it is.

SSR is additionally gated on publication: `flags.EffectiveFlags.ssr_enabled` is
min(configured SSR mode, publication), because rendering comments into HTML a
crawler can read *is* publishing them.
"""

from __future__ import annotations

import html
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from . import states
from .flags import EffectiveFlags

SEO_MODE_USER_INITIATED = "user_initiated"
SEO_MODE_SSR_FIRST_PAGE = "ssr_first_page"
SEO_MODE_SSR_PAGINATED = "ssr_paginated"

SEO_MODES = (SEO_MODE_USER_INITIATED, SEO_MODE_SSR_FIRST_PAGE, SEO_MODE_SSR_PAGINATED)

# Page-level surfaces this module must never emit or alter. The list is used by
# the test that scans rendered output, so adding a tag here tightens the check.
FORBIDDEN_TAGS = (
    "<meta name=\"robots\"",
    "<meta name='robots'",
    "<link rel=\"canonical\"",
    "<link rel='canonical'",
    "<link rel=\"alternate\"",
    "hreflang",
    "application/ld+json",
    "<base ",
    "<title>",
)


@dataclass(frozen=True, slots=True)
class RenderedThread:
    html: str
    rendered_count: int
    mode: str
    # True when the widget should take over and fetch the rest.
    has_more: bool


def _esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def render_comment(comment: Mapping[str, Any]) -> str:
    """One published comment.

    `body_html` arrives already escaped and rendered by `sanitize.render_html`
    and is inserted as-is; everything else on this element is escaped here.
    """
    anchor = _esc(comment.get("anchor") or f"comment-{comment['comment_id']}")
    return (
        f'<article class="cp-comment" id="{anchor}" data-cp-depth="{_esc(comment.get("depth", 0))}">'
        f'<header class="cp-comment__head">'
        f'<span class="cp-comment__author">'
        f'{_esc(comment.get("author", {}).get("subject_id", ""))}</span>'
        f'<time class="cp-comment__time" datetime="{_esc(comment.get("created_at", ""))}">'
        f'{_esc(comment.get("created_at", ""))}</time>'
        f"</header>"
        f'<div class="cp-comment__body">{comment.get("body_html", "")}</div>'
        f'<footer class="cp-comment__meta">'
        f'<span class="cp-comment__reactions">{_esc(comment.get("reaction_count", 0))}</span>'
        f"</footer>"
        f"</article>"
    )


def render_thread(
    comments: Sequence[Mapping[str, Any]],
    *,
    flags: EffectiveFlags,
    total_count: int = 0,
    has_more: bool = False,
) -> RenderedThread:
    """Render the published comments, or render nothing at all.

    Note there is no user-agent parameter and no way to pass one: the same
    bytes go to every caller.
    """
    if not flags.ssr_enabled or flags.seo_mode == SEO_MODE_USER_INITIATED:
        # The mount point only. The widget will fetch on interaction, and a
        # crawler sees an empty container, which is the honest state of a site
        # whose comments are not published.
        return RenderedThread(
            html='<div class="cp-root" data-cp-mode="user_initiated"></div>',
            rendered_count=0,
            mode=SEO_MODE_USER_INITIATED,
            has_more=bool(comments) or has_more,
        )

    publishable = [c for c in comments if states.is_public_visible(c.get("state", ""))]

    if flags.seo_mode == SEO_MODE_SSR_FIRST_PAGE:
        remaining = has_more or len(publishable) < len(comments)
    else:
        remaining = has_more

    body = "".join(render_comment(c) for c in publishable)
    return RenderedThread(
        html=(
            f'<div class="cp-root" data-cp-mode="{_esc(flags.seo_mode)}"'
            f' data-cp-total="{_esc(total_count)}">'
            f'<section class="cp-thread">{body}</section>'
            f"</div>"
        ),
        rendered_count=len(publishable),
        mode=flags.seo_mode,
        has_more=remaining,
    )


def seo_surface_untouched() -> dict[str, Any]:
    """What this module promises never to change about the host page."""
    return {
        "schema_version": "COMMENTS_SEO_V1",
        "modes": list(SEO_MODES),
        "default_mode": SEO_MODE_USER_INITIATED,
        "never_modified": [
            "robots.txt",
            "meta robots",
            "canonical link",
            "sitemap",
            "hreflang",
            "site indexability",
            "ratings JSON-LD",
        ],
        "cloaking": "none — no user-agent branch exists in this module",
        "rendered_states": sorted(states.PUBLIC_VISIBLE),
        "never_rendered_states": sorted(set(states.STATES) - states.PUBLIC_VISIBLE),
        "ssr_requires_publication": True,
    }
