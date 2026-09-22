"""XSS corpus.

Every payload below must come out of :func:`render_html` inert. "Inert" is
asserted structurally, not by eyeballing: no script element, no event handler
attribute, no dangerous URL scheme, and no tag that is not on the allowlist.
"""

from __future__ import annotations

import re

import pytest

from factory.comments_platform.errors import PolicyViolation, ValidationFailed
from factory.comments_platform.sanitize import (
    LINK_REL,
    render_html,
    safe_href,
    sanitize_body,
    to_plain_preview,
)

from .htmlcheck import assert_no_scripting, attribute_values
from .htmlcheck import inspect as inspect_html

XSS_CORPUS = [
    "<script>alert(1)</script>",
    "<SCRIPT SRC=//evil.test/x.js></SCRIPT>",
    "<img src=x onerror=alert(1)>",
    "<svg/onload=alert(1)>",
    "<body onload=alert(1)>",
    "<iframe src='javascript:alert(1)'></iframe>",
    "<a href=\"javascript:alert(1)\">click</a>",
    "[click](javascript:alert(1))",
    "[click](JaVaScRiPt:alert(1))",
    "[click](data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==)",
    "[click](vbscript:msgbox(1))",
    "[click](  javascript:alert(1)  )",
    "<a href=\"x\" onmouseover=\"alert(1)\">y</a>",
    "\"><script>alert(1)</script>",
    "'><img src=x onerror=alert(1)>",
    "</textarea><script>alert(1)</script>",
    "<style>body{background:url('javascript:alert(1)')}</style>",
    "<math><mtext><script>alert(1)</script></mtext></math>",
    "<object data='javascript:alert(1)'>",
    "<embed src='javascript:alert(1)'>",
    "<form action='javascript:alert(1)'><input>",
    "<base href='javascript:'>",
    "<meta http-equiv='refresh' content='0;url=javascript:alert(1)'>",
    "<details open ontoggle=alert(1)>",
    "<marquee onstart=alert(1)>",
    "&lt;script&gt;alert(1)&lt;/script&gt;",
    "&#60;script&#62;alert(1)&#60;/script&#62;",
    "&#x3c;script&#x3e;alert(1)",
    "<scr<script>ipt>alert(1)</scr</script>ipt>",
    "<<SCRIPT>alert(1);//<</SCRIPT>",
    "<img src=`x` onerror=alert(1)>",
    "<a href='&#106;avascript:alert(1)'>x</a>",
    "javascript:alert(1)",
    "  javascript:alert(1)",
    "java\tscript:alert(1)",
    "<script>alert(1)</script>",
    "<div style=\"width:expression(alert(1))\">x</div>",
    "<link rel=stylesheet href='javascript:alert(1)'>",
    "<input autofocus onfocus=alert(1)>",
    "<template><script>alert(1)</script></template>",
    "<noscript><p title=\"</noscript><img src=x onerror=alert(1)>\">",
]

# Tags and attributes the renderer is permitted to emit. Anything else that a
# real parser can see in the output is a leak.
ALLOWED_TAGS = {"strong", "em", "code", "a", "br", "span"}
ALLOWED_ATTRS = {
    "href", "rel", "target", "class", "tabindex", "role", "aria-expanded", "data-cp-spoiler",
}
_DANGEROUS_SCHEME_RE = re.compile(r"(?:javascript|data|vbscript)\s*:", re.IGNORECASE)


def assert_inert(rendered: str) -> None:
    """Judged by a parser, never by a substring search.

    A substring search fails in both directions here: `onerror=` inside escaped
    text is harmless, and an attribute name hidden inside a quoted value looks
    like an attribute to a regex. `htmlcheck.inspect` reports what a browser
    would actually parse, which is the only question that matters.
    """
    assert_no_scripting(rendered, allowed_tags=ALLOWED_TAGS)

    parsed = inspect_html(rendered)
    unexpected = {
        f"{tag}[{attr}]" for tag, attr in parsed.attributes if attr not in ALLOWED_ATTRS
    }
    assert not unexpected, f"unexpected attributes {sorted(unexpected)} in {rendered!r}"

    for href in attribute_values(rendered, "href"):
        assert not _DANGEROUS_SCHEME_RE.match(href.strip()), f"dangerous href: {href!r}"


