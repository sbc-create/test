"""REQ-EXPOSURE, REQ-SEO-SITEMAP: закрытость служебных путей и staging."""
import base64
import urllib.error
import urllib.request

import pytest

from factory import build as build_mod, inventory
from factory.paths import PATHS
from factory.targets import build_target
from factory.verify import security_smoke


@pytest.fixture(scope="module")
def live(pilot_package):
    target = build_target(inventory.target(pilot_package["target_ref"]), pilot_package)
    built = build_mod.build("pilot-local")
    target.deploy(built.output, built.build_id)
    return target, target.base_url(), target.staging_credentials()


def _get(url, auth=""):
    request = urllib.request.Request(url)
    if auth:
        request.add_header("Authorization", "Basic " + base64.b64encode(auth.encode()).decode())
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, dict(response.headers), response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers), ""


@pytest.mark.slow
def test_security_smoke_passes(live):
    target, base, auth = live
    report = security_smoke(base, PATHS.artifact_dir("qa", "pilot-local"), auth=auth, environment="staging")
    assert report.passed, [f.message for f in report.critical]


@pytest.mark.slow
@pytest.mark.parametrize("path", ["/.env", "/routes.json", "/build-manifest.json", "/.git/config",
                                  "/shared/logs/php-server.log", "/install.php"])
def test_service_paths_are_not_public(live, path):
    _, base, auth = live
    status, _, _ = _get(base + path, auth)
    assert status in (401, 403, 404), f"{path} доступен (HTTP {status})"


@pytest.mark.slow
def test_staging_requires_authentication(live):
    _, base, _ = live
    status, headers, _ = _get(base + "/")
    assert status == 401
    assert "Basic" in headers.get("WWW-Authenticate", "")


@pytest.mark.slow
def test_staging_sends_noindex_header(live):
    _, base, auth = live
    _, headers, _ = _get(base + "/", auth)
    assert "noindex" in headers.get("X-Robots-Tag", "")


@pytest.mark.slow
def test_staging_publishes_no_sitemap(live):
    _, base, auth = live
    status, _, _ = _get(base + "/sitemap.xml", auth)
    assert status == 404, "staging-URL не должны попадать в индекс через sitemap"


@pytest.mark.slow
def test_security_headers_present(live):
    _, base, auth = live
    _, headers, _ = _get(base + "/", auth)
    for header in ("X-Content-Type-Options", "X-Frame-Options", "Referrer-Policy", "Content-Security-Policy"):
        assert headers.get(header), f"нет заголовка {header}"
    assert not headers.get("X-Powered-By")


@pytest.mark.slow
def test_directory_listing_disabled(live):
    _, base, auth = live
    status, _, body = _get(base + "/assets/", auth)
    assert "Index of" not in body
