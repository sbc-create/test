"""Сохранность главной animedia.icu после обновления каталога: блоки, составы полок против файла подборок, пересечения."""
import html as H, json, re, sys, urllib.request
UA = "Mozilla/5.0 factory-seo-acceptance"
h = urllib.request.urlopen(urllib.request.Request("https://animedia.icu/", headers={"User-Agent": UA}), timeout=30).read().decode()
main = h[h.find("<main"):]
parts = re.split(r"<h2[^>]*>", main)
blocks = []
for p in parts[1:]:
    t = H.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", p.split("</h2>")[0]))).strip()
    slugs = list(dict.fromkeys(re.findall(r'href="(?:https://animedia\.icu)?/title/([^/"]+)/', p)))
    blocks.append((t, slugs))
cols = {c["key"]: c for c in json.load(open("docs/seo-operator/ANIMEDIA_ICU_COLLECTIONS_20261026.json"))["collections"]}
R = {"blocks": [[t, len(s)] for t, s in blocks]}
by = dict(blocks)
new = set(next((s for t, s in blocks if t.startswith("Новые аниме")), []))
for slug in ("anime-filmy-na-vecher", "korotkie-anime-serialy"):
    c = cols[slug]; want = [i["slug"] for i in sorted(c["items"], key=lambda i: i["order"])]
    got = by.get(c["title"], [])
    R[slug] = {"title_on_home": c["title"] in by, "home_n": len(got), "prefix_matches_file": got == want[:len(got)], "overlap_new": len(set(got) & new)}
names = [t for t, s in blocks]
pairs = []
for i in range(len(blocks)):
    for j in range(i + 1, len(blocks)):
        a, b = set(blocks[i][1]), set(blocks[j][1])
        if a and b and len(a & b) >= 3:
            pairs.append([blocks[i][0], blocks[j][0], len(a & b), min(len(a), len(b))])
R["overlaps_ge3"] = pairs
R["empty"] = [t for t, s in blocks if not s and not t.startswith("Тематические") and not t.startswith("Animedia ICU")]
print(json.dumps(R, ensure_ascii=False, indent=1))
