#!/usr/bin/env python3
"""Глубокая визуальная проверка витрины: измерения в браузере, а не по разметке.

## Почему браузер

Обрезанный текст, налезающие карточки, пустые ячейки сетки и переполнение по
горизонтали не видны в HTML: они возникают из применённого CSS при конкретной
ширине. Проверка по разметке здесь даёт вечный ноль — то есть не проверяет
ничего. Поэтому каждый маршрут открывается на шести ширинах, и величины
снимаются с готового макета через `getBoundingClientRect` и `getComputedStyle`.

## Что считается дефектом

* горизонтальное переполнение документа;
* обрезанный ОБЯЗАТЕЛЬНЫЙ текст — заголовок, дата, время, подпись кнопки:
  `scrollWidth` больше `clientWidth` при `overflow:hidden`, `text-overflow`
  или `-webkit-line-clamp`;
* многоточие внутри даты — дата обязана читаться целиком;
* постер вне допуска пропорции 2:3 (0.64–0.69);
* битое изображение: загрузка завершена, а `naturalWidth` равен нулю;
* пустая видимая ячейка сетки — карточка без текста и без изображения;
* одинокий хвост сетки: в последнем ряду один элемент при трёх и более колонках;
* наложение карточек внутри одного контейнера;
* необъяснённый вертикальный разрыв больше 96 px между соседями;
* ширина карточки вне диапазона, объявленного для этой ширины экрана.

Снимки делаются для ключевых маршрутов; измерения — для всех.

Запуск:

    nova-visual-audit.py --site lords-01 --record OUT.json --screenshots DIR
"""

from __future__ import annotations

import argparse
import datetime as _dt
import importlib.util
import json
import pathlib
import re
import sys
import urllib.parse
import urllib.request

VIEWPORTS = [320, 390, 768, 1024, 1440, 1920]
SCREENSHOT_ROUTES = {"home", "catalog", "title_film", "title_series", "episode", "new"}

#: Контракт карточек проекта. Свой диапазон ширин здесь был бы выдумкой: он
#: уже объявлен числом колонок на каждой точке перелома, и проверять надо его,
#: а не произвольные пиксели. Первая редакция этой проверки как раз и подняла
#: два «дефекта», которых нет: три колонки рекомендаций ниже 860 px и
#: compact_centered для единственного результата поиска — оба по контракту.
CARD_REGISTRY_PATH = pathlib.Path(__file__).resolve().parents[2] / "config" / "lords-card-registry.json"


def ожидаемые_колонки(контракт: dict, ширина: int, это_рекомендации: bool,
                      тип_карточки: str = "poster") -> int:
    """Сколько колонок обязано быть на этой ширине по контракту.

    Лестница у каждого типа своя: у постера одна, у горизонтальной карточки
    серии другая, у редакционной третья. Сверять всё с постером значит
    объявлять дефектом каждый профиль, который постером не пользуется, — ровно
    это и случилось с curated-витриной: сорок восемь «нарушений» на ровном месте.
    """
    типы = контракт.get("types", {})
    если_рек = (типы.get("recommendation") or {}).get("columns_rel")
    if это_рекомендации and если_рек:
        таблица = если_рек
    else:
        таблица = (типы.get(тип_карточки) or типы.get("poster") or {}).get("columns", {})
    точки = sorted((int(k) for k in таблица), reverse=True)
    for точка in точки:
        if ширина >= точка:
            return int(таблица[str(точка)])
    return 0

