"""Повторная приёмка одного домена Yummy после выпуска — одной командой.

python3 yummy_recheck.py <домен> [параллельность=2]
Шаги (только GET к своему домену): снимок всех частей карты → обход собственного каталога
(листалка /catalog и /catalog/announcement) → догон тайтлов из titles.xml, до которых листалка
не довела → новый baseline → yummy_accept.py против baseline-1457Z.
Итог: recheck-<время>/<домен>-recheck.json и строка в stdout.
Признак D4 — сколько тайтлов эталона достижимо из листалки (должно быть все).
"""
import datetime, json, os, re, subprocess, sys

D = sys.argv[1]; W = sys.argv[2] if len(sys.argv) > 2 else "2"
HERE = os.path.dirname(os.path.abspath(__file__))
TAG = datetime.datetime.utcnow().strftime("%Y%m%dT%H%MZ")
OUT = os.path.join(HERE, f"recheck-{TAG}-{D}"); os.makedirs(OUT, exist_ok=True)
run = lambda *a: subprocess.run([sys.executable, *a], cwd=OUT, capture_output=True, text=True)
log = open(os.path.join(OUT, "run.log"), "a")

def step(name, *a):
    r = run(*a); log.write(f"== {name}\n{r.stdout[-3000:]}\n{r.stderr[-3000:]}\n"); log.flush()
    if r.returncode != 0: raise SystemExit(f"{name}: код {r.returncode}, см. {OUT}/run.log")
    return r.stdout

started = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
step("snap", os.path.join(HERE, "yummy_snap.py"), D, ".")
step("catalog", os.path.join(HERE, "yummy_catalog_crawl.py"), D, f"{D}-catalog.json", W)
listed = set(json.load(open(os.path.join(OUT, f"{D}-catalog.json.titles"))))
sm = set(re.findall(rf"https://{re.escape(D)}/anime/([^/<]+)</loc>", open(os.path.join(OUT, f"{D}__titles.xml")).read()))
extra = sorted(sm - listed)
json.dump(extra, open(os.path.join(OUT, f"{D}-extra-titles.json"), "w"))
if extra:
    step("extra", os.path.join(HERE, "yummy_extra_crawl.py"), D, f"{D}-extra.json", W, f"{D}-extra-titles.json")
step("baseline", os.path.join(HERE, "yummy_baseline.py"), D, ".", "base")
acc = step("accept", os.path.join(HERE, "yummy_accept.py"), D, os.path.join(HERE, "baseline-1457Z", f"{D}.json"),
           os.path.join("base", f"{D}.json"), "30")
new = json.load(open(os.path.join(OUT, "base", f"{D}.json")))
res = {"domain": D, "started": started, "finished": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
       "d4_reach": {"titles_in_listing": len(listed), "titles_in_titles_xml": len(sm), "not_reachable_from_listing": len(extra),
                    "own_titles": new["own"]["titles"]},
       "own": new["own"], "sitemap": new["sitemap"], "accept_line": acc.strip()[-1500:], "dir": OUT}
json.dump(res, open(os.path.join(OUT, f"{D}-recheck.json"), "w"), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False))
