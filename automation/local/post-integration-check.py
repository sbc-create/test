#!/usr/bin/env python3
"""Внедрены ли изменения в ДЕЙСТВУЮЩИЕ службы. Только чтение.

    python3 automation/local/post-integration-check.py

Зачем отдельная проверка. Зелёный прогон в рабочем дереве не означает, что
новый код исполняется: мост MCP загружает код при запуске и держит его в
памяти, исполнитель очереди работает КОРНЕВОЙ копией в /usr/local/lib, а
правка в рабочем каталоге сама ни туда, ни туда не попадает. Поэтому
внедрение подтверждается тремя независимыми измерениями:

* **мост** — набор инструментов и версия правил из его собственного ответа
  (`/healthz`), а не из кода репозитория;
* **исполнитель** — наличие и РАБОТА защитных функций в установленной копии:
  модуль импортируется из `/usr/local/lib/site-factory-cell`, замок берётся,
  устаревшее поколение отвергается;
* **права** — роль `qwen` по-прежнему не вправе решать и публиковать.

Код возврата: 0 — всё внедрено; 1 — что-то ещё нет; 2 — измерить нечем.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

МОСТ = "http://127.0.0.1:9000/healthz"
УСТАНОВКА = pathlib.Path("/usr/local/lib/site-factory-cell")
КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]

#: Чего ждём от обновлённого моста. Значения посчитаны тем же кодом, который
#: мост объявит у себя: `factory.qwen.mcp.отпечаток_инструментов()`.
ОЖИДАЕМЫЕ_ИНСТРУМЕНТЫ = {"count": 43, "fingerprint": "38af3933d4df1ac9", "writing": 22}
ОЖИДАЕМАЯ_ИНСТРУКЦИЯ = "2026-10-10.1"
НОВЫЕ_ИНСТРУМЕНТЫ = ("comment_draft", "submit_comment", "comment_drafts_pending",
                     "review_comment")


def _мост() -> dict:
    try:
        with urllib.request.urlopen(МОСТ, timeout=20) as о:
            return json.loads(о.read())
    except (urllib.error.URLError, OSError, ValueError) as ош:
        return {"error": f"{type(ош).__name__}: {ош}"}


def проверить_мост() -> tuple[bool, list[str]]:
    д = _мост()
    строки, ок = [], True
    if "error" in д:
        return False, [f"мост не ответил: {д['error']}"]
    инстр = д.get("tools") or {}
    код = (д.get("environment") or {}).get("code") or {}
    правила = (д.get("environment") or {}).get("instruction") or {}
    строки.append(f"   код службы: ветка {код.get('branch')} коммит {код.get('commit')} "
                  f"dirty={код.get('dirty')} запущен {код.get('process_started_at')}")
    строки.append(f"   инструменты: count={инстр.get('count')} "
                  f"fingerprint={инстр.get('fingerprint')} writing={инстр.get('writing')}")
    строки.append(f"   правила: {правила.get('version')}")
    for поле, ждём in ОЖИДАЕМЫЕ_ИНСТРУМЕНТЫ.items():
        если = инстр.get(поле)
        if если != ждём:
            ок = False
            строки.append(f"   [нет] {поле}: {если}, ожидалось {ждём}")
    if правила.get("version") != ОЖИДАЕМАЯ_ИНСТРУКЦИЯ:
        ок = False
        строки.append(f"   [нет] версия правил {правила.get('version')}, "
                      f"ожидалась {ОЖИДАЕМАЯ_ИНСТРУКЦИЯ}")
    return ок, строки


def проверить_перечень_инструментов() -> tuple[bool, list[str]]:
    """Инструменты объявлены в `tools/list`, а не только посчитаны."""
    запрос = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
    r = urllib.request.Request("http://127.0.0.1:9000/mcp",
                               data=json.dumps(запрос).encode("utf-8"),
                               headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=20) as о:
            д = json.loads(о.read())
    except (urllib.error.URLError, OSError, ValueError) as ош:
        return False, [f"   tools/list не ответил: {type(ош).__name__}: {ош}"]
    имена = {и["name"] for и in ((д.get("result") or {}).get("tools") or [])}
    нет = [и for и in НОВЫЕ_ИНСТРУМЕНТЫ if и not in имена]
    строки = [f"   объявлено инструментов: {len(имена)}"]
    for и in НОВЫЕ_ИНСТРУМЕНТЫ:
        строки.append(f"   {'есть' if и in имена else '[нет]'} {и}")
    return (not нет), строки


def проверить_исполнителя() -> tuple[bool, list[str]]:
    """Защита доставки в УСТАНОВЛЕННОЙ копии: не только есть, но и работает."""
    строки, ок = [], True
    цель = УСТАНОВКА / "factory" / "cell" / "privileged.py"
    if not цель.is_file():
        return False, [f"   установленной копии нет: {цель}"]
    текст = цель.read_text(encoding="utf-8", errors="replace")
    for имя in ("замок_издателя", "снимок_не_старее", "ЗАМОК_ИЗДАТЕЛЯ"):
        если = имя in текст
        строки.append(f"   {'есть' if если else '[нет]'} {имя} в установленной копии")
        ок = ок and если
    исп = (УСТАНОВКА / "factory" / "cell" / "executor.py").read_text(
        encoding="utf-8", errors="replace")
    под_замком = "замок_издателя" in исп
    строки.append(f"   {'есть' if под_замком else '[нет]'} доставка идёт под замком "
                  "(executor.обновить_данные)")
    ок = ок and под_замком
    if not ок:
        return False, строки
    # Работа, а не наличие строки: отдельный процесс с корнем установленной
    # копии на `sys.path` — иначе импортировался бы код рабочего дерева.
    сценарий = """
