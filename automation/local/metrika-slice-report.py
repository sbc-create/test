#!/usr/bin/env python3
"""Срез Метрики по сети: отчёт и CSV из выгрузок штатного сборщика (analytics-collect). Только чтение.

    python3 automation/local/metrika-slice-report.py --out artifacts/analytics/slice-<метка> \\
        [--week1 W1.json --week2 W2.json] --daily D.json [--history E1.json E2.json ...] [--today T.json]

* --week1/--week2 — выгрузки за 2026-10-01…07 и 2026-10-08…14 (агрегаты периода: визиты,
  посетители, глубина, время, отказы, поисковые системы, посадочные из поиска);
* --daily — выгрузка, в которой есть daily_users/daily_search (окно 14daysAgo…yesterday);
* --history — более ранние выгрузки: по ним видно, как дорастают одни и те же дни (задержка данных);
* --today — выгрузка с today_users/today_search (неполный текущий день).

Неизмеренное остаётся неизмеренным (причина из выгрузки), а не нулём. Сумма посетителей по
сайтам не выдаётся за уникальную аудиторию сети. При нулевой базе процент не считается.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
W1 = ("2026-10-01", "2026-10-07")
W2 = ("2026-10-08", "2026-10-14")
import sys  # noqa: E402
sys.path.insert(0, str(ROOT))
from seo_operator.tech_run import ВНЕ_ПРОДВИЖЕНИЯ  # noqa: E402 — восемь новых витрин K2 (реестр фабрики)

K2_NEW = sorted(ВНЕ_ПРОДВИЖЕНИЯ)


def load(p: str | None) -> dict | None:
    return json.load(open(p, encoding="utf-8")) if p else None


def meas(export: dict | None, domain: str) -> dict[str, dict]:
    if not export:
        return {}
    for d in export.get("domains", []):
        if d.get("domain") == domain:
            return {m["key"]: m for m in d.get("measurements", [])}
    return {}


def val(m: dict | None):
    return m.get("value") if m and m.get("measured") else None


def why(m: dict | None) -> str:
    if not m:
        return "нет в выгрузке"
    return "" if m.get("measured") else (m.get("reason") or "не измерено")[:90]


def daily(export: dict | None, domain: str) -> dict[str, dict]:
    """{дата: {visits, users, search_yandex, search_google, search_other}} — только люди, не роботы."""
    out: dict[str, dict] = {}
    m = meas(export, domain)
    for r in val(m.get("daily_users")) or []:
        dims = r.get("dimensions") or []
        if len(dims) >= 2 and (dims[1].get("id") == "yes"):
            continue  # роботы
        day = dims[0].get("name")
        users, visits = (r.get("metrics") or [None, None])[:2]
        e = out.setdefault(day, {})
        e["users"] = (e.get("users") or 0) + (users or 0)
        e["visits"] = (e.get("visits") or 0) + (visits or 0)
    for r in val(m.get("daily_search")) or []:
        dims = r.get("dimensions") or []
        if len(dims) < 3 or dims[1].get("id") != "organic":
            continue
        day, eng = dims[0].get("name"), (dims[2].get("id") or "")
        visits = (r.get("metrics") or [None, None])[1]
        key = "search_yandex" if eng == "yandex" else "search_google" if eng == "google" else "search_other"
        e = out.setdefault(day, {})
        e[key] = (e.get(key) or 0) + (visits or 0)
    return out


def engines(m: dict | None) -> tuple[float | None, float | None]:
    v = val(m)
    if v is None:
        return None, None
    y = sum(r["metrics"][0] for r in v if "yandex" in ((r.get("dimensions") or [{}])[0].get("id") or ""))
    g = sum(r["metrics"][0] for r in v if "google" in ((r.get("dimensions") or [{}])[0].get("id") or ""))
    return y, g


def delta(a, b) -> tuple[str, str]:
    if a is None or b is None:
        return "—", "—"
    d = b - a
    pct = "база 0" if a == 0 else f"{d / a * 100:+.1f}%"
    return f"{d:+.0f}" if abs(d) >= 1 or d == 0 else f"{d:+.2f}", pct


def dates(a: str, b: str) -> list[str]:
    x, y = dt.date.fromisoformat(a), dt.date.fromisoformat(b)
    return [(x + dt.timedelta(days=i)).isoformat() for i in range((y - x).days + 1)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--week1")
    ap.add_argument("--week2")
    ap.add_argument("--daily", required=True)
    ap.add_argument("--history", nargs="*", default=[])
    ap.add_argument("--today")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    w1, w2, dl, td = load(a.week1), load(a.week2), load(a.daily), load(a.today)
    hist = [load(p) for p in a.history]
    reg = json.load(open(ROOT / "config/analytics.json", encoding="utf-8"))["properties"]

    # ---- охват счётчиков
    cov = []
    for p in reg:
        pas = val(meas(dl, p["domain"]).get("counter_passport")) or {}
        cov.append({"domain": p["domain"], "site_id": p.get("site_id"), "counter_id": p.get("counter_id") or "",
                    "counter_state": p.get("counter_state"), "analytics_enabled": p.get("analytics_enabled"),
                    "allowed_hosts": " ".join(p.get("allowed_hosts") or []),
                    "passport_site": pas.get("site", ""), "passport_status": pas.get("status", ""),
                    "shared_counter": sum(1 for q in reg if q.get("counter_id") and q.get("counter_id") == p.get("counter_id")) > 1})
    with open(out / "coverage.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(cov[0].keys()))
        w.writeheader()
        w.writerows(cov)

    # ---- суточная динамика (1–14.10 по возможности)
    days = dates("2026-10-01", "2026-10-14")
    rows = []
    for p in reg:
        dd = daily(dl, p["domain"])
        for day in days:
            e = dd.get(day)
            rows.append({"domain": p["domain"], "date": day,
                         "visits": "" if not e else e.get("visits", ""), "users": "" if not e else e.get("users", ""),
                         "search_yandex": "" if not e else e.get("search_yandex", 0),
                         "search_google": "" if not e else e.get("search_google", 0),
                         "status": "измерено" if e else ("нет данных за день в выгрузке" if dd else "не измерено: " + why(meas(dl, p["domain"]).get("daily_users")))})
    with open(out / "daily.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # ---- полнота: как дорастают одни и те же дни между выгрузками
    lag = []
    for p in reg:
        series = [(e.get("collected_at"), daily(e, p["domain"])) for e in hist + [dl] if e]
        for day in days:
            vals = [(at, s.get(day, {}).get("visits")) for at, s in series if s.get(day, {}).get("visits") is not None]
            if len(vals) >= 2 and vals[-1][1] != vals[0][1]:
                lag.append({"domain": p["domain"], "date": day, "first_at": vals[0][0], "first": vals[0][1],
                            "last_at": vals[-1][0], "last": vals[-1][1]})
    with open(out / "late-data.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["domain", "date", "first_at", "first", "last_at", "last"])
        w.writeheader()
        w.writerows(lag)

    # ---- недели: агрегаты периода (если есть) или сумма суток (визиты, поиск)
    keys = ("visits", "visitors", "pageviews", "search_yandex", "search_google", "bounce_rate", "page_depth", "avg_visit_duration")
    week = []
    for p in reg:
        r = {"domain": p["domain"]}
        dd = daily(dl, p["domain"])
        for tag, wx, (a1, a2) in (("w1", w1, W1), ("w2", w2, W2)):
            m = meas(wx, p["domain"])
            ds = dates(a1, a2)
            have = [d for d in ds if d in dd]
            src = "период" if wx else ("сутки" if have else "")
            visits = val(m.get("visits")) if wx else (sum(dd[d].get("visits", 0) for d in have) if have else None)
            depth = val(m.get("page_depth")) if wx else None
            y, g = engines(m.get("search_engines")) if wx else (
                (sum(dd[d].get("search_yandex", 0) for d in have), sum(dd[d].get("search_google", 0) for d in have)) if have else (None, None))
            r.update({f"{tag}_source": src, f"{tag}_days": len(ds) if wx else len(have),
                      f"{tag}_visits": visits, f"{tag}_visitors": val(m.get("visitors")) if wx else None,
                      f"{tag}_pageviews": round(visits * depth) if (visits is not None and depth is not None) else None,
                      f"{tag}_search_yandex": y, f"{tag}_search_google": g,
                      f"{tag}_bounce_rate": val(m.get("bounce_rate")) if wx else None,
                      f"{tag}_page_depth": depth, f"{tag}_avg_visit_duration": val(m.get("avg_visit_duration")) if wx else None,
                      f"{tag}_note": why(m.get("visits")) if wx else ("" if have else "не измерено")})
        for k in keys:
            r[f"d_{k}"], r[f"pct_{k}"] = delta(r.get(f"w1_{k}"), r.get(f"w2_{k}"))
        week.append(r)
    with open(out / "weeks.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(week[0].keys()))
        w.writeheader()
        w.writerows(week)

    # ---- сегодня (неполный день)
    today = []
    for p in reg:
        m = meas(td, p["domain"])
        today.append({"domain": p["domain"], "today_users": json.dumps(val(m.get("today_users")), ensure_ascii=False)[:200] if td else "",
                      "note": why(m.get("today_users")) if td else "выгрузки за сегодня нет"})
    json.dump({"generated_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
               "inputs": {"week1": a.week1, "week2": a.week2, "daily": a.daily, "history": a.history, "today": a.today},
               "collected_at": {k: (x or {}).get("collected_at") for k, x in (("week1", w1), ("week2", w2), ("daily", dl), ("today", td))},
               "k2_new_domains_in_registry": [d for d in K2_NEW if d in {p["domain"] for p in reg}],
               "today": today}, open(out / "meta.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
