"""Проект сайта и его релиз: воспроизводимость, digest, отказ устаревшему выкату.

Доказывает: REQ-CELL-REPO, REQ-CELL-RELEASE, REQ-CELL-STALE.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from factory.cell import release, siterepo
from factory.cell.release import DigestMismatch, ReleaseError, StaleSource
from factory.cell.siterepo import SiteRepoError

PINS = {"common_core": "abc1234", "template": "1.0.0",
        "modules": {"content-catalog": "2.1.0"}, "schemas": {"site-profile": "1.0"}}


@pytest.fixture()
def template(tmp_path: Path) -> Path:
    src = tmp_path / "template-src"
    src.mkdir()
    (src / "profile.yaml").write_text("profile: pilot-template\n", encoding="utf-8")
    return src


def _repo(tmp_path: Path, template: Path, site_id: str = "pilot-cell") -> siterepo.SiteRepo:
    return siterepo.generate(
        site_id=site_id, domain=f"{site_id}.test", template_id="pilot-template",
        template_source=template, modules=("content-catalog", "seo"), pins=PINS,
        publisher={"provider": "cdnvideohub", "publisher_id_ref": "secret://pilot"},
        deploy_target={"ref": "local-disposable", "server": None},
        destination=tmp_path / "repos" / site_id,
    )


def test_generated_repo_is_a_git_project_with_its_own_history(tmp_path, template):
    repo = _repo(tmp_path, template)
    assert (repo.path / ".git").is_dir()
    assert repo.commit
    log = subprocess.run(["git", "-C", str(repo.path), "log", "--oneline"],
                         capture_output=True, text=True, check=True).stdout
    assert "pilot-cell" in log


def test_repo_carries_the_rules_and_the_pins(tmp_path, template):
    repo = _repo(tmp_path, template)
    agents = (repo.path / "AGENTS.md").read_text(encoding="utf-8")
    assert "только его" in agents
    assert "Массовая замена по всей фабрике запрещена" in agents
    assert "не обновляет сеть" in agents
    pins = json.loads((repo.path / "pins.lock.json").read_text(encoding="utf-8"))
    assert pins["pins"]["common_core"] == "abc1234"


def test_repo_declares_field_ownership_rather_than_last_writer_wins(tmp_path, template):
    repo = _repo(tmp_path, template)
    owners = repo.manifest["field_ownership"]
    assert "seo_text" in owners["seo"]
    assert "year" in owners["catalog"]
    assert "Последний записавший победил" in owners["rule"]


def test_repo_ships_a_ci_template_scoped_to_one_site(tmp_path, template):
    """Шаблон CI обязан разбираться и защищать ровно этот сайт."""
    import yaml

    repo = _repo(tmp_path, template)
    workflow = repo.path / ".github" / "workflows" / "release.yml"
    assert workflow.exists()
    data = yaml.safe_load(workflow.read_text(encoding="utf-8"))
    # Один выкат на сайт одновременно, и прерывать его на середине нельзя.
    assert data["concurrency"]["group"] == "release-pilot-cell"
    assert data["concurrency"]["cancel-in-progress"] is False
    text = workflow.read_text(encoding="utf-8")
    assert "чужой сайт не выпускается" in text
    assert "устаревший выкат отклонён" in text
    # Переключения домена в CI нет и быть не должно.
    assert "dns" not in text.lower()
    # Полная история: без неё merge-base не отвечает, а неответ выглядел бы
    # как «исходник не устарел».
    assert data["jobs"]["release"]["steps"][0]["with"]["fetch-depth"] == 0
    # «Не смог ответить» не приравнивается к «не устарел».
    assert "установить не удалось" in text


def test_generated_ci_shell_steps_are_syntactically_valid(tmp_path, template):
    """Каждый shell-шаг проходит bash -n: сломанный синтаксис иначе выясняется в CI."""
    import subprocess

    import yaml

    repo = _repo(tmp_path, template)
    workflow = repo.path / ".github" / "workflows" / "release.yml"
    data = yaml.safe_load(workflow.read_text(encoding="utf-8"))
    scripts = [s["run"] for s in data["jobs"]["release"]["steps"] if s.get("run")]
    assert scripts, "в шаблоне CI не осталось ни одного shell-шага"
    for script in scripts:
        result = subprocess.run(["bash", "-n"], input=script, text=True,
                                capture_output=True)
        assert result.returncode == 0, f"bash -n: {result.stderr}\n{script}"


def test_repo_checks_reject_floating_pins(tmp_path, template):
    repo = _repo(tmp_path, template)
    pins_file = repo.path / "pins.lock.json"
    data = json.loads(pins_file.read_text(encoding="utf-8"))
    data["pins"]["common_core"] = "latest"
    pins_file.write_text(json.dumps(data), encoding="utf-8")
    result = subprocess.run(["bash", "checks/run.sh"], cwd=repo.path,
                            capture_output=True, text=True)
    assert result.returncode != 0
    assert "no-floating-pins" in result.stdout
    assert "FAIL" in result.stdout


def test_repo_checks_reject_a_committed_database(tmp_path, template):
    repo = _repo(tmp_path, template)
    (repo.path / "smuggled.sqlite3").write_bytes(b"SQLite format 3\x00")
    result = subprocess.run(["bash", "checks/run.sh"], cwd=repo.path,
                            capture_output=True, text=True)
    assert result.returncode != 0
    assert "no-data-or-secrets" in result.stdout


def test_checks_pass_on_a_fresh_repo(tmp_path, template):
    repo = _repo(tmp_path, template)
    result = subprocess.run(["bash", "checks/run.sh"], cwd=repo.path,
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "FAIL" not in result.stdout


def test_generate_refuses_to_overwrite_without_force(tmp_path, template):
    _repo(tmp_path, template)
    with pytest.raises(SiteRepoError, match="force"):
        _repo(tmp_path, template)


def test_release_digest_is_reproducible_from_the_same_commit(tmp_path, template):
    repo = _repo(tmp_path, template)
    first = release.build(site_id="pilot-cell", repo=repo.path,
                          output_dir=tmp_path / "out1")
    second = release.build(site_id="pilot-cell", repo=repo.path,
                           output_dir=tmp_path / "out2")
    assert first.digest == second.digest, "один коммит обязан давать один digest"
    assert first.source_commit == second.source_commit


def test_digest_does_not_depend_on_the_builders_umask(tmp_path, template):
    """Один коммит — один digest, кем бы он ни собирался.

    Git хранит у файла ровно один бит прав. Остальное берётся из umask, и без
    нормализации режима один и тот же коммит давал разный digest у разработчика
    (664) и на раннере CI (644) — digest отвечал на вопрос «кто собирал».
    """
    import os
    import tarfile

    repo = _repo(tmp_path, template)
    first = release.build(site_id="pilot-cell", repo=repo.path,
                          output_dir=tmp_path / "umask-a")

    # Меняем права рабочих файлов так, как это сделал бы другой umask.
    for path in repo.path.rglob("*"):
        if path.is_file() and ".git" not in path.parts:
            mode = path.stat().st_mode
            os.chmod(path, (mode | 0o020) if not (mode & 0o111) else (mode | 0o020))

    second = release.build(site_id="pilot-cell", repo=repo.path,
                           output_dir=tmp_path / "umask-b")
    assert first.digest == second.digest, "digest зависит от прав файлов"

    with tarfile.open(second.artifact, "r:gz") as tar:
        режимы = {oct(m.mode) for m in tar.getmembers() if m.isfile()}
    assert режимы <= {"0o644", "0o755"}, f"в архиве неканонические режимы: {режимы}"


def test_release_manifest_locates_the_source_without_the_old_server(tmp_path, template):
    repo = _repo(tmp_path, template)
    rel = release.build(site_id="pilot-cell", repo=repo.path, output_dir=tmp_path / "out")
    m = rel.manifest
    assert m["source_commit"] == repo.commit
    assert m["digest"].startswith("sha256:")
    assert m["pins"]["common_core"] == "abc1234"
    assert m["contains"]["database"] is False
    assert m["contains"]["secrets"] is False


def test_release_refuses_a_dirty_tree(tmp_path, template):
    repo = _repo(tmp_path, template)
    (repo.path / "stray.txt").write_text("не в коммите", encoding="utf-8")
    with pytest.raises(ReleaseError, match="незакоммиченные"):
        release.build(site_id="pilot-cell", repo=repo.path, output_dir=tmp_path / "out")


def test_release_refuses_to_build_someone_elses_site(tmp_path, template):
    repo = _repo(tmp_path, template)
    with pytest.raises(ReleaseError, match="чужой артефакт"):
        release.build(site_id="neighbour", repo=repo.path, output_dir=tmp_path / "out")


def test_artifact_contains_no_git_and_no_data(tmp_path, template):
    import tarfile
    repo = _repo(tmp_path, template)
    (repo.path / "data").mkdir()
    (repo.path / "data" / "site.sqlite3").write_bytes(b"SQLite format 3\x00")
    rel = release.build(site_id="pilot-cell", repo=repo.path, output_dir=tmp_path / "out")
    with tarfile.open(rel.artifact, "r:gz") as tar:
        names = tar.getnames()
    assert not [n for n in names if n == ".git" or n.startswith(".git/")]
    assert not [n for n in names if "sqlite3" in n]
    assert "site-manifest.json" in names


def test_verify_catches_a_swapped_artifact(tmp_path, template):
    repo = _repo(tmp_path, template)
    rel = release.build(site_id="pilot-cell", repo=repo.path, output_dir=tmp_path / "out")
    assert release.verify_artifact(rel.artifact, rel.manifest)["verified"]
    rel.artifact.write_bytes("подменили".encode())
    with pytest.raises(DigestMismatch):
        release.verify_artifact(rel.artifact, rel.manifest)


def test_stale_session_cannot_overwrite_a_newer_release(tmp_path, template):
    repo = _repo(tmp_path, template)
    old = repo.commit
    (repo.path / "config" / "site.json").write_text('{"changed": true}', encoding="utf-8")
    subprocess.run(["git", "-C", str(repo.path), "commit", "-aqm", "новее"], check=True)
    new = siterepo.head_commit(repo.path)
    # Свежий выкат поверх старого — норма.
    release.guard_stale_source(incoming_commit=new, deployed_commit=old, repo=repo.path)
    # Обратное — нет.
    with pytest.raises(StaleSource):
        release.guard_stale_source(incoming_commit=old, deployed_commit=new, repo=repo.path)


def test_unpack_refuses_paths_that_escape_the_destination(tmp_path):
    import io
    import tarfile
    evil = tmp_path / "evil.tar.gz"
    with tarfile.open(evil, "w:gz") as tar:
        info = tarfile.TarInfo("../escaped.txt")
        payload = b"x"
        info.size = len(payload)
        tar.addfile(info, io.BytesIO(payload))
    with pytest.raises(ReleaseError, match="недопустимый путь"):
        release.unpack(evil, tmp_path / "dest")


def test_unpack_restores_the_project(tmp_path, template):
    repo = _repo(tmp_path, template)
    rel = release.build(site_id="pilot-cell", repo=repo.path, output_dir=tmp_path / "out")
    dest = release.unpack(rel.artifact, tmp_path / "installed",
                          expected_digest=rel.digest)
    restored = json.loads((dest / "site-manifest.json").read_text(encoding="utf-8"))
    assert restored["site_id"] == "pilot-cell"
