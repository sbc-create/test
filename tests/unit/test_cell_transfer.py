"""Перенос: выгрузка одного арендатора, установка по digest, откат без потерь.

Доказывает: REQ-CELL-TRANSFER, REQ-CELL-ROLLBACK, REQ-CELL-FREEZE.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory.cell import release as release_mod
from factory.cell import siterepo, tenant, transfer
from factory.cell.tenant import WritesFrozen
from factory.cell.transfer import Layout, TransferError

TITLE = "3f2a7c10-0000-4000-8000-000000000001"
PINS = {"common_core": "abc1234", "template": "1.0.0"}


@pytest.fixture()
def template(tmp_path: Path) -> Path:
    src = tmp_path / "template-src"
    src.mkdir()
    (src / "profile.yaml").write_text("profile: pilot\n", encoding="utf-8")
    return src


def _repo(tmp_path: Path, template: Path, site_id="pilot-cell") -> siterepo.SiteRepo:
    return siterepo.generate(
        site_id=site_id, domain=f"{site_id}.test", template_id="pilot-template",
        template_source=template, modules=("content-catalog",), pins=PINS,
        publisher={"provider": "cdnvideohub", "publisher_id_ref": "secret://pilot"},
        deploy_target={"ref": "local-disposable", "server": None},
        destination=tmp_path / "repos" / site_id)


def _layout(tmp_path: Path, name: str) -> Layout:
    return Layout(root=tmp_path / name).ensure()


def _seed(layout: Layout, site_id="pilot-cell", comments=3) -> None:
    store = tenant.open_store(site_id, layout.database)
    store.add_identity("u-1", "Первый")
    for i in range(comments):
        c = store.add_comment(title_uuid=TITLE, identity_id="u-1", body=f"текст {i}")
        store.moderate(c.comment_id, status="approved", actor="moder")
    store.vote(title_uuid=TITLE, identity_id="u-1", score=8)
    store.close()


def test_export_carries_only_this_tenant_with_counts_and_checksum(tmp_path):
    src = _layout(tmp_path, "src")
    _seed(src)
    pkg = transfer.export(site_id="pilot-cell", layout=src,
                          destination=tmp_path / "export")
    assert pkg.manifest["row_counts"]["comments"] == 3
    assert pkg.manifest["checksum"].startswith("sha256:")
    assert pkg.manifest["contains_secrets"] is False
    rows = json.loads((pkg.path / "rows.json").read_text(encoding="utf-8"))
    sites = {r["site_id"] for table in rows.values() for r in table}
    assert sites == {"pilot-cell"}


def test_export_dry_run_writes_nothing(tmp_path):
    src = _layout(tmp_path, "src")
    _seed(src)
    destination = tmp_path / "export"
    transfer.export(site_id="pilot-cell", layout=src, destination=destination,
                    dry_run=True)
    assert not destination.exists()


def test_export_dry_run_does_not_create_a_database(tmp_path):
    """Сухой прогон не создаёт пустую базу там, где её не было."""
    src = _layout(tmp_path, "src")
    assert not src.database.exists()
    with pytest.raises(TransferError, match="переносить нечего"):
        transfer.export(site_id="pilot-cell", layout=src,
                        destination=tmp_path / "export", dry_run=True)
    assert not src.database.exists(), "сухой прогон создал файл базы"


def test_import_verifies_counts_and_checksum(tmp_path):
    src, dst = _layout(tmp_path, "src"), _layout(tmp_path, "dst")
    _seed(src)
    pkg = transfer.export(site_id="pilot-cell", layout=src,
                          destination=tmp_path / "export")
    result = transfer.import_data(site_id="pilot-cell", package=pkg.path, layout=dst)
    assert result["row_counts"] == pkg.manifest["row_counts"]
    assert result["checksum"] == pkg.manifest["checksum"]

    store = tenant.open_store("pilot-cell", dst.database)
    assert len(store.comments(title_uuid=TITLE, status="approved")) == 3
    assert store.user_rating(TITLE)["average"] == 8.0
    store.close()


def test_import_refuses_a_package_built_for_another_site(tmp_path):
    src, dst = _layout(tmp_path, "src"), _layout(tmp_path, "dst")
    _seed(src)
    pkg = transfer.export(site_id="pilot-cell", layout=src,
                          destination=tmp_path / "export")
    with pytest.raises(TransferError, match="собран для"):
        transfer.import_data(site_id="neighbour-cell", package=pkg.path, layout=dst)


def test_install_puts_the_verified_artifact_and_leaves_data_alone(tmp_path, template):
    repo = _repo(tmp_path, template)
    rel = release_mod.build(site_id="pilot-cell", repo=repo.path,
                            output_dir=tmp_path / "out")
    dst = _layout(tmp_path, "dst")
    _seed(dst)
    before = tenant.open_store("pilot-cell", dst.database)
    counts_before = before.row_counts()
    before.close()

    result = transfer.install(site_id="pilot-cell", artifact=rel.artifact,
                              manifest=rel.manifest, layout=dst)
    assert result["status"] == "installed"
    assert dst.current.exists()
    assert (dst.current / "site-manifest.json").exists()

    after = tenant.open_store("pilot-cell", dst.database)
    assert after.row_counts() == counts_before
    after.close()


def test_install_dry_run_changes_nothing(tmp_path, template):
    repo = _repo(tmp_path, template)
    rel = release_mod.build(site_id="pilot-cell", repo=repo.path,
                            output_dir=tmp_path / "out")
    dst = _layout(tmp_path, "dst")
    result = transfer.install(site_id="pilot-cell", artifact=rel.artifact,
                              manifest=rel.manifest, layout=dst, dry_run=True)
    assert result["status"] == "dry-run"
    assert not dst.current.exists()


def test_install_refuses_another_sites_artifact(tmp_path, template):
    repo = _repo(tmp_path, template, site_id="pilot-cell")
    rel = release_mod.build(site_id="pilot-cell", repo=repo.path,
                            output_dir=tmp_path / "out")
    dst = _layout(tmp_path, "dst")
    with pytest.raises(TransferError, match="чужой артефакт"):
        transfer.install(site_id="neighbour-cell", artifact=rel.artifact,
                         manifest=rel.manifest, layout=dst)


def test_install_refuses_a_tampered_artifact(tmp_path, template):
    repo = _repo(tmp_path, template)
    rel = release_mod.build(site_id="pilot-cell", repo=repo.path,
                            output_dir=tmp_path / "out")
    rel.artifact.write_bytes("подмена".encode())
    dst = _layout(tmp_path, "dst")
    with pytest.raises(release_mod.DigestMismatch):
        transfer.install(site_id="pilot-cell", artifact=rel.artifact,
                         manifest=rel.manifest, layout=dst)


def test_verify_is_not_satisfied_by_a_missing_route(tmp_path, template):
    repo = _repo(tmp_path, template)
    rel = release_mod.build(site_id="pilot-cell", repo=repo.path,
                            output_dir=tmp_path / "out")
    dst = _layout(tmp_path, "dst")
    _seed(dst)
    transfer.install(site_id="pilot-cell", artifact=rel.artifact,
                     manifest=rel.manifest, layout=dst)
    report = transfer.verify(site_id="pilot-cell", layout=dst,
                             expected_routes=("/catalog/", "/about/"))
    assert report["status"] == "FAIL"
    routes = next(s for s in report["steps"] if s["step"] == "published-routes")
    assert set(routes["detail"]["missing"]) == {"/catalog/", "/about/"}


def test_verify_passes_when_the_routes_are_actually_published(tmp_path, template):
    """Ворота маршрутов обязаны уметь и проходить, а не только падать."""
    repo = _repo(tmp_path, template)
    rel = release_mod.build(site_id="pilot-cell", repo=repo.path,
                            output_dir=tmp_path / "out")
    dst = _layout(tmp_path, "dst")
    _seed(dst)
    transfer.install(site_id="pilot-cell", artifact=rel.artifact,
                     manifest=rel.manifest, layout=dst)
    for route in ("catalog", "about"):
        page = dst.public / route / "index.html"
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text("<html><body>страница</body></html>", encoding="utf-8")
    report = transfer.verify(site_id="pilot-cell", layout=dst,
                             expected_routes=("/catalog/", "/about/"))
    assert report["status"] == "PASS", report
    routes = next(s for s in report["steps"] if s["step"] == "published-routes")
    assert routes["detail"]["missing"] == []


def test_published_pages_survive_a_code_rollback(tmp_path, template):
    """Страницы лежат вне релиза, поэтому откат кода их не уносит."""
    import subprocess
    repo = _repo(tmp_path, template)
    first = release_mod.build(site_id="pilot-cell", repo=repo.path,
                              output_dir=tmp_path / "out1")
    dst = _layout(tmp_path, "dst")
    transfer.install(site_id="pilot-cell", artifact=first.artifact,
                     manifest=first.manifest, layout=dst)
    page = dst.public / "catalog" / "index.html"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text("<html><body>каталог</body></html>", encoding="utf-8")

    (repo.path / "config" / "site.json").write_text('{"v": 2}', encoding="utf-8")
    subprocess.run(["git", "-C", str(repo.path), "commit", "-aqm", "второй"], check=True)
    second = release_mod.build(site_id="pilot-cell", repo=repo.path,
                               output_dir=tmp_path / "out2")
    transfer.install(site_id="pilot-cell", artifact=second.artifact,
                     manifest=second.manifest, layout=dst)
    transfer.rollback(site_id="pilot-cell", layout=dst, reason="проверка")
    assert page.exists(), "откат кода унёс опубликованные страницы"


def test_a_relative_root_still_produces_a_working_current_link(tmp_path, template,
                                                               monkeypatch):
    """Относительный корень не должен давать висящую ссылку `current`.

    Символическая ссылка на относительный путь разрешается от каталога самой
    ссылки, а не от рабочего каталога процесса. Пока пилот жил во временном
    каталоге с абсолютными путями, дефект не проявлялся.
    """
    repo = _repo(tmp_path, template)
    rel = release_mod.build(site_id="pilot-cell", repo=repo.path,
                            output_dir=tmp_path / "out")
    monkeypatch.chdir(tmp_path)
    layout = Layout(root=Path("hosts/relative")).ensure()
    transfer.install(site_id="pilot-cell", artifact=rel.artifact,
                     manifest=rel.manifest, layout=layout)
    assert layout.current.is_dir(), "current указывает в никуда"
    assert (layout.current / "site-manifest.json").exists()


def test_verify_without_routes_says_not_run_rather_than_pass(tmp_path, template):
    repo = _repo(tmp_path, template)
    rel = release_mod.build(site_id="pilot-cell", repo=repo.path,
                            output_dir=tmp_path / "out")
    dst = _layout(tmp_path, "dst")
    _seed(dst)
    transfer.install(site_id="pilot-cell", artifact=rel.artifact,
                     manifest=rel.manifest, layout=dst)
    report = transfer.verify(site_id="pilot-cell", layout=dst)
    routes = next(s for s in report["steps"] if s["step"] == "published-routes")
    assert routes["status"] == "NOT_RUN"


def test_freeze_stops_writes_on_this_site_only(tmp_path):
    src, other = _layout(tmp_path, "src"), _layout(tmp_path, "other")
    _seed(src)
    _seed(other, site_id="neighbour-cell", comments=1)

    transfer.freeze_writes(site_id="pilot-cell", layout=src, reason="перенос дельты")
    frozen = tenant.open_store("pilot-cell", src.database)
    with pytest.raises(WritesFrozen):
        frozen.add_comment(title_uuid=TITLE, identity_id="u-1", body="во время переноса")
    assert len(frozen.comments(title_uuid=TITLE)) == 3, "чтение обязано работать"
    frozen.close()

    # Сосед не заморожен.
    neighbour = tenant.open_store("neighbour-cell", other.database)
    neighbour.add_comment(title_uuid=TITLE, identity_id="u-1", body="сосед пишет")
    neighbour.close()

    transfer.thaw_writes(layout=src)
    thawed = tenant.open_store("pilot-cell", src.database)
    thawed.add_comment(title_uuid=TITLE, identity_id="u-1", body="после разморозки")
    thawed.close()


def test_cutover_dry_run_switches_nothing(tmp_path):
    src, dst = _layout(tmp_path, "src"), _layout(tmp_path, "dst")
    _seed(src)
    result = transfer.cutover(site_id="pilot-cell", source=src, target=dst,
                              reason="репетиция", dry_run=True)
    assert result["status"] == "dry-run"
    assert result["dns_switched"] is False
    assert not tenant.freeze_marker(src.database).exists()


def test_cutover_backs_up_freezes_and_moves_the_delta(tmp_path):
    src, dst = _layout(tmp_path, "src"), _layout(tmp_path, "dst")
    _seed(src, comments=5)
    result = transfer.cutover(site_id="pilot-cell", source=src, target=dst,
                              reason="перенос")
    assert result["status"] == "PASS"
    # Домен не переключался, и отчёт говорит об этом прямо.
    assert result["dns_switched"] is False
    assert result["source_frozen"] is True
    steps = {s["step"]: s["status"] for s in result["steps"]}
    assert steps["backup"] == "PASS"
    assert steps["rehearsal"] == "PASS"
    assert steps["import-delta"] == "PASS"

    moved = tenant.open_store("pilot-cell", dst.database)
    assert len(moved.comments(title_uuid=TITLE)) == 5
    moved.close()


def test_two_writers_are_impossible_after_cutover(tmp_path):
    src, dst = _layout(tmp_path, "src"), _layout(tmp_path, "dst")
    _seed(src)
    transfer.cutover(site_id="pilot-cell", source=src, target=dst, reason="перенос")
    old = tenant.open_store("pilot-cell", src.database)
    with pytest.raises(WritesFrozen):
        old.add_comment(title_uuid=TITLE, identity_id="u-1", body="старый сервер пишет")
    old.close()
    # Новая сторона пишет свободно.
    new = tenant.open_store("pilot-cell", dst.database)
    new.add_comment(title_uuid=TITLE, identity_id="u-1", body="новый сервер пишет")
    new.close()


def test_rollback_keeps_records_accepted_after_the_switch(tmp_path, template):
    repo = _repo(tmp_path, template)
    first = release_mod.build(site_id="pilot-cell", repo=repo.path,
                              output_dir=tmp_path / "out1")
    dst = _layout(tmp_path, "dst")
    _seed(dst)
    transfer.install(site_id="pilot-cell", artifact=first.artifact,
                     manifest=first.manifest, layout=dst)

    import subprocess
    (repo.path / "config" / "site.json").write_text('{"v": 2}', encoding="utf-8")
    subprocess.run(["git", "-C", str(repo.path), "commit", "-aqm", "второй"], check=True)
    second = release_mod.build(site_id="pilot-cell", repo=repo.path,
                               output_dir=tmp_path / "out2")
    transfer.install(site_id="pilot-cell", artifact=second.artifact,
                     manifest=second.manifest, layout=dst)

    # Новые записи приняты уже на новом релизе.
    store = tenant.open_store("pilot-cell", dst.database)
    fresh = store.add_comment(title_uuid=TITLE, identity_id="u-1", body="после выката")
    store.vote(title_uuid=TITLE, identity_id="u-1", score=10)
    store.close()

    result = transfer.rollback(site_id="pilot-cell", layout=dst, reason="провал smoke")
    assert result["status"] == "rolled-back"
    assert result["data_preserved"] is True

    after = tenant.open_store("pilot-cell", dst.database)
    assert after.comment(fresh.comment_id).body == "после выката"
    assert after.user_rating(TITLE)["average"] == 10.0
    after.close()


def test_rollback_without_a_previous_release_is_refused(tmp_path, template):
    repo = _repo(tmp_path, template)
    rel = release_mod.build(site_id="pilot-cell", repo=repo.path,
                            output_dir=tmp_path / "out")
    dst = _layout(tmp_path, "dst")
    transfer.install(site_id="pilot-cell", artifact=rel.artifact,
                     manifest=rel.manifest, layout=dst)
    with pytest.raises(TransferError, match="предыдущего релиза нет"):
        transfer.rollback(site_id="pilot-cell", layout=dst, reason="нет предыдущего")


def test_rollback_dry_run_changes_nothing(tmp_path, template):
    repo = _repo(tmp_path, template)
    first = release_mod.build(site_id="pilot-cell", repo=repo.path,
                              output_dir=tmp_path / "out1")
    dst = _layout(tmp_path, "dst")
    transfer.install(site_id="pilot-cell", artifact=first.artifact,
                     manifest=first.manifest, layout=dst)
    import subprocess
    (repo.path / "config" / "site.json").write_text('{"v": 2}', encoding="utf-8")
    subprocess.run(["git", "-C", str(repo.path), "commit", "-aqm", "второй"], check=True)
    second = release_mod.build(site_id="pilot-cell", repo=repo.path,
                               output_dir=tmp_path / "out2")
    transfer.install(site_id="pilot-cell", artifact=second.artifact,
                     manifest=second.manifest, layout=dst)
    where = dst.current.resolve()
    result = transfer.rollback(site_id="pilot-cell", layout=dst, reason="проверка",
                               dry_run=True)
    assert result["status"] == "dry-run"
    assert dst.current.resolve() == where


def test_reinstall_does_not_lose_data(tmp_path, template):
    repo = _repo(tmp_path, template)
    rel = release_mod.build(site_id="pilot-cell", repo=repo.path,
                            output_dir=tmp_path / "out")
    dst = _layout(tmp_path, "dst")
    _seed(dst)
    store = tenant.open_store("pilot-cell", dst.database)
    counts = store.row_counts()
    store.close()
    transfer.install(site_id="pilot-cell", artifact=rel.artifact,
                     manifest=rel.manifest, layout=dst)
    transfer.install(site_id="pilot-cell", artifact=rel.artifact,
                     manifest=rel.manifest, layout=dst)
    again = tenant.open_store("pilot-cell", dst.database)
    assert again.row_counts() == counts
    again.close()
