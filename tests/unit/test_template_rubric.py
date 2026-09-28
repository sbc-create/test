"""Проверки самой рубрики: критерий обязан уметь падать.

Рубрика стала основанием для утверждения «страница набирает 10 из 10», и это
делает её саму предметом проверки. Критерий, который не падает ни на чём, даёт
не оценку, а согласие: он всегда возвращает PASS и создаёт видимость контроля.

Два таких случая уже случились и стоят здесь тестами:

* критерий оценок искал атрибут `data-rating`, которого рендерер не выдаёт
  вовсе, — и потому не отличал оценку без источника от отсутствия оценок;
* критерий плеера засчитывал одну лишь фразу «недоступно» и не замечал утечки
  служебного кода в разметку.

Поэтому у каждого критерия здесь по паре: документ, на котором он проходит, и
документ, на котором он обязан упасть.
"""

from __future__ import annotations

from factory.templates import rubric
from factory.templates.rubric import (
    FAIL,
    NOT_APPLICABLE,
    PASS,
    Expectation,
    score_page,
)

#: Минимальный документ, проходящий всё, что не относится к предмету теста.
BASE = """<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Заголовок</title>
<meta name="description" content="{description}">
<meta name="robots" content="{robots}">
<meta name="lords-canonical-state" content="self">
<meta name="lords-data-source" content="fixture/test">
<script type="application/ld+json">{{}}</script>
<link rel="stylesheet" href="/assets/site.css"></head>
<body><a class="visually-hidden" href="#content">К содержимому</a>
<header class="site-header"><button class="nav-toggle" aria-expanded="false"
aria-controls="site-nav">Меню</button><nav id="site-nav" aria-label="Навигация">
<ul><li><a href="/">Главная</a></li></ul></nav></header>
<main id="content"><h1>Заголовок страницы</h1>{body}</main>
<footer class="site-footer"><p>подвал</p></footer></body></html>"""

DESCRIPTION = "Описание раздела длиной более сорока символов для критерия документа."


def document(body: str = "", *, robots: str = "noindex, nofollow",
            description: str = DESCRIPTION) -> str:
    return BASE.format(body=body, robots=robots, description=description)


CARD = ('<article class="card" data-slug="s"><a class="card__poster" href="/t/">'
        '<img src="/p.svg" alt="" loading="lazy" width="400" height="600"></a>'
        '<div class="card__body"><a class="card__title" href="/t/">Название</a>'
        '</div></article>')


def check(html: str, criterion: str, expectation: Expectation):
    page = score_page(html, expectation)
    found = next(c for c in page.checks if c.criterion == criterion)
    return found


PLAIN = Expectation("plain", "index.html", cards=False)


class TestValidity:
    def test_unique_identifiers_pass(self):
        assert check(document('<div id="a"></div>'), "validity", PLAIN).status == PASS

    def test_repeated_identifier_fails(self):
        html = document('<div id="grid"></div><div id="grid"></div>')
        found = check(html, "validity", PLAIN)
        assert found.status == FAIL and "grid" in found.detail


class TestDocument:
    def test_two_h1_fail(self):
        found = check(document("<h1>Второй</h1>"), "document", PLAIN)
        assert found.status == FAIL and "h1" in found.detail

    def test_indexable_page_without_description_fails(self):
        html = document(robots="index, follow", description="")
        found = check(html, "document", PLAIN)
        assert found.status == FAIL and "description" in found.detail

    def test_navigation_page_without_description_passes(self):
        """У раздела с `noindex` собственного текста нет намеренно."""
        html = document(robots="noindex, nofollow", description="")
        assert check(html, "document", PLAIN).status == PASS


class TestAccessibility:
    def test_control_without_a_name_fails(self):
        html = document('<select id="f-genre"><option>а</option></select>')
        found = check(html, "accessibility", PLAIN)
        assert found.status == FAIL and "подписи" in found.detail

    def test_control_with_aria_label_passes(self):
        html = document('<select id="f" aria-label="Жанр"><option>а</option></select>')
        assert check(html, "accessibility", PLAIN).status == PASS


class TestRatings:
    def test_rating_without_a_source_fails(self):
        """Ровно тот случай, который прежняя версия критерия пропускала."""
        html = document('<span class="card__rating-value">8.1</span>')
        found = check(html, "ratings", PLAIN)
        assert found.status == FAIL and "источник" in found.detail

    def test_rating_with_a_source_passes(self):
        html = document('<span class="card__rating-source">IMDb</span>'
                        '<span class="card__rating-value">8.1</span>')
        assert check(html, "ratings", PLAIN).status == PASS

    def test_absence_of_ratings_is_not_a_defect(self):
        assert check(document(), "ratings", PLAIN).status == PASS


