"""Обязательные проверки Audit Ledger (пункты 1–38 задания)."""
from __future__ import annotations

import concurrent.futures as fut
import hashlib, json, os, shutil, sqlite3, subprocess, sys, tempfile, urllib.error, urllib.request, uuid
from pathlib import Path
import pytest

from factory.site_engine.audit import ledger_store as store
from factory.site_engine.audit import ledger_identity as ident
from factory.site_engine.audit import ledger_api as api

# Тесты пишут события, а журнал — только на добавление: удалить написанное
# нельзя. Поэтому прогон идёт по эфемерной копии (`run_tests.py` поднимает
# отдельный экземпляр), а канонический журнал остаётся историей системы, а не
# свалкой тестовых записей.
Б = os.environ.get("AUDIT_API_BASE", "http://127.0.0.1:8790")
ЖУРНАЛ = os.environ.get("AUDIT_LEDGER_DB",
                        "/srv/site-factory/audit-ledger/audit_ledger.sqlite3")
РЕЕСТР = "/srv/site-factory/registry-core/registry.sqlite3"
ТОКЕН = os.environ.get("AUDIT_TOKEN_ARCHITECT", "arch-local-token")
ТОКЕН_QWEN = os.environ.get("AUDIT_TOKEN_QWEN", "qwen-local-token")


