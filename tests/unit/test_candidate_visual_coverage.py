"""Регресс для ремонта визуального кандидата PR #76 (2026-09-17).

Независимый checker насчитал 40.38% неизмеренных токенов и
`BLOCKED_EVIDENCE_INCOMPLETE` при overall 24.05/100 — контрактный прогон
подтверждён локально в `artifacts/evidence/templates/animedia-portal/
visual-candidate-repair/scoring-summary.json` (реальный
`factory/visual_scoring.compare()`, contract PR #81 не изменён). Причины были
на стороне разметки/CSS кандидата, а не окружения:

* карточки медиа измерялись пустыми — эвристика `a img` не находит
  `.card__poster` (постер этого шаблона рисуется без `<img>`, когда у
  фикстурной записи нет постера — а он нет ни у одной, политика
  `content_source.rights_confirmed: false`);
* на странице не было ни одного `<h3>` — заголовок карточки был обычной
  ссылкой без роли заголовка;
* шапка на 768px была на 60px выше соседних ширин — брейкпоинт, на котором
  прячется тумблер меню, не совпадал с брейкпоинтом, на котором меню встаёт в
  одну строку с лого.

Тесты здесь не гоняют браузер (это делает `tests/tools/
measure_candidate_tokens.js` — см. README рядом с evidence): они держат
разметку и CSS `factory/lords/render.py`/`theme.py`, от которых зависит
дальнейшее браузерное измерение, и падают, если кто-то их откатит.
"""

from __future__ import annotations

import re

from factory.lords import fixtures as fx
from factory.lords import preview as preview_mod
from factory.lords import render as render_mod
from factory.paths import PATHS

SITE_ID = "animedia-preview"

REQUIRED_ROLES = ("header", "primary-nav", "main-content", "footer")


def _site():
    package, _ = preview_mod._package(SITE_ID)
    catalog = fx.build_catalog()
    site = render_mod.render_site(package, catalog=catalog, environ={})
    return site, catalog


def _surfaces():
    """Пять поверхностей контракта visual-scoring/1.0.0 с их HTML на этой ветке."""
    site, catalog = _site()
    title = catalog.titles[0]
    collection = catalog.collections[0]
    return {
        "home": site.pages["/"].body,
        "catalog": site.pages["/catalog/"].body,
        "collection_hub": site.pages["/collections/"].body,
        "title": site.pages[title.path].body,
        "not_found": site.not_found.body,
    }


class TestStructuralMarkersCoverAllFifteenCells:
    """`structure_order` кандидата обязан быть технически готов на всех 5 поверхностях.

    Компонент даёт 0 баллов, пока эталон (PR #80) не содержит соответствующих
    токенов — но это не повод молчать про кандидата: `data-visual-role`
    обязаны быть на месте независимо от вердикта контракта.
    """

    def test_every_surface_has_the_four_universal_roles(self):
        surfaces = _surfaces()
        for surface, html in surfaces.items():
            for role in REQUIRED_ROLES:
                assert f'data-visual-role="{role}"' in html, (
                    f"{surface}: нет data-visual-role=\"{role}\" — structure_order "
                    "не сможет заявить required_block присутствующим"
                )

    def test_card_grid_marker_is_unambiguous_where_cards_exist(self):
        surfaces = _surfaces()
        for surface in ("home", "catalog", "collection_hub", "title"):
            assert 'data-visual-role="card-grid"' in surfaces[surface], (
                f"{surface}: карточная лента есть, а data-visual-role=\"card-grid\" нет — "
                "измеритель не сможет однозначно выбрать основной grid"
            )

    def test_not_found_does_not_fabricate_blocks_it_does_not_have(self):
        """Пустой пробел — честный пробел, а не место для невидимой карточки."""
        html = _surfaces()["not_found"]
        assert 'data-visual-role="card-grid"' not in html
        assert re.search(r"<h2[ >]", html) is None
        assert re.search(r"<h3[ >]", html) is None
        assert 'class="card"' not in html
        assert 'data-visual-role="not-found-message"' in html


