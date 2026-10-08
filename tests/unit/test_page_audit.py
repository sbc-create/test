"""REQ-SEO-REGULAR: аудит страницы — измерения и находки, без оценок."""
from __future__ import annotations

from seo_operator import page_audit

LINKS = "".join(f'<a href="/title/t{i}/">t{i}</a>' for i in range(6))


def test_thin_meta_placeholder_and_foreign_canonical_are_found():
    html = ('<html><head><title>Противостояние святого — смотреть онлайн — Animedia</title>'
            '<meta name="description" content="Противостояние святого: Аниме 2023">'
            '<link rel="canonical" href="https://animedia.space/title/x/"></head>'
            f'<body><main><h1>Противостояние святого</h1><p>Описание пока не передано источником</p>{LINKS}</main></body></html>')
    codes = [f["code"] for f in page_audit.audit(html, "https://animedia.icu/title/x/")["findings"]]
    assert "META_THIN" in codes
    assert "PLACEHOLDER_TEXT" in codes
    assert "CANONICAL_OTHER" in codes


def test_self_canonical_with_good_meta_is_clean():
    html = ('<html><head><title>Волки — смотреть онлайн — Lordfilm</title>'
            '<meta name="description" content="В самом сердце андеграундной музыкальной сцены отношения молодой женщины и музыканта проходят испытание.">'
            '<link rel="canonical" href="https://lordfilm47.space/title/volki-2/"></head>'
            f'<body><main><h1>Волки</h1><p>Описание: {"слово " * 130}</p>{LINKS}</main></body></html>')
    assert page_audit.audit(html, "https://lordfilm47.space/title/volki-2/")["findings"] == []


def test_streamed_main_is_not_read_as_empty():
    """Yummy: <main> содержит только <template>, текст — ниже в том же HTML."""
    html = ('<html><head><title>T</title></head><body><main><template id="P:2"></template></main>'
            f'<div hidden id="S:3"><h1>Ледяная стена 2</h1>{"слово " * 200}{LINKS}</div></body></html>')
    out = page_audit.audit(html, "https://yummyani.org/anime/ledyanaya-stena-2")
    assert out["main_streamed"] is True
    assert out["words_main"] > 150


def test_same_title_on_two_urls_is_a_duplicate():
    a = {"url": "https://a.example/x", "title": "Фильмы — Zona"}
    b = {"url": "https://a.example/y", "title": "Фильмы — Zona"}
    assert page_audit.duplicate_titles([a, b])[0]["urls"] == ["https://a.example/x", "https://a.example/y"]