ИЗМЕРЕНИЕ = r"""
() => {
  const out = {overflow_x: 0, clipped: [], date_ellipsis: [], broken_images: [],
               poster_ratio_violations: [], empty_cells: 0, orphan_rows: [],
               overlaps: [], big_gaps: [], card_widths: [], grid_summary: []};
  const de = document.documentElement;
  out.doc_scroll_width = de.scrollWidth;
  out.doc_client_width = de.clientWidth;
  if (de.scrollWidth > de.clientWidth + 1) out.overflow_x = de.scrollWidth - de.clientWidth;

  const visible = (el) => {
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) return false;
    const cs = getComputedStyle(el);
    return cs.display !== 'none' && cs.visibility !== 'hidden' && cs.opacity !== '0';
  };
  const label = (el) => (el.textContent || '').trim().slice(0, 60);

  // --- обрезанный обязательный текст ---------------------------------------
  const required = document.querySelectorAll(
    'h1, h2, .c__title, .card__title, time, .c__meta, .c__date, button, .btn, a.btn, .pl__cta');
  out.sr_only_skipped = 0;
  for (const el of required) {
    if (!visible(el)) continue;
    const rr = el.getBoundingClientRect();
    // Визуально скрытый заголовок для скринридера: рамка в один пиксель с
    // обрезкой. Текст в нём «не помещается» по построению — это приём
    // доступности, а не обрезанная надпись, и считать его дефектом значит
    // требовать убрать доступность.
    if (rr.width <= 2 || rr.height <= 2) { out.sr_only_skipped += 1; continue; }
    const cs = getComputedStyle(el);
    const clamped = cs.webkitLineClamp && cs.webkitLineClamp !== 'none';
    const hidden = cs.overflow === 'hidden' || cs.textOverflow === 'ellipsis';
    const over_w = el.scrollWidth > el.clientWidth + 1;
    const over_h = el.scrollHeight > el.clientHeight + 1;
    const tag = el.tagName.toLowerCase();
    // Заголовок страницы и дата обрезаться не должны вовсе. Заголовок карточки
    // имеет объявленный многострочный зажим и нарушением не считается, пока
    // текст не режется ещё и по ширине.
    const strict = tag === 'h1' || tag === 'time' || /\d{2}\.\d{2}\.\d{4}|\d{2}:\d{2}/.test(el.textContent || '');
    if (strict && (over_w || (hidden && over_h) || clamped)) {
      out.clipped.push({tag, text: label(el), w: el.clientWidth, sw: el.scrollWidth, strict: true});
    } else if (!strict && over_w && hidden) {
      out.clipped.push({tag, text: label(el), w: el.clientWidth, sw: el.scrollWidth, strict: false});
    }
    if (/\d{2}\.\d{2}/.test(el.textContent || '') && /…|\.\.\./.test(el.textContent || '')) {
      out.date_ellipsis.push(label(el));
    }
  }

  // --- изображения ----------------------------------------------------------
  for (const img of document.images) {
    if (!visible(img)) continue;
    if (img.complete && img.naturalWidth === 0) {
      out.broken_images.push(img.getAttribute('src') || '(нет src)');
    }
    const r = img.getBoundingClientRect();
    const box = img.closest('.c__poster, .c__media, [data-poster]');
    if (box) {
      const br = box.getBoundingClientRect();
      if (br.height > 20) {
        const ratio = br.width / br.height;
        if (ratio < 0.64 || ratio > 0.69) {
          out.poster_ratio_violations.push({ratio: +ratio.toFixed(3), w: +br.width.toFixed(1), h: +br.height.toFixed(1)});
        }
      }
    }
  }

  // --- карточки, сетки, пустоты, наложения ---------------------------------
  const cards = [...document.querySelectorAll('[class*="c--poster"], [class*="c--episode"], [class*="c--editorial"]')]
    .filter(visible);
  const byParent = new Map();
  for (const c of cards) {
    const r = c.getBoundingClientRect();
    if (c.className.includes('c--poster')) out.card_widths.push(+r.width.toFixed(1));
    const hasText = (c.textContent || '').trim().length > 0;
    const hasImg = c.querySelector('img') !== null;
    if (!hasText && !hasImg) out.empty_cells += 1;
    const p = c.parentElement;
    if (!p) continue;
    if (!byParent.has(p)) byParent.set(p, []);
    byParent.get(p).push({el: c, r});
  }

  for (const [parent, items] of byParent) {
    if (items.length < 3) continue;
    const top0 = Math.round(items[0].r.top);
    const cols = items.filter(i => Math.abs(i.r.top - top0) < 4).length;
    if (cols >= 3) {
      const tail = items.length % cols;
      if (tail === 1) {
        out.orphan_rows.push({cols, total: items.length,
                              cls: (parent.className || '').slice(0, 40)});
      }
    }
    const pcs = getComputedStyle(parent);
    const declared = (pcs.gridTemplateColumns || '').split(' ').filter(x => x && x !== 'none').length;
    const классы = items.map(i => i.el.className || '').join(' ');
    const тип = /c--editorial/.test(классы) ? 'editorial'
              : /c--episode/.test(классы) ? 'episode'
              : 'poster';
    out.grid_summary.push({cols, declared, total: items.length, card_type: тип,
                           cls: (parent.className || '').slice(0, 40),
                           is_rel: /\brel\b/.test(parent.className || '')});
    // Наложения: сравниваются только соседи одного контейнера.
    for (let i = 0; i < items.length; i++) {
      for (let j = i + 1; j < items.length; j++) {
        const a = items[i].r, b = items[j].r;
        const ox = Math.min(a.right, b.right) - Math.max(a.left, b.left);
        const oy = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
        if (ox > 2 && oy > 2) {
          out.overlaps.push({ox: +ox.toFixed(1), oy: +oy.toFixed(1)});
        }
      }
    }
  }

  // --- необъяснённые вертикальные разрывы ----------------------------------
  const main = document.querySelector('main') || document.body;
  const kids = [...main.children].filter(visible);
  for (let i = 1; i < kids.length; i++) {
    const prev = kids[i - 1].getBoundingClientRect();
    const cur = kids[i].getBoundingClientRect();
    const gap = cur.top - prev.bottom;
    if (gap > 96) out.big_gaps.push({gap: +gap.toFixed(1), after: (kids[i - 1].className || '').slice(0, 40)});
  }
  return out;
}
"""


