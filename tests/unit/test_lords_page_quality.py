"""Дефекты качества страниц, найденные рубрикой шаблона.

Каждый тест здесь описывает воспроизведённый дефект собранного документа, а не
пожелание к оформлению. Рубрика (`factory/templates/rubric.py`) нашла их на
готовом стенде всех четырёх профилей; тесты закрепляют исправление, чтобы оно
не отменилось следующей правкой рендерера.

Три дефекта:

1. **Повторяющийся `id="grid"` на главной.** `_grid()` выдавал идентификатор
   безусловно, а главная зовёт его по разу на каждую полку — от трёх до пяти
   одинаковых `id` в одном документе. Идентификатор нужен только там, где по
   нему работает скрипт списка (`catalog`, `search`): он ищет `listing-data` и
   `grid` вместе. На главной `listing-data` нет, скрипт выходит сразу, и все
   эти `id` не делали ничего — кроме нарушения уникальности.

2. **Фасеты без доступного имени.** Пять `<select>` каталога стояли в
   `<fieldset><legend>`. Легенда называет группу, а не поле: экранный диктор
   объявляет такой список как безымянный. Видимая подпись при этом уже есть,
   поэтому имя добавляется программно и раскладку не трогает.

3. **Пустой `<meta name="description">`.** Профили описывают тексты только для
   главной, поиска и разделов по типам. У `/schedule/` и `/collections/`
   секции нет, и описание выпадало в пустую строку. Пустой description хуже
   отсутствующего: он утверждает, что описание есть, и оно пусто.
"""

from __future__ import annotations

import re
from collections import Counter

import pytest
import yaml

from factory.lords import fixtures as fx
from factory.lords import render as render_mod
from factory.paths import PATHS
from factory.seo import validate as seo_validate

SITES = ("lords-01", "lords-02", "lords-03", "lords-04")

#: Профиль каждого пакета. Второй копии сопоставления нет: оно нужно, чтобы
#: сверить описанные разделы с теми, которыми витрина владеет.
PROFILE_OF = {
    "lords-01": "lords-general",
    "lords-02": "lords-new",
    "lords-03": "lords-curated",
    "lords-04": "lords-genre",
}


