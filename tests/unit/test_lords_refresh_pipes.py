"""Обновление каталога не должно падать из-за оборванной трубы.

Цикл обновления однажды остановился с `grep: write error: Broken pipe` и
кодом 2. Сайты при этом отвечали двумястами — но обновляться перестали, а
такую поломку по главной странице не видно.

Причина: `grep -o … | head -1` при включённом `pipefail`. Пока вывод grep
помещался в буфер трубы, всё работало. На главной появилась карусель, ссылок
на произведения стало вчетверо больше, буфер переполнился — и `head`,
закрывшись после первой строки, начал обрывать grep сигналом SIGPIPE.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

SCRIPTS = sorted(Path("automation/host").glob("*.sh"))


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


class TestNoPipeIntoHead:
    @pytest.mark.parametrize("path", SCRIPTS, ids=lambda p: p.name)
    def test_a_producer_is_never_cut_off_by_head(self, path):
        """`… | head -n` рвёт производителя, и при pipefail это провал цикла."""
        text = read(path)
        if "pipefail" not in text:
            pytest.skip("в этом сценарии pipefail не включён")
        offenders = []
        for number, line in enumerate(text.splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            if re.search(r"\|\s*head\b", line) and re.search(r"\bgrep\b", line):
                offenders.append(f"{number}: {line.strip()[:90]}")
        assert offenders == [], (
            f"{path.name}: вывод grep обрывается head — при pipefail это выход "
            f"с ошибкой:\n" + "\n".join(offenders))


class TestTheRefreshScriptStaysValid:
    @pytest.mark.parametrize("path", SCRIPTS, ids=lambda p: p.name)
    def test_the_shell_parses(self, path):
        result = subprocess.run(["bash", "-n", str(path)],
                                capture_output=True, text=True, check=False)
        assert result.returncode == 0, result.stderr[-300:]

    def test_the_first_match_is_taken_without_a_pipe(self):
        text = read(Path("automation/host/lords-content-refresh.sh"))
        # `grep -m1` останавливается сам и обрывать его некому.
        assert "grep -m1" in text
