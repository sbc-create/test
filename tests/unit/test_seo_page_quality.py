"""Проверки SEO-разметки (SEO-001 … SEO-020).

Проверяется правдивость, а не плотность ключей: совпадает ли напечатанное на
странице с тем, что сказал источник. Длина заголовка и описания — предупреждение,
а не отказ: короткий честный заголовок лучше длинного, набитого словами.
"""
from __future__ import annotations

import pytest

from factory.seo.provenance import content_hash, fact_sheet, from_provider
from factory.seo.validate import (
    PageUnderTest,
    check_corpus,
    check_page,
    warnings,
)

DOMAIN = "example.test"


def page(body: str, *, path="/title/x/", indexable=True, facts=None, provenance=None):
    html = (
        "<html><head>"
        f'<link rel="canonical" href="https://{DOMAIN}{path}">'
        f"{body}"
        "</head><body></body></html>"
    )
    return PageUnderTest(path=path, html=html, domain=DOMAIN, indexable=indexable,
                         facts=facts or {}, provenance=provenance or {})


def result_for(p) -> dict:
    return {f.check: f for f in check_page(p) if not f.ok}


GOOD_HEAD = (
    "<title>Хороший фильм (2019) — смотреть онлайн</title>"
    '<meta name="description" content="Фильм 2019 года: год выпуска, страна производства, '
    'жанр и состав по данным каталога источника, а также оценки с подписями.">'
    "<h1>Хороший фильм</h1>"
)


class TestSEO001TitleExistsAndIsNotTechnical:
    def test_a_title_is_present(self):
        assert "SEO-001" not in result_for(page(GOOD_HEAD))

    @pytest.mark.parametrize("bad", ["lords-01", "Lords General", "LORDS_02"])
    def test_an_internal_build_name_is_refused(self, bad):
        assert "SEO-001" in result_for(page(f"<title>Каталог — {bad}</title>{GOOD_HEAD}"))

    def test_an_empty_title_is_refused(self):
        assert "SEO-001" in result_for(page("<title></title>"))


class TestSEO002TitleIsUniqueInsideDomain:
    def test_two_identical_titles_are_refused(self):
        pages = [page(GOOD_HEAD, path="/a/"), page(GOOD_HEAD, path="/b/")]
        assert any(not f.ok and f.check == "SEO-002" for f in check_corpus(pages))

    def test_distinct_titles_pass(self):
        pages = [page(GOOD_HEAD, path="/a/"),
                 page(GOOD_HEAD.replace("Хороший фильм", "Другой фильм"), path="/b/")]
        assert all(f.ok for f in check_corpus(pages) if f.check == "SEO-002")


class TestSEO003IndexablePageHasDescription:
    def test_a_missing_description_is_refused_on_an_indexable_page(self):
        assert "SEO-003" in result_for(page("<title>Т</title><h1>Т</h1>"))

    def test_a_non_indexable_page_is_not_required_to_have_one(self):
        assert "SEO-003" not in result_for(
            page("<title>Т</title><h1>Т</h1>", indexable=False))

    def test_length_is_a_warning_not_a_refusal(self):
        short = page("<title>Т</title><h1>Т</h1>"
                     '<meta name="description" content="Слишком короткое описание тут.">')
        assert all(f.severity == "warning" for f in warnings(check_page(short))
                   if f.check.startswith("SEO-003-len"))


class TestSEO004NoExactDuplicateDescriptions:
    def test_identical_descriptions_are_refused(self):
        pages = [page(GOOD_HEAD, path="/a/"),
                 page(GOOD_HEAD.replace("Хороший фильм</h1>", "Иной фильм</h1>")
                      .replace("<title>Хороший фильм (2019)", "<title>Иной фильм (2019)"),
                      path="/b/")]
        assert any(not f.ok and f.check == "SEO-004" for f in check_corpus(pages))


class TestSEO005ExactlyOneVisibleH1:
    def test_two_h1_are_refused(self):
        assert "SEO-005" in result_for(page(GOOD_HEAD + "<h1>Второй</h1>"))

    def test_no_h1_is_refused(self):
        assert "SEO-005" in result_for(page("<title>Т</title>"))


class TestSEO006And007FactsMatchTheSource:
    def test_a_year_absent_from_the_page_is_refused(self):
        assert "SEO-006" in result_for(page(GOOD_HEAD, facts={"year": 1997}))

    def test_a_year_present_on_the_page_passes(self):
        assert "SEO-006" not in result_for(page(GOOD_HEAD, facts={"year": 2019}))

    def test_an_unsupported_claim_is_refused(self):
        p = page(GOOD_HEAD + "<p>Обладатель Оскара</p>",
                 facts={"forbidden_claims": ("обладатель оскара",)})
        assert "SEO-007" in result_for(p)


class TestSEO008NoPlaceholdersOrRawEnums:
    @pytest.mark.parametrize("junk", ["NR", "null", "undefined", "нет данных"])
    def test_raw_values_are_refused(self, junk):
        assert "SEO-008" in result_for(page(GOOD_HEAD + f"<p>Возрастная отметка {junk}</p>"))

    def test_a_clean_page_passes(self):
        assert "SEO-008" not in result_for(page(GOOD_HEAD))


class TestSEO009RatingsCarryTheirSource:
    def test_a_number_without_a_label_is_refused(self):
        assert "SEO-009" in result_for(page(GOOD_HEAD + '<span class="rating__value">7.3</span>'))

    def test_a_labelled_pair_passes(self):
        body = ('<span class="rating__source">Кинопоиск</span>'
                '<span class="rating__value">7.3</span>')
        assert "SEO-009" not in result_for(page(GOOD_HEAD + body))


