"""Цели о рекомендательных блоках: показ и переход, без ключа в самой цели.

Повод (линия SEO, 27.10): владелец оценивает эффект по показам блоков и
переходам из блока в карточку, а показов не измеряла ни одна цель — в Метрику
уходили только `title_view` и события плеера. «Блок показали, но из него не
переходят» было неотличимо от «блок никто не видел».

Главное свойство, которое здесь закрепляется: ключ подборки в цель НЕ
передаётся. Третьего аргумента у точки отправки не существует по устройству —
именно это не даёт поисковой фразе уехать в отчёт. Разбивка по подборкам
берётся из просмотров `/collection/<key>/`, а ключ остаётся в разметке.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ИНСТРУМЕНТ = КОРЕНЬ / "automation" / "host" / "apply-block-goals-patch.py"
ВИТРИНЫ = (
    КОРЕНЬ / "var" / "site-repos" / "zonafilm-space" / "src" / "lords-frontend.py",
    КОРЕНЬ / "var" / "site-repos" / "zonafilm12-site" / "src" / "lords-frontend.py",
    КОРЕНЬ / "var" / "site-repos" / "animedia-icu" / "src" / "animedia-frontend.py",
)
КАНОН = КОРЕНЬ / "automation" / "host" / "lords-frontend.py"


def _разметка(путь: pathlib.Path) -> tuple[str, tuple]:
    т = путь.read_text(encoding="utf-8")
    # Порядок объявлений в рантаймах разный: у канона список целей идёт ПОСЛЕ
    # тега метрики, у витрин — до. Поэтому берём кусок от списка до первой
    # функции, объявленной после `цели_метрики`, а не до фиксированного имени.
    import ast as _ast
    дерево = _ast.parse(т)
    строки = т.splitlines()
    узел = next(у for у in дерево.body
                if isinstance(у, _ast.FunctionDef) and у.name == "цели_метрики")
    начало = т.index("ЦЕЛИ_МЕТРИКИ = (")
    кусок = т[начало:len("\n".join(строки[:узел.end_lineno]))]
    область = {"__name__": "цели"}
    exec(compile(кусок, "цели", "exec"), область)  # noqa: S102
    return область["цели_метрики"]("112582938"), область["ЦЕЛИ_МЕТРИКИ"]


@pytest.mark.parametrize("путь", (*ВИТРИНЫ, КАНОН), ids=lambda п: п.parts[-3])
def test_обе_цели_в_закрытом_списке(путь):
    _, цели = _разметка(путь)
    assert "block_view" in цели and "block_click" in цели, цели


@pytest.mark.parametrize("путь", (*ВИТРИНЫ, КАНОН), ids=lambda п: п.parts[-3])
def test_ключ_блока_в_цель_не_уходит(путь):
    разметка, _ = _разметка(путь)
    assert "window.ym(C,'reachGoal',n);" in разметка
    # Никакого третьего аргумента: ни объекта, ни параметров.
    assert "reachGoal',n," not in разметка.replace("reachGoal',n);", "")
    assert "dataset.blockKey" not in разметка
    assert "getAttribute('data-block-key')" not in разметка


@pytest.mark.parametrize("путь", (*ВИТРИНЫ, КАНОН), ids=lambda п: п.parts[-3])
def test_показ_считается_один_раз_за_загрузку(путь):
    """Прокрутка туда-сюда не накручивает показы: защёлка и отключение."""
    разметка, _ = _разметка(путь)
    assert "__sfGoalOnce('block_view')" in разметка
    assert "o.disconnect()" in разметка
    # Переход защёлки не имеет: это навигационное событие.
    assert "g('block_click')" in разметка


@pytest.mark.parametrize("путь", (*ВИТРИНЫ, КАНОН), ids=lambda п: п.parts[-3])
def test_разметка_целей_разбирается(путь):
    разметка, _ = _разметка(путь)
    js = разметка[len("<script>"):-len("</script>")]
    with tempfile.TemporaryDirectory() as кат:
        ф = pathlib.Path(кат) / "g.js"
        ф.write_text(js, encoding="utf-8")
        и = subprocess.run(["node", "--check", str(ф)], capture_output=True,
                           text=True, timeout=60)
    assert и.returncode == 0, и.stderr


@pytest.mark.parametrize("путь", ВИТРИНЫ, ids=lambda п: п.parts[-3])
def test_блоки_витрины_несут_ключ(путь):
    """Наблюдателю нужно, что наблюдать: ключ стоит у полки, визитки и анонсов."""
    т = путь.read_text(encoding="utf-8")
    assert 'data-block-key="rail:' in т, путь
    if "def визитка_подборки" in т:
        assert 'data-block-key="card:' in т, путь
    if "def _блок_анонсов" in т:
        assert 'data-block-key="announce"' in т, путь


def test_инструмент_не_требует_ключа_там_где_блоков_нет():
    """У канона рекомендательных блоков ещё нет: цели объявлены, чтобы новые
    витрины рождались с ними, а требовать ключ не за что."""
    и = subprocess.run([sys.executable, str(ИНСТРУМЕНТ), "--check", str(КАНОН)],
                       capture_output=True, text=True, timeout=180)
    assert и.returncode == 0, и.stdout + и.stderr


def test_инструмент_отказывает_без_отправки_целей():
    with tempfile.TemporaryDirectory() as кат:
        ф = pathlib.Path(кат) / "x.py"
        ф.write_text("# рантайм без целей\n", encoding="utf-8")
        и = subprocess.run([sys.executable, str(ИНСТРУМЕНТ), str(ф)],
                           capture_output=True, text=True, timeout=120)
    assert и.returncode != 0 and "ОТКАЗ" in (и.stdout + и.stderr)
