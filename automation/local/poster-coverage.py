"""Сколько карточек первого экрана идут без изображения — и есть ли оно у самого
произведения. Только чтение публичных страниц.

Зачем разделять. Отсутствие постера на КАРТОЧКЕ может быть и дефектом витрины
(не подставила), и отсутствием изображения у ЗАПИСИ. Это разные владельцы, и
путать их — та же ошибка, что с полем playable.
"""
import importlib.util
import pathlib
import re
import sys
import urllib.error
import urllib.request

КОРЕНЬ = pathlib.Path("/home/claude/wt-nova-publish-memory-02")
_с = importlib.util.spec_from_file_location(
    "audit", КОРЕНЬ / "automation/local/homepage-cards-audit.py")
А = importlib.util.module_from_spec(_с)
_с.loader.exec_module(А)

ДОМЕНЫ = sys.argv[1:] or ["zonafilm.space", "zonafilm12.site"]


def страница(адрес):
    запрос = urllib.request.Request(
        адрес, headers={"User-Agent": "factory-poster-coverage"})
    try:
        with urllib.request.urlopen(запрос, timeout=30) as о:
            return о.read().decode("utf-8", "replace")
    except (urllib.error.URLError, OSError, TimeoutError):
        return ""


for домен in ДОМЕНЫ:
    тело = А.добыть(f"https://{домен}/")
    карточки = А.карточки_по_порядку(тело, 24)
    без = [к for к in карточки if not к.get("постер")]
    print(f"\n{домен}: карточек {len(карточки)}, без изображения {len(без)}")
    for к in без:
        слаг = к.get("слаг") or к["путь"]
        т = страница(f"https://{домен}{к['путь']}")
        if not т:
            print(f"   {слаг[:36]:38} страница не прочитана — НЕ ИЗМЕРЕНО")
            continue
        i = т.find("<h1")
        окно = т[max(0, i - 3000):i + 500]
        свой = len(re.findall(r"poster\.cdnvideohub[^\"]*", окно))
        заглушек = окно.count("zt__none")
        h1 = re.search(r"<h1[^>]*>(.*?)</h1>", т, re.S)
        имя = re.sub(r"<[^>]+>", "", h1.group(1)).strip() if h1 else "—"
        вывод = ("изображения нет и у ЗАПИСИ (страница тоже показывает букву)"
                 if свой == 0 and заглушек else
                 "у записи изображение ЕСТЬ — не подставила витрина")
        print(f"   {слаг[:36]:38} «{имя[:28]}» → {вывод}")
