"""Реальные внешние источники оценок для витрин Nova.

Здесь два адаптера, и оба работают без секретов. Это не компромисс, а
следствие проверки: у источников, требующих токен (TMDB, kinopoisk.dev,
kinopoiskapiunofficial), запрос без ключа возвращает 401, и вводить ключ
разрешено только через защищённый Secret Hub.

IMDb — официальный набор данных
-------------------------------

`https://datasets.imdbws.com/title.ratings.tsv.gz` — официальная выгрузка
самой IMDb: `tconst`, `averageRating`, `numVotes`, 1 709 368 строк. Это не
скрейпинг: файл опубликован IMDb как канал распространения данных.

Соединение идёт по `tconst`. Поставщик каталога отдаёт голое число, а IMDb
дополняет его нулями до семи знаков: `12345` — это `tt0012345`, а `35990570`
— `tt35990570`. Перепутать здесь легко, и цена ошибки — оценка чужого фильма.

**Условие использования.** IMDb разрешает доступ к наборам данных для личного
и некоммерческого применения. Решение о применимости к этим витринам
принимает владелец; адаптер сообщает об условии в отчёте и не скрывает его.

Shikimori — открытый API
------------------------

`https://shikimori.io/api/animes?ids=...` — открытый API без авторизации,
требует представиться в `User-Agent`. Отдаёт до пятидесяти записей за запрос,
что превращает 4 702 обращения в 95.

Соединение идёт по идентификатору MyAnimeList: Shikimori использует их как
собственные. Совпадение проверяется вторым признаком — названием: ID
совпал, а произведение другое — это ровно тот случай, ради которого
проверка и нужна.

Что оба адаптера не делают
--------------------------

Не пишут в поле чужого источника. Оценка Shikimori не станет оценкой IMDb ни
при каких обстоятельствах: витрина подписывает число источником, и подпись
обязана быть правдой. Ноль у Shikimori означает «ещё не оценили» — это
отсутствие, а не оценка в ноль баллов.
"""
from __future__ import annotations

import gzip
import json
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from factory.lords.rating_gateway import ОценкаИсточника, отметка

#: Кто мы для источника. Представляться обязательно: Shikimori требует этого
#: в условиях, и анонимный обход — нарушение, а не находчивость.
АГЕНТ = "site-factory-nova/1.0 (+https://lordfilm47.space)"

ИСТОЧНИК_IMDB = "imdb"
ИСТОЧНИК_SHIKIMORI = "shikimori"

IMDB_ДАТАСЕТ = "https://datasets.imdbws.com/title.ratings.tsv.gz"
IMDB_ЛИЦЕНЗИЯ = ("IMDb разрешает доступ к наборам данных для личного и "
                 "некоммерческого использования; применимость к этим витринам "
                 "определяет владелец")
SHIKIMORI_БАЗА = "https://shikimori.io/api/animes"
SHIKIMORI_ПАКЕТ = 50


def tconst(сырое) -> str | None:
    """Идентификатор IMDb из голого числа.

    IMDb дополняет нулями до семи знаков и не дополняет то, что длиннее.
    Отдать `tt35990570` как `tt0035990` значило бы запросить оценку другого
    произведения — и получить её.
    """
    s = str(сырое or "").strip()
    if s.lower().startswith("tt"):
        s = s[2:]
    if not s.isdigit():
        return None
    return "tt" + (s.zfill(7) if len(s) < 7 else s)


