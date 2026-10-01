#!/usr/bin/env python3
"""Публичная почта обратной связи на ВЫЛОЖЕННЫХ витринах.

    python3 automation/host/contact-email-live-check.py            # весь реестр
    python3 automation/host/contact-email-live-check.py --site lords-02
    python3 automation/host/contact-email-live-check.py --json var/reports/x.json

Зачем отдельная проверка после выкладки
---------------------------------------

Проверки в репозитории отвечают на вопрос «что мы собрали». Они не отвечают на
вопрос «что отдаёт домен»: выложен мог быть прежний релиз, страницу мог отдать
кэш, а у витрины-прокси разметка вообще приходит из чужого образа. Опрос сети
2026-10-01 застал все три случая сразу — часть витрин с прежним адресом, две
без адреса вовсе, и при этом везде заполненная конфигурация.

Поэтому проверка смотрит на выложенный HTML и держит четыре утверждения:

  * новый адрес виден в тексте страницы;
  * `mailto:` ведёт на него же — отображаемый текст и ссылка совпадают, иначе
    посетитель копирует одно, а письмо уходит другому;
  * прежнего адреса на странице нет;
  * проверены и главная, и страницы обратной связи, какие у витрины есть.

Чего проверка НЕ делает
-----------------------

Не подтверждает доставку писем: `mailto:` не отвечает кодом доставки, и
правильная ссылка с дошедшим письмом — разные утверждения. Писем она не
отправляет.
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

#: Адрес сети. Берётся из единственного источника, если он доступен; иначе из
#: аргумента. Литерала здесь нет намеренно: это был бы пятый экземпляр.
def _адрес_сети() -> str:
    sys.path.insert(0, str(КОРЕНЬ))
    from factory import contact  # noqa: PLC0415

    return contact.ПОЧТА_СЕТИ


ПРЕЖНИЕ = ("sbc.claude@yandex.ru",)

#: Пути, где у витрин бывает обратная связь. Отсутствие пути — не отказ:
#: у витрин-ячеек страницы контактов нет вовсе, адрес живёт только в подвале.
ПУТИ = ("/", "/support", "/pages/info", "/pages/report", "/pages/faq", "/about")

ЗАГОЛОВКИ = {"User-Agent": "Mozilla/5.0 (contact-email-live-check)"}


def _страница(url: str, таймаут: int = 25) -> tuple[int | None, str]:
    try:
        запрос = urllib.request.Request(url, headers=ЗАГОЛОВКИ)
        ответ = urllib.request.urlopen(запрос, timeout=таймаут)
        return ответ.status, ответ.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as ошибка:
        return ошибка.code, ""
    except Exception:  # noqa: BLE001 — любая сетевая беда здесь равнозначна
        return None, ""


def _mailto(текст: str) -> list[str]:
    # Обратный слэш отсекается: в полезной нагрузке Next адрес экранирован.
    return sorted({с.rstrip("\\") for с in re.findall(r'mailto:([^"\'>\s\\]+)', текст)})


def проверить_домен(домен: str, адрес: str) -> dict:
    итог: dict = {"domain": домен, "expect": адрес, "pages": [], "verdict": "FAIL"}
    видели_адрес = False
    видели_прежний: list[str] = []
    неверный_mailto: list[str] = []
    главная_код: int | None = None

    for путь in ПУТИ:
        код, текст = _страница(f"https://{домен}{путь}")
        if путь == "/":
            главная_код = код
        if код != 200 or not текст:
            итог["pages"].append({"path": путь, "http": код, "checked": False})
            continue
        есть = адрес in текст
        прежние = [с for с in ПРЕЖНИЕ if с in текст]
        ссылки = _mailto(текст)
        чужие = [с for с in ссылки if с != адрес]
        итог["pages"].append({
            "path": путь, "http": 200, "checked": True,
            "address_visible": есть, "mailto": ссылки,
            "old_present": прежние,
        })
        видели_адрес = видели_адрес or есть
        видели_прежний += прежние
        # mailto, ведущий не на адрес сети, — расхождение ссылки и текста.
        неверный_mailto += [f"{путь}:{с}" for с in чужие]

    итог["home_http"] = главная_код
    итог["address_seen"] = видели_адрес
    итог["old_seen"] = sorted(set(видели_прежний))
    итог["foreign_mailto"] = sorted(set(неверный_mailto))
    причины = []
    if главная_код != 200:
        причины.append(f"главная отвечает {главная_код}")
    if not видели_адрес:
        причины.append("нового адреса нет ни на одной проверенной странице")
    if видели_прежний:
        причины.append(f"остался прежний адрес: {sorted(set(видели_прежний))}")
    if неверный_mailto:
        причины.append(f"mailto ведёт не на адрес сети: {sorted(set(неверный_mailto))}")
    итог["verdict"] = "PASS" if not причины else "FAIL"
    итог["reasons"] = причины
    return итог


def _реестр() -> list[tuple[str, str]]:
    данные = json.loads((КОРЕНЬ / "config" / "site-cells.json").read_text(encoding="utf-8"))
    ячейки = данные.get("cells") or данные.get("sites") or []
    сп = ячейки if isinstance(ячейки, list) else list(ячейки.values())
    итог = []
    for я in сп:
        if not (я.get("repo") or {}).get("path"):
            continue  # местные заготовки без репозитория: проверять нечего
        итог.append((я.get("site_id") or "?", я.get("domain") or ""))
    return [(s, d) for s, d in итог if d]


def главная() -> int:
    р = argparse.ArgumentParser(description="почта обратной связи на выложенных витринах")
    р.add_argument("--site", help="site_id одной витрины; без него — весь реестр")
    р.add_argument("--address", help="ожидаемый адрес; по умолчанию из factory.contact")
    р.add_argument("--json", help="куда записать подробный отчёт")
    а = р.parse_args()

    адрес = а.address or _адрес_сети()
    цели = _реестр()
    if а.site:
        цели = [(s, d) for s, d in цели if s == а.site]
        if not цели:
            print(f"в реестре нет витрины {а.site}", file=sys.stderr)
            return 2

    отчёты = []
    отказов = 0
    print(f"ожидается адрес: {адрес}\n")
    print(f"{'домен':24} {'итог':5} подробности")
    for site_id, домен in цели:
        о = проверить_домен(домен, адрес)
        о["site_id"] = site_id
        отчёты.append(о)
        страниц = sum(1 for p in о["pages"] if p.get("checked"))
        if о["verdict"] != "PASS":
            отказов += 1
        подробно = (f"страниц проверено {страниц}; " + "; ".join(о["reasons"])) \
            if о["reasons"] else f"страниц проверено {страниц}, адрес и mailto совпадают"
        print(f"{домен:24} {о['verdict']:5} {подробно}")

    if а.json:
        п = Path(а.json)
        п.parent.mkdir(parents=True, exist_ok=True)
        п.write_text(json.dumps(отчёты, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\nотчёт: {п}")
    print(f"\nвитрин: {len(отчёты)}, отказов: {отказов}")
    print("доставку писем эта проверка не подтверждает: mailto не отвечает кодом доставки")
    return 1 if отказов else 0


if __name__ == "__main__":
    raise SystemExit(главная())
