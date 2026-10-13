"""Галерея 30 вариантов: данные из доказательств веток + живой опрос превью."""

import html
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

from PIL import Image

OUT = "/home/claude/wt-template-food-daily/templates/food-daily/docs/progress/gallery"
REPORT = "/home/claude/wt-template-food-daily/templates/food-daily/docs/progress/MORNING-REPORT-2026-10-13.md"
REPO = "https://github.com/sbc-create/test/pull/"

SITES = [
    ("food-daily", "Будни на кухне", (95, 111, 124)),
    ("food-baking", "Тесто и десерты", (96, 112, 123)),
    ("food-weekly", "Меню на неделю", (97, 113, 121)),
    ("food-appliances", "Готовим в технике", (98, 114, 122)),
    ("home-practical", "Удобный дом", (99, 100, 115)),
    ("garden-season", "Дача по сезону", (101, 102, 116)),
    ("plants-home", "Домашние растения", (103, 104, 117)),
    ("games-story", "Сюжет пройден", (105, 106, 118)),
    ("games-rpg", "Гайды RPG", (107, 108, 119)),
    ("games-survival", "База выживания", (109, 110, 120)),
]

# строки таблиц утреннего отчёта: | site L name | port | commit | what | actions | axe | widths |
ROW = re.compile(r"^\| (\S+) ([ABC]) (\S+) \| (\d+) \| (\w+) \| (.+?) \| (\d+) \| (\d+) \| (.+?) \|$")


def report_rows():
    rows = {}
    with open(REPORT, encoding="utf-8") as f:
        for line in f:
            m = ROW.match(line.strip())
            if m:
                rows[(m[1], m[2])] = {"variant": m[3], "port": int(m[4]), "what": m[6]}
    return rows


def git(wt, *args):
    return subprocess.run(["git", *args], cwd=wt, capture_output=True, text=True, check=True).stdout.strip()


def passed(v):
    # правило REPORT.md вариантов (gen_report.py): FAIL — False или 0; у составных — поле ok
    if isinstance(v, dict) and "ok" in v:
        return v["ok"] is True
    return v is not False and v != 0 and v is not None


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def evidence(tdir):
    new = os.path.join(tdir, "docs/verification-browser-qa.json")
    if os.path.exists(new):
        qa = load(new)
        vp = load(os.path.join(tdir, "docs/verification-viewports.json"))
        acts = qa.get("actions") or qa["scenarios"]
        axe = sum(len(v) for k, v in qa["axe"].items() if k != "version")
    else:  # food-daily A: старый формат docs/verification/
        qa = load(os.path.join(tdir, "docs/verification/browser-qa.json"))
        sha7 = qa["commit_head"][:7]
        vp = load(os.path.join(tdir, f"docs/verification/viewports-{sha7}.json"))
        acts = qa["scenarios"]
        axe = sum(len(p["violations"]) for p in qa["accessibility"]["pages"].values())
    lcp = [p["lcp_ms"] for p in qa["perf_lab"].values() if p.get("lcp_ms") is not None]
    cls = [p["cls"] for p in qa["perf_lab"].values() if p.get("cls") is not None]
    return {
        "commit": qa["commit_head"][:7],
        "at": qa["at"],
        "pass": sum(1 for v in acts.values() if passed(v)),
        "fail": sorted(k for k, v in acts.items() if not passed(v)),
        "axe": axe,
        "urls": vp["urls"],
        "vp_issues": vp["pages_with_issues"],
        "lcp_max": max(lcp) if lcp else None,
        "cls_max": max(cls) if cls else None,
    }


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


OPENER = urllib.request.build_opener(NoRedirect)


def fetch(url):
    try:
        with OPENER.open(url, timeout=10) as r:
            return r.status, dict(r.headers), r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read().decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001 — недоступность фиксируется как результат
        return None, {}, repr(e)


def meta(page, name):
    m = re.search(rf'<meta name="{re.escape(name)}" content="([^"]*)"', page)
    return m[1] if m else None


