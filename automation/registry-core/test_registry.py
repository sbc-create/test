"""Доказательства G05 и G07: outbox, порядок, replay, идемпотентность, N+1."""
import json, sqlite3, sys, uuid
from pathlib import Path
import pytest
sys.path.insert(0, "/srv/site-factory/registry-core")
import registry_store as rs

БОЕВАЯ = "/srv/site-factory/registry-core/registry.sqlite3"


@pytest.fixture()
def db(tmp_path):
    return rs.открыть(tmp_path / "t.sqlite3")


def зарегистрировать(с, sid, домен, **kw):
    поля = {"canonical_domain": домен, "family": "test",
            "environment": kw.pop("environment", "test"),
            "lifecycle_state": "DRAFT", "integration_refs": {}}
    поля.update(kw)
    return rs.применить(с, команда="register", site_id=sid, поля=поля,
                        actor="service:test")


# --- G05 outbox --------------------------------------------------------------

def test_запись_и_событие_в_одной_транзакции(db):
    """Откат одной транзакции обязан убрать и запись, и событие."""
    зарегистрировать(db, "s1", "s1.test")
    # Конфликт домена откатывает всё: вторая запись не появляется, и события
    # от неё в outbox тоже быть не должно.
    with pytest.raises(rs.ConflictError):
        зарегистрировать(db, "s2", "s1.test")
    assert db.execute("SELECT count(*) c FROM site").fetchone()["c"] == 1
    assert db.execute("SELECT count(*) c FROM outbox").fetchone()["c"] == 1
    assert db.execute("SELECT count(*) c FROM outbox WHERE site_id='s2'"
                      ).fetchone()["c"] == 0


def test_event_id_уникальны_и_версии_монотонны(db):
    зарегистрировать(db, "s1", "s1.test")
    for i in range(5):
        rs.применить(db, команда="update", site_id="s1",
                     поля={"observed_state": f"v{i}"}, actor="service:test")
    ев = rs.события(db, 0, 100)["items"]
    ids = [e["event_id"] for e in ев]
    assert len(ids) == len(set(ids)), "event_id повторились"
    агр = [e["aggregate_version"] for e in ев if e["site_id"] == "s1"]
    assert агр == sorted(агр) and агр == list(range(1, len(агр) + 1)), агр
    рег = [e["registry_version"] for e in ев]
    assert рег == sorted(рег) and len(set(рег)) == len(рег), "registry_version не монотонна"


def test_порядок_внутри_site_id(db):
    зарегистрировать(db, "a", "a.test"); зарегистрировать(db, "b", "b.test")
    for i in range(3):
        rs.применить(db, команда="update", site_id="a", поля={"observed_state": str(i)},
                     actor="service:test")
        rs.применить(db, команда="update", site_id="b", поля={"observed_state": str(i)},
                     actor="service:test")
    для_a = [e["aggregate_version"] for e in rs.события(db, 0, 100)["items"]
             if e["site_id"] == "a"]
    assert для_a == sorted(для_a), "порядок внутри site_id нарушен"


def test_replay_по_курсору_без_потерь_и_дублей(db):
    зарегистрировать(db, "s1", "s1.test")
    for i in range(9):
        rs.применить(db, команда="update", site_id="s1", поля={"observed_state": str(i)},
                     actor="service:test")
    всего = rs.события(db, 0, 1000)["items"]
    собрано, курсор = [], 0
    while True:
        порция = rs.события(db, курсор, 3)
        if not порция["items"]:
            break
        собрано += порция["items"]
        курсор = порция["next_cursor"]
    assert len(собрано) == len(всего), f"{len(собрано)} против {len(всего)}"
    assert [e["event_id"] for e in собрано] == [e["event_id"] for e in всего]
    assert len({e["event_id"] for e in собрано}) == len(собрано), "дубли при replay"


def test_replay_переживает_перезапуск(db, tmp_path):
    """Курсор durable: новое соединение видит те же события в том же порядке."""
    зарегистрировать(db, "s1", "s1.test")
    путь = tmp_path / "t.sqlite3"
    до = [e["event_id"] for e in rs.события(db, 0, 100)["items"]]
    db.close()
    снова = rs.открыть(путь)
    после = [e["event_id"] for e in rs.события(снова, 0, 100)["items"]]
    assert до == после, "после перезапуска поток событий изменился"


