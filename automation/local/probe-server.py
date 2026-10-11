#!/usr/bin/env python3
"""Запуск ПРОБНОГО сервера так, чтобы он не пережил свою надобность.

Повод измерен 11 октября. Редактор простоял 07:09-15:55 с 101 отказом шлюза по
памяти, потому что в системе накопились 13 пробных копий витрин без хозяина
(около 2,8 ГБ): `MemAvailable` держался на 958 МиБ при пороге редактора
2048 МиБ. Копии подняты не инструментами фабрики — все они гасят своих
потомков в `finally`, — а напрямую из оболочек вызова: сервер запускали в фоне,
вызов заканчивался, и процесс жил дальше. Самому старому было 249 часов.

**Два сторожа, и ни один не заменяет другого.** Это не перестраховка, а вывод
из разбора: у сироты `224855` родительская оболочка была ЖИВА, и сторож «умри
вместе с родителем» её бы не тронул.

* `PR_SET_PDEATHSIG` — ребёнок получает сигнал, когда умирает его родитель.
  Закрывает случай «оболочку закрыли, сервер остался». Ставится дважды:
  серверу относительно обёртки и обёртке относительно её собственного
  родителя, иначе цепочка рвётся на середине;
* **предел жизни** (`--ttl`) — обёртка гасит сервер по часам, сколько бы ни
  был жив родитель. Закрывает случай «родитель жив, но о сервере забыли» —
  тот самый, который и дал 249 часов.

Плюс группа процессов: сервер запускается в своей группе, и гасится группа
целиком. Пробный сервер часто поднимает дочерние процессы (сборщик, обозреватель),
и гашение одного главного оставляло бы их.

Записка о процессе (`var/probe-servers/<pid>.json`) пишется сразу после
запуска, до проверки готовности: прерывание до неё иначе оставляет живой
процесс, о котором никто не знает. Та же причина, по которой так сделано в
`factory/targets/payload_multisite.py`.

Постоянные данные сайтов не трогаются: инструмент только запускает чужую
команду и гасит её.

    python3 automation/local/probe-server.py --ttl 900 -- \\
        python3 src/animedia-frontend.py --port 9190
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[1].parent
ЗАПИСКИ = КОРЕНЬ / "var" / "probe-servers"

#: prctl(2): PR_SET_PDEATHSIG = 1. Сигнал приходит ребёнку, когда умирает его
#: родитель, и это свойство ядра, а не обещание обработчика: сработает, даже
#: если родитель убит SIGKILL и никакого finally не выполнил.
PR_SET_PDEATHSIG = 1

#: Предел жизни по умолчанию. Полчаса — больше любого известного пробного
#: прогона (самый долгий замер этой сессии шёл 12 минут) и несопоставимо
#: меньше 249 часов, которые прожила самая старая сирота.
TTL_ПО_УМОЛЧАНИЮ = 1800


def умереть_с_родителем(сигнал: int = signal.SIGTERM) -> None:
    """Попросить ядро прислать сигнал, когда умрёт родитель.

    Молча не падаем: на системе без prctl сторож просто не встанет, и об этом
    надо сказать, а не делать вид, что он есть.
    """
    try:
        libc = ctypes.CDLL("libc.so.6", use_errno=True)
        итог = libc.prctl(PR_SET_PDEATHSIG, сигнал, 0, 0, 0)
    except OSError as сбой:  # pragma: no cover - зависит от системы
        print(f"предупреждение: prctl недоступен ({сбой}), сторож "
              f"«умри с родителем» НЕ поставлен", file=sys.stderr)
        return
    if итог != 0:  # pragma: no cover - зависит от системы
        print(f"предупреждение: prctl вернул {итог}, errno "
              f"{ctypes.get_errno()}; сторож «умри с родителем» НЕ поставлен",
              file=sys.stderr)


def убрать_мёртвые_записки() -> list[int]:
    """Выбросить записки о процессах, которых уже нет. Возвращает их pid.

    Записку убирает сама обёртка в `finally`, но при `SIGKILL` никакой
    `finally` не выполняется — именно тот случай, от которого стоит PDEATHSIG.
    Тогда записка остаётся и начинает врать: утверждает пробный сервер там,
    где его нет. Мёртвая запись о живом процессе хуже отсутствия записи,
    потому что по ней принимают решения.
    """
    if not ЗАПИСКИ.is_dir():
        return []
    убрано = []
    for путь in sorted(ЗАПИСКИ.glob("*.json")):
        try:
            pid = int(путь.stem)
        except ValueError:
            continue
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            путь.unlink(missing_ok=True)
            убрано.append(pid)
        except PermissionError:  # pragma: no cover - чужой процесс, не наш
            continue
    return убрано


def записка(pid: int, порт: str, команда: list[str], ttl: int) -> Path:
    ЗАПИСКИ.mkdir(parents=True, exist_ok=True)
    путь = ЗАПИСКИ / f"{pid}.json"
    путь.write_text(json.dumps({
        "pid": pid,
        "порт": порт,
        "команда": команда,
        "ttl_сек": ttl,
        "запущен": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "обёртка_pid": os.getpid(),
        "рабочий_каталог": os.getcwd(),
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    return путь


def порт_из_команды(команда: list[str]) -> str:
    for i, часть in enumerate(команда):
        if часть in ("--port", "-p") and i + 1 < len(команда):
            return команда[i + 1]
        if часть.startswith("--port="):
            return часть.split("=", 1)[1]
    return ""


def погасить(процесс: subprocess.Popen, причина: str) -> int:
    """Погасить ГРУППУ процесса: мягко, затем жёстко. Возвращает код выхода."""
    if процесс.poll() is not None:
        return процесс.returncode
    print(f"гашу пробный сервер: {причина}", file=sys.stderr)
    for сигнал, пауза in ((signal.SIGTERM, 10.0), (signal.SIGKILL, 5.0)):
        try:
            os.killpg(os.getpgid(процесс.pid), сигнал)
        except ProcessLookupError:
            break
        except PermissionError as сбой:  # pragma: no cover
            print(f"не смог послать сигнал группе: {сбой}", file=sys.stderr)
            break
        try:
            процесс.wait(timeout=пауза)
            break
        except subprocess.TimeoutExpired:
            continue
    return процесс.returncode if процесс.poll() is not None else -1


def главное(аргв: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(
        description="пробный сервер с двумя сторожами: PDEATHSIG и предел жизни")
    р.add_argument("--ttl", type=int, default=TTL_ПО_УМОЛЧАНИЮ,
                   help=f"предел жизни в секундах (по умолчанию {TTL_ПО_УМОЛЧАНИЮ})")
    р.add_argument("--no-pdeathsig", action="store_true",
                   help="не ставить сторож «умри с родителем» (для отладки)")
    р.add_argument("команда", nargs=argparse.REMAINDER,
                   help="-- и затем команда запуска сервера")
    а = р.parse_args(аргв)

    команда = [ч for ч in а.команда if ч != "--"]
    if not команда:
        print("нечего запускать: укажите команду после --", file=sys.stderr)
        return 2
    if а.ttl <= 0:
        print("предел жизни должен быть положительным: сервер без предела — "
              "это та самая сирота", file=sys.stderr)
        return 2

    # Записки от обёрток, убитых жёстко, остались бы врать. Уборка на входе
    # дешевле уборки по расписанию и не требует ничьего внимания.
    if убрано := убрать_мёртвые_записки():
        print(f"убрал записки о мёртвых процессах: "
              f"{', '.join(str(п) for п in убрано)}", file=sys.stderr)

    # Сторож для САМОЙ обёртки: если оболочку вызова закрыли, обёртка получит
    # сигнал и в своём finally погасит сервер. Без этого звена цепочка рвётся.
    if not а.no_pdeathsig:
        умереть_с_родителем()

    def в_ребёнке() -> None:
        os.setpgrp()  # своя группа: гасим её целиком
        if not а.no_pdeathsig:
            умереть_с_родителем()

    процесс = subprocess.Popen(команда, preexec_fn=в_ребёнке)
    путь = записка(процесс.pid, порт_из_команды(команда), команда, а.ttl)
    print(f"пробный сервер {процесс.pid} запущен, предел {а.ttl} с, "
          f"записка {путь}", file=sys.stderr)

    срок = time.monotonic() + а.ttl
    код = 0
    try:
        while True:
            try:
                код = процесс.wait(timeout=1.0)
                break
            except subprocess.TimeoutExpired:
                if time.monotonic() >= срок:
                    код = погасить(процесс, f"исчерпан предел жизни {а.ttl} с")
                    # Предел — не ошибка сервера, но и не успех прогона:
                    # вызывающий обязан узнать, что сервер убит по часам.
                    return 124
    except KeyboardInterrupt:
        код = погасить(процесс, "прерывание с клавиатуры")
        return 130
    finally:
        погасить(процесс, "обёртка завершается")
        try:
            путь.unlink()
        except OSError:
            pass
    return код


if __name__ == "__main__":
    sys.exit(главное())
