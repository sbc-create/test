#!/usr/bin/env python3
"""Браузерная приёмка витрины Zona: измерение, а не утверждение.

Что здесь снимается на каждой ширине и каждой странице:

* горизонтальное переполнение документа;
* обрезанный текст, не объявленный обрезкой;
* карточки без названия и пустые кликабельные зоны;
* битые картинки;
* невидимые и перекрытые органы управления;
* сдвиг раскладки (CLS) и высота первого экрана;
* заполненность сетки;
* число H1 и уникальность DOM-идентификаторов;
* видимый фокус.

И отдельно — НАСТОЯЩЕЕ переключение слайдера: после нажатия, клавиши и жеста
сверяются идентификатор активного слайда, заголовок панели, картинка и адрес
CTA. Тест, проверяющий наличие кнопки, доказывает наличие кнопки и ничего
больше.

Картинки внешних доменов подменяются локальной заглушкой той же пропорции:
иначе в песочнице без сети «битыми» оказались бы все постеры сразу, и
измерение говорило бы о сети, а не о витрине. Скрипт провайдера плеера
отклоняется по той же причине и учитывается отдельно.
"""
from __future__ import annotations

import argparse
import json
import re
import struct
import sys
import zlib
from pathlib import Path

ШИРИНЫ = [320, 390, 768, 1024, 1440, 1920]


def png_заглушка(ширина: int, высота: int, цвет=(32, 38, 46)) -> bytes:
    """PNG нужной пропорции с мягким вертикальным градиентом.

    Ровная заливка делала контактный лист нечитаемым: все постеры сливались в
    одно тёмное поле, и по снимку нельзя было понять ни плотность сетки, ни
    ритм ленты. Цвет выводится из адреса картинки, поэтому у разных тайтлов
    разные плашки — композиция читается, а выдуманного содержимого нет.
    """
    строки = []
    for y in range(высота):
        k = 0.75 + 0.5 * (y / max(1, высота - 1))
        пиксель = bytes(min(255, int(c * k)) for c in цвет)
        строки.append(b"\x00" + пиксель * ширина)
    сырьё = b"".join(строки)

    def кусок(тип: bytes, данные: bytes) -> bytes:
        return (struct.pack(">I", len(данные)) + тип + данные
                + struct.pack(">I", zlib.crc32(тип + данные) & 0xFFFFFFFF))

    return (b"\x89PNG\r\n\x1a\n"
            + кусок(b"IHDR", struct.pack(">IIBBBBB", ширина, высота, 8, 2, 0, 0, 0))
            + кусок(b"IDAT", zlib.compress(сырьё, 6))
            + кусок(b"IEND", b""))


def цвет_по_адресу(url: str) -> tuple:
    """Устойчивый приглушённый цвет из адреса: два прогона дают один снимок."""
    h = zlib.crc32(url.encode("utf-8"))
    return (46 + (h & 0x3F), 54 + ((h >> 6) & 0x3F), 66 + ((h >> 12) & 0x3F))


_КЭШ_ЗАГЛУШЕК: dict = {}


def заглушка_для(url: str, широкая: bool = False) -> bytes:
    ключ = (url, широкая)
    if ключ not in _КЭШ_ЗАГЛУШЕК:
        ц = цвет_по_адресу(url)
        _КЭШ_ЗАГЛУШЕК[ключ] = (png_заглушка(320, 180, ц) if широкая
                               else png_заглушка(200, 300, ц))
    return _КЭШ_ЗАГЛУШЕК[ключ]

