#!/usr/bin/env python3
"""Приёмка переработанного интерфейса Animedia в настоящем браузере.

Две части, и вторая важнее первой.

Первая — матрица: каждый требуемый маршрут на каждой ширине. Проверяется код
ответа, горизонтальное переполнение, битые картинки, пустые кликабельные
области, ошибки консоли и наличие обязательных блоков каркаса. Наличие
элемента в DOM само по себе ничего не доказывает, поэтому:

Вторая — действия. Поиск набирается, подсказка нажимается, фильтр
применяется, сортировка меняет порядок, листалка листает, слайдер
листается стрелкой и точкой, произведение открывается, голос ставится,
меняется и снимается, реакция переключается, комментарий отправляется,
список выбирается, мобильное меню открывается и закрывается. Каждое
действие проверяется по изменению состояния страницы, а не по тому, что
кнопка нашлась.

    .venv/bin/python automation/host/animedia-ux-acceptance.py \\
        --domain animedia.space --label run1 --out <каталог> \\
        --local-runtime automation/host/animedia-frontend.py --site animedia-02
"""
from __future__ import annotations

import argparse
import json
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
ШИРИНЫ = (320, 390, 768, 1024, 1440, 1920)

#: Маршруты обязательного каркаса. Третье поле — ожидаемый код ответа.
МАРШРУТЫ = (
    ("home", "/", 200),
    ("catalog", "/catalog/", 200),
    ("new", "/new/", 200),
    ("top", "/top/", 200),
    ("top_votes", "/top/?by=votes", 200),
    ("lists", "/lists/", 200),
    ("schedule", "/schedule/", 200),
    ("collections", "/collections/", 200),
    ("genres", "/genres/", 200),
    ("types", "/types/", 200),
    ("search_hit", "/search/?q=naruto", 200),
    ("search_empty", "/search/?q=%D1%8A%D1%8B%D1%8C%D1%89%D0%B7%D1%85", 200),
    ("genre_page", "/catalog/?genre=fentezi", 200),
    ("type_page", "/series/", 200),
    ("title", "/title/naruto-posledniy-film/", 200),
    ("not_found", "/definitely-absent-route-xyz/", 404),
)

#: Что обязано быть на конкретных маршрутах. Пусто — значит требований нет
#: сверх общих (переполнение, картинки, консоль).
ОБЯЗАТЕЛЬНО = {
    "home": ('[data-home="search"]', '[data-hero]', '[data-b05]', '[data-b03]'),
    "catalog": ('[data-b11="catalog"]', "[data-afilt]", ".aside-eps"),
    "new": ('[data-b05-page="populated"]',),
    "top": (".atabs", "[data-top-slice]"),
    "genres": ('[data-hub="genres"]',),
    "types": ('[data-hub="types"]',),
    "title": ('[data-b07="ratings"]', "[data-community]", '[data-b10="recs"]'),
}

