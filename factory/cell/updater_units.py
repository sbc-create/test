"""Юниты обработчика обновлений — из выпуска, проверенные, вместе с выпуском.

Зачем
-----
Витрину ячейки исполнитель переводит на новый выпуск сам (`promote`
переписывает её юнит из шаблона). Обработчик обновлений данных — вторая
половина сайта — в выпуск до этого не входил вовсе: его юнит и таймер ставил
владелец руками (`sudo cp deploy/...`), один раз. Измерено 2026-10-05 на
animedia.icu: установленный 27.09 юнит исполнял `/srv/animedia-icu/app`
(sha 3374a18b…, 1527 строк), а витрина — `current` (выпуск 2bb2091, sha
e8c9b966…, 1767 строк). Шагов карты сайта и тематического допуска в
исполняемом файле не было, и каждый прогон заканчивался «проблем: 0»: старый
код не знает о шагах, которых в нём нет. Исправленный юнит лежал в выпуске
с 01.10, но ставить его было некому.

Что делает модуль
-----------------
Реестр объявляет обработчик сайта (`runtime.updater`): имена юнита и таймера
и допустимые учётные данные. Исполнитель при КАЖДОМ переводе витрины на выпуск
(`promote`: первичная установка, обновление и возврат прежнего коммита) берёт
эти файлы из `current/deploy/` — то есть из распакованного артефакта,
digest которого сверен при выпуске, — проверяет их и ставит.

Проверка закрытая, потому что каталог выпуска принадлежит учётной записи
сайта: без неё запись в этот каталог была бы равна командам от root.
Допускаются только перечисленные директивы; исполняемый файл — только внутри
`current`; пользователь — только учётная запись сайта; запись — только в его
каталог данных; учётные данные — только объявленные в реестре.

Если файл выпуска не проходит проверку, установленный юнит не трогается.
Если и установленный юнит не указывает на `current`, итог — отказ: сайт с
обработчиком, исполняющим чужой код, выпуском не считается.
"""
from __future__ import annotations

import hashlib
import os
import re
import shlex
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: Директивы, которые допускаются в юните обработчика. Всё прочее — отказ.
#: `User`/`Group` проверяются отдельно по значению, `ExecStart` — по пути.
РАЗРЕШЕНО_СЛУЖБА = {
    "Unit": {"Description", "Documentation", "After", "Wants", "Requires"},
    "Service": {"Type", "User", "Group", "WorkingDirectory", "ExecStart",
                "LoadCredential", "SuccessExitStatus", "TimeoutStartSec",
                "NoNewPrivileges", "PrivateTmp", "ProtectSystem", "ProtectHome",
                "ReadWritePaths", "ProtectKernelTunables", "ProtectControlGroups",
                "RestrictSUIDSGID", "Environment", "Nice", "IOSchedulingClass",
                "ProtectKernelModules", "ReadOnlyPaths"},
    "Install": {"WantedBy"},
}
РАЗРЕШЕНО_ТАЙМЕР = {
    "Unit": {"Description", "Documentation"},
    "Timer": {"OnBootSec", "OnUnitActiveSec", "OnCalendar", "Persistent",
              "RandomizedDelaySec", "AccuracySec", "Unit"},
    "Install": {"WantedBy"},
}
#: Значения, без которых юнит не ставится: обработчик работает без root-прав
#: и пишет только в свой каталог данных.
ОБЯЗАТЕЛЬНО = {"Type": "oneshot", "NoNewPrivileges": "true",
               "ProtectSystem": "strict"}


class UpdaterUnitRefused(Exception):
    """Юнит обработчика не прошёл проверку."""


@dataclass
class Юнит:
    """Разобранный файл systemd: секция -> [(ключ, значение)]."""
    текст: str
    секции: dict[str, list[tuple[str, str]]] = field(default_factory=dict)

    def все(self, секция: str, ключ: str) -> list[str]:
        return [з for к, з in self.секции.get(секция, []) if к == ключ]

    def одно(self, секция: str, ключ: str) -> str:
        значения = self.все(секция, ключ)
        return значения[-1] if значения else ""

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.текст.encode("utf-8")).hexdigest()


