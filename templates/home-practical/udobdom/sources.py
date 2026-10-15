"""Факты home-practical из открытых и прочитанных источников.

Страница источника скачивается клиентом шаблона (allowlist, robots, пауза) и хранится
в var/home-practical/private (0700, вне git). В репозиторий попадают только факты:
URL, дата, sha256 страницы, короткие цитаты и извлечённые значения.

Два способа получить факты:
- `ikea` — разбор карточки товара (размеры, нагрузка, «Good to know», безопасность, уход);
- `quotes` — цитаты, выбранные вручную (data/sources/manual/*.yaml); каждая цитата
  обязана дословно найтись в тексте сохранённой страницы, иначе импорт падает.

Запуск: python3 -m udobdom.sources ikea <url>… | quotes | check
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
PRIVATE = REPO / "var" / "home-practical" / "private" / "pages"
OUT = ROOT / "data" / "sources"
MANUAL = OUT / "manual"
PARSER = "hp-facts/1.0"
CARE_RX = re.compile(
    r"(?i)\b(wipe|wash|bleach|dry|iron|clean|vacuum|lint|microwave|freezer|dishwasher|"
    r"cutlery|cracks|heating|tighten|damage)"
)
STOP = ("Package details", "Assembly and documents", "Materials and care", "IKEA of Sweden", "Reviews")


def page_lines(raw: str) -> list[str]:
    t = re.sub(r"(?s)<script.*?</script>|<style.*?</style>|<noscript.*?</noscript>", "", raw)
    t = html.unescape(re.sub(r"<[^>]+>", "\n", t)).replace("\xa0", " ")
    return [re.sub(r"\s+", " ", x).strip() for x in t.split("\n") if x.strip()]


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("\xa0", " ").replace("’", "'")).strip().lower()


def _block(lines: list[str], head: str, stop=STOP) -> list[str]:
    for i, x in enumerate(lines):
        if x == head:
            out = []
            for y in lines[i + 1 :]:
                if any(y.startswith(s) for s in stop):
                    break
                out.append(y)
            if out:
                return out
    return []


def parse_ikea(raw: str, url: str) -> dict:
    lines = page_lines(raw)
    title = re.search(r"<title>(.*?)</title>", raw, re.S)
    name = html.unescape(title.group(1)).split(" - IKEA")[0].strip() if title else ""
    art = re.search(r"/p/[a-z0-9-]+-s?(\d{8})/", url)
    measures: dict[str, str] = {}
    for i, x in enumerate(lines):
        if x == "Weight & measurements":
            j = i + 1
            while j + 1 < len(lines) and not lines[j].startswith(STOP):
                k, v = lines[j], lines[j + 1]
                if re.fullmatch(r"[\d.,]+(?:–[\d.,]+)? ?(?:cm|mm|kg|l|m)\b.*", v) and len(k) < 60:
                    measures[k] = v
                    j += 2
                else:
                    j += 1
            if measures:
                break
    good = [x for x in _block(lines, "Good to know") if len(x) > 12]
    safety = [x for x in _block(lines, "Safety and compliance") if x.startswith(("WARNING", "CAUTION", "Warning"))]
    care_stop = ("Assembly and documents", "Package details", "Designer", "Good to know", "Materials and care")
    blocks = [_block(lines[i:], "Care", stop=care_stop) for i, x in enumerate(lines) if x == "Care"]
    lines_c = [x for x in min((b for b in blocks if b), key=len, default=[]) if x.endswith(".")]
    care = [x for x in lines_c if CARE_RX.search(x)]
    notes = [x for x in lines_c if not CARE_RX.search(x)]
    pdfs = sorted(
        set(re.findall(r"https://www\.ikea\.com/[a-z]{2}/[a-z]{2}/assembly_instructions/[^\"'\s]+\.pdf", raw))
    )
    return {
        "kind": "manufacturer",
        "publisher": "IKEA",
        "name": name,
        "article": f"{art.group(1)[:3]}.{art.group(1)[3:6]}.{art.group(1)[6:]}" if art else None,
        "measures": measures,
        "good_to_know": good,
        "safety": safety,
        "care": care,
        "notes": notes,
        "assembly_pdf": pdfs[:2],
    }


def _store(url: str, raw: bytes) -> tuple[str, str]:
    PRIVATE.mkdir(parents=True, exist_ok=True)
    PRIVATE.parent.chmod(0o700)
    sha = hashlib.sha256(raw).hexdigest()
    (PRIVATE / f"{sha[:16]}.html").write_bytes(raw)
    return sha, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def source_id(url: str) -> str:
    return "src-" + hashlib.sha1(url.encode()).hexdigest()[:10]


def fetch(url: str):
    from udobdom.net import Client

    st, final, body = Client(delay=2.0).get(url)
    if st != 200:
        raise RuntimeError(f"{url}: HTTP {st}")
    return final, body


def import_ikea(urls: list[str]) -> list[str]:
    OUT.mkdir(parents=True, exist_ok=True)
    done = []
    for u in urls:
        final, body = fetch(u)
        sha, at = _store(final, body)
        facts = parse_ikea(body.decode("utf-8", "replace"), final)
        if not facts["name"] or not (facts["measures"] or facts["good_to_know"]):
            raise RuntimeError(f"{final}: нет названия или фактов — страница не распознана")
        rec = {"id": source_id(final), "url": final, "fetched_at": at, "page_sha256": sha, "parser": PARSER, **facts}
        (OUT / f"{rec['id']}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n")
        done.append(rec["id"])
    return done


def import_quotes() -> list[str]:
    """Ручные цитаты: data/sources/manual/<имя>.yaml → data/sources/<id>.json, с дословной проверкой."""
    done = []
    for spec_path in sorted(MANUAL.glob("*.yaml")):
        spec = yaml.safe_load(spec_path.read_text())
        final, body = fetch(spec["url"])
        sha, at = _store(final, body)
        text = norm(" ".join(page_lines(body.decode("utf-8", "replace"))))
        missing = [q["quote"] for q in spec["quotes"] if norm(q["quote"]) not in text]
        if missing:
            raise RuntimeError(f"{spec_path.name}: цитаты не найдены на странице: {missing}")
        rec = {
            "id": source_id(final),
            "url": final,
            "fetched_at": at,
            "page_sha256": sha,
            "parser": PARSER,
            "kind": spec["kind"],
            "publisher": spec["publisher"],
            "name": spec["name"],
            "quotes": spec["quotes"],
        }
        (OUT / f"{rec['id']}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n")
        done.append(rec["id"])
    return done


def reparse() -> list[str]:
    """Пересобрать факты IKEA из сохранённых страниц (sha256 из записи) без сети."""
    done = []
    for path in sorted(OUT.glob("src-*.json")):
        rec = json.loads(path.read_text())
        if rec.get("publisher") != "IKEA":
            continue
        raw = (PRIVATE / f"{rec['page_sha256'][:16]}.html").read_bytes()
        if hashlib.sha256(raw).hexdigest() != rec["page_sha256"]:
            raise RuntimeError(f"{path.name}: сохранённая страница не совпадает с sha256")
        rec.update(parse_ikea(raw.decode("utf-8", "replace"), rec["url"]), parser=PARSER)
        path.write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n")
        done.append(rec["id"])
    return done


def load_all() -> dict[str, dict]:
    return {p.stem: json.loads(p.read_text()) for p in sorted(OUT.glob("src-*.json"))}


def fact_strings(rec: dict) -> list[str]:
    """Все утверждения источника одной строкой каждое — для проверки чисел в материалах."""
    out = [f"{k} {v}" for k, v in rec.get("measures", {}).items()]
    out += [rec.get("name", "")] + rec.get("good_to_know", []) + rec.get("safety", [])
    out += rec.get("care", []) + rec.get("notes", [])
    out += [q["quote"] for q in rec.get("quotes", [])]
    out += [str(v) for q in rec.get("quotes", []) for v in q.get("values", [])]
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["ikea", "quotes", "reparse", "check"])
    ap.add_argument("urls", nargs="*")
    a = ap.parse_args(argv)
    if a.cmd == "ikea":
        print(json.dumps(import_ikea(a.urls)))
    elif a.cmd == "reparse":
        print(json.dumps(reparse()))
    elif a.cmd == "quotes":
        print(json.dumps(import_quotes()))
    else:
        for k, r in load_all().items():
            print(k, r["publisher"], r["name"][:60], len(fact_strings(r)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
