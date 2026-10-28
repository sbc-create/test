#!/usr/bin/env python3
"""Читающее API каталога для мобильного/TV-клиента. Ничего не меняет.

    python3 automation/host/app-read-api.py --site animedia-01 \
        --data-dir /srv/animedia-icu/data --bind 127.0.0.1 --port 9180

Зачем отдельная служба, а не маршруты витрины. Витрина отдаёт страницы и несёт
плеер; её рантайм закреплён (`pins.lock.json`), а выпуск требует зелёного CI.
Трогать её ради чтения каталога значит рисковать показом сайта и плеером из-за
задачи, которая к ним не относится. Эта служба читает ТЕ ЖЕ файлы снимка, что и
витрина, и работает рядом: отдельный процесс, отдельный порт, только GET.

Что отдаётся — ровно то, что в снимке есть:

* поиск по русскому и оригинальному написанию с курсором;
* карточка: названия, год, жанры, описание, оценка, постер, внешние id;
* сезоны и серии — ИЗ ЧИСЕЛ снимка (`seasons: [{n, eps, avail}]`): у нас есть
  количество серий и количество доступных, а названий и длительностей серий в
  снимке нет, и выдумывать их нельзя;
* источник видео — ПУСТОЙ список с причиной. Прямых ссылок на поток у фабрики
  нет: витрина подключает web-компонент провайдера, который сам поднимает
  внутренний кадр и запрашивает поток. См. `docs/APP_READ_API.md`;
* «где смотреть» — только ПОДТВЕРЖДЁННЫЕ предложения официальных сервисов из
  отдельного хранилища `<site>-offers.json`. Пока одобренного источника таких
  сведений нет, файла нет, и ответ — `status: unknown`, а не «нигде нет»;
* главная и подборки приложения «Кинатека» — ОПУБЛИКОВАННАЯ ревизия канала
  (`config/{sandbox|production}`, контракт `kinateka-config/1`). Ревизии пишет
  Control API (раздел админки), служба только читает указатель канала и
  подставляет в позиции подборок поля из ТЕКУЩЕГО снимка.

Снимок перечитывается, когда витрина его обновила (раньше читался один раз при
старте, и после ежедневного обновления служба отдавала вчерашний каталог до
перезапуска). Новый указатель строится в стороне и подменяет старый целиком.

Память. Снимок подробностей — десятки мегабайт, и разбор его целиком стоит
гигабайт. Поэтому при старте строится УЗКИЙ указатель: только поля, которые
отдаются клиенту. Большая структура освобождается сразу после.
"""
from __future__ import annotations

import argparse
import datetime
import gc
import hmac
import json
import os
import pathlib
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

ВЕРСИЯ = "app-read-api/1"
ПРЕДЕЛ_СТРАНИЦЫ = 50
ПРЕДЕЛ_ЗАПРОСОВ_В_МИНУТУ = 120
КИРИЛЛИЦА = re.compile(r"[А-Яа-яЁё]")
# «Где смотреть»: сведения старше этого — «устарели» (тот же порог у клиента).
СВЕЖЕСТЬ_ПРЕДЛОЖЕНИЯ_СЕК = 30 * 24 * 3600
ВИДЫ_ПРЕДЛОЖЕНИЙ = {"SUBSCRIPTION", "PURCHASE", "RENTAL", "FREE"}
РЕГИОН = re.compile(r"[A-Z]{2}")
# Ссылка на поиск или главную сервиса — не доказательство, что произведение там есть.
ПУТЬ_ПОИСКА = re.compile(r"(^|/)(search|poisk|find|results)(/|$)", re.IGNORECASE)
ЗАПРОС_ПОИСКА = re.compile(r"(^|&)(q|query|text|search|s|kp_query)=", re.IGNORECASE)
# Конфигурация главной приложения.
КАНАЛЫ = ("sandbox", "production")
СХЕМА_КОНФИГУРАЦИИ = "kinateka-config/1"
# Жанры, с которыми тайтл не показывается на ОБЩЕЙ главной, даже если редактор
# его поставил: возрастной метки в каталоге нет, и жанр — единственный признак
# откровенной обложки, который у нас есть (наблюдение 27.10: «этти» в «Популярном
# за неделю»). Тот же список проверяет Control API при публикации; здесь —
# вторая ступень на случай, если жанр появился у тайтла после публикации.
ЖАНРЫ_НЕ_ДЛЯ_ГЛАВНОЙ = frozenset({"этти", "хентай", "эротика", "гарем"})
# Как часто сверять, не обновила ли витрина снимок.
ПРОВЕРКА_СНИМКА_СЕК = 60


def _нормализовать(с: str) -> str:
    return re.sub(r"[^a-zа-я0-9]+", "", (с or "").lower().replace("ё", "е"))


