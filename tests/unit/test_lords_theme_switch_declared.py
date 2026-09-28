"""Переключатель темы включается объявленной темой витрины.

Публичная проверка нашла: на боевой витрине переключателя режима нет вовсе.
Код переключателя в шаблоне был, но включается он наличием второй палитры, а
профиль витрины её не объявлял — и кнопка не рисовалась. Модуль при этом прямо
отказывается выводить палитру арифметикой: «получится не светлая тема, а тёмная
с испорченным контрастом; выбор цветов — решение оформления, а не вычисление».

Здесь ничего и не вычисляется. Если манифест назвал поверхность (`lords_dark`,
`lords_light`), второй палитрой берётся противоположный набор из
`SURFACE_PALETTES` — уже одобренный и уже проверенный на контраст тестом. Это
тот же приём, которым `tokens_of` подбирает основную палитру.
"""

from __future__ import annotations

import pytest

from factory.lords import theme as th

ПРОФИЛЬ = {"theme": {"name": "lords-curated", "tokens": {}}}


class TestВключениеПереключателя:
    def test_без_объявленной_темы_переключателя_нет(self):
        """Кнопка, которой нечего переключать, хуже её отсутствия."""
        assert th.theme_switch_available(ПРОФИЛЬ) is False

    @pytest.mark.parametrize("тема", ["lords_dark", "lords_light"])
    def test_объявленная_тема_включает_переключатель(self, тема):
        assert th.theme_switch_available(ПРОФИЛЬ, declared_theme=тема) is True

    def test_имя_без_поверхности_переключатель_не_включает(self):
        assert th.theme_switch_available(ПРОФИЛЬ, declared_theme="lords-curated") is False


class TestВтораяПалитраПротивоположна:
    def test_тёмной_теме_соответствует_светлая(self):
        схема, токены = th.alt_tokens_of(ПРОФИЛЬ, declared_theme="lords_dark")
        assert схема == "light"
        assert токены["bg"] == th.SURFACE_PALETTES["light"]["bg"]

    def test_светлой_теме_соответствует_тёмная(self):
        схема, токены = th.alt_tokens_of(ПРОФИЛЬ, declared_theme="lords_light")
        assert схема == "dark"
        assert токены["bg"] == th.SURFACE_PALETTES["dark"]["bg"]

    def test_объявленная_профилем_палитра_сильнее_выведенной(self):
        """Явное решение оформления не перебивается подстановкой."""
        профиль = {"theme": {"name": "x", "tokens": {},
                             "tokens_alt": {"bg": "#010203"}, "alt_scheme": "light"}}
        схема, токены = th.alt_tokens_of(профиль, declared_theme="lords_dark")
        assert схема == "light" and токены["bg"] == "#010203"


class TestПравилаПопадаютВТаблицуСтилей:
    def test_блоки_второй_палитры_появляются(self):
        блоки = th.alt_blocks(ПРОФИЛЬ, declared_theme="lords_dark")
        assert 'prefers-color-scheme: light' in блоки
        assert ':root[data-theme="light"]' in блоки
        assert ':root[data-theme="dark"]' in блоки
        assert ".theme-switch" in блоки

    def test_без_темы_блоков_нет(self):
        assert th.alt_blocks(ПРОФИЛЬ) == ""

    def test_таблица_стилей_несёт_переключатель(self):
        стили = th.stylesheet(ПРОФИЛЬ, declared_theme="lords_dark")
        assert ".theme-switch" in стили, (
            "маркер нового шаблона обязан быть виден публично в /assets/site.css")
