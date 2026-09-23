"""Подключение учётных данных: имя, скрытность, различимость состояний.

Проверка происхождения выпуска — единственное, что отделяет автоматическую
выкладку от исполнения произвольного кода на живом сайте. Поэтому у неё не
может быть тихого «не смогли спросить»: либо связка доказана, либо заявка
отвергнута до единой операции.

Здесь сторожатся три вещи, каждая из которых однажды ломалась молча:
имя учётных данных должно совпадать у юнита и у кода, токен не должен попадать
в вывод, а установка обязана отличать «установлен» от «готов к выпуску».
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(КОРЕНЬ))

from factory.cell import executor, registry  # noqa: E402

СЦЕНАРИЙ = КОРЕНЬ / "automation" / "host" / "install-gh-credential.sh"
УСТАНОВЩИК = КОРЕНЬ / "automation" / "host" / "install-cell-executor.sh"


def test_имя_учётных_данных_совпадает_у_юнита_и_кода():
    """Расхождение здесь выглядит как «токен есть, а gh не видит его»."""
    текст = СЦЕНАРИЙ.read_text(encoding="utf-8")
    assert f"LoadCredential=gh-token:" in текст
    assert executor.ФАЙЛ_ТОКЕНА == "gh-token"


def test_токен_нигде_не_печатается():
    """Секрет не попадает ни в вывод, ни в историю, ни в аргументы."""
    текст = СЦЕНАРИЙ.read_text(encoding="utf-8")
    for опасное in ("echo $token", 'echo "$token"', "printf '%s\\n' \"$token\"",
                    "cat $TOKEN_FILE", 'cat "$TOKEN_FILE"', "set -x"):
        assert опасное not in текст, f"сценарий может вывести секрет: {опасное}"
    # Токен не бывает аргументом командной строки: аргументы видны в ps и
    # остаются в истории оболочки.
    assert "--token" not in текст
    assert "read -rs" in текст or "read -r -s" in текст


def test_права_токена_минимальны_и_названы():
    """Токен на запись дал бы службе менять то, что она проверяет."""
    текст = СЦЕНАРИЙ.read_text(encoding="utf-8")
    assert "fine-grained" in текст
    assert "Actions: Read-only" in текст
    assert "Metadata: Read-only" in текст
    assert "0600" in текст


def test_установщик_различает_готов_и_заблокирован():
    """«Установлен» и «готов к выпуску» — разные состояния и разные коды."""
    текст = УСТАНОВЩИК.read_text(encoding="utf-8")
    assert "ГОТОВ К ВЫПУСКУ" in текст
    assert "УСТАНОВЛЕН, ВЫПУСК ЗАБЛОКИРОВАН" in текст
    assert re.search(r"\nexit 3\b", текст), "заблокированная установка обязана"\
        " возвращать отличный от нуля код"


def test_проверка_идёт_из_контекста_службы():
    """Успешный gh у того, кто запускает сценарий, ничего не доказывает."""
    текст = СЦЕНАРИЙ.read_text(encoding="utf-8")
    assert "systemd-run" in текст
    assert "LoadCredential=gh-token" in текст
    assert "factory cell ci-ready" in текст


def test_политика_веток_одна_на_обе_стороны():
    """Свой список у триггера читался бы как «CI зелёный, а выпуска нет»."""
    from factory.cell import trigger
    assert trigger.РАЗРЕШЁННЫЕ_ВЕТКИ is registry.ВЕТКИ_ВЫПУСКА
    assert registry.ветка_разрешена("claude/extract-zonafilm-space")
    assert registry.ветка_разрешена("main")
    assert not registry.ветка_разрешена("claude/community-comments-platform-01")
