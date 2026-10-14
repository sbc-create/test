#!/usr/bin/env python3
"""Страница предпросмотра: снимки экрана и измерения по каждой витрине партии.

Зачем. Живого предпросмотра по домену нет и быть пока не может: DNS указывает на
прежний узел, а служба без publisher_id не стартует. Но посмотреть, КАК витрина
выглядит и что на ней измерено, нужно уже сейчас — иначе «готово» приходится
принимать на слово.

Страница собирается ТОЛЬКО из того, что измерено: `audit.json` каждой витрины и
её снимки экрана. Ничего не додумывается: если осмотр не проводился, так и
написано. Это НЕ живой сайт, и страница говорит об этом прямо.
"""
from __future__ import annotations

import html
import json
import shutil
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
ОСМОТРЫ = КОРЕНЬ / "var" / "k2-data" / "audit"
ВЫХОД = КОРЕНЬ / "var" / "k2-data" / "preview"
ВОСЕМЬ = [f"lords-{n}" for n in range(10, 18)]
СНИМКИ = [("desktop-home", "Главная, компьютер 1366×768"),
          ("desktop-catalog", "Каталог, компьютер"),
          ("desktop-title", "Карточка, компьютер"),
          ("phone-home", "Главная, телефон 390×844"),
          ("phone-catalog", "Каталог, телефон")]


def да_нет(значение) -> str:
    if значение is True:
        return '<span class="ok">да</span>'
    if значение is False:
        return '<span class="no">нет</span>'
    return '<span class="na">не измерено</span>'


def карточка(site: str) -> str:
    файл = ОСМОТРЫ / site / "audit.json"
    снимки_каталог = ВЫХОД / "shots"
    if not файл.is_file():
        return (f'<section class="site"><h2>{html.escape(site)}</h2>'
                '<p class="na">осмотр не проводился</p></section>')
    д = json.loads(файл.read_text(encoding="utf-8"))
    гл, кат = д.get("главная", {}), д.get("каталог", {})
    тел, нав = д.get("телефон", {}), д.get("навигация", {})
    карта = д.get("карточка", {}) or {}
    фильм = карта.get("фильм") or {}
    сериал = карта.get("сериал") or {}
    лого, меню = гл.get("логотип") or {}, гл.get("меню") or {}
    тлого = тел.get("логотип") or {}

    картинки = []
    for ключ, подпись in СНИМКИ:
        источник = ОСМОТРЫ / site / f"{site}-{ключ}.png"
        if not источник.is_file():
            continue
        снимки_каталог.mkdir(parents=True, exist_ok=True)
        shutil.copy(источник, снимки_каталог / источник.name)
        картинки.append(
            f'<figure><img loading="lazy" src="shots/{источник.name}" '
            f'alt="{html.escape(подпись)}"><figcaption>{html.escape(подпись)}'
            f'</figcaption></figure>')

    порядок = {}
    файл_полок = ОСМОТРЫ / site / "shelf-order.json"
    if файл_полок.is_file():
        порядок = json.loads(файл_полок.read_text(encoding="utf-8"))
    серия = {}
    файл_серий = ОСМОТРЫ / site / "serial.json"
    if файл_серий.is_file():
        серия = (json.loads(файл_серий.read_text(encoding="utf-8"))
                 .get("сериал") or {})

    строки = [
        ("домен", html.escape(str(д.get("domain") or ""))),
        ("профиль", html.escape(str(д.get("profile") or ""))),
        ("коммит ячейки, с которого снимки",
         html.escape(str(д.get("коммит") or "не записан"))),
        ("незакоммиченных файлов при осмотре",
         str(д.get("незакоммиченных файлов", "—"))),
        ("имя в шапке целиком", да_нет(not лого.get("clipped") if лого else None)),
        ("имя в шапке на телефоне целиком",
         да_нет(not тлого.get("clipped") if тлого else None)),
        ("меню без потерь", да_нет(not меню.get("lost") if меню else None)),
        ("обратная связь в подвале", да_нет(гл.get("подвал mailto"))),
        ("битых изображений", str(гл.get("битых изображений", "—"))),
        ("карточек в каталоге", str(кат.get("карточек", "—"))),
        ("жанр меняет выдачу", да_нет(кат.get("жанр меняет выдачу"))),
        ("год меняет выдачу", да_нет(кат.get("год меняет выдачу"))),
        ("сортировка меняет порядок", да_нет(кат.get("сортировка меняет порядок"))),
        ("битых ссылок в шапке и подвале",
         str(len(нав.get("битых") or [])) if нав else "—"),
        ("404 отдаёт 404", да_нет(нав.get("404 отдаёт 404") == 404 if нав else None)),
        ("поиск действием нашёл",
         str((нав.get("поиск действием") or {}).get("найдено карточек", "—"))
         if нав else "—"),
        ("вторая страница каталога отличается",
         да_нет(кат.get("вторая страница отличается"))),
        ("адрес второй страницы",
         html.escape(str(кат.get("ссылка следующей") or "—"))),
        ("название произведения в карточке", да_нет(фильм.get("название в тексте"))),
        ("сюжет из источника в карточке фильма",
         да_нет(фильм.get("сюжет из источника"))),
        ("похожее в карточке фильма", str(фильм.get("похожее", "—"))),
        # Сериальная поверхность: на фильмовой витрине сериал в каталоге тоже
        # есть, поэтому строка осмысленна для всех восьми.
        ("сезонов в карточке сериала", str(сериал.get("сезоны", "—"))),
        ("серий в карточке сериала", str(сериал.get("серии", "—"))),
        # `noaccess` — ожидаемое состояние без номера издателя: рамка на месте
        # и ждёт только номер. Пустая строка означала бы, что рамки нет.
        # Полки главной без publisher_id пусты, поэтому их порядок проверен
        # измерением разметки (`home-shelf-order-check.py`), а не снимком.
        ("полки главной", html.escape(" → ".join(порядок.get("полки") or []))
         or "не измерено"),
        ("своя полка первой", да_нет(порядок.get("своя полка первой"))),
        ("серий открывается действием",
         да_нет((серия.get("переход по серии") or {}).get("адрес совпал с ссылкой"))),
        ("серия помечена текущей",
         да_нет((серия.get("переход по серии") or {}).get("помечена текущей"))),
        ("сезоны и серии сходятся с данными",
         да_нет(bool(серия.get("сезонов сходится")) and bool(серия.get("серий сходится")))),
        ("состояние плеера",
         html.escape(str(фильм.get("состояние плеера") or "не измерено"))),
        ("горизонтальная прокрутка на телефоне",
         да_нет(not тел.get("горизонтальная прокрутка главной")
                if тел else None)),
        ("меню на телефоне открывается", да_нет(тел.get("меню открывается"))),
    ]
    таблица = "".join(f"<tr><td>{к}</td><td>{з}</td></tr>" for к, з in строки)
    return (f'<section class="site" id="{html.escape(site)}">'
            f'<h2>{html.escape(site)} — {html.escape(str(д.get("domain") or ""))}</h2>'
            f'<table>{таблица}</table>'
            f'<div class="shots">{"".join(картинки)}</div></section>')


