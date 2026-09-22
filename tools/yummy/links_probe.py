#!/usr/bin/env python3
"""Оракул ссылок: куда на самом деле ведут адреса с собственных страниц.

Зачем
-----

Собственные страницы витрины публикуют адреса, объявленные контуром полем
`canonical_path`. Контур и приложение расходятся в том, что считать аниме, и
часть объявленных адресов приложение не отдаёт: измерено 2026-09-22 — два
адреса из 164 отвечают 404, оба из раздела «Актуальное».

Почему проверка именно GET
--------------------------

HEAD на тех же адресах отвечает 200 — обработчик HEAD у приложения до отбора
не доходит. Поэтому дешёвой проверки существования страницы не существует, и
инструмент честно делает полный GET. По той же причине витрина такую проверку
в рантайме не делает: полторы сотни рендеров приложения каждые пять минут
лечили бы чужое расхождение ценой нагрузки.

Что считается находкой
----------------------

Любой ответ, кроме 200 и перенаправления, — ссылка ведёт не туда, куда
обещает карточка. Перенаправление отмечается отдельно: оно работает, но
гоняет посетителя и краулер через лишний переход.
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ССЫЛКА = re.compile(r'href="(/[^"]*)"')
#: Адреса, которые собственные страницы публикуют как карточки.
КАРТОЧКА = re.compile(r'<article class="portal-catalog-tile"[^>]*>.*?</article>', re.S)


class _БезПерехода(urllib.request.HTTPRedirectHandler):
    """Перенаправление не следуется: важен код, а не конечная страница."""

    def redirect_request(self, *_а, **_к):
        return None


def адреса_страницы(тело: str, только_карточки: bool) -> list[str]:
    куски = КАРТОЧКА.findall(тело) if только_карточки else [тело]
    найдено = []
    for к in куски:
        for а in ССЫЛКА.findall(к):
            а = а.split("#")[0]
            if а.startswith("/") and not а.startswith("//") and а not in найдено:
                найдено.append(а)
    return найдено


def код(основа: str, путь: str) -> int | str:
    открыватель = urllib.request.build_opener(_БезПерехода)
    адрес = основа + urllib.parse.quote(путь, safe="/?&=:")
    try:
        with открыватель.open(адрес, timeout=120) as о:
            return о.status
    except urllib.error.HTTPError as о:
        return о.code
    except (urllib.error.URLError, OSError) as ош:
        return f"ERR {type(ош).__name__}"


def main() -> int:
    р = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--base", required=True, help="адрес витрины")
    р.add_argument("--pages", default="/new/,/collections/,/schedule/,/top/",
                   help="собственные страницы через запятую")
    р.add_argument("--cards-only", action="store_true",
                   help="только адреса карточек, без шапки и подвала")
    р.add_argument("--out", required=True)
    а = р.parse_args()

    страницы = [п.strip() for п in а.pages.split(",") if п.strip()]
    откуда: dict[str, list[str]] = collections.defaultdict(list)
    for п in страницы:
        try:
            with urllib.request.urlopen(а.base + urllib.parse.quote(п, safe="/?&=:"),
                                        timeout=180) as о:
                тело = о.read().decode("utf-8", "replace")
        except (urllib.error.URLError, OSError) as ош:
            print(f"страница {п} недоступна: {ош}")
            continue
        часть = тело.split("<main", 1)[-1].split("</main>")[0]
        for адрес in адреса_страницы(часть, а.cards_only):
            откуда[адрес].append(п)

    строки = []
    счёт: collections.Counter = collections.Counter()
    for адрес in sorted(откуда):
        к = код(а.base, адрес)
        счёт[к] += 1
        строки.append({"href": адрес, "status": к, "found_on": откуда[адрес]})
    плохие = [с for с in строки if с["status"] != 200]
    свод = {
        "captured_at_utc": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc).isoformat(),
        "base": а.base, "pages": страницы, "cards_only": а.cards_only,
        "unique_links": len(строки), "by_status": {str(к): n for к, n in счёт.items()},
        "not_ok": len(плохие), "rows": строки,
    }
    Path(а.out).write_text(json.dumps(свод, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    print(f"уникальных внутренних ссылок: {len(строки)}; не 200: {len(плохие)}")
    for с in плохие[:20]:
        print(f"   {с['status']} {с['href']}  ← {', '.join(с['found_on'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