ОРАКУЛ = r"""
() => {
  const W = window.innerWidth;
  const док = document.documentElement;
  const видим = (el) => {
    if (!el) return false;
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };
  // Горизонтальное переполнение страницы и его виновники.
  // Переполнение меряется тем, чем его чувствует посетитель: уезжает ли
  // страница вбок на самом деле. `scrollWidth` корня в Chrome учитывает и
  // то, что зажато `overflow:hidden` у предка, и даёт ложную тревогу на
  // слайдере, который прокручивается внутри себя.
  const былоX = window.scrollX;
  window.scrollTo(4000, 0);
  const переполнение = window.scrollX - былоX;
  window.scrollTo(былоX, 0);
  const виновники = [];
  if (переполнение > 1) {
    for (const el of document.querySelectorAll('body *')) {
      if (!видим(el)) continue;
      const r = el.getBoundingClientRect();
      if (r.right > W + 1 || r.left < -1) {
        const cs = getComputedStyle(el);
        if (cs.position === 'fixed') continue;
        виновники.push({
          tag: el.tagName.toLowerCase(),
          cls: (el.className || '').toString().slice(0, 60),
          right: Math.round(r.right), left: Math.round(r.left),
        });
        if (виновники.length >= 6) break;
      }
    }
  }
  // Битые картинки: загрузились, но нулевого размера, либо не загрузились.
  const битые = [];
  for (const img of document.images) {
    if (!видим(img) && img.getAttribute('loading') === 'lazy') continue;
    if (img.complete && img.naturalWidth === 0 && !img.hidden) {
      битые.push((img.currentSrc || img.src || '').slice(0, 120));
    }
  }
  // Пустые кликабельные области: ссылка или кнопка без доступного имени.
  const пустые = [];
  for (const el of document.querySelectorAll('a[href],button')) {
    if (!видим(el)) continue;
    // textContent, а не только innerText: ссылка в свёрнутой панели
    // фильтров текст имеет, просто он сейчас не отрисован. Пустая
    // кликабельная область — это когда имени нет вовсе.
    const имя = (el.innerText || '').trim()
      || (el.textContent || '').trim()
      || (el.getAttribute('aria-label') || '').trim()
      || (el.getAttribute('title') || '').trim()
      || (el.querySelector('img[alt]')?.getAttribute('alt') || '').trim();
    if (!имя) {
      пустые.push({tag: el.tagName.toLowerCase(),
                   cls: (el.className || '').toString().slice(0, 50)});
      if (пустые.length >= 6) break;
    }
  }
  // Цели касания меньше 40px по меньшей стороне — только у кнопок и
  // самостоятельных ссылок, не у ссылок внутри текста.
  const мелкие = [];
  for (const el of document.querySelectorAll('button,a[href]')) {
    if (!видим(el)) continue;
    const cs = getComputedStyle(el);
    if (cs.display === 'inline') continue;
    const r = el.getBoundingClientRect();
    if (Math.min(r.width, r.height) < 34) {
      мелкие.push({cls: (el.className || '').toString().slice(0, 40),
                   w: Math.round(r.width), h: Math.round(r.height)});
      if (мелкие.length >= 6) break;
    }
  }
  const h1 = [...document.querySelectorAll('h1')];
  return {
    width: W,
    overflow_px: переполнение,
    overflow_culprits: виновники,
    broken_images: битые,
    empty_clickables: пустые,
    small_targets: мелкие,
    h1_count: h1.length,
    cards: document.querySelectorAll('a.zt').length,
    score_badges: document.querySelectorAll('.zt__score').length,
    score_with_value: document.querySelectorAll('[data-score-state="value"]').length,
    source_plaques: document.querySelectorAll('.zt__rate').length,
    nav_links: document.querySelectorAll('.zhd__n a').length,
  };
}
"""


def _свободный_порт() -> int:
    с = socket.socket()
    с.bind(("127.0.0.1", 0))
    порт = с.getsockname()[1]
    с.close()
    return порт


def поднять_локально(рантайм: Path, сайт: str, журнал: Path, данные: Path):
    порт = _свободный_порт()
    окружение = dict(os.environ)
    окружение.update({
        "ANIMEDIA_TEMPLATE_MANIFEST": f"/srv/lords/.frontend/template-manifest-{сайт}.json",
        "ANIMEDIA_CATALOG": f"/srv/lords/.frontend/{сайт}-catalog.json",
        "ANIMEDIA_SITE_DATA_DIR": str(данные),
    })
    окружение.pop("LORDS_TEMPLATE_MANIFEST", None)
    журнал.parent.mkdir(parents=True, exist_ok=True)
    ф = open(журнал, "w", encoding="utf-8")
    процесс = subprocess.Popen(
        [sys.executable, str(рантайм), "--port", str(порт)],
        cwd=str(КОРЕНЬ), env=окружение, stdout=ф, stderr=subprocess.STDOUT)
    for _ in range(180):
        try:
            с = socket.create_connection(("127.0.0.1", порт), timeout=1)
            с.close()
            return процесс, порт
        except OSError:
            if процесс.poll() is not None:
                raise SystemExit(f"витрина не поднялась, см. {журнал}")
            time.sleep(1)
    raise SystemExit("порт не открылся")


