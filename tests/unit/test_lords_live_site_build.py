"""REQ-LORDS-LIVE-BUILD: живая сборка не подменяет стенд и не выкатывает пустоту."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory.errors import BlockedInput
from factory.lords import live_site


def items(count: int) -> list[dict]:
    return [
        {
            "external_id": f"01a0-{i:05d}",
            "name": f"Тайтл {i}",
            "type": "movie" if i % 2 else "tv",
            "is_series": bool(i % 2 == 0),
            "year": 2010 + (i % 15),
            "poster_url": f"https://poster.cdnvideohub.com/p/{i}.jpg",
            "tags": ["Драма"],
            "kinopoisk_rating": 7.1,
            "imdb_rating": None,
            "external_ids": {},
            "playback": None,
            "created_at": "2026-08-20T10:00:00Z",
            "updated_at": "2026-08-21T10:00:00Z",
        }
        for i in range(count)
    ]


class TestEmptySourceNeverBecomesAnEmptyStorefront:
    def test_missing_cache_is_refused(self, tmp_path: Path):
        with pytest.raises(BlockedInput):
            live_site.load_live_items("lords-01", root=tmp_path)

    def test_empty_cache_is_refused(self, tmp_path: Path):
        """Пустая выдача обязана останавливать сборку, а не заменять релиз ничем."""
        (tmp_path / "lords-01.json").write_text(json.dumps({"items": []}), encoding="utf-8")
        with pytest.raises(BlockedInput):
            live_site.load_live_items("lords-01", root=tmp_path)

    def test_cache_with_items_is_read(self, tmp_path: Path):
        (tmp_path / "lords-01.json").write_text(
            json.dumps({"items": items(3)}, ensure_ascii=False), encoding="utf-8")
        assert len(live_site.load_live_items("lords-01", root=tmp_path)) == 3


class TestLiveBuildProducesTheWholeSite:
    def test_build_writes_the_full_document_set(self, tmp_path: Path):
        result = live_site.build_live_site("lords-01", output=tmp_path, items=items(60))
        written = {p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*") if p.is_file()}
        assert "index.html" in written
        assert "catalog/index.html" in written, "каталога нет — это снова одна страница"
        assert any(p.startswith("title/") for p in written), "страниц тайтлов нет"
        assert result.report["catalog"]["source"] != "fixture/test"

    def test_listing_pages_stay_small(self, tmp_path: Path):
        result = live_site.build_live_site("lords-01", output=tmp_path, items=items(300))
        for path, size in result.report["listing_bytes"].items():
            assert size < 200_000, f"{path} весит {size} байт — страница несёт весь каталог"

    def test_report_records_what_the_source_actually_gave(self, tmp_path: Path):
        result = live_site.build_live_site("lords-01", output=tmp_path, items=items(20))
        coverage = result.report["coverage"]
        assert coverage["with_poster"] == 20
        assert coverage["with_kinopoisk"] == 20
        # IMDb источник в этой выборке не дал ни разу — и покрытие обязано это показать.
        assert coverage["with_imdb"] == 0
