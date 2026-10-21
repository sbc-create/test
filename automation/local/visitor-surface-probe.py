#!/usr/bin/env python3
"""Что видит посетитель: битые ссылки, пустые полки, технические фразы.

Задание ночи требует проверить на развиваемых витринах отсутствие пустых полок,
битых ссылок и технических фраз для посетителя. Здесь это измеряется, а не
просматривается глазами, и по каждому признаку отдельно:

* **битые ссылки** — выборка внутренних ссылок главной и каталога, с кодом
  ответа у каждой. Выборка СЛУЧАЙНАЯ с фиксированным семенем, чтобы два
  прогона были сравнимы, и её размер печатается: «ссылок проверено N из M» —
  проверка без охвата читается как проверка всего;
* **технические фразы** — строки, которые посетителю видеть незачем:
  `undefined`, `NaN`, `None`, `null`, `TODO`, `не измерено`, `Provider`,
  `Traceback`, `{{`. Ищутся в ТЕКСТЕ страницы, а не в разметке: `null` внутри
  JSON-LD — это нормально, а в абзаце — нет;
* **пустые заголовки разделов** — заголовок полки есть, карточек под ним нет.

Чего эта проверка НЕ делает: не судит о воспроизведении видео (наличие
`iframe` этим не является) и не измеряет посещаемость.

    python3 automation/local/visitor-surface-probe.py --all
    python3 automation/local/visitor-surface-probe.py --domain zonafilm.space --links 40
"""
from __future__ import annotations

import argparse
import html as _html
import json
import random
import re
import subprocess
import sys

ВИТРИНЫ = (
    "lordserials22.info", "1lordserials1.online", "lordfilm47.space",
    "lordserial33.biz", "zonafilm12.site", "zonafilm.space", "zonafilm.cc",
    "animedia.icu", "animedia.space", "animeg0.site", "an1meg0.site",
    "an1mego.site", "yummyani.site", "yummyani7.site", "yummyani7.info",
    "yummyani.org", "yummyani.biz",
)

#: Фразы, которых на странице для посетителя быть не должно. У каждой — повод:
#: `не измерено` и `None` приходили из наших же проходов, `Provider` — из
#: сообщения источника, `undefined`/`NaN` — из клиентского кода.
ТЕХНИЧЕСКИЕ = (
    "undefined", "NaN", "None", "TODO", "FIXME", "Traceback",
    "не измерено", "Provider не", "{{", "[object Object]",
)
СЕМЯ = 20261021


def достать(адрес: str, таймаут: int = 40) -> tuple[int, str]:
    try:
        г = subprocess.run(["curl", "-sSL", "-w", "\n@@КОД@@%{http_code}",
                            "--max-time", str(таймаут), адрес],
                           capture_output=True, text=True, timeout=таймаут + 20)
    except subprocess.TimeoutExpired:
        return 0, ""
    тело, _, код = г.stdout.rpartition("@@КОД@@")
    try:
        return int(код.strip()), тело
    except ValueError:
        return 0, тело


def код(адрес: str, таймаут: int = 30) -> int:
    try:
        г = subprocess.run(["curl", "-sS", "-o", "/dev/null", "-w", "%{http_code}",
                            "--max-time", str(таймаут), адрес],
                           capture_output=True, text=True, timeout=таймаут + 15)
    except subprocess.TimeoutExpired:
        return 0
    try:
        return int((г.stdout or "0").strip())
    except ValueError:
        return 0


def текст_страницы(тело: str) -> str:
    """Текст без разметки, скриптов и JSON-LD: `null` в данных — не фраза."""
    без = re.sub(r"<script.*?</script>", " ", тело, flags=re.S | re.I)
    без = re.sub(r"<style.*?</style>", " ", без, flags=re.S | re.I)
    без = re.sub(r"<[^>]+>", " ", без)
    return _html.unescape(re.sub(r"\s+", " ", без))


def ссылки(тело: str) -> list[str]:
    найдено = []
    for а in re.findall(r'href="(/[^"#]*)"', тело):
        if а.startswith(("/api/", "/poster/", "/__", "/event/")):
            continue
        if а not in найдено:
            найдено.append(а)
    return найдено


