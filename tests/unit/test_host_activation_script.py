"""REQ-HOST-EXEC: сценарии активации на хосте обязаны быть исполнимыми в Bash.

Почему одного `bash -n` мало. Bash не считает `САЙТ="zona-01"` ошибкой разбора:
имя с не-ASCII символами не подходит под правило присваивания, поэтому строка
разбирается как обычная команда и `bash -n` проходит. Ломается это уже в
рантайме — «command not found», а следом `$САЙТ` под `set -u` даёт «unbound
variable», и сценарий умирает, не дойдя ни до перезапуска, ни до отката.

Поэтому здесь три уровня: синтаксис, имена идентификаторов и фактический
запуск. Последний и есть доказательство поведения: сценарий, получив заведомо
несуществующую витрину, обязан дойти до своей штатной проверки манифеста и
сказать об этом, а не развалиться на первой же строке.
"""
from __future__ import annotations

import re
import subprocess

import pytest

from factory.paths import PATHS

HOST_DIR = PATHS.root / "automation" / "host"
ACTIVATE = HOST_DIR / "zona-activate.sh"

# Имя переменной/функции: первый символ — буква или `_`, дальше буквы, цифры, `_`.
# `\w` намеренно юникодный: кириллическое имя СОВПАДЁТ и будет отбраковано
# проверкой `isascii()` ниже. Регексп, ограниченный ASCII, просто не увидел бы
# ровно тот дефект, ради которого написан этот тест.
NAME = r"[^\W\d]\w*"
ASSIGNMENT = re.compile(rf"^\s*(?:local\s+|export\s+|readonly\s+)?({NAME})=")
FUNCTION = re.compile(rf"^\s*({NAME})\s*\(\)")
EXPANSION = re.compile(rf"\$\{{?({NAME})")
HEREDOC = re.compile(r"<<-?\s*'?\"?(\w+)'?\"?")


def host_scripts() -> list:
    return sorted(HOST_DIR.glob("*.sh"))


def shell_lines(text: str):
    """Строки сценария без тел heredoc и без комментариев.

    Тело heredoc — не Bash: внутри `<<'PY'` лежит Python, где кириллическое имя
    совершенно законно. Комментарии по правилам репозитория русские, и требовать
    от них ASCII значило бы запретить эксплуатационную документацию.
    """
    terminator = None
    for number, line in enumerate(text.splitlines(), start=1):
        if terminator is not None:
            if line.strip() == terminator:
                terminator = None
            continue
        match = HEREDOC.search(line)
        if match:
            terminator = match.group(1)
        # `#` считается началом комментария, только если стоит отдельным словом:
        # иначе вырезало бы `${var#prefix}`.
        yield number, re.sub(r"(?<!\S)#.*$", "", line)


@pytest.mark.parametrize("script", host_scripts(), ids=lambda p: p.name)
def test_host_script_parses(script):
    """Уровень 1: сценарий разбирается Bash без синтаксических ошибок."""
    result = subprocess.run(["bash", "-n", str(script)],
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, f"bash -n {script.name}: {result.stderr.strip()}"


@pytest.mark.parametrize("script", host_scripts(), ids=lambda p: p.name)
def test_host_script_identifiers_are_ascii(script):
    """Уровень 2: имена переменных и функций — только ASCII.

    Bash не умеет не-ASCII идентификаторы: такое имя не присваивается, а
    исполняется как команда. Значения и текст сообщений это правило не трогает.
    """
    bad = []
    for number, line in shell_lines(script.read_text(encoding="utf-8")):
        for pattern, kind in ((ASSIGNMENT, "переменная"), (FUNCTION, "функция"),
                              (EXPANSION, "подстановка")):
            for match in pattern.finditer(line):
                name = match.group(1)
                if not name.isascii():
                    bad.append(f"{script.name}:{number}: {kind} {name!r}")
    assert not bad, (
        "не-ASCII идентификаторы делают сценарий неисполнимым в Bash:\n"
        + "\n".join(bad))


def test_activation_script_reaches_its_manifest_check():
    """Уровень 3: фактический запуск доходит до штатной проверки манифеста.

    Витрина заведомо несуществующая, поэтому сценарий обязан остановиться на
    первой же проверке — до `systemctl`, до сети и без единой мутации. Сломанная
    версия сюда не доходила: она падала на `unbound variable` в строке, которая
    только читает имя файла.
    """
    result = subprocess.run(
        ["bash", str(ACTIVATE), "zz-no-such-site-9f3a"],
        capture_output=True, text=True, timeout=120,
        cwd=str(PATHS.root))
    output = result.stdout + result.stderr

    assert "unbound variable" not in output, (
        f"сценарий развалился на неинициализированной переменной:\n{output}")
    assert "command not found" not in output, (
        f"строка сценария исполнилась как команда вместо присваивания:\n{output}")
    assert "нет манифеста витрины" in output, (
        f"сценарий не дошёл до штатной проверки манифеста:\n{output}")
    assert result.returncode == 1, f"ожидался выход 1, получен {result.returncode}"


def test_rollback_repoints_release_link_not_artifact_copy():
    """REQ-HOST-EXEC: откат переводит ссылку релиза, а не копирует байты.

    Юнит исполняет общий загрузчик, а тот через `execv` уходит в релиз, на
    который смотрит `sites/<витрина>/current`. Значит `artifact_path` манифеста
    не исполняется никем, и прежний откат — `cp` в этот файл — возвращал
    витрину ровно никуда, сообщая при этом об успехе.
    """
    text = ACTIVATE.read_text(encoding="utf-8")
    assert "ln -sfn" in text, "откат обязан переводить ссылку релиза"
    assert 'cp "$rollback_src" "$artifact"' not in text, (
        "откат копирует байты в artifact_path — файл, который не исполняется")
    assert "PREVIOUS_TARGET.txt" in text, "откат обязан брать цель из PREVIOUS_TARGET.txt"


def test_rollback_resolution_lands_on_previous_release(tmp_path):
    """Разрешение цели отката и перевод ссылки — на песочном дереве.

    Проверяется поведение, а не текст: относительная запись PREVIOUS_TARGET.txt
    обязана разрешаться относительно каталога витрины и приводить к прежнему
    релизу с рантаймом внутри.
    """
    front = tmp_path / "frontend"
    site_dir = front / "sites" / "zona-01"
    site_dir.mkdir(parents=True)
    for build in ("new", "old"):
        release = front / "releases" / build
        release.mkdir(parents=True)
        (release / "lords-frontend.py").write_text(f"# {build}\n", encoding="utf-8")

    link = site_dir / "current"
    link.symlink_to("../../releases/new")
    (site_dir / "PREVIOUS_TARGET.txt").write_text("../../releases/old", encoding="utf-8")

    # Ровно те шаги, что делает сценарий в ветке отката.
    previous = (site_dir / "PREVIOUS_TARGET.txt").read_text(encoding="utf-8").strip()
    previous_dir = (site_dir / previous).resolve()
    assert (previous_dir / "lords-frontend.py").is_file()

    subprocess.run(["ln", "-sfn", previous, str(link)], check=True, timeout=30)
    assert link.resolve() == previous_dir
    assert link.resolve().name == "old"
