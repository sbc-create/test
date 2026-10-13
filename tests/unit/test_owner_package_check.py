"""Пакет команд владельца обязан быть проверяемым, и проверка — падать на беде.

13.10 в пакете оказались ссылки на сценарии, которых в указанной копии нет:
путь вёл в `/srv/site-factory/repo`, а `install-site-nginx.sh`,
`install-site-tls.sh`, `launch-new-site.sh`, `apply-publisher-patch.py` лежат в
рабочем дереве. Команда отказала бы сразу, и узнал бы об этом владелец, а не я.

Вторая ловушка тоньше: сценарий ищет реестр и заготовку ОТНОСИТЕЛЬНО СЕБЯ
(`SRC_ROOT=$(dirname $0)/../..`). Существование самого сценария ничего не
доказывает — рядом с ним может не быть `config/site-cells.json`, и это ровно
то, чем живая копия отличается от рабочего дерева.

Поэтому здесь закрепляется не текст документа, а СПОСОБНОСТЬ проверки ловить
каждый из этих случаев, плюс то, что действующий пакет её проходит.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
ПАКЕТ = КОРЕНЬ / "docs" / "OWNER_ACTIONS_BATCH8_20261013.md"


def _модуль():
    путь = КОРЕНЬ / "automation" / "local" / "owner-package-check.py"
    spec = importlib.util.spec_from_file_location("owner_package_check", путь)
    м = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(м)
    return м


def _документ(tmp_path, команды: str) -> Path:
    д = tmp_path / "пакет.md"
    д.write_text(f"# проба\n\n```bash\n{команды}\n```\n", encoding="utf-8")
    return д


def test_действующий_пакет_проходит_проверку():
    """Иначе владелец получит команду, которая не запустится."""
    м = _модуль()
    беды = м.проверить(ПАКЕТ)
    assert беды == [], "\n".join(беды)


def test_в_пакете_есть_что_проверять():
    м = _модуль()
    команды = м.блоки(ПАКЕТ.read_text(encoding="utf-8"))
    assert len(команды) >= 15, f"команд всего {len(команды)} — проверка почти пуста"


def test_ловит_несуществующий_сценарий(tmp_path):
    м = _модуль()
    д = _документ(tmp_path, "sudo bash /srv/site-factory/repo/automation/host/"
                            "install-site-nginx.sh --site lords-10")
    беды = м.проверить(д)
    assert any("сценария НЕТ" in б for б in беды), беды


def test_ловит_относительный_путь(tmp_path):
    """После `cd` в чужое дерево относительный путь ведёт не туда."""
    м = _модуль()
    д = _документ(tmp_path, "python3 automation/local/autocontinue-cycles.py --kind tech")
    беды = м.проверить(д)
    assert any("относительный путь" in б for б in беды), беды


def test_ловит_отсутствие_реестра_рядом_со_сценарием(tmp_path):
    """Сценарий на месте, а реестра рядом нет — самый тихий из случаев."""
    м = _модуль()
    поддельный = tmp_path / "копия" / "automation" / "host"
    поддельный.mkdir(parents=True)
    сценарий = поддельный / "install-site-nginx.sh"
    сценарий.write_text("#!/usr/bin/env bash\n# --site\n", encoding="utf-8")
    сценарий.chmod(0o755)
    д = _документ(tmp_path, f"sudo bash {сценарий} --site lords-10")
    беды = м.проверить(д)
    assert any("нет" in б and "site-cells.json" in б for б in беды), беды


def test_ловит_неизвестный_site(tmp_path):
    м = _модуль()
    д = _документ(tmp_path, f"sudo bash {КОРЕНЬ}/automation/host/launch-new-site.sh "
                            "--site lords-999")
    беды = м.проверить(д)
    assert any("нет в реестре" in б for б in беды), беды


def test_ловит_отсутствие_заготовки_nginx(tmp_path):
    """Заготовка — тоже конфигурация, которую сценарий ищет рядом с собой."""
    м = _модуль()
    копия = tmp_path / "дерево"
    (копия / "automation" / "host" / "nginx-site").mkdir(parents=True)
    (копия / "config").mkdir()
    (копия / "config" / "site-cells.json").write_text(
        json.dumps({"cells": [{"site_id": "lords-10", "domain": "x.test"}]}),
        encoding="utf-8")
    сценарий = копия / "automation" / "host" / "install-site-nginx.sh"
    сценарий.write_text("#!/usr/bin/env bash\n# --site\n", encoding="utf-8")
    сценарий.chmod(0o755)
    д = _документ(tmp_path, f"sudo bash {сценарий} --site lords-10")
    беды = м.проверить(д)
    assert any("нет заготовки" in б for б in беды), беды


def test_ловит_отсутствующий_источник_install(tmp_path):
    """У `install` нет сценария, и первая версия проверки такие строки пропускала.

    А это ровно те файлы, которых может не быть: юниты, которые владелец
    ставит в /etc/systemd/system.
    """
    м = _модуль()
    д = _документ(tmp_path, "sudo install -m 0644 -o root -g root "
                            "/home/claude/нет-такого/unit.service /etc/systemd/system/")
    беды = м.проверить(д)
    assert any("install: источника НЕТ" in б for б in беды), беды


def test_существующий_источник_install_проходит(tmp_path):
    м = _модуль()
    юнит = tmp_path / "seo-tech-run.service"
    юнит.write_text("[Service]\n", encoding="utf-8")
    д = _документ(tmp_path, f"sudo install -m 0644 -o root -g root {юнит} "
                            "/etc/systemd/system/")
    assert м.проверить(д) == []


def test_вечерний_блок_проходит_проверку():
    """Второй документ пакета — та же планка, что и у основного."""
    м = _модуль()
    блок = КОРЕНЬ / "docs" / "OWNER_BLOCK_20261013_EVENING.md"
    assert блок.is_file(), "вечернего блока команд нет"
    беды = м.проверить(блок)
    assert беды == [], "\n".join(беды)
