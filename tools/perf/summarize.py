#!/usr/bin/env python3
"""Сводка визитов net-audit.js: медиана, худший, число измерений по сценариям.

summarize.py <visits.jsonl> [--md out.md] [--json out.json]
"""
import json
import statistics as st
import sys
from collections import defaultdict

путь = sys.argv[1]
md = sys.argv[sys.argv.index("--md") + 1] if "--md" in sys.argv else None
js = sys.argv[sys.argv.index("--json") + 1] if "--json" in sys.argv else None

визиты = [json.loads(l) for l in open(путь, encoding="utf-8") if l.strip()]
группы = defaultdict(list)
for в in визиты:
    группы[(в["domain"], в["scenario"], в["mode"])].append(в)


def ряд(значения):
    xs = [x for x in значения if isinstance(x, (int, float))]
    if not xs:
        return None
    return {"med": round(st.median(xs)), "worst": round(max(xs)), "n": len(xs)}


def взять(в, *путь):
    for к in путь:
        if not isinstance(в, dict):
            return None
        в = в.get(к)
    return в


итог = []
for (домен, сц, режим), вв in sorted(группы.items()):
    играли = [в for в in вв if в.get("click_at") is not None]
    содержимое = [в for в in играли if взять(в, "play", "play_to_content_first_frame") is not None]
    строка = {
        "domain": домен, "scenario": сц, "mode": режим, "visits": len(вв),
        "errors": [в.get("error") for в in вв if в.get("result") != "OK"],
        "release": sorted({в.get("release_id") or в.get("build_header") or "" for в in вв}),
        "ttfb": ряд(взять(в, "page", "ttfb") for в in вв),
        "lcp": ряд(взять(в, "page", "lcp") for в in вв),
        "ready": ряд(взять(в, "page", "ready") for в in вв),
        "shell": ряд(взять(в, "page", "shell") for в in вв),
        "player_ready": ряд(в.get("player_ready") for в in вв),
        "play_to_ad": ряд(взять(в, "play", "play_to_ad_first_frame") for в in играли),
        "ad_end_to_content": ряд(взять(в, "play", "ad_end_to_content_first_frame") for в in играли),
        "play_to_content": ряд(взять(в, "play", "play_to_content_first_frame") for в in играли),
        "switch_to_content": ряд(взять(в, "switch", "click_to_content_first_frame") for в in вв),
        "stalls": sum(взять(в, "play", "stall_count") or 0 for в in играли),
        "stall_ms": sum(взять(в, "play", "stall_ms") or 0 for в in играли),
        "has_player": sum(1 for в in вв if в.get("has_player")),
        "player_not_ready": sum(1 for в in вв if в.get("has_player") and в.get("player_ready") is None),
        "played": f"{len(содержимое)}/{len(играли)}" if играли else "",
        "own_failed": sum((взять(в, "net", "failed_own_or_player") or 0) for в in вв),
        "own_http_errors": sorted({e for в in вв for e in (взять(в, "net", "http_errors_own_or_player") or [])})[:5],
        "js_kb": ряд((взять(в, "net", "js_bytes_all") or 0) / 1024 for в in вв),
        "own_kb": ряд((взять(в, "net", "bytes", "own") or 0) / 1024 for в in вв),
        "tbt": ряд(взять(в, "page", "tbt") for в in вв),
    }
    итог.append(строка)

ф = lambda р: "—" if not р else f"{р['med']}/{р['worst']} ({р['n']})"
шапка = "| домен | сценарий | режим | TTFB | LCP | готовность | оболочка | плеер готов | Play→реклама | конец рекламы→кадр | Play→кадр | серия→кадр | буфер | играло | ошибки |"
строки = [шапка, "|" + "---|" * 15]
for с in итог:
    строки.append(f"| {с['domain']} | {с['scenario']} | {с['mode']} | {ф(с['ttfb'])} | {ф(с['lcp'])} | {ф(с['ready'])} | {ф(с['shell'])} | "
                  f"{ф(с['player_ready'])} | {ф(с['play_to_ad'])} | {ф(с['ad_end_to_content'])} | {ф(с['play_to_content'])} | "
                  f"{ф(с['switch_to_content'])} | {с['stalls']} / {с['stall_ms']} мс | {с['played']} | "
                  f"{len(с['errors'])} err, {с['player_not_ready']} плеер не готов, {с['own_failed']} сбоев сети |")
текст = "\n".join(строки)
print(текст)
if md:
    open(md, "w", encoding="utf-8").write("Значения: медиана/худший (число измерений), мс.\n\n" + текст + "\n")
if js:
    json.dump(итог, open(js, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
