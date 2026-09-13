#!/usr/bin/env python3
"""Путь зрителя на живых витринах: карточка → адрес → страница → сущность.

Только чтение. Ничего не меняет, ничего не отправляет, кроме запросов GET, и
не трогает ни плеер, ни провайдера. Это замер исходного состояния, а не
исправление.

Что считается доказательством
-----------------------------

Код ответа 200 доказывает только то, что сервер что-то отдал. Поэтому у
каждой карточки сверяется ещё и содержимое: заголовок страницы против текста
карточки, канонический адрес против запрошенного, наличие оболочки плеера и
признака источника. Страница, отдающая 200 с чужим произведением, — дефект, а
не успех; страница, отдающая 200 с текстом «не найдено», — мягкий 404.

Список витрин берётся из канонического Registry, а не из перечня в задании:
перечень в задании может отстать, а Registry — то, что считается истиной.

    python3 automation/host/live-title-journey.py --out artifacts/live-title-journey
"""
from __future__ import annotations

import argparse
import collections
import gzip
import html
import json
import pathlib
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
РЕЕСТР = "http://127.0.0.1:8790/api/v1/registry/snapshot"
АГЕНТ = "site-factory-templates-readonly/1.0 (+live-title-journey)"

#: Разделы, которые обходятся у каждой витрины. Адреса — из навигации самой
#: витрины, а не выдуманные: то, чего в навигации нет, не проверяется как
#: «отсутствующее», иначе отчёт наполнится несуществующими ожиданиями.
РАЗДЕЛЫ = ("/", "/catalog/", "/movies/", "/series/", "/animation/", "/new/",
           "/genres/", "/countries/", "/search/", "/collections/", "/schedule/")

ССЫЛКА_ТАЙТЛА = re.compile(r'href="(/title/[^"#?]*)"')
ЗАГОЛОВОК = re.compile(r"<h1[^>]*>(.*?)</h1>", re.S | re.I)
КАНОНИЧЕСКИЙ = re.compile(r'<link[^>]+rel="canonical"[^>]+href="([^"]+)"', re.I)
TITLE_TAG = re.compile(r"<title[^>]*>(.*?)</title>", re.S | re.I)
#: Разметка карточки различается по витринам: у нашего кандидата это
#: `article.card`, у выложенного шаблона `nova` — `a.c` с `.c__t` внутри.
#: Один шаблон в разборе означал бы, что на живых витринах текст карточки не
#: извлекается вовсе, и проверка «та ли сущность» молча не выполняется.
КАРТОЧКА_КАНДИДАТА = re.compile(r'<article class="card"[^>]*>(.*?)</article>', re.S)
ТЕКСТ_КАНДИДАТА = re.compile(r'class="card__title"[^>]*>(.*?)</a>', re.S)
КАРТОЧКА_NOVA = re.compile(r'<a class="c" href="(/title/[^"#?]*)".*?</a>', re.S)
ТЕКСТ_NOVA = re.compile(r'class="c__t"[^>]*>(.*?)</div>', re.S)
ВЕРСИЯ_ШАБЛОНА = re.compile(
    r'data-template-version="([^"]*)"[^>]*data-template-family="([^"]*)"'
    r'[^>]*data-build-id="([^"]*)"')
ОТПЕЧАТОК_АРТЕФАКТА = re.compile(r'artifact-sha256="([^"]*)"')
СМОТРЕТЬ = re.compile(r">\s*(смотреть|играть|play)\b", re.I)
ПЛЕЕР = re.compile(r"(<iframe|<video\b|video-player|data-player|player__frame)", re.I)
#: Источник видео — именно видео, а не любое упоминание слова source.
#:
#: Первая версия ловила `data-source`, которым размечено происхождение
#: ДАННЫХ страницы, и объявляла источник видео найденным на страницах, где в
#: области плеера стоит честное «временно недоступно». Признак должен быть
#: узким: элемент плеера, iframe, video, source или ссылка на поток.
ИСТОЧНИК = re.compile(
    r'(<iframe[^>]+src="|<video\b[^>]*>|<source[^>]+src="|<video-player\b'
    r'|src="https?://[^"]+\.(?:m3u8|mp4|mpd))', re.I)
НЕДОСТУПНО = re.compile(
    r"(временно недоступн|источник не передан|видео.{0,20}недоступн|"
    r"не найдена|ничего не нашлось|404)", re.I)
СЕЗОН = re.compile(r"(сезон|season)", re.I)
СЕРИЯ = re.compile(r"(сери[яйи]|episode)", re.I)


