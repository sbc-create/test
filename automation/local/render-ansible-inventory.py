#!/usr/bin/env python3
"""Инвентарь Ansible из `inventory/ssh-hosts.yaml` — то, что обещано комментарием.

`automation/ansible/inventory/hosts.yml` начинается словами «Инвентарь Ansible
генерируется из inventory/ssh-hosts.yaml фабрики», но генератора не было: файл
держали пустым вручную. Из-за этого ключ, объявленный в реестре через
`ssh_key_secret_ref`, до ansible не доходил ВООБЩЕ — адаптер проверяет его
наличие и больше ничего с ним не делает.

Почему путь ключа обязан попадать в ФАЙЛ, а не в командную строку: обращение к
`~/.ssh/` в любой команде оболочки запрещено правилом G-SECRET, и обходить его
нельзя. Declarative-слой для этого и существует — путь живёт в инвентаре,
команда остаётся чистой.

Куда пишем. По умолчанию `var/ansible/hosts.yml` — рабочий каталог, который не
версионируется: сгенерированный файл содержит ПУТЬ к ключу, и в git ему не
место (значение ключа не содержит и содержать не может).

Отказы (код 1), а не тихая починка:

* `deploy_user: root` — least-privilege нарушен;
* нет `known_hosts_entry_ref` или файла по нему — пиннинг host key обязателен;
* `ssh_key_secret_ref` пуст, неизвестной схемы, либо `env:`-переменная не
  задана, либо `file:`-путь не существует;
* `strict_host_key_checking` не `yes`.

Значение ключа не читается и не печатается: инструменту нужен только путь.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import yaml

КОРЕНЬ = Path(__file__).resolve().parents[2]
РЕЕСТР = КОРЕНЬ / "inventory" / "ssh-hosts.yaml"
ПО_УМОЛЧАНИЮ = КОРЕНЬ / "var" / "ansible" / "hosts.yml"
#: Окружение → группа инвентаря. Хост без окружений не попадает ни в одну:
#: пустая группа лучше догадки о назначении узла.
ГРУППЫ = {"staging": "dle_staging", "production": "dle_production"}


class Отказ(Exception):
    """Запись реестра не годится для подключения — с названной причиной."""


def путь_ключа(запись: dict) -> str:
    ссылка = str(запись.get("ssh_key_secret_ref") or "").strip()
    if not ссылка:
        raise Отказ("ssh_key_secret_ref не задан")
    if ссылка.startswith("env:"):
        имя = ссылка.split(":", 1)[1]
        значение = os.environ.get(имя, "")
        if not значение:
            raise Отказ(f"переменная {имя} не задана в окружении")
        # В env лежит ПУТЬ к ключу (так же, как в адаптере фабрики): само
        # значение ключа через переменную не передаётся.
        return значение
    if ссылка.startswith("file:"):
        п = Path(ссылка.split(":", 1)[1]).expanduser()
        if not п.exists():
            raise Отказ(f"файла ключа {п} нет")
        return str(п)
    raise Отказ(f"неизвестная схема ssh_key_secret_ref: {ссылка.split(':', 1)[0]}")


def проверить(запись: dict) -> str:
    ref = str(запись.get("ref") or "")
    if not ref:
        raise Отказ("у записи нет ref")
    if str(запись.get("deploy_user") or "") == "root":
        raise Отказ(f"{ref}: deploy_user = root, least-privilege нарушен")
    for поле in ("hostname", "deploy_user"):
        if not запись.get(поле):
            raise Отказ(f"{ref}: не заполнено {поле}")
    пин = str(запись.get("known_hosts_entry_ref") or "")
    if not пин:
        raise Отказ(f"{ref}: нет known_hosts_entry_ref — пиннинг host key обязателен")
    if not (КОРЕНЬ / пин).is_file():
        raise Отказ(f"{ref}: файла пиннинга {пин} нет")
    строгость = запись.get("strict_host_key_checking")
    if строгость not in (True, "yes", "Yes"):
        raise Отказ(f"{ref}: strict_host_key_checking = {строгость!r}, "
                    "отключать проверку ключа сервера запрещено")
    return путь_ключа(запись)


def инвентарь(записи: list[dict]) -> tuple[dict, list[str]]:
    дерево: dict = {"all": {"children": {г: {"hosts": {}} for г in ГРУППЫ.values()}}}
    беды: list[str] = []
    for запись in записи:
        try:
            ключ = проверить(запись)
        except Отказ as ош:
            беды.append(str(ош))
            continue
        ref = запись["ref"]
        узел = {
            "ansible_host": запись["hostname"],
            "ansible_port": int(запись.get("port") or 22),
            "ansible_user": запись["deploy_user"],
            "ansible_ssh_private_key_file": ключ,
            "ansible_connection": "ssh",
            # Проверка ключа сервера включена и здесь, а не только в адаптере:
            # инвентарь могут использовать ad-hoc командой.
            "ansible_ssh_common_args":
                f"-o UserKnownHostsFile={КОРЕНЬ / запись['known_hosts_entry_ref']} "
                f"-o StrictHostKeyChecking=yes -o BatchMode=yes "
                f"-o ConnectTimeout=10",
        }
        окружения = запись.get("environments") or []
        if not окружения:
            беды.append(f"{ref}: не названо ни одного окружения — группа не выбрана")
            continue
        for о in окружения:
            группа = ГРУППЫ.get(str(о))
            if not группа:
                беды.append(f"{ref}: неизвестное окружение {о!r}")
                continue
            дерево["all"]["children"][группа]["hosts"][ref] = узел
    return дерево, беды


def main() -> int:
    р = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--registry", default=str(РЕЕСТР))
    р.add_argument("--out", default=str(ПО_УМОЛЧАНИЮ))
    р.add_argument("--check", action="store_true",
                   help="только проверить записи, ничего не писать")
    а = р.parse_args()

    реестр = Path(а.registry)
    if not реестр.is_file():
        print(f"ОТКАЗ: нет {реестр}", file=sys.stderr)
        return 2
    данные = yaml.safe_load(реестр.read_text(encoding="utf-8")) or {}
    записи = данные.get("hosts") or []
    if not записи:
        print("в реестре нет ни одного SSH-хоста: инвентарь остаётся пустым, "
              "удалённый доступ закрыт целиком")
        return 1
    дерево, беды = инвентарь(записи)
    узлов = sum(len(г["hosts"]) for г in дерево["all"]["children"].values())
    for б in беды:
        print(f"   [отказ] {б}")
    print(f"записей в реестре: {len(записи)}; узлов в инвентаре: {узлов}; "
          f"отказов: {len(беды)}")
    if беды:
        return 1
    if а.check:
        print("проверка без записи: инвентарь не обновлялся")
        return 0
    выход = Path(а.out)
    выход.parent.mkdir(parents=True, exist_ok=True)
    шапка = ("# СГЕНЕРИРОВАНО automation/local/render-ansible-inventory.py\n"
             "# Источник: inventory/ssh-hosts.yaml. Руками не правится.\n"
             "# Содержит ПУТЬ к ключу, поэтому лежит в var/ и не версионируется.\n")
    выход.write_text(шапка + yaml.safe_dump(дерево, allow_unicode=True,
                                            sort_keys=False), encoding="utf-8")
    print(f"инвентарь: {выход}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
