"""Три величины считаются раздельно, и ни одна не выдаёт ожидание за провал.

Владелец потребовал разделения прямо: готовность кода, готовность интеграции и
готовность действующего сайта — три независимых числа. И отдельно: не ставить
продукту ноль только из-за отсутствия адреса для проверки.

Рубрика разделение выполняла наполовину. Приёмка боевой витрины входила в
готовность интеграции слагаемым, и слагаемое это было нулём — не потому что
витрина не прошла приёмку, а потому что адреса для неё не передали. Интеграция
из-за этого занижена, а в таблице против строки «приёмка боевой витрины» стоял
ноль там, где верное слово — «ждёт адреса».

Ноль и ожидание читаются одинаково, а означают противоположное: первое — что
проверяли и не прошло, второе — что не проверяли и не на чем.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="module")
def отчёт() -> dict:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "product_readiness.py"), "--json"],
        capture_output=True, text=True, cwd=str(ROOT), timeout=1800)
    assert result.returncode == 0, result.stderr[-2000:]
    return json.loads(result.stdout)


class TestПриёмкаВитриныОтдельно:
    def test_приёмка_не_входит_в_готовность_интеграции(self, отчёт):
        """Иначе ожидание входа занижает число, которое к нему не относится."""
        assert "live" not in отчёт["integration_dimensions"]

    def test_состояние_приёмки_названо_а_не_обозначено_нулём(self, отчёт):
        """Состояний несколько, и все описывают адрес, а не витрину.

        Первая редакция требовала `BLOCKED_OWNER_URLS` у всех четырёх. Владелец
        передал адреса, и состояния разошлись: имя не разрешается, TLS не
        обслуживается, адреса нет. Числа по-прежнему нет ни у кого — приёмка не
        проводилась, — но одинакового состояния больше нет и быть не должно.
        """
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
        from product_readiness import ЖДЁТ

        for имя, info in отчёт["products"].items():
            assert info["live_acceptance"] is None, (
                f"{имя}: приёмка боевой витрины выдана числом, хотя не проводилась")
            assert info["live_state"] in ЖДЁТ, (
                f"{имя}: состояние {info['live_state']!r} не названо по-русски")

    def test_причина_объяснена(self, отчёт):
        """Состояние без объяснения не говорит владельцу, что чинить."""
        for имя, info in отчёт["products"].items():
            note = info["dimensions"]["live"]["note"]
            assert ":" in note and len(note.split(":", 1)[1].strip()) > 10, (
                f"{имя}: состояние названо без объяснения — {note!r}")

    def test_ни_одно_состояние_не_объявлено_отказом_витрины(self, отчёт):
        for имя, info in отчёт["products"].items():
            note = info["dimensions"]["live"]["note"].lower()
            assert "провал" not in note and "дефект" not in note, имя


class TestТриВеличиныНезависимы:
    def test_все_три_присутствуют(self, отчёт):
        for имя, info in отчёт["products"].items():
            for поле in ("product_readiness", "integration_readiness", "live_acceptance"):
                assert поле in info, f"{имя}: нет {поле}"

    def test_готовность_продукта_yummy_не_измеряется_этой_полосой(self, отчёт):
        """Ноль здесь был бы неправдой: продукт работает на трёх витринах."""
        assert отчёт["products"]["yummy"]["product_readiness"] is None
        assert отчёт["products"]["yummy"]["product_note"]

    def test_средние_считаются_по_измеренному(self, отчёт):
        измеренные = [i["product_readiness"] for i in отчёт["products"].values()
                      if i["product_readiness"] is not None]
        assert отчёт["average_product"] == round(sum(измеренные) / len(измеренные))
        assert отчёт["measured_products"] == len(измеренные)


class TestВыводЧитаем:
    def test_в_таблице_вместо_нуля_стоит_ожидание(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "product_readiness.py")],
            capture_output=True, text=True, cwd=str(ROOT), timeout=1800)
        assert result.returncode == 0, result.stderr[-2000:]
        строки = [s for s in result.stdout.splitlines() if "приёмка" in s]
        assert строки, "строки приёмки в таблице нет"
        for строка in строки:
            assert "ждёт адреса" in строка, f"ожидание выдано числом: {строка!r}"
