"""REQ-ADMIN-SETTINGS: отдельный экран настроек витрины.

Настройки уже можно было менять — но только с сайта витрины, вслепую и без
ответа на три вопроса, которые оператор задаёт до, а не после изменения.

**Что вообще можно менять.** Список разрешённого жил в коде проверки. Оператор
узнавал границы, наткнувшись на отказ: ввёл значение, получил «не входит в
список». Экран обязан показывать схему до ввода, вместе с причинами отказа для
неизменяемых полей.

**Что станет другим.** Сухой прогон возвращал разницу, но панель показывала её
как текст ответа. Разница «было/стало» — часть экрана, а не сообщение.

**Как вернуть назад.** Отката не было вовсе: прежнее значение оставалось только
в журнале, и возвращать его приходилось руками. Откат — действие на экране,
опирающееся на записанное прежнее значение.

И одно правило, которое дороже трёх: **значение секрета панель не показывает
никогда**. Ссылка на хранилище — да, значение — нет, ни в API, ни в HTML.
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
СЕКРЕТ = "НАСТОЯЩЕЕ-ЗНАЧЕНИЕ-СЕКРЕТА-8f3a"
ПИШУЩИЙ = "tok-w"
ЧИТАЮЩИЙ = "tok-r"
ENV_CONTROL = {
    "SITE_ENGINE_CONTROL_WRITES": "1",
    "SITE_ENGINE_CONTROL_TOKENS": (
        f"{ПИШУЩИЙ}=read,jobs:write,audit:read,config:write|{ЧИТАЮЩИЙ}=read,audit:read"
    ),
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
    образец.update(
        {
            "site_id": SITE,
            "domains": ["js.test"],
            "canonical_host": "js.test",
            "keep_releases": 8,
            "cache_policy": {"homepage_ttl": 60},
            "feature_flags": {"shelves": True},
            # Секрет лежит в профиле так же, как в боевом: ссылкой и значением.
            # Панель обязана показать ссылку и не показать значение.
            "secrets": {
                "analytics_token": {
                    "store": "vault",
                    "ref": "vault://site-factory/js-site/analytics",
                    "value": СЕКРЕТ,
                }
            },
        }
    )
    (профили / f"{SITE}.json").write_text(
        json.dumps(образец, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    for под in ("queue/inbox", "var/locks", "var/audit", "var/state", "artifacts/jobs"):
        (tmp_path / под).mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture
def api(sandbox):
    return ControlApi(root=sandbox, env=ENV_CONTROL)


@pytest.fixture
def app(sandbox):
    read = create_api(
        [SITE], root=sandbox, loader=lambda p: (InMemoryStore(p.site_id), "т"), env=ENV_READ
    )
    return AdminApp(read, ControlApi(root=sandbox, env=ENV_CONTROL))


def войти(app, токен=ПИШУЩИЙ):
    r = app.handle("POST", "/admin/login", form={"token": токен})
    sid = r.headers["Set-Cookie"].split(";")[0].split("=", 1)[1]
    return {ADMIN_COOKIE: sid}


def csrf(app, cookies):
    страница = app.handle("GET", "/admin/settings", cookies=cookies).html
    метка = 'name="_csrf" value="'
    return страница.split(метка, 1)[1].split('"', 1)[0]


H_W = {"Authorization": f"Bearer {ПИШУЩИЙ}"}
H_R = {"Authorization": f"Bearer {ЧИТАЮЩИЙ}"}


class TestЧтениеНастроек:
    def test_маршрут_существует(self, api):
        assert api.handle("GET", f"/api/v1/settings/{SITE}", headers=H_W).status == 200

    def test_схема_разрешённых_полей_приходит_до_ввода(self, api):
        тело = api.handle("GET", f"/api/v1/settings/{SITE}", headers=H_W).body
        поля = {f["key"]: f for f in тело["fields"]}
        assert set(поля) == {"keep_releases", "cache_policy", "feature_flags"}
        assert поля["keep_releases"]["min"] == 2 and поля["keep_releases"]["max"] == 20
        assert поля["keep_releases"]["value"] == 8

    def test_отклонённые_поля_названы_с_причиной(self, api):
        тело = api.handle("GET", f"/api/v1/settings/{SITE}", headers=H_W).body
        отказы = {r["key"]: r["reason"] for r in тело["refused"]}
        assert "domains" in отказы and отказы["domains"]
        assert "indexing_enabled" in отказы

    def test_версия_отдаётся_вместе_со_значениями(self, api):
        тело = api.handle("GET", f"/api/v1/settings/{SITE}", headers=H_W).body
        assert тело["version"].startswith("sha256:")

    def test_ссылка_на_секрет_есть_а_значения_нет(self, api):
        ответ = api.handle("GET", f"/api/v1/settings/{SITE}", headers=H_W)
        ссылки = {s["key"]: s for s in ответ.body["secretRefs"]}
        assert ссылки["analytics_token"]["store"] == "vault"
        assert ссылки["analytics_token"]["ref"].startswith("vault://")
        assert СЕКРЕТ not in json.dumps(ответ.body, ensure_ascii=False)

    def test_контракт_канарейки_и_отката_объявлен(self, api):
        тело = api.handle("GET", f"/api/v1/settings/{SITE}", headers=H_W).body
        поля = {f["key"]: f for f in тело["fields"]}
        assert поля["feature_flags"]["rollout"] == "canary"
        assert поля["keep_releases"]["rollout"] == "immediate"
        assert тело["rollback"]["available"] is False

    def test_неизвестная_витрина_даёт_404(self, api):
        assert api.handle("GET", "/api/v1/settings/нет-такой", headers=H_W).status in (400, 404)


class TestЭкран:
    def test_раздел_есть_в_меню_и_открывается(self, app):
        cookies = войти(app)
        ответ = app.handle("GET", "/admin/settings", cookies=cookies)
        assert ответ.status == 200
        assert "/admin/settings" in app.handle("GET", "/admin", cookies=cookies).html

    def test_показаны_поля_границы_и_причины_отказа(self, app):
        html = app.handle("GET", "/admin/settings", cookies=войти(app)).html
        assert "keep_releases" in html and "cache_policy" in html
        assert "от 2 до 20" in html
        assert "domains" in html and "сертификат" in html

    def test_значение_секрета_не_попадает_в_html(self, app):
        html = app.handle("GET", "/admin/settings", cookies=войти(app)).html
        assert "vault://site-factory/js-site/analytics" in html
        assert СЕКРЕТ not in html

    def test_сухой_прогон_показывает_до_и_после_и_ничего_не_пишет(self, app, sandbox):
        cookies = войти(app)
        путь = sandbox / "config" / "site-profiles" / f"{SITE}.json"
        было = путь.read_bytes()
        ответ = app.handle(
            "POST",
            "/admin/settings",
            form={
                "_csrf": csrf(app, cookies),
                "site": SITE,
                "key": "keep_releases",
                "value": "12",
                "dryRun": "1",
            },
            cookies=cookies,
        )
        html = ответ.html if ответ.status == 200 else app.handle(
            "GET", "/admin/settings", cookies=cookies
        ).html
        assert "было" in html and "станет" in html
        assert "8" in html and "12" in html
        assert путь.read_bytes() == было

    def test_применение_меняет_значение_и_даёт_откат(self, app, sandbox):
        cookies = войти(app)
        app.handle(
            "POST",
            "/admin/settings",
            form={
                "_csrf": csrf(app, cookies),
                "site": SITE,
                "key": "keep_releases",
                "value": "12",
                "dryRun": "",
            },
            cookies=cookies,
        )
        профиль = json.loads(
            (sandbox / "config" / "site-profiles" / f"{SITE}.json").read_text(encoding="utf-8")
        )
        assert профиль["keep_releases"] == 12
        html = app.handle("GET", "/admin/settings", cookies=cookies).html
        assert "Откатить" in html

    def test_откат_возвращает_прежнее_значение(self, app, sandbox):
        cookies = войти(app)
        app.handle(
            "POST",
            "/admin/settings",
            form={
                "_csrf": csrf(app, cookies),
                "site": SITE,
                "key": "keep_releases",
                "value": "12",
                "dryRun": "",
            },
            cookies=cookies,
        )
        app.handle(
            "POST",
            "/admin/settings/rollback",
            form={"_csrf": csrf(app, cookies), "site": SITE},
            cookies=cookies,
        )
        профиль = json.loads(
            (sandbox / "config" / "site-profiles" / f"{SITE}.json").read_text(encoding="utf-8")
        )
        assert профиль["keep_releases"] == 8

    def test_негодное_значение_отклонено_с_границами(self, app, sandbox):
        cookies = войти(app)
        app.handle(
            "POST",
            "/admin/settings",
            form={
                "_csrf": csrf(app, cookies),
                "site": SITE,
                "key": "keep_releases",
                "value": "1",
                "dryRun": "",
            },
            cookies=cookies,
        )
        профиль = json.loads(
            (sandbox / "config" / "site-profiles" / f"{SITE}.json").read_text(encoding="utf-8")
        )
        assert профиль["keep_releases"] == 8
        assert "от 2 до 20" in app.handle("GET", "/admin/settings", cookies=cookies).html

    def test_чужая_версия_отклоняется_и_не_перезаписывает(self, app, sandbox):
        cookies = войти(app)
        токен_csrf = csrf(app, cookies)
        путь = sandbox / "config" / "site-profiles" / f"{SITE}.json"
        профиль = json.loads(путь.read_text(encoding="utf-8"))
        профиль["keep_releases"] = 15
        путь.write_text(json.dumps(профиль, ensure_ascii=False, indent=2), encoding="utf-8")
        app.handle(
            "POST",
            "/admin/settings",
            form={
                "_csrf": токен_csrf,
                "site": SITE,
                "key": "keep_releases",
                "value": "12",
                "dryRun": "",
                "expectedVersion": "sha256:устарело",
            },
            cookies=cookies,
        )
        assert json.loads(путь.read_text(encoding="utf-8"))["keep_releases"] == 15

    def test_читатель_видит_значения_но_не_формы(self, app):
        html = app.handle("GET", "/admin/settings", cookies=войти(app, ЧИТАЮЩИЙ)).html
        assert "keep_releases" in html
        assert 'method="post" action="/admin/settings"' not in html
        assert "только для чтения" in html.lower() or "нет права" in html.lower()

    def test_читатель_получает_отказ_на_запись(self, app, sandbox):
        cookies = войти(app, ЧИТАЮЩИЙ)
        страница = app.handle("GET", "/admin/settings", cookies=cookies).html
        метка = 'name="_csrf" value="'
        токен_csrf = страница.split(метка, 1)[1].split('"', 1)[0] if метка in страница else ""
        ответ = app.handle(
            "POST",
            "/admin/settings",
            form={
                "_csrf": токен_csrf,
                "site": SITE,
                "key": "keep_releases",
                "value": "12",
                "dryRun": "",
            },
            cookies=cookies,
        )
        assert ответ.status in (302, 303, 403)
        профиль = json.loads(
            (sandbox / "config" / "site-profiles" / f"{SITE}.json").read_text(encoding="utf-8")
        )
        assert профиль["keep_releases"] == 8

    def test_отклонённое_поле_нельзя_отправить_через_форму(self, app, sandbox):
        cookies = войти(app)
        app.handle(
            "POST",
            "/admin/settings",
            form={
                "_csrf": csrf(app, cookies),
                "site": SITE,
                "key": "domains",
                "value": '["зло.test"]',
                "dryRun": "",
            },
            cookies=cookies,
        )
        профиль = json.loads(
            (sandbox / "config" / "site-profiles" / f"{SITE}.json").read_text(encoding="utf-8")
        )
        assert профиль["domains"] == ["js.test"]

    def test_изменение_попадает_в_журнал_с_разницей(self, app, sandbox):
        cookies = войти(app)
        app.handle(
            "POST",
            "/admin/settings",
            form={
                "_csrf": csrf(app, cookies),
                "site": SITE,
                "key": "keep_releases",
                "value": "12",
                "dryRun": "",
            },
            cookies=cookies,
        )
        журнал = app.handle("GET", "/admin/audit", cookies=cookies).html
        assert "settings" in журнал


class TestОткатДобавленной:
    """Настройка, которой раньше не было, тоже обязана откатываться.

    Раньше такой случай объявлялся неоткатываемым: путь записи умел только
    присваивать. Оператор, добавивший поле, не мог убрать его из панели вообще —
    и это выглядело как «откат недоступен», а не как пробел.
    """

    def test_добавленная_настройка_убирается_откатом(self, app, sandbox):
        путь = sandbox / "config" / "site-profiles" / f"{SITE}.json"
        профиль = json.loads(путь.read_text(encoding="utf-8"))
        del профиль["cache_policy"]
        путь.write_text(json.dumps(профиль, ensure_ascii=False, indent=2), encoding="utf-8")

        cookies = войти(app)
        app.handle(
            "POST",
            "/admin/settings",
            form={
                "_csrf": csrf(app, cookies),
                "site": SITE,
                "key": "cache_policy",
                "value": '{"homepage_ttl": 30}',
                "dryRun": "",
            },
            cookies=cookies,
        )
        assert "cache_policy" in json.loads(путь.read_text(encoding="utf-8"))

        app.handle(
            "POST",
            "/admin/settings/rollback",
            form={"_csrf": csrf(app, cookies), "site": SITE},
            cookies=cookies,
        )
        assert "cache_policy" not in json.loads(путь.read_text(encoding="utf-8"))

    def test_удалить_можно_только_разрешённое(self, api):
        ответ = api.handle(
            "PATCH",
            f"/api/v1/sites/{SITE}/settings",
            headers=H_W,
            body={"changes": {}, "remove": ["domains"]},
        )
        assert ответ.status == 422
        assert "domains" in json.dumps(ответ.body, ensure_ascii=False)

