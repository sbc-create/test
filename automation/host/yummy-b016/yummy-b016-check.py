#!/usr/bin/env python3
"""B016/T081 Yummy: проверки до и после выкладки. Только чтение.

  yummy-b016-check.py snapshot <out.json>            снимок: образ, настройки контейнера, издатель на странице
  yummy-b016-check.py compare <before.json> <after.json> [--changed web-site ...]
  yummy-b016-check.py sitemaps [--max-seconds 5] [домен ...]
  yummy-b016-check.py links [домен ...]               ссылки /anime/…--<uuid> на главной (T081)

Значения издателя и прочих настроек не печатаются: сравниваются sha256.
Коды выхода: 0 — норма, 1 — отклонение, 2 — проверка не смогла выполниться.
"""
import hashlib
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

CONTAINERS = {
    "yummyani-staging-web-site-1": "yummyani.site",
    "yummyani-staging-web-org-1": "yummyani.org",
    "yummyani-staging-web-biz-1": "yummyani.biz",
    "yummyani7-site-web-1": "yummyani7.site",
    "yummyani7-info-web-1": "yummyani7.info",
}
# Настройки, которые выкладка образа не должна менять (D169, издатель, накладки).
KEPT = re.compile(r"PUBLISHER|CDNVIDEOHUB|^SEO_INDEXING_ENABLED$|^TITLE_OVERLAYS|^SITE_PROFILE$|^REDIS_URL$|^DATABASE_URL$")
UUID_LINK = re.compile(r'href="/anime/[^"]*--[0-9a-f]{8}-[0-9a-f]{4}-')
UA = {"User-Agent": "yummy-b016-check"}


def h(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:16]


def get(url: str, timeout: int = 90) -> tuple[int, str, float]:
    t = time.time()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace"), time.time() - t
    except urllib.error.HTTPError as e:
        return e.code, "", time.time() - t
    except Exception:  # noqa: BLE001 — тайм-аут и сеть — код -1
        return -1, "", time.time() - t


def container(name: str) -> dict:
    r = subprocess.run(["docker", "inspect", name], capture_output=True, text=True)
    if r.returncode != 0:
        return {"missing": True}
    d = json.loads(r.stdout)[0]
    env = dict(x.split("=", 1) for x in d["Config"]["Env"])
    return {
        "image_id": d["Image"],
        "image_ref": d["Config"]["Image"],
        "revision": (d["Config"].get("Labels") or {}).get("org.opencontainers.image.revision"),
        "kept_env": {k: h(v) for k, v in sorted(env.items()) if KEPT.search(k)},
        "mounts": sorted(f"{m.get('Source')}->{m.get('Destination')}:{'rw' if m.get('RW') else 'ro'}" for m in d.get("Mounts", [])),
        "health": (d["State"].get("Health") or {}).get("Status"),
    }


def publisher_on_page(domain: str) -> dict:
    code, body, _ = get(f"https://{domain}/")
    # Только канонические ссылки: «slug--uuid» отвечает 308 (T081), а urllib 3.10 по 308 не идёт.
    links = [x for x in re.findall(r'href="(/anime/[a-z0-9-]+)"', body) if not re.search(r"--[0-9a-f]{8}-", x)]
    if code != 200 or not links:
        return {"error": f"главная {code}, ссылок {len(links)}"}
    robots_home = re.findall(r'<meta name="robots" content="([^"]*)"', body)
    page = links[0]
    code, body, _ = get(f"https://{domain}{page}")
    vals = sorted(set(re.findall(r'data-publisher-id="([^"]*)"', body)))
    # Режим индексации в теле — второй владелец (D169): выкладка образа его не меняет.
    return {"page": page, "code": code, "publisher_sha": [h(v) for v in vals],
            "robots_home": robots_home, "robots_title": re.findall(r'<meta name="robots" content="([^"]*)"', body)}


