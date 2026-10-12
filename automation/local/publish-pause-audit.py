#!/usr/bin/env python3
"""Соблюдается ли пауза публикаций: по журналу очереди, а не по слову «держим».

Повод. Пауза на семи Lords/Zona объявлена до установки защиты редакционных
полей, и проверять её надо записями. Вопрос повторяющийся — значит ему нужен
инструмент, а не разовая проба.

Ловушка, в которую я попал сам и из-за которой инструмент и появился: событие
`task_result` адреса НЕ СОДЕРЖИТ. Его поля — `at, attempts, event, gate,
next_attempt_at, outcome, owner, queue_status, status_after, status_before,
task_id, work_id`. Первая проба спрашивала адрес у него, все успехи попадали в
корзину «адрес не указан», а счётчик считал эту корзину распознанной и печатал
«нарушений паузы 0». То есть незнание выдавалось за доказательство.

Адрес живёт в других событиях, и они же дают соответствие:

* `task_claimed`, `task_registered`, `task_reopened`, `task_published` несут
  `canonical_url`, а первые два ещё и `site`;
* по `task_id` строится соответствие задание → домен по ВСЕЙ истории журнала:
  задание могли выдать раньше окна, а закрыть внутри него.

Поэтому ноль нарушений при нуле распознанных заданий — это отдельный исход
(код 2), а не зелёный результат.

Только чтение журнала.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

ЖУРНАЛ = Path("/var/lib/seo-content-operator/queue_events.jsonl")
#: Исходы, означающие доведённую работу редактора.
УСПЕХ = ("TEXT_WRITTEN", "NO_CHANGE_NEEDED")
#: События, из которых можно узнать адрес задания.
С_АДРЕСОМ = ("task_claimed", "task_registered", "task_reopened",
             "task_published", "task_register_existing",
             "task_result_annulled")


def _домен(значение: str) -> str:
    return (значение or "").split("//")[-1].split("/")[0].lower()


def события(путь: Path) -> list[dict]:
    try:
        строки = путь.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as сбой:
        print(f"журнал очереди не прочитан ({путь}): {сбой}", file=sys.stderr)
        return []
    итог = []
    for строка in строки:
        строка = строка.strip()
        if строка.startswith("{"):
            try:
                итог.append(json.loads(строка))
            except ValueError:
                continue
    return итог


def адреса_заданий(записи: list[dict]) -> dict[str, str]:
    """task_id → домен, по всей истории журнала.

    Окно времени здесь НЕ применяется намеренно: задание могли выдать раньше
    окна, а закрыть внутри него, и тогда адрес нашёлся бы только в старом
    событии.
    """
    итог: dict[str, str] = {}
    for з in записи:
        ключ = з.get("task_id")
        if not ключ or итог.get(ключ):
            continue
        if з.get("event") not in С_АДРЕСОМ:
            continue
        домен = _домен(з.get("canonical_url") or "")
        if not домен and з.get("site"):
            домен = str(з["site"]).lower()
        if домен:
            итог[ключ] = домен
    return итог


def разобрать(записи: list[dict], пауза: set[str], часов: float) -> dict:
    адрес = адреса_заданий(записи)
    порог = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=часов)
    успехи: dict[str, int] = {}
    без_адреса = 0
    на_паузе: list[dict] = []
    for з in записи:
        try:
            когда = dt.datetime.strptime(з.get("at") or "",
                                         "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=dt.timezone.utc)
        except (ValueError, TypeError):
            continue
        if когда < порог or з.get("event") != "task_result":
            continue
        if (з.get("outcome") or "") not in УСПЕХ:
            continue
        домен = адрес.get(з.get("task_id") or "", "")
        if not домен:
            без_адреса += 1
            continue
        успехи[домен] = успехи.get(домен, 0) + 1
        if домен in пауза:
            на_паузе.append({"домен": домен, "task_id": з.get("task_id"),
                             "когда": з.get("at"),
                             "исход": з.get("outcome")})
    return {"успехи": успехи, "без_адреса": без_адреса, "на_паузе": на_паузе,
            "распознано": sum(успехи.values())}


def разбор(аргв=None):
    р = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--journal", type=Path, default=ЖУРНАЛ)
    р.add_argument("--paused", action="append", default=[],
                   help="домен на паузе (можно повторять)")
    р.add_argument("--hours", type=float, default=24.0)
    р.add_argument("--json", action="store_true")
    return р.parse_args(аргв)


def главное(аргв=None) -> int:
    опции = разбор(аргв)
    пауза = {д.lower() for д in опции.paused}
    записи = события(опции.journal)
    if not записи:
        return 2
    итог = разобрать(записи, пауза, опции.hours)

    if опции.json:
        print(json.dumps(итог, ensure_ascii=False, indent=2))
    else:
        print(f"успешные исходы за {опции.hours:g} ч по домену:")
        for домен, н in sorted(итог["успехи"].items(), key=lambda п: -п[1]):
            метка = "  ← ДОМЕН НА ПАУЗЕ" if домен in пауза else ""
            print(f"   {домен:26} {н}{метка}")
        print(f"   успехов без распознанного адреса: {итог['без_адреса']}")
        print(f"\nраспознано успехов: {итог['распознано']}; "
              f"из них на приостановленных домена: {len(итог['на_паузе'])}")
        for с in итог["на_паузе"][:20]:
            print(f"   {с['домен']:24} {с['исход']:18} {с['когда']} "
                  f"({с['task_id']})")
        if не_на_чем_судить(итог, пауза):
            print("\nВНИМАНИЕ: ни одному успеху не сопоставлен домен. Вывод "
                  "«нарушений нет» здесь НЕ доказательство, а признак того, "
                  "что соответствия task_id → адрес в журнале не нашлось: "
                  "событие task_result адреса не содержит.")
        if итог["на_паузе"]:
            print("\nУспех на приостановленном домене сам по себе ещё не "
                  "нарушение: смотреть надо дату и то, была ли публикация "
                  "доставлена. Разбирать по task_id в журнале.")

    if не_на_чем_судить(итог, пауза):
        return 2
    return 1 if итог["на_паузе"] else 0


def не_на_чем_судить(итог: dict, пауза: set[str]) -> bool:
    """Приостановленные домены названы, а распознанных успехов нет вовсе.

    Отдельной функцией затем, что это и есть проверяемый инвариант: ноль
    нарушений при нуле знания — не зелёный результат.
    """
    return bool(пауза) and итог["распознано"] == 0 and итог["без_адреса"] > 0


if __name__ == "__main__":
    raise SystemExit(главное())
