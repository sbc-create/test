"""REQ-SEO-META, REQ-SEO-SD, REQ-SEO-BLOCK, REQ-SEO-SITEMAP: линтер ловит внесённые дефекты."""
import json
import re
import shutil

import pytest

from factory import build as build_mod
from factory.seo.lint import lint


@pytest.fixture(scope="module")
def built():
    return build_mod.build("pilot-local")


@pytest.fixture
def sandbox(built, tmp_path):
    target = tmp_path / "build"
    shutil.copytree(built.output, target)
    return target


def criticals(build_dir, environment="staging"):
    return [f for f in lint(build_dir, environment=environment).findings if f.severity == "critical"]


def test_clean_build_passes(sandbox):
    assert criticals(sandbox) == []


def test_missing_canonical_is_critical(sandbox):
    page = sandbox / "public" / "lekcii" / "material-01" / "index.html"
    page.write_text(re.sub(r'<link rel="canonical"[^>]*>\n?', "", page.read_text(encoding="utf-8")), encoding="utf-8")
    findings = criticals(sandbox)
    assert any(f.check == "canonical" and f.rule == "HR-1" for f in findings)


def test_canonical_pointing_elsewhere_is_critical(sandbox):
    page = sandbox / "public" / "lekcii" / "material-01" / "index.html"
    text = page.read_text(encoding="utf-8")
    page.write_text(re.sub(r'(<link rel="canonical" href=")[^"]+(")', r"\1https://pilot.localhost.test/other/\2", text), encoding="utf-8")
    assert any(f.check == "canonical" for f in criticals(sandbox))


def test_duplicate_title_is_critical(sandbox):
    first = (sandbox / "public" / "lekcii" / "material-01" / "index.html").read_text(encoding="utf-8")
    title = re.search(r"<title>(.*?)</title>", first, re.S).group(1)
    second = sandbox / "public" / "lekcii" / "material-02" / "index.html"
    text = re.sub(r"<title>.*?</title>", f"<title>{title}</title>", second.read_text(encoding="utf-8"), flags=re.S)
    second.write_text(text, encoding="utf-8")
    assert any(f.check == "duplicate-title" for f in criticals(sandbox))


def test_multiple_h1_is_critical(sandbox):
    page = sandbox / "public" / "lekcii" / "material-01" / "index.html"
    page.write_text(page.read_text(encoding="utf-8").replace("</main>", "<h1>Второй заголовок</h1></main>"), encoding="utf-8")
    assert any(f.check == "h1" for f in criticals(sandbox))


def test_video_object_without_player_is_critical(sandbox):
    page = sandbox / "public" / "lekcii" / "material-01" / "index.html"
    text = page.read_text(encoding="utf-8").replace(
        "</head>", '<script type="application/ld+json">{"@type":"VideoObject","name":"x"}</script></head>')
    page.write_text(text.replace('class="player-frame', 'class="was-player'), encoding="utf-8")
    findings = criticals(sandbox)
    assert any(f.check == "jsonld" and f.rule == "HR-6" for f in findings)


def test_broken_jsonld_is_critical(sandbox):
    page = sandbox / "public" / "index.html"
    page.write_text(page.read_text(encoding="utf-8").replace(
        "</head>", '<script type="application/ld+json">{ not json }</script></head>'), encoding="utf-8")
    assert any(f.check == "jsonld" for f in criticals(sandbox))


def test_noindex_url_in_sitemap_is_critical(sandbox):
    routes = json.loads((sandbox / "routes.json").read_text(encoding="utf-8"))
    for route in routes["routes"]:
        if route["path"] == "/search/":
            route["in_sitemap"] = True
    (sandbox / "routes.json").write_text(json.dumps(routes, ensure_ascii=False), encoding="utf-8")
    assert any(f.check == "sitemap" and f.rule == "HR-3" for f in criticals(sandbox))


def test_indexable_page_with_noindex_is_critical(sandbox):
    page = sandbox / "public" / "lekcii" / "material-01" / "index.html"
    page.write_text(page.read_text(encoding="utf-8").replace(
        '<meta name="robots" content="index,follow">', '<meta name="robots" content="noindex,follow">'), encoding="utf-8")
    assert any(f.check == "robots" for f in criticals(sandbox))


def test_empty_indexable_page_is_soft_404(sandbox):
    page = sandbox / "public" / "lekcii" / "material-01" / "index.html"
    text = re.sub(r"<main[^>]*>.*?</main>", '<main id="main"><h1>.</h1></main>', page.read_text(encoding="utf-8"), flags=re.S)
    page.write_text(text, encoding="utf-8")
    assert any(f.check == "soft404" for f in criticals(sandbox)), \
        "пустая индексируемая страница обязана ловиться именно как soft 404"


def test_pagination_without_links_is_critical(sandbox):
    page = sandbox / "public" / "lekcii" / "page" / "2" / "index.html"
    page.write_text(re.sub(r'<nav class="pagination".*?</nav>', "", page.read_text(encoding="utf-8"), flags=re.S), encoding="utf-8")
    assert any(f.check == "pagination" and f.rule == "HR-5" for f in criticals(sandbox))


