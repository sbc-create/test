#!/usr/bin/env python3
"""Как витрина отрисована на телефоне: перелив, сетка, доступность меню.

Только чтение публичных страниц настоящим браузером в окне телефона.

ЗАЧЕМ ОТДЕЛЬНЫЙ ИНСТРУМЕНТ. Остальные ночные проходы читают HTML через
`curl`: по разметке видно ссылки, заголовки и размеры картинок, но НЕ видно,
во что это раскладывается на экране 390 px. Перелив по горизонтали, карточка
шире окна и меню, уехавшее за край, в разметке выглядят нормально.

ЧТО СЧИТАЕТСЯ ДЕФЕКТОМ, А ЧТО НЕТ.

* ``ГОРИЗОНТАЛЬНАЯ ПРОКРУТКА`` — `scrollWidth` документа больше окна более чем
  на ``ПОРОГ_ПЕРЕЛИВА_PX``. Запас нужен: браузер округляет дробные ширины, и
  перелив в 1 px посетитель не прокручивает;
* ``СОДЕРЖИМОЕ ЗА КРАЕМ`` — элемент выходит правее окна более чем на
  ``ПОРОГ_ВЫХОДА_PX``, и над ним НЕТ ни прокручиваемой, ни обрезающей коробки.
  Это главный признак, потому что он не зависит от `overflow-x`: на витринах
  сети документ часто обрезает по краю, и тогда прокрутки нет, а содержимое
  всё равно не видно. **Листаемая полка (`overflow-x: auto|scroll` у
  родителя) дефектом не считается:** карусель и есть горизонтальный жест;
* ``КАРТОЧКА ШИРЕ ОКНА`` — первая карточка каталога не влезает в окно;
* ``МЕНЮ НЕДОСТУПНО`` — ни одной видимой точки входа в навигацию (ссылка
  шапки, кнопка-гамбургер) в границах окна;
* ``ОТРИСОВКА В ПОРЯДКЕ`` — ничего из перечисленного.

РАЗЛИЧАЮЩИЙ КОНТРОЛЬ. Признак «за край ничего не выходит» ничего не стоит,
если инструмент не умеет выход за край замечать: пустая страница и сломанный
замер дают тот же ноль. Поэтому на КАЖДОЙ странице прямым ребёнком `body`
вставляется заведомо широкий блок, и он обязан попасть в найденное. Если не
попал — исход страницы ``НЕ ИЗМЕРЕНО``: сломан замер, а не витрина. Блок тут
же удаляется, страница не сохраняется и никуда не отправляется.

Измерено 21.10 (20:5xZ): контроль через `scrollWidth` провалился на ВСЕХ
десяти страницах пяти семейств — документ там не растёт, потому что обрезан по
краю. Это и есть причина, по которой признак судит по рамкам элементов, а
`scrollWidth` оставлен отдельным, более узким исходом.

    python3 automation/local/mobile-render-probe.py --url <адрес> [--json]
    python3 automation/local/mobile-render-probe.py --family lords-03 --json

Коды: 0 — все проверенные страницы в порядке; 1 — найден дефект отрисовки;
2 — ни одна страница не измерена.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

ХРОМ_ШАБЛОН = os.path.expanduser(
    "~/.cache/ms-playwright/chromium*/chrome-linux*/chrome")

#: Окно телефона. 390×844 — iPhone 12/13/14. Ширина здесь важна, высота — нет:
#: замер не зависит от того, сколько видно сразу.
ОКНО_ТЕЛЕФОНА = (390, 844)

#: Дробные ширины и округление дают перелив в 1–2 px на витринах без дефекта.
#: Порог назван, а не угадан: ниже него перелив не прокручивается пальцем.
ПОРОГ_ПЕРЕЛИВА_PX = 4

#: Ширина контрольного блока. Больше любого окна телефона с большим запасом.
КОНТРОЛЬНАЯ_ШИРИНА_PX = 2400

ПОРЯДОК = "ОТРИСОВКА В ПОРЯДКЕ"
ПРОКРУТКА = "ГОРИЗОНТАЛЬНАЯ ПРОКРУТКА"
ЗА_КРАЕМ = "СОДЕРЖИМОЕ ЗА КРАЕМ"
КАРТОЧКА_ШИРЕ = "КАРТОЧКА ШИРЕ ОКНА"
МЕНЮ_НЕТ = "МЕНЮ НЕДОСТУПНО"
НЕ_ИЗМЕРЕНО = "НЕ ИЗМЕРЕНО"

#: Чем больше вес, тем серьёзнее. Исход страницы — худшее из найденного.
ВЕС = {ПОРЯДОК: 0, МЕНЮ_НЕТ: 1, КАРТОЧКА_ШИРЕ: 2, ЗА_КРАЕМ: 3, ПРОКРУТКА: 4,
       НЕ_ИЗМЕРЕНО: 5}

#: Насколько элемент должен вылезти, чтобы это заметил посетитель. 4 px —
#: округление, 16 px — уже обрезанный текст или край карточки.
ПОРОГ_ВЫХОДА_PX = 16



#: Счётчики не должны получать технические просмотры: браузер исполняет
#: JavaScript страницы, а значит и счётчик Метрики. Требование владельца
#: 23.10. Модуль один на все браузерные инструменты — counter_guard.py.
#: Здесь перехват ставится на СТРАНИЦУ: этот инструмент контекст не создаёт.
def _запрет_счётчиков(цель):
    import importlib.util
    import pathlib as _pl
    п = _pl.Path(__file__).resolve().parent / "counter_guard.py"
    с = importlib.util.spec_from_file_location("counter_guard", п)
    м = importlib.util.module_from_spec(с)
    с.loader.exec_module(м)
    return м.запретить_счётчики(цель)

def исход(замер: dict) -> dict:
    """Исход по одному замеру. Чистая функция: браузер здесь не нужен.

    Ожидает ключи `окно_px`, `перелив_px`, `контроль_перелив_px`,
    `карточек`, `ширина_карточки_px`, `точек_входа_в_меню`.
    """
    if замер.get("ошибка"):
        return {"исход": НЕ_ИЗМЕРЕНО, "почему": замер["ошибка"], "дефекты": []}

    окно = замер.get("окно_px") or 0
    контроль = замер.get("контроль_перелив_px")
    if окно <= 0:
        return {"исход": НЕ_ИЗМЕРЕНО, "почему": "ширина окна не прочитана",
                "дефекты": []}
    if not isinstance(контроль, dict):
        return {"исход": НЕ_ИЗМЕРЕНО,
                "почему": "различающий контроль не выполнялся", "дефекты": []}
    if not контроль.get("замечен"):
        # Вставили блок в 2400 px прямым ребёнком `body` и не заметили его —
        # значит замер не видит выхода за край вообще, и «за краем ничего»
        # про витрину не говорит.
        return {"исход": НЕ_ИЗМЕРЕНО,
                "почему": f"контрольный блок {КОНТРОЛЬНАЯ_ШИРИНА_PX} px не"
                          f" замечен (правый край"
                          f" {контроль.get('справа_px', '—')} px при окне"
                          f" {окно}) — сломан замер",
                "дефекты": []}

    дефекты = []
    перелив = замер.get("перелив_px") or 0
    if перелив > ПОРОГ_ПЕРЕЛИВА_PX:
        дефекты.append({"исход": ПРОКРУТКА, "перелив_px": перелив,
                        "виновники": замер.get("свободные")
                        or замер.get("виновники") or []})
    свободные = замер.get("свободные") or []
    правее = замер.get("правее_всего_px") or 0
    if свободные and правее > окно + ПОРОГ_ВЫХОДА_PX:
        # Вылезло содержимое, над которым НЕТ ни прокручиваемой, ни
        # обрезающей коробки: карусель полки сюда не попадает, она листается
        # намеренно. Если документ обрезает по краю, прокрутки не будет —
        # содержимое просто не видно, и это тот же дефект, а не его отсутствие.
        дефекты.append({
            "исход": ЗА_КРАЕМ, "правее_всего_px": правее, "окно_px": окно,
            "обрезано_документом": bool(замер.get("обрезает_документ")),
            "виновники": свободные[:4]})
    ширина_карточки = замер.get("ширина_карточки_px") or 0
    if замер.get("карточек") and ширина_карточки > окно + ПОРОГ_ПЕРЕЛИВА_PX:
        дефекты.append({"исход": КАРТОЧКА_ШИРЕ,
                        "ширина_карточки_px": ширина_карточки, "окно_px": окно})
    if замер.get("точек_входа_в_меню") == 0:
        дефекты.append({"исход": МЕНЮ_НЕТ})

    if not дефекты:
        return {"исход": ПОРЯДОК,
                "почему": "за край ничего не выходит (кроме листаемых полок),"
                          " карточка влезает, меню доступно",
                "дефекты": []}
    худший = max((д["исход"] for д in дефекты), key=lambda и: ВЕС[и])
    return {"исход": худший, "почему": ", ".join(д["исход"] for д in дефекты),
            "дефекты": дефекты}


ЗАМЕР_JS = """
(() => {
  const w = window.innerWidth;
  const over = document.documentElement.scrollWidth - w;
  // Прокручиваемая или обрезающая родительская коробка объясняет выход за
  // край: карусель полки листается пальцем НАМЕРЕННО, а `overflow:hidden`
  // содержимое обрезает. Без этого различения признак ловил бы всякую полку.
  const рамка = (el) => {
    for (let p = el.parentElement; p && p !== document.documentElement; p = p.parentElement) {
      const ox = getComputedStyle(p).overflowX;
      if (ox === "auto" || ox === "scroll") return "листается";
      if (ox === "hidden" || ox === "clip") return "обрезано";
    }
    return "";
  };
  const bad = [];
  for (const el of document.querySelectorAll("body *")) {
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) continue;
    if (r.right > w + 4 || r.left < -4) {
      bad.push({
        "тег": el.tagName.toLowerCase(),
        "класс": (el.className && el.className.toString
                  ? el.className.toString() : "").slice(0, 60),
        "ширина": Math.round(r.width), "справа": Math.round(r.right),
        "рамка": рамка(el),
      });
    }
  }
  bad.sort((a, b) => b["справа"] - a["справа"]);
  const свободные = bad.filter((э) => э["рамка"] === "");
  const cards = Array.from(document.querySelectorAll(
      'a[href*="/title/"], a[href*="/anime/"], a[href*="/film/"]'))
    .filter((el) => { const r = el.getBoundingClientRect();
                      return r.width > 40 && r.height > 40; });
  const first = cards.length ? cards[0].getBoundingClientRect() : null;
  const inRow = first
    ? cards.filter((el) =>
        Math.abs(el.getBoundingClientRect().top - first.top) < 4).length
    : 0;
  const nav = Array.from(document.querySelectorAll(
      'header a, nav a, button, [class*="burger"], [class*="menu"]'))
    .filter((el) => { const r = el.getBoundingClientRect();
                      return r.width > 8 && r.height > 8
                             && r.right <= w + 4 && r.top < 900; });
  return {
    "окно_px": w, "перелив_px": over, "виновники": bad.slice(0, 4),
    "за_краем": bad.length, "за_краем_свободных": свободные.length,
    "свободные": свободные.slice(0, 4),
    "правее_всего_px": свободные.length ? свободные[0]["справа"] : 0,
    "обрезает_документ": ["hidden", "clip"].includes(
        getComputedStyle(document.documentElement).overflowX)
      || ["hidden", "clip"].includes(getComputedStyle(document.body).overflowX),
    "карточек": cards.length,
    "ширина_карточки_px": first ? Math.round(first.width) : 0,
    "карточек_в_ряду": inRow, "точек_входа_в_меню": nav.length,
  };
})()
"""

#: Контроль измеряет ТО ЖЕ, чем судится витрина. Блок вставляется прямым
#: ребёнком `body`, поэтому прокручиваемой или обрезающей рамки над ним нет, и
#: он обязан попасть в «свободные». Проверять контроль через `scrollWidth`
#: нельзя: на витринах с `overflow-x: hidden` документ не растёт, и контроль
#: провалился бы там, где замер исправен.
КОНТРОЛЬ_JS = """
(() => {
  const d = document.createElement("div");
  d.id = "k2-overflow-control";
  d.style.cssText = "width:%dpx;height:8px";
  document.body.appendChild(d);
  const w = window.innerWidth;
  const r = d.getBoundingClientRect();
  const замечен = r.right > w + 4;
  const рост = document.documentElement.scrollWidth - w;
  d.remove();
  return {"замечен": замечен, "рост_scrollWidth_px": рост,
          "справа_px": Math.round(r.right)};
})()
""" % КОНТРОЛЬНАЯ_ШИРИНА_PX


def замерить(адрес: str, *, окно: tuple[int, int] = ОКНО_ТЕЛЕФОНА) -> dict:
    """Живой замер одной страницы в окне телефона."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"адрес": адрес, "ошибка": "playwright не установлен"}
    кандидаты = sorted(glob.glob(ХРОМ_ШАБЛОН))
    if not кандидаты:
        return {"адрес": адрес, "ошибка": "Chromium playwright не найден"}

    with sync_playwright() as p:
        браузер = p.chromium.launch(
            executable_path=кандидаты[-1],
            args=["--no-sandbox", "--disable-dev-shm-usage"])
        страница = браузер.new_page(
            viewport={"width": окно[0], "height": окно[1]},
            device_scale_factor=3, is_mobile=True, has_touch=True,
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"
                       " AppleWebKit/605.1.15 (KHTML, like Gecko)"
                       " Version/17.0 Mobile/15E148 Safari/604.1")
        _перехвачено = _запрет_счётчиков(страница)
        try:
            try:
                ответ = страница.goto(адрес, wait_until="load", timeout=45000)
            except Exception as сбой:  # noqa: BLE001
                return {"адрес": адрес,
                        "ошибка": f"навигация не завершилась:"
                                  f" {type(сбой).__name__}: {str(сбой)[:80]}"}
            код = ответ.status if ответ else 0
            страница.wait_for_timeout(2500)
            замер = страница.evaluate(ЗАМЕР_JS)
            замер["контроль_перелив_px"] = страница.evaluate(КОНТРОЛЬ_JS)
            замер["адрес"] = адрес
            замер["код"] = код
            return замер
        finally:
            браузер.close()


