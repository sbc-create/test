"""Yummy нельзя объявить неготовым продуктом — ни числом, ни умолчанием.

Это существующий продукт на трёх действующих витринах. Полоса шаблонов его не
измеряла и измерить не может: приложение вне фабрики, боевые домены закрыты
профилем разрешений, рабочая копия занята активной веткой другого потока.

Однажды он уже был представлен как продукт с готовностью 4 %. Число было
верным — но относилось к готовности **подключения к фабрике**, а прочиталось
как оценка продукта. Владелец поправил, и поправка должна держаться не на
памяти, а на проверке: следующая рубрика, посчитавшая среднее по четырём
продуктам вместо трёх измеренных, сделает ту же ошибку молча.

Проверяется поэтому не текст отчёта, а его устройство: у Yummy нет числа
продуктовой готовности, среднее считается по измеренным, а интеграционное
число нигде не выдаётся за продуктовое.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

ОТЧЁТ = ROOT / "artifacts" / "evidence" / "products" / "product-readiness.json"


@pytest.fixture(scope="module")
def отчёт() -> dict:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "product_readiness.py"), "--json"],
        capture_output=True, text=True, cwd=str(ROOT), timeout=1800)
    assert result.returncode == 0, result.stderr[-2000:]
    return json.loads(result.stdout)


class TestПродуктовойОценкиНет:
    def test_числа_нет(self, отчёт):
        assert отчёт["products"]["yummy"]["product_readiness"] is None, (
            "полоса шаблонов не измеряла продукт Yummy и не вправе выдавать число")

    def test_причина_названа(self, отчёт):
        примечание = отчёт["products"]["yummy"]["product_note"]
        assert "не измерено этой полосой" in примечание
        for причина in ("вне фабрики", "разрешений", "ветк"):
            assert причина in примечание, f"не названа причина: {причина}"

    def test_известное_названо_с_источником(self, отчёт):
        """Чужое измерение не выдаётся за своё."""
        примечание = отчёт["products"]["yummy"]["product_note"]
        assert "ARCHITECT_CORE" in примечание


class TestСреднееНеРазмываетсяYummy:
    def test_считается_по_измеренным(self, отчёт):
        измеренные = [i["product_readiness"] for i in отчёт["products"].values()
                      if i["product_readiness"] is not None]
        assert "yummy" not in отчёт["average_product_measured"]
        assert отчёт["average_product"] == round(sum(измеренные) / len(измеренные))

    def test_число_измеренных_названо(self, отчёт):
        assert отчёт["measured_products"] == 3


class TestИнтеграцияНеВыдаётсяЗаПродукт:
    def test_интеграционное_число_есть_и_отдельно(self, отчёт):
        yummy = отчёт["products"]["yummy"]
        assert isinstance(yummy["integration_readiness"], int)
        assert yummy["product_readiness"] is None, (
            "одно число на две величины не отвечает ни на один вопрос")

    def test_документ_владельца_не_называет_yummy_неготовым(self):
        # Строка берётся из таблицы готовности, а не первая попавшаяся: в
        # документе несколько таблиц начинаются со столбца «Продукт», и поиск
        # по имени находил строку таблицы «что прислать». Проверка падала на
        # верном документе — худший вид проверки.
        текст = (ROOT / "docs" / "templates" / "OWNER-STATUS.md").read_text(encoding="utf-8")
        строки = текст.splitlines()
        начало = next(i for i, s in enumerate(строки)
                      if s.startswith("| Продукт | Готовность продукта |"))
        строка = next(s for s in строки[начало:] if s.startswith("| yummy |"))
        assert "не измерено" in строка, строка
        assert "%" in строка, "готовность интеграции всё же должна быть названа"


class TestВнешнийБлокерПринадлежитCore:
    """xfail оставлен только потому, что препятствие действительно внешнее."""

    def test_ворота_сборки_закрыты_в_чужом_репозитории(self):
        from factory.yummy import adapter_contract as contract

        состояние = {r.key: r for r in contract.assess().requirements}["build_gate"]
        assert состояние.owner == "CORE"
        if состояние.satisfied:
            pytest.skip("Core снял TEMPLATE_TO_CORE-007: xfail пора убирать")
        assert "не объявлены" in состояние.detail or "сужен" in состояние.detail, (
            "препятствие названо неконкретно — так его не снимет никто")

    def test_препятствие_вне_этого_репозитория(self):
        from factory.yummy import adapter_contract as contract

        assert not str(contract.APP_REPO).startswith(str(ROOT)), (
            "приложение оказалось внутри репозитория фабрики — тогда это "
            "не внешний блокер, и xfail прикрывает свой дефект")