class Каталог:
    """Узкий указатель по снимку витрины. Только чтение, строится один раз."""

    def __init__(self, site_id: str, каталог_данных: pathlib.Path) -> None:
        self.site_id = site_id
        self.корень = каталог_данных
        self.по_ид: dict[str, dict] = {}
        self.по_слагу: dict[str, str] = {}
        self.порядок: list[str] = []
        self.revision = ""
        self.built_at = ""
        self._построить()

    def _построить(self) -> None:
        путь_к = self.корень / f"{self.site_id}-catalog.json"
        путь_п = self.корень / f"{self.site_id}-details.json"
        каталог = json.loads(путь_к.read_text(encoding="utf-8"))
        self.revision = str(каталог.get("revision") or "")
        self.built_at = str(каталог.get("builtAt") or "")
        записи = {з.get("slug"): з for з in (каталог.get("items") or []) if з.get("slug")}
        del каталог
        подробности = json.loads(путь_п.read_text(encoding="utf-8")).get("details") or {}
        for слаг, д in подробности.items():
            з = записи.get(слаг) or {}
            ид = str(д.get("id") or слаг)
            сезоны = д.get("seasons") or []
            self.по_ид[ид] = {
                "contentId": ид,
                "slug": слаг,
                "type": "SERIES" if str(д.get("type") or "") == "tv" else "MOVIE",
                "titleRu": д.get("name") or з.get("title") or "",
                "originalTitle": д.get("original_name") or None,
                "year": д.get("year") or з.get("year") or None,
                "genres": list(д.get("genres") or []),
                "synopsis": д.get("description") or None,
                "rating": self._оценка(д),
                "artwork": {"posterUrl": д.get("poster_url") or з.get("poster") or None},
                "externalIds": [{"namespace": k, "value": str(v)}
                                for k, v in (д.get("external_ids") or {}).items() if v],
                "addedAt": (з.get("published_at") or "")[:10] or None,
                "_seasons": [{"n": int(с.get("n") or 0),
                              "eps": int(с.get("eps") or 0),
                              "avail": int(с.get("avail") or 0)}
                             for с in сезоны if isinstance(с, dict)],
                "_playable": bool(д.get("playable")),
                "_sources": list(д.get("sources") or []),
                "_поиск": _нормализовать((д.get("name") or з.get("title") or "")
                                         + " " + (д.get("original_name") or "")),
            }
            self.по_слагу[слаг] = ид
        del подробности, записи
        gc.collect()
        self.порядок = sorted(
            self.по_ид, key=lambda и: self.по_ид[и].get("addedAt") or "", reverse=True)

    @staticmethod
    def _оценка(д: dict) -> dict | None:
        """Оценка с НАЗВАННЫМ источником; нулей не выдумываем."""
        по_источникам = д.get("ratings_by_source") or {}
        for источник in ("kinopoisk", "kp", "imdb", "shikimori"):
            значение = по_источникам.get(источник)
            if значение:
                try:
                    return {"value": float(значение), "scale": 10, "source": источник}
                except (TypeError, ValueError):
                    continue
        if д.get("imdb_rating"):
            try:
                return {"value": float(д["imdb_rating"]), "scale": 10, "source": "imdb"}
            except (TypeError, ValueError):
                return None
        return None

    def наружу(self, запись: dict) -> dict:
        return {к: v for к, v in запись.items() if not к.startswith("_")}

    def искать(self, запрос: str, смещение: int, предел: int) -> tuple[list[dict], int | None]:
        игла = _нормализовать(запрос)
        найдено = [и for и in self.порядок if игла in self.по_ид[и]["_поиск"]]
        срез = найдено[смещение:смещение + предел]
        дальше = смещение + предел if смещение + предел < len(найдено) else None
        return [self.наружу(self.по_ид[и]) for и in срез], дальше, len(найдено)

    def перечислить(self, жанр: str, смещение: int,
                    предел: int) -> tuple[list[dict], int | None, int]:
        """Страница каталога по дате добавления, при нужде — в одном жанре.

        Порядок берётся из уже построенного `self.порядок` (он отсортирован по
        `addedAt`), а не считается заново на каждый запрос: это тот же список,
        по которому витрина показывает «новое».
        """
        отобранные = [и for и in self.порядок
                      if not жанр
                      or жанр in [ж.lower() for ж in self.по_ид[и]["genres"]]]
        срез = отобранные[смещение:смещение + предел]
        дальше = (смещение + предел
                  if смещение + предел < len(отобранные) else None)
        return ([self.наружу(self.по_ид[и]) for и in срез], дальше,
                len(отобранные))

    def сезоны(self, ид: str) -> list[dict]:
        запись = self.по_ид[ид]
        return [{"seasonId": f"{ид}:s{с['n']}", "contentId": ид, "number": с["n"],
                 "episodeCount": с["eps"], "availableCount": с["avail"],
                 "isSpecial": с["n"] == 0}
                for с in запись["_seasons"]]

    def серии(self, ид: str, сезон: int) -> list[dict]:
        запись = self.по_ид[ид]
        нужный = next((с for с in запись["_seasons"] if с["n"] == сезон), None)
        if нужный is None:
            return []
        return [{"episodeId": f"{ид}:s{сезон}:e{н}",
                 "seasonId": f"{ид}:s{сезон}", "contentId": ид,
                 "displayNumber": str(н), "order": сезон * 1000 + н,
                 "available": н <= нужный["avail"]}
                for н in range(1, нужный["eps"] + 1)]


