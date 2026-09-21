"""Server-side injection of the community rating widget into title pages.

Why it works the way it does
----------------------------
``yummy-frontend.py`` proxies title pages from the Next.js application and
deliberately never rewrites that markup: nodes or attributes placed inside the
React tree broke hydration (``Minified React error #418``) and took the whole
client side down with them. It also streams foreign pages instead of buffering,
because buffering moved TTFB from 0.2 s to 1.2 s.

Both constraints are respected here:

* the only thing injected is a single ``<script defer>`` immediately before
  ``</body>`` — the last node of the container, which is the one position the
  frontend's own history shows to be safe;
* the injection happens **during** streaming through a rolling tail window, so
  no page is ever held in memory and TTFB is unchanged.

The widget itself then waits for ``load`` and mounts a fixed-position panel, so
nothing is added to the framework's tree while it is hydrating.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
from pathlib import Path
from typing import Any

ASSET_URL_PREFIX = "/assets/community/"
LOADER_ID = "cr-widget-loader"
BODY_END = b"</body>"

#: Only real title pages. Not the API, not assets, not the catalogue.
TITLE_PATH_RE = re.compile(r"^/anime/(?P<slug>[A-Za-z0-9][A-Za-z0-9_-]*)/?$")

ASSETS_DIR = Path(__file__).resolve().parent / "frontend"

ASSET_FILES: dict[str, tuple[str, str]] = {
    "community_rating.js": ("community_rating.js", "application/javascript; charset=utf-8"),
    "community_rating.css": ("community_rating.css", "text/css; charset=utf-8"),
}


def is_title_path(path: str) -> bool:
    return bool(TITLE_PATH_RE.match(path or ""))


def asset_name(path: str) -> str | None:
    """Return the asset filename for an asset URL, or None if it is not one."""
    if not path or not path.startswith(ASSET_URL_PREFIX):
        return None
    name = path[len(ASSET_URL_PREFIX) :]
    # No traversal, no nesting: the asset set is a fixed allowlist.
    if name in ASSET_FILES:
        return name
    return None


def read_asset(name: str, *, assets_dir: Path | None = None) -> tuple[bytes, str] | None:
    entry = ASSET_FILES.get(name)
    if entry is None:
        return None
    filename, content_type = entry
    path = Path(assets_dir or ASSETS_DIR) / filename
    if not path.is_file():
        return None
    return path.read_bytes(), content_type


def widget_enabled(flags: dict[str, Any] | None) -> bool:
    """The widget exists only while public writes are on and unkilled.

    The kill switch must remove the UI, not merely make it fail — a visitor
    should never be offered a control that cannot work.
    """
    if not flags:
        return False
    if int(flags.get("KILL_SWITCH") or 0):
        return False
    if int(flags.get("READ_ONLY") or 0):
        return False
    if not int(flags.get("PUBLIC_WRITE_ENABLED") or 0):
        return False
    return int(flags.get("PUBLIC_WRITE_ROLLOUT_PERCENT") or 0) > 0


def load_flags_file(path: str | Path) -> dict[str, Any] | None:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return None


def resolve_subject(path: str, *, readmodel: str | Path) -> str | None:
    """Map ``/anime/<slug>`` to the community subject id, or None.

    A slug the read model does not know is not an error: that page simply gets
    no widget. Guessing a subject id would attach votes to the wrong title.
    """
    m = TITLE_PATH_RE.match(path or "")
    if not m:
        return None
    slug = m.group("slug")
    db = Path(readmodel)
    if not db.is_file():
        return None
    try:
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=2)
    except Exception:
        return None
    try:
        row = conn.execute(
            "SELECT entity_id FROM entity WHERE slug = ? LIMIT 1", (slug,)
        ).fetchone()
    except Exception:
        return None
    finally:
        conn.close()
    if not row or not row[0]:
        return None
    entity_id = str(row[0])
    return entity_id if entity_id.startswith("nova:") else f"nova:{entity_id}"


def loader_tag(subject_id: str, *, asset_version: str = "") -> bytes:
    """The single node injected into the page.

    Only a script: no stylesheet link and no markup. The script appends its own
    stylesheet and its own container after ``load``, so the served HTML gains
    exactly one element and the framework has finished hydrating before the DOM
    changes at all.
    """
    src = ASSET_URL_PREFIX + "community_rating.js"
    if asset_version:
        src += "?v=" + asset_version
    subject = (
        str(subject_id)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
    return (
        f'<script id="{LOADER_ID}" data-subject="{subject}" src="{src}" defer></script>'
    ).encode("utf-8")


class StreamInjector:
    """Insert ``payload`` before the last ``</body>`` of a streamed response.

    Only ``len(BODY_END) - 1`` bytes are ever held back, so the memory cost is
    constant and the first byte still leaves as soon as the upstream sends it.
    """

    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self._tail = b""
        self.done = False

    def feed(self, chunk: bytes) -> bytes:
        """Return the bytes that are safe to write out for this chunk."""
        if self.done:
            return chunk
        data = self._tail + chunk
        idx = data.rfind(BODY_END)
        if idx >= 0:
            self.done = True
            self._tail = b""
            return data[:idx] + self.payload + data[idx:]
        keep = len(BODY_END) - 1
        if len(data) > keep:
            self._tail = data[-keep:]
            return data[:-keep]
        self._tail = data
        return b""

    def finish(self) -> bytes:
        """Flush whatever was held back. Never loses bytes if no </body> came."""
        tail, self._tail = self._tail, b""
        return tail


def inject_into_document(body: bytes, payload: bytes) -> bytes:
    """Whole-document variant, for tests and for non-streamed responses."""
    idx = body.rfind(BODY_END)
    if idx < 0:
        return body
    return body[:idx] + payload + body[idx:]


def plan_injection(
    path: str,
    *,
    flags_path: str | Path,
    readmodel: str | Path,
    asset_version: str = "",
) -> bytes | None:
    """Full decision for one request: bytes to inject, or None for no widget."""
    if not is_title_path(path):
        return None
    if not widget_enabled(load_flags_file(flags_path)):
        return None
    subject = resolve_subject(path, readmodel=readmodel)
    if not subject:
        return None
    return loader_tag(subject, asset_version=asset_version)
