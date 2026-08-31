"""Control Plane: права, команды, идемпотентность, аудит, границы.

Проверки написаны так, чтобы ловить возврат прежнего поведения, а не
подтверждать нынешнее: почти каждая называет, что именно должно упасть.
"""
from __future__ import annotations

import os

import pytest

from factory.site_engine import audit as audit_mod
from factory.site_engine.access import (
    AccessDenied,
    Permission,
    Principal,
    Role,
    allows,
    require,
)
from factory.site_engine.api.control_plane import ControlPlaneApi, apply_filter, apply_sort, paginate
from factory.site_engine.commands import (
    CommandKind,
    CommandLog,
    CommandRejected,
    CommandState,
)


@pytest.fixture
def окружение(monkeypatch):
    monkeypatch.setenv("SITE_ENGINE_API_ENABLED", "1")
    monkeypatch.setenv("APP_ENV", "staging")
    return dict(os.environ)


@pytest.fixture
def api(окружение):
    return ControlPlaneApi(
        read_api=None,
        commands=CommandLog(),
        audit=audit_mod.AuditLog(),
        principals={
            "owner": Principal("owner", (Role.OWNER,)),
            "viewer": Principal("viewer", (Role.VIEWER,)),
            "operator": Principal("operator", (Role.OPERATOR,)),
            "editor-one": Principal("editor-one", (Role.EDITOR,), frozenset({"site-a"})),
        },
        collectors={
            "sites": lambda: [
                {"id": "site-a", "site_id": "site-a", "name": "Альфа"},
                {"id": "site-b", "site_id": "site-b", "name": "Бета"},
                {"id": "site-c", "site_id": "site-c", "name": "Гамма"},
            ],
            "audit-events": lambda: [],
        },
        env=окружение,
    )


# ------------------------------------------------------------------- права
class TestПрава:
    def test_роль_наблюдателя_не_публикует(self):
        p = Principal("v", (Role.VIEWER,))
        assert allows(p, Permission.SITES_READ)
        assert not allows(p, Permission.PUBLISH_PRODUCTION)

    def test_публикация_в_production_только_у_владельца(self):
        для_всех = [Role.VIEWER, Role.EDITOR, Role.SEO, Role.OPERATOR, Role.ADMIN]
        for роль in для_всех:
            assert not allows(Principal("x", (роль,)), Permission.PUBLISH_PRODUCTION), роль
        assert allows(Principal("o", (Role.OWNER,)), Permission.PUBLISH_PRODUCTION)

    def test_область_сайта_ограничивает_право(self):
        p = Principal("a", (Role.ADMIN,), frozenset({"site-a"}))
        assert allows(p, Permission.PROFILE_WRITE, "site-a")
        assert not allows(p, Permission.PROFILE_WRITE, "site-b")

    def test_отказ_это_исключение_а_не_значение(self):
        """Право, возвращаемое значением, легко забыть проверить."""
        with pytest.raises(AccessDenied):
            require(Principal("v", (Role.VIEWER,)), Permission.ROLLBACK_RUN)

    def test_seo_не_получает_доступа_к_выкладке(self):
        """Граница SEO держится правами, а не договорённостью."""
        p = Principal("s", (Role.SEO,))
        assert allows(p, Permission.SEO_WRITE)
        for запрещённое in (Permission.PUBLISH_CANARY, Permission.PUBLISH_PRODUCTION,
                            Permission.INGESTION_RUN, Permission.ROLLBACK_RUN):
            assert not allows(p, запрещённое), запрещённое


