"""Файл заданий на изображения блюд и приём сгенерированных файлов (22.10.2026)."""

import argparse
import json

import pytest

from fooddaily import media
from fooddaily.views import Site


def test_jobs_cover_every_recipe_without_image_and_come_from_recipe(tmp_path, monkeypatch):
    monkeypatch.setattr(media, "JOBS", tmp_path / "image-jobs.json")
    media.jobs()
    spec = json.loads((tmp_path / "image-jobs.json").read_text())
    site = Site()
    want = {r.slug for r in site.recipes if not r.image}
    assert {j["slug"] for j in spec["jobs"]} == want and spec["site"] == site.cfg["site_id"]
    for j in spec["jobs"]:
        r = site.by_slug[j["slug"]]
        assert (
            j["title"] == r.title and j["url"] == r.url and j["file"] == f"{r.slug}.jpg" and j["kind"] == "illustration"
        )
        assert all(n.lower() in j["prompt"] for n in j["ingredients"][:8]) and r.title in j["prompt"]
        assert j["alt"].startswith(r.title) and j["look"]
        # без выдуманного: ни оценок, ни калорий, ни людей в кадре
        assert not any(w in j["prompt"].lower() for w in ("рейтинг", "ккал", "калори", "звезд"))


def test_intake_requires_tool_and_basis(tmp_path):
    for tool, lic in ((None, "x"), ("x", None), ("  ", "x")):
        with pytest.raises(SystemExit, match="BLOCKED_INPUT"):
            media.intake(argparse.Namespace(dir=tmp_path, tool=tool, license=lic))


def test_intake_adds_generated_file_as_illustration(tmp_path, monkeypatch):
    from PIL import Image

    site = Site()
    r = next(x for x in site.recipes if not x.image)
    jobs = tmp_path / "jobs.json"
    jobs.write_text(json.dumps({"jobs": [media.job(site, r)]}, ensure_ascii=False))
    reg = tmp_path / "images.json"
    reg.write_text('{"items": {}}')
    monkeypatch.setattr(media, "JOBS", jobs)
    monkeypatch.setattr(media, "REGISTRY", reg)
    monkeypatch.setattr(media, "OUT", tmp_path / "out")
    inc = tmp_path / "in"
    inc.mkdir()
    Image.new("RGB", (1600, 1000), (180, 120, 60)).save(inc / f"{r.slug}.jpg")
    res = media.intake(argparse.Namespace(dir=inc, tool="генератор X 1.0", license="лицензия генератора"))
    assert res == {"added": [r.slug], "missing": [], "rejected": {}}
    e = json.loads(reg.read_text())["items"][r.slug]
    assert e["kind"] == "illustration" and e["source"].startswith("сгенерировано: генератор X 1.0")
    assert (e["width"], e["height"]) == (1200, 900) and (tmp_path / "out" / f"{r.slug}-400.webp").is_file()


def _setup(tmp_path, monkeypatch, n=3):
    site = Site()
    rs = [x for x in site.recipes if not x.image][:n]
    jobs = tmp_path / "jobs.json"
    jobs.write_text(json.dumps({"jobs": [media.job(site, r) for r in rs]}, ensure_ascii=False))
    reg = tmp_path / "images.json"
    reg.write_text('{"items": {}}')
    monkeypatch.setattr(media, "JOBS", jobs)
    monkeypatch.setattr(media, "REGISTRY", reg)
    monkeypatch.setattr(media, "OUT", tmp_path / "out")
    inc = tmp_path / "in"
    inc.mkdir()
    return rs, reg, inc


def _pic(path, seed, size=(1600, 1200)):
    """Разные «снимки»: свой рисунок полос у каждого seed, чтобы усреднённый хеш различался."""
    from PIL import Image, ImageDraw

    im = Image.new("RGB", size, (200, 170, 120))
    d = ImageDraw.Draw(im)
    for k in range(8):
        if (seed >> k) & 1:
            d.rectangle((k * size[0] // 8, 0, (k + 1) * size[0] // 8, size[1]), fill=(60, 40, 20))
    im.save(path)


def test_intake_pilot_runs_one_image_through_the_whole_chain(tmp_path, monkeypatch):
    rs, reg, inc = _setup(tmp_path, monkeypatch)
    for n, r in enumerate(rs):
        _pic(inc / f"{r.slug}.jpg", 0b10110010 + n * 7)
    res = media.intake(argparse.Namespace(dir=inc, tool="g 1", license="l", only=rs[1].slug))
    assert res["added"] == [rs[1].slug] and set(json.loads(reg.read_text())["items"]) == {rs[1].slug}
    e = json.loads(reg.read_text())["items"][rs[1].slug]
    assert e["recipe_id"] == rs[1].raw["content_id"] and len(e["sha256"]) == 64 and len(e["ahash"]) == 64
    with pytest.raises(SystemExit, match="задания"):
        media.intake(argparse.Namespace(dir=inc, tool="g 1", license="l", only="net-takogo-recepta"))


def test_intake_rejects_small_and_repeated_images(tmp_path, monkeypatch):
    from PIL import Image

    rs, reg, inc = _setup(tmp_path, monkeypatch)
    _pic(inc / f"{rs[0].slug}.jpg", 0b11001010)
    # та же картинка у второго блюда, только уменьшенная и пересохранённая — не своё изображение
    Image.open(inc / f"{rs[0].slug}.jpg").resize((1400, 1050)).save(inc / f"{rs[1].slug}.jpg", quality=70)
    _pic(inc / f"{rs[2].slug}.jpg", 0b00110101, size=(900, 675))
    res = media.intake(argparse.Namespace(dir=inc, tool="g 1", license="l"))
    assert res["added"] == [rs[0].slug]
    why = res["rejected"][f"{rs[1].slug}.jpg"]
    assert "то же изображение" in why and rs[0].slug in why
    assert "мало пикселей" in res["rejected"][f"{rs[2].slug}.jpg"]
    assert set(json.loads(reg.read_text())["items"]) == {rs[0].slug}


def test_intake_makes_large_version_only_from_large_source(tmp_path, monkeypatch):
    # 1600 px — для крупного кадра рецепта на экранах ×2, но только если исходник не меньше: маленький не растягиваем
    from PIL import Image

    rs, reg, inc = _setup(tmp_path, monkeypatch, n=2)
    _pic(inc / f"{rs[0].slug}.jpg", 0b10100110, size=(1700, 1300))
    _pic(inc / f"{rs[1].slug}.jpg", 0b01011001, size=(1300, 1000))
    res = media.intake(argparse.Namespace(dir=inc, tool="g 1", license="l"))
    assert set(res["added"]) == {rs[0].slug, rs[1].slug}
    items = json.loads(reg.read_text())["items"]
    assert items[rs[0].slug]["widths"] == [400, 800, 1200, 1600]
    assert items[rs[1].slug]["widths"] == [400, 800, 1200]
    for r in rs:
        for w in items[r.slug]["widths"]:
            assert Image.open(tmp_path / "out" / f"{r.slug}-{w}.webp").size == (w, w * 3 // 4)
