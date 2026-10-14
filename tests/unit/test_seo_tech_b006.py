"""B006 (14.10): самостоятельный цикл технического SEO — восстановление, пополнение, выпуск."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import uuid
from pathlib import Path

import pytest

from seo_operator import tech_backlog, tech_publish, tech_run

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def tmp_path():
    """Временный каталог внутри var/ (правило тестов: не писать за пределы var/ и artifacts/)."""
    путь = ROOT / "var" / "test-seo-tech" / ("tmp-" + uuid.uuid4().hex[:8])
    путь.mkdir(parents=True)
    yield путь
    shutil.rmtree(путь, ignore_errors=True)
WRAPPER = ROOT / "automation" / "host" / "editor" / "seo-tech-run.sh"


def _git(репо: Path, *a: str) -> str:
    return subprocess.run(["git", "-C", str(репо), *a], check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def среда(monkeypatch):
    корень = ROOT / "var" / "test-seo-tech" / uuid.uuid4().hex[:8]
    репо = корень / "repo"
    (репо / "checks").mkdir(parents=True)
    (репо / "page.html").write_text("<title>t</title>")
    _git(репо, "init", "-q", "-b", "main")
    _git(репо, "-c", "user.email=t@t", "-c", "user.name=t", "add", ".")
    _git(репо, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "база")
    rel = str(репо.relative_to(ROOT))
    задачи = [{"id": "T901", "repo": rel, "status": "queued", "check": "checks/a.py", "site": "x", "problem": "p"},
              {"id": "T902", "repo": rel, "status": "queued", "check": "checks/b.py", "site": "x", "problem": "p"}]
    очередь = корень / "queue.json"
    очередь.write_text(json.dumps({"tasks": задачи}))
    monkeypatch.setattr(tech_run, "QUEUE", очередь)
    state = корень / "state"
    state.mkdir(parents=True)
    yield {"репо": репо, "state": state, "задачи": задачи, "очередь": очередь, "корень": корень}
    shutil.rmtree(корень, ignore_errors=True)


def _мёртвый_pid() -> int:
    п = subprocess.Popen(["true"])
    п.wait()
    return п.pid


def test_dead_owner_frees_task_at_once_and_counts_attempt(среда, monkeypatch):
    s = среда["state"]
    monkeypatch.setenv("SEO_TECH_OWNER_PID", str(_мёртвый_pid()))
    tech_run.claim(среда["задачи"][0], "R1", state=s)
    # Владелец мёртв: задача доступна сразу, без ожидания STALE_S.
    задачи = tech_run.load_queue(среда["очередь"], state=s)
    assert [з["id"] for з in tech_run.candidates(задачи, s)][0] == "T901"
    закрыто = tech_run.закрыть_брошенные(s)
    assert закрыто == ["T901"]
    сводка = tech_run.task_state(s)
    assert сводка["T901"]["failures"] == 1
    assert сводка["T901"]["last"]["verdict"] == "INTERRUPTED"


def test_live_owner_keeps_claim(среда, monkeypatch):
    s = среда["state"]
    monkeypatch.setenv("SEO_TECH_OWNER_PID", str(os.getpid()))
    tech_run.claim(среда["задачи"][0], "R2", state=s)
    задачи = tech_run.load_queue(среда["очередь"], state=s)
    assert [з["id"] for з in tech_run.candidates(задачи, s)] == ["T902"]


def test_three_interruptions_exhaust_attempts(среда, monkeypatch):
    s = среда["state"]
    for i in range(3):
        monkeypatch.setenv("SEO_TECH_OWNER_PID", str(_мёртвый_pid()))
        tech_run.claim(среда["задачи"][0], f"R3-{i}", state=s)
        tech_run.prune_worktrees(state=s)
    задачи = tech_run.load_queue(среда["очередь"], state=s)
    assert "T901" not in [з["id"] for з in tech_run.candidates(задачи, s)]
    assert tech_run.task_state(s)["T901"]["failures"] == 3


def test_claim_failure_of_one_task_does_not_stop_queue(среда):
    s = среда["state"]
    плохая = {"id": "T903", "repo": "var/test-seo-tech/нет-такого", "status": "queued", "check": "c", "site": "x", "problem": "p"}
    задачи = [плохая] + среда["задачи"]
    захват = tech_run.claim_next(задачи, "R4", state=s)
    assert захват and захват["task_id"] == "T901"
    assert tech_run.task_state(s)["T903"]["last"]["verdict"] == "CLAIM_FAILED"


def test_auto_tasks_merge_and_config_wins(среда):
    s = среда["state"]
    (s / tech_run.AUTO_QUEUE_NAME).write_text(json.dumps({"tasks": [
        {"id": "T901", "status": "queued", "site": "чужой"}, {"id": "A0001", "status": "queued", "site": "y"}]}))
    задачи = tech_run.load_queue(среда["очередь"], state=s)
    assert [з["id"] for з in задачи] == ["T901", "T902", "A0001"]
    assert задачи[0]["site"] == "x" and задачи[2]["source"] == "auto"


def test_superseded_returns_task_to_preparation(среда):
    s = среда["state"]
    tech_run.record({"run_id": "V1", "task_id": "T901", "verdict": "VERIFIED"}, {}, s)
    assert tech_run.task_state(s)["T901"]["status"] == "verified"
    tech_run.record({"run_id": "V1-superseded", "task_id": "T901", "verdict": "SUPERSEDED"}, {}, s)
    с = tech_run.task_state(s)["T901"]
    assert "status" not in с and с["failures"] == 0


def test_stale_player_is_not_linked(tmp_path):
    репо, копия = tmp_path / "r", tmp_path / "w"
    (репо / "config").mkdir(parents=True)
    (копия / "config").mkdir(parents=True)
    (репо / "config" / "player.json").write_text(json.dumps({"publisher_id": "1"}))
    (копия / "config" / "site.json").write_text(json.dumps({"publisher_id_expected": "2"}))
    # Несовпадение: не ссылка на устаревший файл, а фикстура из публичного ожидаемого значения.
    assert tech_run.связать_неотслеживаемые(репо, копия) == ["config/player.json (фикстура)"]
    цель = копия / "config" / "player.json"
    assert not цель.is_symlink() and json.loads(цель.read_text())["publisher_id"] == "2"
    цель.unlink()
    (копия / "config" / "site.json").write_text(json.dumps({"publisher_id_expected": "1"}))
    assert tech_run.связать_неотслеживаемые(репо, копия) == ["config/player.json"]
    assert цель.is_symlink()


# ------------------------------------------------------------------ выпуск

ЖИВОЙ = "a" * 40


def _сведения(**k):
    база = {"live": ЖИВОЙ, "ci_commit": ЖИВОЙ, "remote_head": ЖИВОЙ, "head": "b" * 40,
            "head_in_live": False, "live_in_head": True, "clone_dirty": False, "clone_on_live": True}
    return {**база, **k}


@pytest.mark.parametrize("поля, действие", [
    ({}, "publish"),
    ({"hold": "владелец"}, "hold"),
    ({"head_in_live": True}, "already_live"),
    ({"ci_commit": "c" * 40}, "wait"),          # чужой невыпущенный коммит на ветке выпуска (Zona, publisher_id)
    ({"remote_head": "d" * 40}, "wait"),        # идёт CI или чужой push
    ({"clone_dirty": True}, "wait"),            # в общем клоне работает другая сессия
    ({"clone_on_live": False}, "wait"),
    ({"live_in_head": False}, "superseded"),    # ветка не на живом коммите — повторная подготовка
    ({"live": ""}, "wait"),
])
def test_publish_decision(поля, действие):
    assert tech_publish.решение(_сведения(**поля))[0] == действие


def test_live_check_without_task_probe_is_released_not_live_verified():
    http = lambda u: (200, "<html>Disallow: /random/</html>")  # noqa: E731
    итог = tech_publish.проверить_живой("x.test", None, http)
    assert итог["health"] and итог["task"] is None
    итог = tech_publish.проверить_живой("x.test", [{"url": "https://x.test/robots.txt", "contains": ["Disallow: /random/"]}], http)
    assert итог["task"] is True
    итог = tech_publish.проверить_живой("x.test", [{"url": "https://x.test/robots.txt", "absent": ["Disallow"]}], http)
    assert итог["task"] is False


# ------------------------------------------------------------------ пополнение

def test_backlog_from_regular_maps_only_tech_codes(tmp_path):
    st = tmp_path / "state.json"
    st.write_text(json.dumps({"open_issues_check": {
        "a.test|ROBOTS_WITHOUT_SITEMAP": {"domain": "a.test", "code": "ROBOTS_WITHOUT_SITEMAP", "detail": "нет"},
        "a.test|DNS_UNRESOLVED": {"domain": "a.test", "code": "DNS_UNRESOLVED"},
        "b.test|SITEMAP_SLOW": {"domain": "b.test", "code": "SITEMAP_SLOW"}}}))
    cells = {"a.test": {"repo": "var/site-repos/a", "direction": "lords", "site_id": "a"}}
    out = tech_backlog.from_regular(st, cells)
    assert [з["source"] for з in out] == ["auto:regular:a.test:ROBOTS_WITHOUT_SITEMAP"]


def test_backlog_links_flags_redirect_error_and_noindex_but_not_intentional():
    страницы = {
        "https://a.test/": (200, "", '<a href="/ok/"></a><a href="/old/"></a><a href="/random/"></a>'
                                     '<a href="/gone/"></a><a href="/closed/"></a><a href="/catalog/?f=1"></a>'),
        "https://a.test/catalog/": (200, "", ""),
        "https://a.test/ok/": (200, "", "<meta name=\"robots\" content=\"index, follow\">"),
        "https://a.test/old/": (308, "/new/", ""),
        "https://a.test/gone/": (404, "", ""),
        "https://a.test/closed/": (200, "", "<meta name=\"robots\" content=\"noindex, follow\">"),
        "https://a.test/catalog/?f=1": (200, "", "<meta name=\"robots\" content=\"noindex, follow\">"),
    }
    out = tech_backlog.from_links({"a.test": {"repo": "r", "direction": "anime", "site_id": "a"}},
                                  lambda u: страницы.get(u, (200, "", "")))
    assert len(out) == 1
    текст = out[0]["problem"]
    assert "/old/" in текст and "/gone/" in текст and "/closed/" in текст
    assert "/random/" not in текст and "?f=1" not in текст and "/ok/" not in текст


def test_backlog_run_adds_once_validates_and_dedupes_by_url(tmp_path, monkeypatch):
    state = tmp_path / "st"
    state.mkdir()
    очередь = tmp_path / "q.json"
    очередь.write_text(json.dumps({"tasks": [{"id": "T950", "site": "a.test", "problem": "p", "status": "session",
                                              "urls": ["https://a.test/busy/"]}]}))
    monkeypatch.setattr(tech_run, "QUEUE", очередь)
    monkeypatch.setattr(tech_backlog, "promoted_cells", lambda *_a, **_k: {"a.test": {"repo": "var/site-repos/a", "direction": "anime", "site_id": "a"}})
    reg = tmp_path / "regular.json"
    reg.write_text(json.dumps({"open_issues_check": {"a.test|HOME_SLOW": {"domain": "a.test", "code": "HOME_SLOW", "detail": "5 с"}}}))
    fetch = lambda u: (200, "", "")  # noqa: E731 — ссылок и карт нет
    monkeypatch.setattr(tech_run, "load_queue", _загрузчик(очередь))
    первый = tech_backlog.run(state, links=True, fetch=fetch, regular_state=reg)
    assert len(первый["added"]) == 1
    второй = tech_backlog.run(state, links=True, fetch=fetch, regular_state=reg)
    assert второй["added"] == []
    авто = json.loads((state / "auto-tasks.json").read_text())["tasks"]
    assert авто[0]["id"] == "A0001" and авто[0]["status"] == "queued" and авто[0]["check"]


def _загрузчик(очередь: Path):
    def загрузить(путь: Path = очередь, state: Path | None = None):
        данные = json.loads(очередь.read_text())["tasks"]
        авто = (state or tech_run.STATE) / tech_run.AUTO_QUEUE_NAME
        if авто.is_file():
            ид = {з["id"] for з in данные}
            данные += [з for з in json.loads(авто.read_text())["tasks"] if з["id"] not in ид]
        return данные
    return загрузить


def test_ports_created_only_after_parent_published():
    cells = {"b.test": {"repo": "var/site-repos/b", "direction": "lords", "site_id": "b"}}
    родитель = {"id": "T960", "site": "a.test", "status": "queued", "port_to": ["b.test"], "check": "checks/x.py",
                "urls": ["https://a.test/x/"], "problem": "p"}
    assert tech_backlog.from_ports([родитель], set(), cells) == []
    out = tech_backlog.from_ports([родитель], {"T960"}, cells)
    assert out[0]["site"] == "b.test" and out[0]["urls"] == ["https://b.test/x/"]


# ------------------------------------------------------------------ обёртка

def _обёртка(env: dict, timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", str(WRAPPER)], env={**os.environ, **env}, capture_output=True, text=True, timeout=timeout)


def test_wrapper_unwritable_state_is_73_not_busy(tmp_path):
    закрыто = tmp_path / "ro"
    закрыто.mkdir()
    os.chmod(закрыто, 0o500)
    try:
        if os.access(закрыто, os.W_OK):
            pytest.skip("запуск от root — каталог остаётся доступным для записи")
        r = _обёртка({"SEO_TECH_STATE": str(закрыто / "state")})
        assert r.returncode == 73, r.stderr
        assert "занято" not in r.stderr and "другой прогон" not in r.stderr
    finally:
        os.chmod(закрыто, 0o700)


def test_wrapper_busy_is_75(tmp_path):
    import fcntl
    state = tmp_path / "st"
    state.mkdir()
    with open(state / "run.lock", "w") as fd:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        r = _обёртка({"SEO_TECH_STATE": str(state)})
    assert r.returncode == 75


def test_wrapper_preflight_missing_model_is_70_before_claim(tmp_path):
    state = tmp_path / "st"
    r = _обёртка({"SEO_TECH_STATE": str(state), "CLAUDE_BIN": str(tmp_path / "нет-claude")})
    assert r.returncode == 70 and "исполнитель" in r.stderr
    assert not (state / "claims.jsonl").exists()


def test_wrapper_uses_kill_after_grace():
    текст = WRAPPER.read_text(encoding="utf-8")
    assert 'timeout -k "$GRACE_S" "$LIMIT_S"' in текст
    assert "timeout -k 60 \"$VERIFY_LIMIT_S\"" in текст
    assert текст.index("--peek") < текст.index('seo-tech-next --run-id')


def test_cleanup_touches_only_own_worktrees(среда):
    """PrivateTmp службы: чужие рабочие копии (в /tmp сессии) не снимаются (14.10)."""
    s, репо = среда["state"], среда["репо"]
    своя = s / "wt" / "R9"
    чужая = среда["корень"] / "чужая-копия"
    _git(репо, "worktree", "add", "-q", "--detach", str(своя))
    _git(репо, "worktree", "add", "-q", "--detach", str(чужая))
    shutil.rmtree(своя)
    shutil.rmtree(чужая)  # для службы с PrivateTmp копия сессии тоже «исчезла»
    снято = tech_run.убрать_свои_ссылки(репо, s)
    assert len(снято) == 1
    оставшиеся = [p.name for p in (репо / ".git" / "worktrees").iterdir()]
    assert "чужая-копия" in оставшиеся


def test_non_lords_repo_gets_cell_snapshot_path(tmp_path, monkeypatch):
    """T093 14.10: без mini_stand проверке передаётся снимок ячейки, а не «нет снимка»."""
    данные = tmp_path / "srv" / "an1mego-site" / "data"
    данные.mkdir(parents=True)
    (данные / "animego-02-catalog.json").write_text("{}")
    репо = tmp_path / "an1mego-site"
    (репо / "checks").mkdir(parents=True)
    monkeypatch.setattr(tech_run, "КОРНИ_ДАННЫХ", (tmp_path / "srv",))
    среда = tech_run.снимок_стенда(репо, tmp_path / "mini")
    assert среда == {"SITE_DATA_DIR": str(данные), "SITEMAP_CHECK_DATA": str(данные)}
    assert not (tmp_path / "mini").exists()  # снимок ячейки не копируется и не урезается


def test_backlog_pages_flags_sitemap_entries_that_are_not_indexable():
    стр = {
        "https://a.test/sitemap.xml": (200, "", "<loc>https://a.test/s-1.xml</loc>"),
        "https://a.test/s-1.xml": (200, "", "<loc>https://a.test/title/x/</loc><loc>https://a.test/genre/y/</loc><loc>https://a.test/old/</loc>"),
        "https://a.test/title/x/": (200, "", '<link rel="canonical" href="https://a.test/title/x/"><meta name="description" content="достаточно длинное описание страницы"><h1>X</h1>'),
        "https://a.test/genre/y/": (200, "", '<meta name="robots" content="noindex, follow"><h1>Y</h1>'),
        "https://a.test/old/": (404, "", ""),
    }
    out = tech_backlog.from_pages({"a.test": {"repo": "r", "direction": "lords", "site_id": "a"}},
                                  lambda u: стр.get(u, (200, "", "")), per_site=5)
    assert len(out) == 1
    assert "genre/y/ — в карте, но noindex" in out[0]["problem"]
    assert "old/ — в карте, но код 404" in out[0]["problem"]
    assert "title/x/" not in out[0]["problem"]
