"""yummy-b016-release.py: намеренные отказы на временных данных (поддельный docker, временные git).

Ни одного обращения к настоящему docker, compose.vars или сайтам: все пути и команды
подменены, временные каталоги — в var/test-yummy-b016 (правило тестов).
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "automation/host/yummy-b016/yummy-b016-release.py"
FIX = ROOT / "tests/fixtures/yummy_b016"
SVCS = ("web-biz", "web-org", "web-site")
VARS = {"web-biz": "WEB_BIZ_IMAGE", "web-org": "WEB_ORG_IMAGE", "web-site": "WEB_SITE_IMAGE"}


@pytest.fixture
def tmp_path():
    путь = ROOT / "var" / "test-yummy-b016" / ("tmp-" + uuid.uuid4().hex[:8])
    путь.mkdir(parents=True)
    yield путь
    subprocess.run(["chmod", "-R", "u+w", str(путь)], check=False)
    shutil.rmtree(путь, ignore_errors=True)


def _git(repo: Path, *a: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *a], check=True, capture_output=True, text=True).stdout.strip()


REAL_ENV = Path("/srv/sites/yummyani-staging/runtime/compose.vars")


@pytest.fixture(autouse=True)
def real_compose_vars_untouched():
    """Страж: боевой compose.vars после каждого теста байт в байт прежний."""
    before = REAL_ENV.read_bytes() if REAL_ENV.exists() else None
    yield
    after = REAL_ENV.read_bytes() if REAL_ENV.exists() else None
    assert before == after, "тест изменил боевой compose.vars"


@pytest.fixture
def world(tmp_path, monkeypatch):
    """Три «живые базы» во временном репозитории, compose.vars, поддельные docker и проверки."""
    # Все пути — временные ДО загрузки модуля: ни одно умолчание не может указать на боевые.
    for k, v in {"YB_APP_REPO": tmp_path / "app", "YB_BUILD_ROOT": tmp_path / "build", "YB_ENV_FILE": tmp_path / "compose.vars",
                 "YB_BASE_COMPOSE_DIR": tmp_path / "basecompose", "YB_PATCH_DIR": tmp_path / "patches",
                 "YB_PATCH_SUMS": tmp_path / "PATCHES.sha256", "YB_STATE_ROOT": tmp_path / "state",
                 "YB_WARM_PAUSE": tmp_path / "warm-pause.json", "YB_DOCKER": FIX / "fake_docker.py"}.items():
        monkeypatch.setenv(k, str(v))
    spec = importlib.util.spec_from_file_location("yb_release", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "yb_release", mod)
    spec.loader.exec_module(mod)

    app = tmp_path / "app"
    app.mkdir()
    _git(app, "init", "-q")
    _git(app, "config", "user.email", "t@t")
    _git(app, "config", "user.name", "t")
    bases = {}
    for svc in SVCS:
        (app / "app.txt").write_text(f"base {svc}\n")
        (app / "compose.staging.yaml").write_text("services: {}\n")
        _git(app, "add", "-A")
        _git(app, "commit", "-q", "-m", svc)
        bases[svc] = _git(app, "rev-parse", "HEAD")
    patches = tmp_path / "patches"
    patches.mkdir()
    # Патчи теста добавляют новые файлы — применяются к любой базе.
    def newfile(name, line):
        return f"--- /dev/null\n+++ b/{name}\n@@ -0,0 +1 @@\n+{line}\n"
    (patches / "b016-sitemap-swr.v2.patch").write_text(newfile("swr.txt", "swr"))
    (patches / "b016-sitemap-cap.patch").write_text(newfile("cap.txt", "cap"))
    (patches / "yummy-public-wording.patch").write_text(newfile("wording.txt", "wording"))
    (patches / "t081-shelf-canonical-href.patch").write_text(newfile("t081.txt", "t081"))
    (patches / "t081-shelf-canonical-href.4c5796e.patch").write_text(newfile("t081.txt", "t081 rebased"))
    import hashlib
    sums = tmp_path / "PATCHES.sha256"
    sums.write_text("".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  var/yummy-patches/{p.name}\n" for p in sorted(patches.iterdir())))

    basecompose = tmp_path / "basecompose"
    basecompose.mkdir()
    (basecompose / "compose.staging.yaml").write_text("services: {}\n")
    _git(basecompose, "init", "-q")
    _git(basecompose, "config", "user.email", "t@t")
    _git(basecompose, "config", "user.name", "t")
    _git(basecompose, "add", "-A")
    _git(basecompose, "commit", "-q", "-m", "base")
    overrides = [tmp_path / "ov1.yaml", tmp_path / "ov2.yaml"]
    for o in overrides:
        o.write_text("services: {}\n")

    env_file = tmp_path / "compose.vars"
    old = {svc: f"yummyani/web:rel-{bases[svc][:12]}" for svc in SVCS}
    env_file.write_text("POSTGRES_PASSWORD=x\n" + "".join(f"{VARS[s]}={old[s]}\n" for s in SVCS) + "OTHER=1\n")
    env_file.chmod(0o600)

    pub = {"web-biz": "10375", "web-org": "10377", "web-site": ""}
    containers, images, cfg = {}, {}, {"services": {}}
    for svc in SVCS:
        env = [f"CDNVIDEOHUB_PUBLISHER_ID_PINNED={pub[svc]}", "SEO_INDEXING_ENABLED=true", "TITLE_OVERLAYS_PATH=/o", "SITE_PROFILE=" + svc[4:]]
        images[old[svc]] = {"id": "sha256:old-" + svc, "revision": bases[svc], "env": []}
        containers[f"yummyani-staging-{svc}-1"] = {"image_ref": old[svc], "env": env, "health": "healthy", "mounts": ["/o", "/run/secrets/m"]}
        cfg["services"][svc] = {"environment": dict(e.split("=", 1) for e in env), "volumes": [{"type": "bind", "target": "/o"}],
                                "secrets": [{"source": "m"}]}
    state_file = tmp_path / "docker.json"
    state_file.write_text(json.dumps({"calls": [], "containers": containers, "images": images, "config": cfg, "fail": {}}))
    check_log = tmp_path / "check.log"
    check_log.write_text("")

    monkeypatch.setenv("FAKE_DOCKER_STATE", str(state_file))
    monkeypatch.setenv("FAKE_CHECK_LOG", str(check_log))
    monkeypatch.setenv("YB_BACKUP_CMD", json.dumps(["true"]))
    T = mod.Tenant
    common = ("b016-sitemap-swr.v2.patch", "b016-sitemap-cap.patch", "yummy-public-wording.patch")
    tenants = [T("web-biz", "WEB_BIZ_IMAGE", "yummyani.biz", bases["web-biz"][:12], common + ("t081-shelf-canonical-href.4c5796e.patch",)),
               T("web-org", "WEB_ORG_IMAGE", "yummyani.org", bases["web-org"][:12], common + ("t081-shelf-canonical-href.patch",)),
               T("web-site", "WEB_SITE_IMAGE", "yummyani.site", bases["web-site"][:12], common + ("t081-shelf-canonical-href.patch",))]
    for k, v in {"APP_REPO": app, "BUILD_ROOT": tmp_path / "build", "ENV_FILE": env_file, "BASE_COMPOSE_DIR": basecompose,
                 "BASE_COMPOSE_SHA": _git(basecompose, "rev-parse", "HEAD")[:12], "OVERRIDES": overrides,
                 "PATCH_DIR": patches, "PATCH_SUMS": sums, "STATE_ROOT": tmp_path / "state", "WARM_PAUSE": tmp_path / "warm-pause.json",
                 "DOCKER": str(FIX / "fake_docker.py"), "CHECK": [sys.executable, str(FIX / "fake_check.py")],
                 "TENANTS": tenants, "BY_SERVICE": {t.service: t for t in tenants},
                 "HEALTH_TIMEOUT": 0.2, "HEALTH_POLL": 0.01, "SLEEP": lambda s: None, "STATE_PORTS": {}}.items():
        monkeypatch.setattr(mod, k, v)

    class W:
        pass
    w = W()
    w.mod, w.app, w.env_file, w.state_file, w.check_log, w.bases, w.old, w.tmp = mod, app, env_file, state_file, check_log, bases, old, tmp_path
    w.docker = lambda: json.loads(state_file.read_text())
    w.set_fail = lambda **f: state_file.write_text(json.dumps({**w.docker(), "fail": f}))
    w.mutations = lambda: [c for c in w.docker()["calls"] if c[0] == "tag" or "up" in c or "build" in c]
    w.ups = lambda: [c[-1] for c in w.docker()["calls"] if c[0] == "compose" and "up" in c]
    w.pins = lambda: dict(l.split("=", 1) for l in env_file.read_text().splitlines() if "=" in l)
    return w


# ------------------------------------------------------------------ сборка: только тег наружу, любой отказ — код 4
def test_build_prints_only_tags(world, capsys):
    assert world.mod.main(["build"]) == 0
    out = capsys.readouterr().out.strip().splitlines()
    assert len(out) == 3
    assert all(world.mod.TAG_RE.match(line) for line in out), out   # шум git/patch/сборки — не в stdout
    assert world.ups() == []                                          # контейнеры не тронуты


@pytest.mark.parametrize("how", ["worktree_exists", "bad_patch", "missing_patch", "commit_hook"])
def test_build_git_and_patch_failures_stop_release(world, how):
    t = world.mod.TENANTS[0]
    if how == "worktree_exists":
        (world.mod.BUILD_ROOT / world.tmp.name / t.base).mkdir(parents=True)
    elif how == "bad_patch":
        p = world.mod.PATCH_DIR / "b016-sitemap-cap.patch"
        p.write_text("--- a/app.txt\n+++ b/app.txt\n@@ -1 +1 @@\n-нет такой строки\n+x\n")
        import hashlib
        sums = world.mod.PATCH_SUMS
        sums.write_text("".join(f"{hashlib.sha256(q.read_bytes()).hexdigest()}  var/yummy-patches/{q.name}\n" for q in sorted(world.mod.PATCH_DIR.iterdir())))
    elif how == "commit_hook":
        hook = world.app / ".git/hooks/pre-commit"
        hook.write_text("#!/bin/sh\nexit 1\n")
        hook.chmod(0o755)
    elif how == "missing_patch":
        t = world.mod.Tenant(t.service, t.var, t.domain, t.base, t.patches + ("нет-такого.patch",))
    with pytest.raises(world.mod.Stop) as e:
        world.mod.build_one(t, world.tmp)
    assert e.value.code == 4
    assert world.ups() == []


@pytest.mark.parametrize("fail", ["build", "label", "tag"])
def test_build_docker_failures_stop_release(world, fail):
    world.set_fail(**{fail: True})
    assert world.mod.main(["run", "--no-accept"]) == 4
    assert world.ups() == []                    # ни одного пересоздания
    assert {v: world.pins()[v] for v in VARS.values()} == {VARS[s]: world.old[s] for s in SVCS}


# ------------------------------------------------------------------ preflight: условия остановки до мутаций
@pytest.mark.parametrize("breakage", ["missing_pin", "duplicate_pin", "bad_format", "base_moved", "publisher_differs",
                                      "indexing_off", "mounts_differ", "dirty_base_compose", "unhealthy", "patch_hash"])
def test_preflight_stops_before_any_mutation(world, breakage):
    env = world.env_file.read_text()
    d = world.docker()
    if breakage == "missing_pin":
        world.env_file.write_text(env.replace(f"WEB_ORG_IMAGE={world.old['web-org']}\n", ""))
    elif breakage == "duplicate_pin":
        world.env_file.write_text(env + f"WEB_ORG_IMAGE={world.old['web-org']}\n")
    elif breakage == "bad_format":
        world.env_file.write_text(env.replace(world.old["web-site"], "yummyani/web:staging"))
    elif breakage == "base_moved":
        d["images"][world.old["web-org"]]["revision"] = "f" * 40
    elif breakage == "publisher_differs":
        d["config"]["services"]["web-biz"]["environment"]["CDNVIDEOHUB_PUBLISHER_ID_PINNED"] = "99999"
    elif breakage == "indexing_off":
        for k in ("config",):
            d[k]["services"]["web-biz"]["environment"]["SEO_INDEXING_ENABLED"] = "false"
    elif breakage == "mounts_differ":
        d["config"]["services"]["web-site"]["volumes"] = []
    elif breakage == "dirty_base_compose":
        (world.mod.BASE_COMPOSE_DIR / "compose.staging.yaml").write_text("services: {x: {}}\n")
    elif breakage == "unhealthy":
        d["containers"]["yummyani-staging-web-org-1"]["health"] = "unhealthy"
    elif breakage == "patch_hash":
        (world.mod.PATCH_DIR / "b016-sitemap-swr.v2.patch").write_text("изменён\n")
    world.state_file.write_text(json.dumps(d))
    before = world.env_file.read_text()
    assert world.mod.main(["run", "--no-accept"]) == 3
    assert world.mutations() == []
    assert world.env_file.read_text() == before


# ------------------------------------------------------------------ compose.vars: атомарно, права сохранены
def test_set_pin_is_atomic_and_keeps_mode(world):
    new = "yummyani/web:rel-" + "a" * 12
    world.mod.set_pin("WEB_ORG_IMAGE", new)
    assert world.pins()["WEB_ORG_IMAGE"] == new
    assert world.pins()["POSTGRES_PASSWORD"] == "x" and world.pins()["OTHER"] == "1"
    assert stat.S_IMODE(world.env_file.stat().st_mode) == 0o600
    assert world.env_file.read_text().count("WEB_ORG_IMAGE=") == 1


def test_set_pin_failure_leaves_original(world, monkeypatch):
    before = world.env_file.read_text()
    monkeypatch.setattr(world.mod.os, "replace", lambda *a: (_ for _ in ()).throw(OSError("диск")))
    with pytest.raises(OSError):
        world.mod.set_pin("WEB_ORG_IMAGE", "yummyani/web:rel-" + "b" * 12)
    assert world.env_file.read_text() == before
    assert [p.name for p in world.env_file.parent.iterdir() if p.name.startswith(".compose.vars.")] == []


def test_set_pin_refuses_bad_value(world):
    with pytest.raises(world.mod.Stop):
        world.mod.set_pin("WEB_ORG_IMAGE", "yummyani/web:staging\nEVIL=1")


# ------------------------------------------------------------------ выкладка: откат только текущей витрины
def test_full_run_deploys_in_order(world):
    assert world.mod.main(["run", "--no-accept"]) == 0
    assert world.ups() == ["web-biz", "web-org", "web-site"]
    for s in SVCS:
        assert world.pins()[VARS[s]] != world.old[s] and world.mod.TAG_RE.match(world.pins()[VARS[s]])
    state = next((world.mod.STATE_ROOT).iterdir())
    acts = [json.loads(l)["action"] for l in (state / "journal.jsonl").read_text().splitlines()]
    assert acts.count("deploy") == 3 and "backup" in acts


def test_unhealthy_new_image_rolls_back_only_that_site(world):
    world.set_fail(health_new="web-org")
    assert world.mod.main(["run", "--no-accept"]) == 5
    assert world.ups() == ["web-biz", "web-org", "web-org"]          # org: выкладка и откат; site не трогали
    p = world.pins()
    assert p["WEB_ORG_IMAGE"] == world.old["web-org"]               # закрепление org возвращено
    assert p["WEB_BIZ_IMAGE"] != world.old["web-biz"]               # biz принят и остался
    assert p["WEB_SITE_IMAGE"] == world.old["web-site"]
    c = world.docker()["containers"]["yummyani-staging-web-org-1"]
    assert c["image_ref"] == world.old["web-org"] and c["health"] == "healthy"


def test_failed_acceptance_rolls_back_and_stops(world, monkeypatch):
    monkeypatch.setenv("FAKE_CHECK_RC", json.dumps({"links:yummyani.biz": 1}))
    assert world.mod.main(["run", "--no-accept"]) == 5
    assert world.ups() == ["web-biz", "web-biz"]
    assert world.pins()["WEB_BIZ_IMAGE"] == world.old["web-biz"]


def test_failed_rollback_is_reported_as_needs_human(world):
    world.set_fail(health_new="web-biz", up_rollback=True)
    assert world.mod.main(["run", "--no-accept"]) == 6


def test_backup_failure_stops_before_recreate(world, monkeypatch):
    monkeypatch.setenv("YB_BACKUP_CMD", json.dumps(["false"]))
    assert world.mod.main(["run", "--no-accept"]) == 5
    assert world.ups() == []


def test_manual_rollback_uses_recorded_previous_image(world):
    assert world.mod.main(["run", "--no-accept"]) == 0
    assert world.mod.main(["rollback", "--service", "web-site"]) == 0
    assert world.pins()["WEB_SITE_IMAGE"] == world.old["web-site"]
    assert world.pins()["WEB_BIZ_IMAGE"] != world.old["web-biz"]


# ------------------------------------------------------------------ приёмка постоянного исправления
def _fetcher(seq):
    """seq: список «волн» ответов; каждый вызов fetch берёт следующий ответ по кругу внутри волны."""
    calls = {"n": 0}

    def fetch(domain, path, timeout=120):
        calls["n"] += 1
        return seq(calls["n"], domain, path)
    return fetch


def test_accept_observes_stale_then_background_refresh(world, monkeypatch):
    state = world.tmp / "st"
    state.mkdir()
    n_sweep = 9  # 3 домена × 3 части

    def seq(n, domain, path):
        if n <= n_sweep:                       # первый проход: свежий, возраст 3500
            inv, t = "fresh; age=3500", 0.2
        elif n <= 2 * n_sweep:                 # после ожидания: устаревший — ответ сразу
            inv, t = "stale; age=3650", 0.3
        else:                                  # фоновая перестройка завершилась
            inv, t = "fresh; age=40", 0.2
        loc = 8600 if "titles" in path else 100
        return {"code": 200, "t": t, "loc": loc, "body": "", "inventory": inv}
    monkeypatch.setattr(world.mod, "fetch", _fetcher(seq))
    rep = world.mod.accept(state)
    assert rep["ok"] and rep["checks"]["stale_observed"] and rep["checks"]["background_refresh"]
    assert rep["checks"]["cold_start"]["observed"] is False
    assert not world.mod.WARM_PAUSE.exists()   # пауза снята


@pytest.mark.parametrize("bad", ["504", "cap", "no_header", "links"])
def test_accept_fails_honestly_and_resumes_warmup(world, monkeypatch, bad):
    state = world.tmp / "st"
    state.mkdir()

    def seq(n, domain, path):
        inv = "" if bad == "no_header" else ("stale; age=3700" if n <= 18 else "fresh; age=10")
        code = 504 if (bad == "504" and n == 12) else 200
        loc = 8000 if (bad == "cap" and "titles" in path) else (8600 if "titles" in path else 10)
        return {"code": code, "t": 0.3, "loc": loc, "body": "", "inventory": inv}
    monkeypatch.setattr(world.mod, "fetch", _fetcher(seq))
    if bad == "links":
        monkeypatch.setenv("FAKE_CHECK_RC", json.dumps({"links:yummyani.site": 1}))
    with pytest.raises(world.mod.Stop) as e:
        world.mod.accept(state)
    assert e.value.code == 7
    assert not world.mod.WARM_PAUSE.exists()


# ------------------------------------------------------------------ B031: полное название в <title>
def test_b031_titles_checked_before_and_after_and_failure_rolls_back(world, monkeypatch):
    monkeypatch.setenv("FAKE_CHECK_RC", json.dumps({"titles:yummyani.org": 1}))
    assert world.mod.main(["run", "--no-accept"]) == 5
    log = world.check_log.read_text().splitlines()
    assert any(l.startswith("titles --save ") for l in log), "снимок страниц до выпуска не сделан"
    assert any(l.startswith("titles --against ") and l.endswith(" yummyani.org") for l in log)
    assert world.pins()["WEB_ORG_IMAGE"] == world.old["web-org"]          # откат только org
    assert world.ups()[-2:] == ["web-org", "web-org"]


def test_b031_rule_on_measured_titles():
    spec = importlib.util.spec_from_file_location("yb_check", ROOT / "automation/host/yummy-b016/yummy-b016-check.py")
    c = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(c)
    h1 = "Невероятное приключение ДжоДжо: Гонка «Стальной шар» — 7 сезон, 4 серия: Эпизод 4"
    cut = {"title": "Невероятное приключение ДжоДжо: Гонка — 7 сезон, 4 серия | YummyAnime", "h1": h1}
    full = {"title": "Невероятное приключение ДжоДжо: Гонка «Стальной шар» — 7 сезон, 4 серия", "h1": h1}
    assert not c.name_kept(cut) and c.name_kept(full)
    witch = "Я ведьма, которую возлюбленный попросил создать любовное зелье"
    assert not c.name_kept({"title": "Я ведьма, которую возлюбленный попросил создать любовное | YummyAnime", "h1": witch})
    assert c.name_kept({"title": witch, "h1": witch})
    assert c.name_kept({"title": "Пример — смотреть аниме онлайн | YummyAnime", "h1": "Пример"})
