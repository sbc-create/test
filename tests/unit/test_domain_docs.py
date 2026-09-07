"""REQ-DOMAIN-DOCS: инструкции по доменам не отстают от реестра.

Инструкция, которую ведут отдельно от того, что она описывает, расходится с
ней на первой правке — и расхождением себя не выдаёт. В этом контуре так уже
случалось дважды: настройка навигации, которую не читал никто, и отпечаток
шаблона, отвечавший не на тот вопрос, который по нему задавали.

Поэтому текст производный, а эта проверка — то, что не даёт ему отстать.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
СЦЕНАРИЙ = КОРЕНЬ / "tests" / "tools" / "domain_docs.py"
КАТАЛОГ = КОРЕНЬ / "docs" / "domains"


@pytest.fixture(scope="module")
def сборщик():
    спец = importlib.util.spec_from_file_location("domain_docs", СЦЕНАРИЙ)
    модуль = importlib.util.module_from_spec(спец)
    sys.modules["domain_docs"] = модуль
    спец.loader.exec_module(модуль)
    return модуль


def test_инструкция_есть_у_каждого_домена(сборщик):
    собранное = сборщик.собрать()
    отсутствуют = [ид for ид in собранное if not (КАТАЛОГ / f"{ид}.md").is_file()]
    assert not отсутствуют, (
        f"домены без инструкции: {отсутствуют} — пересоберите: "
        f"python3 tests/tools/domain_docs.py --write")


def test_инструкции_совпадают_с_реестром(сборщик):
    разошлись = [
        ид for ид, текст in сборщик.собрать().items()
        if (КАТАЛОГ / f"{ид}.md").is_file()
        and (КАТАЛОГ / f"{ид}.md").read_text(encoding="utf-8") != текст
    ]
    assert not разошлись, (
        f"инструкции отстали от реестра: {разошлись} — пересоберите: "
        f"python3 tests/tools/domain_docs.py --write")


def test_лишних_инструкций_нет(сборщик):
    известные = set(сборщик.собрать())
    лишние = [п.stem for п in КАТАЛОГ.glob("*.md") if п.stem not in известные]
    assert not лишние, (
        f"инструкции доменов, которых в реестре нет: {лишние} — домен убрали, "
        f"а его описание осталось и продолжает утверждать своё")
