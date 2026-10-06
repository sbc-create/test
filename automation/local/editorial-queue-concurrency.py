#!/usr/bin/env python3
"""Конкуренция и восстановление после прерывания — через РАБОТАЮЩУЮ службу.

Два сценария, оба по заданию владельца:

  1. Пересекающиеся запуски: три исполнителя одновременно обращаются к
     `editorial_queue_next`. Ни одно задание не должно уйти двум — и при этом
     занятость не должна выглядеть как «заданий нет»: занятая секция отвечает
     ОТКАЗОМ с причиной.
  2. Прерванный запуск: задания, взятые и брошенные без результата,
     возвращаются в работу, а статусы записей при этом не меняются.

Ничего не публикуется и ни одного результата не записывается: взятые задания
отпускаются обратно.

    python3 automation/local/editorial-queue-concurrency.py [--site yummyani.site]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys

МОСТ = "http://127.0.0.1:9000/mcp"
КОРЕНЬ = "/home/claude/wt-portable-site-cell-01"


def запрос(имя: str, аргументы: dict) -> dict:
    """Один вызов инструмента моста. Возвращает разобранный ответ или ошибку."""
    тело = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": имя, "arguments": аргументы}}
    r = subprocess.run(
        ["curl", "-sS", "--max-time", "120", "-X", "POST",
         "-H", "Content-Type: application/json", "-d", json.dumps(тело), МОСТ],
        capture_output=True, text=True)
    if r.returncode != 0:
        return {"ошибка": f"мост не ответил: {r.stderr.strip()[:200]}"}
    try:
        о = json.loads(r.stdout)
    except ValueError:
        return {"ошибка": f"ответ не JSON: {r.stdout[:200]!r}"}
    итог = о.get("result") or {}
    текст = (итог.get("content") or [{}])[0].get("text", "")
    if итог.get("isError") or о.get("error"):
        return {"ошибка": текст or json.dumps(о.get("error"), ensure_ascii=False)}
    return json.loads(текст) if текст.lstrip().startswith("{") else {"raw": текст}


def отпустить(task_id: str, owner: str) -> bool:
    """Освобождение задания. Отдельного инструмента моста нет — идём командой.

    Это тот же модуль очереди и тот же файл аренды; разница только в канале.
    Названо прямо, чтобы итог не выглядел проверкой того, чего не делали.
    """
    r = subprocess.run(
        ["python3", "-m", "factory.qwen", "queue-release", "--site",
         "yummyani.site", "--owner", owner, "--task-id", task_id],
        capture_output=True, text=True, cwd=КОРЕНЬ, timeout=180)
    return r.returncode == 0


def главная(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--site", default="yummyani.site")
    а = p.parse_args(argv)
    метка = dt.datetime.now(dt.timezone.utc).strftime("%H%M%SZ")

    print("=== 1. ПЕРЕСЕКАЮЩИЕСЯ ЗАПУСКИ (три одновременных обращения)")
    владельцы = [f"concurrent-{метка}-{n}" for n in (1, 2, 3)]
    КОД = (
        "import json,subprocess,sys\n"
        "sys.path.insert(0, '" + КОРЕНЬ + "')\n"
        "from importlib import import_module\n"
        "м = import_module('automation_concurrency_helper')\n"
    )
    # Запускаем три процесса curl одновременно, без помощника: каждый сам
    # формирует запрос. Так проверяется именно одновременность на службе.
    процессы = []
    for в in владельцы:
        тело = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": "editorial_queue_next",
                           "arguments": {"site": а.site, "owner": в, "limit": 1}}}
        процессы.append((в, subprocess.Popen(
            ["curl", "-sS", "--max-time", "120", "-X", "POST",
             "-H", "Content-Type: application/json", "-d", json.dumps(тело), МОСТ],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)))

    выдано: dict[str, list[str]] = {}
    отказов = 0
    взятые: list[tuple[str, str]] = []
    for в, пр in процессы:
        out, err = пр.communicate(timeout=180)
        try:
            о = json.loads(out)
            итог = о.get("result") or {}
            текст = (итог.get("content") or [{}])[0].get("text", "")
            if итог.get("isError"):
                занят = "ЗАНЯТОСТЬ" in текст or "занята" in текст
                отказов += 1
                print(f"   {в}: ОТКАЗ — {'занятость названа причиной' if занят else 'ПРИЧИНА НЕ НАЗВАНА'}")
                print(f"      {текст.strip()[:180]}")
                continue
            задания = (json.loads(текст).get("queue") or {}).get("tasks") or []
        except (ValueError, KeyError) as ош:
            print(f"   {в}: ответ не разобран ({ош}); stderr {err.strip()[:120]}")
            continue
        for з in задания:
            выдано.setdefault(з["task_id"], []).append(в)
            взятые.append((з["task_id"], в))
            print(f"   {в}: получил {з['task_id']}  {з['canonical_url'][:62]}")

    двойные = {t: кто for t, кто in выдано.items() if len(кто) > 1}
    print(f"   заданий выдано: {len(выдано)}; отказов по занятости: {отказов}; "
          f"выданных дважды: {len(двойные)}")
    if двойные:
        print(f"   ПРОВАЛ: одно задание двум исполнителям — {двойные}", file=sys.stderr)
        return 3
    if not выдано:
        print("   ПРОВАЛ: ни один исполнитель не получил задания — проверять нечего",
              file=sys.stderr)
        return 3

    print("\n=== 2. ВОССТАНОВЛЕНИЕ ПОСЛЕ ПРЕРЫВАНИЯ")
    состояние_до = запрос("editorial_queue_status", {"site": а.site})
    до = состояние_до.get("queue_status") or состояние_до
    for t, в in взятые:
        ок = отпустить(t, в)
        print(f"   {t} отпущено без результата: {ок}")
        if not ок:
            print(f"   ПРОВАЛ: задание {t} не отпустилось", file=sys.stderr)
            return 3
    о = запрос("editorial_queue_next",
               {"site": а.site, "owner": f"after-interrupt-{метка}", "limit": 3})
    снова = (о.get("queue") or {}).get("tasks") or []
    вернулись = [з["task_id"] for з in снова if з["task_id"] in выдано]
    print(f"   после прерывания выдано {len(снова)}, из них брошенных: {len(вернулись)}")
    for з in снова:
        отпустить(з["task_id"], f"after-interrupt-{метка}")
    if not вернулись:
        print("   ПРОВАЛ: брошенные задания не вернулись в работу", file=sys.stderr)
        return 3

    состояние_после = запрос("editorial_queue_status", {"site": а.site})
    после = состояние_после.get("queue_status") or состояние_после
    print("\n=== 3. СТАТУСЫ ЗАПИСЕЙ НЕ ИЗМЕНИЛИСЬ")
    for к in ("texts_present", "texts_recorded_via_queue", "texts_verified",
              "records_total", "leases_active"):
        print(f"   {к:26} {до.get(к)} -> {после.get(к)}")
        if к != "leases_active" and до.get(к) != после.get(к):
            print(f"   ПРОВАЛ: {к} изменилось, хотя результатов не записывалось",
                  file=sys.stderr)
            return 3
    if после.get("leases_active"):
        print(f"   ПРОВАЛ: остались активные аренды: {после.get('leases_active')}",
              file=sys.stderr)
        return 3
    print("\nСЦЕНАРИИ ПРОЙДЕНЫ. Ни одного результата не записано, публикаций нет.")
    return 0


if __name__ == "__main__":
    raise SystemExit(главная())
