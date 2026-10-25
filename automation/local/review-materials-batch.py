#!/usr/bin/env python3
"""Рецензия материалов пачкой: четыре проверки по каждому, без штампа.

ЗАДАНИЕ ВЛАДЕЛЬЦА 24.10: «Сегодняшние 29 материалов проверь текущей датой. Не
оформляй фиктивные рецензии задним числом; найденные ошибки исправляй
адресно».

Поэтому инструмент НЕ ставит «принято» всем подряд. Он выполняет те же четыре
проверки, которые требует операция рецензии, и для каждого материала
печатает, что именно проверено и чем подтверждено. Запись отзыва (`--record`)
делается ТОЛЬКО тем материалам, у которых все четыре прошли; остальные
остаются без отзыва с названной причиной — это и есть «найденные ошибки
исправляй адресно», а не «подпиши и забудь».

ЧТО ПРОВЕРЯЕТСЯ и чем именно:

  соответствие_произведению     название записи каталога встречается в тексте;
  факты_подтверждены_источниками у черновика записан хотя бы один источник;
  посторонних_вставок_нет       имён собственных внутри предложений, которых
                                нет ни в записи каталога, ни в слаге, — нет;
  качество_текста               `editorial.проверить_материал` не нашёл бед.

ЧЕГО ИНСТРУМЕНТ НЕ УМЕЕТ, и это сказано прямо: он не открывает внешние
источники. Если в тексте есть имя, которого нет в снимке каталога, он не
может подтвердить его по shikimori.io — такой материал он НЕ принимает, а
выносит в список «нужна сверка по внешнему источнику». Автоматическая
проверка, которая делает вид, что сходила в источник, хуже её отсутствия.
"""
from __future__ import annotations

import argparse
import datetime
import glob
import importlib.util
import json
import pathlib
import re
import sys

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
if str(КОРЕНЬ) not in sys.path:
    sys.path.insert(0, str(КОРЕНЬ))

from factory.qwen import editorial  # noqa: E402

_о = КОРЕНЬ / "automation" / "local" / "editorial-inventory.py"
_с = importlib.util.spec_from_file_location("editorial_inventory", _о)
ОПИСЬ = importlib.util.module_from_spec(_с)
assert _с.loader is not None
_с.loader.exec_module(ОПИСЬ)

КАТАЛОГИ = ("/srv/lords/.frontend/*-details.json", "/srv/*/data/*-details.json")
СЛОВО = re.compile(r"[А-ЯЁ][а-яё]{3,}")
ПОЛЯ = ("name", "original_name", "year", "genres", "countries", "type",
        "description")


def черновики(дата: str) -> list[dict]:
    из = []
    for путь in sorted(glob.glob("/srv/sites/*/runtime/overlays/*/drafts.json")):
        к = pathlib.Path(путь).parent
        for з in ОПИСЬ._items(json.loads(
                pathlib.Path(путь).read_text(encoding="utf-8"))):
            if not isinstance(з, dict):
                continue
            if дата and (з.get("prepared_at") or "")[:10] != дата:
                continue
            из.append({**з, "домен": к.name, "каталог": к})
    return из


