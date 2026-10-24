#!/usr/bin/env python3
"""Гигиена очереди: живые дубли на одном адресе и форма адреса.

ПОВОД — MOD-08: «Одна страница — два живых редакционных задания». Его критерий
прямо называет нужное: «queue_hygiene в штатном суточном отчёте: живых дублей
0, повторная регистрация того же адреса в относительной форме возвращает
существующее задание». Второй половины (дедупликация при регистрации) в моих
средствах нет — она в коде очереди; первая половина измеряется здесь.

ЧТО СЧИТАТЬ «ЖИВЫМ» — и почему это не мелочь. Первый мой счёт дал 0 дублей,
потому что живыми я взяла только «рабочие» статусы. Это было неверно: очередь
ПЕРЕНАЗНАЧАЕТ и заблокированные задания — `BLOCKED_INSUFFICIENT_FACTS` через
24 ч, `NO_TARGET_PAGE` через 6 ч (MOD-168). Значит живое — это всё, что
очередь ещё может выдать, а терминальное — то, про что её код говорит
«повторно не предлагается», плюс размещённое. С правильным определением дубль
нашёлся: 1 адрес из 1 121.

Определение взято из ПОВЕДЕНИЯ кода, а не из интуиции, и это записано здесь
же, чтобы следующий счёт не разошёлся с этим.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from collections import Counter, defaultdict

РЕЕСТР = pathlib.Path("/var/lib/seo-content-operator/registry.json")

#: Про эти статусы код очереди говорит «повторно не предлагается», либо текст
#: уже размещён. Всё остальное очередь может выдать снова.
ТЕРМИНАЛЬНЫЕ = frozenset({
    "PUBLISHED", "ALREADY_LIVE", "DUPLICATE", "NEAR_DUPLICATE",
    "SUPPRESSED_NEAR_DUPLICATE", "BLOCKED_WRONG_MAPPING",
})


def нормализовать(адрес: str, домен: str) -> tuple[str, str]:
    """Домен и путь. Абсолютная и относительная формы дают ОДИН ключ.

    Именно расхождение форм и породило дубль в MOD-08: одно задание
    зарегистрировано на `https://домен/anime/slug`, другое на `/anime/slug`.
    """
    п = re.sub(r"^https?://[^/]+", "", str(адрес or "").strip())
    п = п.split("?")[0].split("#")[0].rstrip("/")
    return (str(домен or ""), п.lower())


def живые(записи: list[dict]) -> list[dict]:
    return [з for з in записи if з.get("status") not in ТЕРМИНАЛЬНЫЕ]


def дубли(записи: list[dict]) -> dict[tuple[str, str], list[dict]]:
    по: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for з in живые(записи):
        по[нормализовать(з.get("canonical_url"), з.get("target_site"))].append(з)
    return {к: в for к, в in по.items() if len(в) > 1}


def формы(записи: list[dict]) -> Counter:
    """Сколько живых заданий записано абсолютным адресом, сколько относительным."""
    из = Counter()
    for з in живые(записи):
        а = str(з.get("canonical_url") or "")
        из["абсолютная" if а.startswith("http") else
           ("относительная" if а.startswith("/") else "иная")] += 1
    return из


def главное(argv: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--registry", type=pathlib.Path, default=РЕЕСТР)
    р.add_argument("--json", type=pathlib.Path)
    а = р.parse_args(argv)

    if not а.registry.exists():
        print(f"НЕ ИЗМЕРЕНО: реестра нет — {а.registry}")
        return 2
    записи = json.loads(а.registry.read_text(encoding="utf-8"))["items"]
    ж = живые(записи)
    д = дубли(записи)
    ф = формы(записи)

    print(f"заданий в реестре {len(записи)}; живых (переназначаемых) {len(ж)}")
    print(f"форма адреса у живых: " + ", ".join(f"{к} {в}" for к, в in ф.most_common()))
    print()
    print(f"АДРЕСОВ С БОЛЕЕ ЧЕМ ОДНИМ ЖИВЫМ ЗАДАНИЕМ: {len(д)}")
    for (домен, путь), в in sorted(д.items()):
        print(f"  {домен}{путь}")
        for з in в:
            форма = "абс" if str(з.get("canonical_url") or "").startswith("http") else "отн"
            print(f"     {з['content_id']:42} {str(з.get('status')):28} {форма}")
    # Относительная форма — редкость, и именно она рождает дубли. Поэтому
    # перечисляются ПОИМЁННО: это набор риска, а не статистика.
    редкие = [з for з in ж
              if not str(з.get("canonical_url") or "").startswith("http")]
    if редкие and len(редкие) <= 20:
        print(f"живые задания в ОТНОСИТЕЛЬНОЙ форме адреса ({len(редкие)}):")
        for з in редкие:
            print(f"  {з['content_id']:42} {str(з.get('target_site')):18}"
                  f" {str(з.get('canonical_url'))[:46]:48} {з.get('status')}")
        print()
    смешано = ф["абсолютная"] and ф["относительная"]
    print()
    if смешано:
        print(f"ПРИЧИНА РЯДОМ: обе формы адреса в ходу одновременно"
              f" (абсолютных {ф['абсолютная']}, относительных {ф['относительная']})."
              " Пока регистрация не сводит их к одной, дубль может появиться"
              " снова — вторая половина критерия MOD-08 в коде очереди")
    if а.json:
        а.json.parent.mkdir(parents=True, exist_ok=True)
        а.json.write_text(json.dumps({
            "live_tasks": len(ж),
            "duplicate_addresses": len(д),
            "address_forms": dict(ф),
            "duplicates": [
                {"domain": к[0], "path": к[1],
                 "tasks": [{"content_id": з["content_id"],
                            "status": з.get("status"),
                            "canonical_url": з.get("canonical_url")} for з in в]}
                for к, в in sorted(д.items())],
        }, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"подробности: {а.json}")
    if д:
        print(f"ВЫВОД: живых дублей {len(д)} — критерий MOD-08 не выполнен."
              " Убрать дубль моими средствами нечем: `annul` отменяет последний"
              " ИСХОД задания, а не задание; сведение адресов при регистрации"
              " живёт в коде очереди")
        return 1
    print("ВЫВОД: живых дублей нет")
    return 0


if __name__ == "__main__":
    sys.exit(главное())
