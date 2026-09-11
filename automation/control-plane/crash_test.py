#!/usr/bin/env python3
"""Аварийный сценарий: прерывание N+1 после создания записи, до завершения.

Проверяется не «упало ли», а «осталось ли что-нибудь в каноническом
реестре». При изоляции временной базой ответ известен заранее, но утверждать
это без проверки нельзя: именно так и появилась прошлая утечка.

Отдельно проверяется уборка осиротевших временных каталогов: изоляция,
которая копит мусор на диске, — это та же утечка, только медленнее.
"""
from __future__ import annotations
import hashlib, json, os, signal, subprocess, sys, tempfile, time
from pathlib import Path
import sqlite3

КАНОН = "/srv/site-factory/registry-core/registry.sqlite3"
ОТЧЁТ = Path("/srv/site-factory/control-plane-contracts/evidence/r3-crash.json")
провалы: list[str] = []


def шаг(имя, ок, деталь=""):
    print("  %-52s %s %s" % (имя, "PASS" if ок else "FAIL", деталь))
    if not ок:
        провалы.append(имя)


def отпечаток():
    c = sqlite3.connect(f"file:{КАНОН}?mode=ro", uri=True)
    ids = sorted(r[0] for r in c.execute("SELECT site_id FROM site"))
    backlog = c.execute("SELECT count(*) FROM outbox WHERE published_at IS NULL"
                        ).fetchone()[0]
    c.close()
    return len(ids), ids, hashlib.sha256(
        json.dumps(ids, ensure_ascii=False).encode()).hexdigest(), backlog


ЖЕРТВА = '''
import os, sys, shutil, tempfile, uuid, time
sys.path.insert(0, "/srv/site-factory/registry-core")
sys.path.insert(0, "/srv/site-factory/control-api/current")
import registry_command as rc, registry_store as rs
os.environ.setdefault(rc.ТОКЕН_REF, "local-architect-token")
d = tempfile.mkdtemp(prefix="npo-crash-")
p = os.path.join(d, "registry.sqlite3")
shutil.copyfile("/srv/site-factory/registry-core/registry.sqlite3", p)
c = rs.открыть(p)
sid = "synthetic-crash-" + uuid.uuid4().hex[:8]
rc.выполнить(c, команда="register", site_id=sid,
             поля={"canonical_domain": sid + ".test", "family": "test",
                   "environment": "test", "lifecycle_state": "DRAFT",
                   "integration_refs": {}},
             заголовки={"authorization": "Bearer " + os.environ[rc.ТОКЕН_REF],
                        "x-service-name": "service:architect",
                        "idempotency-key": "crash-" + uuid.uuid4().hex[:8]})
print(d, flush=True)
time.sleep(60)   # здесь нас убьют: уборка выполниться не успеет
'''


def main() -> int:
    B0, S0, H0, bl0 = отпечаток()
    print("  baseline: B=%d H=%s backlog=%d" % (B0, H0[:16], bl0))

    скрипт = Path(tempfile.mkdtemp(prefix="crash-runner-")) / "victim.py"
    скрипт.write_text(ЖЕРТВА, encoding="utf-8")
    пр = subprocess.Popen(
        ["/srv/site-factory/control-api/current/.venv/bin/python", str(скрипт)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    врем_каталог = (пр.stdout.readline() or "").strip()
    шаг("тестовая запись создана до прерывания", bool(врем_каталог),
        врем_каталог)

    # Убиваем БЕЗ шанса на уборку: SIGKILL не даёт отработать finally.
    пр.send_signal(signal.SIGKILL)
    пр.wait(timeout=30)
    шаг("процесс убит SIGKILL (уборка не отработала)", пр.returncode != 0,
        f"rc={пр.returncode}")
    шаг("осиротевший временный каталог остался на диске",
        bool(врем_каталог) and Path(врем_каталог).exists())

    B1, S1, H1, bl1 = отпечаток()
    шаг("канонический B не изменился после аварии", B1 == B0, f"{B0}->{B1}")
    шаг("канонический S не изменился", S1 == S0)
    шаг("канонический H не изменился", H1 == H0, H1[:16])
    шаг("канонический backlog не вырос", bl1 == bl0, f"{bl0}->{bl1}")

    # Recovery: уборка осиротевших каталогов изоляции.
    убрано = 0
    for d in Path(tempfile.gettempdir()).glob("npo-crash-*"):
        subprocess.run(["rm", "-rf", str(d)], check=False)
        убрано += 1
    for d in Path(tempfile.gettempdir()).glob("npo-cycle*"):
        subprocess.run(["rm", "-rf", str(d)], check=False)
        убрано += 1
    шаг("recovery убрал осиротевшие каталоги", убрано >= 1, f"убрано {убрано}")
    шаг("после recovery каталог отсутствует",
        not (врем_каталог and Path(врем_каталог).exists()))
    subprocess.run(["rm", "-rf", str(скрипт.parent)], check=False)

    B2, S2, H2, bl2 = отпечаток()
    шаг("baseline сохранён после recovery",
        (B2, S2, H2, bl2) == (B0, S0, H0, bl0), f"B={B2} H={H2[:16]}")

    # Нормальный прогон после восстановления.
    р = subprocess.run(
        ["/srv/site-factory/control-api/current/.venv/bin/python",
         "/srv/site-factory/control-plane-contracts/n_plus_one_isolated.py"],
        capture_output=True, text=True, timeout=300)
    шаг("нормальный N+1 после recovery проходит", р.returncode == 0,
        f"exit={р.returncode}")
    B3, S3, H3, bl3 = отпечаток()
    шаг("baseline сохранён после нормального прогона",
        (B3, S3, H3, bl3) == (B0, S0, H0, bl0), f"B={B3}")

    итог = {"verdict": "PASS" if not провалы else "FAIL", "failures": провалы,
            "B": B0, "H": H0, "orphan_dirs_cleaned": убрано,
            "canonical_delta": B3 - B0}
    ОТЧЁТ.parent.mkdir(parents=True, exist_ok=True)
    ОТЧЁТ.write_text(json.dumps(итог, ensure_ascii=False, indent=1),
                     encoding="utf-8")
    print("\n  вердикт:", итог["verdict"])
    return 0 if not провалы else 1


if __name__ == "__main__":
    sys.exit(main())
