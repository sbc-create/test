"""REQ-ENVSEP, REQ-ADS: mock технически невозможен в production."""
import pytest

from factory.ads import DisabledAds, MockAds, OfficialAds, build_ads
from factory.errors import BlockedRights
from factory.vk import (
    AVAILABLE,
    UNAVAILABLE,
    DisabledPlayer,
    MockPlayer,
    OfficialPlayer,
    build_player,
)


def _pkg(environment="staging", **vk):
    return {"environment": environment, "vk_video": {"enabled": True, "adapter": "mock", **vk}}


def test_mock_player_is_refused_in_production():
    with pytest.raises(BlockedRights):
        build_player(_pkg("production"))


def test_mock_ads_are_refused_in_production():
    package = {"environment": "production", "advertising": {"enabled": True, "adapter": "mock", "placements": []}}
    with pytest.raises(BlockedRights):
        build_ads(package)


def test_mock_player_allowed_on_staging():
    assert isinstance(build_player(_pkg("staging")), MockPlayer)


def test_official_player_requires_contract():
    with pytest.raises(BlockedRights) as exc:
        build_player(_pkg("production", adapter="official"), contract=None)
    assert "contract" in exc.value.required_input.lower()


def test_official_ads_require_contract():
    package = {"environment": "production", "advertising": {"enabled": True, "adapter": "official", "placements": []}}
    with pytest.raises(BlockedRights):
        build_ads(package, contract=None)


def test_disabled_by_default():
    assert isinstance(build_player({"environment": "staging"}), DisabledPlayer)
    assert isinstance(build_ads({"environment": "staging"}), DisabledAds)


def test_mock_never_authorises_video_object():
    """Заглушка не является видимым видео: VideoObject запрещён (HR-6)."""
    player = MockPlayer({"v1": {"availability": AVAILABLE}})
    descriptor = player.resolve("v1")
    assert descriptor.availability == AVAILABLE
    assert player.embed_html(descriptor)
    assert player.may_emit_video_object(descriptor) is False


def test_unavailable_video_produces_no_embed():
    player = MockPlayer({"v1": {"availability": UNAVAILABLE}})
    assert player.embed_html(player.resolve("v1")) == ""


def test_official_player_refuses_without_embed_template():
    player = OfficialPlayer({"catalog": {"v1": {"availability": AVAILABLE}}})
    with pytest.raises(BlockedRights):
        player.embed_html(player.resolve("v1"))


def test_official_player_uses_only_contract_template():
    contract = {"embed_template": '<iframe src="https://player.example/{video_ref}"></iframe>',
                "catalog": {"v1": {"availability": AVAILABLE, "allowed_fields": {"duration": "PT10M"}}},
                "allows_video_object": True}
    player = OfficialPlayer(contract)
    descriptor = player.resolve("v1")
    html = player.embed_html(descriptor)
    assert "player.example/v1" in html
    assert player.may_emit_video_object(descriptor) is True
    assert descriptor.allowed_fields == {"duration": "PT10M"}, "поля берутся только из contract"


def test_official_ads_refuse_unknown_placement():
    contract = {"slot_templates": {"known": "<div></div>"}, "allowed_events": ["impression"]}
    ads = OfficialAds(contract, [{"placement_id": "unknown", "page_types": ["episode"], "reserved_size": {"height": 250}}])
    with pytest.raises(BlockedRights):
        ads.slots("episode")


def test_mock_ads_reserve_size_without_external_scripts():
    ads = MockAds([{"placement_id": "p1", "page_types": ["episode"], "reserved_size": {"height": 300}}])
    slots = ads.slots("episode")
    assert slots and slots[0].height == 300
    assert "script" not in slots[0].html.lower()
    assert ads.allowed_events() == [], "события не выдумываются без contract"
