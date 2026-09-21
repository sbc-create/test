"""B14 — footer and system empty / error / 404 states.

Passport: ANIMEDIA_BLOCK_SPEC_V1/B14.
- required_fields: [brand_or_sections]
- optional: contact_email, telegram_url, privacy_url, terms_url — hidden when
  absent, never invented
- desktop cols 4, height 220–300 px; tablet cols 2; mobile accordion_or_stack
- seo_contract: mutates_indexability false; http_404_policy_owned_by seo_core

The footer used to print `source=…`, `runtime=…`, `build=…` in a title attribute
and a shortened commit in plain sight — on both live domains. Provenance belongs
to the response headers and the release manifest, where acceptance already reads
it; in the markup it is an internal marker handed to anyone crawling the site.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tests.unit.test_animedia_visual_finalization import _load, _вид  # noqa: E402

EV = ROOT / "artifacts/evidence/animedia-blockwise-parity-03-2026-09-20"
CONTRACT_SHA = (EV / "00-contract" / "CONTRACT_SHA256.txt").read_text(
    encoding="utf-8").strip()

#: Каждая страница обязана нести подвал — он часть каркаса, а не главной.
СТРАНИЦЫ = ("home", "catalog", "search", "collections", "title", "episode", "404")


@pytest.fixture
def fe(tmp_path):
    return _load(tmp_path, version="1.2.4")


def _страницы(mod, catalog, details) -> dict[str, str]:
    вид = _вид(mod, catalog, details)
    запись = catalog["items"][0]
    деталь = details["details"].get(запись["slug"], {})
    выдача = {
        "home": вид.главная(),
        "catalog": вид.список("/catalog", {}),
        "search": вид.поиск({"q": ["Альфа"]}),
        "collections": вид.страница_коллекций({}),
        "title": вид.тайтл(запись, деталь),
        "404": вид.не_найдено("/nope/"),
    }
    try:
        выдача["episode"] = вид.серия(запись, деталь, 1, 1)
    except Exception:  # noqa: BLE001 — маршрут серии проверяется в B09
        pass
    return выдача


def test_contract_digest_unchanged() -> None:
    assert CONTRACT_SHA == (
        "5f2112e25ef974333c388bad405abfae3c3d460a713b028afa3c0e549b8eaeb3")


# --- no internal markers ----------------------------------------------

def test_footer_publishes_no_build_version_or_commit(fe):
    mod, catalog, details = fe
    подвал = _вид(mod, catalog, details).подвал()
    assert "zvb" not in подвал
    for утечка in ("source=", "runtime=", "build=", mod.СБОРКА, mod.ВЕРСИЯ):
        assert утечка not in подвал, утечка
    # No bare 7+ hex commit anywhere in the footer.
    assert not re.search(r"\b[0-9a-f]{7,40}\b", подвал)


def test_no_page_leaks_build_markers_in_its_footer(fe):
    mod, catalog, details = fe
    for имя, разметка in _страницы(mod, catalog, details).items():
        i = разметка.rfind("<footer")
        assert i >= 0, f"{имя}: страница без подвала"
        подвал = разметка[i:]
        for утечка in ("source=", "runtime=", "build=", mod.СБОРКА):
            assert утечка not in подвал, f"{имя}: {утечка}"


def test_animedia_stylesheet_has_no_dead_version_badge_rule(fe):
    mod, _, _ = fe
    assert ".zvb{" not in mod.АНИМЕДИА_СТИЛЬ


# --- required and optional fields -------------------------------------

def test_footer_has_brand_and_sections(fe):
    mod, catalog, details = fe
    подвал = _вид(mod, catalog, details).подвал()
    assert 'data-b14="footer"' in подвал
    assert "Animedia" in подвал
    for маршрут in ("/", "/catalog/", "/new/", "/collections/"):
        assert f'href="{маршрут}"' in подвал, маршрут
    assert "© " in подвал


def test_missing_owner_values_are_declared_not_invented(fe, monkeypatch, tmp_path):
    mod, catalog, details = fe
    отсутствует = tmp_path / "no-owner.json"
    monkeypatch.setattr(mod, "АНИМЕДИА_OWNER_CONFIG_PATH", str(отсутствует))
    подвал = _вид(mod, catalog, details).подвал()
    assert 'data-b14-owner-gap="1"' in подвал
    assert 'data-b14-cols="3"' in подвал
    assert "Контакты и правовое" not in подвал
    assert "mailto:" not in подвал
    assert "t.me" not in подвал
    assert "Конфиденциальность" not in подвал
    assert "Условия" not in подвал


def test_real_owner_values_fill_the_fourth_column(fe, monkeypatch, tmp_path):
    mod, catalog, details = fe
    конфиг = tmp_path / "owner.json"
    конфиг.write_text(json.dumps({
        "contact_email": "owner@example.org",
        "telegram_url": "https://t.me/example",
        "privacy_url": "/privacy/",
        "terms_url": "https://example.org/terms/",
    }), encoding="utf-8")
    monkeypatch.setattr(mod, "АНИМЕДИА_OWNER_CONFIG_PATH", str(конфиг))
    подвал = _вид(mod, catalog, details).подвал()
    assert 'data-b14-owner-gap="1"' not in подвал
    assert 'data-b14-cols="4"' in подвал
    assert "mailto:owner@example.org" in подвал
    assert "https://t.me/example" in подвал
    assert "/privacy/" in подвал and "https://example.org/terms/" in подвал


def test_malformed_owner_values_are_refused_not_shown(fe, monkeypatch, tmp_path):
    """A broken value is not a value: it is dropped, not rendered as-is."""
    mod, catalog, details = fe
    конфиг = tmp_path / "owner-bad.json"
    конфиг.write_text(json.dumps({
        "contact_email": "не почта",
        "telegram_url": "http://t.me/insecure",
        "privacy_url": "javascript:alert(1)",
        "terms_url": "ftp://example.org/terms",
    }), encoding="utf-8")
    monkeypatch.setattr(mod, "АНИМЕДИА_OWNER_CONFIG_PATH", str(конфиг))
    подвал = _вид(mod, catalog, details).подвал()
    assert 'data-b14-owner-gap="1"' in подвал
    for мусор in ("не почта", "http://t.me/insecure", "javascript:", "ftp://"):
        assert мусор not in подвал, мусор


# --- geometry ----------------------------------------------------------

def test_footer_columns_are_four_two_one(fe):
    mod, _, _ = fe
    css = mod.АНИМЕДИА_СТИЛЬ
    assert ".zft__cols{display:grid" in css
    assert "@media(min-width:768px){.zft__cols{grid-template-columns:repeat(2,minmax(0,1fr))}}" in css
    assert "@media(min-width:1100px){.zft__cols{grid-template-columns:repeat(4,minmax(0,1fr))}}" in css
    assert "@media(max-width:479px){.zft__cols{grid-template-columns:1fr}}" in css


def test_footer_links_are_reachable_touch_targets(fe):
    mod, _, _ = fe
    css = mod.АНИМЕДИА_СТИЛЬ
    правило = css[css.find(".zft__col a{"): css.find(".zft__col a{") + 220]
    assert "min-height:32px" in правило or "min-height:44px" in правило
    assert "display:inline-flex" in правило


def test_footer_about_text_is_clamped_not_overflowing(fe):
    mod, _, _ = fe
    css = mod.АНИМЕДИА_СТИЛЬ
    правило = css[css.find(".zft__about{"): css.find(".zft__about{") + 260]
    assert "-webkit-line-clamp" in правило
    assert "overflow:hidden" in правило


def test_empty_optional_blocks_collapse(fe):
    mod, _, _ = fe
    assert ".zft__contact:empty,.zft__legal:empty{display:none}" in (
        mod.АНИМЕДИА_СТИЛЬ.replace("\n", ""))


# --- system states -----------------------------------------------------

def test_404_page_is_real_and_carries_the_shell(fe):
    mod, catalog, details = fe
    вид = _вид(mod, catalog, details)
    нф = вид.не_найдено("/definitely-absent/")
    assert "<h1" in нф and "Страница не найдена" in нф
    assert "<footer" in нф
    # A 404 must not claim a canonical of its own.
    assert 'rel="canonical"' not in нф
    assert "noindex" in нф or 'name="robots"' not in нф


def test_404_echoes_the_path_escaped(fe):
    mod, catalog, details = fe
    вид = _вид(mod, catalog, details)
    нф = вид.не_найдено('/<script>alert(1)</script>/')
    assert "<script>alert(1)</script>" not in нф
    assert "&lt;script&gt;" in нф


def test_404_offers_a_real_route_not_an_invented_one(fe):
    """Ссылки самого блока 404 — только настоящие маршруты реестра.

    Проверяется тело блока, а не каркас: в каркасе есть ещё и ссылки на
    ресурсы вроде `/favicon.svg`, и это не маршруты.
    """
    mod, catalog, details = fe
    нф = _вид(mod, catalog, details).не_найдено("/nope/")
    начало = нф.find('class="znf"')
    assert начало >= 0, "блок 404 не найден в разметке"
    блок = нф[начало: нф.find("</div>", начало) + 6]
    ссылки = set(re.findall(r'href="(/[^"#?]*)"', блок))
    известные = {"/", "/catalog/", "/new/", "/collections/", "/search/",
                 "/schedule/"}
    внешние = {с for с in ссылки
               if not (с in известные or с.startswith("/catalog/")
                       or с.startswith("/title/") or с.startswith("/collection/"))}
    assert ссылки, "блок 404 не предлагает ни одного выхода"
    assert внешние == set(), внешние


def test_empty_states_never_show_zero_as_a_rating(fe):
    mod, catalog, details = fe
    for имя, разметка in _страницы(mod, catalog, details).items():
        assert not re.search(r'data-rating="0"', разметка), имя
        assert "★ 0" not in разметка, имя


def test_footer_does_not_change_indexability(fe):
    mod, catalog, details = fe
    for имя, разметка in _страницы(mod, catalog, details).items():
        assert "index, follow" not in разметка, имя
