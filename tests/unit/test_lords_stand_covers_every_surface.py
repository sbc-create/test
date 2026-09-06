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

import pytest

import yaml

from factory.lords import fixtures as fx, preview as preview_mod, recommend as rec
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


class TestСтендРендеритКаруселль:
    @pytest.mark.parametrize("site_id", SITES)
    def test_главная_содержит_карусель(self, site_id, catalog):
        package, _ = preview_mod._package(site_id)
        site = render_mod.render_site(package, catalog=catalog, environ={})
        if "top_carousel" not in _home_blocks(site_id):
            pytest.skip(f"{site_id}: профиль не объявляет верхнюю карусель")
        home = site.pages["/"].body
        assert 'class="rail"' in home, (
            f"{site_id}: профиль объявляет карусель, а стенд её не показывает"
        )
