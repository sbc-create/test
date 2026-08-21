"""Рендер сайта из site package, темы и матрицы индексируемости.

Матрица — вход, а не отчёт: тип страницы без записи в ней не рендерится.
Контент не генерируется: отсутствующий обязательный факт (в том числе alt изображения)
снимает конкретный материал с публикации и попадает в отчёт как пропуск с причиной.
"""
from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined

from factory import ads as ads_mod
from factory import vk as vk_mod
from factory.errors import BlockedInput, BlockedSeo
from factory.paths import PATHS


@dataclass
class Route:
    path: str
    page_type: str
    status: int = 200
    indexable: bool = True
    robots: str = ""
    canonical: str | None = None
    in_sitemap: bool = False
    file: str | None = None
    title: str = ""
    h1: str = ""
    description: str = ""
    lastmod: str | None = None
    parent: str | None = None
    page_number: int = 1

    def as_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class Redirect:
    source: str
    target: str
    status: int = 301

    def as_dict(self) -> dict:
        return {"source": self.source, "target": self.target, "status": self.status}


@dataclass
class RenderResult:
    routes: list[Route] = field(default_factory=list)
    redirects: list[Redirect] = field(default_factory=list)
    skipped: list[dict] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)

    def skip(self, entry: dict) -> None:
        """Пропуск материала фиксируется ровно один раз, но никогда не замалчивается."""
        key = (entry.get("id"), entry.get("reason"))
        if key not in {(s.get("id"), s.get("reason")) for s in self.skipped}:
            self.skipped.append(entry)


