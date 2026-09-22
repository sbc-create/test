"""A real HTML parser for the security assertions.

Written after two regex attempts got this wrong in opposite directions.

The first searched the raw output for `onerror=` and failed on *correct*
output: an escaped `&lt;img src=x onerror=alert(1)&gt;` is inert precisely
because it is text, and it still contains those characters.

The second matched `<tag attrs>` and pulled attribute names out of `attrs` with
a regex — which then found `src` inside `datetime="&lt;img src=x ...&gt;"`,
because a quoted attribute value containing escaped markup has no raw `>` to
stop at.

The lesson is that "is this string safe HTML" is a parsing question, and the
standard library already answers it. :class:`Inspector` reports the tags and
attribute *names* a browser would actually see, so a payload that survives as
text is correctly invisible to it and a payload that becomes markup is not.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser


@dataclass
class Inspector(HTMLParser):
    """Collects what a browser would parse out of a fragment."""

    tags: set[str] = field(default_factory=set)
    attributes: set[tuple[str, str]] = field(default_factory=set)
    text: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        super().__init__(convert_charrefs=True)

    def handle_starttag(self, tag, attrs):
        self.tags.add(tag.lower())
        for name, _value in attrs:
            self.attributes.add((tag.lower(), name.lower()))

    handle_startendtag = handle_starttag

    def handle_endtag(self, tag):
        self.tags.add(tag.lower())

    def handle_data(self, data):
        self.text.append(data)

    def attribute_values(self, wanted: str) -> list[str]:
        return [v for (_, n), v in self._values.items() if n == wanted]


def inspect(fragment: str) -> Inspector:
    parser = Inspector()
    parser.feed(fragment)
    parser.close()
    return parser


def attribute_values(fragment: str, wanted_attr: str) -> list[str]:
    """Every value of one attribute, as a browser would decode it."""
    found: list[str] = []

    class Collector(HTMLParser):
        def handle_starttag(self, tag, attrs):
            for name, value in attrs:
                if name.lower() == wanted_attr.lower() and value is not None:
                    found.append(value)

        handle_startendtag = handle_starttag

    collector = Collector(convert_charrefs=True)
    collector.feed(fragment)
    collector.close()
    return found


def assert_no_scripting(fragment: str, *, allowed_tags: set[str]) -> None:
    """The one assertion every rendering test wants.

    No tag outside the allowlist, no event-handler attribute anywhere, and no
    dangerous scheme in any href — all judged on what a parser sees, not on
    what a substring search finds.
    """
    parsed = inspect(fragment)

    unexpected = parsed.tags - allowed_tags
    assert not unexpected, f"unexpected tags {sorted(unexpected)} in {fragment!r}"

    handlers = sorted(
        f"{tag}[{attr}]" for tag, attr in parsed.attributes if attr.startswith("on")
    )
    assert not handlers, f"event handler attributes {handlers} in {fragment!r}"

    for href in attribute_values(fragment, "href"):
        scheme = href.strip().lower()
        assert scheme.startswith(("http://", "https://")), f"unsafe href {href!r}"
