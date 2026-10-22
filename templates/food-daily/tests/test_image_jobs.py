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
    assert res == {"added": [r.slug], "missing": []}
    e = json.loads(reg.read_text())["items"][r.slug]
    assert e["kind"] == "illustration" and e["source"].startswith("сгенерировано: генератор X 1.0")
    assert (e["width"], e["height"]) == (1200, 900) and (tmp_path / "out" / f"{r.slug}-400.webp").is_file()
