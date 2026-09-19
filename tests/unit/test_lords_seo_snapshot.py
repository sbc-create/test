"""Fail-closed SEO-снимок Lords: missing / partial / stale / wrong-build / valid."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from factory.lords import seo_snapshot as ss

ROOT = Path(__file__).resolve().parents[2]


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _page(path: str, page_type: str, **extra) -> dict:
    base = {
        "path": path,
        "page_type": page_type,
        "title": f"Title for {page_type}",
        "description": f"Description for {page_type} page on closed stand.",
        "h1": f"H1 {page_type}",
        "canonical": f"https://lordserial33.biz{path}",
        "indexable": False,
    }
    base.update(extra)
    return base


def _full_pages() -> list[dict]:
    pages = [
        _page("/", "home"),
        _page("/catalog/", "catalog_index"),
        _page("/movies/", "movies_index"),
        _page("/series/", "series_index"),
        _page("/animation/", "animation_index"),
        _page("/collections/", "collections_index"),
        _page("/collection/top_rated/", "collection"),
        _page("/title/sample/", "title"),
        _page("/title/sample/season-1/", "season"),
        _page("/title/sample/season-1/episode-1/", "episode"),
        _page("/search/", "search"),
    ]
    return pages


def _provenance(**over) -> dict:
    base = {
        "schema_version": 1,
        "template_family": "lords",
        "design_version": "1.1.0",
        "source_commit": "a" * 40,
        "runtime_commit": "b" * 40,
        "build_id": "20260919T120000Z-aaaaaaaa-nova",
        "artifact_sha256": "c" * 64,
        "profile": "lords-new",
        "built_at": "2026-09-19T12:00:00Z",
    }
    base.update(over)
    return base


def _valid_doc(tmp_path: Path, **prov_over) -> dict:
    catalog = tmp_path / "catalog.json"
    details = tmp_path / "details.json"
    catalog.write_text(
        json.dumps({"items": [{"slug": "a", "title": "A", "kind": "Сериал"}] * 3}),
        encoding="utf-8",
    )
    details.write_text(json.dumps({"a": {"description": "d"}}), encoding="utf-8")
    prov = _provenance(**prov_over)
    return ss.собрать(
        provenance=prov,
        catalog=catalog,
        details=details,
        pages=_full_pages(),
        domain="lordserial33.biz",
        site_id="lords-02",
    )


class TestSeoSnapshotContract:
    def test_valid_full_snapshot_passes(self, tmp_path: Path):
        doc = _valid_doc(tmp_path)
        ss.проверить(doc)
        assert doc["indexing_expected"] == "closed"
        assert all(p["indexable"] is False for p in doc["pages"])
        assert set(p["page_type"] for p in doc["pages"]) >= set(ss.REQUIRED_PAGE_TYPES)

    def test_missing_snapshot_raises(self, tmp_path: Path):
        with pytest.raises(ss.SeoSnapshotError, match="нет"):
            ss.прочитать(tmp_path / "missing.json")

    def test_empty_snapshot_rejected(self):
        беды = ss.нарушения({})
        assert any("пуст" in b for b in беды)

    def test_partial_pages_rejected(self, tmp_path: Path):
        doc = _valid_doc(tmp_path)
        doc["pages"] = [p for p in doc["pages"] if p["page_type"] != "episode"]
        беды = ss.нарушения(doc)
        assert any("episode" in b for b in беды)

    def test_stale_build_rejected(self, tmp_path: Path):
        doc = _valid_doc(tmp_path)
        expected = {
            "build_id": "20260919T999999Z-ffffffff-nova",
            "source_commit": doc["source_commit"],
            "runtime_commit": doc["runtime_commit"],
            "artifact_sha256": doc["artifact_sha256"],
            "profile": doc["profile"],
            "design_version": doc["design_version"],
            "content_snapshot_id": doc["content_snapshot_id"],
        }
        беды = ss.нарушения(doc, expected=expected)
        assert any("build_id" in b or "устаревший" in b for b in беды)

    def test_wrong_build_artifact_rejected(self, tmp_path: Path):
        doc = _valid_doc(tmp_path)
        expected = {
            "build_id": doc["build_id"],
            "source_commit": doc["source_commit"],
            "runtime_commit": doc["runtime_commit"],
            "artifact_sha256": "d" * 64,
            "profile": doc["profile"],
            "design_version": doc["design_version"],
            "content_snapshot_id": doc["content_snapshot_id"],
        }
        беды = ss.нарушения(doc, expected=expected)
        assert any("artifact_sha256" in b for b in беды)

    def test_wrong_content_snapshot_rejected(self, tmp_path: Path):
        doc = _valid_doc(tmp_path)
        expected = {
            "build_id": doc["build_id"],
            "source_commit": doc["source_commit"],
            "runtime_commit": doc["runtime_commit"],
            "artifact_sha256": doc["artifact_sha256"],
            "profile": doc["profile"],
            "design_version": doc["design_version"],
            "content_snapshot_id": "e" * 64,
        }
        беды = ss.нарушения(doc, expected=expected)
        assert any("content_snapshot_id" in b for b in беды)

    def test_build_marker_in_title_rejected(self, tmp_path: Path):
        doc = _valid_doc(tmp_path)
        doc["pages"][0]["title"] = "Home Lords · 1.1.0 · deadbeef"
        беды = ss.нарушения(doc)
        assert any("служебный фрагмент" in b for b in беды)

    def test_indexable_true_rejected_on_closed(self, tmp_path: Path):
        doc = _valid_doc(tmp_path)
        doc["pages"][0]["indexable"] = True
        беды = ss.нарушения(doc)
        assert any("indexable" in b for b in беды)

    def test_preparing_snapshot_keeps_indexing_closed(self, tmp_path: Path):
        doc = _valid_doc(tmp_path)
        assert doc["indexing_expected"] == "closed"
        doc["indexing_expected"] = "open"
        беды = ss.нарушения(doc)
        assert any("indexing_expected" in b for b in беды)

    def test_canonical_must_match_path(self, tmp_path: Path):
        doc = _valid_doc(tmp_path)
        movies = next(p for p in doc["pages"] if p["page_type"] == "movies_index")
        movies["canonical"] = "https://lordserial33.biz/catalog/"
        беды = ss.нарушения(doc)
        assert any("canonical" in b for b in беды)

    def test_content_snapshot_id_binds_catalog_and_details(self, tmp_path: Path):
        catalog = tmp_path / "c.json"
        details = tmp_path / "d.json"
        catalog.write_bytes(b'{"items":[1]}')
        details.write_bytes(b'{"x":1}')
        a = ss.content_snapshot_id(catalog=catalog, details=details)
        details.write_bytes(b'{"x":2}')
        b = ss.content_snapshot_id(catalog=catalog, details=details)
        assert a != b
        assert len(a) == 64


class TestDeployHealthzGate:
    """Root cause guard: same-port restart must poll /healthz, not sleep-only."""

    def test_deploy_nova_lords_polls_healthz_before_nginx(self):
        text = (ROOT / "automation/host/deploy-nova-lords.sh").read_text(encoding="utf-8")
        assert "/healthz" in text
        assert "lords-seo-snapshot.py" in text
        # Old race pattern must not remain as the sole readiness check.
        restart_idx = text.index('systemctl restart "nova-${SITE}.service"')
        nginx_idx = text.index("systemctl reload nginx")
        health_idx = text.index("/healthz", restart_idx)
        assert restart_idx < health_idx < nginx_idx
        sleep_only = 'systemctl restart "nova-${SITE}.service"\nsleep 3\nsystemctl is-active'
        assert sleep_only not in text

    def test_apply_validates_seo_snapshot_for_lords(self):
        text = (ROOT / "automation/host/apply-nova-closed-update.py").read_text(
            encoding="utf-8"
        )
        assert "seo_snapshot" in text
        assert "seo-snapshot-" in text
        assert "/healthz" in text
