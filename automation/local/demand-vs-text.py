#!/usr/bin/env python3
"""Есть ли наш текст там, куда поиск уже приводит людей. Только чтение.

Зачем. Отбор кандидатов редактора идёт по каталогу и пробелам в данных, а не по
спросу: витрина с 66 % поисковых входов на пять страниц одного тайтла получает
текст тогда же, когда страница без входов вовсе. Выгрузка кабинета даёт карту
спроса (`search_landing_pages` — визиты из поиска по пути входа), накладка
витрины — список наших текстов. Пересечение показывает, где текст принесёт
больше всего.

Это НЕ запросы и НЕ позиции: Вебмастер закрыт, и подменять его страницами входа
нельзя. Страница входа отвечает на вопрос «куда поиск уже приводит», и только.

Путь входа приводится к slug произведения: `/anime/<slug>/season/7/episode/4`,
`/title/<slug>/season-1/episode-6/` и `/anime/<slug>` дают один и тот же slug —
иначе спрос по сериям разъехался бы на пять строк и ни одна не попала бы в верх.
Пути, из которых slug не выделяется (`/`, `/catalog`, подборки), печатаются
отдельной строкой: это тоже спрос, но текста произведения он не требует.

    python3 automation/local/demand-vs-text.py
    python3 automation/local/demand-vs-text.py --domain yummyani.site --top 15

Коды: 0 — измерено хотя бы по одному домену; 2 — не измерено ничего.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
if str(КОРЕНЬ) not in sys.path:
    sys.path.insert(0, str(КОРЕНЬ))

from factory.qwen import registry  # noqa: E402

ВЫГРУЗКА = pathlib.Path(
    "/home/claude/wt-portable-site-cell-01/var/analytics/cabinet-latest.json")
#: Пути произведения: /anime/<slug>… и /title/<slug>… у наших фронтендов.
ПУТЬ_ТАЙТЛА = re.compile(r"^/(?:anime|title)/([^/?#]+)")


def slug_из_пути(путь: str) -> str:
    м = ПУТЬ_ТАЙТЛА.match(путь or "")
    return м.group(1) if м else ""


def спрос(домен: dict) -> tuple[dict[str, float], dict[str, float], str]:
    """({slug: визиты}, {прочий путь: визиты}, причина пустоты)."""
    мера = next((м for м in домен.get("measurements") or []
                 if м.get("key") == "search_landing_pages"), None)
    if мера is None:
        return {}, {}, "в выгрузке нет страниц входа из поиска"
    if not мера.get("measured"):
        причина = мера.get("state") or "не измерено"
        return {}, {}, f"{причина}{': ' + str(мера['reason']) if мера.get('reason') else ''}"
    по_тайтлам: dict[str, float] = {}
    прочее: dict[str, float] = {}
    for стр in мера.get("value") or []:
        изм = стр.get("dimensions") or []
        мет = стр.get("metrics") or []
        if len(изм) < 2 or not мет:
            continue
        if str((изм[0] or {}).get("id") or "") != "organic":
            continue
        путь = str((изм[1] or {}).get("name") or "")
        визиты = float(мет[0] or 0)
        slug = slug_из_пути(путь)
        if slug:
            по_тайтлам[slug] = по_тайтлам.get(slug, 0.0) + визиты
        else:
            прочее[путь] = прочее.get(путь, 0.0) + визиты
    if not по_тайтлам and not прочее:
        return {}, {}, "страниц входа из поиска в выгрузке нет"
    return по_тайтлам, прочее, ""


def наши_тексты(s) -> tuple[set[str], str]:
    """Slug'и, по которым у витрины есть НАШ опубликованный текст.

    У двух адаптеров наш учёт лежит в разных местах, и путать их нельзя: у
    приложения (yummy, animedia, animego) накладка сама ключуется по slug и
    лежит в корне хранилища адаптера; у lords доставляемый файл ключуется по
    `title_id` и лежит в каталоге данных ЯЧЕЙКИ, а slug'и живут в нашем учёте
    `published.json` — он всегда в корне хранилища адаптера, рядом с
    черновиками, а не рядом с доставленным файлом.
    """
    живой = pathlib.Path(registry.путь_доставки(s))
    если_app = живой.name == "title-overlays.json"
    try:
        каталог = pathlib.Path(registry.корень_хранилища(s.adapter)) / s.domain
    except Exception as сбой:
        return set(), f"корень хранилища не определён: {сбой}"
    try:
        д = json.loads(живой.read_text(encoding="utf-8"))
    except (OSError, ValueError) as сбой:
        # Для adapter lords доставляемый файл ключуется по title_id, и slug'и
        # живут в нашем учёте; для него отсутствие живого файла ещё не ответ.
        if если_app:
            return set(), f"накладка не прочитана: {сбой}"
        д = None
    if если_app and isinstance(д, dict):
        записи = д.get("items") or []
        return ({str(и.get("slug")) for и in записи
                 if isinstance(и, dict) and и.get("slug")}, "")
    учёт = каталог / "published.json"
    try:
        у = json.loads(учёт.read_text(encoding="utf-8"))
    except (OSError, ValueError) as сбой:
        return set(), f"нашего учёта нет: {сбой}"
    записи = у.get("items") or []
    return ({str(и.get("slug")) for и in записи
             if isinstance(и, dict) and и.get("slug")}, "")


def main(аргв: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(description="спрос против наличия нашего текста")
    р.add_argument("--file", default=str(ВЫГРУЗКА))
    р.add_argument("--domain", action="append", default=[])
    р.add_argument("--top", type=int, default=10)
    р.add_argument("--json", action="store_true")
    дов = р.parse_args(аргв)

    try:
        выгрузка = json.loads(pathlib.Path(дов.file).read_text(encoding="utf-8"))
    except (OSError, ValueError) as сбой:
        print(f"НЕ ИЗМЕРЕНО: выгрузка кабинета не прочитана ({сбой})")
        return 2

    сайты = {s.domain: s for s in registry.собрать(опрашивать_сеть=False)}
    итоги = {}
    for домен in выгрузка.get("domains") or []:
        имя = домен.get("domain")
        if дов.domain and имя not in дов.domain:
            continue
        по_тайтлам, прочее, почему = спрос(домен)
        if почему:
            итоги[имя] = {"измерено": False, "почему": почему}
            continue
        s = сайты.get(имя)
        if s is None:
            итоги[имя] = {"измерено": False, "почему": "домена нет в реестре ячеек"}
            continue
        тексты, беда = наши_тексты(s)
        строки = sorted(по_тайтлам.items(), key=lambda п: -п[1])
        итоги[имя] = {
            "измерено": True,
            "текстов": len(тексты),
            "текстов_почему": беда,
            "визитов_тайтлы": sum(по_тайтлам.values()),
            "визитов_прочее": sum(прочее.values()),
            "строки": [{"slug": sl, "визиты": в, "есть_текст": sl in тексты}
                       for sl, в in строки],
            "прочее": sorted(прочее.items(), key=lambda п: -п[1])[:5],
        }

    if дов.json:
        print(json.dumps(итоги, ensure_ascii=False, indent=2))
        return 0 if any(и["измерено"] for и in итоги.values()) else 2

    всего_без = 0.0
    for имя in sorted(итоги, key=lambda н: -(итоги[н].get("визитов_тайтлы") or 0)):
        и = итоги[имя]
        if not и["измерено"]:
            print(f"{имя}: НЕ ИЗМЕРЕНО — {и['почему']}")
            continue
        без_текста = [с for с in и["строки"] if not с["есть_текст"]]
        потеря = sum(с["визиты"] for с in без_текста)
        всего_без += потеря
        print(f"=== {имя}: визитов из поиска на страницы произведений"
              f" {и['визитов_тайтлы']:.0f}, прочие пути {и['визитов_прочее']:.0f};"
              f" наших текстов {и['текстов']}"
              + (f" [{и['текстов_почему']}]" if и["текстов_почему"] else ""))
        print(f"    спрос без нашего текста: {потеря:.0f} визитов"
              f" у {len(без_текста)} произведений")
        for с in и["строки"][:дов.top]:
            метка = "есть текст" if с["есть_текст"] else "ТЕКСТА НЕТ"
            print(f"    {с['визиты']:7.0f}  {метка:10}  {с['slug']}")
        for путь, визиты in и["прочее"]:
            print(f"    {визиты:7.0f}  не произведение  {путь}")
    print()
    print(f"суммарно визитов из поиска на произведения без нашего текста:"
          f" {всего_без:.0f}")
    return 0 if any(и["измерено"] for и in итоги.values()) else 2


if __name__ == "__main__":
    sys.exit(main())
