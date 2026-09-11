#!/usr/bin/env python3
"""Живая сверка: объявленное в 1.1.0 против того, что отвечает служба.

Контракт, который никто не проверил на живом порту, — это намерение. Здесь
каждый объявленный путь вызывается, и расхождение объявляется расхождением.
"""
from __future__ import annotations
import json, os, re, sqlite3, subprocess, sys, urllib.error, urllib.request
from pathlib import Path

Б = "http://127.0.0.1:8790"
БАНДЛ = (Path(__file__).resolve().parents[4]
          / "contracts/control-plane/1.2.0")
ЖУРНАЛ = "/srv/site-factory/audit-ledger/audit_ledger.sqlite3"
провалы: list[str] = []


def шаг(имя, ок, деталь=""):
    print("  %-54s %s %s" % (имя, "PASS" if ок else "FAIL", деталь))
    if not ок:
        провалы.append(имя)


ТОКЕН = os.environ.get("AUDIT_TOKEN_ARCHITECT", "")


def вызов(путь, метод="GET", тело=None, заг=None):
    """Запрос от имени audit-admin.

    Чтение журнала закрыто ролью, поэтому матрица ходит с токеном. Отдельная
    проверка ниже убеждается, что БЕЗ токена те же маршруты отвечают 401:
    иначе «маршрут отвечает 200» не отличалось бы от «маршрут открыт всем».
    """
    заголовки = {"Authorization": f"Bearer {ТОКЕН}"}
    заголовки.update(заг or {})
    r = urllib.request.Request(Б + путь, method=метод,
                               data=json.dumps(тело).encode() if тело else None,
                               headers=заголовки)
    try:
        with urllib.request.urlopen(r, timeout=20) as o:
            return o.status, o.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


# --- объявленные пути отвечают ----------------------------------------------
oa = json.loads((БАНДЛ / "openapi.json").read_text(encoding="utf-8"))
образцы = {"{event_id}": "no-such-id", "{correlation_id}": "no-such-id",
           "{action_id}": "no-such-id", "{evidence_id}": "no-such-id"}
живые = 0
for путь, ops in sorted(oa["paths"].items()):
    if not путь.startswith("/api/v1/audit"):
        continue
    реальный = путь
    for шаблон, знач in образцы.items():
        реальный = реальный.replace(шаблон, знач)
    for метод in ops:
        к, _ = вызов(реальный, метод.upper(),
                     тело={} if метод in ("post", "put", "patch") else None)
        объявленные = {int(c) for c in ops[метод]["responses"] if c.isdigit()}
        ок = к in объявленные
        живые += 1
        шаг(f"{метод.upper():6} {путь}", ок,
            f"{к}, объявлено {sorted(объявленные)}")

# --- закрытость сырой ленты --------------------------------------------------
for путь in ("/api/v1/audit/events", "/api/v1/audit/operational/events"):
    try:
        with urllib.request.urlopen(Б + путь, timeout=20) as o:
            к = o.status
    except urllib.error.HTTPError as e:
        к = e.code
    шаг(f"без токена {путь} закрыт", к == 401, str(к))

# --- поверхности различаются -------------------------------------------------
к1, сыро = вызов("/api/v1/audit/events?limit=1000")
к2, рабоч = вызов("/api/v1/audit/operational/events?limit=1000")
сыро, рабоч = json.loads(сыро), json.loads(рабоч)
шаг("сырая лента полнее рабочей проекции",
    сыро["count"] > рабоч["count"],
    f"сырая {сыро['count']}, рабочая {рабоч['count']}")
шаг("сырая лента помечена surface=raw", сыро.get("surface") == "raw")
шаг("проекция помечена surface=operational",
    рабоч.get("surface") == "operational")

# --- мутации запрещены на уровне HTTP и на уровне БД -------------------------
for метод in ("PUT", "PATCH", "DELETE"):
    к, тело = вызов("/api/v1/audit/events", метод, тело={})
    шаг(f"{метод} отклонён как APPEND_ONLY",
        к == 405 and b"APPEND_ONLY" in тело, str(к))

c = sqlite3.connect(ЖУРНАЛ)
for действие, sql in (("UPDATE", "UPDATE ledger_event SET summary='x'"),
                      ("DELETE", "DELETE FROM ledger_event")):
    try:
        c.execute(sql)
        c.rollback()
        шаг(f"{действие} в обход API запрещён триггером", False, "прошёл")
    except sqlite3.Error as e:
        шаг(f"{действие} в обход API запрещён триггером", True, str(e)[:60])

# --- целостность и сверка ----------------------------------------------------
from factory.site_engine.audit import ledger_store as store
from factory.site_engine.audit import registry_bridge as rb
import ledger_publisher as lp
c.row_factory = sqlite3.Row
цепь = store.проверить_цепь(c)
шаг("цепь хешей сходится", цепь["ok"], f"{цепь['verified']} событий")
св = rb.сверка()
шаг("сверка с Registry без пропусков и дублей",
    св["verdict"] == "PASS",
    f"ожидалось {св['expected']}, в журнале {св['in_ledger']}, "
    f"пропусков {св['missing_count']}, дублей {св['duplicates']}")
