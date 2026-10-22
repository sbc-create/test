#!/usr/bin/env python3
"""Инструктаж исполнителя домена: три уровня знаний за один вызов.

Задание владельца: «При запуске исполнитель должен получать общие правила,
правила семейства и актуальный паспорт своего сайта» и «Само существование
файлов ещё не означает, что исполнитель ими пользуется».

Поэтому инструктаж — не ссылка на файлы, а ВЫВОД их содержимого, и он
ОТКАЗЫВАЕТ, если какого-то уровня нет: исполнитель, начавший работу без
правил семейства, опаснее исполнителя, который не начал.

    python3 automation/local/brief.py --domain yummyani.site
    python3 automation/local/brief.py --domain yummyani.site --short
    python3 automation/local/brief.py --list

Коды: 0 — все три уровня выданы; 1 — домен не активен; 2 — уровень отсутствует.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
СПИСОК = КОРЕНЬ / "config" / "active-domains.json"
СЕТЬ = КОРЕНЬ / "docs" / "knowledge" / "NETWORK.md"


def активные() -> dict[str, dict]:
    д = json.loads(СПИСОК.read_text(encoding="utf-8"))
    return {з["domain"]: з for з in д["domains"]}


def уровни(домен: str) -> dict[str, pathlib.Path]:
    """Пути трёх уровней для домена. Чистая функция от списка."""
    запись = активные()[домен]
    return {
        "сеть": СЕТЬ,
        "семейство": КОРЕНЬ / "docs" / "knowledge" / "family"
        / f"{запись['family']}.md",
        "паспорт": КОРЕНЬ / запись["passport"],
        "очередь": КОРЕНЬ / запись["queue"],
    }


def чего_нет(домен: str) -> list[str]:
    return [имя for имя, п in уровни(домен).items() if not п.is_file()]


def следующий_шаг(очередь: dict) -> str:
    """Первая задача, которая НЕ ждёт и не снята."""
    for з in очередь.get("tasks") or []:
        if з["state"] not in ("снято", "ожидание", "заблокировано"):
            return f"{з['id']}: {з['title']}"
    ждут = [з for з in (очередь.get("tasks") or [])
            if з["state"] in ("ожидание", "заблокировано")]
    if ждут:
        з = ждут[0]
        return (f"все задачи ждут; первая — {з['id']}:"
                f" {з.get('blocked_by') or 'причина не названа'}")
    return "очередь пуста"


def main(аргв: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--domain", default="")
    р.add_argument("--short", action="store_true",
                   help="только сводка: этап, следующий шаг, запреты")
    р.add_argument("--list", action="store_true",
                   help="какие домены активны и у кого какой этап")
    а = р.parse_args(аргв)

    если_все = активные()
    if а.list or not а.domain:
        for домен, з in если_все.items():
            очередь = json.loads((КОРЕНЬ / з["queue"]).read_text(
                encoding="utf-8"))
            нет = чего_нет(домен)
            print(f"{домен:24} {з['family']:9} этап {очередь['stage']}"
                  f" задач {len(очередь['tasks']):2}"
                  f" {'| НЕТ УРОВНЕЙ: ' + ','.join(нет) if нет else ''}")
        print(f"\nактивных домéнов: {len(если_все)}")
        return 0 if а.list else 1

    if а.domain not in если_все:
        ждут = json.loads(СПИСОК.read_text(encoding="utf-8"))
        ожидающие = {з["domain"] for з in ждут["awaiting_replacement"]}
        if а.domain in ожидающие:
            print(f"{а.domain}: домен ОЖИДАЕТ ЗАМЕНЫ — продвижение и"
                  f" миграции не запускаются без нового решения владельца",
                  file=sys.stderr)
        else:
            print(f"{а.domain}: не в списке активных домéнов"
                  f" ({СПИСОК.name})", file=sys.stderr)
        return 1

    нет = чего_нет(а.domain)
    if нет:
        print(f"{а.domain}: ОТСУТСТВУЮТ уровни знаний: {', '.join(нет)}."
              f" Работать без них нельзя — соберите паспорта"
              f" (`make-passports.py`) и очереди (`make-domain-queues.py`).",
              file=sys.stderr)
        return 2

    п = уровни(а.domain)
    очередь = json.loads(п["очередь"].read_text(encoding="utf-8"))
    print(f"=== ИНСТРУКТАЖ: {а.domain} ===")
    print(f"семейство {очередь['family']} | ячейка {очередь['site_id']}"
          f" | исполнитель {очередь['executor']}")
    print(f"этап {очередь['stage']}: {очередь['stage_reason']}")
    print(f"следующий шаг: {следующий_шаг(очередь)}")
    print(f"задач в очереди: {len(очередь['tasks'])}")
    if а.short:
        return 0
    for имя in ("сеть", "семейство", "паспорт"):
        print(f"\n{'=' * 70}\n=== УРОВЕНЬ: {имя} — {п[имя].relative_to(КОРЕНЬ)}"
              f"\n{'=' * 70}\n")
        print(п[имя].read_text(encoding="utf-8").rstrip())
    return 0


if __name__ == "__main__":
    sys.exit(main())
