"""REQ-RELEASE-CANDIDATE: наблюдаемость, безопасность и готовность к выпуску.

Четыре свойства, каждое из которых обычно объявляют, а не проверяют.

**След одного действия виден целиком.** Оператор нажал кнопку — и должен по
одному идентификатору найти запись в журнале, задание и ответ службы. Пока
идентификатор теряется на границе слоёв, «сквозная трассировка» существует
только в описании.

**Оценка считается по измерению, а не по памяти.** Табель, который ведут руками,
показывает то, что о системе думали в момент последней правки. Здесь каждая
оценка либо посчитана, либо честно помечена как неизмеренная.

**У каждой тревоги есть инструкция.** Код тревоги без runbook сообщает
дежурному, что что-то не так, и ничего не говорит о том, что делать.

**Отказ проверяется по матрице, а не по одному примеру.** Права проверяются на
всех сочетаниях «маршрут × область», а не на том, которое вспомнили.

И одно свойство, без которого выпуск не выпуск: **состояние восстановимо**.
Личности операторов, учётные записи, очередь разбора, решения редакторов и
заявки на витрины обязаны переживать восстановление из копии.
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
ТОКЕН = "tok-all"
ЧИТАТЕЛЬ = "tok-ro"
ENV = {
    "SITE_ENGINE_CONTROL_WRITES": "1",
    "SITE_ENGINE_CONTROL_TOKENS": (
        f"{ТОКЕН}=read,jobs:write,audit:read,config:write,cache:write,review:write,"
        f"operators:write,sites:create|{ЧИТАТЕЛЬ}=read"
    ),
}
H = {"Authorization": f"Bearer {ТОКЕН}"}
H_RO = {"Authorization": f"Bearer {ЧИТАТЕЛЬ}"}
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
        "queue/done",
        "var/locks",
        "var/audit",
        "var/state",
        "var/backups",
        "artifacts/jobs",
        "sites",
    ):
        (tmp_path / под).mkdir(parents=True, exist_ok=True)
    for имя in ("schemas", "knowledge", "inventory", "docs"):
        (tmp_path / имя).symlink_to(REPO / имя)
    (tmp_path / "config" / "site-request-presets").symlink_to(
        REPO / "config" / "site-request-presets"
    )
    # Реестр источников оценок — часть поставки: без него экран готовности не
    # сможет назвать причину, по которой оценок нет.
    (tmp_path / "config" / "rating-sources.yaml").symlink_to(
        REPO / "config" / "rating-sources.yaml"
    )
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
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture
def api(sandbox):
    return ControlApi(root=sandbox, env={**ENV, "SITE_ENGINE_CATALOG_DIR": "var/lords/lords/catalog-cache"})


@pytest.fixture
def app(sandbox):
    read = create_api(
        [SITE],
        root=sandbox,
        loader=lambda p: (InMemoryStore(p.site_id), "т"),
        env={"SITE_ENGINE_API_ENABLED": "1", "SITE_ENGINE_ENVIRONMENT": "test"},
    )
    return AdminApp(
        read,
        ControlApi(
            root=sandbox,
            env={**ENV, "SITE_ENGINE_CATALOG_DIR": "var/lords/lords/catalog-cache"},
        ),
    )


def войти(app, токен=ТОКЕН):
    r = app.handle("POST", "/admin/login", form={"token": токен})
    return {ADMIN_COOKIE: r.headers["Set-Cookie"].split(";")[0].split("=", 1)[1]}


class TestСквознойСлед:
    def test_действие_панели_видно_в_журнале_по_одному_идентификатору(self, app, sandbox):
        cookies = войти(app)
        html = app.handle("GET", "/admin/settings", cookies=cookies).html
        csrf = html.split(f'name="{CSRF_FIELD}" value="', 1)[1].split('"', 1)[0]
        версия = html.split('name="expectedVersion" value="', 1)[1].split('"', 1)[0]
        ответ = app.handle(
            "POST",
            "/admin/settings",
            form={
                CSRF_FIELD: csrf,
                "site": SITE,
                "key": "keep_releases",
                "value": "9",
                "expectedVersion": версия,
                "dryRun": "",
            },
            cookies=cookies,
        )
        # Идентификатор связи обязан вернуться вызывающему: без него оператор
        # не может ничего найти, даже когда всё записано.
        связь = ответ.headers.get("X-Correlation-Id") or ""
        assert связь, "ответ панели обязан нести идентификатор связи"
        журнал = app.handle(
            "GET", "/admin/audit", form={"correlationId": связь}, cookies=cookies
        ).html
        assert связь in журнал
        assert "settings" in журнал

    def test_идентификатор_виден_на_экране_журнала(self, app):
        cookies = войти(app)
        assert "Идентификатор связи" in app.handle("GET", "/admin/audit", cookies=cookies).html


class TestТабель:
    def test_маршрут_существует(self, api):
        assert api.handle("GET", "/api/v1/scorecard", headers=H).status == 200

    def test_каждая_оценка_названа_и_обоснована(self, api):
        тело = api.handle("GET", "/api/v1/scorecard", headers=H).body
        assert тело["gates"], "табель без ворот — не табель"
        for ворота in тело["gates"]:
            assert ворота["id"]
            assert "score" in ворота
            assert ворота["basis"], f"{ворота['id']}: оценка без основания"

    def test_неизмеренное_названо_неизмеренным(self, api):
        тело = api.handle("GET", "/api/v1/scorecard", headers=H).body
        неизмеренные = [в for в in тело["gates"] if в.get("measured") is False]
        for в in неизмеренные:
            assert в["score"] is None, "неизмеренная оценка не может иметь число"
            assert в["basis"], "неизмеренное обязано объяснить, чего не хватает"

    def test_итог_не_выдумывается_из_неизмеренного(self, api):
        тело = api.handle("GET", "/api/v1/scorecard", headers=H).body
        измеренные = [в for в in тело["gates"] if в.get("measured")]
        assert тело["measuredCount"] == len(измеренные)
        assert тело["total"] == len(тело["gates"])


class TestТревоги:
    def test_у_каждой_тревоги_есть_инструкция(self, api):
        тело = api.handle("GET", "/api/v1/alerts", headers=H).body
        assert тело["items"], "перечень тревог не может быть пустым"
        без_инструкции = [т["code"] for т in тело["items"] if not т.get("runbook")]
        assert not без_инструкции, f"тревоги без инструкции: {без_инструкции}"

    def test_инструкции_существуют_на_диске(self, api, sandbox):
        тело = api.handle("GET", "/api/v1/alerts", headers=H).body
        пропали = [
            т["code"]
            for т in тело["items"]
            if not (sandbox / т["runbook"].split("#", 1)[0]).exists()
        ]
        assert not пропали, f"инструкция объявлена, но не найдена: {пропали}"

    def test_коды_тревог_сводки_объявлены(self, api):
        from factory.site_engine.api import overview

        объявлены = {т["code"] for т in api.handle("GET", "/api/v1/alerts", headers=H).body["items"]}
        assert set(overview.КОДЫ_ТРЕВОГ) <= объявлены, "сводка умеет коды, которых нет в перечне"


class TestМатрицаОтказов:
    #: Маршрут, метод, тело — и что обязан получить читатель без прав записи.
    МАТРИЦА = [
        ("POST", f"/api/v1/sites/{SITE}/jobs", {"action": "reindex"}, 403),
        ("PATCH", f"/api/v1/sites/{SITE}/settings", {"changes": {"keep_releases": 5}}, 403),
        ("POST", f"/api/v1/sites/{SITE}/cache/invalidate", {"scope": "catalog"}, 403),
        ("POST", "/api/v1/site-requests", {"siteId": "x"}, 403),
        ("GET", "/api/v1/audit", {}, 403),
        # Список людей читается любым вошедшим намеренно: команда должна
        # видеть, у кого есть доступ. Приглашения и сессии — нет: по ним
        # захватывают учётные записи.
        ("GET", "/api/v1/operators/invites", {}, 403),
        ("GET", "/api/v1/operators/sessions", {}, 403),
    ]

    @pytest.mark.parametrize("метод,путь,тело,ожидание", МАТРИЦА)
    def test_читателю_отказано(self, api, метод, путь, тело, ожидание):
        ответ = api.handle(метод, путь, headers=H_RO, body=тело)
        assert ответ.status == ожидание, f"{метод} {путь}: {ответ.status}"

    def test_без_токена_отказ_везде(self, api):
        for метод, путь, тело, _ in self.МАТРИЦА:
            assert api.handle(метод, путь, headers={}, body=тело).status == 401

    def test_список_людей_читается_но_без_секретов(self, api):
        """Роль и состояние — да; всё, чем можно войти, — нет."""
        ответ = api.handle("GET", "/api/v1/operators", headers=H_RO, body={})
        assert ответ.status == 200
        текст = json.dumps(ответ.body, ensure_ascii=False)
        for запретное in ("password", "hash", "secret", "salt", "sid"):
            assert запретное not in текст.lower(), f"в списке людей нашлось «{запретное}»"

    def test_чужой_токен_не_подходит(self, api):
        ответ = api.handle("GET", "/api/v1/audit", headers={"Authorization": "Bearer нет"}, body={})
        assert ответ.status == 401


class TestВосстановление:
    """Состояние службы обязано переживать восстановление из копии."""

    ХРАНИЛИЩА = (
        "operators",
        "accounts",
        "review-queue",
        "kind-overlay",
        "site-requests",
        "canary-profiles",
    )

    def test_перечень_хранилищ_объявлен(self, api):
        тело = api.handle("GET", "/api/v1/state-inventory", headers=H).body
        объявлены = {х["id"] for х in тело["items"]}
        пропали = set(self.ХРАНИЛИЩА) - объявлены
        assert not пропали, f"состояние не объявлено в описи: {sorted(пропали)}"
        for х in тело["items"]:
            assert х["path"], "хранилище без пути невозможно ни скопировать, ни восстановить"
            assert "restorable" in х

    def test_опись_показывает_фактическое_наличие(self, api, sandbox):
        (sandbox / "var" / "state" / "operators").mkdir(parents=True, exist_ok=True)
        (sandbox / "var" / "state" / "operators" / "a.json").write_text("{}", encoding="utf-8")
        тело = api.handle("GET", "/api/v1/state-inventory", headers=H).body
        операторы = next(х for х in тело["items"] if х["id"] == "operators")
        assert операторы["present"] is True
        assert операторы["files"] >= 1

    def test_восстановление_проверяется_кругом(self, api, sandbox):
        """Копия снимается и разворачивается в отдельный каталог, а не поверх."""
        (sandbox / "var" / "state" / "operators").mkdir(parents=True, exist_ok=True)
        (sandbox / "var" / "state" / "operators" / "a.json").write_text(
            '{"email": "a@test"}', encoding="utf-8"
        )
        ответ = api.handle("POST", "/api/v1/state-backup", headers=H, body={"verify": True})
        assert ответ.status == 200, ответ.body
        тело = ответ.body
        assert тело["verified"] is True, "копия без проверки восстановления — обещание"
        assert тело["stores"], "в копии должно быть перечислено, что именно скопировано"
        # Живое состояние не тронуто: проверка восстановления идёт в стороне.
        assert (sandbox / "var" / "state" / "operators" / "a.json").exists()


class TestЭкранГотовности:
    """Табель, тревоги и опись обязаны быть доступны оператору, а не только API.

    Оценка, которую видно только в ответе службы, не помогает тому, кто решает,
    выпускать или нет.
    """

    def test_раздел_есть_в_меню_и_открывается(self, app):
        cookies = войти(app)
        assert "/admin/readiness" in app.handle("GET", "/admin", cookies=cookies).html
        ответ = app.handle("GET", "/admin/readiness", cookies=cookies)
        assert ответ.status == 200
        assert "Табель" in ответ.html

    def test_неизмеренное_названо_словами(self, app):
        html = app.handle("GET", "/admin/readiness", cookies=войти(app)).html
        assert "не измерено" in html
        assert "ratingsProvenance" in html

    def test_тревоги_показаны_с_инструкцией(self, app):
        html = app.handle("GET", "/admin/readiness", cookies=войти(app)).html
        assert "docs/runbooks/alerts.md" in html
        assert "CANARY_INDEXABLE" in html

    def test_опись_состояния_показана(self, app):
        html = app.handle("GET", "/admin/readiness", cookies=войти(app)).html
        for хранилище in ("operators", "accounts", "site-requests"):
            assert хранилище in html

    def test_причина_отсутствия_оценок_названа(self, app):
        """Пустой раздел читался бы как «оценки просто не сделали»."""
        html = app.handle("GET", "/admin/readiness", cookies=войти(app)).html
        assert "Источники оценок" in html
        assert "ни один источник оценок не разрешён" in html
        assert "kinopoisk" in html and "imdb" in html

