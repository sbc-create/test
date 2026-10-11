"""apply-country-title.py: страна выборки попадает в заголовок раздела Zona; без страны — как прежде."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
спец = importlib.util.spec_from_file_location("apply_country_title", ROOT / "automation" / "host" / "apply-country-title.py")
инструмент = importlib.util.module_from_spec(спец)
спец.loader.exec_module(инструмент)

ОБРАЗЕЦ = '''ВИД_ПО_МАРШРУТУ = {}
КАТЕГОРИЯ_ПО_МАРШРУТУ = {}


class Вид:
    индекс = {"country_names": [("ssha", "США"), ("yaponiya", "Япония")]}

    def заголовок(self, разд, выбрано, жанр_имя=None, год=None):
        титул = "Каталог"
        if разд == "/catalog" and год:
            титул = f"Каталог {год} года"
        elif жанр_имя:
            титул = жанр_имя.capitalize() if жанр_имя[:1].islower() else жанр_имя

        kind_route = разд in ВИД_ПО_МАРШРУТУ or разд in КАТЕГОРИЯ_ПО_МАРШРУТУ
        return титул
'''


@pytest.mark.parametrize("выбрано, жанр, год, ждём", [
    ({"country": "ssha"}, None, None, "Каталог: США"),
    ({"country": "yaponiya"}, "драма", None, "Драма: Япония"),
    ({"country": "ssha"}, None, "2024", "Каталог 2024 года: США"),
    ({}, "драма", None, "Драма"),
    ({}, None, None, "Каталог"),
    ({"country": "нет-такой"}, None, None, "Каталог"),
])
def test_country_in_title(выбрано, жанр, год, ждём):
    новый, n = инструмент.привести(ОБРАЗЕЦ)
    assert n == 1
    п: dict = {}
    exec(новый, п)  # noqa: S102
    assert п["Вид"]().заголовок("/catalog", выбрано, жанр, год) == ждём


def test_rerun_is_a_no_op_and_missing_anchor_is_refused():
    новый, _ = инструмент.привести(ОБРАЗЕЦ)
    assert инструмент.привести(новый) == (новый, 0)
    with pytest.raises(ValueError):
        инструмент.привести(ОБРАЗЕЦ.replace("kind_route", "kind_путь"))
