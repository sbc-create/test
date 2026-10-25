#!/usr/bin/env python3
"""Доходит ли редакционный материал до посетителя. Путь целиком, по каждому.

Задание ночи: проследить материалы редакции «задание → фактический файл →
проверка → принятие → публикация → доступный URL» и определить, где они
задерживаются. Здесь проверяется самый конец этого пути, потому что он один
решает: видит ли текст посетитель.

По каждой замене из хранилища (`/var/lib/site-cells/editorial/<site>.json`):

1. запись существует и названа актором (кто и каким прогоном её сделал);
2. идентификатор произведения разрешается в слаг по снимку каталога витрины —
   если не разрешается, материал привязан к записи, которой в каталоге нет;
3. страница произведения запрашивается и в ней ищется ОТЛИЧИТЕЛЬНЫЙ кусок
   текста замены, а не её начало: начало часто совпадает с исходным описанием,
   и поиск по нему дал бы «опубликовано» и для неопубликованного.

Состояния: `дошло`, `НЕ ДОШЛО`, `страница не прочитана`, `нет в каталоге`,
`короткая замена` (куска длиной от 40 символов не нашлось — сравнивать нечем).

    python3 automation/local/editorial-reaches-visitor.py
    python3 automation/local/editorial-reaches-visitor.py --json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys

АГЕНТ = "factory-editorial-reaches-visitor"

ХРАНИЛИЩЕ = pathlib.Path("/var/lib/site-cells/editorial")
РЕЕСТР = pathlib.Path("/home/claude/wt-nova-publish-memory-02/config/site-cells.json")
#: Кусок текста, по которому ищется публикация. Короче — не отличительно.
МИН_КУСОК = 40


def достать(адрес: str, таймаут: int = 40) -> str | None:
    try:
        г = subprocess.run(["curl", "-A", АГЕНТ, "-sSL", "-w", "\n@@КОД@@%{http_code}",
                            "--max-time", str(таймаут), адрес],
                           capture_output=True, text=True, timeout=таймаут + 20)
    except subprocess.TimeoutExpired:
        return None
    тело, _, код = г.stdout.rpartition("@@КОД@@")
    return тело if код.strip() == "200" else None


def реестр() -> dict:
    d = json.loads(РЕЕСТР.read_text(encoding="utf-8"))
    return {я.get("site_id"): я for я in d.get("cells") or []}


def слаги(ячейка: dict) -> dict:
    """`{идентификатор: слаг}` из снимка подробностей витрины."""
    каталог = (ячейка.get("runtime") or {}).get("data_dir") or ""
    if not каталог:
        return {}
    корень = pathlib.Path(каталог)
    итог: dict = {}
    for файл in корень.glob("*-details.json"):
        try:
            d = json.loads(файл.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for слаг, запись in (d.get("details") or {}).items():
            ид = str((запись or {}).get("id") or "").strip()
            if ид:
                итог.setdefault(ид, слаг)
    return итог


def отличительный(замена: str) -> str | None:
    """Кусок текста, по которому публикацию можно отличить от исходного."""
    части = [ч.strip() for ч in re.split(r"[.!?]\s+", замена) if ч.strip()]
    части.sort(key=len, reverse=True)
    for ч in части:
        if len(ч) >= МИН_КУСОК:
            return ч[:120]
    return None


def проверить(site_id: str, ячейка: dict) -> dict:
    файл = ХРАНИЛИЩЕ / f"{site_id}.json"
    итог: dict = {"site_id": site_id, "домен": ячейка.get("domain", "—"),
                  "материалы": []}
    if not файл.is_file():
        итог["замечание"] = "файла хранилища нет — материалов не заводилось"
        return итог
    try:
        d = json.loads(файл.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        итог["замечание"] = "файл хранилища не прочитан"
        return итог
    замены = d.get("overrides") or {}
    по_ид = слаги(ячейка)
    слаги_каталога = set(по_ид.values())
    домен = ячейка.get("domain") or ""
    for ид, запись in замены.items():
        поля = (запись or {}).get("fields") or {}
        актор = (запись or {}).get("actor") or "—"
        текст = поле_текста(поля)
        # Ключ хранилища бывает ДВУХ видов: провайдерский идентификатор и
        # слаг. Первая редакция разрешала только идентификатор и объявила
        # материал «непривязанным» — а он был опубликован и виден на странице.
        # Поймано живой проверкой: заголовок страницы оказался заменённым.
        слаг = по_ид.get(ид)
        как = "по идентификатору"
        if слаг is None and ид in слаги_каталога:
            слаг, как = ид, "по слагу"
        строка = {"ид": ид[:12], "актор": актор, "поля": sorted(поля),
                  "слаг": слаг or "—", "ключ": как if слаг else "не разрешён"}
        if not слаг:
            строка["итог"] = "ключ не разрешён ни как идентификатор, ни как слаг"
        elif not текст:
            строка["итог"] = "нечего искать: заменено не текстовое поле"
        else:
            тело = достать(f"https://{домен}/title/{слаг}/")
            if тело is None:
                строка["итог"] = "страница не прочитана"
            elif "name" in поля or "title" in поля:
                # Название — короткая строка, и отличительного куска в ней не
                # найти. Зато поверхность узкая: название обязано стоять в `h1`
                # и в `title`, и там его можно сверить целиком. Без этой ветки
                # замена названия получала вердикт «короткая замена», то есть
                # оставалась непроверенной — а она была опубликована.
                цель = (поля.get("name") or поля.get("title") or "").strip()
                в_h1 = bool(re.search(r"<h1[^>]*>\s*" + re.escape(цель), тело))
                в_title = bool(re.search(r"<title[^>]*>\s*" + re.escape(цель), тело))
                строка["кусок"] = цель[:60]
                строка["итог"] = ("дошло" if (в_h1 or в_title)
                                  else "НЕ ДОШЛО")
                строка["где"] = ("h1+title" if в_h1 and в_title
                                 else "h1" if в_h1 else "title" if в_title else "—")
            else:
                кусок = отличительный(текст)
                if not кусок:
                    строка["итог"] = "замена короче 40 символов — сверять нечем"
                else:
                    строка["итог"] = "дошло" if кусок in тело else "НЕ ДОШЛО"
                    строка["кусок"] = кусок[:60]
        итог["материалы"].append(строка)
    return итог


def поле_текста(поля: dict) -> str:
    for имя in ("description", "name", "title", "synopsis"):
        значение = поля.get(имя)
        if isinstance(значение, str) and значение.strip():
            return значение
    return ""


def main(аргв: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--json", action="store_true")
    а = р.parse_args(аргв)
    ячейки = реестр()
    итоги = []
    for файл in sorted(ХРАНИЛИЩЕ.glob("*.json")):
        site_id = файл.stem
        ячейка = ячейки.get(site_id)
        if ячейка is None:
            итоги.append({"site_id": site_id, "домен": "—",
                          "замечание": "ячейки нет в реестре", "материалы": []})
            continue
        итоги.append(проверить(site_id, ячейка))
    if а.json:
        print(json.dumps(итоги, ensure_ascii=False, indent=1))
        return 0
    всего = дошло = не_дошло = прочее = 0
    for и in итоги:
        print(f"{и['site_id']:10} {и['домен']:22} материалов {len(и['материалы'])}"
              f"{'  ' + и['замечание'] if и.get('замечание') else ''}")
        for м in и["материалы"]:
            всего += 1
            if м["итог"] == "дошло":
                дошло += 1
            elif м["итог"] == "НЕ ДОШЛО":
                не_дошло += 1
            else:
                прочее += 1
            print(f"   {м['ид']:14} {м['слаг'][:30]:<30} {м.get('ключ', ''):<18}"
                  f" поля {','.join(м['поля'])[:20]:<20} {м['итог']}")
            print(f"   {'':14} актор {м['актор']}")
    print(f"\nматериалов всего {всего}: дошло {дошло}, НЕ ДОШЛО {не_дошло},"
          f" прочих состояний {прочее}")
    print("искался ОТЛИЧИТЕЛЬНЫЙ кусок замены (от 40 символов), а не её начало:"
          " начало часто совпадает с исходным описанием")
    return 1 if не_дошло else 0


if __name__ == "__main__":
    sys.exit(main())
