"""REQ-SEO-URL: единая политика URL зафиксирована тестом."""
import re

from factory import validation
from factory.seo import matrix as matrix_mod


def test_package_policy_matches_matrix(pilot_package):
    policy = pilot_package["metadata"]["canonical_policy"]
    url_policy = matrix_mod.url_policy()
    assert policy["scheme"] == url_policy["scheme"] == "https"
    assert policy["host_form"] == url_policy["host_form"]
    assert policy["trailing_slash"] == url_policy["trailing_slash"]
    assert policy["case"] == "lower"


def test_canonical_url_follows_policy(pilot_package):
    canonical = pilot_package["canonical_url"]
    assert canonical.startswith("https://")
    assert canonical.endswith("/")
    assert canonical == canonical.lower()
    assert pilot_package["domain"] in canonical


def test_tracking_parameters_are_forbidden_in_urls():
    forbidden = set(matrix_mod.url_policy()["forbidden_in_url"])
    assert {"utm_source", "gclid", "yclid", "fbclid", "session_id"} <= forbidden


def test_url_templates_are_lowercase_with_dashes(pilot_package):
    for template in pilot_package["seo"]["url_templates"].values():
        stripped = re.sub(r"\{[a-z_]+\}", "", template)
        assert stripped == stripped.lower(), template
        assert "_" not in stripped, "слова разделяются дефисом, не подчёркиванием"


def test_query_parameter_normalisation_is_declared():
    normalisation = matrix_mod.load()["query_parameters"]["normalization"]
    assert normalisation["sort_keys"] is True
    assert normalisation["reject_repeated_keys"] is True
    assert normalisation["reject_unknown_keys"] is True


def test_mixed_pagination_schemes_are_rejected(temp_site):
    site = temp_site(lambda p: p["seo"].__setitem__("pagination_template", "?page={n}"))
    assert validation.validate(site).status == "BLOCKED_SEO"
