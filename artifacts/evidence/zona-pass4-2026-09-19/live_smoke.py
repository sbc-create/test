#!/usr/bin/env python3
import json, re, urllib.request, ssl, urllib.error
from pathlib import Path

CTX = ssl.create_default_context()
OUT = Path("/home/claude/wt-zona-finalization-01/artifacts/evidence/zona-pass4-2026-09-19")


class Noredir(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch(path, allow_redirects=False):
    https = urllib.request.HTTPSHandler(context=CTX)
    handlers = [https]
    if not allow_redirects:
        handlers.append(Noredir())
    opener = urllib.request.build_opener(*handlers)
    req = urllib.request.Request(
        "https://zonafilm.space" + path,
        headers={"User-Agent": "zona-pass4-smoke"},
    )
    try:
        with opener.open(req, timeout=45) as r:
            return r.status, dict(r.headers.items()), r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace") if e.fp else ""
        return e.code, dict(e.headers.items()), body


def main():
    smoke = {}
    for path, expect_prefix in [
        ("/movies/?kind=%D0%A1%D0%B5%D1%80%D0%B8%D0%B0%D0%BB&year=2025", "/series/"),
        ("/series/?kind=%D0%A4%D0%B8%D0%BB%D1%8C%D0%BC&year=2026", "/movies/"),
        ("/movies/?kind=%D0%A4%D0%B8%D0%BB%D1%8C%D0%BC", "/movies/"),
        ("/movies/?page=1", "/movies/"),
    ]:
        st, h, _ = fetch(path)
        loc = h.get("Location") or ""
        smoke[path] = {
            "status": st,
            "location": loc,
            "ok": st in (301, 302, 308) and loc.startswith(expect_prefix),
        }

    checks = {}
    for path in [
        "/movies/",
        "/series/?year=2026",
        "/new/",
        "/collections/",
        "/",
        "/title/chasha-vesny/",
    ]:
        st, h, b = fetch(path, allow_redirects=True)
        titles = re.findall(r'class="zt__t"[^>]*>([^<]+)', b)[:8]
        metas = re.findall(r'class="zt__m"[^>]*>([^<]+)', b)[:8]
        h1 = re.search(r"<h1[^>]*>(.*?)</h1>", b, re.S)
        h1t = re.sub("<[^>]+>", "", h1.group(1)).strip() if h1 else None
        checks[path] = {
            "status": st,
            "build": h.get("X-Site-Factory-Build-Id"),
            "h1": h1t,
            "titles": titles,
            "metas": metas,
            "has240": "Найдено 240" in b,
            "placeholder": (
                "Разделы появятся" in b or "Документы не опубликованы" in b
            ),
            "freshness": ("Премьера ·" in b or "Обновлено ·" in b),
            "sort_ui": "Сначала новые" in b,
            "contact_missing": 'data-contact-config-missing="1"' in b,
        }
        print(
            path,
            checks[path]["h1"],
            checks[path]["titles"][:3],
            "240=",
            checks[path]["has240"],
            "ph=",
            checks[path]["placeholder"],
        )

    _, _, b = fetch("/movies/", True)
    checks["/movies/"]["wrong_kind"] = sum(
        1 for m in re.findall(r'class="zt__m"[^>]*>([^<]+)', b) if "Фильм" not in m
    )
    _, _, b = fetch("/series/?year=2026", True)
    checks["/series/?year=2026"]["foreign_year"] = sum(
        1 for m in re.findall(r'class="zt__m"[^>]*>([^<]+)', b) if "2026" not in m
    )

    report = {"redirects": smoke, "pages": checks}
    (OUT / "LIVE_SMOKE.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("redirects", {k: v["ok"] for k, v in smoke.items()})
    print("build", checks["/"]["build"])


if __name__ == "__main__":
    main()
