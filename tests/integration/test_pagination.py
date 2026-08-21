"""REQ-SEO-PAGINATION: пагинация доступна без JS и не даёт дублей."""
import base64
import json
import re
import urllib.error
import urllib.request

import pytest

from factory import build as build_mod, inventory
from factory.targets import build_target


@pytest.fixture(scope="module")
def live(pilot_package):
    target = build_target(inventory.target(pilot_package["target_ref"]), pilot_package)
    built = build_mod.build("pilot-local")
    target.deploy(built.output, built.build_id)
    return target.base_url(), target.staging_credentials(), built


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def _get(url, auth="", follow=False):
    opener = urllib.request.build_opener() if follow else urllib.request.build_opener(_NoRedirect)
    request = urllib.request.Request(url)
    if auth:
        request.add_header("Authorization", "Basic " + base64.b64encode(auth.encode()).decode())
    try:
        with opener.open(request, timeout=10) as response:
            return response.status, dict(response.headers), response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers), exc.read().decode("utf-8", "replace")


@pytest.mark.slow
def test_page_two_opens_directly(live):
    base, auth, _ = live
    status, _, body = _get(f"{base}/lekcii/page/2/", auth)
    assert status == 200
    assert '<li class="card">' in body


@pytest.mark.slow
def test_page_one_duplicate_redirects_once(live):
    base, auth, _ = live
    status, headers, _ = _get(f"{base}/lekcii/page/1/", auth)
    assert status == 301
    location = headers["Location"]
    assert location.endswith("/lekcii/")
    second_status, _, _ = _get(base + location, auth)
    assert second_status == 200, "цепочки редиректов быть не должно"


@pytest.mark.slow
def test_out_of_range_page_is_404(live):
    base, auth, _ = live
    for path in ("/lekcii/page/999/", "/lekcii/page/0/", "/lekcii/page/abc/"):
        status, _, _ = _get(base + path, auth)
        assert status == 404, f"{path} обязан отдавать 404, а не копию первой страницы"


@pytest.mark.slow
def test_each_page_has_self_canonical(live):
    base, auth, _ = live
    for path in ("/lekcii/", "/lekcii/page/2/"):
        _, _, body = _get(base + path, auth)
        canonical = re.search(r'<link rel="canonical" href="([^"]+)"', body).group(1)
        assert canonical.endswith(path), f"{path}: canonical={canonical} (не self)"


@pytest.mark.slow
def test_pagination_is_linked_with_real_anchors(live):
    base, auth, _ = live
    _, _, body = _get(f"{base}/lekcii/", auth)
    links = re.findall(r'<nav class="pagination".*?</nav>', body, re.S)
    assert links, "нет блока пагинации"
    assert re.search(r'<a[^>]+href="/lekcii/page/2/"', links[0]), "следующая страница обязана быть обычной ссылкой"


@pytest.mark.slow
def test_no_duplicate_or_missing_items_across_pages(live):
    base, auth, built = live
    seen = []
    for path in ("/lekcii/", "/lekcii/page/2/"):
        _, _, body = _get(base + path, auth)
        seen.extend(re.findall(r'<a class="card-link" href="([^"]+)"', body))
    assert len(seen) == len(set(seen)), "карточка не должна встречаться на двух страницах"
    routes = json.loads((built.output / "routes.json").read_text(encoding="utf-8"))
    titles = {r["path"] for r in routes["routes"] if r["page_type"] in ("title", "content_unavailable") and r["path"].startswith("/lekcii/")}
    assert set(seen) == titles, "порядок детерминирован, ни одна карточка не теряется между страницами"


@pytest.mark.slow
def test_pagination_titles_are_unique(live):
    base, auth, _ = live
    titles = []
    for path in ("/lekcii/", "/lekcii/page/2/"):
        _, _, body = _get(base + path, auth)
        titles.append(re.search(r"<title>(.*?)</title>", body, re.S).group(1))
    assert len(set(titles)) == len(titles)
    assert "страница 2" in titles[1].lower()
