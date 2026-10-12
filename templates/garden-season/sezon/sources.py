"""Факты garden-season из открытых и прочитанных источников.

Каждый факт хранит РЕГИОН, к которому относится срок: сроки одного региона не выдаются за универсальные.
Страницы источников — в var/garden-season/private (0700, вне git); в репозитории — URL, дата, sha256 и факты.

- `osu` — месячный календарь OSU Extension: месяц, раздел, пункт, регион (весь Орегон / Western / Central-eastern),
  оговорка о применимости, даты публикации и пересмотра;
- `quotes` — ручные цитаты (data/sources/manual/*.yaml) с регионом; каждая дословно сверяется с текстом страницы.

Запуск: python3 -m sezon.sources osu <url>… | quotes | reparse | check
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

import yaml

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
PRIVATE = REPO / "var" / "garden-season" / "private" / "pages"
OUT = ROOT / "data" / "sources"
MANUAL = OUT / "manual"
PARSER = "gs-facts/1.0"
MONTHS = [
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
]
OSU_REGIONS = {
    "Western Oregon": "or-west",
    "Central/eastern Oregon": "or-east",
    "Central Oregon": "or-east",
    "Eastern Oregon": "or-east",
    "Coastal Oregon": "or-coast",
    "Southern Oregon": "or-south",
}


REGION_RX = re.compile(r"(?i)oregon|valley|coast|cascades|elevation|portland|ontario|medford|roseburg")
TIME_RX = re.compile(
    r"(?i)\b(early|mid|late|first|second|last|week|january|february|march|april|may|june|july|august|"
    r"september|october|november|december)\b"
)


def text_of(fragment: str) -> str:
    t = html.unescape(re.sub(r"<[^>]+>", "", fragment)).replace("\xa0", " ")
    return re.sub(r"\s+", " ", t).strip()


def norm(s: str) -> str:
    s = s.replace("\xa0", " ").replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", s).strip().lower()


def parse_osu(raw: str, url: str) -> dict:
    title = text_of(re.search(r"<title>(.*?)</title>", raw, re.S).group(1)).split(" | ")[0]
    month = next((i + 1 for i, m in enumerate(MONTHS) if m in title.lower()), None)
    if not month:
        raise ValueError(f"{url}: месяц не распознан в «{title}»")
    body = raw[raw.find("<h2>") : raw.find("Trade-name products")]
    items, n = [], 0
    for sec in re.split(r"(?=<h2>)", body):
        h = re.match(r"<h2>(.*?)</h2>", sec, re.S)
        if not h:
            continue
        section = text_of(h.group(1))
        for li in re.findall(r"<li>(.*?)</li>", sec, re.S):
            t = text_of(li)
            if not t:
                continue
            region, label, when, rest = "or-all", None, None, t
            m = re.match(r"^([A-Z][^:]{2,90}):\s*(.+)$", t)
            if m:
                pre = m.group(1).strip()
                known = {k.lower(): v for k, v in OSU_REGIONS.items()}
                if pre.lower() in known:
                    region, label, rest = known[pre.lower()], pre, m.group(2)
                elif REGION_RX.search(pre):
                    region, label, rest = "or-local", pre, m.group(2)
                elif TIME_RX.search(pre):
                    when, rest = pre, m.group(2)
            n += 1
            it = {"id": f"m{month:02d}-{n:02d}", "section": section, "region": region, "text": rest}
            if label:
                it["region_label"] = label
            if when:
                it["when"] = when
            items.append(it)
    plain = text_of(raw)
    caveat = re.search(r"[A-Z][a-z ]+ (?:are|is) not necessarily applicable to all areas of Oregon\.", plain)
    pub = re.search(r"Published ([A-Z][a-z]+ \d{4})(?:, Reviewed (\d{4}))?", plain)
    return {
        "kind": "university",
        "publisher": "Oregon State University Extension Service",
        "name": title,
        "month": month,
        "region_scope": "Орегон, США",
        "caveat": caveat.group(0) if caveat else None,
        "published": pub.group(1) if pub else None,
        "reviewed": pub.group(2) if pub else None,
        "items": items,
    }


def source_id(url: str) -> str:
    return "src-" + hashlib.sha1(url.encode()).hexdigest()[:10]


def _store(raw: bytes) -> tuple[str, str]:
    PRIVATE.mkdir(parents=True, exist_ok=True)
    PRIVATE.parent.chmod(0o700)
    sha = hashlib.sha256(raw).hexdigest()
    (PRIVATE / f"{sha[:16]}.html").write_bytes(raw)
    return sha, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def fetch(url: str):
    from sezon.net import Client

    st, final, body = Client(delay=2.0).get(url)
    if st != 200:
        raise RuntimeError(f"{url}: HTTP {st}")
    return final, body


def _write(rec: dict) -> str:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{rec['id']}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n")
    return rec["id"]


def import_osu(urls: list[str]) -> list[str]:
    done = []
    for u in urls:
        final, body = fetch(u)
        sha, at = _store(body)
        facts = parse_osu(body.decode("utf-8", "replace"), final)
        if len(facts["items"]) < 5 or not facts["caveat"]:
            raise RuntimeError(f"{final}: календарь не распознан (пунктов {len(facts['items'])})")
        done.append(
            _write(
                {"id": source_id(final), "url": final, "fetched_at": at, "page_sha256": sha, "parser": PARSER, **facts}
            )
        )
    return done


def import_quotes() -> list[str]:
    done = []
    for spec_path in sorted(MANUAL.glob("*.yaml")):
        spec = yaml.safe_load(spec_path.read_text())
        final, body = fetch(spec["url"])
        sha, at = _store(body)
        text = norm(text_of(body.decode("utf-8", "replace")))
        missing = [q["quote"] for q in spec["quotes"] if norm(q["quote"]) not in text]
        if missing:
            raise RuntimeError(f"{spec_path.name}: цитаты не найдены на странице: {missing}")
        done.append(
            _write(
                {
                    "id": source_id(final),
                    "url": final,
                    "fetched_at": at,
                    "page_sha256": sha,
                    "parser": PARSER,
                    **{k: spec[k] for k in ("kind", "publisher", "name", "region_scope")},
                    "quotes": spec["quotes"],
                }
            )
        )
    return done


def reparse() -> list[str]:
    done = []
    for path in sorted(OUT.glob("src-*.json")):
        rec = json.loads(path.read_text())
        if "items" not in rec:
            continue
        raw = (PRIVATE / f"{rec['page_sha256'][:16]}.html").read_bytes()
        if hashlib.sha256(raw).hexdigest() != rec["page_sha256"]:
            raise RuntimeError(f"{path.name}: сохранённая страница не совпадает с sha256")
        rec.update(parse_osu(raw.decode("utf-8", "replace"), rec["url"]), parser=PARSER)
        done.append(_write(rec))
    return done


def load_all() -> dict[str, dict]:
    return {p.stem: json.loads(p.read_text()) for p in sorted(OUT.glob("src-*.json"))}


def fact_lines(rec: dict, refs: list[str] | None = None) -> list[tuple[str, str]]:
    """(регион, утверждение) — для проверки чисел и регионов в материалах. refs ограничивает пункты/цитаты."""
    out = []
    for it in rec.get("items", []):
        if refs is None or it["id"] in refs:
            out.append((it["region"], it["text"]))
    for q in rec.get("quotes", []):
        if refs is None or q["id"] in refs:
            out.append(
                (
                    q.get("region", rec.get("region_default", "")),
                    q["quote"] + " " + " ".join(map(str, q.get("values", []))),
                )
            )
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["osu", "quotes", "reparse", "check"])
    ap.add_argument("urls", nargs="*")
    a = ap.parse_args(argv)
    if a.cmd == "osu":
        print(json.dumps(import_osu(a.urls)))
    elif a.cmd == "quotes":
        print(json.dumps(import_quotes()))
    elif a.cmd == "reparse":
        print(json.dumps(reparse()))
    else:
        for k, r in load_all().items():
            print(k, r.get("month"), r["name"][:50], len(r.get("items", r.get("quotes", []))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
