"""Сборка браузера выбирается по НОМЕРУ, а не по алфавиту.

Номер сборки Playwright когда-то был вписан числом в семь файлов, и на машине
с другой сборкой браузерная приёмка молча переставала выполняться. Поиск по
шаблону это закрыл — но сортировал имена каталогов СТРОКОЙ, и строковое
сравнение ставит `chromium-980` выше `chromium-1243`. Пока у всех сборок на
хосте одинаковое число цифр, подмена незаметна: сегодня
`chromium-1243 > chromium-1234 > chromium-1140` совпадает и так.

Проверка работает на поддельных каталогах: от настоящего хоста она не зависит
и поэтому говорит о правиле, а не о том, что сейчас установлено.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]

from factory.seo import render_check  # noqa: E402


def _сборки(корень: Path, номера: list[int]) -> None:
    for номер in номера:
        путь = корень / f"chromium-{номер}" / "chrome-linux64"
        путь.mkdir(parents=True)
        (путь / "chrome").write_text("", encoding="utf-8")
        (путь / "chrome").chmod(0o755)


def test_выбирается_сборка_с_наибольшим_номером(tmp_path: Path, monkeypatch):
    """980 рядом с 1243: алфавит выбрал бы 980."""
    _сборки(tmp_path, [980, 1243, 1140])
    monkeypatch.setattr(render_check, "КАТАЛОГИ_СБОРОК", (tmp_path,))
    monkeypatch.setattr(render_check, "CHROMIUM_CANDIDATES", ())
    найдено = render_check.chromium_path()
    assert найдено is not None
    assert "chromium-1243" in найдено, найдено


def test_нечисловой_хвост_не_ломает_выбор(tmp_path: Path, monkeypatch):
    """Каталог без номера не должен ни падать, ни выигрывать."""
    _сборки(tmp_path, [1243])
    странный = tmp_path / "chromium-next" / "chrome-linux64"
    странный.mkdir(parents=True)
    (странный / "chrome").write_text("", encoding="utf-8")
    monkeypatch.setattr(render_check, "КАТАЛОГИ_СБОРОК", (tmp_path,))
    monkeypatch.setattr(render_check, "CHROMIUM_CANDIDATES", ())
    assert "chromium-1243" in (render_check.chromium_path() or "")


def test_явный_путь_главнее_шаблона(tmp_path: Path, monkeypatch):
    """`FACTORY_CHROMIUM` остаётся главнее любого поиска."""
    _сборки(tmp_path, [1243])
    свой = tmp_path / "свой-chrome"
    свой.write_text("", encoding="utf-8")
    monkeypatch.setattr(render_check, "КАТАЛОГИ_СБОРОК", (tmp_path,))
    monkeypatch.setattr(render_check, "CHROMIUM_CANDIDATES", (str(свой),))
    assert render_check.chromium_path() == str(свой)


def test_то_же_правило_в_js_реализации(tmp_path: Path):
    """Два языка — одно правило. Расхождение здесь означало бы разный выбор.

    Проверяется запуском: подделываются каталоги, корень поиска подменяется
    переменной окружения HOME, и сравнивается, что выбрала реализация на JS.
    """
    домик = tmp_path / "home"
    кеш = домик / ".cache" / "ms-playwright"
    кеш.mkdir(parents=True)
    _сборки(кеш, [980, 1243])
    сценарий = (
        "const {chromiumPath} = require(process.argv[1]);"
        "console.log(chromiumPath() || '');"
    )
    г = subprocess.run(
        ["node", "-e", сценарий, str(КОРЕНЬ / "tools" / "chromium-path.js")],
        capture_output=True, text=True, timeout=120,
        env={"HOME": str(домик), "PATH": "/usr/bin:/bin"})
    assert г.returncode == 0, г.stderr
    assert "chromium-1243" in г.stdout, г.stdout


if __name__ == "__main__":
    raise SystemExit(subprocess.call([sys.executable, "-m", "pytest", __file__, "-q"]))
