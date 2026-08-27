"""Сборка сайта Lords из живого каталога CDNVideoHub.

Отдельный путь, а не флаг у `build_preview`. Стенд по своему контракту обязан
быть синтетическим: он проверяет, что настоящего источника нет вовсе, и отказ
собираться при включённом источнике — не помеха, а его смысл. Живая сборка —
другая операция с другими гарантиями, и смешивать их в одной функции значило бы
ослабить ту проверку, ради которой она написана.

Что здесь происходит: кэш живого каталога превращается в `Catalog` через
`live_catalog`, тем же `render_site` собирается тот же самый сайт — главная,
каталог с пагинацией, разделы по типам, жанры, годы, страны, подборки,
расписание, поиск, страницы тайтлов — и выгружается в каталог документов.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import yaml

from factory.errors import BlockedInput
from factory.lords import live_catalog
from factory.lords import render as render_mod
from factory.lords import serve as serve_mod
from factory.paths import PATHS


def cache_file(site_id: str, root: Path | None = None) -> Path:
    """Где лежит кэш живого каталога направления."""
    base = Path(root) if root else PATHS.root / "var" / "lords" / "lords" / "catalog-cache"
    return base / f"{site_id}.json"


def load_live_items(site_id: str, *, root: Path | None = None) -> list[dict]:
    """Записи живого каталога. Пусто — это отказ, а не пустой сайт."""
    path = cache_file(site_id, root)
    if not path.is_file():
        raise BlockedInput(
            f"нет кэша живого каталога {path}: сначала выполните живую выборку",
            field="content_api.cache",
            required_input="python3 -m factory lords-live",
            blocks_stage="BUILDING",
        )
    raw = json.loads(path.read_text(encoding="utf-8"))
    items = raw.get("items") if isinstance(raw, dict) else raw
    if not items:
        # Пустая выдача не должна превращаться в пустую витрину: прежний релиз
        # с настоящим каталогом полезнее свежего релиза ни с чем.
        raise BlockedInput(
            f"кэш живого каталога {path} пуст: сборка остановлена, релиз не заменяется",
            field="content_api.cache",
            required_input="повторить живую выборку и убедиться, что источник ответил",
            blocks_stage="BUILDING",
        )
    return list(items)


@dataclass
class LiveSiteResult:
    site_id: str
    profile: str
    directory: Path
    report: dict


def build_live_site(
    site_id: str,
    *,
    output: Path | None = None,
    items: list[dict] | None = None,
    root: Path | None = None,
) -> LiveSiteResult:
    """Собирает сайт одного пакета Lords из живого каталога."""
    package = yaml.safe_load(PATHS.site_package(site_id).read_text(encoding="utf-8"))
    entries = items if items is not None else load_live_items(site_id, root=root)

    catalog = live_catalog.catalog_from_live(entries)
    site = render_mod.render_site(package, catalog=catalog, environ={})

    directory = Path(output) if output else PATHS.artifact_dir("lords", "live", site_id)
    directory.mkdir(parents=True, exist_ok=True)
    for existing in sorted(directory.rglob("*"), reverse=True):
        if existing.is_file():
            existing.unlink()
        elif existing.is_dir():
            existing.rmdir()
    export = serve_mod.export(site, directory)

    report = dict(site.report)
    report["documents"] = len(export["files"])
    report["directory"] = str(directory)
    report["catalog"] = {
        "source": live_catalog.SOURCE,
        "titles": len(catalog.titles),
        "collections": len(catalog.collections),
    }
    # Наблюдаемые числа, по которым видно, что страница не несёт весь каталог.
    pages = site.pages
    listing = {}
    for path in ("/", "/catalog/", "/movies/", "/series/"):
        page = pages.get(path) if isinstance(pages, dict) else None
        if page is not None:
            listing[path] = len(page.body)
    report["listing_bytes"] = listing
    report["coverage"] = {
        "with_poster": sum(1 for t in catalog.titles if t.poster_url),
        "with_kinopoisk": sum(1 for t in catalog.titles if t.kinopoisk_rating is not None),
        "with_imdb": sum(1 for t in catalog.titles if t.imdb_rating is not None),
        "with_genres": sum(1 for t in catalog.titles if t.genres),
    }

    (directory / "live-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return LiveSiteResult(
        site_id=site_id, profile=str(site.profile), directory=directory, report=report)
