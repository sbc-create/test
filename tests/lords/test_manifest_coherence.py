"""Сторож когерентности манифестов витрин Lords.

Дефект, который закрывает этот набор, наблюдался вживую 2026-09-21: артефакт
визуального ремонта установили ради lords-02, а исполняемый файл у всех трёх
витрин общий. Манифест переписали только у lords-02. Дальше суточный refresh
перезапустил соседей, и lords-01 с lords-03 начали исполнять новый код,
продолжая объявлять прежнюю сборку.

Проверки идут на фикстуре, а не на живом хосте: набор обязан краснеть в CI, где
никакого `/srv/lords` нет.
"""

from __future__ import annotations

import importlib.util
import json
import pathlib

import pytest

MODULE_PATH = (
    pathlib.Path(__file__).resolve().parents[2] / "automation" / "host" / "nova-manifest-coherence.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("nova_manifest_coherence", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


coherence = _load()


def _front(tmp_path: pathlib.Path, runtime_body: bytes, manifests: dict[str, str]) -> pathlib.Path:
    """Каталог рантайма с общим исполняемым файлом и манифестами витрин."""
    front = tmp_path / "frontend"
    front.mkdir()
    (front / "lords-frontend.py").write_bytes(runtime_body)
    for site, artifact_sha in manifests.items():
        name = "template-manifest.json" if site == "lords-01" else f"template-manifest-{site}.json"
        (front / name).write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "artifact_sha256": artifact_sha,
                    "build_id": f"build-for-{artifact_sha[:8]}",
                    "profile": site,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    return front


def _sha(body: bytes) -> str:
    import hashlib

    return hashlib.sha256(body).hexdigest()


NEW = b"# new artifact\n"
OLD_SHA = "0" * 64


def test_all_manifests_match_runtime_is_coherent(tmp_path):
    front = _front(tmp_path, NEW, {s: _sha(NEW) for s in ("lords-01", "lords-02", "lords-03")})
    mtime = (front / "lords-frontend.py").stat().st_mtime
    code, report = coherence.check(front, starts={"9110": mtime + 5, "9111": mtime + 5, "9112": mtime + 5})
    assert code == coherence.COHERENT
    assert report["diverged_sites"] == []


def test_process_older_than_swap_is_pending_not_diverged(tmp_path):
    """Сосед, поднятый до подмены, исполняет то, что объявляет — это не ложь."""
    front = _front(
        tmp_path, NEW, {"lords-01": OLD_SHA, "lords-02": _sha(NEW), "lords-03": OLD_SHA}
    )
    mtime = (front / "lords-frontend.py").stat().st_mtime
    code, report = coherence.check(
        front, starts={"9110": mtime - 60, "9111": mtime + 5, "9112": mtime - 60}
    )
    assert code == coherence.COHERENT
    assert report["sites"]["lords-01"]["verdict"] == "PENDING_RESTART"
    assert report["sites"]["lords-03"]["verdict"] == "PENDING_RESTART"


def test_neighbour_restarted_after_swap_is_diverged(tmp_path):
    """Наблюдавшийся дефект: сосед перезапущен после подмены и объявляет старое."""
    front = _front(
        tmp_path, NEW, {"lords-01": OLD_SHA, "lords-02": _sha(NEW), "lords-03": OLD_SHA}
    )
    mtime = (front / "lords-frontend.py").stat().st_mtime
    code, report = coherence.check(
        front, starts={"9110": mtime + 60, "9111": mtime + 5, "9112": mtime + 60}
    )
    assert code == coherence.DIVERGED
    assert sorted(report["diverged_sites"]) == ["lords-01", "lords-03"]
    assert report["sites"]["lords-02"]["verdict"] == "COHERENT"
    assert report["sites"]["lords-01"]["verdict"] == "DIVERGED_RUNTIME_AHEAD_OF_MANIFEST"


def test_missing_runtime_is_unmeasurable_not_pass(tmp_path):
    """Отсутствие файла не превращается в «всё хорошо»."""
    empty = tmp_path / "empty"
    empty.mkdir()
    code, report = coherence.check(empty, starts={})
    assert code == coherence.UNMEASURABLE
    assert "error" in report


def test_missing_manifest_is_unmeasurable_per_site(tmp_path):
    front = _front(tmp_path, NEW, {"lords-02": _sha(NEW)})
    mtime = (front / "lords-frontend.py").stat().st_mtime
    code, report = coherence.check(front, starts={"9111": mtime + 5})
    assert report["sites"]["lords-01"]["verdict"] == "UNMEASURABLE_NO_MANIFEST"
    assert code == coherence.COHERENT


@pytest.mark.parametrize("site,port", [("lords-01", 9110), ("lords-02", 9111), ("lords-03", 9112)])
def test_site_port_and_unit_mapping_is_declared(site, port):
    """Имена юнитов не угадываются: они зафиксированы и проверяются."""
    mapping = {v[0]: (int(k), v[2]) for k, v in coherence.SITES.items()}
    assert mapping[site][0] == port
    assert mapping[site][1].endswith(".service")
