"""Спрос на наших сайтах по сопоставленным сущностям (сигнал приоритета первой партии).

Источник — var/analytics/cabinet-latest.json (сборщик 28.10 05:02Z, период 7daysAgo–yesterday):
Метрика search_landing_pages, landing_pages, popular_pages (верх 20 строк на домен — хвост не виден,
поэтому 0 здесь значит «не в верхних 20», а не «нет спроса»). Запросы Вебмастера в этой выгрузке —
окно 30.09–06.10 (известный дефект без явных дат, исправлен в сборщике), для приоритета не берутся.
"""
import json
import pathlib
import re

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
cab = json.loads((ROOT / "var/analytics/cabinet-latest.json").read_text(encoding="utf-8"))
dec = json.loads((HERE / "match-decisions-20261028.json").read_text(encoding="utf-8"))
slugs = {o["entity"]["slug"] for o in dec["rows"] if o["entity"]}

sig = {}
for dom in cab["domains"]:
    for m in dom.get("measurements", []):
        if m["key"] not in ("search_landing_pages", "landing_pages", "popular_pages") or not m.get("measured"):
            continue
        for row in m.get("value") or []:
            path = row["dimensions"][-1]["name"]
            mm = re.match(r"^/title/([^/]+)/", path)
            if mm and mm.group(1) in slugs:
                s = sig.setdefault(mm.group(1), {})
                key = f"{dom['domain']}:{m['key']}"
                s[key] = s.get(key, 0) + int(row["metrics"][0])

out = {"collected_at": cab["collected_at"], "period": cab["period"], "top_n_per_domain": 20, "signals": sig}
(HERE / "demand-20261028.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
for s, v in sorted(sig.items(), key=lambda kv: -sum(kv[1].values())):
    print(s, v)