def опора(слаги: set[str]) -> dict[str, dict]:
    """Запись каталога по слагу. Каталоги читаются ПО ОДНОМУ: они по 95–128 МиБ."""
    из: dict[str, dict] = {}
    файлы = []
    for об in КАТАЛОГИ:
        файлы.extend(glob.glob(об))
    for ф in sorted(set(файлы)):
        п = pathlib.Path(ф)
        if п.is_symlink():
            continue
        try:
            д = json.loads(п.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        детали = д.get("details") if isinstance(д, dict) else None
        if isinstance(детали, dict):
            for с in слаги:
                if с not in из and детали.get(с):
                    из[с] = детали[с]
        del д, детали
    return из


def чужие(тело: str, запись: dict, слаг: str) -> list[str]:
    поле = " ".join(str(запись.get(к) or "") for к in ПОЛЯ) + " " + слаг
    поле = poleL = поле.lower()
    из = []
    for м in СЛОВО.finditer(тело):
        до = тело[:м.start()].rstrip()
        if not до or до[-1] in ".!?…»\"":
            continue
        с = м.group(0)
        if с.lower() not in poleL and с not in из:
            из.append(с)
    return из


def проверить(з: dict, запись: dict) -> dict:
    тело = з.get("body") or ""
    слаг = з.get("slug") or ""
    имя = str(запись.get("name") or "")
    н = lambda т: " ".join(т.split()).lower().replace("ё", "е")
    соответствие = bool(имя) and н(имя) in н(тело)
    источники = list(з.get("sources") or [])
    посторонние = чужие(тело, запись, слаг) if запись else ["(записи каталога нет)"]
    беды = editorial.проверить_материал(тело, {"facts": запись or {}})
    return {
        "соответствие_произведению": соответствие,
        "факты_подтверждены_источниками": bool(источники),
        "посторонних_вставок_нет": not посторонние,
        "качество_текста": not беды,
        "_посторонние": посторонние,
        "_беды": беды,
        "_имя_каталога": имя,
        "_источники": источники,
    }


def главное(argv: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--date", default=datetime.datetime.now(
        datetime.timezone.utc).strftime("%Y-%m-%d"))
    р.add_argument("--reviewer", default="")
    р.add_argument("--record", action="store_true")
    р.add_argument("--limit", type=int, default=0)
    р.add_argument("--external-verified", type=pathlib.Path,
                   help="файл внешней сверки имён (поля domain, slug, "
                        "not_found): чем подтверждена проверка имён, которую "
                        "этот инструмент сам сделать не может")
    а = р.parse_args(argv)

    зп = черновики(а.date)
    if not зп:
        print(f"НЕ ИЗМЕРЕНО: черновиков с датой подготовки {а.date} не найдено")
        return 2
    # Уже проверенные откладываются: иначе вывод показывает всю пачку заново,
    # и остаток работы в нём не виден. Измерено 25.10: прогон по 24.10 печатал
    # 52 материала, хотя 48 из них отзыв уже имели.
    проверенные = [з for з in зп if (з.get("review") or {}).get("verdict")]
    зп = [з for з in зп if not (з.get("review") or {}).get("verdict")]
    if проверенные:
        print(f"уже проверены ранее и отложены: {len(проверенные)}")
        for з in проверенные[:3]:
            о = з.get("review") or {}
            print(f"   {з['домен']:18} {str(з.get('slug'))[:36]:38}"
                  f" {о.get('verdict')} — {str(о.get('reviewer'))[:40]}"
                  f" {str(о.get('at'))[:16]}")
        if len(проверенные) > 3:
            print(f"   … и ещё {len(проверенные) - 3}")
        print()
    if not зп:
        print(f"материалов за {а.date} без записи о проверке нет:"
              f" все {len(проверенные)} уже проверены")
        return 0
    if а.limit:
        зп = зп[:а.limit]
    записи = опора({з.get("slug") or "" for з in зп})
    # Внешняя сверка имён. Инструмент НЕ открывает внешние источники — это
    # сказано в его описании. Если сверку сделал кто-то другой и приложил
    # доказательство, проверка «посторонних вставок нет» считается
    # подтверждённой ИМ, и это называется в заметках отзыва: чужая работа не
    # присваивается.
    внешняя: dict[tuple[str, str], dict] = {}
    if а.external_verified:
        try:
            сырое = json.loads(а.external_verified.read_text(encoding="utf-8"))
        except (OSError, ValueError) as ош:
            print(f"ОТКАЗ: файл внешней сверки не прочитан: {ош}")
            return 2
        for з in (сырое.get("results") if isinstance(сырое, dict) else сырое) or []:
            if isinstance(з, dict) and з.get("slug"):
                внешняя[(з.get("domain") or "", з["slug"])] = з
        print(f"внешняя сверка имён: {а.external_verified}, записей "
              f"{len(внешняя)}, метод: {str(сырое.get('method'))[:120]}")
    print(f"материалов за {а.date}: {len(зп)}; записей каталога найдено "
          f"{len(записи)}")
    print()
    годны, негодны = [], []
    for з in зп:
        итог = проверить(з, записи.get(з.get("slug") or "") or {})
        вн = внешняя.get((з["домен"], з.get("slug") or ""))
        итог["_внешняя"] = вн
        if вн is not None and not итог["посторонних_вставок_нет"]:
            if not (вн.get("not_found") or []):
                итог["посторонних_вставок_нет"] = True
                итог["_подтверждено_внешне"] = True
            else:
                итог["_внешне_не_найдено"] = list(вн.get("not_found") or [])
        все = all(итог[к] for к in editorial.ПРОВЕРКИ_РЕЦЕНЗИИ)
        (годны if все else негодны).append((з, итог))
        метка = "ГОДЕН" if все else "НЕ ПРИНЯТ"
        print(f"{метка:10} {з['домен']:18} {str(з.get('slug'))[:40]:42}"
              f" автор {str(з.get('author'))[:34]}")
        if not все:
            for к in editorial.ПРОВЕРКИ_РЕЦЕНЗИИ:
                if not итог[к]:
                    подробно = ""
                    if к == "посторонних_вставок_нет":
                        подробно = ": " + ", ".join(итог["_посторонние"][:6])
                        if итог.get("_внешне_не_найдено"):
                            подробно += (" | внешняя сверка не нашла: "
                                         + ", ".join(итог["_внешне_не_найдено"]))
                        elif итог.get("_внешняя") is None:
                            подробно += " | внешней сверки по этому слагу нет"
                    elif к == "качество_текста":
                        подробно = ": " + "; ".join(итог["_беды"][:2])
                    elif к == "соответствие_произведению":
                        подробно = (f": названия {итог['_имя_каталога']!r}"
                                    " в тексте нет")
                    print(f"           не прошло {к}{подробно}")
    print()
    print(f"годны к рецензии: {len(годны)}; не приняты: {len(негодны)}")
    if негодны:
        print("  не принятые отзыва НЕ получают: фиктивная рецензия хуже её"
              " отсутствия. Им нужна сверка по внешнему источнику или правка")

    if а.record:
        if not а.reviewer:
            print("ОТКАЗ: --record требует --reviewer (кто проверял)")
            return 2
        записано = отказано = 0
        for з, итог in годны:
            заметки = [
                f"Проверено пачкой {а.date}: название записи каталога"
                f" {итог['_имя_каталога']!r} в тексте есть;"
                f" источников записано {len(итог['_источники'])};"
                " имён вне записи каталога и слага нет;"
                " ворота качества материала без замечаний.",
                "Внешние источники инструментом не открывались.",
            ]
            if итог.get("_подтверждено_внешне"):
                вн = итог["_внешняя"] or {}
                заметки[-1] = (
                    "Имена вне снимка каталога подтверждены ВНЕШНЕЙ сверкой"
                    f" линии wt-portable-site-cell-01: {а.external_verified};"
                    f" источники {', '.join((вн.get('sources') or [])[:3])};"
                    f" подтверждено имён {len(вн.get('confirmed') or [])},"
                    " не найдено ноль. Сверку выполняла не я — работа чужая и"
                    " названа.")
            try:
                editorial.рецензировать(
                    з["домен"], з["slug"], reviewer=а.reviewer,
                    verdict="accepted", body_digest=з.get("body_digest") or "",
                    notes=заметки,
                    checks={к: True for к in editorial.ПРОВЕРКИ_РЕЦЕНЗИИ})
                записано += 1
            except Exception as ош:  # отказ операции — это результат, не сбой
                отказано += 1
                print(f"  отказ по {з['домен']}/{з.get('slug')}: "
                      f"{type(ош).__name__}: {str(ош)[:160]}")
        print()
        print(f"отзывов записано: {записано}; отказов операции: {отказано}")
        if отказано:
            return 1
    return 0 if not негодны else 1


if __name__ == "__main__":
    sys.exit(главное())