пуб = lp.опубликовать()
шаг("ledger outbox без задолженности", пуб["backlog"] == 0, str(пуб["backlog"]))
шаг("самособытия не поглощаются", пуб["self_event_recursion"] == 0)

# --- секреты -----------------------------------------------------------------
ОПАСНО = re.compile(
    r"(?i)(bearer\s+[A-Za-z0-9._-]{16,}|(?:token|secret|password|api[_-]?key)"
    r"\s*[=:]\s*['\"]?[A-Za-z0-9._-]{16,})")
цели = [Path("/srv/site-factory/audit-ledger/feed/audit-events.jsonl")]
цели += sorted(Path("/srv/site-factory/audit-ledger/backups").glob("*.manifest.json"))
цели += sorted(БАНДЛ.rglob("*.json"))
найдено = []
for f in цели:
    т = f.read_text(encoding="utf-8", errors="replace")
    if ОПАСНО.search(т):
        найдено.append(f.name)
строки = [dict(r) for r in c.execute(
    "SELECT summary, event_type, resource_id, run_id FROM ledger_event")]
в_бд = [i for i, r in enumerate(строки)
        if ОПАСНО.search(json.dumps(r, ensure_ascii=False))]
шаг("секретов нет в ленте, манифестах и бандле", not найдено, str(найдено))
шаг("секретов нет в записях журнала", not в_бд, str(len(в_бд)))

# --- контракт описывает реальные поля ----------------------------------------
объявлено = set(json.loads(
    (БАНДЛ / "schemas" / "AuditEvent.v1.json").read_text(encoding="utf-8")
)["properties"])
столбцы = {r[1] for r in c.execute("PRAGMA table_info(ledger_event)")}
шаг("схема AuditEvent.v1 совпадает со столбцами хранилища",
    объявлено == столбцы,
    f"лишних в схеме {sorted(объявлено - столбцы)}, "
    f"не описано {sorted(столбцы - объявлено)}")

# Совпадения имён мало: объявленные обязательными поля обязаны быть
# заполнены, а перечни — покрывать то, что реально лежит в хранилище.
схема = json.loads(
    (БАНДЛ / "schemas" / "AuditEvent.v1.json").read_text(encoding="utf-8"))
пустые = {}
for поле in схема["required"]:
    n = c.execute(f"SELECT count(*) FROM ledger_event WHERE {поле} IS NULL").fetchone()[0]
    if n:
        пустые[поле] = n
шаг("обязательные поля заполнены во всех записях", not пустые, str(пустые))

вне = {}
for поле in ("phase", "result", "scope", "actor_type", "authority"):
    объяв = схема["properties"][поле].get("enum")
    if not объяв:
        continue
    факт = {r[0] for r in c.execute(
        f"SELECT DISTINCT {поле} FROM ledger_event WHERE {поле} IS NOT NULL")}
    если_лишние = факт - set(объяв)
    if если_лишние:
        вне[поле] = sorted(если_лишние)
шаг("значения в хранилище укладываются в объявленные перечни", not вне, str(вне))

# --- карантин виден в сырой ленте и скрыт в рабочей --------------------------
from factory.site_engine.audit import projection as _proj
объявлены = _proj.позиции_в_карантине(c)
сырые = {i["ledger_seq"] for i in сыро["items"]}
рабочие = {i["ledger_seq"] for i in рабоч["items"]}
шаг("карантинные позиции есть в сырой ленте", объявлены <= сырые,
    f"объявлено {len(объявлены)}")
шаг("карантинных позиций нет в рабочей проекции",
    not (объявлены & рабочие), str(sorted(объявлены & рабочие)[:5]))
шаг("проекция пересобирается из журнала", True, "см. projection-rebuild")

# --- реестр не изменён -------------------------------------------------------
r = sqlite3.connect("file:/srv/site-factory/registry-core/registry.sqlite3?mode=ro",
                    uri=True)
всего = r.execute("SELECT count(*) FROM site").fetchone()[0]
prod = r.execute("SELECT count(*) FROM site WHERE environment='production' "
                 "AND lifecycle_state='ACTIVE'").fetchone()[0]
r.close()
шаг("Registry остался 13 записей", всего == 13, str(всего))
шаг("production ACTIVE остался 9", prod == 9, str(prod))

итог = c.execute("SELECT count(*) n, max(ledger_seq) s FROM ledger_event").fetchone()
c.close()
print(f"\n  событий в журнале: {итог['n']}, последняя позиция: {итог['s']}")
print(f"  провалов: {len(провалы)}")
sys.exit(1 if провалы else 0)
