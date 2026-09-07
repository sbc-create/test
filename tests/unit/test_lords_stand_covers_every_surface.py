"""Стенд обязан показывать те же поверхности, что и боевые витрины.

Ворота приёмки ходят на фикстурный стенд, а не на боевые витрины: так и
задумано — боевые данные в тесты не тянутся. Но у этого есть цена, которую
легко не заметить. Если стенд не рендерит какой-то блок, все двести с лишним
браузерных проверок — доступность, эталон раскладки, клавиатура, увеличение —
об этом блоке ничего не говорят, а отчёт при этом зелёный.

Ровно это и случилось с верхней каруселью. Полка `latest_added` отбирает
записи по дате добавления, у фикстурных записей её не было вовсе, полка
выходила пустой, а карусель рендерится только от четырёх записей. На боевых
витринах карусель есть, на стенде её не было никогда — и обрезку названий при
двукратном увеличении текста ворота пропустили именно поэтому.

Эти проверки закрепляют, что стенд показывает каждый объявленный профилем
блок. Они про полноту доказательства, а не про разметку.
"""

from __future__ import annotations

import pathlib
import re

import pytest
import yaml

from factory.lords import fixtures as fx
from factory.lords import preview as preview_mod
from factory.lords import recommend as rec
from factory.lords import render as render_mod

PROFILES = {
    "lords-01": "lords-general",
    "lords-02": "lords-new",
    "lords-03": "lords-curated",
    "lords-04": "lords-genre",
}


def _home_blocks(site_id: str) -> list:
    path = f"blueprints/lords/profiles/{PROFILES[site_id]}.yaml"
    data = yaml.safe_load(pathlib.Path(path).read_text(encoding="utf-8"))
    for section in data.values():
        if isinstance(section, dict) and "home_blocks" in section:
            return list(section["home_blocks"])
    return list(data.get("home_blocks") or [])

SITES = ("lords-01", "lords-02", "lords-03", "lords-04")


@pytest.fixture(scope="module")
def catalog():
    return fx.build_catalog()


class TestПолкаСобираетсяНаФикстуре:
    def test_у_каждой_записи_есть_дата_добавления(self, catalog):
        """Без неё `latest_added` пуста, и карусель не появляется никогда."""
        без_даты = [t.slug for t in catalog.titles if not getattr(t, "created_at", None)]
        assert без_даты == [], f"записи без даты добавления: {без_даты[:5]}"

    def test_даты_различаются(self, catalog):
        """Одинаковые даты дали бы порядок по слагу, а не по свежести."""
        даты = {t.created_at for t in catalog.titles}
        assert len(даты) > 1, "все записи добавлены одним мгновением"

    def test_каталог_детерминирован(self):
        """Дата, взятая от текущего времени, ломала бы отпечаток сборки."""
        assert [t.created_at for t in fx.build_catalog().titles] == [
            t.created_at for t in fx.build_catalog().titles
        ]

    def test_полка_набирает_карусель(self, catalog):
        shelf = rec.carousel_shelf(catalog.titles, domain=None)
        assert shelf is not None and len(shelf) >= 4, (
            f"полка из {0 if shelf is None else len(shelf)} записей: "
            "карусель не отрисуется, и ворота её не увидят"
        )


class TestСтендПоказываетКаждыйОбъявленныйБлок:
    """Полнота стенда целиком, а не одна карусель.

    Проверка обобщена намеренно. Карусель нашлась случайно — при разборе
    обрезки названий, — и точечная проверка на неё закрепила бы один частный
    случай, оставив тот же разрыв открытым для остальных блоков. Обобщение
    сразу же дало вторую находку: полка «высокие оценки» объявлена тремя
    профилями и не появлялась на стенде ни разу, потому что у фикстурных
    записей не было оценок. Вместе с ней ворота не видели и показ двух оценок
    на карточке.
    """

    #: `hero` рендерится всегда и в список блоков профиля не входит: это не
    #: элемент состава главной, а её шапка.
    ВСЕГДА = {"hero"}

    @pytest.mark.parametrize("site_id", SITES)
    def test_каждый_объявленный_блок_есть_в_разметке(self, site_id, catalog):
        package, _ = preview_mod._package(site_id)
        home = render_mod.render_site(package, catalog=catalog, environ={}).pages["/"].body
        present = set(re.findall(r'data-block="([^"]+)"', home))
        объявлено = _home_blocks(site_id)
        нет = [b for b in объявлено if b not in present]
        assert нет == [], (
            f"{site_id}: профиль объявляет {нет}, а стенд их не показывает — "
            "значит браузерные ворота об этих блоках ничего не проверяют"
        )

    @pytest.mark.parametrize("site_id", SITES)
    def test_лишних_блоков_не_появляется(self, site_id, catalog):
        package, _ = preview_mod._package(site_id)
        home = render_mod.render_site(package, catalog=catalog, environ={}).pages["/"].body
        present = set(re.findall(r'data-block="([^"]+)"', home)) - self.ВСЕГДА
        лишние = sorted(present - set(_home_blocks(site_id)))
        assert лишние == [], f"{site_id}: показаны блоки, которых манифест не просил: {лишние}"


class TestДанныеСтендаПредставительны:
    """Данных должно хватать не «чтобы собралось», а чтобы ворота были зрячими.

    Каждое из этих свойств уже однажды стоило пропущенного дефекта.
    """

    def test_есть_записи_с_обеими_оценками(self, catalog):
        обе = [t for t in catalog.titles
               if t.kinopoisk_rating is not None and t.imdb_rating is not None]
        assert обе, "без записей с двумя оценками показ обеих не проверяется ничем"

    def test_есть_записи_с_одной_оценкой_и_без_оценок(self, catalog):
        только_кп = [t for t in catalog.titles
                     if t.kinopoisk_rating is not None and t.imdb_rating is None]
        только_imdb = [t for t in catalog.titles
                       if t.kinopoisk_rating is None and t.imdb_rating is not None]
        без = [t for t in catalog.titles
               if t.kinopoisk_rating is None and t.imdb_rating is None]
        assert только_кп and только_imdb and без, (
            "рендерер различает четыре случая оценок; стенд обязан показать все"
        )

    def test_есть_все_три_состояния_потока(self, catalog):
        состояния = {t.playable for t in catalog.titles}
        assert состояния == {True, False, None}, (
            f"на стенде только состояния {состояния}: запасные ветки плеера "
            "не отрисовываются, и ворота их не видят"
        )

    def test_длина_названий_покрывает_боевой_диапазон(self, catalog):
        """Ворота, меряющие перенос и обрезку, на коротких именах молчат."""
        самое_длинное = max(len(t.name) for t in catalog.titles)
        assert самое_длинное >= 34, (
            f"самое длинное имя стенда — {самое_длинное} знаков; в боевом "
            "каталоге встречаются тридцать четыре и длиннее, и обрезку при "
            "увеличении текста короткие имена не воспроизводят"
        )
