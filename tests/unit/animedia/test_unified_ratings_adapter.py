"""Адаптер оценок animedia.icu: отказ в пользу страницы, когорта, kill switch."""

from __future__ import annotations

import json

import pytest

from factory.animedia import unified_ratings_adapter as adapter


@pytest.fixture(autouse=True)
def runtime(tmp_path, monkeypatch):
    monkeypatch.setattr(adapter, "RUNTIME_DIR", tmp_path)
    monkeypatch.setattr(adapter, "PROJECTION_PATH", tmp_path / "proj.json")
    monkeypatch.setattr(adapter, "FLAGS_PATH", tmp_path / "flags.json")
    adapter._cache.update({"flags": None, "proj": None, "stamps": None})
    return tmp_path


def write(runtime, *, flags=None, titles=None):
    (runtime / "flags.json").write_text(
        json.dumps(flags if flags is not None else {}), encoding="utf-8"
    )
    (runtime / "proj.json").write_text(
        json.dumps({"titles": titles or {}}), encoding="utf-8"
    )
    adapter._cache.update({"flags": None, "proj": None, "stamps": None})


DETAIL = {"id": "01927e18-0e9e-7319-91b5-b8dd8be5a6a9", "name": "009-1",
          "ratings_by_source": {"imdb": {"value": 6.4, "scale": 10.0, "source": "imdb"}}}

ENTRY = {
    "external": [
        {"source": "anilist", "label": "AniList", "score": "7.0", "votes": 4000,
         "url": "https://anilist.co/anime/1"},
        {"source": "kitsu", "label": "Kitsu", "score": "7.4", "votes": 2000, "url": ""},
    ],
    "composite": {"label": "Сводная оценка", "value": "7.2", "source_count": 2,
                  "sources": ["anilist", "kitsu"], "formula_version": "equal_weight_mean_v1",
                  "confidence": "MEDIUM"},
    "native": {"average": "8.00", "votes": 3, "label": "Оценка зрителей", "scale": "1-10"},
    "editorial": {"label": "Наша оценка", "value": 9, "scale": "1-10"},
}

FLAGS_ON = {
    "RATINGS_PUBLIC_READ_ANIMEDIA": 1,
    "RATINGS_PUBLIC_WRITE_ANIMEDIA": 0,
    "KILL_SWITCH": 0,
    "allowlist": {"animedia": ["01927e18-0e9e-7319-91b5-b8dd8be5a6a9"]},
}


# ---------------------------------------------------------------------------
# отказ в пользу страницы
# ---------------------------------------------------------------------------


def test_no_files_leaves_the_detail_untouched():
    assert adapter.merge_into_detail(DETAIL) == DETAIL


def test_corrupt_projection_leaves_the_detail_untouched(runtime):
    (runtime / "flags.json").write_text(json.dumps(FLAGS_ON), encoding="utf-8")
    (runtime / "proj.json").write_text("{не json", encoding="utf-8")
    adapter._cache.update({"flags": None, "proj": None, "stamps": None})
    assert adapter.merge_into_detail(DETAIL) == DETAIL


def test_read_flag_off_leaves_the_detail_untouched(runtime):
    write(runtime, flags={**FLAGS_ON, "RATINGS_PUBLIC_READ_ANIMEDIA": 0},
          titles={DETAIL["id"]: {"animedia": ENTRY}})
    assert adapter.merge_into_detail(DETAIL) == DETAIL


def test_title_outside_the_cohort_is_untouched(runtime):
    write(runtime, flags={**FLAGS_ON, "allowlist": {"animedia": ["someone-else"]}},
          titles={DETAIL["id"]: {"animedia": ENTRY}})
    assert adapter.merge_into_detail(DETAIL) == DETAIL


def test_empty_cohort_means_nobody(runtime):
    write(runtime, flags={**FLAGS_ON, "allowlist": {"animedia": []}},
          titles={DETAIL["id"]: {"animedia": ENTRY}})
    assert adapter.merge_into_detail(DETAIL) is DETAIL or adapter.merge_into_detail(DETAIL) == DETAIL


def test_kill_switch_hides_everything(runtime):
    write(runtime, flags={**FLAGS_ON, "KILL_SWITCH": 1},
          titles={DETAIL["id"]: {"animedia": ENTRY}})
    assert adapter.merge_into_detail(DETAIL) == DETAIL
    assert adapter.widget_context(DETAIL) is None


