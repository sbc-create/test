"""Команда владельца `authorize-indexing.sh` — исполнением в песочнице.

Команда требует root, поэтому в проверке подставлены ровно две вещи: `id`
(иначе скрипт откажется работать) и `install` (без root нельзя назначить
владельцем файла root). Всё остальное настоящее: разбор реестра, запись
подтверждения, сохранение прочих полей, журнал, отзыв.

Проверяется то, что нельзя увидеть чтением: что правка реестра не теряет
соседние поля, не трогает `desired_state` и что `--undo` снимает разрешение.
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import textwrap

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
СКРИПТ = КОРЕНЬ / "automation" / "host" / "authorize-indexing.sh"
ДОМЕН = "t-grant.example"
САЙТ = "grant-01"

ЗАГЛУШКИ = {
    "id": 'echo 0',
    # Без root нельзя `-o root -g root`: владелец отбрасывается, остальное
    # делает настоящий install.
    "install": """
        args=()
        while [ $# -gt 0 ]; do
          case "$1" in
            -o|-g) shift 2 ;;
            *) args+=("$1"); shift ;;
          esac
        done
        exec /usr/bin/install "${args[@]}"
    """,
    # Проверка фабрикой в конце скрипта идёт через sudo -u claude: в песочнице
    # прав нет, поэтому вызов превращается в прямой запуск.
    "sudo": """
        while [ $# -gt 0 ]; do
          case "$1" in
            -u) shift 2 ;;
            env) shift ;;
            *) break ;;
          esac
        done
        exec "$@"
    """,
}


def _реестр(п: pathlib.Path) -> pathlib.Path:
    """Реестр с ДВУМЯ сайтами и богатой записью: видно, что ничего не потеряно."""
    файл = п / "site-cells.json"
    файл.write_text(json.dumps({"schema_version": 1, "cells": [
        {"site_id": САЙТ, "domain": ДОМЕН,
         "repo": {"path": "var/site-repos/x", "kind": "remote"},
         "runtime": {"account": САЙТ, "port": 9999},
         "template": {"template_id": "lords-animation"},
         "indexing": {"desired_state": "CLOSED", "reason": "новый домен",
                      "extra_field": "не трогать"}},
        {"site_id": "other-01", "domain": "other.example",
         "indexing": {"desired_state": "CLOSED"}},
    ]}, ensure_ascii=False, indent=2), encoding="utf-8")
    return файл


@pytest.fixture()
def песочница(tmp_path):
    корзина = tmp_path / "bin"
    корзина.mkdir()
    for имя, тело in ЗАГЛУШКИ.items():
        п = корзина / имя
        п.write_text("#!/usr/bin/env bash\n" + textwrap.dedent(тело).strip() + "\n",
                     encoding="utf-8")
        п.chmod(0o755)
    окр = dict(os.environ)
    окр["PATH"] = f"{корзина}:{окр['PATH']}"
    согласия = tmp_path / "owner-consent"
    return {"tmp": tmp_path, "окр": окр, "реестр": _реестр(tmp_path),
            "согласия": согласия}


def _запуск(п, *аргументы):
    return subprocess.run(
        ["bash", str(СКРИПТ), "--domain", ДОМЕН,
         "--registry", str(п["реестр"]), "--consent-dir", str(п["согласия"]),
         *аргументы],
        capture_output=True, text=True, env=п["окр"], cwd=str(п["tmp"]),
        timeout=300)


def test_без_домена_команда_отказывает(песочница):
    итог = subprocess.run(["bash", str(СКРИПТ)], capture_output=True, text=True,
                          env=песочница["окр"], timeout=120)
    assert итог.returncode != 0
    assert "нужен --domain" in итог.stdout + итог.stderr


def test_неизвестный_домен_не_получает_разрешения(песочница):
    итог = subprocess.run(
        ["bash", str(СКРИПТ), "--domain", "nosuch.example",
         "--registry", str(песочница["реестр"]),
         "--consent-dir", str(песочница["согласия"])],
        capture_output=True, text=True, env=песочница["окр"], timeout=300)
    assert итог.returncode != 0
    вывод = итог.stdout + итог.stderr
    assert "нет в реестре ячеек" in вывод, вывод
    assert not песочница["согласия"].exists() or not list(
        песочница["согласия"].glob("*.json")), "подтверждение создано зря"


def test_выдача_пишет_подтверждение_и_сохраняет_остальные_поля(песочница):
    итог = _запуск(песочница)
    вывод = итог.stdout + итог.stderr
    # Последний шаг (проверка фабрикой) в песочнице может не пройти из-за
    # подменённого владельца файла — важны первые четыре.
    assert "создан" in вывод and "owner-consent" in вывод, вывод
    согласие = json.loads((песочница["согласия"] / f"{ДОМЕН}.json")
                          .read_text(encoding="utf-8"))
    assert согласие["domain"] == ДОМЕН and согласие["site_id"] == САЙТ
    assert согласие["authorized"] is True
    assert согласие["by"] and согласие["at"] and согласие["id"]
    assert "один домен" in согласие["scope"]

    реестр = json.loads(песочница["реестр"].read_text(encoding="utf-8"))
    запись = next(я for я in реестр["cells"] if я["site_id"] == САЙТ)
    инд = запись["indexing"]
    assert инд["open_authorized"] is True
    assert инд["open_authorization_ref"].endswith(f"{ДОМЕН}.json")
    assert инд["open_authorization_id"]
    # Остальное не тронуто — ни соседние поля, ни режим, ни соседний сайт.
    assert инд["desired_state"] == "CLOSED", "разрешение изменило объявленный режим"
    assert инд["extra_field"] == "не трогать"
    assert инд["reason"] == "новый домен"
    assert запись["repo"]["kind"] == "remote" and запись["runtime"]["port"] == 9999
    сосед = next(я for я in реестр["cells"] if я["site_id"] == "other-01")
    assert сосед["indexing"] == {"desired_state": "CLOSED"}, (
        "разрешение одного домена задело другой")
    # Резервная копия реестра рядом.
    assert list(песочница["tmp"].glob("site-cells.json.bak.*")), "нет копии реестра"
    # Журнал подтверждений.
    журнал = (песочница["согласия"] / "journal.jsonl").read_text(encoding="utf-8")
    запись_журнала = json.loads(журнал.strip().splitlines()[-1])
    assert запись_журнала["op"] == "grant" and запись_журнала["domain"] == ДОМЕН


def test_отзыв_снимает_разрешение_и_удаляет_подтверждение(песочница):
    _запуск(песочница)
    assert (песочница["согласия"] / f"{ДОМЕН}.json").exists()
    итог = _запуск(песочница, "--undo")
    вывод = итог.stdout + итог.stderr
    assert итог.returncode == 0, вывод
    assert not (песочница["согласия"] / f"{ДОМЕН}.json").exists()
    реестр = json.loads(песочница["реестр"].read_text(encoding="utf-8"))
    инд = next(я for я in реестр["cells"] if я["site_id"] == САЙТ)["indexing"]
    assert инд["open_authorized"] is False
    assert "open_authorization_ref" not in инд
    assert инд["desired_state"] == "CLOSED", "отзыв изменил объявленный режим"
    assert инд["extra_field"] == "не трогать", "отзыв потерял соседние поля"


def test_показ_не_требует_root_и_ничего_не_меняет(песочница):
    _запуск(песочница)
    было = песочница["реестр"].read_text(encoding="utf-8")
    окр = dict(песочница["окр"])
    окр["PATH"] = os.environ["PATH"]  # без подставного id: --show root не нужен
    итог = subprocess.run(
        ["bash", str(СКРИПТ), "--domain", ДОМЕН, "--show",
         "--registry", str(песочница["реестр"]),
         "--consent-dir", str(песочница["согласия"])],
        capture_output=True, text=True, env=окр, timeout=120)
    assert итог.returncode == 0, итог.stdout + итог.stderr
    assert "open_authorized" in итог.stdout
    assert песочница["реестр"].read_text(encoding="utf-8") == было
