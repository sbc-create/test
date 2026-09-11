"""G04: аутентификация, Idempotency-Key, конкурентность. G06: сверка."""
import os, sys, pytest
sys.path.insert(0, "/srv/site-factory/registry-core")
import registry_store as rs, registry_command as rc

ТОКЕН = "test-token-not-a-real-secret"


@pytest.fixture(autouse=True)
def окружение(monkeypatch):
    monkeypatch.setenv(rc.ТОКЕН_REF, ТОКЕН)


@pytest.fixture()
def db(tmp_path):
    return rs.открыть(tmp_path / "t.sqlite3")


ЗАГ = {"authorization": f"Bearer {ТОКЕН}", "x-service-name": "service:architect"}


def поля(домен, среда="test"):
    return {"canonical_domain": домен, "family": "test", "environment": среда,
            "lifecycle_state": "DRAFT", "integration_refs": {}}


def test_без_токена_команда_отклонена(db):
    with pytest.raises(rc.AuthError):
        rc.выполнить(db, команда="register", site_id="s1", поля=поля("s1.test"),
                     заголовки={"idempotency-key": "k1"})
    assert db.execute("SELECT count(*) c FROM site").fetchone()["c"] == 0


def test_неверный_токен_отклонён(db):
    with pytest.raises(rc.AuthError):
        rc.выполнить(db, команда="register", site_id="s1", поля=поля("s1.test"),
                     заголовки={"authorization": "Bearer wrong",
                                "idempotency-key": "k1"})


def test_без_idempotency_key_отклонено(db):
    with pytest.raises(ValueError):
        rc.выполнить(db, команда="register", site_id="s1", поля=поля("s1.test"),
                     заголовки=dict(ЗАГ))


def test_повтор_с_тем_же_ключом_не_создаёт_второй(db):
    з = dict(ЗАГ, **{"idempotency-key": "k-1"})
    a = rc.выполнить(db, команда="register", site_id="s1", поля=поля("s1.test"),
                     заголовки=з)
    b = rc.выполнить(db, команда="register", site_id="s1", поля=поля("s1.test"),
                     заголовки=з)
    assert a["idempotent_replay"] is False and b["idempotent_replay"] is True
    assert a["registry_version"] == b["registry_version"]
    assert db.execute("SELECT count(*) c FROM site").fetchone()["c"] == 1
    событий = db.execute("SELECT count(*) c FROM outbox WHERE site_id='s1'"
                         ).fetchone()["c"]
    assert событий == 1, f"событий {событий}, повтор создал второе"


def test_идемпотентность_переживает_перезапуск(db, tmp_path):
    з = dict(ЗАГ, **{"idempotency-key": "k-restart"})
    a = rc.выполнить(db, команда="register", site_id="s1", поля=поля("s1.test"),
                     заголовки=з)
    db.close()
    снова = rs.открыть(tmp_path / "t.sqlite3")
    b = rc.выполнить(снова, команда="register", site_id="s1",
                     поля=поля("s1.test"), заголовки=з)
    assert b["idempotent_replay"] is True
    assert b["registry_version"] == a["registry_version"]
    assert снова.execute("SELECT count(*) c FROM site").fetchone()["c"] == 1


def test_if_match_конфликт(db):
    rc.выполнить(db, команда="register", site_id="s1", поля=поля("s1.test"),
                 заголовки=dict(ЗАГ, **{"idempotency-key": "a"}))
    with pytest.raises(rs.ConflictError):
        rc.выполнить(db, команда="update", site_id="s1", поля={},
                     заголовки=dict(ЗАГ, **{"idempotency-key": "b"}),
                     expected_version=999)


# --- G06 сверка --------------------------------------------------------------

def test_сверка_находит_пропуск_и_лишнее(db):
    rc.выполнить(db, команда="register", site_id="s1",
                 поля=поля("s1.test", "production"),
                 заголовки=dict(ЗАГ, **{"idempotency-key": "1"}))
    rc.выполнить(db, команда="activate", site_id="s1", поля={},
                 заголовки=dict(ЗАГ, **{"idempotency-key": "2"}))
    р = rc.сверка(db, ожидаемые_домены={"s1.test", "s2.test"})
    виды = {f["kind"] for f in р["findings"]}
    assert р["verdict"] == "DIVERGENCE_FOUND"
    assert "MISSING" in виды
    р2 = rc.сверка(db, ожидаемые_домены={"s1.test"})
    assert р2["verdict"] == "SUCCESS" and not р2["findings"]


def test_сверка_находит_drift_по_манифесту(db):
    rc.выполнить(db, команда="register", site_id="s1",
                 поля=dict(поля("s1.test", "production"), build_id="B1"),
                 заголовки=dict(ЗАГ, **{"idempotency-key": "1"}))
    rc.выполнить(db, команда="activate", site_id="s1", поля={},
                 заголовки=dict(ЗАГ, **{"idempotency-key": "2"}))
    р = rc.сверка(db, ожидаемые_домены={"s1.test"},
                  манифесты={"s1": {"build_id": "B2"}})
    assert р["verdict"] == "DIVERGENCE_FOUND"
    assert any(f["kind"] == "DRIFT" for f in р["findings"])


def test_сверка_идемпотентна(db):
    rc.выполнить(db, команда="register", site_id="s1",
                 поля=поля("s1.test", "production"),
                 заголовки=dict(ЗАГ, **{"idempotency-key": "1"}))
    rc.выполнить(db, команда="activate", site_id="s1", поля={},
                 заголовки=dict(ЗАГ, **{"idempotency-key": "2"}))
    a = rc.сверка(db, ожидаемые_домены={"s1.test"})
    b = rc.сверка(db, ожидаемые_домены={"s1.test"})
    assert a["verdict"] == b["verdict"] == "SUCCESS"
    assert a["input_registry_version"] == b["input_registry_version"], \
        "сверка изменила реестр — она обязана быть только читающей"


def test_таймаут_не_даёт_success(db, monkeypatch):
    monkeypatch.setattr(rc, "ПРЕДЕЛ_СЕКУНД", -1)
    р = rc.сверка(db, ожидаемые_домены=set())
    assert р["verdict"] == "TIMEOUT" and р["timed_out"] is True
