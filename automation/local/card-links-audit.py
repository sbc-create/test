#!/usr/bin/env python3
"""Переходы с карточки: куда с неё можно уйти и живы ли эти адреса.

Что это измеряет. Карточка — конечная точка обхода: на неё приходят из каталога
и из карты сайта. Если с неё никуда нельзя уйти по таксономии (жанр, год,
страна, раздел), обходчик и читатель упираются в тупик, а соседние разделы
получают ссылки только из каталога. Если переход есть, но ведёт на 404 или на
`noindex`, он хуже отсутствия: вес уходит в никуда.

Три вопроса, и каждый мерится отдельно:

* сколько переходов по таксономии несёт карточка (ноль — тупик);
* каждый ли переход отвечает 200 (иначе битый переход);
* индексируется ли цель (иначе переход в закрытую страницу).

**Текст ссылки признаком не считается.** Жанр, выведенный простым текстом,
выглядит ссылкой на картинке и не является ею — это и есть B017. Считаются
только `href`.

Инструмент только читает публичные страницы. Ничего не публикует.

    python3 automation/local/card-links-audit.py lordfilm47.space
    python3 automation/local/card-links-audit.py --all --cards 2
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import unquote, urljoin

sys.path.insert(0, str(Path(__file__).resolve().parent))
import card_facts_block  # noqa: E402  — рядом, не пакет

ПАСПОРТ = Path("/home/claude/wt-portable-site-cell-01/config/site-cells.json")
#: Формы адреса карточки. Две, и это измерено (см. pager-bounds-probe).
ФОРМЫ_КАРТОЧКИ = ("/title/", "/anime/")
#: Переходы по таксономии: путём и параметром. Обе формы в сети встречаются, и
#: проверять только одну значит объявить половину сети тупиковой.
ТАКСОНОМИЯ = (
    ("жанр", (r'href="(/genre/[^"#]+)"', r'href="([^"]*[?&]genre=[^"&]+[^"]*)"')),
    ("год", (r'href="(/year/[^"#]+)"', r'href="([^"]*[?&]year=[^"&]+[^"]*)"')),
    ("страна", (r'href="(/c/[^"#]+)"', r'href="([^"]*[?&]country=[^"&]+[^"]*)"')),
    ("раздел", (r'href="(/(?:movies|series|animation|anime|dorama)/)"',)),
)
#: Сколько целей проверять на карточку. Предел назван, а не «сколько-нибудь»:
#: карточка несёт до десятков ссылок жанров, и обход всех — часы.
ЦЕЛЕЙ_НА_КАРТОЧКУ = 4


def достать(url: str, таймаут: int = 40) -> tuple[str, str, dict[str, str]]:
    with tempfile.NamedTemporaryFile(prefix="cl-head-", suffix=".txt") as ф, \
            tempfile.NamedTemporaryFile(prefix="cl-body-", suffix=".bin") as б:
        г = subprocess.run(
            ["curl", "-sS", "-L", "--max-time", str(таймаут), "-D", ф.name,
             "-o", б.name, "-w", "%{url_effective}", url],
            capture_output=True, text=True)
        голова = Path(ф.name).read_text(encoding="utf-8", errors="replace")
        тело = Path(б.name).read_text(encoding="utf-8", errors="replace")
    блоки = re.split(r"(?m)^(?=HTTP/)", голова)
    последний = блоки[-1] if блоки else голова
    код, заг = "", {}
    for с in последний.splitlines():
        if с.lower().startswith("http/"):
            части = с.split()
            код = части[1] if len(части) > 1 else ""
        elif ":" in с:
            к, _, з = с.partition(":")
            заг[к.strip().lower()] = з.strip()
    заг["итоговый-адрес"] = (г.stdout or "").strip() or url
    if г.returncode != 0 and not код:
        заг["ошибка-curl"] = f"curl={г.returncode}: {(г.stderr or '').strip()[:100]}"
    return код, тело, заг


def закрыта(тело: str, заг: dict[str, str]) -> bool:
    """Страница закрыта от индексации заголовком или meta."""
    если = (заг.get("x-robots-tag") or "").lower()
    if "noindex" in если:
        return True
    м = re.search(r'<meta[^>]+name=["\']robots["\'][^>]*content=["\']([^"\']+)',
                  тело, re.I)
    return bool(м and "noindex" in м.group(1).lower())


def карточки(тело: str) -> list[str]:
    for форма in ФОРМЫ_КАРТОЧКИ:
        найдено = sorted(set(re.findall(
            r'href="(' + re.escape(форма) + r'[^"#?]+)"', тело)))
        if найдено:
            return найдено
    return []


def переходы(тело: str) -> dict[str, list[str]]:
    """Вид перехода → адреса. Текст ссылкой не считается, только href."""
    итог: dict[str, list[str]] = {}
    for вид, шаблоны in ТАКСОНОМИЯ:
        собрано: list[str] = []
        for ш in шаблоны:
            собрано.extend(re.findall(ш, тело))
        # Один и тот же жанр встречается и в характеристиках, и в хлебных
        # крошках: это один переход, а не два.
        итог[вид] = sorted({unquote(а) for а in собрано})
    return итог


def проверить_витрину(домен: str, сколько_карточек: int) -> list[str]:
    замечания: list[str] = []
    корень = f"https://{домен}"
    код, тело, заг = достать(f"{корень}/catalog/", таймаут=30)
    if код != "200":
        причина = заг.get("ошибка-curl") or f"код {код or 'пустой'}"
        print(f"   каталог не отвечает: {причина} — карточки НЕ ИЗМЕРЕНЫ")
        return замечания
    список = карточки(тело)
    if not список:
        print("   в каталоге не распознана ни одна форма адреса карточки — "
              "НЕ ИЗМЕРЕНО")
        замечания.append(f"{домен}: форма адреса карточки не распознана в "
                         "каталоге — мерить переходы нечем")
        return замечания
    print(f"   карточек в каталоге: {len(список)}; беру первые "
          f"{min(сколько_карточек, len(список))}")

    проверено: dict[str, tuple[str, bool]] = {}
    for адрес in список[:сколько_карточек]:
        к, т, з = достать(urljoin(корень, адрес))
        if к != "200":
            причина = з.get("ошибка-curl") or f"код {к or 'пустой'}"
            print(f"   {адрес}: {причина} — переходы НЕ ИЗМЕРЕНЫ")
            continue
        # Считается БЛОК ХАРАКТЕРИСТИК, а не страница: на странице есть
        # сквозное меню жанров, и по странице целиком «карточка ссылается на
        # свой жанр» неотличимо от «на сайте есть меню жанров». Измерено
        # 13.10 — первые два подхода (сравнение двух карточек и вычитание
        # меню) дали неверный ответ, см. card_facts_block.
        вырезка = card_facts_block.блок(т)
        if вырезка is None:
            print(f"   {адрес}: блок характеристик не распознан "
                  f"(известны {', '.join(card_facts_block.КОНТЕЙНЕРЫ)}) — "
                  "переходы НЕ ИЗМЕРЕНЫ")
            замечания.append(
                f"{домен}{адрес}: блок характеристик не распознан — ноль "
                "переходов здесь означал бы не тупик, а слепой признак")
            continue
        разметка, контейнер = вырезка
        п = переходы(разметка)
        всего = sum(len(v) for v in п.values())
        сводка = ", ".join(f"{вид} {len(v)}" for вид, v in п.items())
        print(f"   {адрес}: контейнер {контейнер}, переходов {всего} ({сводка})")
        if всего == 0:
            строка_жанра = "Жанр" in разметка
            замечания.append(
                f"{домен}{адрес}: ни одного перехода по таксономии из блока "
                f"характеристик ({контейнер}); строка «Жанр» в блоке "
                f"{'ЕСТЬ — значит жанр выведен текстом' if строка_жанра else 'ОТСУТСТВУЕТ — значит жанр не выведен вовсе'}"
                " — с карточки нельзя уйти в её раздел")
            continue
        цели = [а for v in п.values() for а in v][:ЦЕЛЕЙ_НА_КАРТОЧКУ]
        for цель in цели:
            полный = urljoin(корень, цель)
            if полный in проверено:
                continue
            кц, тц, зц = достать(полный)
            закр = закрыта(тц, зц)
            проверено[полный] = (кц, закр)
            if кц != "200":
                причина = зц.get("ошибка-curl") or f"код {кц or 'пустой'}"
                замечания.append(
                    f"{домен}{адрес} → {цель}: {причина} — битый переход")
            elif закр:
                замечания.append(
                    f"{домен}{адрес} → {цель}: код 200, но страница закрыта от "
                    "индексации — переход ведёт в закрытую страницу")
    живых = sum(1 for к, з in проверено.values() if к == "200" and not з)
    print(f"   целей проверено {len(проверено)}, из них открытых и живых {живых}")
    return замечания


def домены() -> list[str]:
    if not ПАСПОРТ.is_file():
        return []
    ячейки = json.loads(ПАСПОРТ.read_text(encoding="utf-8")).get("cells") or []
    return [str(я.get("domain")) for я in ячейки
            if я.get("domain")
            and not str(я["domain"]).endswith((".test", ".localhost"))]


def main() -> int:
    р = argparse.ArgumentParser()
    р.add_argument("домены", nargs="*")
    р.add_argument("--all", action="store_true")
    р.add_argument("--cards", type=int, default=2,
                   help="сколько карточек проверять на витрине")
    а = р.parse_args()

    цели = а.домены or (домены() if а.all else [])
    if not цели:
        print("не названо ни одной витрины: домен аргументом или --all")
        return 2

    все: list[str] = []
    for домен in цели:
        print(f"\n=== {домен}")
        все.extend(проверить_витрину(домен, max(1, а.cards)))

    print(f"\n{'=' * 60}\nзамечаний: {len(все)}")
    for з in все:
        print(f"  • {з}")
    return 1 if все else 0


if __name__ == "__main__":
    sys.exit(main())
