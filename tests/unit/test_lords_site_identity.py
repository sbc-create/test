"""Имя сайта, иконка и честная причина пустой карты.

Три вещи, по которым посетитель судит, что сайт закончен: как он называется во
вкладке, есть ли у вкладки иконка и не отдаёт ли корень сайта 404 на файлы,
которые браузер запрашивает сам.
"""
from __future__ import annotations

import json

import pytest

from factory.lords import icons, render


class TestBrandIsNotAnInternalIdentifier:
    def _package(self, **over):
        pkg = {"site_id": "lords-01", "domain": "example.test",
               "brand": {"name": "lords-01"}}
        pkg.update(over)
        return pkg

    def test_the_profile_label_does_not_become_the_site_name(self):
        # «Lords General» — название шаблона сборки, а не сайта.
        name = render._brand_name(self._package(), {"label": "Lords General"}, "example.test")
        assert name == "example.test"
        assert "Lords" not in name

    @pytest.mark.parametrize("technical", ["lords-01", "lords_02", "LORDS-3"])
    def test_technical_identifiers_are_not_names(self, technical):
        name = render._brand_name(
            self._package(brand={"name": technical}), {"label": "Lords New"}, "example.test")
        assert name == "example.test"

    def test_a_name_given_by_the_owner_wins(self):
        # Владелец назвал сайт — домен больше не нужен.
        name = render._brand_name(
            self._package(brand={"name": "Кинозал"}), {"label": "Lords General"}, "example.test")
        assert name == "Кинозал"

    def test_without_a_domain_it_falls_back_rather_than_inventing_one(self):
        name = render._brand_name({"site_id": "lords-01"}, {"label": "Lords General"}, "")
        assert name == "Lords General"


class TestIconsAreRealFiles:
    def test_the_ico_is_a_valid_icon_container(self):
        blob = icons.favicon_ico("#79c142", "#0d0d0d")
        assert blob[:4] == b"\x00\x00\x01\x00"  # reserved=0, type=1 (icon), count=1
        assert b"\x89PNG\r\n\x1a\n" in blob

    def test_the_png_is_a_valid_png_of_the_declared_size(self):
        blob = icons.favicon_png("#79c142", "#0d0d0d")
        assert blob[:8] == b"\x89PNG\r\n\x1a\n"
        width = int.from_bytes(blob[16:20], "big")
        height = int.from_bytes(blob[20:24], "big")
        assert (width, height) == (icons.SIZE, icons.SIZE)

    def test_the_icon_uses_the_theme_accent_and_not_a_grey_placeholder(self):
        svg = icons.favicon_svg("#79c142", "#0d0d0d")
        assert "#79c142" in svg
        assert "888" not in svg

    def test_a_shorthand_colour_is_accepted(self):
        assert icons._rgb("#abc") == (0xAA, 0xBB, 0xCC)

    @pytest.mark.parametrize("bad", ["", "#12", "не цвет", "#1234567"])
    def test_a_non_colour_is_rejected_rather_than_guessed(self, bad):
        with pytest.raises(ValueError):
            icons._rgb(bad)


class TestIconPagesAreServed:
    def _ctx(self, brand="example.test"):
        return {"brand": brand,
                "tokens": {"accent": "#79c142", "accent_text": "#0d0d0d", "bg": "#111111"}}

    def test_the_four_root_documents_exist(self):
        paths = {p.path for p in render._icon_pages(self._ctx())}
        assert paths == {"/favicon.ico", "/icon-32.png", "/favicon.svg",
                         "/manifest.webmanifest"}

    def test_binary_documents_carry_bytes_not_mojibake(self):
        for page in render._icon_pages(self._ctx()):
            if page.path in ("/favicon.ico", "/icon-32.png"):
                assert isinstance(page.raw, bytes) and page.raw
                assert page.payload == page.raw

    def test_a_text_document_still_serialises_from_its_body(self):
        svg = next(p for p in render._icon_pages(self._ctx()) if p.path == "/favicon.svg")
        assert svg.raw is None
        assert svg.payload == svg.body.encode("utf-8")

    def test_the_manifest_names_the_site_the_visitor_sees(self):
        page = next(p for p in render._icon_pages(self._ctx("Кинозал"))
                    if p.path == "/manifest.webmanifest")
        data = json.loads(page.body)
        assert data["name"] == "Кинозал"
        assert data["theme_color"] == "#79c142"
        assert {icon["src"] for icon in data["icons"]} == {"/icon-32.png", "/favicon.svg"}


class TestSitemapStatesTheRealReason:
    def _ctx(self, domain, indexing):
        return {"domain": domain, "indexing_enabled": indexing}

    def test_a_closed_indexing_gate_is_named_as_the_cause(self):
        body = render._sitemap(self._ctx("example.test", False), ["/"]).body
        assert "индексация выключена" in body
        # Домен на месте — винить его было бы неправдой.
        assert "домен не передан" not in body

    def test_a_missing_domain_is_still_named_as_the_cause(self):
        body = render._sitemap(self._ctx("", False), ["/"]).body
        assert "домен не передан" in body

    def test_an_open_gate_with_a_domain_lists_absolute_addresses(self):
        body = render._sitemap(self._ctx("example.test", True), ["/", "/movies/"]).body
        assert "<loc>https://example.test/</loc>" in body
        assert "<loc>https://example.test/movies/</loc>" in body
        assert "<!--" not in body

    def test_the_document_is_well_formed_in_every_case(self):
        from xml.etree import ElementTree

        for ctx in (self._ctx("example.test", True), self._ctx("example.test", False),
                    self._ctx("", False)):
            ElementTree.fromstring(render._sitemap(ctx, ["/"]).body)
