"""REQ-ADMIN-RELEASES-INCIDENTS-AUDIT: три последних раздела редакционной панели.

Общее правило у всех трёх одно и то же, и оно же — причина, по которой раздел
нельзя было собрать «из чего есть».

**Пустой список и недоступный источник — разные ответы.** Каталог выпусков,
который не читается, обязан сказать это словами. Список из нуля строк на месте
нечитаемого каталога выглядит как «выпусков не было» и в этом виде уже стоил
нам месяцев: каталог тридцатипятичасовой давности отвечал 200 и считался
работающим.

Отбор в журнале проверяется на совпадение по значению, а не на «страница
открылась»: фильтр, который ничего не отсекает, хуже отсутствующего — он
создаёт уверенность, что отобранное и есть всё.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory import audit
from factory.paths import PATHS
from factory.site_engine.admin import ADMIN_COOKIE
from factory.site_engine.admin.app import AdminApp
from factory.site_engine.api import create_api
from factory.site_engine.api.control import ControlApi
from factory.site_engine.store import InMemoryStore

SITE = "js-site"
ТОКЕН = "tok"
REPO = Path(__file__).resolve().parents[2]
H = {"Authorization": f"Bearer {ТОКЕН}"}


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
    for под in ("queue/inbox", "var/locks", "var/audit", "var/state"):
        (tmp_path / под).mkdir(parents=True, exist_ok=True)

    коорд = tmp_path / "coordination" / "v1"
    (коорд / "releases").mkdir(parents=True)
    (коорд / "incidents").mkdir(parents=True)
    (коорд / "releases" / "RELEASE-2026-09-01-core-alpha.json").write_text(
        json.dumps(
            {
                "iteration": "CORE-ALPHA-01",
                "branch": "claude/alpha",
                "headSha": "a" * 40,
                "commitCount": 3,
                "generatedAt": "2026-09-01T10:00:00Z",
                "deployed": {
                    "component": "site-factory-control-api.service",
                    "sha": "b" * 40,
                    "previousSha": "c" * 40,
                    "deployedAt": "2026-09-01T11:00:00Z",
                    "digest": "d" * 64,
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (коорд / "releases" / "RELEASE-2026-09-04-core-beta.json").write_text(
        json.dumps(
            {
                "iteration": "CORE-BETA-02",
                "branch": "claude/beta",
                "headSha": "e" * 40,
                "commitCount": 7,
                "generatedAt": "2026-09-04T10:00:00Z",
                "deployed": {
                    "component": "site-factory-control-api.service",
                    "sha": "f" * 40,
                    "previousSha": "b" * 40,
                    "deployedAt": "2026-09-04T12:00:00Z",
                    "digest": "0" * 64,
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (коорд / "incidents" / "001-cache-key-was-a-url.md").write_text(
        "# 001 Ключ кэша оказался адресом\n\n"
        "- Статус: CLOSED\n- Обнаружено: 2026-08-30\n- Влияние: витрина lords-01\n\n"
        "Исполнитель обошёлся с ключом как с адресом.\n",
        encoding="utf-8",
    )
    (коорд / "incidents" / "004-control-api-stopped-by-broad-pkill.md").write_text(
        "# 004 Широкий pkill остановил боевую службу\n\n"
        "- Статус: OPEN\n- Обнаружено: 2026-09-05\n- Влияние: site-factory-control-api\n\n"
        "Шаблон совпал с боевым процессом.\n",
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture
def env(sandbox):
    return {
        "SITE_ENGINE_CONTROL_WRITES": "1",
        "SITE_ENGINE_CONTROL_TOKENS": f"{ТОКЕН}=read,jobs:write,audit:read,config:write",
        "SITE_ENGINE_COORDINATION_DIR": str(sandbox / "coordination" / "v1"),
    }


@pytest.fixture
def api(sandbox, env):
    return ControlApi(root=sandbox, env=env)


@pytest.fixture
def app(sandbox, env):
    read = create_api(
        [SITE],
        root=sandbox,
        loader=lambda p: (InMemoryStore(p.site_id), "т"),
        env={"SITE_ENGINE_API_ENABLED": "1", "SITE_ENGINE_ENVIRONMENT": "test"},
    )
    return AdminApp(read, ControlApi(root=sandbox, env=env))


def войти(app):
    r = app.handle("POST", "/admin/login", form={"token": ТОКЕН})
    return {ADMIN_COOKIE: r.headers["Set-Cookie"].split(";")[0].split("=", 1)[1]}


@pytest.fixture
def журнал(sandbox):
    """Записи журнала на несколько действующих лиц, витрин и исходов."""
    записи = [
        ("alice", SITE, "control.settings.patch", 0, "cid-1"),
        ("alice", SITE, "control.job.start", 0, "cid-2"),
        ("bob", "other-site", "control.settings.patch", 0, "cid-3"),
        ("bob", SITE, "control.refusal", 1, "cid-4"),
        ("carol", "other-site", "control.cache.invalidate", 1, "cid-5"),
    ]
    for актор, сайт, действие, код, cid in записи:
        audit.record(
            job_id=cid,
            site_id=сайт,
            environment="test",
            action=действие,
            target="цель",
            exit_code=код,
            mutation=код == 0,
            extra={"correlation_id": cid, "actor": актор},
        )
    return записи


class TestВыпуски:
    def test_маршрут_существует(self, api):
        assert api.handle("GET", "/api/v1/releases", headers=H).status == 200

    def test_читаются_настоящие_записи(self, api):
        тело = api.handle("GET", "/api/v1/releases", headers=H).body
        assert тело["available"] is True
        ids = [r["releaseId"] for r in тело["items"]]
        assert "RELEASE-2026-09-04-core-beta" in ids

    def test_новые_первыми(self, api):
        тело = api.handle("GET", "/api/v1/releases", headers=H).body
        assert тело["items"][0]["releaseId"] == "RELEASE-2026-09-04-core-beta"

    def test_видно_что_выложено_и_куда_откатываться(self, api):
        последний = api.handle("GET", "/api/v1/releases", headers=H).body["items"][0]
        assert последний["deployedSha"] == "f" * 40
        assert последний["rollbackTo"] == "b" * 40
        assert последний["component"] == "site-factory-control-api.service"

    def test_недоступный_каталог_говорит_об_этом(self, sandbox, env):
        плохой = dict(env, SITE_ENGINE_COORDINATION_DIR=str(sandbox / "нет-такого"))
        тело = ControlApi(root=sandbox, env=плохой).handle(
            "GET", "/api/v1/releases", headers=H
        ).body
        assert тело["available"] is False
        assert тело["reason"]
        assert тело["items"] == []

    def test_битая_запись_не_роняет_список(self, sandbox, api):
        (sandbox / "coordination" / "v1" / "releases" / "RELEASE-битая.json").write_text(
            "{не json", encoding="utf-8"
        )
        тело = api.handle("GET", "/api/v1/releases", headers=H).body
        assert тело["available"] is True
        assert len(тело["items"]) == 2
        assert "RELEASE-битая" in тело["unreadable"]


class TestПроисшествия:
    def test_маршрут_существует(self, api):
        assert api.handle("GET", "/api/v1/incidents", headers=H).status == 200

    def test_открытые_отделены_от_закрытых(self, api):
        тело = api.handle("GET", "/api/v1/incidents", headers=H).body
        состояния = {i["incidentId"]: i["state"] for i in тело["items"]}
        assert состояния["004-control-api-stopped-by-broad-pkill"] == "OPEN"
        assert состояния["001-cache-key-was-a-url"] == "CLOSED"
        assert тело["open"] == 1

    def test_заголовок_и_влияние_видны(self, api):
        тело = api.handle("GET", "/api/v1/incidents", headers=H).body
        свежее = next(
            i for i in тело["items"] if i["incidentId"].startswith("004")
        )
        assert "pkill" in свежее["title"]
        assert свежее["impact"]

    def test_недоступный_каталог_говорит_об_этом(self, sandbox, env):
        плохой = dict(env, SITE_ENGINE_COORDINATION_DIR=str(sandbox / "нет-такого"))
        тело = ControlApi(root=sandbox, env=плохой).handle(
            "GET", "/api/v1/incidents", headers=H
        ).body
        assert тело["available"] is False and тело["items"] == []


class TestОтборВЖурнале:
    def test_без_отбора_видны_все(self, api, журнал):
        тело = api.handle("GET", "/api/v1/audit", headers=H, body={"limit": 100}).body
        assert тело["matched"] == тело["total"] >= 5

    def test_отбор_по_действующему_лицу(self, api, журнал):
        тело = api.handle(
            "GET", "/api/v1/audit", headers=H, body={"actor": "alice", "limit": 100}
        ).body
        assert тело["matched"] == 2
        assert all((e.get("extra") or {}).get("actor") == "alice" for e in тело["entries"])

    def test_отбор_по_витрине(self, api, журнал):
        тело = api.handle(
            "GET", "/api/v1/audit", headers=H, body={"siteId": "other-site", "limit": 100}
        ).body
        assert тело["matched"] == 2

    def test_отбор_по_действию_по_началу_имени(self, api, журнал):
        тело = api.handle(
            "GET", "/api/v1/audit", headers=H, body={"action": "control.settings", "limit": 100}
        ).body
        assert тело["matched"] == 2

    def test_отбор_по_исходу(self, api, журнал):
        плохие = api.handle(
            "GET", "/api/v1/audit", headers=H, body={"result": "error", "limit": 100}
        ).body
        хорошие = api.handle(
            "GET", "/api/v1/audit", headers=H, body={"result": "ok", "limit": 100}
        ).body
        assert плохие["matched"] == 2
        assert хорошие["matched"] >= 3
        assert плохие["matched"] + хорошие["matched"] == плохие["total"]

    def test_отбор_по_идентификатору_связи(self, api, журнал):
        тело = api.handle(
            "GET", "/api/v1/audit", headers=H, body={"correlationId": "cid-4", "limit": 100}
        ).body
        assert тело["matched"] == 1

    def test_отбор_сочетается(self, api, журнал):
        тело = api.handle(
            "GET",
            "/api/v1/audit",
            headers=H,
            body={"actor": "bob", "siteId": SITE, "limit": 100},
        ).body
        assert тело["matched"] == 1

    def test_совпадений_нет_это_ноль_а_не_все(self, api, журнал):
        тело = api.handle(
            "GET", "/api/v1/audit", headers=H, body={"actor": "нет-такого", "limit": 100}
        ).body
        assert тело["matched"] == 0 and тело["entries"] == []
        assert тело["total"] >= 5, "общее число не должно зависеть от отбора"

    def test_негодный_исход_отклонён_поимённо(self, api, журнал):
        ответ = api.handle("GET", "/api/v1/audit", headers=H, body={"result": "может быть"})
        assert ответ.status == 400
        assert "result" in json.dumps(ответ.body, ensure_ascii=False)

    def test_страницы_не_пересекаются(self, api, журнал):
        первая = api.handle("GET", "/api/v1/audit", headers=H, body={"limit": 2}).body
        вторая = api.handle(
            "GET", "/api/v1/audit", headers=H, body={"limit": 2, "offset": 2}
        ).body
        ключ = lambda e: (e.get("ts"), e.get("job_id"))  # noqa: E731
        assert {ключ(e) for e in первая["entries"]} & {ключ(e) for e in вторая["entries"]} == set()


class TestЭкраны:
    def test_разделы_есть_в_меню(self, app):
        html = app.handle("GET", "/admin", cookies=войти(app)).html
        assert "/admin/releases" in html and "/admin/incidents" in html

    def test_выпуски_открываются_и_показывают_данные(self, app):
        html = app.handle("GET", "/admin/releases", cookies=войти(app)).html
        assert "CORE-BETA-02" in html
        assert "f" * 12 in html

    def test_происшествия_открываются_и_различают_состояние(self, app):
        html = app.handle("GET", "/admin/incidents", cookies=войти(app)).html
        assert "pkill" in html
        assert "OPEN" in html and "CLOSED" in html

    def test_журнал_отбирает_по_форме(self, app, журнал):
        cookies = войти(app)
        все = app.handle("GET", "/admin/audit", cookies=cookies).html
        часть = app.handle("GET", "/admin/audit", form={"actor": "alice"}, cookies=cookies).html
        assert "bob" in все
        assert "bob" not in часть
        assert "alice" in часть

    def test_недоступный_источник_виден_на_экране(self, sandbox, env):
        плохой = dict(env, SITE_ENGINE_COORDINATION_DIR=str(sandbox / "нет-такого"))
        read = create_api(
            [SITE],
            root=sandbox,
            loader=lambda p: (InMemoryStore(p.site_id), "т"),
            env={"SITE_ENGINE_API_ENABLED": "1", "SITE_ENGINE_ENVIRONMENT": "test"},
        )
        приложение = AdminApp(read, ControlApi(root=sandbox, env=плохой))
        r = приложение.handle("POST", "/admin/login", form={"token": ТОКЕН})
        cookies = {ADMIN_COOKIE: r.headers["Set-Cookie"].split(";")[0].split("=", 1)[1]}
        html = приложение.handle("GET", "/admin/releases", cookies=cookies).html
        assert "недоступен" in html.lower() or "не читается" in html.lower()
        assert "Выпусков нет" not in html, "нечитаемый источник — не пустой список"
