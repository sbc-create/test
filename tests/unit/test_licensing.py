"""REQ-DLE-LICENSE: одна лицензия = один домен второго уровня и его поддомены."""
import datetime as dt

import pytest

from factory import inventory, licensing
from factory.errors import BlockedLicense


@pytest.fixture
def licenses(monkeypatch):
    def install(entries):
        monkeypatch.setattr(inventory, "all_licenses", lambda: entries)
    return install


def test_registrable_domain():
    assert licensing.registrable_domain("example.ru") == "example.ru"
    assert licensing.registrable_domain("www.example.ru") == "example.ru"
    assert licensing.registrable_domain("a.b.example.ru") == "example.ru"
    assert licensing.registrable_domain("shop.example.co.uk") == "example.co.uk"
    assert licensing.registrable_domain("co.uk") is None, "публичный суффикс не является регистрируемым доменом"
    assert licensing.registrable_domain("localhost") is None


def test_no_license_blocks_production(licenses):
    licenses([])
    with pytest.raises(BlockedLicense) as exc:
        licensing.require_license("example.ru", license_ref=None, environment="production")
    assert exc.value.status == "BLOCKED_LICENSE"
    assert exc.value.required_input


def test_matching_license_allows_production(licenses):
    licenses([{"ref": "lic-1", "covered_domain": "example.ru", "covers_subdomains": True, "version": "20.0"}])
    result = licensing.require_license("www.example.ru", license_ref="lic-1", environment="production")
    assert result.covered


def test_license_for_another_domain_does_not_cover(licenses):
    licenses([{"ref": "lic-1", "covered_domain": "other.ru", "version": "20.0"}])
    assert not licensing.check_domain("example.ru", license_ref="lic-1").covered


def test_license_must_be_named_explicitly(licenses):
    """Подходящая чужая лицензия в инвентаре не покрывает сайт, который её не назвал."""
    licenses([{"ref": "lic-1", "covered_domain": "example.ru", "version": "20.0"}])
    result = licensing.check_domain("example.ru", license_ref=None)
    assert not result.covered
    assert "dle_license_ref" in result.reason


def test_subdomains_can_be_excluded(licenses):
    licenses([{"ref": "lic-1", "covered_domain": "example.ru", "covers_subdomains": False, "version": "20.0"}])
    assert licensing.check_domain("example.ru", license_ref="lic-1").covered
    assert not licensing.check_domain("shop.example.ru", license_ref="lic-1").covered


def test_expired_license_does_not_cover(licenses):
    licenses([{"ref": "lic-1", "covered_domain": "example.ru", "version": "20.0", "expires_at": "2020-01-01"}])
    result = licensing.check_domain("example.ru", license_ref="lic-1", today=dt.date(2026, 8, 21))
    assert not result.covered and "истек" in result.reason.lower()


def test_license_for_other_version_does_not_cover(licenses):
    licenses([{"ref": "lic-1", "covered_domain": "example.ru", "version": "19.0"}])
    assert not licensing.check_domain("example.ru", license_ref="lic-1").covered


def test_unresolvable_suffix_is_not_treated_as_covered(licenses):
    licenses([{"ref": "lic-1", "covered_domain": "localhost", "version": "20.0"}])
    assert not licensing.check_domain("localhost", license_ref="lic-1").covered


def test_staging_is_not_blocked_by_missing_license(licenses):
    licenses([])
    assert licensing.require_license("example.ru", license_ref=None, environment="staging").covered is False
