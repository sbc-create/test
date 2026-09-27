#!/usr/bin/env python3
"""Аудит счётчика Метрики на публичных страницах: главная, раздел, карточка, серия.

    python3 automation/host/metrika-audit.py [--domain <домен>] [--json]

Что проверяется на каждой странице:

    правильный ID      совпадает с реестром config/analytics.json
    однократность      ровно одна инициализация; две означали бы двойной учёт
    noscript           резервный пиксель ведёт на тот же счётчик

Чего проверка НЕ доказывает: что просмотр действительно отправлен и что данные
дошли до кабинета. Разметка — необходимое условие, не достаточное. Отправку
измеряет `metrika-send-check.js` перехватом сетевых запросов браузера,
получение в кабинете — только чтение статистики по OAuth.

Форма записи ID отличается между семействами: Zona и Lords пишут `ym(112582938,`
числом, Yummy — `ym("111881037",` строкой. Первая версия этой проверки искала
только число и объявила расхождением три исправных домена Yummy. Поэтому здесь
принимаются обе формы, а тест `test_metrika_audit` держит это свойство.
"""
from __future__ import annotations

import argparse
import json
import re
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parent.parent.parent
if not (КОРЕНЬ / "factory" / "cell" / "executor.py").is_file():
    raise SystemExit(f"не похоже на репозиторий фабрики: {КОРЕНЬ}")
РЕЕСТР = КОРЕНЬ / "config" / "analytics.json"

#: Инициализация счётчика. Идентификатор — числом или строкой: обе формы
#: рабочие, и различать их значило бы считать одно из семейств сломанным.
ИНИЦИАЛИЗАЦИЯ = re.compile(r"""ym\(\s*['"]?(\d+)['"]?\s*,\s*['"]init['"]""")
ТЕГ = re.compile(r"mc\.yandex\.ru/metrika/tag")
ПИКСЕЛЬ = re.compile(r"mc\.yandex\.ru/watch/(\d+)")
ССЫЛКА = re.compile(r'href="(/[^"#?]*)"')

АГЕНТ = {"User-Agent": "site-factory-metrika-audit"}


#: Пути, которые разделом не являются: служебное, правовое и статика.
НЕ_РАЗДЕЛ = ("/search", "/_next", "/legal", "/about", "/brand", "/icon",
             "/favicon", "/apple-icon", "/blogger", "/sitemap", "/robots")


def _раздел(путь: str) -> bool:
    """Раздел витрины: один-два сегмента, не карточка, не служебный путь.

    Требование «кончается на /» тут было ошибкой: у Zona и Lords разделы со
    слешем (`/movies/`), у Yummy без (`/catalog/ongoing`). Из-за него у трёх
    доменов Yummy раздел не находился вовсе, и отчёт показывал три вида
    страницы из четырёх, выглядя при этом полным.
    """
    if путь.startswith(НЕ_РАЗДЕЛ) or "." in путь.rsplit("/", 1)[-1]:
        return False
    сегменты = [с for с in путь.split("/") if с]
    if not 1 <= len(сегменты) <= 2:
        return False
    return not _карточка(путь)


def _карточка(путь: str) -> bool:
    """Страница одного тайтла, а не раздел с таким же префиксом.

    `/anime/` — раздел витрины Lords, `/anime/<слаг>` — карточка Yummy.
    Различает их число сегментов, а не префикс: проверка по префиксу
    подставляла раздел вместо карточки и отчёт выглядел полным.
    """
    сегменты = [с for с in путь.split("/") if с]
    if len(сегменты) < 2:
        return False
    return сегменты[0] in {"title", "anime", "film", "serial", "movie"}


def взять(url: str, таймаут: float = 25) -> tuple[int, str, dict]:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    r = urllib.request.urlopen(urllib.request.Request(url, headers=АГЕНТ),
                               timeout=таймаут, context=ctx)
    тело = r.read()
    return r.status, тело.decode("utf-8", "replace"), dict(r.headers)


