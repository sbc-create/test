#!/usr/bin/env python3
"""N+1 контрактный тест на ИЗОЛИРОВАННОЙ базе. Канонический реестр не меняется.

Почему прежний тест оставлял запись
-----------------------------------

Он создавал синтетический сайт прямо в каноническом реестре и переводил его
в RETIRED. RETIRED — это состояние, а не удаление: запись оставалась
навсегда, и каждый прогон добавлял ещё одну. Рост 11 → 12 → 13 был не
случайностью, а устройством теста. Отчёт при этом объявлял ноль мутаций
реестра, потому что считал только production-записи, — и потому противоречил
сам себе.

Как изолировано
---------------

Канонический файл копируется в временную базу, и весь сценарий идёт там.
Используются ТЕ ЖЕ модули: `registry_store`, `registry_command`,
`outbox_worker`, `site_filter` и настоящий обработчик `SiteEngineApi` — тот
самый, что обслуживает 8790. Подменён только путь к базе, и он читается из
окружения на каждом вызове. Тестовая имитация обработчика проверяла бы саму
себя, а не production-код.

Временная база удаляется в `finally`, поэтому ни штатное завершение, ни
исключение, ни таймаут не оставляют следа в каноническом реестре: следа там
не появляется вовсе, а не убирается потом.
"""
from __future__ import annotations

import hashlib, json, os, shutil, sqlite3, sys, tempfile, uuid
from pathlib import Path

КАНОН = "/srv/site-factory/registry-core/registry.sqlite3"
ОТЧЁТ = Path("/srv/site-factory/control-plane-contracts/evidence/r3-n-plus-one.json")
sys.path.insert(0, "/srv/site-factory/registry-core")
sys.path.insert(0, "/srv/site-factory/control-api/current")

import registry_command as rc, registry_store as rs, outbox_worker

ПОТРЕБИТЕЛИ = ["templates", "seo", "content", "monitoring", "backup",
               "architect", "qwen-planner"]


def отпечаток(путь: str) -> tuple[int, list[str], str]:
    c = sqlite3.connect(f"file:{путь}?mode=ro", uri=True)
    ids = sorted(r[0] for r in c.execute("SELECT site_id FROM site"))
    c.close()
    return len(ids), ids, hashlib.sha256(
        json.dumps(ids, ensure_ascii=False).encode()).hexdigest()


def обработчик(путь_бд: str):
    """Настоящий production-обработчик поверх указанной базы."""
    os.environ["REGISTRY_DB"] = путь_бд
    from factory.site_engine.api import create_api
    from factory.site_engine import profiles as _p
    ids = [q.site_id for q in _p.load_all("/srv/site-factory/repo")]
    return create_api(ids, root="/srv/site-factory/repo",
                      env={"SITE_ENGINE_API_ENABLED": "1",
                           "SITE_ENGINE_ENVIRONMENT": "local"})