ИЗМЕРЕНИЕ_JS = r"""
() => {
  const вне = [];
  const видимый = (el) => {
    const r = el.getBoundingClientRect();
    const s = getComputedStyle(el);
    return r.width >= 1 && r.height >= 1 && s.visibility !== 'hidden' &&
           s.display !== 'none' && parseFloat(s.opacity || '1') > 0.01;
  };
  // Скрытая вкладка — это замысел, а не пропавшая карточка. Панели табов
  // помечены `hidden`, и считать их содержимое дефектом значит требовать,
  // чтобы все три вкладки были открыты разом.
  const скрыт_замыслом = (el) => !!el.closest('[hidden], [aria-hidden="true"]');

  // Попадание проверяется ТОЛЬКО в видимой области. Раньше точка зажималась
  // краем экрана, и элемент ниже сгиба «перекрывался» первым, что попалось
  // в зажатой точке, — измерение говорило о зажиме, а не о вёрстке.
  const перекрыт = (el) => {
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) return true;
    if (r.bottom < 0 || r.top > innerHeight || r.right < 0 || r.left > innerWidth) {
      return null;  // вне экрана — не проверяемо здесь
    }
    const x = r.left + r.width / 2;
    const y = r.top + r.height / 2;
    if (x < 0 || x > innerWidth || y < 0 || y > innerHeight) return null;
    const сверху = document.elementFromPoint(x, y);
    return !(сверху && (сверху === el || el.contains(сверху) || сверху.contains(el)));
  };

  // Переполнение документа
  const overflow = Math.max(0, document.documentElement.scrollWidth - innerWidth);

  // Элементы шире экрана, не объявленные прокруткой
  const широкие = [...document.querySelectorAll('body *')].filter(el => {
    if (el.closest('[data-scroller]')) return false;
    const r = el.getBoundingClientRect();
    return r.width > innerWidth + 1 && видимый(el);
  }).slice(0, 8).map(el => el.className || el.tagName);

  // Обрезанный текст без объявления
  const обрезано = [...document.querySelectorAll('body *')].filter(el => {
    if (el.children.length) return false;
    if (el.closest('[data-clamp-allowed],[data-scroller]')) return false;
    if (!el.textContent || !el.textContent.trim()) return false;
    const s = getComputedStyle(el);
    if (s.overflow === 'visible' && s.textOverflow !== 'ellipsis') return false;
    return el.scrollWidth > el.clientWidth + 2 || el.scrollHeight > el.clientHeight + 2;
  }).slice(0, 8).map(el => ({ cls: el.className, text: el.textContent.trim().slice(0, 40) }));

  // Карточки
  const все_карточки = [...document.querySelectorAll('[data-testid="title-card"]')];
  const скрытые_вкладкой = все_карточки.filter(скрыт_замыслом).length;
  const карточки = все_карточки.filter(c => !скрыт_замыслом(c));
  const без_названия = карточки.filter(c => {
    const t = c.querySelector('.zt__t');
    return !t || !t.textContent.trim() || !видимый(t);
  }).length;
  const пустые = карточки.filter(c => !видимый(c)).length;
  const без_ссылки = карточки.filter(c => !c.getAttribute('href')).length;
  const неоткликаемые = карточки.filter(c => перекрыт(c) === true).length;
  const непроверенные = карточки.filter(c => перекрыт(c) === null).length;

  // Картинки: отдельно «битые» и отдельно «не загрузились»
  const картинки = [...document.images];
  const битые = картинки.filter(i => i.complete && i.naturalWidth === 0).length;
  const помечены = картинки.filter(i => i.getAttribute('data-broken') === '1').length;

  // Органы управления
  const кнопки = [...document.querySelectorAll('button, [role="tab"], a.zrl__btn')]
                   .filter(b => !скрыт_замыслом(b));
  const невидимые = кнопки.filter(b => !видимый(b)).map(b => b.getAttribute('aria-label') || b.className);
  const перекрытые = кнопки.filter(b => видимый(b) && перекрыт(b) === true)
                           .map(b => b.getAttribute('aria-label') || b.className);
  const мелкие = кнопки.filter(b => {
    if (!видимый(b)) return false;
    const r = b.getBoundingClientRect();
    return r.width < 24 || r.height < 24;
  }).map(b => b.getAttribute('aria-label') || b.className);

  // Мёртвая полоса: секция заметно выше собственного содержимого. Так
  // ловится пустой первый экран, который не является ни переполнением, ни
  // пропавшим элементом, — измеримый только через разницу высот.
  const мёртвые = [];
  for (const sec of document.querySelectorAll('section')) {
    if (скрыт_замыслом(sec)) continue;
    const r = sec.getBoundingClientRect();
    if (r.height < 160) continue;
    let верх = Infinity, низ = -Infinity;
    for (const el of sec.querySelectorAll('*')) {
      if (!видимый(el)) continue;
      if (el.children.length && !el.matches('img,video,svg,canvas')) continue;
      const b = el.getBoundingClientRect();
      if (b.height < 1 || b.width < 1) continue;
      верх = Math.min(верх, b.top);
      низ = Math.max(низ, b.bottom);
    }
    if (верх === Infinity) continue;
    const пусто = Math.round(r.height - (низ - верх));
    if (пусто > 200) {
      мёртвые.push({ cls: sec.className, height: Math.round(r.height), empty: пусто });
    }
  }

  // Заголовки и идентификаторы
  const h1 = [...document.querySelectorAll('h1')];
  const ids = [...document.querySelectorAll('[id]')].map(el => el.id);
  const дубли_id = [...new Set(ids.filter(i => ids.filter(j => j === i).length > 1))];

  // Первый экран и сетка
  const герой = document.querySelector('.zhero');
  const сетка = document.querySelector('.zg');
  const заполнено = сетка ? сетка.querySelectorAll('[data-testid="title-card"]').length : 0;

  // Слайдер: состояние, а не наличие
  const s = document.querySelector('[data-zhero-slider]');
  const слайдер = s ? {
    ready: s.getAttribute('data-zhero-ready'),
    slides: s.querySelectorAll('[data-zhero-slide]').length,
    dots: s.querySelectorAll('[data-zhero-dot]').length,
    index: s.getAttribute('data-active-index'),
    prev_visible: !!s.querySelector('[data-zhero-prev]') && видимый(s.querySelector('[data-zhero-prev]')),
    next_visible: !!s.querySelector('[data-zhero-next]') && видимый(s.querySelector('[data-zhero-next]')),
    prev_hit: s.querySelector('[data-zhero-prev]') ? (() => {
      const r = s.querySelector('[data-zhero-prev]').getBoundingClientRect();
      return { w: Math.round(r.width), h: Math.round(r.height) };
    })() : null,
    height: герой ? Math.round(герой.getBoundingClientRect().height) : 0,
  } : null;

  return {
    overflow, широкие, обрезано,
    cards: карточки.length, cards_no_title: без_названия, cards_hidden: пустые,
    cards_no_href: без_ссылки, cards_unclickable: неоткликаемые,
    cards_offscreen: непроверенные, cards_in_hidden_tabs: скрытые_вкладкой,
    images: картинки.length, images_broken: битые, images_marked_broken: помечены,
    buttons: кнопки.length, buttons_invisible: невидимые,
    buttons_covered: перекрытые, buttons_small: мелкие,
    h1: h1.length, h1_text: h1.map(e => e.textContent.trim().slice(0, 60)),
    dup_ids: дубли_id,
    grid_filled: заполнено, dead_space: мёртвые,
    first_screen: герой ? Math.round(герой.getBoundingClientRect().height) : 0,
    viewport: innerHeight,
    slider: слайдер,
    cls: window.__cls || 0,
  };
}
"""