# --- G04 конкурентность ------------------------------------------------------

def test_optimistic_concurrency(db):
    зарегистрировать(db, "s1", "s1.test")
    версия = rs.события(db, 0, 100)["registry_version"]
    rs.применить(db, команда="update", site_id="s1", поля={"observed_state": "x"},
                 actor="service:test", expected_version=версия)
    with pytest.raises(rs.ConflictError):
        rs.применить(db, команда="update", site_id="s1", поля={"observed_state": "y"},
                     actor="service:test", expected_version=версия)


def test_домен_и_алиас_не_пересекаются(db):
    зарегистрировать(db, "s1", "s1.test")
    rs.применить(db, команда="update", site_id="s1", поля={}, actor="service:test",
                 aliases=["alias1.test"])
    with pytest.raises(rs.ConflictError):
        зарегистрировать(db, "s2", "alias1.test")


# --- G07 N+1 -----------------------------------------------------------------

def test_n_plus_one_без_правки_кода(db):
    """Синтетический сайт добавляется командой, не кодом и не списком."""
    до = rs.снимок(db)["count"]
    sid = "synthetic-" + uuid.uuid4().hex[:8]
    р = зарегистрировать(db, sid, f"{sid}.test", environment="test")
    assert р["aggregate_version"] == 1
    сколько = len([e for e in rs.события(db, 0, 1000)["items"]
                   if e["site_id"] == sid and e["event_type"] == "site.registered.v1"])
    assert сколько == 1, f"событий регистрации {сколько}, должно быть одно"
    rs.применить(db, команда="activate", site_id=sid, поля={}, actor="service:test")
    rs.применить(db, команда="update", site_id=sid, поля={"observed_state": "up"},
                 actor="service:test")
    rs.применить(db, команда="retire", site_id=sid, поля={}, actor="service:test")
    жиз = [e["event_type"] for e in rs.события(db, 0, 1000)["items"]
           if e["site_id"] == sid]
    assert жиз == ["site.registered.v1", "site.activated.v1",
                   "site.updated.v1", "site.retired.v1"], жиз
    # Синтетический сайт не имеет права попасть в production snapshot.
    сн = rs.снимок(db)
    assert сн["count"] == до
    assert sid not in [s["site_id"] for s in сн["sites"]]


# --- боевое хранилище --------------------------------------------------------

def test_боевой_снимок_девять_производственных():
    if not Path(БОЕВАЯ).exists():
        pytest.skip("хранилище не создано")
    с = sqlite3.connect(БОЕВАЯ); с.row_factory = sqlite3.Row
    сн = rs.снимок(с)
    assert сн["count"] == 9, f"ACTIVE production {сн['count']}, ожидалось 9"
    домены = sorted(s["canonical_domain"] for s in сн["sites"])
    assert домены == sorted([
        "1lordserials1.online", "animedia.icu", "animedia.space",
        "lordfilm47.space", "lordserial33.biz", "yummyani.biz",
        "yummyani.org", "yummyani.site", "zonafilm.space"]), домены
    # demo-books и любые fixtures в production-снимок не попадают.
    assert "demo-books.invalid" not in домены
    for s in сн["sites"]:
        for поле in ("site_id", "canonical_domain", "family", "environment",
                     "lifecycle_state", "owner_ref", "template_id",
                     "template_version", "build_id", "release_id",
                     "desired_state", "integration_refs",
                     "monitoring_profile_ref", "backup_policy_ref",
                     "content_profile_ref", "seo_profile_ref",
                     "aggregate_version", "created_at", "updated_at"):
            assert поле in s, f"{s['site_id']}: нет поля {поле}"


def test_боевые_site_id_сохранены():
    if not Path(БОЕВАЯ).exists():
        pytest.skip("хранилище не создано")
    с = sqlite3.connect(БОЕВАЯ); с.row_factory = sqlite3.Row
    есть = {р["site_id"] for р in с.execute("SELECT site_id FROM site")}
    for sid in ("lords-01", "lords-02", "lords-03",
                "yummyani-biz", "yummyani-org", "yummyani-site"):
        assert sid in есть, f"утрачен исходный site_id {sid}"