class ХранилищеПредложений:
    """Подтверждённые предложения «где смотреть» — отдельно от снимка каталога.

    Файл `<site>-offers.json` пишет одобренный источник сведений (фид партнёра,
    проверка редакции), служба его только читает и перечитывает при изменении.
    Форма: `{"source": {"id","name"}, "generatedAt", "offers": [WatchOffer…]}`.

    Три состояния различаются и не сливаются:

    * файла нет — источника сведений нет: `status: unknown` (ни «нигде нет»,
      ни ошибка);
    * файл есть, но не читается или не той формы — ОШИБКА службы (503): клиент
      видит «не удалось загрузить» и повторяет, а не «данных нет»;
    * файл есть — каждая запись проверяется, неполные и ссылки на поиск
      отбрасываются, старше порога — в `staleOffers`, не в `offers`.
    """

    def __init__(self, путь: pathlib.Path) -> None:
        self.путь = путь
        self._метка: tuple[int, int] | None = None
        self._данные: dict | None = None
        self._ошибка: str | None = None

    def снимок(self) -> tuple[dict | None, str | None]:
        """(данные, ошибка); оба None — хранилища нет."""
        try:
            ст = self.путь.stat()
        except FileNotFoundError:
            self._метка, self._данные, self._ошибка = None, None, None
            return None, None
        except OSError as ош:
            return None, f"хранилище предложений недоступно: {type(ош).__name__}"
        метка = (ст.st_mtime_ns, ст.st_size)
        if метка != self._метка:
            self._метка = метка
            try:
                данные = json.loads(self.путь.read_text(encoding="utf-8"))
                if not isinstance(данные, dict) or not isinstance(данные.get("offers"), list):
                    raise ValueError("нет списка offers")
                self._данные, self._ошибка = данные, None
            except (OSError, ValueError) as ош:
                self._данные, self._ошибка = None, f"хранилище предложений не читается: {ош}"
        return self._данные, self._ошибка


def _ссылка_на_поиск(url: str) -> bool:
    разбор = urlparse(url)
    путь = разбор.path or ""
    if путь in ("", "/"):
        return True
    return bool(ПУТЬ_ПОИСКА.search(путь) or ЗАПРОС_ПОИСКА.search(разбор.query or ""))


