"""Ссылки на подборки на `/catalog/` — на всех трёх линиях.

Повод измеренный (линия ячейки, 27.10): `/catalog/` — самая посещаемая
страница разделов animedia.icu, 1252 просмотра за 20–26.10 против 414 у
главной, а ведёт она только на хаб `/collections/`; на сами подборки ссылок
нет. Страница есть и на двух витринах Zona (обе отдают 200), отбор полосы там
тот же, и пустота по несовпадению ключа раздела — общая причина, а не беда
одного домена.

Полоса раздела остаётся полосой РАЗДЕЛА: на `/movies/` и `/series/` она
по-прежнему отбирает подборки своего раздела. Каталог — родитель разделов,
поэтому для него «подборки этого раздела» означает все.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ИНСТРУМЕНТ = КОРЕНЬ / "automation" / "host" / "apply-manual-collections-patch.py"
РАНТАЙМЫ = (
    КОРЕНЬ / "var" / "site-repos" / "zonafilm-space" / "src" / "lords-frontend.py",
    КОРЕНЬ / "var" / "site-repos" / "zonafilm12-site" / "src" / "lords-frontend.py",
    КОРЕНЬ / "var" / "site-repos" / "animedia-icu" / "src" / "animedia-frontend.py",
)


@pytest.mark.parametrize("путь", РАНТАЙМЫ, ids=lambda п: п.parts[-3])
def test_каталог_показывает_все_подборки(путь):
    т = путь.read_text(encoding="utf-8")
    assert 'if ключ_раздела == "catalog":' in т
    assert 'заголовок, метка = "Редакционные подборки", "catalog"' in т
    assert "свои = list(РУЧНЫЕ_ПОДБОРКИ.values())" in т


@pytest.mark.parametrize("путь", РАНТАЙМЫ, ids=lambda п: п.parts[-3])
def test_раздел_остался_разделом(путь):
    """Отбор по своему разделу не потерян: иначе `/movies/` показывал бы и
    подборки сериалов, то есть полоса врала бы о владельце."""
    т = путь.read_text(encoding="utf-8")
    assert '(п.section or "").strip("/") == ключ_раздела' in т
    assert 'заголовок, метка = "Подборки этого раздела", "section"' in т


@pytest.mark.parametrize("путь", РАНТАЙМЫ, ids=lambda п: п.parts[-3])
def test_метка_полосы_различает_каталог_и_раздел(путь):
    """Метка в разметке — то, по чему проверка со стороны отличает полосу
    каталога от полосы раздела, не угадывая по подписи."""
    т = путь.read_text(encoding="utf-8")
    assert 'data-collections="{метка}"' in т


@pytest.mark.parametrize("путь", РАНТАЙМЫ, ids=lambda п: п.parts[-3])
def test_рантайм_разбирается(путь):
    import ast
    ast.parse(путь.read_text(encoding="utf-8"))


def test_инструмент_видит_отсутствие_правки():
    """Проверка обязана назвать именно этот пробел, а не сказать «ок»."""
    with tempfile.TemporaryDirectory() as кат:
        ф = pathlib.Path(кат) / "lords-frontend.py"
        т = РАНТАЙМЫ[0].read_text(encoding="utf-8")
        # Возврат к прежнему отбору: признак правки исчезает.
        т = т.replace('if ключ_раздела == "catalog":', 'if False:')
        т = т.replace('заголовок, метка = "Редакционные подборки", "catalog"',
                      'заголовок, метка = "", "section"')
        ф.write_text(т, encoding="utf-8")
        и = subprocess.run([sys.executable, str(ИНСТРУМЕНТ), "--check", str(ф)],
                           capture_output=True, text=True, timeout=180)
    assert и.returncode != 0
    assert "на /catalog/ ссылок на подборки нет" in и.stdout


def test_все_три_рантайма_приведены():
    и = subprocess.run([sys.executable, str(ИНСТРУМЕНТ), "--check",
                        *[str(п) for п in РАНТАЙМЫ]],
                       capture_output=True, text=True, timeout=240)
    assert и.returncode == 0, и.stdout + и.stderr
