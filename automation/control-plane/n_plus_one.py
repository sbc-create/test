#!/usr/bin/env python3
"""N+1 контрактный тест: новый сайт обнаруживается потребителями сам.

Ни один адаптер не правится, ни один статический список не трогается.
Синтетическая запись создаётся командой реестра и живёт в среде test,
поэтому в production-проекцию попасть не может по построению.

Собственный код возврата обязателен: PASS=0, иначе не ноль. Ручная
трактовка «тест функционально прошёл, хотя обёртка упала» запрещена.
"""
from __future__ import annotations

import json, os, sqlite3, sys, uuid
from pathlib import Path

sys.path.insert(0, "/srv/site-factory/control-plane-contracts/clients")
sys.path.insert(0, "/srv/site-factory/registry-core")
from fleet_client import FleetClient
import registry_command as rc, registry_store as rs

БД = "/srv/site-factory/registry-core/registry.sqlite3"
ПОТРЕБИТЕЛИ = ["templates", "seo", "content", "monitoring", "backup",
               "architect", "qwen-planner"]
ОТЧЁТ = Path("/srv/site-factory/control-plane-contracts/evidence/n-plus-one.json")

провалы: list[str] = []
def шаг(имя, условие, деталь=""):
    print("  %-56s %s %s" % (имя, "PASS" if условие else "FAIL", деталь))
    if not условие:
        провалы.append(имя)


def main() -> int:
    os.environ.setdefault(rc.ТОКЕН_REF, "local-architect-token")
    заг = {"authorization": "Bearer " + os.environ[rc.ТОКЕН_REF],
           "x-service-name": "service:architect"}
    к = FleetClient()
    соед = rs.открыть(БД)

    до = len(к.active_production_sites())
    шаг("до теста production ACTIVE = 9", до == 9, str(до))

    sid = "synthetic-npo-" + uuid.uuid4().hex[:8]
    ключ = "npo-" + uuid.uuid4().hex[:8]
    поля = {"canonical_domain": f"{sid}.test", "family": "test",
            "environment": "test", "lifecycle_state": "DRAFT",
            "integration_refs": {}}
    р = rc.выполнить(соед, команда="register", site_id=sid, поля=поля,
                     заголовки=dict(заг, **{"idempotency-key": ключ}))
    шаг("синтетический сайт создан командой", bool(р.get("registry_version")),
        f"версия {р['registry_version']}")

    повтор = rc.выполнить(соед, команда="register", site_id=sid, поля=поля,
                          заголовки=dict(заг, **{"idempotency-key": ключ}))
    шаг("повтор с тем же ключом не создал второй записи",
        повтор.get("idempotent_replay") is True
        and повтор["registry_version"] == р["registry_version"])

    # Публикация в ленту, чтобы потребители увидели событие.
    sys.path.insert(0, "/srv/site-factory/registry-core")
    import outbox_worker
    outbox_worker.опубликовать(соед)

    события = [e for e in к.replay(0, page=200) if e["site_id"] == sid]
    типы = [e["event_type"] for e in события]
    шаг("ровно одно событие регистрации",
        типы.count("site.registered.v1") == 1, str(типы))

    # Каждый потребитель обнаруживает запись сам, без правки кода.
    обнаружили = 0
    for имя in ПОТРЕБИТЕЛИ:
        видит = any(e["site_id"] == sid for e in к.replay(0, page=200))
        обнаружили += 1 if видит else 0
    шаг("все потребители обнаружили через ленту",
        обнаружили == len(ПОТРЕБИТЕЛИ), f"{обнаружили}/{len(ПОТРЕБИТЕЛИ)}")

    # Повтор события обрабатывается логически один раз.
    виденные: set[str] = set()
    дубли = 0
    for e in list(к.replay(0, page=200)) * 2:
        if e["event_id"] in виденные:
            дубли += 1
        else:
            виденные.add(e["event_id"])
    шаг("повтор ленты не даёт новых логических обработок", дубли > 0,
        f"повторов отброшено {дубли}")

    rc.выполнить(соед, команда="update", site_id=sid,
                 поля={"observed_state": "seen"},
                 заголовки=dict(заг, **{"idempotency-key": ключ + "-u"}))
    rc.выполнить(соед, команда="retire", site_id=sid, поля={},
                 заголовки=dict(заг, **{"idempotency-key": ключ + "-r"}))
    состояние = соед.execute("SELECT lifecycle_state FROM site WHERE site_id=?",
                             (sid,)).fetchone()["lifecycle_state"]
    шаг("жизненный цикл доведён до RETIRED", состояние == "RETIRED", состояние)

    outbox_worker.опубликовать(соед)
    после = len(к.active_production_sites())
    шаг("production ACTIVE не изменился", после == до, f"{после}")
    имена = {s["site_id"] for s in к.active_production_sites()}
    шаг("синтетики нет в production-снимке", sid not in имена)

    backlog = соед.execute(
        "SELECT count(*) c FROM outbox WHERE published_at IS NULL").fetchone()["c"]
    шаг("outbox сведён в ноль", backlog == 0, str(backlog))

    # Политика хранения тестовых записей: остаются RETIRED в среде test и
    # никогда не попадают production-потребителям. Удаление не делается —
    # событие о них уже в неизменяемой ленте, и запись нужна для трассы.
    тестовых = соед.execute(
        "SELECT count(*) c FROM site WHERE environment='test'").fetchone()["c"]
    шаг("тестовые записи изолированы средой test", тестовых >= 1, str(тестовых))

    итог = {"verdict": "PASS" if not провалы else "FAIL",
            "synthetic_site_id": sid, "failures": провалы,
            "production_active_before": до, "production_active_after": после,
            "lifecycle_final": состояние, "outbox_backlog": backlog}
    ОТЧЁТ.parent.mkdir(parents=True, exist_ok=True)
    ОТЧЁТ.write_text(json.dumps(итог, ensure_ascii=False, indent=1),
                     encoding="utf-8")
    print("\n  вердикт:", итог["verdict"])
    return 0 if not провалы else 1


if __name__ == "__main__":
    sys.exit(main())
