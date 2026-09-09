#!/usr/bin/env python3
"""Установка приёмщика выкладки Lords. Одна команда, идемпотентная.

После неё владелец больше не нужен: выкладка запускается заявкой в каталоге,
доступном пользователю `claude`, а результаты и журналы читаются им же без
повышения прав.

Что делает:

1. сверяет отпечатки устанавливаемых файлов с записанными здесь;
2. кладёт их на исполняемый раздел — `/usr/local/libexec/site-factory`;
3. создаёт каталоги очереди, состояния, результатов и свидетельств;
4. ставит два юнита, перечитывает конфигурацию, включает наблюдение за очередью;
5. выполняет настоящую самопроверку установленной копии;
6. кладёт первую заявку на `lords-02` и возвращает управление.

Чего не делает: не трогает SSH, firewall, пользователей, DNS, не обновляет
систему и не перезагружает хост. Права, которые он выдаёт, ограничены тремя
витринами Lords и заданы внутри установленных файлов, а не в заявке.

Повторный запуск безопасен: файлы переустанавливаются, каталоги создаются
только при отсутствии, незавершённая выкладка продолжается с той же витрины.
"""

from __future__ import annotations

import hashlib
import json
import os
import pwd
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ИСТОЧНИК = Path("/home/claude/wt-integration-28/automation/deploy")
LIBEXEC = Path("/usr/local/libexec/site-factory")
SBIN = Path("/usr/local/sbin")
UNITS = Path("/etc/systemd/system")
БАЗА = Path("/var/lib/lords-deploy")

#: Отпечатки полезной нагрузки. Файл, не совпавший с записанным здесь, не
#: устанавливается: источник лежит в дереве пользователя, и доверять ему без
#: сверки значило бы устанавливать что угодно.
ПОЛЕЗНАЯ_НАГРУЗКА = @@MANIFEST@@

#: Первая заявка. Кладётся ровно один раз за установку и содержит только то,
#: что схема приёмщика разрешает: витрины, ревизию и отпечатки.
ЗАЯВКА = @@REQUEST@@


def отпечаток(путь: Path) -> str:
    h = hashlib.sha256()
    with путь.open("rb") as ф:
        for кусок in iter(lambda: ф.read(1 << 20), b""):
            h.update(кусок)
    return h.hexdigest()


def сказать(текст: str) -> None:
    print(f"[bootstrap] {текст}", flush=True)


def выполнить(argv: list[str], таймаут: float = 300.0) -> subprocess.CompletedProcess:
    return subprocess.run(argv, capture_output=True, text=True, timeout=таймаут)


def установить_файлы() -> None:
    LIBEXEC.mkdir(parents=True, exist_ok=True)
    os.chmod(LIBEXEC, 0o755)
    for имя, ожидаемый in ПОЛЕЗНАЯ_НАГРУЗКА.items():
        источник = ИСТОЧНИК / имя
        if not источник.is_file():
            raise SystemExit(f"нет файла для установки: {источник}")
        фактический = отпечаток(источник)
        if фактический != ожидаемый:
            raise SystemExit(
                f"отпечаток {имя} не совпал: {фактический} вместо {ожидаемый}")
        цель = (UNITS / Path(имя).name) if имя.startswith("units/") else (LIBEXEC / имя)
        цель.parent.mkdir(parents=True, exist_ok=True)
        временный = цель.with_suffix(цель.suffix + ".new")
        shutil.copyfile(источник, временный)
        os.chown(временный, 0, 0)
        os.chmod(временный, 0o644 if имя.startswith("units/") else 0o755)
        os.replace(временный, цель)
        сказать(f"установлен {цель} ({фактический[:12]}…)")
    # Помощник доступен и как отдельная команда: диагностика не должна требовать
    # знания внутреннего пути.
    ссылка = SBIN / "lords-deployctl"
    if ссылка.is_symlink() or ссылка.exists():
        ссылка.unlink()
    ссылка.symlink_to(LIBEXEC / "lords-deployctl")
    сказать(f"установлен {ссылка} → {LIBEXEC / 'lords-deployctl'}")


