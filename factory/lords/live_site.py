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
import os
from dataclasses import dataclass
from pathlib import Path

import yaml

from factory.errors import BlockedInput
from factory.lords import content_live, detail_enrichment, live_catalog
from factory.lords import playability as playability_mod
from factory.lords import player as player_mod
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



def publisher_id_for(site_id: str) -> str | None:
    """Publisher ID направления: сначала systemd credential, затем реестр.

    Порядок важен. Обновление каталога работает в sandbox, где каталог секретов
    объявлен недоступным — и правильно объявлен: читать оттуда напрямую ему
    незачем. Значение приходит через LoadCredential, как и токен. Когда
    credential не передан (ручной запуск, тесты), остаётся путь через реестр.

    Промах здесь не заметен на глаз: Publisher ID не находится, плеер молча
    заменяется нейтральной фразой на КАЖДОЙ странице, а сайт продолжает
    отвечать двумястами. Именно так однажды и пропало видео со всех трёх
    доменов сразу.
    """
    from_credential = _publisher_from_credentials()
    if from_credential:
        return from_credential
    return _publisher_from_registry(site_id)


def _publisher_from_credentials() -> str | None:
    """Значение, переданное systemd через LoadCredential."""
    directory = os.environ.get("CREDENTIALS_DIRECTORY", "").strip()
    if not directory:
        return None
    name = os.environ.get("CDNVIDEOHUB_PUBLISHER_ID_CREDENTIAL", "cdnvideohub_publisher_id")
    try:
        value = (Path(directory) / name).read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return value if player_mod.is_valid_publisher_id(value) else None


def _publisher_from_registry(site_id: str) -> str | None:
    """Publisher ID направления из реестра Secret Hub.

    Значение публичное по назначению: плеер получает его атрибутом элемента, и
    оно уходит в разметку в момент ответа. Секретен рядом лежащий токен — его
    здесь не читают вовсе. Отсутствие файла не должно ронять сборку: каталог,
    навигация и описания от плеера не зависят, а страница тайтла в этом случае
    покажет нейтральное состояние.
    """
    registry = PATHS.root / "config" / "secret-hub.json"
    try:
        config = json.loads(registry.read_text(encoding="utf-8"))
    except OSError:
        return None
    for portfolio in config.get("portfolios", []):
        for consumer in portfolio.get("consumers", []):
            if consumer.get("id") != site_id:
                continue
            files = consumer.get("files") or {}
            name = files.get("publisher_id") if isinstance(files, dict) else None
            directory = consumer.get("directory")
            if not name or not directory:
                return None
            try:
                value = (Path(directory) / name).read_text(encoding="utf-8").strip()
            except OSError:
                return None
            # Нечисловое значение плеер превращает в NaN и молча не стартует,
            # поэтому непригодное лучше считать отсутствующим.
            return value if player_mod.is_valid_publisher_id(value) else None
    return None


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
    publisher_id: str | None = None,
    enrich_budget: int = 0,
    credentials_token: str | None = None,
    playability_budget: int = 0,
) -> LiveSiteResult:
    """Собирает сайт одного пакета Lords из живого каталога."""
    package = yaml.safe_load(PATHS.site_package(site_id).read_text(encoding="utf-8"))
    entries = items if items is not None else load_live_items(site_id, root=root)
    publisher = publisher_id if publisher_id is not None else publisher_id_for(site_id)

    # Обогащение до сборки: описания, страны, жанры, состав и хронометраж
    # берутся из detail и кладутся в кэш. Бюджет ограничен — покрытие набирается
    # прогонами, а не одним залпом в четыре тысячи запросов.
    enrichment = None
    if enrich_budget and credentials_token:
        try:
            contract = content_live.load_live_contract()
            fetcher = content_live.Fetcher(contract=contract, token=credentials_token)
            cache = detail_enrichment.DetailCache(
                detail_enrichment.cache_dir(PATHS.root / "var"))
            entries, enrichment = detail_enrichment.enrich_items(
                entries, fetcher=fetcher, contract=contract,
                cache=cache, budget=enrich_budget)
        except Exception as error:  # noqa: BLE001
            # Обогащение — улучшение, а не условие сборки: без него страницы
            # беднее, но сайт остаётся прежним и рабочим.
            enrichment = {"error": repr(error)[:200]}

    # Проверка воспроизводимости: наличие пары «агрегатор + идентификатор»
    # ничего не обещает — она есть у всех записей, включая те, для которых
    # поток ещё не завели. Проверяются самые свежие поступления: именно они
    # претендуют на первый экран и именно у них потока чаще всего нет.
    playability = None
    if playability_budget and publisher:
        try:
            cache = playability_mod.PlayabilityCache(
                PATHS.root / "var" / "lords" / "playability.json")
            playability = playability_mod.annotate(
                entries, str(publisher), budget=playability_budget, cache=cache,
                referer=f"https://{package.get('domain') or ''}/")
            cache.save()
        except Exception as error:  # noqa: BLE001
            # Проверка — улучшение витрины, а не условие сборки. Если она не
            # состоялась, все записи остаются «непроверенными», то есть
            # пригодными, и ни один рабочий плеер не пропадает.
            playability = {"error": repr(error)[:200]}

    catalog = live_catalog.catalog_from_live(entries)
    site = render_mod.render_site(
        package, catalog=catalog, environ={}, publisher_id=publisher)

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
    playable = sum(1 for t in catalog.titles if (t.playback or {}).get("title_id"))
    report["player"] = {
        # Значение не пишется: в отчёт идёт только факт его наличия.
        "publisher_id_present": bool(publisher),
        "titles_with_playback": playable,
        "titles_total": len(catalog.titles),
    }
    report["enrichment"] = (
        enrichment.as_dict() if hasattr(enrichment, "as_dict") else enrichment
    )
    report["playability"] = playability
    report["coverage"] = {
        "with_poster": sum(1 for t in catalog.titles if t.poster_url),
        # Записи, про которые источник подтвердил, что играть нечего. Средняя
        # цифра «у скольких есть контракт воспроизведения» их не отличала.
        "confirmed_silent": sum(
            1 for t in catalog.titles if getattr(t, "playable", None) is False),
        "confirmed_playable": sum(
            1 for t in catalog.titles if getattr(t, "playable", None) is True),
        "with_kinopoisk": sum(1 for t in catalog.titles if t.kinopoisk_rating is not None),
        "with_imdb": sum(1 for t in catalog.titles if t.imdb_rating is not None),
        "with_genres": sum(1 for t in catalog.titles if t.genres),
        "with_description": sum(1 for t in catalog.titles if t.summary),
        "with_country": sum(1 for t in catalog.titles if t.country),
        "with_actors": sum(1 for t in catalog.titles if getattr(t, "actors", ())),
    }

    # Отчёт лежит РЯДОМ с каталогом документов, а не внутри него. Внутри он
    # становится страницей сайта: `/live-report.json` отдавался публично и нёс
    # наружу и причину отказа плеера, и внутренние пути сборки.
    report_path = directory.parent / f"{directory.name}-live-report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    report["report_path"] = str(report_path)
    return LiveSiteResult(
        site_id=site_id, profile=str(site.profile), directory=directory, report=report)