def probe(port, variant):
    base = f"http://127.0.0.1:{port}"
    st, hdr, page = fetch(base + "/")
    res = {"status": st}
    if st != 200:
        res["ok"] = False
        res["why"] = f"/ → {st} {page[:80]}"
        return res
    vid = meta(page, "site-factory-variant-id") or ""
    res["variant_id"] = vid
    res["variant_version"] = meta(page, "site-factory-variant-version")
    robots_meta = meta(page, "robots") or ""
    rst, _, robots = fetch(base + "/robots.txt")
    sst, _, sitemap = fetch(base + "/sitemap.xml")
    nst, _, _ = fetch(base + "/nesushchestvuet-gallery-probe/")
    checks = {
        "variant_id": variant in vid,
        "noindex_meta": "noindex" in robots_meta,
        "robots_disallow": rst == 200 and re.search(r"(?m)^Disallow: /\s*$", robots) is not None,
        "sitemap_200": sst == 200 and "<urlset" in sitemap,
        "unknown_404": nst == 404,
    }
    res["checks"] = checks
    res["ok"] = all(checks.values())
    res["why"] = ", ".join(k for k, v in checks.items() if not v)
    return res


def thumb(src, dst, width, crop_h, out_w):
    im = Image.open(src).convert("RGB")
    scale = im.width / width  # скриншоты могут быть с deviceScaleFactor
    im = im.crop((0, 0, im.width, min(im.height, int(crop_h * scale))))
    im = im.resize((out_w, int(im.height * out_w / im.width)), Image.LANCZOS)
    im.save(dst, "JPEG", quality=78, optimize=True, progressive=True)


def main():
    rows = report_rows()
    os.makedirs(os.path.join(OUT, "img"), exist_ok=True)
    data = []
    for site, title, prs in SITES:
        for i, letter in enumerate("ABC"):
            wt = f"/home/claude/wt-template-{site}" + ("" if letter == "A" else f"-{letter.lower()}")
            tdir = f"{wt}/templates/{site}"
            row = rows[(site, letter)]
            ev = evidence(tdir)
            shots = os.path.join(tdir, "docs/screenshots", ev["commit"])
            slug = f"{site}-{letter.lower()}"
            thumb(os.path.join(shots, "home-desktop.png"), f"{OUT}/img/{slug}-desktop.jpg", 1440, 900, 720)
            thumb(os.path.join(shots, "home-mobile.png"), f"{OUT}/img/{slug}-mobile.jpg", 390, 760, 195)
            data.append(
                {
                    "site": site,
                    "title": title,
                    "letter": letter,
                    "variant": row["variant"],
                    "what": row["what"],
                    "port": row["port"],
                    "pr": prs[i],
                    "branch": git(wt, "branch", "--show-current"),
                    "head": git(wt, "rev-parse", "--short=7", "HEAD"),
                    "evidence": ev,
                    "shots_dir": f"templates/{site}/docs/screenshots/{ev['commit']}/",
                    "live": probe(row["port"], row["variant"]),
                }
            )
            print(slug, data[-1]["live"]["ok"], data[-1]["live"].get("why", ""), file=sys.stderr)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(f"{OUT}/gallery.json", "w", encoding="utf-8") as f:
        json.dump({"probed_at": now, "variants": data}, f, ensure_ascii=False, indent=1)
    recs = load(f"{OUT}/recommendations.json") if os.path.exists(f"{OUT}/recommendations.json") else {}
    with open(f"{OUT}/index.html", "w", encoding="utf-8") as f:
        f.write(render(data, now, recs))
    bad = [d for d in data if not d["live"]["ok"] or any(d["evidence"][k] for k in ("fail", "axe", "vp_issues"))]
    print(f"variants={len(data)} problems={len(bad)}", file=sys.stderr)
    return 1 if bad else 0


def e(s):
    return html.escape(str(s))