class TestPlayerShell:
    PLAYER = Expectation("title", "t.html", player=True, cards=False)

    def test_reserved_frame_with_explanation_passes(self):
        html = document('<div class="player__frame"><p>временно недоступно</p></div>')
        assert check(html, "player_shell", self.PLAYER).status == PASS

    def test_leaked_service_code_fails(self):
        """Утечка кода — дефект, а не признак диагностируемости (D128)."""
        html = document('<div class="player__frame" '
                        'data-player-status="BLOCKED_INPUT_CDNVIDEOHUB_CREDENTIALS">'
                        "<p>временно недоступно</p></div>")
        found = check(html, "player_shell", self.PLAYER)
        assert found.status == FAIL and "утёк" in found.detail

    def test_page_without_a_player_is_not_penalised(self):
        assert check(document(), "player_shell", PLAIN).status == NOT_APPLICABLE


class TestUpdates:
    def test_listing_page_counts_its_own_cards(self):
        expectation = Expectation("new", "new.html", updates=True, updates_via="listing")
        assert check(document(CARD), "updates", expectation).status == PASS

    def test_empty_listing_fails(self):
        expectation = Expectation("new", "new.html", updates=True, updates_via="listing")
        assert check(document(), "updates", expectation).status == FAIL

    def test_home_requires_a_shelf_block(self):
        expectation = Expectation("home", "index.html", updates=True)
        assert check(document(CARD), "updates", expectation).status == FAIL
        shelf = f'<section data-block="latest_grid">{CARD}</section>'
        assert check(document(shelf), "updates", expectation).status == PASS


class TestScoreArithmetic:
    def test_not_applicable_does_not_inflate_the_score(self):
        """Снятый критерий не даёт балла и не входит в знаменатель."""
        page = score_page(document(), PLAIN)
        applicable = [c for c in page.checks if c.status != NOT_APPLICABLE]
        assert len(page.applicable) == len(applicable)
        assert page.score == round(10.0 * page.passed / len(applicable), 1)

    def test_unmeasured_is_not_counted_as_success(self):
        page = score_page(document(), PLAIN)
        page.checks.append(rubric.Check("выдуманный", rubric.UNMEASURED, "не запускалась"))
        assert page.score < 10.0, "непроверенный критерий не может давать балл"

    def test_page_of_only_not_applicable_checks_does_not_apply(self):
        page = score_page(document(), PLAIN)
        page.checks = [rubric.Check(c.criterion, NOT_APPLICABLE, "нет") for c in page.checks]
        assert not page.applies


