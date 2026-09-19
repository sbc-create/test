"""Animedia follow-up: player binding, episodes, collections, release gates."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "automation" / "host"
sys.path.insert(0, str(HOST))
sys.path.insert(0, str(ROOT))

from factory.lords import collection_contract as кк  # noqa: E402

gate_path = HOST / "nova_release_gate.py"
_spec = importlib.util.spec_from_file_location("nova_release_gate", gate_path)
gate = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(gate)


def _load_frontend(monkeypatch, tmp_path, *, family="animedia", version="1.2.1"):
    manifest = {
        "schema_version": 1,
        "family": family,
        "template_family": family,
        "design_version": version,
        "source_commit": "deadbeef",
        "runtime_commit": "cafebabe",
        "profile": "animedia-icu",
        "build_id": "test-build",
        "artifact_sha256": "0" * 64,
        "built_at": "2026-09-19T00:00:00Z",
    }
    man = tmp_path / "manifest.json"
    man.write_text(json.dumps(manifest), encoding="utf-8")
    cat = {
        "items": [
            {
                "slug": "master-lda-i-plameni-2",
                "title": "Мастер льда и пламени 2",
                "kind": "Аниме",
                "year": 2022,
                "published_at": "2026-09-01T00:00:00Z",
                "poster": "",
                "url": "/title/master-lda-i-plameni-2/",
            },
            {
                "slug": "movie-one",
                "title": "Фильм один",
                "kind": "Аниме",
                "year": 2024,
                "published_at": "2026-09-02T00:00:00Z",
                "poster": "",
                "url": "/title/movie-one/",
            },
        ],
        "revision": "rev-a",
        "count": 2,
    }
    details = {
        "catalog_revision": "rev-a",
        "details": {
            "master-lda-i-plameni-2": {
                "id": "01a0b507-3280-7b2a-8af4-674dd73cff72",
                "playable": True,
                "type": "tv",
                "year": 2022,
                "countries": ["Китай"],
                "genres": ["боевик", "фэнтези"],
                "sources": [
                    {
                        "availability_status": "available",
                        "provider": "mali",
                        "source_id": "53477",
                    }
                ],
                "external_ids": {"mal": "53477"},
                "seasons": [{"n": 2, "eps": 104, "avail": 104}],
                "imdb_rating": 7.2,
            },
            "movie-one": {
                "id": "movie-uuid",
                "playable": True,
                "type": "movie",
                "year": 2024,
                "countries": ["Япония"],
                "genres": ["романтика"],
                "sources": [
                    {
                        "availability_status": "available",
                        "provider": "mali",
                        "source_id": "1",
                    }
                ],
                "seasons": [],
                "imdb_rating": 8.1,
            },
        },
    }
    cat_path = tmp_path / "catalog.json"
    det_path = tmp_path / "details.json"
    player_cfg = tmp_path / "player.json"
    cat_path.write_text(json.dumps(cat), encoding="utf-8")
    det_path.write_text(json.dumps(details), encoding="utf-8")
    player_cfg.write_text(
        json.dumps({"publisher_id": "10252", "source_mode": "provider-id"}),
        encoding="utf-8",
    )
    monkeypatch.setenv("LORDS_TEMPLATE_MANIFEST", str(man))
    monkeypatch.setenv("LORDS_CATALOG", str(cat_path))
    monkeypatch.setenv("LORDS_DETAILS", str(det_path))
    monkeypatch.setenv("LORDS_PLAYER_CONFIG", str(player_cfg))
    monkeypatch.setenv("LORDS_SITE_NAME", "Animedia")
    path = HOST / "lords-frontend.py"
    name = f"animedia_fe_test_{tmp_path.name}"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    assert mod.ПЛЕЕР.get("publisher_id") == "10252", mod.ПЛЕЕР
    return mod, details["details"]["master-lda-i-plameni-2"], cat["items"][0]


def test_mali_before_cvh_candidates(monkeypatch, tmp_path):
    mod, det, _ = _load_frontend(monkeypatch, tmp_path)
    cands = mod.кандидаты_источника(det)
    assert cands[0] == ("mali", "53477")
    assert ("cvh", det["id"]) in cands


def test_player_markup_emits_candidates_and_mali_first(monkeypatch, tmp_path):
    mod, det, item = _load_frontend(monkeypatch, tmp_path)
    код, html = mod.разметка_плеера(mod.ВидАнимедиа, item, det, 2, 104)
    assert код == "resolving"
    assert "data-src-candidates" in html
    assert 'data-aggregator="mali"' in html
    assert 'data-title-id="53477"' in html
    bind = gate.provider_binding_match(html)
    assert bind["PROVIDER_BINDING_MATCH"] == 1
    assert bind["mali_first"] is True


def test_hub_picks_latest_available_episode(monkeypatch, tmp_path):
    mod, det, _ = _load_frontend(monkeypatch, tmp_path)
    assert mod.выбрать_доступную_серию(det) == (2, 104)


def test_direct_unavailable_episode_stays(monkeypatch, tmp_path):
    mod, det, item = _load_frontend(monkeypatch, tmp_path)
    det = dict(det)
    det["seasons"] = [{"n": 2, "eps": 104, "avail": 103}]
    код, html = mod.разметка_плеера(mod.ВидАнимедиа, item, det, 2, 104)
    assert код == "unavailable"
    assert "video-player" not in html


def test_season_label_has_separator(monkeypatch, tmp_path):
    mod, det, item = _load_frontend(monkeypatch, tmp_path)
    данные = mod.Данные(str(tmp_path / "catalog.json"))
    подробности = mod.Подробности(str(tmp_path / "details.json"))
    индекс = mod.построить_индекс(данные, подробности)
    семейство = mod.СЕМЕЙСТВА_1_1["animedia"]
    вид = mod.ВидАнимедиа(семейство, данные, подробности, индекс, "Animedia")
    сезоны = mod.список_серий(det)
    html = вид._серии(item, сезоны, текущий=(2, 104))
    assert "Сезон 2" in html
    assert "· 104 серий" in html
    assert "Сезон 2104" not in html
    import re
    nums = [int(m.group(1)) for m in re.finditer(r">(\d+)<", html)]
    assert nums == list(range(1, 105))


def test_new_episodes_not_catalog_fallback():
    items = [
        {"slug": "a", "title": "A", "kind": "Аниме", "year": 2024,
         "published_at": "2026-09-10T00:00:00Z", "poster": "", "url": "/title/a/"},
        {"slug": "b", "title": "B", "kind": "Аниме", "year": 2024,
         "published_at": "2026-09-09T00:00:00Z", "poster": "", "url": "/title/b/"},
    ]
    details = {
        "a": {"playable": True, "type": "tv", "seasons": [{"n": 1, "eps": 12, "avail": 12}]},
        "b": {"playable": True, "type": "movie", "seasons": []},
    }
    snap = кк.Снимок(items, details, revision="r1")
    recent = кк.разрешить("recently_added", snap, "animedia", предел=12)
    episodes = кк.разрешить("new_episodes", snap, "animedia", предел=12)
    assert recent is not None and [к.entity_id for к in recent.items]
    # Without episode timestamps the episode-events selector is empty.
    assert episodes is not None
    assert episodes.total == 0
    assert [к.raw["slug"] for к in recent.items] != [к.raw["slug"] for к in episodes.items]


def test_animedia_collection_selectors_diverge():
    items = []
    details = {}
    for i, (slug, typ, country, genre, year, rating, eps) in enumerate([
        ("m1", "movie", "Япония", "боевик", 2024, 8.0, 0),
        ("d1", "tv", "Китай", "фэнтези", 2023, 7.0, 40),
        ("s1", "tv", "Япония", "романтика", 1999, 9.0, 8),
        ("a1", "tv", "Япония", "боевик", 2025, 6.0, 24),
        ("f1", "tv", "Япония", "семейный", 2010, 7.5, 12),
    ]):
        items.append({
            "slug": slug, "title": slug, "kind": "Аниме", "year": year,
            "published_at": f"2026-09-{10-i:02d}T00:00:00Z",
            "poster": "p.webp", "url": f"/title/{slug}/",
        })
        details[slug] = {
            "id": slug, "playable": True, "type": typ,
            "countries": [country], "genres": [genre],
            "imdb_rating": rating,
            "seasons": ([{"n": 1, "eps": eps, "avail": eps}] if eps else []),
        }
    snap = кк.Снимок(items, details, revision="r2")
    keys = [
        "recently_added", "anime_movies", "donghua", "short_series",
        "classic", "action", "romance", "family", "top_rated",
        "series_with_episodes",
    ]
    tops = {}
    for key in keys:
        col = кк.разрешить(key, snap, "animedia", предел=12)
        assert col is not None, key
        tops[key] = [к.raw["slug"] for к in col.items]
        assert col.total == len(tops[key]) or col.total >= len(tops[key])
    assert tops["anime_movies"] == ["m1"]
    assert tops["donghua"] == ["d1"]
    assert "s1" in tops["classic"]
    assert tops["romance"] == ["s1"]
    # Exact duplicate top sets forbidden among orthogonal selectors.
    specialized = ["anime_movies", "donghua", "short_series", "action"]
    seen = []
    for key in specialized:
        sig = tuple(tops[key][:4])
        assert sig not in seen, key
        seen.append(sig)
    assert tops["romance"] == ["s1"]
    assert "s1" in tops["classic"]


def test_release_gate_requires_zona_ready_markers():
    cand = HOST / "lords-frontend.py"
    report = gate.runtime_compatible(cand, None)
    assert report["RUNTIME_COMPATIBLE"] == 1
    assert report["RUNTIME_DOWNGRADE"] == 0
    text = cand.read_text(encoding="utf-8")
    assert "providerShell" in text
    assert "__animediaPlayback" in text
    assert "node.addEventListener('error'" not in text


def test_split_seo_profile_does_not_change_provider_binding(monkeypatch, tmp_path):
    mod, det, item = _load_frontend(monkeypatch, tmp_path)
    for profile in ("animedia-icu", "animedia-space"):
        monkeypatch.setenv("LORDS_TEMPLATE_MANIFEST", str(tmp_path / "manifest.json"))
        man = json.loads((tmp_path / "manifest.json").read_text())
        man["profile"] = profile
        (tmp_path / "manifest.json").write_text(json.dumps(man), encoding="utf-8")
        cands = mod.кандидаты_источника(det)
        assert cands[0][0] == "mali"


def test_player_client_never_listens_for_undocumented_error():
    text = (HOST / "lords-frontend.py").read_text(encoding="utf-8")
    # Only script-tag load error is allowed — not provider 'error' on video-player.
    assert "node.addEventListener('error'" not in text
    assert "node.addEventListener('noData'" in text
    assert "providerShell(node)" in text
    assert "progress+3s" in text


def test_domain_profiles_diverge_seo_and_shelves():
    import animedia_ratings_sources as rs

    text = (HOST / "lords-frontend.py").read_text(encoding="utf-8")
    assert "animedia.icu" in text and "animedia.space" in text
    assert "Новые серии и популярное аниме" in text
    assert "Сериалы, фильмы и дунхуа" in text
    assert text.count('"seo_home"') >= 2 or text.count("seo_home") >= 4
    assert "Шикимуни" in rs.unresolved_owner_names()
    assert "Nisa Media" in rs.unresolved_owner_names()
    assert "shikimori" in rs.enabled_source_keys()


def test_hub_selects_latest_available_episode(monkeypatch, tmp_path):
    mod, det, _item = _load_frontend(monkeypatch, tmp_path)
    s, e = mod.выбрать_доступную_серию(det)
    assert (s, e) == (2, 104)


def test_home_css_locks_hero_card_width():
    text = (HOST / "lords-frontend.py").read_text(encoding="utf-8")
    assert "min(1704px,calc(100vw - 80px))" in text
    assert "clamp(148px,8.2vw,168px)" in text
    assert ".ahero" in text and "max-height:min(300px,34vh)" in text
    assert "clamp(240px,15.8vw,306px) minmax(0,1fr)" in text
    assert "aspect-ratio:16/9" in text


def test_player_overlay_hidden_css_not_overridden():
    text = (HOST / "lords-frontend.py").read_text(encoding="utf-8")
    assert "[data-player-state][hidden]" in text
    assert "display:none !important" in text
    assert "st.style.display='none'" in text
