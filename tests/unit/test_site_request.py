"""REQ-SELF-SERVICE-PLAN: заявка на витрину и её сухой прогон.

Создание витрины сегодня — это редактирование `sites/<id>/package.yaml` руками
и запуск конвейера по SSH. Пока это так, «самообслуживание» существует только
на бумаге: пользователь не может ни завести витрину, ни узнать, чего для неё
не хватает, не получив доступ к машине.

Заявка отвечает на три вопроса до того, как что-либо создано.

**Чего не хватает.** Незаполненный шаг называется по имени, а не превращается в
общее «пакет негоден». Требования берутся из той же проверки, которая потом
будет блокировать сборку: второй список требований разошёлся бы с первой.

**Что будет затронуто.** Сухой прогон перечисляет ресурсы, замки и контракты
поимённо. План без списка ресурсов — это обещание, а не план.

**Что произойдёт при откате.** План отката строится вместе с планом действий, а
не после первой неудачи.

И одно свойство, без которого сухой прогон бесполезен: он **детерминирован**.
Два вызова на одних входных данных дают одинаковый план — иначе «сравните и
подтвердите» не имеет смысла, потому что подтверждают не то, что выполнится.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory.paths import PATHS
from factory.site_engine.admin import ADMIN_COOKIE, CSRF_FIELD
from factory.site_engine.admin.app import AdminApp
from factory.site_engine.api import create_api
from factory.site_engine.api.control import ControlApi
from factory.site_engine.store import InMemoryStore

SITE = "js-site"
ПИШУЩИЙ = "tok-w"
ЧИТАЮЩИЙ = "tok-r"
ENV = {
    "SITE_ENGINE_CONTROL_WRITES": "1",
    "SITE_ENGINE_CONTROL_TOKENS": (
        f"{ПИШУЩИЙ}=read,jobs:write,audit:read,config:write,sites:create"
        f"|{ЧИТАЮЩИЙ}=read,audit:read"
    ),
}
H_W = {"Authorization": f"Bearer {ПИШУЩИЙ}"}
H_R = {"Authorization": f"Bearer {ЧИТАЮЩИЙ}"}
REPO = Path(__file__).resolve().parents[2]

ОТВЕТЫ = {
    "domain": {"domain": "novaya.test", "aliases": ""},
    "profile": {"environment": "staging", "targetRef": "local-disposable",
                "seoProfile": "catalog_authority"},
    "content": {"contentSource": "provider-feed", "contentTypes": "movie,series"},
    "template": {"themeRef": "basis-video"},
    "branding": {"brandName": "Новая", "legalName": "ООО Новая",
                 "primaryColor": "#1f4fd8"},
    "seo": {"canonicalHostForm": "non_www", "trailingSlash": "1"},
    "analytics": {"analyticsRef": "secret://analytics/novaya", "adsRef": ""},
    "legal": {"legalEntity": "ООО Новая", "contactEmail": "legal@novaya.test",
              "rightsConfirmed": "1"},
}


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setattr(PATHS, "root", tmp_path)
    профили = tmp_path / "config" / "site-profiles"
    профили.mkdir(parents=True)
    образец = json.loads(
        (REPO / "config" / "site-profiles" / "lords-01.json").read_text(encoding="utf-8")
    )
    образец.update({"site_id": SITE, "domains": ["taken.test"], "canonical_host": "taken.test"})
    (профили / f"{SITE}.json").write_text(json.dumps(образец, ensure_ascii=False), encoding="utf-8")
    for под in ("queue/inbox", "var/locks", "var/audit", "var/state", "sites"):
        (tmp_path / под).mkdir(parents=True, exist_ok=True)
    # Схемы нужны настоящие: проверка пакета читает их с диска, и подменённая
    # схема проверяла бы не то, что проверит конвейер.
    (tmp_path / "schemas").symlink_to(REPO / "schemas")
    (tmp_path / "knowledge").symlink_to(REPO / "knowledge")
    return tmp_path


@pytest.fixture
def api(sandbox):
    return ControlApi(root=sandbox, env=ENV)


@pytest.fixture
def app(sandbox):
    read = create_api(
        [SITE],
        root=sandbox,
        loader=lambda p: (InMemoryStore(p.site_id), "т"),
        env={"SITE_ENGINE_API_ENABLED": "1", "SITE_ENGINE_ENVIRONMENT": "test"},
    )
    return AdminApp(read, ControlApi(root=sandbox, env=ENV))


def создать(api) -> str:
    ответ = api.handle("POST", "/api/v1/site-requests", headers=H_W, body={"siteId": "novaya"})
    assert ответ.status == 201, ответ.body
    return ответ.body["requestId"]


def заполнить(api, rid: str, шаги=None) -> None:
    for шаг in шаги if шаги is not None else ОТВЕТЫ:
        ответ = api.handle(
            "PATCH",
            f"/api/v1/site-requests/{rid}",
            headers=H_W,
            body={"step": шаг, "answers": ОТВЕТЫ[шаг]},
        )
        assert ответ.status == 200, (шаг, ответ.body)


class TestЗаявка:
    def test_создаётся_и_знает_первый_шаг(self, api):
        rid = создать(api)
        тело = api.handle("GET", f"/api/v1/site-requests/{rid}", headers=H_W).body
        assert тело["state"] == "DRAFT"
        assert тело["nextStep"] == "domain"
        assert [ш["id"] for ш in тело["steps"]][:3] == ["domain", "profile", "content"]

    def test_шаги_идут_по_порядку(self, api):
        rid = создать(api)
        ответ = api.handle(
            "PATCH",
            f"/api/v1/site-requests/{rid}",
            headers=H_W,
            body={"step": "branding", "answers": ОТВЕТЫ["branding"]},
        )
        assert ответ.status == 409
        assert "domain" in json.dumps(ответ.body, ensure_ascii=False)

    def test_негодный_домен_отклонён_поимённо(self, api):
        rid = создать(api)
        ответ = api.handle(
            "PATCH",
            f"/api/v1/site-requests/{rid}",
            headers=H_W,
            body={"step": "domain", "answers": {"domain": "не домен вовсе"}},
        )
        assert ответ.status == 422
        assert "domain" in json.dumps(ответ.body, ensure_ascii=False)

    def test_занятый_домен_отклонён(self, api):
        rid = создать(api)
        ответ = api.handle(
            "PATCH",
            f"/api/v1/site-requests/{rid}",
            headers=H_W,
            body={"step": "domain", "answers": {"domain": "taken.test"}},
        )
        assert ответ.status == 409
        assert "taken.test" in json.dumps(ответ.body, ensure_ascii=False)

    def test_заполненная_заявка_доходит_до_конца(self, api):
        rid = создать(api)
        заполнить(api, rid)
        тело = api.handle("GET", f"/api/v1/site-requests/{rid}", headers=H_W).body
        assert тело["nextStep"] is None
        assert тело["complete"] is True

    def test_ссылка_на_аналитику_хранится_а_значение_нет(self, api, sandbox):
        rid = создать(api)
        заполнить(api, rid)
        файлы = list((sandbox / "var" / "state" / "site-requests").glob("*.json"))
        текст = "\n".join(f.read_text(encoding="utf-8") for f in файлы)
        assert "secret://analytics/novaya" in текст
        # Ключ аналитики в заявке не хранится ни при каких ответах: поле принимает
        # только ссылку. Значение, попавшее в заявку, разошлось бы по журналу,
        # по плану и по экрану сразу.
        ответ = api.handle(
            "PATCH",
            f"/api/v1/site-requests/{rid}",
            headers=H_W,
            body={"step": "analytics", "answers": {"analyticsRef": "G-СЕКРЕТНЫЙ-КЛЮЧ"}},
        )
        assert ответ.status == 422
        assert "ссылк" in json.dumps(ответ.body, ensure_ascii=False).lower()

    def test_чтение_без_права_не_создаёт(self, api):
        assert api.handle(
            "POST", "/api/v1/site-requests", headers=H_R, body={"siteId": "чужая"}
        ).status == 403


class TestСухойПрогон:
    def test_план_есть_и_не_меняет_ничего(self, api, sandbox):
        rid = создать(api)
        заполнить(api, rid)
        # След запроса — не мутация витрины: его пишет каждый запрос, включая
        # читающие, и он принадлежит службе, а не заявке. Всё остальное
        # проверяется строго: сухой прогон не создаёт ни профиля, ни пакета,
        # ни каталога выпусков.
        снимок = lambda: sorted(  # noqa: E731
            str(p)
            for p in sandbox.rglob("*")
            if "site-requests" not in str(p) and "var/state/trace" not in str(p)
        )
        до = снимок()
        план = api.handle("GET", f"/api/v1/site-requests/{rid}/plan", headers=H_W).body
        после = снимок()
        assert план["mutations"] == 0
        появилось = sorted(set(после) - set(до))
        исчезло = sorted(set(до) - set(после))
        assert not появилось and not исчезло, (
            f"сухой прогон не создаёт и не удаляет файлы; появилось {появилось}, "
            f"исчезло {исчезло}"
        )

    def test_план_детерминирован(self, api):
        rid = создать(api)
        заполнить(api, rid)
        первый = api.handle("GET", f"/api/v1/site-requests/{rid}/plan", headers=H_W).body
        второй = api.handle("GET", f"/api/v1/site-requests/{rid}/plan", headers=H_W).body
        assert первый["planHash"] == второй["planHash"]
        assert первый["steps"] == второй["steps"]

    def test_другой_ввод_даёт_другой_план(self, api):
        rid = создать(api)
        заполнить(api, rid)
        было = api.handle("GET", f"/api/v1/site-requests/{rid}/plan", headers=H_W).body["planHash"]
        api.handle(
            "PATCH",
            f"/api/v1/site-requests/{rid}",
            headers=H_W,
            body={"step": "branding", "answers": {**ОТВЕТЫ["branding"], "brandName": "Другая"}},
        )
        стало = api.handle("GET", f"/api/v1/site-requests/{rid}/plan", headers=H_W).body["planHash"]
        assert было != стало

    def test_план_называет_ресурсы_замки_и_контракты(self, api):
        rid = создать(api)
        заполнить(api, rid)
        план = api.handle("GET", f"/api/v1/site-requests/{rid}/plan", headers=H_W).body
        assert план["resources"], "план без списка ресурсов — обещание, а не план"
        assert any("novaya" in str(r) for r in план["resources"])
        assert план["locks"]
        assert план["contracts"]

    def test_план_несёт_откат(self, api):
        rid = создать(api)
        заполнить(api, rid)
        план = api.handle("GET", f"/api/v1/site-requests/{rid}/plan", headers=H_W).body
        assert план["rollback"]["steps"], "план отката строится вместе с планом действий"

    def test_незаполненная_заявка_даёт_требования_а_не_ошибку(self, api):
        rid = создать(api)
        заполнить(api, rid, ["domain"])
        ответ = api.handle("GET", f"/api/v1/site-requests/{rid}/plan", headers=H_W)
        assert ответ.status == 200
        assert ответ.body["ready"] is False
        не_хватает = json.dumps(ответ.body["requirements"], ensure_ascii=False)
        assert "profile" in не_хватает and "legal" in не_хватает

    def test_витрина_не_индексируется_до_публикации(self, api):
        rid = создать(api)
        заполнить(api, rid)
        план = api.handle("GET", f"/api/v1/site-requests/{rid}/plan", headers=H_W).body
        assert план["package"]["seo_indexing_enabled"] is False
        assert план["package"]["production_authorized"] is False

    def test_разрешение_на_production_не_выдаётся_из_мастера(self, api):
        rid = создать(api)
        заполнить(api, rid)
        ответ = api.handle(
            "PATCH",
            f"/api/v1/site-requests/{rid}",
            headers=H_W,
            body={"step": "profile", "answers": {**ОТВЕТЫ["profile"],
                                                 "environment": "production",
                                                 "productionAuthorized": "1"}},
        )
        тело = api.handle("GET", f"/api/v1/site-requests/{rid}/plan", headers=H_W).body
        assert тело["package"]["production_authorized"] is False, (
            "разрешение владельца не выдаётся полем формы"
        )
        assert ответ.status in (200, 409, 422)


class TestЭкран:
    def test_раздел_есть_и_ведёт_по_шагам(self, app):
        cookies = войти(app)
        html = app.handle("GET", "/admin/new-site", cookies=cookies).html
        assert "Домен" in html or "domain" in html
        assert "/admin/new-site" in html

    def test_путь_проходится_без_ssh_и_правки_файлов(self, app, sandbox):
        cookies = войти(app)
        r = app.handle(
            "POST",
            "/admin/new-site",
            form={CSRF_FIELD: csrf(app, cookies), "siteId": "novaya"},
            cookies=cookies,
        )
        assert r.status in (200, 302, 303)
        html = app.handle("GET", "/admin/new-site", cookies=cookies).html
        assert "novaya" in html

    def test_читатель_не_создаёт_заявку(self, app):
        cookies = войти(app, ЧИТАЮЩИЙ)
        html = app.handle("GET", "/admin/new-site", cookies=cookies).html
        assert 'method="post" action="/admin/new-site"' not in html


def войти(app, токен=ПИШУЩИЙ):
    r = app.handle("POST", "/admin/login", form={"token": токен})
    return {ADMIN_COOKIE: r.headers["Set-Cookie"].split(";")[0].split("=", 1)[1]}


def csrf(app, cookies) -> str:
    html = app.handle("GET", "/admin/new-site", cookies=cookies).html
    метка = f'name="{CSRF_FIELD}" value="'
    return html.split(метка, 1)[1].split('"', 1)[0]
