"""apply-h1-page-number.py: H1 страницы N>1 получает номер по title; прочие страницы не меняются (REQ-SEO-PAGINATION п.7)."""

from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
спец = importlib.util.spec_from_file_location(
    "apply_h1_page_number", ROOT / "automation" / "host" / "apply-h1-page-number.py"
)
инструмент = importlib.util.module_from_spec(спец)
спец.loader.exec_module(инструмент)


@pytest.fixture()
def слой(tmp_path):
    путь = tmp_path / "seo_layer.py"
    shutil.copy(ROOT / "automation" / "host" / "seo_layer.py", путь)
    новый, n = инструмент.привести(путь.read_text(encoding="utf-8"))
    assert n == 1
    путь.write_text(новый, encoding="utf-8")
    спец_с = importlib.util.spec_from_file_location("seo_layer_h1", путь)
    модуль = importlib.util.module_from_spec(спец_с)
    спец_с.loader.exec_module(модуль)
    return модуль


def страница(титул: str, h1: str) -> bytes:
    return (f"<html><head><title>{титул}</title></head>"
            f'<body><h1 class="lead">{h1}</h1><h1>второй</h1></body></html>').encode("utf-8")


def h1(тело: bytes) -> str:
    текст = тело.decode("utf-8")
    return текст[текст.index("<h1"):текст.index("</h1>")].split(">", 1)[1]


def test_page_two_h1_follows_title(слой):
    тело = слой.обогатить(страница("Каталог — страница 2 — Сайт", "Каталог"), "text/html; charset=utf-8",
                          хост="example.test", путь="/catalog/?page=2&sort=new", код=200)
    assert h1(тело) == "Каталог — страница 2"
    assert тело.decode("utf-8").count("страница 2") == 2  # title и первый H1; второй H1 не тронут


@pytest.mark.parametrize("путь, титул, код", [
    ("/catalog/", "Каталог — Сайт", 200),                       # первая страница
    ("/catalog/?page=1", "Каталог — Сайт", 200),
    ("/catalog/?page=2", "Каталог — Сайт", 200),                 # вид не объявил номер — H1 не угадывается
    ("/catalog/?page=abc", "Каталог — страница 2 — Сайт", 200),
    ("/catalog/?page=2", "Каталог — страница 2 — Сайт", 404),   # не 200
])
def test_other_pages_unchanged(слой, путь, титул, код):
    тело = слой.обогатить(страница(титул, "Каталог"), "text/html; charset=utf-8",
                          хост="example.test", путь=путь, код=код)
    assert h1(тело) == "Каталог"


def test_h1_with_number_is_not_doubled_and_rerun_is_a_no_op(слой):
    тело = слой.обогатить(страница("Боевики — страница 3 — Сайт", "Боевики — страница 3"),
                          "text/html; charset=utf-8", хост="example.test",
                          путь="/collection/action/?page=3", код=200)
    assert h1(тело) == "Боевики — страница 3"
    текст = (ROOT / "automation" / "host" / "seo_layer.py").read_text(encoding="utf-8")
    новый, _ = инструмент.привести(текст)
    assert инструмент.привести(новый) == (новый, 0)


def test_missing_anchor_is_refused():
    with pytest.raises(ValueError):
        инструмент.привести("def обогатить(): pass\n")
