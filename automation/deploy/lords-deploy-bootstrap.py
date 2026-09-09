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
import time
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

#: Файлы, без которых установка бессмысленна. `lords_fence.py` попал сюда
#: после `LORDS-FENCE-FAIL-OPEN-37`: помощник и приёмщик ищут барьер рядом с
#: собой, и установка без него молча возвращает выкладку без барьера.
ОБЯЗАТЕЛЬНЫЕ_ФАЙЛЫ = ("lords-deploy-broker", "lords-deployctl", "lords_fence.py")

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
    нет = [и for и in ОБЯЗАТЕЛЬНЫЕ_ФАЙЛЫ if и not in ПОЛЕЗНАЯ_НАГРУЗКА]
    if нет:
        raise SystemExit(f"полезная нагрузка неполна, установка отменена: {нет}")
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
        # Барьер объявляет ПОДАТЕЛЬ, а не приёмщик: объявление — это «хочу вот
        # это состояние сейчас», и оно обязано вытеснить всё, что уже лежит в
        # очереди. Если бы поколение назначалось при захвате, устаревшая заявка
        # получала бы свежее поколение и барьер не значил бы ничего.
        "fence": (0o2775, claude.pw_uid, claude.pw_gid),
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



def _ctl(*argv, таймаут=1800.0) -> dict:
    готово = выполнить([sys.executable, str(LIBEXEC / "lords-deployctl"), *argv],
                       таймаут=таймаут)
    try:
        return json.loads(готово.stdout or "{}")
    except json.JSONDecodeError:
        return {"error": (готово.stdout or готово.stderr)[-800:]}


def _канареечное_окружение() -> list[str]:
    вывод = выполнить(["systemctl", "show", "-p", "Environment", "--value",
                       "lords-content-refresh.service"]).stdout
    return [ч for ч in вывод.split() if ч.startswith("LORDS_CANARY_")]


def выпустить() -> int:
    """Вся последовательность разблокировки и ровно одна заявка.

    Порядок здесь не декоративный. Таймер сначала — иначе освобождённое место
    займёт очередной цикл. Гашение раньше карантина — иначе снятый drop-in
    ничего не изменит для уже идущего прогона, который прочитал его при старте.
    Доказательство чистого окружения раньше заявки — иначе новый прогон
    унаследует чужую канарейку. Возврат таймера — только в finally, потому что
    путей выхода отсюда больше одного.
    """
    было_активен = выполнить(["systemctl", "is-active",
                              "lords-content-refresh.timer"]).stdout.strip()
    было_включён = выполнить(["systemctl", "is-enabled",
                              "lords-content-refresh.timer"]).stdout.strip()
    сказать(f"таймер до начала: {было_активен}/{было_включён}")
    итог = 1
    try:
        сказать("покой таймера")
        _ctl("timer", "stop", таймаут=120)

        текущая = выполнить(["systemctl", "show", "-p", "InvocationID", "--value",
                             "lords-content-refresh.service"]).stdout.strip()
        if текущая:
            сказать(f"гашу идущий прогон {текущая}")
            отчёт = _ctl("cancel-stuck", "--unit", "lords-content-refresh.service",
                         "--invocation", текущая, таймаут=1800)
            сказать(f"  отмена: {отчёт.get('verdict', отчёт.get('error'))}")
        else:
            сказать("прогон не идёт")

        каталог = Path("/etc/systemd/system/lords-content-refresh.service.d")
        for файл in sorted(каталог.glob("zz-canary-*.conf")):
            сумма = отпечаток(файл)
            сказать(f"карантин {файл.name} ({сумма[:12]}…)")
            отчёт = _ctl("quiesce-dropin", "--file", файл.name, "--sha256", сумма,
                         "--reason", "устаревшая канарейка: ревизия уже выложена",
                         таймаут=600)
            сказать(f"  {отчёт.get('verdict', отчёт.get('error'))}"
                    f" {отчёт.get('moved_to', '')}")

        выполнить(["systemctl", "daemon-reload"])
        остались = _канареечное_окружение()
        if остались:
            сказать(f"в конфигурации остались {остались} — заявка не подаётся")
            print("CANARY_ENV_REMAINS")
            return 1
        сказать("канареечных переменных в конфигурации нет")

        сказать("жду девяносто секунд полного простоя")
        # Занят — это не только `active`. Для работающего oneshot
        # `systemctl is-active` отвечает `activating`, и сравнение с одним
        # `active` дважды объявило занятый юнит свободным: заявка подавалась в
        # чужой прогон и присоединялась к нему вместо запуска своей.
        занятые = ("active", "activating", "deactivating", "reloading")
        подряд = 0
        while подряд < 90:
            состояние = выполнить(["systemctl", "is-active",
                                   "lords-content-refresh.service"]).stdout.strip()
            подряд = 0 if состояние in занятые else подряд + 10
            time.sleep(10)
        сказать("простой подтверждён")

        if ЗАЯВКА is None:
            сказать("вшитой заявки нет")
            print("NO_REQUEST_EMBEDDED")
            return 2

        # Барьер объявляется ДО постановки в очередь: заявка обязана нести
        # поколение, а поколение обязано существовать раньше заявки. Обратный
        # порядок означал бы заявку без барьера — то есть без защиты.
        sys.path.insert(0, "/home/claude/wt-integration-28")
        from automation.deploy import lords_fence as барьер_мод
        объявленный = барьер_мод.объявить(
            ЗАЯВКА["sites"][0], ЗАЯВКА["revision"], ЗАЯВКА["artifact_sha256"],
            reason=f"bootstrap --release {ЗАЯВКА['deployment_id']}")
        сказать(f"барьер {объявленный.site}: поколение {объявленный.generation}, "
                f"ревизия {объявленный.desired_revision[:12]}")
        ЗАЯВКА["generation"] = объявленный.generation
        подать_заявку()
        выполнить(["systemctl", "start", "lords-deploy-broker.path"])
        выполнить(["systemctl", "start", "--no-block", "lords-deploy-broker.service"])
        сказать(f"заявка {ЗАЯВКА['deployment_id']} подана; выкладка идёт в приёмщике")
        print("RELEASE_STARTED")
        итог = 0
    finally:
        # Таймер возвращается на любом пути выхода: остановленный, он замораживает
        # каталог у всех трёх витрин, и заметно это только через часы.
        if было_включён == "enabled":
            выполнить(["systemctl", "start", "lords-content-refresh.timer"])
        сказать("таймер обновления: "
                + выполнить(["systemctl", "is-active",
                             "lords-content-refresh.timer"]).stdout.strip()
                + "/" + выполнить(["systemctl", "is-enabled",
                                   "lords-content-refresh.timer"]).stdout.strip())
    return итог


