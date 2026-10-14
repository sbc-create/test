#!/usr/bin/env python3
"""Осмотр витрины ДЕЙСТВИЕМ в браузере: клики, ввод, фильтры, снимки экрана.

Почему недостаточно кодов ответа. Страница отвечает 200 и с пустой выдачей, со
сломанным меню и с фильтром, который ничего не меняет. Поэтому здесь браузер
(Chromium через Playwright) действительно нажимает, вводит, прокручивает и
сравнивает ЧТО ИЗМЕНИЛОСЬ, а снимки экрана делаются в размерах компьютера и
телефона.

Что проверяется действием:
  * главная: блоки профиля, карточки, изображения, меню, поиск, подвал;
  * каталог: смена жанра/года/сортировки МЕНЯЕТ состав выдачи, работает
    пагинация;
  * карточка: название, постер, сведения, описание, похожее, сезоны и серии;
  * навигация: каждая видимая ссылка в шапке и подвале отвечает не 4xx/5xx,
    переход по карточке ведёт на её же страницу, пустая выдача и 404;
  * мобильная версия: нет горизонтальной прокрутки на 390×844, меню открывается;
  * SEO: title, description, canonical, h1, число внутренних ссылок;
  * режим индексации: X-Robots-Tag на каждой проверенной странице.

Стенд поднимает сам (как inspect-cell-ui.py) и гасит после осмотра. Данные
копируются во временный каталог: витрина в нём пишет только своё.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
#: Готовый Chromium окружения. Библиотека playwright ждёт сборку 1243, а
#: установлена 1234 — на одну версию старше. Скачивать новую ради одного
#: осмотра незачем: протокол совместим, и путь задаётся явно. Если файла нет,
#: инструмент скажет об этом прямо, а не упадёт стеной трассировки.
ГОТОВЫЙ_CHROMIUM = Path("/home/claude/.cache/ms-playwright/chromium-1234"
                        "/chrome-linux64/chrome")

КОМПЬЮТЕР = {"width": 1366, "height": 768}
ТЕЛЕФОН = {"width": 390, "height": 844}


def окружение(конфиг: dict, проект: Path, данные: Path) -> dict:
    env = dict(os.environ)
    for имя, шаблон in (конфиг.get("environment") or {}).items():
        env[имя] = (str(шаблон).replace("<data>", str(данные))
                    .replace("<app>", str(проект)))
    контакт = str(конфиг.get("contact_email") or "").strip()
    if контакт:
        env["SITE_CONTACT_EMAIL"] = контакт
    домен = str(конфиг.get("domain") or "").strip()
    if домен:
        env["LORDS_INDEXING_SITE"] = домен
    разрешение = (конфиг.get("indexing") or {}).get("release_permits_open")
    env["LORDS_INDEXING_RELEASE_PERMITS_OPEN"] = "true" if разрешение is True else "false"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def поднять(проект: Path, конфиг: dict, данные: Path, порт: int):
    точка = проект / "src" / конфиг["entrypoint"]
    процесс = subprocess.Popen(
        [sys.executable, str(точка), "--port", str(порт)],
        cwd=проект, env=окружение(конфиг, проект, данные),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    for _ in range(120):
        try:
            # Таймаут 12 с, а не 3: первый ответ /healthz на этом рантайме
            # занимает около четырёх секунд, и трёхсекундный пробник рвал
            # соединение раньше ответа — в журнале витрины оставались
            # BrokenPipe, а стенд считался не поднявшимся.
            urllib.request.urlopen(f"http://127.0.0.1:{порт}/healthz", timeout=12)
            return процесс, True
        except Exception:  # noqa: BLE001
            if процесс.poll() is not None:
                return процесс, False
            time.sleep(1)
    return процесс, False


def дождаться_картинок(стр, предел_мс: int = 15000) -> int:
    """Дождаться загрузки изображений перед снимком; вернуть число незагруженных.

    Переход ждёт `domcontentloaded`, а постеры помечены `loading="lazy"` и
    приходят с внешнего хоста: снимок сразу после перехода показывал пустые
    рамки там, где разметка полна. Предел конечный — недоступный хост не
    должен подвешивать осмотр, он должен попасть в отчёт числом.
    """
    try:
        стр.wait_for_function(
            "() => Array.from(document.images).every(i => i.complete)",
            timeout=предел_мс)
    except Exception:  # noqa: BLE001
        pass
    return стр.evaluate(
        "() => Array.from(document.images).filter(i => !i.complete).length")


def осмотр(стр, база: str, итог: dict) -> None:
    """Главная: блоки, карточки, изображения, меню, поиск, подвал."""
    стр.goto(база + "/", wait_until="domcontentloaded")
    карточки = стр.locator("a[href^='/title/'], article a[href*='/title/']")
    картинки = стр.locator("img")
    меню = стр.locator("header a, nav a")
    поиск = стр.locator("input[type='search'], input[name='q'], form input[type='text']")
    подвал = стр.locator("footer")
    итог["главная"] = {
        "title": стр.title(),
        "h1": (стр.locator("h1").first.inner_text().strip()
               if стр.locator("h1").count() else ""),
        "карточек": карточки.count(),
        "изображений": картинки.count(),
        "битых изображений": стр.evaluate(
            "() => Array.from(document.images).filter(i => i.complete && i.naturalWidth === 0).length"),
        "ссылок в меню": меню.count(),
        "поле поиска": поиск.count() > 0,
        "подвал": подвал.count() > 0,
        "подвал содержит почту": "mailto:" in (подвал.first.inner_html() if подвал.count() else ""),
        "ширина прокрутки": стр.evaluate("() => document.documentElement.scrollWidth"),
        # Обрезка имени сайта видна только измерением: `overflow:hidden`
        # молчит, а многоточие во флексе не показывается. Сравниваем, сколько
        # элементу НУЖНО, с тем, сколько ему дали.
        "логотип": стр.evaluate(
            "() => {const l=document.querySelector('.hd__logo');"
            "return l ? {text:l.innerText.trim(), need:l.scrollWidth, have:l.clientWidth,"
            " clipped:l.scrollWidth > l.clientWidth + 1} : null;}"),
        # Меню обрезается так же молча, как имя: ряд без переноса просто
        # уводит последние пункты за край.
        # «Не помещается» и «потеряно» — разные вещи: ряд с прокруткой не
        # теряет пунктов, их достают колесом и свайпом. Первая редакция
        # считала обрезкой любое превышение.
        "меню": стр.evaluate(
            "() => {const n=document.querySelector('.hd__nav');"
            "if(!n) return null;"
            "const ov=getComputedStyle(n).overflowX;"
            "const over=n.scrollWidth > n.clientWidth + 1;"
            "return {need:n.scrollWidth, have:n.clientWidth,"
            " overflowing:over, scrollable:(ov==='auto'||ov==='scroll'),"
            " lost: over && !(ov==='auto'||ov==='scroll'),"
            " links:n.querySelectorAll('a').length};}"),
        "подвал mailto": стр.evaluate(
            "() => !!document.querySelector('footer a[href^=\"mailto:\"]')"),
    }
    # Технические подписи и заглушки: ищем прямо в тексте страницы.
    текст = стр.locator("body").inner_text()
    маркеры = ["TODO", "FIXME", "PLACEHOLDER", "заглушка", "Lorem ipsum",
               "test data", "не реализовано", "{{", "}}", "None", "undefined"]
    итог["главная"]["техмаркеры"] = sorted(
        {м for м in маркеры if м.lower() in текст.lower()})


def осмотр_каталога(стр, база: str, итог: dict) -> None:
    """Каталог: фильтры и сортировка обязаны МЕНЯТЬ выдачу."""
    стр.goto(база + "/catalog/", wait_until="domcontentloaded")
    первый_состав = стр.evaluate(
        "() => Array.from(document.querySelectorAll(\"a[href^='/title/']\")).map(a => a.getAttribute('href')).slice(0, 12)")
    итог["каталог"] = {
        "title": стр.title(),
        "h1": (стр.locator("h1").first.inner_text().strip()
               if стр.locator("h1").count() else ""),
        "карточек": len(первый_состав),
        "ссылок жанров": стр.locator("a[href*='/genre'], a[href*='zhanr']").count(),
        "ссылок годов": стр.locator("a[href*='/year'], a[href*='god']").count(),
        "сортировка": стр.locator("a[href*='sort'], select[name='sort']").count(),
        "пагинация": стр.locator("a[href*='page'], a[href*='/page/']").count(),
    }

    def состав(адрес: str) -> list[str]:
        стр.goto(адрес, wait_until="domcontentloaded")
        return стр.evaluate(
            "() => Array.from(document.querySelectorAll(\"a[href^='/title/']\")).map(a => a.getAttribute('href')).slice(0, 12)")

    # Жанр: берём первую жанровую ссылку и сравниваем состав.
    стр.goto(база + "/catalog/", wait_until="domcontentloaded")
    жанр = стр.locator("a[href*='/genre'], a[href*='zhanr']").first
    if жанр.count():
        адрес = жанр.get_attribute("href") or ""
        состав_жанра = состав(база + адрес if адрес.startswith("/") else адрес)
        итог["каталог"]["жанр меняет выдачу"] = состав_жанра != первый_состав
        итог["каталог"]["жанр"] = адрес
        итог["каталог"]["карточек в жанре"] = len(состав_жанра)
    else:
        итог["каталог"]["жанр меняет выдачу"] = None

    # Год.
    стр.goto(база + "/catalog/", wait_until="domcontentloaded")
    год = стр.locator("a[href*='/year'], a[href*='god']").first
    if год.count():
        адрес = год.get_attribute("href") or ""
        состав_года = состав(база + адрес if адрес.startswith("/") else адрес)
        итог["каталог"]["год меняет выдачу"] = состав_года != первый_состав
        итог["каталог"]["год"] = адрес
    else:
        итог["каталог"]["год меняет выдачу"] = None

    # Сортировка — ДЕЙСТВИЕМ: поле `select[name=sort]` отправляет форму при
    # изменении. Проверка по ссылкам `sort=` нашла бы ноль и объявила бы, что
    # сортировки нет.
    стр.goto(база + "/catalog/", wait_until="domcontentloaded")
    поле = стр.locator("select[name='sort']")
    if поле.count():
        варианты = стр.evaluate(
            "() => Array.from(document.querySelectorAll(\"select[name='sort'] option\"))"
            ".map(o => o.value)")
        текущий = стр.evaluate(
            "() => (document.querySelector(\"select[name='sort']\") || {}).value || ''")
        другой = next((в for в in варианты if в and в != текущий), "")
        итог["каталог"]["варианты сортировки"] = варианты
        if другой:
            # Выбор варианта отправляет форму, то есть УВОДИТ страницу. Без
            # ожидания перехода следующий вызов попадает в уничтоженный
            # контекст — ровно это и случилось в первой редакции:
            # «Execution context was destroyed, most likely because of a
            # navigation».
            with стр.expect_navigation(wait_until="domcontentloaded",
                                       timeout=90000):
                поле.first.select_option(другой)
            порядок = стр.evaluate(
                "() => Array.from(document.querySelectorAll(\"a[href^='/title/']\"))"
                ".map(a => a.getAttribute('href')).slice(0, 12)")
            итог["каталог"]["сортировка меняет порядок"] = порядок != первый_состав
            итог["каталог"]["сортировка применена"] = другой
            итог["каталог"]["адрес после сортировки"] = стр.url.replace(база, "")
        else:
            итог["каталог"]["сортировка меняет порядок"] = None
    else:
        итог["каталог"]["варианты сортировки"] = []
        итог["каталог"]["сортировка меняет порядок"] = None

    # Пагинация: адрес берётся СО СТРАНИЦЫ. Первая редакция подставляла
    # `/catalog/page/2/` от себя, получала 404 и записывала его витрине в
    # дефекты — проверка выдумала требование вместо того, чтобы прочитать
    # ссылку.
    стр.goto(база + "/catalog/", wait_until="domcontentloaded")
    # Шаблон — ТОЛЬКО адрес с номером страницы. Прежний искал «page|стр|след»
    # по склейке href и текста и на сериальном каталоге выбрал ссылку
    # произведения: проверка пагинации сравнивала каталог с карточкой фильма и
    # разницу считала успехом.
    следующая = стр.evaluate(
        "() => {const a=Array.from(document.querySelectorAll('a[href]'))"
        ".map(x => x.getAttribute('href') || '')"
        ".find(h => /\\/page\\/\\d|[?&]page=\\d/.test(h));"
        "return a || '';}")
    итог["каталог"]["ссылка следующей"] = следующая
    if следующая:
        состав_второй = состав(база + следующая if следующая.startswith("/") else следующая)
        итог["каталог"]["вторая страница отличается"] = (
            bool(состав_второй) and состав_второй != первый_состав)
        итог["каталог"]["карточек на второй"] = len(состав_второй)
    else:
        итог["каталог"]["вторая страница отличается"] = None
        итог["каталог"]["карточек на второй"] = None


def осмотр_карточки(стр, база: str, данные: Path, site: str, итог: dict) -> None:
    каталог = json.loads((данные / f"{site}-catalog.json").read_text(encoding="utf-8"))
    элементы = каталог.get("items") or []
    # Берём произведение с сезонами, если такое есть: сериальная поверхность
    # проверяется только на нём.
    # Вид в снимке каталога записан по-русски («Фильм», «Сериал»,
    # «Мультфильм»). Прежний отбор по английским значениям давал сериал None на
    # всех пяти сериальных витринах — сезоны и серии не проверялись ни разу, а
    # фильм брался первым попавшимся элементом.
    СЕРИАЛЬНЫЕ = ("Сериал", "series", "tv", "serial")
    ФИЛЬМОВЫЕ = ("Фильм", "Мультфильм", "movie", "film")

    def вид(э):
        return str(э.get("kind") or э.get("type") or "")

    сериал = next((э for э in элементы if вид(э) in СЕРИАЛЬНЫЕ), None)
    фильм = next((э for э in элементы if вид(э) in ФИЛЬМОВЫЕ),
                 элементы[0] if элементы else None)
    итог["карточка"] = {}
    for имя, элемент in (("фильм", фильм), ("сериал", сериал)):
        if not элемент:
            итог["карточка"][имя] = None
            continue
        слаг = элемент.get("slug") or элемент.get("id")
        стр.goto(f"{база}/title/{слаг}/", wait_until="domcontentloaded")
        текст = стр.locator("body").inner_text()
        название = элемент.get("title") or элемент.get("name") or ""
        итог["карточка"][имя] = {
            "слаг": слаг,
            "title страницы": стр.title(),
            "название в тексте": bool(название) and название in текст,
            "постер": стр.locator("img[src*='poster'], .poster img, img").count() > 0,
            "описание": len(текст) > 400,
            "похожее": стр.locator("a[href^='/title/']").count(),
            "сезоны": стр.locator("a[href*='season'], [class*='season']").count(),
            "серии": стр.locator("a[href*='episode'], [class*='episode']").count(),
            # Признак рамки — атрибут `data-player`, а не слово «player» в
            # классе: классы здесь `pl`/`pl__frame`, и прежний селектор давал
            # ноль на каждой карточке.
            "плеер": стр.locator("[data-player], iframe").count(),
            "состояние плеера": стр.evaluate(
                "() => {const n=document.querySelector('[data-player]');"
                "return n ? (n.getAttribute('data-state') || '') : null;}"),
            "сюжет из источника": стр.locator(".plot p:not(.none)").count() > 0,
            "canonical": стр.evaluate(
                "() => (document.querySelector(\"link[rel='canonical']\") || {}).href || ''"),
            "description": стр.evaluate(
                "() => (document.querySelector(\"meta[name='description']\") || {}).content || ''"),
        }


def осмотр_навигации(стр, база: str, итог: dict) -> None:
    стр.goto(база + "/", wait_until="domcontentloaded")
    ссылки = стр.evaluate(
        "() => Array.from(document.querySelectorAll('header a, nav a, footer a'))"
        ".map(a => a.getAttribute('href')).filter(h => h && h.startsWith('/'))")
    ссылки = sorted(set(ссылки))[:25]
    плохие = []
    for адрес in ссылки:
        ответ = стр.request.get(база + адрес)
        if ответ.status >= 400:
            плохие.append({"href": адрес, "code": ответ.status})
    итог["навигация"] = {
        "проверено ссылок": len(ссылки),
        "битых": плохие,
        "404 отдаёт 404": стр.request.get(база + "/нет-такой-страницы-12345/").status,
        "пустой поиск": стр.request.get(база + "/search/?q=zzzqqqxyz123").status,
    }
    # Поиск действием: ввести и получить результаты.
    стр.goto(база + "/", wait_until="domcontentloaded")
    поле = стр.locator("input[type='search'], input[name='q']").first
    if поле.count():
        поле.fill("ветер")
        поле.press("Enter")
        стр.wait_for_load_state("domcontentloaded")
        итог["навигация"]["поиск действием"] = {
            "адрес": стр.url.replace(база, ""),
            "найдено карточек": стр.locator("a[href^='/title/']").count(),
        }
    else:
        итог["навигация"]["поиск действием"] = None


def осмотр_телефона(браузер, база: str, снимки: Path, site: str, итог: dict) -> None:
    контекст = браузер.new_context(viewport=ТЕЛЕФОН, is_mobile=True,
                                  has_touch=True, device_scale_factor=2)
    стр = контекст.new_page()
    стр.goto(база + "/", wait_until="domcontentloaded")
    прокрутка = стр.evaluate(
        "() => ({scroll: document.documentElement.scrollWidth, view: window.innerWidth})")
    бургер = стр.locator("[class*='burger'], [class*='menu-toggle'], button[aria-label*='меню'], "
                         "button[aria-expanded]")
    меню_открылось = None
    if бургер.count():
        было = стр.locator("nav a, header a").count()
        try:
            бургер.first.click(timeout=3000)
            стр.wait_for_timeout(400)
            меню_открылось = стр.locator("nav a, header a").count() >= было
        except Exception:  # noqa: BLE001
            меню_открылось = False
    # Имя сайта режется и на телефоне — там ряд ещё теснее. Измеряем, а не
    # смотрим: на снимке это заметно только если знать, как имя пишется.
    итог.setdefault("телефон", {})["логотип"] = стр.evaluate(
        "() => {const l=document.querySelector('.hd__logo');"
        "return l ? {text:l.innerText.trim(), need:l.scrollWidth, have:l.clientWidth,"
        " clipped:l.scrollWidth > l.clientWidth + 1} : null;}")
    итог["телефон"]["незагруженных изображений перед снимком"] = (
        дождаться_картинок(стр))
    стр.screenshot(path=str(снимки / f"{site}-phone-home.png"), full_page=False)
    стр.goto(база + "/catalog/", wait_until="domcontentloaded")
    прокрутка_каталога = стр.evaluate(
        "() => ({scroll: document.documentElement.scrollWidth, view: window.innerWidth})")
    дождаться_картинок(стр)
    стр.screenshot(path=str(снимки / f"{site}-phone-catalog.png"), full_page=False)
    итог["телефон"].update({
        "видимая ширина": прокрутка["view"],
        "ширина документа": прокрутка["scroll"],
        "горизонтальная прокрутка главной": прокрутка["scroll"] > прокрутка["view"] + 1,
        "горизонтальная прокрутка каталога":
            прокрутка_каталога["scroll"] > прокрутка_каталога["view"] + 1,
        "кнопка меню": бургер.count() > 0,
        "меню открывается": меню_открылось,
    })
    контекст.close()


def main() -> int:
    р = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--site", required=True)
    р.add_argument("--data", required=True)
    р.add_argument("--project", default=None)
    р.add_argument("--port", type=int, default=19300)
    р.add_argument("--out", default=None, help="куда класть снимки и отчёт")
    а = р.parse_args()

    проект = Path(а.project or (КОРЕНЬ / "var" / "new-sites" / а.site))
    конфиг = json.loads((проект / "config" / "site.json").read_text(encoding="utf-8"))
    выход = Path(а.out or (КОРЕНЬ / "var" / "k2-data" / "audit" / а.site))
    выход.mkdir(parents=True, exist_ok=True)

    врем = Path(tempfile.mkdtemp(prefix=f"audit-{а.site}-"))
    данные = врем / "data"
    данные.mkdir()
    for ф in Path(а.data).glob(f"{а.site}-*.json"):
        shutil.copy(ф, данные / ф.name)

    доступно = 0
    for строка in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
        if строка.startswith("MemAvailable:"):
            доступно = int(строка.split()[1]) // 1024
    print(f"{а.site}: стенд {врем}, доступно памяти {доступно} МиБ")

    процесс, готово = поднять(проект, конфиг, данные, а.port)
    if not готово:
        вывод = (процесс.stdout.read() if процесс.stdout else b"").decode("utf-8", "replace")
        (выход / "runtime-fail.log").write_text(вывод, encoding="utf-8")
        print("ОТКАЗ: рантайм не поднялся; журнал в", выход / "runtime-fail.log")
        процесс.kill()
        shutil.rmtree(врем, ignore_errors=True)
        return 1

    база = f"http://127.0.0.1:{а.port}"
    # Происхождение осмотра: снимки без коммита — картинки без адреса.
    # Запись делается ДО измерений, чтобы в отчёте стоял тот коммит, который
    # измерялся, а не тот, что оказался в репозитории потом.
    _вг = ["git", "-C", str(проект)]
    коммит = subprocess.run(_вг + ["rev-parse", "--short=12", "HEAD"],
                            capture_output=True, text=True).stdout.strip()
    грязно = subprocess.run(_вг + ["status", "--porcelain"],
                            capture_output=True, text=True).stdout.strip()
    итог: dict = {"site": а.site, "domain": конфиг.get("domain"),
                  "profile": (конфиг.get("template") or {}).get("template_id"),
                  "коммит": коммит,
                  "незакоммиченных файлов": len(грязно.splitlines())}
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            пуск: dict = {}
            if ГОТОВЫЙ_CHROMIUM.is_file():
                пуск["executable_path"] = str(ГОТОВЫЙ_CHROMIUM)
                print(f"браузер: {ГОТОВЫЙ_CHROMIUM}")
            else:
                print("браузер: сборка playwright по умолчанию")
            браузер = pw.chromium.launch(**пуск)
            контекст = браузер.new_context(viewport=КОМПЬЮТЕР)
            стр = контекст.new_page()
            осмотр(стр, база, итог)
            итог["главная"]["незагруженных изображений перед снимком"] = (
                дождаться_картинок(стр))
            стр.screenshot(path=str(выход / f"{а.site}-desktop-home.png"))
            осмотр_каталога(стр, база, итог)
            итог["каталог"]["незагруженных изображений перед снимком"] = (
                дождаться_картинок(стр))
            стр.screenshot(path=str(выход / f"{а.site}-desktop-catalog.png"))
            осмотр_карточки(стр, база, данные, а.site, итог)
            дождаться_картинок(стр)
            стр.screenshot(path=str(выход / f"{а.site}-desktop-title.png"))
            осмотр_навигации(стр, база, итог)
            контекст.close()
            осмотр_телефона(браузер, база, выход, а.site, итог)
            браузер.close()
    finally:
        процесс.send_signal(signal.SIGTERM)
        try:
            процесс.wait(timeout=15)
        except subprocess.TimeoutExpired:
            процесс.kill()
        shutil.rmtree(врем, ignore_errors=True)

    (выход / "audit.json").write_text(
        json.dumps(итог, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    print(json.dumps(итог, ensure_ascii=False, indent=2)[:3000])
    print(f"\nснимки и отчёт: {выход}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