@dataclass
class ИсточникIMDb:
    """Оценки IMDb из официального набора данных."""
    путь: Path
    имя: str = "imdb-datasets"
    ключ_привязки: str = "imdb"
    отдаёт: tuple[str, ...] = (ИСТОЧНИК_IMDB,)
    лицензия: str = IMDB_ЛИЦЕНЗИЯ
    _таблица: dict[str, tuple[float, int]] = field(default_factory=dict)
    загружено_строк: int = 0

    @staticmethod
    def скачать(куда: Path, *, url: str = IMDB_ДАТАСЕТ, таймаут: int = 600) -> dict:
        """Забрать свежую выгрузку. Прежняя остаётся, пока новая не скачалась."""
        куда.parent.mkdir(parents=True, exist_ok=True)
        врем = куда.with_suffix(куда.suffix + ".part")
        запрос = urllib.request.Request(url, headers={"User-Agent": АГЕНТ})
        начало = time.time()
        with urllib.request.urlopen(запрос, timeout=таймаут) as ответ:  # noqa: S310
            данные = ответ.read()
        врем.write_bytes(данные)
        врем.replace(куда)
        return {"url": url, "bytes": len(данные), "path": str(куда),
                "seconds": round(time.time() - начало, 1),
                "fetched_at": отметка()}

    def загрузить(self) -> "ИсточникIMDb":
        таблица: dict[str, tuple[float, int]] = {}
        with gzip.open(self.путь, "rt", encoding="utf-8") as ф:
            next(ф, None)                       # заголовок
            for строка in ф:
                части = строка.rstrip("\n").split("\t")
                if len(части) != 3:
                    continue
                try:
                    таблица[части[0]] = (float(части[1]), int(части[2]))
                except ValueError:
                    continue
        self._таблица = таблица
        self.загружено_строк = len(таблица)
        return self

    def оценки(self, запрос: list[str]) -> dict[str, list[ОценкаИсточника]]:
        if not self._таблица:
            self.загрузить()
        когда = отметка()
        итог: dict[str, list[ОценкаИсточника]] = {}
        for сырое in запрос:
            т = tconst(сырое)
            if not т:
                continue
            найдено = self._таблица.get(т)
            if not найдено:
                continue
            значение, голоса = найдено
            итог[сырое] = [ОценкаИсточника(
                source=ИСТОЧНИК_IMDB, provider=self.имя,
                # Внешний идентификатор возвращается в том виде, в каком его
                # спросили: шлюз сверяет его с запрошенным, и приведённая
                # форма выглядела бы как ответ про другое произведение.
                external_id=str(сырое), value=значение, scale=10.0,
                votes=голоса, retrieved_at=когда)]
        return итог


@dataclass
class ИсточникShikimori:
    """Оценки Shikimori по идентификаторам MyAnimeList."""
    имя: str = "shikimori"
    ключ_привязки: str = "myanimelist"
    отдаёт: tuple[str, ...] = (ИСТОЧНИК_SHIKIMORI,)
    база: str = SHIKIMORI_БАЗА
    пакет: int = SHIKIMORI_ПАКЕТ
    пауза: float = 1.0
    таймаут: int = 40
    открыватель = None
    запросов: int = 0
    ошибок: int = 0
    названия: dict[str, str] = field(default_factory=dict)

    def _получить(self, url: str) -> list:
        запрос = urllib.request.Request(url, headers={
            "User-Agent": АГЕНТ, "Accept": "application/json"})
        открыть = self.открыватель or (
            lambda з, таймаут: urllib.request.urlopen(з, timeout=таймаут))  # noqa: S310
        with открыть(запрос, self.таймаут) as ответ:
            тело = ответ.read()
        данные = json.loads(тело.decode("utf-8"))
        return данные if isinstance(данные, list) else []

    def оценки(self, запрос: list[str]) -> dict[str, list[ОценкаИсточника]]:
        итог: dict[str, list[ОценкаИсточника]] = {}
        for начало in range(0, len(запрос), self.пакет):
            кусок = [str(и) for и in запрос[начало:начало + self.пакет]]
            адрес = (f"{self.база}?"
                     + urllib.parse.urlencode({"ids": ",".join(кусок),
                                               "limit": self.пакет}))
            self.запросов += 1
            try:
                записи = self._получить(адрес)
            except Exception:       # noqa: BLE001
                # Отказ источника — это отсутствие ответа, а не отсутствие
                # оценки: записи просто не попадут в результат и будут
                # спрошены в следующий раз.
                self.ошибок += 1
                if self.пауза:
                    time.sleep(self.пауза)
                continue
            когда = отметка()
            for запись in записи:
                ид = str(запись.get("id") or "")
                if not ид:
                    continue
                название = запись.get("russian") or запись.get("name") or ""
                if название:
                    self.названия[ид] = название
                try:
                    значение = float(запись.get("score") or 0)
                except (TypeError, ValueError):
                    continue
                if значение <= 0:
                    # Ноль у Shikimori значит «ещё не оценили».
                    continue
                итог[ид] = [ОценкаИсточника(
                    source=ИСТОЧНИК_SHIKIMORI, provider=self.имя,
                    external_id=ид, value=значение, scale=10.0,
                    votes=None, retrieved_at=когда)]
            if self.пауза:
                time.sleep(self.пауза)
        return итог


def описание_источников() -> list[dict]:
    """Паспорт источников для отчёта: без секретов, с условиями применения."""
    return [
        {"name": "imdb-datasets", "source": ИСТОЧНИК_IMDB,
         "kind": "official dataset", "url": IMDB_ДАТАСЕТ,
         "auth": "не требуется", "join_key": "imdb (tconst)",
         "terms": IMDB_ЛИЦЕНЗИЯ},
        {"name": "shikimori", "source": ИСТОЧНИК_SHIKIMORI,
         "kind": "public API", "url": SHIKIMORI_БАЗА,
         "auth": "не требуется, обязателен User-Agent",
         "join_key": "myanimelist id",
         "terms": "открытый API; пакет до 50 записей, обход с паузой"},
    ]
