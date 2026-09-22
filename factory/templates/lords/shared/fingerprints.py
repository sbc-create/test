#!/usr/bin/env python3
"""Отпечатки шаблонов: DOM, раскладка и то, как страница выглядит.

## Зачем три отпечатка, а не один

Подпись композиции сравнивает объявленное. Этого мало для независимой
проверки: объявить можно одно, а получиться может другое. Поэтому здесь
считаются три независимые величины по РЕЗУЛЬТАТУ:

* **DOM-отпечаток** — скелет разметки без текста: последовательность тегов и
  классов. Два пакета с одинаковым скелетом — это один шаблон, чем бы они ни
  отличались в словах;
* **отпечаток раскладки** — лестницы колонок и число карточек по ширинам,
  снятые из CSS результата;
* **перцептивный отпечаток снимка** — усреднённый хеш уменьшенного до 16×16
  полутонового снимка. Он ловит случай, когда DOM разный, а страница
  выглядит одинаково: именно так «разные шаблоны» и оказываются перекраской.

Расстояние по снимкам считается по Хэммингу: у одинаковых картинок оно около
нуля, у разных — десятки бит.

Перцептивный отпечаток намеренно грубый. Он не доказывает красоту и не
заменяет глаз владельца — он ловит совпадение, которое человек, просматривая
пятьдесят страниц подряд, заметит не сразу.
"""

from __future__ import annotations

import argparse
import itertools
import json
import pathlib
import re
import struct
import zlib

#: Ниже этого расстояния по Хэммингу две страницы считаются визуально
#: неразличимыми. Порог выведен из наблюдения: у пакетов одного семейства
#: расстояние держится выше двадцати бит, у копии — ноль.
ПОРОГ_СНИМКА = 6


def dom_отпечаток(html: str) -> str:
    """Скелет разметки: теги и классы, без текста и атрибутов данных."""
    скелет = []
    for тег, атрибуты in re.findall(r"<([a-zA-Z][\w-]*)([^>]*)>", html):
        классы = re.search(r'class="([^"]*)"', атрибуты)
        скелет.append(тег.lower() + ("." + ".".join(sorted(классы.group(1).split())) if классы else ""))
    return f"{len(скелет)}:{zlib.crc32('|'.join(скелет).encode()):08x}"


def раскладка_отпечаток(html: str) -> str:
    """Лестницы колонок и точки перелома из стилей результата."""
    правила = re.findall(r"grid-template-columns:repeat\((\d+)", html)
    точки = sorted(set(int(т) for т in re.findall(r"@media\(min-width:(\d+)px\)", html)))
    карточки = len(re.findall(r'class="k k--', html))
    return f"cols={'-'.join(правила)}|bp={'-'.join(map(str, точки))}|cards={карточки}"


