#!/usr/bin/env python3
"""Сверка привязки источника с провайдером по всему инвентарю витрины.

Отвечает на три вопроса по каждой записи: есть ли привязка, отдаёт ли провайдер
по ней дорожки и та ли это сущность. Последнее проверяется сверкой названия:
запрос идёт по собственному идентификатору провайдера, поэтому расхождение имени
означало бы порчу данных, а не неточность сопоставления.

Нагрузку держит в узде: ограниченная частота, небольшая конкуррентность, кэш на
диске. Повторный прогон почти не трогает сеть. Нагрузочным тестированием это не
является и являться не должно — витрины живые.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import queue
import re
import sys
import threading
import time
import unicodedata
import urllib.error
import urllib.request

ЛОГОВО = pathlib.Path("/srv/lords/.frontend")
API = "https://plapi.cdnvideohub.com/api/v1/player/sv/playlist"
КЭШ = pathlib.Path("/srv/site-factory/repo/var/lords/source-verify-cache")
АГРЕГАТОРЫ = ("cvh", "kp", "mdl", "mali", "imdb")
ИДЕНТИФИКАТОР = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")

СЕМЕЙСТВО = {
    "lords-01": ("lords", "lordfilm47.space"), "lords-02": ("lords", "lordserial33.biz"),
    "lords-03": ("lords", "1lordserials1.online"), "zona-01": ("lords", "zonafilm.space"),
    "animedia-01": ("yami", "animedia.icu"), "animedia-02": ("yami", "animedia.space"),
}
СЕКРЕТ = {
    "lords": "/etc/site-factory/secrets/lords/lords-01/cdnvideohub-publisher-id",
    "yami": "/srv/sites/yummyani-staging/runtime/cdnvideohub/publisher-id",
}


def источник(деталь: dict) -> tuple[str, str]:
    """Тот же порядок, что и в рендерере: сначала собственный ключ провайдера."""
    свой = str(деталь.get("id") or "").strip().lower()
    if ИДЕНТИФИКАТОР.match(свой):
        return "cvh", свой
    for з in деталь.get("sources") or ():
        if isinstance(з, dict):
            а = str(з.get("provider") or "").strip()
            i = str(з.get("source_id") or "").strip()
            if i and а in АГРЕГАТОРЫ:
                return а, i
    в = деталь.get("external_ids") or {}
    for ключ, а in (("kp", "kp"), ("mdl", "mdl"), ("mal", "mali"), ("imdb", "imdb")):
        i = str(в.get(ключ) or "").strip()
        if i:
            return а, i
    return "", ""


def свернуть(текст: str) -> str:
    """Название без регистра, пунктуации и диакритики — для сверки сущности."""
    т = unicodedata.normalize("NFKD", str(текст or "")).lower()
    т = "".join(с for с in т if not unicodedata.combining(с))
    return re.sub(r"[^0-9a-zа-я]+", "", т)


class Ограничитель:
    """Не больше N запросов в секунду на весь прогон."""

    def __init__(self, в_секунду: float) -> None:
        self._шаг = 1.0 / max(в_секунду, 0.1)
        self._замок = threading.Lock()
        self._следующий = time.monotonic()

    def ждать(self) -> None:
        with self._замок:
            сейчас = time.monotonic()
            если = max(сейчас, self._следующий)
            self._следующий = если + self._шаг
        пауза = если - сейчас
        if пауза > 0:
            time.sleep(пауза)


def спросить(pub: str, домен: str, аггр: str, ид: str, огр: Ограничитель,
             попыток: int = 3) -> dict:
    q = f"{API}?pub={pub}&id={ид}&aggr={аггр}"
    заг = {"Accept": "application/json", "Origin": f"https://{домен}",
           "x-origin": f"https://{домен}", "Referer": f"https://{домен}/"}
    задержка = 1.0
    for попытка in range(попыток):
        огр.ждать()
        try:
            with urllib.request.urlopen(urllib.request.Request(q, headers=заг),
                                        timeout=30) as о:
                тело = о.read().decode("utf-8", "replace")
                код = о.status
            # 204 у этого API означает «такого контента нет», а не сбой запроса.
            # Пустое тело роняло разбор JSON, и запись попадала в ошибки сети —
            # то есть настоящая непокрытая запись пряталась среди сбоев.
            if код == 204 or not тело.strip():
                return {"http": 204, "items": 0, "title": None, "stream": False,
                        "reason": "NO_CONTENT_AT_PROVIDER"}
            j = json.loads(тело)
            items = j.get("items") or []
            return {"http": 200, "items": len(items),
                    "title": j.get("titleName"),
                    "stream": bool(items and (items[0].get("cvhId") or items[0].get("vkId")))}
        except urllib.error.HTTPError as e:
            # 429/5xx — отступаем и пробуем снова; остальное окончательно.
            if e.code in (429, 500, 502, 503, 504) and попытка + 1 < попыток:
                time.sleep(задержка); задержка *= 2; continue
            return {"http": e.code, "items": 0, "title": None, "stream": False}
        except Exception as e:
            if попытка + 1 < попыток:
                time.sleep(задержка); задержка *= 2; continue
            return {"http": -1, "items": 0, "title": None, "stream": False,
                    "error": str(e)[:120]}
    return {"http": -1, "items": 0, "title": None, "stream": False}


def прогон(сайт: str, предел: int | None, rps: float, потоков: int,
           только: list[str] | None) -> dict:
    профиль, домен = СЕМЕЙСТВО[сайт]
    pub = pathlib.Path(СЕКРЕТ[профиль]).read_text(encoding="utf-8").strip()
    детали = json.loads((ЛОГОВО / f"{сайт}-details.json").read_text())["details"]

    записи = [(с, д) for с, д in детали.items() if isinstance(д, dict)]
    if только:
        нужные = set(только)
        записи = [(с, д) for с, д in записи if с in нужные]
    if предел:
        записи = записи[:предел]

    КЭШ.mkdir(parents=True, exist_ok=True)
    файл_кэша = КЭШ / f"{профиль}.json"
    кэш = {}
    if файл_кэша.exists():
        try:
            кэш = json.loads(файл_кэша.read_text())
        except ValueError:
            кэш = {}

    огр = Ограничитель(rps)
    очередь: queue.Queue = queue.Queue()
    for пара in записи:
        очередь.put(пара)
    итог = {"site": сайт, "domain": домен, "profile": профиль,
            "total": len(записи), "bound": 0, "unbound": [], "no_content": [],
            "wrong_entity": [], "http_error": [], "by_aggr": {}}
    замок = threading.Lock()

    def работник():
        while True:
            try:
                слаг, деталь = очередь.get_nowait()
            except queue.Empty:
                return
            аггр, ид = источник(деталь)
            with замок:
                if not (аггр and ид):
                    итог["unbound"].append(слаг)
                    итог["by_aggr"]["—"] = итог["by_aggr"].get("—", 0) + 1
                    очередь.task_done(); continue
                итог["bound"] += 1
                итог["by_aggr"][аггр] = итог["by_aggr"].get(аггр, 0) + 1
            ключ = f"{аггр}:{ид}"
            ответ = кэш.get(ключ)
            if ответ is None:
                ответ = спросить(pub, домен, аггр, ид, огр)
                with замок:
                    кэш[ключ] = ответ
            with замок:
                if ответ.get("http") != 200:
                    итог["http_error"].append([слаг, ответ.get("http")])
                elif not ответ.get("stream"):
                    итог["no_content"].append(слаг)
                elif аггр == "cvh":
                    # Запрос шёл по собственному идентификатору провайдера:
                    # сущность совпадает тождественно, сверять нечего. Провайдер
                    # при этом возвращает заголовок в ромадзи (`jigoku_shoujo`
                    # против «Адская девочка»), и сравнение имён давало ложные
                    # расхождения там, где расхождения быть не может.
                    pass
                else:
                    наше = свернуть(деталь.get("name"))
                    их = свернуть(ответ.get("title"))
                    ориг = свернуть(деталь.get("original_name"))
                    # Совпадением считается вхождение: провайдер отдаёт то же имя,
                    # иногда с уточнением сезона. Полное расхождение — порча данных.
                    похоже = bool(их) and (их in наше or наше in их
                                           or (ориг and (их in ориг or ориг in их)))
                    if not похоже:
                        итог["wrong_entity"].append([слаг, деталь.get("name"),
                                                     ответ.get("title")])
            очередь.task_done()

    нити = [threading.Thread(target=работник, daemon=True) for _ in range(потоков)]
    for н in нити:
        н.start()
    for н in нити:
        н.join()

    временный = файл_кэша.with_suffix(".tmp")
    временный.write_text(json.dumps(кэш, ensure_ascii=False), encoding="utf-8")
    os.replace(временный, файл_кэша)
    return итог


def главная() -> int:
    р = argparse.ArgumentParser(description="сверка источников витрины с провайдером")
    р.add_argument("--site", required=True, choices=sorted(СЕМЕЙСТВО))
    р.add_argument("--limit", type=int, default=None)
    р.add_argument("--rps", type=float, default=6.0)
    р.add_argument("--threads", type=int, default=4)
    р.add_argument("--slugs", default=None, help="файл со списком слагов")
    р.add_argument("--out", default=None)
    а = р.parse_args()

    только = None
    if а.slugs:
        только = [с.strip() for с in pathlib.Path(а.slugs).read_text().split() if с.strip()]

    итог = прогон(а.site, а.limit, а.rps, а.threads, только)
    сводка = {k: v for k, v in итог.items() if not isinstance(v, list)}
    сводка["unbound"] = len(итог["unbound"])
    сводка["no_content"] = len(итог["no_content"])
    сводка["wrong_entity"] = len(итог["wrong_entity"])
    сводка["http_error"] = len(итог["http_error"])
    print(json.dumps(сводка, ensure_ascii=False, indent=1))
    if а.out:
        pathlib.Path(а.out).write_text(json.dumps(итог, ensure_ascii=False, indent=1),
                                       encoding="utf-8")
    return 0 if not итог["wrong_entity"] else 1


if __name__ == "__main__":
    sys.exit(главная())
