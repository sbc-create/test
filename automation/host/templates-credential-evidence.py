#!/usr/bin/env python3
"""Снимок границы учётных данных Templates. Значения не читаются и не печатаются.

Измеряется живой юнит и учётная запись службы: что юнит объявляет, что
процесс фактически видит и чего он не может. Всё — только чтение.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

ЮНИТ = "templates-cp-consumer"
ЗАПРЕЩЕНО_В_ОКРУЖЕНИИ = ("AUDIT_TOKEN_", "CHANGESET_APPROVAL_KEY",
                         "SITE_ENGINE_CONTROL_TOKENS", "APPROVAL_CALLER")
ЧУЖИЕ_CREDENTIALS = (
    "approval-signing-key", "approval-caller-control-api",
    "approval-caller-changeset-worker", "approval-caller-fingerprints",
    "site-engine-control-tokens", "audit-token-architect",
    "audit-token-audit-bridge", "audit-token-changeset-worker",
    "audit-token-registry", "audit-token-seo", "audit-token-content",
    "audit-token-monitoring", "audit-token-backup", "audit-token-integrations",
    "audit-token-qwen", "audit-token-fingerprints")


def показать(*ключи):
    вывод = subprocess.run(["systemctl", "show", ЮНИТ, *[f"-p{к}" for к in ключи]],
                           capture_output=True, text=True).stdout
    return dict(с.split("=", 1) for с in вывод.splitlines() if "=" in с)


def как(пользователь, команда):
    import pwd
    try:
        з = pwd.getpwnam(пользователь)
    except KeyError:
        return -1
    try:
        r = subprocess.run(
            ["setpriv", "--reuid", str(з.pw_uid), "--regid", str(з.pw_gid),
             "--clear-groups", "--", "/bin/sh", "-c", команда],
            capture_output=True, text=True, timeout=15, stdin=subprocess.DEVNULL)
        return r.returncode
    except subprocess.TimeoutExpired:
        return 124


итог = {"unit": ЮНИТ}
св = показать("MainPID", "User", "EnvironmentFiles", "ActiveState")
итог["user"] = св.get("User")
итог["active_state"] = св.get("ActiveState")
итог["environment_files"] = св.get("EnvironmentFiles", "")
итог["shared_env_readers"] = int("control-api.env" in св.get("EnvironmentFiles", ""))

pid = св.get("MainPID", "0")
имена, видимые, аргументы, потомки = [], [], "", []
if pid and pid != "0":
    сырое = open(f"/proc/{pid}/environ", "rb").read().decode("utf-8", "replace")
    окр = dict(з.split("=", 1) for з in сырое.split("\0") if "=" in з)
    имена = sorted(окр)
    кат = окр.get("CREDENTIALS_DIRECTORY")
    видимые = sorted(os.listdir(кат)) if кат and os.path.isdir(кат) else []
    итог["credentials_directory_present"] = bool(кат)
    аргументы = open(f"/proc/{pid}/cmdline", "rb").read().decode(
        "utf-8", "replace").replace("\0", " ").strip()
    дети = subprocess.run(["pgrep", "-P", pid], capture_output=True,
                          text=True).stdout.split()
    for д in дети:
        try:
            потомки.append(open(f"/proc/{д}/cmdline", "rb").read().decode(
                "utf-8", "replace").replace("\0", " ").strip())
        except OSError:
            pass

итог["env_var_names"] = имена
итог["secrets_in_env"] = sorted(
    и for и in имена if any(и.startswith(п) or и == п
                            for п in ЗАПРЕЩЕНО_В_ОКРУЖЕНИИ))
итог["visible_credentials"] = видимые
итог["foreign_credential_refs"] = sorted(set(видимые) & set(ЧУЖИЕ_CREDENTIALS))
итог["long_lived_credential_refs"] = [и for и in видимые
                                      if и.startswith("audit-token-templates")]
итог["process_args"] = аргументы
итог["child_process_args"] = потомки
итог["denials"] = {
    "approval_private_key": как("templates-cp",
        "cat /etc/site-factory/credentials/approval-signing-key") != 0,
    "credentials_dir": как("templates-cp", "ls /etc/site-factory/credentials") != 0,
    "sudo": как("templates-cp", "sudo -n true") != 0,
    "site_unit_restart": как("templates-cp",
        "systemctl restart lords-01.service") != 0,
    "operator_home": как("templates-cp", "ls /home/claude") != 0,
    "docker": как("templates-cp", "docker ps") != 0,
}

корень = os.path.realpath("/srv/site-factory/control-api/current")
sys.path.insert(0, корень)
try:
    from factory.site_engine.audit import ledger_store as _ls
    from factory.site_engine.changeset import model as _m
    итог["ledger_rights_templates"] = sorted(_ls.ПРАВА_СЛУЖБ.get("templates", []))
    итог["changeset_roles_templates"] = sorted(_m.ПРАВА.get("templates", []))
    итог["model_forbidden_actions"] = sorted(_m.ЗАПРЕЩЕНО_МОДЕЛИ)
    итог["template_release_owner"] = _m.ЕДИНСТВЕННЫЙ_ПИСАТЕЛЬ.get("template.release")
    итог["template_build_owner"] = _m.ЕДИНСТВЕННЫЙ_ПИСАТЕЛЬ.get("template.build")
except Exception as ош:
    итог["matrix_error"] = f"{type(ош).__name__}: {ош}"

print(json.dumps(итог, ensure_ascii=False, indent=1))
