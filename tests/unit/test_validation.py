"""REQ-MODE-B, REQ-VK-RIGHTS, REQ-SEO-FACETS: семантические блокеры."""

from factory import validation


def test_pilot_package_is_ready():
    assert validation.validate("pilot-local").status == "READY"


def test_missing_package_gives_blocked_input():
    result = validation.validate("no-such-site")
    assert result.status == "BLOCKED_INPUT"
    assert result.blockers[0].required_input


def test_empty_required_field_is_not_defaulted(temp_site):
    site = temp_site(lambda p: p.__setitem__("domain", ""))
    result = validation.validate(site)
    assert result.status == "BLOCKED_INPUT"
    assert any("domain" in b.field for b in result.blockers)


def test_unknown_target_is_blocked_access(temp_site):
    site = temp_site(lambda p: p.__setitem__("target_ref", "nowhere"))
    result = validation.validate(site)
    assert result.status == "BLOCKED_ACCESS"


def test_canonical_host_mismatch_is_blocked_seo(temp_site):
    site = temp_site(lambda p: p.__setitem__("canonical_url", "https://other.example.test/"))
    result = validation.validate(site)
    assert result.status == "BLOCKED_SEO"
    assert any(b.field == "canonical_url" for b in result.blockers)


def test_pagination_scheme_must_match_matrix(temp_site):
    site = temp_site(lambda p: p["seo"].__setitem__("pagination_template", "?page={n}"))
    result = validation.validate(site)
    assert result.status == "BLOCKED_SEO"


def test_non_indexable_parameters_must_cover_matrix(temp_site):
    site = temp_site(lambda p: p["seo"].__setitem__("non_indexable_parameters", ["sort"]))
    result = validation.validate(site)
    assert result.status == "BLOCKED_SEO"
    assert any("non_indexable_parameters" in b.field for b in result.blockers)


def test_unknown_page_type_in_acceptance_is_blocked(temp_site):
    def mutate(package):
        package["acceptance"]["routes"][0]["page_type"] = "invented_type"
    site = temp_site(mutate)
    assert validation.validate(site).status == "BLOCKED_SEO"


def test_vk_enabled_without_contract_is_blocked_rights(temp_site):
    site = temp_site(lambda p: p["vk_video"].__setitem__("contract_ref", None))
    result = validation.validate(site)
    assert result.status == "BLOCKED_RIGHTS"


def test_missing_vk_contract_file_is_blocked_rights(temp_site):
    site = temp_site(lambda p: p["vk_video"].__setitem__("contract_ref", "content/absent.yaml"))
    assert validation.validate(site).status == "BLOCKED_RIGHTS"


def test_catalog_checksum_mismatch_is_blocked_rights(temp_site):
    site = temp_site(lambda p: p["content_source"].__setitem__("catalog_sha256", "0" * 64))
    result = validation.validate(site)
    assert result.status == "BLOCKED_RIGHTS"
    assert any("catalog_sha256" in b.field for b in result.blockers)


def test_missing_legal_document_file_is_blocked_input(temp_site):
    def mutate(package):
        package["legal"]["documents"][0]["body_ref"] = "legal/absent.md"
    site = temp_site(mutate)
    result = validation.validate(site)
    assert result.status == "BLOCKED_INPUT"


def test_secret_given_as_literal_value_is_blocked_secret(temp_site):
    def mutate(package):
        package["advertising"] = {"enabled": True, "provider": "vk_adman_adtech", "adapter": "mock",
                                  "contract_ref": "content/vk-player-contract.fixture.yaml",
                                  "placements": [{"placement_id": "p1", "page_types": ["episode"], "reserved_size": {"height": 250}}],
                                  "policy_refs": [], "secret_ref": "raw-token-value"}
    site = temp_site(mutate)
    result = validation.validate(site)
    assert result.status == "BLOCKED_SECRET"


def test_unresolvable_secret_ref_is_blocked_secret(temp_site, monkeypatch):
    monkeypatch.delenv("FACTORY_TEST_ADS_TOKEN", raising=False)

    def mutate(package):
        package["advertising"] = {"enabled": True, "provider": "vk_adman_adtech", "adapter": "mock",
                                  "contract_ref": "content/vk-player-contract.fixture.yaml",
                                  "placements": [{"placement_id": "p1", "page_types": ["episode"], "reserved_size": {"height": 250}}],
                                  "policy_refs": [], "secret_ref": "env:FACTORY_TEST_ADS_TOKEN"}
    site = temp_site(mutate)
    assert validation.validate(site).status == "BLOCKED_SECRET"


def test_wildcard_network_allowlist_is_rejected(temp_site):
    site = temp_site(lambda p: p.__setitem__("network_allowlist", ["*"]))
    assert validation.validate(site).status == "BLOCKED_ACCESS"


def test_cross_site_verification_id_leak_is_detected(temp_site):
    shared = "google-site-verification=SHARED-ID-EXAMPLE"
    first = temp_site(lambda p: p["seo"].__setitem__("webmaster_verification_refs", {"google_search_console": shared}))
    second = temp_site(lambda p: p["seo"].__setitem__("webmaster_verification_refs", {"google_search_console": shared}))
    result = validation.validate(second)
    assert any("cross-site" in b.reason.lower() or "верификац" in b.reason.lower() for b in result.blockers), \
        f"утечка verification ID между {first} и {second} обязана быть найдена"


def test_alias_duplicate_is_rejected(temp_site):
    site = temp_site(lambda p: p.__setitem__("aliases", [p["domain"]]))
    assert validation.validate(site).status == "BLOCKED_INPUT"
