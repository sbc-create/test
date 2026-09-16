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

    def test_без_встроенного_набора_страница_обещает_ровно_то_что_умеет(self):
        """Главное правило прежнее: не называть число, до которого не дотянуться.

        Изменилось не правило, а возможность. Прежде на большом каталоге поиска
        не было вовсе, и назвать число записей значило солгать. Теперь страница
        забирает указатель отдельным документом, и число названо законно — но
        только если указатель действительно отдаётся. Проверяется именно связь
        обещания с возможностью, а не наличие того или другого по отдельности.
        """
        big = render_mod.DATASET_MAX_TITLES + 1
        body = self._страница(big)
        assert "application/json" not in body, "набор встроен вопреки пределу"
        assert render_mod.SEARCH_INDEX_PATH in body, (
            "страница не знает, где взять указатель, но обещает поиск")
        assert str(big) in body, "число записей не названо при работающем поиске"

    def test_с_отключённым_указателем_обещания_нет(self):
        """Владелец вправе отказаться от указателя — тогда возвращается прежняя правда."""
        big = render_mod.DATASET_MAX_TITLES + 1
        body = render_mod._search_body({}, _catalog(big).titles, index_enabled=False)
        assert render_mod.SEARCH_INDEX_PATH not in body
        assert str(big) not in body, (
            f"страница обещает поиск по {big} записям, не имея ни одной: "
            "именно так зритель и заключает, что каталог пуст")
        text = re.sub(r"<[^>]+>", " ", body).lower()
        assert any(word in text for word in ("отключён", "недоступен", "разделы")), (
            "страница молчит о том, что поиска нет, и выглядит исправной")

    def test_состояние_загрузки_названо(self):
        """Указатель не мгновенный, и молчание в эти секунды выглядит поломкой."""
        body = self._страница(render_mod.DATASET_MAX_TITLES + 1)
        text = re.sub(r"<[^>]+>", " ", body).lower()
        assert "загружается" in text, "страница не предупреждает о загрузке указателя"
        assert "раздел" in text, "страница не называет путь, работающий без указателя"
