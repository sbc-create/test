"""REQ-REVIEW: очередь разбора спорных записей.

Проверяется путь редактора целиком, а не наличие маршрутов: найти запись,
увидеть оба утверждения, принять решение, убедиться, что оно записано, и
отменить его. Отдельно — что читатель без права ничего не изменит и что отказ
попадёт в журнал.

Групповое действие проверяется полным путём: сухой прогон, сверка отпечатка
набора, применение, сверка результата, откат партии. Каждое звено здесь
существует из-за конкретной ошибки, которую оно предотвращает, и тесты названы
по этим ошибкам, а не по функциям.
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
from factory.site_engine.review_queue import (
    CONTRACT_VERSION,
    Claim,
    ReviewError,
    ReviewItem,
    ReviewQueue,
    ReviewState,
    item_id_for,
)
from factory.site_engine.store import InMemoryStore

SITE = "review-site"
РЕДАКТОР = "editor-token"
ЧИТАТЕЛЬ = "ro-token"
ENV_CONTROL = {
    "SITE_ENGINE_CONTROL_WRITES": "1",
    "SITE_ENGINE_CONTROL_TOKENS": (f"{РЕДАКТОР}=read,review:write,audit:read|{ЧИТАТЕЛЬ}=read"),
}
ENV_READ = {"SITE_ENGINE_API_ENABLED": "1", "SITE_ENGINE_ENVIRONMENT": "test"}
REPO = Path(__file__).resolve().parents[2]


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setattr(PATHS, "root", tmp_path)
    profiles = tmp_path / "config" / "site-profiles"
    profiles.mkdir(parents=True)
    образец = json.loads(
        (REPO / "config" / "site-profiles" / "lords-01.json").read_text(encoding="utf-8")
    )
    образец.update({"site_id": SITE, "domains": ["review.test"], "canonical_host": "review.test"})
    (profiles / f"{SITE}.json").write_text(
        json.dumps(образец, ensure_ascii=False), encoding="utf-8"
    )
    for sub in (
        "queue/inbox",
        "queue/processing",
        "queue/done",
        "queue/failed",
        "queue/quarantine",
        "var/locks",
        "var/audit",
        "var/state",
    ):
        (tmp_path / sub).mkdir(parents=True, exist_ok=True)
    return tmp_path


def наполнить(root: Path, сколько: int = 4) -> ReviewQueue:
    q = ReviewQueue(root)
    for n in range(сколько):
        eid = f"{SITE}:e{n}"
        q.upsert(
            ReviewItem(
                item_id=item_id_for(eid, "contentKind"),
                internal_entity_id=eid,
                site_id=SITE,
                conflict_code="PROVIDER_TYPE_VS_KIND_TAG",
                field="contentKind",
                claims=(
                    Claim("MOVIE", "поле type поставщика", "type='movie'", 0.5),
                    Claim("OVA", "тег вида у поставщика", "tags=['ova']", 0.5),
                ),
                title=f"Спорный тайтл {n}",
                year=2020 + n,
                external_ids={"myanimelist": str(1000 + n)},
                recommendation="",
                recommendation_reason="оснований для выбора нет",
            )
        )
    return q


@pytest.fixture
def app(sandbox):
    наполнить(sandbox)
    read = create_api(
        [SITE], root=sandbox, loader=lambda p: (InMemoryStore(p.site_id), "тестовый"), env=ENV_READ
    )
    return AdminApp(read, ControlApi(root=sandbox, env=ENV_CONTROL))


def войти(app, token=РЕДАКТОР):
    r = app.handle("POST", "/admin/login", form={"token": token})
    assert r.status == 303, r.status
    sid = r.headers["Set-Cookie"].split(";")[0].split("=", 1)[1]
    return {ADMIN_COOKIE: sid}, app.sessions.csrf_token(sid)


# --------------------------------------------------------------------------
# Хранилище
# --------------------------------------------------------------------------
class TestХранилище:
    def test_идентификатор_устойчив_к_пересчёту(self):
        """Иначе решение редактора потеряется при следующем прогоне каталога."""
        assert item_id_for("s:a", "contentKind") == item_id_for("s:a", "contentKind")
        assert item_id_for("s:a", "contentKind") != item_id_for("s:b", "contentKind")

    def test_пересчёт_не_стирает_решение(self, sandbox):
        q = наполнить(sandbox, 1)
        (iid,) = (i["itemId"] for i in q.list()["items"])
        q.decide(iid, value="OVA", actor="editor", expected_version=1)
        наполнить(sandbox, 1)  # повторный пересчёт
        assert q.get(iid).state is ReviewState.RESOLVED
        assert q.get(iid).decided_value == "OVA"

    def test_третье_значение_не_принимается(self, sandbox):
        """Очередь разрешает выбрать между источниками, а не придумать своё."""
        q = наполнить(sandbox, 1)
        (iid,) = (i["itemId"] for i in q.list()["items"])
        with pytest.raises(ReviewError, match="не входит в утверждения"):
            q.decide(iid, value="PODCAST", actor="e", expected_version=1)

    def test_устаревшая_версия_отклоняется(self, sandbox):
        """Двое редакторов не должны перезаписывать решение друг друга."""
        q = наполнить(sandbox, 1)
        (iid,) = (i["itemId"] for i in q.list()["items"])
        q.decide(iid, value="OVA", actor="first", expected_version=1)
        with pytest.raises(ReviewError, match="изменилась"):
            q.decide(iid, value="MOVIE", actor="second", expected_version=1)

    def test_отмена_возвращает_исходное_состояние(self, sandbox):
        q = наполнить(sandbox, 1)
        (iid,) = (i["itemId"] for i in q.list()["items"])
        q.decide(iid, value="OVA", actor="e", expected_version=1)
        после = q.revert(iid, actor="e", note="ошибся")
        assert после.state is ReviewState.OPEN
        assert после.decided_value == "" and после.decided_by == ""
        assert [h["action"] for h in после.history] == ["decide", "revert"]

    def test_отменять_нерешённое_нельзя(self, sandbox):
        q = наполнить(sandbox, 1)
        (iid,) = (i["itemId"] for i in q.list()["items"])
        with pytest.raises(ReviewError, match="отменять нечего"):
            q.revert(iid, actor="e")

    def test_испорченный_файл_не_прячет_очередь(self, sandbox):
        """Одна битая запись не должна делать невидимыми остальные."""
        q = наполнить(sandbox, 3)
        (q.dir / "битая.json").write_text("{не json", encoding="utf-8")
        assert q.list()["totalAll"] == 3

    def test_сортировка_устойчива(self, sandbox):
        """Иначе страница меняется под руками при фоновом пересчёте."""
        q = наполнить(sandbox, 5)
        первый = [i["itemId"] for i in q.list()["items"]]
        наполнить(sandbox, 5)
        assert [i["itemId"] for i in q.list()["items"]] == первый

    def test_состояние_считается_по_всей_очереди_а_не_по_странице(self, sandbox):
        q = наполнить(sandbox, 5)
        стр = q.list(limit=2)
        assert len(стр["items"]) == 2
        assert sum(стр["byState"].values()) == 5


# --------------------------------------------------------------------------
# Групповое действие
# --------------------------------------------------------------------------
class TestГрупповое:
    def test_сухой_прогон_ничего_не_меняет(self, sandbox):
        q = наполнить(sandbox, 4)
        q.batch_preview(
            conflict_code="PROVIDER_TYPE_VS_KIND_TAG", from_value="MOVIE", to_value="OVA"
        )
        assert q.list()["byState"] == {"OPEN": 4}

    def test_сухой_прогон_показывает_число_разницу_и_выборку(self, sandbox):
        q = наполнить(sandbox, 4)
        p = q.batch_preview(
            conflict_code="PROVIDER_TYPE_VS_KIND_TAG", from_value="MOVIE", to_value="OVA", sample=2
        )
        assert p["dryRun"] and p["affected"] == 4
        assert p["diff"]["from"] == "MOVIE" and p["diff"]["to"] == "OVA"
        assert len(p["sample"]) == 2 and p["sample"][0]["title"]

    def test_применение_без_отпечатка_отклонено(self, sandbox):
        q = наполнить(sandbox, 4)
        with pytest.raises(ReviewError, match="набор изменился"):
            q.batch_apply(
                conflict_code="PROVIDER_TYPE_VS_KIND_TAG",
                from_value="MOVIE",
                to_value="OVA",
                actor="e",
                expected_fingerprint="",
            )

    def test_изменение_набора_между_прогоном_и_применением_ловится(self, sandbox):
        """Поштучная сверка версий не заметила бы изменения СОСТАВА."""
        q = наполнить(sandbox, 4)
        p = q.batch_preview(
            conflict_code="PROVIDER_TYPE_VS_KIND_TAG", from_value="MOVIE", to_value="OVA"
        )
        наполнить(sandbox, 6)  # набор вырос
        with pytest.raises(ReviewError, match="набор изменился"):
            q.batch_apply(
                conflict_code="PROVIDER_TYPE_VS_KIND_TAG",
                from_value="MOVIE",
                to_value="OVA",
                actor="e",
                expected_fingerprint=p["versionFingerprint"],
            )

    def test_применение_проверяет_себя(self, sandbox):
        q = наполнить(sandbox, 4)
        p = q.batch_preview(
            conflict_code="PROVIDER_TYPE_VS_KIND_TAG", from_value="MOVIE", to_value="OVA"
        )
        r = q.batch_apply(
            conflict_code="PROVIDER_TYPE_VS_KIND_TAG",
            from_value="MOVIE",
            to_value="OVA",
            actor="e",
            expected_fingerprint=p["versionFingerprint"],
        )
        assert r["changed"] == r["verified"] == 4 and r["consistent"]

    def test_откат_партии_возвращает_все_записи(self, sandbox):
        q = наполнить(sandbox, 4)
        p = q.batch_preview(
            conflict_code="PROVIDER_TYPE_VS_KIND_TAG", from_value="MOVIE", to_value="OVA"
        )
        r = q.batch_apply(
            conflict_code="PROVIDER_TYPE_VS_KIND_TAG",
            from_value="MOVIE",
            to_value="OVA",
            actor="e",
            expected_fingerprint=p["versionFingerprint"],
        )
        b = q.batch_revert(batch_id=r["batchId"], actor="e")
        assert b["reverted"] == 4
        assert q.list()["byState"] == {"OPEN": 4}

    def test_откат_не_трогает_чужие_решения(self, sandbox):
        """Партия отменяется целиком, но только своя."""
        q = наполнить(sandbox, 4)
        одиночная = q.list()["items"][0]["itemId"]
        q.decide(одиночная, value="OVA", actor="ручное", expected_version=1)
        p = q.batch_preview(
            conflict_code="PROVIDER_TYPE_VS_KIND_TAG", from_value="MOVIE", to_value="OVA"
        )
        r = q.batch_apply(
            conflict_code="PROVIDER_TYPE_VS_KIND_TAG",
            from_value="MOVIE",
            to_value="OVA",
            actor="e",
            expected_fingerprint=p["versionFingerprint"],
        )
        q.batch_revert(batch_id=r["batchId"], actor="e")
        assert q.get(одиночная).state is ReviewState.RESOLVED
        assert q.get(одиночная).decided_by == "ручное"

    def test_пустой_набор_это_отказ_а_не_успех(self, sandbox):
        q = наполнить(sandbox, 1)
        p = q.batch_preview(conflict_code="НЕТ_ТАКОГО", from_value="", to_value="OVA")
        with pytest.raises(ReviewError, match="ни одной подходящей"):
            q.batch_apply(
                conflict_code="НЕТ_ТАКОГО",
                from_value="",
                to_value="OVA",
                actor="e",
                expected_fingerprint=p["versionFingerprint"],
            )


# --------------------------------------------------------------------------
# Control API и права
# --------------------------------------------------------------------------
class TestApi:
    def api(self, sandbox, token):
        return ControlApi(root=sandbox, env=ENV_CONTROL), {"Authorization": f"Bearer {token}"}

    def test_читатель_видит_очередь(self, sandbox):
        наполнить(sandbox, 3)
        api, h = self.api(sandbox, ЧИТАТЕЛЬ)
        r = api.handle("GET", "/api/v1/review-queue", headers=h)
        assert r.status == 200 and r.body["total"] == 3
        assert r.body["contractVersion"] == CONTRACT_VERSION

    def test_читатель_не_может_решать(self, sandbox):
        наполнить(sandbox, 1)
        api, h = self.api(sandbox, ЧИТАТЕЛЬ)
        iid = api.handle("GET", "/api/v1/review-queue", headers=h).body["items"][0]["itemId"]
        r = api.handle(
            "POST",
            f"/api/v1/review-queue/{iid}/decide",
            body={"value": "OVA", "expectedVersion": 1},
            headers=h,
        )
        assert r.status == 403

    def test_отказ_читателя_не_имеет_побочного_эффекта(self, sandbox):
        наполнить(sandbox, 1)
        api, h = self.api(sandbox, ЧИТАТЕЛЬ)
        iid = api.handle("GET", "/api/v1/review-queue", headers=h).body["items"][0]["itemId"]
        api.handle(
            "POST",
            f"/api/v1/review-queue/{iid}/decide",
            body={"value": "OVA", "expectedVersion": 1},
            headers=h,
        )
        assert ReviewQueue(sandbox).get(iid).state is ReviewState.OPEN

    def test_отказ_попадает_в_журнал(self, sandbox):
        наполнить(sandbox, 1)
        api, h = self.api(sandbox, ЧИТАТЕЛЬ)
        iid = api.handle("GET", "/api/v1/review-queue", headers=h).body["items"][0]["itemId"]
        api.handle(
            "POST",
            f"/api/v1/review-queue/{iid}/decide",
            body={"value": "OVA", "expectedVersion": 1},
            headers=h,
        )
        from factory import audit

        записи = audit.read_all()
        assert any(
            з.get("exit_code") == 403 or "403" in json.dumps(з, ensure_ascii=False)
            for з in записи[-5:]
        ), "отказ по праву обязан быть в журнале"

    def test_конфликт_версии_это_409_а_не_500(self, sandbox):
        наполнить(sandbox, 1)
        api, h = self.api(sandbox, РЕДАКТОР)
        iid = api.handle("GET", "/api/v1/review-queue", headers=h).body["items"][0]["itemId"]
        api.handle(
            "POST",
            f"/api/v1/review-queue/{iid}/decide",
            body={"value": "OVA", "expectedVersion": 1},
            headers=h,
        )
        r = api.handle(
            "POST",
            f"/api/v1/review-queue/{iid}/decide",
            body={"value": "MOVIE", "expectedVersion": 1},
            headers=h,
        )
        assert r.status == 409

    def test_негодный_идентификатор_не_выходит_за_каталог(self, sandbox):
        """Путь из идентификатора не должен читать чужие файлы."""
        наполнить(sandbox, 1)
        api, h = self.api(sandbox, ЧИТАТЕЛЬ)
        r = api.handle("GET", "/api/v1/review-queue/..%2F..%2Fetc%2Fpasswd", headers=h)
        assert r.status in (400, 404)

    def test_предел_страницы_ограничен(self, sandbox):
        наполнить(sandbox, 3)
        api, h = self.api(sandbox, ЧИТАТЕЛЬ)
        assert (
            api.handle("GET", "/api/v1/review-queue", body={"limit": 100000}, headers=h).status
            == 400
        )

    def test_групповое_применение_требует_права(self, sandbox):
        наполнить(sandbox, 2)
        api, h = self.api(sandbox, ЧИТАТЕЛЬ)
        p = api.handle(
            "POST",
            "/api/v1/review-queue/batch",
            body={"mode": "dryRun", "conflictCode": "PROVIDER_TYPE_VS_KIND_TAG", "toValue": "OVA"},
            headers=h,
        )
        assert p.status == 200
        r = api.handle(
            "POST",
            "/api/v1/review-queue/batch",
            body={
                "mode": "apply",
                "conflictCode": "PROVIDER_TYPE_VS_KIND_TAG",
                "toValue": "OVA",
                "expectedFingerprint": p.body["versionFingerprint"],
            },
            headers=h,
        )
        assert r.status == 403


# --------------------------------------------------------------------------
# Путь редактора в панели
# --------------------------------------------------------------------------
class TestПутьРедактора:
    def test_сценарий_редактора_целиком(self, app):
        """Найти спорный тайтл, изучить доказательства, решить, проверить."""
        cookies, csrf = войти(app)
        список = app.handle("GET", "/admin/review", cookies=cookies)
        assert список.status == 200
        assert "Спорный тайтл 0" in список.html
        assert "поле type поставщика" in список.html and "тег вида у поставщика" in список.html

        iid = ReviewQueue(PATHS.root).list()["items"][0]["itemId"]
        карточка = app.handle("GET", f"/admin/review/{iid}", cookies=cookies)
        assert карточка.status == 200
        # Доказательства попадают в разметку ЭКРАНИРОВАННЫМИ: type='movie'
        # выводится как type=&#x27;movie&#x27;. Проверяется смысл, а не
        # дословная строка, иначе тест требовал бы отключить экранирование.
        for обязательное in (
            "movie",
            "ova",
            "myanimelist",
            "MOVIE",
            "OVA",
            "Утверждения",
            "История",
            "Доказательство",
        ):
            assert обязательное in карточка.html, обязательное
        assert "&#x27;" in карточка.html, "кавычки обязаны быть экранированы"

        решение = app.handle(
            "POST",
            f"/admin/review/{iid}/decide",
            cookies=cookies,
            form={
                CSRF_FIELD: csrf,
                "value": "OVA",
                "expectedVersion": "1",
                "note": "по тегу источника",
            },
        )
        assert решение.status == 303
        после = app.handle("GET", f"/admin/review/{iid}", cookies=cookies)
        assert "RESOLVED" in после.html and "по тегу источника" in после.html
        assert ReviewQueue(PATHS.root).get(iid).decided_value == "OVA"

    def test_читатель_не_видит_кнопок_решения(self, app):
        cookies, _ = войти(app, ЧИТАТЕЛЬ)
        iid = ReviewQueue(PATHS.root).list()["items"][0]["itemId"]
        html = app.handle("GET", f"/admin/review/{iid}", cookies=cookies).html
        assert "Взять в работу" not in html
        assert "Групповое решение" not in app.handle("GET", "/admin/review", cookies=cookies).html

    def test_читателю_отказано_и_состояние_не_изменилось(self, app):
        cookies, csrf = войти(app, ЧИТАТЕЛЬ)
        iid = ReviewQueue(PATHS.root).list()["items"][0]["itemId"]
        app.handle(
            "POST",
            f"/admin/review/{iid}/decide",
            cookies=cookies,
            form={CSRF_FIELD: csrf, "value": "OVA", "expectedVersion": "1"},
        )
        assert ReviewQueue(PATHS.root).get(iid).state is ReviewState.OPEN

    def test_подделанная_форма_отклонена(self, app):
        cookies, _ = войти(app)
        iid = ReviewQueue(PATHS.root).list()["items"][0]["itemId"]
        r = app.handle(
            "POST",
            f"/admin/review/{iid}/decide",
            cookies=cookies,
            form={CSRF_FIELD: "подделка", "value": "OVA"},
        )
        assert r.status == 403
        assert ReviewQueue(PATHS.root).get(iid).state is ReviewState.OPEN

    def test_без_сессии_запись_отклонена(self, app):
        iid = ReviewQueue(PATHS.root).list()["items"][0]["itemId"]
        assert (
            app.handle("POST", f"/admin/review/{iid}/decide", form={"value": "OVA"}).status == 403
        )

    def test_отмена_решения_через_панель(self, app):
        cookies, csrf = войти(app)
        iid = ReviewQueue(PATHS.root).list()["items"][0]["itemId"]
        app.handle(
            "POST",
            f"/admin/review/{iid}/decide",
            cookies=cookies,
            form={CSRF_FIELD: csrf, "value": "OVA", "expectedVersion": "1", "note": "решил"},
        )
        app.handle(
            "POST",
            f"/admin/review/{iid}/revert",
            cookies=cookies,
            form={CSRF_FIELD: csrf, "note": "передумал"},
        )
        assert ReviewQueue(PATHS.root).get(iid).state is ReviewState.OPEN

    def test_сухой_прогон_в_панели_показывает_выборку(self, app):
        cookies, _ = войти(app)
        r = app.handle(
            "GET",
            "/admin/review/batch",
            cookies=cookies,
            form={
                "conflictCode": "PROVIDER_TYPE_VS_KIND_TAG",
                "fromValue": "MOVIE",
                "toValue": "OVA",
            },
        )
        assert r.status == 200
        assert "Спорный тайтл" in r.html and "Отпечаток набора" in r.html
        assert "Применить к 4 записям" in r.html

    def test_страница_очереди_не_ломается_на_чужой_опечатке(self, app):
        cookies, _ = войти(app)
        assert (
            app.handle("GET", "/admin/review", cookies=cookies, form={"offset": "абв"}).status
            == 200
        )

    def test_название_с_разметкой_экранируется(self, sandbox):
        """Название приходит от поставщика: доверять ему как разметке нельзя."""
        q = ReviewQueue(sandbox)
        eid = f"{SITE}:xss"
        q.upsert(
            ReviewItem(
                item_id=item_id_for(eid, "contentKind"),
                internal_entity_id=eid,
                site_id=SITE,
                conflict_code="PROVIDER_TYPE_VS_KIND_TAG",
                field="contentKind",
                claims=(
                    Claim("MOVIE", "поле type", "type='movie'"),
                    Claim("OVA", "тег", "tags=['ova']"),
                ),
                title="<script>alert(1)</script>",
            )
        )
        read = create_api(
            [SITE], root=sandbox, loader=lambda p: (InMemoryStore(p.site_id), "т"), env=ENV_READ
        )
        приложение = AdminApp(read, ControlApi(root=sandbox, env=ENV_CONTROL))
        cookies, _ = войти(приложение)
        html = приложение.handle("GET", "/admin/review", cookies=cookies).html
        assert "<script>alert(1)</script>" not in html
        assert "&lt;script&gt;" in html

    def test_пустая_очередь_объясняет_себя(self, sandbox):
        read = create_api(
            [SITE], root=sandbox, loader=lambda p: (InMemoryStore(p.site_id), "т"), env=ENV_READ
        )
        пустая = AdminApp(read, ControlApi(root=sandbox, env=ENV_CONTROL))
        cookies, _ = войти(пустая)
        html = пустая.handle("GET", "/admin/review", cookies=cookies).html
        assert "Записей нет" in html and "не ошибка" in html