def main() -> int:
    р = argparse.ArgumentParser(description="установка приёмщика выкладки Lords")
    р.add_argument("--install-only", action="store_true",
                   help="поставить и проверить, ничего не выкладывая")
    р.add_argument("--deploy", action="store_true",
                   help="поставить и подать вшитую заявку (нужна вшитая заявка)")
    р.add_argument("--cancel-stuck", action="store_true",
                   help="поставить и адресно погасить зависший прогон обновления")
    р.add_argument("--release", action="store_true",
                   help="полная последовательность: покой таймера, гашение "
                        "застоя, карантин устаревших канареечных drop-in, "
                        "доказательство чистого окружения, простой и одна заявка")
    args = р.parse_args()
    if not (args.install_only or args.deploy or args.cancel_stuck or args.release):
        print("укажите --install-only, --cancel-stuck, --release или --deploy")
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

    if args.release:
        return выпустить()

    if args.cancel_stuck:
        # Одна команда доводит дело до конца: ставит помощника с глаголом
        # отмены и тут же гасит именно тот прогон, который сейчас идёт.
        # Последовательность из двух ручных действий здесь была бы хуже: между
        # ними InvocationID сменится, и вторая команда промахнётся.
        текущая = выполнить(["systemctl", "show", "-p", "InvocationID", "--value",
                             "lords-content-refresh.service"]).stdout.strip()
        if not текущая:
            сказать("прогон обновления не идёт: гасить нечего")
            print("NOTHING_TO_CANCEL")
            return 0
        сказать(f"гашу прогон InvocationID={текущая}")
        готово = выполнить([sys.executable, str(LIBEXEC / "lords-deployctl"),
                            "cancel-stuck", "--unit", "lords-content-refresh.service",
                            "--invocation", текущая], таймаут=1800)
        print(готово.stdout.strip() or готово.stderr.strip()[:2000])
        try:
            отчёт = json.loads(готово.stdout or "{}")
        except json.JSONDecodeError:
            отчёт = {}
        вердикт = отчёт.get("verdict", "CANCEL_FAILED")
        сказать(f"итог отмены: {вердикт}")
        сказать(f"очередь заявок: {БАЗА / 'requests'} (пишет claude)")
        print(вердикт)
        return 0 if вердикт in ("STALE_RENDER_CANCELLED_NO_CHANGE", "already_gone",
                                "not_stale") else 1

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
