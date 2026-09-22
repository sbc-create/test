"""Пилотная витрина: настоящие страницы, настоящие адреса, настоящий инвентарь.

Минимальная, но не игрушечная: страницы собираются из локального каталога и
локальных данных, адреса выводятся из устойчивого UUID, и инвентарь адресов
снимается с готовых файлов, а не из намерения их создать.

Почему адрес выводится из UUID, а не из названия. Название меняется — правкой
редактора, исправлением опечатки в источнике, — и адрес, выведенный из
названия, меняется вместе с ним. Страница исчезает, а в отчёте это выглядит как
«обновили метаданные». Устойчивый идентификатор разрывает эту связь.

Шаблон здесь отвечает за показ и только за него: список опубликованных страниц
задаёт каталог, а не сетка и не CSS.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"

#: Разрешённая форма части адреса. Всё остальное отбрасывается: адрес — это
#: контракт, и попадание в него произвольного текста ломает его молча.
SLUG_RE = re.compile(r"[^a-z0-9-]+")


class PilotError(RuntimeError):
    pass


def slug_for(title_uuid: str, name: str | None = None) -> str:
    """Устойчивая часть адреса.

    Хвост присутствует всегда: два произведения с одинаковым названием иначе
    делили бы один адрес, и одно из них было бы недоступно.

    Хвост — это отпечаток **всего** идентификатора, а не его начало. Срез
    `uuid[:8]` выглядит уникальным ровно до первой партии, выданной одним
    генератором: у таких идентификаторов совпадает именно начало, и три
    разные записи молча съезжаются на один адрес. Отпечаток зависит от каждого
    символа, поэтому съехаться они не могут.

    Читаемая часть необязательна: у названия из кириллицы латинского слага не
    получается, и адрес держится на одном хвосте. Это осознанно — выдумывать
    транслитерацию значит менять адрес при смене правил транслитерации.
    """
    readable = SLUG_RE.sub("-", (name or "").strip().lower()).strip("-")[:48]
    tail = hashlib.sha256(title_uuid.encode()).hexdigest()[:10]
    return f"{readable}-{tail}".strip("-") if readable else tail


@dataclass(frozen=True)
class Page:
    route: str
    path: Path
    title_uuid: str | None
    content_hash: str


def _document(*, title: str, body: str, domain: str, canonical: str) -> str:
    return f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title>
<link rel="canonical" href="https://{html.escape(domain)}{html.escape(canonical)}">
<meta name="robots" content="noindex, nofollow">
<style>
:root{{color-scheme:light dark}}
body{{margin:0;font:16px/1.5 system-ui,sans-serif;background:#12141a;color:#e8e8ea}}
main{{max-width:1200px;margin:0 auto;padding:16px}}
a{{color:#8fbcff}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:16px}}
article{{background:#1c1f28;border-radius:12px;padding:12px;overflow-wrap:anywhere}}
img{{width:100%;aspect-ratio:2/3;object-fit:cover;border-radius:8px;background:#2a2e3a}}
video-player{{display:block;min-height:320px;background:#000;border-radius:8px}}
@media (max-width:420px){{main{{padding:12px}}.grid{{grid-template-columns:repeat(auto-fill,minmax(140px,1fr))}}}}
</style>
</head>
<body><main>{body}</main></body>
</html>
"""


def _card(record: dict[str, Any]) -> str:
    name = html.escape(str(record.get("title") or "Без названия"))
    route = record["route"]
    year = record.get("year")
    poster = record.get("poster_url") or ""
    rating = record.get("rating_external")
    bits = [f'<h3><a href="{route}">{name}</a></h3>']
    if year:
        bits.append(f"<p>{html.escape(str(year))}</p>")
    if rating is not None:
        bits.append(f'<p data-role="rating-external">Внешняя оценка: {html.escape(str(rating))}</p>')
    poster_tag = (f'<img src="{html.escape(str(poster))}" alt="{name}">'
                  if poster else '<img alt="" src="data:image/gif;base64,R0lGODlhAQABAAAAACw=">')
    return f"<article>{poster_tag}{''.join(bits)}</article>"