def main() -> int:
    ВЫХОД.mkdir(parents=True, exist_ok=True)
    карточки = "".join(карточка(с) for с in ВОСЕМЬ)
    страница = f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Партия K2</title>
<style>
:root{{--bg:#0f1115;--card:#171a21;--line:#262b36;--tx:#e8eaf0;--dim:#9aa3b2;
--ok:#5cb85c;--no:#d9534f;--na:#8a94a6;color-scheme:dark}}
@media (prefers-color-scheme: light){{:root:not([data-theme="dark"]){{
--bg:#f6f7fa;--card:#fff;--line:#e3e6ee;--tx:#14171f;--dim:#5b6470;color-scheme:light}}}}
*{{box-sizing:border-box}}
body{{margin:0;padding:24px 16px 64px;background:var(--bg);color:var(--tx);
font:15px/1.55 -apple-system,Segoe UI,Roboto,Arial,sans-serif;max-width:1100px;margin-inline:auto}}
h1{{font-size:26px;margin:0 0 6px}} h2{{font-size:19px;margin:0 0 12px}}
.note{{color:var(--dim);margin:0 0 28px}}
.site{{background:var(--card);border:1px solid var(--line);border-radius:10px;
padding:18px;margin:0 0 22px}}
table{{border-collapse:collapse;width:100%;margin:0 0 16px}}
td{{padding:5px 8px;border-bottom:1px solid var(--line);font-size:14px}}
td:first-child{{color:var(--dim);width:60%}}
.ok{{color:var(--ok)}} .no{{color:var(--no)}} .na{{color:var(--na)}}
.shots{{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:14px}}
figure{{margin:0}} img{{width:100%;border:1px solid var(--line);border-radius:6px;display:block}}
figcaption{{color:var(--dim);font-size:12.5px;padding-top:5px}}
</style></head><body>
<h1>Партия K2: восемь витрин</h1>
<p class="note">Снимки и измерения с изолированного стенда. <b>Это не живой
сайт</b>: домены ещё указывают на прежний узел, а служба не запускается без
publisher_id — поэтому пустая главная здесь ожидаема, полки наполняются только
после появления номера. Режим индексации у всех витрин закрытый.</p>
{карточки}
</body></html>
"""
    (ВЫХОД / "index.html").write_text(страница, encoding="utf-8")
    снимков = len(list((ВЫХОД / "shots").glob("*.png"))) if (ВЫХОД / "shots").is_dir() else 0
    print(f"страница: {ВЫХОД / 'index.html'}; снимков {снимков}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
