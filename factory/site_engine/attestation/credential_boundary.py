"""Граница учётных данных Templates: снятие на хосте и проверка правила.

Разделены намеренно и по одной причине: снять снимок можно только там, где
работает юнит, а проверить правило можно где угодно. Смешение этих двух вещей
и было прежним дефектом — набор `tests/tplr2` утверждал о СЕГОДНЯШНЕМ юните на
машине, где юнита нет, и там не выполнялся вовсе.

Теперь:

* `снять` работает только на хосте и честно отказывает, если systemd или юнита
  нет. Отсутствие доступа — `ДоступНедоступен`, а не пустой снимок: пустой
  снимок прошёл бы проверку, ничего не измерив;
* `проверить` — чистая функция над снимком. Её проверяет герметичный CI на
  версионированных fixture: и на годном снимке, и на испорченных.

Значения секретов сюда не попадают ни на одном пути. `secrets_in_env` хранит
ИМЕНА переменных, `process_args` — строку аргументов, в которой наличие слова
«token» и есть нарушение; сам секрет для этого читать не требуется.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

ВЕРСИЯ_СНИМКА = "credential-boundary/1.0.0"

#: Юнит, чья граница проверяется.
ЮНИТ = "templates-cp-consumer.service"

#: Учётная запись, под которой юнит обязан работать.
УЧЁТНАЯ_ЗАПИСЬ = "templates-cp"

#: Общий env-файл, который юниту читать нельзя.
ОБЩИЙ_ENV = "control-api.env"

#: Запреты, каждый из которых обязан действовать.
ЗАПРЕТЫ = ("approval_private_key", "credentials_dir", "sudo",
           "site_unit_restart", "operator_home", "docker")

#: Слова, наличие которых в аргументах процесса само по себе является утечкой:
#: аргументы видны всем, кто может читать /proc.
ОПАСНЫЕ_В_АРГУМЕНТАХ = ("token", "key=", "secret", "bearer")

#: То же для потомков, но без `key=`: у дочерних процессов эта подстрока
#: встречается в безобидных путях, и ловить ею — значит ловить шум.
ОПАСНЫЕ_У_ПОТОМКОВ = ("token", "secret", "bearer")

#: Единственная роль постоянной личности Templates.
РОЛЬ_TEMPLATES = "proposer"

#: Действия, запрещённые актору-модели.
ЗАПРЕЩЕНО_МОДЕЛИ = ("approve", "apply", "rollback")

КОРЕНЬ = Path(__file__).resolve().parents[3]
СХЕМА = КОРЕНЬ / "schemas/credential-boundary.schema.json"


class ДоступНедоступен(RuntimeError):
    """Снимок снять нечем: нет systemd, нет юнита, нет прав."""


class СнимокНевалиден(ValueError):
    """Документ не является снимком границы объявленной формы."""


# --------------------------------------------------------------------- разбор


def _валидатор():
    from jsonschema import Draft202012Validator, FormatChecker
    схема = json.loads(СХЕМА.read_text(encoding="utf-8"))
    return Draft202012Validator(схема, format_checker=FormatChecker())


def разобрать(сырое: str | bytes | dict[str, Any]) -> dict[str, Any]:
    """Разобрать снимок и проверить его форму."""
    if isinstance(сырое, str | bytes):
        try:
            снимок = json.loads(сырое)
        except ValueError as ош:
            raise СнимокНевалиден(f"снимок не разбирается как JSON: {ош}") from ош
    else:
        снимок = сырое
    ошибки = sorted(_валидатор().iter_errors(снимок), key=lambda о: list(о.path))
    if ошибки:
        путь = "/".join(str(ч) for ч in ошибки[0].path) or "<корень>"
        raise СнимокНевалиден(f"{путь}: {ошибки[0].message}")
    return снимок


# -------------------------------------------------------------------- правило


def проверить(снимок: dict[str, Any]) -> list[str]:
    """Нарушения границы. Пустой список означает «нарушений не найдено».

    Формулировки нарушений — те же утверждения, что прежде стояли в
    `tests/tplr2`, слово в слово по смыслу. Изменилось одно: они больше не
    привязаны к тому, запущен ли pytest на хосте с этим юнитом.
    """
    нарушения: list[str] = []

    if снимок["user"] != УЧЁТНАЯ_ЗАПИСЬ:
        нарушения.append(
            f"служба работает под {снимок['user']!r}, а не под собственной "
            f"учётной записью {УЧЁТНАЯ_ЗАПИСЬ!r}")
    if снимок["active_state"] != "active":
        нарушения.append(f"юнит в состоянии {снимок['active_state']!r}")

    if снимок["shared_env_readers"] != 0:
        нарушения.append(
            f"общий env читают {снимок['shared_env_readers']} посторонних юнитов")
    if ОБЩИЙ_ENV in снимок["environment_files"]:
        нарушения.append(f"юниту доступен общий {ОБЩИЙ_ENV}")

    if снимок["foreign_credential_refs"]:
        нарушения.append(
            f"доступны чужие credential: {снимок['foreign_credential_refs']}")
    if снимок["secrets_in_env"]:
        нарушения.append(
            f"секреты объявлены в окружении: {снимок['secrets_in_env']}")

    аргументы = снимок["process_args"].lower()
    for опасное in ОПАСНЫЕ_В_АРГУМЕНТАХ:
        if опасное in аргументы:
            нарушения.append(f"в аргументах процесса встречается {опасное!r}")
    for строка in снимок["child_process_args"]:
        низ = строка.lower()
        for опасное in ОПАСНЫЕ_У_ПОТОМКОВ:
            if опасное in низ:
                нарушения.append(
                    f"в аргументах потомка встречается {опасное!r}")

    for запрет in ЗАПРЕТЫ:
        if снимок["denials"].get(запрет) is not True:
            нарушения.append(f"запрет {запрет} не действует")

    роли = set(снимок["changeset_roles_templates"])
    if роли != {РОЛЬ_TEMPLATES}:
        нарушения.append(
            f"роли Templates {sorted(роли)}: постоянная личность предлагает "
            "и не более того")

    запрещено = set(снимок["model_forbidden_actions"])
    не_запрещены = sorted(set(ЗАПРЕЩЕНО_МОДЕЛИ) - запрещено)
    if не_запрещены:
        нарушения.append(f"модели не запрещены действия: {не_запрещены}")

    return нарушения


# ---------------------------------------------------------------- снятие (host)


def _systemctl(*аргументы: str) -> str:
    двоичный = shutil.which("systemctl")
    if двоичный is None:
        raise ДоступНедоступен("systemctl не найден: снимать границу нечем")
    п = subprocess.run([двоичный, *аргументы], capture_output=True,
                       text=True, timeout=60)
    if п.returncode != 0:
        raise ДоступНедоступен(
            f"systemctl {' '.join(аргументы)} → {п.returncode}: "
            f"{(п.stderr or п.stdout).strip()[:300]}")
    return п.stdout


def _свойства(юнит: str, *имена: str) -> dict[str, str]:
    вывод = _systemctl("show", юнит, "--property=" + ",".join(имена))
    свойства: dict[str, str] = {}
    for строка in вывод.splitlines():
        if "=" in строка:
            ключ, _, значение = строка.partition("=")
            свойства[ключ] = значение
    return свойства


def снять(*, юнит: str = ЮНИТ) -> dict[str, Any]:
    """Снимок живого юнита. Работает только на хосте, где юнит существует.

    Мягкой деградации здесь нет по той же причине, по которой её нет в
    остальном host-контуре: снимок, собранный из умолчаний, прошёл бы проверку
    и сообщил бы о границе ровно ничего.
    """
    from factory.site_engine.changeset import model as M

    свойства = _свойства(
        юнит, "User", "ActiveState", "EnvironmentFiles", "LoadCredential",
        "ExecStart", "MainPID")
    if not свойства.get("ActiveState"):
        raise ДоступНедоступен(f"юнит {юнит} на этом хосте не объявлен")

    env_файлы = [ч.split()[0].lstrip("-") for ч in
                 свойства.get("EnvironmentFiles", "").split() if ч.strip()]
    свои = [ч for ч in свойства.get("LoadCredential", "").split() if ч.strip()]
    чужие = [ч for ч in свои if not ч.startswith(("templates-", "cp-"))]

    аргументы = свойства.get("ExecStart", "")
    потомки = _потомки(свойства.get("MainPID", "0"))

    снимок = {
        "snapshot_version": ВЕРСИЯ_СНИМКА,
        "unit": юнит,
        "user": свойства.get("User", ""),
        "active_state": свойства.get("ActiveState", ""),
        "shared_env_readers": _читатели_общего_env(),
        "environment_files": env_файлы,
        "foreign_credential_refs": чужие,
        "secrets_in_env": _секреты_в_окружении(юнит),
        "process_args": аргументы,
        "child_process_args": потомки,
        "denials": {з: _запрет_действует(з, юнит) for з in ЗАПРЕТЫ},
        "changeset_roles_templates": sorted(M.роли_службы("templates")),
        "model_forbidden_actions": sorted(ЗАПРЕЩЕНО_МОДЕЛИ),
    }
    return разобрать(снимок)


def _читатели_общего_env() -> int:
    """Сколько юнитов, кроме владельца, объявили общий env-файл."""
    вывод = _systemctl("show", "*.service", "--property=Id,EnvironmentFiles")
    читатели = 0
    текущий = ""
    for строка in вывод.splitlines():
        if строка.startswith("Id="):
            текущий = строка[3:]
        elif (строка.startswith("EnvironmentFiles=") and ОБЩИЙ_ENV in строка
              and текущий != "control-api.service"):
            читатели += 1
    return читатели


def _секреты_в_окружении(юнит: str) -> list[str]:
    """ИМЕНА переменных, похожих на секреты. Значения не читаются."""
    свойства = _свойства(юнит, "Environment")
    подозрительные = []
    for пара in свойства.get("Environment", "").split():
        имя = пара.split("=", 1)[0]
        if any(с in имя.lower() for с in ("token", "secret", "password", "key")):
            подозрительные.append(имя)
    return sorted(подозрительные)


def _потомки(main_pid: str) -> list[str]:
    if not main_pid.isdigit() or main_pid == "0":
        return []
    п = subprocess.run(["ps", "--ppid", main_pid, "-o", "args="],
                       capture_output=True, text=True, timeout=60)
    return [с.strip() for с in п.stdout.splitlines() if с.strip()]


def _запрет_действует(запрет: str, юнит: str) -> bool:
    """Действует ли конкретный запрет на живом юните.

    Проверяется настройка юнита, а не попытка нарушения: пробовать `sudo` от
    имени службы значит выяснять запрет ценой его нарушения там, где он вдруг
    не действует.
    """
    свойства = _свойства(
        юнит, "LoadCredential", "InaccessiblePaths", "ReadWritePaths",
        "ProtectHome", "NoNewPrivileges", "PrivateDevices", "DeviceAllow")
    credential = свойства.get("LoadCredential", "")
    if запрет == "approval_private_key":
        return "approval-signing-key" not in credential
    if запрет == "credentials_dir":
        return "ProtectHome" in свойства and свойства["ProtectHome"] in (
            "yes", "read-only", "tmpfs")
    if запрет == "sudo":
        return свойства.get("NoNewPrivileges") == "yes"
    if запрет == "site_unit_restart":
        return "site-" not in свойства.get("ReadWritePaths", "")
    if запрет == "operator_home":
        return свойства.get("ProtectHome") in ("yes", "read-only", "tmpfs")
    if запрет == "docker":
        return "/run/docker.sock" not in свойства.get("ReadWritePaths", "")
    raise ДоступНедоступен(f"запрет {запрет} нечем проверить")