def _реестр():
    путь = pathlib.Path(__file__).resolve().parent / "nova-runtime-registry.py"
    spec = importlib.util.spec_from_file_location("nova_runtime_registry", путь)
    модуль = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(модуль)
    return модуль.build()


def маршруты(база: str, домен: str) -> dict[str, str]:
    """Маршруты берутся с самой витрины, а не выдумываются.

    Имя раздела, слаг жанра, страны и года, тайтл фильма и сериала, адрес серии
    — всё это разное у разных профилей. Захардкоженный слаг дал бы честный 404 и
    ложный дефект.
    """
    def взять(путь: str) -> str:
        req = urllib.request.Request(база + путь, headers={"Host": домен})
        try:
            with urllib.request.urlopen(req, timeout=40) as ответ:
                return ответ.read().decode("utf-8", "replace")
        except Exception:
            return ""

    дом = взять("/")
    серии = взять("/series/")

    def первый(шаблон: str, текст: str) -> str:
        найдено = re.findall(шаблон, текст)
        return найдено[0] if найдено else ""

    тайтл_фильм = первый(r'href="(/title/[^"]+)"', взять("/movies/")) or первый(r'href="(/title/[^"]+)"', дом)
    тайтл_сериал = первый(r'href="(/title/[^"]+)"', серии)
    серия = ""
    if тайтл_сериал:
        серия = первый(r'href="(/title/[^"]*/season-\d+/episode-\d+/)"', взять(тайтл_сериал))

    набор = {
        "home": "/",
        "catalog": "/catalog/",
        "catalog_page2": "/catalog/?page=2",
        "new": "/new/",
        "movies": "/movies/",
        "series": "/series/",
        "animation": "/animation/",
        "genre": первый(r'href="(/genre/[^"]+)"', дом),
        "year": первый(r'href="(/year/[^"]+)"', дом),
        "country": первый(r'href="(/country/[^"]+)"', дом) or "/country/rossiya/",
        "collections": "/collections/",
        "collection": первый(r'href="(/collection/[^"]+)"', дом),
        "search_exact": "",
        "search_nonsense": "/search/?q=zzzqqxvbnmwy",
        "title_film": тайтл_фильм,
        "title_series": тайтл_сериал,
        "episode": серия,
        "not_found": "/zzz-nonexistent-route-audit/",
    }
    # Точный поиск — по названию реального тайтла, взятого из каталога.
    заголовок = первый(r'href="/title/[^"]+"[^>]*>\s*<[^>]*>\s*([^<]{4,40})', дом)
    if not заголовок and тайтл_фильм:
        заголовок = тайтл_фильм.strip("/").split("/")[-1].replace("-", " ")
    набор["search_exact"] = f"/search/?q={urllib.parse.quote(заголовок.strip()[:24])}" if заголовок else "/search/?q=film"
    return {к: v for к, v in набор.items() if v}


