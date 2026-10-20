#!/usr/bin/env python3
"""Что видит посетитель на странице серии: загрузка, плеер, начало показа.

Проверяется браузером, а не кодом ответа: плеер витрин Yummy и Lords — сторонний
кадр (iframe), страница рисуется на клиенте, и `curl` о работе плеера не говорит
ничего.

Что измеряется по каждой странице и каждому устройству:

* код ответа и время до готовности разметки;
* найден ли контейнер плеера и кадр со сторонним адресом;
* **начался ли показ** — по сетевым запросам кадра к видеопотоку
  (`.m3u8`, `.mpd`, `.mp4`, `/segment`, `videohub`): запрос манифеста означает,
  что плеер действительно начал забирать видео, а не просто нарисовался;
* ошибки консоли и неудачные запросы (кроме сторонней рекламы — она считается
  отдельно);
* перекрытия: элементы с большим z-index поверх плеера;
* ссылка на следующую серию.

Третий исход обязателен: нет браузера — «не измерено», а не «плеер не работает».

    python3 automation/local/player-page-probe.py --url https://yummyani.site/anime/x/season/7/episode/4
    python3 automation/local/player-page-probe.py --file страницы.txt --json

Коды: 0 — на всех страницах показ начался; 1 — где-то не начался; 2 — не измерено.
"""
from __future__ import annotations

import argparse
import glob
import json
import pathlib
import re
import sys

ХРОМ_ШАБЛОН = "/home/claude/.cache/ms-playwright/chromium*/chrome-linux*/chrome"
#: Настоящий видеопоток. Картинки и постеры сюда НЕ входят: в первой редакции
#: шаблон содержал «videohub», а постеры витрины лежат на
#: poster.cdnvideohub.com — проверка срабатывала на главной, где плеера нет
#: вовсе, то есть не могла провалиться и ничего не стоила.
ПОТОК = re.compile(
    r"\.m3u8|\.mpd|/hls/|/dash/|/segment|\.ts(\?|$)|\.mp4(\?|$)|\.m4s(\?|$)"
    # Видео витрин Yummy отдаёт инфраструктура VK/OK: кадр плеера
    # player.cdnvideohub.com забирает поток с *.vkuser.net. Измерено 19.10:
    # до нажатия запросов к vkuser.net ноль, после нажатия — восемь. Классических
    # «.m3u8» в этом пути нет вовсе, поэтому без этих хостов проверка отвечала
    # бы «показ не начался» даже на работающем плеере.
    # Узлы доставки видео VK/OK: `*.vkuser.net` и `vd<N>.okcdn.ru`. Проверено
    # 19.10 на двух тайтлах: до нажатия запросов к ним ноль, после нажатия
    # 6–8. Хосты `iv.okcdn.ru` и `api.mycdn.me` сюда НЕ входят — они
    # отвечают и до нажатия (предпросмотр), и по ним показ не отличить.
    r"|vkuser\.net|vd\d+\.okcdn\.ru|getVideo", re.I)
#: Что похоже на поток, но им не является.
НЕ_ПОТОК = re.compile(r"poster\.|/poster/|\.webp|\.jpe?g|\.png|\.avif|\.svg|\.ico", re.I)
РЕКЛАМА = re.compile(r"doubleclick|googlesyndication|adfox|yandex\.ru/ads|advert", re.I)
УСТРОЙСТВА = {
    "телефон": {"viewport": {"width": 390, "height": 844}, "is_mobile": True,
                "user_agent": ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                               "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                               "Version/17.0 Mobile/15E148 Safari/604.1")},
    "компьютер": {"viewport": {"width": 1366, "height": 768}, "is_mobile": False,
                  "user_agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                 "AppleWebKit/537.36 (KHTML, like Gecko) "
                                 "Chrome/125.0 Safari/537.36")},
}


#: Разделы, где плеера нет по замыслу: главная, каталог, подборки, расписание.
БЕЗ_ПЛЕЕРА = re.compile(r"^https?://[^/]+/?$|/catalog|/collections?|/schedule|/top|/new")


def не_требует_плеера(адрес: str) -> bool:
    return bool(БЕЗ_ПЛЕЕРА.search(адрес))