def разобрать(текст: str) -> Юнит:
    """Разбор INI systemd с продолжением строки через `\\`."""
    юнит = Юнит(текст=текст)
    секция = ""
    накопленное = ""
    for сырая in текст.splitlines():
        строка = сырая.rstrip()
        if накопленное:
            строка = накопленное + " " + строка.strip()
            накопленное = ""
        if строка.endswith("\\"):
            накопленное = строка[:-1].rstrip()
            continue
        чистая = строка.strip()
        if not чистая or чистая.startswith(("#", ";")):
            continue
        if чистая.startswith("[") and чистая.endswith("]"):
            секция = чистая[1:-1]
            юнит.секции.setdefault(секция, [])
            continue
        if "=" not in чистая or not секция:
            raise UpdaterUnitRefused(f"строка вне формата systemd: {чистая[:80]!r}")
        ключ, значение = чистая.split("=", 1)
        юнит.секции[секция].append((ключ.strip(), значение.strip()))
    if накопленное:
        raise UpdaterUnitRefused("файл оборван на продолжении строки")
    return юнит


def _внутри(путь: str, корень: Path) -> bool:
    п = os.path.normpath(путь)
    к = os.path.normpath(str(корень))
    return п == к or п.startswith(к + os.sep)


def проверить_службу(текст: str, *, account: str, current: Path, data: Path,
                     учётные: set[str] | frozenset[str] = frozenset()) -> Юнит:
    """Юнит обработчика или исключение с причиной.

    `current` — ссылка на выложенный выпуск (`/srv/<учётка>/current`), а не
    каталог конкретного выпуска: иначе следующий выпуск снова оставил бы
    обработчик на прежнем коде.
    """
    юнит = разобрать(текст)
    беды: list[str] = []
    for секция, пары in юнит.секции.items():
        разрешено = РАЗРЕШЕНО_СЛУЖБА.get(секция)
        if разрешено is None:
            беды.append(f"секция [{секция}] не допускается")
            continue
        for ключ, _ in пары:
            if ключ not in разрешено:
                беды.append(f"[{секция}] {ключ} не допускается")
    for ключ, надо in ОБЯЗАТЕЛЬНО.items():
        if юнит.одно("Service", ключ).lower() != надо:
            беды.append(f"{ключ} обязан быть {надо}")
    if юнит.одно("Service", "User") != account:
        беды.append(f"User обязан быть {account}")
    if юнит.одно("Service", "Group") not in ("", account):
        беды.append(f"Group обязан быть {account}")
    рабочий = юнит.одно("Service", "WorkingDirectory")
    if not _внутри(рабочий, current):
        беды.append(f"WorkingDirectory {рабочий!r} вне {current}")
    запуски = юнит.все("Service", "ExecStart")
    if len(запуски) != 1:
        беды.append("ExecStart обязан быть ровно один")
    else:
        запуск = запуски[0]
        if запуск[:1] in "@-:+!":
            беды.append("префиксы ExecStart (@ - : + !) не допускаются")
        try:
            слова = shlex.split(запуск)
        except ValueError as ош:
            слова = []
            беды.append(f"ExecStart не разбирается: {ош}")
        if слова:
            интерпретатор = слова[0]
            if not интерпретатор.startswith("/usr/bin/python3"):
                беды.append(f"интерпретатор {интерпретатор!r} не допускается")
            сценарий = слова[1] if len(слова) > 1 else ""
            if not сценарий.endswith(".py") or not _внутри(сценарий, current):
                беды.append(f"исполняемый файл {сценарий!r} вне {current}")
            if any(s.startswith("-") and s in ("-c", "-m") for s in слова[1:2]):
                беды.append("python -c/-m не допускается")
    for значения in юнит.все("Service", "ReadWritePaths"):
        for путь in значения.split():
            if not _внутри(путь.lstrip("-"), data):
                беды.append(f"ReadWritePaths {путь!r} вне {data}")
    for значение in юнит.все("Service", "LoadCredential"):
        if значение not in учётные:
            беды.append(f"LoadCredential {значение.split(':', 1)[0]!r} не объявлен в реестре")
    if беды:
        raise UpdaterUnitRefused("; ".join(беды))
    return юнит


