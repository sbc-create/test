"""REQ-ADMIN-OVERVIEW: сводка и каталог в редакционной админке.

Сводка обязана считаться по фактическим данным, а не показывать заглушки:
счётчик, который всегда показывает ноль или единицу, хуже отсутствия счётчика —
он выглядит как измерение и им не является.

Каталог обязан фильтровать на сервере. Фильтр, применённый в браузере поверх
первой страницы, отвечает на вопрос «что нашлось среди двадцати пяти», а
оператор задаёт вопрос «что есть во всём каталоге».
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

SITE = "ov-site"
ТОКЕН = "tok"
ENV_CONTROL = {
    "SITE_ENGINE_CONTROL_WRITES": "1",
    "SITE_ENGINE_CONTROL_TOKENS": f"{ТОКЕН}=read,review:write,audit:read,jobs:write",
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
    образец.update({"site_id": SITE, "domains": ["ov.test"], "canonical_host": "ov.test"})
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
    ):
        (tmp_path / под).mkdir(parents=True, exist_ok=True)
    # Небольшой, но настоящий каталог: сводка обязана считаться по нему.
    кэш = tmp_path / "var" / "lords" / "lords" / "catalog-cache"
    кэш.mkdir(parents=True)
    записи = []
    for n in range(40):
        записи.append(
            {
                "external_id": f"e{n:03d}",
                "name": f"Тайтл {n:03d}",
                "type": "movie" if n % 3 else "tv",
                "year": 2000 + (n % 26),
                "external_ids": ({"kinopoisk": str(n)} if n % 4 else {"imdb": str(n)}),
                "playback": ({"aggregator": "kp", "title_id": str(n)} if n % 4 else None),
                "kinopoisk_rating": 7.5 if n % 5 == 0 else None,
                "imdb_rating": None,
                "tags": ["ona"] if n % 7 == 0 else [],
                "poster_url": "p.jpg",
                "licensed": False,
                "created_at": "2026-08-01T00:00:00Z",
                "updated_at": "2026-08-01T00:00:00Z",
            }
        )
    (кэш / f"{SITE}.json").write_text(
        json.dumps({"fetched_at_ms": 0, "source": "test", "items": записи}, ensure_ascii=False),
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
    assert r.status == 303, r.status
    sid = r.headers["Set-Cookie"].split(";")[0].split("=", 1)[1]
    return {ADMIN_COOKIE: sid}


# --------------------------------------------------------------------------
# Сводка
# --------------------------------------------------------------------------
class TestСводка:
    def test_маршрут_существует(self, api):
        control, h = api
        assert control.handle("GET", "/api/v1/overview", headers=h).status == 200

    def test_считает_по_фактическому_каталогу(self, api):
        control, h = api
        тело = control.handle("GET", "/api/v1/overview", headers=h).body
        витрина = тело["sites"][0]
        assert витрина["titles"] == 40, "счётчик обязан считать, а не показывать заглушку"
        assert 0 < витрина["playbackCoverage"] < 1

    def test_называет_свежесть_и_её_возраст(self, api):
        control, h = api
        витрина = control.handle("GET", "/api/v1/overview", headers=h).body["sites"][0]
        assert "freshnessSeconds" in витрина and витрина["freshnessSeconds"] >= 0
        assert витрина["freshnessState"] in ("FRESH", "STALE", "UNKNOWN")

    def test_показывает_очередь_и_конфликты(self, api):
        control, h = api
        тело = control.handle("GET", "/api/v1/overview", headers=h).body
        assert "queue" in тело and "identityConflicts" in тело

    def test_тревоги_выводятся_из_порогов_а_не_вписаны(self, api):
        control, h = api
        тело = control.handle("GET", "/api/v1/overview", headers=h).body
        assert isinstance(тело["alerts"], list)
        for тревога in тело["alerts"]:
            assert {"code", "severity", "subject", "detail"} <= set(тревога)

    def test_пустой_каталог_это_тревога_а_не_ноль_процентов(self, sandbox, env_all):
        кэш = sandbox / "var/lords/lords/catalog-cache" / f"{SITE}.json"
        кэш.write_text(json.dumps({"items": []}), encoding="utf-8")
        control = ControlApi(root=sandbox, env=env_all)
        тело = control.handle(
            "GET", "/api/v1/overview", headers={"Authorization": f"Bearer {ТОКЕН}"}
        ).body
        коды = {t["code"] for t in тело["alerts"]}
        assert "EMPTY_CATALOG" in коды


# --------------------------------------------------------------------------
# Каталог
# --------------------------------------------------------------------------
class TestКаталог:
    def test_маршрут_существует(self, api):
        control, h = api
        assert (
            control.handle("GET", "/api/v1/content", body={"siteId": SITE}, headers=h).status == 200
        )

    def test_фильтр_меняет_результат_на_сервере(self, api):
        """Фильтр поверх первой страницы отвечает не на тот вопрос."""
        control, h = api
        всего = control.handle(
            "GET", "/api/v1/content", body={"siteId": SITE, "limit": 5}, headers=h
        ).body
        сериалы = control.handle(
            "GET", "/api/v1/content", body={"siteId": SITE, "kind": "SERIES", "limit": 5}, headers=h
        ).body
        assert всего["total"] > сериалы["total"] > 0
        assert all(i["contentKind"] == "SERIES" for i in сериалы["items"])

    def test_поиск_ищет_по_всему_каталогу(self, api):
        control, h = api
        найдено = control.handle(
            "GET", "/api/v1/content", body={"siteId": SITE, "q": "Тайтл 039", "limit": 5}, headers=h
        ).body
        assert найдено["total"] == 1 and найдено["items"][0]["title"] == "Тайтл 039"

    def test_страница_устойчива_к_повтору(self, api):
        control, h = api
        первая = control.handle(
            "GET", "/api/v1/content", body={"siteId": SITE, "limit": 5}, headers=h
        ).body
        снова = control.handle(
            "GET", "/api/v1/content", body={"siteId": SITE, "limit": 5}, headers=h
        ).body
        assert [i["externalId"] for i in первая["items"]] == [
            i["externalId"] for i in снова["items"]
        ]

    def test_карточка_несёт_provenance_и_причину(self, api):
        control, h = api
        первый = control.handle(
            "GET", "/api/v1/content", body={"siteId": SITE, "limit": 1}, headers=h
        ).body
        eid = первый["items"][0]["externalId"]
        карточка = control.handle("GET", f"/api/v1/content/{SITE}/{eid}", headers=h)
        assert карточка.status == 200
        for поле in (
            "contentKind",
            "externalIds",
            "sourceRefs",
            "playbackReason",
            "ratingState",
            "seoState",
            "timeline",
        ):
            assert поле in карточка.body, поле

    def test_предел_страницы_ограничен(self, api):
        control, h = api
        assert (
            control.handle(
                "GET", "/api/v1/content", body={"siteId": SITE, "limit": 100000}, headers=h
            ).status
            == 400
        )

    def test_чужая_витрина_не_отдаётся(self, api):
        control, h = api
        assert control.handle(
            "GET", "/api/v1/content", body={"siteId": "нет-такой"}, headers=h
        ).status in (400, 404)


# --------------------------------------------------------------------------
# Страницы админки
# --------------------------------------------------------------------------
class TestСтраницы:
    def test_сводка_открывается(self, app):
        r = app.handle("GET", "/admin/overview", cookies=войти(app))
        assert r.status == 200 and "Сводка" in r.html

    def test_каталог_открывается_и_фильтрует(self, app):
        куки = войти(app)
        обычный = app.handle("GET", "/admin/content", cookies=куки, form={"siteId": SITE})
        assert обычный.status == 200 and "Тайтл 000" in обычный.html
        сериалы = app.handle(
            "GET", "/admin/content", cookies=куки, form={"siteId": SITE, "kind": "SERIES"}
        )
        assert сериалы.status == 200
        assert обычный.html != сериалы.html, "фильтр обязан менять выдачу"

    def test_состояние_фильтра_видно_в_ссылках(self, app):
        """Иначе после обновления страницы оператор теряет свой отбор."""
        r = app.handle(
            "GET",
            "/admin/content",
            cookies=войти(app),
            form={"siteId": SITE, "kind": "SERIES", "offset": "0"},
        )
        assert "kind=SERIES" in r.html

    def test_карточка_тайтла_открывается(self, app):
        куки = войти(app)
        r = app.handle("GET", f"/admin/content/{SITE}/e000", cookies=куки)
        assert r.status == 200 and "Тайтл 000" in r.html

    def test_пустая_выдача_объясняет_себя(self, app):
        r = app.handle(
            "GET",
            "/admin/content",
            cookies=войти(app),
            form={"siteId": SITE, "q": "такого-нет-совсем"},
        )
        assert r.status == 200 and "не найдено" in r.html.lower()
