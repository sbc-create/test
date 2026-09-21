"""Сторож когерентности витрин: объявленное против фактически исполняемого.

Дефект, который закрывает набор, наблюдался вживую 2026-09-21: артефакт
установили ради lords-02, исполняемый файл у шести витрин был общий, манифест
переписали одной витрине, а суточный refresh перезапустил соседей — и они стали
исполнять чужой код, продолжая объявлять прежнюю сборку.

Проверки идут на фикстуре: набор обязан краснеть в CI, где нет ни `/srv/lords`,
ни systemd.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import pathlib

import pytest

HOST = pathlib.Path(__file__).resolve().parents[2] / "automation" / "host"


def _load(имя: str, файл: str):
    spec = importlib.util.spec_from_file_location(имя, HOST / файл)
    модуль = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(модуль)
    return модуль


coherence = _load("nova_manifest_coherence", "nova-manifest-coherence.py")
registry_mod = _load("nova_runtime_registry", "nova-runtime-registry.py")

NEW = b"# new release\n"
OLD = b"# old release\n"


def _sha(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def _front(tmp_path: pathlib.Path) -> pathlib.Path:
    front = tmp_path / "frontend"
    front.mkdir()
    (front / RUNTIME).write_bytes(b"# shared legacy runtime\n")
    return front


RUNTIME = "lords-frontend.py"


def _release(front: pathlib.Path, build_id: str, body: bytes) -> pathlib.Path:
    каталог = front / "releases" / build_id
    каталог.mkdir(parents=True)
    (каталог / RUNTIME).write_bytes(body)
    return каталог


def _bind(front: pathlib.Path, site: str, каталог: pathlib.Path) -> None:
    ссылка = front / "sites" / site / "current"
    ссылка.parent.mkdir(parents=True, exist_ok=True)
    ссылка.symlink_to(каталог)


def _manifest(front: pathlib.Path, site: str, artifact: str, **extra) -> pathlib.Path:
    путь = front / f"template-manifest-{site}.json"
    путь.write_text(
        json.dumps({"artifact_sha256": artifact, "build_id": f"b-{artifact[:8]}", **extra}),
        encoding="utf-8",
    )
    return путь


def _registry(front: pathlib.Path, sites: dict[str, int]) -> dict:
    записи = {}
    for site, порт in sites.items():
        записи[site] = {
            "site_id": site,
            "port": порт,
            "unit": f"{site}.service",
            "exact_domain": f"{site}.example",
            "canonical_host": f"{site}.example",
            "indexing_enabled": False,
            "scope": "exact-domain-registry",
            "manifest_path": str(front / f"template-manifest-{site}.json"),
            "release_link": str(front / "sites" / site / "current"),
        }
    return {"sites": записи, "out_of_registry": [], "shared_runtime_path": str(front / RUNTIME)}


def test_each_site_running_its_own_release_is_coherent(tmp_path):
    front = _front(tmp_path)
    рел = _release(front, "b-new", NEW)
    процессы = {}
    for i, site in enumerate(("lords-01", "lords-02", "lords-03"), start=9110):
        _bind(front, site, рел)
        _manifest(front, site, _sha(NEW))
        процессы[i] = {"pid": 100 + i, "exec_script": str(рел / RUNTIME), "started_utc": "t"}
    код, отчёт = coherence.check(
        front, _registry(front, {"lords-01": 9110, "lords-02": 9111, "lords-03": 9112}), процессы
    )
    assert код == coherence.COHERENT
    assert отчёт["diverged_sites"] == []
    assert отчёт["sites_running_shared_mutable_path"] == []


def test_neighbour_running_foreign_bytes_is_diverged(tmp_path):
    """Наблюдавшийся дефект: сосед исполняет новое, объявляя старое."""
    front = _front(tmp_path)
    новый = _release(front, "b-new", NEW)
    процессы = {
        9110: {"pid": 1, "exec_script": str(новый / RUNTIME), "started_utc": "t"},
        9111: {"pid": 2, "exec_script": str(новый / RUNTIME), "started_utc": "t"},
    }
    _manifest(front, "lords-01", _sha(OLD))
    _manifest(front, "lords-02", _sha(NEW))
    код, отчёт = coherence.check(front, _registry(front, {"lords-01": 9110, "lords-02": 9111}), процессы)
    assert код == coherence.DIVERGED
    assert отчёт["diverged_sites"] == ["lords-01"]
    assert отчёт["sites"]["lords-02"]["verdict"] == "COHERENT"


def test_running_shared_mutable_path_is_reported(tmp_path):
    """Исполнение общего изменяемого пути называется прямо, даже когда sha сходится."""
    front = _front(tmp_path)
    общий = front / RUNTIME
    _manifest(front, "lords-01", _sha(общий.read_bytes()))
    процессы = {9110: {"pid": 1, "exec_script": str(общий), "started_utc": "t"}}
    код, отчёт = coherence.check(front, _registry(front, {"lords-01": 9110}), процессы)
    assert код == coherence.COHERENT
    assert отчёт["sites_running_shared_mutable_path"] == ["lords-01"]
    assert отчёт["sites"]["lords-01"]["runs_shared_mutable_path"] is True


def test_process_started_before_loader_is_pending_not_diverged(tmp_path):
    """Процесс, поднятый до установки загрузчика, исполняет старый код из памяти.

    Хешировать в этом случае общий путь — значит измерить байты загрузчика и
    объявить расхождение, которого нет. Такое состояние называется ожиданием
    перезапуска. Ошибка была допущена и исправлена 2026-09-21.
    """
    front = _front(tmp_path)
    (front / RUNTIME).write_bytes(b"# loader\nLORDS_RUNTIME_DISPATCHED = 1\n")
    _manifest(front, "lords-01", _sha(NEW))
    процессы = {9110: {"pid": 1, "exec_script": str(front / RUNTIME), "started_utc": "t"}}
    код, отчёт = coherence.check(front, _registry(front, {"lords-01": 9110}), процессы)
    assert код == coherence.COHERENT
    assert отчёт["sites"]["lords-01"]["verdict"] == "PENDING_RESTART_PROCESS_PREDATES_LOADER"
    assert отчёт["sites"]["lords-01"]["running_artifact_sha256"] == ""
    assert отчёт["shared_path_is_loader"] is True


def test_stopped_site_is_not_reported_as_pass(tmp_path):
    front = _front(tmp_path)
    _manifest(front, "lords-01", _sha(NEW))
    код, отчёт = coherence.check(front, _registry(front, {"lords-01": 9110}), {})
    assert отчёт["sites"]["lords-01"]["verdict"] == "NOT_RUNNING"
    assert код == coherence.COHERENT


def test_empty_registry_is_unmeasurable_not_pass(tmp_path):
    front = _front(tmp_path)
    код, отчёт = coherence.check(front, {"sites": {}}, {})
    assert код == coherence.UNMEASURABLE
    assert "error" in отчёт


def test_declared_source_dirty_is_surfaced(tmp_path):
    """Ложное source_dirty обязано быть видно в отчёте, а не молчать."""
    front = _front(tmp_path)
    рел = _release(front, "b-new", NEW)
    _bind(front, "lords-01", рел)
    _manifest(front, "lords-01", _sha(NEW), source_dirty=True, source_commit="deadbeef")
    процессы = {9110: {"pid": 1, "exec_script": str(рел / RUNTIME), "started_utc": "t"}}
    _, отчёт = coherence.check(front, _registry(front, {"lords-01": 9110}), процессы)
    assert отчёт["sites"]["lords-01"]["declared_source_dirty"] is True
    assert отчёт["sites"]["lords-01"]["bound_artifact_sha256"] == _sha(NEW)


# --- реестр -----------------------------------------------------------------


def _unit(dir_: pathlib.Path, имя: str, описание: str, порт: int) -> None:
    (dir_ / имя).write_text(
        "[Unit]\n"
        f"Description={описание}\n"
        "[Service]\n"
        f"Environment=LORDS_TEMPLATE_MANIFEST=/srv/lords/.frontend/template-manifest-x.json\n"
        f"ExecStart=/usr/bin/python3 /srv/lords/.frontend/{RUNTIME} --port {порт}\n",
        encoding="utf-8",
    )


def test_registry_reads_units_and_does_not_guess_names(tmp_path):
    """Асимметричное имя юнита берётся как есть, а не приводится к шаблону."""
    units = tmp_path / "units"
    units.mkdir()
    _unit(units, "lords-nova-01.service", "Lords nova frontend: lords-01 (lordfilm47.space)", 9110)
    _unit(units, "nova-lords-02.service", "Lords nova frontend: lords-02 (lordserial33.biz)", 9111)
    repo = tmp_path / "repo"
    (repo / "config" / "site-profiles").mkdir(parents=True)
    for site, домен in (("lords-01", "lordfilm47.space"), ("lords-02", "lordserial33.biz")):
        (repo / "config" / "site-profiles" / f"{site}.json").write_text(
            json.dumps(
                {
                    "site_id": site,
                    "domains": [домен],
                    "seo": {"canonical_host": домен, "indexing_enabled": False},
                }
            ),
            encoding="utf-8",
        )
    реестр = registry_mod.build(units, repo, tmp_path / "front")
    assert реестр["sites"]["lords-01"]["unit"] == "lords-nova-01.service"
    assert реестр["sites"]["lords-02"]["unit"] == "nova-lords-02.service"
    assert реестр["sites"]["lords-01"]["exact_domain"] == "lordfilm47.space"
    assert реестр["conflicts"] == []
    assert реестр["in_registry"] == ["lords-01", "lords-02"]


def test_registry_flags_domain_conflict_between_unit_and_profile(tmp_path):
    units = tmp_path / "units"
    units.mkdir()
    _unit(units, "nova-lords-02.service", "Lords nova frontend: lords-02 (wrong.example)", 9111)
    repo = tmp_path / "repo"
    (repo / "config" / "site-profiles").mkdir(parents=True)
    (repo / "config" / "site-profiles" / "lords-02.json").write_text(
        json.dumps(
            {
                "site_id": "lords-02",
                "domains": ["lordserial33.biz"],
                "seo": {"canonical_host": "lordserial33.biz", "indexing_enabled": False},
            }
        ),
        encoding="utf-8",
    )
    реестр = registry_mod.build(units, repo, tmp_path / "front")
    assert реестр["conflicts"], "расхождение домена юнита и профиля обязано быть замечено"


def test_registry_keeps_sites_without_profile_visible(tmp_path):
    """Витрина без профиля не исчезает: она исполняет тот же файл."""
    units = tmp_path / "units"
    units.mkdir()
    _unit(units, "nova-animedia-01.service", "Animedia nova frontend: animedia-01", 9121)
    repo = tmp_path / "repo"
    (repo / "config" / "site-profiles").mkdir(parents=True)
    реестр = registry_mod.build(units, repo, tmp_path / "front")
    assert реестр["out_of_registry"] == ["animedia-01"]
    assert реестр["sites"]["animedia-01"]["exact_domain"] is None


@pytest.mark.parametrize("порт,ожидание", [(9110, "lords-01"), (9112, "lords-03"), (9999, "")])
def test_loader_maps_port_to_site(tmp_path, порт, ожидание, monkeypatch):
    loader = _load("nova_runtime_dispatch", "nova-runtime-dispatch.py")
    реестр = {"sites": {"lords-01": {"port": 9110}, "lords-03": {"port": 9112}}}
    файл = tmp_path / "lords-runtime-registry.json"
    файл.write_text(json.dumps(реестр), encoding="utf-8")
    monkeypatch.setattr(loader, "REGISTRY", файл)
    assert loader.витрина_по_порту(str(порт)) == ожидание


def test_loader_parses_port_from_both_argument_forms():
    loader = _load("nova_runtime_dispatch", "nova-runtime-dispatch.py")
    assert loader.порт_из_аргументов(["--port", "9111"]) == "9111"
    assert loader.порт_из_аргументов(["--port=9112"]) == "9112"
    assert loader.порт_из_аргументов(["--host", "127.0.0.1"]) == ""
