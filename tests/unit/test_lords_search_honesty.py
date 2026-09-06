"""Страница поиска не обещает того, чего не может.

Дефект наблюдался на боевой витрине lordserial33.biz. Страница `/search/`
сообщала «Введите название: поиск идёт по 52 725 записям каталога» и не
находила ничего — ни при переходе по `/search/?q=…`, ни при вводе в поле.
Проверено браузером с включённым JavaScript: блоков данных на странице ноль.

Причина в `_dataset`: набор для клиентского поиска не отдаётся, если записей
больше `DATASET_MAX_TITLES` (200). Ограничение разумно — иначе каждая страница
несла бы мегабайты, — но следствие никем не объявлено: поиск молча перестаёт
работать на любом каталоге больше двухсот записей, а страница продолжает
называть их число.

Ложное обещание хуже отсутствия возможности: зритель вводит запрос, ничего не
получает и заключает, что в каталоге ничего нет.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from factory.lords import fixtures as fx  # noqa: E402
from factory.lords import render as render_mod  # noqa: E402


def _catalog(n: int) -> fx.Catalog:
    titles = tuple(
        fx.Title(slug=f"t{i}", name=f"Запись {i}", original_name="",
                 content_type="movies", year=2024, country_slug="ssha",
                 country="США", genre_slugs=("drama",), genres=("Драма",),
                 studio="", runtime_min=None, age_rating="", summary="", seasons=())
        for i in range(n)
    )
    return fx.Catalog(titles=titles, collections=())


class TestОбещаниеПоискаСоответствуетВозможности:
    @staticmethod
    def _страница(n: int) -> str:
        # Проверяется тело страницы, а не сборка документа: та требует полного
        # контекста витрины — токенов темы, навигации, крошек, — и
        # восстанавливать их ради одного правила значило бы проверять оснастку
        # теста.
        return render_mod._search_body({}, _catalog(n).titles)

    def test_при_наличии_набора_число_названо(self):
        body = self._страница(10)
        assert "10 запис" in body or "10 " in body, "число записей не названо"
        assert "dataset" in body or "application/json" in body, (
            "набор данных не отдан, хотя записей меньше предела")

    def test_без_набора_страница_не_обещает_поиск_по_каталогу(self):
        """Главное правило: не называть число, до которого не дотянуться."""
        big = render_mod.DATASET_MAX_TITLES + 1
        body = self._страница(big)
        assert "application/json" not in body, "набор отдан вопреки пределу"
        assert str(big) not in body, (
            f"страница обещает поиск по {big} записям, не имея ни одной: "
            "именно так зритель и заключает, что каталог пуст")

    def test_без_набора_состояние_объяснено(self):
        body = self._страница(render_mod.DATASET_MAX_TITLES + 1)
        text = re.sub(r"<[^>]+>", " ", body).lower()
        assert any(word in text for word in ("недоступен", "не работает", "разделы")), (
            "страница молчит о том, что поиск сейчас недоступен, и выглядит исправной")
