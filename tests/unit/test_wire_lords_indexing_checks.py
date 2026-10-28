"""Проверки доставщика проверок режима индексации (MOD-216, пробел 1 из 4).

Главное, что здесь закрепляется, — ОТКАЗ. Молчаливое копирование проверки на
витрину, где наблюдаемое поведение механизма другое, даёт вечно красную
проверку, а такие перестают читать: ровно этим кончилась попытка перенести
checks/header_fit.py 27.10.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import textwrap

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ПУТЬ = КОРЕНЬ / "automation" / "local" / "wire-lords-indexing-checks.py"

МОДУЛЬ_РЕЖИМА = '''
ЗАКРЫТ = "CLOSED"
ОТКРЫТ = "OPEN"
МЕТА = {ЗАКРЫТ: "noindex, nofollow", ОТКРЫТ: "index, follow"}
ЗАКРЫТЫЙ_ROBOTS = "User-agent: *\\nDisallow: /\\n"

def robots_txt(состояние, sitemap=""):
    if состояние != ОТКРЫТ:
        return ЗАКРЫТЫЙ_ROBOTS
    строки = ["User-agent: *", "Allow: /"]
    {ДОБАВКА}
    if sitemap:
        строки.append(f"Sitemap: {sitemap}")
    return "\\n".join(строки) + "\\n"
'''


def _инструмент():
    спец = importlib.util.spec_from_file_location("wire_lords_indexing_checks", ПУТЬ)
    assert спец and спец.loader
    м = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(м)
    return м


@pytest.fixture(scope="module")
def ин():
    return _инструмент()


def _витрина(корень: pathlib.Path, домен: str, добавка: str = "",
             с_проверками: bool = False) -> pathlib.Path:
    (корень / "src").mkdir(parents=True)
    (корень / "checks").mkdir(parents=True)
    (корень / "config").mkdir(parents=True)
    (корень / "src" / "indexing_mode.py").write_text(
        МОДУЛЬ_РЕЖИМА.replace("{ДОБАВКА}", добавка), encoding="utf-8")
    (корень / "config" / "site.json").write_text(
        json.dumps({"domain": домен}), encoding="utf-8")
    if с_проверками:
        for имя in ("indexing_mode_rules.py", "indexing_live_switch.py"):
            (корень / "checks" / имя).write_text(
                f"# проверка {имя}\n", encoding="utf-8")
    return корень


def test_инструмент_на_месте():
    assert ПУТЬ.is_file()


def test_доставка_при_совпадении_поведения(ин, tmp_path):
    ист = _витрина(tmp_path / "ист", "a.test", с_проверками=True)
    цель = _витрина(tmp_path / "цель", "b.test")
    исход, пояснение = ин.доставить(ист, цель, писать=True)
    assert исход == "ok", пояснение
    assert (цель / "checks" / "indexing_mode_rules.py").is_file()
    assert (цель / "checks" / "indexing_live_switch.py").is_file()


def test_добавка_не_меняющая_поведения_не_мешает(ин, tmp_path):
    """Исходники разошлись, наблюдаемое поведение — нет: доставка идёт."""
    ист = _витрина(tmp_path / "ист", "a.test", с_проверками=True)
    цель = _витрина(tmp_path / "цель", "b.test",
                    добавка='pass  # блок, не меняющий отдачи')
    исход, пояснение = ин.доставить(ист, цель, писать=True)
    assert исход == "ok", пояснение


def test_отказ_когда_поведение_разошлось(ин, tmp_path):
    """Цель обещает карту без адреса — проверка там упала бы. Отказ."""
    ист = _витрина(tmp_path / "ист", "a.test", с_проверками=True)
    цель = _витрина(tmp_path / "цель", "b.test",
                    добавка='строки.append("Sitemap: https://b.test/sitemap.xml")')
    исход, пояснение = ин.доставить(ист, цель, писать=True)
    assert исход == "refuse"
    assert "расходится" in пояснение
    assert "открытый обещает карту" in пояснение
    assert not (цель / "checks" / "indexing_mode_rules.py").exists(), \
        "при отказе не должно быть записано ни одного файла"


def test_отказ_когда_мета_другая(ин, tmp_path):
    ист = _витрина(tmp_path / "ист", "a.test", с_проверками=True)
    цель = _витрина(tmp_path / "цель", "b.test")
    текст = (цель / "src" / "indexing_mode.py").read_text(encoding="utf-8")
    (цель / "src" / "indexing_mode.py").write_text(
        текст.replace('"index, follow"', '"all"'), encoding="utf-8")
    исход, пояснение = ин.доставить(ист, цель, писать=True)
    assert исход == "refuse"
    assert "мета открытого" in пояснение
    assert not (цель / "checks" / "indexing_mode_rules.py").exists()


def test_отказ_без_механизма(ин, tmp_path):
    ист = _витрина(tmp_path / "ист", "a.test", с_проверками=True)
    цель = _витрина(tmp_path / "цель", "b.test")
    (цель / "src" / "indexing_mode.py").unlink()
    исход, пояснение = ин.доставить(ист, цель, писать=True)
    assert исход == "refuse"
    assert "indexing_mode.py" in пояснение


def test_отказ_без_домена_в_настройке(ин, tmp_path):
    """Проверка берёт домен из настройки; подставлять своё нельзя."""
    ист = _витрина(tmp_path / "ист", "a.test", с_проверками=True)
    цель = _витрина(tmp_path / "цель", "b.test")
    (цель / "config" / "site.json").write_text(json.dumps({}), encoding="utf-8")
    исход, пояснение = ин.доставить(ист, цель, писать=True)
    assert исход == "refuse"
    assert "domain" in пояснение
    assert not (цель / "checks" / "indexing_mode_rules.py").exists()


def test_существующая_проверка_не_перезаписывается(ин, tmp_path):
    ист = _витрина(tmp_path / "ист", "a.test", с_проверками=True)
    цель = _витрина(tmp_path / "цель", "b.test", с_проверками=True)
    своё = (цель / "checks" / "indexing_mode_rules.py").read_bytes()
    исход, пояснение = ин.доставить(ист, цель, писать=True)
    assert исход == "skip"
    assert (цель / "checks" / "indexing_mode_rules.py").read_bytes() == своё


def test_dry_run_не_пишет(ин, tmp_path):
    ист = _витрина(tmp_path / "ист", "a.test", с_проверками=True)
    цель = _витрина(tmp_path / "цель", "b.test")
    исход, пояснение = ин.доставить(ист, цель, писать=False)
    assert исход == "ok"
    assert "будет доставлено" in пояснение
    assert not (цель / "checks" / "indexing_mode_rules.py").exists()


def test_нерабочий_модуль_источника_останавливает(ин, tmp_path):
    ист = _витрина(tmp_path / "ист", "a.test", с_проверками=True)
    (ист / "src" / "indexing_mode.py").write_text(
        "это не python(", encoding="utf-8")
    цель = _витрина(tmp_path / "цель", "b.test")
    исход, пояснение = ин.доставить(ист, цель, писать=True)
    assert исход == "refuse"
    assert "источник" in пояснение