def _slugify_ok(value: str) -> bool:
    return bool(re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", value or ""))


class SiteRenderer:
    def __init__(self, package: dict, site_id: str, *, output: Path, matrix: dict | None = None,
                 vk_contract: dict | None = None, ads_contract: dict | None = None) -> None:
        self.pkg = package
        self.site_id = site_id
        self.out = output
        self.public = output / "public"
        self.matrix = matrix or yaml.safe_load((PATHS.knowledge / "SEO_INDEXABILITY_MATRIX.yaml").read_text(encoding="utf-8"))
        self.page_types = {p["id"]: p for p in self.matrix.get("page_types", [])}
        self.url_policy = self.matrix.get("url_policy", {})
        self.result = RenderResult()
        self.content = self._load_content()
        self.player = vk_mod.build_player(package, vk_contract, self._video_catalog())
        self.ads = ads_mod.build_ads(package, ads_contract)
        theme_dir = PATHS.themes / package["theme_ref"]
        if not theme_dir.exists():
            raise BlockedInput(f"Тема «{package['theme_ref']}» отсутствует.", field="theme_ref", required_input="Одобренный theme pack в themes/")
        self.theme_dir = theme_dir
        self.env = Environment(
            loader=FileSystemLoader(str(theme_dir / "templates")),
            autoescape=True,
            undefined=StrictUndefined,
            trim_blocks=False,
            lstrip_blocks=False,
        )
        self.base = package["canonical_url"].rstrip("/")
        #: Классы, которые заменяют инлайновые style: CSP запрещает style-src 'unsafe-inline',
        #: и ослаблять политику ради вёрстки нельзя.
        self._dynamic_css: dict[str, str] = {}
        self.per_page = int((package.get("seo") or {}).get("items_per_page") or 12)

    # ------------------------------------------------------------------ входные данные
    def _site_file(self, ref: str) -> Path | None:
        if not ref:
            return None
        base = PATHS.site_dir(self.site_id).resolve()
        path = (base / ref).resolve()
        return path if str(path).startswith(str(base)) and path.exists() else None

    def _load_content(self) -> dict:
        ref = (self.pkg.get("content_source") or {}).get("catalog_ref")
        if not ref:
            return {"categories": [], "titles": [], "collections": [], "articles": []}
        path = self._site_file(ref)
        if not path:
            raise BlockedInput(f"Каталог контента «{ref}» не найден.", field="content_source.catalog_ref", required_input="Переданная выгрузка каталога")
        data = json.loads(path.read_text(encoding="utf-8")) if path.suffix == ".json" else yaml.safe_load(path.read_text(encoding="utf-8"))
        for key in ("categories", "titles", "collections", "articles"):
            data.setdefault(key, [])
        return data

    def _video_catalog(self) -> dict:
        catalog: dict[str, dict] = {}
        for item in (self._load_content().get("titles") or []):
            if item.get("video_ref"):
                catalog[item["video_ref"]] = {"availability": item.get("availability", "unavailable")}
            for season in item.get("seasons") or []:
                for ep in season.get("episodes") or []:
                    if ep.get("video_ref"):
                        catalog[ep["video_ref"]] = {"availability": ep.get("availability", "unavailable")}
        return catalog

    # ------------------------------------------------------------------ утилиты
    def abs_url(self, path: str) -> str:
        return self.base + path

    def _policy(self, page_type: str) -> dict:
        policy = self.page_types.get(page_type)
        if not policy:
            raise BlockedSeo(
                f"Тип страницы «{page_type}» отсутствует в матрице индексируемости — рендер запрещён.",
                field="knowledge/SEO_INDEXABILITY_MATRIX.yaml",
                required_input="Добавь тип страницы в матрицу через /research-freeze",
                blocks_stage="BUILDING",
            )
        return policy

    def _tmpl(self, name: str, page: dict) -> str:
        return self.env.get_template(name).render(site=self.site_context, page=page)

    def _write(self, route_path: str, content: str) -> str:
        rel = route_path.strip("/")
        target = self.public / rel / "index.html" if rel else self.public / "index.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return str(target.relative_to(self.public))

    def _image(self, item: dict, *, required_for: str) -> dict | None:
        image = item.get("image")
        if not image:
            return None
        alt = (image.get("alt") or "").strip()
        if not alt:
            self.result.skip({
                "id": item.get("id") or item.get("slug"),
                "reason": "У изображения нет alt в переданных данных — публикация материала заблокирована (§9).",
                "required_input": "alt из переданного контентного пакета",
                "context": required_for,
            })
            return None
        return {
            "src": image.get("src", ""),
            "alt": alt,
            "width": image.get("width", 640),
            "height": image.get("height", 360),
        }

    def _publishable(self, item: dict, context: str) -> bool:
        """Материал публикуется, только если все обязательные факты переданы."""
        missing = [k for k in ("title", "slug") if not item.get(k)]
        if not _slugify_ok(item.get("slug", "")):
            missing.append("slug (строчные латинские буквы, цифры и дефис)")
        if missing:
            self.result.skip({
                "id": item.get("id") or item.get("slug") or "?",
                "reason": f"Не переданы обязательные поля: {', '.join(missing)}.",
                "required_input": "Полные метаданные материала из контентного пакета",
                "context": context,
            })
            return False
        if item.get("image") and not self._image(item, required_for=context):
            return False
        return True

    # ------------------------------------------------------------------ контекст сайта
    def build_site_context(self, *, environment: str) -> dict:
        brand = self.pkg["brand"]
        legal = self.pkg["legal"]
        nav = [{"label": i["label"], "url": i["url"], "current": False} for i in self.pkg["navigation"]["primary"]]
        footer = [{"label": i["label"], "url": i["url"]} for i in (self.pkg["navigation"].get("footer") or [])]
        footer += [{"label": d["title"], "url": f"/legal/{d['slug']}/"} for d in legal["documents"]]
        self.site_context = {
            "language": self.pkg.get("language", "ru"),
            "brand_name": brand["name"],
            "logo_url": "/assets/" + Path(brand["logo_ref"]).name,
            "logo_width": 40,
            "logo_height": 40,
            "favicon_url": "/assets/" + Path(brand["favicon_ref"]).name,
            "css_url": "/assets/site.css",
            "build_css_url": "/assets/build.css",
            "js_url": "/assets/enhance.js",
            "navigation": nav,
            "footer_navigation": footer,
            "legal_owner": legal["owner"],
            "legal_email": legal["contacts"]["email"],
            "og_enabled": ((self.pkg.get("metadata") or {}).get("og") or {}).get("enabled", True),
            "hreflang": (self.pkg.get("seo") or {}).get("hreflang") or [],
            "environment": environment,
        }
        return self.site_context

    # ------------------------------------------------------------------ JSON-LD
    def _ratio_class(self, ratio: str) -> str:
        name = "ratio-" + re.sub(r"[^0-9a-z]+", "-", str(ratio).lower()).strip("-")
        self._dynamic_css[name] = f"aspect-ratio: {ratio};"
        return name

    def _height_class(self, height: int) -> str:
        name = f"ad-h-{int(height)}"
        self._dynamic_css[name] = f"min-height: {int(height)}px;"
        return name

    def _write_dynamic_css(self) -> None:
        lines = ["/* Сгенерировано рендером: заменяет инлайновые style, запрещённые CSP. */"]
        for name, body in sorted(self._dynamic_css.items()):
            lines.append(f".{name} {{ {body} }}")
        (self.public / "assets" / "build.css").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _jsonld(self, blocks: Iterable[dict]) -> list[str]:
        allowed = set(((self.pkg.get("metadata") or {}).get("structured_data_input") or {}).get("allowed_types") or [])
        out: list[str] = []
        for block in blocks:
            if not block:
                continue
            if block.get("@type") not in allowed:
                continue
            # `<` экранируется, чтобы содержимое не могло закрыть тег <script>
            out.append(json.dumps(block, ensure_ascii=False).replace("<", "\\u003c"))
        return out

    def _breadcrumb_ld(self, crumbs: list[dict]) -> dict | None:
        if not crumbs:
            return None
        return {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": i + 1, "name": c["label"], "item": self.abs_url(c["url"])}
                for i, c in enumerate(crumbs)
            ],
        }

    # ------------------------------------------------------------------ страницы
    def _register(self, route: Route) -> None:
        self.result.routes.append(route)
        self.result.counts[route.page_type] = self.result.counts.get(route.page_type, 0) + 1

    def _robots_for(self, policy: dict, indexable: bool) -> str:
        if indexable:
            return "index,follow"
        return str(policy.get("robots") or "noindex,follow")

    def _render_listing(self, *, page_type: str, base_path: str, h1: str, intro: str,
                        items: list[dict], title_template: str, description_template: str,
                        crumbs: list[dict], indexable: bool = True) -> None:
        policy = self._policy(page_type)
        pagination_policy = self._policy("paginated_page")
        if not items:
            if policy.get("empty_behaviour") == "not_published":
                self.result.skip({
                    "id": base_path,
                    "reason": "Листинг пуст: публикация как indexable 200 запрещена матрицей (soft 404).",
                    "required_input": "Материалы для раздела или удаление раздела из навигации",
                    "context": page_type,
                })
                return
        pages = [items[i:i + self.per_page] for i in range(0, len(items), self.per_page)] or [[]]
        total = len(pages)
        for index, chunk in enumerate(pages, start=1):
            path = base_path if index == 1 else f"{base_path}page/{index}/"
            ptype = page_type if index == 1 else "paginated_page"
            eff_policy = policy if index == 1 else pagination_policy
            title = title_template if index == 1 else (self.pkg["metadata"]["title_templates"]["pagination"]
                                                       .replace("{title}", title_template).replace("{n}", str(index)))
            description = description_template if index == 1 else (
                self.pkg["metadata"]["description_templates"]["pagination"]
                .replace("{description}", description_template).replace("{n}", str(index)))
            page_crumbs = crumbs if index == 1 else crumbs + [{"label": f"Страница {index}", "url": path}]
            pagination = {
                "total_pages": total,
                "prev_url": None if index == 1 else (base_path if index == 2 else f"{base_path}page/{index - 1}/"),
                "next_url": None if index == total else f"{base_path}page/{index + 1}/",
                "pages": [
                    {"number": n, "url": base_path if n == 1 else f"{base_path}page/{n}/", "current": n == index}
                    for n in range(1, total + 1)
                ],
            }
            page = {
                "title": title,
                "h1": h1,
                "description": description,
                "intro": intro if index == 1 else "",
                "items": chunk,
                "pagination": pagination,
                "page_number": index,
                "canonical": self.abs_url(path),
                "robots": self._robots_for(eff_policy, indexable),
                "breadcrumbs": page_crumbs,
                "prev_url": self.abs_url(pagination["prev_url"]) if pagination["prev_url"] else None,
                "next_url": self.abs_url(pagination["next_url"]) if pagination["next_url"] else None,
                "jsonld": self._jsonld([self._breadcrumb_ld(page_crumbs)]),
            }
            file = self._write(path, self._tmpl("_listing.html", page))
            self._register(Route(
                path=path, page_type=ptype, status=200, indexable=indexable,
                robots=page["robots"], canonical=page["canonical"], in_sitemap=indexable,
                file=file, title=title, h1=h1, description=description,
                parent=base_path if index > 1 else None, page_number=index,
            ))
        if total >= 1:
            # page 1 доступна ровно по одному URL
            self.result.redirects.append(Redirect(f"{base_path}page/1/", base_path))

    def render_home(self) -> None:
        policy = self._policy("home")
        sections = []
        for collection in self.content.get("collections", []):
            items = [self._card(t) for t in self._titles_for_collection(collection)]
            items = [i for i in items if i]
            if items:
                sections.append({
                    "title": collection["title"], "url": f"/collections/{collection['slug']}/",
                    "description": collection.get("description", ""), "items": items[:6],
                })
        for category in self.content.get("categories", []):
            items = [self._card(t) for t in self._titles_in_category(category["slug"])]
            items = [i for i in items if i]
            if items:
                sections.append({
                    "title": category["title"], "url": f"/{category['slug']}/",
                    "description": category.get("description", ""), "items": items[:6],
                })
        meta = self.pkg["metadata"]
        title = meta["title_templates"]["home"].replace("{brand}", self.pkg["brand"]["name"])
        description = meta["description_templates"]["home"].replace("{brand}", self.pkg["brand"]["name"])
        sd = (meta.get("structured_data_input") or {})
        page = {
            "title": title, "h1": self.pkg["brand"]["name"], "description": description,
            "intro": sd.get("website", {}).get("description", "") if isinstance(sd.get("website"), dict) else "",
            "sections": sections, "canonical": self.abs_url("/"),
            "robots": self._robots_for(policy, True), "breadcrumbs": [],
            "prev_url": None, "next_url": None,
            "jsonld": self._jsonld([
                {"@context": "https://schema.org", "@type": "WebSite", "name": self.pkg["brand"]["name"], "url": self.abs_url("/")},
                ({"@context": "https://schema.org", "@type": "Organization", **sd["organization"]} if isinstance(sd.get("organization"), dict) else None),
            ]),
        }
        file = self._write("/", self._tmpl("home.html", page))
        self._register(Route(path="/", page_type="home", indexable=True, robots=page["robots"],
                             canonical=page["canonical"], in_sitemap=True, file=file,
                             title=title, h1=page["h1"], description=description))

    def _titles_in_category(self, slug: str) -> list[dict]:
        items = [t for t in self.content.get("titles", []) if t.get("category") == slug]
        return sorted(items, key=lambda t: (str(t.get("sort_key", t.get("title", ""))), str(t.get("id", ""))))

    def _titles_for_collection(self, collection: dict) -> list[dict]:
        ids = collection.get("items") or []
        by_id = {t.get("id"): t for t in self.content.get("titles", [])}
        return [by_id[i] for i in ids if i in by_id]

    def _card(self, item: dict) -> dict | None:
        if not self._publishable(item, "card"):
            return None
        return {
            "url": f"/{item['category']}/{item['slug']}/",
            "title": item["title"],
            "image": self._image(item, required_for="card"),
            "meta": item.get("meta", ""),
            "availability": item.get("availability", "unavailable"),
        }

    def render_categories(self) -> None:
        for category in self.content.get("categories", []):
            if not _slugify_ok(category.get("slug", "")):
                self.result.skip({"id": category.get("slug"), "reason": "Некорректный slug категории.", "required_input": "slug вида lower-case-with-dashes", "context": "category"})
                continue
            items = [c for c in (self._card(t) for t in self._titles_in_category(category["slug"])) if c]
            meta = self.pkg["metadata"]
            self._render_listing(
                page_type="category",
                base_path=f"/{category['slug']}/",
                h1=category["title"],
                intro=category.get("description", ""),
                items=items,
                title_template=meta["title_templates"]["category"].replace("{category}", category["title"]).replace("{brand}", self.pkg["brand"]["name"]),
                description_template=category.get("description", "") or meta["description_templates"]["category"].replace("{category}", category["title"]),
                crumbs=[{"label": "Главная", "url": "/"}, {"label": category["title"], "url": f"/{category['slug']}/"}],
            )

    def render_collections(self) -> None:
        for collection in self.content.get("collections", []):
            items = [c for c in (self._card(t) for t in self._titles_for_collection(collection)) if c]
            self._render_listing(
                page_type="collection",
                base_path=f"/collections/{collection['slug']}/",
                h1=collection["title"],
                intro=collection.get("description", ""),
                items=items,
                title_template=f"{collection['title']} — {self.pkg['brand']['name']}",
                description_template=collection.get("description", ""),
                crumbs=[{"label": "Главная", "url": "/"}, {"label": collection["title"], "url": f"/collections/{collection['slug']}/"}],
            )

    def render_titles(self) -> None:
        categories = {c["slug"]: c for c in self.content.get("categories", [])}
        for item in self.content.get("titles", []):
            if not self._publishable(item, "title"):
                continue
            category = categories.get(item.get("category"))
            if not category:
                self.result.skip({"id": item.get("id"), "reason": f"Категория «{item.get('category')}» отсутствует в каталоге.", "required_input": "Существующая категория", "context": "title"})
                continue
            path = f"/{item['category']}/{item['slug']}/"
            crumbs = [{"label": "Главная", "url": "/"}, {"label": category["title"], "url": f"/{category['slug']}/"}, {"label": item["title"], "url": path}]
            descriptor = self.player.resolve(item["video_ref"]) if item.get("video_ref") else None
            available = descriptor is not None and descriptor.availability == vk_mod.AVAILABLE
            embed = self.player.embed_html(descriptor) if descriptor else ""
            page_type = "title" if (available and embed) or item.get("seasons") else ("content_unavailable" if descriptor else "title")
            policy = self._policy(page_type)
            children = []
            for season in item.get("seasons") or []:
                season_title = season.get("title") or f"Сезон {season['number']}"
                children.append({"url": f"{path}season-{season['number']}/", "title": season_title, "availability": "available"})
                for episode in season.get("episodes") or []:
                    children.append({
                        "url": f"{path}season-{season['number']}/episode-{episode['number']}/",
                        "title": f"{season_title} · {episode.get('title') or 'Эпизод ' + str(episode['number'])}",
                        "availability": episode.get("availability", "unavailable"),
                    })
            meta = self.pkg["metadata"]
            title = meta["title_templates"]["title"].replace("{title}", item["title"]).replace("{brand}", self.pkg["brand"]["name"])
            jsonld_blocks: list[dict] = [self._breadcrumb_ld(crumbs)]
            if available and embed and self.player.may_emit_video_object(descriptor):
                jsonld_blocks.append(self._video_object(item, descriptor, path))
            page = {
                "title": title, "h1": item["title"], "description": item.get("description", ""),
                "canonical": self.abs_url(path), "robots": self._robots_for(policy, True),
                "breadcrumbs": crumbs, "prev_url": None, "next_url": None,
                "player": {"html": embed, "ratio_class": self._ratio_class(self.player.aspect_ratio())} if (available and embed) else None,
                "availability_notice": None if (available and embed) else {
                    "title": "Видео сейчас недоступно",
                    "text": "Материал доступен в каталоге, но воспроизведение временно невозможно. "
                            "Другой ролик вместо запрошенного не подставляется.",
                },
                "ad_slots": [{"placement_id": s.placement_id, "height_class": self._height_class(s.height), "html": s.html} for s in self.ads.slots(page_type)],
                "facts": item.get("facts") or [],
                "body_html": item.get("body_html", ""),
                "children": children, "children_title": "Сезоны и эпизоды",
                "related": self._related(item),
                "sequence": None,
                "jsonld": self._jsonld(jsonld_blocks),
            }
            file = self._write(path, self._tmpl("detail.html", page))
            self._register(Route(path=path, page_type=page_type, indexable=True, robots=page["robots"],
                                 canonical=page["canonical"], in_sitemap=True, file=file,
                                 title=title, h1=item["title"], description=item.get("description", ""),
                                 lastmod=item.get("updated_at")))
            self._render_seasons(item, category, path, crumbs)

    def _related(self, item: dict) -> list[dict]:
        by_id = {t.get("id"): t for t in self.content.get("titles", [])}
        out = []
        for rid in item.get("related") or []:
            other = by_id.get(rid)
            if other and self._publishable(other, "related"):
                out.append({"url": f"/{other['category']}/{other['slug']}/", "title": other["title"]})
        return out

    def _video_object(self, item: dict, descriptor, path: str) -> dict:
        """Только поля, явно разрешённые contract. Ничего не додумывается."""
        block = {"@context": "https://schema.org", "@type": "VideoObject", "name": item["title"]}
        for key, value in (descriptor.allowed_fields or {}).items():
            block[key] = value
        if item.get("description"):
            block["description"] = item["description"]
        block["url"] = self.abs_url(path)
        return block

    def _render_seasons(self, item: dict, category: dict, title_path: str, base_crumbs: list[dict]) -> None:
        for season in item.get("seasons") or []:
            spath = f"{title_path}season-{season['number']}/"
            episodes = season.get("episodes") or []
            crumbs = base_crumbs + [{"label": season.get("title") or f"Сезон {season['number']}", "url": spath}]
            children = [{"url": f"{spath}episode-{e['number']}/", "title": e.get("title") or f"Эпизод {e['number']}",
                         "availability": e.get("availability", "unavailable")} for e in episodes]
            if not children:
                self.result.skip({"id": spath, "reason": "Сезон без эпизодов не публикуется (запрет пустой indexable 200).", "required_input": "Список эпизодов", "context": "season"})
                continue
            policy = self._policy("season")
            page = {
                "title": f"{item['title']} — {season.get('title') or 'Сезон ' + str(season['number'])}",
                "h1": season.get("title") or f"Сезон {season['number']}",
                "description": season.get("description", ""),
                "canonical": self.abs_url(spath), "robots": self._robots_for(policy, True),
                "breadcrumbs": crumbs, "prev_url": None, "next_url": None,
                "player": None, "availability_notice": None, "ad_slots": [],
                "facts": [], "body_html": "", "children": children, "children_title": "Эпизоды",
                "related": [], "sequence": None,
                "jsonld": self._jsonld([self._breadcrumb_ld(crumbs)]),
            }
            file = self._write(spath, self._tmpl("detail.html", page))
            self._register(Route(path=spath, page_type="season", indexable=True, robots=page["robots"],
                                 canonical=page["canonical"], in_sitemap=True, file=file,
                                 title=page["title"], h1=page["h1"], description=page["description"]))
            for idx, episode in enumerate(episodes):
                self._render_episode(item, season, episode, spath, crumbs, episodes, idx)

    def _render_episode(self, item: dict, season: dict, episode: dict, season_path: str,
                        season_crumbs: list[dict], siblings: list[dict], index: int) -> None:
        epath = f"{season_path}episode-{episode['number']}/"
        crumbs = season_crumbs + [{"label": episode.get("title") or f"Эпизод {episode['number']}", "url": epath}]
        descriptor = self.player.resolve(episode["video_ref"]) if episode.get("video_ref") else None
        embed = self.player.embed_html(descriptor) if descriptor else ""
        available = descriptor is not None and descriptor.availability == vk_mod.AVAILABLE and bool(embed)
        page_type = "episode" if available else "content_unavailable"
        policy = self._policy(page_type)
        meta = self.pkg["metadata"]
        title = meta["title_templates"]["episode"].replace("{title}", item["title"]) \
            .replace("{season}", str(season["number"])).replace("{episode}", str(episode["number"])) \
            .replace("{brand}", self.pkg["brand"]["name"])
        jsonld: list[dict] = [self._breadcrumb_ld(crumbs)]
        if available and self.player.may_emit_video_object(descriptor):
            jsonld.append(self._video_object({"title": title, "description": episode.get("description", "")}, descriptor, epath))
        sequence = {
            "prev": {"url": f"{season_path}episode-{siblings[index-1]['number']}/", "title": siblings[index-1].get("title") or f"Эпизод {siblings[index-1]['number']}"} if index > 0 else None,
            "next": {"url": f"{season_path}episode-{siblings[index+1]['number']}/", "title": siblings[index+1].get("title") or f"Эпизод {siblings[index+1]['number']}"} if index + 1 < len(siblings) else None,
        }
        page = {
            "title": title, "h1": episode.get("title") or f"Эпизод {episode['number']}",
            "description": episode.get("description", ""),
            "canonical": self.abs_url(epath), "robots": self._robots_for(policy, True),
            "breadcrumbs": crumbs, "prev_url": None, "next_url": None,
            "player": {"html": embed, "ratio_class": self._ratio_class(self.player.aspect_ratio())} if available else None,
            "availability_notice": None if available else {
                "title": "Эпизод сейчас недоступен",
                "text": "Запись есть в каталоге, но воспроизведение временно невозможно. Замена другим роликом не выполняется.",
            },
            "ad_slots": [{"placement_id": s.placement_id, "height_class": self._height_class(s.height), "html": s.html} for s in self.ads.slots(page_type)],
            "facts": episode.get("facts") or [], "body_html": "",
            "children": [], "children_title": "", "related": [],
            "sequence": sequence if (sequence["prev"] or sequence["next"]) else None,
            "jsonld": self._jsonld(jsonld),
        }
        file = self._write(epath, self._tmpl("detail.html", page))
        self._register(Route(path=epath, page_type=page_type, indexable=True, robots=page["robots"],
                             canonical=page["canonical"], in_sitemap=True, file=file,
                             title=title, h1=page["h1"], description=page["description"]))

    def render_articles(self) -> None:
        articles = sorted(self.content.get("articles", []), key=lambda a: (str(a.get("published_at", "")), str(a.get("slug", ""))), reverse=True)
        cards = []
        for article in articles:
            if not self._publishable(article, "article"):
                continue
            path = f"/news/{article['slug']}/"
            crumbs = [{"label": "Главная", "url": "/"}, {"label": "Новости", "url": "/news/"}, {"label": article["title"], "url": path}]
            policy = self._policy("article")
            page = {
                "title": f"{article['title']} — {self.pkg['brand']['name']}",
                "h1": article["title"], "description": article.get("lead", ""),
                "canonical": self.abs_url(path), "robots": self._robots_for(policy, True),
                "breadcrumbs": crumbs, "prev_url": None, "next_url": None,
                "body_html": article.get("body_html", ""),
                "jsonld": self._jsonld([self._breadcrumb_ld(crumbs)]),
            }
            file = self._write(path, self._tmpl("text.html", page))
            self._register(Route(path=path, page_type="article", indexable=True, robots=page["robots"],
                                 canonical=page["canonical"], in_sitemap=True, file=file,
                                 title=page["title"], h1=article["title"], description=article.get("lead", ""),
                                 lastmod=article.get("published_at")))
            cards.append({"url": path, "title": article["title"], "image": None, "meta": article.get("published_at", ""), "availability": "available"})
        if cards:
            meta = self.pkg["metadata"]
            self._render_listing(
                page_type="news_index", base_path="/news/", h1="Новости", intro="",
                items=cards,
                title_template=meta["title_templates"].get("news_index", "Новости — {brand}").replace("{brand}", self.pkg["brand"]["name"]),
                description_template=meta["description_templates"].get("news_index", ""),
                crumbs=[{"label": "Главная", "url": "/"}, {"label": "Новости", "url": "/news/"}],
            )

    def render_legal(self) -> None:
        policy = self._policy("legal")
        for doc in self.pkg["legal"]["documents"]:
            path = f"/legal/{doc['slug']}/"
            body_path = self._site_file(doc["body_ref"])
            if not body_path:
                raise BlockedInput(f"Текст документа «{doc['slug']}» не найден.", field="legal.documents[].body_ref", required_input="Утверждённый текст юридического документа")
            body = body_path.read_text(encoding="utf-8")
            body_html = "\n".join(f"<p>{html.escape(par.strip())}</p>" for par in body.split("\n\n") if par.strip())
            crumbs = [{"label": "Главная", "url": "/"}, {"label": doc["title"], "url": path}]
            page = {
                "title": f"{doc['title']} — {self.pkg['brand']['name']}", "h1": doc["title"],
                "description": doc.get("summary", ""), "canonical": self.abs_url(path),
                "robots": self._robots_for(policy, True), "breadcrumbs": crumbs,
                "prev_url": None, "next_url": None,
                "body_html": body_html,
                "jsonld": self._jsonld([self._breadcrumb_ld(crumbs)]),
            }
            file = self._write(path, self._tmpl("text.html", page))
            self._register(Route(path=path, page_type="legal", indexable=True, robots=page["robots"],
                                 canonical=page["canonical"], in_sitemap=True, file=file,
                                 title=page["title"], h1=doc["title"], description=doc.get("summary", "")))

    def render_service_pages(self) -> None:
        meta = self.pkg["metadata"]
        # поиск: функция для пользователя, не landing
        policy = self._policy("search")
        page = {
            "title": meta["title_templates"].get("search", "Поиск"), "h1": "Поиск по каталогу",
            "description": "", "canonical": None, "robots": policy["robots"],
            "breadcrumbs": [{"label": "Главная", "url": "/"}, {"label": "Поиск", "url": "/search/"}],
            "prev_url": None, "next_url": None, "query": "", "items": [],
            "jsonld": [],
        }
        file = self._write("/search/", self._tmpl("search.html", page))
        self._register(Route(path="/search/", page_type="search", indexable=False, robots=policy["robots"],
                             canonical=None, in_sitemap=False, file=file, title=page["title"], h1=page["h1"]))

        for page_type, path, status, key in (("not_found", "/404/", 404, "not_found"), ("gone", "/410/", 410, "gone")):
            policy = self._policy(page_type)
            title = meta["title_templates"].get(key) or ("Страница не найдена" if status == 404 else "Материал удалён")
            page = {
                "title": title, "h1": title,
                "message": "Страница не найдена. Воспользуйтесь навигацией ниже." if status == 404
                           else "Материал удалён и больше не доступен.",
                "links": [{"url": "/", "label": "Главная"}] + [{"url": c["url"], "label": c["label"]} for c in self.site_context["navigation"]],
                "canonical": None, "robots": policy["robots"], "breadcrumbs": [],
                "prev_url": None, "next_url": None, "description": "", "jsonld": [],
            }
            file = self._write(path, self._tmpl("status.html", page))
            self._register(Route(path=path, page_type=page_type, status=status, indexable=False,
                                 robots=policy["robots"], canonical=None, in_sitemap=False, file=file,
                                 title=title, h1=title))

    # ------------------------------------------------------------------ robots и sitemap
    def render_robots(self, environment: str) -> None:
        lines: list[str] = []
        if environment != "production":
            lines += ["# staging: индексация запрещена полностью, доступ дополнительно закрыт авторизацией",
                      "User-agent: *", "Disallow: /"]
        else:
            lines += ["User-agent: *"]
            for param in (self.pkg.get("seo") or {}).get("non_indexable_parameters") or []:
                lines.append(f"Disallow: /*?{param}=")
            lines.append("Disallow: /search/")
            for extra in ((self.pkg["metadata"].get("robots") or {}).get("extra_disallow") or []):
                lines.append(f"Disallow: {extra}")
            lines.append("")
            lines.append(f"Sitemap: {self.abs_url('/sitemap.xml')}")
        (self.public / "robots.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def render_sitemap(self, environment: str) -> None:
        """Sitemap собирается всегда, публикуется только в production.

        Раньше на staging он не собирался вовсе, поэтому генерация, разбиение по типам
        и правило «только canonical+indexable+200» не проверялись ни разу.
        """
        if not (self.pkg["metadata"].get("sitemap") or {}).get("enabled", True):
            return
        # На staging файлы кладутся вне docroot: индексироваться нечему, а проверить есть что.
        target_dir = self.public if environment == "production" else (self.out / "sitemap-preview")
        target_dir.mkdir(parents=True, exist_ok=True)
        entries = [r for r in self.result.routes if r.in_sitemap and r.indexable and r.status == 200 and r.canonical]
        split = (self.pkg["metadata"]["sitemap"] or {}).get("split_by_type")
        limit = int((self.pkg["metadata"]["sitemap"] or {}).get("max_urls_per_file") or 50000)
        groups: dict[str, list[Route]] = {}
        for route in entries:
            groups.setdefault(route.page_type if split else "all", []).append(route)
        files: list[str] = []
        for name, routes in sorted(groups.items()):
            for part, start in enumerate(range(0, len(routes), limit), start=1):
                chunk = routes[start:start + limit]
                fname = f"sitemap-{name}.xml" if part == 1 else f"sitemap-{name}-{part}.xml"
                body = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
                for route in chunk:
                    body.append("  <url>")
                    body.append(f"    <loc>{html.escape(route.canonical)}</loc>")
                    if route.lastmod:
                        body.append(f"    <lastmod>{html.escape(str(route.lastmod))}</lastmod>")
                    body.append("  </url>")
                body.append("</urlset>")
                (target_dir / fname).write_text("\n".join(body) + "\n", encoding="utf-8")
                files.append(fname)
        index = ['<?xml version="1.0" encoding="UTF-8"?>', '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
        for fname in files:
            index.append(f"  <sitemap><loc>{self.abs_url('/' + fname)}</loc></sitemap>")
        index.append("</sitemapindex>")
        (target_dir / "sitemap.xml").write_text("\n".join(index) + "\n", encoding="utf-8")

    def copy_assets(self) -> None:
        target = self.public / "assets"
        target.mkdir(parents=True, exist_ok=True)
        for asset in (self.theme_dir / "assets").iterdir():
            (target / asset.name).write_bytes(asset.read_bytes())
        for ref in (self.pkg["brand"]["logo_ref"], self.pkg["brand"]["favicon_ref"]):
            src = self._site_file(ref)
            if src:
                (target / Path(ref).name).write_bytes(src.read_bytes())
        # медиа сайта копируются как есть: файлы приходят из переданного пакета,
        # фабрика ничего не подставляет и ничего не скачивает.
        media = PATHS.site_dir(self.site_id) / "media"
        if media.exists():
            for item in sorted(media.rglob("*")):
                if item.is_file():
                    dest = target / "media" / item.relative_to(media)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(item.read_bytes())

    # ------------------------------------------------------------------ вход
    def render(self, environment: str) -> RenderResult:
        self.public.mkdir(parents=True, exist_ok=True)
        self.build_site_context(environment=environment)
        self.render_home()
        self.render_categories()
        self.render_collections()
        self.render_titles()
        self.render_articles()
        self.render_legal()
        self.render_service_pages()
        self.copy_assets()
        self._write_dynamic_css()
        self.render_robots(environment)
        self.render_sitemap(environment)
        routes_map = {
            "site_id": self.site_id,
            "environment": environment,
            "base_url": self.base,
            "routes": [r.as_dict() for r in self.result.routes],
            "redirects": [r.as_dict() for r in self.result.redirects],
            "url_policy": self.url_policy,
            "non_indexable_parameters": (self.pkg.get("seo") or {}).get("non_indexable_parameters") or [],
            "max_depth": int(((self.pkg.get("seo") or {}).get("internal_link_rules") or {}).get("max_depth") or 4),
            # Поля VideoObject, разрешённые contract: всё остальное линт считает выдуманным.
            "allowed_video_fields": sorted((self.pkg.get("content_source") or {}).get("allowed_fields") or []),
            "canonical_changing_parameters": (self.matrix.get("query_parameters") or {}).get("canonical_changing") or [],
        }
        (self.out / "routes.json").write_text(json.dumps(routes_map, ensure_ascii=False, indent=2), encoding="utf-8")
        return self.result