def проверить_таймер(текст: str, *, служба: str) -> Юнит:
    юнит = разобрать(текст)
    беды: list[str] = []
    for секция, пары in юнит.секции.items():
        разрешено = РАЗРЕШЕНО_ТАЙМЕР.get(секция)
        if разрешено is None:
            беды.append(f"секция [{секция}] не допускается")
            continue
        for ключ, _ in пары:
            if ключ not in разрешено:
                беды.append(f"[{секция}] {ключ} не допускается")
    цель = юнит.одно("Timer", "Unit")
    if цель and цель != служба:
        беды.append(f"таймер запускает {цель!r}, а не {служба}")
    if not (юнит.все("Timer", "OnUnitActiveSec") or юнит.все("Timer", "OnCalendar")):
        беды.append("у таймера нет расписания")
    if беды:
        raise UpdaterUnitRefused("; ".join(беды))
    return юнит


@dataclass
class Объявление:
    """Что реестр говорит об обработчике сайта."""
    service: str
    timer: str
    credentials: frozenset[str]

    @classmethod
    def из_блока(cls, блок: dict[str, Any] | None) -> "Объявление | None":
        if not блок:
            return None
        служба = str(блок.get("service") or "").strip()
        таймер = str(блок.get("timer") or "").strip()
        if not служба.endswith(".service") or not таймер.endswith(".timer"):
            raise UpdaterUnitRefused(
                "runtime.updater обязан назвать service (*.service) и timer (*.timer)")
        for имя in (служба, таймер):
            if "/" in имя or имя.startswith("."):
                raise UpdaterUnitRefused(f"имя юнита {имя!r} недопустимо")
        return cls(служба, таймер,
                   frozenset(str(с) for с in (блок.get("credentials") or [])))


def сверить(объявление: Объявление, *, выпуск: Path, account: str,
            current: Path, data: Path, каталог: Path) -> dict[str, Any]:
    """Сверка без изменений: что лежит в выпуске и что установлено.

    `исполняет_current` — главный ответ: исполняет ли установленный юнит код
    выложенного выпуска. Именно его не было у animedia.icu.
    """
    итог: dict[str, Any] = {"service": объявление.service, "timer": объявление.timer}
    for вид, имя in (("service", объявление.service), ("timer", объявление.timer)):
        файл_выпуска = выпуск / "deploy" / имя
        установлен = каталог / имя
        запись: dict[str, Any] = {"release_file": str(файл_выпуска),
                                  "installed_file": str(установлен)}
        try:
            текст = файл_выпуска.read_text(encoding="utf-8")
            запись["release_sha256"] = hashlib.sha256(текст.encode()).hexdigest()
            if вид == "service":
                проверить_службу(текст, account=account, current=current, data=data,
                                 учётные=объявление.credentials)
            else:
                проверить_таймер(текст, служба=объявление.service)
            запись["release_valid"] = True
        except OSError:
            запись["release_valid"] = False
            запись["release_reason"] = "в выпуске нет файла"
        except UpdaterUnitRefused as ош:
            запись["release_valid"] = False
            запись["release_reason"] = str(ош)
        try:
            стоит = установлен.read_text(encoding="utf-8")
            запись["installed_sha256"] = hashlib.sha256(стоит.encode()).hexdigest()
            запись["installed_matches_release"] = (
                запись.get("release_sha256") == запись["installed_sha256"])
            if вид == "service":
                try:
                    проверить_службу(стоит, account=account, current=current, data=data,
                                     учётные=объявление.credentials)
                    запись["installed_valid"] = True
                except UpdaterUnitRefused as ош:
                    запись["installed_valid"] = False
                    запись["installed_reason"] = str(ош)
                юнит = разобрать(стоит)
                запись["installed_exec"] = юнит.одно("Service", "ExecStart")
                запись["installed_workdir"] = юнит.одно("Service", "WorkingDirectory")
        except OSError:
            запись["installed_sha256"] = ""
            запись["installed_matches_release"] = False
        except UpdaterUnitRefused as ош:
            запись["installed_valid"] = False
            запись["installed_reason"] = str(ош)
        итог[вид] = запись
    служба = итог["service"]
    итог["исполняет_current"] = bool(служба.get("installed_valid"))
    итог["согласован"] = bool(
        итог["исполняет_current"]
        and служба.get("installed_matches_release")
        and итог["timer"].get("installed_matches_release"))
    return итог


