"""apply-home-h1.py: главная zonafilm.cc получает ровно один видимый H1 из титула."""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
спец = importlib.util.spec_from_file_location("apply_home_h1", ROOT / "automation" / "host" / "apply-home-h1.py")
инструмент = importlib.util.module_from_spec(спец)
спец.loader.exec_module(инструмент)

ОБРАЗЕЦ = '''from __future__ import annotations

import importlib.util


class home:
    @staticmethod
    def построить(вид, рантайм):
        return "<section><h2>Новые фильмы</h2></section>"


class Вид:
    имя = "Zona <&>"

    def оболочка(self, тело, титул, путь, актив=None, описание=None, og=None):
        return f"<title>{титул}</title>" + тело


def главная(self, рантайм=None):
        тело = home.построить(self, рантайм)
        return self.оболочка(
            тело, f"{self.имя} — фильмы и сериалы онлайн", "/", актив="/",
            описание="x")
'''


def _страница(образец=ОБРАЗЕЦ) -> str:
    новый, n = инструмент.привести(образец)
    assert n == 1
    п: dict = {}
    exec(новый, п)  # noqa: S102
    return п["главная"](п["Вид"]())


def test_one_visible_h1_equal_to_title():
    с = _страница()
    h1 = re.findall(r"<h1[^>]*>(.*?)</h1>", с)
    assert len(h1) == 1
    assert h1[0] == "Zona &lt;&amp;&gt; — фильмы и сериалы онлайн"   # экранирован
    assert "display:none" not in с and "visibility:hidden" not in с
    assert с.index("<h1") < с.index("<h2")                         # над первым блоком


def test_unpatched_has_no_h1():
    п: dict = {}
    exec(ОБРАЗЕЦ, п)  # noqa: S102
    assert "<h1" not in п["главная"](п["Вид"]())


def test_rerun_no_op_and_refusals():
    новый, _ = инструмент.привести(ОБРАЗЕЦ)
    assert инструмент.привести(новый) == (новый, 0)
    with pytest.raises(ValueError):
        инструмент.привести(ОБРАЗЕЦ.replace("фильмы и сериалы онлайн", "кино"))


def test_real_serve_py_anchor():
    путь = ROOT / "var" / "site-repos" / "zonafilm-cc" / "src" / "serve.py"
    if not путь.exists():
        pytest.skip("нет рабочей копии zonafilm-cc")
    новый, n = инструмент.привести(путь.read_text(encoding="utf-8"))
    assert n in (0, 1)
    compile(новый, str(путь), "exec")