CLS_JS = r"""
window.__cls = 0;
try {
  new PerformanceObserver((l) => {
    for (const e of l.getEntries()) if (!e.hadRecentInput) window.__cls += e.value;
  }).observe({ type: 'layout-shift', buffered: true });
} catch (e) {}
"""

СОСТОЯНИЕ_JS = r"""
() => {
  const s = document.querySelector('[data-zhero-slider]');
  if (!s) return null;
  const a = s.querySelector('[data-zhero-slide][data-active="1"]');
  const cta = s.querySelector('[data-zhero-more]');
  return {
    index: s.getAttribute('data-active-index'),
    id: a && a.getAttribute('data-slide-id'),
    title: (s.querySelector('[data-zhero-title]') || {}).textContent,
    img: a && a.querySelector('img') && a.querySelector('img').getAttribute('src'),
    href: cta && cta.getAttribute('href'),
    dot: [...s.querySelectorAll('[data-zhero-dot]')]
           .findIndex(d => d.getAttribute('aria-selected') === 'true'),
  };
}
"""


def настроить_маршруты(page) -> dict:
    счёт = {"posters": 0, "blocked_scripts": 0}

    def обработчик(route):
        запрос = route.request
        url = запрос.url
        if url.startswith("http://127.0.0.1"):
            return route.continue_()
        if запрос.resource_type == "image":
            счёт["posters"] += 1
            широкая = not re.search(r"poster|webp|jpg|jpeg", url)
            return route.fulfill(status=200, body=заглушка_для(url, широкая),
                                 content_type="image/png")
        счёт["blocked_scripts"] += 1
        return route.abort()

    page.route("**/*", обработчик)
    return счёт


