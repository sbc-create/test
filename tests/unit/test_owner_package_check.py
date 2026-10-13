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


# --- Третья ловушка: форма `python3 -m <модуль>` проверкой ПРОПУСКАЛАСЬ -------
#
# У неё нет ни пути, ни расширения `.py`, поэтому разбор возвращал «сценария
# нет», и строка не проверялась вовсе. Так в пакет едва не попал вызов
# анализатора журналов без обязательного `--format`: отказ случился бы в
# терминале владельца, а проверка пакета оставалась зелёной.


def test_ловит_модуль_без_объявленного_каталога_запуска(tmp_path):
    """Без `cd` модуль не разрешить — это расхождение, а не повод промолчать."""
    м = _модуль()
    д = _документ(tmp_path, "python3 -m seo_operator.crawl_log --format combined "
                            "/var/log/nginx/lords-01.access.log")
    беды = м.проверить(д)
    assert any("каталог запуска не объявлен" in б for б in беды), беды


def test_ловит_несуществующий_модуль(tmp_path):
    м = _модуль()
    д = _документ(tmp_path, f"cd {КОРЕНЬ} && python3 -m нет_такого.модуля")
    беды = м.проверить(д)
    assert any("модуля НЕТ" in б for б in беды), беды


def test_ловит_отсутствие_обязательного_ключа(tmp_path):
    """`required=True` читается разбором кода, а не поиском подстроки."""
    м = _модуль()
    пакет = tmp_path / "инструмент"
    пакет.mkdir()
    (пакет / "разбор.py").write_text(
        "import argparse\n"
        "р = argparse.ArgumentParser()\n"
        'р.add_argument("--format", required=True)\n'
        'р.add_argument("--domain")\n', encoding="utf-8")
    д = _документ(tmp_path, f"cd {tmp_path} && python3 -m инструмент.разбор --domain x")
    беды = м.проверить(д)
    assert any("нет обязательного ключа --format" in б for б in беды), беды

    ладно = _документ(tmp_path, f"cd {tmp_path} && python3 -m инструмент.разбор "
                                "--format combined --domain x")
    assert м.проверить(ладно) == []


def test_режим_доступа_install_не_принимается_за_модуль(tmp_path):
    """`install -m 0644` — права, а не модуль; первая версия путала."""
    м = _модуль()
    файл = tmp_path / "seo-tech-run.timer"
    файл.write_text("[Timer]\n", encoding="utf-8")
    д = _документ(tmp_path, f"sudo install -m 0644 -o root -g root {файл} "
                            "/etc/systemd/system/")
    assert м.модуль_в_команде(f"sudo install -m 0644 {файл} /etc/systemd/system/") is None
    assert м.проверить(д) == []


def test_относительный_путь_с_объявленным_каталогом_разрешается(tmp_path):
    """Объявленный `cd` делает относительный путь проверяемым, а не бедой."""
    м = _модуль()
    д = _документ(tmp_path, f"cd {КОРЕНЬ} && python3 -m factory cell content --site lords-10")
    assert м.проверить(д) == []


def test_ловит_несуществующий_каталог_запуска(tmp_path):
    м = _модуль()
    д = _документ(tmp_path, f"cd {tmp_path}/нет-такого && python3 -m factory status")
    беды = м.проверить(д)
    assert any("каталога запуска НЕТ" in б for б in беды), беды


def test_отчёт_партии_проходит_проверку():
    """Команды отчёта — тоже команды: их блоки объявляют каталог запуска."""
    м = _модуль()
    отчёт = КОРЕНЬ / "docs" / "BATCH_EIGHT_LORDS_20261013.md"
    assert отчёт.is_file(), "отчёта партии нет"
    беды = м.проверить(отчёт)
    assert беды == [], "\n".join(беды)


def test_блок_P0_проходит_проверку():
    м = _модуль()
    блок = КОРЕНЬ / "docs" / "OWNER_BLOCK_20261013_BACKUP_P0.md"
    assert блок.is_file(), "блока P0 нет"
    беды = м.проверить(блок)
    assert беды == [], "\n".join(беды)


def test_источник_install_не_требует_исполнимости_и_ключей(tmp_path):
    """`install x.py /etc/...` — копирование, а не запуск.

    Прежняя версия требовала от источника бита исполнения, а с проверкой
    обязательных ключей потребовала бы и `--format`: обе придирки — ни за что.
    """
    м = _модуль()
    источник = tmp_path / "разбор.py"
    источник.write_text('import argparse\n'
                        'р = argparse.ArgumentParser()\n'
                        'р.add_argument("--format", required=True)\n', encoding="utf-8")
    д = _документ(tmp_path, f"sudo install -m 0644 -o root -g root {источник} "
                            "/etc/site-factory/")
    assert м.проверить(д) == []


def test_источник_созданный_ранее_в_блоке_не_считается_пропавшим(tmp_path):
    """Порядок внутри блока: строка выше создаёт то, что ставит строка ниже."""
    м = _модуль()
    цель = tmp_path / "откат.py"
    д = _документ(tmp_path, f"printf 'x' > {цель}\n"
                            f"sudo install -m 0644 -o root -g root {цель} /etc/site-factory/")
    assert м.проверить(д) == []
    assert цель in set(м.созданные_пути(f"printf 'x' > {цель}"))