def план_установки(сверка: dict[str, Any]) -> dict[str, Any]:
    """Что делать: ставить из выпуска, оставить установленное или отказать."""
    служба, таймер = сверка["service"], сверка["timer"]
    if служба.get("release_valid") and таймер.get("release_valid"):
        if служба.get("installed_matches_release") and таймер.get("installed_matches_release"):
            return {"действие": "без изменений"}
        return {"действие": "установить"}
    if служба.get("installed_valid"):
        # Возврат прежнего выпуска, чей файл юнита ещё указывал на `app`:
        # установленный юнит уже исполняет `current`, то есть ровно
        # возвращаемый код. Ломать его файлом прежнего выпуска нельзя.
        return {"действие": "оставить установленный",
                "причина": служба.get("release_reason") or таймер.get("release_reason")}
    return {"действие": "отказ",
            "причина": ("ни файл выпуска, ни установленный юнит не исполняют "
                        f"выложенный код: {служба.get('release_reason')}; "
                        f"установлен: {служба.get('installed_reason') or 'нет'}")}


def установить(объявление: Объявление, *, выпуск: Path, account: str,
               current: Path, data: Path, каталог: Path,
               systemctl, метка: str | None = None) -> dict[str, Any]:
    """Поставить юниты обработчика из выпуска. Вызывается только от root.

    Прежний файл сохраняется рядом (`.bak.<время>`), запись — атомарная
    заменой. Работающий в этот момент прогон не прерывается: systemd
    дочитает его со старым кодом, следующий запуск таймера возьмёт новый.
    Двух прогонов над одними данными не бывает: oneshot-служба systemd не
    запускается повторно, пока идёт прежний, а сам обработчик держит замок
    каталога данных.
    """
    сверка = сверить(объявление, выпуск=выпуск, account=account, current=current,
                     data=data, каталог=каталог)
    план = план_установки(сверка)
    итог: dict[str, Any] = {"operation": "install_updater_units", "plan": план,
                            "before": сверка, "steps": []}
    if план["действие"] == "отказ":
        raise UpdaterUnitRefused(план["причина"])
    if план["действие"] == "установить":
        метка = метка or time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        for имя in (объявление.service, объявление.timer):
            источник = выпуск / "deploy" / имя
            цель = каталог / имя
            текст = источник.read_text(encoding="utf-8")
            if цель.is_file():
                if цель.read_text(encoding="utf-8") == текст:
                    continue
                копия = каталог / f"{имя}.bak.{метка}"
                копия.write_bytes(цель.read_bytes())
                итог["steps"].append(f"копия {копия.name}")
            врем = каталог / f".{имя}.new"
            врем.write_text(текст, encoding="utf-8")
            os.chmod(врем, 0o644)
            os.replace(врем, цель)
            итог["steps"].append(f"установлен {имя} из {источник}")
        systemctl("daemon-reload")
        итог["steps"].append("daemon-reload")
    # Таймер включается при любом исходе, кроме отказа: включение идемпотентно,
    # а выключенный таймер — это тот же молчаливый обработчик.
    вкл = systemctl("enable", "--now", объявление.timer, проверять=False)
    итог["steps"].append(f"enable --now {объявление.timer}: rc={вкл.returncode}")
    итог["after"] = сверить(объявление, выпуск=выпуск, account=account,
                            current=current, data=data, каталог=каталог)
    итог["ok"] = bool(итог["after"].get("исполняет_current"))
    return итог