# ------------------------------------------------------------------ команды
class TestКоманды:
    def test_повтор_с_тем_же_ключом_не_создаёт_вторую(self):
        log = CommandLog()
        op = Principal("op", (Role.OPERATOR,))
        первая, повтор1 = log.submit(kind=CommandKind.INGESTION_RUN, principal=op,
                                     site_id="s", payload={}, idempotency_key="k")
        вторая, повтор2 = log.submit(kind=CommandKind.INGESTION_RUN, principal=op,
                                     site_id="s", payload={}, idempotency_key="k")
        assert not повтор1 and повтор2
        assert первая.command_id == вторая.command_id
        assert len(log) == 1

    def test_команда_без_ключа_не_принимается(self):
        with pytest.raises(CommandRejected, match="ключа идемпотентности"):
            CommandLog().submit(kind=CommandKind.INGESTION_RUN,
                                principal=Principal("op", (Role.OPERATOR,)),
                                site_id="s", payload={}, idempotency_key="")

    def test_опасная_команда_требует_отдельного_подтверждения(self):
        """Иначе «сохранить форму» однажды становится «выложить в production»."""
        log = CommandLog()
        owner = Principal("o", (Role.OWNER,))
        with pytest.raises(CommandRejected, match="подтверждение"):
            log.submit(kind=CommandKind.RELEASE_PUBLISH, principal=owner, site_id="s",
                       payload={}, idempotency_key="k1")
        команда, _ = log.submit(kind=CommandKind.RELEASE_PUBLISH, principal=owner, site_id="s",
                                payload={}, idempotency_key="k2", confirmed=True)
        assert команда.state is CommandState.DRAFT

    def test_переходы_состояний_закрыты(self):
        log = CommandLog()
        команда, _ = log.submit(kind=CommandKind.INGESTION_RUN,
                                principal=Principal("op", (Role.OPERATOR,)),
                                site_id="s", payload={}, idempotency_key="k")
        with pytest.raises(CommandRejected, match="не предусмотрен"):
            log.transition(команда.command_id, CommandState.SUCCEEDED)
        for состояние in (CommandState.VALIDATING, CommandState.QUEUED,
                          CommandState.RUNNING, CommandState.SUCCEEDED):
            log.transition(команда.command_id, состояние)
        assert log.get(команда.command_id).state is CommandState.SUCCEEDED

    def test_версия_объекта_ловит_одновременную_правку(self):
        log = CommandLog()
        admin = Principal("a", (Role.ADMIN,))
        c, _ = log.submit(kind=CommandKind.PROFILE_UPDATE, principal=admin, site_id="s",
                          payload={}, idempotency_key="v1", expected_version=0)
        for st in (CommandState.VALIDATING, CommandState.QUEUED,
                   CommandState.RUNNING, CommandState.SUCCEEDED):
            log.transition(c.command_id, st)
        assert log.version_of(CommandKind.PROFILE_UPDATE, "s") == 1
        with pytest.raises(CommandRejected, match="объект изменили"):
            log.submit(kind=CommandKind.PROFILE_UPDATE, principal=admin, site_id="s",
                       payload={}, idempotency_key="v2", expected_version=0)

    def test_payload_не_отдаётся_целиком(self):
        """В содержании команды может оказаться что угодно, включая лишнее."""
        log = CommandLog()
        c, _ = log.submit(kind=CommandKind.INGESTION_RUN,
                          principal=Principal("op", (Role.OPERATOR,)),
                          site_id="s", payload={"budget": 10, "внутреннее": "x"},
                          idempotency_key="k")
        представление = c.as_dict()
        assert "payload" not in представление
        assert представление["payload_keys"] == ["budget", "внутреннее"]


# --------------------------------------------------------------- выборка
class TestВыборка:
    def test_страница_считает_итог_и_признак_следующей(self):
        записи = [{"id": str(i)} for i in range(10)]
        стр = paginate(записи, {"page": 2, "per_page": 3})
        assert [i["id"] for i in стр.items] == ["3", "4", "5"]
        assert стр.as_dict()["page"]["total_pages"] == 4
        assert стр.as_dict()["page"]["has_next"] is True

    def test_размер_страницы_ограничен_сверху(self):
        """Иначе один запрос выгружает всё хранилище."""
        стр = paginate([{"id": str(i)} for i in range(500)], {"per_page": 100000})
        assert стр.per_page == 200

    def test_фильтр_по_подстроке_и_по_полю(self):
        записи = [{"id": "a", "site_id": "s1"}, {"id": "b", "site_id": "s2"}]
        assert len(apply_filter(записи, {"q": "s2"})) == 1
        assert len(apply_filter(записи, {"site_id": "s1"})) == 1
        assert len(apply_filter(записи, {"page": 2})) == 2  # служебные не фильтруют

    def test_сортировка_в_обе_стороны(self):
        записи = [{"id": "b"}, {"id": "a"}, {"id": "c"}]
        assert [i["id"] for i in apply_sort(записи, {"sort": "id"})] == ["a", "b", "c"]
        assert [i["id"] for i in apply_sort(записи, {"sort": "id", "order": "desc"})] == ["c", "b", "a"]


