"""REQ-UCC-7: настройка витрины правится в её карточке во флоте.

Сводка флота показывала состояние пяти витрин и умела только одно действие —
увести в контур витрины. Чтобы поменять одно значение, оператор уходил со
сводки, терял отбор и место в списке и возвращался руками. Собранное окно, из
которого приходится уходить на каждое действие, перестают открывать.

Три правила, каждое из которых защищает не удобство, а корректность.

**Путь записи один.** Форма из карточки ходит тем же маршрутом договора, что и
страница настроек: сверка версии, сухой прогон и журнал остаются на месте.
Второй способ записать настройку однажды разойдётся с первым.

**Сверка версий переживает переезд формы.** Версия берётся из формы, показанной
оператору, а не из свежего чтения перед записью: иначе чужая правка, сделанная
между показом сводки и отправкой, была бы затёрта молча.

**Отсутствие права видно словами.** Витрина, которую не дали прочитать, и
витрина без изменяемых настроек — разные вещи, и обе не пустая таблица.
"""

from __future__ import annotations

import pytest

from tests.unit.test_fleet_console import (  # noqa: F401
    САЙТ_A,
    app,
    sandbox,
    войти,
    люди,
)


def карточка(html: str, сайт: str) -> str:
    """Кусок разметки, относящийся к одной витрине."""
    начало = html.find(f'value="{сайт}"')
    assert начало >= 0, f"витрины {сайт} нет на экране"
    конец = html.find("</details>", начало)
    return html[max(0, начало - 4000):конец if конец > 0 else len(html)]


def версия_из_формы(html: str, сайт: str) -> str:
    """Версия конфигурации ровно та, что показана оператору в форме."""
    кусок = карточка(html, сайт)
    метка = 'name="expectedVersion" value="'
    начало = кусок.find(метка)
    assert начало >= 0, "в форме карточки нет версии конфигурации"
    начало += len(метка)
    return кусок[начало:кусок.index('"', начало)]


@pytest.fixture
def cookies(app, люди):  # noqa: F811
    return войти(app, "super@test")


class TestКарточкаУмеетНастройки:
    def test_в_карточке_есть_форма_настройки(self, app, cookies):  # noqa: F811
        html = app.handle("GET", "/admin/fleet", cookies=cookies).html
        кусок = карточка(html, САЙТ_A)
        assert 'action="/admin/fleet/settings"' in кусок, (
            "из карточки витрины настройку не поменять")

    def test_форма_несёт_версию_конфигурации(self, app, cookies):  # noqa: F811
        html = app.handle("GET", "/admin/fleet", cookies=cookies).html
        assert версия_из_формы(html, САЙТ_A).startswith("sha256:")

    def test_форма_защищена_csrf(self, app, cookies):  # noqa: F811
        html = app.handle("GET", "/admin/fleet", cookies=cookies).html
        кусок = карточка(html, САЙТ_A)
        i = кусок.find('action="/admin/fleet/settings"')
        assert '_csrf' in кусок[i:i + 400], "форма настройки идёт без токена"


class TestЗаписьИдётДоговором:
    def _форма(self, app, cookies, **поля):  # noqa: F811
        html = app.handle("GET", "/admin/fleet", cookies=cookies).html
        кусок = карточка(html, САЙТ_A)
        метка = 'name="_csrf" value="'
        i = кусок.find(метка)
        csrf = кусок[i + len(метка):кусок.index('"', i + len(метка))]
        форма = {"_csrf": csrf, "siteId": САЙТ_A, "key": "advertising_partner_id"}
        форма.update(поля)
        return форма

    def test_сухой_прогон_показывает_сравнение_в_карточке(self, app, cookies):  # noqa: F811
        html = app.handle("GET", "/admin/fleet", cookies=cookies).html
        форма = self._форма(
            app, cookies,
            value="partner-777",
            expectedVersion=версия_из_формы(html, САЙТ_A),
            dryRun="1",
        )
        ответ = app.handle("POST", "/admin/fleet/settings", form=форма, cookies=cookies)
        assert ответ.status == 200, "сухой прогон не открыл сводку"
        assert "станет" in ответ.html and "partner-777" in ответ.html, (
            "проверка не показала, что именно изменится")

    def test_карточка_с_проверкой_раскрыта(self, app, cookies):  # noqa: F811
        html = app.handle("GET", "/admin/fleet", cookies=cookies).html
        форма = self._форма(
            app, cookies,
            value="partner-777",
            expectedVersion=версия_из_формы(html, САЙТ_A),
            dryRun="1",
        )
        ответ = app.handle("POST", "/admin/fleet/settings", form=форма, cookies=cookies)
        assert "<details open>" in ответ.html, (
            "сравнение спрятано за закрытым треугольником — его не увидят")

    def test_применение_меняет_значение(self, app, cookies):  # noqa: F811
        html = app.handle("GET", "/admin/fleet", cookies=cookies).html
        форма = self._форма(
            app, cookies,
            value="partner-777",
            expectedVersion=версия_из_формы(html, САЙТ_A),
        )
        ответ = app.handle("POST", "/admin/fleet/settings", form=форма, cookies=cookies)
        assert ответ.status in (302, 303), "после записи оператор не возвращён в сводку"
        assert ответ.headers.get("Location", "").endswith("/fleet")
        снова = app.handle("GET", "/admin/fleet", cookies=cookies).html
        assert "partner-777" in карточка(снова, САЙТ_A), "значение не записано"

    def test_чужая_правка_замечена_по_версии(self, app, cookies):  # noqa: F811
        html = app.handle("GET", "/admin/fleet", cookies=cookies).html
        устаревшая = версия_из_формы(html, САЙТ_A)

        первая = self._форма(app, cookies, value="partner-111", expectedVersion=устаревшая)
        app.handle("POST", "/admin/fleet/settings", form=первая, cookies=cookies)

        вторая = self._форма(app, cookies, value="partner-222", expectedVersion=устаревшая)
        app.handle("POST", "/admin/fleet/settings", form=вторая, cookies=cookies)

        снова = карточка(app.handle("GET", "/admin/fleet", cookies=cookies).html, САЙТ_A)
        assert "partner-111" in снова, "вторая запись затёрла первую по устаревшей версии"
        assert "partner-222" not in снова


class TestГраницыОстаютсяНаМесте:
    def test_локальному_администратору_маршрут_закрыт(self, app, люди):  # noqa: F811
        свои = войти(app, "local@test", САЙТ_A)
        ответ = app.handle(
            "POST", f"/s/{САЙТ_A}/admin/fleet/settings",
            form={"siteId": САЙТ_A, "key": "advertising_partner_id", "value": "x"},
            cookies=свои,
        )
        assert ответ.status in (403, 404), (
            "локальный администратор пишет настройки через экран массива")
