"""Широкий установщик не вправе УБРАТЬ ячейку из корневого реестра.

Повод измерен 13.10. `install-cell-executor.sh` кладёт в корневую копию
`config` целиком (`cp -a "$SRC_ROOT/config"`), а значит и `site-cells.json`.
Рабочие деревья разошлись: у дерева службы в реестре 25 ячеек, у рабочего — 33.
Установка из первого убрала бы восемь витрин и `animedia-01.runtime.data_dir`,
по которому сбор данных витрин находит живую `animedia.icu`, — то есть вернула
бы ровно тот пробел резервной копии, который был только что закрыт, и вернула
бы молча: отказа у широкого установщика на этот случай не было.

У узкого установщика защита есть («ячейки нет в пакете»). Здесь закрепляется,
что она появилась и у широкого, и проверяется НЕ наличие текста, а поведение:
встроенная проверка запускается на трёх парах реестров.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
УСТАНОВЩИК = КОРЕНЬ / "automation" / "host" / "install-cell-executor.sh"


def _встроенная_проверка() -> str:
    """Тело проверки ИЗ установщика: тест привязан к его тексту, не к копии."""
    текст = УСТАНОВЩИК.read_text(encoding="utf-8")
    # Метка `<<'PYCELLS'` стоит не в конце строки: за ней идёт продолжение `\`
    # и строка `die`. Поэтому тело берётся от первой строки с `import`.
    куски = re.findall(r"<<'PYCELLS'(.*?)\nPYCELLS\n", текст, re.S)
    assert куски, "в установщике нет встроенной проверки состава реестра"
    assert len(куски) == 1, f"ожидалась одна проверка, найдено {len(куски)}"
    строки = куски[0].splitlines()
    начало = next((i for i, с in enumerate(строки) if с.startswith("import")), None)
    assert начало is not None, "во встроенной проверке нет кода на python"
    return "\n".join(строки[начало:])


def _реестр(путь: Path, site_ids: list[str]) -> Path:
    путь.write_text(json.dumps({
        "schema_version": 1,
        "cells": [{"site_id": s, "domain": f"{s}.example"} for s in site_ids],
    }, ensure_ascii=False), encoding="utf-8")
    return путь


def _запустить(стоит: Path, ставим: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-", str(стоит), str(ставим)],
                          input=_встроенная_проверка(), capture_output=True,
                          text=True, timeout=60)


def test_проверка_отказывает_при_потере_ячейки(tmp_path):
    """Тот самый измеренный случай: 33 стоит, 25 ставим."""
    все = [f"lords-{n:02d}" for n in range(1, 10)] + [f"lords-{n}" for n in range(10, 18)]
    стоит = _реестр(tmp_path / "стоит.json", все)
    ставим = _реестр(tmp_path / "ставим.json", все[:9])
    готово = _запустить(стоит, ставим)
    assert готово.returncode == 1, готово.stdout
    assert "lords-10" in готово.stdout and "lords-17" in готово.stdout
    assert "пропадает 8" in готово.stdout, готово.stdout


def test_проверка_пропускает_надмножество(tmp_path):
    """Добавление ячеек — штатный случай установки, а не беда."""
    стоит = _реестр(tmp_path / "стоит.json", ["lords-01", "lords-02"])
    ставим = _реестр(tmp_path / "ставим.json", ["lords-01", "lords-02", "lords-10"])
    готово = _запустить(стоит, ставим)
    assert готово.returncode == 0, готово.stdout
    assert "добавляется 1" in готово.stdout, готово.stdout


def test_проверка_пропускает_равный_состав(tmp_path):
    стоит = _реестр(tmp_path / "стоит.json", ["lords-01", "animedia-01"])
    ставим = _реестр(tmp_path / "ставим.json", ["animedia-01", "lords-01"])
    готово = _запустить(стоит, ставим)
    assert готово.returncode == 0, готово.stdout
    assert "пропадает 0" in готово.stdout, готово.stdout


def test_нечитаемый_установленный_реестр_это_отказ(tmp_path):
    """«Не прочитали» и «совпадает» — разные вещи; склейка скрыла бы потерю."""
    стоит = tmp_path / "битый.json"
    стоит.write_text("{не json", encoding="utf-8")
    ставим = _реестр(tmp_path / "ставим.json", ["lords-01"])
    готово = _запустить(стоит, ставим)
    assert готово.returncode == 1, готово.stdout
    assert "предел измерения" in готово.stdout, готово.stdout


def test_проверка_вызывается_до_замены_копии():
    """Отказ после `mv` оставил бы корневую копию уже подменённой."""
    текст = УСТАНОВЩИК.read_text(encoding="utf-8")
    проверка = текст.index("<<'PYCELLS'")
    замена = текст.index('run mv "$DEST" "$DEST.prev"')
    assert проверка < замена, "проверка состава стоит ПОСЛЕ замены корневой копии"


def test_проверка_не_меняет_ничего():
    """Она читает два файла; любая запись здесь была бы правкой постоянных данных."""
    тело = _встроенная_проверка()
    for запрещено in ("open(", "write", "unlink", "rename", "mkdir", "rmtree"):
        if запрещено == "open(":
            # единственное `open` — чтение в `состав`
            assert тело.count("open(") == 1, тело
            assert 'encoding="utf-8"' in тело
            continue
        assert запрещено not in тело, f"во встроенной проверке есть {запрещено}"