import fcntl, json, pathlib, sys, tempfile
sys.path.insert(0, sys.argv[1])
from factory.cell import privileged as p
итог = {}
врем = pathlib.Path(tempfile.mkdtemp())
p.ЗАМОК_ИЗДАТЕЛЯ = врем / "lock"
with p.замок_издателя() as с:
    итог["замок берётся"] = bool(с.get("held"))
чужой = open(p.ЗАМОК_ИЗДАТЕЛЯ, "a+")
fcntl.flock(чужой, fcntl.LOCK_EX | fcntl.LOCK_NB)
try:
    try:
        with p.замок_издателя():
            итог["занятый замок останавливает"] = False
    except p.PrivilegedRefused:
        итог["занятый замок останавливает"] = True
finally:
    fcntl.flock(чужой, fcntl.LOCK_UN); чужой.close()
ист, цел = врем / "front", врем / "cell"
for к, рев, когда in ((ист, "старое", "2026-10-08T03:15:24Z"),
                      (цел, "новое", "2026-10-10T11:46:13Z")):
    к.mkdir(parents=True, exist_ok=True)
    (к / "zona-02-catalog.json").write_text(json.dumps(
        {"builtAt": когда, "count": 400,
         "items": [{"slug": f"z-{i}", "title": "Тайтл " * 12} for i in range(400)],
         "revision": рев, "schema": "nova-catalog/2.0.0", "site": "zona-02"},
        ensure_ascii=False), encoding="utf-8")
итог["устаревшее поколение отвергается"] = (
    p.снимок_не_старее(ист, цел, "zona-02")["verdict"] == "источник старее")
итог["свежее поколение проходит"] = (
    p.снимок_не_старее(цел, ист, "zona-02")["verdict"] == "не старее")
