#!/usr/bin/env python3
"""Rebase the Stage 1 comments adapter onto the release animedia-01 now declares.

The prepared release 20260922T071857Z-e84ee6e was built from fac5643. The
symlink and the template manifest for animedia-01 now point at efdef56
(ANIMEDIA-UX-REBUILD-01), so applying the prepared release would restart the
site onto the older UX. This rebuilds the same adapter on top of efdef56.

The adapter is two edits and nothing else:
  1. module-level switch + `_блок_комментариев()` inserted above
     `def _аниме_контакты_html()`
  2. one interpolation appended to the title-page body, after every block the
     new UX renders, so nothing the rebuild introduced is moved or dropped.
"""
import hashlib
import json
import pathlib
import re
import shutil
import subprocess
import sys

RELEASES = pathlib.Path("/srv/lords/.frontend/releases")
BASE_ID = "20260922T143111Z-efdef56-animedia-parity"
OLD_ID = "20260922T071857Z-e84ee6e-animedia-comments-stage1"
NEW_ID = "20260922T150000Z-632a622-animedia-comments-stage1-efdef56"

BASE = RELEASES / BASE_ID
OLD = RELEASES / OLD_ID
NEW = RELEASES / NEW_ID

# The adapter, taken verbatim from the release that already carries it, so this
# is a rebase and not a rewrite.
ADAPTER = '''

# --- COMMUNITY_COMMENTS: Stage 1 adapter (animedia.icu owner pilot) ---------
#
# The entire integration with the shared comments module is this function plus
# one f-string interpolation on the title page. There is no comments logic
# here, no styling, no markup beyond a mount point: the widget, the API, the
# cohort gate and every policy live in the shared module and are served by the
# comments gateway at /api/comments/v1/.
#
# Off unless ANIMEDIA_COMMENTS_MOUNT=1 is set in the unit. Shipping the release
# therefore changes nothing by itself, and the switch that turns it on is a
# root-owned file, which is the correct place for it.
#
# Even when mounted, an ordinary visitor sees an empty container and no
# network request result: the widget asks the gateway, the gateway answers 503
# for the public cohort, and the widget renders a notice inside its own box
# without touching the page. What gates the pilot is the server, never this.
#
# Rebased onto ANIMEDIA-UX-REBUILD-01: the mount point is appended after every
# block that release renders, so the community section, the recommendation
# shelf and the player keep the order and the markup the rebuild gave them.
КОММЕНТАРИИ_ВКЛЮЧЕНЫ = os.environ.get("ANIMEDIA_COMMENTS_MOUNT", "") == "1"
КОММЕНТАРИИ_БАЗА = "/api/comments/v1"


def _блок_комментариев(content_id: str) -> str:
    """Mount point for the shared comments widget, or nothing at all.

    `content_id` is the provider UUID of the title, not its slug. A slug is an
    address and addresses change; keying the discussion on the stable id means
    renaming a title does not orphan its comments.
    """
    if not КОММЕНТАРИИ_ВКЛЮЧЕНЫ or not content_id:
        return ""
    безопасный = html.escape(str(content_id), quote=True)
    return (
        f'<link rel="stylesheet" href="{КОММЕНТАРИИ_БАЗА}/assets/comments-widget.css">'
        f'<div class="zwrap zwrap--title">'
        f'<div id="cp-comments" data-cp-comments '
        f'data-cp-resource-type="title" data-cp-content-id="{безопасный}"></div>'
        f"</div>"
        f'<script src="{КОММЕНТАРИИ_БАЗА}/assets/comments-widget.js" defer></script>'
        f"<script>"
        f"window.addEventListener('DOMContentLoaded',function(){{"
        f"if(!window.SiteFactoryComments)return;"
        f"window.SiteFactoryComments.mount('#cp-comments',{{"
        f"apiBase:'',resourceType:'title',canonicalContentId:'{безопасный}',"
        f"theme:'dark',locale:'ru'}});}});"
        f"</script>"
    )

'''

ANCHOR_FN = "def _аниме_контакты_html() -> str:"
ANCHOR_BODY = "            f'{блок_рекомендуем}</div>')"
REPLACE_BODY = (
    "            f'{блок_рекомендуем}'\n"
    "            f'{_блок_комментариев(деталь.get(\"id\") or \"\")}</div>')"
)


