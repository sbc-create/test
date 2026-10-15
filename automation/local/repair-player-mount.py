#!/usr/bin/env python3
"""Починить витрины, у которых моя доставка целей СТЁРЛА вставку узла плеера.

Что случилось. `deliver-metrika-goals.py` подставлял третью вставку по якорю
`host.appendChild(n);\\n  bind(n, ++token);`, а замену вынимал из шаблона
начиная с КОММЕНТАРИЯ `/* player_start`, который стоит строкой НИЖЕ вставки
узла. Значит якорь содержал `host.appendChild(n);`, а замена — нет, и
`str.replace` эту строку удалял.

Чем это было у витрины, где правка успела выйти (измерено её линией на живом
сайте): обычный показ не страдал — узел `<video-player>` кладёт в разметку
сервер, и начальный путь идёт через `bind(first)`, минуя `mountAt`. Ломался
ПЕРЕБОР источников после отказа: `destroy()` снимал текущий узел, новый
создавался и никуда не вставлялся. Зритель, у которого первый источник не
отдал видео, терял плеер насовсем при неиспробованных источниках.

Починка здесь делает три вещи:

1. возвращает `host.appendChild(n);` на место — порядок «создать → вставить →
   привязать»;
2. снимает отправку `player_start` из `mountAt`;
3. ставит её в `bind(node, my)` — он на пути ОБОИХ монтирований, и
   `__sfGoalOnce` не даёт перебору отправить вторую цель. Это поправка линии
   витрины: цель из `mountAt` означала бы «показ запрошен» только у тех
   зрителей, у кого он сперва не состоялся.

Проверка после правки обязательна и делается здесь же: вставка ровно одна,
цели в `mountAt` нет, цель в `bind` есть, файл разбирается.

    python3 automation/local/repair-player-mount.py --dry-run lords-10
    python3 automation/local/repair-player-mount.py lords-10 … lords-17
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
ФАЙЛ = "lords-frontend.py"

СЛОМАННОЕ = """  n.setAttribute('data-aggregator', c.aggregator||'');
  /* player_start — площадка ЗАПРОСИЛА воспроизведение, а не факт первого
     кадра: у провайдера в зафиксированном контракте события начала показа
     нет. Та же формулировка, что у Yummy, чтобы одна цель не значила на
     разных витринах разное. */
  try{ if(window.__sfGoalOnce){ window.__sfGoalOnce('player_start'); } }catch(e){}
  bind(n, ++token);"""

ПОЧИНЕННОЕ = """  n.setAttribute('data-aggregator', c.aggregator||'');
  host.appendChild(n);
  bind(n, ++token);"""

ЯКОРЬ_BIND = """ function bind(node, my){
  if(!node) return;
  snapshot(node);"""

ПРИМЕЧАНИЕ = (
    "Починка вставки узла плеера: доставка целей стёрла host.appendChild(n), "
    "из-за чего перебор источников после отказа терял плеер. Порядок "
    "«создать → вставить → привязать» восстановлен, player_start перенесён из "
    "mountAt в bind (он на пути обоих монтирований)."
)


def цель_для_bind() -> str:
    """Блок отправки цели — ИЗ ШАБЛОНА, где он уже исправлен."""
    t = (КОРЕНЬ / "automation" / "host" / ФАЙЛ).read_text(encoding="utf-8")
    м = re.search(r"(?s)( function bind\(node, my\)\{\n  if\(!node\) return;\n)"
                  r"(.*?)(  snapshot\(node\);)", t)
    if not м or "player_start" not in м.group(2):
        raise SystemExit("в шаблоне нет цели в bind — сначала поправьте шаблон")
    return м.group(2)


def закрепить(проект: Path, файл: Path) -> str:
    замок = проект / "pins.lock.json"
    if not замок.is_file():
        return "замка нет"
    д = json.loads(замок.read_text(encoding="utf-8"))
    запись = (д.get("files") or {}).get(ФАЙЛ)
    if запись is None:
        return f"в замке нет записи о {ФАЙЛ}"
    запись["sha256"] = hashlib.sha256(файл.read_bytes()).hexdigest()
    запись["bytes"] = файл.stat().st_size
    прежнее = (запись.get("note") or "").strip()
    if ПРИМЕЧАНИЕ not in прежнее:
        запись["note"] = (прежнее + " " if прежнее else "") + ПРИМЕЧАНИЕ
    замок.write_text(json.dumps(д, ensure_ascii=False, indent=1) + "\n",
                     encoding="utf-8")
    return "замок обновлён"


def проверить(текст: str) -> list[str]:
    беды = []
    if текст.count("host.appendChild(n);") != 1:
        беды.append(f"вставок узла {текст.count('host.appendChild(n);')}, а не одна")
    м = re.search(r"(?s)function mountAt\(i\)\{(.*?)\n }", текст)
    if м and "player_start" in м.group(1):
        беды.append("цель осталась в mountAt")
    м2 = re.search(r"(?s)function bind\(node, my\)\{(.*?)snapshot\(node\)", текст)
    if not м2 or "player_start" not in м2.group(1):
        беды.append("цели в bind нет")
    if м and "appendChild" not in м.group(1):
        беды.append("в mountAt нет вставки узла")
    # Порядок: создать → вставить → привязать.
    if м:
        тело = м.group(1)
        i1 = тело.find("createElement('video-player')")
        i2 = тело.find("host.appendChild(n);")
        i3 = тело.find("bind(n, ++token)")
        if not (0 <= i1 < i2 < i3):
            беды.append(f"порядок нарушен: create {i1}, append {i2}, bind {i3}")
    return беды


def главное(аргв=None) -> int:
    р = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("sites", nargs="*")
    р.add_argument("--repo", action="append", default=[], type=Path)
    р.add_argument("--dry-run", action="store_true")
    опции = р.parse_args(аргв)
    if not опции.sites and not опции.repo:
        р.error("нужен хотя бы один site_id или --repo")

    цель = цель_для_bind()
    цели = [(s, КОРЕНЬ / "var" / "new-sites" / s) for s in опции.sites]
    цели += [(п.name, п) for п in опции.repo]

    плохо = 0
    for имя, проект in цели:
        файл = проект / "src" / ФАЙЛ
        if not файл.is_file():
            print(f"[x] {имя}: нет {файл}")
            плохо += 1
            continue
        было = файл.read_text(encoding="utf-8")
        if not проверить(было):
            print(f"{имя}: уже в порядке")
            continue
        стало = было
        if СЛОМАННОЕ in стало:
            стало = стало.replace(СЛОМАННОЕ, ПОЧИНЕННОЕ, 1)
        if "player_start" not in (
                re.search(r"(?s)function bind\(node, my\)\{(.*?)snapshot\(node\)",
                          стало) or re.match("", "")).group(1 if True else 0):
            if стало.count(ЯКОРЬ_BIND) != 1:
                print(f"[x] {имя}: начало bind не найдено — правка руками")
                плохо += 1
                continue
            стало = стало.replace(
                ЯКОРЬ_BIND,
                " function bind(node, my){\n  if(!node) return;\n"
                + цель + "  snapshot(node);", 1)
        беды = проверить(стало)
        if беды:
            print(f"[x] {имя}: после правки осталось: {'; '.join(беды)}")
            плохо += 1
            continue
        if опции.dry_run:
            print(f"{имя}: починка легла бы ({len(было)} -> {len(стало)} знаков)")
            continue
        файл.write_text(стало, encoding="utf-8")
        г = subprocess.run(
            [sys.executable, "-c",
             "import ast,sys;ast.parse(open(sys.argv[1],encoding='utf-8').read())",
             str(файл)], capture_output=True, text=True)
        if г.returncode != 0:
            файл.write_text(было, encoding="utf-8")
            print(f"[x] {имя}: файл не разбирается, возвращён")
            плохо += 1
            continue
        print(f"{имя}: вставка узла на месте, цель в bind; {закрепить(проект, файл)}")
    return 1 if плохо else 0


if __name__ == "__main__":
    raise SystemExit(главное())
