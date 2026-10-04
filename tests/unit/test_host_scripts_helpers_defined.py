"""Хостовый скрипт не вправе звать функцию вывода, которой у него нет.

Случай измерен 2026-10-04 и стоил установки. В `install-cell-executor.sh`
оказалась строка `ok "загруженный юнит…"`, а функции `ok` в этом скрипте нет —
она есть у соседних сценариев, и строка переехала между ними. При
`set -Eeuo pipefail` неизвестная команда даёт код 127, и установка оборвалась
на предпоследнем шаге: `install-cell-executor.sh: line 273: ok: command not
found`. Главное к тому моменту уже было сделано, то есть отказ был ложным — и
хуже того, он выглядел отказом установки.

`bash -n` такого не ловит: вызов неизвестной команды синтаксически законен.
Поэтому проверка живёт отдельно, как и проверка ASCII-имён.
"""
from __future__ import annotations

import pathlib
import re

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]

#: Имена, которые в этих сценариях означают функции вывода и шагов. Список
#: закрытый: он описывает принятый словарь, а не угадывает произвольные
#: команды.
ПОМОЩНИКИ = {"log", "ok", "die", "run", "say", "warn", "note", "step", "fail",
             "cut_chars", "revert_and_die", "ask"}


def сценарии() -> list[pathlib.Path]:
    исключить = {".git", ".venv", "var", "node_modules"}
    return sorted(p for p in (КОРЕНЬ / "automation").rglob("*.sh")
                  if not (исключить & set(p.relative_to(КОРЕНЬ).parts)))


def _без_комментариев(текст: str) -> list[str]:
    """Строки кода без комментариев и без тел heredoc.

    Тело heredoc — не код оболочки: `docker compose run` в примере
    использования вызовом не является, и считать его таковым значит получить
    ложное срабатывание (измерено на `yummy-content-run.sh`).
    """
    строки: list[str] = []
    метка = None
    for с in текст.splitlines():
        if метка is not None:
            if с.strip() == метка:
                метка = None
            continue
        без = с.split("#", 1)[0]
        строки.append(без)
        м = re.search(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1", без)
        if м:
            метка = м.group(2)
    return строки


def test_сценарии_найдены():
    assert len(сценарии()) >= 5


@pytest.mark.parametrize("путь", сценарии(),
                         ids=lambda p: str(p.relative_to(КОРЕНЬ)))
def test_все_вызванные_помощники_определены(путь: pathlib.Path) -> None:
    текст = путь.read_text(encoding="utf-8")
    строки = _без_комментариев(текст)
    код = "\n".join(строки)
    объявлены = set(re.findall(r"^\s*([a-z_][a-z0-9_]*)\s*\(\)\s*\{", код, re.M))
    вызваны = set()
    for с in строки:
        # Вызов в начале строки, после `;`, `&&`, `||`, `(` и в ветке `case`.
        for м in re.finditer(r"(?:^|[;&|(]|\)\s)\s*([a-z_][a-z0-9_]*)\s+[\"'$]", с):
            if м.group(1) in ПОМОЩНИКИ:
                вызваны.add(м.group(1))
    нет = sorted(вызваны - объявлены)
    assert not нет, (
        f"{путь.name} зовёт функции вывода, которых в нём не определено: {нет}. "
        f"Определены: {sorted(объявлены & ПОМОЩНИКИ)}. При set -e это код 127 и "
        "обрыв сценария на полпути")


def test_проверка_ловит_перенесённую_строку(tmp_path):
    """Доказательство, что сторож не пустой: тот самый случай."""
    плохой = tmp_path / "broken.sh"
    плохой.write_text(
        "#!/usr/bin/env bash\nset -Eeuo pipefail\n"
        "log() { printf '%s\\n' \"$*\"; }\n"
        "log \"шаг\"\n"
        "ok \"готово\"\n", encoding="utf-8")
    строки = _без_комментариев(плохой.read_text(encoding="utf-8"))
    объявлены = set(re.findall(r"^\s*([a-z_][a-z0-9_]*)\s*\(\)\s*\{",
                               "\n".join(строки), re.M))
    вызваны = {м.group(1) for с in строки
               for м in re.finditer(r"(?:^|[;&|(]|\)\s)\s*([a-z_][a-z0-9_]*)\s+[\"'$]", с)
               if м.group(1) in ПОМОЩНИКИ}
    assert sorted(вызваны - объявлены) == ["ok"]