def _png_серый_16(путь: pathlib.Path) -> list[int] | None:
    """Полутоновая матрица 16×16 из PNG без внешних библиотек.

    Читается только необходимое: заголовок и сжатые строки. Полноценного
    декодера здесь нет и не нужно — нужен грубый отпечаток, а не картинка.
    """
    данные = путь.read_bytes()
    if данные[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    сдвиг, ширина, высота, глубина, тип = 8, 0, 0, 0, 0
    поток = b""
    while сдвиг < len(данные):
        длина = struct.unpack(">I", данные[сдвиг:сдвиг + 4])[0]
        имя = данные[сдвиг + 4:сдвиг + 8]
        тело = данные[сдвиг + 8:сдвиг + 8 + длина]
        if имя == b"IHDR":
            ширина, высота, глубина, тип = struct.unpack(">IIBB", тело[:10])
        elif имя == b"IDAT":
            поток += тело
        elif имя == b"IEND":
            break
        сдвиг += 12 + длина
    if not поток or глубина != 8 or тип not in (2, 6):
        return None
    каналов = 3 if тип == 2 else 4
    сырое = zlib.decompress(поток)
    шаг = ширина * каналов
    строки: list[bytes] = []
    пред = bytearray(шаг)
    поз = 0
    for _ in range(высота):
        фильтр = сырое[поз]; поз += 1
        текущая = bytearray(сырое[поз:поз + шаг]); поз += шаг
        for i in range(шаг):
            a = текущая[i - каналов] if i >= каналов else 0
            b = пред[i]
            c = пред[i - каналов] if i >= каналов else 0
            if фильтр == 1: текущая[i] = (текущая[i] + a) & 0xFF
            elif фильтр == 2: текущая[i] = (текущая[i] + b) & 0xFF
            elif фильтр == 3: текущая[i] = (текущая[i] + (a + b) // 2) & 0xFF
            elif фильтр == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                пр = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                текущая[i] = (текущая[i] + пр) & 0xFF
        строки.append(bytes(текущая)); пред = текущая

    сетка = []
    for ry in range(16):
        y = min(высота - 1, ry * высота // 16)
        строка = строки[y]
        for rx in range(16):
            x = min(ширина - 1, rx * ширина // 16) * каналов
            r, g, b = строка[x], строка[x + 1], строка[x + 2]
            сетка.append((r * 299 + g * 587 + b * 114) // 1000)
    return сетка


def снимок_отпечаток(путь: pathlib.Path) -> str | None:
    сетка = _png_серый_16(путь)
    if not сетка:
        return None
    среднее = sum(сетка) / len(сетка)
    биты = "".join("1" if з > среднее else "0" for з in сетка)
    return f"{int(биты, 2):064x}"


def расстояние(a: str, b: str) -> int:
    return bin(int(a, 16) ^ int(b, 16)).count("1")


#: Маршруты, по которым считается сходство. Одной главной мало: два шаблона
#: могут открываться по-разному и оказаться неотличимыми в каталоге, где
#: человек проводит больше времени.
СРАВНИВАЕМЫЕ = ("home", "catalog", "title-series")


def собрать(превью: pathlib.Path, снимки: pathlib.Path) -> dict:
    записи = {}
    for каталог in sorted(превью.iterdir()):
        страница = каталог / "home.html"
        if not страница.is_file():
            страница = каталог / "index.html"
        if not страница.is_file():
            continue
        tid = каталог.name[:4]
        html = страница.read_text(encoding="utf-8")
        каталожная = каталог / "catalog.html"
        снимки_маршрутов = {}
        for маршрут in СРАВНИВАЕМЫЕ:
            файл = снимки / tid / f"{маршрут}-1440.png"
            if файл.is_file():
                снимки_маршрутов[маршрут] = снимок_отпечаток(файл)
        записи[tid] = {
            "dom": dom_отпечаток(html),
            "dom_catalog": (dom_отпечаток(каталожная.read_text(encoding="utf-8"))
                            if каталожная.is_file() else None),
            "layout": раскладка_отпечаток(html),
            "screenshot": снимки_маршрутов.get("home"),
            "routes": снимки_маршрутов,
        }
    return записи


def ближайшие(записи: dict) -> dict:
    """Ближайший визуальный сосед каждого шаблона и расстояние до него.

    Владельцу это нужнее среднего по пулу: «на что это больше всего похоже» —
    первый вопрос при отборе, и ответ на него должен быть измеренным.
    """
    итог = {}
    for a, x in записи.items():
        если_есть = [(расстояние(x["screenshot"], y["screenshot"]), b)
                     for b, y in записи.items()
                     if b != a and x["screenshot"] and y["screenshot"]]
        if не_пусто := sorted(если_есть):
            д, сосед = не_пусто[0]
            итог[a] = {"neighbour": сосед, "hamming": д,
                       "mean": round(sum(р for р, _ in не_пусто) / len(не_пусто), 1)}
    return итог


def главное() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preview", default="var/preview")
    parser.add_argument("--shots", default="var/shots")
    parser.add_argument("--record")
    args = parser.parse_args()

    записи = собрать(pathlib.Path(args.preview), pathlib.Path(args.shots))
    dom_дубли = [(a, b) for (a, x), (b, y) in itertools.combinations(записи.items(), 2)
                 if x["dom"] == y["dom"]]
    layout_дубли = [(a, b) for (a, x), (b, y) in itertools.combinations(записи.items(), 2)
                    if x["layout"] == y["layout"]]
    близкие = []
    for (a, x), (b, y) in itertools.combinations(записи.items(), 2):
        if x["screenshot"] and y["screenshot"]:
            d = расстояние(x["screenshot"], y["screenshot"])
            if d <= ПОРОГ_СНИМКА:
                близкие.append({"pair": [a, b], "hamming": d})

    # Пара считается визуально близкой, только если она близка И на главной,
    # И в каталоге: шаблоны с одинаковым входом, но разным каталогом — это
    # разные шаблоны, и объявлять их дублями нечестно.
    каталожные = []
    for (a, x), (b, y) in itertools.combinations(записи.items(), 2):
        ка, кб = x["routes"].get("catalog"), y["routes"].get("catalog")
        if ка and кб and расстояние(ка, кб) <= ПОРОГ_СНИМКА:
            каталожные.append({"pair": [a, b], "hamming": расстояние(ка, кб)})
    близкие = [п for п in близкие
               if any(к["pair"] == п["pair"] for к in каталожные)] if каталожные else []
    расстояния = [расстояние(x["screenshot"], y["screenshot"])
                  for (a, x), (b, y) in itertools.combinations(записи.items(), 2)
                  if x["screenshot"] and y["screenshot"]]
    отчёт = {
        "templates": len(записи),
        "with_screenshot": sum(1 for з in записи.values() if з["screenshot"]),
        "DOM_FINGERPRINT_DUPLICATES": len(dom_дубли),
        "dom_duplicate_pairs": dom_дубли,
        "LAYOUT_FINGERPRINT_DUPLICATES": len(layout_дубли),
        "layout_duplicate_pairs": layout_дубли,
        "SCREENSHOT_NEAR_DUPLICATES": len(близкие),
        "screenshot_near_pairs": близкие,
        "screenshot_hamming_min": min(расстояния) if расстояния else None,
        "screenshot_hamming_median": sorted(расстояния)[len(расстояния) // 2] if расстояния else None,
        "threshold": ПОРОГ_СНИМКА,
        "CATALOG_NEAR_DUPLICATES": len(каталожные),
        "catalog_near_pairs": каталожные,
        "nearest": ближайшие(записи),
        "fingerprints": записи,
        "PASS": not dom_дубли and not layout_дубли and not близкие,
    }
    if args.record:
        pathlib.Path(args.record).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(args.record).write_text(
            json.dumps(отчёт, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in отчёт.items() if k != "fingerprints"},
                     ensure_ascii=False, indent=2)[:1600])
    return 0 if отчёт["PASS"] else 2


if __name__ == "__main__":
    raise SystemExit(главное())
