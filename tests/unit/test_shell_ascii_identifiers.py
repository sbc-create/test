"""Имена переменных и функций в shell-скриптах фабрики — только ASCII.

Bash считает именем переменной лишь ``[A-Za-z_][A-Za-z0-9_]*``. Строка
``СУХОЙ=0`` для него не присваивание, а попытка выполнить команду с таким
именем, и падает она только в момент запуска::

    activate.sh: line 18: СУХОЙ=0: command not found

``bash -n`` этого не ловит: синтаксически там законный вызов команды. Проверка
живёт отдельно именно поэтому — она смотрит на то, чего разбор синтаксиса не
видит.

Ограничение касается только идентификаторов: русские сообщения, комментарии и
значения не трогаются, иначе эксплуатационные скрипты пришлось бы переписать
на английский без всякой пользы.

Проверка появилась в репозиториях выделенных сайтов, а дефект родом отсюда —
и при первой же правке ``lords-staging-apply.sh`` в монорепозитории снова
возникло кириллическое имя массива. Поэтому она стоит и здесь.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]

#: Присваивание в начале строки и любое обращение через $ или ${...}.
ПРИСВАИВАНИЕ = re.compile(r"^\s*(?:export\s+|local\s+|declare\s+|readonly\s+)?"
                          r"([^\s=]*[^\x00-\x7F][^\s=]*)=")
ОБРАЩЕНИЕ = re.compile(r"\$\{?([A-Za-z_]*[^\x00-\x7F][^\s}/:\-]*)")
ФУНКЦИЯ = re.compile(r"^\s*(?:function\s+)?([^\s()]*[^\x00-\x7F][^\s()]*)\s*\(\s*\)")

ПРАВИЛА = ((ПРИСВАИВАНИЕ, "присваивание"), (ОБРАЩЕНИЕ, "обращение"),
           (ФУНКЦИЯ, "объявление функции"))


def беды_файла(текст: str, имя: str) -> list[str]:
    найдено = []
    for номер, строка in enumerate(текст.splitlines(), 1):
        без_комментария = строка.split("#", 1)[0]
        for правило, что in ПРАВИЛА:
            for найденное in правило.findall(без_комментария):
                найдено.append(f"{имя}:{номер}: {что} к не-ASCII имени {найденное!r}")
    return найдено


def скрипты() -> list[Path]:
    исключить = {".git", ".venv", "var", "node_modules", "knowledge"}
    return sorted(p for p in КОРЕНЬ.rglob("*.sh")
                  if not (исключить & set(p.relative_to(КОРЕНЬ).parts)))


def test_скрипты_найдены():
    """Пустой список означал бы, что проверка ничего не проверяет."""
    assert len(скрипты()) >= 5


@pytest.mark.parametrize("путь", скрипты(), ids=lambda p: str(p.relative_to(КОРЕНЬ)))
def test_имена_в_shell_только_ascii(путь: Path):
    беды = беды_файла(путь.read_text(encoding="utf-8"), str(путь.relative_to(КОРЕНЬ)))
    assert not беды, "\n".join(беды)


def test_проверка_ловит_то_чего_не_ловит_bash_n(tmp_path: Path):
    """Доказательство, что проверка не дублирует `bash -n`.

    Без этого теста легко поверить, что синтаксической проверки достаточно —
    именно эта вера и пропустила дефект в production.
    """
    плохой = tmp_path / "broken.sh"
    плохой.write_text("#!/usr/bin/env bash\nset -euo pipefail\nСУХОЙ=0\necho \"$СУХОЙ\"\n",
                      encoding="utf-8")

    разбор = subprocess.run(["bash", "-n", str(плохой)], capture_output=True, text=True)
    assert разбор.returncode == 0, "bash -n внезапно стал ловить это сам"

    запуск = subprocess.run(["bash", str(плохой)], capture_output=True, text=True)
    assert запуск.returncode != 0
    assert "command not found" in запуск.stderr

    assert беды_файла(плохой.read_text(encoding="utf-8"), "broken.sh")
