"""Стенд витрины Zona для модульных проверок.

Зачем отдельный файл: шесть наборов ночной проверки поднимают витрину
одинаково, и шесть копий `_поднять` разошлись бы через неделю. Здесь один
подъём, один набор данных и один способ спросить страницу.

Данные намеренно маленькие и намеренно «грязные»: пустая дата, одинаковые
даты, испорченная дата, ноль вместо оценки, отсутствующий постер, пустое
название. Чистый набор доказывает только то, что код работает на чистом
наборе.

Витрина не ходит в сеть и не читает production: каталог, подробности и
манифест создаются во временном каталоге теста.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
ИСХОДНИК = КОРЕНЬ / "automation" / "host" / "lords-frontend.py"

#: Версия оформления, объявленная манифестом боевой витрины zona-01.
ЖИВАЯ_ВЕРСИЯ_ZONA = "1.3.0"

ЧАС = "2026-09-20T12:00:00Z"


def _запись(slug, title, kind, year, *, poster=True, published_at=None):
    return {
        "slug": slug, "title": title, "kind": kind, "year": year,
        "poster": (f"https://poster.example/{slug}.webp" if poster else ""),
        "url": f"/title/{slug}/",
        "published_at": published_at if published_at is not None else "",
        "published_at_estimated": False,
    }


#: Набор каталога. Порядок в списке НЕ является ожидаемым порядком выдачи:
#: он нарочно перемешан, чтобы сортировка проверялась, а не совпадала случайно.
ЗАПИСИ = [
    _запись("kadr-null-date", "Кадр без даты", "Фильм", 2021, published_at=""),
    _запись("svezhiy", "Свежий фильм", "Фильм", 2026, published_at="2026-09-19T10:00:00Z"),
    _запись("ravnyy-a", "Равный А", "Фильм", 2024, published_at="2026-09-18T08:00:00Z"),
    _запись("ravnyy-b", "Равный Б", "Сериал", 2024, published_at="2026-09-18T08:00:00Z"),
    _запись("bitaya-data", "Битая дата", "Фильм", 2023, published_at="20-09-2026"),
    _запись("samyy-svezhiy", "Самый свежий", "Сериал", 2026, published_at="2026-09-20T09:30:00Z"),
    _запись("bez-postera", "Без постера", "Фильм", 2015, poster=False,
            published_at="2026-09-17T00:00:00Z"),
    _запись("multik", "Мультфильм про кота", "Мультфильм", 2022,
            published_at="2026-09-16T00:00:00Z"),
    _запись("serial-s-sezonami", "Сериал с сезонами", "Сериал", 2020,
            published_at="2026-09-15T00:00:00Z"),
    _запись("tolko-imdb", "Только IMDb", "Фильм", 2018, published_at="2026-09-14T00:00:00Z"),
    _запись("tolko-kp", "Только КП", "Фильм", 2017, published_at="2026-09-13T00:00:00Z"),
    _запись("tolko-shiki", "Только Шикимори", "Мультфильм", 2019,
            published_at="2026-09-12T00:00:00Z"),
    _запись("bez-ocenki", "Совсем без оценки", "Фильм", 2016,
            published_at="2026-09-11T00:00:00Z"),
    _запись("nol-ocenka", "Оценка ноль", "Фильм", 2014, published_at="2026-09-10T00:00:00Z"),
    _запись("dlinnoe", "Очень длинное название которое обязано обрезаться в две строки "
            "и остаться доступным целиком", "Фильм", 2013, published_at="2026-09-09T00:00:00Z"),
    _запись("buduschaya-premiera", "Будущая премьера", "Фильм", 2027,
            published_at="2026-09-08T00:00:00Z"),
]


def _деталь(**поля):
    основа = {"description": "", "genres": [], "countries": [], "playable": True,
              "sources": [{"provider": "kp", "source_id": "1",
                           "availability_status": "available"}],
              "external_ids": {"kp": "1"}}
    основа.update(поля)
    return основа


ПОДРОБНОСТИ = {
    "kadr-null-date": _деталь(genres=["драма"], countries=["США"], description="Без даты."),
    "svezhiy": _деталь(genres=["боевик"], countries=["Россия"], description="Свежий.",
                       imdb_rating=7.8, kinopoisk_rating=8.1,
                       ratings_by_source={"imdb": {"value": 7.8, "scale": 10.0, "votes": 1200},
                                          "kp": {"value": 8.1, "scale": 10.0, "votes": 900}}),
    "ravnyy-a": _деталь(genres=["драма"], description="Равный А."),
    "ravnyy-b": _деталь(genres=["драма"], description="Равный Б."),
    "bitaya-data": _деталь(genres=["ужасы"], description="Битая дата."),
    "samyy-svezhiy": _деталь(genres=["фантастика"], countries=["Япония"],
                             description="Самый свежий.", imdb_rating=6.4,
                             ratings_by_source={"imdb": {"value": 6.4, "scale": 10.0,
                                                         "votes": 55}}),
    "bez-postera": _деталь(genres=["комедия"], description="Нет постера."),
    "multik": _деталь(genres=["мультфильм", "семейный"], description="Мультфильм."),
    "serial-s-sezonami": _деталь(
        genres=["драма"], description="Сериал.",
        seasons=[{"number": 1, "episodes": [{"number": 1, "title": "Первая"},
                                            {"number": 2, "title": "Вторая"}]}]),
    "tolko-imdb": _деталь(genres=["драма"], imdb_rating=5.5,
                          ratings_by_source={"imdb": {"value": 5.5, "scale": 10.0,
                                                      "votes": 10}}),
    "tolko-kp": _деталь(genres=["драма"], kinopoisk_rating=6.6),
    "tolko-shiki": _деталь(genres=["аниме"],
                           ratings_by_source={"shikimori": {"value": 8.2, "scale": 10.0,
                                                            "votes": 340}}),
    "bez-ocenki": _деталь(genres=["драма"], description="Нет оценок вовсе."),
    "nol-ocenka": _деталь(genres=["драма"], imdb_rating=0, kinopoisk_rating=0,
                          ratings_by_source={"imdb": {"value": 0, "scale": 10.0, "votes": 0}}),
    "dlinnoe": _деталь(genres=["драма"], description="Длинное название."),
    "buduschaya-premiera": _деталь(genres=["драма"], premiere_date="2027-04-01",
                                   description="Ещё не вышло."),
}


@dataclass
class Ответ:
    статус: int
    тело: str
    заголовки: dict


def поднять(tmp_path, *, design: str = ЖИВАЯ_ВЕРСИЯ_ZONA, family: str = "zona",
            записи=None, подробности=None, site_name: str = "Zona",
            имя_модуля: str | None = None, clock: str = ЧАС):
    """Импортировать рантайм с собственными данными и манифестом."""
    записи = ЗАПИСИ if записи is None else записи
    подробности = ПОДРОБНОСТИ if подробности is None else подробности
    корень = Path(tmp_path) / f"{family}-stand"
    корень.mkdir(parents=True, exist_ok=True)
    каталог = {"version": 2, "count": len(записи), "items": list(записи),
               "site": f"{family}-01", "schema": "nova-catalog/2.0.0",
               "revision": "kit", "builtAt": "2026-09-20T00:00:00Z"}
    (корень / "catalog.json").write_text(json.dumps(каталог, ensure_ascii=False),
                                         encoding="utf-8")
    (корень / "details.json").write_text(json.dumps(
        {"schema": "nova.details.sidecar/2.0.0", "site": f"{family}-01",
         "details_total": len(подробности), "items_total": len(записи),
         "source": "kit", "details": подробности}, ensure_ascii=False), encoding="utf-8")
    (корень / "player.json").write_text(
        json.dumps({"publisher_id": "10238", "source_mode": "provider-id"}),
        encoding="utf-8")
    манифест = корень / "manifest.json"
    манифест.write_text(json.dumps({
        "schema_version": 1, "template_family": family,
        "design_version": design, "source_commit": "0" * 40,
        "build_id": f"kit-{family}-{design}", "artifact_sha256": "0" * 64,
        "profile": f"{family}-test", "built_at": "2026-09-20T00:00:00Z",
    }), encoding="utf-8")

    старое = dict(os.environ)
    os.environ.update({
        "LORDS_TEMPLATE_MANIFEST": str(манифест),
        "LORDS_CATALOG": str(корень / "catalog.json"),
        "LORDS_DETAILS": str(корень / "details.json"),
        "LORDS_PLAYER_CONFIG": str(корень / "player.json"),
        "LORDS_SITE_NAME": site_name,
        "LORDS_CLOCK_ISO": clock,
        "LORDS_LEGACY_ROOT": str(корень / "legacy-root-otsutstvuet"),
        "LORDS_LEGACY_UPSTREAM": "",
    })
    for ключ in ("LORDS_POPULAR_WEEKLY", "LORDS_SITEMAP_DIR", "LORDS_METRIKA_COUNTER"):
        os.environ.pop(ключ, None)
    try:
        имя = имя_модуля or f"nova_zona_kit_{family}_{design.replace('.', '')}_{Path(tmp_path).name}"
        спец = importlib.util.spec_from_file_location(имя, ИСХОДНИК)
        модуль = importlib.util.module_from_spec(спец)
        sys.modules[имя] = модуль
        спец.loader.exec_module(модуль)
    finally:
        os.environ.clear()
        os.environ.update(старое)
    модуль.Обработчик.данные = модуль.Данные(str(корень / "catalog.json"))
    модуль.Обработчик.подробности = модуль.Подробности(str(корень / "details.json"))
    модуль.Обработчик.индекс = модуль.построить_индекс(
        модуль.Обработчик.данные, модуль.Обработчик.подробности)
    return модуль


def запросить(модуль, путь: str, *, host: str = "zonafilm.space") -> Ответ:
    """Один запрос к витрине без сокета."""
    собрано = {"статус": 200, "тело": b"", "заголовки": {}}

    class Заглушка(модуль.Обработчик):
        def __init__(self):  # сокет не нужен
            self.path = путь
            self.command = "GET"
            self.headers = {"Host": host}

        def _отдать(self, тело, тип="text/html; charset=utf-8", код=200):
            собрано["статус"] = код
            собрано["тело"] = тело
            собрано["заголовки"]["Content-Type"] = тип

        def send_response(self, код):
            собрано["статус"] = код

        def send_header(self, имя, значение):
            собрано["заголовки"][имя] = значение

        def end_headers(self):
            pass

    Заглушка().do_GET()
    тело = собрано["тело"]
    if isinstance(тело, bytes):
        тело = тело.decode("utf-8", "replace")
    return Ответ(собрано["статус"], тело or "", собрано["заголовки"])