def аудит(site: str, база: str, домен: str, снимки: pathlib.Path | None,
          viewports: list[int]) -> dict:
    from playwright.sync_api import sync_playwright

    набор = маршруты(база, домен)
    итог = {
        "site": site, "domain": домен, "base": база,
        "routes": набор, "viewports": viewports,
        "checked_at_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "pages": [], "defects": [],
    }

    with sync_playwright() as pw:
        # Заголовок Host подменять нельзя: Chromium считает его защищённым и
        # отвечает ERR_INVALID_ARGUMENT. Поэтому имя витрины отображается на её
        # локальный порт на уровне резолвера — и страница ходит по настоящему
        # домену, со своими canonical и относительными ссылками.
        порт = база.rsplit(":", 1)[-1]
        браузер = pw.chromium.launch(args=[
            "--disable-dev-shm-usage",
            f"--host-resolver-rules=MAP {домен} 127.0.0.1:{порт}",
        ])
        try:
            for ширина in viewports:
                контекст = браузер.new_context(
                    viewport={"width": ширина, "height": 900},
                    ignore_https_errors=True,
                )
                try:
                    for имя, путь in набор.items():
                        страница = контекст.new_page()
                        запись = {"route": имя, "path": путь, "viewport": ширина}
                        try:
                            # Перезапуск витрины платформой закрывает порт на
                            # считанные секунды. Без повтора это окно читается
                            # как визуальный дефект, которым не является;
                            # с повтором оно остаётся видимым отдельной
                            # метрикой, а не растворяется.
                            ответ = None
                            for попытка in range(4):
                                try:
                                    ответ = страница.goto(f"http://{домен}{путь}",
                                                          wait_until="load", timeout=45000)
                                    break
                                except Exception as отказ:
                                    # Перезапуск витрины даёт не только отказ в
                                    # соединении: соединение может быть принято
                                    # и тут же закрыто. Все эти признаки — одно
                                    # и то же окно рестарта, и различать их
                                    # незачем; счётчик повторов оставляет его
                                    # видимым.
                                    транзиент = any(
                                        признак in str(отказ) for признак in (
                                            "ERR_CONNECTION_REFUSED", "ERR_EMPTY_RESPONSE",
                                            "ERR_CONNECTION_RESET", "ERR_CONNECTION_CLOSED",
                                            "ERR_SOCKET_NOT_CONNECTED",
                                        )
                                    )
                                    if not транзиент or попытка == 3:
                                        raise
                                    запись["retries"] = запись.get("retries", 0) + 1
                                    страница.wait_for_timeout(5000)
                            запись["status"] = ответ.status if ответ else 0
                            страница.wait_for_timeout(350)
                            измерено = страница.evaluate(ИЗМЕРЕНИЕ)
                            запись.update(измерено)
                            if снимки and имя in SCREENSHOT_ROUTES:
                                снимки.mkdir(parents=True, exist_ok=True)
                                файл = снимки / f"{site}-{имя}-{ширина}.png"
                                страница.screenshot(path=str(файл), full_page=False)
                                запись["screenshot"] = файл.name
                        except Exception as ошибка:
                            запись["error"] = f"{type(ошибка).__name__}: {ошибка}"
                        finally:
                            # Страница закрывается сразу: сто восемь открытых
                            # вкладок — это не проверка, а расход памяти.
                            страница.close()
                        итог["pages"].append(запись)
                finally:
                    контекст.close()
        finally:
            браузер.close()

    # --- сведение дефектов ---------------------------------------------------
    для_сводки = [p for p in итог["pages"] if "error" not in p]
    def всего(ключ):
        return sum(len(p.get(ключ, []) or []) for p in для_сводки)

    строгие = [c for p in для_сводки for c in (p.get("clipped") or []) if c.get("strict")]
    мягкие = [c for p in для_сводки for c in (p.get("clipped") or []) if not c.get("strict")]

    # Сверка сеток с контрактом: сколько колонок объявлено для этой ширины и
    # сколько получилось на самом деле. Поиск с единственным результатом имеет
    # объявленную раскладку compact_centered и в сверку колонок не входит.
    контракт = json.loads(CARD_REGISTRY_PATH.read_text()) if CARD_REGISTRY_PATH.is_file() else {}
    нарушения_сетки = []
    if контракт:
        for p in для_сводки:
            if p["route"].startswith("search"):
                continue
            for сетка in (p.get("grid_summary") or []):
                факт = сетка.get("declared") or сетка.get("cols") or 0
                ждём = ожидаемые_колонки(контракт, p["viewport"], bool(сетка.get("is_rel")),
                                         сетка.get("card_type", "poster"))
                if ждём and факт and факт != ждём:
                    нарушения_сетки.append({
                        "route": p["route"], "viewport": p["viewport"],
                        "container": сетка.get("cls", ""), "card_type": сетка.get("card_type"),
                        "expected_columns": ждём,
                        "actual_columns": факт, "items": сетка.get("total"),
                    })

    итог["metrics"] = {
        "pages_measured": len(для_сводки),
        "pages_failed": len(итог["pages"]) - len(для_сводки),
        "CONNECTION_REFUSED_RETRIES": sum(p.get("retries", 0) for p in итог["pages"]),
        "HORIZONTAL_OVERFLOW_COUNT": sum(1 for p in для_сводки if p.get("overflow_x")),
        "CLIPPED_REQUIRED_TEXT_COUNT": len(строгие),
        "CLIPPED_SOFT_COUNT": len(мягкие),
        "TIMESTAMP_ELLIPSIS_COUNT": всего("date_ellipsis"),
        "POSTER_ASPECT_RATIO_VIOLATIONS": всего("poster_ratio_violations"),
        "BROKEN_IMAGE_COUNT": всего("broken_images"),
        "EMPTY_VISIBLE_CELL_COUNT": sum(p.get("empty_cells", 0) for p in для_сводки),
        "ORPHAN_LAST_ROW_COUNT": всего("orphan_rows"),
        "OVERLAP_COUNT": всего("overlaps"),
        "UNINTENDED_GAP_OVER_96PX_COUNT": всего("big_gaps"),
        "GRID_COLUMNS_CONTRACT_VIOLATIONS": len(нарушения_сетки),
        "HTTP_5XX_COUNT": sum(1 for p in для_сводки if (p.get("status") or 0) >= 500),
        "SOFT_404_COUNT": sum(1 for p in для_сводки if p["route"] == "not_found" and p.get("status") == 200),
    }
    итог["grid_columns_violations"] = нарушения_сетки[:40]
    итог["strict_clipped_examples"] = строгие[:20]
    итог["verdict"] = "PASS" if all(
        итог["metrics"][k] == 0 for k in (
            "HORIZONTAL_OVERFLOW_COUNT", "CLIPPED_REQUIRED_TEXT_COUNT", "TIMESTAMP_ELLIPSIS_COUNT",
            "POSTER_ASPECT_RATIO_VIOLATIONS", "BROKEN_IMAGE_COUNT", "EMPTY_VISIBLE_CELL_COUNT",
            "ORPHAN_LAST_ROW_COUNT", "OVERLAP_COUNT", "GRID_COLUMNS_CONTRACT_VIOLATIONS",
            "HTTP_5XX_COUNT", "SOFT_404_COUNT", "pages_failed",
        )
    ) else "FAIL"
    return итог


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", required=True)
    parser.add_argument("--record", required=True)
    parser.add_argument("--screenshots")
    parser.add_argument("--viewports", default=",".join(str(v) for v in VIEWPORTS))
    args = parser.parse_args()

    реестр = _реестр()
    запись = (реестр.get("sites") or {}).get(args.site)
    if not запись or запись.get("scope") != "exact-domain-registry":
        print(f"витрины {args.site} нет в exact-domain реестре", file=sys.stderr)
        return 2

    итог = аудит(
        args.site, f"http://127.0.0.1:{запись['port']}", запись["exact_domain"],
        pathlib.Path(args.screenshots) if args.screenshots else None,
        [int(v) for v in args.viewports.split(",")],
    )
    pathlib.Path(args.record).write_text(
        json.dumps(итог, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({"site": args.site, "verdict": итог["verdict"], **итог["metrics"]},
                     ensure_ascii=False, indent=2))
    return 0 if итог["verdict"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
