#!/usr/bin/env python3
"""Наблюдатель за прогоном nova-daily-refresh. Только чтение, ничего не запускает.

Признаки старта ищутся независимо друг от друга, чтобы не пропустить прогон,
который упал раньше, чем успел написать отчёт:

* процесс конвейера в /proc;
* cgroup службы в system.slice (есть, только пока служба активна);
* новый файл отчёта публикации;
* промежуточные данные, обновлённые после опорной метки.

Пока прогон идёт, пишется пиковый RSS его процессов: иначе измерить пик нечем —
после выхода cgroup исчезает, а журнал этой учётной записи недоступен.
"""
from __future__ import annotations

import datetime
import json
import pathlib
import sys
import time

ВАР = pathlib.Path("/srv/site-factory/repo/var/lords")
ОТЧЁТЫ = ВАР / "publish-reports"
СЛАЙС = pathlib.Path("/sys/fs/cgroup/system.slice")
ИМЕНА = ("nova-daily-refresh", "nova-catalog-publish", "nova-detail-backfill",
         "nova-ratings-backfill")
ОПОРА = float(sys.argv[1]) if len(sys.argv) > 1 else time.time()
ПРЕДЕЛ = float(sys.argv[2]) if len(sys.argv) > 2 else 2400.0
ЖУРНАЛ = pathlib.Path(sys.argv[3]) if len(sys.argv) > 3 else pathlib.Path("/tmp/watch.jsonl")


def сейчас() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def процессы() -> list[dict]:
    итог = []
    for п in pathlib.Path("/proc").iterdir():
        if not п.name.isdigit():
            continue
        try:
            cmd = (п / "cmdline").read_bytes().replace(b"\0", b" ").decode("utf-8", "replace")
        except OSError:
            continue
        # Собственная команда наблюдателя не считается прогоном.
        if "watch_run.py" in cmd or "python3 -c" in cmd:
            continue
        if not any(и in cmd for и in ИМЕНА):
            continue
        rss = 0
        try:
            for с in (п / "status").read_text().splitlines():
                if с.startswith("VmRSS:"):
                    rss = int(с.split()[1]) * 1024
        except OSError:
            pass
        итог.append({"pid": п.name, "rss": rss, "cmd": cmd.strip()[:160]})
    return итог


def cgroup_службы() -> dict:
    к = СЛАЙС / "nova-daily-refresh.service"
    if not к.is_dir():
        return {}
    итог = {"есть": True}
    for ф in ("memory.current", "memory.peak", "memory.max", "memory.events"):
        try:
            итог[ф] = (к / ф).read_text().strip()
        except OSError:
            pass
    return итог


def отчёты_после() -> list[str]:
    if not ОТЧЁТЫ.is_dir():
        return []
    return sorted(ф.name for ф in ОТЧЁТЫ.glob("daily-*.json")
                  if ф.stat().st_mtime > ОПОРА)


def свежие_промежуточные() -> list[str]:
    цели = [ВАР / "lords" / "catalog-cache" / "lords-01.json",
            ВАР / "ratings-store.json", ВАР / "detail-cache",
            ВАР / "nova-catalog-publish.lock"]
    return [п.name for п in цели if п.exists() and п.stat().st_mtime > ОПОРА]


def запись(событие: dict) -> None:
    with ЖУРНАЛ.open("a", encoding="utf-8") as ф:
        ф.write(json.dumps({"at": сейчас(), **событие}, ensure_ascii=False) + "\n")


def главное() -> int:
    запись({"событие": "наблюдение начато", "опора": ОПОРА, "предел_сек": ПРЕДЕЛ})
    пик = 0
    шёл = False
    до = time.time() + ПРЕДЕЛ
    while time.time() < до:
        пр = процессы()
        cg = cgroup_службы()
        идёт = bool(пр) or bool(cg)
        if идёт:
            сумма = sum(п["rss"] for п in пр)
            пик = max(пик, сумма)
            if not шёл:
                шёл = True
                запись({"событие": "СТАРТ ОБНАРУЖЕН", "процессы": пр, "cgroup": cg})
            else:
                запись({"событие": "идёт", "rss_сумма": сумма, "пик": пик,
                        "процессов": len(пр), "cgroup": cg})
        elif шёл:
            запись({"событие": "ЗАВЕРШИЛСЯ", "пик_rss": пик,
                    "новые_отчёты": отчёты_после()})
            return 0
        time.sleep(15 if идёт else 30)
    запись({"событие": "наблюдение окончено без старта",
            "новые_отчёты": отчёты_после(),
            "свежие_промежуточные": свежие_промежуточные(), "шёл": шёл, "пик": пик})
    return 0


if __name__ == "__main__":
    raise SystemExit(главное())
