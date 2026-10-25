#!/usr/bin/env python3
"""Сверка имён из текста с ЗАПИСАННЫМИ источниками черновика.

Зачем. Рецензия (MOD-173) требует «посторонних вставок нет», а автоматическая
проверка в `review-materials-batch.py` этого сама подтвердить не может: она
видит только запись каталога и слаг, внешних источников не открывает и прямо
об этом говорит. Поэтому каждый материал с именами персонажей, актёров или мест
уходил в «нужна сверка по внешнему источнику» и ждал ручной работы.

Что делает этот инструмент. Берёт источники ИЗ САМОГО черновика (поле
`sources`), читает их штатным путём (`source_fetch.py`: robots, своё имя,
не чаще 4 запросов в секунду) и ищет каждое отмеченное имя в ответе.

Три свойства, без которых сверка была бы видимостью работы:

* **падежи.** Сравнение идёт по ОСНОВЕ слова: источник пишет «Кошачьего
  Франциско», текст — «Кошачий Франциско»; «Тёмной триады» против «Тёмная».
  Побуквенное совпадение дало бы «не найдено» там, где источник прямо это
  называет (проверено 25.10 на четырёх материалах: три «не найдено» из четырёх
  оказались падежами);
* **письменность.** Для англоязычного источника русское имя подтверждается
  латинским написанием, и соответствие печатается явно: «Алисса (как Alyssa)».
  Соответствие задаётся парами в `--latin`, а не угадывается;
* **фрагмент.** Для каждого подтверждённого имени печатается кусок источника,
  в котором оно найдено. Подтверждение без фрагмента неотличимо от
  подтверждения по совпадению букв в другом слове.

Выход в формате `--external-verified` для `review-materials-batch.py`.

    python3 automation/local/names-against-sources.py --slug holodnaya-reka \
        --latin Алисса=Alyssa --latin Кэмпбелл=Campbell \
        --json artifacts/evidence/names-20261025.json
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import pathlib
import re
import subprocess
import sys

ХРАНИЛИЩА = "/srv/sites/*/runtime/overlays/*/drafts.json"
ИНСТРУМЕНТ = pathlib.Path(__file__).resolve().parent / "source_fetch.py"
#: Окончания, отбрасываемые при сравнении основ. Список закрытый и назван:
#: «умное» морфологическое приведение без словаря даёт ложные совпадения.
ОКОНЧАНИЯ = ("ого", "его", "ому", "ему", "ыми", "ими", "ей", "ой", "ом", "ем",
             "ах", "ях", "ам", "ям", "ов", "ев", "ую", "юю", "ая", "яя", "ые",
             "ие", "ью", "ия", "ии", "а", "я", "ы", "и", "у", "ю", "е", "о",
             "ь", "й")
#: Остаток основы после отбрасывания окончания и минимальная длина имени,
#: которому сравнение по основе вообще разрешено. Два предела, а не один:
#: «Асты» (4 знака) обязано совпасть с «Аста», а «Ас» (2 знака) — нет, иначе
#: основа совпадёт почти с чем угодно («астрономия»).
МИН_ОСНОВА = 3
МИН_ИМЯ = 4


def основа(слово: str) -> str:
    """Основа для сравнения: без окончания, без мягкого знака и конечного «и».

    Последний шаг нужен из-за пары «Кошачьего» → `кошачь` и «Кошачий» →
    `кошачи`: без него один и тот же корень давал две разные основы, и
    источник, прямо называющий имя, считался его не называющим.
    """
    #: «ё»→«е» и «э»→«е»: источник пишет «Бредфорде», черновик «Брэдфорда» —
    #: это разночтение транслитерации, а не другое имя.
    с = (слово or "").strip().lower().replace("ё", "е").replace("э", "е")
    for о in ОКОНЧАНИЯ:
        if len(с) - len(о) >= МИН_ОСНОВА and с.endswith(о):
            с = с[: len(с) - len(о)]
            break
    пока = с.rstrip("ьи")
    return пока if len(пока) >= МИН_ОСНОВА else с


def слова(текст: str) -> list[str]:
    return re.findall(r"[А-Яа-яЁёA-Za-z][А-Яа-яЁёA-Za-z\-']+", текст or "")


def найти_имя(имя: str, текст: str) -> tuple[bool, str]:
    """Подтверждено ли имя и каким фрагментом источника.

    Сначала прямое вхождение, затем совпадение основ. Фрагмент возвращается
    всегда, когда подтверждение есть: без него нечего предъявить.
    """
    if not имя or not текст:
        return False, ""
    #: Прямое совпадение требует ГРАНИЦЫ слова: иначе «Ас» нашлось бы внутри
    #: «астрономия», и подтверждение означало бы совпадение букв.
    м = re.search(r"\b" + re.escape(имя) + r"\b", текст, re.IGNORECASE)
    if not м and ("э" in имя.lower() or "ё" in имя.lower()):
        мягче = имя.lower().replace("ё", "е").replace("э", "е")
        for с in слова(текст):
            if с.lower().replace("ё", "е").replace("э", "е") == мягче:
                м = re.search(r"\b" + re.escape(с) + r"\b", текст)
                break
    if м:
        а, б = max(0, м.start() - 60), min(len(текст), м.end() + 60)
        return True, текст[а:б].replace("\n", " ")
    if len(имя.strip()) < МИН_ИМЯ:
        return False, ""
    цель = основа(имя)
    if len(цель) < МИН_ОСНОВА:
        return False, ""
    for с in слова(текст):
        if основа(с) == цель:
            место = текст.find(с)
            а, б = max(0, место - 60), min(len(текст), место + len(с) + 60)
            return True, текст[а:б].replace("\n", " ")
    return False, ""


def черновик(слаг: str, домен: str = "") -> tuple[str, dict] | tuple[None, None]:
    for путь in sorted(glob.glob(ХРАНИЛИЩА)):
        д = pathlib.Path(путь).parent.name
        if домен and д != домен:
            continue
        данные = json.loads(pathlib.Path(путь).read_text(encoding="utf-8"))
        ч = (данные.get("items") or {}).get(слаг)
        if ч:
            return д, ч
    return None, None


_СНИМКИ: dict[str, dict] = {}


def запись_снимка(путь: pathlib.Path, слаг: str) -> tuple[str, str]:
    """Запись ОДНОГО произведения из снимка каталога, а не весь снимок.

    Измерено 25.10, и это чуть не стоило четырёх ложных подтверждений: снимок
    витрины — это 69 870 записей в одном файле, поэтому поиск имени по всему
    файлу подтверждал «Алиссу» описанием ДРУГОГО фильма, а «Кошачий» — фразой
    «кошачий слух» из третьего. Подтверждать имя чужой записью нельзя: сверка
    тогда проверяет лишь то, что имя встречается в русском языке.
    """
    #: Ключ кэша — строка: по `Path` он не совпадал с тем, чем кладётся, и
    #: снимок на 95 МБ разбирался заново для каждого материала.
    if str(путь) not in _СНИМКИ:
        try:
            _СНИМКИ[str(путь)] = json.loads(путь.read_text(encoding="utf-8"))
        except (OSError, ValueError) as ош:
            return "", f"снимок не прочитан: {type(ош).__name__}"
    д = _СНИМКИ.get(str(путь)) or {}
    записи = д.get("details") or д.get("items") or д
    з = записи.get(слаг) if isinstance(записи, dict) else None
    if з is None:
        return "", (f"в снимке нет записи {слаг!r}: подтверждать имя чужими"
                    " записями нельзя")
    return json.dumps(з, ensure_ascii=False), ""


def прочитать_источник(адрес: str, слаг: str = "",
                       таймаут: int = 180) -> tuple[str, str]:
    """Текст источника и причина отказа. Читается ТОЛЬКО штатным путём."""
    if адрес.startswith("snapshot:") or адрес.startswith("/"):
        п = pathlib.Path(адрес.replace("snapshot:", "", 1))
        if not п.is_file():
            return "", f"снимка нет: {п}"
        return запись_снимка(п, слаг)
    м = re.search(r"shikimori\.(?:io|one)/animes/(\d+)", адрес)
    команда = ([sys.executable, str(ИНСТРУМЕНТ), "shikimori", м.group(1)] if м
               else [sys.executable, str(ИНСТРУМЕНТ), "page", адрес])
    г = subprocess.run(команда, capture_output=True, text=True, timeout=таймаут)
    if г.returncode != 0:
        return "", f"источник не прочитан: {(г.stderr or '').strip()[-160:]}"
    try:
        д = json.loads(г.stdout)
    except ValueError:
        return "", "ответ источника не JSON"
    if not д.get("ok", True):
        return "", f"источник отказал: {str(д.get('error'))[:120]}"
    return json.dumps(д, ensure_ascii=False), ""


def главное(аргв=None) -> int:
    р = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--slug", action="append", required=True)
    р.add_argument("--domain", default="")
    р.add_argument("--name", action="append", default=[],
                   help="имя для сверки; по умолчанию берутся отмеченные "
                        "проверкой материала")
    р.add_argument("--latin", action="append", default=[],
                   help="соответствие письменностей: Алисса=Alyssa")
    р.add_argument("--json", type=pathlib.Path)
    а = р.parse_args(аргв)
    латиница = dict(п.split("=", 1) for п in а.latin if "=" in п)

    #: Отмеченные имена берутся у той же проверки, что требует их сверки, —
    #: иначе сверяется один список, а принимает решение другой.
    import importlib.util
    спец = importlib.util.spec_from_file_location(
        "rmb", pathlib.Path(__file__).resolve().parent / "review-materials-batch.py")
    ПАЧКА = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(ПАЧКА)

    итог = {"method": ("source_fetch.py по источникам, записанным в черновике;"
                       " сравнение по основе слова; для англоязычного источника"
                       " соответствие письменностей задано парами --latin"),
            "at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "results": []}
    код = 0
    for слаг in а.slug:
        домен, ч = черновик(слаг, а.domain)
        if not ч:
            print(f"{слаг}: черновика нет")
            код = 2
            continue
        записи = ПАЧКА.опора({слаг})
        проверка = ПАЧКА.проверить({**ч, "домен": домен, "slug": слаг},
                                   записи.get(слаг) or {})
        имена = а.name or проверка.get("_посторонние") or []
        источники = [и for и in (ч.get("sources") or []) if str(и).strip()]
        print(f"=== {домен} / {слаг}")
        print(f"    источников {len(источники)}, имён к сверке {len(имена)}")
        if not источники:
            print("    НЕ ИЗМЕРЕНО: у черновика не записано ни одного источника")
            итог["results"].append({"domain": домен, "slug": слаг,
                                    "confirmed": [], "not_found": list(имена),
                                    "note": "источников не записано"})
            код = код or 1
            continue
        тексты, отказы = [], []
        for и in источники:
            т, причина = прочитать_источник(и, слаг)
            (тексты if т else отказы).append((и, т or причина))
        if отказы:
            for и, п_ in отказы:
                print(f"    источник не дал текста: {и} — {п_}")
        подтв, нет, фрагменты, чем = [], [], {}, {}
        for имя in имена:
            есть, фр, источник = False, "", ""
            for адрес, текст in тексты:
                есть, фр = найти_имя(имя, текст)
                if есть:
                    источник = адрес
                    break
                if латиница.get(имя):
                    есть, фр = найти_имя(латиница[имя], текст)
                    if есть:
                        источник = адрес
                        break
            как = имя
            if есть and фр and латиница.get(имя) and имя.lower() not in фр.lower():
                как = f"{имя} (как «{латиница[имя]}»)"
            if есть:
                подтв.append(как)
                фрагменты[как] = фр[:180]
                чем[как] = источник
            else:
                нет.append(имя)
        for к in подтв:
            print(f"    подтверждено: {к}")
            print(f"        источник: {чем[к]}")
            print(f"        …{фрагменты[к]}…")
        for к in нет:
            print(f"    НЕ НАЙДЕНО: {к}")
        итог["results"].append({
            "domain": домен, "slug": слаг, "sources": источники,
            "unreadable_sources": [{"url": и, "reason": п_} for и, п_ in отказы],
            "confirmed": подтв, "not_found": нет, "fragments": фрагменты,
            "confirmed_by": чем})
        if нет:
            код = код or 1
    if а.json:
        а.json.parent.mkdir(parents=True, exist_ok=True)
        а.json.write_text(json.dumps(итог, ensure_ascii=False, indent=1),
                          encoding="utf-8")
        print(f"\nсверка записана: {а.json}")
    всего = sum(len(з["confirmed"]) + len(з["not_found"]) for з in итог["results"])
    подтверждено = sum(len(з["confirmed"]) for з in итог["results"])
    print(f"\nимён сверено {всего}; подтверждено источником {подтверждено};"
          f" не найдено {всего - подтверждено}")
    return код


if __name__ == "__main__":
    sys.exit(главное())