def test_адрес_в_истории_не_считается_путём_на_диске(tmp_path):
    """`<ревизия>:<путь>` файлом не является, и спрашивать его на диске нельзя."""
    м = _модуль()
    команда = "git show 4f94542:automation/host/app-read-api.py > /tmp/откат.py"
    путь, _ = м.путь_сценария(команда)
    assert путь is None, путь


def test_цель_перенаправления_не_считается_запускаемым_файлом(tmp_path):
    м = _модуль()
    путь, _ = м.путь_сценария("python3 -c 'print(1)' > /tmp/нет-такого.py")
    assert путь is None, путь


# --- Планка по классу документа ------------------------------------------------
#
# Копируемый пакет владельца обязан объявлять каталог запуска в самом блоке: он
# вставляет строки в терминал, где рабочий каталог ничем не задан. Документ
# повествовательный объявляет каталог один раз прозой — для него планка мягкая,
# но КОМАНДЫ проверяются так же.

КОПИРУЕМЫЕ = ("OWNER_ACTIONS_BATCH8_20261013.md",
              "OWNER_BLOCK_20261013_EVENING.md",
              "OWNER_BLOCK_20261013_BACKUP_P0.md",
              "OWNER_COMMANDS_20261013_MORNING.md",
              "OWNER_SERVERHOLD_PACKAGE.md")
ПОВЕСТВОВАТЕЛЬНЫЕ = ("OWNER_TERMINAL_20261013.md",)


@pytest.mark.parametrize("имя", КОПИРУЕМЫЕ)
def test_копируемый_пакет_строгой_планки(имя):
    м = _модуль()
    док = КОРЕНЬ / "docs" / имя
    assert док.is_file(), f"нет {имя}"
    беды = м.проверить(док, строгий_каталог=True)
    assert беды == [], "\n".join(беды)


@pytest.mark.parametrize("имя", ПОВЕСТВОВАТЕЛЬНЫЕ)
def test_повествовательный_пакет_мягкой_планки(имя):
    м = _модуль()
    док = КОРЕНЬ / "docs" / имя
    assert док.is_file(), f"нет {имя}"
    беды = м.проверить(док, строгий_каталог=False)
    assert беды == [], "\n".join(беды)


def test_мягкая_планка_не_отменяет_проверку_путей(tmp_path):
    """Иначе «мягкий режим» стал бы разрешением писать что угодно."""
    м = _модуль()
    д = _документ(tmp_path, "python3 automation/host/нет-такого-инструмента.py --site lords-10")
    беды = м.проверить(д, строгий_каталог=False)
    assert any("сценария НЕТ" in б for б in беды), беды


# --- Блок для ДРУГОЙ машины ---------------------------------------------------
#
# Блок подготовки узла K2 ставит файлы из /home/k2deploy/stage/ — они лежат на
# узле, а не здесь, и проверка честно сказала «источника НЕТ» пять раз. Снять
# проверку целиком нельзя: тогда опечатка в пути прошла бы молча. Поэтому метка
# явная и действует только для хоста, УЖЕ внесённого в inventory.


def test_метка_узла_снимает_проверку_локальных_путей(tmp_path):
    м = _модуль()
    узлы = м.inventory_хосты()
    if not узлы:
        pytest.skip("в inventory нет хостов: метку не на что опереть")
    узел = sorted(узлы)[0]
    д = _документ(tmp_path, f"# host: {узел}\n"
                            "install -m 0644 /home/k2deploy/stage/units/nova-x.service "
                            "/etc/systemd/system/")
    assert м.проверить(д) == []


def test_метка_с_хостом_вне_реестра_это_расхождение(tmp_path):
    """Иначе метка стала бы способом отключить проверку одной строкой."""
    м = _модуль()
    д = _документ(tmp_path, "# host: нет-такого-узла\n"
                            "install -m 0644 /nope/x /etc/systemd/system/")
    беды = м.проверить(д)
    assert any("вне inventory" in б for б in беды), беды


def test_без_метки_пути_по_прежнему_требуются(tmp_path):
    м = _модуль()
    д = _документ(tmp_path, "install -m 0644 /home/k2deploy/stage/units/nova-x.service "
                            "/etc/systemd/system/")
    беды = м.проверить(д)
    assert any("источника НЕТ" in б for б in беды), беды


def test_метка_узла_видна_в_сводке(tmp_path, capsys):
    """Молчащий пропуск хуже отсутствующей проверки: он выглядит проверкой."""
    м = _модуль()
    узлы = м.inventory_хосты()
    if not узлы:
        pytest.skip("в inventory нет хостов")
    узел = sorted(узлы)[0]
    д = _документ(tmp_path, f"# host: {узел}\ninstall -m 0644 /x/y /etc/")
    import sys as _sys

    старые = _sys.argv
    _sys.argv = ["c", str(д)]
    try:
        assert м.main() == 0
    finally:
        _sys.argv = старые
    вывод = capsys.readouterr().out
    assert "для другой машины" in вывод and узел in вывод, вывод


def test_план_узла_k2_проходит_проверку():
    м = _модуль()
    док = КОРЕНЬ / "docs" / "K2_NIGHT_PLAN_20261013.md"
    assert док.is_file(), "плана узла K2 нет"
    беды = м.проверить(док)
    assert беды == [], "\n".join(беды)