def текст(сырое: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", сырое or "")).strip()


class Читатель:
    """GET с ограничением частоты и записью цепочки переходов."""

    def __init__(self, пауза: float = 0.15, таймаут: float = 20.0) -> None:
        self.пауза, self.таймаут = пауза, таймаут
        self.запросов = 0

    def получить(self, адрес: str) -> dict:
        переходы: list[str] = []

        class Ловец(urllib.request.HTTPRedirectHandler):
            def redirect_request(сам, req, fp, code, msg, headers, newurl):
                переходы.append(f"{code} → {newurl}")
                return super().redirect_request(req, fp, code, msg, headers, newurl)

        открыватель = urllib.request.build_opener(Ловец)
        зпр = urllib.request.Request(адрес, headers={"User-Agent": АГЕНТ})
        начало = time.monotonic()
        try:
            with открыватель.open(зпр, timeout=self.таймаут) as о:
                тело = о.read()
                исход = {"status": о.status, "final_url": о.geturl(),
                         "bytes": len(тело), "body": тело.decode("utf-8", "replace"),
                         "redirects": переходы}
        except urllib.error.HTTPError as ош:
            тело = ош.read()
            исход = {"status": ош.code, "final_url": адрес, "bytes": len(тело),
                     "body": тело.decode("utf-8", "replace"), "redirects": переходы}
        except Exception as ош:                      # сеть, TLS, отказ узла
            исход = {"status": None, "final_url": адрес, "bytes": 0, "body": "",
                     "redirects": переходы, "error": f"{type(ош).__name__}: {ош}"[:160]}
        исход["seconds"] = round(time.monotonic() - начало, 3)
        self.запросов += 1
        time.sleep(self.пауза)
        return исход


def витрины() -> list[dict]:
    зпр = urllib.request.Request(РЕЕСТР, headers={"User-Agent": АГЕНТ})
    with urllib.request.urlopen(зпр, timeout=20) as о:
        снимок = json.loads(о.read())
    return [с for с in снимок["sites"]], снимок["registry_version"]


def карточки(тело: str) -> list[dict]:
    """Карточки страницы: текст и адрес вместе, а не по отдельности."""
    из = []
    for кусок in КАРТОЧКА_КАНДИДАТА.findall(тело):
        адреса = ССЫЛКА_ТАЙТЛА.findall(кусок)
        подпись = ТЕКСТ_КАНДИДАТА.search(кусок)
        if not адреса:
            continue
        из.append({"href": адреса[0], "text": текст(подпись.group(1)) if подпись else ""})
    for м in re.finditer(r'<a class="c" href="(/title/[^"#?]*)"(.*?)</a>', тело, re.S):
        подпись = ТЕКСТ_NOVA.search(м.group(2))
        из.append({"href": м.group(1),
                   "text": текст(подпись.group(1)) if подпись else ""})
    # Ссылки на произведения вне карточек (карусель, «похожее») тоже ведут
    # зрителя и потому проверяются.
    вне = [а for а in ССЫЛКА_ТАЙТЛА.findall(тело)
           if all(а != к["href"] for к in из)]
    из.extend({"href": а, "text": ""} for а in dict.fromkeys(вне))
    return из


def разобрать_страницу(ответ: dict, ожидание: str) -> dict:
    тело = ответ.get("body") or ""
    h1 = ЗАГОЛОВОК.search(тело)
    заголовок = текст(h1.group(1)) if h1 else ""
    тайтл = TITLE_TAG.search(тело)
    кан = КАНОНИЧЕСКИЙ.search(тело)
    видно = текст(тело)
    версия = ВЕРСИЯ_ШАБЛОНА.search(тело)
    отпечаток = ОТПЕЧАТОК_АРТЕФАКТА.search(тело)
    return {
        "template_version": версия.group(1) if версия else None,
        "template_family": версия.group(2) if версия else None,
        "build_id": версия.group(3) if версия else None,
        "artifact_sha256": отпечаток.group(1) if отпечаток else None,
        "watch_cta": bool(СМОТРЕТЬ.search(тело)),
        "h1": заголовок,
        "title_tag": текст(тайтл.group(1)) if тайтл else "",
        "canonical": кан.group(1) if кан else None,
        "player_shell": bool(ПЛЕЕР.search(тело)),
        "source_ref": bool(ИСТОЧНИК.search(тело)),
        # Ищем по всему видимому тексту, а не по началу: сообщение о
        # недоступности стоит у плеера, то есть в середине страницы, и
        # ограничение первыми четырьмя тысячами знаков его не находило —
        # страница с честным «временно недоступно» числилась исправной.
        "unavailable_text": bool(НЕДОСТУПНО.search(видно)),
        "has_season": bool(СЕЗОН.search(тело)),
        "has_episode": bool(СЕРИЯ.search(тело)),
        "title_matches_card": bool(ожидание) and ожидание.casefold()[:40] in заголовок.casefold(),
    }


def класс_дефекта(ответ: dict, разбор: dict, ожидание: str) -> str | None:
    if ответ.get("status") is None:
        return "SITE_DOWN"
    if ответ["status"] in (502, 503, 504):
        return "SITE_DOWN"
    if ответ["status"] == 404:
        return "ROUTE_BROKEN"
    if ответ["status"] != 200:
        return "ROUTE_BROKEN"
    if разбор["unavailable_text"] and not разбор["h1"]:
        return "SOFT_404"
    if ожидание and not разбор["title_matches_card"]:
        return "ENTITY_MISMATCH"
    if разбор["canonical"]:
        путь = urllib.parse.urlparse(разбор["canonical"]).path or "/"
        if путь.rstrip("/") != urllib.parse.urlparse(ответ["final_url"]).path.rstrip("/"):
            return "CANONICAL_MISMATCH"
    if not разбор["player_shell"]:
        return "PLAYER_UNAVAILABLE"
    if not разбор["source_ref"]:
        # Оболочка есть, источника нет. Честное сообщение о недоступности
        # делает состояние правдивым, но просмотр от этого не появляется:
        # для зрителя это по-прежнему недоступное произведение.
        return "PLAYER_UNAVAILABLE"
    return None


def главное(аргв=None) -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--out", default="artifacts/live-title-journey")
    р.add_argument("--limit-per-site", type=int, default=0,
                   help="ограничить число проверяемых карточек (0 — все видимые)")
    а = р.parse_args(аргв)
    куда = КОРЕНЬ / а.out
    куда.mkdir(parents=True, exist_ok=True)

    сайты, версия = витрины()
    цель = [с for с in сайты if с.get("family") in ("lords", "zona")]
    читатель = Читатель()
    инвентарь: list[dict] = []
    отказы: list[dict] = []
    сводка: dict[str, dict] = {}

    for с in цель:
        домен = с["canonical_domain"]
        база = f"https://{домен}"
        свод = collections.Counter()
        ссылки: dict[str, dict] = {}
        разделы_итог = []
        for раздел in РАЗДЕЛЫ:
            ответ = читатель.получить(база + раздел)
            разделы_итог.append({"path": раздел, "status": ответ["status"],
                                 "bytes": ответ["bytes"],
                                 "error": ответ.get("error")})
            if ответ["status"] != 200:
                continue
            for к in карточки(ответ["body"]):
                ссылки.setdefault(к["href"], {"href": к["href"], "text": к["text"],
                                              "from": раздел})
        адреса = list(ссылки.values())
        if а.limit_per_site:
            адреса = адреса[:а.limit_per_site]
        for к in адреса:
            ответ = читатель.получить(база + к["href"])
            разбор = разобрать_страницу(ответ, к["text"])
            дефект = класс_дефекта(ответ, разбор, к["text"])
            запись = {"site_id": с["site_id"], "domain": домен,
                      "from_page": к["from"], "card_text": к["text"],
                      "href": к["href"], "status": ответ["status"],
                      "redirects": ответ["redirects"],
                      "final_url": ответ["final_url"], **разбор,
                      "defect": дефект}
            инвентарь.append(запись)
            свод[дефект or "OK"] += 1
            if дефект:
                отказы.append(запись)
        сводка[с["site_id"]] = {"domain": домен, "sections": разделы_итог,
                                "links_checked": len(адреса),
                                "by_defect": dict(свод)}
        print(f"{с['site_id']:10s} {домен:24s} ссылок {len(адреса):4d} "
              f"{json.dumps(dict(свод), ensure_ascii=False)}", flush=True)

    (куда / "live-inventory.json").write_text(
        json.dumps({"registry_version": версия, "requests": читатель.запросов,
                    "sites": сводка, "links": инвентарь},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    (куда / "live-failures.json").write_text(
        json.dumps({"count": len(отказы), "failures": отказы},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"sites": len(цель), "links": len(инвентарь),
                      "failures": len(отказы), "requests": читатель.запросов},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(главное())