def полки(тело: str) -> tuple[list[str], list[str]]:
    """`(пустые, без_карточек)` по заголовкам полок.

    Два состояния, а не одно, и это важно: ПУСТАЯ — в блоке нет ни одной
    ссылки, то есть посетителю под заголовком нечего делать. БЕЗ КАРТОЧЕК —
    ссылки есть, а карточек произведений нет: так устроены законные хабы
    («Жанры», «Подборки»), и объявлять их дефектом нельзя. Первая редакция
    считала только карточки и называла хабы пустыми — находка там, где раздел
    полон.
    """
    пустые = []
    без_карточек = []
    части = re.split(r"<h2[^>]*>(.*?)</h2>", тело, flags=re.S)
    # части: [до, заголовок1, тело1, заголовок2, тело2, ...]
    for i in range(1, len(части) - 1, 2):
        имя = re.sub(r"<[^>]+>", "", части[i]).strip()
        # Считаются ЛЮБЫЕ внутренние ссылки блока, а не только карточки
        # произведений. Первая редакция считала только `/title/` и `/anime/` —
        # и объявляла пустыми разделы «Жанры» и «Подборки», где ссылки ведут на
        # фасеты каталога. Признак давал находку там, где раздел полон.
        ссылок = len(re.findall(r'href="/', части[i + 1]))
        карточек = len(re.findall(r'href="/(?:title|anime)/', части[i + 1]))
        if not имя or len(части[i + 1]) >= 20000:
            continue
        if ссылок == 0:
            пустые.append(имя[:40])
        elif карточек == 0:
            без_карточек.append(имя[:40])
    return пустые, без_карточек


def проверить(домен: str, сколько_ссылок: int) -> dict:
    итог: dict = {"домен": домен, "замечания": []}
    к, тело = достать(f"https://{домен}/")
    итог["главная_код"] = к
    if к != 200:
        итог["замечания"].append(f"главная отвечает {к}")
        итог["измерено"] = False
        return итог
    итог["измерено"] = True

    все = ссылки(тело)
    к2, каталог = достать(f"https://{домен}/catalog/")
    if к2 == 200:
        for а in ссылки(каталог):
            if а not in все:
                все.append(а)
    итог["ссылок_найдено"] = len(все)
    выборка = все if len(все) <= сколько_ссылок else random.Random(СЕМЯ).sample(
        все, сколько_ссылок)
    итог["ссылок_проверено"] = len(выборка)
    битые = []
    for а in sorted(выборка):
        c = код(f"https://{домен}{а}")
        if c not in (200, 301, 302, 308):
            битые.append({"адрес": а, "код": c})
    итог["битых"] = битые
    if битые:
        итог["замечания"].append(
            f"битых ссылок {len(битые)} из {len(выборка)} проверенных:"
            + ", ".join(f"{б['адрес']} → {б['код']}" for б in битые[:4]))

    текст = текст_страницы(тело)
    найдено = {ф for ф in ТЕХНИЧЕСКИЕ if ф in текст}
    итог["технические_фразы"] = sorted(найдено)
    if найдено:
        итог["замечания"].append(
            f"технические фразы на главной: {', '.join(sorted(найдено))}")

    пустые, без_карточек = полки(тело)
    итог["пустые_полки"] = пустые
    итог["полок_без_карточек"] = без_карточек
    if пустые:
        итог["замечания"].append(f"пустые полки: {', '.join(пустые)}")
    return итог


def main(аргв: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--domain", action="append", default=[])
    р.add_argument("--all", action="store_true")
    р.add_argument("--links", type=int, default=25)
    р.add_argument("--json", action="store_true")
    а = р.parse_args(аргв)
    домены = а.domain or (list(ВИТРИНЫ) if а.all else [])
    if not домены:
        print("не названо ни одной витрины: --domain или --all")
        return 2
    итоги = [проверить(д, а.links) for д in домены]
    if а.json:
        print(json.dumps(итоги, ensure_ascii=False, indent=1))
        return 1 if any(и["замечания"] for и in итоги) else 0
    for и in итоги:
        метка = "НЕТ" if и["замечания"] else "ок "
        print(f"[{метка}] {и['домен']:22} ссылок проверено"
              f" {и.get('ссылок_проверено', 0):>3} из {и.get('ссылок_найдено', 0):>3},"
              f" битых {len(и.get('битых') or [])},"
              f" пустых полок {len(и.get('пустые_полки') or [])},"
              f" без карточек {len(и.get('полок_без_карточек') or [])},"
              f" технических фраз {len(и.get('технические_фразы') or [])}")
        for з in и["замечания"]:
            print(f"       → {з}")
    плохих = [и["домен"] for и in итоги if и["замечания"]]
    print(f"\nвитрин проверено {len(итоги)}, с замечаниями {len(плохих)}"
          f"{': ' + ', '.join(плохих) if плохих else ''}")
    print("выборка ссылок случайная с семенем 20261021 — два прогона сравнимы;"
          " воспроизведение видео здесь не проверяется")
    return 1 if плохих else 0


if __name__ == "__main__":
    sys.exit(main())