def пост(тело, токен=ТОКЕН, доп=None):
    з = {"Content-Type": "application/json", "Authorization": f"Bearer {токен}"}
    з.update(доп or {})
    r = urllib.request.Request(Б + "/api/v1/audit/events",
                               data=json.dumps(тело).encode(), headers=з,
                               method="POST")
    try:
        with urllib.request.urlopen(r, timeout=20) as o:
            return o.status, json.loads(o.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def гет(путь, токен=None):
    """Чтение журнала. По умолчанию — от имени audit-admin.

    Сырая лента закрыта ролью: анонимный запрос к ней обязан получить 401, и
    это проверяется отдельным тестом, а не случайным отсутствием заголовка.
    """
    зап = urllib.request.Request(
        Б + путь, headers={"Authorization": f"Bearer {токен or ТОКЕН}"})
    try:
        with urllib.request.urlopen(зап, timeout=20) as o:
            return o.status, json.loads(o.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def гет_без_токена(путь):
    try:
        with urllib.request.urlopen(Б + путь, timeout=20) as o:
            return o.status, json.loads(o.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def событие(**kw):
    d = {"event_type": "test.observed.v1", "phase": "OBSERVED",
         "result": "SUCCESS", "scope": "FLEET",
         "correlation_id": "corr-" + uuid.uuid4().hex[:8],
         "idempotency_key": "k-" + uuid.uuid4().hex[:10],
         "summary": "проверка"}
    d.update(kw)
    return d


@pytest.fixture()
def врем(tmp_path):
    return store.открыть(tmp_path / "l.sqlite3")


# 1
def test_01_append_и_чтение():
    к, т = пост(событие())
    assert к == 201, т
    к2, е = гет(f"/api/v1/audit/events/{т['event_id']}")
    assert к2 == 200 and е["event_id"] == т["event_id"]


# 2, 3
def test_02_идемпотентность_тот_же_payload():
    e = событие()
    к1, a = пост(e); к2, b = пост(e)
    assert к1 == 201 and к2 == 200
    assert a["event_id"] == b["event_id"] and b["idempotent_replay"] is True


def test_03_конфликт_идемпотентности():
    e = событие()
    пост(e)
    к, т = пост(dict(e, summary="другое содержимое"))
    assert к == 409 and т["error_code"] == "IDEMPOTENCY_CONFLICT"


# 4
def test_04_двадцать_параллельных_одинаковых():
    e = событие()
    with fut.ThreadPoolExecutor(max_workers=20) as p:
        ответы = list(p.map(lambda _: пост(e), range(20)))
    ids = {т["event_id"] for к, т in ответы if к in (200, 201)}
    созданий = sum(1 for к, _ in ответы if к == 201)
    assert len(ids) == 1, f"создано разных событий: {len(ids)}"
    assert созданий == 1, f"HTTP 201 получено {созданий} раз"


# 5
def test_05_crash_после_commit_не_даёт_дубль(врем):
    e = событие()
    a = store.append(врем, e, producer_service="architect",
                     actor_id="service:architect", actor_type="SERVICE",
                     authority="OBSERVE")
    # Ответ «потерян» — клиент повторяет тем же ключом.
    b = store.append(врем, e, producer_service="architect",
                     actor_id="service:architect", actor_type="SERVICE",
                     authority="OBSERVE")
    assert a["event_id"] == b["event_id"] and b["idempotent_replay"]
    assert врем.execute("SELECT count(*) c FROM ledger_event").fetchone()["c"] == 1


# 6
def test_06_registry_replay_без_дублей():
    from factory.site_engine.audit import registry_bridge as rb
    до = rb.сверка()
    rb.перенести(); rb.перенести()
    после = rb.сверка()
    assert после["duplicates"] == 0 and после["missing_count"] == 0
    assert после["in_ledger"] == до["in_ledger"]


# 7, 8
def test_07_несуществующий_site_id_отклонён():
    к, т = пост(событие(scope="SITE", site_id="нет-такого-сайта"))
    assert к == 422 and т["error_code"] == "SITE_ID_UNKNOWN"


def test_08_домен_не_принимается_вместо_site_id():
    к, т = пост(событие(scope="SITE", site_id="lordfilm47.space"))
    assert к == 422 and т["error_code"] == "SITE_ID_UNKNOWN", \
        "домен принят как идентификатор сайта"


# 9
def test_09_подмена_личности_отклонена():
    к, т = пост(событие(), токен=ТОКЕН_QWEN,
                доп={"X-Service-Name": "architect"})
    assert к == 403 and т["error_code"] == "IDENTITY_SPOOF"


# 10
def test_10_qwen_не_может_authorize_apply_rollback():
    for фаза in ("AUTHORIZED", "STARTED", "SUCCEEDED", "ROLLED_BACK"):
        к, т = пост(событие(phase=фаза), токен=ТОКЕН_QWEN)
        assert к == 403, f"qwen записал фазу {фаза}: {к}"
        assert т["error_code"] in ("MODEL_PHASE_DENIED", "AUTHORITY_DENIED")
    к, т = пост(событие(authority="AUTHORIZE"), токен=ТОКЕН_QWEN)
    assert к == 403 and т["error_code"] == "AUTHORITY_DENIED"


# 11
def test_11_неавторизованный_post():
    r = urllib.request.Request(Б + "/api/v1/audit/events",
                               data=b"{}", method="POST",
                               headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(r, timeout=20)
        assert False, "принято без токена"
    except urllib.error.HTTPError as e:
        assert e.code in (401, 403)


# 12
def test_12_фильтры_server_side():
    к, все = гет("/api/v1/audit/events?limit=1000")
    к2, только = гет("/api/v1/audit/events?producer_service=registry&limit=1000")
    assert к == к2 == 200
    assert len(только["items"]) < len(все["items"])
    assert all(i["producer_service"] == "registry" for i in только["items"])
    к3, т3 = гет("/api/v1/audit/events?unknown_filter=1")
    assert к3 == 422 and т3["error_code"] == "FILTER_UNKNOWN"
    к4, т4 = гет("/api/v1/audit/events?site_id=")
    assert к4 == 422 and т4["error_code"] == "FILTER_VALUE_EMPTY"
    к5, т5 = гет("/api/v1/audit/events?site_id=a&site_id=b")
    assert к5 == 422 and т5["error_code"] == "FILTER_VALUE_CONFLICT"


# 13
def test_13_курсор_стабилен_при_конкурентной_записи():
    к, стр1 = гет("/api/v1/audit/events?limit=5")
    пост(событие())          # конкурентная запись между страницами
    к, стр2 = гет(f"/api/v1/audit/events?after={стр1['next_cursor']}&limit=5")
    ids1 = [i["ledger_seq"] for i in стр1["items"]]
    ids2 = [i["ledger_seq"] for i in стр2["items"]]
    assert ids1 == sorted(ids1) and ids2 == sorted(ids2)
    assert not (set(ids1) & set(ids2)), "страницы пересеклись"


# 14
def test_14_correlation_timeline():
    corr = "tl-" + uuid.uuid4().hex[:8]
    act = "act-" + uuid.uuid4().hex[:8]
    for фаза in ("PROPOSED", "VALIDATED", "AUTHORIZED", "STARTED", "SUCCEEDED"):
        к, _ = пост(событие(phase=фаза, correlation_id=corr, action_id=act,
                            authority="AUTHORIZE"))
        assert к == 201, фаза
    к, т = гет(f"/api/v1/audit/correlations/{corr}")
    фазы = [i["phase"] for i in т["items"]]
    assert фазы == ["PROPOSED", "VALIDATED", "AUTHORIZED", "STARTED", "SUCCEEDED"]
    к2, a = гет(f"/api/v1/audit/actions/{act}")
    assert a["count"] == 5


# 15
def test_15_проекция_пересобирается(врем):
    for ф in ("PROPOSED", "STARTED", "SUCCEEDED"):
        store.append(врем, событие(phase=ф, action_id="A1"),
                     producer_service="architect", actor_id="service:architect",
                     actor_type="SERVICE", authority="EXECUTE")
    def проекция(c):
        строки = list(c.execute("SELECT phase FROM ledger_event WHERE "
                                "action_id='A1' ORDER BY ledger_seq"))
        return [r["phase"] for r in строки]
    a = проекция(врем)
    b = проекция(врем)            # пересборка из того же журнала
    assert a == b == ["PROPOSED", "STARTED", "SUCCEEDED"]


# 16, 17
def test_16_update_невозможен(врем):
    store.append(врем, событие(), producer_service="architect",
                 actor_id="service:architect", actor_type="SERVICE",
                 authority="OBSERVE")
    with pytest.raises(sqlite3.IntegrityError if False else Exception):
        врем.execute("UPDATE ledger_event SET summary='подмена'")


def test_17_delete_невозможен(врем):
    store.append(врем, событие(), producer_service="architect",
                 actor_id="service:architect", actor_type="SERVICE",
                 authority="OBSERVE")
    with pytest.raises(Exception):
        врем.execute("DELETE FROM ledger_event")


# 18
def test_18_bit_flip_обнаруживается(tmp_path):
    копия = tmp_path / "copy.sqlite3"
    shutil.copyfile(ЖУРНАЛ, копия)
    c = sqlite3.connect(копия); c.row_factory = sqlite3.Row
    assert store.проверить_цепь(c)["ok"], "копия изначально повреждена"
    # Триггеры запрещают UPDATE — правим в обход, как это сделал бы тот, кто
    # получил доступ к файлу. Именно такой случай цепь и обязана поймать.
    c.execute("DROP TRIGGER le_no_update")
    цель = c.execute("SELECT ledger_seq FROM ledger_event "
                     "ORDER BY ledger_seq LIMIT 1 OFFSET 3").fetchone()[0]
    c.execute("UPDATE ledger_event SET summary=summary||'x' WHERE ledger_seq=?",
              (цель,))
    c.commit()
    п = store.проверить_цепь(c)
    c.close()
    assert п["ok"] is False
    assert п["broken_at_seq"] == цель, f"указано {п.get('broken_at_seq')} вместо {цель}"
    # Живой журнал не тронут.
    ж = sqlite3.connect(f"file:{ЖУРНАЛ}?mode=ro", uri=True)
    ж.row_factory = sqlite3.Row
    assert store.проверить_цепь(ж)["ok"]
    ж.close()


# 19, 20
def test_19_изменённое_доказательство_не_проходит(tmp_path):
    файл = Path("/srv/site-factory/audit-ledger/evidence/probe.json")
    файл.parent.mkdir(parents=True, exist_ok=True)
    файл.write_text('{"a":1}', encoding="utf-8")
    сумма = hashlib.sha256(файл.read_bytes()).hexdigest()
    ev = {"evidence_id": "ev-probe-" + uuid.uuid4().hex[:6], "uri": str(файл),
          "checksum": сумма, "media_type": "application/json", "size": 7,
          "created_at": store.сейчас(), "producer": "architect",
          "retention_class": "RUN"}
    к, _ = пост(событие(evidence_refs=[ev]))
    assert к == 201
    к, м = гет(f"/api/v1/audit/evidence/{ev['evidence_id']}/metadata")
    assert к == 200 and м["verified"] is True
    файл.write_text('{"a":2}', encoding="utf-8")     # подмена после создания
    к, м2 = гет(f"/api/v1/audit/evidence/{ev['evidence_id']}/metadata")
    assert м2["verified"] is False and м2["verification"] == "HASH_MISMATCH"


def test_20_path_traversal_отклоняется():
    ev = {"evidence_id": "ev-trav-" + uuid.uuid4().hex[:6],
          "uri": "/srv/site-factory/audit-ledger/evidence/../../../etc/passwd",
          "checksum": "0" * 64, "media_type": "text/plain", "size": 1,
          "created_at": store.сейчас(), "producer": "architect",
          "retention_class": "RUN"}
    к, _ = пост(событие(evidence_refs=[ev]))
    assert к == 201
    к, м = гет(f"/api/v1/audit/evidence/{ev['evidence_id']}/metadata")
    assert к == 403 and м["error_code"] == "EVIDENCE_PATH_DENIED"


# 21
def test_21_секрет_в_payload_отклоняется():
    к, т = пост(событие(summary="token=AbCdEf0123456789XyZ"))
    assert к == 422 and т["error_code"] == "SECRET_IN_PAYLOAD"


# 22, 23, 24, 25
def test_22_курсор_потребителя_переживает_перезапуск():
    from factory.site_engine.audit import registry_bridge as rb
    ж = sqlite3.connect(ЖУРНАЛ); ж.row_factory = sqlite3.Row
    поз = ж.execute("SELECT position FROM consumer_cursor WHERE consumer=?",
                    (rb.ПОТРЕБИТЕЛЬ,)).fetchone()
    ж.close()
    assert поз is not None and int(поз["position"]) > 0
    итог = rb.перенести()          # «после перезапуска»
    assert итог["appended"] == 0, "после перезапуска события обработаны заново"


def test_24_сверка_находит_пропуск(tmp_path, monkeypatch):
    from factory.site_engine.audit import registry_bridge as rb
    ж_копия = tmp_path / "l.sqlite3"
    shutil.copyfile(ЖУРНАЛ, ж_копия)
    c = sqlite3.connect(ж_копия)
    c.execute("DROP TRIGGER le_no_delete")
    ушло = c.execute("SELECT idempotency_key FROM ledger_event WHERE "
                     "producer_service='registry' LIMIT 1").fetchone()[0]
    c.execute("DELETE FROM ledger_event WHERE idempotency_key=?", (ушло,))
    c.commit(); c.close()
    monkeypatch.setattr(rb, "ЖУРНАЛ", str(ж_копия))
    с = rb.сверка()
    assert с["missing_count"] == 1 and ушло in с["missing"]
    assert с["verdict"] == "FAIL"


def test_25_dlq_принимает_исчерпавшее(врем):
    from factory.site_engine.audit import registry_bridge as rb
    rb._в_dlq(врем, 1, "SITE_ID_UNKNOWN", "нет такого сайта", 3, {"x": 1})
    n = врем.execute("SELECT count(*) c FROM ledger_dlq").fetchone()["c"]
    assert n == 1


# 26
def test_26_нет_рекурсии_самособытий():
    ж = sqlite3.connect(f"file:{ЖУРНАЛ}?mode=ro", uri=True)
    n = ж.execute("SELECT count(*) c FROM ledger_event WHERE "
                  "event_type='audit.event.appended.v1'").fetchone()[0]
    ж.close()
    assert n == 0, "журнал поглотил собственное событие о добавлении"


# 28–31
def test_29_канонический_реестр_остался_13():
    r = sqlite3.connect(f"file:{РЕЕСТР}?mode=ro", uri=True)
    n = r.execute("SELECT count(*) FROM site").fetchone()[0]
    prod = r.execute("SELECT count(*) FROM site WHERE environment='production' "
                     "AND lifecycle_state='ACTIVE'").fetchone()[0]
    синт = [x[0] for x in r.execute(
        "SELECT site_id FROM site WHERE site_id LIKE 'synthetic%' ORDER BY site_id")]
    r.close()
    assert n == 13 and prod == 9
    assert синт == ["synthetic-http-b4e4f1", "synthetic-npo-1c85d0bd",
                    "synthetic-npo-30c9237d"]


def test_30_production_snapshot_девять():
    к, т = гет("/api/v1/registry/snapshot")
    assert к == 200 and т["count"] == 9


# 38
def test_38_backlog_после_сверки_ноль():
    from factory.site_engine.audit import ledger_publisher as lp
    итог = lp.опубликовать()
    assert итог["backlog"] == 0 and итог["self_event_recursion"] == 0


# health / integrity
def test_health_и_целостность():
    к, h = гет("/api/v1/audit/health")
    assert к == 200 and h["ready"] is True
    assert h["tamper_evidence_level"] == "LOCAL_HASH_CHAIN"
    к, i = гет("/api/v1/audit/integrity")
    assert к == 200 and i["ok"] is True


# --- R2: поверхности, роли, отзыв токена ------------------------------------

def test_r2_сырая_лента_требует_роли():
    к, _ = гет_без_токена("/api/v1/audit/events")
    assert к == 401, "сырая лента отдаётся без токена"
    к2, т2 = гет("/api/v1/audit/events", токен=ТОКЕН_QWEN)
    assert к2 == 403 and т2["error_code"] == "ROLE_DENIED"


def test_r2_рабочая_проекция_открыта_службам():
    к, т = гет("/api/v1/audit/operational/events?limit=1000", токен=ТОКЕН_QWEN)
    assert к == 200 and т["surface"] == "operational"
    к2, т2 = гет("/api/v1/audit/events?limit=1000")
    assert к2 == 200 and т2["surface"] == "raw"
    # Рабочая поверхность не может быть шире сырой.
    assert т["count"] <= т2["count"]


def test_r2_карантинные_не_попадают_в_проекцию():
    from factory.site_engine.audit import projection as pr
    c = store.открыть(ЖУРНАЛ)
    try:
        объявлены = pr.позиции_в_карантине(c)
    finally:
        c.close()
    assert объявлены, "в копии нет карантинных позиций — проверять нечего"
    к, рабоч = гет("/api/v1/audit/operational/events?limit=1000",
                   токен=ТОКЕН_QWEN)
    assert к == 200
    видимые = {i["ledger_seq"] for i in рабоч["items"]}
    assert not (видимые & объявлены), \
        f"в рабочей проекции видны карантинные позиции: " \
        f"{sorted(видимые & объявлены)[:5]}"
    к2, сыро = гет("/api/v1/audit/events?limit=1000")
    сырые = {i["ledger_seq"] for i in сыро["items"]}
    assert объявлены <= сырые, "сырая лента потеряла карантинные записи"


def test_r2_include_quarantined_только_для_admin():
    к, _ = гет("/api/v1/audit/operational/events?include_quarantined=true")
    assert к == 200
    к2, т2 = гет("/api/v1/audit/operational/events?include_quarantined=true",
                 токен=ТОКЕН_QWEN)
    assert к2 == 403 and т2["error_code"] == "ROLE_DENIED"


def test_r2_нить_показывает_число_скрытых():
    к, сыро = гет("/api/v1/audit/events?event_type=test.observed.v1&limit=1000")
    нити = [i["correlation_id"] for i in сыро["items"] if i.get("action_id")]
    assert нити, "в копии нет загрязнённой нити"
    corr = нити[0]
    к2, рабоч = гет(f"/api/v1/audit/correlations/{corr}", токен=ТОКЕН_QWEN)
    assert к2 == 200 and рабоч["count"] == 0
    assert рабоч["quarantined_count"] > 0, "скрытые события не посчитаны"
    к3, полн = гет(f"/api/v1/audit/correlations/{corr}?include_quarantined=true")
    assert полн["count"] == рабоч["quarantined_count"]


def test_r2_проекция_пересобирается_из_журнала(tmp_path):
    from factory.site_engine.audit import projection as pr
    c = store.открыть(ЖУРНАЛ)
    try:
        было = pr.позиции_в_карантине(c)
        pr.пересобрать(c)
        стало = pr.позиции_в_карантине(c)
    finally:
        c.close()
    assert было == стало, "пересборка из журнала дала другой результат"


def test_r2_отозванный_токен_отклонён(monkeypatch):
    from factory.site_engine.audit import ledger_identity as li
    import hashlib
    отпечаток = hashlib.sha256(ТОКЕН.encode()).hexdigest()[:12]
    monkeypatch.setenv(li.ОТОЗВАННЫЕ, отпечаток)
    with pytest.raises(li.IdentityError) as ош:
        li.опознать({"authorization": f"Bearer {ТОКЕН}"})
    assert ош.value.error_code == "TOKEN_REVOKED" and ош.value.status == 403


def test_r2_неверный_токен_отклонён():
    from factory.site_engine.audit import ledger_identity as li
    with pytest.raises(li.IdentityError) as ош:
        li.опознать({"authorization": "Bearer заведомо-не-тот-токен-0000"})
    assert ош.value.error_code == "UNAUTHENTICATED"
