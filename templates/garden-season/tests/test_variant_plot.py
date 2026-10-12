"""Приёмочные тесты варианта C (my-plot): регион и культуры → личный календарь без смешивания регионов."""

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sezon.server import App  # noqa: E402
from sezon.site import Site  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return App()


def get(app, p, q=None):
    return app.route(p, q or {})


def canon(html):
    m = re.search(r'<link rel="canonical" href="([^"]+)"', html)
    return m.group(1) if m else None


def test_identity_port_storage(app):
    c = app.site.cfg
    assert (c["variant_id"], c["server"]["port"], c["storage_namespace"]) == ("my-plot", 8868, "gs-plot")
    assert not (ROOT / "static" / "js" / "season.js").exists()


def test_plot_never_mixes_regions(app):
    s = app.site
    crops = list(s.crops())
    for region, allowed in Site.PLOT_REGIONS.items():
        for rows in s.plot(region, crops, True).values():
            assert all(r["region"] in allowed for r in rows), region
    uk = s.plot("uk", crops, True)
    assert uk and all(r["region"] == "uk" for rows in uk.values() for r in rows)
    west = s.plot("or-west", ["chesnok"], False)
    assert {r["region"] for rows in west.values() for r in rows} == {"or-west", "or-all"}


def test_plot_rows_match_work_timing(app):
    s = app.site
    for m, rows in s.plot("or-all", list(s.crops()), True).items():
        for r in rows:
            assert any(t.get("month") == m and t["region"] == r["region"] for t in r["work"].timing)


def test_plot_page_states(app):
    st, html, _ = get(app, "/moj-uchastok/")
    assert st == 200 and canon(html) == app.site.abs("/moj-uchastok/") and 'class="plot"' not in html
    st, html, _ = get(app, "/moj-uchastok/", {"region": ["or-west"], "k": ["chesnok"]})
    assert st == 200 and canon(html) is None and 'class="plot"' in html and "Западный Орегон" in html
    assert get(app, "/moj-uchastok/", {"region": ["moskva"], "k": ["chesnok"]})[0] == 400
    assert get(app, "/moj-uchastok/", {"region": ["uk"]})[0] == 400
    st, html, _ = get(app, "/moj-uchastok/", {"region": ["uk"], "k": ["golubika"]})
    assert st == 200 and "Для этого выбора работ нет" in html
