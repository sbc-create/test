"""Одно произведение с по-разному обрезанным слагом в двух семействах (19.10)."""

from seo_operator import regular


def test_truncated_slugs_of_one_work_match():
    yummy = regular.work_key("izgnannyy-chiter-charodey-naslazhdaetsya-bezzabotnoy-vtoroy-zhiznyu-ya-mogu")
    animedia = regular.work_key("izgnannyy-chiter-charodey-naslazhdaetsya-bezzabotnoy-vtoroy-zhiznyu-ya-mogu-nakl")
    assert yummy != animedia
    assert animedia in regular.WorkSet({yummy})
    assert yummy in regular.WorkSet({animedia})


def test_trailing_dash_of_truncation_ignored():
    a = regular.work_key("nesmotrya-na-to-chto-ya-ochen-robkaya-blagorodnaya-devushka-ya-prinyala-pari-ot")
    b = regular.work_key("nesmotrya-na-to-chto-ya-ochen-robkaya-blagorodnaya-devushka-ya-prinyala-pari-ot-")
    assert b in regular.WorkSet({a})


def test_short_keys_are_not_prefix_matched():
    assert regular.work_key("chernyy-klever-2") not in regular.WorkSet({regular.work_key("chernyy-klever")})
    assert "magiya-vernuvshegosya" not in regular.WorkSet({"magiya-vernuvshegosya-dolzhna-byt-osobennoy"})


def test_numbered_sequel_of_long_title_is_another_work():
    base = "x" * 72
    assert base + "-2" not in regular.WorkSet({base})
    assert base not in regular.WorkSet({base + "-2"})


def test_unrelated_long_keys_do_not_match():
    a = "a" * 75
    b = "b" * 75
    assert b not in regular.WorkSet({a})


def test_yummy_demand_candidates_respect_truncated_network_text(tmp_path):
    import json

    snap = tmp_path / "analytics-2026-10-19.json"
    long_yummy = "izgnannyy-chiter-charodey-naslazhdaetsya-bezzabotnoy-vtoroy-zhiznyu-ya-mogu"
    snap.write_text(json.dumps({"domains": [{"domain": "yummyani.site", "measurements": [
        {"key": "search_landing_pages", "measured": True,
         "value": [{"dimensions": [{"id": "organic"}, {"name": f"/anime/{long_yummy}"}], "metrics": [70, 70]}]}]}]}),
        encoding="utf-8")
    got = regular.yummy_demand_candidates(
        snap, {("animedia.icu", long_yummy + "-nakl")}, describe=lambda d, s: "")
    assert got == []
