"""Адреса витрины и инвентарь: уникальность, устойчивость, честное сравнение.

Доказывает: REQ-CELL-URLS.
"""
from __future__ import annotations

from pathlib import Path

from factory.cell import pilot

UUIDS = [
    # Одна партия одного генератора: совпадает именно начало. Срез первых
    # символов дал бы всем трём один адрес.
    "3f2a7c10-0000-4000-8000-00000000000a",
    "3f2a7c10-0000-4000-8000-00000000000b",
    "3f2a7c10-0000-4000-8000-00000000000c",
]


def test_similar_uuids_never_share_a_route():
    slugs = {pilot.slug_for(u, "Одинаковое название") for u in UUIDS}
    assert len(slugs) == len(UUIDS), f"адреса совпали: {slugs}"


def test_cyrillic_name_still_yields_a_usable_route():
    slug = pilot.slug_for(UUIDS[0], "Первая запись")
    assert slug
    assert slug.isascii()


def test_route_does_not_change_when_the_name_changes():
    """Правка названия не должна уносить страницу с прежнего адреса."""
    before = pilot.slug_for(UUIDS[0], "Название")
    after = pilot.slug_for(UUIDS[0], "Название с исправленной опечаткой")
    # Читаемая часть меняется, устойчивый хвост — нет.
    assert before.split("-")[-1] == after.split("-")[-1]


def _catalog() -> dict:
    return {
        u: {"title": f"Запись {i}", "year": 2020 + i, "episodes": i + 1,
            "playback": {"aggregator": "kp", "title_id": f"fixture-{i}"}}
        for i, u in enumerate(UUIDS)
    }


def test_every_catalog_record_gets_its_own_page(tmp_path: Path):
    pages = pilot.render(site_id="s", domain="s.invalid", publisher_id="10252",
                         catalog=_catalog(), destination=tmp_path)
    title_pages = [p for p in pages if p.route.startswith("/title/")]
    assert len(title_pages) == len(UUIDS)
    assert len({p.route for p in title_pages}) == len(UUIDS)


def test_inventory_notices_a_lost_route(tmp_path: Path):
    pilot.render(site_id="s", domain="s.invalid", publisher_id="10252",
                 catalog=_catalog(), destination=tmp_path / "before")
    smaller = _catalog()
    smaller.pop(UUIDS[-1])
    pilot.render(site_id="s", domain="s.invalid", publisher_id="10252",
                 catalog=smaller, destination=tmp_path / "after")
    before = pilot.url_inventory(tmp_path / "before")
    after = pilot.url_inventory(tmp_path / "after")
    comparison = pilot.compare_inventories(before, after)
    assert comparison["status"] == "FAIL"
    assert len(comparison["lost"]) == 1


def test_inventory_notices_pages_emptied_into_a_stub(tmp_path: Path):
    """Пустая страница с кодом 200 успехом не считается."""
    pilot.render(site_id="s", domain="s.invalid", publisher_id="10252",
                 catalog=_catalog(), destination=tmp_path / "before")
    before = pilot.url_inventory(tmp_path / "before")
    import shutil
    shutil.copytree(tmp_path / "before", tmp_path / "after")
    for page in (tmp_path / "after").rglob("index.html"):
        page.write_text("<html></html>", encoding="utf-8")
    after = pilot.url_inventory(tmp_path / "after")
    comparison = pilot.compare_inventories(before, after)
    assert comparison["status"] == "FAIL"
    assert comparison["emptied"]


def test_unchanged_site_compares_clean(tmp_path: Path):
    pilot.render(site_id="s", domain="s.invalid", publisher_id="10252",
                 catalog=_catalog(), destination=tmp_path / "a")
    pilot.render(site_id="s", domain="s.invalid", publisher_id="10252",
                 catalog=_catalog(), destination=tmp_path / "b")
    comparison = pilot.compare_inventories(pilot.url_inventory(tmp_path / "a"),
                                           pilot.url_inventory(tmp_path / "b"))
    assert comparison["status"] == "PASS"
    assert comparison["lost"] == []
    assert comparison["changed"] == []


def test_retired_publisher_id_never_appears_in_markup(tmp_path: Path):
    pilot.render(site_id="s", domain="s.invalid", publisher_id="10252",
                 catalog=_catalog(), destination=tmp_path)
    for page in tmp_path.rglob("index.html"):
        text = page.read_text(encoding="utf-8")
        assert "10331" not in text
        assert "10332" not in text
        assert "10333" not in text


def test_title_without_playback_says_so_instead_of_faking_a_player(tmp_path: Path):
    catalog = {UUIDS[0]: {"title": "Без воспроизведения", "year": 2024}}
    pilot.render(site_id="s", domain="s.invalid", publisher_id="10252",
                 catalog=catalog, destination=tmp_path)
    page = next((tmp_path / "title").rglob("index.html"))
    text = page.read_text(encoding="utf-8")
    assert "playback-unavailable" in text
    assert "<video-player" not in text
