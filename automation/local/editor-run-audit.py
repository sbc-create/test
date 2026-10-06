#!/usr/bin/env python3
"""Был ли запуск редактора и что он сделал. Только чтение двух журналов.

Зачем инструмент, а не рассуждение. «Автоматизация включена» и «запуск был» —
разные утверждения, и первое не доказывает второго: признак `is_active` живёт у
планировщика, а работа видна по следам. Следов ровно два, и оба на этой машине:

* журнал моста MCP (`site-factory-mcp.service`) — КАЖДЫЙ вызов инструмента со
  временем и исходом. Запуск редактора, который обработал задание, не может не
  вызвать `editorial_queue_next`;
* журнал очереди (`queue_events.jsonl`) — выдачи, результаты, возобновления и
  отмены с владельцем и заданием.

Что инструмент отвечает:

* были ли вызовы в названном окне и какие;
* попадает ли обращение на сетку расписания (`--grid 30` — каждые 30 минут);
* брал ли кто-нибудь задание и чем закончил;
* считается ли это ОБРАБОТАННЫМ заданием: выдача плюс результат по тому же
  заданию и владельцу.

Чего инструмент НЕ делает: не называет виновника. Планировщик живёт в среде
исполнителя, и отсюда видно только то, дошла ли работа до фабрики.

    python3 automation/local/editor-run-audit.py --since "2026-10-06 14:00:00" \\
        --until "2026-10-06 15:00:00" [--grid 30] [--tz-offset 3]
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import pathlib
import subprocess
import sys

#: `dt.UTC` появился в 3.11, а мост и этот инструмент работают на 3.10.
ЮТС = dt.timezone.utc

ЖУРНАЛ_ОЧЕРЕДИ = pathlib.Path("/var/lib/seo-content-operator/queue_events.jsonl")
ЮНИТ = "site-factory-mcp.service"
#: Инструменты, без которых обработка задания невозможна. Запуск, не вызвавший
#: ни одного из них, задания не обрабатывал — чем бы он себя ни называл.
ОЧЕРЕДЬ = ("editorial_queue_next", "editorial_queue_result")
ЗАКРЫВАЮЩИЕ = ("task_result", "task_released", "task_reopened",
               "task_result_annulled")


def _время(с: str) -> dt.datetime:
    return dt.datetime.strptime(с, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=ЮТС)


def вызовы(since: str, until: str) -> list[dict]:
    """Вызовы инструментов из журнала моста. Пусто — значит пусто."""
    г = subprocess.run(
        ["journalctl", "-u", ЮНИТ, "--since", since, "--until", until,
         "--no-pager", "-o", "cat"],
        capture_output=True, text=True)
    если: list[dict] = []
    for с in (г.stdout or "").splitlines():
        с = с.strip()
        if not с.startswith("{"):
            continue
        try:
            з = json.loads(с)
        except ValueError:
            continue
        if з.get("outcome") == "started":
            continue
        if not з.get("at") or not з.get("tool"):
            # Строка журнала не про вызов инструмента (мост пишет сюда и
            # собственные сообщения). Пропускается молча: это не отказ.
            continue
        если.append(з)
    if г.returncode != 0 and not если:
        print(f"журнал моста не прочитан: {(г.stderr or '').strip()[:200]}",
              file=sys.stderr)
    return если


def события_очереди(с: dt.datetime, до: dt.datetime) -> list[dict]:
    if not ЖУРНАЛ_ОЧЕРЕДИ.is_file():
        print(f"нет {ЖУРНАЛ_ОЧЕРЕДИ}", file=sys.stderr)
        return []
    итог = []
    for строка in ЖУРНАЛ_ОЧЕРЕДИ.read_text(encoding="utf-8").splitlines():
        строка = строка.strip()
        if not строка:
            continue
        try:
            е = json.loads(строка)
        except ValueError:
            continue
        try:
            когда = _время(str(е.get("at")))
        except ValueError:
            continue
        if с <= когда <= до:
            итог.append(е)
    return итог


def главная(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--since", required=True, help="начало окна, UTC")
    p.add_argument("--until", required=True, help="конец окна, UTC")
    p.add_argument("--grid", type=int, default=30,
                   help="период расписания в минутах для проверки сетки")
    p.add_argument("--tz-offset", type=int, default=3,
                   help="сдвиг часов для показа местного времени (МСК = 3)")
    p.add_argument("--gap", type=int, default=180,
                   help="разрыв в секундах, который считается новым обращением")
    args = p.parse_args(argv)

    с = dt.datetime.fromisoformat(args.since).replace(tzinfo=ЮТС)
    до = dt.datetime.fromisoformat(args.until).replace(tzinfo=ЮТС)
    сдвиг = dt.timedelta(hours=args.tz_offset)

    в = вызовы(args.since, args.until)
    е = события_очереди(с, до)
    print(f"окно {args.since}Z — {args.until}Z "
          f"(местное {(с+сдвиг).strftime('%H:%M')}—{(до+сдвиг).strftime('%H:%M')})")
    print(f"вызовов инструментов: {len(в)}; событий очереди: {len(е)}")

    if not в:
        print("\nВЫЗОВОВ НЕТ. Работа до фабрики не дошла: запуск, обработавший "
              "задание, обязан вызвать editorial_queue_next.")
    else:
        # Обращения: подряд идущие вызовы с разрывом не больше --gap.
        обращения: list[list[dict]] = []
        for з in sorted(в, key=lambda x: x["at"]):
            if обращения and (_время(з["at"])
                              - _время(обращения[-1][-1]["at"])).total_seconds() <= args.gap:
                обращения[-1].append(з)
            else:
                обращения.append([з])
        print(f"\nобращений (разрыв > {args.gap} с считается новым): {len(обращения)}")
        for о in обращения:
            нач = _время(о[0]["at"])
            м = нач.minute + нач.second / 60
            отступ = min(abs(м - x) for x in (0, args.grid, 60))
            инструменты = collections.Counter(з.get("tool") for з in о)
            очередные = sum(n for и, n in инструменты.items() if и in ОЧЕРЕДЬ)
            print(f"   {нач.strftime('%H:%M:%S')}Z "
                  f"(местное {(нач+сдвиг).strftime('%H:%M:%S')}) "
                  f"вызовов {len(о):3}, к сетке {отступ:4.1f} мин"
                  f"{' <= 2 мин' if отступ <= 2 else '':9}"
                  f" очередь: {очередные}")
            print(f"      {dict(инструменты)}")

    выдачи = [x for x in е if x.get("event") == "task_claimed"]
    закрытия = [x for x in е if x.get("event") in ЗАКРЫВАЮЩИЕ]
    print(f"\nвыдач заданий в окне: {len(выдачи)}; закрытий: {len(закрытия)}")
    for x in выдачи:
        print(f"   выдано {x['at']} {x.get('task_id')} владельцу "
              f"{x.get('owner')!r} ({x.get('work_id')})")
    for x in закрытия:
        print(f"   закрыто {x['at']} {x.get('task_id')} {x.get('event')} "
              f"{x.get('outcome') or ''} владелец {x.get('owner')!r}")

    # ОБРАБОТАННОЕ задание: выдача и результат по тому же заданию и владельцу.
    обработано = []
    for в_ in выдачи:
        for з_ in закрытия:
            if (з_.get("event") == "task_result"
                    and з_.get("task_id") == в_.get("task_id")
                    and з_.get("owner") == в_.get("owner")
                    and _время(з_["at"]) >= _время(в_["at"])):
                обработано.append((в_, з_))
                break
    print(f"\nОБРАБОТАННЫХ заданий в окне (выдача + результат того же "
          f"владельца): {len(обработано)}")
    for в_, з_ in обработано:
        секунд = int((_время(з_["at"]) - _время(в_["at"])).total_seconds())
        print(f"   {в_.get('task_id')} владелец {в_.get('owner')!r}: "
              f"{в_['at']} -> {з_['at']} ({секунд} с), исход {з_.get('outcome')}")
    if not обработано:
        print("   нет: ни одно задание в этом окне не прошло путь "
              "«выдано -> результат».")
    return 0


if __name__ == "__main__":
    raise SystemExit(главная())