def страницы(домен: str, дом: str) -> list[tuple[str, str]]:
    """Четыре вида страницы. Пути берутся с самого сайта, а не выдумываются."""
    итог = [("главная", "/")]
    ссылки = sorted(set(ССЫЛКА.findall(дом)))
    разделы = [п for п in ссылки if _раздел(п)]
    карточки = [п for п in ссылки if _карточка(п)]
    if разделы:
        итог.append(("раздел", разделы[0]))
    # У витрин Lords на главной нет ни одной ссылки на карточку — только
    # разделы, жанры и подборки. Поэтому карточку ищем в разделе, а не
    # объявляем её отсутствующей: страница карточки у этих сайтов есть.
    if not карточки and разделы:
        for раздел in разделы[:3]:
            try:
                _, тело, _ = взять(f"https://{домен}{раздел}")
            except (urllib.error.HTTPError, urllib.error.URLError, OSError):
                continue
            карточки = [п for п in sorted(set(ССЫЛКА.findall(тело))) if _карточка(п)]
            if карточки:
                break
    if not карточки:
        return итог
    итог.append(("карточка", карточки[0]))
    try:
        _, карточка, _ = взять(f"https://{домен}{карточки[0]}")
    except (urllib.error.URLError, OSError):
        return итог
    серии = [п for п in sorted(set(ССЫЛКА.findall(карточка)))
             if re.search(r"episode|seriya|/series/\d", п, re.I)]
    if серии:
        итог.append(("серия", серии[0]))
    return итог


def проверить_домен(домен: str, ожидаемый: int | None) -> dict:
    отчёт: dict = {"domain": домен, "expected_counter": ожидаемый, "pages": []}
    try:
        код, дом, заголовки = взять(f"https://{домен}/")
    except urllib.error.HTTPError as ош:
        отчёт["error"] = f"HTTP {ош.code}"
        return отчёт
    except (urllib.error.URLError, OSError) as ош:
        отчёт["error"] = f"{type(ош).__name__}: {ош}"
        return отчёт
    отчёт["build_id"] = заголовки.get("X-Site-Factory-Build-Id")
    for имя, путь in страницы(домен, дом):
        тело = дом if путь == "/" else None
        код_с = код
        if тело is None:
            try:
                код_с, тело, _ = взять(f"https://{домен}{путь}")
            except (urllib.error.HTTPError, urllib.error.URLError, OSError) as ош:
                отчёт["pages"].append({"kind": имя, "path": путь,
                                       "error": f"{type(ош).__name__}: {ош}"})
                continue
        инициализации = ИНИЦИАЛИЗАЦИЯ.findall(тело)
        пиксели = sorted(set(ПИКСЕЛЬ.findall(тело)))
        строка = {
            "kind": имя, "path": путь, "status": код_с,
            "init_count": len(инициализации),
            "init_ids": sorted(set(инициализации)),
            "tag_scripts": len(ТЕГ.findall(тело)),
            "noscript_ids": пиксели,
        }
        if ожидаемый is None:
            строка["verdict"] = "счётчика нет" if not инициализации else "ЛИШНИЙ СЧЁТЧИК"
        elif len(инициализации) == 1 and инициализации[0] == str(ожидаемый):
            строка["verdict"] = ("ок" if пиксели == [str(ожидаемый)]
                                 else "ок, но noscript не совпал")
        elif len(инициализации) > 1:
            строка["verdict"] = "ДВОЙНОЙ УЧЁТ"
        elif not инициализации:
            строка["verdict"] = "КОДА НЕТ"
        else:
            строка["verdict"] = "ЧУЖОЙ ID"
        отчёт["pages"].append(строка)
    return отчёт


def main() -> int:
    р = argparse.ArgumentParser()
    р.add_argument("--domain")
    р.add_argument("--json", action="store_true")
    а = р.parse_args()

    реестр = json.loads(РЕЕСТР.read_text(encoding="utf-8"))["properties"]
    выбор = [z for z in реестр if not а.domain or z["domain"] == а.domain]
    if not выбор:
        print(f"домен {а.domain} отсутствует в {РЕЕСТР.name}", file=sys.stderr)
        return 2

    отчёты = [проверить_домен(z["domain"], z.get("counter_id")) for z in выбор]
    if а.json:
        print(json.dumps({"reports": отчёты}, ensure_ascii=False, indent=2))
    else:
        плохо = 0
        for о in отчёты:
            if о.get("error"):
                print(f"{о['domain']:22} НЕДОСТУПЕН: {о['error']}")
                continue
            ожид = о["expected_counter"] or "счётчика нет"
            print(f"{о['domain']:22} реестр={ожид}  build-id={о.get('build_id')}")
            for с in о["pages"]:
                if с.get("error"):
                    print(f"    {с['kind']:9} {с['path'][:44]:46} {с['error']}")
                    continue
                print(f"    {с['kind']:9} {с['path'][:44]:46} "
                      f"init={с['init_count']}{с['init_ids']} "
                      f"tag={с['tag_scripts']} noscript={с['noscript_ids'] or '—'}  "
                      f"{с['verdict']}")
                if с["verdict"] not in ("ок", "счётчика нет"):
                    плохо += 1
        print(f"\nстраниц с замечаниями: {плохо}")
        print("Разметка проверена. Фактическая отправка просмотра — "
              "metrika-send-check.js; получение в кабинете — только по OAuth.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
