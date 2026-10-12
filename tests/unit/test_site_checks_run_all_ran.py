"""Проверка, которая не исполнилась, не должна выглядеть пройденной.

Найдено на живых витринах 12.10: в `checks/run.sh` трёх ячеек AnimeGo стояла
строка `check "visible-breadcrumbs" …`, а обёртка в этих файлах называется
`step`. bash отвечает «command not found» с кодом 127 и код прогона от этого
не меняется — проверка молчала, и отсутствие крошек на трёх витринах выглядело
как исправность.

Сторож считает объявленные и исполненные проверки. Здесь проверяется, что он
ловит обе подмены и не срабатывает зря: ложное срабатывание в прогоне выпуска
стоило бы дороже молчания.

Шаблон запускается настоящий. Команды проверок подменены заглушкой в PATH:
предмет измерения — обёртка и счёт, а не сами проверки.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
ШАБЛОН = КОРЕНЬ / "factory" / "cell" / "site_checks" / "run.sh"


def _стенд(tmp_path: Path, текст: str) -> tuple[Path, dict]:
    """Ячейка, где любая команда проверки успешна, и свой run.sh."""
    ячейка = tmp_path / "cell"
    (ячейка / "checks").mkdir(parents=True)
    (ячейка / "deploy").mkdir(parents=True)
    сценарий = ячейка / "checks" / "run.sh"
    сценарий.write_text(текст, encoding="utf-8")
    сценарий.chmod(0o755)

    заглушки = tmp_path / "bin"
    заглушки.mkdir()
    for имя in ("python3", "bash"):
        путь = заглушки / имя
        путь.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        путь.chmod(0o755)

    среда = dict(os.environ)
    # Заглушки впереди: предмет измерения — обёртка и счёт, а не проверки.
    # Настоящий bash нужен самому сценарию, поэтому он вызывается по полному
    # пути, а не из PATH.
    среда["PATH"] = f"{заглушки}:{среда.get('PATH', '')}"
    return сценарий, среда


def _прогон(сценарий: Path, среда: dict) -> subprocess.CompletedProcess:
    настоящий_bash = shutil.which("bash", path="/usr/bin:/bin") or "/bin/bash"
    return subprocess.run([настоящий_bash, str(сценарий)], env=среда,
                          capture_output=True, text=True, timeout=300)


def test_целый_шаблон_проходит_и_сторож_молчит(tmp_path):
    """Без этого проверки ниже прошли бы и у сторожа, который падает всегда."""
    сценарий, среда = _стенд(tmp_path, ШАБЛОН.read_text(encoding="utf-8"))
    готово = _прогон(сценарий, среда)
    assert готово.returncode == 0, готово.stdout + готово.stderr
    assert "checks-all-ran" in готово.stdout
    assert "PASS" in готово.stdout.split("checks-all-ran")[1]


def test_строка_check_в_файле_с_обёрткой_step_ловится(tmp_path):
    """Ровно случай AnimeGo: добавленная строка `check` при обёртке `step`."""
    текст = ШАБЛОН.read_text(encoding="utf-8")
    # Переименовываем ОБЁРТКУ и её вызовы, оставив одну строку `check` —
    # как и вышло у ячеек, куда строку скопировали из другого семейства.
    текст = текст.replace("check() {", "step() {")
    текст = re.sub(r"^check ", "step ", текст, flags=re.M)
    текст = текст.replace(
        'step "contact-email"      python3 checks/contact_email.py',
        'check "visible-breadcrumbs" python3 checks/visible_breadcrumbs.py')
    assert "\ncheck " in текст, "подмена не состоялась — проверка пуста"

    сценарий, среда = _стенд(tmp_path, текст)
    готово = _прогон(сценарий, среда)
    assert готово.returncode != 0, готово.stdout + готово.stderr
    assert "checks-all-ran" in готово.stdout
    assert "FAIL" in готово.stdout.split("checks-all-ran")[1]
    assert "исполнилось" in готово.stdout


def test_переименование_строки_в_step_тоже_ловится(tmp_path):
    """Вторая подмена: обёртка осталась `check`, а строка стала `step`.

    Если считать только `check`, ожидание снизилось бы вместе с исполненным и
    сторож промолчал бы о той самой подмене, ради которой написан.
    """
    текст = ШАБЛОН.read_text(encoding="utf-8")
    текст = текст.replace(
        'check "contact-email"      python3 checks/contact_email.py',
        'step "contact-email"      python3 checks/contact_email.py')
    сценарий, среда = _стенд(tmp_path, текст)
    готово = _прогон(сценарий, среда)
    assert готово.returncode != 0, готово.stdout + готово.stderr
    assert "FAIL" in готово.stdout.split("checks-all-ran")[1]


def test_упавшая_проверка_остаётся_упавшей(tmp_path):
    """Сторож не должен подменять обычный провал своим.

    Иначе настоящая причина провала потерялась бы за сообщением о счёте.
    """
    сценарий, среда = _стенд(tmp_path, ШАБЛОН.read_text(encoding="utf-8"))
    # python3 теперь отказывает: все проверки падают, но ИСПОЛНЯЮТСЯ все.
    плохой = Path(среда["PATH"].split(":")[0]) / "python3"
    плохой.write_text("#!/bin/sh\necho 'проверка не прошла' >&2\nexit 1\n",
                      encoding="utf-8")
    плохой.chmod(0o755)
    готово = _прогон(сценарий, среда)
    assert готово.returncode != 0
    assert "FAIL" in готово.stdout
    # Счёт при этом сходится: проверки исполнились, просто не прошли.
    assert "PASS" in готово.stdout.split("checks-all-ran")[1], готово.stdout


def test_новая_строка_проверки_поднимает_ожидание_сама(tmp_path):
    """Число не вписывается руками, иначе устаревшее число соврало бы.

    Добавленная строка обязана и считаться объявленной, и исполниться.
    """
    текст = ШАБЛОН.read_text(encoding="utf-8")
    текст = текст.replace(
        'check "contact-email"      python3 checks/contact_email.py',
        'check "contact-email"      python3 checks/contact_email.py\n'
        'check "ещё-одна"           python3 checks/новая.py')
    сценарий, среда = _стенд(tmp_path, текст)
    готово = _прогон(сценарий, среда)
    assert готово.returncode == 0, готово.stdout + готово.stderr
    assert "PASS" in готово.stdout.split("checks-all-ran")[1]
    assert "ещё-одна" in готово.stdout


def test_пропуск_по_окружению_не_выглядит_пройденной(tmp_path):
    """Второй тихий случай: проверка исполнилась и НЕ ИЗМЕРИЛА ничего.

    Цена измерена 12.10: `config/player.json` у двух ячеек AnimeGo принадлежит
    root (0600), стенд `data_chain` не поднимался, проверка уходила в пропуск —
    и регрессия таблицы характеристик прошла run.sh и вышла на живой сайт.
    В выводе это выглядело как PASS.
    """
    сценарий, среда = _стенд(tmp_path, ШАБЛОН.read_text(encoding="utf-8"))
    заглушки = Path(среда["PATH"].split(":")[0])
    (заглушки / "python3").write_text(
        "#!/bin/sh\necho 'ПРОПУЩЕНО: стенд не поднялся (ограничение окружения)'\nexit 0\n",
        encoding="utf-8")
    (заглушки / "python3").chmod(0o755)
    готово = _прогон(сценарий, среда)

    # Прогон НЕ валится: предел окружения бывает законным, и превращать его в
    # отказ — решение о выпусках, а не дело этого сценария.
    assert готово.returncode == 0, готово.stdout + готово.stderr
    # Но молчания нет: пропуски названы и посчитаны.
    assert "ПРОПУЩЕНО" in готово.stdout
    assert "checks-measured" in готово.stdout
    итог = готово.stdout.split("checks-measured")[1]
    assert "ПРОПУЩЕНО" in итог, итог
    assert "PASS" not in итог.splitlines()[0], итог


def test_без_пропусков_строка_измерения_проходит(tmp_path):
    """Без этого предыдущая проверка прошла бы и у сценария, который печатает
    «ПРОПУЩЕНО» всегда."""
    сценарий, среда = _стенд(tmp_path, ШАБЛОН.read_text(encoding="utf-8"))
    готово = _прогон(сценарий, среда)
    assert готово.returncode == 0, готово.stdout + готово.stderr
    итог = готово.stdout.split("checks-measured")[1]
    assert "PASS" in итог.splitlines()[0], итог


def test_упавшая_проверка_пропуском_не_считается(tmp_path):
    """Отказ и пропуск — разные исходы, и смешать их значило бы скрыть отказ."""
    сценарий, среда = _стенд(tmp_path, ШАБЛОН.read_text(encoding="utf-8"))
    заглушки = Path(среда["PATH"].split(":")[0])
    (заглушки / "python3").write_text(
        "#!/bin/sh\necho 'ПРОПУЩЕНО: и при этом отказ' >&2\nexit 1\n",
        encoding="utf-8")
    (заглушки / "python3").chmod(0o755)
    готово = _прогон(сценарий, среда)
    assert готово.returncode != 0, готово.stdout
    assert "FAIL" in готово.stdout
    итог = готово.stdout.split("checks-measured")[1]
    assert "PASS" in итог.splitlines()[0], (
        "упавшая проверка посчитана пропуском — отказ оказался бы скрыт")