class TestCardTitlesAreRealHeadingsWithoutBreakingNavigation:
    """`type_h3_*` было `unavailable` на каждой ячейке: страница не содержала `h3`."""

    def test_card_titles_are_wrapped_in_h3(self):
        surfaces = _surfaces()
        for surface in ("home", "catalog", "collection_hub", "title"):
            assert re.search(r'<h3><a class="card__title"', surfaces[surface]), (
                f"{surface}: заголовок карточки не обёрнут в <h3> — "
                "type_h3_font_size/font_weight снова будет unavailable"
            )

    def test_card_title_link_keeps_its_own_href(self):
        """Клик и `.getAttribute('href')` на `.card__title` — договор с E2E-спеками.

        `<h3>` вокруг ссылки — структурный якорь для измерителя, а не замена
        ссылки: `.card__title` обязан остаться самим `<a href>`, иначе
        `tests/e2e-lords/*.spec.js` (`page.locator('.card__title').first()
        .getAttribute('href')`/`.click()`) перестанут находить переход.
        """
        html = _surfaces()["home"]
        match = re.search(r'<h3><a class="card__title" href="([^"]+)">', html)
        assert match, "class=\"card__title\" должен остаться на <a href=...>, не на <h3>"
        assert match.group(1).startswith("/"), "href карточки должен вести на реальную страницу"

    def test_h3_wrapper_does_not_add_visible_spacing_or_size(self):
        """`h3{{font:inherit}}`/`margin:0` — иначе кегль/отступ браузерного h3 добавятся сверху.

        Правило проверяется по тексту исходника темы, а не через верстальный
        движок: воспроизводить весь контекст профиля ради одной CSS-строки
        было бы дороже и не надёжнее прямой проверки её присутствия.
        """
        source = (PATHS.root / "factory" / "lords" / "theme.py").read_text(encoding="utf-8")
        assert re.search(r"\.card__body h3\s*\{\{\s*margin:\s*0;\s*font:\s*inherit;", source), (
            "сброс margin/font для <h3> внутри .card__body пропал — "
            "браузерный кегль h3 (1.17em, bold) снова добавится над .card__title"
        )


class TestHeaderBreakpointStaysOnePassage:
    """768px давал шапку в 150px против 90/61 на соседних ширинах.

    Причина: тумблер меню прятался на 640px, а меню встраивалось в строку
    шапки (`flex: 1 1 auto`) только на 1024px — в промежутке `.site-nav`
    получал `width: 100%` и падал на отдельную строку, а сама она заворачивала
    четыре пункта в две. Правило проверяется по тексту исходника: только
    браузер посчитал бы реальную высоту, а этот тест обязан падать без него.
    """

    def _theme_source(self) -> str:
        return (PATHS.root / "factory" / "lords" / "theme.py").read_text(encoding="utf-8")

    def _media_block(self, source: str, min_width: str) -> str:
        marker = f"@media (min-width: {min_width})"
        start = source.index(marker)
        depth = 0
        i = source.index("{{", start)
        body_start = i
        depth = 1
        i += 2
        while depth > 0:
            if source[i] == "{":
                depth += 1
            elif source[i] == "}":
                depth -= 1
            i += 1
        return source[body_start:i]

    def test_nav_toggle_hides_in_the_640_block(self):
        block = self._media_block(self._theme_source(), "640px")
        assert ".nav-toggle" in block and "display: none" in block

    def test_nav_becomes_a_flex_item_in_the_same_640_block(self):
        """Меню обязано перейти в инлайн-раскладку там же, где прячется тумблер."""
        block = self._media_block(self._theme_source(), "640px")
        assert re.search(r"\.site-nav\s*\{\{[^}]*flex:\s*1\s+1\s+auto", block), (
            "нет .site-nav{{flex:1 1 auto}} в блоке 640px — меню снова получит "
            "width:100% и упадёт на отдельную строку между 640 и 1024px"
        )

    def test_desktop_block_no_longer_duplicates_the_nav_inline_rule(self):
        source = self._theme_source()
        desktop = self._media_block(source, "1024px")
        assert "width: auto; flex: 1 1 auto" not in desktop


class TestMeasurementToolNeverCopiesReferenceValues:
    """ЗАПРЕТЫ ПРОТИВ ПОДГОНКИ: инструмент кандидата не должен знать числа эталона."""

    #: Значения эталона amd-online (PR #80, `VISUAL_TOKENS.yaml`), которых в
    #: инструменте кандидата не должно быть ни при каких обстоятельствах —
    #: это не совпадения, а прямые цитаты чужого замера.
    FORBIDDEN_LITERALS = (
        "17934",  # page_height, home@390 у эталона
        "0f1419", "161d24", "e8edf2",  # прежняя тёмная палитра, которую путали с эталоном
    )

    def test_tool_source_has_no_reference_literal(self):
        source = (PATHS.root / "tests" / "tools" / "measure_candidate_tokens.js").read_text(
            encoding="utf-8")
        for literal in self.FORBIDDEN_LITERALS:
            assert literal not in source, (
                f"инструмент кандидата содержит литерал {literal!r} эталона — "
                "подгонка значения вместо измерения"
            )
