#!/usr/bin/env python3
"""Каталог для визуальной приёмки владельцем.

## Почему не «папка с шестьюстами файлов»

Шестьсот снимков в файловой системе — это не материал для приёмки, а материал
для её откладывания. Владельцу нужно за один заход увидеть все пятьдесят,
сравнить внутри семьи, посмотреть внутренние страницы и открыть любой снимок в
полный размер. Поэтому каталог состоит из пяти частей:

* **указатель** — все пятьдесят подряд: рабочий стол и мобильный рядом,
  дизайн-ДНК, стратегия маршрутов, ближайший визуальный сосед, результаты
  ворот и пустое поле решения владельца;
* **десять листов семьи** — пять шаблонов одной семьи бок о бок, в одном
  масштабе и на одной странице: только так видно, что внутри семьи они
  действительно разные;
* **лист маршрутов** у каждого шаблона — главная, каталог, тайтл, серия,
  поиск и 404 подряд: шаблон, проверенный только по главной, не проверен;
* **сводный лист** — все пятьдесят сеткой;
* **лист отбора** — десять кандидатов на шести ширинах и с внутренними
  страницами.

Миниатюры намеренно крупные: по картинке в сто пикселей нельзя судить об
интерфейсе, а приёмка по такой картинке была бы приёмкой вслепую.

## Чего каталог не делает

Он не проставляет приёмку. Поле решения пустое, и заполняет его владелец.
Технический балл показан рядом и назван техническим.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import html
import json
import pathlib
import re

СЕМЕЙСТВА = {
    "forest-cinema": "Лесное кино",
    "series-feed": "Лента сериалов",
    "curated": "Редакционные",
    "premiere": "Календарные",
    "genre": "Навигация",
    "rating": "Порядок",
    "collection": "Мозаика и срезы",
    "archive": "Архив",
    "modern": "Современные",
    "hybrid": "Гибриды",
}

ПОДПИСИ_МАРШРУТОВ = {
    "home": "Главная", "catalog": "Каталог", "catalog-p2": "Каталог, стр. 2",
    "new": "Новинки", "search": "Поиск", "search-empty": "Пустой поиск",
    "genre": "Жанр", "year": "Год", "country": "Страна", "collection": "Подборка",
    "title-movie": "Фильм", "title-series": "Сериал", "season": "Сезон",
    "episode": "Серия с плеером", "notfound": "404",
    "edge-long-title": "Длинный заголовок", "edge-no-poster": "Без постера",
    "edge-no-description": "Без описания", "edge-long-description": "Длинное описание",
}

СТРАТЕГИИ = {
    "grid": "витрина", "rows": "перечень строк", "mosaic": "мозаика",
    "board": "доска по видам", "index": "азбука и таблица", "split": "разворот",
    "magazine": "журнальная полоса",
    "poster-aside": "постер сбоку", "hero-wide": "крупный заголовок",
    "editorial": "описание первым", "panel": "панель фактов",
    "data-first": "факты первыми",
    "chips": "жанровые фишки", "rail": "полоса", "filters": "фильтры",
    "similar": "в похожем", "discovery": "в разведке", "none": "не используется",
}

СТИЛЬ = """
:root{--ink:#e8efe6;--dim:#9fb3a3;--bg:#0c1210;--card:#121a16;--line:#223029;
--brand:#3F7D26;--mint:#8ED6B0;--warn:#E4B363}
*,*::before,*::after{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font:400 15px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
a{color:var(--mint)}
.wrap{max-width:1680px;margin:0 auto;padding:24px 20px 64px}
h1{font-size:26px;margin:0 0 6px}
h2{font-size:19px;margin:36px 0 12px;padding-bottom:8px;border-bottom:1px solid var(--line)}
h3{font-size:16px;margin:24px 0 10px}
.lead{color:var(--dim);max-width:82ch;margin:0 0 20px}
.nav{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 24px}
.nav a{display:inline-flex;align-items:center;min-height:44px;padding:0 14px;
border:1px solid var(--line);border-radius:999px;background:var(--card);text-decoration:none}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;
padding:16px;margin:0 0 20px}
.head{display:flex;flex-wrap:wrap;gap:10px;align-items:baseline;margin:0 0 10px}
.tid{font-weight:800;font-size:18px;color:var(--mint);font-variant-numeric:tabular-nums}
.name{font-weight:700}
.fam{color:var(--dim);font-size:13px}
.shots{display:grid;gap:14px;grid-template-columns:minmax(0,1fr)}
@media(min-width:900px){.shots{grid-template-columns:minmax(0,3fr) minmax(0,1fr)}}
.shots img{width:100%;height:auto;display:block;border:1px solid var(--line);border-radius:8px}
.meta{display:grid;gap:10px;margin:14px 0 0}
@media(min-width:760px){.meta{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(min-width:1200px){.meta{grid-template-columns:repeat(3,minmax(0,1fr))}}
.k{color:var(--dim);font-size:13px;text-transform:uppercase;letter-spacing:.06em;margin:0 0 2px}
.v{margin:0}
.badge{display:inline-block;padding:3px 10px;border-radius:999px;font-size:12px;
border:1px solid var(--line);background:#0f1713;margin:0 4px 4px 0}
.ok{color:var(--mint)}
.bad{color:var(--warn);border-color:var(--warn)}
.decide{margin-top:14px;padding:12px;border:1px dashed var(--line);border-radius:8px;
color:var(--dim)}
.grid50{display:grid;gap:14px;grid-template-columns:repeat(2,minmax(0,1fr))}
@media(min-width:900px){.grid50{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media(min-width:1400px){.grid50{grid-template-columns:repeat(4,minmax(0,1fr))}}
.cell{background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden}
.cell img{width:100%;height:auto;display:block}
.cell .cap{padding:8px 10px;font-size:13px}
.row5{display:grid;gap:12px;grid-template-columns:minmax(0,1fr)}
@media(min-width:760px){.row5{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(min-width:1300px){.row5{grid-template-columns:repeat(5,minmax(0,1fr))}}
.routes{display:grid;gap:12px;grid-template-columns:repeat(auto-fill,minmax(230px,1fr))}
table{border-collapse:collapse;width:100%;font-size:14px}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--dim);font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.05em}
footer{margin-top:40px;color:var(--dim);border-top:1px solid var(--line);padding-top:16px}
"""


def э(з) -> str:
    return html.escape("" if з is None else str(з), quote=True)


def днк(манифест: dict, паспорт: dict, токены: str) -> dict:
    """Короткая дизайн-ДНК: чем этот шаблон отличается от прочих."""
    первый = манифест["home_block_order"][0]
    фон = re.search(r"--bg:\s*(#[0-9a-fA-F]{6})", токены)
    радиус = re.search(r"--radius:\s*(\d+)px", токены)
    тон = "светлая" if фон and int(фон.group(1)[1:3], 16) > 128 else "тёмная"
    плотность = паспорт["declared"].get("desktop_density_1440", 0)
    модель = манифест.get("route_model") or {}
    return {
        "открывает": f"{первый['тип']} · {первый.get('грамматика', 'без карточек')}",
        "состав": " → ".join(паспорт["declared"]["home_signature"]),
        "грамматика": ", ".join(манифест["card_grammar"]),
        "палитра": f"{тон}, фон {фон.group(1) if фон else '—'}, "
                   f"радиус {радиус.group(1) if радиус else '—'}px",
        "зелёный": манифест["green_identity"],
        "плотность": f"до {плотность} колонок на 1440",
        "каталог": СТРАТЕГИИ.get(модель.get("catalog"), "—"),
        "тайтл": СТРАТЕГИИ.get(модель.get("title"), "—"),
        "разведка": СТРАТЕГИИ.get(модель.get("discovery"), "—"),
        "полоса": СТРАТЕГИИ.get(модель.get("rail"), "—"),
    }


def собрать_данные(корень: pathlib.Path, оценки: pathlib.Path, снимки: pathlib.Path,
                   отпечатки: dict) -> list[dict]:
    соседи = отпечатки.get("nearest") or {}
    записи = []
    for пакет in sorted(корень.glob("T0*")):
        if not (пакет / "template.json").is_file():
            continue
        манифест = json.loads((пакет / "template.json").read_text(encoding="utf-8"))
        паспорт = json.loads((пакет / "PASSPORT.json").read_text(encoding="utf-8"))
        токены = (пакет / "tokens.css").read_text(encoding="utf-8")
        tid = манифест["template_id"]
        оценка = {}
        файл = оценки / f"{tid}.json"
        if файл.is_file():
            оценка = json.loads(файл.read_text(encoding="utf-8"))
        кадры = sorted(п.name for п in (снимки / tid).glob("*.png")) \
            if (снимки / tid).is_dir() else []
        измерено = оценка.get("measured", {})
        записи.append({
            "tid": tid, "slug": манифест["slug"], "name": манифест["title"],
            "family": манифест["family"], "version": манифест["version"],
            "intent": манифест["design_intent"],
            "journey": манифест["primary_user_journey"],
            "днк": днк(манифест, паспорт, токены),
            "score": оценка.get("TOTAL_SCORE", паспорт["measured"]["visual_score"]),
            "hard_fails": оценка.get("hard_fails", {}),
            "routes": измерено.get("ROUTES_MEASURED", 0),
            "measurements": измерено.get("PAGE_MEASUREMENTS", 0),
            "interactions": измерено.get("INTERACTION_CHECKS", 0),
            "interaction_failures": измерено.get("INTERACTION_FAILURES", 0),
            "contrast": измерено.get("LOW_CONTRAST_COUNT", 0),
            "targets": измерено.get("SMALL_TOUCH_TARGET_COUNT", 0),
            "dead": измерено.get("DEAD_CONTROL_COUNT", 0),
            "digest": паспорт["package_digest"][:12],
            "neighbour": соседи.get(tid, {}),
            "frames": кадры,
        })
    return записи


def _имя_кадра(запись: dict, маршрут: str, ширина: int) -> str | None:
    имя = f"{маршрут}-{ширина}.png"
    return имя if имя in запись["frames"] else None


def _ссылка(запись: dict, путь: str, маршрут: str, ширина: int, alt: str) -> str:
    имя = _имя_кадра(запись, маршрут, ширина)
    if not имя:
        return ""
    адрес = f"{путь}/{запись['tid']}/screenshots/{имя[:-4]}.jpg"
    return (f"<a href='{э(адрес)}'><img loading=lazy src='{э(адрес)}' "
            f"alt='{э(alt)}'></a>")


def _ячейка(содержимое: str, подпись: str) -> str:
    return f"<div class=cell>{содержимое}<div class=cap>{э(подпись)}</div></div>"


def страница(титул: str, тело: str, подвал: str) -> str:
    return (f"<!doctype html><html lang=ru><head><meta charset=utf-8>"
            f"<meta name=viewport content='width=device-width,initial-scale=1'>"
            f"<title>{э(титул)}</title><style>{СТИЛЬ}</style></head><body>"
            f"<div class=wrap>{тело}<footer>{подвал}</footer></div></body></html>")


def карточка_шаблона(з: dict, путь: str) -> str:
    д = з["днк"]
    большой = _ссылка(з, путь, "home", 1440, f"{з['tid']} — главная, 1440 px") \
        or "<p>снимка нет</p>"
    малый = _ссылка(з, путь, "home", 390, f"{з['tid']} — главная, 390 px")
    поля = [
        ("Замысел", з["intent"]), ("Путь пользователя", з["journey"]),
        ("Открывает", д["открывает"]), ("Состав главной", д["состав"]),
        ("Каталог", д["каталог"]), ("Страница тайтла", д["тайтл"]),
        ("Разведка", д["разведка"]), ("Полоса", д["полоса"]),
        ("Грамматика карточек", д["грамматика"]), ("Палитра", д["палитра"]),
        ("Роль зелёного", д["зелёный"]), ("Плотность", д["плотность"]),
    ]
    мета = "".join(f"<div><p class=k>{э(к)}</p><p class=v>{э(v)}</p></div>" for к, v in поля)
    сосед = з["neighbour"]
    рядом = (f"<span class=badge>ближайший сосед {э(сосед.get('neighbour'))} "
             f"на расстоянии {э(сосед.get('hamming'))}</span>" if сосед else "")
    отказы = "".join(f"<span class='badge bad'>{э(к)}: {э(v)}</span>"
                     for к, v in (з["hard_fails"] or {}).items())
    статус = (f"<span class='badge ok'>технический балл {э(з['score'])}/100</span>"
              f"<span class=badge>маршрутов измерено {э(з['routes'])}</span>"
              f"<span class=badge>измерений {э(з['measurements'])}</span>"
              f"<span class=badge>проверок действием {э(з['interactions'])}, "
              f"провалов {э(з['interaction_failures'])}</span>"
              f"<span class=badge>контраст ниже порога: {э(з['contrast'])}</span>"
              f"<span class=badge>целей мельче 44: {э(з['targets'])}</span>"
              f"{рядом}{отказы}")
    ссылки = " · ".join(
        f"<a href='{путь}/{э(з['tid'])}/screenshots/home-{ш}.jpg'>{ш}</a>"
        for ш in (320, 390, 768, 1024, 1440, 1920) if _имя_кадра(з, "home", ш))
    return (f"<article class=card id='{э(з['tid'])}'>"
            f"<div class=head><span class=tid>{э(з['tid'])}</span>"
            f"<span class=name>{э(з['name'])}</span>"
            f"<span class=fam>{э(СЕМЕЙСТВА.get(з['family'], з['family']))} · "
            f"{э(з['slug'])}</span></div>"
            f"<div class=shots><div>{большой}</div><div>{малый}</div></div>"
            f"<div class=meta>{мета}</div>"
            f"<p style='margin:12px 0 0'>{статус}</p>"
            f"<p class=fam>Ширины: {ссылки or '—'} · "
            f"<a href='routes-{э(з['tid'])}.html'>внутренние страницы</a></p>"
            f"<p class=decide>Решение владельца: __________ "
            f"(принять · доработать · отклонить). Статус до решения — "
            f"TECHNICAL_CANDIDATE.</p></article>")


def лист_маршрутов(з: dict, путь: str, подвал: str) -> str:
    ячейки = []
    for маршрут, подпись in ПОДПИСИ_МАРШРУТОВ.items():
        for ширина in (1440, 390):
            кадр = _ссылка(з, путь, маршрут, ширина, f"{з['tid']} — {подпись}")
            if кадр:
                ячейки.append(f"<div class=cell>{кадр}<div class=cap><b>{э(подпись)}</b> "
                              f"· {ширина} px</div></div>")
                break
    тело = (f"<h1>{э(з['tid'])} {э(з['name'])} — внутренние страницы</h1>"
            f"<p class=lead>{э(з['intent'])}</p>"
            f"<p class=nav><a href='index.html'>← Указатель</a>"
            f"<a href='index.html#{э(з['tid'])}'>Карточка шаблона</a></p>"
            f"<div class=routes>{''.join(ячейки)}</div>")
    return страница(f"{з['tid']} — маршруты", тело, подвал)


def таблица_охвата() -> str:
    строки = [
        ("Главная, каталог, пагинация, новинки, поиск, пустой поиск, жанр, год, "
         "страна, подборка, фильм, сериал, сезон, серия с плеером, 404, "
         "четыре краевых случая",
         "представление пакета", "измерено на 390 и 1440, опорные — на шести ширинах"),
        ("Маршрутизация, коды ответа, канонический адрес, индексация, выбор данных",
         "ядро витрины", "ROUTE_OWNED_BY_CORE: проверяется на живых доменах, не здесь"),
        ("Полоса, вкладки сезонов, фильтры, сортировка, поиск на странице, "
         "раскрытие описания, кнопка плеера, клавиатура",
         "пакет и общее ядро интерактивности", "проверено действием: нажатие, "
         "клавиатура, состояние до и после"),
        ("Настоящие названия, годы, жанры, страны, описания, постеры, сезоны, "
         "оценки с источником",
         "каталог витрины", "присоединено по ключу записи, ничего не досочинено"),
        ("Названия серий", "источник", "их нет ни у одной записи — страница серии "
         "обходится номером"),
        ("Длительность и дата премьеры", "источник",
         "в выборке отсутствуют у всех записей; блок не рисуется"),
        ("Публичный контур: TLS, заголовки, реальный домен", "инфраструктура",
         "вне периметра пакета и этой задачи"),
    ]
    тело = "".join(f"<tr><td>{э(ч)}</td><td>{э(к)}</td><td>{э(с)}</td></tr>"
                   for ч, к, с in строки)
    return (f"<table><thead><tr><th>Что</th><th>Чьё</th><th>Как проверено</th></tr>"
            f"</thead><tbody>{тело}</tbody></table>")


def построить(корень: pathlib.Path, оценки: pathlib.Path, снимки: pathlib.Path,
              отпечатки: dict, куда: pathlib.Path, отбор: list[str]) -> dict:
    записи = собрать_данные(корень, оценки, снимки, отпечатки)
    куда.mkdir(parents=True, exist_ok=True)
    метка = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
    подвал = (f"Каталог собран {э(метка)}. Технический балл — самооценка проверок "
              f"фабрики, а не приёмка. Все шаблоны в статусе TECHNICAL_CANDIDATE.")
    путь = "../templates"

    по_семьям: dict[str, list[dict]] = {}
    for з in записи:
        по_семьям.setdefault(з["family"], []).append(з)

    навигация = "".join(
        f"<a href='family-{э(сем)}.html'>{э(СЕМЕЙСТВА.get(сем, сем))} ({len(v)})</a>"
        for сем, v in по_семьям.items())
    всего_измерений = sum(з["measurements"] for з in записи)
    всего_действий = sum(з["interactions"] for з in записи)
    тело = (f"<h1>Lords T001–T050 — каталог для приёмки</h1>"
            f"<p class=lead>Пятьдесят шаблонных пакетов на настоящих данных каталога "
            f"витрины. У каждого показан рабочий стол на 1440 px и мобильный на 390 px, "
            f"дизайн-ДНК, стратегия внутренних страниц, ближайший визуальный сосед и "
            f"измеренное состояние. Всего измерений страниц: {всего_измерений}, "
            f"проверок действием: {всего_действий}. Поле решения пустое: приёмку "
            f"проставляет владелец.</p>"
            f"<p class=nav>{навигация}<a href='all.html'>Сводный лист (50)</a>"
            f"<a href='shortlist.html'>Отбор (10)</a></p>"
            f"<h2>Что проверено, что принадлежит ядру, что осталось</h2>"
            f"{таблица_охвата()}")
    for сем, список in по_семьям.items():
        тело += f"<h2 id='{э(сем)}'>{э(СЕМЕЙСТВА.get(сем, сем))}</h2>"
        тело += "".join(карточка_шаблона(з, путь) for з in список)
    (куда / "index.html").write_text(
        страница("Lords T001–T050 — каталог", тело, подвал), encoding="utf-8")

    for сем, список in по_семьям.items():
        ячейки = "".join(
            f"<div class=cell>{_ссылка(з, путь, 'home', 1440, з['tid'])}"
            f"<div class=cap><b>{э(з['tid'])}</b> {э(з['name'])}<br>"
            f"<span class=fam>каталог: {э(з['днк']['каталог'])} · "
            f"тайтл: {э(з['днк']['тайтл'])}</span></div></div>" for з in список)
        тело_семьи = (
            f"<h1>{э(СЕМЕЙСТВА.get(сем, сем))} — пять шаблонов рядом</h1>"
            f"<p class=lead>Один масштаб, одна ширина (1440 px), одна страница. Так "
            f"видно, различаются ли шаблоны внутри семьи на самом деле — и не только "
            f"на главной: под каждым указано, как устроены каталог и страница тайтла.</p>"
            f"<p class=nav><a href='index.html'>← Указатель</a>"
            f"<a href='all.html'>Сводный лист</a></p>"
            f"<div class=row5>{ячейки}</div>")
        (куда / f"family-{сем}.html").write_text(
            страница(f"Lords — {СЕМЕЙСТВА.get(сем, сем)}", тело_семьи, подвал),
            encoding="utf-8")

    ячейки = "".join(
        f"<div class=cell>{_ссылка(з, путь, 'home', 1440, з['tid'])}"
        f"<div class=cap><b>{э(з['tid'])}</b> {э(з['name'])}<br>"
        f"<span class=fam>{э(СЕМЕЙСТВА.get(з['family'], з['family']))} · "
        f"балл {э(з['score'])}</span></div></div>" for з in записи)
    тело_всех = (f"<h1>Все пятьдесят на одном листе</h1>"
                 f"<p class=lead>Снимок открывается в полный размер по щелчку. "
                 f"Миниатюры намеренно крупные: по картинке в сто пикселей об "
                 f"интерфейсе не судят.</p>"
                 f"<p class=nav><a href='index.html'>← Указатель</a></p>"
                 f"<div class=grid50>{ячейки}</div>")
    (куда / "all.html").write_text(страница("Lords — все пятьдесят", тело_всех, подвал),
                                   encoding="utf-8")

    for з in записи:
        (куда / f"routes-{з['tid']}.html").write_text(
            лист_маршрутов(з, путь, подвал), encoding="utf-8")

    выбранные = [з for з in записи if з["tid"] in отбор]
    части = []
    for з in выбранные:
        ширины = "".join(
            _ячейка(_ссылка(з, путь, "home", ш, f"{з['tid']} на {ш} px"), f"{ш} px")
            for ш in (320, 390, 768, 1024, 1440, 1920) if _имя_кадра(з, "home", ш))
        внутренние = "".join(
            _ячейка(_ссылка(з, путь, м, 1440, f"{з['tid']}: {п}"), п)
            for м, п in ПОДПИСИ_МАРШРУТОВ.items()
            if м in ("catalog", "title-series", "episode", "search-empty", "notfound")
            and _имя_кадра(з, м, 1440))
        части.append(
            f"<h2 id='{э(з['tid'])}'>{э(з['tid'])} {э(з['name'])} — "
            f"{э(СЕМЕЙСТВА.get(з['family'], з['family']))}</h2>"
            f"<p class=lead>{э(з['intent'])}</p>"
            f"<h3>Шесть ширин</h3><div class=routes>{ширины}</div>"
            f"<h3>Внутренние страницы</h3><div class=routes>{внутренние}</div>")
    тело_отбора = (f"<h1>Отбор: десять кандидатов</h1>"
                   f"<p class=lead>Десять технически сильнейших — по одному из каждой "
                   f"семьи. Это не одобрение: статус каждого остаётся "
                   f"TECHNICAL_CANDIDATE. Обоснование выбора — в SHORTLIST.md.</p>"
                   f"<p class=nav><a href='index.html'>← Указатель</a></p>"
                   + "".join(части))
    (куда / "shortlist.html").write_text(
        страница("Lords — отбор десяти", тело_отбора, подвал), encoding="utf-8")

    return {"templates": len(записи), "families": len(по_семьям),
            "index": str(куда / "index.html"),
            "shortlist": str(куда / "shortlist.html"),
            "route_sheets": len(записи),
            "all_sheet": str(куда / "all.html")}


def главное() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="factory/templates/lords")
    parser.add_argument("--scores", default="var/scores")
    parser.add_argument("--shots", default="var/shots")
    parser.add_argument("--fingerprints", default="var/review/FINGERPRINTS.json")
    parser.add_argument("--shortlist", default="")
    parser.add_argument("--out",
                        default="artifacts/evidence/lords-50-template-factory-01/review")
    args = parser.parse_args()
    отпечатки = {}
    if pathlib.Path(args.fingerprints).is_file():
        отпечатки = json.loads(pathlib.Path(args.fingerprints).read_text(encoding="utf-8"))
    отбор = [и.strip() for и in args.shortlist.split(",") if и.strip()]
    итог = построить(pathlib.Path(args.root), pathlib.Path(args.scores),
                     pathlib.Path(args.shots), отпечатки, pathlib.Path(args.out), отбор)
    print(json.dumps(итог, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(главное())
