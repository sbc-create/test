"""Изоляция шаблона food-daily от соседних шаблонов и общего UI."""

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
SOURCES = [
    p
    for p in ROOT.rglob("*")
    if p.is_file()
    and p.suffix in (".py", ".html", ".css", ".js", ".yaml", ".sh")
    and "__pycache__" not in p.parts
    and p.parent.name != "tests"
    and p.name != "OWNERSHIP.yaml"
]  # policy-файл перечисляет чужие каталоги как запретные
OTHER_SITES = re.compile(
    r"\b(lords|yummy|animedia|zona|animego|lordserial|amd\.online|wt-(?!template-food-daily))", re.I
)


def test_no_symlinks_inside_template():
    assert not [p for p in ROOT.rglob("*") if p.is_symlink()]


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: str(p.relative_to(ROOT)))
def test_no_references_to_other_templates(path):
    text = path.read_text(errors="replace")
    assert not OTHER_SITES.search(text), path
    # каталог тем фабрики (themes/ в корне репозитория) и рабочие копии чужих сайтов
    assert not re.search(r"\.\./+themes|REPO\s*/\s*[\"']themes|/srv/sites", text), path


def test_python_imports_stay_inside_template():
    # PIL — только офлайн-инструмент fooddaily.media (уменьшение фото с правами); сервер его не импортирует
    allowed_top = {"fooddaily", "jinja2", "yaml", "jsonschema", "playwright", "PIL"}
    std = {
        "argparse",
        "base64",
        "collections",
        "concurrent",
        "contextlib",
        "csv",
        "dataclasses",
        "datetime",
        "difflib",
        "functools",
        "gzip",
        "hashlib",
        "hmac",
        "html",
        "http",
        "ipaddress",
        "json",
        "math",
        "os",
        "random",
        "re",
        "secrets",
        "socket",
        "socketserver",
        "sqlite3",
        "subprocess",
        "sys",
        "threading",
        "time",
        "traceback",
        "urllib",
        "xml",
        "__future__",
        "pathlib",
        "typing",
        "getpass",
        "io",
        "tarfile",
        "tempfile",
        "statistics",
    }
    for p in (ROOT / "fooddaily").glob("*.py"):
        for m in re.finditer(r"^\s*(?:from|import)\s+([a-zA-Z_][\w]*)", p.read_text(), re.M):
            mod = m.group(1)
            assert mod in allowed_top | std or mod == "fooddaily", (p.name, mod)


def test_template_layer_has_no_data_access():
    """Шаблоны и модель представления не обращаются к БД, сети и очередям."""
    for p in list((ROOT / "templates").glob("*.html")) + [
        ROOT / "fooddaily" / "views.py",
        ROOT / "fooddaily" / "seo.py",
    ]:
        t = p.read_text()
        assert not re.search(r"sqlite|urllib\.request|requests\.|open_store|Store\(", t), p


def test_static_assets_are_own_files():
    css = (ROOT / "static" / "css" / "party.css").read_text()
    assert "@import" not in css and "url(http" not in css
    html = "".join(p.read_text() for p in (ROOT / "templates").glob("*.html"))
    assert not re.search(r'(src|href)="https?://(?!schema\.org)', html.replace("{{ r.source.url }}", ""))


def test_snapshot_belongs_to_site_and_has_no_source_text():
    snap = json.loads((ROOT / "data" / "content-snapshot.json").read_text())
    assert snap["site_id"] == "food-daily"
    for item in snap["items"]:
        assert "steps" not in item["facts"], "исходные шаги не должны попадать в публичную сборку"
        assert "editor_notes" not in item["draft"]


def test_foreign_snapshot_refused(tmp_path):
    from fooddaily.views import Site

    p = tmp_path / "snap.json"
    p.write_text(json.dumps({"site_id": "home-practical", "generated_at": "x", "items": []}))
    with pytest.raises(PermissionError):
        Site(snapshot_path=p)


def test_runtime_resources_are_site_scoped():
    import yaml

    cfg = yaml.safe_load((ROOT / "config" / "site.yaml").read_text())
    for k, v in cfg["storage"].items():
        assert "food-daily" in v, k
    assert cfg["server"]["bind"] == "127.0.0.1" and cfg["mode"] == "preview" and not cfg["production_authorized"]
    assert cfg["origin"]["production"] is None


def test_private_sources_not_in_git_tree():
    assert (REPO / ".gitignore").read_text().count("var/*") >= 1
    assert not list(ROOT.rglob("*.html.gz"))
