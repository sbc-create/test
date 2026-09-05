"""Точное покрытие воспроизведения по всему каталогу Lords.

Знаменатель — все карточки в кэше каталога, из которого строятся страницы.
Не выборка и не первая страница API.
"""

import json
from collections import Counter
from pathlib import Path

BASE = Path("/srv/site-factory/repo/var/lords")
CACHE = BASE / "lords" / "catalog-cache"
PLAY = BASE / "playability.json"

AGGR_SUPPORTED = {"kp", "mali", "mdl"}


def load_play():
    try:
        return json.loads(PLAY.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def classify(t, play):
    pb = t.get("playback")
    ext = t.get("external_ids") or {}
    if not isinstance(pb, dict) or not pb:
        if not ext:
            return "MISSING_PROVIDER_ID"
        return "UNSUPPORTED_AGGREGATOR"
    aggr, tid = pb.get("aggregator"), pb.get("title_id")
    if not aggr or not tid:
        return "DESCRIPTOR_INVALID"
    if aggr not in AGGR_SUPPORTED:
        return "UNSUPPORTED_AGGREGATOR"
    rec = play.get(f"{aggr}:{tid}")
    if rec is None:
        return "DESCRIPTOR_OK_UNPROBED"
    if rec.get("playable") is False:
        return "PROVIDER_NOT_PLAYABLE"
    return "DESCRIPTOR_OK_PLAYABLE"


play = load_play()
итог = {}
for path in sorted(CACHE.glob("lords-*.json")):
    site = path.stem
    d = json.loads(path.read_text(encoding="utf-8"))
    items = d.get("items") or []
    n = len(items)
    причины = Counter()
    тип_причина = Counter()
    год_причина = Counter()
    агрегаторы = Counter()
    примеры = {}
    for t in items:
        c = classify(t, play)
        причины[c] += 1
        тип = (
            "сериал"
            if t.get("is_series")
            else ("фильм" if t.get("is_series") is False else "не указан")
        )
        тип_причина[(тип, c)] += 1
        g = t.get("year")
        бак = (
            "без года"
            if not isinstance(g, int)
            else "до 2000"
            if g < 2000
            else "2000-2015"
            if g < 2016
            else "2016+"
        )
        год_причина[(бак, c)] += 1
        pb = t.get("playback") or {}
        агрегаторы[pb.get("aggregator") or "нет"] += 1
        if c not in примеры and not c.startswith("DESCRIPTOR_OK"):
            примеры[c] = {
                "name": t.get("name"),
                "id": t.get("external_id"),
                "ext": t.get("external_ids"),
                "year": t.get("year"),
                "type": t.get("type"),
                "series": t.get("is_series"),
            }
    итог[site] = {
        "всего": n,
        "причины": dict(причины),
        "агрегаторы": dict(агрегаторы),
        "примеры": примеры,
        "по_типу": {f"{a}|{b}": v for (a, b), v in тип_причина.items()},
        "по_году": {f"{a}|{b}": v for (a, b), v in год_причина.items()},
    }

print("=" * 78)
print("ТОЧНОЕ ПОКРЫТИЕ ВОСПРОИЗВЕДЕНИЯ — ВЕСЬ КАТАЛОГ LORDS")
print("=" * 78)
for site, s in итог.items():
    n = s["всего"]
    c = s["причины"]
    есть = c.get("DESCRIPTOR_OK_PLAYABLE", 0) + c.get("DESCRIPTOR_OK_UNPROBED", 0)
    print(f"\n── {site}: карточек всего {n}")
    print(f"   с валидным дескриптором:      {есть:6}  {есть/n*100:5.1f}%")
    print(
        f"     из них проба «играет»:      {c.get('DESCRIPTOR_OK_PLAYABLE',0):6}  {c.get('DESCRIPTOR_OK_PLAYABLE',0)/n*100:5.1f}%"
    )
    print(
        f"     из них не проверялись:      {c.get('DESCRIPTOR_OK_UNPROBED',0):6}  {c.get('DESCRIPTOR_OK_UNPROBED',0)/n*100:5.1f}%"
    )
    print(f"   БЕЗ воспроизведения:          {n-есть:6}  {(n-есть)/n*100:5.1f}%")
    print("   по классам причин:")
    for k, v in sorted(c.items(), key=lambda x: -x[1]):
        print(f"     {k:26} {v:6}  {v/n*100:5.1f}%")
    print("   агрегаторы:", dict(sorted(s["агрегаторы"].items(), key=lambda x: -x[1])))
    if s["примеры"]:
        print("   примеры проблемных:")
        for k, ex in list(s["примеры"].items())[:5]:
            print(
                f"     {k}: {ex['name']!r} тип={ex['type']} сериал={ex['series']} год={ex['year']} ids={ex['ext']}"
            )

Path("/tmp/coverage.json").write_text(
    json.dumps(итог, ensure_ascii=False, indent=2), encoding="utf-8"
)
print("\nсводка: /tmp/coverage.json")
