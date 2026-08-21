"""REQ-CONTENT, REQ-VK-UNAVAILABLE, REQ-SEO-QUALITY: контент не выдумывается."""
import json
import shutil

import pytest

from factory import build as build_mod
from factory.paths import PATHS


@pytest.fixture(scope="module")
def built():
    return build_mod.build("pilot-local")


def test_material_without_alt_is_not_published(built):
    """Отсутствующий alt снимает материал с публикации, а не заменяется умолчанием."""
    reasons = {skip["id"]: skip["reason"] for skip in built.skipped}
    assert "fx-noalt" in reasons
    assert "alt" in reasons["fx-noalt"].lower()
    routes = json.loads((built.output / "routes.json").read_text(encoding="utf-8"))
    paths = {route["path"] for route in routes["routes"]}
    assert "/lekcii/material-bez-alt/" not in paths


def test_empty_category_is_not_published_as_indexable_200(built):
    routes = json.loads((built.output / "routes.json").read_text(encoding="utf-8"))
    paths = {route["path"] for route in routes["routes"]}
    assert "/arhiv/" not in paths, "пустой раздел не публикуется (запрет soft 404)"
    assert any(skip["id"] == "/arhiv/" for skip in built.skipped)


def test_unavailable_video_renders_status_not_substitute(built):
    page = built.output / "public" / "praktikum" / "serial-fikstura" / "season-1" / "episode-3" / "index.html"
    html = page.read_text(encoding="utf-8")
    assert 'class="availability"' in html, "должно быть контролируемое состояние недоступности"
    assert 'class="player-frame"' not in html, "плеер не показывается для недоступного видео"
    assert "VideoObject" not in html, "VideoObject запрещён без видимого видео"


def test_available_video_renders_player(built):
    page = built.output / "public" / "praktikum" / "serial-fikstura" / "season-1" / "episode-1" / "index.html"
    html = page.read_text(encoding="utf-8")
    assert 'class="player-frame' in html


def test_no_placeholder_or_lorem_ipsum(built):
    forbidden = ("lorem ipsum", "todo:", "заглушка текста", "placeholder text")
    for path in (built.output / "public").rglob("index.html"):
        text = path.read_text(encoding="utf-8").lower()
        for marker in forbidden:
            assert marker not in text, f"{path}: найден {marker}"


def test_every_published_image_has_alt(built):
    import re
    for path in (built.output / "public").rglob("index.html"):
        for tag in re.findall(r"<img\s[^>]*>", path.read_text(encoding="utf-8")):
            alt = re.search(r'alt="([^"]*)"', tag)
            assert alt and alt.group(1).strip(), f"{path}: изображение без alt — {tag[:80]}"


def test_images_declare_dimensions(built):
    import re
    for path in (built.output / "public").rglob("index.html"):
        for tag in re.findall(r"<img\s[^>]*>", path.read_text(encoding="utf-8")):
            assert 'width="' in tag and 'height="' in tag, f"{path}: изображение без размеров — {tag[:80]}"


def test_related_links_come_only_from_package_relations(built):
    catalog = json.loads((PATHS.sites / "pilot-local" / "content" / "catalog.json").read_text(encoding="utf-8"))
    by_id = {item["id"]: item for item in catalog["titles"]}
    item = by_id["fx-005"]
    expected = {f"/{by_id[rid]['category']}/{by_id[rid]['slug']}/" for rid in item.get("related", []) if rid in by_id}
    html = (built.output / "public" / item["category"] / item["slug"] / "index.html").read_text(encoding="utf-8")
    import re
    section = re.search(r'<h2 id="related-heading">.*?</section>', html, re.S)
    if section:
        found = set(re.findall(r'href="([^"]+)"', section.group(0)))
        assert found <= expected, "в «связанных» не может быть ничего, кроме переданных отношений"


def test_no_brand_mimicry_markers(built):
    """Мимикрия под VK/правообладателя запрещена: бренд берётся из пакета."""
    home = (built.output / "public" / "index.html").read_text(encoding="utf-8")
    for marker in ("vk.com", "вконтакте", "official vk", "vk video"):
        assert marker not in home.lower(), f"мимикрия под чужой бренд: {marker}"


def test_pages_are_not_empty_shells_around_player(built):
    import re
    page = (built.output / "public" / "praktikum" / "serial-fikstura" / "season-1" / "episode-1" / "index.html").read_text(encoding="utf-8")
    body = re.search(r"<main[^>]*>(.*?)</main>", page, re.S).group(1)
    text = re.sub(r"<[^>]+>", " ", body)
    assert "хлебные крошки" not in text.lower()
    assert len(re.sub(r"\s+", " ", text).strip()) > 100, "страница обязана давать контекст, а не быть оболочкой плеера"
    assert 'class="sequence"' in page, "должна быть навигация по эпизодам"
