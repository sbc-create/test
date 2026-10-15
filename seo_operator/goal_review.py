"""Еженедельный разбор цели «≥ 5 000 реальных визитов в сутки на каждом сайте». Только чтение.

Источник — последняя выгрузка штатного сборщика (`analytics-collect`): посуточно
`daily_users` (люди, без роботов) и `daily_search` (органика по поисковым системам)
за окно 14daysAgo…yesterday, поисковые посадочные `search_landing_pages` за период
выгрузки. Окно делится на две полные недели по 7 суток (сутки — по часовому поясу
счётчика, Europe/Moscow).

Правила честности:
* отсутствующая строка — «нет строки», а не ноль; неизмеренный показатель — с причиной;
* последние двое суток окна помечаются предварительными (данные дорастают — замер 15.10:
  13.10 у yummyani.site вырос с 1 174 до 15 028 визитов между выгрузками);
* сутки, где визиты > 3 × медианы недели, отмечаются как всплеск для отдельной проверки;
* визиты, посетители и поисковые входы — раздельно; сумма посетителей сайтов не
  выдаётся за аудиторию сети; рост не приписывается правкам автоматически.

    python3 -m seo_operator.goal_review [--export var/analytics/cabinet-latest.json] [--out-dir docs/seo-operator/goal-review]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOAL = 5000


def _m(domain_rec: dict, key: str) -> dict:
    return next((m for m in domain_rec.get("measurements", []) if m.get("key") == key), {})


def daily(domain_rec: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for r in (_m(domain_rec, "daily_users").get("value") or []):
        dims = r.get("dimensions") or []
        if len(dims) >= 2 and dims[1].get("id") == "yes":
            continue
        e = out.setdefault(dims[0].get("name"), {})
        users, visits = (r.get("metrics") or [0, 0])[:2]
        e["users"] = e.get("users", 0) + (users or 0)
        e["visits"] = e.get("visits", 0) + (visits or 0)
    for r in (_m(domain_rec, "daily_search").get("value") or []):
        dims = r.get("dimensions") or []
        if len(dims) < 3 or dims[1].get("id") != "organic":
            continue
        eng = dims[2].get("id") or ""
        k = "yandex" if eng == "yandex" else "google" if eng == "google" else "other_search"
        e = out.setdefault(dims[0].get("name"), {})
        e[k] = e.get(k, 0) + ((r.get("metrics") or [0, 0])[1] or 0)
    return out


def review(export: dict) -> dict:
    period_end = dt.date.fromisoformat(export["collected_at"][:10]) - dt.timedelta(days=1)
    days = [(period_end - dt.timedelta(days=13 - i)).isoformat() for i in range(14)]
    weeks = {"w1": days[:7], "w2": days[7:]}
    sites = []
    for rec in export.get("domains", []):
        dm = rec["domain"]
        du = _m(rec, "daily_users")
        if not du.get("measured"):
            sites.append({"domain": dm, "measured": False, "reason": du.get("reason") or "нет показателя"})
            continue
        d = daily(rec)
        row = {"domain": dm, "measured": True, "rows": sum(1 for x in days if x in d)}
        for w, ds in weeks.items():
            have = [x for x in ds if x in d]
            vis = [d[x].get("visits", 0) for x in have]
            row[w] = {
                "days_with_row": len(have),
                "visits": sum(vis), "avg_per_day": round(sum(vis) / 7, 1),
                "days_ge_goal": sum(1 for v in vis if v >= GOAL),
                "yandex": sum(d[x].get("yandex", 0) for x in have),
                "google": sum(d[x].get("google", 0) for x in have),
                "spikes": [x for x in have if vis and len(vis) >= 3 and d[x].get("visits", 0) > 3 * max(statistics.median(vis), 1)],
            }
        lp = _m(rec, "search_landing_pages")
        if lp.get("measured"):
            agg: dict[str, float] = {}
            for r in lp.get("value") or []:
                dims = r.get("dimensions") or []
                p = dims[1].get("name") if len(dims) > 1 else dims[0].get("name")
                agg[p] = agg.get(p, 0) + (r.get("metrics") or [0])[0]
            tot = sum(agg.values()) or 0
            top = sorted(agg.values(), reverse=True)
            row["search_pages"] = {"pages": len(agg), "total": tot, "top1_share": round(top[0] / tot, 3) if tot else None,
                                   "top5_share": round(sum(top[:5]) / tot, 3) if tot else None,
                                   "top_n_limit": lp.get("top_n")}
        else:
            row["search_pages"] = {"unmeasured": lp.get("reason") or "нет показателя"}
        row["gap_avg_w2"] = round(max(GOAL - row["w2"]["avg_per_day"], 0), 1)
        sites.append(row)
    return {"collected_at": export["collected_at"], "weeks": {k: [v[0], v[-1]] for k, v in weeks.items()},
            "preliminary_days": days[-2:], "goal": GOAL, "sites": sites}


def pct(a: float, b: float) -> str:
    return "база 0" if not a else f"{(b - a) / a * 100:+.0f} %"


def markdown(r: dict) -> str:
    w1, w2 = r["weeks"]["w1"], r["weeks"]["w2"]
    L = [f"# Цель ≥ {r['goal']} визитов/сутки на каждом сайте — разбор недели {w2[0]}…{w2[1]}", "",
         f"Выгрузка {r['collected_at']} (штатный сборщик). Неделя 1 — {w1[0]}…{w1[1]}, неделя 2 — {w2[0]}…{w2[1]}; "
         f"сутки по часовому поясу счётчика (Europe/Moscow). **Предварительно**: {', '.join(r['preliminary_days'])} (данные дорастают). "
         "Нет строки — не ноль. Позиции, показы и индекс здесь не измеряются (Вебмастер/Search Console — отдельно).", "",
         "| Сайт | Визиты/сут н1 → н2 | Δ | Суток ≥ 5 000 (н2) | Органика Яндекс н1 → н2 | Органика Google н1 → н2 | Страниц с поиском (н2) | Доля топ-1 / топ-5 | Всплески | Разрыв до цели, визитов/сут |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for s in sorted(r["sites"], key=lambda x: -(x.get("w2", {}).get("avg_per_day", -1))):
        if not s.get("measured"):
            L.append(f"| {s['domain']} | не измерено: {s['reason'][:60]} | | | | | | | | |")
            continue
        a, b = s["w1"], s["w2"]
        sp = s["search_pages"]
        spages = f"{sp['pages']}" + (" (≥ предела выгрузки)" if sp.get("top_n_limit") and sp["pages"] >= sp["top_n_limit"] else "") if "pages" in sp else "не измерено"
        share = f"{sp['top1_share']:.0%} / {sp['top5_share']:.0%}" if sp.get("top1_share") is not None else "—"
        L.append(f"| {s['domain']} | {a['avg_per_day']:.0f} → {b['avg_per_day']:.0f} | {pct(a['avg_per_day'], b['avg_per_day'])} | {b['days_ge_goal']} | "
                 f"{a['yandex']:.0f} → {b['yandex']:.0f} | {a['google']:.0f} → {b['google']:.0f} | {spages} | {share} | "
                 f"{', '.join(x[5:] for x in a['spikes'] + b['spikes']) or '—'} | {s['gap_avg_w2']:.0f}"
                 + (" — **цель не подтверждена**: в неделе всплески, их происхождение проверяется отдельно" if b["spikes"] and b["days_ge_goal"] else "") + " |")
    return "\n".join(L) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--export", default=str(ROOT / "var/analytics/cabinet-latest.json"))
    ap.add_argument("--out-dir", default=str(ROOT / "docs/seo-operator/goal-review"))
    a = ap.parse_args(argv)
    r = review(json.load(open(a.export, encoding="utf-8")))
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stem = f"goal-review-{r['weeks']['w2'][1]}"
    (out / f"{stem}.md").write_text(markdown(r), encoding="utf-8")
    (ROOT / "var/analytics").mkdir(parents=True, exist_ok=True)
    (ROOT / "var/analytics" / f"{stem}.json").write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    print(out / f"{stem}.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
