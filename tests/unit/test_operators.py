"""REQ-OPERATORS: каталог операторов, роли, приглашения, сессии.

До этого модель доступа была «вход по токену Control API». Для одного человека
этого хватает, для команды нет: токен нельзя отозвать у одного и оставить у
другого, нельзя увидеть, кто вошёл, нельзя заблокировать человека, не выбив
остальных, и в журнале виден отпечаток токена, а не человек.

Проверяется не наличие маршрутов, а свойства, потеря которых стоит дорого:
отзыв действует немедленно, последнего администратора нельзя убрать, себе
полномочия не повышают, отказ входа не различает причину.
"""

from __future__ import annotations

import time

import pytest

from factory.site_engine.api.control import ControlApi
from factory.site_engine.operators import (
    CONTRACT_VERSION,
    LOCKOUT_THRESHOLD,
    ROLES,
    Invite,
    MfaState,
    OperatorDirectory,
    OperatorError,
    OperatorState,
    hash_password,
    scopes_for,
    verify_password,
)

ПАРОЛЬ = "надёжный-пароль-1"


@pytest.fixture
def каталог(tmp_path):
    return OperatorDirectory(tmp_path)


def завести(каталог, email, роли, *, кем="bootstrap"):
    _, секрет = каталог.invite(
        email=email, roles=роли, created_by=кем, super_admin=True
    )
    return каталог.accept_invite(secret=секрет, password=ПАРОЛЬ)


# --------------------------------------------------------------------------
# Пароли и роли
# --------------------------------------------------------------------------
class TestОсновы:
    def test_пароль_хранится_только_хэшем(self):
        з = hash_password(ПАРОЛЬ)
        assert з["algo"] == "scrypt"
        assert ПАРОЛЬ not in str(з)
        assert verify_password(ПАРОЛЬ, з) and not verify_password("другой", з)

    def test_короткий_пароль_отклонён(self):
        with pytest.raises(OperatorError, match="короче"):
            hash_password("коротко")

    def test_отсутствие_записи_это_отказ_а_не_ошибка(self):
        assert verify_password(ПАРОЛЬ, None) is False
        assert verify_password(ПАРОЛЬ, {"algo": "своя-схема"}) is False

    @pytest.mark.parametrize("роль", sorted(ROLES))
    def test_каждая_роль_даёт_известные_права(self, роль):
        assert scopes_for([роль])

    def test_неизвестная_роль_не_молчит(self):
        with pytest.raises(OperatorError, match="неизвестная роль"):
            scopes_for(["суперпользователь"])

    def test_роли_упорядочены_по_праву(self):
        """viewer не должен внезапно уметь больше, чем editor."""
        assert set(scopes_for(["viewer"])) < set(scopes_for(["reviewer"]))
        assert set(scopes_for(["reviewer"])) < set(scopes_for(["editor"]))
        assert set(scopes_for(["editor"])) < set(scopes_for(["operator"]))
        assert set(scopes_for(["operator"])) < set(scopes_for(["admin"]))

    def test_право_на_людей_только_у_администратора(self):
        for роль in ROLES:
            есть = "operators:write" in scopes_for([роль])
            assert есть == (роль == "admin"), роль

    def test_адрес_приводится_к_одному_виду(self, каталог):
        завести(каталог, "Admin@Example.COM", ["admin"])
        assert каталог.by_email("admin@example.com") is not None
        assert каталог.by_email("ADMIN@EXAMPLE.COM") is not None

    def test_негодный_адрес_отклонён(self, каталог):
        with pytest.raises(OperatorError, match="негодный адрес"):
            каталог.invite(
                email="без-собаки", roles=["viewer"], created_by="b", super_admin=True
            )


