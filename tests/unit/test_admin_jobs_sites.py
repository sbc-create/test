"""REQ-ADMIN-JOBS-SITES: задания и витрины в редакционной админке.

Два правила, каждое из-за конкретной лжи, которую легко показать оператору.

**Принятое задание — не выполненное задание.** Панель, отвечающая «готово» на
постановку в очередь, обманывает: работа ещё не начиналась. Состояние берётся
из очереди и из результата, а не из факта успешного HTTP.

**HTTP 200 — не здоровье витрины.** Витрина с пустым или устаревшим каталогом
отвечает 200 и при этом неисправна. Именно так каталог тридцатипятичасовой
давности месяцами считался работающим.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory.paths import PATHS
from factory.site_engine.admin import ADMIN_COOKIE
from factory.site_engine.admin.app import AdminApp
from factory.site_engine.api import create_api
from factory.site_engine.api.control import ControlApi
from factory.site_engine.store import InMemoryStore

SITE = "js-site"
ТОКЕН = "tok"
ENV_CONTROL = {
    "SITE_ENGINE_CONTROL_WRITES": "1",
    "SITE_ENGINE_CONTROL_TOKENS": f"{ТОКЕН}=read,jobs:write,audit:read,config:write",
}
ENV_READ = {"SITE_ENGINE_API_ENABLED": "1", "SITE_ENGINE_ENVIRONMENT": "test"}
REPO = Path(__file__).resolve().parents[2]


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setattr(PATHS, "root", tmp_path)
    профили = tmp_path / "config" / "site-profiles"
    профили.mkdir(parents=True)
    образец = json.loads(
        (REPO / "config" / "site-profiles" / "lords-01.json").read_text(encoding="utf-8")
    )
    образец.update({"site_id": SITE, "domains": ["js.test"], "canonical_host": "js.test"})
    (профили / f"{SITE}.json").write_text(json.dumps(образец, ensure_ascii=False), encoding="utf-8")
    for под in (
        "queue/inbox",
        "queue/processing",
        "queue/done",
        "queue/failed",
        "queue/quarantine",
        "var/locks",
        "var/audit",
        "var/state",
        "artifacts/jobs",
    ):
        (tmp_path / под).mkdir(parents=True, exist_ok=True)
    кэш = tmp_path / "var" / "lords" / "lords" / "catalog-cache"
    кэш.mkdir(parents=True)
    (кэш / f"{SITE}.json").write_text(
        json.dumps(
            {
                "fetched_at_ms": 0,
                "source": "test",
                "items": [
                    {
                        "external_id": "e1",
                        "name": "Т",
                        "type": "movie",
                        "playback": {"aggregator": "kp", "title_id": "1"},
                        "external_ids": {"kinopoisk": "1"},
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    # Настоящий результат задания: раздел обязан показывать не только очередь.
    (tmp_path / "artifacts" / "jobs" / SITE).mkdir(parents=True)
    (tmp_path / "artifacts" / "jobs" / SITE / "j1.json").write_text(
        json.dumps(
            {
                "job_id": "j1",
                "site_id": SITE,
                "status": "BLOCKED_SEO",
                "started_at": "2026-09-05T10:00:00Z",
                "finished_at": "2026-09-05T10:01:00Z",
                "checks": [
                    {"id": "seo-render", "passed": False, "exit_code": 1, "artifact": "a.json"}
                ],
                "blockers": [
                    {
                        "status": "BLOCKED_SEO",
                        "field": "seo-render",
                        "reason": "проверка не пройдена",
                    }
                ],
                "notes": [],
                "steps": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture
def env_all(sandbox):
    return {**ENV_CONTROL, "SITE_ENGINE_CATALOG_DIR": "var/lords/lords/catalog-cache"}


@pytest.fixture
def api(sandbox, env_all):
    return ControlApi(root=sandbox, env=env_all), {"Authorization": f"Bearer {ТОКЕН}"}


@pytest.fixture
def app(sandbox, env_all):
    read = create_api(
        [SITE], root=sandbox, loader=lambda p: (InMemoryStore(p.site_id), "т"), env=ENV_READ
    )
    return AdminApp(read, ControlApi(root=sandbox, env=env_all))


def войти(app):
    r = app.handle("POST", "/admin/login", form={"token": ТОКЕН})
    sid = r.headers["Set-Cookie"].split(";")[0].split("=", 1)[1]
    return {ADMIN_COOKIE: sid}


class TestЗадания:
    def test_маршрут_существует(self, api):
        control, h = api
        assert control.handle("GET", "/api/v1/jobs", headers=h).status == 200

    def test_показывает_и_очередь_и_результаты(self, api):
        control, h = api
        тело = control.handle("GET", "/api/v1/jobs", headers=h).body
        assert "queue" in тело and "items" in тело
        assert any(i["jobId"] == "j1" for i in тело["items"])

    def test_различает_принятое_и_выполненное(self, api):
        """Принятое задание — не выполненное. Смешивать нельзя."""
        control, h = api
        задание = next(
            i
            for i in control.handle("GET", "/api/v1/jobs", headers=h).body["items"]
            if i["jobId"] == "j1"
        )
        assert задание["state"] == "BLOCKED"
        assert задание["succeeded"] is False
        assert задание["failedChecks"] == ["seo-render"]

    def test_блокеры_названы_поимённо(self, api):
        control, h = api
        задание = control.handle("GET", "/api/v1/jobs/j1", headers=h).body
        assert задание["blockers"] and задание["blockers"][0]["field"] == "seo-render"


class TestВитрины:
    def test_маршрут_существует(self, api):
        control, h = api
        assert control.handle("GET", f"/api/v1/site-status/{SITE}", headers=h).status == 200

    def test_несёт_контракты_и_флаги(self, api):
        control, h = api
        тело = control.handle("GET", f"/api/v1/site-status/{SITE}", headers=h).body
        for поле in (
            "siteId",
            "domains",
            "contracts",
            "featureFlags",
            "freshness",
            "health",
            "catalog",
        ):
            assert поле in тело, поле

    def test_здоровье_не_равно_ответу_200(self, api, sandbox):
        """Пустой каталог — неисправность, а не здоровая витрина."""
        control, h = api
        кэш = sandbox / "var/lords/lords/catalog-cache" / f"{SITE}.json"
        кэш.write_text(json.dumps({"items": []}), encoding="utf-8")
        тело = control.handle("GET", f"/api/v1/site-status/{SITE}", headers=h).body
        assert тело["health"]["state"] != "HEALTHY"
        assert "EMPTY_CATALOG" in тело["health"]["problems"]

    def test_чужая_витрина_отклонена(self, api):
        control, h = api
        assert control.handle("GET", "/api/v1/site-status/нет-такой", headers=h).status in (
            400,
            404,
        )


class TestСтраницы:
    def test_задания_открываются(self, app):
        r = app.handle("GET", "/admin/jobs", cookies=войти(app))
        assert r.status == 200 and "Задания" in r.html
        assert "j1" in r.html

    def test_страница_не_называет_принятое_выполненным(self, app):
        r = app.handle("GET", "/admin/jobs", cookies=войти(app))
        assert "BLOCKED" in r.html and "seo-render" in r.html

    def test_витрины_открываются(self, app):
        r = app.handle("GET", "/admin/sites", cookies=войти(app))
        assert r.status == 200 and SITE in r.html

    def test_список_витрин_ведёт_на_существующую_страницу(self, app):
        """Новый список не подменяет прежнюю страницу витрины.

        Она уже показывает контракт CMS и полноту каталога; вторая страница
        того же про то же разошлась бы с первой на первой правке.
        """
        r = app.handle("GET", "/admin/sites", cookies=войти(app))
        assert f'href="/admin/sites/{SITE}"' in r.html
        карточка = app.handle("GET", f"/admin/sites/{SITE}", cookies=войти(app))
        assert карточка.status == 200 and "Контракт CMS" in карточка.html
