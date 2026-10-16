#!/usr/bin/env python3
"""Где посетитель упирается в ошибку или не может пользоваться сайтом.

Четвёртый вопрос из порядка владельца: страницы доступны обходу (проверено),
спрос и запросы — за SEO, показы и позиции не измеряются (B023), а вот
работоспособность страницы измерить можно прямо сейчас, и это моя часть.

По каждому домену берётся выборка страниц произведений ИЗ КАРТЫ САЙТА (а не
придуманные адреса) плюс главная и каталог. На каждой считается:

  код, время      отвечает ли и за сколько (полное время до последнего байта)
  плеер           есть ли узел плеера и номер издателя в разметке
  серии           сколько ссылок на серии нашлось на странице сериала
  ошибки          видимые посетителю формулировки отказа
  вес             размер страницы

Инструмент только читает публичные страницы. Ничего не меняет и ничего не
чинит; его дело — назвать адреса, на которых посетителю нечего смотреть.

    python3 automation/local/usability-sweep.py
    python3 automation/local/usability-sweep.py --domain zonafilm.cc --sample 10
"""
from __future__ import annotations

import argparse
import json
import random
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
РЕЕСТР = КОРЕНЬ / "config" / "site-cells.json"

СЕМЬИ = ("lord", "zona")

ОШИБКИ = (
    "Провайдер не отдал источник",
    "не отдал источник",
    "Источник недоступен",
    "Произошла ошибка",
    "Что-то пошло не так",
    "Ничего не найдено",
    "временно недоступ",
)


def тело(url: str, таймаут: int = 30) -> tuple[int, float, str]:
    г = subprocess.run(
        ["curl", "-sL", "-w", "\n%{http_code} %{time_total}", "--max-time", str(таймаут), url],
        capture_output=True, text=True, timeout=таймаут + 20)
    весь = г.stdout or ""
    тело_, _, хвост = весь.rpartition("\n")
    части = хвост.split()
    код = int(части[0]) if части and части[0].isdigit() else 0
    время = float(части[1]) if len(части) > 1 else 0.0
    return код, время, тело_


def адреса_тайтлов(домен: str, сколько: int) -> list[str]:
    _, _, индекс = тело(f"https://{домен}/sitemap.xml", 40)
    части = re.findall(r"<loc>([^<]+)</loc>", индекс)
    кандидаты: list[str] = []
    for адрес in части[:3]:
        _, _, часть = тело(адрес, 60)
        кандидаты += [у for у in re.findall(r"<loc>([^<]+)</loc>", часть)
                      if "/title/" in у]
        if len(кандидаты) > 500:
            break
    if not кандидаты:
        кандидаты = [у for у in части if "/title/" in у]
    random.shuffle(кандидаты)
    return кандидаты[:сколько]


def видимое(t: str) -> str:
    """Текст, который видит посетитель.

    Первая версия этой проверки искала формулировку отказа по всему исходнику
    и нашла её на каждой странице Zona. Измерено: «Видео временно недоступно»
    лежит там в СКРЫТОМ блоке (`data-player-state hidden`) и в строках
    `LABELS` внутри скрипта плеера, то есть посетителю не показано. Мера
    проверяла наличие строки, а не состояние страницы; здесь это исправлено:
    скрипты, стили и элементы с `hidden` вырезаются до поиска.
    """
    без_скриптов = re.sub(r"(?is)<script\b.*?</script>", " ", t)
    без_стилей = re.sub(r"(?is)<style\b.*?</style>", " ", без_скриптов)
    без_шаблонов = re.sub(r"(?is)<template\b.*?</template>", " ", без_стилей)
    # Элементы с атрибутом hidden — вместе с содержимым, по одному уровню.
    без_скрытых = re.sub(r"(?is)<(\w+)[^>]*\bhidden\b[^>]*>.*?</\1>", " ",
                         без_шаблонов)
    return без_скрытых


