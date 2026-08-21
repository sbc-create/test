"""REQ-SEO-LINKS: живой обход доказывает связность и эквивалентность контента."""
import pytest

from factory import build as build_mod, inventory
from factory.seo.crawl import Crawler, crawl
from factory.targets import build_target


@pytest.fixture(scope="module")
def live(pilot_package):
    target = build_target(inventory.target(pilot_package["target_ref"]), pilot_package)
    built = build_mod.build("pilot-local")
    target.deploy(built.output, built.build_id)
    return target.base_url(), target.staging_credentials(), built


@pytest.mark.slow
def test_crawl_finds_no_critical_issues(live):
    base, auth, built = live
    report = crawl(base, built.output, auth=auth, environment="staging")
    assert report.passed, [f"{f.check}: {f.url} — {f.message}" for f in report.critical]


@pytest.mark.slow
def test_all_indexable_pages_are_reachable_by_links(live):
    base, auth, built = live
    report = crawl(base, built.output, auth=auth, environment="staging")
    orphans = [f for f in report.findings if f.check == "orphan"]
    assert not orphans, f"недостижимые страницы: {[f.url for f in orphans]}"


@pytest.mark.slow
def test_crawl_depth_within_budget(live):
    base, auth, built = live
    report = crawl(base, built.output, auth=auth, environment="staging")
    assert report.counts["max_depth"] <= 4
    assert report.counts["fetched"] > 20


@pytest.mark.slow
def test_no_broken_internal_links(live):
    base, auth, built = live
    report = crawl(base, built.output, auth=auth, environment="staging")
    broken = [f for f in report.findings if f.check == "broken-link"]
    assert not broken, [f.url for f in broken]


@pytest.mark.slow
def test_mobile_and_desktop_receive_the_same_markup(live):
    """Эквивалентность основного контента: клоакинг и раздельные версии запрещены."""
    base, auth, _ = live
    crawler = Crawler(base, auth=auth)
    desktop = crawler.fetch("/lekcii/")
    request_ua = "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/120 Mobile Safari/537.36"
    import base64, urllib.request
    req = urllib.request.Request(base + "/lekcii/", headers={"User-Agent": request_ua})
    req.add_header("Authorization", "Basic " + base64.b64encode(auth.encode()).decode())
    with urllib.request.urlopen(req, timeout=10) as response:
        mobile = response.read().decode("utf-8")
    assert desktop.body == mobile, "робот и мобильный пользователь обязаны получать один и тот же HTML"


@pytest.mark.slow
def test_googlebot_receives_the_same_content(live):
    base, auth, _ = live
    import base64, urllib.request
    bodies = []
    for ua in ("factory-seo-crawler/1.0", "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"):
        req = urllib.request.Request(base + "/", headers={"User-Agent": ua})
        req.add_header("Authorization", "Basic " + base64.b64encode(auth.encode()).decode())
        with urllib.request.urlopen(req, timeout=10) as response:
            bodies.append(response.read().decode("utf-8"))
    assert bodies[0] == bodies[1], "подмена контента для робота запрещена"
