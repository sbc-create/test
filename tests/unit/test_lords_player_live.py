"""REQ-LORDS-PLAYER: живой плеер CDNVideoHub подключается по контракту.

Проверяется разметка, которую отдаёт сервер: custom element без iframe,
атрибуты из `knowledge/cdnvideohub/PLAYER_CONTRACT.yaml`, серверный Publisher ID
и отсутствие его в общем клиентском бандле.

Боевые секреты здесь не нужны: Publisher ID — это число, и для проверки формы
разметки достаточно любого числа.
"""

from __future__ import annotations

import re

import pytest

from factory.lords import player

PUBLISHER = "4321"
TITLE_ID = "778899"


def render(**overrides) -> str:
    kwargs = {
        "publisher_id": PUBLISHER, "aggregator": "kp", "title_id": TITLE_ID,
        "title_name": "Тайтл", "ident": "lords-01:kp:778899",
        "season": 1, "episode": 1,
    }
    kwargs.update(overrides)
    return player.render_live(**kwargs)


class TestPublisherId:
    @pytest.mark.parametrize("value", ["1", "42", "999999"])
    def test_a_positive_integer_is_accepted(self, value):
        assert player.is_valid_publisher_id(value)

    @pytest.mark.parametrize("value", ["", "0", "-1", "1.5", "abc", "12a", None, "007"])
    def test_anything_else_is_refused(self, value):
        assert not player.is_valid_publisher_id(value)

    def test_a_non_numeric_publisher_id_blocks_rendering(self):
        """Плеер делает Number(pub); NaN превращается в 400 у провайдера."""
        with pytest.raises(player.PlayerContractError, match="положительным целым"):
            render(publisher_id="not-a-number")


class TestContractRules:
    def test_imdb_is_refused_as_a_playback_identifier(self):
        """PC-2: IMDb не используется как playback identifier."""
        with pytest.raises(player.PlayerContractError, match="PC-2"):
            render(aggregator="imdb")

    @pytest.mark.parametrize("aggregator", ["kp", "mali", "mdl"])
    def test_the_approved_aggregators_are_accepted(self, aggregator):
        assert f'data-aggregator="{aggregator}"' in render(aggregator=aggregator)

    def test_conflicting_voices_are_refused(self):
        """PC-1: одновременно only-voice и priority-voice запрещены."""
        with pytest.raises(player.PlayerContractError, match="PC-1"):
            render(only_voice="studio-a", priority_voice="studio-b")

    def test_only_voice_wins_when_alone(self):
        markup = render(only_voice="studio-a")
        assert 'only-voice="studio-a"' in markup
        assert "priority-voice" not in markup

    def test_disable_licensed_is_fixed(self):
        """PC-3: значение не берётся из настроек сайта."""
        assert 'disable-licensed="false"' in render()

    def test_the_player_is_not_wrapped_in_an_iframe(self):
        """PC-4: собственный iframe вокруг плеера запрещён."""
        assert "<iframe" not in render().lower()

    @pytest.mark.parametrize(("season", "episode"), [(0, 1), (1, 0), (-1, 1), (1, -2)])
    def test_non_positive_season_or_episode_is_refused(self, season, episode):
        with pytest.raises(player.PlayerContractError):
            render(season=season, episode=episode)


class TestMarkup:
    def test_the_custom_element_is_used(self):
        assert re.search(r"<video-player [^>]*></video-player>", render())

    def test_the_script_url_comes_from_the_frozen_contract(self):
        contract = player.load_player_contract()
        url = contract["script"]["url"]
        assert f'src="{url}"' in render()
        assert url.startswith("https://player.cdnvideohub.com/")

    def test_the_script_is_async(self):
        assert "async" in render()

    def test_every_required_attribute_is_present(self):
        markup = render()
        for name in ("ident", "season", "episode", "data-publisher-id",
                     "data-title-id", "data-aggregator", "is-show-voice-only",
                     "is-show-banner", "disable-licensed"):
            assert f"{name}=" in markup, name

    def test_seasons_and_episodes_are_addressable(self):
        markup = render(season=3, episode=7)
        assert 'season="3"' in markup
        assert 'episode="7"' in markup

    def test_a_film_without_seasons_still_renders(self):
        """Фильм — это сезон 1, серия 1, а не отсутствие плеера."""
        markup = render(season=1, episode=1)
        assert "<video-player" in markup

    def test_there_is_a_visible_fallback_for_an_unavailable_source(self):
        markup = render()
        assert "data-player-fallback" in markup
        assert "недоступен" in markup

    def test_noscript_explains_the_requirement(self):
        assert "<noscript>" in render()


class TestSecrets:
    def test_the_api_token_never_appears_in_markup(self):
        """Токен — серверный. В разметку он не попадает ни при каких условиях."""
        markup = render()
        assert "CDNVIDEOHUB_API_TOKEN" not in markup
        assert "Bearer" not in markup
        assert "Authorization" not in markup

    def test_the_publisher_id_is_an_attribute_not_a_bundle_constant(self):
        """Publisher ID живёт атрибутом элемента, а не в общем JS."""
        markup = render()
        assert f'data-publisher-id="{PUBLISHER}"' in markup
        # Отдельного скрипта с конфигурацией, который попал бы в общий бандл, нет.
        inline = re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", markup, re.S)
        assert all(PUBLISHER not in chunk for chunk in inline), inline

    def test_the_public_env_prefix_is_refused(self):
        with pytest.raises(player.PublicPublisherIdError):
            player.assert_no_public_publisher_id(
                {"NEXT_PUBLIC_CDNVIDEOHUB_PUBLISHER_ID": "1"}
            )

    def test_the_stub_stays_a_stub_without_credentials(self):
        state = player.state({})
        assert state.placeholder
        assert state.status == player.BLOCKED_STATUS
        assert player.contract_check(state)["passed"] is False