def проверить(адрес: str, **кв) -> dict:
    замер = замерить(адрес, **кв)
    замер.update(исход(замер))
    return замер


СЕМЬИ = {
    "lords-03": ["https://lordserial33.biz/", "https://lordserial33.biz/films/"],
    "zona-01": ["https://zonafilm.space/", "https://zonafilm.space/films/"],
    "animedia": ["https://animedia.space/", "https://animedia.space/catalog/"],
    "animego": ["https://animeg0.site/", "https://animeg0.site/catalog/"],
    "yummy": ["https://yummyani.biz/", "https://yummyani.biz/catalog"],
}


def main(аргв: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--url", action="append", default=[])
    р.add_argument("--family", action="append", default=[],
                   choices=sorted(СЕМЬИ))
    р.add_argument("--json", action="store_true")
    а = р.parse_args(аргв)

    адреса = list(а.url)
    for семья in а.family:
        адреса.extend(СЕМЬИ[семья])
    if not адреса:
        for семья in sorted(СЕМЬИ):
            адреса.extend(СЕМЬИ[семья])

    итоги = [проверить(адрес) for адрес in адреса]
    if а.json:
        print(json.dumps({"страниц": len(итоги), "страницы": итоги},
                         ensure_ascii=False, indent=2))
    else:
        for и in итоги:
            print(f"{и['адрес'][:62]:64} {и['исход']}")
            print(f"{'':66} окно {и.get('окно_px', '—')} перелив"
                  f" {и.get('перелив_px', '—')} за краем"
                  f" {и.get('за_краем', '—')} из них без рамки"
                  f" {и.get('за_краем_свободных', '—')} обрезает документ"
                  f" {'да' if и.get('обрезает_документ') else 'нет'}")
            print(f"{'':66} карточка {и.get('ширина_карточки_px', '—')}"
                  f" в ряду {и.get('карточек_в_ряду', '—')} меню"
                  f" {и.get('точек_входа_в_меню', '—')}")
            if и["исход"] != ПОРЯДОК:
                print(f"{'':66} {и.get('почему', '')}")
            for д in и.get("дефекты", []):
                for в in д.get("виновники", [])[:2]:
                    print(f"{'':68} {в['тег']}.{в['класс'][:36]}"
                          f" ширина {в['ширина']} справа {в['справа']}")

    if all(и["исход"] == НЕ_ИЗМЕРЕНО for и in итоги):
        return 2
    return 1 if any(и["исход"] not in (ПОРЯДОК, НЕ_ИЗМЕРЕНО) for и in итоги) else 0


if __name__ == "__main__":
    sys.exit(main())
