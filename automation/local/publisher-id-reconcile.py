#!/usr/bin/env python3
"""Три места `publisher_id` по D177: согласны ли они, и где пусто.

Решение D177 называет три места и требует их согласия:

1. **значение** — файл производителя вне git (`player-<site_id>.json`, 0600).
   Эта сессия его не читает и не пытается: права принадлежат учётной записи
   сайта, и это правильно;
2. **объявление** — `config/site.json: publisher_id_expected` в пакете сайта;
3. **учёт** — `config/site-cells.json: publisher.publisher_id` в реестре.

Вместо недоступного первого места берётся то, что витрина отдаёт САМА:
атрибут `data-publisher-id` на карточке. Он публичен по устройству — проверено
на живых страницах, — поэтому сверка им законна, а значение секретом не
является.

Что инструмент пишет и чего не пишет. Заполняется ТОЛЬКО учёт и ТОЛЬКО там,
где объявление и живая страница согласны между собой: два независимых
источника против одного — разница между записью по знанию и записью по
догадке. Где объявления нет, учёт не выдумывается: такой случай выводится
отдельно, потому что это вопрос о самом D177 для этого семейства, а не
опечатка в реестре.

Значения не печатаются никогда: только равенство, наличие и чей ещё это
идентификатор.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(КОРЕНЬ))

#: Где лежат рабочие копии репозиториев сайтов. Отдельной постоянной —
#: чтобы приёмка этого инструмента могла подставить свой стенд.
КОРЕНЬ_ЯЧЕЕК = КОРЕНЬ / "var" / "site-repos"

ЗАГОЛОВКИ = {"User-Agent": "site-factory-acceptance/1.0 (publisher)"}
ПРЕДЕЛ_С = 30
КАРТОЧКА = re.compile(r'href="(/(?:title|anime)/[^"]+)"')
АТРИБУТ = re.compile(r'data-publisher-id="(\d+)"')
#: Сколько карточек пробуется, прежде чем признать «не измерено».
КАРТОЧЕК = 3


class _Перенаправления(urllib.request.HTTPRedirectHandler):
    """308 на Python 3.10 не следуется штатно, а `/catalog/` его отдаёт."""

    def http_error_308(self, req, fp, code, msg, headers):  # noqa: N802
        return self.http_error_307(req, fp, 307, msg, headers)


_ОТКРЫВАТЕЛЬ = urllib.request.build_opener(_Перенаправления())


def достать(url: str) -> str:
    try:
        with _ОТКРЫВАТЕЛЬ.open(
                urllib.request.Request(url, headers=ЗАГОЛОВКИ),
                timeout=ПРЕДЕЛ_С) as ответ:
            return ответ.read().decode("utf-8", "replace")
    except (urllib.error.URLError, OSError, ValueError):
        return ""


def живое(домен: str) -> str:
    """Что витрина отдаёт сама. Пусто — значит не измерено, а не «нет»."""
    каталог = достать(f"https://{домен}/catalog/") or достать(f"https://{домен}/")
    if not каталог:
        return ""
    for путь in КАРТОЧКА.findall(каталог)[:КАРТОЧЕК]:
        найдено = АТРИБУТ.search(достать(f"https://{домен}{путь}"))
        if найдено:
            return найдено.group(1)
    return ""


def объявление(ячейка) -> str:
    """`config/site.json: publisher_id_expected` пакета сайта."""
    путь = (ячейка.repo.get("path") or "")
    if not путь:
        return ""
    файл = КОРЕНЬ_ЯЧЕЕК / Path(путь).name / "config" / "site.json"
    if not файл.is_file():
        return ""
    try:
        return str(json.loads(файл.read_text(encoding="utf-8")).get(
            "publisher_id_expected") or "")
    except (ValueError, OSError):
        return ""


def главное(аргв=None) -> int:
    р = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--registry", type=Path, default=None)
    р.add_argument("--site", action="append", default=[])
    р.add_argument("--confirm-writes", action="store_true",
                   help="заполнить УЧЁТ там, где объявление и живое согласны")
    р.add_argument("--offline", action="store_true",
                   help="не ходить в сеть: тогда живое значение не измерено")
    опции = р.parse_args(аргв)

    from factory.cell import registry as реестр_модуль

    ячейки = [я for я in реестр_модуль.all_cells(опции.registry)
              if not опции.site or я.site_id in опции.site]
    if not ячейки:
        print("в реестре нет таких ячеек", file=sys.stderr)
        return 2

    учёт_всех: dict[str, list[str]] = {}
    for я in ячейки:
        зн = str((я.publisher or {}).get("publisher_id") or "")
        if зн:
            учёт_всех.setdefault(зн, []).append(я.site_id)

    к_записи: list[tuple[str, str]] = []
    расхождения: list[str] = []
    без_объявления: list[str] = []
    не_измерено = 0

    for я in sorted(ячейки, key=lambda c: c.site_id):
        if not я.domain:
            continue
        учёт = str((я.publisher or {}).get("publisher_id") or "")
        объявлено = объявление(я)
        факт = "" if опции.offline else живое(я.domain)

        if not факт:
            не_измерено += 1
            знак, подробно = "—  ", "карточка не ответила или атрибута нет"
        elif объявлено and факт != объявлено:
            знак = "НЕТ"
            подробно = ("живое значение расходится с объявлением "
                        "config/site.json: publisher_id_expected")
            расхождения.append(я.site_id)
        elif учёт and учёт != факт:
            знак = "НЕТ"
            чей = учёт_всех.get(учёт, [])
            подробно = (f"учёт в реестре расходится с живым; то, что в учёте, "
                        f"объявлено у {', '.join(чей) or 'никого'}")
            расхождения.append(я.site_id)
        elif учёт:
            общий = учёт_всех.get(учёт, [])
            знак = "ок " if len(общий) == 1 else "зам"
            подробно = ("все три места согласны" if len(общий) == 1 else
                        f"согласны, но тот же идентификатор в учёте у "
                        f"{len(общий)} ячеек: {', '.join(общий)}")
        elif объявлено:
            знак = "НЕТ"
            подробно = ("учёт пуст, а объявление и живое согласны — "
                        "заполняется по двум источникам")
            к_записи.append((я.site_id, факт))
        else:
            знак = "НЕТ"
            подробно = ("пусты И учёт, И объявление, а витрина идентификатор "
                        "отдаёт: вопрос о D177 для этого семейства")
            без_объявления.append(я.site_id)
        print(f"   [{знак}] {я.site_id:12} {я.domain:20} {подробно}")

    print(f"\nячеек: {len(ячейки)}; к заполнению учёта: {len(к_записи)}; "
          f"расхождений: {len(расхождения)}; без объявления: "
          f"{len(без_объявления)}; не измерено: {не_измерено}")
    if без_объявления:
        print(f"учёт НЕ выдумывается для {без_объявления}: одного источника "
              "мало, и пустое объявление — вопрос к D177, а не опечатка")

    if not опции.confirm_writes:
        if к_записи:
            print(f"\nничего не записано: нужен --confirm-writes "
                  f"(к заполнению {len(к_записи)})")
        # Пустое объявление при работающей витрине — тоже остаток:
        # исход 0 обязан значить «докладывать нечего».
        return 1 if (к_записи or расхождения or без_объявления) else 0

    записано, отказы = 0, []
    for site_id, значение in к_записи:
        ячейка = next(я for я in ячейки if я.site_id == site_id)
        новый = {**(ячейка.publisher or {}), "publisher_id": значение}
        try:
            реестр_модуль.update(site_id, {"publisher": новый},
                                 path=опции.registry)
            записано += 1
        except Exception as сбой:  # noqa: BLE001 — отказ называется
            отказы.append(f"{site_id}: {type(сбой).__name__}: {сбой}")
    print(f"\nзаполнено записей учёта: {записано} из {len(к_записи)}")
    for о in отказы:
        print(f"   ОТКАЗ {о}", file=sys.stderr)
    return 1 if (отказы or расхождения or без_объявления) else 0


if __name__ == "__main__":
    raise SystemExit(главное())
