#!/usr/bin/env python3
"""Доезжают ли новые серии до витрины lords без перезапуска процесса.

watch_episode_delivery.py <data-dir> <домен> <out.json> [минут]
Ждёт, пока служба согласования перепишет `<site>-details.json`; после этого
сверяет: процесс витрины тот же (pid и время старта), отметки
`.episode-refresh-restart` нет, и у тайтлов из `changed` отчёта прохода
публичная страница показывает доступность из нового снимка. Только чтение.
"""
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

data, домен, out = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
предел = float(sys.argv[4]) * 60 if len(sys.argv) > 4 else 1800
снимок = next(data.glob("*-details.json"))
отчёт_путь = next(data.glob("*-episode-availability.json"))
отметка = data / ".episode-refresh-restart"


def процесс():
    for p in os.listdir("/proc"):
        if not p.isdigit():
            continue
        try:
            c = open(f"/proc/{p}/cmdline", "rb").read().replace(b"\0", b" ").decode()
        except OSError:
            continue
        if f"{data.parent}/releases/" in c and "frontend" in c:
            return int(p), os.stat(f"/proc/{p}").st_mtime
    return None, None


def страница(путь):
    з = urllib.request.Request(f"https://{домен}{путь}", headers={"User-Agent": "site-factory-perf-audit"})
    with urllib.request.urlopen(з, timeout=60) as о:
        return о.read().decode("utf-8", "ignore")


до = снимок.stat().st_mtime_ns
pid0, старт0 = процесс()
t0 = time.time()
print(f"жду прохода: снимок {time.strftime('%H:%M:%S', time.gmtime(до / 1e9))}, pid {pid0}", flush=True)
while снимок.stat().st_mtime_ns == до and time.time() - t0 < предел:
    time.sleep(10)
if снимок.stat().st_mtime_ns == до:
    итог = {"проход": False, "почему": f"за {предел / 60:.0f} мин снимок не переписан"}
else:
    t_записи = снимок.stat().st_mtime
    time.sleep(45)                     # перечитывание: 2 проверки по 10 с + постройка
    отчёт = json.loads(отчёт_путь.read_text(encoding="utf-8"))
    детали = json.loads(снимок.read_text(encoding="utf-8")).get("details") or {}
    pid1, старт1 = процесс()
    сверка = []
    for з in (отчёт.get("changed") or [])[:6]:
        слаг = з.get("slug")
        д = детали.get(слаг) or {}
        avail = sum(int(с.get("avail") or 0) for с in д.get("seasons") or [])
        try:
            html = страница(f"/title/{слаг}/")
            серий_на_странице = len(set(re.findall(rf'/title/{re.escape(слаг)}/season-\d+/episode-\d+/', html)))
        except Exception as ош:  # noqa: BLE001
            серий_на_странице = f"ошибка {ош!r}"
        сверка.append({"slug": слаг, "avail_в_снимке": avail, "ссылок_на_серии": серий_на_странице,
                       "план": з.get("seasons")})
    итог = {"проход": True,
            "снимок_переписан": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t_записи)),
            "snapshot_changed": отчёт.get("snapshot_changed"),
            "reload_in_place": отчёт.get("reload_in_place"),
            "отметка_перезапуска": отметка.exists(),
            "процесс_до": [pid0, старт0], "процесс_после": [pid1, старт1],
            "перезапуска_не_было": pid0 == pid1 and старт0 == старт1,
            "изменённые": сверка}
json.dump(итог, open(out, "w"), ensure_ascii=False, indent=1)
print(json.dumps(итог, ensure_ascii=False)[:1500])