def страница(url: str) -> dict:
    код, время, t = тело(url)
    серии = len(set(re.findall(r'href="([^"]*/(?:episode|seriya|series)[^"]*)"', t)))
    if not серии:
        серии = len(set(re.findall(r'data-episode(?:-number)?="[^"]+"', t)))
    текст = видимое(t)
    видимые = [ф for ф in ОШИБКИ if ф.lower() in текст.lower()]
    return {
        "url": url,
        "код": код,
        "время": время,
        "вес": len(t),
        "плеер": ("data-publisher-id" in t) or ("player" in t and "mount" in t),
        "издатель": bool(re.search(r'data-publisher-id="(\d+)"', t)),
        "серий": серии,
        "ошибки": видимые,
    }


def раздел_каталога(домен: str) -> str:
    """Адрес каталога берётся из навигации витрины, а не угадывается.

    Первая версия спрашивала `/serialy/` у всех семи доменов и получила семь
    404 — это была ошибка меры, а не витрин: разделы у семейства называются
    `/series/` и `/movies/`.
    """
    _, _, t = тело(f"https://{домен}/", 30)
    for образец in (r'href="(/series/)"', r'href="(/movies/)"',
                    r'href="(/catalog/?)"'):
        м = re.search(образец, t)
        if м:
            return f"https://{домен}{м.group(1)}"
    return f"https://{домен}/"


def по_домену(домен: str, сколько: int) -> dict:
    страницы = [f"https://{домен}/", раздел_каталога(домен)]
    страницы += адреса_тайтлов(домен, сколько)
    with ThreadPoolExecutor(3) as ex:
        итоги = list(ex.map(страница, страницы))
    тайтлы = [и for и in итоги if "/title/" in и["url"]]
    плохие = [и for и in итоги if и["код"] != 200 or и["ошибки"]]
    без_плеера = [и for и in тайтлы if not и["плеер"]]
    без_серий = [и for и in тайтлы if и["серий"] == 0]
    медленные = [и for и in итоги if и["время"] > 3.0]
    return {
        "домен": домен,
        "страниц": len(итоги),
        "тайтлов": len(тайтлы),
        "не_200_или_ошибка": плохие,
        "без_плеера": без_плеера,
        "без_серий": без_серий,
        "медленные": медленные,
        "среднее_время": (sum(и["время"] for и in итоги) / len(итоги)) if итоги else 0.0,
    }


def главное(аргв=None) -> int:
    р = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--domain", action="append", default=[])
    р.add_argument("--sample", type=int, default=6)
    р.add_argument("--seed", type=int, default=20261016)
    опции = р.parse_args(аргв)
    random.seed(опции.seed)

    домены = опции.domain
    if not домены:
        д = json.loads(РЕЕСТР.read_text(encoding="utf-8"))
        домены = sorted({я["domain"] for я in д["cells"]
                         if я.get("status") == "live"
                         and not (я.get("promotion") or {}).get("excluded")
                         and any(я["domain"].startswith(с) or с in я["domain"]
                                 for с in СЕМЬИ)})
    print(f"доменов: {len(домены)}; выборка страниц произведений: {опции.sample}\n")

    итоги = [по_домену(д, опции.sample) for д in домены]
    print(f"{'домен':22s} {'стр':>4s} {'не 200/ошибка':>13s} {'без плеера':>11s} "
          f"{'без серий':>10s} {'медленнее 3с':>13s} {'сред. время':>11s}")
    находки: list[str] = []
    for и in итоги:
        print(f"{и['домен']:22s} {и['страниц']:4d} {len(и['не_200_или_ошибка']):13d} "
              f"{len(и['без_плеера']):11d} {len(и['без_серий']):10d} "
              f"{len(и['медленные']):13d} {и['среднее_время']:10.2f}с")
        for п in и["не_200_или_ошибка"]:
            находки.append(f"{и['домен']}: код {п['код']} {п['ошибки']} — {п['url']}")
        for п in и["без_плеера"]:
            находки.append(f"{и['домен']}: нет узла плеера — {п['url']}")
        for п in и["медленные"]:
            находки.append(f"{и['домен']}: {п['время']:.1f}с — {п['url']}")

    print(f"\nнаходок: {len(находки)}")
    for н in находки[:40]:
        print(f"   {н}")
    print("\n«без серий» у фильма — не ошибка; смотреть вместе с типом страницы")
    return 1 if находки else 0


if __name__ == "__main__":
    raise SystemExit(главное())
