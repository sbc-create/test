"""Факты games-survival из открытых и прочитанных страниц Minecraft Wiki: рецепты крафта (сетка, ингредиенты,
результат и количество), вводные сведения о блоках/предметах и биомах, версия игры.

Текст источника не копируется: в репозиторий попадают URL, дата, sha256 и извлечённые поля; страницы — в var/games-survival/private.
Запуск: python3 -m craft.sources import <тип> <url>… | reparse | check
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
PRIVATE = REPO / "var" / "games-survival" / "private" / "pages"
OUT = ROOT / "data" / "sources"
PARSER = "gsv-facts/1.1.2"  # 1.1.1: подписи спрайтов («COLOR _GRAY») не считаются абзацем


def tx(s: str) -> str:
    s = re.sub(r"(?s)<style.*?</style>|<script.*?</script>", "", s)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def _body(raw: str) -> str:
    i = raw.find("mw-parser-output")
    j = raw.find('class="printfooter"')
    return raw[i : j if j > i else len(raw)]


def _slot_items(slot: str) -> list[str]:
    # у слота результата перед «>» бывают атрибуты (data-minetip-text) — их пропускаем
    return [html.unescape(t) for t in re.findall(r'class="invslot-item[^"]*"[^>]*>.*?title="([^"]+)"', slot, re.S)]


def parse_recipes(raw: str) -> list[dict]:
    """Каждая сетка верстака: её строка таблицы, ячейка ингредиентов прямо перед сеткой, непустые слоты, результат и количество.
    Строки чужих таблиц (лут, вместимость) отбрасываются: в ингредиентах не бывает цифр, процентов и скобок."""
    out = []
    for m in re.finditer(r'<span class="mcui mcui-Crafting&#95;Table', raw):
        pos = m.start()
        tr = raw.rfind("<tr>", 0, pos)
        end = raw.find("</tr>", pos)
        if tr < 0 or end < 0:
            continue
        tds = re.findall(r"(?s)<td[^>]*>(.*?)</td>", raw[tr:pos] + "</td>")
        if len(tds) < 2:
            continue
        ingredients = tx(tds[-2])
        if not ingredients or re.search(r"[\d%{}\[\]]", ingredients) or len(ingredients) > 200:
            continue
        cell = raw[pos:end]
        inp = re.search(r'(?s)<span class="mcui-input">(.*?)<span class="mcui-arrow"', cell)
        outp = re.search(r'(?s)<span class="mcui-output">(.*)', cell)
        if not inp or not outp:
            continue
        chunks = re.split(r'<span class="invslot(?: animated)?">', inp.group(1))[1:]
        filled = [f for f in (_slot_items(c) for c in chunks) if f]
        result = _slot_items(outp.group(1))
        size = re.search(r"invslot-stacksize[^>]*>(?:<[^>]+>)*(\d+)", outp.group(1))
        if result and filled:
            out.append(
                {
                    "ingredients": ingredients,
                    "slots": len(filled),
                    "alternatives_in_first_slot": len(filled[0]),
                    "slot_items": [f[0] for f in filled],
                    "result": result[0],
                    "results": list(dict.fromkeys(result)),
                    "count": int(size.group(1)) if size else 1,
                }
            )
    return out


def parse(raw: str, url: str, kind: str) -> dict:
    title = tx(re.search(r"<title>(.*?)</title>", raw, re.S).group(1)).split(" – Minecraft Wiki")[0]
    body = _body(raw)
    paras = [re.sub(r"\s*\[\s*\d+\s*\]", "", tx(p)) for p in re.findall(r"<p>(.*?)</p>", body, re.S)]
    rec = {
        "kind": "wiki",
        "publisher": "Minecraft Wiki",
        "game": "minecraft",
        "type": kind,
        "name": title,
        "lead": [p for p in paras if len(p) > 60 and not re.search(r"\b[A-Z]{3,} _", p)][:2],
    }
    if kind in ("item", "block"):
        base = title.lower().split(" (")[0]
        rec["recipes"] = [r for r in parse_recipes(raw) if base in r["result"].lower() or r["result"].lower() in base]
    if kind == "version":
        cur = re.search(r"Java Edition (\d+(?:\.\d+)+) \(current\)", tx(raw))
        rec["java_current"] = cur.group(1) if cur else None
    return rec


def source_id(url: str) -> str:
    return "src-" + hashlib.sha1(url.encode()).hexdigest()[:10]


def import_pages(kind: str, urls: list[str]) -> dict:
    from craft.net import Client

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


def reparse() -> list[str]:
    done = []
    for path in sorted(OUT.glob("src-*.json")):
        rec = json.loads(path.read_text())
        raw = (PRIVATE / f"{rec['page_sha256'][:16]}.html").read_bytes()
        rec.update(parse(raw.decode("utf-8", "replace"), rec["url"], rec["type"]), parser=PARSER)
        path.write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n")
        done.append(rec["id"])
    return done


def load_all() -> dict[str, dict]:
    return {p.stem: json.loads(p.read_text()) for p in sorted(OUT.glob("src-*.json"))}


def fact_text(rec: dict) -> str:
    parts = [rec["name"], *rec.get("lead", []), rec.get("java_current") or ""]
    parts += [f"{r['ingredients']} {r['slots']} {r['result']} {r['count']}" for r in rec.get("recipes", [])]
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
            k: f"{r['type']} {r['name']} rec={[(x['ingredients'][:30], x['slots'], x['result'], x['count']) for x in r.get('recipes', [])][:3]} v={r.get('java_current')}"
            for k, r in load_all().items()
        }
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
