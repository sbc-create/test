#!/usr/bin/env python3
"""Разметка данных против видимого: объявляет ли карточка то, чего на ней нет.

Зачем. `schema.org` описывает СОДЕРЖИМОЕ СТРАНИЦЫ. Поле, объявленное в
`ld+json` и отсутствующее в разметке, — это заявление о том, чего посетитель не
видит: по правилам поисковых систем такая разметка не поддерживается
содержимым, а для читателя факт просто потерян.

Измерено 13.10: у Zona и Animedia карточка объявляет `genre` в `ld+json`, а на
странице жанра нет ни строкой, ни ссылкой (см. `card-links-audit.py`). То есть
данные есть, разметка их несёт, а страница — нет.

Что проверяется на карточке:

* поля `ld+json`, которым в видимой части не нашлось подтверждения;
* `BreadcrumbList` — есть ли он вообще (крошки это и навигация, и расширенный
  результат);
* число серий: `numberOfEpisodes` против числа в видимой строке.

Инструмент только читает публичные страницы.

    python3 automation/local/schema-vs-visible.py lordfilm47.space
    python3 automation/local/schema-vs-visible.py --all
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import card_facts_block  # noqa: E402  — рядом, не пакет

ПАСПОРТ = Path("/home/claude/wt-portable-site-cell-01/config/site-cells.json")
ФОРМЫ_КАРТОЧКИ = ("/title/", "/anime/")
#: Типы узлов, описывающих само произведение. Остальные (`WebSite`,
#: `BreadcrumbList`) описывают сайт и навигацию, и к видимому тексту карточки
#: их сверять не надо.
ТИПЫ_ПРОИЗВЕДЕНИЯ = ("Movie", "TVSeries", "TVSeason", "TVEpisode", "VideoObject")


def достать(url: str, таймаут: int = 40) -> tuple[str, str]:
    with tempfile.NamedTemporaryFile(prefix="sv-body-", suffix=".bin") as б:
        г = subprocess.run(
            ["curl", "-sS", "-L", "--max-time", str(таймаут), "-o", б.name,
             "-w", "%{http_code}", url],
            capture_output=True, text=True)
        тело = Path(б.name).read_text(encoding="utf-8", errors="replace")
    return (г.stdout or "").strip(), тело


def карточки(тело: str) -> list[str]:
    for форма in ФОРМЫ_КАРТОЧКИ:
        найдено = sorted(set(re.findall(
            r'href="(' + re.escape(форма) + r'[^"#?]+)"', тело)))
        if найдено:
            return найдено
    return []


def узлы(тело: str) -> tuple[list[dict], list[str]]:
    """Узлы ld+json и список блоков, которые не разобрались."""
    собрано: list[dict] = []
    битые: list[str] = []
    for бл in re.findall(
            r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>',
            тело, re.S):
        try:
            д = json.loads(бл)
        except ValueError as exc:
            битые.append(str(exc)[:80])
            continue
        собрано.extend(у for у in (д if isinstance(д, list) else [д])
                       if isinstance(у, dict))
    return собрано, битые


def видимый_текст(тело: str) -> str:
    """Текст страницы без скриптов, стилей и служебных мета-тегов.

    Мета-теги вырезаются намеренно: `description` несёт жанры и у Zona, где на
    странице их нет. Если считать мета видимым, несоответствие исчезнет — а
    посетитель всё равно жанра не увидит.
    """
    без_скриптов = re.sub(r"<script.*?</script>", " ", тело, flags=re.S)
    без_стилей = re.sub(r"<style.*?</style>", " ", без_скриптов, flags=re.S)
    без_головы = re.sub(r"<head.*?</head>", " ", без_стилей, flags=re.S)
    текст = re.sub(r"<[^>]+>", " ", без_головы)
    return re.sub(r"\s+", " ", текст).lower()


def значения(поле) -> list[str]:
    """Значения поля ld+json строками: поле бывает строкой, списком и узлом."""
    если = поле if isinstance(поле, list) else [поле]
    итог: list[str] = []
    for з in если:
        if isinstance(з, str):
            итог.append(з)
        elif isinstance(з, dict):
            имя = з.get("name")
            if isinstance(имя, str):
                итог.append(имя)
    return [з.strip() for з in итог if з and з.strip()]


def проверить(домен: str, сколько: int) -> list[str]:
    замечания: list[str] = []
    корень = f"https://{домен}"
    код, тк = достать(f"{корень}/catalog/", таймаут=30)
    if код != "200":
        print(f"   каталог отвечает {код or 'пусто'} — карточки НЕ ИЗМЕРЕНЫ")
        return замечания
    список = карточки(тк)
    if not список:
        print("   форма адреса карточки не распознана — НЕ ИЗМЕРЕНО")
        замечания.append(f"{домен}: форма адреса карточки не распознана")
        return замечания

    for адрес in список[:сколько]:
        к, т = достать(f"{корень}{адрес}")
        if к != "200":
            print(f"   {адрес}: код {к or 'пусто'} — НЕ ИЗМЕРЕНО")
            continue
        собрано, битые = узлы(т)
        for причина in битые:
            замечания.append(f"{домен}{адрес}: блок ld+json не разобран ({причина})")
        типы = [str(у.get("@type")) for у in собрано]
        видимо = видимый_текст(т)
        print(f"   {адрес}: узлов {len(собрано)} {типы}")

        if not any("BreadcrumbList" == т2 for т2 in типы):
            замечания.append(
                f"{домен}{адрес}: BreadcrumbList в ld+json отсутствует — "
                "крошки не объявлены ни навигацией, ни расширенным результатом")

        for у in собрано:
            if str(у.get("@type")) not in ТИПЫ_ПРОИЗВЕДЕНИЯ:
                continue
            for поле in ("genre", "countryOfOrigin"):
                зн = значения(у.get(поле))
                если_нет = [з for з in зн if з.lower() not in видимо]
                if зн and len(если_нет) == len(зн):
                    замечания.append(
                        f"{домен}{адрес}: ld+json объявляет {поле}="
                        f"{зн} — ни одного из этих значений в видимой части "
                        "страницы нет")
            серии = у.get("numberOfEpisodes")
            if серии is not None:
                видно = re.findall(r"(\d+)\s*сер", видимо)
                if видно and str(серии) not in видно:
                    замечания.append(
                        f"{домен}{адрес}: numberOfEpisodes={серии}, а в видимой "
                        f"строке серий {видно[:3]} — числа не совпадают")
    return замечания


def домены() -> list[str]:
    if not ПАСПОРТ.is_file():
        return []
    ячейки = json.loads(ПАСПОРТ.read_text(encoding="utf-8")).get("cells") or []
    return [str(я["domain"]) for я in ячейки
            if я.get("domain")
            and not str(я["domain"]).endswith((".test", ".localhost"))]


def main() -> int:
    р = argparse.ArgumentParser()
    р.add_argument("домены", nargs="*")
    р.add_argument("--all", action="store_true")
    р.add_argument("--cards", type=int, default=2)
    а = р.parse_args()
    цели = а.домены or (домены() if а.all else [])
    if not цели:
        print("не названо ни одной витрины: домен аргументом или --all")
        return 2
    все: list[str] = []
    for домен in цели:
        print(f"\n=== {домен}")
        все.extend(проверить(домен, max(1, а.cards)))
    print(f"\n{'=' * 60}\nзамечаний: {len(все)}")
    for з in все:
        print(f"  • {з}")
    return 1 if все else 0


if __name__ == "__main__":
    sys.exit(main())