def проверить_слайдер(page) -> dict:
    """Настоящая смена состояния: нажатие, точка, клавиша, жест, серия."""
    из_ = page.evaluate(СОСТОЯНИЕ_JS)
    if not из_ or not из_.get("id"):
        return {"applicable": False, "reason": "слайдера на странице нет"}

    # Шаблон с одним кадром героя — законное состояние, а не сломанный слайдер.
    # Листать там нечего, и органов управления быть НЕ должно: мёртвая кнопка
    # хуже отсутствующей. Поэтому здесь проверяется именно их отсутствие.
    слайдов = page.locator("[data-zhero-slide]").count()
    if слайдов < 2:
        лишние = (page.locator("[data-zhero-next]").count()
                  + page.locator("[data-zhero-prev]").count()
                  + page.locator("[data-zhero-dot]").count())
        return {"applicable": False, "reason": "один кадр героя по замыслу шаблона",
                "slides": слайдов, "dead_controls": лишние,
                "failures": ([f"при одном слайде осталось органов управления: {лишние}"]
                             if лишние else [])}

    итог: dict = {"applicable": True, "start": из_, "steps": [], "failures": []}

    def состояние():
        return page.evaluate(СОСТОЯНИЕ_JS)

    def шаг(имя: str, действие, ожидать_смену: bool = True):
        до = состояние()
        действие()
        page.wait_for_timeout(420)
        после = состояние()
        сменилось = (до["id"] != после["id"] and до["title"] != после["title"]
                     and до["img"] != после["img"] and до["href"] != после["href"])
        итог["steps"].append({"step": имя, "from": до["id"], "to": после["id"],
                              "changed": сменилось})
        if ожидать_смену and not сменилось:
            итог["failures"].append(f"{имя}: состояние не сменилось ({до['id']} → {после['id']})")
        return после

    вперёд = page.locator("[data-zhero-next]")
    назад = page.locator("[data-zhero-prev]")
    точки = page.locator("[data-zhero-dot]")
    всего = точки.count()

    первый = из_["id"]
    шаг("click-next", lambda: вперёд.click())
    шаг("click-next-2", lambda: вперёд.click())
    состояние_после_назад = шаг("click-prev", lambda: назад.click())
    if состояние_после_назад["id"] != итог["steps"][0]["to"]:
        итог["failures"].append("click-prev не вернул на предыдущий слайд")

    if всего > 2:
        цель = всего - 1
        после = шаг(f"dot-{цель}", lambda: точки.nth(цель).click())
        if после["dot"] != цель:
            итог["failures"].append(f"точка {цель} привела на {после['dot']}")

    # Клавиатура: фокус на кнопке, затем стрелки на самом слайдере.
    def клавиша(имя):
        page.locator("[data-zhero-slider]").focus()
        page.keyboard.press(имя)

    шаг("key-ArrowRight", lambda: клавиша("ArrowRight"))
    шаг("key-ArrowLeft", lambda: клавиша("ArrowLeft"))

    # Жест: свайп указателем по области просмотра, мимо органов управления.
    def свайп():
        рамка = page.locator("[data-zhero-viewport]").bounding_box()
        y = рамка["y"] + рамка["height"] * 0.35
        page.mouse.move(рамка["x"] + рамка["width"] * 0.75, y)
        page.mouse.down()
        page.mouse.move(рамка["x"] + рамка["width"] * 0.25, y, steps=12)
        page.mouse.up()

    шаг("swipe", свайп)

    # Цикл: с последнего вперёд — на первый.
    точки.nth(всего - 1).click()
    page.wait_for_timeout(300)
    после = шаг("wrap-forward", lambda: вперёд.click())
    if после["dot"] != 0:
        итог["failures"].append(f"цикл вперёд привёл на {после['dot']}, а не на 0")
    после = шаг("wrap-backward", lambda: назад.click())
    if после["dot"] != всего - 1:
        итог["failures"].append(f"цикл назад привёл на {после['dot']}")

    # Серия быстрых нажатий: индекс обязан быть предсказуем.
    точки.nth(0).click()
    page.wait_for_timeout(300)
    for _ in range(10):
        вперёд.click()
    page.wait_for_timeout(600)
    конец = состояние()
    ожидаемый = 10 % всего
    итог["rapid"] = {"expected_dot": ожидаемый, "actual_dot": конец["dot"]}
    if конец["dot"] != ожидаемый:
        итог["failures"].append(
            f"десять быстрых нажатий: точка {конец['dot']}, ожидалась {ожидаемый}")

    # Фокус обязан быть виден — и проверять его надо КЛАВИАТУРОЙ. `:focus-visible`
    # не срабатывает на программном `focus()` после мышиного ввода, и проверка
    # тогда измеряет способ фокусировки, а не стиль.
    назад.focus()
    page.keyboard.press("Tab")
    page.wait_for_timeout(120)
    видимость = page.evaluate(
        "() => { const b = document.activeElement;"
        " const s = getComputedStyle(b); return {el: b.getAttribute('aria-label'),"
        " visible: b.matches(':focus-visible'), outline: s.outlineStyle,"
        " width: s.outlineWidth, shadow: s.boxShadow}; }")
    итог["focus"] = видимость
    заметен = (видимость["visible"]
               and (видимость["outline"] not in ("none", "")
                    or видимость["shadow"] not in ("none", "")))
    if not заметен:
        итог["failures"].append(f"фокус клавиатурой не виден: {видимость}")

    итог["unique_ids_seen"] = len({ш["to"] for ш in итог["steps"] if ш["to"]})
    return итог