# --------------------------------------------------------------------------
# Приглашения
# --------------------------------------------------------------------------
class TestПриглашения:
    def test_секрет_не_попадает_на_диск(self, каталог, tmp_path):
        _, секрет = каталог.invite(
            email="a@x.com", roles=["viewer"], created_by="b", super_admin=True
        )
        весь = "".join(
            ф.read_text(encoding="utf-8")
            for ф in (tmp_path / "var/state/operators").rglob("*.json")
        )
        assert секрет not in весь, "одноразовый секрет обязан храниться только хэшем"

    def test_приглашённый_виден_в_списке_сразу(self, каталог):
        каталог.invite(
            email="a@x.com", roles=["viewer"], created_by="b", super_admin=True
        )
        assert каталог.list()["byState"].get("INVITED") == 1

    def test_принятие_задаёт_пароль_приглашённым(self, каталог):
        o = завести(каталог, "a@x.com", ["editor"])
        assert o.state is OperatorState.ACTIVE and o.roles == ("editor",)
        assert каталог.authenticate(email="a@x.com", password=ПАРОЛЬ)

    def test_повторное_использование_отклонено(self, каталог):
        _, секрет = каталог.invite(
            email="a@x.com", roles=["viewer"], created_by="b", super_admin=True
        )
        каталог.accept_invite(secret=секрет, password=ПАРОЛЬ)
        with pytest.raises(OperatorError, match="уже использовано"):
            каталог.accept_invite(secret=секрет, password="другой-пароль-11")

    def test_отозванное_приглашение_не_принимается(self, каталог):
        приглашение, секрет = каталог.invite(
            email="a@x.com", roles=["viewer"], created_by="b", super_admin=True
        )
        каталог.revoke_invite(приглашение.invite_id, actor="b")
        with pytest.raises(OperatorError, match="отозвано"):
            каталог.accept_invite(secret=секрет, password=ПАРОЛЬ)

    def test_истёкшее_приглашение_не_принимается(self, tmp_path):
        часы = [1000.0]
        к = OperatorDirectory(tmp_path, now=lambda: часы[0])
        _, секрет = к.invite(
            email="a@x.com", roles=["viewer"], created_by="b",
            ttl_seconds=60, super_admin=True,
        )
        часы[0] += 61
        with pytest.raises(OperatorError, match="истёк"):
            к.accept_invite(secret=секрет, password=ПАРОЛЬ)
        assert [i["state"] for i in к.list_invites()] == ["EXPIRED"]

    def test_чужой_секрет_не_подходит(self, каталог):
        каталог.invite(
            email="a@x.com", roles=["viewer"], created_by="b", super_admin=True
        )
        with pytest.raises(OperatorError, match="не найдено"):
            каталог.accept_invite(secret="подобранный", password=ПАРОЛЬ)

    def test_приглашение_без_ролей_бессмысленно(self, каталог):
        with pytest.raises(OperatorError, match="без ролей"):
            каталог.invite(
                email="a@x.com", roles=[], created_by="b", super_admin=True
            )

    def test_приглашение_активного_отклонено(self, каталог):
        завести(каталог, "a@x.com", ["viewer"])
        with pytest.raises(OperatorError, match="уже активен"):
            каталог.invite(
                email="a@x.com", roles=["admin"], created_by="b", super_admin=True
            )


# --------------------------------------------------------------------------
# Вход
# --------------------------------------------------------------------------
class TestВход:
    def test_отказ_не_различает_причину(self, каталог):
        """Разные сообщения дали бы перебор адресов."""
        завести(каталог, "a@x.com", ["viewer"])
        сообщения = set()
        for адрес, пароль in (
            ("a@x.com", "неверный"),
            ("нет@x.com", ПАРОЛЬ),
            ("совсем-не-адрес", ПАРОЛЬ),
        ):
            with pytest.raises(OperatorError) as e:
                каталог.authenticate(email=адрес, password=пароль)
            сообщения.add(str(e.value))
        assert len(сообщения) == 1, сообщения

    def test_блокировка_после_нескольких_неудач(self, каталог):
        o = завести(каталог, "a@x.com", ["viewer"])
        for _ in range(LOCKOUT_THRESHOLD):
            with pytest.raises(OperatorError):
                каталог.authenticate(email="a@x.com", password="неверный")
        # Верный пароль тоже не проходит, пока держится блокировка.
        with pytest.raises(OperatorError):
            каталог.authenticate(email="a@x.com", password=ПАРОЛЬ)
        assert каталог.get(o.operator_id).locked_until > 0

    def test_удачный_вход_обнуляет_счётчик(self, каталог):
        o = завести(каталог, "a@x.com", ["viewer"])
        with pytest.raises(OperatorError):
            каталог.authenticate(email="a@x.com", password="неверный")
        каталог.authenticate(email="a@x.com", password=ПАРОЛЬ)
        assert каталог.get(o.operator_id).failed_logins == 0

    def test_заблокированный_не_входит(self, каталог):
        завести(каталог, "admin@x.com", ["admin"])
        o = завести(каталог, "b@x.com", ["editor"])
        админ = каталог.by_email("admin@x.com")
        каталог.block(o.operator_id, reason="проверка", actor_id=админ.operator_id)
        with pytest.raises(OperatorError):
            каталог.authenticate(email="b@x.com", password=ПАРОЛЬ)


