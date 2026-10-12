"""Факты games-rpg из открытых и прочитанных страниц bg3.wiki (CC BY-NC-SA): персонажи, классы, механики, квесты, патч.

Текст источника не копируется: в репозиторий попадают URL, дата, sha256 и извлечённые поля; страницы — в var/games-rpg/private.
Запуск: python3 -m quest.sources import <тип> <url>… | check
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
PRIVATE = REPO / "var" / "games-rpg" / "private" / "pages"
OUT = ROOT / "data" / "sources"
PARSER = "grpg-facts/1.0"
ABIL = ["STR", "DEX", "CON", "INT", "WIS", "CHA"]


def tx(s: str) -> str:
    s = re.sub(r"(?s)<style.*?</style>|<script.*?</script>", "", s)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def _body(raw: str) -> str:
    i = raw.find("mw-parser-output")
    j = raw.find('class="printfooter"')
    return raw[i : j if j > i else len(raw)]


def parse(raw: str, url: str, kind: str) -> dict:
    title = tx(re.search(r"<title>(.*?)</title>", raw, re.S).group(1)).split(" - bg3.wiki")[0]
    body = _body(raw)
    paras = [re.sub(r"\s*\[\s*\d+\s*\]", "", tx(p)) for p in re.findall(r"<p>(.*?)</p>", body, re.S)]
    paras = [p for p in paras if len(p) > 60]
    heads = [(int(lv), tx(x).split("[")[0].strip()) for lv, x in re.findall(r"<h([234])[^>]*>(.*?)</h\1>", body, re.S)]
    if kind == "character":
        intro = [p for p in paras if re.search(r"\bis an? (?:Origin|recruitable)", p, re.I)]
        rest = [
            p
            for p in paras
            if p not in intro
            and not p.startswith(("Has proficiency", "Advantage on", "When rolling", "Gain proficiency"))
        ]
        paras = intro + rest
    rec = {
        "kind": "wiki",
        "publisher": "bg3.wiki",
        "game": "baldurs-gate-3",
        "type": kind,
        "name": title,
        "lead": paras[:2],
        "patches": sorted(set(re.findall(r"Patch \d+(?: Hotfix \d+)?", tx(body)))),
    }
    if kind == "character":
        m = re.search(r"STR DEX CON INT WIS CHA ((?:\d+ \([+-]?\d+\) ){6})", tx(raw))
        if m:
            nums = re.findall(r"(\d+) \(([+-]?\d+)\)", m.group(1))
            rec["abilities"] = {a: int(v) for a, (v, _) in zip(ABIL, nums, strict=False)}
    if kind == "class":
        i = raw.find("Class Progression")
        tb = re.search(r"(?s)<table.*?</table>", raw[i:]).group(0) if i >= 0 else ""
        rows, fi, bi = [], None, None
        for tr in re.findall(r"(?s)<tr.*?</tr>", tb):
            cells = [tx(c) for c in re.findall(r"(?s)<t[dh][^>]*>(.*?)</t[dh]>", tr)]
            if fi is None and "Features" in cells:
                fi = cells.index("Features")
                bi = next((i for i, c in enumerate(cells) if c.startswith("Proficiency")), None)
                hl = len(cells)
                continue
            if (
                fi is not None and bi is not None and len(cells) == hl - 1
            ):  # бонус объединён на несколько уровней (rowspan)
                cells.insert(bi, "")
            if fi is not None and cells and re.match(r"\d+(st|nd|rd|th)$", cells[0]) and len(cells) > fi:
                rows.append(
                    {
                        "level": int(re.match(r"\d+", cells[0]).group(0)),
                        "bonus": cells[bi] if bi is not None and bi < len(cells) else "",
                        "features": cells[fi],
                    }
                )
        bad = sum(1 for r in rows if re.fullmatch(r"[\d\s+-]*", r["features"]))
        rec["progression"] = rows if rows and bad <= 1 else []
        rec["progression_parsed"] = bool(rec["progression"])
    if kind == "quest":
        stages, w = [], False
        for lv, name in heads:
            if lv == 2:
                w = name == "Walkthrough"
            elif lv == 3 and w:
                stages.append(name)
        rec["stages"] = stages
    return rec


def source_id(url: str) -> str:
    return "src-" + hashlib.sha1(url.encode()).hexdigest()[:10]


def reparse() -> list[str]:
    done = []
    for path in sorted(OUT.glob("src-*.json")):
        rec = json.loads(path.read_text())
        raw = (PRIVATE / f"{rec['page_sha256'][:16]}.html").read_bytes()
        rec.update(parse(raw.decode("utf-8", "replace"), rec["url"], rec["type"]), parser=PARSER)
        path.write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n")
        done.append(rec["id"])
    return done


def import_pages(kind: str, urls: list[str]) -> dict:
    from quest.net import Client

    c = Client(delay=2.0)
    OUT.mkdir(parents=True, exist_ok=True)
    rep = {}
    for u in urls:
        st, final, body = c.get(u)
        if st != 200:
            rep[u] = f"HTTP {st}"
            continue
        facts = parse(body.decode("utf-8", "replace"), final, kind)
        if not facts["lead"]:
            rep[u] = "нет вводного текста"
            continue
        PRIVATE.mkdir(parents=True, exist_ok=True)
        PRIVATE.parent.chmod(0o700)
        sha = hashlib.sha256(body).hexdigest()
        (PRIVATE / f"{sha[:16]}.html").write_bytes(body)
        rec = {
            "id": source_id(final),
            "url": final,
            "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "page_sha256": sha,
            "parser": PARSER,
            **facts,
        }
        (OUT / f"{rec['id']}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n")
        rep[u] = rec["id"]
    return rep


def load_all() -> dict[str, dict]:
    return {p.stem: json.loads(p.read_text()) for p in sorted(OUT.glob("src-*.json"))}


def fact_text(rec: dict) -> str:
    parts = [rec["name"], *rec.get("lead", []), *rec.get("patches", []), *rec.get("stages", [])]
    parts += [f"{k} {v}" for k, v in rec.get("abilities", {}).items()]
    parts += [f"level {r['level']} {r['bonus']} {r['features']}" for r in rec.get("progression", [])]
    return " ".join(parts)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["import", "reparse", "check"])
    ap.add_argument("args", nargs="*")
    a = ap.parse_args(argv)
    if a.cmd == "import":
        rep = import_pages(a.args[0], a.args[1:])
    elif a.cmd == "reparse":
        rep = reparse()
    else:
        rep = {
            k: f"{r['type']} {r['name']} patches={r['patches']} ab={r.get('abilities')} "
            f"prog={len(r.get('progression', []))} st={r.get('stages')}"
            for k, r in load_all().items()
        }
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