def test_detail_without_an_id_is_untouched(runtime):
    write(runtime, flags=FLAGS_ON, titles={DETAIL["id"]: {"animedia": ENTRY}})
    assert adapter.merge_into_detail({"name": "без id"}) == {"name": "без id"}


# ---------------------------------------------------------------------------
# обогащение
# ---------------------------------------------------------------------------


def test_external_scores_go_into_ratings_by_source(runtime):
    write(runtime, flags=FLAGS_ON, titles={DETAIL["id"]: {"animedia": ENTRY}})
    out = adapter.merge_into_detail(DETAIL)
    assert out["ratings_by_source"]["anilist"]["value"] == "7.0"
    assert out["ratings_by_source"]["kitsu"]["votes"] == 2000
    assert out["ratings_by_source"]["imdb"]["value"] == 6.4, "прежние источники сохранены"


def test_the_three_kinds_get_their_own_keys(runtime):
    write(runtime, flags=FLAGS_ON, titles={DETAIL["id"]: {"animedia": ENTRY}})
    out = adapter.merge_into_detail(DETAIL)
    assert out["unified_composite"]["value"] == "7.2"
    assert out["unified_community"]["average"] == "8.00"
    assert out["unified_editorial"]["value"] == 9
    assert "composite" not in out["ratings_by_source"]
    assert "community" not in out["ratings_by_source"]


def test_a_missing_score_is_not_written_as_zero(runtime):
    entry = {"external": [{"source": "kitsu", "label": "Kitsu", "score": None, "votes": None}]}
    write(runtime, flags=FLAGS_ON, titles={DETAIL["id"]: {"animedia": entry}})
    out = adapter.merge_into_detail(DETAIL)
    assert "kitsu" not in out["ratings_by_source"]


def test_bare_and_prefixed_identifiers_both_resolve(runtime):
    write(runtime, flags=FLAGS_ON, titles={f"nova:{DETAIL['id']}": {"animedia": ENTRY}})
    assert adapter.merge_into_detail(DETAIL)["unified_composite"]["value"] == "7.2"


def test_schema_org_aggregate_rating_stays_off(runtime):
    write(runtime, flags=FLAGS_ON, titles={DETAIL["id"]: {"animedia": ENTRY}})
    assert adapter.merge_into_detail(DETAIL)["aggregate_rating_schema_org"] is False


# ---------------------------------------------------------------------------
# виджет и запись
# ---------------------------------------------------------------------------


def test_widget_context_is_none_without_data(runtime):
    write(runtime, flags=FLAGS_ON, titles={})
    assert adapter.widget_context(DETAIL) is None


def test_widget_context_reports_write_disabled_by_default(runtime):
    write(runtime, flags=FLAGS_ON, titles={DETAIL["id"]: {"animedia": ENTRY}})
    ctx = adapter.widget_context(DETAIL)
    assert ctx["write_enabled"] is False
    assert ctx["space"] == "animedia"
    assert ctx["api_base"] == "/api/unified-ratings"
    assert ctx["composite"]["source_count"] == 2


def test_write_flag_enables_voting(runtime):
    write(runtime, flags={**FLAGS_ON, "RATINGS_PUBLIC_WRITE_ANIMEDIA": 1},
          titles={DETAIL["id"]: {"animedia": ENTRY}})
    assert adapter.widget_context(DETAIL)["write_enabled"] is True


def test_read_flag_alone_does_not_enable_writing(runtime):
    write(runtime, flags=FLAGS_ON, titles={DETAIL["id"]: {"animedia": ENTRY}})
    assert adapter.public_read_enabled() is True
    assert adapter.public_write_enabled() is False


def test_runtime_status_describes_what_is_loaded(runtime):
    write(runtime, flags=FLAGS_ON, titles={DETAIL["id"]: {"animedia": ENTRY}})
    status = adapter.runtime_status()
    assert status["projection_present"] is True
    assert status["public_read_enabled"] is True
    assert status["public_write_enabled"] is False
    assert status["cohort_size"] == 1


def test_adapter_never_touches_the_network_or_database():
    """Адаптер читает два файла и ничего больше."""
    source = (
        __import__("pathlib").Path(adapter.__file__).read_text(encoding="utf-8")
    )
    for forbidden in ("sqlite3", "urllib", "requests", "socket", "http.client"):
        assert forbidden not in source, f"адаптер не должен использовать {forbidden}"
