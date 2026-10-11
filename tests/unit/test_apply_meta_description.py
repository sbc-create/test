"""apply-meta-description.py: заглушка описания заменяется по якорям, повтор ничего не меняет."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
спец = importlib.util.spec_from_file_location(
    "apply_meta_description", ROOT / "automation" / "host" / "apply-meta-description.py"
)
инструмент = importlib.util.module_from_spec(спец)
спец.loader.exec_module(инструмент)

ОБРАЗЕЦ = '''class Вид:
    pass


def факты(вид: Вид, запись: dict, деталь: dict) -> list:
    return []


class ВидЛордс(Вид):
    def тайтл(self, запись, деталь):
        краткое = (описание[:180] if описание else
                   f"{имя}: {запись.get('kind') or ''} {запись.get('year') or ''}".strip())


class ВидЗона(Вид):
    def тайтл(self, запись, деталь):
        краткое = (meta_desc[:180] if meta_desc else
                   f"{имя}: {запись.get('kind') or ''} {запись.get('year') or ''}".strip())
'''


def test_both_stub_forms_are_replaced_and_rerun_is_a_no_op():
    новый, n = инструмент.привести(ОБРАЗЕЦ)
    assert n == 2
    assert "краткое_описание(имя, запись, деталь, описание, self.имя)" in новый
    assert "краткое_описание(имя, запись, деталь, meta_desc, self.имя)" in новый
    assert новый.count("def краткое_описание(") == 1
    assert инструмент.привести(новый) == (новый, 0)


def test_helper_builds_the_description_from_catalog_facts():
    пространство: dict = {}
    exec(инструмент.ПОМОЩНИК, пространство)  # noqa: S102 — проверка вставляемого кода
    к = пространство["краткое_описание"]
    assert (
        к("40 дней", {"kind": "Фильм", "year": 2025},
          {"original_name": "40 Days", "countries": ["США"], "genres": ["западный контент", "драма"]},
          "", "Zona")
        == "«40 дней» (40 Days) — фильм 2025 года, США. Жанр: драма. Смотреть онлайн на Zona."
    )
    срез = к("Имя", {}, {}, "слово " * 60, "Zona")
    assert len(срез) <= 180 and срез.endswith("слово…")


def test_file_of_another_kind_is_refused_before_writing():
    with pytest.raises(ValueError):
        инструмент.привести("def другое():\n    pass\n")
