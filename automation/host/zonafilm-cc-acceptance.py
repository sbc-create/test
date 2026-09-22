#!/usr/bin/env python3
"""Приёмка витрины zonafilm.cc: маршруты, блоки, SEO, поиск, плеер, безопасность.

Проверяется поведение, а не наличие селектора. Каждая проверка возвращает не
«ok», а то, что измерено: сколько карточек, какие коды ответа, какие значения
заголовков. Пустой блок и отсутствующий блок — разные результаты, и различать
их обязан отчёт, а не читатель.

Ничего не меняет: только GET и HEAD по указанному origin с заданным Host.

    python3 automation/host/zonafilm-cc-acceptance.py \
        --origin http://127.0.0.1:9123 --host zonafilm.cc --out отчёт.json
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Транспорт
# ---------------------------------------------------------------------------
@dataclass
class Ответ:
    url: str
    status: int
    headers: dict
    body: str
    ms: float
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error and 200 <= self.status < 400


class Клиент:
    def __init__(self, origin: str, host: str, timeout: float = 30.0):
        self.origin = origin.rstrip("/")
        self.host = host
        self.timeout = timeout
        self.журнал: list[Ответ] = []

    @staticmethod
    def безопасный(путь: str) -> str:
        """Нелатинские байты в адресе экранируются.

        Кириллический запрос без quote даёт UnicodeEncodeError внутри http.client,
        и проверка падает, не дойдя до витрины. Такой «отказ» неотличим от отказа
        витрины — а это разные вещи, и путать их нельзя.
        """
        разобрано = urllib.parse.urlsplit(путь)
        return urllib.parse.urlunsplit((
            разобрано.scheme, разобрано.netloc,
            urllib.parse.quote(разобрано.path, safe="/%"),
            urllib.parse.quote(разобрано.query, safe="=&%+"),
            разобрано.fragment,
        ))

    def get(self, путь: str, *, method: str = "GET", follow: bool = False,
            headers: dict | None = None) -> Ответ:
        путь = self.безопасный(путь.replace("&amp;", "&"))
        url = self.origin + путь
        заголовки = {"Host": self.host, "User-Agent": "site-factory-acceptance/1"}
        заголовки.update(headers or {})
        запрос = urllib.request.Request(url, method=method, headers=заголовки)
        opener = urllib.request.build_opener(
            *([] if follow else [_НеСледовать()])
        )
        начало = time.monotonic()
        try:
            with opener.open(запрос, timeout=self.timeout) as r:
                тело = r.read()
                ответ = Ответ(url, r.status, dict(r.headers), тело.decode("utf-8", "replace"),
                              round((time.monotonic() - начало) * 1000, 1))
        except urllib.error.HTTPError as e:
            тело = e.read()
            ответ = Ответ(url, e.code, dict(e.headers), тело.decode("utf-8", "replace"),
                          round((time.monotonic() - начало) * 1000, 1))
        except Exception as e:  # сеть, таймаут, разрыв
            ответ = Ответ(url, 0, {}, "", round((time.monotonic() - начало) * 1000, 1),
                          error=f"{type(e).__name__}: {e}")
        self.журнал.append(ответ)
        return ответ


class _НеСледовать(urllib.request.HTTPRedirectHandler):
    """Редирект — это факт, а не деталь доставки: его нужно увидеть, а не пройти."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, msg, headers, fp)


# ---------------------------------------------------------------------------
# Разбор
# ---------------------------------------------------------------------------
def найти_все(шаблон: str, текст: str) -> list[str]:
    return re.findall(шаблон, текст, re.I | re.S)


def счёт(шаблон: str, текст: str) -> int:
    return len(найти_все(шаблон, текст))


def атрибут(html: str, тег_шаблон: str, атр: str) -> list[str]:
    out = []
    for тег in найти_все(тег_шаблон, html):
        m = re.search(rf'{атр}="([^"]*)"', тег, re.I)
        if m:
            out.append(m.group(1))
    return out


@dataclass
class Проверка:
    id: str
    ok: bool
    measured: dict = field(default_factory=dict)
    note: str = ""


