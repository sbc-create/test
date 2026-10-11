"""apply-pagination-canonical.py: возврат оболочки раздела получает номер страницы; повтор без изменений."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
спец = importlib.util.spec_from_file_location(
    "apply_pagination_canonical", ROOT / "automation" / "host" / "apply-pagination-canonical.py"
)
инструмент = importlib.util.module_from_spec(спец)
спец.loader.exec_module(инструмент)

ОБРАЗЕЦ = '''class ВидЗона:
    def список(self, разд, зпр):
        актив = разд + "/"
        return self.оболочка(тело, f"{титул} — {self.имя}", канон or (разд + "/"),
                             актив=актив,
                             описание=f"{титул} на витрине {self.имя}.",
                             сверху="")
'''


def test_anchor_is_rewritten_and_rerun_is_a_no_op():
    новый, n = инструмент.привести(ОБРАЗЕЦ)
    assert n == 1
    assert 'адрес += ("&" if "?" in адрес else "?") + f"page={стр}"' in новый
    assert 'описание=f"{титул} на витрине {self.имя}{хвост}.",' in новый
    assert инструмент.привести(новый) == (новый, 0)
    compile(новый, "образец", "exec")


def test_rewritten_code_behaves():
    новый, _ = инструмент.привести(ОБРАЗЕЦ)
    пространство: dict = {}
    exec(новый, пространство)  # noqa: S102 — проверка вставляемого кода
    вид = пространство["ВидЗона"]()
    вид.имя = "Zona"
    вызовы = []
    вид.оболочка = lambda тело, титул, путь, **к: вызовы.append((титул, путь, к["описание"]))
    for стр in (1, 3):
        пространство.update(тело="", титул="Каталог", канон="/catalog/?genre=drama", стр=стр)
        вид.список.__func__.__globals__.update(пространство)
        вид.список("/catalog", {})
    assert вызовы[0] == ("Каталог — Zona", "/catalog/?genre=drama", "Каталог на витрине Zona.")
    assert вызовы[1] == ("Каталог — страница 3 — Zona", "/catalog/?genre=drama&page=3",
                         "Каталог на витрине Zona — страница 3.")


def test_file_of_another_kind_is_refused():
    with pytest.raises(ValueError):
        инструмент.привести("def другое():\n    pass\n")
