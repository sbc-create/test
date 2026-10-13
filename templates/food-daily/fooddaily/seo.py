"""SEO-слой: метаданные, директивы индексации и JSON-LD.

JSON-LD строится только из того, что видно на странице. Не выводятся:
aggregateRating, review, author, nutrition, image (у нас нет фотографий
с подтверждёнными правами — иллюстрации раздела фото блюда не являются),
video (готовых роликов нет).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from .views import Recipe, Site, iso_duration


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
        "recipeYield": f"{r.servings} порц." if r.servings else None,
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
        "keywords": ", ".join(t for t in r.tags) or None,
    }
    for k, v in (
        ("prepTime", r.prep_minutes),
        ("cookTime", r.cook_minutes),
        ("totalTime", r.total_minutes),
    ):
        if v:
            ld[k] = iso_duration(v)
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
        description = f"{description} Страница {page} из {pages}."
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
