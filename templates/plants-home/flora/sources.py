"""Факты plants-home из открытых и прочитанных страниц NC State Extension Plant Toolbox.

Факт привязан к КОНКРЕТНОМУ виду (научное название из источника): условия одного вида не переносятся на другой.
Страницы — в var/plants-home/private (0700, вне git); в репозитории — URL, дата, sha256 и извлечённые поля.

Запуск: python3 -m flora.sources ncsu <url>… | reparse | check
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
PRIVATE = REPO / "var" / "plants-home" / "private" / "pages"
OUT = ROOT / "data" / "sources"
PARSER = "ph-facts/1.0"
KEEP = {
    "Light:",
    "Soil Texture:",
    "Soil pH:",
    "Soil Drainage:",
    "Available Space To Plant:",
    "Maintenance:",
    "Growth Rate:",
    "Habit/Form:",
    "Leaf Characteristics:",
    "Recommended Propagation Strategy:",
    "Country Or Region Of Origin:",
    "USDA Plant Hardiness Zone:",
    "Poison Severity:",
    "Poison Symptoms:",
    "Poison Toxic Principle:",
    "Causes Contact Dermatitis:",
    "Poison Part:",
    "Height:",
    "Width:",
    "Problems:",
    "Insects, Diseases, and Other Plant Problems:",
    "Flower Bloom Time:",
}


def text_of(fragment: str) -> str:
    t = html.unescape(re.sub(r"<[^>]+>", " ", fragment)).replace("\xa0", " ")
    return re.sub(r"\s+", " ", t).strip()


def parse_ncsu(raw: str, url: str) -> dict:
    title = text_of(re.search(r"<title>(.*?)</title>", raw, re.S).group(1))
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", raw, re.S)
    sci = text_of(h1.group(1)) if h1 else title.split("(")[0].strip()
    sci = re.sub(r"\s*Play pronunciation\s*$", "", sci)
    common = re.search(r"\(([^)]*)\)", title)
    attrs: dict[str, list[str]] = {}
    for dt, body in re.findall(r"<dt>\s*(.*?)\s*</dt>(.*?)(?=<dt>|</dl>)", raw, re.S):
        label = text_of(dt)
        if label in KEEP:
            vals = [text_of(v) for v in re.findall(r"<dd>(.*?)</dd>", body, re.S)]
            vals = [v for v in vals if v and v != "See below"]
            if vals:
                attrs[label] = vals
    desc = []
    m = re.search(r"<dt>\s*Description\s*</dt>\s*<dd>(.*?)</dd>", raw, re.S)
    if m:
        desc = [text_of(p) for p in re.findall(r"<p>(.*?)</p>", m.group(1), re.S)]
        desc = [p for p in desc if p and not p.startswith("VIDEO")]
    prx = re.compile(r"^(?:Insects?|Diseases?)[^:]{0,60}Problems\s*:\s*(.*)$")
    problems, keep = None, []
    for i, para in enumerate(desc):
        m2 = prx.match(para)
        if m2:
            problems = m2.group(1).strip() or (desc[i + 1] if i + 1 < len(desc) else None)
            continue
        if problems and para == problems:
            continue
        keep.append(para)
    desc = [p for p in keep if not p.startswith(("Quick ID", "More information on"))]
    return {
        "kind": "university",
        "publisher": "NC State Extension — Plant Toolbox",
        "name": sci,
        "common_names": [c.strip() for c in common.group(1).split(",")] if common else [],
        "attrs": attrs,
        "description": desc,
        "problems": problems
        or (attrs.get("Insects, Diseases, and Other Plant Problems:") or attrs.get("Problems:") or [None])[0],
    }


def source_id(url: str) -> str:
    return "src-" + hashlib.sha1(url.encode()).hexdigest()[:10]


def _store(raw: bytes) -> tuple[str, str]:
    PRIVATE.mkdir(parents=True, exist_ok=True)
    PRIVATE.parent.chmod(0o700)
    sha = hashlib.sha256(raw).hexdigest()
    (PRIVATE / f"{sha[:16]}.html").write_bytes(raw)
    return sha, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def import_ncsu(urls: list[str]) -> dict:
    from flora.net import Client

    c = Client(delay=2.0)
    OUT.mkdir(parents=True, exist_ok=True)
    report = {}
    for u in urls:
        try:
            st, final, body = c.get(u)
        except Exception as e:  # noqa: BLE001 — отказ политики или сети фиксируется в отчёте, импорт продолжается
            report[u] = f"отказ: {e}"
            continue
        if st != 200:
            report[u] = f"HTTP {st}"
            continue
        facts = parse_ncsu(body.decode("utf-8", "replace"), final)
        if "Light:" not in facts["attrs"] or not facts["description"]:
            report[u] = "страница не распознана (нет Light или Description)"
            continue
        sha, at = _store(body)
        rec = {"id": source_id(final), "url": final, "fetched_at": at, "page_sha256": sha, "parser": PARSER, **facts}
        (OUT / f"{rec['id']}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n")
        report[u] = rec["id"]
    return report


def reparse() -> list[str]:
    done = []
    for path in sorted(OUT.glob("src-*.json")):
        rec = json.loads(path.read_text())
        raw = (PRIVATE / f"{rec['page_sha256'][:16]}.html").read_bytes()
        if hashlib.sha256(raw).hexdigest() != rec["page_sha256"]:
            raise RuntimeError(f"{path.name}: сохранённая страница не совпадает с sha256")
        rec.update(parse_ncsu(raw.decode("utf-8", "replace"), rec["url"]), parser=PARSER)
        path.write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n")
        done.append(rec["id"])
    return done


def load_all() -> dict[str, dict]:
    return {p.stem: json.loads(p.read_text()) for p in sorted(OUT.glob("src-*.json"))}


def fact_lines(rec: dict) -> list[str]:
    out = [rec["name"], *rec.get("common_names", [])]
    out += [f"{k} {v}" for k, vs in rec.get("attrs", {}).items() for v in vs]
    out += rec.get("description", []) + ([rec["problems"]] if rec.get("problems") else [])
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["ncsu", "reparse", "check"])
    ap.add_argument("urls", nargs="*")
    a = ap.parse_args(argv)
    if a.cmd == "ncsu":
        print(json.dumps(import_ncsu(a.urls), ensure_ascii=False, indent=1))
    elif a.cmd == "reparse":
        print(json.dumps(reparse()))
    else:
        for k, r in load_all().items():
            print(k, r["name"], "|", r["attrs"].get("Light:"), "|", len(r["description"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
