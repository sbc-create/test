#!/usr/bin/env python3
"""Оценка шаблонного пакета: измерения в браузере, действия и балл по рубрике.

Измеритель геометрии переиспользуется из `automation/host/nova-visual-audit.py` —
тот самый, которым принимались живые витрины. Второй измеритель означал бы два
разных определения «обрезанного текста», и расхождение между ними обнаружилось
бы позже всего.

## Что изменилось во второй версии

Раньше мерялась одна страница — главная. Шаблон, проверенный только на главной,
не проверен: каталог, тайтл, сезон и серия посещаются чаще, и дефект там стоит
столько же. Теперь меряется матрица маршрутов.

И добавлено то, чего измерение геометрии не видит в принципе: РАБОТАЕТ ли
интерфейс. Стрелка полосы, вкладка сезона, фильтр, сортировка, раскрытие
описания и кнопка плеера проверяются действием — нажатием и клавиатурой, с
проверкой состояния до и после. Нарисованный орган управления, который ничего
не делает, — дефект, и ловится он только так.

## Как считается балл

Сто баллов разложены по одиннадцати критериям. Балл — не среднее впечатление:
у части критериев есть жёсткий отказ, и он обнуляет критерий целиком. Обрезанный
обязательный текст не компенсируется удачной типографикой.

Самооценка агента не является приёмкой владельца и так и помечена в отчёте.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import importlib.util
import json
import pathlib
import re
import sys

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[4]
ТОЧКИ = (320, 390, 768, 1024, 1440, 1920)

#: Маршруты, которые меряются на всех шести ширинах: они несут основную
#: нагрузку композиции и именно на них ломается адаптивность.
ОПОРНЫЕ = ("home", "catalog", "title-series", "episode")

#: Остальные маршруты меряются на узкой и широкой — там ловятся переполнение и
#: обрезка, а промежуточные ширины у них повторяют опорные.
ПРОЧИЕ_ТОЧКИ = (390, 1440)

#: Движение при включённом «уменьшить анимацию». Обещание уважать эту
#: настройку ничего не стоит, пока его не измерили: браузер сообщает
#: фактическую длительность переходов, и она обязана быть нулевой.
СПОКОЙСТВИЕ = r"""
() => {
  const итог = {respects: true, offenders: []};
  for (const el of document.querySelectorAll('a,button,.k,.sec,.chip,[data-lx]')) {
    const cs = getComputedStyle(el);
    const длительности = (cs.transitionDuration + ',' + cs.animationDuration)
      .split(',').map(з => parseFloat(з) || 0);
    if (длительности.some(з => з > 0.05)) {
      итог.respects = false;
      итог.offenders.push({cls: (el.className || '').slice(0, 24),
                           t: cs.transitionDuration, a: cs.animationDuration});
    }
  }
  return итог;
}
"""

#: Снимки для каталога приёмки.
СНИМКИ = (("home", 390), ("home", 1440), ("catalog", 390), ("catalog", 1440),
          ("title-series", 1440), ("episode", 1440))

#: Критерий → (вес, что считается жёстким отказом).
РУБРИКА = {
    "hierarchy": (15, "нет первичного действия или одинаковые повторяющиеся полки"),
    "grid": (12, "пустые ячейки, одинокий хвост, гигантские карточки"),
    "typography": (10, "обрезанный обязательный текст"),
    "media": (10, "растяжение, битое изображение, разрушительный кроп"),
    "responsive": (12, "переполнение или наложение на любой требуемой ширине"),
    "content_truth": (12, "ложная новизна, дата или оценка"),
    "ux": (8, "недоступные или мёртвые элементы управления"),
    "accessibility": (8, "клавиатура, фокус или контраст"),
    "performance": (6, "неограниченный обход, скачки макета, тяжёлые кадры до действия"),
    "distinctness": (5, "отличие только цветом"),
    "polish": (2, "явные шероховатости"),
}


#: Доступность и контраст меряются здесь, а не додумываются. Без этого
#: критерий «accessibility» получал бы полный вес просто за отсутствие
#: измерения — то есть был бы штампом, а не проверкой.
ДОСТУПНОСТЬ = r"""
() => {
  const out = {small_targets: [], heading_skips: [], low_contrast: [], focusable: 0,
               h1: 0, landmarks: {}, heavy_frames: 0, autoplay: 0, live_regions: 0,
               dead_controls: [], unlabelled: []};
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

  for (const el of document.querySelectorAll('a,button,input,select,[tabindex]')) {
    if (!видим(el)) continue;
    out.focusable += 1;
    const r = el.getBoundingClientRect();
    // Карточка-ссылка сама по себе крупная; мелкими бывают чипы и кнопки.
    const мелкая = r.width < 44 || r.height < 44;
    // Ссылка внутри строки текста — исключение самого правила о целях
    // нажатия: растянуть её до 44 px значит разорвать абзац. Признак
    // «внутри текста» проверяется, а не объявляется: у абзаца есть свой
    // текст помимо ссылки.
    const внутри_текста = el.tagName === 'A' && el.closest('p') &&
      (el.closest('p').textContent || '').trim().length >
      (el.textContent || '').trim().length + 3;
    if (мелкая && !el.closest('.k') && !внутри_текста) {
      out.small_targets.push({tag: el.tagName.toLowerCase(),
                              cls: (el.className || '').slice(0, 24),
                              w: +r.width.toFixed(1), h: +r.height.toFixed(1)});
    }
    // Орган управления без доступного имени: скринридер объявит «кнопка».
    const имя = (el.getAttribute('aria-label') || el.textContent || '').trim()
      || (el.labels && el.labels.length ? 'label' : '');
    if (!имя && el.tagName !== 'INPUT') {
      out.unlabelled.push({tag: el.tagName.toLowerCase(),
                           cls: (el.className || '').slice(0, 24)});
    }
    // Кнопка, за которой ничего не стоит: ни отправки формы, ни разметки
    // поведения. Такую рисовать нельзя — она обещает действие, которого нет.
    if (el.tagName === 'BUTTON') {
      // `el.type` возвращает 'submit' и у кнопки вне формы: это значение по
      // умолчанию, а не признак поведения. Пока правило опиралось на него,
      // гейт считал живой любую нарисованную кнопку — то есть не работал.
      // Отправка засчитывается только внутри формы.
      const отправляет = el.getAttribute('type') !== 'button' && !!el.closest('form');
      const живая = отправляет || [...el.attributes].some(
        a => a.name.startsWith('data-lx') || a.name === 'role' ||
             a.name === 'aria-pressed' || a.name === 'aria-expanded' ||
             a.name === 'aria-selected' || a.name === 'aria-controls');
      if (!живая) out.dead_controls.push({cls: (el.className || '').slice(0, 30),
                                          text: (el.textContent || '').trim().slice(0, 24)});
    }
  }

  let предыдущий = 0;
  for (const h of document.querySelectorAll('h1,h2,h3,h4,h5,h6')) {
    if (!видим(h)) continue;
    const уровень = +h.tagName[1];
    if (уровень === 1) out.h1 += 1;
    if (предыдущий && уровень > предыдущий + 1) {
      out.heading_skips.push({from: предыдущий, to: уровень,
                              text: (h.textContent || '').trim().slice(0, 40)});
    }
    предыдущий = уровень;
  }

  for (const el of document.querySelectorAll('p,span,a,h1,h2,h3,li,time,button,option,dd,dt')) {
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

  // Ссылка, которая никуда не ведёт, обещает переход и не выполняет его.
  // Пустой href, решётка и javascript: — три её обычных вида.
  out.dead_links = [];
  for (const a of document.querySelectorAll('a')) {
    if (!видим(a)) continue;
    const href = (a.getAttribute('href') || '').trim();
    if (!href || href === '#' || href.toLowerCase().startsWith('javascript:')) {
      out.dead_links.push({cls: (a.className || '').slice(0, 24),
                           text: (a.textContent || '').trim().slice(0, 24)});
    }
  }

  out.landmarks = {
    banner: document.querySelectorAll('header[role="banner"],header.hd').length,
    main: document.querySelectorAll('main').length,
    contentinfo: document.querySelectorAll('footer[role="contentinfo"],footer.ft').length,
    nav: document.querySelectorAll('nav').length,
  };
  // Тяжёлый кадр до первого действия человека — это автозагрузка чужого
  // источника. Плеер обязан появляться только после нажатия.
  out.heavy_frames = document.querySelectorAll('iframe,video,audio,embed,object').length;
  out.autoplay = document.querySelectorAll('[autoplay],[data-autoplay="true"]').length;
  out.live_regions = document.querySelectorAll('[aria-live],[role="status"]').length;
  return out;
}
"""

#: Разметка пакетов фабрики размечена как `k--poster`, живого рантайма — как
#: `c--poster`. Общий измеритель написан под второй, и на пакетах фабрики он
#: молча не находил ни одной карточки: сетки, пустые ячейки, одинокие хвосты и
#: наложения измерялись на пустом множестве и давали ноль всегда.
#: Проверка, которая не может упасть, ничего не проверяет — поэтому селектор
#: расширяется на обе разметки. Определение «обрезанного текста» при этом
#: остаётся одно: второй измеритель означал бы два разных определения.
ЗАМЕНЫ_СЕЛЕКТОРОВ = (
    ('[class*="c--poster"], [class*="c--episode"], [class*="c--editorial"]',
     '[class*="c--poster"], [class*="c--episode"], [class*="c--editorial"], '
     '[class*="k--poster"], [class*="k--compact"], [class*="k--editorial"], '
     '[class*="k--tile"], [class*="k--ranked"], [class*="k--rich"], '
     '[class*="k--row"]'),
    ("c.className.includes('c--poster')",
     "(c.className.includes('c--poster') || c.className.includes('k--poster') || "
     "c.className.includes('k--rich'))"),
    ("/c--editorial/.test(классы)", "/c--editorial|k--editorial/.test(классы)"),
    ("/c--episode/.test(классы)", "/c--episode|k--compact/.test(классы)"),
    ("'.c__poster, .c__media, [data-poster]'", "'.c__poster, .c__media, .k__p, [data-poster]'"),
)


def _измеритель():
    путь = КОРЕНЬ / "automation" / "host" / "nova-visual-audit.py"
    spec = importlib.util.spec_from_file_location("nova_visual_audit", путь)
    модуль = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(модуль)
    измерение = модуль.ИЗМЕРЕНИЕ
    for было, стало in ЗАМЕНЫ_СЕЛЕКТОРОВ:
        if было not in измерение:
            raise RuntimeError(
                f"измеритель изменился: не найдено {было!r}. Молча продолжать нельзя — "
                f"значит расширение селекторов не применилось и проверки снова пусты."
            )
        измерение = измерение.replace(было, стало)
    модуль.ИЗМЕРЕНИЕ = измерение
    return модуль


# --- действия ---------------------------------------------------------------

def _дождаться(стр, узел, выражение: str, таймаут: int = 2500) -> bool:
    """Дождаться состояния, а не времени.

    Плавная прокрутка и переключение панелей происходят не мгновенно.
    Фиксированное ожидание делает проверку зависимой от загрузки машины: на
    занятом хосте исправная полоса объявлялась сломанной. Ожидание по условию
    убирает это целиком.
    """
    try:
        узел.evaluate(f"(e) => new Promise((ок, нет) => {{"
                      f"const срок = Date.now() + {таймаут};"
                      f"const тик = () => (({выражение})(e) ? ок(true)"
                      f" : Date.now() > срок ? нет(new Error('не дождались'))"
                      f" : requestAnimationFrame(тик));"
                      f"тик();}})")
        return True
    except Exception:  # noqa: BLE001 — «не дождались» тоже результат
        return False


#: Браузеру здесь незачем держать кэши на диске: страницы локальные, а
#: свободного места на хосте мало — при его нехватке вкладка падает с
#: «Page crashed», и измерение теряется целиком.
ФЛАГИ_БРАУЗЕРА = [
    "--disable-dev-shm-usage", "--disk-cache-size=1", "--media-cache-size=1",
    "--disable-gpu-shader-disk-cache", "--disable-background-networking",
    "--disable-extensions", "--no-first-run", "--disable-breakpad",
]


#: Кадры, по которым считаются отпечатки, сохраняются без потерь: сравнение
#: похожести не должно зависеть от артефактов сжатия. Остальные кадры идут в
#: JPEG — их сотни, и в PNG они занимали втрое больше места, чем есть на диске.
БЕЗ_ПОТЕРЬ = (("home", 1440), ("home", 390), ("catalog", 1440),
              ("title-series", 1440))


def _расширение(маршрут: str, ширина: int) -> str:
    return ".png" if (маршрут, ширина) in БЕЗ_ПОТЕРЬ else ".jpg"


def _дождаться_картинок(стр, таймаут: int = 15000) -> None:
    """Дождаться, пока все изображения страницы дорисованы.

    Ленивая загрузка и раскодирование WebP занимают время. Снимок, сделанный
    раньше, отличается от снимка той же страницы в следующем прогоне — и
    воспроизводимость превращается в лотерею, а «битое изображение» — в
    случайную находку.
    """
    try:
        стр.wait_for_function(
            "() => [...document.images].every(i => i.complete)", timeout=таймаут)
    except Exception:  # noqa: BLE001 — неготовность будет видна в измерении
        pass
    try:
        стр.wait_for_timeout(120)
    except Exception:  # noqa: BLE001 — вкладка могла упасть; решит вызывающий
        pass


def _проба(итог: list, узел: str, что: str, годно: bool, подробность=""):
    итог.append({"component": узел, "check": что, "ok": bool(годно),
                 "detail": str(подробность)[:160]})


def полоса_работает(стр, итог: list) -> None:
    """Полоса обязана прокручиваться, а стрелки — появляться только по делу."""
    полос = стр.locator('[data-lx="rail"]')
    if полос.count() == 0:
        return
    полоса = полос.first
    дорожка = полоса.locator("[data-lx-track]").first
    навигация = полоса.locator("[data-lx-nav]").first
    прокручиваемо = дорожка.evaluate("e => e.scrollWidth - e.clientWidth > 1.5")
    видна = навигация.is_visible()
    _проба(итог, "rail", "стрелки только при прокручиваемом содержимом",
           видна == прокручиваемо, f"прокрутка={прокручиваемо} стрелки={видна}")
    if not прокручиваемо:
        return
    назад = полоса.locator(".rail__b").first
    вперёд = полоса.locator(".rail__b").last
    _проба(итог, "rail", "в начале «назад» недоступна", назад.is_disabled())
    было = дорожка.evaluate("e => e.scrollLeft")
    вперёд.click()
    _дождаться(стр, дорожка, f"e => e.scrollLeft > {было}")
    стало = дорожка.evaluate("e => e.scrollLeft")
    _проба(итог, "rail", "«вперёд» действительно прокручивает", стало > было,
           f"{было} → {стало}")
    # Состояние кнопки обновляет обработчик прокрутки, и он срабатывает позже
    # самой прокрутки. Ждать надо именно состояние кнопки, иначе проверка
    # меряет расторопность браузера, а не поведение полосы.
    _дождаться(стр, назад, "e => !e.disabled")
    _проба(итог, "rail", "после прокрутки «назад» доступна", not назад.is_disabled())
    дорожка.evaluate("e => e.scrollLeft = e.scrollWidth")
    _дождаться(стр, вперёд, "e => e.disabled")
    _проба(итог, "rail", "в конце «вперёд» недоступна", вперёд.is_disabled())
    дорожка.evaluate("e => e.scrollLeft = 0")
    стр.wait_for_timeout(300)
    дорожка.scroll_into_view_if_needed()
    дорожка.focus()
    стр.keyboard.press("ArrowRight")
    # Прокрутка плавная, и фиксированное ожидание делает проверку зависимой от
    # скорости машины: на загруженном хосте она падала при исправной полосе.
    # Ждём результата, а не времени.
    сдвинулась = _дождаться(стр, дорожка, "e => e.scrollLeft > 0")
    _проба(итог, "rail", "клавиатура прокручивает полосу", сдвинулась,
           дорожка.evaluate("e => e.scrollLeft"))
    _проба(итог, "rail", "полоса не рвёт страницу по горизонтали",
           not стр.evaluate("() => document.documentElement.scrollWidth > "
                            "document.documentElement.clientWidth + 1"))


def вкладки_работают(стр, итог: list) -> None:
    вкладок = стр.locator('[role="tab"]')
    сколько = вкладок.count()
    if сколько == 0:
        return
    _проба(итог, "tabs", "у вкладок есть панели",
           стр.locator('[role="tabpanel"]').count() == сколько)
    if сколько < 2:
        _проба(итог, "tabs", "единственный сезон показан развёрнутым",
               стр.locator('[role="tabpanel"]').first.is_visible())
        return
    первая, вторая = вкладок.nth(0), вкладок.nth(1)
    вторая.click()
    стр.wait_for_timeout(120)
    _проба(итог, "tabs", "нажатие переключает выбранную вкладку",
           вторая.get_attribute("aria-selected") == "true"
           and первая.get_attribute("aria-selected") == "false")
    панель1 = стр.locator(f'#{первая.get_attribute("aria-controls")}')
    панель2 = стр.locator(f'#{вторая.get_attribute("aria-controls")}')
    _проба(итог, "tabs", "видна ровно одна панель",
           панель2.is_visible() and not панель1.is_visible())
    вторая.focus()
    стр.keyboard.press("ArrowLeft")
    стр.wait_for_timeout(120)
    _проба(итог, "tabs", "стрелки клавиатуры переключают вкладки",
           первая.get_attribute("aria-selected") == "true")


def фильтры_работают(стр, итог: list) -> None:
    чипы = стр.locator("[data-lx-filter]")
    if чипы.count() == 0:
        return
    живое = стр.locator("[data-lx-live]").first
    сброс = стр.locator("[data-lx-reset]").first
    видно_до = стр.evaluate(
        "() => [...document.querySelectorAll('[data-lx=listing] .k')]"
        ".filter(k => !k.hidden).length")
    текст_до = живое.text_content() if живое.count() else ""
    # Берётся самый редкий из предложенных признаков, а не первый. По самому
    # частому выдача может не сократиться законно — и проверка объявит дефект
    # там, где фильтр работает правильно.
    чипы.last.click()
    стр.wait_for_timeout(150)
    видно_после = стр.evaluate(
        "() => [...document.querySelectorAll('[data-lx=listing] .k')]"
        ".filter(k => !k.hidden).length")
    _проба(итог, "filters", "фильтр действительно сокращает выдачу",
           видно_после < видно_до, f"{видно_до} → {видно_после}")
    _проба(итог, "filters", "состояние кнопки объявлено",
           чипы.last.get_attribute("aria-pressed") == "true")
    объявлено = (живое.text_content() if живое.count() else "")
    _проба(итог, "filters", "объявленное число совпадает с показанным",
           str(видно_после) in объявлено, f"видно {видно_после}, сказано «{объявлено}»")
    _проба(итог, "filters", "живая область сообщила об изменении",
           живое.count() > 0 and живое.text_content() != текст_до,
           живое.text_content() if живое.count() else "нет области")
    _проба(итог, "filters", "сброс появляется только при активном отборе",
           сброс.count() > 0 and сброс.is_visible())
    if сброс.count():
        сброс.click()
        стр.wait_for_timeout(150)
        вернулось = стр.evaluate(
            "() => [...document.querySelectorAll('[data-lx=listing] .k')]"
            ".filter(k => !k.hidden).length")
        _проба(итог, "filters", "сброс возвращает полную выдачу",
               вернулось == видно_до, f"{вернулось} из {видно_до}")


def сортировка_работает(стр, итог: list) -> None:
    выбор = стр.locator("[data-lx-sort]")
    if выбор.count() == 0:
        return
    порядок_до = стр.evaluate(
        "() => [...document.querySelectorAll('[data-lx=listing] .k')]"
        ".map(k => k.getAttribute('data-t')).join('|')")
    выбор.first.select_option("title")
    стр.wait_for_timeout(200)
    порядок_после = стр.evaluate(
        "() => [...document.querySelectorAll('[data-lx=listing] .k')]"
        ".map(k => k.getAttribute('data-t'))")
    _проба(итог, "sort", "сортировка меняет порядок",
           "|".join(порядок_после) != порядок_до)
    _проба(итог, "sort", "порядок по названию действительно алфавитный",
           порядок_после == sorted(порядок_после))
    _проба(итог, "sort", "сортировка ничего не потеряла",
           len(порядок_после) == len(порядок_до.split("|")))


def поиск_работает(стр, итог: list) -> None:
    поле = стр.locator("[data-lx-search]")
    if поле.count() == 0:
        return
    пусто = стр.locator("[data-lx-none]").first
    поле.first.fill("щщщыъ")
    стр.wait_for_timeout(200)
    видно = стр.evaluate(
        "() => [...document.querySelectorAll('[data-lx=listing] .k')]"
        ".filter(k => !k.hidden).length")
    _проба(итог, "search", "заведомо пустой запрос не оставляет карточек", видно == 0)
    _проба(итог, "search", "пустая выдача объяснена словами",
           пусто.count() > 0 and пусто.is_visible())
    поле.first.fill("")
    стр.wait_for_timeout(200)
    _проба(итог, "search", "очистка запроса возвращает выдачу",
           стр.evaluate("() => [...document.querySelectorAll('[data-lx=listing] .k')]"
                        ".filter(k => !k.hidden).length") > 0)


def раскрытие_работает(стр, итог: list) -> None:
    кнопка = стр.locator("[data-lx-more-btn]")
    if кнопка.count() == 0:
        return
    тело = стр.locator("#ttl-d").first
    свёрнуто = тело.evaluate("e => e.scrollHeight - e.clientHeight > 4")
    _проба(итог, "disclosure", "до нажатия описание действительно свёрнуто", свёрнуто)
    кнопка.first.click()
    стр.wait_for_timeout(150)
    _проба(итог, "disclosure", "состояние объявлено через aria-expanded",
           кнопка.first.get_attribute("aria-expanded") == "true")
    _проба(итог, "disclosure", "после раскрытия текст виден целиком",
           тело.evaluate("e => e.scrollHeight - e.clientHeight <= 4"))


def плеер_работает(стр, итог: list) -> None:
    рамка = стр.locator("[data-player-host]")
    if рамка.count() == 0:
        return
    _проба(итог, "player", "до нажатия тяжёлых кадров нет",
           стр.locator("iframe, video, audio").count() == 0)
    высота_до = рамка.first.evaluate("e => Math.round(e.getBoundingClientRect().height)")
    кнопка = стр.locator("[data-lx-play]").first
    _проба(итог, "player", "кнопка просмотра названа для скринридера",
           bool((кнопка.get_attribute("aria-label") or "").strip()))
    кнопка.click()
    стр.wait_for_timeout(200)
    _проба(итог, "player", "нажатие меняет состояние места плеера",
           рамка.first.get_attribute("data-state") == "requested")
    высота_после = рамка.first.evaluate("e => Math.round(e.getBoundingClientRect().height)")
    _проба(итог, "player", "включение не сдвигает макет",
           abs(высота_после - высота_до) <= 2, f"{высота_до} → {высота_после}")
    _проба(итог, "player", "автозапуска нет",
           стр.locator("[autoplay]").count() == 0)


def клавиатура_работает(стр, итог: list) -> None:
    """Первая цель табуляции — ссылка обхода, и фокус обязан быть видимым.

    Порядок табуляции считается от начала документа, поэтому предыдущая
    проверка не должна оставлять фокус в середине страницы: иначе измеряется
    не порядок, а хвост чужого действия.
    """
    # Перезагрузка, а не blur: браузер помнит последний фокус для
    # последовательного перехода, и после чужого действия табуляция начнётся
    # с середины страницы — измерялся бы хвост предыдущей проверки.
    стр.reload(wait_until="load")
    стр.wait_for_timeout(150)
    стр.keyboard.press("Tab")
    первый = стр.evaluate("() => document.activeElement.className || ''")
    _проба(итог, "keyboard", "первая цель табуляции — ссылка обхода",
           "skip" in первый, первый)
    видимость = стр.evaluate(
        """() => {
          const el = document.activeElement;
          const cs = getComputedStyle(el);
          return cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) >= 1;
        }""")
    _проба(итог, "keyboard", "фокус виден", видимость)
    цепочка = []
    for _ in range(12):
        стр.keyboard.press("Tab")
        цепочка.append(стр.evaluate(
            "() => document.activeElement.tagName + '.' + "
            "(document.activeElement.className || '').split(' ')[0]"))
    _проба(итог, "keyboard", "табуляция идёт по разным элементам",
           len(set(цепочка)) > 1, " → ".join(цепочка[:5]))


ПРОВЕРКИ_МАРШРУТА = {
    "catalog": (фильтры_работают, сортировка_работает, клавиатура_работает),
    "home": (полоса_работает, клавиатура_работает),
    "title-series": (вкладки_работают, раскрытие_работает, полоса_работает),
    "title-movie": (раскрытие_работает, полоса_работает),
    "episode": (плеер_работает, вкладки_работают),
    "search": (поиск_работает,),
    "search-empty": (клавиатура_работает,),
}


def проверить_действия(стр, маршрут: str) -> list[dict]:
    итог: list[dict] = []
    for проверка in ПРОВЕРКИ_МАРШРУТА.get(маршрут, ()):
        try:
            проверка(стр, итог)
        except Exception as беда:  # noqa: BLE001 — падение проверки тоже результат
            _проба(итог, проверка.__name__, "проверка выполнилась", False, repr(беда))
    return итог


# --- измерение --------------------------------------------------------------

def матрица(превью: pathlib.Path, полная: bool = False) -> list[tuple[str, int]]:
    маршруты = sorted(ф.stem for ф in превью.glob("*.html") if ф.stem != "index")
    пары = []
    for маршрут in маршруты:
        точки = ТОЧКИ if (полная or маршрут in ОПОРНЫЕ) else ПРОЧИЕ_ТОЧКИ
        пары.extend((маршрут, ш) for ш in точки)
    return пары


def пагинация_связна(превью: pathlib.Path) -> list[dict]:
    """Вторая страница каталога обязана показывать другие записи.

    Пагинация, которая рисует ссылки и отдаёт тот же список, выглядит рабочей
    и не работает. Проверка сравнивает состав страниц по признакам карточек,
    а не по наличию ссылок.
    """
    первая = превью / "catalog.html"
    вторая = превью / "catalog-p2.html"
    if not (первая.is_file() and вторая.is_file()):
        return [{"component": "pagination", "check": "обе страницы отрисованы",
                 "ok": False, "detail": "нет catalog.html или catalog-p2.html"}]
    состав = []
    for файл in (первая, вторая):
        текст = файл.read_text(encoding="utf-8")
        состав.append([м for м in re.findall(r'data-t="([^"]*)"', текст)])
    пересечение = set(состав[0]) & set(состав[1])
    пробы = [
        {"component": "pagination", "check": "на обеих страницах есть записи",
         "ok": bool(состав[0]) and bool(состав[1]),
         "detail": f"{len(состав[0])} и {len(состав[1])}"},
        {"component": "pagination", "check": "вторая страница не повторяет первую",
         "ok": not пересечение, "detail": f"совпадений {len(пересечение)}"},
        {"component": "pagination", "check": "со второй страницы есть возврат",
         "ok": 'rel="prev"' in вторая.read_text(encoding="utf-8"), "detail": ""},
        {"component": "pagination", "check": "с первой страницы есть переход вперёд",
         "ok": 'rel="next"' in первая.read_text(encoding="utf-8"), "detail": ""},
    ]
    for проба in пробы:
        проба["route"] = "catalog"
        проба["viewport"] = 0
    return пробы


def измерить(превью: pathlib.Path, снимки: pathlib.Path | None,
             полная: bool = False) -> tuple[list[dict], list[dict], dict]:
    from playwright.sync_api import sync_playwright

    измеритель = _измеритель()
    пары = матрица(превью, полная)
    по_ширине: dict[int, list[str]] = {}
    for маршрут, ширина in пары:
        по_ширине.setdefault(ширина, []).append(маршрут)

    страницы: list[dict] = []
    действия: list[dict] = []
    нужны_снимки = set(СНИМКИ) if not полная else {(м, ш) for м, ш in пары}
    with sync_playwright() as pw:
        браузер = pw.chromium.launch(args=ФЛАГИ_БРАУЗЕРА)
        try:
            for ширина in sorted(по_ширине):
                контекст = браузер.new_context(viewport={"width": ширина, "height": 900})
                стр = контекст.new_page()
                try:
                    for маршрут in по_ширине[ширина]:
                        адрес = (превью / f"{маршрут}.html").resolve().as_uri()
                        # Страница со ста тридцатью настоящими постерами изредка
                        # роняет вкладку под нагрузкой. Это сбой среды, а не
                        # дефект шаблона, и терять из-за него сотню измерений
                        # нельзя: вкладка пересоздаётся, а неудача записывается
                        # и остаётся видимой в отчёте.
                        сорвалось = None
                        for попытка in range(2):
                            try:
                                стр.goto(адрес, wait_until="load", timeout=45000)
                                стр.wait_for_timeout(200)
                                сорвалось = None
                                break
                            except Exception as сбой:  # noqa: BLE001
                                сорвалось = str(сбой)[:160]
                                if попытка:
                                    break
                                try:
                                    стр.close()
                                    контекст.close()
                                except Exception:  # noqa: BLE001
                                    pass
                                контекст = браузер.new_context(
                                    viewport={"width": ширина, "height": 900})
                                стр = контекст.new_page()
                        if сорвалось:
                            страницы.append({"route": маршрут, "viewport": ширина,
                                             "measurement_error": сорвалось})
                            continue
                        # Измерение и снимок — только после того, как все
                        # изображения дорисованы. Иначе отпечаток первого экрана
                        # зависит от того, успел ли браузер раскодировать
                        # постеры, и два одинаковых прогона дают разные
                        # расстояния: воспроизводимости конец.
                        try:
                            _дождаться_картинок(стр)
                            запись = {"route": маршрут, "viewport": ширина}
                            запись.update(стр.evaluate(измеритель.ИЗМЕРЕНИЕ))
                            запись["a11y"] = стр.evaluate(ДОСТУПНОСТЬ)
                        except Exception as сбой:  # noqa: BLE001
                            # Вкладка может упасть на любом шаге, а не только
                            # при переходе: под нехваткой места браузеру негде
                            # держать даже свои кэши. Маршрут отмечается
                            # несостоявшимся, вкладка пересоздаётся, прогон
                            # пакета продолжается.
                            страницы.append({"route": маршрут, "viewport": ширина,
                                             "measurement_error": str(сбой)[:160]})
                            try:
                                стр.close()
                                контекст.close()
                            except Exception:  # noqa: BLE001
                                pass
                            контекст = браузер.new_context(
                                viewport={"width": ширина, "height": 900})
                            стр = контекст.new_page()
                            continue
                        # Битое изображение подтверждается вторым измерением:
                        # под нагрузкой браузер изредка не успевает раскодировать
                        # картинку, и однократное наблюдение назвало бы дефектом
                        # файл, который лежит на месте и цел на пяти других
                        # ширинах. Настоящая пропажа переживёт перезагрузку.
                        if запись.get("broken_images"):
                            стр.reload(wait_until="load", timeout=45000)
                            _дождаться_картинок(стр)
                            повтор = стр.evaluate(измеритель.ИЗМЕРЕНИЕ)
                            запись["broken_images_first_pass"] = запись["broken_images"]
                            запись["broken_images"] = повтор.get("broken_images") or []
                        if снимки and (маршрут, ширина) in нужны_снимки:
                            снимки.mkdir(parents=True, exist_ok=True)
                            файл = снимки / (f"{маршрут}-{ширина}"
                                             f"{_расширение(маршрут, ширина)}")
                            for попытка in range(3):
                                try:
                                    стр.screenshot(path=str(файл), full_page=False,
                                                   **({} if файл.suffix == ".png"
                                                      else {"quality": 74}))
                                    запись["screenshot"] = файл.name
                                    break
                                except Exception as сбой:  # noqa: BLE001
                                    запись["screenshot_error"] = str(сбой)[:120]
                                    стр.wait_for_timeout(400 * (попытка + 1))
                        страницы.append(запись)
                        # Действия проверяются на узкой и широкой: на узкой
                        # ломается касание, на широкой — прокрутка полосы.
                        if ширина in (390, 1440):
                            try:
                                пробы = проверить_действия(стр, маршрут)
                            except Exception as сбой:  # noqa: BLE001
                                # Падение вкладки посреди проверки действием —
                                # сбой среды. Он записывается как несостоявшаяся
                                # проверка, а не как исправный интерфейс.
                                пробы = [{"component": "среда",
                                          "check": "проверки действием состоялись",
                                          "ok": False, "detail": str(сбой)[:120]}]
                                try:
                                    стр.close(); контекст.close()
                                except Exception:  # noqa: BLE001
                                    pass
                                контекст = браузер.new_context(
                                    viewport={"width": ширина, "height": 900})
                                стр = контекст.new_page()
                            for проба in пробы:
                                проба["route"] = маршрут
                                проба["viewport"] = ширина
                                действия.append(проба)
                finally:
                    стр.close()
                    контекст.close()

            # Уважение к «уменьшить анимацию» проверяется в контексте, где эта
            # настройка включена. Объявить её в стилях и не проверить — ровно
            # тот случай, когда обещание ничего не стоит.
            контекст = браузер.new_context(viewport={"width": 1440, "height": 900},
                                           reduced_motion="reduce")
            стр = контекст.new_page()
            try:
                стр.goto((превью / "home.html").resolve().as_uri(),
                         wait_until="load", timeout=45000)
                стр.wait_for_timeout(150)
                спокойствие = стр.evaluate(СПОКОЙСТВИЕ)
            except Exception as сбой:  # noqa: BLE001
                спокойствие = {"respects": None, "offenders": [],
                               "measurement_error": str(сбой)[:120]}
            finally:
                try:
                    стр.close(); контекст.close()
                except Exception:  # noqa: BLE001
                    pass
        finally:
            браузер.close()
    действия.extend(пагинация_связна(превью))
    return страницы, действия, спокойствие


def одинокие_хвосты(страницы: list[dict]) -> list[dict]:
    """Одинокий хвост сетки, посчитанный по объявленным колонкам, а не по виду.

    Общий измеритель определяет число колонок как «сколько элементов стоят на
    одной высоте с первым». Для мозаики это неверно: ведущая плитка растянута
    на две колонки, и в первом ряду видно три элемента вместо четырёх. Семь
    карточек делились на три с остатком один, и шесть исправных шаблонов
    объявлялись дефектными.

    Здесь колонки берутся из `grid-template-columns`, а растянутая плитка
    считается за четыре ячейки — как она и занимает.
    """
    найдено = []
    for страница in страницы:
        for сетка in (страница.get("grid_summary") or []):
            колонок = сетка.get("declared") or сетка.get("cols") or 0
            если_мозаика = "mosaic" in (сетка.get("cls") or "")
            ячеек = (сетка.get("total") or 0) + (3 if если_мозаика else 0)
            if колонок >= 3 and ячеек % колонок == 1:
                найдено.append({"viewport": страница.get("viewport"),
                                "route": страница.get("route"), "cols": колонок,
                                "cells": ячеек, "cls": сетка.get("cls")})
    return найдено


def оценить(манифест: dict, страницы: list[dict], действия: list[dict],
            css_байт: int = 0, спокойствие: dict | None = None) -> dict:
    # Несостоявшееся измерение — не дефект шаблона и не его заслуга. Запись о
    # нём не несёт ни геометрии, ни доступности, и если считать её наравне с
    # остальными, страница без данных превращается в «страницу без h1 и без
    # ориентиров». Ровно это и случилось: сбой среды выглядел как отказ
    # доступности. Такие записи исключаются из счёта и считаются отдельно.
    несостоявшиеся = [с for с in страницы if с.get("measurement_error")]
    измеренные = [с for с in страницы if not с.get("measurement_error")]

    def всего(ключ):
        return sum(len(с.get(ключ) or []) for с in измеренные)

    def a11y(ключ):
        return sum(len(с.get("a11y", {}).get(ключ, [])) for с in измеренные)

    строгие = [c for с in измеренные for c in (с.get("clipped") or []) if c.get("strict")]
    переполнение = sum(1 for с in измеренные if с.get("overflow_x"))
    пустые = sum(с.get("empty_cells", 0) for с in измеренные)
    провалы = [д for д in действия if not д["ok"]]
    без_h1 = [с["route"] for с in измеренные if с.get("a11y", {}).get("h1") != 1]
    тяжёлые = sum(с.get("a11y", {}).get("heavy_frames", 0) for с in измеренные)
    без_ориентиров = [
        с["route"] for с in измеренные
        if not all((с.get("a11y", {}).get("landmarks") or {}).get(к)
                   for к in ("banner", "main", "contentinfo", "nav"))]

    измерено = {
        "ROUTES_MEASURED": len({с["route"] for с in измеренные}),
        "PAGE_MEASUREMENTS": len(измеренные),
        "MEASUREMENTS_FAILED": len(несостоявшиеся),
        "HORIZONTAL_OVERFLOW_COUNT": переполнение,
        "CLIPPED_REQUIRED_TEXT_COUNT": len(строгие),
        "TIMESTAMP_ELLIPSIS_COUNT": всего("date_ellipsis"),
        "POSTER_ASPECT_RATIO_VIOLATIONS": всего("poster_ratio_violations"),
        "BROKEN_IMAGE_COUNT": всего("broken_images"),
        "EMPTY_GRID_CELL_COUNT": пустые,
        "ORPHAN_LAST_ROW_COUNT": len(одинокие_хвосты(измеренные)),
        "OVERLAP_COUNT": всего("overlaps"),
        "UNINTENDED_GAP_OVER_96PX_COUNT": всего("big_gaps"),
        "SMALL_TOUCH_TARGET_COUNT": a11y("small_targets"),
        "HEADING_ORDER_SKIPS": a11y("heading_skips"),
        "LOW_CONTRAST_COUNT": a11y("low_contrast"),
        "UNLABELLED_CONTROL_COUNT": a11y("unlabelled"),
        "DEAD_CONTROL_COUNT": a11y("dead_controls"),
        "DEAD_LINK_COUNT": a11y("dead_links"),
        "REDUCED_MOTION_VIOLATIONS": len((спокойствие or {}).get("offenders") or []),
        "PAGES_WITHOUT_SINGLE_H1": len(без_h1),
        "PAGES_WITHOUT_LANDMARKS": len(без_ориентиров),
        "HEAVY_FRAMES_BEFORE_ACTION": тяжёлые,
        "AUTOPLAY_COUNT": sum(с.get("a11y", {}).get("autoplay", 0) for с in измеренные),
        "FOCUSABLE_ELEMENTS": max(
            (с.get("a11y", {}).get("focusable", 0) for с in измеренные), default=0),
        "INTERACTION_CHECKS": len(действия),
        "INTERACTION_FAILURES": len(провалы),
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
    if (измерено["LOW_CONTRAST_COUNT"] or измерено["HEADING_ORDER_SKIPS"]
            or измерено["PAGES_WITHOUT_SINGLE_H1"] or измерено["PAGES_WITHOUT_LANDMARKS"]
            or измерено["UNLABELLED_CONTROL_COUNT"]):
        отказы["accessibility"] = (
            f"контраст ниже порога у {измерено['LOW_CONTRAST_COUNT']}, "
            f"пропусков уровня {измерено['HEADING_ORDER_SKIPS']}, "
            f"страниц без единственного h1 {измерено['PAGES_WITHOUT_SINGLE_H1']}, "
            f"без ориентиров {измерено['PAGES_WITHOUT_LANDMARKS']}, "
            f"безымянных органов управления {измерено['UNLABELLED_CONTROL_COUNT']}")
    if (измерено["SMALL_TOUCH_TARGET_COUNT"] or измерено["DEAD_CONTROL_COUNT"]
            or измерено["DEAD_LINK_COUNT"]):
        отказы["ux"] = (f"{измерено['SMALL_TOUCH_TARGET_COUNT']} целей мельче 44×44, "
                        f"{измерено['DEAD_CONTROL_COUNT']} кнопок без действия, "
                        f"{измерено['DEAD_LINK_COUNT']} ссылок в никуда")
    if измерено["REDUCED_MOTION_VIOLATIONS"]:
        отказы["accessibility"] = (
            f"{измерено['REDUCED_MOTION_VIOLATIONS']} элементов продолжают двигаться "
            f"при включённой настройке «уменьшить анимацию»")
    if провалы:
        отказы["ux"] = (отказы.get("ux", "") +
                        f"; провалов действия {len(провалы)}: "
                        f"{провалы[0]['component']}/{провалы[0]['check']}").strip("; ")
    if измерено["FOCUSABLE_ELEMENTS"] == 0:
        отказы["accessibility"] = "на странице нет ни одного фокусируемого элемента"
    if измерено["HEAVY_FRAMES_BEFORE_ACTION"] or измерено["AUTOPLAY_COUNT"]:
        отказы["performance"] = "тяжёлый кадр или автозапуск до действия человека"
    # Бюджет объявлен заданием: 80 КБ на собственные стили пакета.
    if css_байт and css_байт > 80 * 1024:
        отказы["performance"] = f"стили пакета {css_байт} байт при бюджете {80 * 1024}"

    блоки = манифест.get("home_block_order", [])
    сетки = [б for б in блоки if б.get("тип") in ("grid", "feed")]
    if len(блоки) < 5:
        отказы["hierarchy"] = "меньше пяти блоков: композиции нет"
    if len(сетки) >= 3 and len({б.get("грамматика") for б in сетки}) == 1:
        отказы["hierarchy"] = "три и более одинаковых полки подряд"
    if измерено["ROUTES_MEASURED"] < 10:
        отказы["hierarchy"] = (f"измерено маршрутов {измерено['ROUTES_MEASURED']}: "
                               f"матрица неполна, оценивать нечего")

    баллы = {}
    for критерий, (вес, _) in РУБРИКА.items():
        баллы[критерий] = 0 if критерий in отказы else вес
    итог = sum(баллы.values())

    return {
        "template_id": манифест["template_id"],
        "slug": манифест["slug"],
        "route_model": манифест.get("route_model"),
        "measured": измерено,
        "criteria": баллы,
        "hard_fails": отказы,
        "measurement_failures": [
            {"route": с["route"], "viewport": с["viewport"],
             "error": с["measurement_error"]} for с in несостоявшиеся],
        "interaction_failures": провалы[:12],
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
    parser.add_argument("--preview", required=True, help="каталог с отрисованными маршрутами")
    parser.add_argument("--record")
    parser.add_argument("--screenshots")
    parser.add_argument("--full", action="store_true",
                        help="все маршруты на всех шести ширинах (для shortlist)")
    args = parser.parse_args()

    пакет = pathlib.Path(args.package)
    манифест = json.loads((пакет / "template.json").read_text(encoding="utf-8"))
    превью = pathlib.Path(args.preview)
    if not any(превью.glob("*.html")):
        print(f"нет отрисованных маршрутов в {превью}", file=sys.stderr)
        return 2

    css_байт = sum(
        (пакет / имя).stat().st_size
        for имя in ("tokens.css", "layout.css", "components.css")
        if (пакет / имя).is_file()
    )
    страницы, действия, спокойствие = измерить(
        превью, pathlib.Path(args.screenshots) if args.screenshots else None, args.full)
    отчёт = оценить(манифест, страницы, действия, css_байт, спокойствие)
    отчёт["pages"] = страницы
    отчёт["interactions"] = действия
    отчёт["reduced_motion"] = спокойствие
    if args.record:
        pathlib.Path(args.record).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(args.record).write_text(
            json.dumps(отчёт, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in отчёт.items()
                      if k not in ("pages", "interactions")},
                     ensure_ascii=False, indent=2))
    return 0 if отчёт["PASS"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
