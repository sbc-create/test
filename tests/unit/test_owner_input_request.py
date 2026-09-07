"""Единый запрос входов включает то, что сейчас держит четыре продукта.

Правило §13 прямое: не спрашивать по одному вопросу в процессе работы, а
выдать один список. Список собирается, но три вещи в него не попадали.

Первое — боевые адреса витрин. Живая приёмка всех четырёх продуктов сейчас
стоит именно на них, и это единственное, чего ждут от владельца. В списке
недостающего этого пункта не было вовсе: самое важное отсутствовало в
документе, созданном ради полноты.

Второе — Yummy. Пакета направления в фабрике нет, поэтому в список, который
собирается обходом пакетов, направление не попадало ничем. Его требования
описаны отдельно, в контракте подключения, и владелец должен был читать два
документа вместо одного.

Третье — повторы. Поле `content_source.rights_confirmed` спрашивалось дважды
на каждый сайт: две проверки сообщают об одном и том же под разными статусами.
Владельцу это читается как два разных требования.
"""

from __future__ import annotations

import pytest

from factory.input_request import collect

ПОЛЯ = ("field", "why", "format", "example_without_secret", "where_to_put", "blocks_stage")


@pytest.fixture(scope="module")
def список() -> list[dict]:
    return collect()


class TestПолнота:
    def test_адреса_от_владельца_запрошены(self, список):
        поля = [i["field"] for i in список]
        assert any("owner" in f and "url" in f for f in поля), (
            "живая приёмка стоит на адресах витрин, а в списке недостающего их нет")

    def test_запрос_называет_только_ещё_не_переданное(self, список):
        """Запрос, просящий уже полученное, обесценивает весь список.

        Первая редакция требовала перечисления всех четырёх продуктов. Владелец
        передал два адреса, и повторять их в списке недостающего значило бы
        учить читателя не доверять этому документу.
        """
        import json
        from pathlib import Path

        slot = json.loads((Path(__file__).resolve().parents[2] / "config" /
                           "live-acceptance.json").read_text(encoding="utf-8"))["products"]
        ждут = {имя for имя, v in slot.items() if not v.get("base_url")}
        переданы = set(slot) - ждут

        пункт = next(i for i in список if "owner" in i["field"] and "live_urls" in i["field"])
        текст = (пункт["why"] + пункт["format"] + пункт["where_to_put"]).lower()
        for продукт in ждут:
            assert продукт in текст, f"{продукт} ждёт адреса, но в запросе не назван"
        for продукт in переданы:
            assert f"{продукт} —" not in текст, (
                f"{продукт}: адрес передан, а запрос всё ещё его требует")

    def test_состояние_переданных_адресов_названо(self, список):
        """Переданный, но нерабочий адрес — состояние, а не отказ витрины."""
        состояния = [i for i in список if i["field"].startswith("owner.address_state.")]
        for пункт in состояния:
            assert "не отказ витрины" in пункт["why"], пункт["field"]
            assert пункт["blocks_stage"].startswith("PRODUCT_LIVE_ACCEPTANCE")

    def test_состояние_названо_как_ожидание_а_не_отказ(self, список):
        пункт = next(i for i in список if "owner" in i["field"] and "url" in i["field"])
        assert "BLOCKED_OWNER_URLS" in пункт["blocks_stage"], (
            "отсутствие адреса — ожидание входа, а не провал продукта")

    def test_требования_yummy_включены(self, список):
        поля = " ".join(i["field"] for i in список)
        assert "yummy" in поля.lower(), (
            "пакета у Yummy нет, и обходом пакетов направление не находится")


class TestСписокЧитаем:
    def test_повторов_нет(self, список):
        ключи = [(i["field"], i["where_to_put"]) for i in список]
        повторы = sorted({k for k in ключи if ключи.count(k) > 1})
        assert повторы == [], f"одно и то же спрошено дважды: {повторы}"

    def test_объединённый_пункт_называет_оба_статуса(self, список):
        """Слияние повторов не должно терять статус: их два, и оба верны."""
        пункт = next((i for i in список
                      if i["field"].endswith("content_source.rights_confirmed")), None)
        if пункт is None:
            pytest.skip("в текущем состоянии пакетов права подтверждены")
        assert "BLOCKED_RIGHTS" in пункт["blocks_stage"]
        assert "BLOCKED_CONTENT_RIGHTS" in пункт["blocks_stage"]

    def test_каждый_пункт_заполнен(self, список):
        пустые = [(i.get("field"), поле) for i in список for поле in ПОЛЯ if not i.get(поле)]
        assert пустые == [], f"незаполненные поля: {пустые}"


class TestСекретовНет:
    def test_примеры_без_значений_секретов(self, список):
        for i in список:
            пример = str(i["example_without_secret"]).lower()
            assert "password=" not in пример
            assert not пример.startswith("postgres://")
            assert "publisher_id: " not in пример
