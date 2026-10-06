#!/usr/bin/env python3
"""Обрыв соединений при обновлении серий: перезапуск витрины против перечитывания.

restart_vs_reload.py <режим> <выпуск> <data> <порт> <out.json> [секунд]

Режим `restart` повторяет то, что делает служба согласования серий на
lordserials22.info: снимок подробностей переписан -> `systemctl try-restart`
(SIGTERM процессу, новый процесс читает снимок с нуля). Режим `reload`
переписывает снимок атомарно (как `записать_атомарно` инструмента) и процесс
НЕ трогает: выпуск с перечитыванием обязан подхватить снимок сам.

Нагрузка — один посетитель: запрос раз в 0.5 с по кругу (главная, карточка,
серия, поиск), таймаут 30 с. Это не нагрузочный тест. Копия локальная, на
копии данных: живая витрина не участвует.

Итог: число неудач (отказ соединения, сброс, таймаут, не-200), самая длинная
дыра без успешного ответа и худшее время ответа после события.
"""
import json
import os
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

режим, выпуск, data, порт, out = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
длительность = float(sys.argv[6]) if len(sys.argv) > 6 else 150
ЗДЕСЬ = Path(__file__).resolve().parent
ЗАПУСК = ЗДЕСЬ.parent.parent / "var" / "perf" / "prof_lords.py"
ПУТИ = ["/", "/title/boec-baki/", "/title/boec-baki/season-1/episode-2/", "/search/?q=%D0%B2%D0%BE%D0%BB%D0%BA"]


def поднять():
    return subprocess.Popen([sys.executable, str(ЗАПУСК), str(выпуск), str(data), str(порт), "-"],
                            stdout=open(f"{out}.{int(time.time())}.log", "w"), stderr=subprocess.STDOUT,
                            start_new_session=True)


def готов(предел=600):
    t = time.time()
    while time.time() - t < предел:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{порт}/", timeout=5) as о:
                if о.status == 200:
                    return time.time() - t
        except Exception:  # noqa: BLE001
            pass
        time.sleep(0.5)
    raise SystemExit("витрина не поднялась")


процесс = поднять()
print(f"готов за {готов():.1f} с", flush=True)
for п in ПУТИ:                                   # прогрев: память на снимок
    urllib.request.urlopen(f"http://127.0.0.1:{порт}{п}", timeout=120).read()

журнал = []
стоп = threading.Event()


def посетитель():
    i = 0
    while not стоп.is_set():
        путь = ПУТИ[i % len(ПУТИ)]
        i += 1
        t = time.time()
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{порт}{путь}", timeout=30) as о:
                о.read()
                код = о.status
        except urllib.error.HTTPError as о:
            код = о.code
        except Exception as ош:  # noqa: BLE001
            код = type(ош).__name__ + ":" + str(getattr(ош, "reason", ош))[:60]
        журнал.append({"t": round(t, 3), "путь": путь, "код": код, "мс": round((time.time() - t) * 1000)})
        time.sleep(0.5)


поток = threading.Thread(target=посетитель, daemon=True)
поток.start()
time.sleep(10)
событие = time.time()
снимок = data / "lords-05-details.json"
if режим == "restart":
    # Тот же шаг, что ExecStartPost: try-restart = SIGTERM, затем новый процесс.
    os.killpg(процесс.pid, signal.SIGTERM)
    процесс.wait(timeout=60)
    процесс = поднять()
else:
    # Новый снимок приходит атомарной заменой файла: tmp + rename. Пишет
    # ОТДЕЛЬНЫЙ процесс, как служба согласования: разбор 80 МБ в процессе
    # стенда останавливал бы поток посетителя и мерил бы сам стенд.
    subprocess.run([sys.executable, "-c", (
        "import json,os,sys,time;p=sys.argv[1];d=json.load(open(p,encoding='utf-8'));"
        "d['catalog_built_at']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime());"
        "t=p+'.tmp';json.dump(d,open(t,'w',encoding='utf-8'),ensure_ascii=False);os.replace(t,p)"),
        str(снимок)], check=True)
time.sleep(длительность)
стоп.set()
поток.join(timeout=40)
os.killpg(процесс.pid, signal.SIGTERM)

после = [з for з in журнал if з["t"] >= событие]
неудачи = [з for з in после if з["код"] != 200]
успехи = [з["t"] + з["мс"] / 1000 for з in журнал if з["код"] == 200]
дыра, прежний = 0.0, None
for т in sorted(успехи):
    if прежний is not None:
        дыра = max(дыра, т - прежний)
    прежний = т
итог = {"режим": режим, "запросов_после": len(после), "неудач": len(неудачи),
        "виды_неудач": sorted({str(з["код"]) for з in неудачи}),
        "дыра_без_ответа_с": round(дыра, 1),
        "худший_ответ_после_мс": max([з["мс"] for з in после if з["код"] == 200] or [0]),
        "журнал": журнал}
json.dump(итог, open(out, "w"), ensure_ascii=False, indent=1)
print(json.dumps({к: в for к, в in итог.items() if к != "журнал"}, ensure_ascii=False))
