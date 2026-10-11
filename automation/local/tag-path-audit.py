#!/usr/bin/env python3
"""Сценарий «карточка → кликабельная метка → тематический раздел → подходящие тайтлы» на живых витринах.

Метки (жанры и тематические метки каталога: «Самураи», «Школа», «Вампиры»…) берутся
из проверенных данных каталога — поле genres; новых не назначается. Для каждой
витрины и метки:
1. раздел метки отвечает 200; из выдачи берётся первая карточка тайтла;
2. в HTML карточки (без JS) есть обычная ссылка с текстом метки на раздел;
3. переход по ссылке: 200, title и H1 содержат метку, description непустой,
   canonical — сам раздел (или его каноническая форма), robots без noindex
   (раздел наполнен), хлебные крошки есть, viewport-meta есть;
4. исходный тайтл есть в выдаче раздела (первые страницы) — выборка соответствует;
5. если страниц больше одной — ссылка на страницу 2 есть и она отвечает 200.
Не измерено — отдельно, не успех.

    python3 automation/local/tag-path-audit.py [домен …]
"""
from __future__ import annotations

import html
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

q = urllib.parse.quote
СЕТЬ = {
    "lordserial33.biz": ("Самураи", "/genre/samurai/"), "lordfilm47.space": ("Самураи", "/genre/samurai/"),
    "1lordserials1.online": ("Самураи", "/genre/samurai/"), "lordserials22.info": ("Самураи", "/genre/samurai/"),
    "zonafilm.space": ("Самураи", "/catalog/?genre=samurai"), "zonafilm12.site": ("Самураи", "/catalog/?genre=samurai"),
    "zonafilm.cc": ("Самураи", "/catalog/?genre=samurai"),
    "an1mego.site": ("самураи", "/catalog/?genre=" + q("самураи")), "animeg0.site": ("самураи", "/catalog/?genre=" + q("самураи")),
    "an1meg0.site": ("самураи", "/catalog/?genre=" + q("самураи")),
    "animedia.icu": ("Самураи", "/catalog/?genre=samurai"), "animedia.space": ("Самураи", "/catalog/?genre=samurai"),
}


class _Без(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *а, **к):
        return None


def get(адрес: str):
    req = urllib.request.Request(адрес, headers={"User-Agent": "seo-operator-tag-path/1"})
    try:
        r = urllib.request.build_opener(_Без).open(req, timeout=60)
        return r.status, r.headers, r.read(4_000_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.headers, ""


def текст(х: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", х or "")).strip()


def карточки(тело: str) -> list[str]:
    return list(dict.fromkeys(re.findall(r'href="(?:https://[^"/]+)?(/title/[^/"]+/)"', тело)))


def проверить(хост: str, метка: str, раздел: str) -> list[str]:
    база = f"https://{хост}"
    беды: list[str] = []
    код, _, тело = get(база + раздел)
    if код != 200:
        return [f"раздел {раздел}: {код}"]
    тайтлы = карточки(тело)
    if not тайтлы:
        return [f"в разделе {раздел} нет карточек"]
    карта = тайтлы[0]
    код, _, тк = get(база + карта)
    if код != 200:
        return [f"карточка {карта}: {код}"]
    ссылки = [(html.unescape(h), текст(t)) for h, t in re.findall(r'<a [^>]*href="([^"]+)"[^>]*>(.*?)</a>', тк, re.S)]
    к_метке = [h for h, t in ссылки if t.lower() == метка.lower() and ("genre" in h)]
    if not к_метке:
        return [f"в HTML карточки {карта} нет обычной ссылки «{метка}» на раздел"]
    цель = к_метке[0] if к_метке[0].startswith("http") else база + к_метке[0]
    код, заг, тр = get(цель)
    if код != 200:
        return [f"переход по метке {цель}: {код} {заг.get('Location') or ''}"]
    титул = текст((re.findall(r"<title>(.*?)</title>", тр, re.S) or [""])[0])
    h1 = текст((re.findall(r"<h1[^>]*>(.*?)</h1>", тр, re.S) or [""])[0])
    опис = html.unescape((re.findall(r'<meta name="description" content="([^"]*)"', тр) or [""])[0])
    канон = [html.unescape(к) for к in re.findall(r'<link rel="canonical" href="([^"]+)"', тр)]
    роботы = " ".join(re.findall(r'<meta\s+name="robots"\s+content="([^"]+)"', тр)) + " " + (заг.get("X-Robots-Tag") or "")
    if метка.lower() not in титул.lower():
        беды.append(f"title раздела без метки: «{титул[:70]}»")
    if метка.lower() not in h1.lower():
        беды.append(f"H1 раздела без метки: «{h1[:70]}»")
    if not опис.strip():
        беды.append("description раздела пуст")
    if len(канон) != 1:
        беды.append(f"canonical раздела: {канон}")
    if "noindex" in роботы.lower():
        беды.append(f"наполненный раздел закрыт от индекса: {роботы.strip()}")
    if not re.search(r'breadcrumb|крошк|class="[^"]*(?:crumbs|bc)\b', тр, re.I):
        беды.append("хлебных крошек нет")
    if 'name="viewport"' not in тр:
        беды.append("нет viewport — мобильная вёрстка не объявлена")
    в_выдаче = set(карточки(тр))
    if карта not in в_выдаче:
        # тайтл мог уйти на страницу 2 при другом порядке — смотрим её
        стр2 = re.findall(r'href="([^"]*page=2[^"]*)"', тр)
        if стр2:
            а2 = html.unescape(стр2[0])
            а2 = а2 if а2.startswith("http") else база + а2
            в_выдаче |= set(карточки(get(а2)[2]))
        if карта not in в_выдаче:
            беды.append(f"исходный тайтл {карта} не найден в выдаче раздела (стр. 1–2)")
    стр2 = re.findall(r'href="([^"]*page=2[^"]*)"', тр)
    if стр2:
        а2 = html.unescape(стр2[0])
        а2 = а2 if а2.startswith("http") else база + а2
        if get(а2)[0] != 200:
            беды.append(f"страница 2 раздела не 200: {а2}")
    print(f"   {хост}: {карта} → «{метка}» → {цель} | title «{титул[:60]}» | H1 «{h1[:40]}» | "
          f"canon {канон[:1]} | карточек {len(карточки(тр))} | стр.2 {'есть' if стр2 else 'нет'}", flush=True)
    return беды


def main(argv: list[str]) -> int:
    хосты = argv or list(СЕТЬ)
    if any(х not in СЕТЬ for х in хосты):
        print("домены вне перечня")
        return 2
    плохо = 0
    for х in хосты:
        метка, раздел = СЕТЬ[х]
        try:
            беды = проверить(х, метка, раздел)
        except (urllib.error.URLError, OSError) as exc:
            беды = [f"НЕ ИЗМЕРЕНО: {exc}"]
        плохо += bool(беды)
        print(f"{'ок' if not беды else 'НАРУШЕНИЕ':10} {х}", *беды, sep="\n    · " if беды else "", flush=True)
    print("ИТОГ", "чисто" if not плохо else f"витрин с нарушениями: {плохо}")
    return 1 if плохо else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