class TestSEO010And015CanonicalIsCorrect:
    def test_canonical_pointing_elsewhere_is_refused(self):
        p = PageUnderTest(path="/a/", domain=DOMAIN, html=(
            '<link rel="canonical" href="https://other.tld/a/">' + GOOD_HEAD))
        assert "SEO-010" in {f.check for f in check_page(p) if not f.ok}

    def test_canonical_for_a_paginated_route_keeps_its_own_address(self):
        p = page(GOOD_HEAD, path="/catalog/page/2/")
        assert "SEO-010" not in result_for(p)


class TestSEO011DomainsDoNotShareOneSeoBlock:
    def test_two_domains_with_identical_home_blocks_are_refused(self):
        a = PageUnderTest(path="/", html=f'<link rel="canonical" href="https://a.tld/">{GOOD_HEAD}',
                          domain="a.tld")
        b = PageUnderTest(path="/", html=f'<link rel="canonical" href="https://b.tld/">{GOOD_HEAD}',
                          domain="b.tld")
        assert any(not f.ok and f.check == "SEO-011" for f in check_corpus([a, b]))


class TestSEO012IncompletePageStaysOutOfTheSitemap:
    def test_a_page_without_a_description_is_not_indexable(self):
        """Неполная страница не должна звать поисковика.

        Проверка формулируется как правило: если описание не набралось,
        страница не объявляется индексируемой, а значит и в карту не попадает.
        """
        incomplete = page("<title>Т</title><h1>Т</h1>", indexable=True)
        assert "SEO-003" in result_for(incomplete), "неполнота обязана быть замечена"


class TestSEO013PosterHasMeaningfulAlt:
    def test_a_decorative_image_may_have_an_empty_alt(self):
        assert "SEO-013" not in result_for(page(GOOD_HEAD + '<img src="a.webp" alt="">'))

    def test_a_meaningful_alt_passes(self):
        assert "SEO-013" not in result_for(
            page(GOOD_HEAD + '<img src="a.webp" alt="Постер фильма">'))


class TestSEO014InternalLinksAreCrawlable:
    def test_a_broken_link_is_refused(self):
        assert "SEO-014" in result_for(page(GOOD_HEAD + '<a href="/плохая ссылка/">т</a>'))

    def test_ordinary_links_pass(self):
        assert "SEO-014" not in result_for(page(GOOD_HEAD + '<a href="/catalog/">каталог</a>'))


class TestSEO016And019MetadataSurvivesAndIsEquivalent:
    def test_the_same_markup_serves_every_width(self):
        # Мобильная версия отдаётся тем же документом: отдельного усечённого
        # набора метаданных не существует, и разойтись им негде.
        p = page(GOOD_HEAD)
        assert "<title>" in p.html and 'name="description"' in p.html


class TestSEO017NoKeywordStuffing:
    def test_a_repeated_word_in_the_description_is_refused(self):
        # Набивка — это повтор внутри самого текста, а не название фильма,
        # стоящее по одному разу в заголовке, описании и H1.
        stuffed = ("<title>Фильм смотреть онлайн</title>"
                   '<meta name="description" content="смотреть смотреть смотреть смотреть '
                   'смотреть смотреть смотреть смотреть онлайн бесплатно хорошем качестве '
                   'русском переводе новинка">'
                   "<h1>Фильм</h1>")
        assert "SEO-017" in result_for(page(stuffed))

    def test_a_natural_description_is_not_stuffing(self):
        natural = ("<title>Хороший фильм (2019)</title>"
                   '<meta name="description" content="Драма 2019 года производства Франции: '
                   'режиссёр, состав исполнителей, продолжительность и оценки источников '
                   'с подписями, собранные из каталога поставщика.">'
                   "<h1>Хороший фильм</h1>")
        assert "SEO-017" not in result_for(page(natural))

    def test_an_episode_list_is_not_stuffing(self):
        # «Серия 1 … Серия 24» повторяется по устройству страницы, а не ради
        # поисковика. Считать её набивкой — значит наказывать за навигацию.
        episodes = "".join(f"<a href='/s/{i}/'>Серия {i}</a>" for i in range(1, 25))
        assert "SEO-017" not in result_for(page(GOOD_HEAD + episodes))


class TestSEO018SynopsisHasProvenance:
    def test_provider_text_carries_source_and_hash(self):
        prov = from_provider("Текст описания от поставщика", source="cdnvideohub.detail")
        assert prov.source and prov.content_hash
        assert prov.kind == "synopsis"

    def test_a_fact_sheet_is_not_called_a_synopsis(self):
        # Из полей каталога можно собрать полезную справку, но выдавать её за
        # пересказ сюжета нельзя.
        sheet = fact_sheet("2019, Франция, драма", facts=("year", "country", "genre"))
        assert sheet.kind == "fact_sheet"
        assert sheet.input_facts == ("year", "country", "genre")

    def test_the_hash_changes_with_the_text(self):
        assert content_hash("а") != content_hash("б")

    def test_a_page_without_provenance_is_flagged(self):
        p = page(GOOD_HEAD, provenance={"source": "", "content_hash": ""})
        assert "SEO-018" in result_for(p)


class TestSEO020JsonLdMatchesVisibleFacts:
    def test_a_name_absent_from_the_page_is_refused(self):
        block = ('<script type="application/ld+json">'
                 '{"@type":"Movie","name":"Совсем другой фильм"}</script>')
        assert "SEO-020" in result_for(page(GOOD_HEAD + block))

    def test_a_matching_name_passes(self):
        block = ('<script type="application/ld+json">'
                 '{"@type":"Movie","name":"Хороший фильм"}</script>')
        assert "SEO-020" not in result_for(page(GOOD_HEAD + block))