def main() -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--base", required=True)
    р.add_argument("--out", required=True)
    р.add_argument("--widths", default=",".join(str(ш) for ш in ШИРИНЫ))
    р.add_argument("--pages", default="")
    р.add_argument("--tag", default="run")
    р.add_argument("--shots", action="store_true", help="сохранять снимки")
    р.add_argument("--slider-on", default="/", help="где проверять слайдер")
    а = р.parse_args()

    from playwright.sync_api import sync_playwright

    выход = Path(а.out)
    (выход / "screenshots").mkdir(parents=True, exist_ok=True)
    ширины = [int(ш) for ш in а.widths.split(",") if ш.strip()]
    страницы = [п for п in а.pages.split(",") if п.strip()]
    if not страницы:
        страницы = ["/", "/catalog/", "/new/?mode=added", "/movies/", "/series/",
                    "/search/?q=%D0%B0", "/search/?q=zzzzzzzzzz"]

    отчёт = {"base": а.base, "tag": а.tag, "widths": ширины,
             "pages": {}, "slider": {}, "verdict": "PASS", "failures": []}

    with sync_playwright() as pw:
        # Флаги памяти, а не удобства: стенд делит машину с другими сеансами,
        # и на пике свободной памяти остаётся около двух гигабайт. Chromium с
        # процессом на вкладку в такой обстановке убивает ядро, и прогон
        # обрывается без единой строки — то есть выглядит как «тесты прошли».
        браузер = pw.chromium.launch(args=[
            "--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu",
            "--renderer-process-limit=1", "--js-flags=--max-old-space-size=256",
            "--disable-extensions", "--disable-background-networking",
            "--blink-settings=imagesEnabled=true"])
        for ширина in ширины:
            контекст = браузер.new_context(
                viewport={"width": ширина, "height": 900},
                device_scale_factor=1, has_touch=ширина <= 768)
            page = контекст.new_page()
            счёт = настроить_маршруты(page)
            page.add_init_script(CLS_JS)
            for путь in страницы:
                page.goto(а.base + путь, wait_until="load", timeout=60000)
                page.wait_for_timeout(500)
                данные = page.evaluate(ИЗМЕРЕНИЕ_JS)
                данные["blocked"] = dict(счёт)
                ключ = f"{путь}@{ширина}"
                отчёт["pages"][ключ] = данные
                беды = []
                if данные["overflow"] > 1:
                    беды.append(f"переполнение {данные['overflow']}px")
                if данные["cards_no_title"]:
                    беды.append(f"карточек без названия: {данные['cards_no_title']}")
                if данные["cards_unclickable"]:
                    беды.append(f"неоткликаемых карточек: {данные['cards_unclickable']}")
                if данные["images_broken"]:
                    беды.append(f"битых картинок: {данные['images_broken']}")
                if данные["h1"] != 1:
                    беды.append(f"H1 = {данные['h1']}")
                if данные["dup_ids"]:
                    беды.append(f"дубли DOM-id: {данные['dup_ids'][:3]}")
                if данные["buttons_covered"]:
                    беды.append(f"перекрытые органы: {данные['buttons_covered'][:3]}")
                if данные["cls"] > 0.1:
                    беды.append(f"CLS {данные['cls']:.3f}")
                if данные["широкие"]:
                    беды.append(f"элементы шире экрана: {данные['широкие'][:3]}")
                if данные["dead_space"]:
                    беды.append("мёртвая полоса: " + ", ".join(
                        f"{м['cls']} {м['empty']}px" for м in данные["dead_space"][:3]))
                if беды:
                    отчёт["failures"].append({"page": ключ, "issues": беды})
                if а.shots:
                    имя = re.sub(r"[^a-z0-9]+", "-", путь.lower()).strip("-") or "home"
                    page.screenshot(
                        path=str(выход / "screenshots" / f"{имя}-{ширина}.png"),
                        full_page=False)
            # Слайдер: отдельный проход на объявленной странице
            page.goto(а.base + а.slider_on, wait_until="load", timeout=60000)
            page.wait_for_timeout(700)
            try:
                итог = проверить_слайдер(page)
            except Exception as ош:  # noqa: BLE001 — приёмка обязана назвать причину
                итог = {"applicable": True, "failures": [f"проверка слайдера сорвалась: {ош!r}"]}
            отчёт["slider"][str(ширина)] = итог
            if итог.get("failures"):
                отчёт["failures"].append({"page": f"slider@{ширина}",
                                          "issues": итог["failures"]})
            контекст.close()
        браузер.close()

    if отчёт["failures"]:
        отчёт["verdict"] = "FAIL"
    (выход / f"audit-{а.tag}.json").write_text(
        json.dumps(отчёт, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"verdict": отчёт["verdict"],
                      "failures": отчёт["failures"][:12],
                      "out": str(выход / f"audit-{а.tag}.json")},
                     ensure_ascii=False, indent=1))
    return 0 if отчёт["verdict"] == "PASS" else 2


if __name__ == "__main__":
    sys.exit(main())
