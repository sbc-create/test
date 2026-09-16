"""Имена в shell-сценариях выкладки — только ASCII.

Дефект LORDS-NIGHT-RUNNER-NONASCII-VAR-34. Runner ночной выкладки не запустился
на боевом хосте:

    line 25: СВОЙ=/usr/local/sbin/lords-night-release: No such file or directory

Кириллица недопустима в имени переменной, поэтому `СВОЙ="$(readlink -f "$0")"`
разбирается не как присваивание, а как имя команды. `bash -n` пропускает это и
пропустит всегда: синтаксически строка безупречна. Проверка исполнения нужна
отдельная — вот она.

Первая проверка ниже важнее остальных: она предъявляет ровно ту строку, что
уронила выкладку, и требует, чтобы контролёр её отверг. Контролёр, который
молчит на известном дефекте, хуже отсутствующего — он создаёт уверенность.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from shell_ascii_check import нарушения  # noqa: E402

СЦЕНАРИИ = (
    "automation/host/lords-unit-launch.sh",
    "automation/host/lords-release-runner.sh",
    "automation/host/lords-release-conduct.sh",
    "automation/host/lords-release-launch.tmpl",
)


class TestКонтролёрЛовитИзвестныйДефект:
    def test_строка_уронившая_выкладку_отвергается(self):
        беды = нарушения('СВОЙ="$(readlink -f "$0")"\n')
        assert беды, "контролёр молчит на строке, которая уронила боевую выкладку"

    def test_кириллическое_имя_функции_отвергается(self):
        assert нарушения("свод() {\n  echo x\n}\n")

    def test_кириллическая_переменная_цикла_отвергается(self):
        assert нарушения("for сайт in a b; do echo $сайт; done\n")

    def test_голое_кириллическое_слово_отвергается(self):
        assert нарушения("phase предполёт\n")


class TestКонтролёрНеШумит:
    def test_русский_комментарий_разрешён(self):
        assert нарушения("# это комментарий про витрину\nx=1\n") == []

    def test_русское_сообщение_разрешено(self):
        assert нарушения('echo "витрина не тронута"\n') == []

    def test_русское_значение_в_кавычках_разрешено(self):
        assert нарушения('REUSED="нет"\n') == []

    def test_подстановка_внутри_кавычек_разбирается_верно(self):
        """`x="$(cmd "путь" || echo "СЛОВО")"` — безупречная строка.

        Первая редакция контролёра считала подстановку только вне кавычек и
        объявляла эту строку нарушением. Кавычки внутри `$( )` независимы от
        внешних, и одиночные кавычки подстановку не открывают.
        """
        строка = 'v="$(cat "/run/${s}-release.verdict" 2>/dev/null || echo "НЕТ_ИТОГА")"\n'
        assert нарушения(строка) == []

    def test_кириллица_в_одиночных_кавычках_разрешена(self):
        assert нарушения("echo 'витрина цела'\n") == []

    def test_тело_heredoc_не_проверяется(self):
        текст = "cat > f <<'PYEOF'\nимя = 1\nPYEOF\n"
        assert нарушения(текст) == []


class TestСценарииВыкладкиЧисты:
    @pytest.mark.parametrize("имя", СЦЕНАРИИ)
    def test_сценарий_без_не_ascii_имён(self, имя):
        беды = нарушения((ROOT / имя).read_text(encoding="utf-8"))
        assert беды == [], f"{имя}: " + "; ".join(f"строка {n}: {к}" for n, к in беды)

    @pytest.mark.parametrize("имя", СЦЕНАРИИ)
    def test_сценарий_разбирается_bash(self, имя):
        r = subprocess.run(["bash", "-n", str(ROOT / имя)], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr

    def test_инструмент_возвращает_код_один_при_нарушении(self, tmp_path):
        плохой = tmp_path / "плохой.sh"
        плохой.write_text('ПЕРЕМЕННАЯ=1\n', encoding="utf-8")
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "shell_ascii_check.py"),
                            str(плохой)], capture_output=True, text=True)
        assert r.returncode == 1, r.stdout + r.stderr
        assert "не-ASCII" in r.stdout
