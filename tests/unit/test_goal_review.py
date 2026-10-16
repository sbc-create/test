"""seo_operator.goal_review: две недели, раздельная органика, всплески, честный разрыв до цели."""
from seo_operator import goal_review


def _export(days_visits: dict[str, int], search: dict[str, tuple[int, int]] | None = None, measured: bool = True) -> dict:
    rows = [{"dimensions": [{"name": d}, {"id": "no"}], "metrics": [v, v]} for d, v in days_visits.items()]
    rows.append({"dimensions": [{"name": "2026-10-10"}, {"id": "yes"}], "metrics": [999, 999]})  # роботы — не считаются
    srows = []
    for d, (y, g) in (search or {}).items():
        srows.append({"dimensions": [{"name": d}, {"id": "organic"}, {"id": "yandex"}], "metrics": [y, y]})
        srows.append({"dimensions": [{"name": d}, {"id": "organic"}, {"id": "google"}], "metrics": [g, g]})
    return {"collected_at": "2026-10-15T05:00:00Z", "domains": [
        {"domain": "a.test", "measurements": [
            {"key": "daily_users", "measured": measured, "value": rows if measured else None, "reason": None if measured else "HTTP 429"},
            {"key": "daily_search", "measured": True, "value": srows},
            {"key": "search_landing_pages", "measured": True, "top_n": 200, "value": [
                {"dimensions": [{"id": "organic"}, {"name": "/x"}], "metrics": [80, 70]},
                {"dimensions": [{"id": "organic"}, {"name": "/y"}], "metrics": [20, 15]}]}]}]}


def test_two_weeks_gap_and_missing_rows_are_not_zero():
    visits = {f"2026-10-{d:02d}": 100 for d in range(1, 8)}
    visits.update({f"2026-10-{d:02d}": 200 for d in (8, 9, 10, 11, 12)})   # 13 и 14 — строк нет
    r = goal_review.review(_export(visits, {"2026-10-09": (30, 5)}))
    s = r["sites"][0]
    assert r["weeks"] == {"w1": ["2026-10-01", "2026-10-07"], "w2": ["2026-10-08", "2026-10-14"]}
    assert s["w1"]["avg_per_day"] == 100 and s["w2"]["days_with_row"] == 5
    assert s["w2"]["visits"] == 1000 and s["w2"]["yandex"] == 30 and s["w2"]["google"] == 5
    assert s["gap_avg_w2"] == round(5000 - 1000 / 7, 1)
    assert s["search_pages"]["pages"] == 2 and s["search_pages"]["top1_share"] == 0.8
    assert r["preliminary_days"] == ["2026-10-13", "2026-10-14"]


def test_goal_reached_only_by_spike_is_marked_unconfirmed():
    visits = {f"2026-10-{d:02d}": 1000 for d in range(1, 15)}
    visits["2026-10-14"] = 20000
    r = goal_review.review(_export(visits))
    s = r["sites"][0]
    assert s["w2"]["days_ge_goal"] == 1 and "2026-10-14" in s["w2"]["spikes"]
    assert "цель не подтверждена" in goal_review.markdown(r)


def test_unmeasured_site_is_reported_with_reason_not_zero():
    r = goal_review.review(_export({}, measured=False))
    assert r["sites"][0] == {"domain": "a.test", "measured": False, "reason": "HTTP 429"}
    assert "не измерено: HTTP 429" in goal_review.markdown(r)


def test_headless_browser_visits_are_not_real_visits():
    visits = {f"2026-10-{d:02d}": 1000 for d in range(1, 15)}
    visits["2026-10-14"] = 21000
    e = _export(visits)
    e["domains"][0]["measurements"].append({"key": "daily_traffic_profile", "measured": True, "value": [
        {"dimensions": [{"name": "2026-10-14"}, {"id": "direct"}, {"name": "PC"}, {"name": "HeadlessChrome"}], "metrics": [20000, 99, 1.0, 2]}]})
    s = goal_review.review(e)["sites"][0]
    assert s["w2"]["automated"] == 20000 and s["w2"]["days_ge_goal"] == 0 and s["w2"]["avg_per_day"] == 1000