# --------------------------------------------------------------------------
# Роли, блокировка, защиты
# --------------------------------------------------------------------------
class TestЗащиты:
    def test_последнего_администратора_нельзя_разжаловать(self, каталог):
        o = завести(каталог, "admin@x.com", ["admin"])
        with pytest.raises(OperatorError, match="последний активный администратор"):
            каталог.set_roles(o.operator_id, ["viewer"], actor_id="другой", actor_roles=["admin"])

    def test_последнего_администратора_нельзя_заблокировать(self, каталог):
        o = завести(каталог, "admin@x.com", ["admin"])
        with pytest.raises(OperatorError, match="последний активный"):
            каталог.block(o.operator_id, reason="x", actor_id="другой")

    def test_последнего_администратора_нельзя_удалить(self, каталог):
        o = завести(каталог, "admin@x.com", ["admin"])
        with pytest.raises(OperatorError, match="последний активный"):
            каталог.delete(o.operator_id, actor_id="другой")

    def test_при_втором_администраторе_первого_можно_разжаловать(self, каталог):
        первый = завести(каталог, "a@x.com", ["admin"])
        второй = завести(каталог, "b@x.com", ["admin"])
        итог = каталог.set_roles(
            первый.operator_id, ["viewer"], actor_id=второй.operator_id, actor_roles=["admin"]
        )
        assert итог.roles == ("viewer",)

    def test_нельзя_повысить_себя(self, каталог):
        ред = завести(каталог, "e@x.com", ["editor"])
        with pytest.raises(OperatorError, match="собственные полномочия"):
            каталог.set_roles(
                ред.operator_id, ["admin"], actor_id=ред.operator_id, actor_roles=["editor"]
            )

    def test_понизить_себя_можно(self, каталог):
        завести(каталог, "a@x.com", ["admin"])
        ред = завести(каталог, "e@x.com", ["operator"])
        assert каталог.set_roles(
            ред.operator_id, ["viewer"], actor_id=ред.operator_id, actor_roles=["operator"]
        ).roles == ("viewer",)

    def test_нельзя_заблокировать_себя(self, каталог):
        завести(каталог, "a@x.com", ["admin"])
        o = завести(каталог, "b@x.com", ["admin"])
        with pytest.raises(OperatorError, match="самого себя"):
            каталог.block(o.operator_id, reason="x", actor_id=o.operator_id)

    def test_разблокировка_возвращает_в_строй(self, каталог):
        админ = завести(каталог, "a@x.com", ["admin"])
        o = завести(каталог, "b@x.com", ["editor"])
        каталог.block(o.operator_id, reason="x", actor_id=админ.operator_id)
        assert каталог.unblock(o.operator_id).state is OperatorState.ACTIVE
        assert каталог.authenticate(email="b@x.com", password=ПАРОЛЬ)

    def test_удаление_не_стирает_запись(self, каталог):
        """Журнал ссылается на действующее лицо: исчезнувший id — загадка."""
        админ = завести(каталог, "a@x.com", ["admin"])
        o = завести(каталог, "b@x.com", ["editor"])
        каталог.delete(o.operator_id, actor_id=админ.operator_id)
        мёртвый = каталог.get(o.operator_id)
        assert мёртвый.state is OperatorState.DELETED
        assert мёртвый.password is None and мёртвый.roles == ()


