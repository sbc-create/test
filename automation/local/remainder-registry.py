#!/usr/bin/env python3
"""Единый реестр остатка по сети: что принято, что готово, что заблокировано.

Сводит в одну таблицу то, что иначе приходится собирать из пяти мест: реестр
ячеек, рабочие копии репозиториев, выложенные релизы, состояние доставки данных
и публичный ответ домена. Ничего не меняет.

Разделение домена по категориям выводится из ИЗМЕРЕНИЙ, а не из отчётов:

* `принято`     — публичная сборка совпадает с головой рабочей копии;
* `готово`      — голова впереди выложенного, CI зелёный, удержания нет;
* `удержано`    — выпуск ведёт другое окно (запись `release.hold` в реестре);
* `внешний`     — домен не отвечает и выпуска нет (serverHold и подобное);
* `сверки нет`  — витрина не объявляет сборку в разметке: установлено или нет,
  этим способом не определяется;
* `тестовый`    — площадка без публичного домена.

Запуск: python3 automation/local/remainder-registry.py [--json]
"""
from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys
import urllib.error
import urllib.request

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ЗАГОЛОВКИ = {"User-Agent": "site-factory-remainder/1.0"}
ТАЙМАУТ = 25


def ячейки() -> list[dict]:
    д = json.loads((КОРЕНЬ / "config" / "site-cells.json").read_text(encoding="utf-8"))
    return д.get("cells") or []


def голова(репо: str) -> tuple[str, str]:
    путь = КОРЕНЬ / репо
    if not (путь / ".git").exists():
        return "", ""
    def ск(*арг: str) -> str:
        return subprocess.run(["git", *арг], cwd=путь, capture_output=True,
                              text=True).stdout.strip()
    return ск("rev-parse", "--short=12", "HEAD"), ск("rev-parse", "--abbrev-ref", "HEAD")


def публичное(домен: str) -> dict:
    try:
        with urllib.request.urlopen(
                urllib.request.Request(f"https://{домен}/", headers=ЗАГОЛОВКИ),
                timeout=ТАЙМАУТ) as о:
            html = о.read().decode("utf-8", "replace")
            код: object = о.status
            робот = о.headers.get("X-Robots-Tag") or ""
    except urllib.error.HTTPError as ош:
        return {"код": ош.code, "build": "", "robots": ""}
    except (urllib.error.URLError, OSError, ValueError) as ош:
        return {"код": f"нет ответа ({type(ош).__name__})", "build": "", "robots": ""}
    сборка = re.search(r'data-build-id="([^"]+)"', html)
    мета = re.search(
        r'<meta[^>]+name=["\']robots["\'][^>]+content=["\']([^"\']*)["\']', html, re.I)
    return {"код": код, "build": сборка.group(1) if сборка else "",
            "robots": робот or (мета.group(1) if мета else "")}


#: Ячейки, живущие ЗАИМСТВОВАННЫМ снимком семейства: производитель не выпускает
#: снимок под их идентификатором, и сравнивать с `<site_id>-catalog.json` нельзя —
#: такого файла нет и быть не должно. Имя источника объявлено здесь явно, иначе
#: отсутствие файла читалось бы как остановка доставки.
ЗАИМСТВОВАННЫЙ_ИСТОЧНИК = {
    "animego-02": "animedia-02", "animego-03": "animedia-02",
    "animego-04": "animedia-02",
}


def данные(c: dict) -> str:
    """Свежесть каталога в ячейке против источника издателя."""
    runtime = c.get("runtime") or {}
    кат = runtime.get("data_dir")
    sid = c.get("site_id") or ""
    if not кат:
        return "каталог данных не объявлен"
    цель = pathlib.Path(кат) / f"{sid}-catalog.json"
    имя_источника = ЗАИМСТВОВАННЫЙ_ИСТОЧНИК.get(sid, sid)
    источник = pathlib.Path("/srv/lords/.frontend") / f"{имя_источника}-catalog.json"
    if not цель.is_file():
        return "каталога нет"
    def позиций(п: pathlib.Path) -> int | None:
        try:
            return len(json.loads(п.read_text(encoding="utf-8")).get("items") or [])
        except (OSError, ValueError):
            return None
    в_ячейке = позиций(цель)
    у_источника = позиций(источник) if источник.is_file() else None
    if у_источника is None:
        return f"в ячейке {в_ячейке}, источника нет"
    пометка = ("" if имя_источника == sid
               else f" (источник {имя_источника})")
    if в_ячейке == у_источника:
        return f"совпадает ({в_ячейке}){пометка}"
    return f"РАСХОЖДЕНИЕ: в ячейке {в_ячейке}, у источника {у_источника}"


