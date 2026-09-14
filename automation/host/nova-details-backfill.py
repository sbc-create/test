#!/usr/bin/env python3
"""Backfill бокового файла подробностей витрин Nova (Lords и Zona).

Зачем
-----

Публичный рендерер читает `{site}-details.json` и только его. Сегодня этот
файл собирается из `detail-cache`, который покрывает треть каталога, поэтому
оценка, пришедшая в списке поставщика, до карточки не доходит: на витрине
это «КП — IMDb —» у записи, для которой источник оценку отдал.

Здесь боковой файл собирается из канонической проекции: список поставщика
объединяется с `detail`, и результат покрывает весь публикуемый каталог сайта.

Почему инструмент знает про сайт
--------------------------------

Предшественник был Lords-only: он писал в файл все записи поставщика, у
которых нашёлся slug. Для Lords это почти совпадало с истиной, для Zona —
нет: её каталог составляет 3868 записей из тех же 53 390 поставщика, и слепой
прогон перенёс бы на Zona весь чужой каталог. Граница сайта здесь не
украшение, а единственное, что отличает восстановление от порчи, поэтому она
задана профилем и проверяется до записи, а не подразумевается.

Защиты
------

* **граница сайта.** Пишутся только slug из собственного каталога витрины;
  имя целевого файла обязано совпасть с профилем. Lords не может записать
  данные Zona и наоборот;
* **неоднозначный slug не угадывается.** Один и тот же slug у поставщика
  встречается больше одного раза (206 случаев). Молча взять любой из
  идентификаторов значит однажды показать чужое произведение под чужим
  названием, поэтому такая запись отклоняется с кодом причины;
* **привязка не меняется.** Если slug уже связан с идентификатором, он за ним
  и остаётся: смена привязки — отклонение записи, а не тихая перезапись;
* **null не затирает непустое.** Отсутствие значения в проекции оставляет
  прежнее. Обратное — самый дорогой вид порчи: данные исчезают, а прогон
  выглядит успешным;
* **ничего не исчезает.** Записи, которых новая сборка не касается,
  переносятся как есть: неполный `detail-cache` не может опустошить файл;
* **отказ одной записи не роняет прогон.** Причина кодируется и попадает в
  отчёт; остальные записи обрабатываются;
* **идемпотентность.** Повторный прогон на том же входе даёт тот же файл
  побайтно;
* **замок и атомарная замена.** Полуфайла не возникает, два прогона
  одновременно не идут;
* **before-image.** До записи сохраняется прежний файл: откат — возврат
  файла, а не обратное вычисление.

Запись только по явному `--apply`. Значение по умолчанию — сухой прогон: у
инструмента, который пишет по умолчанию, однажды не посмотрят на флаги.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import shutil
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from factory.lords.canonical_projection import спроецировать
from factory.lords.canonical_recommend import построить_корзины, подобрать

СХЕМА = "nova.details.sidecar/2.0.0"
ИСТОЧНИК = "canonical-projection/2.0.0"
ПАРТИЯ = 2000

# Причины отказа. Отказ без причины неотличим от потери, поэтому код
# обязателен: «не записано 2315» без разбивки не отчёт, а его видимость.
НЕТ_ПРИВЯЗКИ = "no_id_mapping"
НЕОДНОЗНАЧНО = "ambiguous_slug"
НЕТ_В_ИСТОЧНИКЕ = "not_in_upstream"
СМЕНА_ПРИВЯЗКИ = "entity_rebind_refused"
ОШИБКА_ПРОЕКЦИИ = "projection_error"


class ContractViolation(RuntimeError):
    """Нарушение контракта: работа прекращается, а не продолжается молча."""


@dataclass(frozen=True)
class Профиль:
    """Пути одной витрины. Профиль — это и есть граница записи."""
    site_id: str
    каталог: Path          # собственный каталог витрины: что она публикует
    источник: Path         # список поставщика: оценки, постеры, внешние ид
    карта: Path            # соответствие идентификатор → slug
    детали: Path           # кэш подробностей, общий для всех витрин
    цель: Path             # боковой файл рендерера
    корень_цели: Path      # допустимый каталог для записи
    сервис: str            # unit, который перечитывает файл
    домен: str

    def проверить(self) -> None:
        """Профиль обязан указывать на свой файл и никуда больше."""
        ожидаемое = f"{self.site_id}-details.json"
        if self.цель.name != ожидаемое:
            raise ContractViolation(
                f"{self.site_id}: целевой файл {self.цель.name}, "
                f"ожидался {ожидаемое}")
        try:
            self.цель.resolve().relative_to(self.корень_цели.resolve())
        except ValueError:
            raise ContractViolation(
                f"{self.site_id}: цель {self.цель} вне разрешённого "
                f"каталога {self.корень_цели}") from None


ВАР = Path("/srv/site-factory/repo/var/lords")
ФРОНТ = Path("/srv/lords/.frontend")
СОСТОЯНИЕ = Path("/srv/site-factory/content-pipeline/state")

# Поставщик и карта slug'ов общие для семейства: каталог у CDNVideoHub один,
# а витрины публикуют из него разные подмножества. Общий вход — не повод для
# общей записи, и именно поэтому каталог сайта указан отдельно.
ПРОФИЛИ: dict[str, Профиль] = {
    "lords-01": Профиль(
        site_id="lords-01",
        каталог=СОСТОЯНИЕ / "lords-01" / "catalog.lkg.json",
        источник=ВАР / "lords" / "catalog-cache" / "lords-01.json",
        карта=ВАР / "render-state" / "lords-01.titles.json",
        детали=ВАР / "detail-cache",
        цель=ФРОНТ / "lords-01-details.json",
        корень_цели=ФРОНТ,
        сервис="lords-nova-01.service",
        домен="lordfilm47.space",
    ),
    "zona-01": Профиль(
        site_id="zona-01",
        каталог=СОСТОЯНИЕ / "zona-01" / "catalog.lkg.json",
        источник=ВАР / "lords" / "catalog-cache" / "lords-01.json",
        карта=ВАР / "render-state" / "lords-01.titles.json",
        детали=ВАР / "detail-cache",
        цель=ФРОНТ / "zona-01-details.json",
        корень_цели=ФРОНТ,
        сервис="nova-zona-01.service",
        домен="zonafilm.space",
    ),
}


def переукоренить(п: Профиль, корень: Path) -> Профиль:
    """Тот же профиль внутри песочницы — для фикстур и тестов.

    Отдельный профиль для тестов означал бы, что проверяется не то, что
    работает. Здесь меняется только корень, а структура и проверки — те же.
    """
    def _(путь: Path) -> Path:
        return корень / str(путь).lstrip("/")
    return Профиль(
        site_id=п.site_id, каталог=_(п.каталог), источник=_(п.источник),
        карта=_(п.карта), детали=_(п.детали), цель=_(п.цель),
        корень_цели=_(п.корень_цели), сервис=п.сервис, домен=п.домен)


def _канон(данные) -> str:
    return json.dumps(данные, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))


def отпечаток(данные) -> str:
    return hashlib.sha256(_канон(данные).encode("utf-8")).hexdigest()


def загрузить_список(путь: Path, что: str) -> list[dict]:
    д = json.loads(путь.read_text(encoding="utf-8"))
    записи = д.get("items") if isinstance(д, dict) else д
    if not isinstance(записи, list):
        raise ContractViolation(f"{путь}: в {что} нет списка items")
    return записи


def ревизия(путь: Path) -> str:
    д = json.loads(путь.read_text(encoding="utf-8"))
    return str(д.get("revision") or "") if isinstance(д, dict) else ""


def построен(путь: Path) -> str:
    д = json.loads(путь.read_text(encoding="utf-8"))
    return str(д.get("builtAt") or "") if isinstance(д, dict) else ""


def загрузить_карту(путь: Path) -> dict[str, list[str]]:
    """Соответствие slug → идентификаторы.

    Список, а не одно значение, намеренно: у поставщика один slug встречается
    несколько раз, и словарь «последний выиграл» превращает это в случайный
    выбор произведения. Неоднозначность должна быть видна вызывающему.
    """
    if not путь.is_file():
        return {}
    д = json.loads(путь.read_text(encoding="utf-8"))
    по_слагу: dict[str, list[str]] = {}
    for ид, значение in д.items():
        слаг = (значение or {}).get("slug") if isinstance(значение, dict) else None
        if слаг:
            по_слагу.setdefault(слаг, []).append(str(ид))
    for слаг in по_слагу:
        по_слагу[слаг].sort()      # порядок не зависит от обхода словаря
    return по_слагу


def прочитать_деталь(каталог_деталей: Path, ид: str) -> dict | None:
    п = каталог_деталей / f"{ид}.json"
    if not п.is_file():
        return None
    try:
        return json.loads(п.read_text(encoding="utf-8")).get("detail") or {}
    except (OSError, ValueError):
        return None


def _целое(значение) -> int | None:
    try:
        return int(str(значение).strip())
    except (TypeError, ValueError):
        return None


def сезоны_рендерера(значение) -> list[dict]:
    """Сезоны в той форме, которую читает витрина: `n`, `eps`, `avail`.

    Поставщик отдаёт `number`/`episodes_count`/`available_episodes_count`, а
    шаблон обращается к `сезон["n"]` по индексу, без `get`. Пронести сырую
    форму насквозь значит уронить витрину на первой же карточке сериала —
    именно так и произошло: боковой файл записался целиком и корректно, а
    публичные страницы начали отдавать 502.

    Форма витрины на входе распознаётся тоже: повторный прогон не должен
    портить уже правильные записи.
    """
    if not isinstance(значение, list):
        return []
    итог = []
    for сезон in значение:
        if not isinstance(сезон, dict):
            continue
        н = _целое(сезон.get("n") if сезон.get("n") is not None
                   else сезон.get("number"))
        if н is None:
            continue
        серий = _целое(сезон.get("eps") if сезон.get("eps") is not None
                       else сезон.get("episodes_count")) or 0
        доступно = _целое(
            сезон.get("avail") if сезон.get("avail") is not None
            else сезон.get("available_episodes_count"))
        if доступно is None:
            доступно = серий
        итог.append({"n": н, "eps": серий, "avail": доступно})
    итог.sort(key=lambda с: с["n"])
    return итог


#: Поля, которые витрина читает по индексу, без `get`. Несоответствие здесь
#: — это 502, а не отсутствующее значение, поэтому проверка стоит до записи.
def проверить_контракт_рендерера(детали: dict) -> list[dict]:
    """Нарушения формы, которые витрина не переживёт.

    Проверяется не «похоже на правду», а ровно те обращения по индексу,
    которые есть в шаблоне. Отчёт о покрытии, собранный поверх файла, из-за
    которого сайт отдаёт 502, не стоит ничего.
    """
    беды = []
    for слаг, з in детали.items():
        for сезон in (з.get("seasons") or []):
            if not isinstance(сезон, dict) or "n" not in сезон or "eps" not in сезон:
                беды.append({"slug": слаг, "field": "seasons", "value": сезон})
                break
        for член in (з.get("crew") or []):
            if not isinstance(член, dict) or "name" not in член:
                беды.append({"slug": слаг, "field": "crew", "value": член})
                break
        for поле in ("genres", "countries"):
            значение = з.get(поле)
            if значение is not None and not isinstance(значение, list):
                беды.append({"slug": слаг, "field": поле, "value": значение})
        внешние = з.get("external_ids")
        if внешние is not None and not isinstance(внешние, dict):
            беды.append({"slug": слаг, "field": "external_ids", "value": внешние})
    return беды


def слить_запись(было: dict | None, стало: dict) -> tuple[dict, list[str]]:
    """Новое поверх старого, но пустым не затирая."""
    было = было or {}
    итог = dict(было)
    изменено = []
    for ключ, значение in стало.items():
        if значение in (None, "", [], {}):
            continue
        if было.get(ключ) != значение:
            итог[ключ] = значение
            изменено.append(ключ)
    return итог, изменено


def разрешить(слаг: str, прежний: dict, по_слагу: dict[str, list[str]]
              ) -> tuple[str | None, str | None]:
    """Идентификатор для slug'а и причина отказа, если его нет.

    Порядок предпочтения задан явно. Уже существующая привязка сильнее карты:
    витрина показывает это произведение под этим адресом прямо сейчас, и
    менять его из-за коллизии в общем списке поставщика нельзя.
    """
    прежняя = (прежний.get(слаг) or {}).get("id")
    if прежняя:
        return str(прежняя), None
    кандидаты = по_слагу.get(слаг) or []
    if not кандидаты:
        return None, НЕТ_ПРИВЯЗКИ
    if len(кандидаты) > 1:
        return None, НЕОДНОЗНАЧНО
    return кандидаты[0], None


def собрать(*, каталог_сайта: list[dict], поставщик: dict[str, dict],
            по_слагу: dict[str, list[str]], детали: Path, прежний: dict,
            с_рекомендациями: bool = True,
            предел: int | None = None,
            только: set[str] | None = None) -> tuple[dict, dict]:
    """Новое содержимое бокового файла и отчёт о различиях."""
    записи = каталог_сайта
    if только is not None:
        # Канарейка: в production уходит ровно названный набор записей, всё
        # остальное переносится нетронутым. Проверять выкатку на первых N по
        # порядку каталога значит проверять не те записи, которые выбраны.
        записи = [з for з in записи if з.get("slug") in только]
    if предел:
        записи = записи[:предел]
    # Перенос прежнего целиком: запись, которой новая сборка не касается,
    # обязана остаться. Неполный вход не должен опустошать витрину.
    итог: dict[str, dict] = {с: dict(з) for с, з in прежний.items()}
    проекции: dict[str, object] = {}
    затронуто: dict[str, str] = {}

    ст = {"каталог": len(записи), "записей": 0, "новых": 0, "изменено": 0,
          "сохранено_прежних": 0, "перенесено_вне_каталога": 0,
          "полей_изменено": {}, "отказы": {}, "без_upstream": 0}

    def отказ(код: str) -> None:
        ст["отказы"][код] = ст["отказы"].get(код, 0) + 1

    for запись in записи:
        слаг = запись.get("slug")
        if not слаг:
            отказ(НЕТ_ПРИВЯЗКИ)
            continue
        ид, причина = разрешить(слаг, прежний, по_слагу)
        if not ид:
            отказ(причина or НЕТ_ПРИВЯЗКИ)
            continue
        сырое = поставщик.get(ид)
        if сырое is None:
            # Записи нет у поставщика: восстанавливать нечего, и выдумывать
            # тоже. Прежнее значение при этом остаётся нетронутым.
            ст["без_upstream"] += 1
            отказ(НЕТ_В_ИСТОЧНИКЕ)
            continue
        было = прежний.get(слаг)
        if было and было.get("id") and str(было["id"]) != str(ид):
            отказ(СМЕНА_ПРИВЯЗКИ)
            continue
        try:
            п = спроецировать(сырое, прочитать_деталь(детали, ид))
        except (ValueError, TypeError):
            отказ(ОШИБКА_ПРОЕКЦИИ)
            continue
        if str(п.id) != str(ид):
            отказ(СМЕНА_ПРИВЯЗКИ)
            continue
        d = п.as_dict()
        новое = {
            "id": d["id"],
            "name": d["name"],
            "original_name": d["original_name"],
            "type": d["type"],
            "year": d["year"],
            "description": d["description"],
            "description_source": d["description_source"],
            "poster_url": d["poster"],
            "poster_source": d["poster_source"],
            "kinopoisk_rating": d["ratings"].get("kinopoisk"),
            "imdb_rating": d["ratings"].get("imdb"),
            "ratings_source": d["ratings_source"],
            "external_ids": d["external_ids"],
            "sources": d["sources"],
            "playable": d["playable"],
            "seasons": сезоны_рендерера(d["seasons"]),
            "genres": d["genres"],
            "countries": d["countries"],
        }
        слито, изменено = слить_запись(было, новое)
        if было is None:
            ст["новых"] += 1
        elif изменено:
            ст["изменено"] += 1
        else:
            ст["сохранено_прежних"] += 1
        for поле in изменено:
            ст["полей_изменено"][поле] = ст["полей_изменено"].get(поле, 0) + 1
        итог[слаг] = слито
        проекции[ид] = п
        затронуто[слаг] = ид
        ст["записей"] += 1

    ст["перенесено_вне_каталога"] = len(
        [с for с in прежний if с not in затронуто])

    if с_рекомендациями and проекции:
        # Корзины строятся один раз на прогон: перебор всего каталога для
        # каждой записи давал бы квадрат и не заканчивался вовсе.
        #
        # Пул — только собственные записи витрины. Общий пул подсунул бы Zona
        # рекомендации на произведения, которых у неё нет, и «чужая сущность»
        # появилась бы не в карточке, а в блоке похожего.
        список = list(проекции.values())
        корзины = построить_корзины(список)
        for слаг, ид in затронуто.items():
            текущая = проекции.get(ид)
            if текущая is not None:
                итог[слаг]["recommendation_ids"] = подобрать(
                    текущая, список, корзины=корзины)

    # Перенесённые записи приводятся к той же форме. На правильной форме это
    # ничего не меняет, а неправильную — единственную, которая роняет
    # витрину, — снимает до того, как её увидит рендерер.
    for слаг, з in итог.items():
        сырые = з.get("seasons")
        if сырые:
            приведённые = сезоны_рендерера(сырые)
            if приведённые != сырые:
                з["seasons"] = приведённые
                ст["сезонов_приведено"] = ст.get("сезонов_приведено", 0) + 1

    # Ключи упорядочены: побайтная воспроизводимость — часть контракта, по
    # ней сверяют ожидаемый SHA-256 до записи.
    содержимое = {
        "schema": СХЕМА,
        "source": ИСТОЧНИК,
        "details_total": len(итог),
        "details": {с: итог[с] for с in sorted(итог)},
    }
    return содержимое, ст


def посчитать(детали: dict) -> dict:
    """Покрытие по полям — то, что потом сверяют с публичной выдачей."""
    def есть(з, к):
        return з.get(к) not in (None, "", [], {})
    return {
        "entries": len(детали),
        "kp": sum(1 for з in детали.values() if есть(з, "kinopoisk_rating")),
        "imdb": sum(1 for з in детали.values() if есть(з, "imdb_rating")),
        "description": sum(1 for з in детали.values() if есть(з, "description")),
        "poster_url": sum(1 for з in детали.values() if есть(з, "poster_url")),
        "external_ids": sum(1 for з in детали.values() if есть(з, "external_ids")),
        "sources": sum(1 for з in детали.values() if есть(з, "sources")),
    }


def регрессии(было: dict, стало: dict) -> list[dict]:
    """Непустые значения, которые новая сборка обнулила бы.

    Список обязан быть пустым. Он существует, чтобы это можно было показать,
    а не утверждать.
    """
    поля = ("id", "name", "kinopoisk_rating", "imdb_rating", "description",
            "poster_url", "external_ids", "sources", "year", "type")
    найдено = []
    for слаг, прежняя in было.items():
        новая = стало.get(слаг)
        if новая is None:
            найдено.append({"slug": слаг, "field": "*", "reason": "entry_dropped"})
            continue
        for поле in поля:
            п, н = прежняя.get(поле), новая.get(поле)
            if п not in (None, "", [], {}) and н in (None, "", [], {}):
                найдено.append({"slug": слаг, "field": поле,
                                "before": п, "after": н})
    return найдено


def выполнить(*, профиль: Профиль, применить: bool, копии: Path, run_id: str,
              предел: int | None = None, ожидаемая_ревизия: str | None = None,
              с_рекомендациями: bool = True,
              только: set[str] | None = None,
              черновик: Path | None = None) -> dict:
    начало = time.time()
    профиль.проверить()

    рев = ревизия(профиль.каталог)
    if ожидаемая_ревизия and рев != ожидаемая_ревизия:
        raise ContractViolation(
            f"{профиль.site_id}: ревизия каталога {рев}, "
            f"ожидалась {ожидаемая_ревизия} — снимок устарел")

    каталог_сайта = загрузить_список(профиль.каталог, "каталоге витрины")
    сырой_поставщик = загрузить_список(профиль.источник, "списке поставщика")
    поставщик = {}
    for з in сырой_поставщик:
        ид = з.get("external_id") or з.get("id")
        if ид:
            поставщик[str(ид)] = з
    по_слагу = загрузить_карту(профиль.карта)

    прежний = {}
    прежний_сырой = None
    if профиль.цель.is_file():
        try:
            прежний_сырой = json.loads(профиль.цель.read_text(encoding="utf-8"))
            прежний = прежний_сырой.get("details") or {}
        except (OSError, ValueError):
            прежний = {}

    содержимое, ст = собрать(
        каталог_сайта=каталог_сайта, поставщик=поставщик, по_слагу=по_слагу,
        детали=профиль.детали, прежний=прежний, предел=предел,
        с_рекомендациями=с_рекомендациями, только=только)

    # Метаданные снимка переносятся в файл: по ним видно, из чего он собран,
    # без сверки с посторонним состоянием.
    содержимое["site"] = профиль.site_id
    содержимое["catalog_revision"] = рев
    содержимое["catalog_built_at"] = построен(профиль.каталог)
    содержимое["items_total"] = len(каталог_сайта)

    # Граница сайта проверяется на результате, а не на намерении: ни один
    # записанный slug не может быть чужим.
    свои = {з["slug"] for з in каталог_сайта if з.get("slug")} | set(прежний)
    чужие = sorted(set(содержимое["details"]) - свои)
    if чужие:
        raise ContractViolation(
            f"{профиль.site_id}: {len(чужие)} чужих slug в результате, "
            f"например {чужие[:3]}")

    беды = проверить_контракт_рендерера(содержимое["details"])
    if беды:
        raise ContractViolation(
            f"{профиль.site_id}: {len(беды)} записей нарушают форму, которую "
            f"витрина читает по индексу, например {беды[:3]}")

    потери = регрессии(прежний, содержимое["details"])
    # Сериализация выполняется один раз и здесь же: ожидаемый SHA-256 обязан
    # быть хэшем тех самых байтов, которые лягут в файл. Хэш канонической
    # формы предсказывал бы не файл, и сверка после записи ничего бы не
    # доказывала — совпадения не было бы никогда.
    текст = json.dumps(содержимое, ensure_ascii=False, sort_keys=True)
    новый_отпечаток = hashlib.sha256(текст.encode("utf-8")).hexdigest()

    отчёт = {
        "run_id": run_id,
        "site": профиль.site_id,
        "mode": "apply" if применить else "dry-run",
        "inputs": {
            "catalog": str(профиль.каталог),
            "upstream": str(профиль.источник),
            "render_state": str(профиль.карта),
            "detail_cache": str(профиль.детали),
        },
        "output": str(профиль.цель),
        "catalog_revision": рев,
        "scope": ("canary" if только is not None else "full"),
        "scope_slugs": sorted(только) if только is not None else None,
        "catalog_items": len(каталог_сайта),
        "upstream_items": len(поставщик),
        "render_state_slugs": len(по_слагу),
        "ambiguous_slugs_total": sum(1 for к in по_слагу.values() if len(к) > 1),
        "before": посчитать(прежний),
        "after": посчитать(содержимое["details"]),
        "planned": {
            "inserted": ст["новых"], "updated": ст["изменено"],
            "preserved": ст["сохранено_прежних"],
            "carried_outside_catalog": ст["перенесено_вне_каталога"],
            "rejected": sum(ст["отказы"].values()),
        },
        "rejections": ст["отказы"],
        "upstream_missing": ст["без_upstream"],
        "wrong_entity_candidates": ст["отказы"].get(НЕОДНОЗНАЧНО, 0)
                                  + ст["отказы"].get(СМЕНА_ПРИВЯЗКИ, 0),
        "fields_changed": ст["полей_изменено"],
        "seasons_normalized": ст.get("сезонов_приведено", 0),
        "renderer_contract_violations": 0,
        "nonempty_regressions": len(потери),
        "nonempty_regression_sample": потери[:10],
        "before_digest": отпечаток({"details": прежний}) if прежний else None,
        "content_digest": отпечаток(содержимое),
        "expected_sha256": новый_отпечаток,
        "duration_sec": round(time.time() - начало, 2),
        "production_mutations": 0,
    }

    if потери:
        raise ContractViolation(
            f"{профиль.site_id}: сборка обнулила бы {len(потери)} непустых "
            f"значений, например {потери[:3]}")

    if черновик is not None:
        # Черновик вне production: по нему поднимают витрину на запасном
        # порту и проверяют, что она вообще отвечает. Проверки формы ловят
        # известные способы её уронить, прогон настоящего рендерера — ещё и
        # неизвестные. Стоит это одну минуту, а пропущенный отказ стоил 502
        # на живом домене.
        черновик.parent.mkdir(parents=True, exist_ok=True)
        черновик.write_text(текст, encoding="utf-8")
        отчёт["staging_out"] = str(черновик)
        отчёт["staging_sha256"] = hashlib.sha256(
            черновик.read_bytes()).hexdigest()

    if not применить:
        отчёт["note"] = ("сухой прогон: ни один production-файл не записан; "
                         "для записи нужен явный --apply")
        return отчёт

    копии.mkdir(parents=True, exist_ok=True)
    замок = копии / f"{профиль.site_id}.lock"
    with open(замок, "w") as ф:
        try:
            fcntl.flock(ф, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise ContractViolation(
                f"{профиль.site_id}: другой прогон уже идёт "
                f"(замок {замок})") from None
        # Отпечаток входа сверяется ещё раз непосредственно перед записью:
        # между сухим прогоном и применением каталог мог обновиться.
        if ревизия(профиль.каталог) != рев:
            raise ContractViolation(
                f"{профиль.site_id}: каталог изменился во время прогона")
        if профиль.цель.is_file():
            копия = копии / f"{профиль.цель.name}.before.{run_id}"
            shutil.copy2(профиль.цель, копия)
            отчёт["before_image"] = str(копия)
            отчёт["before_image_sha256"] = hashlib.sha256(
                копия.read_bytes()).hexdigest()
            отчёт["rollback_command"] = (
                f"install -m 664 -o claude -g claude {копия} {профиль.цель} "
                f"&& systemctl restart {профиль.сервис}")
        врем = профиль.цель.with_suffix(профиль.цель.suffix + f".{run_id}.tmp")
        with open(врем, "w", encoding="utf-8") as вых:
            вых.write(текст)
            вых.flush()
            os.fsync(вых.fileno())      # содержимое на диске до подмены
        os.replace(врем, профиль.цель)  # подмена целиком: полуфайла не будет
        отчёт["written"] = True
        отчёт["written_sha256"] = hashlib.sha256(
            профиль.цель.read_bytes()).hexdigest()
        # Записанное обязано совпасть с обещанным. Расхождение здесь — это
        # запись не того, что проверяли на сухом прогоне.
        if отчёт["written_sha256"] != новый_отпечаток:
            raise ContractViolation(
                f"{профиль.site_id}: записан {отчёт['written_sha256']}, "
                f"ожидался {новый_отпечаток}")
        отчёт["production_mutations"] = 1
        fcntl.flock(ф, fcntl.LOCK_UN)
    return отчёт


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="backfill бокового файла подробностей витрины Nova")
    ap.add_argument("--site", required=True, choices=sorted(ПРОФИЛИ))
    ap.add_argument("--root", type=Path, default=None,
                    help="корень песочницы для фикстур и тестов")
    ap.add_argument("--backup-dir", type=Path,
                    default=Path("/srv/site-factory/repo/var/lords/backfill-backups"))
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--expect-revision", default=None)
    ap.add_argument("--staging-out", type=Path, default=None,
                    help="записать результат вне production для проверки "
                         "настоящим рендерером")
    ap.add_argument("--only-slugs", default=None,
                    help="канарейка: обработать только эти slug (через запятую)")
    ap.add_argument("--no-recommendations", action="store_true")
    ap.add_argument("--apply", action="store_true",
                    help="записать результат; без него ничего не пишется")
    a = ap.parse_args(argv)

    профиль = ПРОФИЛИ[a.site]
    if a.root:
        профиль = переукоренить(профиль, a.root)
    run_id = a.run_id or f"bf-{uuid.uuid4().hex[:12]}"
    только = None
    if a.only_slugs:
        только = {с.strip() for с in a.only_slugs.split(",") if с.strip()}
    try:
        отчёт = выполнить(профиль=профиль, применить=a.apply,
                          копии=a.backup_dir, run_id=run_id, предел=a.limit,
                          ожидаемая_ревизия=a.expect_revision,
                          с_рекомендациями=not a.no_recommendations,
                          только=только, черновик=a.staging_out)
    except ContractViolation as ош:
        print(json.dumps({"run_id": run_id, "site": a.site,
                          "status": "CONTRACT_VIOLATION",
                          "detail": str(ош)}, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps(отчёт, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
