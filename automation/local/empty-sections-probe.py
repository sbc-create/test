#!/usr/bin/env python3
"""Индексируемый раздел без единой записи: страница есть, содержимого нет.

Что это измеряет. Раздел, который отвечает 200, индексируется и не содержит ни
одной карточки, — не страница: обходчик тратит на неё бюджет, а читатель
получает пустоту. Класс уже найден у Yummy (13 пустых страниц каталога на
витрину, 65 по семейству) и у Zona в прошлом (`/year/1066/` отдавался 200 с
заголовком «1066 год» без карточек). Здесь он мерится у ВСЕХ семейств и по
разделам, которые витрина сама же называет ссылками.

Устройство. Разделы НЕ придумываются: берутся те, на которые ссылается сама
страница каталога (жанр, год, страна — обе формы адреса, путём и параметром).
Это важно: придуманный адрес проверял бы обработку неизвестного значения, а не
пустой раздел, а это разные вещи, и смешивать их нельзя.

Отдельно проверяются **заведомо отсутствующие** значения: у них правильный
ответ — 404 или `noindex`, и 200 с индексацией был бы находкой.

Инструмент только читает публичные страницы.

    python3 automation/local/empty-sections-probe.py zonafilm.space
    python3 automation/local/empty-sections-probe.py --all --limit 40
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urljoin

ПАСПОРТ = Path("/home/claude/wt-portable-site-cell-01/config/site-cells.json")
ФОРМЫ_КАРТОЧКИ = ("/title/", "/anime/")
#: Ссылки на разделы, которые витрина даёт сама. Обе формы адреса: путём и
#: параметром — у Lords/AnimeGo первая, у Zona/Animedia вторая.
ССЫЛКИ_РАЗДЕЛОВ = (
    r'href="(/genre/[^"#]+)"', r'href="([^"]*[?&]genre=[^"&]+[^"]*)"',
    r'href="(/year/[^"#]+)"', r'href="([^"]*[?&]year=[^"&]+[^"]*)"',
    r'href="(/c/[^"#]+)"', r'href="([^"]*[?&]country=[^"&]+[^"]*)"',
)
#: Заведомо отсутствующие значения. Год взят вне любого кинопроизводства, жанр
#: и страна — строки, которых в таксономии быть не может.
ЗАВЕДОМО_НЕТ = ("/year/1066/", "/genre/nesuschestvuyuschiy-zhanr-13102026/",
                "/c/nesuschestvuyuschaya-strana-13102026/")


def достать(url: str, таймаут: int = 40) -> tuple[str, str, dict[str, str]]:
    with tempfile.NamedTemporaryFile(prefix="es-head-", suffix=".txt") as ф, \
            tempfile.NamedTemporaryFile(prefix="es-body-", suffix=".bin") as б:
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
    если = (заг.get("x-robots-tag") or "").lower()
    if "noindex" in если:
        return True
    м = re.search(r'<meta[^>]+name=["\']robots["\'][^>]*content=["\']([^"\']+)',
                  тело, re.I)
    return bool(м and "noindex" in м.group(1).lower())


def карточек(тело: str) -> tuple[int, str] | None:
    """(сколько, форма) или None — форма адреса карточки не распознана.

    None не равен нулю: ноль утверждает «записей нет», None — «мерить нечем».
    """
    for форма in ФОРМЫ_КАРТОЧКИ:
        найдено = set(re.findall(
            r'href="(' + re.escape(форма) + r'[^"#?]+)"', тело))
        if найдено:
            return len(найдено), форма
    return None


def разделы(тело: str) -> list[str]:
    итог: set[str] = set()
    for ш in ССЫЛКИ_РАЗДЕЛОВ:
        итог.update(re.findall(ш, тело))
    return sorted(итог)


def проверить(домен: str, предел: int) -> list[str]:
    замечания: list[str] = []
    корень = f"https://{домен}"
    # Каталог у Yummy без хвостовой косой черты отвечает 308; переходы следуются.
    код, тело, заг = достать(f"{корень}/catalog/", таймаут=30)
    if код != "200":
        причина = заг.get("ошибка-curl") or f"код {код or 'пустой'}"
        print(f"   каталог отвечает {причина} — разделы НЕ ИЗМЕРЕНЫ")
        return замечания
    список = разделы(тело)
    # Форма адреса карточки берётся с НЕПУСТОЙ страницы каталога: если её не
    # распознать здесь, ноль карточек в разделе ничего не значил бы.
    эталон = карточек(тело)
    if эталон is None:
        print("   форма адреса карточки не распознана на странице каталога — "
              "разделы НЕ ИЗМЕРЕНЫ")
        замечания.append(f"{домен}: форма адреса карточки не распознана — "
                         "пустоту раздела мерить нечем")
        return замечания
    print(f"   каталог: карточек {эталон[0]} (форма {эталон[1]}), "
          f"ссылок на разделы {len(список)}; проверяю {min(предел, len(список))}")

    пусто = живых = 0
    for адрес in список[:предел]:
        к, т, з = достать(urljoin(корень, адрес))
        if к != "200":
            continue
        найдено = карточек(т)
        сколько = найдено[0] if найдено else 0
        if сколько:
            живых += 1
            continue
        пусто += 1
        если_закрыта = закрыта(т, з)
        h1 = re.search(r"<h1[^>]*>(.{0,80}?)</h1>", т, re.S)
        подпись = (h1.group(1).strip() if h1 else "—")
        if not если_закрыта:
            замечания.append(
                f"{домен}{адрес}: код 200, карточек 0, индексируется, "
                f"H1 «{подпись}» — пустая индексируемая страница раздела")
        else:
            print(f"      {адрес}: 0 карточек, но noindex — в индекс не попадёт")
    print(f"   разделов с записями {живых}, пустых {пусто}")

    for адрес in ЗАВЕДОМО_НЕТ:
        к, т, з = достать(f"{корень}{адрес}")
        if к == "200" and not закрыта(т, з):
            найдено = карточек(т)
            замечания.append(
                f"{домен}{адрес}: код 200 и индексируется "
                f"(карточек {найдено[0] if найдено else 0}) — заведомо "
                "отсутствующее значение раздела выглядит страницей")
        else:
            print(f"      заведомо нет {адрес}: код {к}"
                  f"{', noindex' if к == '200' else ''} — верно")
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
    р.add_argument("--limit", type=int, default=30,
                   help="сколько разделов проверять на витрине")
    а = р.parse_args()

    цели = а.домены or (домены() if а.all else [])
    if not цели:
        print("не названо ни одной витрины: домен аргументом или --all")
        return 2

    все: list[str] = []
    for домен in цели:
        print(f"\n=== {домен}")
        все.extend(проверить(домен, max(1, а.limit)))

    print(f"\n{'=' * 60}\nзамечаний: {len(все)}")
    for з in все:
        print(f"  • {з}")
    return 1 if все else 0


if __name__ == "__main__":
    sys.exit(main())