# --------------------------------------------------------------------------
# Сессии
# --------------------------------------------------------------------------
class TestСессии:
    def test_сессия_видна_в_списке(self, каталог):
        o = завести(каталог, "a@x.com", ["editor"])
        каталог.register_session(sid="s1", operator_id=o.operator_id, user_agent="Firefox")
        (строка,) = каталог.list_sessions(operator_id=o.operator_id)
        assert строка["active"] and строка["userAgent"] == "Firefox"
        assert "s1" not in str(строка), "идентификатор сессии не отдаётся наружу"

    def test_отзыв_одной_сессии_не_трогает_остальные(self, каталог):
        o = завести(каталог, "a@x.com", ["editor"])
        каталог.register_session(sid="s1", operator_id=o.operator_id)
        каталог.register_session(sid="s2", operator_id=o.operator_id)
        первая = каталог.list_sessions(operator_id=o.operator_id)[0]["sessionId"]
        assert каталог.revoke_session(первая, actor="admin")
        активные = каталог.list_sessions(operator_id=o.operator_id)
        assert len(активные) == 1

    def test_отозванная_сессия_недействительна_сразу(self, каталог):
        o = завести(каталог, "a@x.com", ["editor"])
        каталог.register_session(sid="s1", operator_id=o.operator_id)
        assert каталог.session_valid("s1") is not None
        каталог.revoke_session(
            каталог.list_sessions(operator_id=o.operator_id)[0]["sessionId"], actor="admin"
        )
        assert каталог.session_valid("s1") is None

    def test_отзыв_всех_гасит_и_будущие_из_прошлого(self, каталог):
        """Отметка времени, а не перебор: перебор пропустил бы гонку."""
        o = завести(каталог, "a@x.com", ["editor"])
        каталог.register_session(sid="s1", operator_id=o.operator_id)
        time.sleep(0.01)
        каталог.revoke_all_sessions(o.operator_id, actor="admin")
        assert каталог.session_valid("s1") is None

    def test_блокировка_гасит_сессию_немедленно(self, каталог):
        админ = завести(каталог, "a@x.com", ["admin"])
        o = завести(каталог, "b@x.com", ["editor"])
        каталог.register_session(sid="s1", operator_id=o.operator_id)
        assert каталог.session_valid("s1") is not None
        каталог.block(o.operator_id, reason="x", actor_id=админ.operator_id)
        assert каталог.session_valid("s1") is None

    def test_смена_ролей_гасит_сессию(self, каталог):
        """Иначе новые ограничения начнут действовать только после выхода."""
        админ = завести(каталог, "a@x.com", ["admin"])
        o = завести(каталог, "b@x.com", ["operator"])
        каталог.register_session(sid="s1", operator_id=o.operator_id)
        time.sleep(0.01)
        каталог.set_roles(
            o.operator_id, ["viewer"], actor_id=админ.operator_id, actor_roles=["admin"]
        )
        assert каталог.session_valid("s1") is None

    def test_смена_пароля_гасит_сессии(self, каталог):
        o = завести(каталог, "a@x.com", ["editor"])
        каталог.register_session(sid="s1", operator_id=o.operator_id)
        time.sleep(0.01)
        каталог.set_password(o.operator_id, password="совершенно-новый-1")
        assert каталог.session_valid("s1") is None

    def test_чужая_сессия_не_даёт_прав(self, каталог):
        assert каталог.session_valid("выдуманный") is None


# --------------------------------------------------------------------------
# Второй фактор
# --------------------------------------------------------------------------
class TestВторойФактор:
    def test_состояние_говорит_что_провайдера_нет(self, каталог):
        o = завести(каталог, "a@x.com", ["editor"])
        assert o.mfa_state is MfaState.PROVIDER_NOT_CONFIGURED
        итог = каталог.start_mfa_enrollment(o.operator_id)
        assert итог["providerConfigured"] is False and итог["blocker"]

    def test_код_восстановления_хранится_хэшем_и_одноразов(self, каталог, tmp_path):
        o = завести(каталог, "a@x.com", ["editor"])
        _, код = каталог.issue_mfa_recovery(o.operator_id)
        весь = "".join(
            ф.read_text(encoding="utf-8")
            for ф in (tmp_path / "var/state/operators").rglob("*.json")
        )
        assert код not in весь
        каталог.consume_mfa_recovery(o.operator_id, code=код)
        with pytest.raises(OperatorError, match="не подходит"):
            каталог.consume_mfa_recovery(o.operator_id, code=код)


