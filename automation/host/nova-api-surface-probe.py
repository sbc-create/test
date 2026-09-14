#!/usr/bin/env python3
"""Последние неопрошенные поверхности API: filters и search.

Если поставщик держит оценки, которых нет в списке и в detail, они обязаны
проявиться хотя бы как фасет фильтра («показать с оценкой выше N») или как
дополнительное поле в ответе поиска. Отсутствие и там закрывает вопрос
фактом, а не рассуждением.
"""
import json, os, sys
from pathlib import Path
sys.path.insert(0, "/srv/site-factory/repo")
from factory.lords import content_live

def токен():
    к = os.environ["CREDENTIALS_DIRECTORY"]
    и = os.environ.get("CDNVIDEOHUB_API_TOKEN_CREDENTIAL", "cdnvideohub_api_token")
    return (Path(к) / и).read_text(encoding="utf-8").strip()

c = content_live.load_live_contract()
f = content_live.Fetcher(contract=c, token=токен())
итог = {}

# 1. filters — есть ли фасет оценки
try:
    d = f.get_json(c.url("titles_filters"))
    ключи = sorted(d.keys()) if isinstance(d, dict) else []
    текст = json.dumps(d, ensure_ascii=False).lower()
    итог["titles_filters"] = {
        "top_level_keys": ключи[:40],
        "mentions_rating": [w for w in ("rating", "kinopoisk", "imdb", "score", "vote")
                            if w in текст],
        "payload_bytes": len(json.dumps(d, ensure_ascii=False)),
    }
except Exception as e:
    итог["titles_filters"] = {"error": repr(e)[:200]}

# 2. search — богаче ли ответ, чем список
try:
    url = c.url("titles_search") + "?query=%D0%BC%D0%B0%D1%82%D1%80%D0%B8%D1%86%D0%B0&limit=5"
    d = f.get_json(url)
    items = d.get("items") or d.get("data") or []
    поля = sorted({k for i in items if isinstance(i, dict) for k in i})
    итог["titles_search"] = {
        "returned": len(items),
        "item_fields": поля,
        "rating_fields": [k for k in поля if any(
            w in k.lower() for w in ("rating", "score", "vote"))],
        "sample_rating_values": [
            
            {k: i.get(k) for k in поля if "rating" in k.lower()}
            for i in items[:3]],
    }
except Exception as e:
    итог["titles_search"] = {"error": repr(e)[:200]}

итог["requests_made"] = f.requests_made
Path("/srv/site-factory/repo/var/lords/api-surface-probe.json").write_text(
    json.dumps(итог, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(итог, ensure_ascii=False, indent=2))
