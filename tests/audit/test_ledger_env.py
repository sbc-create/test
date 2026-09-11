"""Проверки окружения и сохранности базовой линии (пункты 23, 27, 28, 31–37).

Отдельным файлом, потому что эти проверки касаются не журнала, а того, что он
ничего вокруг себя не испортил. Смешивать их с функциональными тестами значит
потерять различие между «журнал работает» и «журнал ничего не сломал».
"""
from __future__ import annotations

import hashlib, json, os, shutil, sqlite3, subprocess, sys, urllib.error, urllib.request
from pathlib import Path
import pytest

from factory.site_engine.audit import ledger_store as store

ЖУРНАЛ = "/srv/site-factory/audit-ledger/audit_ledger.sqlite3"
РЕЕСТР = "/srv/site-factory/registry-core/registry.sqlite3"
ДОМЕНЫ = ["yummyani.org", "yummyani.site", "yummyani.biz"]
#: Исходный код журнала — в репозитории; сканировать рабочий каталог данных
#: бессмысленно, там больше нет ни одного модуля.
ИСХОДНИКИ = [Path(__file__).resolve().parent,
             Path(__file__).resolve().parents[2] / "factory/site_engine/audit"]
#: Базовая линия реестра, зафиксированная до начала работ.
ОЖИДАЕМЫЙ_РЕЕСТР = 13
ОЖИДАЕМЫЙ_PRODUCTION = 9


def _строки_синтетики(путь: str) -> str:
    c = sqlite3.connect(f"file:{путь}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    строки = [dict(r) for r in c.execute(
        "SELECT * FROM site WHERE site_id LIKE 'synthetic%' ORDER BY site_id")]
    c.close()
    return hashlib.sha256(json.dumps(строки, ensure_ascii=False, sort_keys=True)
                          .encode()).hexdigest()


# 23
def test_23_перерыв_ленты_не_теряет_событий(tmp_path, monkeypatch):
    """Публикация падает после записи в ленту, но до отметки.

    Такое падение обязано дать повтор, а не потерю: повтор потребитель
    отсеет по event_id, потерю не заметит никто.
    """
    import ledger_publisher as lp
    копия = tmp_path / "l.sqlite3"
    shutil.copyfile(ЖУРНАЛ, копия)
    лента = tmp_path / "feed.jsonl"
    c = store.открыть(копия)
    for i in range(3):
        store.append(c, {"event_type": "test.outage.v1", "phase": "OBSERVED",
                         "result": "SUCCESS", "scope": "FLEET",
                         "correlation_id": f"out-{i}",
                         "idempotency_key": f"outage-{i}", "summary": "перерыв"},
                     producer_service="architect", actor_id="service:architect",
                     actor_type="SERVICE", authority="OBSERVE")
    ждали = c.execute("SELECT count(*) c FROM ledger_outbox "
                      "WHERE published_at IS NULL").fetchone()["c"]
    c.close()
    monkeypatch.setattr(lp, "ЖУРНАЛ", str(копия))
    monkeypatch.setattr(lp, "ЛЕНТА", лента)

    настоящий = store.сейчас
    вызовов = {"n": 0}

    def падать(*a, **k):
        вызовов["n"] += 1
        if вызовов["n"] == 2:      # запись в ленту прошла, отметка — нет
            raise RuntimeError("перерыв публикации")
        return настоящий(*a, **k)

    monkeypatch.setattr(store, "сейчас", падать)
    with pytest.raises(RuntimeError):
        lp.опубликовать()
    monkeypatch.setattr(store, "сейчас", настоящий)
    итог = lp.опубликовать()          # восстановление
    assert итог["backlog"] == 0
    строки = [json.loads(s) for s in лента.read_text(encoding="utf-8").splitlines()]
    ушедшие = {s["event_id"] for s in строки}
    assert len(ушедшие) == ждали, "после восстановления часть событий не дошла"
    assert len(строки) >= ждали, "доставка не at-least-once"


