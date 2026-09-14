"""Каноническая проекция записи каталога для публичного контракта.

Зачем она нужна
---------------

Поля одной и той же записи приходят двумя путями: список каталога отдаёт
идентификаторы, постер, воспроизведение и обе оценки, а `detail` добавляет
описание, состав сезонов, страны и жанры. Оба источника заполнены неполно и
неполны по-разному.

Пока каждый потребитель решал сам, откуда взять поле, получалось так: карточка
читала оценку только из `detail`, а `detail` существует лишь для трети
каталога. Оценка, пришедшая в списке, до страницы не доходила — не потому что
её не было, а потому что её не спросили. На витрине это выглядело как «КП —
IMDb —» у записи, для которой источник оценку вернул.

Здесь объединение выполняется ОДИН раз и в одном месте, и результат несёт
происхождение каждого значения. Потребителю больше не нужно знать, из какого
файла что берётся, — а значит, и забыть спросить он не может.

Правила
-------

* объединение только добавляет: пустое значение никогда не затирает заполненное;
* оценки независимы — отсутствие одной не скрывает другую;
* заглушка описанием не считается;
* запись объявляется воспроизводимой только при наличии разрешённой привязки
  к источнику; «есть playback» само по себе таким основанием не является.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

SCHEMA_VERSION = "lords.title.projection/1.0.0"

#: Состояния доступности источника. `pending` отличается от `unavailable`
#: намеренно: «ещё не выяснили» и «выяснили, что нет» — разные вещи, и
#: показывать их одинаково значит скрыть незавершённую работу.
ДОСТУПНО = "available"
НЕДОСТУПНО = "unavailable"
ОЖИДАЕТСЯ = "pending"
ОШИБКА = "error"
СОСТОЯНИЯ = (ДОСТУПНО, НЕДОСТУПНО, ОЖИДАЕТСЯ, ОШИБКА)

#: Откуда пришло значение. Нужно, чтобы «нет данных» и «данные потерялись по
#: дороге» различались в отчёте, а не сливались в один процент.
ИЗ_КАТАЛОГА = "catalog"
ИЗ_ДЕТАЛИ = "detail"
НЕТ_ИСТОЧНИКА = None

#: Тексты, которые встречаются вместо описания. Считать их описанием значит
#: отчитаться о покрытии, которого нет.
_ЗАГЛУШКИ = re.compile(
    r"^\s*(описание\s*(отсутствует|не\s*найдено)?|нет\s*описания|"
    r"no\s+description|n/?a|—|-|\.{1,3})\s*$", re.I)

_МИН_ДЛИНА_ОПИСАНИЯ = 40


def описание_годное(текст: Any) -> bool:
    """Отличить описание от заглушки.

    Короткая строка может быть настоящим описанием, но строка из прочерка или
    слова «нет» — не может. Порог длины выбран так, чтобы не принимать
    служебные пометки, и он один на весь контур: разные пороги в разных местах
    дали бы разные проценты покрытия для одних и тех же данных.
    """
    if not isinstance(текст, str):
        return False
    очищено = текст.strip()
    if not очищено or _ЗАГЛУШКИ.match(очищено):
        return False
    return len(очищено) >= _МИН_ДЛИНА_ОПИСАНИЯ


def _пусто(значение: Any) -> bool:
    return значение is None or значение == "" or значение == [] or значение == {}


def _оценка(значение: Any) -> float | None:
    """Оценка или ничего. Ноль — это оценка, а не её отсутствие."""
    if isinstance(значение, bool) or значение is None:
        return None
    try:
        число = float(значение)
    except (TypeError, ValueError):
        return None
    return число if 0.0 <= число <= 10.0 else None


def _внешний_ид(значение: Any) -> str | None:
    if значение is None:
        return None
    текст = str(значение).strip()
    return текст or None


@dataclass(frozen=True)
class Источник:
    """Одна привязка к поставщику воспроизведения."""
    provider: str
    source_id: str
    player_id: str | None
    availability_status: str

    def as_dict(self) -> dict[str, Any]:
        return {"provider": self.provider, "source_id": self.source_id,
                "player_id": self.player_id,
                "availability_status": self.availability_status}


@dataclass
class Проекция:
    """Каноническая запись публичного контракта."""
    id: str
    schema_version: str = SCHEMA_VERSION
    name: str = ""
    original_name: str | None = None
    type: str = ""
    year: int | None = None
    external_ids: dict[str, str] = field(default_factory=dict)
    ratings: dict[str, float] = field(default_factory=dict)
    ratings_source: dict[str, str] = field(default_factory=dict)
    description: str | None = None
    description_source: str | None = None
    description_language: str | None = None
    poster: str | None = None
    poster_source: str | None = None
    sources: list[Источник] = field(default_factory=list)
    seasons: list[dict] = field(default_factory=list)
    recommendation_ids: list[str] = field(default_factory=list)
    genres: list[str] = field(default_factory=list)
    countries: list[str] = field(default_factory=list)
    playable: bool = False
    detail_present: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "schema_version": self.schema_version,
            "name": self.name,
            "original_name": self.original_name,
            "type": self.type,
            "year": self.year,
            "external_ids": dict(self.external_ids),
            "ratings": dict(self.ratings),
            "ratings_source": dict(self.ratings_source),
            "description": self.description,
            "description_source": self.description_source,
            "description_language": self.description_language,
            "poster": self.poster,
            "poster_source": self.poster_source,
            "sources": [и.as_dict() for и in self.sources],
            "seasons": list(self.seasons),
            "recommendation_ids": list(self.recommendation_ids),
            "genres": list(self.genres),
            "countries": list(self.countries),
            "playable": self.playable,
            "detail_present": self.detail_present,
        }


def _собрать_источники(запись: dict, деталь: dict | None) -> list[Источник]:
    """Привязки к поставщику. Без идентификатора источника привязки нет.

    Поставщик даёт пару `{aggregator, title_id}`. Подставлять сюда
    канонический идентификатор записи нельзя ни при каких обстоятельствах:
    он принадлежит нашему каталогу, а не агрегатору, и плеер по нему откроет
    либо ничего, либо чужое. Отсутствие `title_id` — это `pending`, а не
    повод придумать идентификатор.
    """
    playback = запись.get("playback")
    if not isinstance(playback, dict) or not playback:
        return []
    провайдер = _внешний_ид(playback.get("aggregator")
                            or playback.get("provider"))
    сид = _внешний_ид(playback.get("title_id") or playback.get("source_id"))
    # Идентификатор плеера поставщик в этом контракте не отдаёт. Ставить сюда
    # что-либо своё значило бы выдать догадку за привязку.
    плеер = _внешний_ид(playback.get("player_id"))
    if not провайдер or not сид:
        return [Источник(провайдер or "", сид or "", плеер, ОЖИДАЕТСЯ)]
    состояние = НЕДОСТУПНО if playback.get("available") is False else ДОСТУПНО
    return [Источник(провайдер, сид, плеер, состояние)]


def спроецировать(запись: dict, деталь: dict | None = None) -> Проекция:
    """Объединить список и подробности в одну каноническую запись.

    Порядок предпочтения задан явно: где значение есть в обоих источниках,
    берётся `detail` как более подробный; где его там нет — берётся каталог.
    Обратный порядок и был причиной потери: каталог спрашивали последним, а
    чаще всего только его и было.
    """
    деталь = деталь or {}
    ид = _внешний_ид(запись.get("external_id") or деталь.get("id"))
    if not ид:
        raise ValueError("запись без канонического идентификатора")

    п = Проекция(id=ид)
    п.name = str(деталь.get("name") or запись.get("name") or "").strip()
    п.original_name = (str(деталь.get("original_name")).strip()
                       if деталь.get("original_name") else None)
    п.type = str(деталь.get("type") or запись.get("type") or "").strip()
    год = деталь.get("year") if деталь.get("year") else запись.get("year")
    п.year = int(год) if isinstance(год, int) and год > 0 else None
    п.detail_present = bool(деталь)

    # --- внешние идентификаторы -----------------------------------------
    для_слияния = {}
    for источник, откуда in ((запись.get("external_ids"), ИЗ_КАТАЛОГА),
                             (деталь.get("external_ids"), ИЗ_ДЕТАЛИ)):
        if isinstance(источник, dict):
            for ключ, значение in источник.items():
                очищено = _внешний_ид(значение)
                if очищено and ключ not in для_слияния:
                    для_слияния[ключ] = очищено
    п.external_ids = для_слияния

    # --- оценки: независимы друг от друга --------------------------------
    for ключ, поле in (("kinopoisk", "kinopoisk_rating"), ("imdb", "imdb_rating")):
        значение = _оценка(деталь.get(поле))
        откуда = ИЗ_ДЕТАЛИ
        if значение is None:
            значение = _оценка(запись.get(поле))
            откуда = ИЗ_КАТАЛОГА
        if значение is not None:
            п.ratings[ключ] = значение
            п.ratings_source[ключ] = откуда

    # --- описание ---------------------------------------------------------
    for источник, откуда in ((деталь.get("description"), ИЗ_ДЕТАЛИ),
                             (запись.get("description"), ИЗ_КАТАЛОГА)):
        if описание_годное(источник):
            п.description = источник.strip()
            п.description_source = откуда
            п.description_language = "ru"
            break

    # --- постер -----------------------------------------------------------
    for источник, откуда in ((деталь.get("poster_url"), ИЗ_ДЕТАЛИ),
                             (запись.get("poster_url"), ИЗ_КАТАЛОГА)):
        if not _пусто(источник):
            п.poster = str(источник)
            п.poster_source = откуда
            break

    # --- источники воспроизведения ---------------------------------------
    п.sources = _собрать_источники(запись, деталь)
    п.playable = any(и.source_id and и.availability_status == ДОСТУПНО
                     for и in п.sources)

    сезоны = деталь.get("seasons")
    п.seasons = list(сезоны) if isinstance(сезоны, list) else []
    п.genres = [str(g) for g in (деталь.get("genres") or запись.get("genres") or [])]
    п.countries = [str(c) for c in (деталь.get("countries") or [])]
    return п


#: Поля, которые обязаны дойти от источника до проекции. Проверяется тестом:
#: если значение есть на входе, оно обязано быть на выходе. Список закрыт
#: намеренно — молчаливое расширение контракта так же опасно, как молчаливая
#: потеря.
СКВОЗНЫЕ_ПОЛЯ = (
    ("kinopoisk_rating", lambda п: п.ratings.get("kinopoisk")),
    ("imdb_rating", lambda п: п.ratings.get("imdb")),
    ("poster_url", lambda п: п.poster),
    ("external_ids", lambda п: п.external_ids or None),
    ("description", lambda п: п.description),
)


def потери(запись: dict, деталь: dict | None, проекция: Проекция) -> list[str]:
    """Какие поля были на входе и исчезли на выходе.

    Отдельная функция, а не проверка внутри теста: её вызывает и измеритель
    покрытия, поэтому «ноль потерь» в отчёте и «ноль потерь» в тесте — одно и
    то же утверждение, а не два похожих.
    """
    деталь = деталь or {}
    потеряно = []
    for имя, достать in СКВОЗНЫЕ_ПОЛЯ:
        было = деталь.get(имя) if not _пусто(деталь.get(имя)) else запись.get(имя)
        if _пусто(было):
            continue
        if имя == "description" and not описание_годное(было):
            continue
        if имя in ("kinopoisk_rating", "imdb_rating") and _оценка(было) is None:
            continue
        if достать(проекция) in (None, {}, []):
            потеряно.append(имя)
    return потеряно