def объявленная_сборка(репо: str) -> str:
    """`build_id` из манифеста рабочей копии.

    Нужна для раскладки `app`: у таких ячеек `build_id` — строка манифеста, а
    не коммит, и штамп считается по файлу рантайма (`src/*-frontend.py`).
    Правка в `automation/` его не меняет, поэтому сравнение «голова против
    build_id» объявляло бы такую ячейку неустановленной навсегда. Измерено
    2026-10-08 на an1mego.site и animeg0.site: установка владельцем прошла,
    отпечаток файла совпал с коммитом, а `build_id` остался прежним — и это
    ожидаемо.
    """
    п = КОРЕНЬ / репо / "config" / "template-manifest.json"
    if not п.is_file():
        return ""
    try:
        return str(json.loads(п.read_text(encoding="utf-8")).get("build_id") or "")
    except (OSError, ValueError):
        return ""


def категория(c: dict, гол: str, публ: dict, объявлено: str = "") -> str:
    выпуск = c.get("release") or {}
    домен = c.get("domain") or ""
    if домен.endswith(".localhost") or домен.endswith(".localhost.test"):
        return "тестовый"
    if not isinstance(публ.get("код"), int):
        return "внешний"
    if выпуск.get("hold"):
        return "удержано"
    живой = публ.get("build") or ""
    # Витрина может не объявлять сборку в разметке (приложение Yummy её не
    # печатает). Тогда СВЕРКИ НЕТ, и называть это «готово к выкладке» нельзя:
    # неизвестно, установлено или нет. Категория говорит именно это.
    if not живой:
        return "сверки нет"
    # Раскладка с выпусками: build_id начинается с коммита.
    if гол and (живой.startswith(гол[:12]) or гол[:12] in живой):
        return "принято"
    # Раскладка app: сверяется объявленный манифестом build_id.
    if объявлено and живой == объявлено:
        return "принято"
    return "готово" if гол else "принято"


def собрать() -> list[dict]:
    строки = []
    for c in ячейки():
        репо = ((c.get("repo") or {}).get("path")
                if isinstance(c.get("repo"), dict) else c.get("repo")) or ""
        гол, ветка = голова(репо) if репо else ("", "")
        публ = публичное(c.get("domain") or "")
        объявлено = объявленная_сборка(репо) if репо else ""
        строки.append({
            "домен": c.get("domain"), "site_id": c.get("site_id"),
            "ветка": ветка, "голова": гол,
            "публичная_сборка": публ["build"], "код": публ["код"],
            "индексация": публ["robots"],
            "данные": данные(c),
            "удержание": ((c.get("release") or {}).get("hold_reason") or "")[:90]
                         if (c.get("release") or {}).get("hold") else "",
            "объявлено_манифестом": объявлено,
            "категория": категория(c, гол, публ, объявлено),
        })
    return строки


def main() -> int:
    строки = собрать()
    if "--json" in sys.argv:
        print(json.dumps(строки, ensure_ascii=False, indent=1))
        return 0
    шапка = (f"{'домен':24} {'site_id':14} {'кат.':9} {'код':6} "
             f"{'публичная сборка':26} {'данные':28} индексация")
    print(шапка)
    print("-" * len(шапка))
    for с in строки:
        print(f"{(с['домен'] or '—')[:23]:24} {(с['site_id'] or '—')[:13]:14} "
              f"{с['категория']:9} {str(с['код'])[:5]:6} "
              f"{(с['публичная_сборка'] or '—')[:25]:26} {с['данные'][:27]:28} "
              f"{(с['индексация'] or '—')[:22]}")
    счёт: dict[str, int] = {}
    for с in строки:
        счёт[с["категория"]] = счёт.get(с["категория"], 0) + 1
    print("\nпо категориям:", json.dumps(счёт, ensure_ascii=False))
    for с in строки:
        if с["удержание"]:
            print(f"   удержано {с['домен']}: {с['удержание']}")
        if с["данные"].startswith("РАСХОЖДЕНИЕ"):
            print(f"   данные {с['домен']}: {с['данные']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