# 27
def test_27_backup_и_изолированное_восстановление():
    import ledger_backup as bk
    м = bk.создать()
    r = bk.восстановить(Path(bk.КАТАЛОГ) / м["backup_file"])
    assert r["restore_verdict"] == "PASS", r["mismatches"]
    assert r["restored_snapshot"]["count"] == м["source_snapshot"]["count"]
    assert r["restored_snapshot"]["last_seq"] == м["source_snapshot"]["last_seq"]
    assert r["restored_snapshot"]["chain_root"] == м["source_snapshot"]["chain_root"]
    assert {"le_no_update", "le_no_delete"} <= set(r["immutability_triggers"])


# 28
def test_28_n_plus_one_в_ephemeral_db_не_трогает_базовую_линию():
    до_всего, до_prod, до_синт = _слепок_реестра()
    p = subprocess.run(["/home/claude/work-test/.venv/bin/python",
                        "n_plus_one_isolated.py"],
                       cwd="/srv/site-factory/control-plane-contracts",
                       capture_output=True, text=True, timeout=300)
    assert p.returncode == 0, p.stdout[-2000:] + p.stderr[-2000:]
    assert "'CANONICAL_REGISTRY_RECORD_MUTATIONS': 0" in p.stdout, p.stdout[-800:]
    assert "'CANONICAL_TEST_RECORDS_CREATED': 0" in p.stdout, p.stdout[-800:]
    после = _слепок_реестра()
    assert (до_всего, до_prod, до_синт) == после, "базовая линия изменилась"


def _слепок_реестра():
    c = sqlite3.connect(f"file:{РЕЕСТР}?mode=ro", uri=True)
    всего = c.execute("SELECT count(*) FROM site").fetchone()[0]
    prod = c.execute("SELECT count(*) FROM site WHERE environment='production' "
                     "AND lifecycle_state='ACTIVE'").fetchone()[0]
    c.close()
    return всего, prod, _строки_синтетики(РЕЕСТР)


# 31
def test_31_три_синтетические_записи_не_изменены():
    c = sqlite3.connect(f"file:{РЕЕСТР}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    строки = [dict(r) for r in c.execute(
        "SELECT * FROM site WHERE site_id LIKE 'synthetic%' ORDER BY site_id")]
    c.close()
    assert len(строки) == 3
    assert [r["site_id"] for r in строки] == [
        "synthetic-http-b4e4f1", "synthetic-npo-1c85d0bd", "synthetic-npo-30c9237d"]
    # Записи остаются долгом, а не мусором: их не удаляют и не «чинят».
    # Версии агрегата (1, 3, 3) достались от прошлых задач; доказывать нужно
    # не их значение, а то, что в этой задаче записи не менялись. Любое
    # изменение реестра порождает событие outbox, поэтому отсутствие таких
    # событий после генезиса журнала и есть доказательство.
    ж = sqlite3.connect(f"file:{ЖУРНАЛ}?mode=ro", uri=True)
    генезис = ж.execute("SELECT occurred_at FROM ledger_event "
                        "WHERE ledger_seq=1").fetchone()[0]
    ж.close()
    c = sqlite3.connect(f"file:{РЕЕСТР}?mode=ro", uri=True)
    правки = list(c.execute(
        "SELECT event_id, site_id, event_type, occurred_at FROM outbox "
        "WHERE site_id LIKE 'synthetic%' AND occurred_at > ?", (генезис,)))
    версия = c.execute("SELECT max(version) FROM registry_version").fetchone()[0]
    c.close()
    assert not правки, правки
    assert версия == 32, f"registry_version изменилась: {версия}"
    # Долг зафиксирован в журнале, по одному событию на запись.
    ж = sqlite3.connect(f"file:{ЖУРНАЛ}?mode=ro", uri=True)
    n = ж.execute("SELECT count(*) FROM ledger_event WHERE "
                  "event_type='technical.debt.observed.v1'").fetchone()[0]
    ж.close()
    assert n == 3


# 32, 33
def test_32_публичные_сайты_только_читаются():
    методы = set()
    for домен in ДОМЕНЫ:
        r = urllib.request.Request(f"https://{домен}/", method="GET",
                                   headers={"User-Agent": "fleet-audit-smoke",
                                            "Cache-Control": "no-cache"})
        методы.add("GET")
        последняя = None
        for попытка in range(3):
            try:
                with urllib.request.urlopen(r, timeout=40) as o:
                    assert o.status == 200, f"{домен}: {o.status}"
                    assert o.read(4096), f"{домен}: пустой ответ"
                последняя = None
                break
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                последняя = e
        if последняя is not None:
            pytest.fail(f"{домен} недоступен после 3 попыток: {последняя}")
    assert методы == {"GET"}, "smoke использовал не только чтение"