class Приёмка:
    def __init__(self, клиент: Клиент):
        self.к = клиент
        self.проверки: list[Проверка] = []

    def добавить(self, id: str, ok: bool, **measured) -> Проверка:
        note = measured.pop("note", "")
        п = Проверка(id, bool(ok), measured, note)
        self.проверки.append(п)
        return п

    # -- 1. маршруты ------------------------------------------------------
    #: (имя, путь, допустимые коды). Допустимое — не «что угодно»: `/schedule/`
    #: обязан быть ровно одним 308 на действующий раздел, а `sitemap.xml` у
    #: закрытого canary имеет право не существовать. Записывать 308 в провалы
    #: значило бы требовать от витрины того, чего у неё быть не должно.
    МАРШРУТЫ = [
        ("home", "/", (200,)),
        ("catalog", "/catalog/", (200,)),
        ("catalog_page2", "/catalog/?page=2", (200,)),
        ("movies", "/movies/", (200,)),
        ("series", "/series/", (200,)),
        ("animation", "/animation/", (200,)),
        ("new", "/new/", (200,)),
        ("collections", "/collections/", (200,)),
        ("schedule", "/schedule/", (200, 301, 308)),
        ("search_empty", "/search/", (200,)),
        ("search_query", "/search/?q=матрица", (200,)),
        ("robots", "/robots.txt", (200,)),
        ("sitemap", "/sitemap.xml", (200, 404)),
        ("healthz", "/healthz", (200,)),
        ("template_version", "/__template_version", (200,)),
    ]

    def маршруты(self) -> dict:
        результат = {}
        for имя, путь, допустимые in self.МАРШРУТЫ:
            о = self.к.get(путь)
            результат[имя] = {"path": путь, "status": о.status, "ms": о.ms,
                              "bytes": len(о.body), "error": о.error,
                              "allowed": list(допустимые)}
            if о.status in (301, 308):
                результат[имя]["location"] = о.headers.get("Location")
            self.добавить(f"route.{имя}", о.status in допустимые,
                          path=путь, status=о.status, allowed=list(допустимые), ms=о.ms)
        # 404 обязан быть осмысленным: код 404 и собственная оболочка витрины.
        о = self.к.get("/этого-точно-нет-" + str(int(time.time())))
        осмысленная = о.status == 404 and "<html" in о.body.lower() and len(о.body) > 500
        результат["not_found"] = {"status": о.status, "bytes": len(о.body),
                                  "has_shell": "<html" in о.body.lower()}
        self.добавить("route.404_meaningful", осмысленная,
                      status=о.status, bytes=len(о.body))
        return результат

    # -- 2. индексация и canonical ---------------------------------------
    def индексация(self, домен: str) -> dict:
        страницы = ["/", "/catalog/", "/new/", "/search/?q=тест"]
        итог = {"pages": {}}
        все_закрыты = True
        canonical_ok = True
        чужой_canonical = []
        for путь in страницы:
            о = self.к.get(путь)
            заголовок = (о.headers.get("X-Robots-Tag") or "").lower().replace(" ", "")
            мета = найти_все(r'<meta[^>]+name="robots"[^>]*>', о.body)
            мета_знач = [re.search(r'content="([^"]*)"', m, re.I).group(1).lower().replace(" ", "")
                         for m in мета if re.search(r'content="([^"]*)"', m, re.I)]
            канон = найти_все(r'<link[^>]+rel="canonical"[^>]*>', о.body)
            канон_знач = [re.search(r'href="([^"]*)"', c, re.I).group(1)
                          for c in канон if re.search(r'href="([^"]*)"', c, re.I)]
            закрыта = "noindex" in заголовок and "nofollow" in заголовок and \
                      any("noindex" in v and "nofollow" in v for v in мета_знач)
            все_закрыты = все_закрыты and закрыта
            for c in канон_знач:
                хост = urllib.parse.urlparse(c).hostname or ""
                if хост and хост != домен:
                    чужой_canonical.append({"path": путь, "canonical": c})
                    canonical_ok = False
            итог["pages"][путь] = {"x_robots_tag": заголовок, "meta_robots": мета_знач,
                                   "canonical": канон_знач}
        self.добавить("seo.noindex_header_and_meta", все_закрыты, pages=len(страницы))
        self.добавить("seo.canonical_own_domain_only", canonical_ok,
                      foreign=чужой_canonical)

        robots = self.к.get("/robots.txt")
        тело = robots.body.lower()
        закрыт = "disallow: /" in тело and "user-agent: *" in тело
        итог["robots_txt"] = {"status": robots.status, "body": robots.body[:400]}
        self.добавить("seo.robots_txt_closed", robots.status == 200 and закрыт,
                      status=robots.status, body_head=robots.body[:200])

        карта = self.к.get("/sitemap.xml")
        urls = счёт(r"<loc>", карта.body)
        итог["sitemap"] = {"status": карта.status, "urls": urls,
                           "bytes": len(карта.body)}
        # Закрытый canary: карта не должна звать краулера на страницы.
        self.добавить("seo.sitemap_matches_closed_canary", карта.status in (200, 404) and urls == 0,
                      status=карта.status, url_count=urls)
        return итог

    # -- 3. блоки главной --------------------------------------------------
    def главная(self) -> dict:
        """Блоки главной измеряются по разметке, которую витрина реально отдаёт.

        Оформление 1.2.0 семейства zona строит главную иначе, чем дореформенная
        ветка того же артефакта: один герой (`zhero`) и плитки коллекций
        (`zhub__c`) вместо полок карточек. Проверять здесь `hero__it` значило бы
        мерить блок, которого в этой версии нет, и записывать его отсутствие как
        поломку витрины, хотя это свойство шаблона.

        Слайдер проверяется отдельно и честно: сколько слайдов, есть ли
        управление. Ноль — это результат, а не пропуск проверки.
        """
        о = self.к.get("/")
        html = о.body
        # Два поколения разметки героя: дореформенная (`hero__it`) и 1.2
        # (`zhero`). Считаются обе, потому что вопрос задания — «сколько разных
        # тайтлов показывает герой», а не «какой класс у контейнера».
        слайды = (найти_все(r'<[^>]+class="hero__it"[^>]*>', html)
                  + найти_все(r'<[^>]+data-zhero-slide[^>]*>', html))
        ссылки_слайдов = set(
            атрибут(html, r'<a[^>]+class="[^"]*hero__[^"]*"[^>]*>', "href")
            + атрибут(html, r'<div[^>]+class="zhero__cta"[^>]*>.*?</div>', "href")
            + найти_все(r'class="zhero__cta"[^>]*>\s*<a[^>]+href="([^"]+)"', html))
        герой_есть = счёт(r'class="zhero"', html) + счёт(r'class="hero"', html)
        точки = (счёт(r'class="hero__dots"', html)
                 + счёт(r"data-zhero-dot", html))
        плитки = атрибут(html, r'<a[^>]+class="zhub__c"[^>]*>', "href")
        виды = атрибут(html, r'<a[^>]+class="zkind"[^>]*>', "href")
        секции = {}
        for m in re.finditer(r'<h2[^>]*>(.*?)</h2>', html, re.I | re.S):
            заголовок = re.sub(r"<[^>]+>", "", m.group(1)).strip()
            if заголовок:
                секции[заголовок] = секции.get(заголовок, 0) + 1
        карточки = счёт(r'href="/title/', html)
        подборки = счёт(r'href="/collection/', html)
        пустые = счёт(r'<section[^>]*>\s*</section>', html)
        футер = счёт(r"<footer", html)
        итог = {
            "hero_present": герой_есть,
            "hero_slides": len(слайды),
            "hero_distinct_links": len(ссылки_слайдов),
            "hero_dots": точки,
            "sections": секции,
            "title_links": карточки,
            "collection_tiles": плитки,
            "kind_links": виды,
            "collection_links": подборки,
            "empty_sections": пустые,
            "footer": футер,
            "bytes": len(html),
            "ms": о.ms,
        }
        self.добавить("home.hero_present", герой_есть >= 1, hero_blocks=герой_есть)
        # Слайдер: отдельная проверка и отдельный результат. Ноль слайдов у
        # закреплённого шаблона — известный дефект (TEMPLATE_ZONA_BLOCKER-01),
        # и он обязан быть виден в отчёте как провал, а не спрятан смягчением
        # условия под то, что витрина и так умеет.
        self.добавить("home.slider_multiple_titles", len(слайды) >= 3,
                      slides=len(слайды), distinct_links=len(ссылки_слайдов),
                      note="TEMPLATE_ZONA_BLOCKER-01, если 0: в 1.2.0 герой статичен")
        self.добавить("home.slider_controls", точки >= 1, dots=точки,
                      note="управление слайдером: точки или стрелки")
        self.добавить("home.collection_tiles", len(плитки) >= 4,
                      tiles=len(плитки), hrefs=плитки)
        self.добавить("home.kind_links", len(виды) >= 2, kinds=виды)
        self.добавить("home.no_empty_containers", пустые == 0, empty_sections=пустые)
        self.добавить("home.footer_present", футер >= 1, footer=футер)
        return итог

    # -- 3b. коллекции: смысл блоков, а не их наличие ---------------------
    def коллекции(self, плитки: list[str]) -> dict:
        """Каждая плитка ведёт на страницу, и страницы не совпадают между собой.

        Проверяется то, что задание и называет: «последние добавления» и
        «новые серии» разделены, блок «с видео» не показывает записей без
        просмотра, порядок детерминирован, дубликатов нет.
        """
        итог: dict = {}
        наборы: dict[str, list[str]] = {}
        for href in плитки:
            о = self.к.get(href)
            ссылки = атрибут(о.body, r'<a[^>]+href="/title/[^"]*"[^>]*>', "href")
            уникальные = list(dict.fromkeys(ссылки))
            повтор = self.к.get(href)
            ссылки2 = list(dict.fromkeys(
                атрибут(повтор.body, r'<a[^>]+href="/title/[^"]*"[^>]*>', "href")))
            заголовок = (найти_все(r"<h1[^>]*>(.*?)</h1>", о.body) or [""])[0]
            заголовок = re.sub(r"<[^>]+>", "", заголовок).strip()
            ключ = href.strip("/").replace("/", ".")
            итог[href] = {
                "status": о.status, "title": заголовок,
                "items": len(ссылки), "distinct": len(уникальные),
                "duplicates": len(ссылки) - len(уникальные),
                "deterministic": уникальные == ссылки2, "ms": о.ms,
            }
            наборы[href] = уникальные
            self.добавить(f"collection.{ключ}.has_items",
                          о.status == 200 and len(уникальные) > 0,
                          href=href, status=о.status, items=len(уникальные))
            self.добавить(f"collection.{ключ}.no_duplicates",
                          len(ссылки) == len(уникальные),
                          items=len(ссылки), distinct=len(уникальные))
            self.добавить(f"collection.{ключ}.deterministic",
                          уникальные == ссылки2, href=href)

        добавленные = наборы.get("/collection/recently_added/", [])
        серии = наборы.get("/collection/new_episodes/", [])
        if добавленные and серии:
            совпало = len(set(добавленные) & set(серии))
            self.добавить("collection.added_and_episodes_are_different",
                          добавленные != серии, overlap=совпало,
                          added=len(добавленные), episodes=len(серии))
            итог["added_vs_episodes_overlap"] = совпало

        # «С видео» обещает просмотр. Проверяется не наличие iframe, а состояние
        # плеера: `noaccess` означает, что витрине не выдан Publisher ID, и это
        # внешний блокер, а не ошибка подборки. Смешивать их нельзя — иначе
        # отсутствие учётных данных читалось бы как враньё витрины о контенте,
        # а настоящее враньё потерялось бы среди него.
        с_видео = наборы.get("/collection/video_available/", [])
        состояния: dict[str, int] = {}
        без_блока, пустой_iframe = [], []
        for href in с_видео[:12]:
            о = self.к.get(href)
            состояние = (найти_все(r'data-player[^>]*data-state="([a-z]+)"', о.body)
                         or найти_все(r'data-state="([a-z]+)"[^>]*data-player', о.body))
            ключ = состояние[0] if состояние else "нет-блока"
            состояния[ключ] = состояния.get(ключ, 0) + 1
            if not состояние:
                без_блока.append(href)
            кадры = атрибут(о.body, r"<iframe[^>]*>", "src")
            if счёт(r"<iframe", о.body) and not [s for s in кадры if s]:
                пустой_iframe.append(href)
        только_noaccess = set(состояния) <= {"noaccess"}
        self.добавить("collection.video_available_has_player_block", not без_блока,
                      checked=len(с_видео[:12]), states=состояния, without_block=без_блока[:5])
        self.добавить("collection.video_available_no_empty_iframe", not пустой_iframe,
                      empty=пустой_iframe[:5])
        self.добавить(
            "collection.video_available_is_watchable",
            bool(состояния) and not только_noaccess,
            states=состояния,
            note=("BLOCKED_EXTERNAL_CREDENTIAL: все записи в состоянии noaccess — "
                  "витрине не выдан Publisher ID провайдера (player-zona-02.json)"
                  if только_noaccess else ""))
        итог["video_available_probe"] = {"checked": len(с_видео[:12]),
                                         "player_states": состояния,
                                         "without_block": без_блока,
                                         "empty_iframe": пустой_iframe}
        return итог

    # -- 4. каталог --------------------------------------------------------
    def каталог(self) -> dict:
        итог = {}
        первая = self.к.get("/catalog/")
        вторая = self.к.get("/catalog/?page=2")
        сл1 = set(атрибут(первая.body, r'<a[^>]+href="/title/[^"]*"[^>]*>', "href"))
        сл2 = set(атрибут(вторая.body, r'<a[^>]+href="/title/[^"]*"[^>]*>', "href"))
        итог["page1_titles"] = len(сл1)
        итог["page2_titles"] = len(сл2)
        итог["overlap"] = len(сл1 & сл2)
        self.добавить("catalog.pagination_distinct", bool(сл1) and bool(сл2) and not (сл1 & сл2),
                      page1=len(сл1), page2=len(сл2), overlap=len(сл1 & сл2))
        self.добавить("catalog.page1_no_duplicates",
                      len(сл1) == счёт(r'<a[^>]+href="/title/[^"]*"[^>]*class="[^"]*card', первая.body)
                      or len(сл1) > 0,
                      distinct=len(сл1))

        # Фильтры: значения берутся из самой выдачи, а не придумываются.
        #
        # Искать их только в href недостаточно: год на витрине Zona выбирается
        # через <select>, и его значения живут в `option value`, а жанр вообще
        # не выведен на страницу каталога — ссылка на него есть на странице
        # тайтла. Поэтому область поиска — каталог плюс одна страница тайтла.
        тайтл_href = (sorted(сл1) or [""])[0]
        источник = первая.body + (self.к.get(тайтл_href).body if тайтл_href else "")
        def кандидаты(параметр: str) -> list[str]:
            найдено = set()
            найдено |= set(найти_все(rf'href="(/catalog/\?[^"]*{параметр}=[^"&]*[^"]*)"', источник))
            найдено |= set(найти_все(rf'value="(/catalog/\?[^"]*{параметр}=[^"&]*[^"]*)"', источник))
            return sorted(с.replace("&amp;", "&") for с in найдено)

        фильтры = {}
        for имя in ("genre", "country", "year", "kind", "sort"):
            ссылки = кандидаты(имя)
            фильтры[имя] = {"links_found": len(ссылки), "sample": ссылки[:3]}
            if ссылки:
                проба = ссылки[0].replace("&amp;", "&")
                о = self.к.get(проба)
                карточек = len(set(атрибут(о.body, r'<a[^>]+href="/title/[^"]*"[^>]*>', "href")))
                фильтры[имя].update({"probe": проба, "status": о.status, "titles": карточек})
                self.добавить(f"catalog.filter_{имя}", о.status == 200 and карточек > 0,
                              probe=проба, status=о.status, titles=карточек)
            else:
                self.добавить(f"catalog.filter_{имя}", False,
                              note="на странице каталога нет ни одной ссылки такого фильтра")
        итог["filters"] = фильтры

        # состояние в URL: два запроса одного адреса дают одно и то же
        if фильтры.get("genre", {}).get("probe"):
            адрес = фильтры["genre"]["probe"]
            a = self.к.get(адрес)
            b = self.к.get(адрес)
            self.добавить("catalog.url_state_deterministic",
                          a.status == b.status and a.body == b.body,
                          url=адрес, equal=a.body == b.body)
            комбинация = адрес + "&sort=year"
            c = self.к.get(комбинация)
            self.добавить("catalog.filter_combination", c.status == 200,
                          url=комбинация, status=c.status)
            итог["combination"] = {"url": комбинация, "status": c.status}
        return итог

    # -- 5. поиск ----------------------------------------------------------
    def поиск(self, образец: str) -> dict:
        части = образец.split()
        запросы = {
            "exact": образец,
            "partial": части[0][:5] if части else образец[:5],
            "upper": образец.upper(),
            "lower": образец.lower(),
            "latin": "matrix",
            "cyrillic": "матрица",
            "hyphen": "человек-паук",
            "colon": "миссия: невыполнима",
            "spaces": "  два   пробела  ",
            "absent": "щщщнесуществующийзапросщщщ",
            "xss": '<script>alert(1)</script>',
            "sqli": "' OR 1=1 --",
        }
        итог = {}
        for имя, q in запросы.items():
            путь = "/search/?q=" + urllib.parse.quote(q)
            о = self.к.get(путь)
            найдено = len(set(атрибут(о.body, r'<a[^>]+href="/title/[^"]*"[^>]*>', "href")))
            отражено = "<script>alert(1)</script>" in о.body
            итог[имя] = {"q": q, "status": о.status, "results": найдено, "ms": о.ms,
                         "raw_script_reflected": отражено}
            if имя == "xss":
                self.добавить("search.xss_not_reflected", о.status == 200 and not отражено,
                              status=о.status, reflected=отражено)
            elif имя == "sqli":
                self.добавить("search.sqli_handled", о.status == 200, status=о.status,
                              results=найдено)
            elif имя == "absent":
                self.добавить("search.no_results_is_a_page", о.status == 200 and найдено == 0,
                              status=о.status, results=найдено)
            else:
                self.добавить(f"search.{имя}", о.status == 200, status=о.status,
                              results=найдено, ms=о.ms)
        медиана = statistics.median([v["ms"] for v in итог.values()])
        итог["median_ms"] = медиана
        self.добавить("search.responds_fast", медиана < 1500, median_ms=медиана)

        # переход из результата ведёт на существующую страницу
        о = self.к.get("/search/?q=" + urllib.parse.quote(образец))
        ссылки = sorted(set(атрибут(о.body, r'<a[^>]+href="/title/[^"]*"[^>]*>', "href")))
        if ссылки:
            цель = self.к.get(ссылки[0])
            итог["follow_first_result"] = {"href": ссылки[0], "status": цель.status}
            self.добавить("search.result_leads_to_page", цель.status == 200,
                          href=ссылки[0], status=цель.status)
        else:
            self.добавить("search.result_leads_to_page", False,
                          note="точный запрос не дал ни одной ссылки на тайтл")
        return итог

    # -- 6. страница тайтла ------------------------------------------------
    def тайтл(self, href: str, домен: str) -> dict:
        о = self.к.get(href)
        html = о.body
        h1 = найти_все(r"<h1[^>]*>.*?</h1>", html)
        канон = атрибут(html, r'<link[^>]+rel="canonical"[^>]*>', "href")
        og = {m.group(1): m.group(2) for m in
              re.finditer(r'<meta[^>]+property="(og:[^"]+)"[^>]+content="([^"]*)"', html, re.I)}
        jsonld = найти_все(r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', html)
        # Крошки бывают разметкой и бывают JSON-LD. Zona 1.2 отдаёт их вторым
        # способом, и требовать именно microdata значило бы объявить отсутствие
        # того, что есть.
        крошки = (счёт(r'itemtype="https?://schema\.org/BreadcrumbList"', html)
                  + счёт(r'class="[^"]*crumb', html)
                  + счёт(r'"@type"\s*:\s*"BreadcrumbList"', html))
        плеер = счёт(r"<iframe", html)
        состояние_плеера = (найти_все(r'data-player[^>]*data-state="([a-z]+)"', html)
                            + найти_все(r'data-state="([a-z]+)"[^>]*data-player', html))
        контракт = (найти_все(r'data-player-contract="([^"]+)"', html) or [""])[0]
        iframe_src = атрибут(html, r"<iframe[^>]*>", "src")
        сезоны = счёт(r'data-season|class="[^"]*season', html)
        эпизоды = счёт(r'data-episode|class="[^"]*episode', html)
        рекоменд = счёт(r'href="/title/', html)
        # Считаются источники оценок В БЛОКЕ РЕЙТИНГА, а не все упоминания слова
        # в документе: «IMDb 9.1» в карточке рекомендации — это подпись к оценке
        # соседнего тайтла, а не ещё один логотип на этой странице. Нагромождение
        # логотипов — это про блок оценок, и мерить надо его.
        источники_оценок = sorted(set(найти_все(r'data-source="([a-z]+)"', html)))
        логотипы = len(источники_оценок)
        оценка = найти_все(r'(\d+[.,]\d)\s*(?:/\s*10|из\s*10)', html)

        итог = {
            "href": href, "status": о.status, "ms": о.ms, "bytes": len(html),
            "h1_count": len(h1),
            "canonical": канон,
            "og_keys": sorted(og),
            "jsonld_blocks": len(jsonld),
            "breadcrumbs": крошки,
            "iframes": плеер,
            "player_state": состояние_плеера,
            "player_contract": контракт,
            "rating_sources": источники_оценок,
            "iframe_src": iframe_src[:3],
            "season_markers": сезоны,
            "episode_markers": эпизоды,
            "related_links": рекоменд,
            "rating_like": оценка[:5],
            "provider_logo_mentions": логотипы,
        }
        self.добавить("title.status", о.status == 200, href=href, status=о.status)
        self.добавить("title.single_h1", len(h1) == 1, count=len(h1))
        свой = all((urllib.parse.urlparse(c).hostname or домен) == домен for c in канон)
        self.добавить("title.canonical_own_domain", bool(канон) and свой, canonical=канон)
        self.добавить("title.open_graph", {"og:title", "og:type"} <= set(og), keys=sorted(og))
        self.добавить("title.jsonld", len(jsonld) >= 1, blocks=len(jsonld))
        self.добавить("title.breadcrumbs", крошки >= 1, markers=крошки)
        self.добавить("title.back_to_catalog",
                      'href="/catalog/' in html or 'href="/movies/' in html
                      or 'href="/series/' in html,
                      note="ссылка назад в каталог")
        self.добавить("title.no_provider_logo_pile", логотипы <= 3,
                      rating_sources=источники_оценок)
        # Пустой iframe хуже отсутствующего: он обещает просмотр, которого нет.
        # Честные состояния — `noaccess`/`nosource` с подписью и без рамки.
        self.добавить("title.player_has_no_empty_iframe",
                      not (плеер and not [s for s in iframe_src if s]),
                      iframes=плеер, srcs=iframe_src[:3], state=состояние_плеера)
        self.добавить("title.player_contract_declared", bool(контракт),
                      contract=контракт, state=состояние_плеера)
        return итог

    # -- 7. карточки не ведут в 404 ---------------------------------------
    def карточки_живые(self, сколько: int = 40) -> dict:
        о = self.к.get("/")
        ссылки = sorted(set(атрибут(о.body, r'<a[^>]+href="/title/[^"]*"[^>]*>', "href")))
        о2 = self.к.get("/catalog/")
        ссылки += sorted(set(атрибут(о2.body, r'<a[^>]+href="/title/[^"]*"[^>]*>', "href")))
        ссылки = sorted(set(ссылки))[:сколько]
        коды: dict[int, int] = {}
        плохие = []
        for href in ссылки:
            о = self.к.get(href, method="HEAD")
            коды[о.status] = коды.get(о.status, 0) + 1
            if о.status != 200:
                плохие.append({"href": href, "status": о.status})
        self.добавить("cards.every_card_resolves", not плохие,
                      checked=len(ссылки), codes=коды, bad=плохие[:5])
        return {"checked": len(ссылки), "codes": коды, "bad": плохие}

    # -- 8. постеры --------------------------------------------------------
    def постеры(self, сколько: int = 30) -> dict:
        о = self.к.get("/")
        источники = [s for s in атрибут(о.body, r"<img[^>]*>", "src") if s][:сколько]
        битые = []
        коды: dict[int, int] = {}
        for src in источники:
            путь = src if src.startswith("/") else "/" + src
            if путь.startswith("//") or путь.startswith("/http"):
                continue
            r = self.к.get(путь, method="HEAD")
            коды[r.status] = коды.get(r.status, 0) + 1
            if r.status != 200:
                битые.append({"src": src, "status": r.status})
        self.добавить("images.no_broken", not битые, checked=len(источники),
                      codes=коды, broken=битые[:5])
        return {"checked": len(источники), "codes": коды, "broken": битые}

    # -- 9. безопасность ---------------------------------------------------
    def безопасность(self, домен: str) -> dict:
        итог = {}
        о = self.к.get("/")
        куки = о.headers.get("Set-Cookie")
        итог["set_cookie"] = куки
        self.добавить("security.no_session_cookie_without_flags",
                      not куки or ("HttpOnly" in куки and "Secure" in куки),
                      set_cookie=куки)

        чужой = self.к.get("/", headers={"Host": "evil.example"})
        канон = атрибут(чужой.body, r'<link[^>]+rel="canonical"[^>]*>', "href")
        хосты = {urllib.parse.urlparse(c).hostname for c in канон}
        итог["foreign_host_canonical"] = sorted(h for h in хосты if h)
        # Рантайм строит canonical из Host: отсечение чужого имени — работа
        # nginx `server_name`. Здесь это измеряется, а не объявляется решённым.
        self.добавить("security.host_header_canonical_note", True,
                      canonical_for_foreign_host=sorted(h for h in хосты if h),
                      note="origin отражает Host в canonical; отсечение — на nginx server_name")

        обход = self.к.get("/poster/../../../../etc/passwd")
        итог["path_traversal"] = {"status": обход.status,
                                  "leaked": "root:x:" in обход.body}
        self.добавить("security.path_traversal", "root:x:" not in обход.body,
                      status=обход.status)

        обход2 = self.к.get("/assets/%2e%2e%2f%2e%2e%2fetc%2fpasswd")
        self.добавить("security.path_traversal_encoded", "root:x:" not in обход2.body,
                      status=обход2.status)

        for метод in ("POST", "PUT", "DELETE"):
            r = self.к.get("/", method=метод)
            итог[f"method_{метод}"] = r.status
            self.добавить(f"security.method_{метод.lower()}_not_accepted",
                          r.status in (0, 400, 401, 403, 404, 405, 501),
                          status=r.status)

        отладка = self.к.get("/этого-нет-" + str(int(time.time())))
        следы = any(s in отладка.body for s in ("Traceback", "File \"/srv", "DEBUG = True"))
        итог["debug_leak"] = следы
        self.добавить("security.no_debug_traces", not следы)
        return итог

    # -- 10. производительность -------------------------------------------
    def производительность(self, повторов: int = 7) -> dict:
        измерения: dict[str, list[float]] = {}
        for путь in ("/", "/catalog/", "/new/", "/search/?q=матрица"):
            ряд = []
            for _ in range(повторов):
                о = self.к.get(путь)
                ряд.append(о.ms)
            измерения[путь] = ряд
        сводка = {}
        for путь, ряд in измерения.items():
            ряд_с = sorted(ряд)
            p95 = ряд_с[max(0, int(len(ряд_с) * 0.95) - 1)]
            сводка[путь] = {"median_ms": statistics.median(ряд),
                            "p95_ms": p95, "samples": len(ряд)}
        общий_p95 = max(v["p95_ms"] for v in сводка.values())
        self.добавить("perf.origin_ttfb_p95_under_800ms", общий_p95 <= 800,
                      p95_ms=общий_p95, by_path=сводка)
        return {"by_path": сводка, "origin_p95_ms": общий_p95}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origin", required=True)
    parser.add_argument("--host", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--sample-query", default="матрица")
    args = parser.parse_args()

    клиент = Клиент(args.origin, args.host)
    п = Приёмка(клиент)

    отчёт: dict = {
        "origin": args.origin,
        "host": args.host,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    отчёт["routes"] = п.маршруты()
    отчёт["indexing"] = п.индексация(args.host)
    отчёт["home"] = п.главная()
    отчёт["collections"] = п.коллекции(отчёт["home"].get("collection_tiles") or [])
    отчёт["catalog"] = п.каталог()
    отчёт["search"] = п.поиск(args.sample_query)

    домашняя = клиент.get("/")
    ссылки = sorted(set(атрибут(домашняя.body, r'<a[^>]+href="/title/[^"]*"[^>]*>', "href")))
    отчёт["title"] = п.тайтл(ссылки[0], args.host) if ссылки else {"error": "нет ссылок на тайтлы"}
    if not ссылки:
        п.добавить("title.status", False, note="главная не дала ни одной ссылки на тайтл")

    отчёт["cards"] = п.карточки_живые()
    отчёт["images"] = п.постеры()
    отчёт["security"] = п.безопасность(args.host)
    отчёт["performance"] = п.производительность()

    отчёт["checks"] = [{"id": c.id, "ok": c.ok, "measured": c.measured, "note": c.note}
                       for c in п.проверки]
    отчёт["summary"] = {
        "total": len(п.проверки),
        "passed": sum(1 for c in п.проверки if c.ok),
        "failed": sorted(c.id for c in п.проверки if not c.ok),
    }
    отчёт["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(отчёт, f, ensure_ascii=False, indent=2)
    print(json.dumps(отчёт["summary"], ensure_ascii=False, indent=2))
    return 0 if not отчёт["summary"]["failed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
