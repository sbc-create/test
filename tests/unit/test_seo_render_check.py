"""REQ-SEO-RENDER: браузер находится по фактической раскладке, а не по вшитой версии.

Проверка отрисованного DOM — единственный способ доказать, что тег аналитики
действительно сработал, а тег-ссылка действительно кликабельна. Если поиск
браузера промахивается, фабрика честно скажет «недоступно» — и молча потеряет
целый класс проверок. Поэтому промах ищется тестом, а не глазами.
"""
from pathlib import Path

import pytest

from factory.seo import render_check


@pytest.fixture
def browser_root(tmp_path, monkeypatch):
    monkeypatch.setattr(render_check, "BROWSER_ROOT", tmp_path)
    monkeypatch.delenv("FACTORY_CHROMIUM", raising=False)
    return tmp_path


def _install(root: Path, version: str, layout: str) -> Path:
    binary = root / f"chromium-{version}" / layout / "chrome"
    binary.parent.mkdir(parents=True)
    binary.write_text("#!/bin/sh\n", encoding="utf-8")
    binary.chmod(0o755)
    return binary


def test_finds_chromium_in_the_current_playwright_layout(browser_root):
    """Playwright переехал с chrome-linux на chrome-linux64 и сменил версию."""
    binary = _install(browser_root, "1234", "chrome-linux64")
    assert render_check.chromium_path() == str(binary)


def test_finds_chromium_in_the_older_layout(browser_root):
    """Старая раскладка обязана продолжать работать."""
    binary = _install(browser_root, "1194", "chrome-linux")
    assert render_check.chromium_path() == str(binary)


def test_newest_build_wins_when_numbers_differ_in_length(browser_root):
    """Номер сборки — число, а не строка.

    Playwright уже перешёл с трёхзначных номеров на четырёхзначные. При
    лексикографическом сравнении «chromium-999» оказывается старше
    «chromium-1234», и поиск молча берёт устаревший браузер: он существует и
    запускается, поэтому ошибка не проявится ни падением, ни сообщением.
    """
    _install(browser_root, "999", "chrome-linux")
    newest = _install(browser_root, "1234", "chrome-linux64")
    assert render_check.chromium_path() == str(newest)


def test_explicit_env_var_wins(browser_root, tmp_path, monkeypatch):
    _install(browser_root, "1234", "chrome-linux64")
    chosen = tmp_path / "own-chrome"
    chosen.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setenv("FACTORY_CHROMIUM", str(chosen))
    assert render_check.chromium_path() == str(chosen)


def test_missing_browser_is_reported_as_absent(browser_root, monkeypatch):
    """Отсутствие браузера не должно превращаться в выдуманный путь."""
    monkeypatch.setattr(render_check.shutil, "which", lambda _name: None)
    assert render_check.chromium_path() is None