print(json.dumps(итог, ensure_ascii=False))
"""
    r = subprocess.run([sys.executable, "-c", сценарий, str(УСТАНОВКА)],
                       capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        return False, строки + [f"   проверка работы не прошла: {r.stderr.strip()[-300:]}"]
    измерено = json.loads(r.stdout.strip().splitlines()[-1])
    for имя, значение in измерено.items():
        строки.append(f"   {'да' if значение else '[нет]'} {имя}")
        ок = ок and bool(значение)
    return ок, строки


def проверить_права() -> tuple[bool, list[str]]:
    """Разделение прав в коде ДЕЙСТВУЮЩЕЙ службы, а не в своём дереве.

    Читать свой репозиторий здесь нельзя: он и так зелёный, а вопрос ровно в
    том, что исполняет служба. Корень берётся из её же ответа
    (`environment.code.worktree`), модуль читается отдельным процессом с этим
    корнем на `sys.path` — иначе импортировался бы наш.
    """
    д = _мост()
    корень = ((д.get("environment") or {}).get("code") or {}).get("worktree") or ""
    if not корень:
        return False, ["   корень кода службы неизвестен: мост не ответил"]
    r = subprocess.run(
        [sys.executable, "-c",
         "import json, sys; sys.path.insert(0, sys.argv[1]);"
         "from factory.qwen import actors; print(json.dumps(actors.сведения()))",
         корень], capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        return False, [f"   код службы не читается: {r.stderr.strip()[-200:]}"]
    св = json.loads(r.stdout.strip().splitlines()[-1])
    разрешено = св["roles"].get("qwen") or []
    строки = [f"   корень кода службы: {корень}",
              f"   роль qwen: {разрешено}"]
    ок = True
    for надо in ("comment-prepare", "comment-submit"):
        если = надо in разрешено
        строки.append(f"   {'есть' if если else '[нет]'} {надо}")
        ок = ок and если
    for нельзя in ("comment-review", "comment-publish", "comment-unpublish"):
        если = нельзя not in разрешено
        строки.append(f"   {'не разрешено' if если else '[ПЛОХО: разрешено]'} {нельзя}")
        ок = ок and если
    return ок, строки


def проверить_канал_qwen() -> tuple[bool, list[str]]:
    """Что отвечает САМ мост на вызовы без токена доверия, то есть роли `qwen`.

    Это единственная проверка, измеряющая право там, где оно действует: канал
    без токена получает роль `qwen` независимо от поля `author`. Запись здесь
    не делается ни в одном случае: читается черновик, а отказ решения
    наступает до любой записи.
    """
    def вызов(имя: str, аргументы: dict) -> dict:
        запрос = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                  "params": {"name": имя, "arguments": аргументы}}
        r = urllib.request.Request("http://127.0.0.1:9000/mcp",
                                   data=json.dumps(запрос).encode("utf-8"),
                                   headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(r, timeout=40) as о:
            return json.loads(о.read())

    строки, ок = [], True
    try:
        чтение = вызов("comment_draft", {"site": "yummyani.org", "slug": "van-pis"})
    except (urllib.error.URLError, OSError, ValueError) as ош:
        return False, [f"   мост не ответил: {type(ош).__name__}: {ош}"]
    если_ошибка = bool((чтение.get("result") or {}).get("isError"))
    текст = json.dumps(чтение, ensure_ascii=False)
    if "неизвестный инструмент" in текст or "unknown tool" in текст.lower():
        return False, ["   comment_draft мост ещё не знает: перезапуска не было"]
    строки.append(f"   {'[нет]' if если_ошибка else 'да'} qwen читает свой черновик "
                  "(comment_draft)")
    ок = ок and not если_ошибка
    решение = вызов("review_comment", {"site": "yummyani.org", "slug": "van-pis",
                                       "verdict": "accepted"})
    отказано = bool((решение.get("result") or {}).get("isError"))
    причина = json.dumps(решение, ensure_ascii=False)
    строки.append(f"   {'да' if отказано else '[ПЛОХО: прошло]'} решение проверяющего "
                  "роли qwen отвергнуто")
    ок = ок and отказано
    if отказано and "comment-review" not in причина:
        строки.append("   [!] отказ не называет операцию comment-review")
    return ок, строки


def главное() -> int:
    части = (("мост MCP", проверить_мост),
             ("перечень инструментов моста", проверить_перечень_инструментов),
             ("исполнитель доставки", проверить_исполнителя),
             ("разделение прав в коде службы", проверить_права),
             ("права через живой канал qwen", проверить_канал_qwen))
    всё = True
    for имя, проверка in части:
        try:
            ок, строки = проверка()
        except Exception as ош:  # noqa: BLE001 — одна часть не роняет остальные
            ок, строки = False, [f"   проверка упала: {type(ош).__name__}: {ош}"]
        print(f"=== {имя}: {'внедрено' if ок else 'ЕЩЁ НЕТ'}")
        for с in строки:
            print(с)
        всё = всё and ок
    print(f"\nитог: {'внедрено во всех службах' if всё else 'внедрено НЕ полностью'}")
    return 0 if всё else 1


if __name__ == "__main__":
    raise SystemExit(главное())