def package(site_id: str) -> dict:
    return yaml.safe_load(PATHS.site_package(site_id).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def catalog():
    return fx.build_catalog()


@pytest.fixture(scope="module")
def sites(catalog):
    return {
        site_id: render_mod.render_site(package(site_id), catalog=catalog, environ={})
        for site_id in SITES
    }


def _by_path(site) -> dict[str, str]:
    """Собранные HTML-документы сайта по адресу.

    Не-HTML отсеивается намеренно: `robots.txt`, `sitemap.xml` и иконка живут в
    том же наборе страниц, но правила разметки к ним неприменимы.
    """
    return {
        path: page.body
        for path, page in site.pages.items()
        if page.content_type.startswith("text/html") and page.raw is None
    }


def _ids(html: str) -> Counter:
    return Counter(re.findall(r'\bid="([^"]+)"', html))


# ---------------------------------------------------------------------------
# 1. Уникальность идентификаторов
# ---------------------------------------------------------------------------
class TestIdentifiersAreUnique:
    @pytest.mark.parametrize("site_id", SITES)
    def test_home_has_no_repeated_identifier(self, sites, site_id):
        html = _by_path(sites[site_id])["/"]
        repeated = {i: n for i, n in _ids(html).items() if n > 1}
        assert not repeated, f"{site_id}: повторяются id {repeated}"

    @pytest.mark.parametrize("site_id", SITES)
    def test_every_page_has_unique_identifiers(self, sites, site_id):
        for path, html in _by_path(sites[site_id]).items():
            repeated = {i: n for i, n in _ids(html).items() if n > 1}
            assert not repeated, f"{site_id} {path}: повторяются id {repeated}"

    def test_listing_anchor_survives_where_the_script_uses_it(self, sites):
        """Якорь остаётся там, где по нему действительно работает скрипт.

        Проверка защищает от «исправления» через полное удаление
        идентификатора: каталог и поиск оживают скриптом, который ищет
        `listing-data` и `grid` вместе, и без якоря список перестал бы
        отзываться на фильтры.
        """
        pages = _by_path(sites["lords-01"])
        for path in ("/catalog/", "/search/"):
            html = pages[path]
            assert 'id="grid"' in html, f"{path}: якорь списка пропал"
            assert 'id="listing-data"' in html, f"{path}: набор данных пропал"


# ---------------------------------------------------------------------------
# 2. Доступное имя у каждого поля формы
# ---------------------------------------------------------------------------
class TestFormControlsAreNamed:
    @pytest.mark.parametrize("site_id", SITES)
    def test_every_control_has_an_accessible_name(self, sites, site_id):
        """У поля есть имя: подпись через `for`, обёртка или `aria-label`."""
        for path, html in _by_path(sites[site_id]).items():
            labelled = set(re.findall(r'<label[^>]*\bfor="([^"]+)"', html))
            controls = re.findall(r'<(?:select|textarea|input)\b[^>]*>', html)
            for control in controls:
                if re.search(r'type="(?:hidden|submit|button|reset)"', control):
                    continue
                if "aria-label" in control:
                    continue
                found = re.search(r'\bid="([^"]+)"', control)
                assert found and found.group(1) in labelled, (
                    f"{site_id} {path}: поле без доступного имени: {control}")

    def test_facet_selects_keep_their_visible_legend(self, sites):
        """Имя добавляется, видимая подпись остаётся на месте."""
        html = _by_path(sites["lords-01"])["/catalog/"]
        for legend in ("Жанр", "Год", "Страна", "Сортировка"):
            assert f"<legend>{legend}</legend>" in html, f"пропала легенда {legend}"


# ---------------------------------------------------------------------------
# 3. Описание страницы либо содержательно, либо отсутствует
# ---------------------------------------------------------------------------
class TestDescriptionIsNeverEmpty:
    @pytest.mark.parametrize("site_id", SITES)
    def test_no_page_declares_an_empty_description(self, sites, site_id):
        for path, html in _by_path(sites[site_id]).items():
            assert 'name="description" content=""' not in html, (
                f"{site_id} {path}: объявлен пустой description")

    @pytest.mark.parametrize("site_id", SITES)
    def test_owned_sections_describe_themselves(self, site_id):
        """Профиль описывает ровно те разделы, которые индексирует.

        Владение и описание — одно решение, а не два. Раздел, который витрина
        отдаёт в индекс, обязан нести собственный текст: без него в выдаче
        окажется страница, за которую никто не отвечал. Раздел, которым витрина
        не владеет, текста не несёт намеренно — он остаётся навигацией с
        `noindex`, и придумывать ему описание значило бы заводить второго
        владельца одному и тому же разделу.
        """
        profile = yaml.safe_load(
            (PATHS.root / "blueprints/lords/profiles"
             / f"{PROFILE_OF[site_id]}.yaml").read_text(encoding="utf-8"))
        sections = profile.get("sections", {})
        # home и search есть у каждой витрины: у первой владелец `self`,
        # у второй владельца нет вовсе, но обе нуждаются в тексте.
        expected = set(profile.get("owns", [])) | {"home", "search"}
        assert set(sections) == expected, (
            f"{site_id}: описаны разделы {sorted(sections)}, "
            f"а индексируются {sorted(expected)}")
        # Порог не выбирается заново: он взят из SEO-003, который уже действует
        # в `factory/seo/validate.py`. Своя константа здесь означала бы второй
        # источник правды и расхождение при первой же правке ворот.
        indexed = set(profile.get("owns", [])) | {"home"}
        for name in sorted(indexed):
            description = (sections.get(name) or {}).get("description", "").strip()
            # Жёсткий порог SEO-003 — 40 символов — здесь отдельно не проверяется:
            # рекомендуемый минимум (70) строже, и его выполнение означает
            # выполнение жёсткого. Проверять оба значило бы проверять одно дважды.
            assert (seo_validate.DESCRIPTION_SOFT_MIN
                    <= len(description) <= seo_validate.DESCRIPTION_SOFT_MAX), (
                f"{site_id} раздел {name}: описание {len(description)} символов вне "
                f"рекомендуемого диапазона "
                f"{seo_validate.DESCRIPTION_SOFT_MIN}–{seo_validate.DESCRIPTION_SOFT_MAX}")

    def test_indexed_descriptions_are_unique_across_profiles(self):
        """Одинаковое описание у двух витрин — это одна витрина в двух адресах."""
        seen: dict[str, str] = {}
        for site_id, profile_name in PROFILE_OF.items():
            profile = yaml.safe_load(
                (PATHS.root / "blueprints/lords/profiles"
                 / f"{profile_name}.yaml").read_text(encoding="utf-8"))
            sections = profile.get("sections", {})
            for name in set(profile.get("owns", [])) | {"home"}:
                description = (sections.get(name) or {}).get("description", "").strip()
                assert description not in seen, (
                    f"{site_id}/{name} повторяет описание {seen.get(description)}")
                seen[description] = f"{site_id}/{name}"


# ---------------------------------------------------------------------------
# 4. Клиентский список знает то же разбиение, что и серверный
# ---------------------------------------------------------------------------
class TestPaginationModelIsDeclared:
    """Сервер режет каталог блоками годов, а скрипт списка — ровными двадцатью
    четырьмя. Пока модель разбиения не объявлена в разметке, скрипт не может её
    повторить, и первое же обращение к фильтру подменяет страницу: посетитель
    открыл блок 2025 года из трёх записей, тронул фильтр, сбросил его — и
    получил двадцать четыре записи вместо своих трёх. Обратно на страницу, с
    которой он начал, вернуться нечем.

    Договор о блоках годов записан в `adr/0007-pagination-by-year-blocks.md`.
    """

    def test_dataset_declares_page_size_and_model(self, sites):
        html = _by_path(sites["lords-01"])["/catalog/"]
        found = re.search(r'<script[^>]*id="listing-data"[^>]*>', html)
        assert found, "набора данных списка нет"
        tag = found.group(0)
        assert 'data-per-page="24"' in tag, f"не объявлен размер страницы: {tag}"
        assert 'data-pagination="year"' in tag, f"не объявлена модель разбиения: {tag}"

    def test_server_first_page_follows_year_blocks(self, sites, catalog):
        """Первая страница каталога — целиком первый блок года, не срез в 24."""
        html = _by_path(sites["lords-01"])["/catalog/"]
        slugs = re.findall(r'<article class="card" data-slug="([^"]+)"', html)
        assert slugs, "на первой странице каталога нет карточек"
        years = {s.rsplit("-", 1)[-1] for s in slugs}
        assert len(years) == 1, (
            f"первая страница смешала годы {sorted(years)} — это сплошной срез, "
            "а не блок года")


# ---------------------------------------------------------------------------
# 5. Заглушка плеера: кадр на месте, диагностика — в отчёте
# ---------------------------------------------------------------------------
class TestPlayerPlaceholderStaysPolite:
    """Договор REQ-LORDS-PLAYER-LIVE, зафиксированный решением D128.

    Соблазн здесь ровно один и он ошибочен: раз приёмке нужно отличать заглушку
    от плеера, вынести код отказа в `data-атрибут` — «посетитель же не увидит».
    Увидит: атрибут остаётся в исходнике публичной страницы, а запрет в
    `test_lords_player_reaches_the_visitor.py` написан по следам регрессии, где
    служебный текст месяцами висел на страницах фильмов. Отличать заглушку от
    плеера положено по её собственным признакам — их и проверяем.
    """

    @pytest.mark.parametrize("site_id", SITES)
    def test_placeholder_reserves_the_frame_and_explains_itself(self, sites, site_id):
        pages = {p: h for p, h in _by_path(sites[site_id]).items()
                 if p.startswith("/title/")}
        assert pages, f"{site_id}: страниц произведений нет"
        for path, html in pages.items():
            assert 'class="player__frame"' in html, (
                f"{site_id} {path}: кадр плеера не зарезервирован")
            assert "временно недоступно" in html, (
                f"{site_id} {path}: состояние плеера не объяснено посетителю")

    @pytest.mark.parametrize("site_id", SITES)
    def test_no_diagnostic_code_anywhere_in_the_document(self, sites, site_id):
        """Запрет распространяется на весь документ, а не на видимый текст."""
        for path, html in _by_path(sites[site_id]).items():
            for forbidden in ("BLOCKED_INPUT", "CDNVIDEOHUB_CREDENTIALS", "Publisher"):
                assert forbidden not in html, (
                    f"{site_id} {path}: в разметку попал служебный код {forbidden}")

    def test_dead_status_element_is_not_reintroduced(self, sites):
        """Элемента `.player__status` нет: он и был носителем утечки."""
        for site_id in SITES:
            for path, html in _by_path(sites[site_id]).items():
                assert "player__status" not in html, (
                    f"{site_id} {path}: вернулся элемент утечки")


# ---------------------------------------------------------------------------
# 6. Оценка не появляется без источника
# ---------------------------------------------------------------------------
class TestRatingsAlwaysCarryTheirSource:
    """Оценка без подписи источника — это выдуманное число.

    Механика оценок в рендерере есть (`_card_rating`: Кинопоиск, затем IMDb), а
    в синтетическом каталоге оценок нет как полей. Оба факта верны
    одновременно, и тест закрепляет связь между ними: пока источник молчит,
    разметки оценки не возникает, а как только она возникнет — рядом обязана
    стоять подпись источника.
    """

    @pytest.mark.parametrize("site_id", SITES)
    def test_no_rating_value_stands_without_a_source(self, sites, site_id):
        for path, html in _by_path(sites[site_id]).items():
            values = html.count('class="card__rating-value"')
            sources = html.count('class="card__rating-source"')
            assert values == sources, (
                f"{site_id} {path}: оценок {values}, подписей источника {sources}")

    def test_fixture_catalog_declares_no_ratings_at_all(self, catalog):
        """У синтетических записей оценок нет как полей, а не как пустых значений."""
        for title in catalog.titles:
            assert getattr(title, "kinopoisk_rating", None) is None
            assert getattr(title, "imdb_rating", None) is None
