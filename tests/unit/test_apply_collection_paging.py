"""apply-collection-paging.py: коллекция — self-canonical N>1, ?page=1 → 308, 400/404; повтор без изменений; отказ без якоря."""

from __future__ import annotations

import importlib.util
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
спец = importlib.util.spec_from_file_location(
    "apply_collection_paging", ROOT / "automation" / "host" / "apply-collection-paging.py"
)
инструмент = importlib.util.module_from_spec(спец)
спец.loader.exec_module(инструмент)

ОБРАЗЕЦ = '''def запрос_строкой(пары):
    return "?" + "&".join(f"{к}={з}" for к, з in пары.items())


class ВидЗона:
    имя = "Zona"

    def коллекция(self, данные) -> str:
        тело = ""
        звенья = []
        return self.оболочка(тело, f"{данные.title} — {self.имя}",
                             данные.canonical_path, актив="/collections/",
                             описание=данные.description,
                             крошки=None,
                             разметка=None)


class Обработчик:
    def маршрут_коллекции(self, в, ключ, путь, зпр):
        снимок = СЕМЕЙСТВО = None
        try:
            страница = max(1, int((зпр.get("page") or ["1"])[0] or 1))
        except (TypeError, ValueError):
            страница = 1
        данные = КОЛЛЕКЦИИ.разрешить(ключ, снимок, СЕМЕЙСТВО, страница=страница)
        if данные is None:
            return self._отдать(в.не_найдено(путь).encode("utf-8"), код=404)
        return self._отдать(в.коллекция(данные).encode("utf-8"))
'''


def _собрать():
    новый, n = инструмент.привести(ОБРАЗЕЦ)
    assert n == 2
    пространство: dict = {}
    exec(новый, пространство)  # noqa: S102 — проверка вставляемого кода
    return новый, пространство


def test_rerun_is_a_no_op_and_missing_anchor_is_refused():
    новый, _ = _собрать()
    assert инструмент.привести(новый) == (новый, 0)
    with pytest.raises(ValueError):
        инструмент.привести(ОБРАЗЕЦ.replace("описание=данные.description,", "описание=None,"))
    with pytest.raises(ValueError):
        инструмент.привести(ОБРАЗЕЦ.replace("def запрос_строкой(", "def другое("))


def test_page_two_is_self_canonical_with_number_in_title():
    _, п = _собрать()
    снято = []
    вид = п["ВидЗона"]()
    вид.оболочка = lambda тело, титул, путь, **к: снято.append((титул, путь, к["описание"]))
    данные = types.SimpleNamespace(title="Комедии", description="Подборка.", page=2,
                                   canonical_path="/collection/comedy/")
    вид.коллекция(данные)
    данные.page = 1
    вид.коллекция(данные)
    assert снято == [("Комедии — страница 2 — Zona", "/collection/comedy/?page=2", "Подборка. — страница 2"),
                     ("Комедии — Zona", "/collection/comedy/", "Подборка.")]


@pytest.mark.parametrize("номер, ждём", [("1", ("переход", "/collection/c/?sort=new")),
                                         ("abc", ("код", 400)), ("0", ("код", 400)),
                                         ("9999", ("код", 404)), ("2", ("код", 200))])
def test_route_parses_the_page_number(номер, ждём):
    _, п = _собрать()

    class Коллекции:
        def разрешить(self, ключ, снимок, семейство, страница):
            return types.SimpleNamespace(items=["x"] if страница <= 2 else [])

    п["КОЛЛЕКЦИИ"] = Коллекции()
    итог = []
    обр = п["Обработчик"]()
    обр._переход = lambda адрес: итог.append(("переход", адрес))
    обр._отдать = lambda тело, код=200: итог.append(("код", код))
    в = types.SimpleNamespace(не_найдено=lambda путь: "нет", коллекция=lambda д: "страница")
    обр.маршрут_коллекции(в, "c", "/collection/c/", {"page": [номер], "sort": ["new"]})
    assert итог == [ждём]