def _момент(значение) -> float | None:
    if not isinstance(значение, str) or not значение:
        return None
    try:
        return datetime.datetime.fromisoformat(значение.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def проверить_предложение(з: dict, ид: str, сейчас: float) -> tuple[dict | None, str | None]:
    """(предложение наружу, причина отказа). Обязательны все поля контракта."""
    if not isinstance(з, dict) or з.get("contentId") != ид:
        return None, "другое произведение"
    for поле in ("serviceId", "serviceName", "url", "source", "checkedAt", "region"):
        if not isinstance(з.get(поле), str) or not з[поле].strip():
            return None, f"нет поля {поле}"
    if not РЕГИОН.fullmatch(з["region"]):
        return None, "регион не ISO 3166-1 alpha-2"
    if not з["url"].startswith("https://") or _ссылка_на_поиск(з["url"]):
        return None, "не официальная https-страница произведения"
    момент = _момент(з["checkedAt"])
    if момент is None or момент > сейчас + 24 * 3600:
        return None, "время проверки не читается или в будущем"
    вид = з.get("kind")
    наружу = {
        "contentId": ид, "serviceId": з["serviceId"], "serviceName": з["serviceName"],
        "region": з["region"], "url": з["url"],
        # Условия — только подтверждённые; неизвестный вид не превращается в «бесплатно».
        "kind": вид if вид in ВИДЫ_ПРЕДЛОЖЕНИЙ else None,
        "source": з["source"], "checkedAt": з["checkedAt"],
    }
    if isinstance(з.get("androidPackage"), str) and з["androidPackage"]:
        наружу["androidPackage"] = з["androidPackage"]
    return наружу, None


def ответ_предложений(данные: dict | None, ид: str, регион: str, сейчас: float) -> dict:
    """Тело ответа `titles/{id}/offers` по содержимому хранилища (без ошибки)."""
    if данные is None:
        return {"contentId": ид, "region": регион, "status": "unknown",
                "reason": "NO_AVAILABILITY_SOURCE",
                "offers": [], "staleOffers": [], "source": None, "checkedAt": None}
    свежие, старые, отброшено = [], [], 0
    for з in данные.get("offers") or []:
        if not isinstance(з, dict) or з.get("contentId") != ид:
            continue
        п, причина = проверить_предложение(з, ид, сейчас)
        if п is None:
            отброшено += 1
            continue
        (старые if сейчас - _момент(п["checkedAt"]) > СВЕЖЕСТЬ_ПРЕДЛОЖЕНИЯ_СЕК else свежие).append(п)
    в_регионе = [п for п in свежие if п["region"] == регион]
    if в_регионе:
        статус = "confirmed"
    elif свежие:
        статус = "other_region"
    elif старые:
        статус = "stale"
    else:
        статус = "unknown"
    источник = данные.get("source") if isinstance(данные.get("source"), dict) else None
    return {"contentId": ид, "region": регион, "status": статус,
            "reason": None if статус != "unknown" else "NO_CONFIRMED_OFFERS",
            "offers": свежие, "staleOffers": старые,
            "source": {"id": источник.get("id"), "name": источник.get("name")} if источник else None,
            "checkedAt": данные.get("generatedAt"), "dropped": отброшено}


class ХранилищеКонфигурации:
    """Опубликованные ревизии главной приложения — только чтение.

    Раскладка (пишет Control API, см. `factory/site_engine/api/app_config.py`):
    `revisions/<n>.json` — неизменяемые ревизии, `published-<канал>.json` —
    указатель `{"revision": n}`, который меняется атомарной подменой файла.
    Каналы раздельны: указатель sandbox не читается для production.

    Состояния, как у предложений, не сливаются: нет указателя — `NO_CONFIG`
    (клиент строит свою главную), указатель или ревизия не читаются — 503
    (клиент оставляет последнюю рабочую ревизию).
    """

    def __init__(self, корень: pathlib.Path | None) -> None:
        self.корень = корень
        self._метки: dict[str, tuple] = {}
        self._ревизии: dict[str, dict] = {}

    def действующая(self, канал: str) -> tuple[dict | None, str | None]:
        """(ревизия, ошибка); оба None — в канале ничего не опубликовано."""
        if self.корень is None:
            return None, None
        указатель = self.корень / f"published-{канал}.json"
        try:
            ст = указатель.stat()
        except FileNotFoundError:
            self._метки.pop(канал, None)
            self._ревизии.pop(канал, None)
            return None, None
        except OSError as ош:
            return None, f"хранилище конфигурации недоступно: {type(ош).__name__}"
        метка = (ст.st_mtime_ns, ст.st_size)
        if метка != self._метки.get(канал):
            try:
                номер = int(json.loads(указатель.read_text(encoding="utf-8"))["revision"])
                ревизия = json.loads((self.корень / "revisions" / f"{номер}.json")
                                     .read_text(encoding="utf-8"))
                if (ревизия.get("schema") != СХЕМА_КОНФИГУРАЦИИ or ревизия.get("channel") != канал
                        or int(ревизия.get("revision") or 0) != номер):
                    raise ValueError("ревизия не той схемы, канала или номера")
            except (OSError, ValueError, KeyError, TypeError) as ош:
                return None, f"опубликованная ревизия не читается: {type(ош).__name__}: {ош}"
            self._метки[канал], self._ревизии[канал] = метка, ревизия
        return self._ревизии[канал], None


def отдать_конфигурацию(ревизия: dict, каталог: "Каталог") -> dict:
    """Ревизия в отдаваемой форме: позиции подборок дополнены из ТЕКУЩЕГО снимка.

    Состав задан по `contentId` и порядок его не меняется. Позиция, которой в
    снимке нет, или тайтл с жанром не для общей главной уходят в `missing`
    (клиент их не показывает), а не исчезают молча: редактор видит число.
    """
    тело = json.loads(json.dumps(ревизия))
    for подборка in тело.get("collections") or []:
        оставлены, нет = [], []
        for поз in подборка.get("items") or []:
            запись = каталог.по_ид.get(str(поз.get("contentId") or ""))
            if запись is None or ЖАНРЫ_НЕ_ДЛЯ_ГЛАВНОЙ & {ж.lower() for ж in запись["genres"]}:
                нет.append(поз.get("contentId"))
                continue
            поз["title"] = запись["titleRu"] or поз.get("title")
            поз["type"] = "movie" if запись["type"] == "MOVIE" else "series"
            if запись["artwork"].get("posterUrl"):
                поз["posterUrl"] = запись["artwork"]["posterUrl"]
            if запись.get("year"):
                поз["year"] = запись["year"]
            оставлены.append(поз)
        подборка["items"] = оставлены
        подборка["missing"] = нет
    тело["catalogRevision"] = каталог.revision
    return тело


class ОбновительСнимка:
    """Перечитывает снимок, когда витрина его обновила, не останавливая службу.

    Признак обновления — метка (время изменения, размер) файлов каталога и
    подробностей. Новый указатель строится в отдельном потоке и подменяет
    прежний одним присваиванием: запросы, пришедшие во время сборки, получают
    прежний снимок целиком, а не смесь. Сборка не чаще раза в `интервал`
    секунд: подробности витрина дописывает часто, а разбор стоит сотни МиБ на
    время сборки. Неудачная сборка (файл в процессе записи) оставляет прежний
    снимок и называется в состоянии.
    """

    def __init__(self, site_id: str, корень: pathlib.Path, *, интервал: float = 600.0,
                 часы=time.monotonic) -> None:
        self.site_id, self.корень, self.интервал, self._часы = site_id, корень, интервал, часы
        self._метка = self._снять_метку()
        self._сверено = self._часы()
        self._собрано = self._часы()
        self._поток: threading.Thread | None = None
        self.ошибка: str | None = None
        self.перечитано: str | None = None

    def _снять_метку(self) -> tuple:
        метка = []
        for имя in (f"{self.site_id}-catalog.json", f"{self.site_id}-details.json"):
            try:
                ст = (self.корень / имя).stat()
                метка.append((ст.st_mtime_ns, ст.st_size))
            except OSError:
                метка.append(None)
        return tuple(метка)

    def сверить(self, *, ждать: bool = False) -> None:
        сейчас = self._часы()
        if сейчас - self._сверено < ПРОВЕРКА_СНИМКА_СЕК and not ждать:
            return
        self._сверено = сейчас
        if self._поток is not None and self._поток.is_alive():
            return
        метка = self._снять_метку()
        if метка == self._метка or (сейчас - self._собрано < self.интервал and not ждать):
            return
        self._собрано = сейчас
        self._поток = threading.Thread(target=self._собрать, args=(метка,), daemon=True)
        self._поток.start()
        if ждать:
            self._поток.join()

    def _собрать(self, метка: tuple) -> None:
        try:
            новый = Каталог(self.site_id, self.корень)
        except (OSError, ValueError) as ош:
            self.ошибка = f"снимок не перечитан: {type(ош).__name__}"
            return
        Обработчик.каталог = новый
        self._метка, self.ошибка = метка, None
        self.перечитано = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        gc.collect()


class Обработчик(BaseHTTPRequestHandler):
    server_version = ВЕРСИЯ
    каталог: Каталог
    предложения: ХранилищеПредложений | None = None
    конфигурация: ХранилищеКонфигурации | None = None
    обновитель: "ОбновительСнимка | None" = None
    ключ: str = ""
    счётчик: dict = {}

    def log_message(self, формат, *арг):  # noqa: N802 — подпись из базового класса
        return

    # --- служебное ---------------------------------------------------------
    def _ответ(self, код: int, тело: dict, заголовки: dict | None = None) -> None:
        данные = json.dumps(тело, ensure_ascii=False).encode("utf-8")
        self.send_response(код)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(данные)))
        if "Cache-Control" not in (заголовки or {}):
            self.send_header("Cache-Control", "public, max-age=300")
        self.send_header("X-Catalog-Revision", self.каталог.revision[:32])
        for к, з in (заголовки or {}).items():
            self.send_header(к, з)
        self.end_headers()
        self.wfile.write(данные)

    def _отказ(self, код: int, код_ошибки: str, текст: str,
               заголовки: dict | None = None) -> None:
        self._ответ(код, {"error": {"code": код_ошибки, "message": текст}}, заголовки)

    def _ключ_верен(self) -> bool:
        """Ключ клиента обязателен ВСЕГДА, и отсутствие настройки — не допуск.

        Прежняя версия отвечала всем, пока ключ не задан: «иначе первый запуск
        клиента упёрся бы в 401». Это и есть разрешение доступа по недосмотру —
        служба, выложенная наружу до появления файла ключа, отдавала бы каталог
        кому угодно, и выглядело бы это как исправная работа. Теперь без
        настроенного ключа данные не отдаются вовсе, а причина называется в
        состоянии готовности.

        Сравнение постоянное по времени: длина и совпадение ключа не должны
        угадываться по времени ответа.
        """
        if not self.ключ:
            return False
        прислан = self.headers.get("X-App-Key", "")
        if not прислан:
            return False
        return hmac.compare_digest(прислан, self.ключ)

    def _частота_в_норме(self) -> bool:
        окно = int(time.time() // 60)
        кто = self.client_address[0]
        ключ = (кто, окно)
        Обработчик.счётчик = {к: v for к, v in Обработчик.счётчик.items()
                              if к[1] >= окно - 1}
        Обработчик.счётчик[ключ] = Обработчик.счётчик.get(ключ, 0) + 1
        return Обработчик.счётчик[ключ] <= ПРЕДЕЛ_ЗАПРОСОВ_В_МИНУТУ

    @staticmethod
    def _путь(сырой: str) -> str | None:
        """Путь с раскрытыми процентными последовательностями, по сегментам.

        Идентификаторы сезонов и серий несут двоеточие
        (`<contentId>:s1:e3`). Кодировать его в сегменте пути как `%3A`
        законно и равнозначно самому двоеточию (RFC 3986 §2.2, §6.2.2.2),
        поэтому принимать надо обе формы. Прежде служба сравнивала СЫРОЙ путь, и
        `%3A` давало 404 — наблюдение приложения 2026-10-11, воспроизведено на
        публичном адресе.

        Раскрытие идёт ПО СЕГМЕНТАМ, а не целиком: иначе `%2F` превратилось бы
        в разделитель и один сегмент стал бы двумя — это подмена маршрута, а не
        удобство. Сегмент, в котором после раскрытия появился `/`, отвергается:
        `None` здесь означает «такого пути нет».
        """
        части = []
        for сегмент in сырой.split("/"):
            раскрытый = unquote(сегмент)
            if "/" in раскрытый:
                return None
            части.append(раскрытый)
        return "/".join(части)

    # --- маршруты ---------------------------------------------------------
    def do_GET(self) -> None:  # noqa: N802 — подпись из базового класса
        разбор = urlparse(self.path)
        путь = self._путь(разбор.path)
        if путь is None:
            return self._отказ(400, "bad_request",
                               "в сегменте пути закодирован разделитель")
        путь = путь.rstrip("/") or "/"
        параметры = parse_qs(разбор.query)
        if self.обновитель is not None:
            self.обновитель.сверить()
        # Два адреса состояния, и оба нужны.
        #
        # `/healthz` — локальная проверка установщика и юнита: наружу он НЕ
        # выходит, потому что в конфигурации витрины уже стоит
        # `location = /healthz` и ведёт в саму витрину. Трогать её маршрут
        # нельзя: это чужой работающий путь.
        #
        # `/api/app/v1/healthz` — то же состояние внутри ОТДАННОГО наружу
        # префикса, и только по нему клиент приложения может проверить
        # доступность. Без него разработчик получал 404 от витрины и не мог
        # отличить «маршрута нет» от «служба не работает» — ровно это и
        # случилось 10 октября.
        #
        # Ключ здесь не требуется намеренно: состояние обязано отвечать и тогда,
        # когда ключ не настроен, иначе «нет доступа» и «нет службы» снова
        # сливаются в один ответ. Данных каталога тело не несёт.
        if путь in ("/healthz", "/api/app/v1/healthz"):
            # Готовность — это НЕ «процесс жив». Без настроенного ключа служба
            # данные не отдаёт, и состояние обязано это называть: иначе
            # «ok: true» на выложенной наружу службе означало бы работающий
            # доступ, которого нет.
            ключ_задан = bool(self.ключ)
            return self._ответ(200 if ключ_задан else 503, {
                "ok": ключ_задан,
                "ready": ключ_задан,
                "keyConfigured": ключ_задан,
                "reason": None if ключ_задан else
                          ("файл ключа клиента не задан или пуст: данные не "
                           "отдаются, пока ключ не настроен"),
                "version": ВЕРСИЯ,
                "site": self.каталог.site_id,
                "titles": len(self.каталог.по_ид),
                "catalogRevision": self.каталог.revision,
                "catalogBuiltAt": self.каталог.built_at,
                "catalogReloadedAt": self.обновитель.перечитано if self.обновитель else None,
                "catalogReloadError": self.обновитель.ошибка if self.обновитель else None,
                "configChannels": {к: (р or {}).get("revisionId") if not ош else "error"
                                   for к in КАНАЛЫ
                                   for р, ош in [self.конфигурация.действующая(к)
                                                 if self.конфигурация else (None, None)]}})
        if not self._ключ_верен():
            return self._отказ(
                401, "unauthorized",
                "нужен верный заголовок X-App-Key" if self.ключ else
                "ключ клиента на сервере не настроен: доступ закрыт")
        if not self._частота_в_норме():
            return self._отказ(429, "rate_limited",
                               f"не больше {ПРЕДЕЛ_ЗАПРОСОВ_В_МИНУТУ} запросов в минуту",
                               {"Retry-After": "60"})

        м = re.fullmatch(r"/api/app/v1/search", путь)
        if м:
            запрос = (параметры.get("q") or [""])[0].strip()
            if not (2 <= len(запрос) <= 100):
                return self._отказ(400, "bad_request",
                                   "q обязателен, от 2 до 100 знаков")
            try:
                смещение = int((параметры.get("cursor") or ["0"])[0] or 0)
                предел = int((параметры.get("limit") or ["20"])[0] or 20)
            except ValueError:
                return self._отказ(400, "bad_request", "cursor и limit — числа")
            предел = max(1, min(предел, ПРЕДЕЛ_СТРАНИЦЫ))
            items, дальше, всего = self.каталог.искать(запрос, max(0, смещение), предел)
            return self._ответ(200, {"items": items,
                                     "nextCursor": str(дальше) if дальше else None,
                                     "total": всего})

        # Перечень для главной. Форма запрошена клиентом (уточнение 002): та же
        # страница с курсором, что у поиска, но порядок — по дате добавления, и
        # можно сузить жанром. Правило ряда называется в ответе полем `rule`:
        # «новое» у нас — это порядок по `addedAt` снимка, и приложение не
        # должно домысливать за нас, что это значит.
        м = re.fullmatch(r"/api/app/v1/titles", путь)
        if м:
            порядок = (параметры.get("sort") or ["added"])[0].strip() or "added"
            if порядок != "added":
                return self._отказ(400, "bad_request",
                                   "sort поддерживает только added: других "
                                   "измеренных порядков у снимка нет")
            жанр = (параметры.get("genre") or [""])[0].strip().lower()
            try:
                смещение = max(0, int((параметры.get("cursor") or ["0"])[0] or 0))
                предел = int((параметры.get("limit") or ["20"])[0] or 20)
            except ValueError:
                return self._отказ(400, "bad_request", "cursor и limit — числа")
            предел = max(1, min(предел, ПРЕДЕЛ_СТРАНИЦЫ))
            items, дальше, всего = self.каталог.перечислить(жанр, смещение, предел)
            return self._ответ(200, {
                "rule": "added: порядок по дате добавления в снимок каталога",
                "genre": жанр or None,
                "items": items,
                "nextCursor": str(дальше) if дальше else None,
                "total": всего})

        м = re.fullmatch(r"/api/app/v1/titles/([^/]+)", путь)
        if м:
            запись = self.каталог.по_ид.get(м.group(1))
            if запись is None:
                return self._отказ(404, "not_found", "тайтла нет в снимке")
            return self._ответ(200, self.каталог.наружу(запись))

        м = re.fullmatch(r"/api/app/v1/titles/([^/]+)/seasons", путь)
        if м:
            if м.group(1) not in self.каталог.по_ид:
                return self._отказ(404, "not_found", "тайтла нет в снимке")
            return self._ответ(200, self.каталог.сезоны(м.group(1)))

        м = re.fullmatch(r"/api/app/v1/seasons/([^/]+):s(\d+)/episodes", путь)
        if м:
            ид, сезон = м.group(1), int(м.group(2))
            if ид not in self.каталог.по_ид:
                return self._отказ(404, "not_found", "тайтла нет в снимке")
            серии = self.каталог.серии(ид, сезон)
            if not серии:
                return self._отказ(404, "not_found", "такого сезона нет")
            return self._ответ(200, серии)

        м = re.fullmatch(r"/api/app/v1/episodes/([^/]+)/sources", путь)
        if м:
            # Две формы адреса, обе рабочие.
            #
            # Сериал: `episodes/<contentId>:s<N>:e<M>/sources` — идентификатор
            # серии несёт тайтл в себе. Фильм: клиент прислал форму
            # `episodes/movie/sources?contentId=…`, и она же стоит в его
            # исходном задании, поэтому поддержана как есть, а не заменена
            # своей: называть клиенту «мою» форму, когда его собственная
            # договорённость уже написана, значит ломать её без причины.
            хвост = м.group(1)
            ид = (параметры.get("contentId") or [""])[0].strip() \
                if хвост == "movie" else хвост.split(":")[0]
            if not ид:
                return self._отказ(400, "bad_request",
                                   "для фильма нужен contentId в запросе")
            запись = self.каталог.по_ид.get(ид)
            if запись is None:
                return self._отказ(404, "not_found", "тайтла нет в снимке")
            # Прямых ссылок у фабрики нет и выдумывать их нельзя: воспроизведение
            # на сайте делает web-компонент провайдера. Ответ честный и машинно
            # различимый, плюс сведения о встраиваемом пути — чтобы клиент не
            # угадывал, а знал, почему пусто.
            провайдеры = [{"provider": и.get("provider"),
                           "sourceId": и.get("source_id"),
                           "availability": и.get("availability_status")}
                          for и in запись["_sources"]]
            return self._ответ(200, {
                "sources": [],
                # Одна явная причина вместо двух похожих: прямого потока нет
                # не потому, что «запись не вышла», а потому, что договора на
                # прямые ссылки для приложения нет. Код обязан читаться как
                # ограничение, а не как временная пустота.
                "reason": "NO_SOURCE_CONTRACT_RELEASED",
                "embed": {"kind": "provider-web-component",
                          "provider": "cdnvideohub",
                          "note": ("прямой поток фабрикой не выдаётся: провайдер "
                                   "отдаёт воспроизведение только своим веб-"
                                   "компонентом. Нативному плееру это не подходит"),
                          "providerRefs": провайдеры}})

        # «Где смотреть». Отдельное хранилище подтверждённых сведений, не снимок
        # каталога: наличие фильма в сервисе — утверждение о третьей стороне, и
        # без одобренного источника оно не делается. `unknown` — честное «мы не
        # знаем», а не «нигде нет»; ошибка хранилища — 503, а не пустой список.
        м = re.fullmatch(r"/api/app/v1/titles/([^/]+)/offers", путь)
        if м:
            ид = м.group(1)
            if ид not in self.каталог.по_ид:
                return self._отказ(404, "not_found", "тайтла нет в снимке")
            регион = (параметры.get("region") or [""])[0].strip().upper()
            if not РЕГИОН.fullmatch(регион):
                return self._отказ(400, "bad_request", "region обязателен: ISO 3166-1 alpha-2, например RU")
            данные, ошибка = (self.предложения.снимок() if self.предложения else (None, None))
            if ошибка:
                return self._отказ(503, "offers_unavailable", ошибка, {"Retry-After": "60"})
            return self._ответ(200, ответ_предложений(данные, ид, регион, time.time()))

        # Главная и подборки приложения: действующая ревизия канала. Каналы
        # закрыты списком — произвольное имя не должно читать произвольный файл.
        м = re.fullmatch(r"/api/app/v1/config/([^/]+)", путь)
        if м:
            канал = м.group(1)
            if канал not in КАНАЛЫ:
                return self._отказ(404, "not_found", "нет такого канала")
            ревизия, ошибка = (self.конфигурация.действующая(канал)
                               if self.конфигурация else (None, None))
            if ошибка:
                return self._отказ(503, "config_unavailable", ошибка, {"Retry-After": "60"})
            if ревизия is None:
                return self._отказ(404, "NO_CONFIG", f"в канале {канал} ничего не опубликовано")
            метка = f'"{ревизия.get("revisionId")}.{self.каталог.revision[:12]}"'
            if self.headers.get("If-None-Match") == метка:
                self.send_response(304)
                self.send_header("ETag", метка)
                self.end_headers()
                return
            return self._ответ(200, отдать_конфигурацию(ревизия, self.каталог),
                               {"ETag": метка, "Cache-Control": "max-age=60"})

        return self._отказ(404, "not_found", "нет такого маршрута")


def главное(argv=None) -> int:
    ap = argparse.ArgumentParser(description="читающее API каталога для клиента")
    ap.add_argument("--site", required=True)
    ap.add_argument("--data-dir", required=True, type=pathlib.Path)
    ap.add_argument("--bind", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=9180)
    ap.add_argument("--key-file", type=pathlib.Path, default=None)
    ap.add_argument("--config-dir", type=pathlib.Path, default=None,
                    help="каталог ревизий главной приложения (пишет Control API)")
    a = ap.parse_args(argv)
    Обработчик.каталог = Каталог(a.site, a.data_dir)
    Обработчик.предложения = ХранилищеПредложений(a.data_dir / f"{a.site}-offers.json")
    Обработчик.конфигурация = ХранилищеКонфигурации(a.config_dir)
    Обработчик.обновитель = ОбновительСнимка(a.site, a.data_dir)
    if a.key_file and a.key_file.is_file():
        Обработчик.ключ = a.key_file.read_text(encoding="utf-8").strip()
    rss = 0
    try:
        for с in pathlib.Path("/proc/self/status").read_text().splitlines():
            if с.startswith("VmRSS:"):
                rss = int(с.split()[1]) // 1024
    except OSError:
        pass
    print(f"[app-api] {a.site}: тайтлов {len(Обработчик.каталог.по_ид)}, "
          f"поколение {Обработчик.каталог.revision[:12]}, RSS {rss} МиБ, "
          f"слушаю {a.bind}:{a.port}, ключ "
          f"{'задан' if Обработчик.ключ else 'не задан'}", flush=True)
    ThreadingHTTPServer((a.bind, a.port), Обработчик).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(главное())
