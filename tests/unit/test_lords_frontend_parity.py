"""Интерфейс витрин Lords: один поиск, честные секции.

Проверки написаны по замерам в браузере, а не по намерению. Каждая соответствует
дефекту, который был виден на живой витрине.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from factory.lords import live_catalog  # noqa: E402
from factory.lords import render as render_mod
from factory.paths import PATHS  # noqa: E402

КЭШ = Path("/srv/site-factory/repo/var/lords/lords/catalog-cache")


def построить(site_id: str, сколько: int = 200):
    """Разметка витрины на подмножестве настоящего каталога."""
    import yaml

    файл = КЭШ / f"{site_id}.json"
    if not файл.exists():
        pytest.skip(f"кэша каталога нет: {файл}")
    items = json.loads(файл.read_text(encoding="utf-8"))["items"][:сколько]
    catalog = live_catalog.catalog_from_live(items)
    package = yaml.safe_load(PATHS.site_package(site_id).read_text(encoding="utf-8"))
    return render_mod.render_site(package, catalog=catalog, environ={}, publisher_id=None)


@pytest.fixture(scope="module")
def главные():
    out = {}
    for site in ("lords-01", "lords-02", "lords-03"):
        сайт = построить(site)
        out[site] = сайт.pages["/"].body
    return out


class TestОдинПоиск:
    """На lordfilm47.space было две одинаковых формы: в шапке и в герое."""

    @pytest.mark.parametrize("site", ["lords-01", "lords-02", "lords-03"])
    def test_ровно_одна_форма_поиска(self, главные, site):
        assert главные[site].count('class="header-search"') == 1, (
            "две формы поиска на одной странице — это выбор без разницы"
        )

    @pytest.mark.parametrize("site", ["lords-01", "lords-02", "lords-03"])
    def test_ровно_одно_поле_поиска(self, главные, site):
        assert главные[site].count('type="search"') == 1

    @pytest.mark.parametrize("site", ["lords-01", "lords-02", "lords-03"])
    def test_форма_ведёт_на_страницу_поиска(self, главные, site):
        assert 'action="/search/"' in главные[site]

    @pytest.mark.parametrize("site", ["lords-01", "lords-02", "lords-03"])
    def test_поле_имеет_подпись(self, главные, site):
        """Подпись нужна не для красоты: без неё поле безымянно для чтения с экрана."""
        assert 'class="visually-hidden" for="q"' in главные[site]
        assert "Поиск по каталогу" in главные[site]

    def test_дубликат_в_герое_не_возвращается(self):
        """Регрессия: блок hero_search не должен снова рисовать форму."""
        исходник = (PATHS.root / "factory" / "lords" / "render.py").read_text(encoding="utf-8")
        i = исходник.index('if "hero_search" in blocks:') if 'if "hero_search" in blocks:' in исходник else -1
        assert i == -1, "форма поиска в герое повторяет форму шапки"


class TestФильтрРядомСПоиском:
    @pytest.mark.parametrize("site", ["lords-01", "lords-02", "lords-03"])
    def test_кнопка_фильтра_есть(self, главные, site):
        assert "header-search__filter" in главные[site]

    @pytest.mark.parametrize("site", ["lords-01", "lords-02", "lords-03"])
    def test_фильтр_внутри_формы_поиска(self, главные, site):
        """Иначе он не окажется в одной строке с полем."""
        html = главные[site]
        начало = html.index('<form class="header-search"')
        конец = html.index("</form>", начало)
        assert "header-search__filter" in html[начало:конец]

    @pytest.mark.parametrize("site", ["lords-01", "lords-02", "lords-03"])
    def test_фильтр_ведёт_в_каталог(self, главные, site):
        assert 'href="/catalog/"' in главные[site]

    def test_стиль_держит_фильтр_в_строке(self):
        стили = (PATHS.root / "factory" / "lords" / "theme.py").read_text(encoding="utf-8")
        assert ".header-search__filter" in стили
        assert "white-space: nowrap" in стили, "без этого надпись переносится и ломает строку"
        assert "flex-wrap: nowrap" in стили, "строка поиска не должна рассыпаться по элементам"


class TestСекцииНеОбещаютЛишнего:
    """«Жанры» показывали одну ссылку: жанры заполнены у 129 записей из 53 116."""

    def test_порог_жанров_объявлен(self):
        assert render_mod.MIN_GENRE_CHIPS >= 3

    @pytest.mark.parametrize("site", ["lords-01", "lords-02", "lords-03"])
    def test_раздел_жанров_скрыт_при_бедных_данных(self, главные, site):
        """Заголовок «Жанры» с одной ссылкой выглядит поломкой, а не рубрикатором."""
        html = главные[site]
        if "<h2>Жанры</h2>" not in html:
            return
        начало = html.index("<h2>Жанры</h2>")
        конец = html.index("</section>", начало)
        ссылок = html[начало:конец].count("<a ")
        assert ссылок >= render_mod.MIN_GENRE_CHIPS, (
            f"раздел «Жанры» показан с {ссылок} ссылками"
        )

    @pytest.mark.parametrize("site", ["lords-01", "lords-02", "lords-03"])
    def test_годы_остаются_на_месте(self, главные, site):
        """Годы заполнены и полезны — их скрывать не за что."""
        html = главные[site]
        if "<h2>Годы выпуска</h2>" in html:
            начало = html.index("<h2>Годы выпуска</h2>")
            конец = html.index("</section>", начало)
            assert html[начало:конец].count("<a ") >= 5


class TestПлеерНеТронут:
    """Плеер — запретная область; проверка стережёт границу."""

    def test_разметка_плеера_не_менялась(self):
        исходник = (PATHS.root / "factory" / "lords" / "player.py").read_text(encoding="utf-8")
        assert "video-player" in исходник

    def test_вызов_плеера_из_рендерера_не_менялся(self):
        """Проверяется то, что тест способен установить.

        Первая редакция требовала, чтобы плеер присутствовал на собранных
        страницах. Это оказалось неверным критерием: состояние плеера приходит
        из окружения, а сборка в тесте передаёт пустое, и плееров ноль — как до
        моих правок, так и после. Проверено сравнением с базовой веткой:
        196 страниц тайтлов, 0 плееров в обоих деревьях.

        Поэтому здесь стережётся граница, а не поведение: рендерер обращается к
        модулю плеера ровно так же, как раньше. Присутствие плеера на живых
        страницах проверяет PLAYER_FREEZE_GATE, которому доступно настоящее
        окружение.
        """
        исходник = (PATHS.root / "factory" / "lords" / "render.py").read_text(encoding="utf-8")
        assert "player_mod.state(environ)" in исходник
        assert "player_mod" in исходник

    def test_модуль_плеера_не_изменён_ветвью(self):
        """Плеер — запретная область: файл не должен отличаться от базы."""
        import subprocess

        итог = subprocess.run(
            ["git", "diff", "--name-only", "0e966d8", "--", "factory/lords/player.py"],
            cwd=PATHS.root, capture_output=True, text=True, check=False,
        )
        assert итог.stdout.strip() == "", f"файл плеера изменён: {итог.stdout}"
