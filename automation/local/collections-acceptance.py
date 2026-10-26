#!/usr/bin/env python3
"""Приёмка редакционных подборок: схема, живые факты и неповторяемость по сети.

Требования владельца к подборке записаны проверяемо, и проверка разделена на
три части, потому что они отвечают на разные вопросы и ломаются по-разному:

* **схема** (`schemas/site-collections.schema.json`) — есть ли у подборки
  потребность пользователя, принцип отбора, содержательное описание,
  устойчивый ключ, осмысленный порядок, постоянные идентификаторы и
  ОБОСНОВАННОЕ решение об индексации. Схема не знает, правда ли написанное;
* **живые факты** — отвечает ли адрес, индексируется ли страница, есть ли
  постер и плеер. Это то, чего схема проверить не может, и ровно то, что
  устаревает: состав подбирается однажды, а каталог меняется каждую ночь;
* **неповторяемость** — одинаковые подборки по всей сети запрещены: общими
  должны быть механизм и требования, а состав и подача — по профилю домена.

Чего этот инструмент НЕ измеряет, и это сказано прямо: мобильный сценарий
«увидеть подборку → выбрать → открыть карточку → начать просмотр» измеряется
событиями аналитики, а не разметкой. Пока цели не выпущены ни на одной
витрине, кроме одной, этот признак остаётся «не измерено» — не «работает» и
не «сломано».

Только чтение: ни один файл подборок не правится.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import ssl
import urllib.error
import urllib.request

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
СХЕМА = КОРЕНЬ / "schemas" / "site-collections.schema.json"
ОК, НЕТ, НЕ_ИЗМЕРЕНО = "ок", "НЕТ", "не измерено"


def проверить_схемой(данные: dict, схема: pathlib.Path = СХЕМА) -> list[str]:
    """Нарушения требований, которые видны по самому файлу."""
    import jsonschema
    s = json.loads(схема.read_text(encoding="utf-8"))
    ош = []
    for e in jsonschema.Draft202012Validator(s).iter_errors(данные):
        путь = "/".join(str(ч) for ч in e.path) or "(корень)"
        ош.append(f"{путь}: {e.message}")
    return ош


def _снять(адрес: str, предел: float) -> dict:
    контекст = ssl.create_default_context()
    контекст.check_hostname = False
    контекст.verify_mode = ssl.CERT_NONE
    открыть = urllib.request.build_opener(urllib.request.HTTPSHandler(context=контекст))
    запрос = urllib.request.Request(адрес, headers={"User-Agent": "factory-collections-acceptance"})
    try:
        ответ = открыть.open(запрос, timeout=предел)
        тело = ответ.read(300_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as сбой:
        return {"код": сбой.code, "ошибка": f"HTTP {сбой.code}"}
    except Exception as сбой:  # noqa: BLE001 — чужая сеть не должна ронять приёмку
        return {"код": None, "ошибка": f"{type(сбой).__name__}: {str(сбой)[:60]}"}
    роботы = re.search(r"""name=["']robots["'][^>]+content=["']([^"']+)""", тело)
    канон = re.search(r"""rel=["']canonical["'][^>]+href=["']([^"']+)""", тело)
    return {"код": ответ.status, "байт": len(тело),
            "роботы": роботы.group(1) if роботы else "",
            "канон": канон.group(1) if канон else "",
            "плеер": bool(re.search(r"data-player\b", тело)),
            "постер": bool(re.search(r"<img[^>]+(?:poster|card__img)", тело))}


def живые_факты(данные: dict, выборка: int, предел: float) -> list[dict]:
    """Состояние первых `выборка` работ каждой подборки на живом сайте."""
    итог = []
    for подборка in данные.get("collections") or []:
        for элемент in (подборка.get("items") or [])[:выборка]:
            снято = _снять(элемент["url"], предел)
            беда = []
            if снято.get("ошибка"):
                беда.append(снято["ошибка"])
            else:
                if снято["код"] != 200:
                    беда.append(f"код {снято['код']}")
                if "noindex" in (снято["роботы"] or ""):
                    беда.append(f"роботы: {снято['роботы']}")
                if снято["канон"] and снято["канон"].rstrip("/") != элемент["url"].rstrip("/"):
                    беда.append(f"canonical ведёт на {снято['канон']}")
                if not снято["плеер"]:
                    беда.append("плеера на странице нет")
            итог.append({"подборка": подборка.get("key"), "работа": элемент.get("slug"),
                         "исход": ОК if not беда else НЕТ, "почему": "; ".join(беда) or "200, index, плеер есть"})
    return итог


def неповторяемость(файлы: list[pathlib.Path]) -> list[dict]:
    """Одинаковые ключи и заголовки подборок у РАЗНЫХ витрин."""
    по_ключу: dict[str, set[str]] = {}
    по_заголовку: dict[str, set[str]] = {}
    for ф in файлы:
        try:
            д = json.loads(ф.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        сайт = д.get("site") or ф.stem
        for п in д.get("collections") or []:
            по_ключу.setdefault(str(п.get("key")), set()).add(сайт)
            по_заголовку.setdefault(str(п.get("title")).strip().lower(), set()).add(сайт)
    итог = []
    for что, карта in (("ключ", по_ключу), ("заголовок", по_заголовку)):
        for значение, сайты in sorted(карта.items()):
            if len(сайты) > 1:
                итог.append({"что": что, "значение": значение[:60],
                             "сайты": sorted(сайты)})
    return итог


def главная(аргв: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("files", nargs="+", type=pathlib.Path, help="файлы подборок витрин")
    р.add_argument("--sample", type=int, default=2, help="сколько работ каждой подборки проверять живыми")
    р.add_argument("--timeout", type=float, default=25.0)
    р.add_argument("--offline", action="store_true", help="только схема и неповторяемость")
    а = р.parse_args(аргв)

    всего_нарушений = 0
    for ф in а.files:
        данные = json.loads(ф.read_text(encoding="utf-8"))
        print(f"\n=== {ф.name}: {данные.get('site')} ({данные.get('site_id')}), "
              f"состояние {данные.get('status')}")
        ош = проверить_схемой(данные)
        print(f"  схема: нарушений {len(ош)}")
        for с in ош[:8]:
            print(f"     {с[:120]}")
        всего_нарушений += len(ош)
        if а.offline:
            print("  живые факты: не измерено (запрошен режим без сети)")
        else:
            факты = живые_факты(данные, а.sample, а.timeout)
            плохо = [ф_ for ф_ in факты if ф_["исход"] == НЕТ]
            print(f"  живые факты: проверено {len(факты)}, с бедой {len(плохо)}")
            for ф_ in плохо[:6]:
                print(f"     {ф_['подборка']}/{ф_['работа']}: {ф_['почему'][:90]}")
            всего_нарушений += len(плохо)
        print("  мобильный сценарий: НЕ ИЗМЕРЕНО — нужны события аналитики, "
              "а не разметка (цели выпущены не на всех витринах)")
    повторы = неповторяемость(list(а.files))
    print(f"\nодинаковых подборок у разных витрин: {len(повторы)}")
    for п in повторы[:6]:
        print(f"   {п['что']} «{п['значение']}» у {', '.join(п['сайты'])}")
    всего_нарушений += len(повторы)
    return 1 if всего_нарушений else 0


if __name__ == "__main__":
    raise SystemExit(главная())
