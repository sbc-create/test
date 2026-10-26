"""Сверка идентичности удержанных IDENTITY_UNCLEAR: ID → Shikimori → класс расхождения.

Только чтение: снимки потоком, страницы Yummy, Shikimori через source_fetch.
"""
import json, pathlib, re, subprocess, sys, time, urllib.request

sys.path.insert(0, "/home/claude/wt-portable-site-cell-01")
from factory.qwen import editorial

held = json.load(open(sys.argv[1]))
out_path = sys.argv[2]
SNAP = {
    "animedia.icu": "/srv/lords/.frontend/animedia-01-details.json",
    "zonafilm.space": "/srv/zonafilm-space/data/zona-01-details.json",
    "zonafilm12.site": "/srv/lords/.frontend/zona-03-details.json",
    "an1mego.site": "/srv/an1mego-site/data/animego-02-details.json",
    "animeg0.site": "/srv/animeg0-site/data/animego-03-details.json",
    "an1meg0.site": "/srv/an1meg0-site/data/animego-04-details.json",
}
urls = [u for u, l in held.items() if l["outcome"] == "IDENTITY_UNCLEAR" and "animedia.space" not in u]
by_site = {}
for u in urls:
    by_site.setdefault(u.split("/")[2], []).append(u)

recs = {}
for site, us in by_site.items():
    if site not in SNAP:
        continue
    want = {u.rstrip("/").rsplit("/", 1)[-1]: u for u in us}

    def take(slug, rec):
        if slug in want:
            sh = (rec.get("ratings_by_source") or {}).get("shikimori") or {}
            recs[want[slug]] = {"name": rec.get("name"), "original_name": rec.get("original_name"),
                                "year": rec.get("year"), "type": rec.get("type"),
                                "shikimori_id": sh.get("external_id"), "match_state": sh.get("match_state"),
                                "mal": (rec.get("external_ids") or {}).get("mal"),
                                "imdb": (rec.get("external_ids") or {}).get("imdb")}
        return len(recs) >= len(urls)
    editorial._обойти_снимок(pathlib.Path(SNAP[site]), take)

for u in urls:
    if "yummyani" in u.split("/")[2]:
        try:
            b = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "site-factory-check"}), timeout=30).read().decode()
            mal = re.search(r'\\"myAnimeList\\":\\"?(\d+)', b)
            nm = re.search(r'\\"name\\":\{\\"rus\\":\\"(.*?)\\"', b)
            on = re.search(r'\\"originalName\\":\\"(.*?)\\"', b)
            recs[u] = {"name": nm and nm.group(1), "original_name": on and on.group(1), "mal": mal and mal.group(1)}
        except Exception as e:  # noqa: BLE001
            recs[u] = {"error": f"{type(e).__name__}"}


def norm(s):
    return re.sub(r"[^0-9a-zа-яё]+", "", str(s or "").lower().replace("ё", "е"))


rows = []
for u in urls:
    r = recs.get(u, {})
    sid = r.get("shikimori_id") or r.get("mal")
    row = {"url": u, "same_in_row": held[u].get("same_in_row"), **r}
    if not sid:
        row["class"] = "NO_ID"
        rows.append(row)
        continue
    o = subprocess.run(["python3", "/home/claude/wt-portable-site-cell-01/automation/local/source_fetch.py", "shikimori", str(sid)],
                       capture_output=True, text=True, cwd="/home/claude/wt-portable-site-cell-01")
    try:
        s = json.loads(o.stdout)
    except ValueError:
        s = {"ok": False}
    time.sleep(1.2)
    if not s.get("ok"):
        row["class"] = "SOURCE_FAIL"
        rows.append(row)
        continue
    row.update({"sh_id": sid, "sh_russian": s.get("russian"), "sh_name": s.get("name"), "sh_kind": s.get("kind"),
                "sh_aired": s.get("aired_on"), "sh_synonyms": s.get("synonyms"), "sh_english": s.get("english")})
    card, rus = norm(r.get("name")), norm(s.get("russian"))
    alt = {norm(x) for x in (s.get("synonyms") or []) + (s.get("english") or []) + [s.get("name")] if x}
    orig_ok = bool(r.get("original_name")) and norm(r.get("original_name")) in alt
    if card and card == rus:
        row["class"] = "EXACT"
    elif card and rus and (card.startswith(rus) or rus.startswith(card)):
        row["class"] = "PREFIX"
    elif card in alt and orig_ok:
        row["class"] = "SYNONYM+ORIGINAL"
    elif card in alt:
        row["class"] = "SYNONYM_ONLY"
    elif orig_ok:
        row["class"] = "ORIGINAL_ONLY"
    else:
        row["class"] = "MISMATCH"
    rows.append(row)

json.dump(rows, open(out_path, "w"), ensure_ascii=False, indent=1)
from collections import Counter
print(Counter(r["class"] for r in rows))
