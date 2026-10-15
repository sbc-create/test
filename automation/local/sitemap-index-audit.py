#!/usr/bin/env python3
"""Согласован ли индекс карты сайта со своим содержимым.

Зачем отдельная проверка. Обходчик читает `/sitemap.xml` первым и по
`<lastmod>` каждой вложенной карты решает, перезапрашивать ли её. Если индекс
объявляет дату старше содержимого, свежие адреса остаются непрочитанными — и
снятие потолка, и новые страницы до поиска не доезжают. Измерено 2026-10-15 на
пяти витринах Yummy: индекс объявлял всем пяти частям `2026-08-21`, тогда как
внутри `titles.xml` записи были от `2026-10-12` (разрыв 52 суток).

Что считается расхождением:

* `lastmod` части в индексе СТАРШЕ свежайшего `lastmod` внутри этой части;
* часть, объявленная индексом, отвечает не 200;
* часть, у которой в индексе нет `lastmod` вовсе (обходчику нечем решать).

Совпадение дат и «внутри дат нет» расхождением НЕ считаются: карта без дат
имеет право нести дату сборки, и это отдельный разговор, а не ошибка.

    python3 automation/local/sitemap-index-audit.py yummyani.org
    python3 automation/local/sitemap-index-audit.py --all-yummy --json
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys

ВИТРИНЫ_YUMMY = ("yummyani.site", "yummyani.org", "yummyani.biz",
                 "yummyani7.site", "yummyani7.info")


def достать(адрес: str, таймаут: int) -> tuple[str, str]:
    """Код ответа и тело. Исключение кодом не подменяется."""
    try:
        г = subprocess.run(
            ["curl", "-sS", "-w", "\n@@КОД@@%{http_code}", "--max-time",
             str(таймаут), адрес],
            capture_output=True, text=True, timeout=таймаут + 20)
    except subprocess.SubprocessError as ош:
        return f"{type(ош).__name__}", ""
    вывод = г.stdout or ""
    м = re.search(r"@@КОД@@(\d+)\s*$", вывод)
    if not м:
        return "нет ответа", вывод
    return м.group(1), вывод[:м.start()]


def даты(xml: str) -> list[str]:
    return re.findall(r"<lastmod>\s*([^<\s]+)\s*</lastmod>", xml)


def проверить(домен: str, таймаут: int = 90) -> dict:
    итог: dict = {"domain": домен, "parts": [], "problems": [], "ok": False}
    код, индекс = достать(f"https://{домен}/sitemap.xml", 40)
    итог["index_status"] = код
    if код != "200":
        итог["problems"].append(f"индекс ответил {код}")
        return итог          # ok остаётся False: ответа нет — вывода нет
    записи = re.findall(r"<sitemap>(.*?)</sitemap>", индекс, re.S)
    итог["declared_parts"] = len(записи)
    if not записи:
        итог["problems"].append(
            "индекс не перечисляет вложенных карт: проверять нечего")
        return итог
    for запись in записи:
        м_адрес = re.search(r"<loc>\s*([^<\s]+)\s*</loc>", запись)
        if not м_адрес:
            итог["problems"].append("в записи индекса нет <loc>")
            continue
        адрес = м_адрес.group(1)
        имя = адрес.rsplit("/", 1)[-1]
        м_дата = re.search(r"<lastmod>\s*([^<\s]+)\s*</lastmod>", запись)
        объявлено = м_дата.group(1) if м_дата else None
        код_части, часть = достать(адрес, таймаут)
        внутри = даты(часть)
        свежайшее = max(внутри) if внутри else None
        запись_итога = {
            "part": имя, "url": адрес, "status": код_части,
            "urls": len(re.findall(r"<loc>", часть)),
            "declared_lastmod": объявлено, "newest_inside": свежайшее,
        }
        if код_части != "200":
            итог["problems"].append(f"{имя}: ответ {код_части}")
        elif объявлено is None:
            итог["problems"].append(
                f"{имя}: в индексе нет lastmod — обходчику нечем решать")
        elif свежайшее and объявлено < свежайшее:
            итог["problems"].append(
                f"{имя}: индекс объявляет {объявлено}, внутри {свежайшее} — "
                "обходчик имеет основание карту не перезапрашивать")
            запись_итога["stale_index"] = True
        итог["parts"].append(запись_итога)
    итог["ok"] = not итог["problems"]
    return итог


def main() -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("domains", nargs="*")
    р.add_argument("--all-yummy", action="store_true")
    р.add_argument("--timeout", type=int, default=90)
    р.add_argument("--json", action="store_true")
    а = р.parse_args()
    домены = list(dict.fromkeys(а.domains + (list(ВИТРИНЫ_YUMMY) if а.all_yummy else [])))
    if not домены:
        print("нужен домен или --all-yummy", file=sys.stderr)
        return 2
    итоги = [проверить(д, а.timeout) for д in домены]
    if а.json:
        print(json.dumps(итоги, ensure_ascii=False, indent=2))
    else:
        for и in итоги:
            знак = "ок " if и.get("ok") else "НЕТ"
            print(f"[{знак}] {и['domain']}: индекс {и['index_status']}, "
                  f"частей {и.get('declared_parts', 0)}")
            for ч in и["parts"]:
                пометка = " ← индекс старше" if ч.get("stale_index") else ""
                print(f"       {ч['part']:14} {ч['status']} адресов "
                      f"{ч['urls']:5} | индекс {ч['declared_lastmod']} | "
                      f"внутри {ч['newest_inside']}{пометка}")
            for п in и["problems"]:
                print(f"       → {п}")
    плохих = [и for и in итоги if not и.get("ok")]
    print(f"\nвитрин проверено {len(итоги)}, с расхождениями {len(плохих)}")
    return 1 if плохих else 0


if __name__ == "__main__":
    sys.exit(main())
