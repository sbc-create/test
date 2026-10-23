"""SEO-слой: метаданные, директивы индексации и JSON-LD.

JSON-LD строится только из того, что видно на странице. Не выводятся:
aggregateRating, review, author, nutrition, image (у нас нет фотографий
с подтверждёнными правами — иллюстрации раздела фото блюда не являются),
video (готовых роликов нет).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from .views import TAGS, Recipe, Site, iso_duration


@dataclass
class Meta:
    title: str
    description: str
    canonical: str | None  # None — у страницы нет собственного canonical (поиск, фильтры)
    index: bool  # желаемая индексация в production
    breadcrumbs: list[tuple[str, str]] = field(default_factory=list)
    jsonld: list[dict] = field(default_factory=list)
    prev: str | None = None
    next: str | None = None
    page_type: str = "page"

    def robots(self, site: Site) -> str:
        # preview закрыт целиком, независимо от типа страницы
        if not site.indexable:
            return "noindex, nofollow"
        return "index, follow" if self.index else "noindex, follow"

    def jsonld_html(self) -> list[str]:
        return [json.dumps(x, ensure_ascii=False).replace("</", "<\\/") for x in self.jsonld]


def plural(n: int, one: str, few: str, many: str) -> str:
    m = abs(n) % 100
    if 11 <= m <= 14:
        return many
    return one if m % 10 == 1 else few if 2 <= m % 10 <= 4 else many


def with_examples(head: str, titles: list[str], limit: int = 160) -> str:
    """Описание из данных: «<head>: название, название…» — столько названий, сколько помещается в limit."""
    out, shown = head, 0
    for t in titles:
        nxt = out + (": " if not shown else ", ") + t
        tail = "." if shown + 1 == len(titles) else " и другие."
        if len(nxt + tail) > limit:
            break
        out, shown = nxt, shown + 1
    if not shown:
        return head + "."
    return out + ("." if shown == len(titles) else " и другие.")


def breadcrumb_ld(site: Site, crumbs: list[tuple[str, str]]) -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": name, "item": site.abs(path)}
            for i, (name, path) in enumerate(crumbs)
        ],
    }


def recipe_ld(site: Site, r: Recipe) -> dict:
    ld = {
        "@context": "https://schema.org",
        "@type": "Recipe",
        "name": r.title,
        "description": r.d["intro"],
        "url": site.abs(r.url),
        "recipeCategory": r.category_label,
        "recipeYield": f"{r.yield_n} порц." if r.yield_n else None,
        "recipeIngredient": [i.jsonld for i, _ in r.ingredients],
        "recipeInstructions": [
            {
                "@type": "HowToStep",
                "position": n + 1,
                "text": s["text"],
                "url": site.abs(r.url) + f"#shag-{n + 1}",
            }
            for n, s in enumerate(r.d["steps"])
        ],
        "datePublished": (r.published_at or "")[:10] or None,
        "dateModified": (r.updated_at or "")[:10] or None,
        "inLanguage": "ru",
        "keywords": ", ".join(TAGS[t][0].lower() for t in r.tags if t in TAGS) or None,
    }
    for k, v in (
        ("prepTime", r.prep_minutes),
        ("cookTime", r.cook_minutes),
        ("totalTime", r.total_minutes),
    ):
        if v:
            ld[k] = iso_duration(v)
    if r.nutrition:  # только принятый расчёт; на странице показан тот же «≈ N ккал на порцию»
        n = r.nutrition
        ld["nutrition"] = {
            "@type": "NutritionInformation",
            "servingSize": "1 порция",
            "calories": f"{n['kcal']} ккал",
            **{
                key: f"{n[k]:g} г"
                for k, key in (("protein_g", "proteinContent"), ("fat_g", "fatContent"), ("carbs_g", "carbohydrateContent"))
                if isinstance(n.get(k), int | float)
            },
        }
    if r.image:  # только изображение с установленными правами (data/media/images.json)
        ld["image"] = [site.abs(f"/static/media/{r.image['file']}-{w}.webp") for w in r.image["widths"]]
    return {k: v for k, v in ld.items() if v is not None}


def recipe_meta(site: Site, r: Recipe) -> Meta:
    crumbs = [
        ("Главная", "/"),
        ("Рецепты", "/recepty/"),
        (r.category_label, f"/recepty/{r.category}/"),
        (r.title, r.url),
    ]
    return Meta(
        title=r.d["seo_title"],
        description=r.d["seo_description"],
        canonical=site.abs(r.url),
        index=True,
        breadcrumbs=crumbs,
        jsonld=[recipe_ld(site, r), breadcrumb_ld(site, crumbs)],
        page_type="recipe",
    )


def website_ld(site: Site) -> dict:
    """WebSite с поиском: поиск на сайте действительно есть (/poisk/?q=)."""
    return {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": site.cfg["name"],
        "url": site.abs("/"),
        "inLanguage": "ru",
        "potentialAction": {
            "@type": "SearchAction",
            "target": {"@type": "EntryPoint", "urlTemplate": site.abs("/poisk/") + "?q={search_term_string}"},
            "query-input": "required name=search_term_string",
        },
    }


def itemlist_ld(site: Site, urls: list[str]) -> dict:
    """ItemList для страницы-коллекции: только адреса материалов, видимых на ней."""
    return {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "itemListElement": [{"@type": "ListItem", "position": i + 1, "url": site.abs(u)} for i, u in enumerate(urls)],
    }


def article_meta(site: Site, a: dict) -> Meta:
    path = f"/sovety/{a['slug']}/"
    crumbs = [("Главная", "/"), ("Советы", "/sovety/"), (a["title"], path)]
    ld = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": a["title"],
        "description": a["description"],
        "datePublished": a["published"],
        "dateModified": a["updated"],
        "url": site.abs(path),
        "inLanguage": "ru",
    }
    return Meta(
        title=a["seo_title"],
        description=a["description"],
        canonical=site.abs(path),
        index=True,
        breadcrumbs=crumbs,
        jsonld=[ld, breadcrumb_ld(site, crumbs)],
        page_type="article",
    )


def fit_description(text: str, limit: int) -> str:
    """Описание не длиннее limit: целыми предложениями, если хоть одно помещается, иначе по слову с «…»."""
    if len(text) <= limit:
        return text
    out = ""
    for sent in re.split(r"(?<=[.!?])\s+", text):
        if len((out + " " + sent).strip()) > limit:
            break
        out = (out + " " + sent).strip()
    return out or text[: limit - 1].rsplit(" ", 1)[0].rstrip(",;:—") + "…"


def listing_meta(
    site: Site,
    *,
    title: str,
    description: str,
    path: str,
    crumbs: list[tuple[str, str]],
    page: int,
    pages: int,
    index: bool = True,
    page_type: str = "listing",
    items: list | None = None,
) -> Meta:
    def page_path(n: int) -> str:
        return path if n == 1 else f"{path}page/{n}/"

    own = page_path(page)
    if page > 1:
        title = f"{title} — страница {page}"
        tail = f" Страница {page} из {pages}."
        description = fit_description(description, 160 - len(tail)) + tail
    ld = [breadcrumb_ld(site, crumbs)] if len(crumbs) > 1 else []
    if items:
        ld.append(itemlist_ld(site, [r.url for r in items]))
    return Meta(
        title=title,
        description=description,
        canonical=site.abs(own),
        index=index,
        breadcrumbs=crumbs,
        jsonld=ld,
        prev=site.abs(page_path(page - 1)) if page > 1 else None,
        next=site.abs(page_path(page + 1)) if page < pages else None,
        page_type=page_type,
    )
