#!/usr/bin/env python3
"""Ворота маршрутов кандидата: карточка → адрес → страница → сущность.

Проверяется собранное дерево, а не намерение сборщика. Каждая видимая ссылка
на произведение со всех собранных страниц открывается по HTTP через локальный
стенд, и у ответа сверяется не только код, но и содержимое: заголовок против
текста карточки, канонический адрес против запрошенного, отсутствие текста
«не найдено» при коде 200.

Код ответа 200 сам по себе ничего не доказывает: мягкая 404 отдаёт его же.

    python3 automation/host/candidate-route-gate.py var/zona-candidate/zona-cinema \
        --out artifacts/candidate-route-gate/zona.json
"""
from __future__ import annotations

import argparse
import collections
import concurrent.futures
import html
import json
import pathlib
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(КОРЕНЬ))

from scripts.lords_stand import стенд                      # noqa: E402

ССЫЛКА = re.compile(r'href="(/title/[^"#?]*)"')
КАРТОЧКА = re.compile(r'<article class="card"[^>]*>(.*?)</article>', re.S)
ТЕКСТ_КАРТОЧКИ = re.compile(r'class="card__title"[^>]*>(.*?)</a>', re.S)
ЗАГОЛОВОК = re.compile(r"<h1[^>]*>(.*?)</h1>", re.S | re.I)
КАНОНИЧЕСКИЙ = re.compile(r'<link[^>]+rel="canonical"[^>]+href="([^"]+)"', re.I)
МЯГКАЯ_404 = re.compile(r"(страница не найдена|ничего не нашлось|не найдена)", re.I)


def текст(сырое: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", сырое or "")).strip()


def карточки_дерева(корень: pathlib.Path) -> dict[str, dict]:
    """Все видимые ссылки на произведения во всём собранном дереве.

    Обходится дерево целиком, а не первые страницы витрины: карточка,
    ведущая в никуда, чаще всего лежит не на главной.
    """
    найдено: dict[str, dict] = {}
    for ф in корень.rglob("*.html"):
        тело = ф.read_text("utf-8", "replace")
        откуда = "/" + str(ф.parent.relative_to(корень)).replace("\\", "/").strip(".")
        откуда = откуда.replace("//", "/")
        for кусок in КАРТОЧКА.findall(тело):
            адреса = ССЫЛКА.findall(кусок)
            подпись = ТЕКСТ_КАРТОЧКИ.search(кусок)
            if адреса:
                найдено.setdefault(адреса[0], {
                    "href": адреса[0], "from": откуда,
                    "text": текст(подпись.group(1)) if подпись else ""})
        for а in ССЫЛКА.findall(тело):
            найдено.setdefault(а, {"href": а, "from": откуда, "text": ""})
    return найдено


def проверить(база: str, к: dict) -> dict:
    адрес = база + к["href"]
    try:
        with urllib.request.urlopen(адрес, timeout=20) as о:
            тело = о.read().decode("utf-8", "replace")
            код, конечный = о.status, о.geturl()
    except urllib.error.HTTPError as ош:
        тело, код, конечный = ош.read().decode("utf-8", "replace"), ош.code, адрес
    except Exception as ош:
        return {**к, "status": None, "defect": "SITE_DOWN",
                "error": f"{type(ош).__name__}: {ош}"[:120]}
    h1 = ЗАГОЛОВОК.search(тело)
    заголовок = текст(h1.group(1)) if h1 else ""
    кан = КАНОНИЧЕСКИЙ.search(тело)
    запись = {**к, "status": код, "h1": заголовок,
              "canonical": кан.group(1) if кан else None,
              "final_path": urllib.parse.urlparse(конечный).path}
    if код != 200:
        запись["defect"] = "ROUTE_BROKEN"
    elif МЯГКАЯ_404.search(текст(тело)[:2000]) and not заголовок:
        запись["defect"] = "SOFT_404"
    elif к["text"] and к["text"].casefold()[:40] not in заголовок.casefold():
        запись["defect"] = "ENTITY_MISMATCH"
    elif кан and urllib.parse.urlparse(кан.group(1)).path.rstrip("/") != к["href"].rstrip("/"):
        запись["defect"] = "CANONICAL_MISMATCH"
    else:
        запись["defect"] = None
    return запись


def главное(аргв=None) -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("корень")
    р.add_argument("--out", required=True)
    р.add_argument("--workers", type=int, default=8)
    а = р.parse_args(аргв)

    корень = pathlib.Path(а.корень)
    ссылки = карточки_дерева(корень)
    карта = json.loads((корень / "route-map.json").read_text("utf-8"))["routes"]
    маршруты = {f"/title/{с}/" for с in карта}
    сироты = sorted(set(ссылки) - маршруты)
    неупомянутые = sorted(маршруты - set(ссылки))

    итог: list[dict] = []
    with стенд(корень) as с:
        with concurrent.futures.ThreadPoolExecutor(а.workers) as пул:
            for запись in пул.map(lambda к: проверить(с.база, к), ссылки.values()):
                итог.append(запись)

    свод = collections.Counter(з["defect"] or "OK" for з in итог)
    # Карта сайта: сверяется с той же картой маршрутов, а не с деревом.
    файл_карты = корень / "sitemap.xml"
    адреса_карты = []
    if файл_карты.is_file():
        тело = файл_карты.read_text("utf-8", "replace")
        адреса_карты = [м for м in re.findall(r"<loc>([^<]+)</loc>", тело)]
    # Отсутствие файла и пустой файл — разные вещи, и путать их нельзя:
    # «ни один адрес карты сайта не ведёт в никуда» верно и когда карты нет,
    # и это утверждение ни о чём.
    тело_карты = файл_карты.read_text("utf-8", "replace") if файл_карты.is_file() else None
    паритет = {"sitemap_present": файл_карты.is_file(),
               "sitemap_entries": len(адреса_карты),
               "sitemap_declares_empty": bool(тело_карты and "Адресов нет" in тело_карты),
               "sitemap_outside_route_map": sorted(
                   а_ for а_ in адреса_карты
                   if urllib.parse.urlparse(а_).path not in маршруты)[:10],
               "verdict": ("NO_SITEMAP" if тело_карты is None else
                           "EMPTY_DECLARED" if not адреса_карты and
                           "Адресов нет" in тело_карты else
                           "EMPTY_SILENT" if not адреса_карты else
                           "PARITY_OK" if not [а_ for а_ in адреса_карты
                                               if urllib.parse.urlparse(а_).path
                                               not in маршруты] else "PARITY_FAIL")}

    свод_итог = {
        "root": str(корень), "links_total": len(ссылки),
        "route_map_routes": len(карта),
        "orphan_card_targets": len(сироты),
        "routes_without_cards": len(неупомянутые),
        "by_defect": dict(свод),
        "sitemap": паритет,
        "failures": [з for з in итог if з["defect"]][:200],
    }
    путь = КОРЕНЬ / а.out
    путь.parent.mkdir(parents=True, exist_ok=True)
    путь.write_text(json.dumps({**свод_итог, "links": итог}, ensure_ascii=False,
                               indent=1), encoding="utf-8")
    print(json.dumps(свод_итог | {"failures": len(свод_итог["failures"])},
                     ensure_ascii=False, indent=1))
    return 0 if not свод_итог["failures"] and not сироты else 1


if __name__ == "__main__":
    raise SystemExit(главное())
