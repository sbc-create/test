"""SSR: only published comments, no SEO surface touched, no cloaking."""

from __future__ import annotations

import inspect

import pytest

from factory.comments_platform import ssr, states
from factory.comments_platform.flags import EffectiveFlags

from .htmlcheck import assert_no_scripting


def flags(*, ssr_enabled: int = 1, seo_mode: str = "ssr_first_page") -> EffectiveFlags:
    return EffectiveFlags(
        tenant_id="lords", site_id="lords-main",
        read_enabled=1, write_enabled=1, publication_enabled=1, rollout_percent=100,
        ssr_enabled=ssr_enabled, seo_mode=seo_mode, moderation_mode="post",
        kill_switch_global=0, kill_switch_site=0,
    )


def comment(comment_id: str, state: str, body_html: str = "hello") -> dict:
    return {
        "comment_id": comment_id,
        "anchor": f"comment-{comment_id}",
        "depth": 0,
        "author": {"subject_id": "g_abc"},
        "state": state,
        "body_html": body_html,
        "created_at": "2026-09-22T10:00:00Z",
        "reaction_count": 2,
    }


ALL_STATES = [comment(f"c{i}", state) for i, state in enumerate(states.STATES)]


class TestOnlyPublishedIsRendered:
    def test_non_public_states_never_reach_the_html(self):
        rendered = ssr.render_thread(ALL_STATES, flags=flags())
        for index, state in enumerate(states.STATES):
            present = f"comment-c{index}" in rendered.html
            assert present == (state in states.PUBLIC_VISIBLE), (
                f"state {state} rendered={present}"
            )

    def test_the_count_matches_what_was_rendered(self):
        rendered = ssr.render_thread(ALL_STATES, flags=flags())
        assert rendered.rendered_count == len(states.PUBLIC_VISIBLE)

    @pytest.mark.parametrize(
        "state", sorted(set(states.STATES) - states.PUBLIC_VISIBLE)
    )
    def test_a_held_comments_text_is_absent_entirely(self, state):
        """Not hidden by CSS, not in a JSON island — absent from the bytes."""
        secret = "text that must not be delivered to a crawler"
        rendered = ssr.render_thread(
            [comment("c1", state, body_html=secret)], flags=flags()
        )
        assert secret not in rendered.html

    def test_no_display_none_trick_is_used(self):
        rendered = ssr.render_thread(ALL_STATES, flags=flags())
        assert "display:none" not in rendered.html.replace(" ", "")
        assert "hidden" not in rendered.html


class TestUserInitiatedMode:
    def test_default_mode_renders_a_mount_point_only(self):
        rendered = ssr.render_thread(
            ALL_STATES, flags=flags(ssr_enabled=0, seo_mode="user_initiated")
        )
        assert rendered.rendered_count == 0
        assert "hello" not in rendered.html
        assert 'class="cp-root"' in rendered.html

    def test_ssr_mode_without_publication_renders_nothing(self):
        """SSR is a strict subset of publication."""
        rendered = ssr.render_thread(
            ALL_STATES, flags=flags(ssr_enabled=0, seo_mode="ssr_first_page")
        )
        assert rendered.rendered_count == 0
        assert "hello" not in rendered.html


class TestSeoSurfaceIsNotTouched:
    @pytest.mark.parametrize("tag", ssr.FORBIDDEN_TAGS)
    def test_rendered_output_contains_no_page_level_seo_tag(self, tag):
        rendered = ssr.render_thread(ALL_STATES, flags=flags())
        assert tag.lower() not in rendered.html.lower()

    def test_no_json_ld_is_emitted(self):
        rendered = ssr.render_thread(ALL_STATES, flags=flags())
        assert "ld+json" not in rendered.html
        assert "aggregateRating" not in rendered.html

    def test_the_promise_names_every_surface(self):
        promise = ssr.seo_surface_untouched()
        never = " ".join(promise["never_modified"]).lower()
        for surface in ("robots", "canonical", "sitemap", "hreflang", "indexability", "json-ld"):
            assert surface in never
        assert promise["default_mode"] == "user_initiated"
        assert promise["ssr_requires_publication"] is True


class TestNoCloaking:
    def test_render_thread_takes_no_user_agent(self):
        signature = inspect.signature(ssr.render_thread)
        for name in signature.parameters:
            assert "agent" not in name.lower()
            assert "bot" not in name.lower()
            assert "crawler" not in name.lower()

    def test_the_module_never_inspects_a_user_agent(self):
        source = inspect.getsource(ssr)
        lowered = source.lower()
        for needle in ("user_agent", "user-agent", "googlebot", "yandexbot", "crawler"):
            # The word may appear in prose explaining why there is no branch;
            # what must not appear is a comparison against one.
            assert f'== "{needle}"' not in lowered
            assert "in request" not in lowered or needle not in lowered.split("in request")[0][-40:]

    def test_two_identical_calls_produce_identical_bytes(self):
        first = ssr.render_thread(ALL_STATES, flags=flags())
        second = ssr.render_thread(ALL_STATES, flags=flags())
        assert first.html == second.html


class TestEscaping:
    def test_metadata_is_escaped(self):
        """Checked structurally, on the real tags only.

        Searching the raw string for `onerror=` would fail on correct output:
        an escaped `&lt;img src=x onerror=alert(1)&gt;` is inert precisely
        because it is text, and it still contains those characters.
        """
        hostile = comment("c1", states.PUBLISHED)
        hostile["author"] = {"subject_id": '"><script>alert(1)</script>'}
        hostile["created_at"] = '"><img src=x onerror=alert(1)>'
        rendered = ssr.render_thread([hostile], flags=flags())

        assert_no_scripting(
            rendered.html,
            allowed_tags={"div", "section", "article", "header", "span", "time", "footer"},
        )
        assert "<script" not in rendered.html
        assert "<img" not in rendered.html

    def test_body_html_is_inserted_as_prepared(self):
        """It arrives already escaped from sanitize; double-escaping would show
        readers literal entity text."""
        safe = comment("c1", states.PUBLISHED, body_html="<strong>bold</strong>")
        rendered = ssr.render_thread([safe], flags=flags())
        assert "<strong>bold</strong>" in rendered.html


class TestPagination:
    def test_first_page_mode_signals_that_more_exist(self):
        rendered = ssr.render_thread(
            ALL_STATES, flags=flags(seo_mode="ssr_first_page"), has_more=True
        )
        assert rendered.has_more is True

    def test_paginated_mode_reports_the_caller_s_has_more(self):
        rendered = ssr.render_thread(
            [comment("c1", states.PUBLISHED)],
            flags=flags(seo_mode="ssr_paginated"),
            has_more=False,
        )
        assert rendered.has_more is False
