"""Классификация реестра URL и подсчёт по типам страниц.

Тип определяется правилом хоста: сначала по имени карты сайта (самый
сильный признак — так сайт сам группирует страницы), затем по пути.
Каждая запись хранит сработавшее правило, чтобы выборочная проверка могла
показать, какое правило ошибается.

Не считаются отдельными страницами: AMP/print-версии, параметры сортировки
и пагинация списков (тип `listing_page`, в «прочие» не попадает).
"""

from __future__ import annotations

import collections
import gzip
import json
import re
import urllib.parse
from pathlib import Path

from .inventory import CRAWL_ROOT

TYPES = ("recipe", "article", "category", "tag", "video", "other", "unknown")

# (условие по карте сайта | None, условие по пути+query | None, тип)
RULES: dict[str, list[tuple[str | None, str | None, str]]] = {
    "1000-menu": [
        (None, r"^/cooking/\d+-", "recipe"),
        (None, r"^/(meals|catalog|table)/", "tag"),
        (None, r"^/advice/", "article"),
        (None, r"^/cooking/[a-z-]+$", "category"),
    ],
    "eda-rambler": [
        (r"RecipePagesGroup", None, "recipe"),
        (r"VideoTutorialPagesGroup", None, "video"),
        (r"ArticlePagesGroup|JournalPagesGroup", None, "article"),
        (
            r"RecipeCategoryPagesGroup|CuisinePagesGroup|CookingMethodPagesGroup|DietPagesGroup",
            None,
            "category",
        ),
        (r"RecipeGroupPagesGroup|EventPagesGroup", None, "tag"),
        (None, r"^/recepty/ingredienty/", "tag"),
        (None, r"^/recepty/[a-z-]+/ingredienty/", "tag"),  # рубрика × продукт
        (None, r"^/recepty/[a-z-]+/[a-z0-9-]+-\d+$", "recipe"),
        (None, r"^/media/", "article"),
        (None, r"^/recepty/[a-z-]+$", "category"),
        (
            None,
            r"^/(wiki|chefs|recepty/chefs|restaurants|instrumenty|artwork|specproekty)/",
            "other",
        ),
    ],
    "food-ru": [
        (r"/recipes-\d+\.xml", None, "recipe"),
        (r"/articles-\d+\.xml", None, "article"),
        (r"/headings-\d+\.xml", None, "category"),
        (r"/(recipes-tags|tags|filters)-\d+\.xml", None, "tag"),
        (r"/(products|news|about)-\d+\.xml", None, "other"),
    ],
    "gastronom": [
        (r"sitemaps_recipes_", None, "recipe"),
        (r"sitemaps_articles_", None, "article"),
        (r"sitemaps_groups_", None, "tag"),
        (r"sitemaps_products_|sitemaps_news", None, "other"),
        (None, r"^/recipe/\d+", "recipe"),
        (None, r"^/(text)/", "article"),
        (None, r"^/(group)/", "tag"),
        (None, r"^/(news|product|user)/", "other"),
        (None, r"^/[a-z-]+-\d+$", "category"),  # рубрики журнала
    ],
    "menunedeli": [
        (r"/recipe-sitemap\d*\.xml", None, "recipe"),
        (r"/post-sitemap\d*\.xml", None, "article"),
        (r"/category-sitemap\d*\.xml", None, "category"),
        (r"/post_tag-sitemap\d*\.xml", None, "tag"),
        (r"/(page|addl)-sitemap\d*\.xml", None, "other"),
    ],
    "russianfood": [
        (None, r"^/recipes/recipe\.php\?rid=\d+$", "recipe"),
        (None, r"^/recipes/bytype/\?fid=\d+$", "category"),
        (
            None,
            r"^/recipes/bytype/\?fid=\d+((,|%2C)\d+)+$",
            "tag",
        ),  # сочетание рубрик (запятая после нормализации — %2C)
        (None, r"^/themes/(\?theme_id=\d+)?$", "tag"),
        (None, r"^/reading/", "article"),
        (None, r"^/(blogs|forum|entertainment|subscribe|search|users)/", "other"),
        (None, r"[?&](sort|page)=", "listing_page"),
    ],
    "povar": [
        (None, r"^/recipes/[a-z0-9_]+-\d+\.html$", "recipe"),
        (None, r"^/list/[a-z0-9_]+/$", "category"),
        (None, r"^/list/[a-z0-9_]+/\d+/$", "listing_page"),  # пагинация рубрики, canonical → 1-я
        (None, r"^/menu/[a-z0-9_]+/$", "tag"),
        (None, r"^/mostnew/", "listing_page"),
        (None, r"^/(wiki|articles)/", "article"),
        (None, r"^/video/", "video"),
    ],
    "iamcook": [
        (None, r"^/showrecipe/\d+$", "recipe"),
        (None, r"^/(section|showsubsection)/[^/]+$", "category"),
        (None, r"^/(section|showsubsection|theme|country|ingredients)/[^/]+/\d+$", "listing_page"),
        (None, r"^/(theme|country|ingredients|event)/", "tag"),
        (None, r"^/(blog|digest)/", "article"),
        (None, r"^/(user|ug)/", "other"),
    ],
    "povarenok": [
        (None, r"^/recipes/show/\d+/$", "recipe"),
        (None, r"[?&]searchid=", "listing_page"),  # отбор внутри рубрики
        (None, r"^/recipes/(dishes/[a-z]+|category/\d+)/$", "category"),
        (None, r"^/recipes/(kitchen|destiny|ingredient)/\d+/?$", "tag"),
        (None, r"/~\d+/$", "listing_page"),
        (None, r"^/(articles|tips)/", "article"),
        (None, r"^/video/", "video"),
    ],
    "edimdoma": [
        (None, r"[?&]page=\d+", "listing_page"),  # пагинация лент и тегов
        (None, r"^/retsepty/\d+-[a-z0-9-]+$", "recipe"),
        (None, r"^/retsepty/tags/\d+-", "tag"),
        (None, r"^/retsepty$", "category"),
        (None, r"^/(stati|articles|kulinarnye-stati)/", "article"),
        (None, r"^/video/", "video"),
        (None, r"^/users/", "other"),
    ],
}

