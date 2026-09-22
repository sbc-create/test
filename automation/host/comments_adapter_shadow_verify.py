#!/usr/bin/env python3
"""Run the rebased artifact on a spare port and check what it actually renders.

Nothing here touches production: a private port, no nginx, no systemd, no
symlink. The question is narrow — did rebasing the adapter onto the UX rebuild
keep the rebuild's page intact and add the mount point?

Each page is fetched twice: once with ANIMEDIA_COMMENTS_MOUNT=1 and once
without, because "off by default" is a claim about the artifact and is cheap to
test directly.
"""
import json
import os
import pathlib
import subprocess
import sys
import time
import urllib.error
import urllib.request

RELEASES = pathlib.Path("/srv/lords/.frontend/releases")
NEW = RELEASES / "20260922T150000Z-632a622-animedia-comments-stage1-efdef56"
BASE = RELEASES / "20260922T143111Z-efdef56-animedia-parity"
TITLE = "/title/master-lda-i-plameni-2/"

# Markers of the UX rebuild that must survive the rebase, and the mount point
# the adapter is supposed to add.
UX_MARKERS = {
    "player section": 'data-b07-player="1"',
    "player frame": "zpl__f",
    "community section": "acomm",
    "recommendation shelf": "data-suggest-basis",
}
MOUNT_MARKERS = {
    "mount div": 'id="cp-comments"',
    "widget css": "comments-widget.css",
    "widget js": "comments-widget.js",
}


def serve(release: pathlib.Path, port: int, mount: bool):
    env = dict(os.environ)
    if mount:
        env["ANIMEDIA_COMMENTS_MOUNT"] = "1"
    else:
        env.pop("ANIMEDIA_COMMENTS_MOUNT", None)
    return subprocess.Popen(
        [sys.executable, "animedia-frontend.py", "--port", str(port)],
        cwd=str(release), env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


def fetch(port: int, path: str, tries: int = 40):
    url = f"http://127.0.0.1:{port}{path}"
    last = None
    for _ in range(tries):
        try:
            req = urllib.request.Request(url, headers={"Host": "animedia.icu"})
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, r.read().decode("utf-8", "replace"), dict(r.headers)
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8", "replace"), dict(e.headers)
        except Exception as e:  # not up yet
            last = e
            time.sleep(0.5)
    raise SystemExit(f"server on {port} never answered: {last}")


def run(release, port, mount, label):
    proc = serve(release, port, mount)
    try:
        code, body, headers = fetch(port, TITLE)
        home_code, home_body, _ = fetch(port, "/")
        cat_code, _, _ = fetch(port, "/catalog/")
        return {
            "label": label,
            "title_status": code,
            "title_bytes": len(body),
            "home_status": home_code,
            "home_bytes": len(home_body),
            "catalog_status": cat_code,
            "ux": {k: (v in body) for k, v in UX_MARKERS.items()},
            "mount": {k: (v in body) for k, v in MOUNT_MARKERS.items()},
            "robots": headers.get("X-Robots-Tag", ""),
        }
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


results = [
    run(BASE, 9187, False, "base efdef56 (no adapter)"),
    run(NEW, 9188, False, "rebased, mount OFF"),
    run(NEW, 9189, True, "rebased, mount ON"),
]

for r in results:
    print(f"\n== {r['label']}")
    print(f"   /            -> {r['home_status']}  ({r['home_bytes']} bytes)")
    print(f"   /catalog/    -> {r['catalog_status']}")
    print(f"   title page   -> {r['title_status']}  ({r['title_bytes']} bytes)")
    print(f"   X-Robots-Tag -> {r['robots'] or '(none at app layer)'}")
    for k, v in r["ux"].items():
        print(f"   UX    {'ok ' if v else 'GONE'}  {k}")
    for k, v in r["mount"].items():
        print(f"   mount {'yes' if v else 'no '}   {k}")

base, off, on = results
print("\n== verdict")
ok = True

if base["ux"] != off["ux"] or base["ux"] != on["ux"]:
    print("   FAIL: the rebase changed which UX blocks render")
    ok = False
else:
    print("   UX blocks identical across base / mount-off / mount-on")

if any(off["mount"].values()):
    print("   FAIL: mount point present with the switch off")
    ok = False
else:
    print("   mount absent when ANIMEDIA_COMMENTS_MOUNT is unset")

if not all(on["mount"].values()):
    print("   FAIL: mount point incomplete with the switch on")
    ok = False
else:
    print("   mount present and complete when the switch is set")

if off["title_bytes"] != base["title_bytes"]:
    print(f"   FAIL: mount-off page differs from base by "
          f"{on['title_bytes'] - base['title_bytes']} bytes")
    ok = False
else:
    print("   mount-off page is byte-identical in length to the base")

print(f"\nSHADOW_VERDICT={'PASS' if ok else 'FAIL'}")
pathlib.Path(sys.argv[1]).write_text(
    json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
sys.exit(0 if ok else 1)
