"""Инструмент инвентаризации долга сам обязан быть проверяем.

Он делает утверждения, по которым правят живой код, и первая же его редакция
сделала три неверных. Реестр с выдуманными пунктами хуже отсутствующего:
по нему гасят несуществующие тревоги и трогают то, что работает.

Что было неверно и здесь закреплено.

Строка `FIXTURE_DATA_SOURCE = "fixture/test"` объявлялась критическим долгом.
Метка условная и подписывает синтетический каталог синтетическим — ровно так,
как должна; дефектом было бы её появление в витрине, собранной из живого
источника. Проверять надо вывод, а не исходник.

`factory/__main__.py` объявлялся мёртвым модулем. Его не импортируют по
устройству: он запускается как `python -m factory`.

Тесты, проверяющие «не должно бросить», объявлялись тестами без утверждения
наравне с пустыми. `ast.parse` на сломанном модуле падает, и зелёный результат
кое-что значит. Смешивать их в одном пункте — завышать реестр.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import debt_audit  # noqa: E402


def _handlers(source: str) -> list[ast.ExceptHandler]:
    return [n for n in ast.walk(ast.parse(source)) if isinstance(n, ast.ExceptHandler)]


class TestПодавленноеИсключениеОтличаетсяОтОбработанного:
    def test_pass_считается_подавлением(self):
        assert debt_audit._swallows(_handlers("try:\n a()\nexcept Exception:\n pass\n")[0])

    def test_continue_считается_подавлением(self):
        source = "for x in y:\n try:\n  a()\n except Exception:\n  continue\n"
        assert debt_audit._swallows(_handlers(source)[0])

    def test_запись_в_состояние_подавлением_не_считается(self):
        source = "try:\n a()\nexcept Exception as e:\n errors.append(e)\n"
        assert not debt_audit._swallows(_handlers(source)[0])

    def test_возврат_значения_подавлением_не_считается(self):
        """Отказ, превращённый в значение, — это обработка, а не молчание."""
        source = "try:\n a()\nexcept Exception:\n return None\n"
        assert not debt_audit._swallows(_handlers(source)[0])


class TestКлассификацияТестов:
    def _findings(self, tmp_path, body: str):
        target = tmp_path / "tests" / "unit"
        target.mkdir(parents=True)
        (target / "test_образец.py").write_text(body, encoding="utf-8")
        old = debt_audit.ROOT
        debt_audit.ROOT = tmp_path
        try:
            return debt_audit.check_test_assertions()
        finally:
            debt_audit.ROOT = old

    def test_пустой_тест_назван_высоким(self, tmp_path):
        found = self._findings(tmp_path, "def test_ничего():\n    x = 1\n")
        assert [f.severity for f in found] == ["высокий"]

    def test_проверка_не_должно_бросить_названа_низким(self, tmp_path):
        found = self._findings(tmp_path, "import ast\ndef test_разбор():\n    ast.parse('x')\n")
        assert [f.severity for f in found] == ["низкий"]
        assert "не должно бросить" in found[0].kind or "неявное" in found[0].kind

    def test_тест_с_утверждением_не_попадает_в_реестр(self, tmp_path):
        assert self._findings(tmp_path, "def test_ок():\n    assert 1 == 1\n") == []


class TestВладение:
    @pytest.mark.parametrize("path,owner", [
        ("factory/lords/render.py", "TEMPLATES"),
        ("factory/templates/digest.py", "TEMPLATES"),
        ("factory/cli.py", "CORE"),
        ("factory/secret_hub/panel/server.py", "CORE"),
        ("seo_operator/planner.py", "SEO"),
        ("automation/host/lords-canary-apply.sh", "OPS"),
        ("var/product-preview/basis-video/404/index.html", "TEMPLATES"),
    ])
    def test_владелец_определяется_по_пути(self, path, owner):
        assert debt_audit.owner_of(path) == owner

    def test_каждый_пункт_реестра_имеет_владельца(self):
        безымянные = [f.path for f in debt_audit.collect() if f.owner == "UNASSIGNED"]
        assert безымянные == [], f"пункты без владельца: {безымянные}"


class TestРеестрВоспроизводим:
    def test_два_прогона_дают_одно_и_то_же(self):
        """Реестр сравнивают до и после работы: плавающий счёт сравнить нельзя."""
        первый = [f.as_dict() for f in debt_audit.collect()]
        второй = [f.as_dict() for f in debt_audit.collect()]
        assert первый == второй


class TestПринятыйДолг:
    """Принятие отличается от исключения тем, что названо и охраняется."""

    def test_каждый_принятый_пункт_называет_сторожа(self):
        for запись in debt_audit._accepted():
            guard = запись.get("guard", "")
            файл = guard.split("::", 1)[0]
            assert файл and (ROOT / файл).is_file(), (
                f"{запись.get('path')}: сторож {guard!r} не существует")

    def test_причина_не_отписка(self):
        """Однострочное «так надо» ничего не объясняет следующему правящему."""
        for запись in debt_audit._accepted():
            assert len(запись.get("reason", "")) >= 60, запись.get("path")

    def test_отсутствующий_сторож_становится_пунктом_реестра(self, tmp_path, monkeypatch):
        import json

        поддельный = tmp_path / "debt-accepted.json"
        поддельный.write_text(json.dumps({"schema_version": 1, "accepted": [
            {"kind": "повторённый блок", "path": "factory/x.py",
             "reason": "причина достаточной длины, объясняющая, почему пункт остаётся принятым",
             "guard": "tests/unit/такого_файла_нет.py"}]}), encoding="utf-8")
        monkeypatch.setattr(debt_audit, "ACCEPTED", поддельный)
        found = debt_audit.check_accepted_guards()
        assert [f.kind for f in found] == ["принятый долг без сторожа"]
        assert found[0].severity == "высокий"

    def test_принятое_не_попадает_в_реестр_как_долг(self):
        принято = {(з["kind"], з["path"]) for з in debt_audit._accepted()}
        в_реестре = {(f.kind, f.path) for f in debt_audit.collect()}
        assert not (принято & в_реестре), "принятый пункт учтён дважды"