NON_PAGE = re.compile(r"(/amp/|[?&](amp|print)=|/print/?$|/rating/|/comments)", re.I)


def classify(host_id: str, url: str, sitemap: str | None) -> tuple[str, str]:
    p = urllib.parse.urlsplit(url)
    pq = (p.path or "/") + (("?" + p.query) if p.query else "")
    if NON_PAGE.search(pq):
        return "variant", "non_page_variant"
    for i, (sm_rx, path_rx, typ) in enumerate(RULES.get(host_id, [])):
        if sm_rx and not (sitemap and re.search(sm_rx, sitemap)):
            continue
        if path_rx and not re.search(path_rx, pq):
            continue
        return typ, f"{host_id}#{i}"
    if pq in ("/", ""):
        return "other", "home"
    if re.fullmatch(r"/[a-z-]+(/[a-z-]+)?/?", pq):
        return "other", "static_section"
    return "unknown", "no_rule"


def host_counts(host_id: str, *, export: Path | None = None) -> dict:
    path = CRAWL_ROOT / host_id / "urls.jsonl"
    if not path.exists():
        return {"host": host_id, "unique_urls": None}
    seen: dict[str, dict] = {}
    raw = 0
    for line in path.open():
        raw += 1
        d = json.loads(line)
        u = d["url"]
        if u in seen:
            # повтор в другой карте/странице — тот же URL, источник дописываем
            seen[u].setdefault("also_in", 0)
            seen[u]["also_in"] += 1
            continue
        typ, rule = classify(host_id, u, d.get("sitemap"))
        if d.get("has_video") and typ not in ("video",):
            d["sitemap_video"] = True
        seen[u] = {
            "url": u,
            "source_url": d["source_url"],
            "type": typ,
            "rule": rule,
            "discovered_via": d["discovered_via"],
            "sitemap": d.get("sitemap"),
            "found_on": d.get("found_on"),
            "lastmod": d.get("lastmod"),
            "sitemap_video": d.get("has_video", False),
            # поля проверки страницы — заполняются только выборкой verify
            "http_status": None,
            "canonical": None,
            "indexable": None,
        }
    c = collections.Counter(v["type"] for v in seen.values())
    if export:
        export.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(export, "wt") as f:
            for v in seen.values():
                f.write(json.dumps(v, ensure_ascii=False) + "\n")
    return {
        "host": host_id,
        "raw_records": raw,
        "unique_urls": len(seen),
        "pages_counted": len(seen) - c["variant"] - c["listing_page"],
        **{t: c[t] for t in TYPES},
        "listing_page": c["listing_page"],
        "variant": c["variant"],
        "with_sitemap_video": sum(1 for v in seen.values() if v["sitemap_video"]),
    }
