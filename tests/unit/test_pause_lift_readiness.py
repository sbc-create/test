"""Готовность к снятию паузы: оба исхода проверяются исполнением.

Повод у инструмента измеренный: 12.10 пробную публикацию на `zonafilm.space`
начали, когда мост исполнял ещё старый код. Сверка дала «подменено авторство:
3», витрину вернули в `PAUSED_PUBLISH`, и попытка стоила живой публикации.
Отличить «правка лежит» от «правка исполняется» можно только стадией
«загружено процессом».

Проверяется и «НЕ ГОТОВО», и «ГОТОВО»: инструмент, который на любом входе
отвечает «не готово», доверия не несёт.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
ПУТЬ = КОРЕНЬ / "automation" / "local" / "pause-lift-readiness.py"

ВИД = '''"""Подложный единый вид состояния доставки для стенда."""
from dataclasses import dataclass

НЕТ = "нет"
ДА = "да"
НЕ_ИЗМЕРЕНО = "не измерено"


@dataclass(frozen=True)
class Компонент:
    ключ: str
    имя: str


СОСТАВ = (Компонент(ключ="editorial", имя="проба"),)

ЗАГРУЖЕНО = "{загружено}"


def разобрать(к):
    return {{
        "подготовлено": (ДА, "сумма совпадает"),
        "установлено": (ДА, "совпадает с ветвью"),
        "загружено": (ЗАГРУЖЕНО, "{причина}"),
        "проверено": (НЕ_ИЗМЕРЕНО, "артефакт не объявлен"),
    }}
'''


def _стенд(tmp_path: Path, *, загружено: str, причина: str) -> Path:
    путь = tmp_path / "delivery-state.py"
    путь.write_text(ВИД.format(загружено=загружено, причина=причина),
                    encoding="utf-8")
    return путь


def _прогон(вид: Path):
    return subprocess.run(
        [sys.executable, str(ПУТЬ), "--view", str(вид)],
        capture_output=True, text=True, timeout=180, cwd=str(КОРЕНЬ))


def test_процесс_исполняет_старый_код_это_не_готово(tmp_path):
    г = _прогон(_стенд(tmp_path, загружено="нет",
                       причина="pid 1 стартовал раньше правки"))
    assert г.returncode == 1, г.stdout + г.stderr
    assert "НЕ ГОТОВО" in г.stdout, г.stdout
    # Причина и следующий шаг названы: без них вывод не действие, а мнение.
    assert "pid 1 стартовал раньше правки" in г.stdout
    assert "systemctl restart site-factory-mcp" in г.stdout
    # И история названа, чтобы попытку не повторили в том же состоянии.
    assert "подменено авторство: 3" in г.stdout


def test_процесс_исполняет_исправленный_код_это_готово(tmp_path):
    """Обратная сторона: иначе инструмент отвечал бы «нет» на любом входе."""
    г = _прогон(_стенд(tmp_path, загружено="да", причина="pid 2 новее правки"))
    assert г.returncode == 0, г.stdout + г.stderr
    assert "ГОТОВО" in г.stdout, г.stdout
    assert "НЕ ГОТОВО" not in г.stdout
    # Порядок дальше назван по шагам, с конкретными командами.
    assert "--snapshot" in г.stdout and "--compare" in г.stdout
    assert "остаётся в PAUSED_PUBLISH" in г.stdout


def test_вид_состояния_не_прочитан_это_не_измерено(tmp_path):
    г = subprocess.run(
        [sys.executable, str(ПУТЬ), "--view", str(tmp_path / "нет.py")],
        capture_output=True, text=True, timeout=180, cwd=str(КОРЕНЬ))
    assert г.returncode == 2, г.stdout
    assert "НЕ ИЗМЕРЕНО" in г.stdout
    assert "вывод о готовности не делается" in г.stdout


def test_неизвестный_компонент_называет_известные(tmp_path):
    вид = _стенд(tmp_path, загружено="да", причина="неважно")
    г = subprocess.run(
        [sys.executable, str(ПУТЬ), "--view", str(вид),
         "--component", "нет-такого"],
        capture_output=True, text=True, timeout=180, cwd=str(КОРЕНЬ))
    assert г.returncode == 2, г.stdout
    assert "editorial" in г.stdout, г.stdout


def test_стадия_не_переписана_а_импортирована():
    """Второе определение той же стадии разошлось бы с первым молча."""
    текст = ПУТЬ.read_text(encoding="utf-8")
    assert "importlib" in текст
    assert "delivery-state.py" in текст
    assert "sys.modules.setdefault" in текст, (
        "модуль должен регистрироваться до exec_module: dataclasses ищет его "
        "в sys.modules при разборе класса")
