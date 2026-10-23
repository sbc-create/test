#!/usr/bin/env python3
"""LCP и CLS на страницах произведений и серий. Только чтение.

ЗАЧЕМ ИМЕННО ЭТИ СТРАНИЦЫ. Разбор посадочных 23.10 показал, что поисковые
визиты приносят почти исключительно страницы произведений и серий: 65–97 % по
домéнам. Главная значима только у двух витрин. Значит и качество отрисовки
имеет смысл мерить там, где приходят люди, а не на главной.

ЧТО ЭТО ЗА ДАННЫЕ. ЛАБОРАТОРНЫЕ. По L-007 решение о Core Web Vitals
принимается по ПОЛЕВЫМ данным (CrUX, Вебмастер), которых у сессии нет (B027,
B023). Лабораторный замер называет кандидата и сравнивает витрины между собой,
но не доказывает, что посетители видят то же самое. Инструмент печатает это
сам, чтобы число не поехало в отчёт без оговорки.

ПОЧЕМУ ВЫБОРКА, А НЕ ОДНА СТРАНИЦА. На коротких страницах CLS и LCP шумят:
одна страница даёт число, выборка даёт распределение. Берётся несколько
адресов на витрину, печатается медиана и максимум.

КАК СЧИТАЕТСЯ:

* ``LCP`` — последняя запись `largest-contentful-paint` к моменту снятия, плюс
  тег и адрес самого элемента: без элемента непонятно, что именно улучшать;
* ``CLS`` — сумма `layout-shift` без `hadRecentInput`, то есть сдвиги, которые
  посетитель не вызывал сам;
* ``элементов без размеров`` — изображения в разметке без width/height:
  отдельный признак, потому что это главная причина сдвигов и её видно и без
  CLS.

Счётчики не получают технических просмотров: перехват ставится на контекст до
первого перехода (counter_guard.py).

    python3 automation/local/page-vitals-probe.py --domain animedia.icu --count 6
    python3 automation/local/page-vitals-probe.py --domain animedia.icu --json
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
import re
import statistics
import subprocess
import sys

ХРОМ = pathlib.Path.home() / ".cache" / "ms-playwright"
ОКНО_ТЕЛЕФОНА = (390, 844, 3)
АГЕНТ = "factory-vitals-probe"

ЗАМЕР_JS = """() => new Promise((готово) => {
  let lcp = null;
  let cls = 0;
  try {
    new PerformanceObserver((список) => {
      const записи = список.getEntries();
      const последняя = записи[записи.length - 1];
      if (последняя) {
        lcp = {
          ms: Math.round(последняя.startTime),
          тег: (последняя.element && последняя.element.tagName) || '',
          класс: (последняя.element && последняя.element.className) || '',
          адрес: (последняя.url || '').slice(-70),
          размер: Math.round(последняя.size || 0),
        };
      }
    }).observe({type: 'largest-contentful-paint', buffered: true});
  } catch (e) { /* браузер без поддержки — отдаём null */ }
  try {
    new PerformanceObserver((список) => {
      for (const з of список.getEntries()) {
        if (!з.hadRecentInput) { cls += з.value; }
      }
    }).observe({type: 'layout-shift', buffered: true});
  } catch (e) { /* то же */ }
  setTimeout(() => {
    const картинки = [...document.querySelectorAll('img')];
    const без_размеров = картинки.filter((и) => {
      const вид = window.getComputedStyle(и);
      const задан = (и.getAttribute('width') && и.getAttribute('height'))
        || (вид.aspectRatio && вид.aspectRatio !== 'auto');
      const виден = и.getBoundingClientRect().width > 2;
      return виден && !задан;
    }).length;
    готово({
      lcp,
      cls: Math.round(cls * 10000) / 10000,
      картинок: картинки.length,
      без_размеров,
      высота: document.documentElement.scrollHeight,
    });
  }, 3000);
})"""


def _страж():
    п = pathlib.Path(__file__).resolve().parent / "counter_guard.py"
    с = importlib.util.spec_from_file_location("counter_guard", п)
    м = importlib.util.module_from_spec(с)
    с.loader.exec_module(м)
    return м


def адреса(домен: str, сколько: int) -> tuple[list[str], list[str]]:
    """Адреса произведений и серий с живой карты сайта.

    Берутся из карты, а не придумываются: в CLOSED_WORLD адрес, которого нет
    в данных витрины, не существует.
    """
    def тело(адрес, предел=40):
        р = subprocess.run(
            ["curl", "-sSL", "--max-time", str(предел), "--compressed",
             "-A", АГЕНТ, адрес],
            capture_output=True, text=True, timeout=предел + 20)
        return р.stdout

    индекс = тело(f"https://{домен}/sitemap.xml")
    части = [а for а in re.findall(r"<loc>([^<]+)</loc>", индекс)
             if а.endswith(".xml")] or [f"https://{домен}/sitemap.xml"]
    произведения: list[str] = []
    серии: list[str] = []
    for часть in части[:3]:
        for а in re.findall(r"<loc>([^<]+)</loc>", тело(часть, 60)):
            путь = а.split(домен, 1)[-1]
            if re.search(r"/(season|episode)[-/]", путь):
                серии.append(а)
            elif re.match(r"^/(title|anime)/[^/]+/?$", путь):
                произведения.append(а)
            if len(произведения) >= сколько * 40 and len(серии) >= сколько * 40:
                break
    шаг_п = max(1, len(произведения) // max(1, сколько))
    выбранные_п = произведения[::шаг_п][:сколько]
    if not серии and выбранные_п:
        # Адресов серий в карте может не быть вовсе: их включение —
        # решение КАЖДОЙ витрины и по умолчанию выключено (MOD-79, бюджет
        # карты). Тогда адреса берутся со страницы произведения, где они и
        # объявлены ссылками. Это по-прежнему данные витрины, а не догадка.
        for страница in выбранные_п[:3]:
            html = тело(страница)
            ссылки = re.findall(
                r'href="([^"]*?(?:/season[-/]\d+/episode[-/]\d+|'
                r'/season/\d+/episode/\d+)[^"]*?)"', html)
            for сс in ссылки:
                полный = сс if сс.startswith("http") else (
                    f"https://{домен}{сс}")
                if полный not in серии:
                    серии.append(полный)
            if len(серии) >= сколько:
                break
    шаг_с = max(1, len(серии) // max(1, сколько))
    return (выбранные_п, серии[::шаг_с][:сколько])


def замерить(адреса_списком: list[str], окно=ОКНО_ТЕЛЕФОНА) -> list[dict]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("НЕ ИЗМЕРЕНО: playwright не установлен", file=sys.stderr)
        return []
    кандидаты = sorted(ХРОМ.glob("chromium*/chrome-linux*/chrome"))
    if not кандидаты:
        print("НЕ ИЗМЕРЕНО: chromium playwright не найден", file=sys.stderr)
        return []
    ширина, высота, плотность = окно
    страж = _страж()
    итог: list[dict] = []
    with sync_playwright() as p:
        браузер = p.chromium.launch(
            executable_path=str(кандидаты[-1]),
            args=["--no-sandbox", "--disable-dev-shm-usage"])
        try:
            контекст = браузер.new_context(
                viewport={"width": ширина, "height": высота},
                device_scale_factor=плотность, is_mobile=True,
                has_touch=True, locale="ru-RU", user_agent=АГЕНТ)
            перехвачено = страж.запретить_счётчики(контекст)
            страница = контекст.new_page()
            for адрес in адреса_списком:
                запись = {"адрес": адрес}
                try:
                    ответ = страница.goto(адрес, wait_until="load",
                                          timeout=45000)
                    запись["код"] = ответ.status if ответ else 0
                    запись.update(страница.evaluate(ЗАМЕР_JS))
                except Exception as сбой:  # noqa: BLE001
                    запись["ошибка"] = (f"{type(сбой).__name__}:"
                                        f" {str(сбой)[:70]}")
                итог.append(запись)
            запись = {"адрес": "—", "счётчиков_перехвачено": len(перехвачено)}
            итог.append(запись)
            контекст.close()
        finally:
            браузер.close()
    return итог


def свод(строки: list[dict], имя: str) -> None:
    годные = [с for с in строки if с.get("lcp") and not с.get("ошибка")]
    if not годные:
        print(f"{имя}: НЕ ИЗМЕРЕНО — ни одной страницы с LCP")
        return
    lcp = [с["lcp"]["ms"] for с in годные]
    cls = [с.get("cls") or 0 for с in годные]
    без = [с.get("без_размеров") or 0 for с in годные]
    теги = {}
    for с in годные:
        ключ = f"{с['lcp']['тег']}.{(с['lcp']['класс'] or '').split(' ')[0]}"
        теги[ключ] = теги.get(ключ, 0) + 1
    print(f"{имя}: страниц {len(годные)}"
          f" | LCP медиана {statistics.median(lcp):.0f} мс,"
          f" макс {max(lcp)} мс"
          f" | CLS медиана {statistics.median(cls):.4f},"
          f" макс {max(cls):.4f}"
          f" | картинок без размеров медиана {statistics.median(без):.0f}")
    print(f"     элемент LCP: {теги}")
    худший = max(годные, key=lambda с: с["lcp"]["ms"])
    print(f"     самый медленный: {худший['lcp']['ms']} мс,"
          f" {худший['адрес'][-60:]}")


def main(аргв=None) -> int:
    р = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--domain", action="append", default=[], required=True)
    р.add_argument("--count", type=int, default=5,
                   help="сколько произведений и сколько серий на витрину")
    р.add_argument("--path", action="append", default=[],
                   help="мерить ИМЕННО эти пути на каждой витрине. Нужно для"
                        " честного сравнения пары: выборка из своей карты у"
                        " каждой витрины своя, и разница страниц выдаёт себя"
                        " за разницу витрин")
    р.add_argument("--json", action="store_true")
    а = р.parse_args(аргв)
    всё: list[dict] = []
    for домен in а.domain:
        if а.path:
            произведения = [f"https://{домен}{п_}" for п_ in а.path
                            if not re.search(r"/(season|episode)[-/]", п_)]
            серии = [f"https://{домен}{п_}" for п_ in а.path
                     if re.search(r"/(season|episode)[-/]", п_)]
        else:
            произведения, серии = адреса(домен, а.count)
        if not произведения and not серии:
            print(f"{домен}: НЕ ИЗМЕРЕНО — адресов в карте не нашлось",
                  file=sys.stderr)
            continue
        строки = замерить(произведения + серии)
        for с in строки:
            с["домен"] = домен
            путь = с.get("адрес", "")
            с["вид"] = ("серия" if re.search(r"/(season|episode)[-/]", путь)
                        else ("произведение" if путь.startswith("http")
                              else "служебное"))
        всё += строки
        if not а.json:
            print("=" * 72)
            print(домен)
            свод([с for с in строки if с["вид"] == "произведение"],
                 "  произведения")
            свод([с for с in строки if с["вид"] == "серия"], "  серии")
    if а.json:
        print(json.dumps(всё, ensure_ascii=False, indent=1))
    else:
        print("\nДанные ЛАБОРАТОРНЫЕ: по L-007 решение о Core Web Vitals"
              " принимается по полевым (CrUX, Вебмастер), которых у сессии"
              " нет (B027, B023). Лабораторный замер называет кандидата LCP"
              " и сравнивает витрины, но не доказывает, что посетители видят"
              " то же самое.")
    годных = sum(1 for с in всё if с.get("lcp"))
    print(f"ЗАВЕРШЕНО: страниц с LCP {годных} из {len(всё)}", file=sys.stderr)
    return 0 if годных else 1


if __name__ == "__main__":
    sys.exit(main())