def card(d):
    ev, lv = d["evidence"], d["live"]
    slug = f"{d['site']}-{d['letter'].lower()}"
    if lv["ok"]:
        live = '<span class="ok">превью отвечает</span>'
    else:
        live = f'<span class="bad">превью: {e(lv.get("why") or lv.get("status"))}</span>'
    fail = f' <span class="bad">провалено: {e(", ".join(ev["fail"]))}</span>' if ev["fail"] else ""
    cls = "—" if ev["cls_max"] is None else f"{ev['cls_max']:g}".replace(".", ",")
    return f"""
<article class="v" id="{slug}">
 <header><span class="letter">{d["letter"]}</span><h3>{e(d["variant"])}</h3></header>
 <p class="what">{e(d["what"])}</p>
 <div class="shots">
  <a href="img/{slug}-desktop.jpg"><img src="img/{slug}-desktop.jpg" width="720" height="450"
   alt="Главная {e(d["variant"])} на компьютере, 1440 px" loading="lazy"></a>
  <a href="img/{slug}-mobile.jpg"><img src="img/{slug}-mobile.jpg" width="195" height="380"
   alt="Главная {e(d["variant"])} на телефоне, 390 px" loading="lazy"></a>
 </div>
 <ul class="links">
  <li><a href="http://127.0.0.1:{d["port"]}/">Превью :{d["port"]}</a></li>
  <li><a href="{REPO}{d["pr"]}">PR #{d["pr"]}</a></li>
 </ul>
 <dl class="st">
  <dt>Сейчас</dt><dd>{live}</dd>
  <dt>Проверено на</dt><dd><code>{e(ev["commit"])}</code> · {e(ev["at"][:16].replace("T", " "))}Z</dd>
  <dt>Действия</dt><dd>{ev["pass"]} PASS{fail}</dd>
  <dt>axe</dt><dd>{ev["axe"]}</dd>
  <dt>Ширины</dt><dd>{ev["urls"]} URL × 4, замечаний {ev["vp_issues"]}</dd>
  <dt>LCP / CLS max</dt><dd>{ev["lcp_max"]} мс / {cls}</dd>
 </dl>
 <p class="branch"><code>{e(d["branch"])}</code>, скриншоты: <code>{e(d["shots_dir"])}</code></p>
</article>"""


def rec_block(rec):
    if not rec:
        return ""
    why = "".join(f"<li>{e(x)}</li>" for x in rec["why"])
    take = "".join(f"<li>{e(x)}</li>" for x in rec.get("take_from_others", []))
    take = f"<p>Перенести из других вариантов:</p><ul>{take}</ul>" if take else ""
    return f"""
<div class="rec"><p><strong>Предлагаю: {e(rec["pick"])} — {e(rec["variant"])}.</strong> {e(rec.get("summary", ""))}</p>
<ul>{why}</ul>{take}</div>"""


def render(data, now, recs):
    ok_live = sum(1 for d in data if d["live"]["ok"])
    sections = []
    for site, title, _ in SITES:
        items = "".join(card(d) for d in data if d["site"] == site)
        sections.append(
            f'<section class="site" id="{e(site)}"><h2>{e(title)} <small>{e(site)}</small></h2>'
            f'{rec_block(recs.get(site))}<div class="grid">{items}</div></section>'
        )
    nav = "".join(f'<a href="#{e(s)}">{e(t)}</a>' for s, t, _ in SITES)
    return f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>Галерея вариантов</title>
<link rel="stylesheet" href="gallery.css">
</head>
<body>
<main>
<h1>Галерея вариантов: 10 сайтов × A/B/C</h1>
<p class="lead">Локальная страница, не для публикации. Превью проверены заново {e(now)}:
отвечают {ok_live} из {len(data)} (главная 200, свой <code>site-factory-variant-id</code>, <code>noindex</code>,
robots <code>Disallow: /</code>, sitemap, 404 на несуществующий адрес). Статусы проверок — из
<code>verification-*.json</code> коммита, указанного в карточке. Скриншоты — верх главной, 1440 и 390 px.
Ссылки на превью работают через SSH-туннель к 127.0.0.1. Рекомендации — моё предложение, решение за владельцем.</p>
<nav aria-label="Сайты">{nav}</nav>
{"".join(sections)}
</main>
</body>
</html>
"""


if __name__ == "__main__":
    sys.exit(main())