def цикл(номер: int, счётчики: dict) -> dict:
    провалы: list[str] = []

    def шаг(имя, ок, деталь=""):
        print("    %-50s %s %s" % (имя, "PASS" if ок else "FAIL", деталь))
        if not ок:
            провалы.append(имя)

    B0, S0, H0 = отпечаток(КАНОН)
    врем = Path(tempfile.mkdtemp(prefix=f"npo-cycle{номер}-")) / "registry.sqlite3"
    try:
        shutil.copyfile(КАНОН, врем)
        соед = rs.открыть(врем)
        api = обработчик(str(врем))

        до = api.handle("/api/v1/sites", {}).body["total"]
        prod_до = api.handle("/api/v1/sites",
                             {"environment": ["production"],
                              "lifecycle_state": ["ACTIVE"]}).body["total"]
        шаг("временная база повторяет канон", до == B0, f"{до}=={B0}")
        шаг("production ACTIVE во временной базе = 9", prod_до == 9, str(prod_до))

        sid = "synthetic-npo-" + uuid.uuid4().hex[:8]
        ключ = "npo-" + uuid.uuid4().hex[:8]
        заг = {"authorization": "Bearer " + os.environ[rc.ТОКЕН_REF],
               "x-service-name": "service:architect",
               "idempotency-key": ключ}
        поля = {"canonical_domain": f"{sid}.test", "family": "test",
                "environment": "test", "lifecycle_state": "DRAFT",
                "integration_refs": {}}
        р = rc.выполнить(соед, команда="register", site_id=sid, поля=поля,
                         заголовки=заг)
        счётчики["EPHEMERAL_TEST_RECORD_MUTATIONS"] += 1
        шаг("N+1 создан командой", bool(р.get("registry_version")))

        повтор = rc.выполнить(соед, команда="register", site_id=sid, поля=поля,
                              заголовки=заг)
        шаг("повтор ключа идемпотентен",
            повтор.get("idempotent_replay") is True
            and повтор["registry_version"] == р["registry_version"])

        outbox_worker.ЛЕНТА = врем.parent / "feed.jsonl"
        outbox_worker.опубликовать(соед)
        события = [json.loads(l) for l in
                   outbox_worker.ЛЕНТА.read_text(encoding="utf-8").splitlines()]
        свои = [e for e in события if e["site_id"] == sid]
        шаг("ровно одно событие регистрации",
            [e["event_type"] for e in свои].count("site.registered.v1") == 1)

        найдено = sum(1 for _ in ПОТРЕБИТЕЛИ
                      if any(e["site_id"] == sid for e in события))
        шаг("все потребители обнаружили", найдено == len(ПОТРЕБИТЕЛИ),
            f"{найдено}/{len(ПОТРЕБИТЕЛИ)}")

        после_созд = api.handle("/api/v1/sites", {}).body["total"]
        prod_после = api.handle("/api/v1/sites",
                                {"environment": ["production"],
                                 "lifecycle_state": ["ACTIVE"]}).body["total"]
        шаг("N+1 виден в полной выдаче", после_созд == B0 + 1,
            f"{после_созд}")
        шаг("N+1 НЕ попал в production ACTIVE", prod_после == 9, str(prod_после))

        for команда in ("update", "retire"):
            rc.выполнить(соед, команда=команда, site_id=sid,
                         поля={"observed_state": "seen"} if команда == "update" else {},
                         заголовки=dict(заг, **{"idempotency-key": ключ + команда}))
            счётчики["EPHEMERAL_TEST_RECORD_MUTATIONS"] += 1
        состояние = соед.execute(
            "SELECT lifecycle_state FROM site WHERE site_id=?", (sid,)
        ).fetchone()["lifecycle_state"]
        шаг("жизненный цикл доведён до RETIRED", состояние == "RETIRED", состояние)
        outbox_worker.опубликовать(соед)
        соед.close()
    finally:
        # Временная база уходит целиком: следа не остаётся ни при штатном
        # завершении, ни при исключении.
        shutil.rmtree(врем.parent, ignore_errors=True)
        os.environ.pop("REGISTRY_DB", None)

    B1, S1, H1 = отпечаток(КАНОН)
    шаг("канонический B восстановлен", B1 == B0, f"{B0}->{B1}")
    шаг("канонический S восстановлен", S1 == S0)
    шаг("канонический H восстановлен", H1 == H0, H1[:16])
    backlog = sqlite3.connect(f"file:{КАНОН}?mode=ro", uri=True).execute(
        "SELECT count(*) FROM outbox WHERE published_at IS NULL").fetchone()[0]
    шаг("канонический outbox backlog = 0", backlog == 0, str(backlog))

    return {"cycle": номер, "verdict": "PASS" if not провалы else "FAIL",
            "failures": провалы, "B_before": B0, "B_after": B1,
            "H_before": H0, "H_after": H1, "set_restored": S0 == S1,
            "canonical_net_persistent_delta": B1 - B0,
            "outbox_backlog": backlog}


def main() -> int:
    os.environ.setdefault(rc.ТОКЕН_REF, "local-architect-token")
    счётчики = {"EPHEMERAL_TEST_RECORD_MUTATIONS": 0,
                "CANONICAL_TEST_RECORDS_CREATED": 0,
                "CANONICAL_REGISTRY_RECORD_MUTATIONS": 0,
                "PRODUCTION_RECORD_MUTATIONS": 0}
    итоги = []
    for n in (1, 2):
        print(f"  цикл {n}:")
        итоги.append(цикл(n, счётчики))
    провалов = sum(1 for и in итоги if и["verdict"] != "PASS")
    отчёт = {"verdict": "PASS" if not провалов else "FAIL",
             "isolation_mode": "EPHEMERAL_DB",
             "cycles": итоги, "counters": счётчики}
    ОТЧЁТ.parent.mkdir(parents=True, exist_ok=True)
    ОТЧЁТ.write_text(json.dumps(отчёт, ensure_ascii=False, indent=1),
                     encoding="utf-8")
    print("\n  вердикт:", отчёт["verdict"], " счётчики:", счётчики)
    return 0 if not провалов else 1


if __name__ == "__main__":
    sys.exit(main())
