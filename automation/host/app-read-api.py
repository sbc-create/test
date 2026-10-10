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
  внутренний кадр и запрашивает поток. См. `docs/APP_READ_API.md`.

Память. Снимок подробностей — десятки мегабайт, и разбор его целиком стоит
гигабайт. Поэтому при старте строится УЗКИЙ указатель: только поля, которые
отдаются клиенту. Большая структура освобождается сразу после.
"""
from __future__ import annotations

import argparse
import gc
import hmac
import json
import os
import pathlib
import re
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

ВЕРСИЯ = "app-read-api/1"
ПРЕДЕЛ_СТРАНИЦЫ = 50
ПРЕДЕЛ_ЗАПРОСОВ_В_МИНУТУ = 120
КИРИЛЛИЦА = re.compile(r"[А-Яа-яЁё]")


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


class Обработчик(BaseHTTPRequestHandler):
    server_version = ВЕРСИЯ
    каталог: Каталог
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

    # --- маршруты ---------------------------------------------------------
    def do_GET(self) -> None:  # noqa: N802 — подпись из базового класса
        разбор = urlparse(self.path)
        путь = разбор.path.rstrip("/") or "/"
        параметры = parse_qs(разбор.query)
        if путь == "/healthz":
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
                "catalogBuiltAt": self.каталог.built_at})
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

        return self._отказ(404, "not_found", "нет такого маршрута")


def главное(argv=None) -> int:
    ap = argparse.ArgumentParser(description="читающее API каталога для клиента")
    ap.add_argument("--site", required=True)
    ap.add_argument("--data-dir", required=True, type=pathlib.Path)
    ap.add_argument("--bind", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=9180)
    ap.add_argument("--key-file", type=pathlib.Path, default=None)
    a = ap.parse_args(argv)
    Обработчик.каталог = Каталог(a.site, a.data_dir)
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