def build_records(catalog: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Привести записи каталога к виду представления, добавив адреса."""
    records = []
    for title_uuid, fields in sorted(catalog.items()):
        record = dict(fields)
        record["title_uuid"] = title_uuid
        record["route"] = f"/title/{slug_for(title_uuid, fields.get('title'))}/"
        records.append(record)
    return records


def render(*, site_id: str, domain: str, publisher_id: str | None,
           catalog: dict[str, dict[str, Any]], destination: Path,
           content_revision: int = 0) -> list[Page]:
    """Собрать витрину. Возвращает список страниц с их адресами."""
    destination.mkdir(parents=True, exist_ok=True)
    records = build_records(catalog)
    pages: list[Page] = []

    def write(route: str, title: str, body: str, title_uuid: str | None = None) -> None:
        target = destination / route.strip("/") / "index.html" if route != "/" \
            else destination / "index.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        document = _document(title=title, body=body, domain=domain, canonical=route)
        target.write_text(document, encoding="utf-8")
        pages.append(Page(route=route, path=target, title_uuid=title_uuid,
                          content_hash=hashlib.sha256(document.encode()).hexdigest()[:16]))

    cards = "".join(_card(r) for r in records)
    write("/", f"{site_id} — главная",
          f"<h1>{html.escape(site_id)}</h1>"
          f'<p data-role="content-revision">Ревизия содержимого: {content_revision}</p>'
          f'<nav><a href="/catalog/">Каталог</a> <a href="/search/">Поиск</a></nav>'
          f'<section class="grid">{cards}</section>')

    write("/catalog/", f"{site_id} — каталог",
          f"<h1>Каталог</h1><section class=\"grid\">{cards}</section>")

    index = [{"route": r["route"], "title": r.get("title"),
              "year": r.get("year"), "title_uuid": r["title_uuid"]} for r in records]
    write("/search/", f"{site_id} — поиск",
          "<h1>Поиск</h1>"
          '<form role="search"><label for="q">Запрос</label>'
          '<input id="q" name="q" type="search"></form>'
          f'<script type="application/json" id="search-index">{json.dumps(index, ensure_ascii=False)}</script>'
          f'<section class="grid">{cards}</section>')

    for record in records:
        name = html.escape(str(record.get("title") or "Без названия"))
        player = ""
        playback = record.get("playback") or {}
        if publisher_id and playback.get("aggregator") and playback.get("title_id"):
            # Идентификатор издателя — открытое значение настройки web component
            # (D89), а не учётные данные: в разметку он попадает по контракту.
            player = (f'<video-player data-publisher="{html.escape(str(publisher_id))}" '
                      f'data-aggregator="{html.escape(str(playback["aggregator"]))}" '
                      f'data-id="{html.escape(str(playback["title_id"]))}"></video-player>')
        else:
            player = ('<p data-role="playback-unavailable">Воспроизведение недоступно: '
                      'источник не подтверждён.</p>')
        seo_text = record.get("seo_text")
        seo_block = (f'<section data-role="seo-text">{html.escape(str(seo_text))}</section>'
                     if seo_text else "")
        rating = record.get("rating_external")
        rating_block = (f'<p data-role="rating-external">Внешняя оценка: '
                        f'{html.escape(str(rating))}</p>' if rating is not None else "")
        episodes = record.get("episodes")
        episodes_block = (f'<p data-role="episodes">Серий: {html.escape(str(episodes))}</p>'
                          if episodes is not None else "")
        write(record["route"], str(record.get("seo_title") or record.get("title") or name),
              f"<h1>{name}</h1>{rating_block}{episodes_block}{player}{seo_block}"
              f'<section data-role="comments"></section>',
              title_uuid=record["title_uuid"])

    return pages


def url_inventory(site_dir: Path) -> dict[str, Any]:
    """Инвентарь опубликованных адресов, снятый с готовых файлов.

    Сравнение двух инвентарей отвечает на вопрос «не исчез ли адрес», а не
    «собрались ли страницы»: второе бывает истинным при первом ложном.
    """
    entries: dict[str, Any] = {}
    for path in sorted(site_dir.rglob("index.html")):
        relative = path.parent.relative_to(site_dir)
        route = "/" if str(relative) == "." else "/" + str(relative) + "/"
        text = path.read_text(encoding="utf-8")
        uuid_match = re.search(r'/title/[a-z0-9-]*?([0-9a-f]{10})/', text)
        entries[route] = {
            "content_hash": hashlib.sha256(text.encode()).hexdigest()[:16],
            "bytes": len(text.encode()),
            "uuid_tail": uuid_match.group(1) if uuid_match else None,
        }
    return {"schema_version": SCHEMA_VERSION, "routes": entries, "total": len(entries)}


def compare_inventories(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    """Что изменилось между двумя инвентарями.

    Редирект всех адресов на главную и пустая страница с кодом 200 успехом не
    считаются: первое видно как исчезнувшие маршруты, второе — как обнулившийся
    размер страницы.
    """
    before_routes = set(before["routes"])
    after_routes = set(after["routes"])
    lost = sorted(before_routes - after_routes)
    added = sorted(after_routes - before_routes)
    emptied = sorted(
        route for route in before_routes & after_routes
        if after["routes"][route]["bytes"] < max(
            200, before["routes"][route]["bytes"] // 4)
    )
    changed = sorted(
        route for route in before_routes & after_routes
        if before["routes"][route]["content_hash"] != after["routes"][route]["content_hash"]
    )
    return {
        "lost": lost,
        "added": added,
        "emptied": emptied,
        "changed": changed,
        "before_total": before["total"],
        "after_total": after["total"],
        "status": "PASS" if not lost and not emptied else "FAIL",
    }


def catalog_from_records(records: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Свести записи владельцев полей к плоскому каталогу для показа."""
    return {uuid: record.view() for uuid, record in records.items()}