def sha256(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def fail(msg):
    print(f"REFUSED: {msg}", file=sys.stderr)
    sys.exit(1)


# --- preconditions ---------------------------------------------------------
if not BASE.is_dir():
    fail(f"base release missing: {BASE}")
if NEW.exists():
    # A finished release is never overwritten — that would change an artifact
    # somebody may already have deployed. A partial build (no RELEASE.json) is
    # this script's own debris from a failed run and is cleared, so the build
    # is repeatable.
    if (NEW / "RELEASE.json").exists():
        fail(f"refusing to overwrite a finished release: {NEW}")
    print(f"clearing an unfinished build left at {NEW}")
    shutil.rmtree(NEW)

base_manifest = json.loads((BASE / "RELEASE.json").read_text(encoding="utf-8"))
declared = base_manifest["artifact_sha256"]
actual = sha256(BASE / "animedia-frontend.py")
if declared != actual:
    fail(f"base artifact does not match its manifest: {actual} != {declared}")
print(f"base {BASE_ID} verified against its own manifest ({actual[:16]}…)")

src = (BASE / "animedia-frontend.py").read_text(encoding="utf-8")
if "ANIMEDIA_COMMENTS_MOUNT" in src:
    fail("base already carries a comments adapter — refusing to add a second")
if src.count(ANCHOR_FN) != 1:
    fail(f"anchor 1 is not unique in the base ({src.count(ANCHOR_FN)} hits)")
if src.count(ANCHOR_BODY) != 1:
    fail(f"anchor 2 is not unique in the base ({src.count(ANCHOR_BODY)} hits)")

# --- the two edits ---------------------------------------------------------
patched = src.replace(ANCHOR_FN, ADAPTER.lstrip("\n") + "\n" + ANCHOR_FN, 1)
patched = patched.replace(ANCHOR_BODY, REPLACE_BODY, 1)

if patched == src:
    fail("patch produced no change")
if patched.count("_блок_комментариев") != 2:
    fail("expected exactly one definition and one call site")

# --- assemble the release --------------------------------------------------
NEW.mkdir(parents=True)
for item in sorted(BASE.iterdir()):
    if item.name in ("RELEASE.json", "animedia-frontend.py"):
        continue
    shutil.copy2(item, NEW / item.name)
    print(f"copied unchanged: {item.name}")

target = NEW / "animedia-frontend.py"
target.write_text(patched, encoding="utf-8")
shutil.copymode(BASE / "animedia-frontend.py", target)

# --- prove the artifact is the base plus the adapter and nothing else ------
syntax = subprocess.run(
    [sys.executable, "-c",
     "import sys,pathlib;compile(pathlib.Path(sys.argv[1]).read_text('utf-8'),"
     "sys.argv[1],'exec')", str(target)],
    capture_output=True, text=True)
if syntax.returncode != 0:
    shutil.rmtree(NEW)
    fail(f"patched artifact does not compile:\n{syntax.stderr}")
print("patched artifact compiles")
# compile() writes nothing, but be explicit: a release directory holds the
# release and nothing a build step happened to leave behind.
shutil.rmtree(NEW / "__pycache__", ignore_errors=True)

diff = subprocess.run(
    ["diff", "-u", str(BASE / "animedia-frontend.py"), str(target)],
    capture_output=True, text=True).stdout
added = [l for l in diff.splitlines() if l.startswith("+") and not l.startswith("+++")]
removed = [l for l in diff.splitlines() if l.startswith("-") and not l.startswith("---")]
print(f"diff vs base: +{len(added)} / -{len(removed)} lines")
if len(removed) != 1:
    shutil.rmtree(NEW)
    fail(f"expected exactly one replaced line, got {len(removed)}: {removed}")

new_sha = sha256(target)
manifest = {
    "schema_version": 1,
    "tenant": "animedia",
    "site_id": "animedia-01",
    "domain": "animedia.icu",
    "build_id": NEW_ID,
    "stage": "ANIMEDIA-COMMENTS-CANARY-01",
    "branch": "claude/community-comments-platform-01",
    "source_commit": "632a6222e754d3265e7ae55e0c3963887f94d1c3",
    "built_at": "2026-09-22T15:00:00Z",
    "built_from": "git worktree /home/claude/wt-community-comments-platform-01",
    "release_dir": str(NEW),
    "artifact": "animedia-frontend.py",
    "artifact_sha256": new_sha,
    "rebased_onto": {
        "build_id": BASE_ID,
        "artifact_sha256": declared,
        "why": (
            "animedia-01 declares this release in its symlink and template "
            "manifest. The earlier adapter build was based on fac5643; "
            "applying it would have restarted the site onto the older UX."
        ),
    },
    "supersedes": {
        "build_id": OLD_ID,
        "based_on": "20260921T214937Z-fac5643-animedia-parity",
    },
    "adapter": {
        "edits": 2,
        "lines_added": len(added),
        "lines_replaced": len(removed),
        "ui_blocks_removed": 0,
        "note": (
            "Additive only. The player, the community section and the "
            "recommendation shelf of ANIMEDIA-UX-REBUILD-01 are untouched; the "
            "mount point is appended after them."
        ),
    },
    "files": {},
}
for item in sorted(NEW.iterdir()):
    if item.name == "RELEASE.json" or not item.is_file():
        continue
    manifest["files"][item.name] = {
        "sha256": sha256(item),
        "bytes": item.stat().st_size,
    }
(NEW / "RELEASE.json").write_text(
    json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

print(f"\nBUILT {NEW_ID}")
print(f"  artifact sha256 : {new_sha}")
print(f"  rebased onto    : {BASE_ID}")
print(f"  supersedes      : {OLD_ID}")