def проверить_страницу(bp, адрес: str, устройство: str, ожидание_мс: int) -> dict:
    итог = {"url": адрес, "устройство": устройство, "итог": "не измерено"}
    настройки = dict(УСТРОЙСТВА[устройство])
    мобильный = настройки.pop("is_mobile")
    контекст = bp.new_context(**настройки, is_mobile=мобильный,
                              has_touch=мобильный, locale="ru-RU")
    страница = контекст.new_page()
    поток, ошибки, неудачи, реклама = [], [], [], []
    страница.on("console", lambda с: ошибки.append(с.text[:160])
                if с.type == "error" else None)
    страница.on("requestfailed", lambda з: (
        реклама if РЕКЛАМА.search(з.url) else неудачи).append(з.url[:120]))
    страница.on("request", lambda з: поток.append(з.url[:160])
                if (ПОТОК.search(з.url) and not НЕ_ПОТОК.search(з.url)) else None)
    try:
        ответ = страница.goto(адрес, wait_until="domcontentloaded", timeout=45000)
        итог["код"] = ответ.status if ответ else None
        страница.wait_for_timeout(ожидание_мс)
        итог["заголовок"] = (страница.title() or "")[:120]
        кадры = [к.url for к in страница.frames if к.url and к.url != адрес]
        итог["кадров"] = len(кадры)
        итог["кадр_плеера"] = next((к for к in кадры if "http" in к), "")[:160]
        итог["контейнер_плеера"] = страница.locator(
            "video, iframe, [class*=player], [id*=player]").count()
        итог["ссылка_след_серия"] = страница.locator(
            "a[href*='/episode/'], a[href*='episode-']").count()
        # Перекрытия: элементы с z-index выше 1000 и площадью больше четверти экрана.
        итог["перекрытий"] = страница.evaluate(
            """() => {
                const w = window.innerWidth * window.innerHeight;
                return [...document.querySelectorAll('body *')].filter((э) => {
                    const с = getComputedStyle(э);
                    const z = parseInt(с.zIndex || '0', 10);
                    if (!z || z < 1000) return false;
                    if (с.display === 'none' || с.visibility === 'hidden') return false;
                    const r = э.getBoundingClientRect();
                    return r.width * r.height > w / 4;
                }).length;
            }"""
        )
        # Автозапуск браузеры блокируют, и посетитель нажимает сам. Если поток
        # не пошёл, пробуем ровно то, что сделал бы человек: одно нажатие по
        # области плеера — и смотрим снова. Без этого «показ не начался» значило
        # бы только «автозапуск запрещён».
        if not поток:
            итог["нажатие"] = False
            try:
                цель = страница.locator(
                    "iframe, video, [class*=player], [id*=player]").first
                if цель.count() if hasattr(цель, "count") else True:
                    цель.click(timeout=5000, position={"x": 20, "y": 20})
                    итог["нажатие"] = True
                    страница.wait_for_timeout(min(ожидание_мс, 8000))
            except Exception as сбой:
                итог["нажатие_почему"] = str(сбой)[:120]
        итог["показ_начался"] = bool(поток)
        итог["поток_примеры"] = поток[:3]
        итог["ошибки_консоли"] = ошибки[:5]
        итог["неудачных_запросов"] = len(неудачи)
        итог["рекламных_отказов"] = len(реклама)
        # Страница без плеера — не поломка: на главной и в каталоге его нет по
        # замыслу. Такой исход называется отдельно, иначе список «не начался»
        # смешает отсутствие плеера с его отказом.
        если_плеер = итог["контейнер_плеера"] or итог["кадров"]
        if не_требует_плеера(адрес) or not если_плеер:
            итог["итог"] = "плеера нет"
        else:
            итог["итог"] = "показ начался" if поток else "показ не начался"
    except Exception as сбой:  # сетевой сбой — честная причина, не «не работает»
        итог["итог"] = "не измерено"
        итог["почему"] = str(сбой)[:160]
    finally:
        контекст.close()
    return итог


def main(аргв: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(description="страница серии глазами посетителя")
    р.add_argument("--url", action="append", default=[])
    р.add_argument("--file", default="", help="файл со списком адресов")
    р.add_argument("--wait", type=int, default=9000, help="ожидание после загрузки, мс")
    р.add_argument("--json", action="store_true")
    р.add_argument("--device", action="append", default=[],
                   choices=sorted(УСТРОЙСТВА), help="по умолчанию оба")
    дов = р.parse_args(аргв)

    адреса = list(дов.url)
    if дов.file:
        адреса += [с.strip() for с
                   in pathlib.Path(дов.file).read_text(
                       encoding="utf-8").splitlines()
                   if с.strip() and not с.startswith("#")]
    if not адреса:
        print("НЕ ИЗМЕРЕНО: адреса не переданы")
        return 2
    устройства = дов.device or sorted(УСТРОЙСТВА)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("НЕ ИЗМЕРЕНО: playwright не установлен")
        return 2
    кандидаты = sorted(glob.glob(ХРОМ_ШАБЛОН))
    if not кандидаты:
        print("НЕ ИЗМЕРЕНО: Chromium playwright не найден")
        return 2

    итоги = []
    with sync_playwright() as p:
        браузер = p.chromium.launch(executable_path=кандидаты[-1], args=[
            "--no-sandbox", "--disable-dev-shm-usage"])
        try:
            for адрес in адреса:
                for устройство in устройства:
                    итоги.append(проверить_страницу(браузер, адрес, устройство, дов.wait))
        finally:
            браузер.close()

    if дов.json:
        print(json.dumps(итоги, ensure_ascii=False, indent=2))
    else:
        for и in итоги:
            print(f"{и['устройство']:10} {и['итог']:16} код {и.get('код')}"
                  f"  плеер {и.get('контейнер_плеера')}  кадров {и.get('кадров')}"
                  f"  перекрытий {и.get('перекрытий')}"
                  f"  ошибок консоли {len(и.get('ошибки_консоли') or [])}"
                  f"  неудач {и.get('неудачных_запросов')}"
                  f"  ссылок на серии {и.get('ссылка_след_серия')}  {и['url']}")
            if и.get("почему"):
                print(f"           причина: {и['почему']}")
        начался = [и for и in итоги if и["итог"] == "показ начался"]
        не_начался = [и for и in итоги if и["итог"] == "показ не начался"]
        без_плеера = [и for и in итоги if и["итог"] == "плеера нет"]
        не_изм = [и for и in итоги if и["итог"] == "не измерено"]
        print()
        print(f"страниц-проверок {len(итоги)}: показ начался {len(начался)},"
              f" не начался {len(не_начался)}, плеера нет {len(без_плеера)},"
              f" не измерено {len(не_изм)}")
    если_измерено = [и for и in итоги if и["итог"] != "не измерено"]
    if not если_измерено:
        return 2
    return 1 if any(и["итог"] == "показ не начался" for и in если_измерено) else 0


if __name__ == "__main__":
    sys.exit(main())