# --------------------------------------------------------------------------
# Control API
# --------------------------------------------------------------------------
ENV = {
    "SITE_ENGINE_CONTROL_WRITES": "1",
    "SITE_ENGINE_CONTROL_TOKENS": (
        "adm=read,operators:write,audit:read|ro=read|ed=read,review:write"
    ),
}


class TestApi:
    def api(self, tmp_path, token):
        return (ControlApi(root=tmp_path, env=ENV), {"Authorization": f"Bearer {token}"})

    def test_список_доступен_по_чтению(self, tmp_path):
        завести(OperatorDirectory(tmp_path), "a@x.com", ["admin"])
        api, h = self.api(tmp_path, "ro")
        r = api.handle("GET", "/api/v1/operators", headers=h)
        assert r.status == 200 and r.body["total"] == 1
        assert r.body["contractVersion"] == CONTRACT_VERSION

    def test_список_не_отдаёт_хэш_пароля(self, tmp_path):
        завести(OperatorDirectory(tmp_path), "a@x.com", ["admin"])
        api, h = self.api(tmp_path, "ro")
        тело = str(api.handle("GET", "/api/v1/operators", headers=h).body)
        assert "scrypt" not in тело and "salt" not in тело

    @pytest.mark.parametrize(
        "маршрут,тело",
        [
            (
                "/api/v1/operators/invites",
                {"email": "n@x.com", "roles": ["viewer"], "superAdmin": True},
            ),
            ("/api/v1/operators/sessions/revoke", {"sessionId": "нет"}),
        ],
    )
    def test_изменение_без_права_отклонено(self, tmp_path, маршрут, тело):
        завести(OperatorDirectory(tmp_path), "a@x.com", ["admin"])
        for токен in ("ro", "ed"):
            api, h = self.api(tmp_path, токен)
            assert api.handle("POST", маршрут, body=тело, headers=h).status == 403

    def test_приглашение_через_api_отдаёт_секрет_один_раз(self, tmp_path):
        api, h = self.api(tmp_path, "adm")
        r = api.handle(
            "POST",
            "/api/v1/operators/invites",
            body={"email": "n@x.com", "roles": ["reviewer"], "superAdmin": True},
            headers=h,
        )
        assert r.status == 201 and r.body["secret"]
        список = api.handle("GET", "/api/v1/operators/invites", headers=h)
        assert all("secret" not in i for i in список.body["items"])

    def test_последний_администратор_даёт_409(self, tmp_path):
        o = завести(OperatorDirectory(tmp_path), "a@x.com", ["admin"])
        api, h = self.api(tmp_path, "adm")
        r = api.handle(
            "POST",
            f"/api/v1/operators/{o.operator_id}/block",
            body={"reason": "x", "actorOperatorId": "другой"},
            headers=h,
        )
        assert r.status == 409

    def test_негодный_идентификатор_не_выходит_за_каталог(self, tmp_path):
        завести(OperatorDirectory(tmp_path), "a@x.com", ["admin"])
        api, h = self.api(tmp_path, "adm")
        r = api.handle(
            "POST", "/api/v1/operators/..%2F..%2Fetc/block", body={"reason": "x"}, headers=h
        )
        assert r.status in (400, 404, 409)

    def test_действия_попадают_в_журнал(self, tmp_path):
        api, h = self.api(tmp_path, "adm")
        api.handle(
            "POST",
            "/api/v1/operators/invites",
            body={"email": "n@x.com", "roles": ["viewer"]},
            headers=h,
        )
        from factory import audit

        assert any(з.get("action") == "operators_invite" for з in audit.read_all())

    def test_секрет_приглашения_не_попадает_в_журнал(self, tmp_path):
        api, h = self.api(tmp_path, "adm")
        r = api.handle(
            "POST",
            "/api/v1/operators/invites",
            body={"email": "n@x.com", "roles": ["viewer"], "superAdmin": True},
            headers=h,
        )
        assert r.status == 201, r.body
        import json as _json

        from factory import audit

        assert r.body["secret"] not in _json.dumps(audit.read_all(), ensure_ascii=False)


def test_запись_приглашения_не_содержит_секрета():
    """Форма записи не должна позволять положить секрет рядом с хэшем."""
    поля = {f.name for f in Invite.__dataclass_fields__.values()}
    assert "secret" not in поля and "token" not in поля
