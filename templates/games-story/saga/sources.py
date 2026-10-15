"""Факты games-story из открытых и прочитанных страниц: Celeste Wiki (главы, стороны, клубники, чекпоинты),
Википедия (сведения об игре), YouTube oEmbed (проверка видео: существует, название, канал, встраивание).

Страницы — в var/games-story/private (0700, вне git); в репозитории — URL, дата, sha256 и извлечённые поля.
Запуск: python3 -m saga.sources chapters <url>… | collectible <url>… | video <id>… | check
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
PRIVATE = REPO / "var" / "games-story" / "private" / "pages"
OUT = ROOT / "data" / "sources"
PARSER = "gst-facts/1.0"


def tx(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def _body(raw: str) -> str:
    i = raw.find('class="mw-parser-output"')
    j = raw.find('class="printfooter"')
    return raw[i : j if j > i else len(raw)]


def _lead(body: str) -> str:
    for p in re.findall(r"<p>(.*?)</p>", body, re.S):
        t = tx(p)
        if len(t) > 60:
            return re.sub(r"\s*\[\s*\d+\s*\]", "", t)
    return ""


def berries(cell: str) -> list[dict]:
    """Ячейка «Strawberries»: пары (вид клубники по заголовку иконки, число)."""
    out = []
    for m in re.finditer(r'title="([^"]+)"[^>]*>.*?</a></span>\s*(?:<b>)?\s*(\d+)', cell, re.S):
        out.append({"kind": m.group(1), "count": int(m.group(2))})
    return out


def parse_chapter(raw: str, url: str) -> dict:
    title = tx(re.search(r"<title>(.*?)</title>", raw, re.S).group(1)).split(" - Celeste Wiki")[0]
    raw_rows = re.findall(r'<tr><th scope="row">(.*?)</th><td>(.*?)</td></tr>', raw, re.S)
    rows = [(tx(a), tx(b)) for a, b in raw_rows]
    berry_cells = [berries(b) for a, b in raw_rows if tx(a) == "Strawberries"]
    info, levels, cur = {}, [], None
    for k, v in rows:
        if k == "Level":
            cur = {"level": v}
            levels.append(cur)
        elif cur is not None:
            cur[k.lower()] = v
        else:
            info[k.lower()] = v
    body = _body(raw)
    heads = [
        (int(lv), tx(x).replace("[ edit | edit source ]", "").strip())
        for lv, x in re.findall(r"<h([234])[^>]*>(.*?)</h\1>", body, re.S)
    ]
    sides = {"A-Side", "B-Side", "C-Side"}
    checkpoints, in_a = [], False
    for lv, name in heads:
        if lv <= 3:
            in_a = name == "A-Side"
        elif lv == 4 and in_a:
            checkpoints.append(name)
    if not checkpoints:  # Farewell: участки — подзаголовки третьего уровня в «Gameplay», а не стороны
        g = False
        for lv, name in heads:
            if lv == 2:
                g = name == "Gameplay"
            elif lv == 3 and g and name not in sides:
                checkpoints.append(name)
    checkpoints = list(dict.fromkeys(checkpoints))
    chars = [c.strip() for c in re.sub(r"\(.*?\)", "", info.get("characters", "")).split("•") if c.strip()]
    return {
        "kind": "wiki",
        "publisher": "Celeste Wiki",
        "game": "celeste",
        "name": title,
        "chapter": int(info["chapter"]) if info.get("chapter", "").isdigit() else None,
        "strawberries": info.get("strawberries"),
        "berries": berry_cells[0] if berry_cells else [],
        "sides": info.get("sides"),
        "characters": [re.sub(r"\s*\(.*?\)\s*", " ", c).strip() for c in chars],
        "levels": [{"level": x["level"], "strawberries": x.get("strawberries")} for x in levels],
        "checkpoints": checkpoints,
        "lead": _lead(body),
    }


def parse_collectible(raw: str, url: str) -> dict:
    title = tx(re.search(r"<title>(.*?)</title>", raw, re.S).group(1)).split(" - Celeste Wiki")[0]
    body = _body(raw)
    paras = [re.sub(r"\s*\[\s*\d+\s*\]", "", tx(p)) for p in re.findall(r"<p>(.*?)</p>", body, re.S)]
    return {
        "kind": "wiki",
        "publisher": "Celeste Wiki",
        "game": "celeste",
        "name": title,
        "paragraphs": [p for p in paras if len(p) > 40][:4],
    }


def parse_video(raw: str, vid: str) -> dict:
    d = json.loads(raw)
    return {
        "kind": "video",
        "publisher": "YouTube oEmbed",
        "game": "celeste",
        "video_id": vid,
        "name": d["title"],
        "channel": d["author_name"],
        "channel_url": d["author_url"],
        "embeddable": "iframe" in d.get("html", ""),
    }


def source_id(url: str) -> str:
    return "src-" + hashlib.sha1(url.encode()).hexdigest()[:10]


def _store(raw: bytes) -> tuple[str, str]:
    PRIVATE.mkdir(parents=True, exist_ok=True)
    PRIVATE.parent.chmod(0o700)
    sha = hashlib.sha256(raw).hexdigest()
    (PRIVATE / f"{sha[:16]}.html").write_bytes(raw)
    return sha, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _import(urls, parse, check):
    from saga.net import Client

    c = Client(delay=2.0)
    OUT.mkdir(parents=True, exist_ok=True)
    rep = {}
    for u, key in urls:
        st, final, body = c.get(u)
        if st != 200:
            rep[u] = f"HTTP {st}"
            continue
        facts = parse(body.decode("utf-8", "replace"), key)
        problem = check(facts)
        if problem:
            rep[u] = problem
            continue
        sha, at = _store(body)
        sid = source_id(final)
        url = f"https://www.youtube.com/watch?v={key}" if facts["kind"] == "video" else final
        rec = {"id": sid, "url": url, "fetched_at": at, "page_sha256": sha, "parser": PARSER, **facts}
        (OUT / f"{sid}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n")
        rep[u] = sid
    return rep


def load_all() -> dict[str, dict]:
    return {p.stem: json.loads(p.read_text()) for p in sorted(OUT.glob("src-*.json"))}


def fact_text(rec: dict) -> str:
    parts = [rec.get("name", ""), rec.get("lead", ""), rec.get("strawberries") or "", rec.get("sides") or ""]
    parts += rec.get("checkpoints", []) + rec.get("characters", []) + rec.get("paragraphs", [])
    parts += [f"{x['level']} {x.get('strawberries') or ''}" for x in rec.get("levels", [])]
    parts += [f"{b['kind']} {b['count']}" for b in rec.get("berries", [])]
    if rec.get("chapter") is not None:
        parts.append(f"chapter {rec['chapter']}")
    return " ".join(parts)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["chapters", "collectible", "video", "check"])
    ap.add_argument("args", nargs="*")
    a = ap.parse_args(argv)
    if a.cmd == "chapters":
        rep = _import([(u, u) for u in a.args], parse_chapter, lambda f: None if f["lead"] else "нет вводного абзаца")
    elif a.cmd == "collectible":
        rep = _import([(u, u) for u in a.args], parse_collectible, lambda f: None if f["paragraphs"] else "нет текста")
    elif a.cmd == "video":
        rep = _import(
            [
                (f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={v}&format=json", v)
                for v in a.args
            ],
            parse_video,
            lambda f: None if f["embeddable"] else "видео не встраивается",
        )
    else:
        rep = {
            k: f"{r['kind']} {r['name'][:50]} ch={r.get('chapter')} cp={r.get('checkpoints')}"
            for k, r in load_all().items()
        }
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
