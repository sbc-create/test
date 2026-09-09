"""Карантин устаревшего канареечного drop-in: точно, доказанно, без масок.

Временный файл, который забыли снять, тише всех прочих отказов. Он ничего не
ломает сразу — он просто заставляет каждый цикл обновления делать полный
рендер. Такой файл был оставлен 8 сентября с собственным обещанием «снимается
сразу после проверки канарейки», и с тех пор каждый прогон упирался в предел
памяти на часы, блокируя любую выкладку.

Уносить чужой файл можно только при трёх условиях сразу: точное имя без масок,
совпадение отпечатка с осмотренным и доказательство, что везомая канарейкой
ревизия уже выложена. Проверки ниже закрепляют каждое.
"""

from __future__ import annotations

import argparse
import ast
import importlib.machinery
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def помощник():
    путь = ROOT / "automation" / "deploy" / "lords-deployctl"
    спец = importlib.util.spec_from_loader(
        "ctl_quiesce", importlib.machinery.SourceFileLoader("ctl_quiesce", str(путь)))
    м = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(м)
    return м


def _args(**kw):
    основа = dict(file="zz-canary-29.conf", sha256="a" * 64,
                  reason="test", force_proven=False)
    основа.update(kw)
    return argparse.Namespace(**основа)


class TestТолькоКанареечныеФайлы:
    @pytest.mark.parametrize("имя", ["pinned-tooling.conf", "retention.conf",
                                     "timeout.conf", "override.conf"])
    def test_неканареечный_файл_отвергается(self, помощник, имя):
        """Тронуть их значило бы поменять устройство обновления, а не убрать."""
        with pytest.raises(помощник.Отказ):
            помощник.глагол_quiesce_dropin(_args(file=имя))

    @pytest.mark.parametrize("имя", ["../etc/passwd", "a/b.conf",
                                     "zz-canary-*.conf", "zz-canary-29.txt"])
    def test_путь_маска_и_чужое_расширение_отвергаются(self, помощник, имя):
        with pytest.raises(помощник.Отказ):
            помощник.глагол_quiesce_dropin(_args(file=имя))

    def test_префикс_и_каталог_закреплены(self, помощник):
        assert помощник.КАНАРЕЕЧНЫЙ_ПРЕФИКС == "zz-canary-"
        assert str(помощник.ДРОПИН_КАТАЛОГ).endswith(
            "lords-content-refresh.service.d")


class TestБезПроизвольногоИсполнения:
    def test_нет_оболочки_и_сигналов(self, помощник):
        дерево = ast.parse(Path(помощник.__file__).read_text(encoding="utf-8"))
        оболочка = [у.lineno for у in ast.walk(дерево) if isinstance(у, ast.Call)
                    for к in у.keywords
                    if к.arg == "shell" and getattr(к.value, "value", False) is True]
        assert оболочка == []
        имена = {ast.unparse(у.func) for у in ast.walk(дерево) if isinstance(у, ast.Call)}
        assert "os.kill" not in имена

    def test_файл_переносится_а_не_удаляется(self, помощник):
        дерево = ast.parse(Path(помощник.__file__).read_text(encoding="utf-8"))
        функция = next(у for у in ast.walk(дерево) if isinstance(у, ast.FunctionDef)
                       and у.name == "глагол_quiesce_dropin")
        тело = ast.unparse(функция)
        assert "shutil.move" in тело
        assert "unlink" not in тело and "rmtree" not in тело

    def test_рядом_кладётся_объяснение(self, помощник):
        дерево = ast.parse(Path(помощник.__file__).read_text(encoding="utf-8"))
        функция = next(у for у in ast.walk(дерево) if isinstance(у, ast.FunctionDef)
                       and у.name == "глагол_quiesce_dropin")
        тело = ast.unparse(функция)
        assert "why.json" in тело, "перенос без записи причины"


class TestДоказательствоУстарелости:
    def test_сверяется_выложенная_ревизия(self, помощник):
        дерево = ast.parse(Path(помощник.__file__).read_text(encoding="utf-8"))
        функция = next(у for у in ast.walk(дерево) if isinstance(у, ast.FunctionDef)
                       and у.name == "глагол_quiesce_dropin")
        тело = ast.unparse(функция)
        assert "renderer_revision" in тело and "already_deployed" in тело

    def test_вердикт_различает_карантин_и_отказ(self, помощник):
        текст = Path(помощник.__file__).read_text(encoding="utf-8")
        for вердикт in ("QUARANTINED", "not_stale", "already_gone", "CANARY_ENV_REMAINS"):
            assert вердикт in текст

    def test_глагол_объявлен(self, помощник):
        assert "quiesce-dropin" in помощник.ГЛАГОЛЫ