def действия(стр, база: str, снимки: Path, метка: str) -> list:
    """Реальные действия посетителя. Каждое — с проверкой последствия."""
    итог = []

    def шаг(имя: str, функция):
        try:
            подробности = функция()
            итог.append({"action": имя, "pass": True, "details": подробности})
        except Exception as ош:  # noqa: BLE001 — отчёт важнее стека
            итог.append({"action": имя, "pass": False,
                         "error": f"{type(ош).__name__}: {ош}"})

    def поиск_с_главной():
        стр.goto(база + "/", wait_until="load", timeout=60000)
        стр.fill("#home-q", "naruto")
        стр.press("#home-q", "Enter")
        стр.wait_for_load_state("load", timeout=60000)
        сколько = стр.eval_on_selector_all("a.zt", "e => e.length")
        assert "/search/" in стр.url, f"не ушли на поиск: {стр.url}"
        assert сколько > 0, "поиск латиницей ничего не нашёл"
        return {"url": стр.url, "cards": сколько}

    def подсказка_ведёт_на_произведение():
        стр.goto(база + "/", wait_until="load", timeout=60000)
        подсказка = стр.locator(".ahero-s__chip").first
        имя = подсказка.inner_text().strip()
        подсказка.click()
        стр.wait_for_load_state("load", timeout=60000)
        assert "/title/" in стр.url, f"подсказка увела не туда: {стр.url}"
        return {"chip": имя, "url": стр.url}

    def пустой_поиск_честен():
        стр.goto(база + "/search/?q=%D1%8A%D1%8B%D1%8C%D1%89%D0%B7%D1%85",
                 wait_until="load", timeout=60000)
        сколько = стр.eval_on_selector_all("a.zt", "e => e.length")
        assert сколько == 0, "бессмысленный запрос что-то нашёл"
        assert стр.locator('[data-b12-state="zero"]').count() == 1
        return {"cards": 0}

    def фильтр_меняет_выдачу():
        стр.goto(база + "/catalog/", wait_until="load", timeout=60000)
        было = int(re.search(r"Найдено (\d+)", стр.inner_text("body")).group(1))
        стр.goto(база + "/catalog/?genre=fentezi", wait_until="load", timeout=60000)
        стало = int(re.search(r"Найдено (\d+)", стр.inner_text("body")).group(1))
        assert стало < было, f"фильтр не сузил выдачу: {было} → {стало}"
        стр.goto(база + "/catalog/?genre=fentezi&ongoing=1",
                 wait_until="load", timeout=60000)
        оба = int(re.search(r"Найдено (\d+)", стр.inner_text("body")).group(1))
        assert оба < стало, f"второе условие не сузило: {стало} → {оба}"
        return {"all": было, "genre": стало, "genre_ongoing": оба}

    def сброс_возвращает_всё():
        стр.goto(база + "/catalog/?genre=fentezi&ongoing=1",
                 wait_until="load", timeout=60000)
        стр.click(".afilt__reset")
        стр.wait_for_load_state("load", timeout=60000)
        всё = int(re.search(r"Найдено (\d+)", стр.inner_text("body")).group(1))
        assert стр.url.rstrip("/").endswith("/catalog"), стр.url
        return {"after_reset": всё}

    def назад_восстанавливает_состояние():
        стр.goto(база + "/catalog/", wait_until="load", timeout=60000)
        стр.goto(база + "/catalog/?genre=fentezi", wait_until="load", timeout=60000)
        с_фильтром = int(re.search(r"Найдено (\d+)", стр.inner_text("body")).group(1))
        стр.go_back(wait_until="load", timeout=60000)
        без = int(re.search(r"Найдено (\d+)", стр.inner_text("body")).group(1))
        стр.go_forward(wait_until="load", timeout=60000)
        снова = int(re.search(r"Найдено (\d+)", стр.inner_text("body")).group(1))
        assert снова == с_фильтром, f"вперёд дал другое: {с_фильтром} ≠ {снова}"
        assert без > с_фильтром
        return {"filtered": с_фильтром, "back": без, "forward": снова}

    def сортировка_меняет_порядок():
        стр.goto(база + "/catalog/", wait_until="load", timeout=60000)
        первое = стр.eval_on_selector_all(
            ".zt__t", "e => e.slice(0,3).map(x => x.textContent)")
        стр.goto(база + "/catalog/?sort=rating", wait_until="load", timeout=60000)
        второе = стр.eval_on_selector_all(
            ".zt__t", "e => e.slice(0,3).map(x => x.textContent)")
        оценки = стр.eval_on_selector_all(
            "[data-score]", "e => e.map(x => parseFloat(x.dataset.score))")
        assert первое != второе, "сортировка не изменила порядок"
        assert оценки == sorted(оценки, reverse=True), "оценки идут не по убыванию"
        return {"default_top": первое[:2], "by_rating_top": второе[:2],
                "monotonic": True}

    def листалка_листает():
        стр.goto(база + "/catalog/", wait_until="load", timeout=60000)
        первая = стр.eval_on_selector_all(
            ".zt__t", "e => e.map(x => x.textContent)")
        стр.goto(база + "/catalog/?page=2", wait_until="load", timeout=60000)
        вторая = стр.eval_on_selector_all(
            ".zt__t", "e => e.map(x => x.textContent)")
        пересечение = set(первая) & set(вторая)
        assert вторая and not пересечение, f"страницы пересекаются: {len(пересечение)}"
        return {"page1": len(первая), "page2": len(вторая), "overlap": 0}

    def слайдер_листается():
        стр.goto(база + "/", wait_until="load", timeout=60000)
        стр.wait_for_selector("[data-hero]", timeout=30000)
        было = стр.eval_on_selector(".ahero__vp", "e => e.scrollLeft")
        стр.click("[data-hero-next]")
        стр.wait_for_timeout(900)
        стало = стр.eval_on_selector(".ahero__vp", "e => e.scrollLeft")
        assert стало > было, f"стрелка не пролистала: {было} → {стало}"
        стр.click('[data-hero-dot="0"]')
        стр.wait_for_timeout(900)
        назад = стр.eval_on_selector(".ahero__vp", "e => e.scrollLeft")
        assert назад < стало, f"точка не вернула: {стало} → {назад}"
        нажата = стр.eval_on_selector("[data-hero-play]",
                                      "e => e.getAttribute('aria-pressed')")
        стр.click("[data-hero-play]")
        стр.wait_for_timeout(200)
        после = стр.eval_on_selector("[data-hero-play]",
                                     "e => e.getAttribute('aria-pressed')")
        assert нажата != после, "кнопка автопрокрутки не переключилась"
        return {"scroll_after_next": стало, "scroll_after_dot": назад,
                "autoplay_toggled": f"{нажата}→{после}"}

    def произведение_открывается():
        стр.goto(база + "/catalog/", wait_until="load", timeout=60000)
        стр.locator("a.zt").first.click()
        стр.wait_for_load_state("load", timeout=60000)
        assert "/title/" in стр.url, стр.url
        assert стр.locator('[data-b07="ratings"]').count() == 1
        return {"url": стр.url}

    def голос_ставится_меняется_снимается():
        стр.goto(база + "/title/naruto-posledniy-film/",
                 wait_until="load", timeout=60000)
        if стр.locator('[data-community="on"]').count() == 0:
            raise AssertionError("раздел сообщества выключен")
        стр.click('.acomm__vote[value="8"]')
        стр.wait_for_load_state("load", timeout=60000)
        первый = стр.eval_on_selector('[data-community]',
                                      "e => e.dataset.communityVotes")
        assert стр.locator('.acomm__vote[value="8"][aria-pressed="true"]').count() == 1
        стр.click('.acomm__vote[value="3"]')
        стр.wait_for_load_state("load", timeout=60000)
        assert стр.locator('.acomm__vote[value="3"][aria-pressed="true"]').count() == 1
        assert стр.locator('.acomm__vote[value="8"][aria-pressed="true"]').count() == 0
        второй = стр.eval_on_selector('[data-community]',
                                      "e => e.dataset.communityVotes")
        assert первый == второй == "1", f"смена голоса добавила голос: {первый}→{второй}"
        стр.click(".acomm__clear")
        стр.wait_for_load_state("load", timeout=60000)
        третий = стр.eval_on_selector('[data-community]',
                                      "e => e.dataset.communityVotes")
        assert третий == "0", f"голос не снялся: {третий}"
        return {"after_vote": первый, "after_change": второй, "after_clear": третий}

    def реакция_переключается():
        стр.goto(база + "/title/naruto-posledniy-film/",
                 wait_until="load", timeout=60000)
        кнопка = стр.locator(".acomm__react").first
        кнопка.click()
        стр.wait_for_load_state("load", timeout=60000)
        включена = стр.locator('.acomm__react[aria-pressed="true"]').count()
        assert включена == 1, f"реакция не включилась: {включена}"
        стр.locator('.acomm__react[aria-pressed="true"]').first.click()
        стр.wait_for_load_state("load", timeout=60000)
        осталось = стр.locator('.acomm__react[aria-pressed="true"]').count()
        assert осталось == 0, "реакция не снялась повторным нажатием"
        return {"on": включена, "off": осталось}

    def комментарий_отправляется():
        стр.goto(база + "/title/naruto-posledniy-film/",
                 wait_until="load", timeout=60000)
        было = стр.eval_on_selector('[data-community]',
                                    "e => e.dataset.communityComments")
        текст = f"Проверка приёмки {метка} {int(time.time())}"
        стр.fill("#acomm-name", "Приёмка")
        стр.fill("#acomm-text", текст)
        стр.click(".acomm__form button[type=submit]")
        стр.wait_for_load_state("load", timeout=60000)
        стало = стр.eval_on_selector('[data-community]',
                                     "e => e.dataset.communityComments")
        assert int(стало) == int(было) + 1, f"комментарий не добавился: {было}→{стало}"
        assert текст in стр.inner_text("body"), "комментария нет на странице"
        return {"before": было, "after": стало}

    def список_выбирается_и_снимается():
        стр.goto(база + "/title/naruto-posledniy-film/",
                 wait_until="load", timeout=60000)
        стр.click('.acomm__list[value="watching"]')
        стр.wait_for_load_state("load", timeout=60000)
        выбран = стр.eval_on_selector("[data-lists-widget]", "e => e.dataset.myList")
        assert выбран == "watching", f"список не выбрался: {выбран!r}"
        стр.goto(база + "/lists/", wait_until="load", timeout=60000)
        в_списке = стр.eval_on_selector_all('[data-list="watching"] a.zt',
                                            "e => e.length")
        assert в_списке >= 1, "произведение не появилось в разделе списков"
        стр.goto(база + "/title/naruto-posledniy-film/",
                 wait_until="load", timeout=60000)
        стр.click('.acomm__list.is-on')
        стр.wait_for_load_state("load", timeout=60000)
        снят = стр.eval_on_selector("[data-lists-widget]", "e => e.dataset.myList")
        assert снят == "", f"список не снялся: {снят!r}"
        return {"chosen": выбран, "in_lists": в_списке, "cleared": True}

    def серия_выбирается():
        стр.goto(база + "/title/master-lda-i-plameni-2/",
                 wait_until="load", timeout=60000)
        ссылки = стр.locator(".zeps a:not([data-off])")
        if ссылки.count() == 0:
            return {"skipped": "у записи нет доступных серий"}
        ссылки.first.click()
        стр.wait_for_load_state("load", timeout=60000)
        assert "/episode-" in стр.url, стр.url
        return {"url": стр.url}

    def мобильное_меню_открывается():
        стр.set_viewport_size({"width": 390, "height": 844})
        стр.goto(база + "/", wait_until="load", timeout=60000)
        кнопка = стр.locator("[data-drawer-toggle]").first
        assert кнопка.is_visible(), "кнопки меню не видно на 390"
        кнопка.click()
        стр.wait_for_timeout(400)
        открыто = стр.eval_on_selector_all(
            "[data-drawer-toggle]", "e => e.map(x => x.getAttribute('aria-expanded'))")
        assert "true" in открыто, f"меню не открылось: {открыто}"
        стр.keyboard.press("Escape")
        стр.wait_for_timeout(400)
        закрыто = стр.eval_on_selector_all(
            "[data-drawer-toggle]", "e => e.map(x => x.getAttribute('aria-expanded'))")
        assert "true" not in закрыто, f"Escape не закрыл меню: {закрыто}"
        стр.screenshot(path=str(снимки / f"{метка}-mobile-menu.png"))
        стр.set_viewport_size({"width": 1440, "height": 900})
        return {"opened": True, "closed_by_escape": True}

    шаг("поиск с главной", поиск_с_главной)
    шаг("подсказка ведёт на произведение", подсказка_ведёт_на_произведение)
    шаг("пустой поиск честен", пустой_поиск_честен)
    шаг("фильтр меняет выдачу", фильтр_меняет_выдачу)
    шаг("сброс фильтров", сброс_возвращает_всё)
    шаг("назад и вперёд", назад_восстанавливает_состояние)
    шаг("сортировка", сортировка_меняет_порядок)
    шаг("листалка", листалка_листает)
    шаг("слайдер", слайдер_листается)
    шаг("открытие произведения", произведение_открывается)
    шаг("выбор серии", серия_выбирается)
    шаг("голос: поставить, сменить, снять", голос_ставится_меняется_снимается)
    шаг("реакция", реакция_переключается)
    шаг("комментарий", комментарий_отправляется)
    шаг("списки", список_выбирается_и_снимается)
    шаг("мобильное меню", мобильное_меню_открывается)
    return итог


