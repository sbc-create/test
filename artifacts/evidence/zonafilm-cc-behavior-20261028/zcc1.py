import json, collections
def dom(f):
    d = json.load(open(f)); x = [x for x in d["domains"] if x["domain"] == "zonafilm.cc"][0]
    return d, {m["key"]: m for m in x["measurements"]}
for f in ("artifacts/analytics/analytics-2026-10-27.json", "artifacts/analytics/analytics-2026-10-28.json"):
    d, M = dom(f); print("==", f, d["collected_at"], d["period"])
    for k in ("today_users", "today_search"):
        print(k, M[k]["title"]); [print("  ", [x.get("name") for x in r["dimensions"]], r["metrics"]) for r in M[k]["value"]]
    print("goals", M["goal_reaches"]["value"])
    # daily profile by date x device, people only
    agg = collections.defaultdict(lambda: [0, 0, 0, 0])  # visits, pv, bounces, dur*visits
    for r in M["daily_traffic_profile"]["value"]:
        dims = r["dimensions"]; date = dims[0]["name"]; dev = dims[2]["id"]; robot = dims[4]["id"]
        if robot != "no": continue
        v, br, depth, dur = r["metrics"]
        a = agg[(date, dev)]; a[0] += v; a[1] += v * depth; a[2] += v * br / 100; a[3] += v * dur
    for (date, dev), a in sorted(agg.items()):
        if date >= "2026-10-25":
            print("  ", date, dev, "visits", int(a[0]), "pv~", round(a[1]), "depth", round(a[1] / a[0], 2), "bounce%", round(100 * a[2] / a[0], 1), "dur", round(a[3] / a[0]))
    print("rows", len(M["daily_traffic_profile"]["value"]), "top_n", M["daily_traffic_profile"].get("top_n"))
