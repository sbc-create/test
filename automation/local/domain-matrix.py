#!/usr/bin/env python3
"""Матрица: домен → site_id → семейство → репозиторий → живой build → исход.

Повод. Отчёты ночного цикла требуют таблицу по доменам, и собирать её руками
означает переписывать цифры из сообщений. Здесь каждый столбец берётся из
своего источника, и ни один не выводится из другого:

* домен, site_id, семейство, репозиторий и статус — реестр ячеек
  `config/site-cells.json`;
* живой build — заголовок `x-site-factory-build-id` самой витрины;
* последний УДАЧНЫЙ выпуск и его время — журнал исполнителя
  `/var/lib/site-cells/results/*-code-*.json`;
* режим индексации — `meta robots` и `X-Robots-Tag` живой главной.

Числа из прежних отчётов (12 витрин, 23 записи реестра) здесь не
воспроизводятся: состав считается заново при каждом запуске, потому что
историческое число легко принять за сегодняшнее.

Только чтение: ни одного запроса, меняющего состояние.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[1].parent
РЕЕСТР = КОРЕНЬ / "config" / "site-cells.json"
РЕЗУЛЬТАТЫ = Path("/var/lib/site-cells/results")

#: Имена из RFC 6761: публично не разрешаются, и молчание — свойство имени.
ИСПЫТАТЕЛЬНЫЕ = (".localhost", ".test", ".invalid", ".example")


def ячейки() -> list[dict]:
    try:
        документ = json.loads(РЕЕСТР.read_text(encoding="utf-8"))
    except (OSError, ValueError) as сбой:
        print(f"реестр ячеек не прочитан: {сбой}", file=sys.stderr)
        return []
    return документ.get("cells") or []


def живое(домен: str, таймаут: int = 20) -> tuple[str, str, str]:
    """(build, режим индексации, код). Пустой build — витрина не ответила.

    Заголовки пишутся в ОТДЕЛЬНЫЙ файл, а не в тот же поток. Первая редакция
    брала `curl -D -` и делила вывод по `\\r\\n\\r\\n` — и делила неверно:
    `text=True` переводит переводы строк, разделитель исчезает, тело выходит
    пустым ВСЕГДА. Режим индексации при этом читался только из заголовка
    `X-Robots-Tag`, а мету в теле проверка не видела ни разу: у Lords и Zona
    заголовок есть, и столбец выглядел осмысленным, а у пяти Yummy заголовка
    нет — там стоял «—», хотя мета говорит `index, follow`. Пустое значение
    выглядело как «режим не задан», то есть ошибка инструмента читалась как
    факт о витрине.
    """
    with tempfile.NamedTemporaryFile("w+", encoding="utf-8",
                                     delete=False) as ф:
        файл_заголовков = Path(ф.name)
    try:
        итог = subprocess.run(
            ["curl", "-sS", "-D", str(файл_заголовков), "--max-time",
             str(таймаут), f"https://{домен}/"],
            capture_output=True, text=True)
        if итог.returncode:
            return "", "", f"curl {итог.returncode}"
        заголовки = файл_заголовков.read_text(encoding="utf-8",
                                              errors="replace")
        тело = итог.stdout
    finally:
        файл_заголовков.unlink(missing_ok=True)
    код = ""
    build = ""
    хедер_робота = ""
    for строка in заголовки.splitlines():
        низ = строка.lower()
        if низ.startswith("http/"):
            части = строка.split()
            код = части[1] if len(части) > 1 else ""
        elif низ.startswith("x-site-factory-build-id:"):
            build = строка.split(":", 1)[1].strip()
        elif низ.startswith("x-robots-tag:"):
            хедер_робота = строка.split(":", 1)[1].strip()
    мета = re.search(r'<meta[^>]+name="robots"[^>]+content="([^"]*)"', тело)
    из_меты = мета.group(1).strip() if мета else ""
    # Источники называются раздельно: расхождение меты и заголовка — повод
    # разбираться, а склейка в одно значение его бы спрятала. Так уже было у
    # /healthz витрин на общем ядре (решение D166): приложение отдавало
    # index, follow, а nginx — noindex, и ответ противоречил сам себе.
    if из_меты and хедер_робота and из_меты.lower() != хедер_робота.lower():
        режим = f"мета {из_меты} ≠ заголовок {хедер_робота}"
    elif из_меты:
        режим = из_меты
    elif хедер_робота:
        режим = f"только заголовок: {хедер_робота}"
    elif тело:
        режим = "тега нет"
    else:
        режим = "не прочитано"
    return build, режим, код


def последний_удачный(site_id: str) -> tuple[str, str]:
    записи = []
    for ф in sorted(РЕЗУЛЬТАТЫ.glob(f"{site_id}-code-*.json")):
        try:
            д = json.loads(ф.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if д.get("status") != "ok":
            continue
        записи.append((str(д.get("finished_at") or ""), д))
    if not записи:
        return "", ""
    когда, д = max(записи, key=lambda п: п[0])
    return (д.get("commit") or "")[:12], когда[:19].replace("T", " ") + "Z"


def главное(аргв: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--json", action="store_true")
    р.add_argument("--only-live", action="store_true",
                   help="только отвечающие витрины")
    а = р.parse_args(аргв)

    строки = []
    for я in ячейки():
        домен = str(я.get("domain") or "")
        сайт = str(я.get("site_id") or "")
        if not домен or not сайт:
            continue
        репо = (я.get("repo") or {}).get("remote") or ""
        семейство = ((я.get("template") or {}).get("family")
                     or (я.get("template") or {}).get("template_id") or "—")
        если_испытательное = домен.endswith(ИСПЫТАТЕЛЬНЫЕ)
        if если_испытательное:
            build, режим, код = "", "—", "RFC 6761"
        else:
            build, режим, код = живое(домен)
        коммит, когда = последний_удачный(сайт)
        строки.append({
            "домен": домен, "site_id": сайт, "семейство": семейство,
            "статус_реестра": str(я.get("status") or ""),
            "репозиторий": репо.replace("https://github.com/", ""),
            "живой_build": build, "режим": режим, "код": код,
            "последний_выпуск": коммит, "когда": когда,
            "build_совпал": bool(build) and bool(коммит)
                            and build.startswith(коммит),
        })

    if а.only_live:
        строки = [с for с in строки if с["живой_build"]]
    if а.json:
        print(json.dumps(строки, ensure_ascii=False, indent=1))
        return 0

    print(f"{'домен':24} {'site_id':14} {'семейство':10} {'живой build':30} "
          f"{'режим':16} выпуск")
    for с in строки:
        отметка = "" if с["build_совпал"] or not с["живой_build"] else " ≠"
        print(f"{с['домен']:24} {с['site_id']:14} {с['семейство']:10} "
              f"{(с['живой_build'] or с['код'] or '—'):30} "
              f"{с['режим'][:16]:16} {с['последний_выпуск'] or '—'}{отметка}")
    живых = [с for с in строки if с["живой_build"]]
    расхождений = [с for с in живых if not с["build_совпал"]]
    print(f"\nячеек в реестре: {len(строки)}; отвечают: {len(живых)}; "
          f"build не совпал с журналом: {len(расхождений)}")
    return 1 if расхождений else 0


if __name__ == "__main__":
    sys.exit(главное())