def test_orphan_indexable_page_is_critical(sandbox):
    """Убираем все ссылки на материал — он обязан быть найден как orphan."""
    for path in (sandbox / "public").rglob("index.html"):
        text = path.read_text(encoding="utf-8")
        if "/lekcii/material-05/" in text and "material-05/index.html" not in str(path):
            path.write_text(text.replace('href="/lekcii/material-05/"', 'href="/lekcii/"'), encoding="utf-8")
    assert any(f.check == "orphan" and f.rule == "HR-7" for f in criticals(sandbox))


def test_staging_markers_are_critical_in_production_build(sandbox):
    findings = [f for f in lint(sandbox, environment="production").findings if f.check == "production-purity"]
    assert findings, "маркеры staging/localhost в production-сборке обязаны блокировать публикацию"


def test_non_canonical_internal_link_is_critical(sandbox):
    """Ссылка в другом регистре или без слэша — это лишний 301 внутри сайта."""
    page = sandbox / "public" / "index.html"
    page.write_text(page.read_text(encoding="utf-8").replace('href="/lekcii/"', 'href="/Lekcii"', 1), encoding="utf-8")
    findings = criticals(sandbox)
    assert any(f.check == "link-canonicality" for f in findings)


def test_tracking_parameter_in_internal_link_is_critical(sandbox):
    page = sandbox / "public" / "index.html"
    page.write_text(page.read_text(encoding="utf-8").replace('href="/lekcii/"', 'href="/lekcii/?utm_source=nav"', 1), encoding="utf-8")
    assert any(f.check == "link-canonicality" for f in criticals(sandbox))


def test_hreflang_without_self_reference_is_critical(sandbox):
    page = sandbox / "public" / "lekcii" / "material-01" / "index.html"
    page.write_text(page.read_text(encoding="utf-8").replace(
        "</head>", '<link rel="alternate" hreflang="en" href="https://pilot.localhost.test/en/">\n</head>'), encoding="utf-8")
    assert any(f.check == "hreflang" for f in criticals(sandbox))


def test_future_lastmod_is_reported(sandbox):
    import json
    routes = json.loads((sandbox / "routes.json").read_text(encoding="utf-8"))
    for route in routes["routes"]:
        if route["page_type"] == "title":
            route["lastmod"] = "2099-01-01"
            break
    (sandbox / "routes.json").write_text(json.dumps(routes, ensure_ascii=False), encoding="utf-8")
    from factory.seo.lint import lint
    assert any(f.check == "lastmod" for f in lint(sandbox).findings)


# --- REQ-SEO-SITEMAP: содержимое собранного sitemap проверяется, а не только его наличие ---

def test_sitemap_is_built_even_for_staging(built):
    """Раньше на staging sitemap не собирался, и правило HR-3 не проверялось ни разу."""
    preview = built.output / "sitemap-preview" / "sitemap.xml"
    public = built.output / "public" / "sitemap.xml"
    assert preview.exists(), "sitemap обязан собираться всегда"
    assert not public.exists(), "но публиковаться на staging он не должен"


def test_sitemap_contains_only_canonical_indexable_200(built, sandbox):
    import json as _json
    routes = {r["path"]: r for r in _json.loads((sandbox / "routes.json").read_text(encoding="utf-8"))["routes"]}
    import re as _re
    import urllib.parse as _url
    for sitemap in (sandbox / "sitemap-preview").glob("sitemap-*.xml"):
        for loc in _re.findall(r"<loc>([^<]+)</loc>", sitemap.read_text(encoding="utf-8")):
            route = routes[_url.urlparse(loc).path]
            assert route["indexable"] and route["status"] == 200
            assert route["canonical"] == loc


def test_noindex_url_in_sitemap_is_critical(sandbox):
    sitemap = sandbox / "sitemap-preview" / "sitemap-home.xml"
    sitemap.write_text(sitemap.read_text(encoding="utf-8").replace(
        "</urlset>", "  <url><loc>https://pilot.localhost.test/search/</loc></url>\n</urlset>"), encoding="utf-8")
    assert any(f.check == "sitemap" and f.rule == "HR-3" for f in criticals(sandbox))


def test_missing_sitemap_is_critical(sandbox):
    import shutil as _shutil
    _shutil.rmtree(sandbox / "sitemap-preview")
    assert any(f.check == "sitemap" for f in criticals(sandbox))


def test_sitemap_missing_indexable_url_is_critical(sandbox):
    import re as _re
    sitemap = next((sandbox / "sitemap-preview").glob("sitemap-category.xml"))
    text = sitemap.read_text(encoding="utf-8")
    first = _re.search(r"  <url>.*?</url>\n", text, _re.S).group(0)
    sitemap.write_text(text.replace(first, ""), encoding="utf-8")
    assert any(f.check == "sitemap" for f in criticals(sandbox))