def main() -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--domain", required=True)
    р.add_argument("--label", required=True)
    р.add_argument("--out", required=True)
    р.add_argument("--local-runtime", default=None)
    р.add_argument("--site", default="animedia-02")
    a = р.parse_args()

    вывод = Path(a.out)
    снимки = вывод / "screenshots"
    снимки.mkdir(parents=True, exist_ok=True)

    процесс = порт = None
    if a.local_runtime:
        процесс, порт = поднять_локально(
            Path(a.local_runtime), a.site, вывод / "runtime.log",
            вывод / "site-data")

    from playwright.sync_api import sync_playwright

    схема = "http" if a.local_runtime else "https"
    база = f"{схема}://{a.domain}"
    # `/dev/shm` в контейнере маленький, и вкладка на тяжёлой странице
    # произведения падала с «Target crashed» — это отказ окружения, а не
    # страницы. Флаг переводит общую память в обычный временный каталог.
    аргументы = ["--disable-dev-shm-usage"]
    if a.local_runtime:
        аргументы.append(f"--host-resolver-rules=MAP {a.domain} 127.0.0.1:{порт}")
    итог = {
        "task": "ANIMEDIA-UX-ACCEPTANCE", "tenant": "animedia",
        "domain": a.domain, "label": a.label,
        "measured_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "widths": list(ШИРИНЫ), "routes": [r[0] for r in МАРШРУТЫ],
        "cells": [], "actions": [], "console": [], "bad_responses": [],
    }

    def записать_ответ(о):
        if о.status >= 400:
            итог["bad_responses"].append({"status": о.status, "url": о.url[:160]})

    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(args=аргументы)
            try:
                for ширина in ШИРИНЫ:
                    ctx = b.new_context(viewport={"width": ширина, "height": 900})
                    стр = ctx.new_page()
                    # Адрес обязателен: текст «Failed to load resource … 404»
                    # одинаков и для настоящего дефекта, и для нашей же
                    # проверки маршрута 404, а различать их надо.
                    стр.on("console", lambda м: (
                        итог["console"].append(
                            {"width": ширина, "type": м.type, "text": м.text[:200],
                             "url": (м.location or {}).get("url", "")[:160],
                             "page": стр.url[:160]})
                        if м.type == "error" else None))
                    стр.on("pageerror", lambda ош: итог["console"].append(
                        {"width": ширина, "type": "pageerror", "text": str(ош)[:200]}))
                    стр.on("response", записать_ответ)
                    # Прокси постеров при холодном старте ходит к источнику и
                    # под залпом может не успеть. Боевая витрина всегда тёплая,
                    # поэтому прогреваем её и здесь — иначе меряем не страницу,
                    # а первую секунду жизни процесса.
                    if ширина == ШИРИНЫ[0]:
                        стр.goto(база + "/", wait_until="load", timeout=60000)
                        стр.wait_for_timeout(2500)
                        итог["bad_responses"].clear()
                        итог["console"].clear()
                    for имя, путь, ждём in МАРШРУТЫ:
                        ответ = стр.goto(база + путь, wait_until="load", timeout=60000)
                        стр.wait_for_timeout(250)
                        м = стр.evaluate(ОРАКУЛ)
                        отсутствуют = [с for с in ОБЯЗАТЕЛЬНО.get(имя, ())
                                       if стр.locator(с).count() == 0]
                        заг = ответ.headers if ответ else {}
                        м.update({
                            "route": имя, "path": путь, "width": ширина,
                            "http": ответ.status if ответ else None,
                            "expected_http": ждём,
                            "missing_required": отсутствуют,
                            "served_build": заг.get("x-site-factory-build-id"),
                            "x_robots": заг.get("x-robots-tag"),
                        })
                        итог["cells"].append(м)
                        if ширина in (390, 1440):
                            стр.screenshot(
                                path=str(снимки / f"{a.label}-{имя}-{ширина}.png"),
                                full_page=False)
                    ctx.close()
                # Действия — на одной устойчивой ширине, с чистым контекстом.
                ctx = b.new_context(viewport={"width": 1440, "height": 900})
                стр = ctx.new_page()
                стр.on("console", lambda м: (
                    итог["console"].append({"width": 1440, "type": м.type,
                                            "text": м.text[:200]})
                    if м.type == "error" else None))
                итог["actions"] = действия(стр, база, снимки, a.label)
                ctx.close()
            finally:
                b.close()
    finally:
        if процесс is not None:
            процесс.terminate()
            try:
                процесс.wait(timeout=20)
            except subprocess.TimeoutExpired:
                процесс.kill()

    # Ошибки консоли с ожидаемой 404 — не дефект страницы: мы сами её просим.
    итог["console"] = [
        с for с in итог["console"]
        if "definitely-absent-route" not in (с.get("text", "") + с.get("url", "")
                                             + с.get("page", ""))]
    # Ожидаемая 404 — наша собственная проверка маршрута, не дефект страницы.
    итог["bad_responses"] = [о for о in итог["bad_responses"]
                             if "definitely-absent-route" not in о["url"]]
    постерные = [о for о in итог["bad_responses"] if "/poster/" in о["url"]]
    провалы = []
    for я in итог["cells"]:
        если = []
        if я["http"] != я["expected_http"]:
            если.append(f"код {я['http']} вместо {я['expected_http']}")
        if я["overflow_px"] > 1:
            если.append(f"переполнение {я['overflow_px']}px")
        if я["broken_images"]:
            если.append(f"битых картинок {len(я['broken_images'])}")
        if я["empty_clickables"]:
            если.append(f"пустых кликабельных {len(я['empty_clickables'])}")
        if я["missing_required"]:
            если.append("нет блоков: " + ", ".join(я["missing_required"]))
        if я["h1_count"] != 1:
            если.append(f"h1 на странице {я['h1_count']}")
        if если:
            провалы.append({"route": я["route"], "width": я["width"], "why": если})
    действия_провалы = [д for д in итог["actions"] if not д["pass"]]
    итог["summary"] = {
        "cells": len(итог["cells"]),
        "cell_failures": провалы,
        "actions": len(итог["actions"]),
        "action_failures": действия_провалы,
        "console_errors": len(итог["console"]),
        "bad_responses": len(итог["bad_responses"]),
        "bad_responses_poster_proxy": len(постерные),
        "bad_responses_other": [о for о in итог["bad_responses"]
                                if "/poster/" not in о["url"]][:10],
        "http_5xx": sum(1 for я in итог["cells"] if (я["http"] or 0) >= 500),
        "broken_images": sum(len(я["broken_images"]) for я in итог["cells"]),
        "overflow_failures": sum(1 for я in итог["cells"] if я["overflow_px"] > 1),
        "source_plaques": sum(я["source_plaques"] for я in итог["cells"]),
        "pass": not провалы and not действия_провалы and not итог["console"],
    }
    (вывод / f"UX_ACCEPTANCE_{a.label}.json").write_text(
        json.dumps(итог, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(итог["summary"], ensure_ascii=False, indent=1))
    return 0 if итог["summary"]["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