class TestXssCorpus:
    @pytest.mark.parametrize("payload", XSS_CORPUS)
    def test_payload_renders_inert(self, payload):
        assert_inert(render_html(payload))

    @pytest.mark.parametrize("payload", XSS_CORPUS)
    def test_payload_renders_inert_in_plain_mode(self, payload):
        assert_inert(render_html(payload, allow_markdown=False))

    @pytest.mark.parametrize("payload", XSS_CORPUS)
    def test_payload_survives_the_full_pipeline_inert(self, payload):
        try:
            body = sanitize_body(payload, max_length=4000, max_links=5)
        except (ValidationFailed, PolicyViolation):
            return  # refusing the input outright is a valid answer
        assert_inert(body.rendered_html)

    def test_no_raw_angle_bracket_survives(self):
        out = render_html("a < b > c")
        assert "&lt;" in out and "&gt;" in out


class TestAllowlistMarkdown:
    def test_bold_italic_code(self):
        out = render_html("**b** *i* `c`")
        assert "<strong>b</strong>" in out
        assert "<em>i</em>" in out
        assert "<code>c</code>" in out

    def test_markdown_inside_code_is_not_applied(self):
        out = render_html("`**not bold**`")
        assert "<strong>" not in out

    def test_safe_link_gets_ugc_nofollow(self):
        out = render_html("[site](https://example.test/x)")
        assert f'rel="{LINK_REL}"' in out
        assert "ugc" in LINK_REL and "nofollow" in LINK_REL
        assert 'target="_blank"' in out

    def test_bare_url_is_linkified_safely(self):
        out = render_html("see https://example.test/page")
        assert_inert(out)
        assert f'rel="{LINK_REL}"' in out

    def test_unsafe_link_degrades_to_text_not_to_a_tag(self):
        out = render_html("[x](javascript:alert(1))")
        assert "<a" not in out
        assert "javascript" in out  # visible as text, harmless

    def test_spoiler_is_collapsed_and_accessible(self):
        out = render_html("||ending||")
        assert 'data-cp-spoiler="1"' in out
        assert 'aria-expanded="false"' in out
        assert 'tabindex="0"' in out

    def test_newlines_become_breaks(self):
        assert "<br>" in render_html("a\nb")


class TestNormalisation:
    def test_length_is_refused_not_truncated(self):
        with pytest.raises(ValidationFailed):
            sanitize_body("x" * 100, max_length=50, max_links=2)

    def test_empty_after_stripping_is_refused(self):
        with pytest.raises(ValidationFailed):
            sanitize_body("​​   \n\n", max_length=100, max_links=2)

    def test_bidi_override_is_stripped(self):
        body = sanitize_body("safe‮txet", max_length=100, max_links=2)
        assert "‮" not in body.stored_text

    def test_zero_width_smuggling_is_stripped(self):
        body = sanitize_body("sp​am", max_length=100, max_links=2)
        assert body.stored_text == "spam"

    def test_unicode_is_nfc_normalised(self):
        decomposed = "é"  # e + combining acute
        body = sanitize_body(decomposed, max_length=100, max_links=2)
        assert body.stored_text == "é"

    def test_link_cap_is_enforced(self):
        text = " ".join(f"https://example.test/{i}" for i in range(5))
        with pytest.raises(PolicyViolation) as exc:
            sanitize_body(text, max_length=4000, max_links=2)
        assert exc.value.rule == "LINK_CAP"

    def test_crlf_is_normalised(self):
        body = sanitize_body("a\r\nb", max_length=100, max_links=2)
        assert "\r" not in body.stored_text


class TestSafeHref:
    @pytest.mark.parametrize(
        "bad",
        [
            "javascript:alert(1)", "data:text/html,x", "vbscript:x", "//evil.test",
            "/relative", "mailto:a@b.test", "file:///etc/passwd", "",
            'https://a.test" onmouseover="x', "https://a.test\nx",
        ],
    )
    def test_rejected(self, bad):
        assert safe_href(bad) is None

    @pytest.mark.parametrize("good", ["https://a.test", "http://a.test/p?q=1", "www.a.test"])
    def test_accepted(self, good):
        assert safe_href(good) is not None


class TestPreview:
    def test_preview_is_flat_and_bounded(self):
        preview = to_plain_preview("a\n\nb   c" + "x" * 500, limit=40)
        assert "\n" not in preview
        assert len(preview) <= 40