# ------------------------------------------------------------------- API
class TestApi:
    def test_неопознанное_лицо_получает_401_а_не_403(self, api):
        """Разница между «кто ты» и «тебе нельзя» нужна при разборе инцидента."""
        assert api.handle("GET", "/api/v1/sites", principal_id="нет").status == 401

    def test_наблюдатель_читает_но_не_командует(self, api):
        assert api.handle("GET", "/api/v1/sites", principal_id="viewer").status == 200
        ответ = api.handle("POST", "/api/v1/publications", principal_id="viewer",
                           body={"site_id": "site-a", "confirmed": True})
        assert ответ.status == 403

    def test_редактор_чужого_сайта_отклонён(self, api):
        свой = api.handle("POST", "/api/v1/commands", principal_id="editor-one",
                          body={"kind": "editorial.create", "site_id": "site-a",
                                "payload": {}, "idempotency_key": "e1"})
        чужой = api.handle("POST", "/api/v1/commands", principal_id="editor-one",
                           body={"kind": "editorial.create", "site_id": "site-b",
                                 "payload": {}, "idempotency_key": "e2"})
        assert свой.status == 202
        assert чужой.status == 403

    def test_каждый_ответ_несёт_идентификатор_связи(self, api):
        ответ = api.handle("GET", "/api/v1/sites", principal_id="viewer",
                           headers={"X-Correlation-Id": "мой-запрос"})
        assert ответ.body["correlation_id"] == "мой-запрос"

    def test_неподключённый_источник_отвечает_501_а_не_пустым_списком(self, api):
        """Пустой список неотличим от «данных нет», и это скрывает поломку."""
        ответ = api.handle("GET", "/api/v1/media", principal_id="viewer")
        assert ответ.status == 501

    def test_команда_попадает_в_аудит_один_раз(self, api):
        тело = {"site_id": "site-a", "payload": {}, "idempotency_key": "j1"}
        api.handle("POST", "/api/v1/jobs", principal_id="operator", body=тело)
        api.handle("POST", "/api/v1/jobs", principal_id="operator", body=тело)
        assert len(api.audit) == 1, "повтор не должен порождать вторую запись аудита"

    def test_выключенный_api_отвечает_404_а_не_403(self, окружение, monkeypatch):
        monkeypatch.delenv("SITE_ENGINE_API_ENABLED", raising=False)
        выключенный = ControlPlaneApi(
            read_api=None, commands=CommandLog(), audit=audit_mod.AuditLog(),
            principals={"o": Principal("o", (Role.OWNER,))},
            collectors={}, env=dict(os.environ),
        )
        assert выключенный.handle("GET", "/api/v1/sites", principal_id="o").status == 404


# ------------------------------------------------------------- спецификация
class TestСпецификация:
    def test_спецификация_порождается_из_таблиц_маршрутизатора(self):
        from factory.site_engine.api.control_plane import COMMAND_ROUTES, READ_RESOURCES
        from factory.site_engine.api.openapi_v1 import spec

        документ = spec()
        for ресурс in READ_RESOURCES:
            assert f"/api/v1/{ресурс}" in документ["paths"], ресурс
        for ресурс in COMMAND_ROUTES:
            assert "post" in документ["paths"][f"/api/v1/{ресурс}"], ресурс

    def test_все_ссылки_разрешаются(self):
        import json as _json
        import re

        from factory.site_engine.api.openapi_v1 import spec

        документ = spec()
        текст = _json.dumps(документ)
        for ссылка in set(re.findall(r'"\$ref":\s*"([^"]+)"', текст)):
            узел = документ
            for часть in ссылка.lstrip("#/").split("/"):
                assert часть in узел, f"висячая ссылка {ссылка}"
                узел = узел[часть]
