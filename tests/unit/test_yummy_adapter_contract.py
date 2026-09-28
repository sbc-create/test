"""Контракт подключения Yummy: что фабрике нужно от приложения.

Приложение живёт в отдельном репозитории и сюда не переносится. Эти проверки —
сторона потребителя: они описывают требования исполняемо, называют владельца
каждого и падают там, где требование не выполнено.

Смысл в том, чтобы ноль перестал быть немым. Пока контракта не было, Yummy
числился нулём по всем измерениям, и ноль этот ничего не сообщал: неизвестно,
чего не хватает, кому это принадлежит и что изменится, когда препятствие
снимут.

Часть проверок сейчас проходит, часть — нет, и это правильное состояние. Те,
что не проходят, названы в отчёте с владельцем и повторяют содержание
`TEMPLATES_TO_CORE-045`. Когда Core снимет препятствие, они станут приёмочными
без единой правки.
"""

from __future__ import annotations

import pytest

from factory.yummy import adapter_contract as contract


@pytest.fixture(scope="module")
def оценка():
    return contract.assess()


class TestИсследованиеПриложения:
    """То, что установлено чтением, а не памятью."""

    def test_домены_подтверждены_кодом(self):
        # `yummyani.*`, а не `yummyanime.*`: подмена одного другим делалась бы
        # без единого основания, и в отчёте она уже однажды встречалась.
        assert contract.DOMAINS == (
            "yummyani.me", "yummyani.site", "yummyani.org", "yummyani.biz")

    def test_витрины_приложения_читаются(self):
        ids = contract.profile_ids()
        assert ids, "список витрин пуст: контракт не может назвать, что собирать"
        assert set(ids) == {"site", "org", "biz"}

    def test_вложенные_поля_витриной_не_считаются(self):
        """Первая редакция разбора возвращала `jsonLd` и `openGraph`.

        Список, собранный неверно, хуже отсутствующего: по нему нельзя ни
        собрать, ни проверить, а выглядит он рабочим.
        """
        assert "jsonLd" not in contract.profile_ids()
        assert "openGraph" not in contract.profile_ids()

    def test_версия_контракта_объявлена(self):
        assert contract.CONTRACT_VERSION == "yummy-app/1.0.0"


class TestВыборВитриныБезопасен:
    def test_известная_витрина_принимается(self):
        env = contract.environment_for("site")
        assert env[contract.PROFILE_ENV] == "site"

    def test_неизвестная_витрина_отвергается(self):
        """Неверный профиль отдал бы канонические адреса одной витрины под
        доменом другой — это хуже отсутствующего профиля."""
        with pytest.raises(ValueError):
            contract.environment_for("не-существует")

    def test_секретов_в_окружении_нет(self):
        """Строка подключения и токены передаются процессу, а не этим словарём."""
        env = contract.environment_for("site")
        assert not any(k for k in env if "SECRET" in k or "TOKEN" in k or "DATABASE" in k)


class TestТребованияНазваныСВладельцами:
    def test_каждое_требование_имеет_владельца(self, оценка):
        безымянные = [r.key for r in оценка.requirements if not r.owner]
        assert безымянные == [], f"требования без владельца: {безымянные}"

    def test_состояние_каждого_требования_обосновано(self, оценка):
        молчащие = [r.key for r in оценка.requirements if not r.detail]
        assert молчащие == [], f"требования без объяснения состояния: {молчащие}"

    def test_есть_и_выполненные_и_заблокированные(self, оценка):
        """Ноль по всем измерениям был бы неправдой: часть уже выполнена."""
        assert оценка.satisfied, "ни одно требование не выполнено — проверьте доступ"
        assert оценка.blocked, "все требования выполнены: контракт пора закрывать"

    def test_приложение_доступно_на_чтение(self, оценка):
        state = {r.key: r for r in оценка.requirements}
        assert state["app_present"].satisfied, state["app_present"].detail

    def test_сценарии_сборки_объявлены(self, оценка):
        state = {r.key: r for r in оценка.requirements}
        assert state["scripts"].satisfied, state["scripts"].detail


class TestЗапросНедостающихВходов:
    def test_перечень_непуст(self):
        assert contract.missing_inputs()

    def test_каждый_вход_объясняет_себя(self):
        for item in contract.missing_inputs():
            for поле in ("field", "why", "format", "where_to_put", "blocks"):
                assert item.get(поле), f"{item.get('field')}: не заполнено {поле}"

    def test_примеры_не_содержат_секретов(self):
        """Значение секрета не попадает ни в запрос, ни в отчёт."""
        for item in contract.missing_inputs():
            example = str(item.get("example_without_secret", "")).lower()
            assert "password" not in example
            assert "secret=" not in example
            assert not example.startswith("postgres://")


class TestВоротаСборкиОстаютсяЗакрытыми:
    """Приёмочная проверка `TEMPLATE_TO_CORE-007`, выраженная исполнимо.

    Она падает, пока декларация наблюдателя не приведена в соответствие с
    реализацией. Это и есть тот самый падающий consumer test: он не чинится со
    стороны шаблонов и станет зелёным ровно тогда, когда Core закроет ворота.
    """

    def test_состояние_ворот_измерено_а_не_предположено(self, оценка):
        state = {r.key: r for r in оценка.requirements}["build_gate"]
        assert state.detail, "состояние ворот не объяснено"

    @pytest.mark.xfail(reason="TEMPLATE_TO_CORE-007 открыт: декларация наблюдателя "
                              "отстала от реализации; правка принадлежит Core",
                       strict=False)
    def test_декларация_наблюдателя_совпадает_с_реализацией(self, оценка):
        state = {r.key: r for r in оценка.requirements}["build_gate"]
        assert state.satisfied, state.detail