# --------------------------------------------------------------------------
# Обобщение критериев с рендерера Lords на любой theme pack
#
# Четыре критерия проверяли не свойство документа, а служебные метки и точные
# слова рендерера Lords: `lords-canonical-state`, `lords-data-source`, класс
# `nav-toggle` и подстроки «недоступ»/«не подключ». На втором theme pack они
# объявляли отказом работающую витрину.
#
# Послабление опасно ровно тем, что критерий может перестать ловить настоящий
# дефект. Поэтому каждая пара ниже проверяет обе стороны: обобщённую форму
# критерий обязан принять, а испорченный документ — по-прежнему отвергнуть.
class TestКритерииПроверяютСвойствоАНеМеткуРендерера:
    def _проверка(self, html, expectation, имя, css=""):
        from factory.templates.rubric import score_page
        page = score_page(html, expectation, css=css)
        return next(c for c in page.checks if c.criterion == имя)

    def test_canonical_принимается_вместо_метки_lords(self):
        from factory.templates.rubric import Expectation, PASS
        html = ('<html lang="ru"><head><meta name="robots" content="index,follow">'
                '<link rel="canonical" href="https://example.test/"></head>'
                '<body><h1>Х</h1></body></html>')
        check = self._проверка(html, Expectation("home", "index.html"), "routes")
        assert check.status == PASS, check.detail

    def test_страница_без_объявления_места_по_прежнему_отвергается(self):
        from factory.templates.rubric import Expectation, FAIL
        html = ('<html lang="ru"><head><meta name="robots" content="index,follow">'
                '</head><body><h1>Х</h1></body></html>')
        check = self._проверка(html, Expectation("home", "index.html"), "routes")
        assert check.status == FAIL, "индексируемая страница без canonical обязана падать"

    def test_noindex_считается_объявлением_места(self):
        from factory.templates.rubric import Expectation, PASS
        html = ('<html lang="ru"><head><meta name="robots" content="noindex,follow">'
                '</head><body><h1>Х</h1></body></html>')
        check = self._проверка(html, Expectation("search", "search/index.html"), "routes")
        assert check.status == PASS, check.detail

    def test_общая_метка_источника_принимается(self):
        from factory.templates.rubric import Expectation, PASS
        html = ('<html lang="ru"><head><meta name="data-source" content="package:a@b">'
                '</head><body><h1>Х</h1></body></html>')
        check = self._проверка(html, Expectation("home", "index.html", cards=False),
                               "content_honesty")
        assert check.status == PASS, check.detail

    def test_документ_без_источника_по_прежнему_отвергается(self):
        from factory.templates.rubric import Expectation, FAIL
        html = '<html lang="ru"><head></head><body><h1>Х</h1></body></html>'
        check = self._проверка(html, Expectation("home", "index.html", cards=False),
                               "content_honesty")
        assert check.status == FAIL

    def test_меню_без_переключателя_не_считается_дефектом(self):
        from factory.templates.rubric import Expectation, PASS
        html = ('<html lang="ru"><head><meta name="viewport" content="width=device-width">'
                '</head><body><nav><a href="/">Главная</a></nav></body></html>')
        check = self._проверка(html, Expectation("home", "index.html"), "adaptivity")
        assert check.status == PASS, check.detail

    def test_переключатель_без_aria_expanded_по_прежнему_отвергается(self):
        from factory.templates.rubric import Expectation, FAIL
        html = ('<html lang="ru"><head><meta name="viewport" content="width=device-width">'
                '</head><body><button class="nav-toggle">Меню</button></body></html>')
        check = self._проверка(html, Expectation("home", "index.html"), "adaptivity")
        assert check.status == FAIL

    def test_фиксированная_ширина_по_прежнему_отвергается(self):
        from factory.templates.rubric import Expectation, FAIL
        html = ('<html lang="ru"><head><meta name="viewport" content="width=device-width">'
                '</head><body><div style="width: 1200px">Х</div></body></html>')
        check = self._проверка(html, Expectation("home", "index.html"), "adaptivity")
        assert check.status == FAIL

    def test_заглушка_плеера_объяснённая_своими_словами_принимается(self):
        from factory.templates.rubric import Expectation, PASS
        html = ('<html lang="ru"><head></head><body>'
                '<div class="player-frame ratio-16-9">'
                '<div class="player-mock" role="region" aria-label="Видеоплеер (заглушка)">'
                '<p>Плеер подключается после передачи контракта поставщика; '
                'контейнер держит размеры, чтобы раскладка не сдвинулась.</p>'
                '</div></div></body></html>')
        css = ".ratio-16-9 { aspect-ratio: 16 / 9; }"
        check = self._проверка(html, Expectation("title", "t/index.html", player=True,
                                                 cards=False), "player_shell", css=css)
        assert check.status == PASS, check.detail

    def test_молчащий_кадр_плеера_по_прежнему_отвергается(self):
        from factory.templates.rubric import Expectation, FAIL
        html = ('<html lang="ru"><head></head><body>'
                '<div class="player-frame ratio-16-9"></div></body></html>')
        css = ".ratio-16-9 { aspect-ratio: 16 / 9; }"
        check = self._проверка(html, Expectation("title", "t/index.html", player=True,
                                                 cards=False), "player_shell", css=css)
        assert check.status == FAIL, "кадр без подписи и объяснения обязан падать"

    def test_утечка_служебного_кода_в_разметку_по_прежнему_отвергается(self):
        from factory.templates.rubric import Expectation, FAIL
        html = ('<html lang="ru"><head></head><body>'
                '<div class="player-frame ratio-16-9" role="region" aria-label="Плеер">'
                '<p>Плеер недоступен: BLOCKED_INPUT по контракту поставщика видео, '
                'и это состояние объяснено читателю подробно.</p></div></body></html>')
        css = ".ratio-16-9 { aspect-ratio: 16 / 9; }"
        check = self._проверка(html, Expectation("title", "t/index.html", player=True,
                                                 cards=False), "player_shell", css=css)
        assert check.status == FAIL

    def test_резерв_кадра_во_внешних_стилях_виден_критерию(self):
        """Резерв кадра живёт в правиле класса, а не в разметке.

        Без чтения подключённых таблиц стилей критерий объявлял отсутствующим
        то, что есть, — и требовал бы вписать `style="aspect-ratio"` в разметку
        ради проверки, а не ради читателя.
        """
        from factory.templates.rubric import Expectation, PASS, FAIL
        html = ('<html lang="ru"><head><link rel="stylesheet" href="/assets/build.css">'
                '</head><body><div class="player-frame ratio-16-9" role="region" '
                'aria-label="Плеер"><p>Плеер подключается после передачи контракта '
                'поставщика, контейнер держит размеры кадра.</p></div></body></html>')
        exp = Expectation("title", "t/index.html", player=True, cards=False)
        без_стилей = self._проверка(html, exp, "player_shell")
        со_стилями = self._проверка(html, exp, "player_shell",
                                    css=".ratio-16-9 { aspect-ratio: 16 / 9; }")
        assert без_стилей.status == FAIL, "без стилей резерв подтвердить нечем"
        assert со_стилями.status == PASS, со_стилями.detail

    def test_служебная_страница_не_обязана_описывать_себя_машинам(self):
        from factory.templates.rubric import Expectation, NOT_APPLICABLE, FAIL
        html = '<html lang="ru"><head></head><body><h1>Не найдено</h1></body></html>'
        служебная = self._проверка(
            html, Expectation("not_found", "404/index.html", cards=False,
                              structured_data=False), "structured_data")
        обычная = self._проверка(html, Expectation("home", "index.html"), "structured_data")
        assert служебная.status == NOT_APPLICABLE
        assert обычная.status == FAIL, "обычная страница обязана нести JSON-LD"
