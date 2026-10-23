#!/usr/bin/env python3
"""Обложки на ШЕСТИ ширинах экрана: что выбрал браузер и сколько это весит.

ЗАЧЕМ. Решение «постер избыточен» нельзя принимать по объявленному в разметке
`width`: решает ФАКТИЧЕСКИЙ размер отрисовки, умноженный на плотность экрана.
А после появления `srcset`/`sizes` появляется второй вопрос — КАКОЙ из
кандидатов браузер взял на этой ширине, и сколько байт он на это потратил.
Оба ответа даёт только настоящий браузер.

ПОЧЕМУ ШЕСТЬ ОКОН, А НЕ ДВА. `sizes` меньше истинной ширины отрисовки — это не
экономия: браузер берёт файл меньше нужного и растягивает его, теряя чёткость.
Значит проверять надо точки перелома сетки. По CSS витрин это 640, 768 и 1200,
поэтому берутся 390, 700, 768, 1024, 1280 и 1440 — по одной точке в каждом
диапазоне и две внутри самого широкого.

ВЕС берётся из Resource Timing (`encodedBodySize`), то есть ровно столько, сколько
ушло по сети за эту картинку на этом окне. Отдельный `curl` того же адреса
ответил бы на другой вопрос: он не знает, какой кандидат выбрал браузер.

ИСТИННЫЕ ПИКСЕЛИ — отдельным шагом (`--resolve-pixels`), по самому файлу.
`naturalWidth` при выборе кандидата из `srcset` с дескриптором `w` отдаётся
ПРИВЕДЁННЫМ к `sizes`, а не настоящим: измерено 23.10 — файл 424 px при
дескрипторе 480w и `sizes="176px"` даёт `naturalWidth` 155. Сравнение такого
числа с контролем, у которого `srcset` нет, показало бы уменьшение в шесть
раз, которого не было. Поле `файл_ш` поэтому называется приведённым, а
решения принимаются по `истинная_ш`.

Счётчики не получают технических просмотров: перехват ставится на КОНТЕКСТ до
первого перехода (counter_guard.py, требование владельца 23.10).

    python3 automation/local/poster-window-probe.py --domain animedia.icu \
        --domain animedia.space > замер.json
    python3 automation/local/poster-window-probe.py --domain … --windows 390,768
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
import sys

ХРОМ = pathlib.Path.home() / ".cache" / "ms-playwright"

#: (ширина, высота, плотность, мобильный). Плотность 2 на узких окнах и 1 на
#: широких — так же, как у настоящих устройств: решение по избытку зависит от
#: произведения ширины на плотность, и подставлять одну плотность всем нельзя.
ОКНА = {390: (390, 844, 2, True), 700: (700, 900, 2, True),
        768: (768, 1024, 2, True), 1024: (1024, 768, 1, False),
        1280: (1280, 800, 1, False), 1440: (1440, 900, 1, False)}

СТРАНИЦЫ = {"главная": "/", "каталог": "/catalog/", "карточка": "/title/009-1/"}

#: Имя агента не притворяется ни роботом, ни curl: витрины отвечают людям и
#: роботам по-разному, и замер «как роботу» ответил бы на другой вопрос.
АГЕНТ = "factory-window-probe"

ЗАМЕР_JS = """() => {
  // Вес по Resource Timing: ровно то, что ушло по сети за эту картинку.
  const вес = new Map();
  for (const з of performance.getEntriesByType('resource')) {
    if (з.initiatorType === 'img' || /\\.(webp|jpe?g|png|avif)/i.test(з.name)) {
      вес.set(з.name, {сеть: з.encodedBodySize || 0,
                       всего: з.transferSize || 0});
    }
  }
  const итог = [];
  for (const img of document.querySelectorAll('img')) {
    const r = img.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) continue;
    const адрес = img.currentSrc || img.src || '';
    if (!адрес.includes('/poster/') && !адрес.includes('poster.cdnvideohub')) {
      continue;
    }
    const в = вес.get(адрес) || {сеть: null, всего: null};
    итог.push({
      класс: img.className || '',
      показ_ш: Math.round(r.width), показ_в: Math.round(r.height),
      // Приведённая ширина: при srcset с дескриптором w это НЕ ширина
      // файла (см. описание модуля). Истинную даёт --resolve-pixels.
      приведённая_ш: img.naturalWidth, приведённая_в: img.naturalHeight,
      dpr: window.devicePixelRatio,
      нужно_px: Math.round(r.width * window.devicePixelRatio),
      вес_байт: в.сеть, вес_с_заголовками: в.всего,
      srcset: (img.getAttribute('srcset') || '').slice(0, 200),
      sizes: img.getAttribute('sizes') || '',
      loading: img.getAttribute('loading') || 'НЕТ',
      fetchpriority: img.getAttribute('fetchpriority') || 'НЕТ',
      // Классы предков: по ним обложка относится к БЛОКУ показа (карусель,
      // сетка подборки, шапка карточки). Без этого два места показа с одним
      // классом картинки различить нельзя, а `sizes` у них разный.
      предки: (() => {
        const ц = [];
        let у = img.parentElement;
        while (у && ц.length < 6) {
          if (у.className && typeof у.className === 'string') {
            ц.push(у.className.trim().slice(0, 40));
          }
          у = у.parentElement;
        }
        return ц;
      })(),
      адрес,
    });
  }
  return итог;
}"""


def _страж():
    п = pathlib.Path(__file__).resolve().parent / "counter_guard.py"
    с = importlib.util.spec_from_file_location("counter_guard", п)
    м = importlib.util.module_from_spec(с)
    с.loader.exec_module(м)
    return м


def замерить(домены, окна, страницы) -> list[dict]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("НЕ ИЗМЕРЕНО: playwright не установлен", file=sys.stderr)
        return []
    кандидаты = sorted(ХРОМ.glob("chromium*/chrome-linux*/chrome"))
    if not кандидаты:
        print("НЕ ИЗМЕРЕНО: chromium playwright не найден", file=sys.stderr)
        return []
    страж = _страж()
    строки: list[dict] = []
    with sync_playwright() as p:
        браузер = p.chromium.launch(
            executable_path=str(кандидаты[-1]),
            args=["--no-sandbox", "--disable-dev-shm-usage"])
        try:
            for ключ in окна:
                ш, в, плотность, мобильный = ОКНА[ключ]
                контекст = браузер.new_context(
                    viewport={"width": ш, "height": в},
                    device_scale_factor=плотность, is_mobile=мобильный,
                    has_touch=мобильный, locale="ru-RU", user_agent=АГЕНТ)
                перехвачено = страж.запретить_счётчики(контекст)
                страница = контекст.new_page()
                for домен in домены:
                    for вид, путь in страницы.items():
                        адрес = f"https://{домен}{путь}"
                        try:
                            страница.goto(адрес, wait_until="load",
                                          timeout=45000)
                            # Прокрутка до низа: отложенные обложки иначе не
                            # грузятся, и вес первого экрана не отличить от
                            # веса страницы.
                            страница.evaluate(
                                "window.scrollTo(0,"
                                " document.body.scrollHeight)")
                            страница.wait_for_timeout(1800)
                        except Exception as сбой:  # noqa: BLE001
                            строки.append({
                                "окно": ключ, "домен": домен, "страница": вид,
                                "исход": f"НЕ ИЗМЕРЕНО:"
                                         f" {type(сбой).__name__}:"
                                         f" {str(сбой)[:80]}"})
                            continue
                        for з in страница.evaluate(ЗАМЕР_JS):
                            з.update({"окно": ключ, "плотность": плотность,
                                      "домен": домен, "страница": вид})
                            строки.append(з)
                строки.append({"окно": ключ, "домен": "—",
                               "страница": "служебное",
                               "счётчиков_перехвачено": len(перехвачено)})
                контекст.close()
        finally:
            браузер.close()
    return строки


def разрешить_пиксели(строки: list[dict]) -> dict:
    """Истинные размеры и вес по выбранным адресам, по одному запросу на адрес.

    Читается только заголовок: PIL разбирает размеры, не декодируя картинку.
    Если библиотеки нет, шаг честно отказывается, а не подставляет приведённые
    числа вместо истинных.
    """
    try:
        from PIL import Image
    except ImportError as сбой:
        print(f"ПИКСЕЛИ НЕ РАЗРЕШЕНЫ: {сбой}. Проверять окружением службы:"
              " automation/local/service-image-support-check.py",
              file=sys.stderr)
        return {}
    import io
    import urllib.request
    адреса = sorted({с["адрес"] for с in строки if с.get("адрес")})
    итог: dict[str, dict] = {}
    for адрес in адреса:
        запрос = urllib.request.Request(адрес, headers={"User-Agent": АГЕНТ})
        try:
            with urllib.request.urlopen(запрос, timeout=20) as ответ:
                байты = ответ.read()
            с_ = Image.open(io.BytesIO(байты))
            итог[адрес] = {"истинная_ш": с_.width, "истинная_в": с_.height,
                           "байт_файла": len(байты), "формат": с_.format}
        except Exception as сбой:  # noqa: BLE001
            итог[адрес] = {"истинная_ш": None, "истинная_в": None,
                           "байт_файла": None,
                           "почему": f"{type(сбой).__name__}: {str(сбой)[:60]}"}
    print(f"ПИКСЕЛИ РАЗРЕШЕНЫ: адресов {len(итог)},"
          f" из них без ответа"
          f" {sum(1 for з in итог.values() if з['истинная_ш'] is None)}",
          file=sys.stderr)
    return итог


def main(аргв=None) -> int:
    р = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--domain", action="append", default=[], required=True)
    р.add_argument("--windows", default="",
                   help="через запятую из " + ",".join(str(к) for к in ОКНА))
    р.add_argument("--resolve-pixels", action="store_true",
                   help="добрать истинные размеры и вес по каждому выбранному"
                        " адресу (одним запросом на адрес)")
    р.add_argument("--pages", default="",
                   help="через запятую из " + ",".join(СТРАНИЦЫ))
    а = р.parse_args(аргв)
    окна = ([int(ч) for ч in а.windows.split(",") if ч.strip()]
            if а.windows else list(ОКНА))
    плохие = [к for к in окна if к not in ОКНА]
    if плохие:
        print(f"ОСТАНОВ: неизвестные окна {плохие}", file=sys.stderr)
        return 2
    страницы = ({и: СТРАНИЦЫ[и] for и in а.pages.split(",") if и in СТРАНИЦЫ}
                if а.pages else СТРАНИЦЫ)
    строки = замерить(а.domain, окна, страницы)
    if а.resolve_pixels:
        по_адресу = разрешить_пиксели(строки)
        for с in строки:
            if с.get("адрес") in по_адресу:
                с.update(по_адресу[с["адрес"]])
    print(json.dumps(строки, ensure_ascii=False))
    отказов = sum(1 for с in строки if "исход" in с)
    обложек = sum(1 for с in строки if "адрес" in с)
    # Метка завершения в stderr: stdout должен остаться разбираемым JSON.
    print(f"ЗАВЕРШЕНО: замеров {обложек}, окон {len(окна)},"
          f" домéнов {len(а.domain)}, страниц без замера {отказов}",
          file=sys.stderr)
    return 0 if обложек else 1


if __name__ == "__main__":
    sys.exit(main())
