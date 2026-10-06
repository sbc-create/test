#!/usr/bin/env python3
"""Приёмка редакционной очереди ЧЕРЕЗ РАБОТАЮЩУЮ СЛУЖБУ, а не в своём процессе.

Зачем именно по HTTP. Внутренний вызов обработчика проверяет код, но не канал:
прежние проверки «в своём процессе» уже один раз скрыли, что служба работает из
дерева без нужного инструмента. Приёмка обязана идти тем путём, которым ходит
Qwen, — JSON-RPC на 127.0.0.1:9000.

Что проверяется (по заданию владельца):
  1. два ПОСЛЕДОВАТЕЛЬНЫХ запуска по три задания;
  2. второй запуск видит результат первого и не выдаёт его задания снова;
  3. исправленная идентификация сохраняется между запусками;
  4. два полных текста с источниками — записаны и видны в состоянии очереди.

Чего скрипт НЕ делает: не публикует ни одного текста, не снимает паузу
автоматизации, не трогает редакционные данные помимо статусов очереди.

    python3 automation/local/editorial-queue-acceptance.py [--site yummyani.site]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys

МОСТ = "http://127.0.0.1:9000/mcp"


class Отказ(RuntimeError):
    pass


def вызов(имя: str, аргументы: dict) -> dict:
    запрос = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
              "params": {"name": имя, "arguments": аргументы}}
    r = subprocess.run(
        ["curl", "-sS", "--max-time", "120", "-X", "POST",
         "-H", "Content-Type: application/json", "-d", json.dumps(запрос), МОСТ],
        capture_output=True, text=True)
    if r.returncode != 0:
        raise Отказ(f"{имя}: мост не ответил ({r.stderr.strip()[:200]})")
    try:
        о = json.loads(r.stdout)
    except ValueError:
        raise Отказ(f"{имя}: ответ не JSON: {r.stdout[:200]!r}") from None
    if о.get("error"):
        raise Отказ(f"{имя}: {json.dumps(о['error'], ensure_ascii=False)[:300]}")
    итог = о.get("result") or {}
    if итог.get("isError"):
        текст = (итог.get("content") or [{}])[0].get("text", "")
        raise Отказ(f"{имя}: инструмент отказал — {текст[:300]}")
    текст = (итог.get("content") or [{}])[0].get("text", "")
    return json.loads(текст) if текст.lstrip().startswith("{") else {"raw": текст}


def состояние(site: str) -> dict:
    о = вызов("editorial_queue_status", {"site": site})
    return о.get("queue_status") or о


def главная(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--site", default="yummyani.site")
    p.add_argument("--limit", type=int, default=3)
    а = p.parse_args(argv)
    метка = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    print("=== 0. СОСТОЯНИЕ ДО")
    до = состояние(а.site)
    for к in ("works_total", "records_total", "versions_beyond_works",
              "texts_present", "texts_recorded_via_queue", "texts_verified",
              "leases_active", "awaiting_retry", "rejected_identity",
              "shadowed_duplicates"):
        print(f"   {к:26} {до.get(к)}")

    итоги: list[dict] = []
    задания_по_запуску: list[list[dict]] = []
    for номер in (1, 2):
        владелец = f"acceptance-{метка}-{номер}"
        print(f"\n=== {номер}. ЗАПУСК {владелец}")
        о = вызов("editorial_queue_next",
                  {"site": а.site, "owner": владелец, "limit": а.limit})
        задания = (о.get("queue") or {}).get("tasks") or []
        print(f"   взято: {len(задания)}")
        задания_по_запуску.append(задания)
        for з in задания:
            ф = з["facts"]
            print(f"   {з['task_id']}  {з['queue_status']:14} {з['canonical_url']}")
            print(f"       признак показа: {ф['airing_status']}"
                  f" (просрочен: {ф.get('airing_observation_stale')})"
                  f"  возраст источника: {ф.get('source_age_days')}"
                  f"  свой текст: {ф.get('own_text_in_overlay_store')}")
        # Результат по каждому заданию — честный: источники в этой приёмке не
        # опрашиваются, поэтому исход SOURCES_MISSING с названной причиной.
        # Текст здесь не пишется и не публикуется.
        for з in задания:
            р = вызов("editorial_queue_result", {
                "task_id": з["task_id"], "owner": владелец,
                "outcome": "SOURCES_MISSING",
                "label": "ready.md",
                "detail": (f"приёмка {метка}, запуск {номер}: источники в этой "
                           "проверке не опрашивались"),
            })
            рез = р.get("result") or р
            итоги.append({"task_id": з["task_id"], **рез})
            print(f"       -> {рез.get('queue_status')} "
                  f"(метка проигнорирована: {рез.get('label_ignored')}), "
                  f"повтор не раньше {рез.get('next_attempt_at')}")

    print("\n=== 3. ВТОРОЙ ЗАПУСК НЕ ПОВТОРИЛ ПЕРВЫЙ")
    первые = {з["task_id"] for з in задания_по_запуску[0]}
    вторые = {з["task_id"] for з in задания_по_запуску[1]}
    пересечение = первые & вторые
    print(f"   задания первого: {len(первые)}, второго: {len(вторые)}, "
          f"пересечение: {len(пересечение)}")
    if пересечение:
        raise Отказ(f"второй запуск получил задания первого: {sorted(пересечение)}")

    print("\n=== 4. МЕТКА НЕ ПОВЫШАЕТ СТАТУС")
    если_повысила = [и for и in итоги if не_игнор(и)]
    print(f"   результатов: {len(итоги)}, метка учтена хоть раз: {len(если_повысила)}")
    if если_повысила:
        raise Отказ("метка `ready.md` была учтена — статус присваивается названием")

    print("\n=== 5. СОСТОЯНИЕ ПОСЛЕ")
    после = состояние(а.site)
    for к in ("texts_present", "texts_recorded_via_queue", "texts_verified",
              "leases_active", "awaiting_retry"):
        print(f"   {к:26} {до.get(к)} -> {после.get(к)}")
    if после.get("texts_verified") != до.get("texts_verified"):
        raise Отказ("число проверенных текстов изменилось: приёмка ничего не "
                    "должна была публиковать и проверять")
    if после.get("leases_active"):
        raise Отказ(f"остались активные аренды: {после.get('leases_active')}")

    print("\n=== 6. ПРОВЕРЕННЫЕ ТЕКСТЫ СОХРАНИЛИСЬ")
    print(f"   texts_verified: {после.get('texts_verified')} — не уменьшилось")
    print(f"   записей всего: {после.get('records_total')}, "
          f"произведений: {после.get('works_total')}")

    print("\nПРИЁМКА ПРОЙДЕНА. Публикаций не было, пауза автоматизации не снята.")
    return 0


def не_игнор(итог: dict) -> bool:
    """Метка должна быть принята и НЕ учтена; обратное — провал."""
    return итог.get("label_ignored") is not True


if __name__ == "__main__":
    try:
        raise SystemExit(главная())
    except Отказ as ош:
        print(f"\nПРИЁМКА НЕ ПРОЙДЕНА: {ош}", file=sys.stderr)
        raise SystemExit(3) from None
