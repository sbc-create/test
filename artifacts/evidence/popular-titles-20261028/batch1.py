"""Первая партия: 30 карточек на активных совместимых сайтах (28.10).

Отбор: статус matched*, воспроизведение есть, у направления есть активный сайт, где выпуск сейчас возможен
(Zona space/12 — игровые фильмы/сериалы и турецкие; animedia.icu — аниме и дунхуа). Порядок:
сначала спрос на наших сайтах (входы из поиска за 21–27.10, ≥ 5 — сигнал, меньше — шум),
затем показатель владельца. Полугодовой показатель — сигнал выбора, не измеренный спрос.
Дорамы (zonafilm.cc) и Lords в эту партию не входят: пауза/CI, не по приоритету.
"""
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
dec = json.loads((HERE / "match-decisions-20261028.json").read_text(encoding="utf-8"))["rows"]
dem = json.loads((HERE / "demand-20261028.json").read_text(encoding="utf-8"))["signals"]
SITE = {"live": "zonafilm.space", "turkish": "zonafilm12.site", "anime": "animedia.icu", "donghua": "animedia.icu"}

seen, cands = set(), []
for o in dec:
    e = o["entity"]
    if not e or not o["status"].startswith("matched") or not e["playable"] or o["direction"] not in SITE:
        continue
    if o["direction"] in ("anime", "donghua") and not e["in_anime_catalog"]:
        continue
    if e["id"] in seen:
        continue
    seen.add(e["id"])
    by_dom = {k.split(":")[0]: v for k, v in dem.get(e["slug"], {}).items() if k.endswith("search_landing_pages")}
    search = sum(by_dom.values())
    # Карточку улучшаем там, куда уже приходят из поиска (Чёрный клевер — 646 входов на zonafilm.space);
    # без спроса — на сайте направления. Исключённые и приостановленные домены сюда не попадают.
    active = {"zonafilm.space", "zonafilm12.site", "animedia.icu", "animeg0.site", "an1meg0.site"}
    hot = [d for d, v in sorted(by_dom.items(), key=lambda kv: -kv[1]) if d in active and v >= 5]
    cands.append({"n": o["n"], "title": o["title"], "slug": e["slug"], "direction": o["direction"],
                  "site": hot[0] if hot else SITE[o["direction"]], "search_by_domain_7d": by_dom, "our_search_visits_7d": search, "owner_pageviews": o["pageviews"]})

cands.sort(key=lambda c: (-(c["our_search_visits_7d"] >= 5), -c["our_search_visits_7d"] if c["our_search_visits_7d"] >= 5 else 0, -c["owner_pageviews"]))
batch = cands[:30]
(HERE / "batch1-20261028.json").write_text(json.dumps({
    "rule": __doc__.strip(), "eligible": len(cands), "batch": batch,
}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
for i, c in enumerate(batch, 1):
    print(i, c["n"], c["slug"], c["site"], c["our_search_visits_7d"], c["owner_pageviews"])
print("кандидатов всего:", len(cands))