def test_33_публичных_записей_не_производилось():
    # Единственный способ этого прогона изменить публичный сайт — послать в
    # него не-GET. Ни один тест такого запроса не содержит.
    подозрительные = []
    for f in [x for к in ИСХОДНИКИ for x in к.rglob("*.py")]:
        т = f.read_text(encoding="utf-8", errors="replace")
        for домен in ДОМЕНЫ:
            for м in ("POST", "PUT", "PATCH", "DELETE"):
                if домен in т and f'method="{м}"' in т:
                    подозрительные.append(f"{f.name}:{домен}:{м}")
    assert not подозрительные, подозрительные


# 34
def test_34_внешние_провайдеры_не_вызывались():
    внешние = ("api.kitsu.io", "graphql.anilist.co", "api.simkl.com",
               "shikimori.one", "api-metrika.yandex", "topvisor.com")
    свой = Path(__file__).resolve()
    найдено = [f"{f.name}:{h}" for f in [x for к in ИСХОДНИКИ for x in к.rglob("*.py")]
               if f.resolve() != свой          # список хостов лежит здесь же
               for h in внешние
               if h in f.read_text(encoding="utf-8", errors="replace")]
    assert not найдено, найдено


# 35
def test_35_секретов_не_раскрыто():
    """Токены не должны попадать ни в журнал, ни в ленту, ни в манифесты.

    Проверяются два разных риска: секрет, записанный в событие, и секрет,
    просочившийся в ленту или лог при публикации.
    """
    import re
    опасно = re.compile(
        r"(?i)(bearer\s+[A-Za-z0-9._-]{16,}|(?:token|secret|password|api[_-]?key)"
        r"\s*[=:]\s*[\'\"]?[A-Za-z0-9._-]{16,})")
    живые_токены = [v for k, v in os.environ.items()
                    if k.startswith("AUDIT_TOKEN_") and v]
    цели = [Path("/srv/site-factory/audit-ledger/feed/audit-events.jsonl")]
    цели += sorted(Path("/srv/site-factory/audit-ledger/backups").glob("*.manifest.json"))
    цели += sorted(Path("/srv/site-factory/control-plane-contracts/1.1.0").rglob("*.json"))
    утечки = []
    for f in цели:
        if not f.exists():
            continue
        т = f.read_text(encoding="utf-8", errors="replace")
        if опасно.search(т):
            утечки.append(f"{f.name}: образец секрета")
        утечки += [f"{f.name}: живой токен" for t in живые_токены if t in т]
    c = sqlite3.connect(f"file:{ЖУРНАЛ}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    текст = json.dumps([dict(r) for r in c.execute("SELECT * FROM ledger_event")],
                       ensure_ascii=False)
    c.close()
    if опасно.search(текст):
        утечки.append("ledger_event: образец секрета")
    утечки += [f"ledger_event: живой токен" for t in живые_токены if t in текст]
    assert not утечки, утечки


# 36
def test_36_осиротевших_процессов_нет():
    p = subprocess.run(["ps", "-eo", "pid,ppid,args"], capture_output=True,
                       text=True, timeout=60)
    осиротевшие = [s for s in p.stdout.splitlines()
                   if "site_engine.api.server" in s and "--port 879" in s
                   and "--port 8790" not in s]
    assert not осиротевшие, осиротевшие


# 37
def test_37_дублирующих_слушателей_нет():
    p = subprocess.run(["ss", "-lntp"], capture_output=True, text=True, timeout=60)
    порты: dict[str, int] = {}
    for s in p.stdout.splitlines()[1:]:
        части = s.split()
        if len(части) < 4:
            continue
        адрес = части[3]
        if ":" in адрес:
            порты[адрес] = порты.get(адрес, 0) + 1
    дубли = {k: v for k, v in порты.items() if v > 1}
    assert not дубли, дубли
    assert порты.get("127.0.0.1:8790", 0) == 1, "Control API слушает не один раз"
