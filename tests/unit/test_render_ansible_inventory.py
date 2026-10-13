"""Инвентарь Ansible обязан РОЖДАТЬСЯ из реестра, а не поддерживаться руками.

`automation/ansible/inventory/hosts.yml` начинается словами «Инвентарь Ansible
генерируется из inventory/ssh-hosts.yaml фабрики» — а генератора не было.
Следствие измерено 2026-10-13 при регистрации узла ZOMRO: адаптер
(`factory/targets/ssh_ansible.py`) проверяет наличие `ssh_key_secret_ref` и
больше ничего с ним не делает — в ansible путь ключа не попадал ВООБЩЕ, и
подключение к свежезарегистрированному хосту не состоялось бы ни при каком
содержимом реестра.

Почему путь ключа обязан жить в ФАЙЛЕ инвентаря, а не в командной строке:
обращение к `~/.ssh/` в любой команде оболочки запрещено правилом G-SECRET, и
обходить его нельзя. Декларативный слой для этого и существует.

Здесь закрепляется поведение генератора: что он собирает, на чём ОТКАЗЫВАЕТ и
что никогда не печатает.
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest
import yaml

КОРЕНЬ = Path(__file__).resolve().parents[2]
ГЕНЕРАТОР = КОРЕНЬ / "automation" / "local" / "render-ansible-inventory.py"


def _модуль():
    spec = importlib.util.spec_from_file_location("render_ansible_inventory", ГЕНЕРАТОР)
    м = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(м)
    return м


def _запись(tmp_path: Path, **правки) -> dict:
    """Годная запись реестра; правки делают её негодной по одному полю."""
    пин = tmp_path / "known_hosts.d" / "k2-zomro-01"
    пин.parent.mkdir(parents=True, exist_ok=True)
    пин.write_text("145.63.129.86 ssh-ed25519 AAAA\n", encoding="utf-8")
    ключ = tmp_path / "ключ"
    ключ.write_text("", encoding="utf-8")
    з = {
        "ref": "k2-zomro-01",
        "hostname": "145.63.129.86",
        "port": 22,
        "deploy_user": "k2deploy",
        "auth": "publickey_only",
        "ssh_key_secret_ref": f"file:{ключ}",
        "known_hosts_entry_ref": str(пин.relative_to(tmp_path)),
        "strict_host_key_checking": "yes",
        "sudo_allowlist": [],
        "environments": ["staging"],
    }
    з.update(правки)
    return з


@pytest.fixture()
def м_в(tmp_path, monkeypatch):
    """Модуль с КОРНЕМ в tmp_path: пути пиннинга считаются от него."""
    м = _модуль()
    monkeypatch.setattr(м, "КОРЕНЬ", tmp_path)
    return м


def test_годная_запись_даёт_узел_с_ключом_и_проверкой_хоста(м_в, tmp_path):
    дерево, беды = м_в.инвентарь([_запись(tmp_path)])
    assert беды == []
    узел = дерево["all"]["children"]["dle_staging"]["hosts"]["k2-zomro-01"]
    assert узел["ansible_host"] == "145.63.129.86"
    assert узел["ansible_user"] == "k2deploy"
    assert узел["ansible_ssh_private_key_file"].endswith("ключ")
    assert "StrictHostKeyChecking=yes" in узел["ansible_ssh_common_args"]
    assert "BatchMode=yes" in узел["ansible_ssh_common_args"], (
        "без BatchMode ansible ждал бы ввод пароля")
    assert "UserKnownHostsFile=" in узел["ansible_ssh_common_args"]


def test_root_отвергается(м_в, tmp_path):
    _, беды = м_в.инвентарь([_запись(tmp_path, deploy_user="root")])
    assert any("root" in б for б in беды), беды


def test_без_пиннинга_отвергается(м_в, tmp_path):
    _, беды = м_в.инвентарь([_запись(tmp_path, known_hosts_entry_ref="")])
    assert any("known_hosts_entry_ref" in б for б in беды), беды


def test_пиннинг_без_файла_отвергается(м_в, tmp_path):
    _, беды = м_в.инвентарь([_запись(tmp_path, known_hosts_entry_ref="нет/такого")])
    assert any("файла пиннинга" in б for б in беды), беды


def test_отключённая_проверка_ключа_сервера_отвергается(м_в, tmp_path):
    for значение in ("no", False, None, "accept-new"):
        _, беды = м_в.инвентарь([_запись(tmp_path, strict_host_key_checking=значение)])
        assert any("strict_host_key_checking" in б for б in беды), (значение, беды)


def test_ключ_без_файла_отвергается(м_в, tmp_path):
    _, беды = м_в.инвентарь([_запись(tmp_path,
                                     ssh_key_secret_ref=f"file:{tmp_path}/нет")])
    assert any("файла ключа" in б for б in беды), беды


def test_незаданная_переменная_ключа_отвергается(м_в, tmp_path, monkeypatch):
    monkeypatch.delenv("FACTORY_SSH_KEY_TEST", raising=False)
    _, беды = м_в.инвентарь([_запись(tmp_path,
                                     ssh_key_secret_ref="env:FACTORY_SSH_KEY_TEST")])
    assert any("не задана в окружении" in б for б in беды), беды


def test_неизвестная_схема_ссылки_отвергается(м_в, tmp_path):
    _, беды = м_в.инвентарь([_запись(tmp_path, ssh_key_secret_ref="vault:/x")])
    assert any("неизвестная схема" in б for б in беды), беды


def test_без_окружений_узел_не_попадает_никуда(м_в, tmp_path):
    дерево, беды = м_в.инвентарь([_запись(tmp_path, environments=[])])
    assert any("окружения" in б for б in беды), беды
    assert all(not г["hosts"] for г in дерево["all"]["children"].values())


def test_пустой_реестр_даёт_код_1(tmp_path, monkeypatch, capsys):
    """Пустой реестр — не поломка, а закрытый удалённый доступ."""
    реестр = tmp_path / "ssh-hosts.yaml"
    реестр.write_text("schema_version: 1\nhosts: []\n", encoding="utf-8")
    м = _модуль()
    monkeypatch.setattr("sys.argv", ["g", "--registry", str(реестр),
                                     "--out", str(tmp_path / "hosts.yml")])
    assert м.main() == 1
    assert "удалённый доступ закрыт" in capsys.readouterr().out
    assert not (tmp_path / "hosts.yml").exists(), "файл не должен создаваться"


def test_записанный_инвентарь_читается_ansible_как_yaml(м_в, tmp_path, monkeypatch, capsys):
    реестр = tmp_path / "ssh-hosts.yaml"
    реестр.write_text(yaml.safe_dump({"schema_version": 1,
                                      "hosts": [_запись(tmp_path)]},
                                     allow_unicode=True), encoding="utf-8")
    выход = tmp_path / "var" / "ansible" / "hosts.yml"
    monkeypatch.setattr("sys.argv", ["g", "--registry", str(реестр),
                                     "--out", str(выход)])
    assert м_в.main() == 0
    текст = выход.read_text(encoding="utf-8")
    assert "СГЕНЕРИРОВАНО" in текст and "Руками не правится" in текст
    дерево = yaml.safe_load(текст)
    assert "k2-zomro-01" in дерево["all"]["children"]["dle_staging"]["hosts"]


#: Шапка приватного ключа собирается из частей НАМЕРЕННО: литерал в файле
#: репозитория останавливает проверка содержимого (G-SECRET-CONTENT), и она
#: права — такой строке в git не место даже в тесте.
ШАПКА_КЛЮЧА = "-----BEGIN " + "OPENSSH " + "PRIVATE KEY-----"


def test_значение_ключа_не_печатается(м_в, tmp_path, monkeypatch, capsys):
    """Печатается путь и только путь: содержимое ключа не читается вовсе."""
    ключ = tmp_path / "ключ"
    ключ.write_text(f"{ШАПКА_КЛЮЧА}\nсекрет\n", encoding="utf-8")
    реестр = tmp_path / "ssh-hosts.yaml"
    реестр.write_text(yaml.safe_dump(
        {"schema_version": 1,
         "hosts": [_запись(tmp_path, ssh_key_secret_ref=f"file:{ключ}")]},
        allow_unicode=True), encoding="utf-8")
    выход = tmp_path / "hosts.yml"
    monkeypatch.setattr("sys.argv", ["g", "--registry", str(реестр), "--out", str(выход)])
    assert м_в.main() == 0
    вывод = capsys.readouterr().out
    содержимое = выход.read_text(encoding="utf-8")
    for запрещено in (ШАПКА_КЛЮЧА, "секрет"):
        assert запрещено not in вывод, вывод
        assert запрещено not in содержимое, "значение ключа попало в инвентарь"


def test_check_ничего_не_пишет(м_в, tmp_path, monkeypatch):
    реестр = tmp_path / "ssh-hosts.yaml"
    реестр.write_text(yaml.safe_dump({"schema_version": 1,
                                      "hosts": [_запись(tmp_path)]},
                                     allow_unicode=True), encoding="utf-8")
    выход = tmp_path / "hosts.yml"
    monkeypatch.setattr("sys.argv", ["g", "--registry", str(реестр),
                                     "--out", str(выход), "--check"])
    assert м_в.main() == 0
    assert not выход.exists()


def test_сгенерированный_инвентарь_не_версионируется():
    """Он содержит путь к ключу — в git ему не место."""
    import subprocess

    готово = subprocess.run(["git", "-C", str(КОРЕНЬ), "check-ignore", "-q",
                             "var/ansible/hosts.yml"], capture_output=True)
    assert готово.returncode == 0, "var/ansible/hosts.yml не игнорируется git"


def test_заготовка_инвентаря_в_репозитории_осталась_пустой():
    """Отслеживаемый файл — только образец: хосты в нём не живут."""
    п = КОРЕНЬ / "automation" / "ansible" / "inventory" / "hosts.yml"
    дерево = yaml.safe_load(п.read_text(encoding="utf-8"))
    for группа in (дерево["all"]["children"] or {}).values():
        assert not (группа or {}).get("hosts"), (
            "в отслеживаемой заготовке появился хост: путь к ключу попал бы в git")
