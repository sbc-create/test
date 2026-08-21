"""REQ-SEO-META, REQ-SEO-SD, REQ-SEO-BLOCK: линтер ловит внесённые дефекты."""
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
    findings = criticals(sandbox)
    assert any(f.check in ("soft404", "h1") for f in findings)


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