def snapshot(out: str) -> int:
    snap = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "containers": {}}
    for name, domain in CONTAINERS.items():
        snap["containers"][name] = {"domain": domain, **container(name), "page": publisher_on_page(domain)}
    json.dump(snap, open(out, "w"), ensure_ascii=False, indent=1)
    bad = [n for n, c in snap["containers"].items() if c.get("missing") or c["page"].get("error") or not c["page"].get("publisher_sha")]
    for n, c in snap["containers"].items():
        print(n, c.get("revision", "—")[:12] if c.get("revision") else "—", c.get("health"), "издатель на странице:", len(c["page"].get("publisher_sha") or []))
    return 2 if bad else 0


def compare(before: str, after: str, changed: list[str]) -> int:
    a, b = json.load(open(before))["containers"], json.load(open(after))["containers"]
    rc = 0
    for name in CONTAINERS:
        x, y = a.get(name, {}), b.get(name, {})
        must_change = any(name.endswith(f"-{c}-1") or c == name for c in changed)
        notes = []
        if x.get("kept_env") != y.get("kept_env"):
            diff = sorted(k for k in set(x.get("kept_env", {})) | set(y.get("kept_env", {})) if x.get("kept_env", {}).get(k) != y.get("kept_env", {}).get(k))
            notes.append(f"настройки изменились: {diff}")
        if x.get("mounts") != y.get("mounts"):
            notes.append("монтирования изменились")
        if x.get("page", {}).get("publisher_sha") != y.get("page", {}).get("publisher_sha"):
            notes.append("data-publisher-id на странице изменился")
        for k in ("robots_home", "robots_title"):
            if x.get("page", {}).get(k) != y.get("page", {}).get(k):
                notes.append(f"meta robots ({k}) изменился: {x.get('page', {}).get(k)} → {y.get('page', {}).get(k)}")
        if y.get("health") != "healthy":
            notes.append(f"здоровье {y.get('health')}")
        if must_change and x.get("image_id") == y.get("image_id"):
            notes.append("образ НЕ сменился, а должен был")
        if not must_change and x.get("image_id") != y.get("image_id"):
            notes.append("образ сменился у витрины вне выпуска")
        print(name, "OK" if not notes else "ОТКЛОНЕНИЕ: " + "; ".join(notes), "|", (y.get("revision") or "")[:12])
        rc = rc or (1 if notes else 0)
    return rc


def sitemaps(domains: list[str], max_s: float) -> int:
    rc = 0
    for d in domains:
        code, idx, t = get(f"https://{d}/sitemap.xml")
        parts = re.findall(r"<loc>([^<]+)</loc>", idx) if code == 200 else []
        if code != 200 or not parts:
            print(d, "sitemap.xml", code, round(t, 2), "— частей нет")
            rc = 1
            continue
        for p in parts:
            c, body, t = get(p)
            n = body.count("<loc>")
            ok = c == 200 and t <= max_s and n > 0
            print(d, p.rsplit("/", 1)[-1], c, f"{t:.2f}s", f"loc={n}", "" if ok else "ОТКЛОНЕНИЕ")
            rc = rc or (0 if ok else 1)
    return rc


def links(domains: list[str]) -> int:
    rc = 0
    for d in domains:
        code, body, _ = get(f"https://{d}/")
        n = len(UUID_LINK.findall(body))
        total = len(re.findall(r'href="/anime/', body))
        print(d, code, f"ссылок /anime/ {total}, с --uuid {n}", "" if (code == 200 and n == 0) else "ОТКЛОНЕНИЕ")
        rc = rc or (0 if code == 200 and n == 0 else 1)
    return rc


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    cmd, rest = argv[0], argv[1:]
    if cmd == "snapshot" and len(rest) == 1:
        return snapshot(rest[0])
    if cmd == "compare" and len(rest) >= 2:
        changed = rest[rest.index("--changed") + 1:] if "--changed" in rest else []
        return compare(rest[0], rest[1], changed)
    if cmd == "sitemaps":
        max_s = 5.0
        if "--max-seconds" in rest:
            i = rest.index("--max-seconds")
            max_s = float(rest[i + 1])
            rest = rest[:i] + rest[i + 2:]
        return sitemaps(rest or list(CONTAINERS.values()), max_s)
    if cmd == "links":
        return links(rest or ["yummyani.site", "yummyani.org", "yummyani.biz"])
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
