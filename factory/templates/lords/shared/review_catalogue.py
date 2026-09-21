#!/usr/bin/env python3
"""Каталог для визуальной приёмки владельцем.

## Почему не «папка с тремястами файлов»

Триста снимков в файловой системе — это не материал для приёмки, а материал
для её откладывания. Владельцу нужно за один заход увидеть все пятьдесят,
сравнить внутри семьи и открыть любой в полный размер. Поэтому каталог
состоит из трёх частей:

* **указатель** — все пятьдесят подряд: снимок рабочего стола и мобильный
  рядом, дизайн-ДНК, чем отличается, измеренное состояние и пустое поле
  решения владельца;
* **десять листов семьи** — пять шаблонов одной семьи бок о бок, в одном
  масштабе, на одной ширине и на одной странице: только так видно, что внутри
  семьи они действительно разные;
* **сводный лист** — все пятьдесят сеткой, каждый открывается в полный размер.

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

СТИЛЬ = """
:root{--ink:#e8efe6;--dim:#9fb3a3;--bg:#0c1210;--card:#121a16;--line:#223029;
--brand:#3F7D26;--mint:#8ED6B0}
*,*::before,*::after{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font:400 15px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
a{color:var(--mint)}
.wrap{max-width:1680px;margin:0 auto;padding:24px 20px 64px}
h1{font-size:26px;margin:0 0 6px}
h2{font-size:19px;margin:36px 0 12px;padding-bottom:8px;border-bottom:1px solid var(--line)}
.lead{color:var(--dim);max-width:78ch;margin:0 0 20px}
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
.k{color:var(--dim);font-size:13px;text-transform:uppercase;letter-spacing:.06em;margin:0 0 2px}
.v{margin:0}
.badge{display:inline-block;padding:3px 10px;border-radius:999px;font-size:12px;
border:1px solid var(--line);background:#0f1713}
.ok{color:var(--mint)}
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
    return {
        "открывает": f"{первый['тип']} · {первый.get('грамматика', 'без карточек')}",
        "состав": " → ".join(паспорт["declared"]["home_signature"]),
        "грамматика": ", ".join(манифест["card_grammar"]),
        "палитра": f"{тон}, фон {фон.group(1) if фон else '—'}, радиус {радиус.group(1) if радиус else '—'}px",
        "зелёный": манифест["green_identity"],
        "плотность": f"до {плотность} колонок на 1440",
    }


def собрать_данные(корень: pathlib.Path, доказательства: pathlib.Path) -> list[dict]:
    записи = []
    for пакет in sorted(корень.glob("T0*")):
        if not (пакет / "template.json").is_file():
            continue
        манифест = json.loads((пакет / "template.json").read_text(encoding="utf-8"))
        паспорт = json.loads((пакет / "PASSPORT.json").read_text(encoding="utf-8"))
        токены = (пакет / "tokens.css").read_text(encoding="utf-8")
        tid = манифест["template_id"]
        снимки = sorted((доказательства / "templates" / tid / "screenshots").glob("*.png"))
        записи.append({
            "tid": tid, "slug": манифест["slug"], "name": манифест["title"],
            "family": манифест["family"], "version": манифест["version"],
            "intent": манифест["design_intent"], "journey": манифест["primary_user_journey"],
            "днк": днк(манифест, паспорт, токены),
            "score": паспорт["measured"]["visual_score"],
            "hard_fails": паспорт["measured"]["hard_fail_count"],
            "digest": паспорт["package_digest"][:12],
            "shot_1440": next((с.name for с in снимки if с.name.endswith("-1440.png")), ""),
            "shot_390": next((с.name for с in снимки if с.name.endswith("-390.png")), ""),
            "shots_all": [с.name for с in снимки],
        })
    return записи


def страница(титул: str, тело: str, подвал: str) -> str:
    return (f"<!doctype html><html lang=ru><head><meta charset=utf-8>"
            f"<meta name=viewport content='width=device-width,initial-scale=1'>"
            f"<title>{э(титул)}</title><style>{СТИЛЬ}</style></head><body>"
            f"<div class=wrap>{тело}<footer>{подвал}</footer></div></body></html>")


def карточка_шаблона(з: dict, путь_снимков: str) -> str:
    д = з["днк"]
    большой = (f"<a href='{путь_снимков}/{э(з['tid'])}/screenshots/{э(з['shot_1440'])}'>"
               f"<img loading=lazy src='{путь_снимков}/{э(з['tid'])}/screenshots/{э(з['shot_1440'])}'"
               f" alt='{э(з['tid'])} на 1440 px'></a>") if з["shot_1440"] else "<p>снимка нет</p>"
    малый = (f"<a href='{путь_снимков}/{э(з['tid'])}/screenshots/{э(з['shot_390'])}'>"
             f"<img loading=lazy src='{путь_снимков}/{э(з['tid'])}/screenshots/{э(з['shot_390'])}'"
             f" alt='{э(з['tid'])} на 390 px'></a>") if з["shot_390"] else ""
    поля = [
        ("Назначение", з["intent"]), ("Путь пользователя", з["journey"]),
        ("Открывает", д["открывает"]), ("Состав главной", д["состав"]),
        ("Грамматика карточек", д["грамматика"]), ("Палитра", д["палитра"]),
        ("Роль зелёного", д["зелёный"]), ("Плотность", д["плотность"]),
    ]
    мета = "".join(f"<div><p class=k>{э(к)}</p><p class=v>{э(v)}</p></div>" for к, v in поля)
    статус = (f"<span class='badge ok'>технический балл {э(з['score'])}/100</span> "
              f"<span class=badge>жёстких отказов {э(з['hard_fails'])}</span> "
              f"<span class=badge>версия {э(з['version'])}</span> "
              f"<span class=badge>отпечаток {э(з['digest'])}</span>")
    return (f"<article class=card id='{э(з['tid'])}'>"
            f"<div class=head><span class=tid>{э(з['tid'])}</span>"
            f"<span class=name>{э(з['name'])}</span>"
            f"<span class=fam>{э(СЕМЕЙСТВА.get(з['family'], з['family']))} · {э(з['slug'])}</span></div>"
            f"<div class=shots><div>{большой}</div><div>{малый}</div></div>"
            f"<div class=meta>{мета}</div><p style='margin:12px 0 0'>{статус}</p>"
            f"<p class=decide>Решение владельца: __________ "
            f"(принять · доработать · отклонить). Статус до решения — TECHNICAL_CANDIDATE.</p>"
            f"</article>")


def построить(корень: pathlib.Path, доказательства: pathlib.Path, куда: pathlib.Path) -> dict:
    записи = собрать_данные(корень, доказательства)
    куда.mkdir(parents=True, exist_ok=True)
    метка = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
    подвал = (f"Каталог собран {э(метка)}. Технический балл — самооценка проверок фабрики, "
              f"а не приёмка. Все шаблоны в статусе TECHNICAL_CANDIDATE.")
    путь_снимков = "../templates"

    по_семьям: dict[str, list[dict]] = {}
    for з in записи:
        по_семьям.setdefault(з["family"], []).append(з)

    # --- указатель -----------------------------------------------------------
    навигация = "".join(
        f"<a href='family-{э(сем)}.html'>{э(СЕМЕЙСТВА.get(сем, сем))} ({len(v)})</a>"
        for сем, v in по_семьям.items())
    тело = (f"<h1>Lords T001–T050 — каталог для приёмки</h1>"
            f"<p class=lead>Пятьдесят шаблонных пакетов. У каждого показан рабочий стол на "
            f"1440 px и мобильный на 390 px, дизайн-ДНК и измеренное состояние. Поле решения "
            f"пустое: приёмку проставляет владелец.</p>"
            f"<p class=nav>{навигация}<a href='all.html'>Сводный лист (50)</a></p>")
    for сем, список in по_семьям.items():
        тело += f"<h2 id='{э(сем)}'>{э(СЕМЕЙСТВА.get(сем, сем))}</h2>"
        тело += "".join(карточка_шаблона(з, путь_снимков) for з in список)
    (куда / "index.html").write_text(страница("Lords T001–T050 — каталог", тело, подвал),
                                     encoding="utf-8")

    # --- листы семьи ---------------------------------------------------------
    for сем, список in по_семьям.items():
        ячейки = "".join(
            f"<div class=cell>"
            f"<a href='{путь_снимков}/{э(з['tid'])}/screenshots/{э(з['shot_1440'])}'>"
            f"<img loading=lazy src='{путь_снимков}/{э(з['tid'])}/screenshots/{э(з['shot_1440'])}'"
            f" alt='{э(з['tid'])}'></a>"
            f"<div class=cap><b>{э(з['tid'])}</b> {э(з['name'])}<br>"
            f"<span class=fam>{э(з['днк']['открывает'])} · {э(з['днк']['плотность'])}</span></div>"
            f"</div>" for з in список)
        тело_семьи = (
            f"<h1>{э(СЕМЕЙСТВА.get(сем, сем))} — пять шаблонов рядом</h1>"
            f"<p class=lead>Один масштаб, одна ширина (1440 px), одна страница. Так видно, "
            f"различаются ли шаблоны внутри семьи на самом деле.</p>"
            f"<p class=nav><a href='index.html'>← Указатель</a>"
            f"<a href='all.html'>Сводный лист</a></p>"
            f"<div class=row5>{ячейки}</div>")
        (куда / f"family-{сем}.html").write_text(
            страница(f"Lords — {СЕМЕЙСТВА.get(сем, сем)}", тело_семьи, подвал), encoding="utf-8")

    # --- сводный лист --------------------------------------------------------
    ячейки = "".join(
        f"<div class=cell>"
        f"<a href='{путь_снимков}/{э(з['tid'])}/screenshots/{э(з['shot_1440'])}'>"
        f"<img loading=lazy src='{путь_снимков}/{э(з['tid'])}/screenshots/{э(з['shot_1440'])}'"
        f" alt='{э(з['tid'])}'></a>"
        f"<div class=cap><b>{э(з['tid'])}</b> {э(з['name'])}<br>"
        f"<span class=fam>{э(СЕМЕЙСТВА.get(з['family'], з['family']))}</span></div></div>"
        for з in записи)
    тело_всех = (f"<h1>Все пятьдесят на одном листе</h1>"
                 f"<p class=lead>Снимок открывается в полный размер по щелчку. Миниатюры "
                 f"намеренно крупные: по картинке в сто пикселей об интерфейсе не судят.</p>"
                 f"<p class=nav><a href='index.html'>← Указатель</a></p>"
                 f"<div class=grid50>{ячейки}</div>")
    (куда / "all.html").write_text(страница("Lords — все пятьдесят", тело_всех, подвал),
                                   encoding="utf-8")

    return {"templates": len(записи), "families": len(по_семьям),
            "index": str(куда / "index.html"),
            "family_sheets": [str(куда / f"family-{с}.html") for с in по_семьям],
            "all_sheet": str(куда / "all.html")}


def главное() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="factory/templates/lords")
    parser.add_argument("--evidence", default="artifacts/evidence/lords-50-template-factory-01")
    parser.add_argument("--out", default="artifacts/evidence/lords-50-template-factory-01/review")
    args = parser.parse_args()
    итог = построить(pathlib.Path(args.root), pathlib.Path(args.evidence), pathlib.Path(args.out))
    print(json.dumps(итог, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(главное())
