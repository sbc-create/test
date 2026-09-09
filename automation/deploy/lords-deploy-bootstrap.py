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

import argparse
import hashlib
import json
import os
import pwd
import shutil
import subprocess
import sys
from pathlib import Path

ИСТОЧНИК = Path("/home/claude/wt-integration-28/automation/deploy")
LIBEXEC = Path("/usr/local/libexec/site-factory")
SBIN = Path("/usr/local/sbin")
UNITS = Path("/etc/systemd/system")
БАЗА = Path("/var/lib/lords-deploy")
ТАЙМЕР_ОБНОВЛЕНИЯ = "lords-content-refresh.timer"

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
    выполнить(["systemctl", "start", "lords-deploy-broker.path"])
    сказать("юниты включены, наблюдение за очередью поднято")


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


def проверить_установленное() -> list[dict]:
    """Владельцы, права, пути, рабочий каталог и доставка секретов.

    Проверяется установленная копия, а не исходник: устанавливали одно, а
    работать будет другое, если установка прошла не так, как думали.
    """
    проверки: list[dict] = []

    def проверить(имя: str, условие: bool, деталь: str = "") -> None:
        проверки.append({"check": имя, "ok": bool(условие), "detail": деталь})

    for имя in ПОЛЕЗНАЯ_НАГРУЗКА:
        цель = (UNITS / Path(имя).name) if имя.startswith("units/") else (LIBEXEC / имя)
        ст = цель.stat()
        режим = ст.st_mode & 0o777
        ожидаемый = 0o644 if имя.startswith("units/") else 0o755
        проверить(f"{цель}: владелец root:root", ст.st_uid == 0 and ст.st_gid == 0,
                  f"uid={ст.st_uid} gid={ст.st_gid}")
        проверить(f"{цель}: права {oct(ожидаемый)}", режим == ожидаемый, oct(режим))
        проверить(f"{цель}: путь абсолютный", цель.is_absolute(), str(цель))
        проверить(f"{цель}: отпечаток совпал",
                  отпечаток(цель) == ПОЛЕЗНАЯ_НАГРУЗКА[имя])

    # Рабочий каталог сценария обновления. Из-за его отсутствия прошлый прогон
    # отказал с «No module named factory» за ноль секунд.
    рабочий = выполнить(["systemctl", "show", "-p", "WorkingDirectory", "--value",
                         "lords-content-refresh.service"]).stdout.strip()
    проверить("рабочий каталог обновления — /srv/site-factory/repo",
              рабочий.rstrip("/").endswith("/srv/site-factory/repo"), рабочий or "пусто")

    # Доставка секретов. Lords читает credentials только через LoadCredential, и
    # запуск сценария подпроцессом отказывал именно поэтому. Значения секретов
    # здесь не читаются и не печатаются — только факт объявления.
    creds = выполнить(["systemctl", "show", "-p", "LoadCredential", "--value",
                       "lords-content-refresh.service"]).stdout.strip()
    имена = [ч.split("=", 1)[0] for ч in creds.split() if ч]
    проверить("юнит обновления объявляет LoadCredential", bool(имена),
              ", ".join(имена) or "не объявлено")

    # Очередь: заявки я обязан подавать сам, результаты — читать без sudo.
    claude = pwd.getpwnam("claude")
    очередь = БАЗА / "requests"
    ст = очередь.stat()
    проверить("каталог заявок принадлежит claude", ст.st_uid == claude.pw_uid,
              f"uid={ст.st_uid}")
    проверить("каталог заявок доступен на запись владельцу",
              bool(ст.st_mode & 0o200), oct(ст.st_mode & 0o777))
    for имя in ("results", "state", "logs"):
        ст = (БАЗА / имя).stat()
        проверить(f"каталог {имя} читаем всеми", bool(ст.st_mode & 0o004),
                  oct(ст.st_mode & 0o777))
    проверить("очередь пуста: заявок не подано",
              not list(очередь.glob("*.json")),
              str([p.name for p in очередь.glob("*.json")]))

    # Наблюдатель поднят — без него заявка осталась бы лежать.
    состояние = выполнить(["systemctl", "is-active", "lords-deploy-broker.path"]).stdout.strip()
    проверить("наблюдатель очереди работает", состояние == "active", состояние)

    # Действующие витрины не тронуты установкой.
    for сайт in ("lords-01", "lords-02", "lords-03"):
        служба = выполнить(["systemctl", "is-active", f"{сайт}.service"]).stdout.strip()
        ссылка = Path(f"/srv/lords/{сайт}/current")
        проверить(f"{сайт}: служба работает, релиз на месте",
                  служба == "active" and ссылка.exists(),
                  f"{служба}, {ссылка.resolve().name if ссылка.exists() else 'нет'}")
    таймер = выполнить(["systemctl", "is-active", ТАЙМЕР_ОБНОВЛЕНИЯ]).stdout.strip()
    включён = выполнить(["systemctl", "is-enabled", ТАЙМЕР_ОБНОВЛЕНИЯ]).stdout.strip()
    проверить("таймер обновления каталога не тронут",
              таймер == "active" and включён == "enabled", f"{таймер}/{включён}")
    return проверки


def main() -> int:
    р = argparse.ArgumentParser(description="установка приёмщика выкладки Lords")
    р.add_argument("--install-only", action="store_true",
                   help="поставить и проверить, ничего не выкладывая")
    р.add_argument("--deploy", action="store_true",
                   help="поставить и подать вшитую заявку (нужна вшитая заявка)")
    args = р.parse_args()
    if not args.install_only and not args.deploy:
        print("укажите --install-only или --deploy")
        return 2
    if os.geteuid() != 0:
        print("устанавливает root")
        return 1

    сказать(f"источник {ИСТОЧНИК}")
    установить_файлы()
    создать_каталоги()
    поставить_юниты()
    отчёт = самопроверка()

    сказать("проверка установленной копии")
    проверки = проверить_установленное()
    отказы = [п for п in проверки if not п["ok"]]
    for п in проверки:
        сказать(("  ок      " if п["ok"] else "  ОТКАЗ   ") + п["check"]
                + (f" — {п['detail']}" if п["detail"] else ""))
    if отказы:
        сказать(f"INSTALL_FAILED: отказов {len(отказы)}")
        return 1

    if args.install_only:
        сказать(f"проверок помощника {len(отчёт.get('checks', []))}, "
                f"проверок установки {len(проверки)} — все пройдены")
        сказать("выкладка НЕ запускалась: ни заявки, ни отрисовки, ни переключения")
        сказать(f"очередь заявок:  {БАЗА / 'requests'} (пишет claude)")
        сказать(f"результаты:      {БАЗА / 'results'}")
        сказать(f"журналы:         {БАЗА / 'logs'}")
        сказать(f"состояние:       {БАЗА / 'state'}")
        print("INSTALL_ONLY=PASS")
        return 0

    if ЗАЯВКА is None:
        сказать("вшитой заявки нет: этот файл собран как устанавливающий")
        print("NO_REQUEST_EMBEDDED")
        return 2
    подать_заявку()
    выполнить(["systemctl", "start", "--no-block", "lords-deploy-broker.service"])
    сказать("приёмщик работает")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
