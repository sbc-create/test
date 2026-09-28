#!/usr/bin/env python3
"""Матрица потерь: источник → хранение → адаптер → отрисовано.

Отчёт отвечает на один вопрос и отвечает на него числами: **где именно
теряется значение**. Пока он не отвечен, любая правка покрытия — угадывание:
поле может отсутствовать у поставщика, потеряться при слиянии списка с
обогащением, не дойти до модели шаблона или не попасть в разметку. Это четыре
разных дефекта с четырьмя разными владельцами.

Слои считаются отдельно и в одном и том же знаменателе — по всему каталогу
там, где это возможно, и по детерминированной выборке там, где отрисовка
каждой записи стоила бы часов. Выборка фиксирована шагом по отсортированному
списку идентификаторов: она не зависит от времени запуска и повторяется.

Что считается потерей. Значение есть у поставщика и отсутствует слоем позже —
дефект того слоя. Значения нет у поставщика — не дефект вовсе, и такие случаи
в потери не записываются: подменять отсутствие данных видимостью работы
запрещено прямо.

Запуск:
    .venv/bin/python scripts/lords_chain_audit.py [--sample 400] [--site lords-02]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from factory.lords import detail_enrichment as enrich_mod  # noqa: E402
from factory.lords import live_catalog as live_mod  # noqa: E402
from factory.lords import preview as preview_mod  # noqa: E402
from factory.lords import render as render_mod  # noqa: E402

#: Кэши, наполненные боевой синхронизацией. Читаются только на чтение: эта
#: полоса их не пишет и писать не должна.
LIVE_ROOT = Path("/srv/site-factory/repo/var/lords")
CATALOG_CACHE = LIVE_ROOT / "lords" / "catalog-cache"
DETAIL_CACHE = LIVE_ROOT / "detail-cache"

OUT = ROOT / "artifacts" / "evidence" / "templates" / "chain-audit.json"


def _num(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _filled(value) -> bool:
    return value not in (None, "", [], {}, ())


# --------------------------------------------------------------------------
# Признаки поля на каждом слое. Один и тот же смысл, три разных представления:
# сырая запись поставщика, слитая запись, модель шаблона.
# --------------------------------------------------------------------------

RAW = {
    "название": lambda r: _filled(r.get("name")),
    "год": lambda r: _filled(r.get("year")),
    "тип": lambda r: _filled(r.get("type")),
    "описание": lambda r: _filled(r.get("description")),
    "жанры": lambda r: _filled(r.get("genres")),
    "страны": lambda r: _filled(r.get("countries")),
    "длительность": lambda r: _filled(r.get("duration")),
    "сезоны": lambda r: _filled(r.get("seasons")),
    "Kinopoisk ID": lambda r: _filled((r.get("external_ids") or {}).get("kinopoisk")
                                      or (r.get("external_ids") or {}).get("kp")),
    "рейтинг КП": lambda r: _num(r.get("kinopoisk_rating")),
    "голоса КП": lambda r: _num(r.get("kinopoisk_votes")),
    "IMDb ID": lambda r: _filled((r.get("external_ids") or {}).get("imdb")),
    "рейтинг IMDb": lambda r: _num(r.get("imdb_rating")),
    "голоса IMDb": lambda r: _num(r.get("imdb_votes")),
    "воспроизведение": lambda r: _filled(r.get("playback")),
}

MODEL = {
    "название": lambda t: _filled(t.name),
    # Ноль в поле года — это «источник не сказал», а не год. Адаптер ставит
    # ноль намеренно, разметка такой факт не печатает, и считать его
    # заполненным значило бы завысить покрытие на 2 746 записей.
    "год": lambda t: bool(t.year),
    "тип": lambda t: _filled(t.content_type),
    "описание": lambda t: _filled(t.summary),
    "жанры": lambda t: _filled(t.genres),
    "страны": lambda t: _filled(t.country),
    "длительность": lambda t: bool(t.runtime_min),
    "сезоны": lambda t: _filled(t.seasons),
    "Kinopoisk ID": lambda t: _filled(getattr(t, "kinopoisk_id", None)),
    "рейтинг КП": lambda t: _num(t.kinopoisk_rating),
    "голоса КП": lambda t: _num(getattr(t, "kinopoisk_votes", None)),
    "IMDb ID": lambda t: _filled(getattr(t, "imdb_id", None)),
    "рейтинг IMDb": lambda t: _num(t.imdb_rating),
    "голоса IMDb": lambda t: _num(getattr(t, "imdb_votes", None)),
    "воспроизведение": lambda t: _filled(t.playback),
}

#: Признаки поля в разметке страницы произведения. Ищется то, что увидит
#: зритель или машина, а не то, что мы намеревались вывести.
DOM = {
    "название": lambda h: re.search(r"<h1>[^<]", h) is not None,
    # Факты страницы печатаются парами `<dt>имя</dt><dd>значение</dd>`, и пара
    # без значения не печатается вовсе. Поэтому наличие пары — это и есть
    # наличие значения; искать подстроку где угодно по документу нельзя,
    # первая редакция этих признаков так и завышала покрытие.
    "год": lambda h: "<dt>Год</dt>" in h,
    "тип": lambda h: "<dt>Тип</dt>" in h,
    # Описание живёт в подзаголовке карточки произведения, а не в любом
    # абзаце класса `lede`: такой же абзац есть у вводного текста раздела.
    # Описание — абзац подзаголовка сразу за заголовком страницы. Такой же
    # абзац бывает у вводного текста раздела, поэтому важно именно соседство.
    "описание": lambda h: re.search(r'<h1>[^<]*</h1><p class="lede">[^<]', h) is not None,
    # У живого каталога источник отдаёт теги, а не жанры, и страница честно
    # называет их тегами. Признак учитывает оба заголовка: предмет измерения —
    # дошло ли значение, а не как оно подписано.
    "жанры": lambda h: "<dt>Жанры</dt>" in h or "<dt>Теги</dt>" in h,
    "страны": lambda h: "<dt>Страна</dt>" in h,
    "длительность": lambda h: re.search(r"<dt>Длительность</dt><dd>\d+ мин", h) is not None,
    # Блок сезонов отрисовывается всегда — в том числе состоянием «сезонов
    # нет». Наличие значения показывает перечень серий, а не сам блок.
    "сезоны": lambda h: 'class="episode"' in h,
    "Kinopoisk ID": lambda h: "data-kinopoisk-id=" in h,
    "рейтинг КП": lambda h: re.search(
        r'rating__source">Кинопоиск</span><span class="rating__value">', h) is not None,
    "голоса КП": lambda h: re.search(
        r'rating__source">Кинопоиск</span>.{0,200}?rating__votes"', h, re.S) is not None,
    "IMDb ID": lambda h: "data-imdb-id=" in h,
    "рейтинг IMDb": lambda h: re.search(
        r'rating__source">IMDb</span><span class="rating__value">', h) is not None,
    "голоса IMDb": lambda h: re.search(
        r'rating__source">IMDb</span>.{0,200}?rating__votes"', h, re.S) is not None,
    "воспроизведение": lambda h: 'class="player__frame"' in h,
}


def load_catalog(site: str) -> list[dict]:
    raw = json.loads((CATALOG_CACHE / f"{site}.json").read_text(encoding="utf-8"))
    return raw["items"] if isinstance(raw, dict) else raw


def load_details() -> dict[str, dict]:
    details, broken = enrich_mod.load_cached_details(DETAIL_CACHE)
    if broken:
        print(f"кэш обогащения: пропущено битых файлов {len(broken)}: "
              f"{', '.join(broken[:5])}")
    return details


def sample(ids: list[str], size: int) -> list[str]:
    """Детерминированная выборка равным шагом.

    Не случайная: прогон обязан повторяться. Не «первые N»: начало каталога —
    самые свежие записи, и они покрыты лучше хвоста, поэтому первые N завысили
    бы любую оценку покрытия.
    """
    if size >= len(ids):
        return list(ids)
    step = len(ids) / size
    return [ids[int(i * step)] for i in range(size)]


def audit(site: str, sample_size: int) -> dict:
    items = load_catalog(site)
    details = load_details()
    by_id = {r.get("external_id"): r for r in items if r.get("external_id")}

    layers = {"source": dict.fromkeys(RAW, 0), "merged": dict.fromkeys(RAW, 0),
              "model": dict.fromkeys(RAW, 0)}
    # Полный проход по каталогу: источник, слияние и модель считаются целиком.
    for rid, raw in by_id.items():
        detail = details.get(rid)
        merged = enrich_mod.merge_detail(raw, detail) if detail else dict(raw)
        title = live_mod.title_from_item(merged)
        for field, probe in RAW.items():
            if probe(raw) or (detail and probe(detail)):
                layers["source"][field] += 1
            if probe(merged):
                layers["merged"][field] += 1
        if title is not None:
            for field, probe in MODEL.items():
                if probe(title):
                    layers["model"][field] += 1

    # Слой разметки. Отрисовывать 53 251 страницу ради подсчёта — часы, поэтому
    # он считается по детерминированной выборке; знаменатель у неё свой и
    # назван отдельно, чтобы проценты слоёв нельзя было спутать.
    chosen = sample(sorted(by_id), sample_size)
    dom = dict.fromkeys(DOM, 0)
    dom_source = dict.fromkeys(RAW, 0)
    package, _ = preview_mod._package(site)
    slugs = {}
    for rid in chosen:
        merged = enrich_mod.merge_detail(by_id[rid], details[rid]) if rid in details else dict(by_id[rid])
        title = live_mod.title_from_item(merged)
        if title is None:
            continue
        slugs[title.slug] = (merged, title)
    catalog = live_mod.catalog_from_live(
        [enrich_mod.merge_detail(by_id[r], details[r]) if r in details else by_id[r]
         for r in chosen]) if hasattr(live_mod, "catalog_from_live") else None
    rendered = 0
    if catalog is not None:
        site_obj = render_mod.render_site(package, catalog=catalog, environ={},
                                          only_title_slugs=frozenset(slugs))
        for slug, (merged, _title) in slugs.items():
            page = site_obj.pages.get(f"/title/{slug}/")
            if page is None:
                continue
            rendered += 1
            html = page.body
            for field, probe in DOM.items():
                if probe(html):
                    dom[field] += 1
            for field, probe in RAW.items():
                if probe(merged):
                    dom_source[field] += 1

    return {
        "artifact": "LORDS_CHAIN_AUDIT",
        "site": site,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "catalog_total": len(items),
        "addressable": len(by_id),
        "enriched": len(details),
        "sample_size": min(sample_size, len(by_id)),
        "sample_ids": sample(sorted(by_id), sample_size),
        "layers": layers,
        "dom": {"rendered": rendered, "source": dom_source, "markup": dom},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", default="lords-02")
    parser.add_argument("--sample", type=int, default=400)
    args = parser.parse_args()

    report = audit(args.site, args.sample)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    total = report["addressable"]
    print(f"{report['site']}: каталог {report['catalog_total']}, адресуемых {total}, "
          f"обогащено {report['enriched']}")
    print(f"\n{'поле':18} {'источник':>12} {'слияние':>12} {'модель':>12}   потеря")
    for field in RAW:
        src = report["layers"]["source"][field]
        mrg = report["layers"]["merged"][field]
        mdl = report["layers"]["model"][field]
        loss = src - mdl
        mark = "" if loss <= 0 else f"  −{loss} ({100 * loss / max(src, 1):.1f}%)"
        print(f"{field:18} {src:6} {100*src/total:5.1f}% {mrg:6} {100*mrg/total:5.1f}% "
              f"{mdl:6} {100*mdl/total:5.1f}%{mark}")
    d = report.get("dom") or {}
    if d.get("rendered"):
        n = d["rendered"]
        print(f"\nслой разметки, выборка {n} страниц произведений:")
        print(f"{'поле':18} {'в записи':>12} {'в разметке':>12}   потеря")
        for field in RAW:
            src = d["source"][field]
            got = d["markup"][field]
            loss = src - got
            mark = "" if loss <= 0 else f"  −{loss}"
            print(f"{field:18} {src:6} {100*src/n:5.1f}% {got:6} {100*got/n:5.1f}%{mark}")
    print(f"\n{OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
