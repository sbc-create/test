"""Матрица объявляет формат URL — ворота обязаны его проверять.

`url_policy` фиксирует `case: lower` и `word_separator: "-"`. Обе величины
объявлены и до сих пор не проверялись ничем: сборки им соответствуют, потому
что генератор так устроен, а не потому, что кто-то следит.

Адрес с заглавной буквой или подчёркиванием — это не косметика. Он рождает
вторую версию той же страницы: `/Lekcii/` и `/lekcii/` для поисковой системы
разные, а `page_one_url` и `trailing_slash` уже проверяются рядом именно
затем, чтобы одна страница не размножалась по адресам.
"""
from __future__ import annotations

import json
import shutil

import pytest

from factory import build as build_mod
from factory.seo.lint import lint


@pytest.fixture(scope="module")
def built():
    return build_mod.build("pilot-local")


@pytest.fixture
def sandbox(built, tmp_path):
    target = tmp_path / "build"
    shutil.copytree(built.output, target)
    return target


def criticals(build_dir):
    return [f for f in lint(build_dir).findings if f.severity == "critical"]


def _retarget(build_dir, old_path: str, new_path: str) -> None:
    """Переименовать маршрут, оставив файл на месте: меняется только адрес."""
    routes_file = build_dir / "routes.json"
    config = json.loads(routes_file.read_text(encoding="utf-8"))
    for route in config["routes"]:
        if route["path"] == old_path:
            route["path"] = new_path
            if route.get("canonical"):
                route["canonical"] = route["canonical"].replace(old_path, new_path)
            break
    else:
        raise AssertionError(f"маршрут {old_path} не найден в сборке")
    routes_file.write_text(json.dumps(config), encoding="utf-8")


def test_real_build_satisfies_the_url_policy(sandbox):
    """Опора: на исправной сборке новая проверка молчит."""
    assert not [f for f in criticals(sandbox) if f.check == "url-policy"]


def test_uppercase_in_path_is_refused(sandbox):
    _retarget(sandbox, "/lekcii/", "/Lekcii/")
    assert any(f.check == "url-policy" for f in criticals(sandbox))


def test_underscore_in_path_is_refused(sandbox):
    _retarget(sandbox, "/lekcii/", "/lekcii_arhiv/")
    assert any(f.check == "url-policy" for f in criticals(sandbox))
