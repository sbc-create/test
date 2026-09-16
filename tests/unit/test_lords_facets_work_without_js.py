"""Фильтры работают без JavaScript.

## Что наблюдалось на боевой витрине

На `/catalog/` выбор года `2025` менял `select.value`, и на этом всё
заканчивалось: адрес оставался `/catalog/`, число записей — 52 725, первые
карточки — тайтлы 2026 года.

Причина в разметке: у полей фасетов нет ни `name`, ни `method`, ни `action`.
Это зацепки для скрипта, а не форма. Скрипт же работает «поверх встроенного
набора данных», которого при каталоге больше двухсот записей не существует —
`_dataset` возвращает пустую строку. Обработчики не регистрируются, и выбор
никуда не ведёт.

## Что требуется

Выбор обязан работать без JavaScript. На статической витрине это значит:
каждое значение фасета — ссылка на существующую посадочную страницу
(`/genres/<slug>/`, `/years/<год>/`, `/countries/<slug>/`), а не пункт списка,
который никто не читает.

Скрипт вправе улучшать, но не быть единственным путём.

## Чего эта проверка НЕ требует

Комбинированных фильтров. Пересечение «жанр + год» на статической витрине
требует страницы под каждую комбинацию, и их не существует. Это ограничение
названо прямо и передано владельцу запроса, а не спрятано за молчащим полем.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from factory.lords import fixtures as fx  # noqa: E402
from factory.lords import render as render_mod  # noqa: E402


def _catalog() -> fx.Catalog:
    def title(slug, year, gslug, glabel, cslug, clabel):
        return fx.Title(slug=slug, name=f"Запись {slug}", original_name="",
                        content_type="movies", year=year, country_slug=cslug,
                        country=clabel, genre_slugs=(gslug,), genres=(glabel,),
                        studio="", runtime_min=None, age_rating="", summary="",
                        seasons=())
    return fx.Catalog(titles=(
        title("a", 2025, "drama", "Драма", "ssha", "США"),
        title("b", 2024, "komediya", "комедия", "kanada", "Канада"),
        title("c", 2025, "drama", "Драма", "kanada", "Канада"),
    ), collections=())


def _panel() -> str:
    return render_mod._facets(_catalog(), ("movies",), show_type=False)


class TestФасетыДоступныБезСкрипта:
    def test_жанры_отдаются_ссылками(self):
        panel = _panel()
        assert 'href="/genres/drama/"' in panel, (
            "жанр не является ссылкой: без скрипта выбор никуда не ведёт")
        assert 'href="/genres/komediya/"' in panel

    def test_годы_отдаются_ссылками(self):
        panel = _panel()
        assert 'href="/years/2025/"' in panel
        assert 'href="/years/2024/"' in panel

    def test_страны_отдаются_ссылками(self):
        panel = _panel()
        assert 'href="/countries/ssha/"' in panel
        assert 'href="/countries/kanada/"' in panel

    def test_нет_поля_без_имени_как_единственного_управления(self):
        """`<select>` без `name` в форме без `method` ничего не отправляет.

        Такое поле выглядит рабочим и не работает — худший вид неисправности.
        """
        panel = _panel()
        for match in re.finditer(r"<select\b[^>]*>", panel):
            tag = match.group(0)
            assert "name=" in tag, f"поле без имени: {tag}"

    def test_счётчики_рядом_с_подписью(self):
        panel = _panel()
        assert "Драма" in panel and "(2)" in panel, "счётчик значения потерян"

    def test_панель_имеет_доступное_имя(self):
        assert 'aria-label="Фильтры' in _panel() or "<h2>Фильтры" in _panel()