def создать_каталоги() -> None:
    claude = pwd.getpwnam("claude")
    # Заявки и входящие артефакты пишет claude; остальное он только читает.
    права = {
        "requests": (0o2775, claude.pw_uid, claude.pw_gid),
        "incoming": (0o2775, claude.pw_uid, claude.pw_gid),
        "state": (0o755, 0, 0),
        "results": (0o755, 0, 0),
        "logs": (0o755, 0, 0),
        "evidence": (0o2775, claude.pw_uid, claude.pw_gid),
        "accepted": (0o755, 0, 0),
    }
    БАЗА.mkdir(parents=True, exist_ok=True)
    os.chown(БАЗА, 0, 0)
    os.chmod(БАЗА, 0o755)
    for имя, (режим, uid, gid) in права.items():
        путь = БАЗА / имя
        путь.mkdir(parents=True, exist_ok=True)
        os.chown(путь, uid, gid)
        os.chmod(путь, режим)
    сказать(f"каталоги очереди готовы: {БАЗА}")


def поставить_юниты() -> None:
    выполнить(["systemctl", "daemon-reload"])
    for юнит in ("lords-deploy-broker.service", "lords-deploy-broker.path"):
        готово = выполнить(["systemctl", "enable", юнит])
        if готово.returncode != 0:
            raise SystemExit(f"{юнит} не включён: {готово.stderr.strip()}")
    сказать("юниты включены; наблюдение за очередью поднимается")


def самопроверка() -> dict:
    готово = выполнить([sys.executable, str(LIBEXEC / "lords-deployctl"), "self-test"],
                       таймаут=600)
    try:
        отчёт = json.loads(готово.stdout or "{}")
    except json.JSONDecodeError:
        raise SystemExit(f"самопроверка вернула не JSON: {готово.stdout[:400]}")
    отказы = [п for п in отчёт.get("checks", []) if not п["ok"]]
    for п in отказы:
        сказать(f"  ОТКАЗ {п['check']}: {п['detail']}")
    if отчёт.get("verdict") != "SELF_TEST=PASS":
        raise SystemExit(f"самопроверка установленной копии не пройдена: отказов {len(отказы)}")
    сказать(f"SELF_TEST=PASS, проверок {len(отчёт.get('checks', []))}")
    return отчёт


def подать_заявку() -> Path:
    claude = pwd.getpwnam("claude")
    путь = БАЗА / "requests" / f"{ЗАЯВКА['deployment_id']}.json"
    результат = БАЗА / "results" / f"{ЗАЯВКА['deployment_id']}.json"
    if результат.is_file():
        сказать(f"заявка {ЗАЯВКА['deployment_id']} уже обрабатывалась: {результат}")
        return результат
    временный = путь.with_suffix(".json.new")
    временный.write_text(json.dumps(ЗАЯВКА, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")
    os.chown(временный, claude.pw_uid, claude.pw_gid)
    os.chmod(временный, 0o664)
    os.replace(временный, путь)
    сказать(f"подана заявка {путь}")
    return путь


def main() -> int:
    if os.geteuid() != 0:
        print("устанавливает root")
        return 1
    сказать(f"источник {ИСТОЧНИК}")
    установить_файлы()
    создать_каталоги()
    поставить_юниты()
    самопроверка()
    подать_заявку()
    # Наблюдатель запускается последним: до этого момента очередь могла быть
    # непустой, и служба стартовала бы раньше самопроверки.
    выполнить(["systemctl", "start", "lords-deploy-broker.path"])
    выполнить(["systemctl", "start", "--no-block", "lords-deploy-broker.service"])
    сказать("приёмщик работает; выкладка идёт в юните lords-deploy-broker.service")
    сказать(f"результаты: {БАЗА / 'results'}")
    сказать(f"журналы:    {БАЗА / 'logs'}")
    сказать(f"состояние:  {БАЗА / 'state'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
