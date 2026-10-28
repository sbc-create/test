"""Поиск сайта по названию из списка владельца: где ожидаемая карточка (совпадения / подсказка / нет).

python3 probe_search.py <host> <out.json> <query>=<slug> [...]
Ответ делится по «Совпадений:»: выше — блок «Возможно, вы искали», ниже — совпадения.
"""
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

UA = "Mozilla/5.0 (factory-seo-acceptance; popular-titles-20261028)"


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


host, out = sys.argv[1], sys.argv[2]
rows = []
for arg in sys.argv[3:]:
    q, slug = arg.rsplit("=", 1)
    st, html = get(f"https://{host}/search/?q={urllib.parse.quote(q)}")
    if "Совпадений:" in html:
        maybe, res = html.split("Совпадений:", 1)
    else:
        maybe, res = html, ""
    found = list(dict.fromkeys(re.findall(r'href="/title/([^/"]+)/"', res)))
    sugg = list(dict.fromkeys(re.findall(r'href="/title/([^/"]+)/"', maybe)))
    rows.append({"query": q, "expected": slug, "status": st,
                 "match_position": found.index(slug) + 1 if slug in found else None,
                 "suggest_position": sugg.index(slug) + 1 if slug in sugg else None,
                 "matches_first5": found[:5], "suggest_first5": sugg[:5]})
    r = rows[-1]
    print(st, r["match_position"], r["suggest_position"], q, "→", slug, "| первые:", found[:3])
json.dump({"host": host, "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "user_agent": UA, "rows": rows},
          open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
