#!/usr/bin/env python3
"""Подготовка наборов запросов Topvisor из реального каталога витрины.

Ничего не загружает и ничего не тратит. Задача файла — дать владельцу выбор
между двумя объёмами с честной арифметикой, а не «семантическое ядро», которое
кто-то придумал.

Запросы берутся только из данных: названия — из каталога и подробностей,
жанры — из подробностей, годы — оттуда же. Выдуманных запросов здесь нет, и у
каждого записан источник и причина включения. Оригинальные названия берутся из
поля `original_name`; romaji и подтверждённых английских названий в данных нет,
и придумывать их нельзя — в отчёте это отмечено отдельно.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import pathlib

РЕГИОН_МОСКВА = 213
ПОИСКОВИКИ = ["Яндекс", "Google"]
УСТРОЙСТВА = "desktop+mobile"

ВИД_СЛОВО = {"Фильм": "фильм", "Сериал": "сериал", "Мультфильм": "мультфильм"}
РАЗДЕЛЫ = [("/catalog/", "каталог"), ("/new/", "новинки"),
           ("/collections/", "подборки")]


def запрос(домен, группа, текст, намерение, цель, приоритет, источник, причина):
    return {"domain": домен, "group": группа, "query": текст,
            "intent": намерение, "target_page": f"https://{домен}{цель}",
            "region": РЕГИОН_МОСКВА, "searchers": ПОИСКОВИКИ,
            "device": УСТРОЙСТВА, "priority": приоритет,
            "source": источник, "reason": причина}


def собрать(домен: str, бренд: str, каталог: dict, детали: dict,
            *, тайтлов: int) -> list[dict]:
    из: list[dict] = []
    рев = каталог.get("revision") or "—"

    # 1. Брендовые. Название витрины — не выдумка: им подписаны её страницы.
    for т in (бренд, f"{бренд} смотреть онлайн"):
        из.append(запрос(домен, "Бренд", т, "навигационное: ищут саму витрину",
                         "/", 1, f"имя витрины (LORDS_SITE_NAME)",
                         "запрос по бренду показывает, находят ли витрину по имени"))

    # 2. Разделы, существующие на витрине.
    for путь, имя in РАЗДЕЛЫ:
        из.append(запрос(домен, "Разделы", f"{имя} фильмов и сериалов",
                         "навигационное", путь, 3, "навигация витрины",
                         f"раздел {путь} существует и отдаёт 200"))

    # 3. Виды содержимого — по фактическому наполнению каталога.
    виды = collections.Counter(x.get("kind") for x in каталог.get("items", []))
    for вид, n in виды.most_common():
        слово = ВИД_СЛОВО.get(вид)
        if not слово:
            continue
        из.append(запрос(домен, "Виды", f"смотреть {слово}ы онлайн",
                         "транзакционное", f"/catalog/?kind={вид}",
                         1 if n > 10_000 else 2,
                         f"каталог {рев}, поле kind",
                         f"в каталоге {n} записей этого вида"))

    # 4. Жанры — из подробностей, по частоте. Только реально встречающиеся.
    жанры = collections.Counter()
    годы = collections.Counter()
    for д in детали.values():
        for ж in (д.get("genres") or []):
            жанры[ж] += 1
        if д.get("year"):
            годы[int(д["year"])] += 1
    for ж, n in жанры.most_common(12):
        из.append(запрос(домен, "Жанры", f"{ж} смотреть онлайн",
                         "транзакционное", f"/catalog/?genre={ж}", 2,
                         "подробности каталога, поле genres",
                         f"жанр встречается у {n} записей"))

    # 5. Годы — только последние, по которым каталог действительно наполнен.
    for г, n in sorted(годы.items(), reverse=True)[:5]:
        if n < 50:
            continue
        из.append(запрос(домен, "Годы", f"фильмы {г} года смотреть",
                         "транзакционное", f"/catalog/?year={г}", 3,
                         "подробности каталога, поле year",
                         f"за {г} год в каталоге {n} записей"))

    # 6. Приоритетные тайтлы. Порядок — по наполненности записи, а не по
    #    оценке: оценку здесь использовать нельзя, шкалы КП и IMDb разные.
    записи = []
    for slug, д in детали.items():
        полнота = sum(1 for k in ("description", "genres", "original_name",
                                  "year", "poster_url") if д.get(k))
        записи.append((полнота, slug, д))
    записи.sort(key=lambda x: (-x[0], x[1]))
    for _, slug, д in записи[:тайтлов]:
        имя = д.get("name")
        if not имя:
            continue
        вид = ВИД_СЛОВО.get(д.get("type") or "", "")
        год = д.get("year")
        цель = f"/title/{slug}/"
        из.append(запрос(домен, "Тайтлы", f"{имя} смотреть онлайн",
                         "транзакционное: конкретное произведение", цель, 1,
                         "подробности каталога, поле name",
                         "страница произведения существует"))
        # Год и вид снимают неоднозначность: одноимённых произведений много.
        if год:
            из.append(запрос(домен, "Тайтлы: уточнение", f"{имя} {год}",
                             "транзакционное с уточнением года", цель, 2,
                             "подробности, поля name и year",
                             "одноимённые произведения различаются годом"))
        if вид:
            из.append(запрос(домен, "Тайтлы: уточнение", f"{имя} {вид}",
                             "транзакционное с уточнением вида", цель, 2,
                             "подробности, поля name и type",
                             "фильм и сериал под одним названием — разные сущности"))
        ориг = д.get("original_name")
        if ориг and ориг.strip() and ориг != имя:
            из.append(запрос(домен, "Тайтлы: оригинальное название", ориг,
                             "транзакционное по оригинальному названию", цель, 3,
                             "подробности каталога, поле original_name",
                             "оригинальное название подтверждено данными"))
    # дубли по тексту запроса внутри домена
    видели, чистые = set(), []
    for q in из:
        if q["query"].strip().lower() in видели:
            continue
        видели.add(q["query"].strip().lower())
        чистые.append(q)
    return чистые


def главное(argv: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--domain", required=True)
    р.add_argument("--brand", required=True)
    р.add_argument("--catalog", required=True)
    р.add_argument("--details", required=True)
    р.add_argument("--titles", type=int, default=25)
    р.add_argument("--out", required=True)
    а = р.parse_args(argv)
    кат = json.loads(pathlib.Path(а.catalog).read_text(encoding="utf-8"))
    дет = json.loads(pathlib.Path(а.details).read_text(encoding="utf-8")).get("details", {})
    пакет = собрать(а.domain, а.brand, кат, дет, тайтлов=а.titles)
    путь = pathlib.Path(а.out)
    путь.parent.mkdir(parents=True, exist_ok=True)
    текст = json.dumps(пакет, ensure_ascii=False, indent=1, sort_keys=True)
    путь.write_text(текст, encoding="utf-8")
    print(json.dumps({"domain": а.domain, "queries": len(пакет),
                      "groups": sorted({q["group"] for q in пакет}),
                      "sha256": hashlib.sha256(текст.encode()).hexdigest(),
                      "file": str(путь)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(главное())
