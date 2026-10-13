"""Подсказки и замены на страницах — только подтверждённые источником (решение владельца 13.10.2026)."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_snapshot_has_no_unsourced_tips_or_substitutions_on_pages(site):
    for r in site.recipes:
        assert all(t.get("source_steps") for t in r.tips)
        assert all(s.get("source_steps") for _, s in r.substitutions)


def test_recipe_pages_link_each_tip_and_substitution_to_source(app, site):
    shown = 0
    for r in site.recipes:
        _, html, _ = app.route(r.url, {})
        n = len(r.tips) + len(r.substitutions)
        assert html.count('class="src-step"') == n, r.slug
        if n:
            assert re.search(rf'class="src-step" href="{re.escape(r.source["url"])}"', html)
        for t in r.d.get("tips") or []:
            if not t.get("source_steps"):
                assert t["text"] not in html, r.slug
        shown += n
    assert shown == 11  # 9 подсказок и 2 замены после разбора 13.10.2026


def test_editor_notes_never_published():
    snap = json.loads((ROOT / "data" / "content-snapshot.json").read_text())
    assert all("editor_notes" not in it["draft"] for it in snap["items"])


def test_substitutions_article_lists_only_sourced(app):
    _, html, _ = app.route("/sovety/zameny-produktov/", {})
    assert html.count('class="src-step"') == 2 and "Не проверено." not in html
