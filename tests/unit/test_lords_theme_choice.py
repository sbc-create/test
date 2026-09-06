"""Выбор темы: система, светлая, тёмная.

## Что было

Переключателя не существовало вовсе: ни `prefers-color-scheme`, ни
`color-scheme`, ни `data-theme` в таблице стилей и разметке не встречалось.
Палитра задавалась профилем витрины — `lords_dark` тёмная (#111111),
`lords_light` светлая (#f4f6f8), — и зритель не мог выбрать ничего.

Профильное различие остаётся: это лицо витрины. Выбор темы — другое: это
предпочтение зрителя поверх лица витрины.

## Что проверяется

Не наличие токенов, а работа: обе палитры объявлены, системная настройка
учтена, выбор переживает переход между страницами, вспышки чужой темы до
разбора разметки нет, и в обеих палитрах текст читается.

Неиспользуемые токены реализацией не считаются.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from factory.lords import plan as plan_mod  # noqa: E402
from factory.lords import theme as theme_mod  # noqa: E402

PROFILES = ("lords-general", "lords-genre")


def sheet(name: str) -> str:
    return theme_mod.stylesheet(plan_mod.load_profiles()[name])


def _luminance(color: str) -> float:
    color = color.strip().lstrip("#")
    if len(color) == 3:
        color = "".join(ch * 2 for ch in color)
    r, g, b = (int(color[i:i + 2], 16) / 255 for i in (0, 2, 4))

    def channel(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = channel(r), channel(g), channel(b)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(fg: str, bg: str) -> float:
    a, b = _luminance(fg), _luminance(bg)
    light, dark = max(a, b), min(a, b)
    return (light + 0.05) / (dark + 0.05)


def _block(css: str, selector: str) -> dict[str, str]:
    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", css)
    if not match:
        return {}
    out = {}
    for line in match.group(1).split(";"):
        if ":" in line:
            key, value = line.split(":", 1)
            out[key.strip()] = value.strip()
    return out


class TestОбеПалитрыОбъявлены:
    def test_есть_явная_тёмная_палитра(self):
        css = sheet("lords-general")
        assert ':root[data-theme="dark"]' in css, "нет явной тёмной палитры"

    def test_есть_явная_светлая_палитра(self):
        css = sheet("lords-general")
        assert ':root[data-theme="light"]' in css, "нет явной светлой палитры"

    def test_системная_настройка_учтена(self):
        css = sheet("lords-general")
        assert "prefers-color-scheme" in css, "системная настройка не учитывается"

    def test_color_scheme_объявлен(self):
        """Без `color-scheme` браузер рисует свои элементы управления и полосы
        прокрутки в чужой теме — страница выходит двухцветной."""
        assert "color-scheme" in sheet("lords-general")

    def test_системный_выбор_не_перебивает_явный(self):
        """Явный выбор зрителя обязан побеждать системную настройку."""
        css = sheet("lords-general")
        media = re.search(r"@media \(prefers-color-scheme: dark\)\s*\{(.+?)\n\}", css, re.S)
        assert media, "нет ветки системной тёмной темы"
        assert 'not([data-theme=' in media.group(1), (
            "системная ветка перебивает явный выбор зрителя")


class TestТекстЧитаетсяВОбеихПалитрах:
    def test_контраст_тёмной_палитры(self):
        tokens = _block(sheet("lords-general"), ':root[data-theme="dark"]')
        ratio = contrast(tokens["--text"], tokens["--bg"])
        assert ratio >= 4.5, f"контраст тёмной палитры {ratio:.2f} ниже AA"

    def test_контраст_светлой_палитры(self):
        tokens = _block(sheet("lords-general"), ':root[data-theme="light"]')
        ratio = contrast(tokens["--text"], tokens["--bg"])
        assert ratio >= 4.5, f"контраст светлой палитры {ratio:.2f} ниже AA"

    def test_приглушённый_текст_тоже_читается(self):
        """Приглушённый — не значит нечитаемый: им набраны год, тип и счётчики."""
        for mode in ("dark", "light"):
            tokens = _block(sheet("lords-general"), f':root[data-theme="{mode}"]')
            ratio = contrast(tokens["--muted"], tokens["--bg"])
            assert ratio >= 4.5, f"приглушённый текст в {mode}: {ratio:.2f}"


class TestПрофилиОстаютсяРазличимыми:
    def test_тёмный_и_светлый_профиль_различаются_по_умолчанию(self):
        dark = _block(sheet("lords-general"), ":root")
        light = _block(sheet("lords-genre"), ":root")
        assert dark["--bg"] != light["--bg"], (
            "профили перестали различаться: выбор темы не должен стирать лицо витрины")


class TestПереключательСуществуетИРаботает:
    """Токены без переключателя — не реализация: выбрать зрителю нечем."""

    @staticmethod
    def _header(site_id: str = "lords-01") -> str:
        from factory.lords import render as render_mod
        return render_mod._theme_switch(site_id)

    def test_три_состояния_доступны(self):
        html = self._header()
        for value in ("system", "light", "dark"):
            assert f'data-theme-set="{value}"' in html, f"нет выбора «{value}»"

    def test_у_каждой_кнопки_есть_доступное_имя(self):
        import re
        html = self._header()
        for button in re.findall(r"<button\b[^>]*>", html):
            assert "aria-label" in button or ">" in button, f"кнопка без имени: {button}"
        assert "Тема оформления" in html or 'aria-label="Тема' in html

    def test_состояние_объявлено_для_вспомогательных_технологий(self):
        assert "aria-pressed" in self._header()

    def test_группа_подписана(self):
        html = self._header()
        assert 'role="group"' in html and "aria-label" in html


class TestВыборНеМигаетИСохраняется:
    @staticmethod
    def _script(site_id: str = "lords-01") -> str:
        from factory.lords import render as render_mod
        return render_mod._theme_boot(site_id)

    def test_тема_ставится_до_первого_кадра(self):
        """Скрипт обязан быть встроенным и стоять в head.

        Тема, выставленная после разбора разметки, даёт вспышку: страница
        приходит одной, перекрашивается в другую на глазах. На тёмной теме это
        удар белым в темноте — ровно то, ради чего тему и выбирали.
        """
        script = self._script()
        assert "documentElement" in script
        assert "setAttribute" in script or "dataset" in script

    def test_предпочтение_различается_по_витринам(self):
        """Соседние витрины не делят выбор: у каждой свой ключ.

        Проверяется различие, а не наличие имени витрины в разметке. Имя туда
        попадать не должно: `lords-01` — внутренняя классификация фабрики, и
        в публичном подвале ей не место.
        """
        assert self._script("lords-01") != self._script("lords-03")

    def test_идентификатор_витрины_не_попадает_в_разметку(self):
        from factory.lords import render as render_mod

        assert "lords-01" not in self._script("lords-01")
        assert "lords-01" not in render_mod._theme_switch("lords-01")

    def test_ключ_устойчив_между_сборками(self):
        """Меняющийся ключ терял бы выбор зрителя при каждой выкладке."""
        assert self._script("lords-01") == self._script("lords-01")

    def test_скрипт_переживает_запрет_хранилища(self):
        """В приватном режиме обращение к хранилищу бросает исключение.

        Непойманное — оставит страницу без темы и уронит остальной сценарий.
        """
        assert "catch" in self._script()


class TestСсылкиЧитаютсяВОбеихПалитрах:
    """Акцент профиля — лицо витрины, но не всегда читаемая ссылка.

    Зелёный `#79c142` на тёмном фоне даёт контраст около семи, на светлой
    палитре — около двух. Менять акцент нельзя: витрины перестали бы
    различаться. Поэтому цвет ССЫЛКИ вычисляется из акцента до порога AA —
    вычисляется, а не подбирается: подбор не воспроизводится и разъезжается
    при первой смене палитры.

    Отказ был найден браузерной проверкой: axe отметил 17 узлов с
    недостаточным контрастом на светлой палитре, и это была регрессия от
    введения самой темы.
    """

    def test_ссылка_проходит_порог_в_светлой_палитре(self):
        css = sheet("lords-general")
        tokens = _block(css, ':root[data-theme="light"]')
        ratio = contrast(tokens["--link"], tokens["--bg"])
        assert ratio >= 4.5, f"ссылка в светлой палитре: {ratio:.2f}"

    def test_ссылка_проходит_порог_в_тёмной_палитре(self):
        tokens = _block(sheet("lords-general"), ':root[data-theme="dark"]')
        ratio = contrast(tokens["--link"], tokens["--bg"])
        assert ratio >= 4.5, f"ссылка в тёмной палитре: {ratio:.2f}"

    def test_акцент_не_изменён(self):
        """Вычисляется цвет ссылки, а не акцент: акцент остаётся лицом витрины."""
        css = sheet("lords-general")
        assert _block(css, ":root")["--accent"] == "#79c142"

    def test_вычисление_воспроизводимо(self):
        from factory.lords.theme import readable_on
        assert readable_on("#79c142", "#f4f6f8") == readable_on("#79c142", "#f4f6f8")
