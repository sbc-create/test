"""IMDb ID каталога без ведущих нулей сверяется со статьёй (19.10)."""

import importlib.util
import pathlib

_P = pathlib.Path(__file__).resolve().parents[2] / "automation" / "local" / "source_fetch.py"
_spec = importlib.util.spec_from_file_location("source_fetch", _P)
sf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sf)


def test_short_id_is_padded_to_seven_digits():
    assert sf.imdb_digits("491603") == "0491603"
    assert sf.imdb_digits("tt0790772") == "0790772"
    assert sf.imdb_digits("42888794") == "42888794"


def test_identity_found_for_unpadded_catalog_id(monkeypatch):
    page = '<a href="https://www.imdb.com/title/tt0491603/">IMDb</a> wikidata.org/wiki/Q130615'
    monkeypatch.setattr(sf, "_wiki_article", lambda lang, title: (200, page, "https://ru.wikipedia.org/wiki/X"))
    monkeypatch.setattr(sf, "_log", lambda **kw: None)
    out = sf.film("491603", "H2O", "H2O: Just Add Water", "2006", "tv")
    assert out["ok"] is True
    assert "tt0491603" in out["identity"]


def test_longer_id_with_same_prefix_is_not_a_match(monkeypatch):
    page = '<a href="https://www.imdb.com/title/tt12101660/">IMDb</a>'
    monkeypatch.setattr(sf, "_wiki_article", lambda lang, title: (200, page, "https://ru.wikipedia.org/wiki/X"))
    monkeypatch.setattr(sf, "_log", lambda **kw: None)
    out = sf.film("1210166", "X", "X", "2011", "movie")
    assert out["ok"] is False
