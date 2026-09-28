#!/usr/bin/env python3
"""Сверка `seasons[].avail` снимка с тем, что провайдер отдаёт СЕЙЧАС.

Только чтение. Ничего не пишет, ничего не перезапускает, снимок не трогает:
это измерение масштаба дефекта перед правкой и после неё, а не второй
производитель данных. Производитель один — суточный конвейер; согласованием
между его прогонами занимается `tools/episode_availability.py` в репозитории
конкретной ячейки.

Зачем отдельный инструмент. Задание требует «сначала автоматическую сверку
данных с ограниченной нагрузкой», по ВСЕМ семействам и не по первым двадцати
записям. Инструмент согласования на это не годится: он живёт в репозитории
одной ячейки, пишет снимок и ставит отметку перезапуска.

Правила кандидатов здесь не копируются. Порядок «какой идентификатор витрина
поставит на страницу» берётся из САМОГО рантайма витрины (`кандидаты_источника`
в режиме `provider-id`, `источник_плеера` иначе): вторая копия правила, разойдясь
с рендерером, измеряла бы доступность записи, которую страница всё равно не
играет.

Классы дефекта, которые инструмент различает:

  promise-empty  витрина обещает серии 1..avail, а у провайдера в этом отрезке
                 НЕТ НИ ОДНОЙ дорожки. Это «Скотты»: карточка говорит
                 «доступно 1», плеер монтируется, провайдер отвечает noData.
  zero-only      единственные дорожки записи имеют номер 0 (спецвыпуск).
                 Прежний рантайм отвергал эпизоды меньше единицы, и такая
                 дорожка была недостижима со страницы вовсе.
  understated    непрерывный ряд от первой серии ДЛИННЕЕ записанного `avail`.
                 Это «Мастер Омюр»: снимок отстал от источника.
  gaps           у провайдера есть номера выше непрерывного ряда — одним
                 числом такой сезон не описывается в принципе.
  source-none    провайдер не отдал ни одного кандидата: либо дорожек нет,
                 либо запрос временно не прошёл. РАЗНЫЕ вещи, и они разделены:
                 сетевая ошибка попадает в `errors`, а не в вывод о наличии.

`source-none` по сетевой ошибке НЕ считается подтверждением отсутствия. Это
прямое требование задания: «различай подтверждённое отсутствие потока,
временную ошибку запроса и устаревшие данные».
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import random
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ПЛЕЙЛИСТ = "https://plapi.cdnvideohub.com/api/v1/player/sv/playlist"

#: Сколько запасных кандидатов спрашивать, прежде чем сказать «источника нет».
#: Ровно столько, сколько перебирает клиент на странице.
ЗАПАСНЫХ = 3


def рантайм(путь: Path, манифест: Path | None):
    """Рантайм витрины как модуль: источник правды о порядке кандидатов.

    Импорт по пути, а не по имени: в имени файла дефис. Манифест шаблона
    подставляется явно — рантайм читает его при импорте и без него отказывает,
    а его умолчание ведёт в общее дерево, то есть к снимку СОСЕДНЕЙ витрины.
    """
    if манифест is not None:
        os.environ["LORDS_TEMPLATE_MANIFEST"] = str(манифест)
        os.environ["ANIMEDIA_TEMPLATE_MANIFEST"] = str(манифест)
        os.environ["ANIMEGO_TEMPLATE_MANIFEST"] = str(манифест)
    спец = importlib.util.spec_from_file_location("_витрина_рантайм", путь)
    модуль = importlib.util.module_from_spec(спец)
    sys.modules["_витрина_рантайм"] = модуль
    sys.path.insert(0, str(Path(путь).parent))
    спец.loader.exec_module(модуль)
    return модуль


def кандидаты(модуль, деталь: dict) -> list:
    """Те же кандидаты и в том же порядке, что уйдут в `data-src-candidates`."""
    if getattr(модуль, "ПЛЕЕР", {}).get("source_mode") == "provider-id":
        return list(модуль.кандидаты_источника(деталь))
    агрегатор, ид = модуль.источник_плеера(деталь)
    return [(агрегатор, ид)] if агрегатор and ид else []


class ВременнаяОшибка(RuntimeError):
    """Запрос не состоялся. Это НЕ вывод об отсутствии дорожки."""


def спросить(издатель: str, агрегатор: str, ид: str, домен: str,
             таймаут: float = 20.0) -> list:
    адрес = f"{ПЛЕЙЛИСТ}?" + urllib.parse.urlencode(
        {"pub": издатель, "id": ид, "aggr": агрегатор})
    запрос = urllib.request.Request(адрес, headers={
        "Origin": f"https://{домен}",
        "Referer": f"https://{домен}/",
        "Accept": "application/json",
        "User-Agent": "site-factory-episode-survey/1.0 (read-only)",
    })
    try:
        with urllib.request.urlopen(запрос, timeout=таймаут) as ответ:
            тело = json.loads(ответ.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code in (404, 410):
            return []            # провайдер ответил: записи нет
        raise ВременнаяОшибка(f"HTTP {e.code}") from e
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as e:
        raise ВременнаяОшибка(str(e)) from e
    if not isinstance(тело, dict):
        raise ВременнаяОшибка("ответ не объект")
    return [э for э in (тело.get("items") or []) if isinstance(э, dict)]


def дорожки_по_сезонам(элементы: list) -> dict:
    """Номера серий с ПОТОКОМ, по сезонам.

    Дорожкой считается запись с идентификатором потока (`vkId` или `cvhId`),
    а не заготовка с одним названием: заготовка на странице не играет.
    """
    итог: dict[int, set] = {}
    for э in элементы:
        if not (str(э.get("vkId") or "").strip() or str(э.get("cvhId") or "").strip()):
            continue
        try:
            с = int(э.get("season") or 0)
            н = int(э.get("episode"))
        except (TypeError, ValueError):
            continue
        if с < 1 or н < 0:
            continue
        итог.setdefault(с, set()).add(н)
    return итог


def ряд_от_первой(номера: set) -> int:
    """Длина непрерывного ряда от серии 1. Из {1,2,3} — 3, из {1,3} — 1, из {0} — 0."""
    н = 0
    while (н + 1) in номера:
        н += 1
    return н


def разобрать(деталь: dict, найдено: dict) -> list:
    """Классы дефекта по одному произведению."""
    выводы = []
    for сезон in (деталь.get("seasons") or []):
        н = int(сезон.get("n") or 0)
        eps = int(сезон.get("eps") or 0)
        avail = int(сезон.get("avail") or 0)
        if н < 1 or eps < 1:
            continue
        if н not in найдено:
            # Сезона в ответе нет вовсе: расхождение нумерации или неполный
            # ответ. Доказательством отсутствия он не является.
            continue
        номера = найдено[н]
        ряд = ряд_от_первой(номера)
        классы = []
        if avail >= 1 and not (номера & set(range(1, avail + 1))):
            классы.append("promise-empty")
        if номера and not {x for x in номера if x >= 1}:
            классы.append("zero-only")
        if ряд > avail:
            классы.append("understated")
        if {x for x in номера if x > ряд and x >= 1}:
            классы.append("gaps")
        if классы:
            выводы.append({"season": н, "eps": eps, "avail": avail,
                           "ряд": ряд, "номера": sorted(номера)[:40],
                           "всего_номеров": len(номера), "классы": классы})
    return выводы


def выборка(детали: dict, размер: int, зерно: int, слаги: list) -> list:
    if слаги:
        return [(с, детали[с]) for с in слаги if с in детали]
    сериалы = [(с, д) for с, д in детали.items()
               if (д.get("seasons") or []) and any(int(x.get("eps") or 0) >= 1
                                                   for x in д["seasons"])]
    сериалы.sort(key=lambda п: п[0])          # порядок не зависит от словаря
    rnd = random.Random(зерно)
    rnd.shuffle(сериалы)
    return сериалы[:размер]


def main(argv=None) -> int:
    р = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    р.add_argument("--runtime", required=True, help="lords-/animego-/animedia-frontend.py витрины")
    р.add_argument("--manifest", default="", help="template-manifest.json этой витрины")
    р.add_argument("--snapshot", required=True, help="<site>-details.json витрины")
    р.add_argument("--publisher", required=True)
    р.add_argument("--origin", required=True, help="домен витрины без схемы")
    р.add_argument("--sample", type=int, default=120)
    р.add_argument("--slugs", default="", help="слаги через запятую вместо выборки")
    р.add_argument("--rps", type=float, default=1.5)
    р.add_argument("--seed", type=int, default=20260928)
    р.add_argument("--out", default="")
    args = р.parse_args(argv)

    модуль = рантайм(Path(args.runtime),
                     Path(args.manifest) if args.manifest else None)
    снимок = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
    детали = снимок.get("details") or снимок

    пауза = 1.0 / args.rps if args.rps > 0 else 0.0
    находки, ошибки, без_источника = [], [], []
    спрошено = 0
    начало = time.time()

    for слаг, деталь in выборка(детали, args.sample, args.seed,
                                [с.strip() for с in args.slugs.split(",") if с.strip()]):
        элементы, сбой = [], None
        for агрегатор, ид in кандидаты(модуль, деталь)[:ЗАПАСНЫХ + 1]:
            if спрошено:
                time.sleep(пауза)
            спрошено += 1
            try:
                элементы = спросить(args.publisher, агрегатор, ид, args.origin)
            except ВременнаяОшибка as e:
                сбой = f"{агрегатор}:{ид} {e}"
                continue
            сбой = None
            if элементы:
                break
        if сбой is not None and not элементы:
            ошибки.append({"slug": слаг, "reason": сбой})
            continue
        найдено = дорожки_по_сезонам(элементы)
        if not найдено:
            без_источника.append(слаг)
            continue
        выводы = разобрать(деталь, найдено)
        if выводы:
            находки.append({"slug": слаг, "name": деталь.get("name"),
                            "id": деталь.get("id"), "сезоны": выводы})

    свод: dict[str, int] = {}
    for н in находки:
        for с in н["сезоны"]:
            for к in с["классы"]:
                свод[к] = свод.get(к, 0) + 1

    отчёт = {
        "origin": args.origin, "publisher": args.publisher,
        "snapshot": args.snapshot,
        "catalog_revision": снимок.get("catalog_revision"),
        "catalog_built_at": снимок.get("catalog_built_at"),
        "проверено_записей": args.sample if not args.slugs else len(args.slugs.split(",")),
        "запросов": спрошено, "секунд": round(time.time() - начало, 1),
        "свод_по_классам": свод,
        "записей_с_дефектом": len(находки),
        "без_дорожек_у_провайдера": len(без_источника),
        "временных_ошибок": len(ошибки),
        "находки": находки,
        "ошибки": ошибки,
    }
    текст = json.dumps(отчёт, ensure_ascii=False, indent=1)
    if args.out:
        Path(args.out).write_text(текст, encoding="utf-8")
        print(json.dumps({к: в for к, в in отчёт.items() if к != "находки"},
                         ensure_ascii=False, indent=1))
    else:
        print(текст)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
