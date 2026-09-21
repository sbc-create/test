#!/usr/bin/env python3
"""Оценка шаблонного пакета: измерения в браузере и балл по рубрике.

Измеритель переиспользуется из `automation/host/nova-visual-audit.py` — тот
самый, которым принимались живые витрины. Второй измеритель означал бы два
разных определения «обрезанного текста», и расхождение между ними обнаружилось
бы позже всего.

## Как считается балл

Сто баллов разложены по одиннадцати критериям. Но балл — не среднее
впечатление: у части критериев есть жёсткий отказ, и он обнуляет критерий
целиком независимо от прочего. Обрезанный обязательный текст не компенсируется
удачной типографикой.

Самооценка агента не является приёмкой владельца и так и помечена в отчёте.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import importlib.util
import json
import pathlib
import sys

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[4]
ТОЧКИ = (320, 390, 768, 1024, 1440, 1920)

#: Критерий → (вес, что считается жёстким отказом).
РУБРИКА = {
    "hierarchy": (15, "нет первичного действия или одинаковые повторяющиеся полки"),
    "grid": (12, "пустые ячейки, одинокий хвост, гигантские карточки"),
    "typography": (10, "обрезанный обязательный текст"),
    "media": (10, "растяжение, битое изображение, разрушительный кроп"),
    "responsive": (12, "переполнение или наложение на любой требуемой ширине"),
    "content_truth": (12, "ложная новизна, дата или оценка"),
    "ux": (8, "недоступные элементы управления"),
    "accessibility": (8, "клавиатура, фокус или контраст"),
    "performance": (6, "неограниченный обход, скачки макета"),
    "distinctness": (5, "отличие только цветом"),
    "polish": (2, "явные шероховатости"),
}


#: Доступность и контраст меряются здесь, а не додумываются. Без этого
#: критерий «accessibility» получал бы полный вес просто за отсутствие
#: измерения — то есть был бы штампом, а не проверкой.
ДОСТУПНОСТЬ = r"""
() => {
  const out = {small_targets: [], heading_skips: [], low_contrast: [], focusable: 0};
  const яркость = (цвет) => {
    const m = (цвет || '').match(/rgba?\(([^)]+)\)/); if (!m) return null;
    const [r, g, b] = m[1].split(',').slice(0, 3).map(v => parseFloat(v) / 255);
    const к = (c) => c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
    return 0.2126 * к(r) + 0.7152 * к(g) + 0.0722 * к(b);
  };
  const фон = (el) => {
    let e = el;
    while (e) {
      const c = getComputedStyle(e).backgroundColor;
      if (c && !/rgba\(0, 0, 0, 0\)|transparent/.test(c)) return c;
      e = e.parentElement;
    }
    return getComputedStyle(document.body).backgroundColor;
  };
  const видим = (el) => { const r = el.getBoundingClientRect(); return r.width > 1 && r.height > 1; };

  for (const el of document.querySelectorAll('a,button,input,[tabindex]')) {
    if (!видим(el)) continue;
    out.focusable += 1;
    const r = el.getBoundingClientRect();
    // Карточка-ссылка сама по себе крупная; мелкими бывают чипы и кнопки.
    const мелкая = r.width < 44 || r.height < 44;
    if (мелкая && !el.closest('.k')) {
      out.small_targets.push({tag: el.tagName.toLowerCase(),
                              cls: (el.className || '').slice(0, 24),
                              w: +r.width.toFixed(1), h: +r.height.toFixed(1)});
    }
  }

  let предыдущий = 0;
  for (const h of document.querySelectorAll('h1,h2,h3,h4,h5,h6')) {
    if (!видим(h)) continue;
    const уровень = +h.tagName[1];
    if (предыдущий && уровень > предыдущий + 1) {
      out.heading_skips.push({from: предыдущий, to: уровень,
                              text: (h.textContent || '').trim().slice(0, 40)});
    }
    предыдущий = уровень;
  }

  for (const el of document.querySelectorAll('p,span,a,h1,h2,h3,li,time')) {
    if (!видим(el)) continue;
    if (!(el.textContent || '').trim()) continue;
    const cs = getComputedStyle(el);
    const l1 = яркость(cs.color), l2 = яркость(фон(el));
    if (l1 === null || l2 === null) continue;
    const отношение = (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
    const размер = parseFloat(cs.fontSize);
    const крупный = размер >= 24 || (размер >= 18.66 && +cs.fontWeight >= 700);
    const порог = крупный ? 3 : 4.5;
    if (отношение < порог) {
      out.low_contrast.push({tag: el.tagName.toLowerCase(), ratio: +отношение.toFixed(2),
                             need: порог, size: размер,
                             text: (el.textContent || '').trim().slice(0, 30)});
    }
  }
  return out;
}
"""


def _измеритель():
    путь = КОРЕНЬ / "automation" / "host" / "nova-visual-audit.py"
    spec = importlib.util.spec_from_file_location("nova_visual_audit", путь)
    модуль = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(модуль)
    return модуль


def измерить(страница: pathlib.Path, снимки: pathlib.Path | None,
             точки=ТОЧКИ) -> list[dict]:
    from playwright.sync_api import sync_playwright

    измеритель = _измеритель()
    адрес = страница.resolve().as_uri()
    результаты = []
    with sync_playwright() as pw:
        браузер = pw.chromium.launch(args=["--disable-dev-shm-usage"])
        try:
            for ширина in точки:
                контекст = браузер.new_context(viewport={"width": ширина, "height": 900})
                стр = контекст.new_page()
                try:
                    стр.goto(адрес, wait_until="load", timeout=45000)
                    стр.wait_for_timeout(250)
                    запись = {"viewport": ширина}
                    запись.update(стр.evaluate(измеритель.ИЗМЕРЕНИЕ))
                    запись["a11y"] = стр.evaluate(ДОСТУПНОСТЬ)
                    if снимки:
                        снимки.mkdir(parents=True, exist_ok=True)
                        файл = снимки / f"{страница.parent.name}-{ширина}.png"
                        стр.screenshot(path=str(файл), full_page=False)
                        запись["screenshot"] = файл.name
                    результаты.append(запись)
                finally:
                    стр.close()
                    контекст.close()
        finally:
            браузер.close()
    return результаты


def оценить(манифест: dict, страницы: list[dict], css_байт: int = 0) -> dict:
    def всего(ключ):
        return sum(len(с.get(ключ) or []) for с in страницы)

    строгие = [
        c for с in страницы for c in (с.get("clipped") or []) if c.get("strict")
    ]
    переполнение = sum(1 for с in страницы if с.get("overflow_x"))
    пустые = sum(с.get("empty_cells", 0) for с in страницы)

    измерено = {
        "HORIZONTAL_OVERFLOW_COUNT": переполнение,
        "CLIPPED_REQUIRED_TEXT_COUNT": len(строгие),
        "TIMESTAMP_ELLIPSIS_COUNT": всего("date_ellipsis"),
        "POSTER_ASPECT_RATIO_VIOLATIONS": всего("poster_ratio_violations"),
        "BROKEN_IMAGE_COUNT": всего("broken_images"),
        "EMPTY_GRID_CELL_COUNT": пустые,
        "ORPHAN_LAST_ROW_COUNT": всего("orphan_rows"),
        "OVERLAP_COUNT": всего("overlaps"),
        "UNINTENDED_GAP_OVER_96PX_COUNT": всего("big_gaps"),
        "SMALL_TOUCH_TARGET_COUNT": sum(len(с.get("a11y", {}).get("small_targets", [])) for с in страницы),
        "HEADING_ORDER_SKIPS": sum(len(с.get("a11y", {}).get("heading_skips", [])) for с in страницы),
        "LOW_CONTRAST_COUNT": sum(len(с.get("a11y", {}).get("low_contrast", [])) for с in страницы),
        "FOCUSABLE_ELEMENTS": max((с.get("a11y", {}).get("focusable", 0) for с in страницы), default=0),
        "CSS_BYTES": css_байт,
    }

    отказы: dict[str, str] = {}
    if измерено["CLIPPED_REQUIRED_TEXT_COUNT"] or измерено["TIMESTAMP_ELLIPSIS_COUNT"]:
        отказы["typography"] = "обрезан обязательный текст"
    if измерено["HORIZONTAL_OVERFLOW_COUNT"] or измерено["OVERLAP_COUNT"]:
        отказы["responsive"] = "переполнение или наложение"
    if измерено["POSTER_ASPECT_RATIO_VIOLATIONS"] or измерено["BROKEN_IMAGE_COUNT"]:
        отказы["media"] = "пропорция постера или битое изображение"
    if измерено["EMPTY_GRID_CELL_COUNT"] or измерено["ORPHAN_LAST_ROW_COUNT"]:
        отказы["grid"] = "пустая ячейка или одинокий хвост ряда"
    if измерено["UNINTENDED_GAP_OVER_96PX_COUNT"]:
        отказы["polish"] = "необъяснённый вертикальный разрыв"
    if измерено["LOW_CONTRAST_COUNT"] or измерено["HEADING_ORDER_SKIPS"]:
        отказы["accessibility"] = (
            f"контраст ниже порога у {измерено['LOW_CONTRAST_COUNT']} элементов, "
            f"пропусков уровня заголовка {измерено['HEADING_ORDER_SKIPS']}"
        )
    if измерено["SMALL_TOUCH_TARGET_COUNT"]:
        отказы["ux"] = f"{измерено['SMALL_TOUCH_TARGET_COUNT']} целей мельче 44×44"
    if измерено["FOCUSABLE_ELEMENTS"] == 0:
        отказы["accessibility"] = "на странице нет ни одного фокусируемого элемента"
    # Бюджет объявлен заданием: 80 КБ на собственные стили пакета.
    if css_байт and css_байт > 80 * 1024:
        отказы["performance"] = f"стили пакета {css_байт} байт при бюджете {80 * 1024}"

    блоки = манифест.get("home_block_order", [])
    сетки = [б for б in блоки if б.get("тип") in ("grid", "feed")]
    if len(блоки) < 5:
        отказы["hierarchy"] = "меньше пяти блоков: композиции нет"
    if len(сетки) >= 3 and len({б.get("грамматика") for б in сетки}) == 1:
        отказы["hierarchy"] = "три и более одинаковых полки подряд"

    баллы = {}
    for критерий, (вес, _) in РУБРИКА.items():
        баллы[критерий] = 0 if критерий in отказы else вес
    итог = sum(баллы.values())

    return {
        "template_id": манифест["template_id"],
        "slug": манифест["slug"],
        "measured": измерено,
        "criteria": баллы,
        "hard_fails": отказы,
        "HARD_FAIL_COUNT": len(отказы),
        "TOTAL_SCORE": итог,
        "PASS": итог >= 90 and not отказы,
        "OWNER_VISUAL_REVIEW_REQUIRED": True,
        "SELF_REPORTED_OWNER_ACCEPTANCE": False,
        "scored_at_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", required=True)
    parser.add_argument("--preview", required=True, help="каталог с отрисованным index.html")
    parser.add_argument("--record")
    parser.add_argument("--screenshots")
    args = parser.parse_args()

    пакет = pathlib.Path(args.package)
    манифест = json.loads((пакет / "template.json").read_text(encoding="utf-8"))
    страница = pathlib.Path(args.preview) / "index.html"
    if not страница.is_file():
        print(f"нет отрисованной страницы: {страница}", file=sys.stderr)
        return 2

    css_байт = sum(
        (пакет / имя).stat().st_size
        for имя in ("tokens.css", "layout.css", "components.css")
        if (пакет / имя).is_file()
    )
    страницы = измерить(страница, pathlib.Path(args.screenshots) if args.screenshots else None)
    отчёт = оценить(манифест, страницы, css_байт)
    отчёт["pages"] = страницы
    if args.record:
        pathlib.Path(args.record).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(args.record).write_text(
            json.dumps(отчёт, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in отчёт.items() if k != "pages"},
                     ensure_ascii=False, indent=2))
    return 0 if отчёт["PASS"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
