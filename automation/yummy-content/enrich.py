#!/usr/bin/env python3
"""Полное обогащение shadow-каталога из CVH titles/{id}.

Секрет читается из объявленного secret-path и НИКОГДА не печатается: ни в
лог, ни в отчёт, ни в исключение. Значение живёт только в заголовке запроса.

Возобновляемость: результат каждой сущности пишется в таблицу сразу, поэтому
остановка в любой момент теряет не больше одной записи, а повторный запуск
продолжает с того места, где остановились. Ключ идемпотентности — сама
сущность: `ENRICHED` повторно не запрашивается.
"""
from __future__ import annotations

import argparse, json, os, random, sqlite3, sys, time, urllib.error, urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import store, detail as detail_mod

СЕКРЕТ = "/etc/site-factory/secrets/lords/lords-01/cdnvideohub-api-token"
БАЗА = "https://public-api.cdnvideohub.com/api/v1/"
КЭШ = Path("/srv/site-factory/repo/var/lords/detail-cache")
ПАУЗА = 0.12          # ~8 запросов в секунду
ПОПЫТОК = 3

DDL = """
CREATE TABLE IF NOT EXISTS enrichment_state (
  entity_id  TEXT PRIMARY KEY,
  outcome    TEXT NOT NULL,   -- ENRICHED|PROVIDER_NOT_FOUND|PROVIDER_ERROR|ID_CONFLICT|RETRY_PENDING
  attempts   INTEGER NOT NULL DEFAULT 0,
  http_code  INTEGER,
  reason     TEXT,
  updated_at TEXT NOT NULL
);
"""


def токен() -> str:
    """Прочитать секрет. Возвращается значение, но нигде не печатается."""
    п = Path(СЕКРЕТ)
    if not п.exists():
        raise SystemExit(f"secret-path не найден: {СЕКРЕТ} (значение не читалось)")
    з = п.read_text(encoding="utf-8").strip()
    if not з:
        raise SystemExit("secret-path пуст")
    return з


def запрос(ид: str, тк: str) -> tuple[int, dict | None, str]:
    url = f"{БАЗА}titles/{ид}"
    зпр = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {тк}", "Accept": "application/json",
        "User-Agent": "site-factory-content/1.0"})
    try:
        with urllib.request.urlopen(зпр, timeout=25) as о:
            return о.status, json.loads(о.read().decode("utf-8", "replace")), ""
    except urllib.error.HTTPError as e:
        # Тело ошибки в лог не идёт: в нём может оказаться эхо заголовков.
        return e.code, None, f"HTTP {e.code}"
    except Exception as e:  # noqa: BLE001
        return 0, None, type(e).__name__


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--db", default="/srv/site-factory/yummy-content/state/yummy-content.sqlite3")
    p.add_argument("--limit", type=int, default=0)
    a = p.parse_args()

    соед = store.открыть(a.db)
    соед.executescript(DDL)
    тк = токен()
    КЭШ.mkdir(parents=True, exist_ok=True)

    цели = [р["entity_id"] for р in соед.execute(
        "SELECT e.entity_id FROM entity e LEFT JOIN enrichment_state s "
        "ON s.entity_id = e.entity_id "
        "WHERE s.outcome IS NULL OR s.outcome IN ('RETRY_PENDING','PROVIDER_ERROR') "
        "ORDER BY e.entity_id")]
    if a.limit:
        цели = цели[:a.limit]
    print(f"к обогащению: {len(цели)}", flush=True)

    т0, итоги = time.time(), {}
    for n, ид in enumerate(цели, 1):
        # Уже лежащий в кэше detail сетевого запроса не требует.
        if (КЭШ / f"{ид}.json").exists():
            исход, код, причина = "ENRICHED", None, "из кэша"
        else:
            исход = код = причина = None
            for попытка in range(1, ПОПЫТОК + 1):
                код, тело, ош = запрос(ид, тк)
                if код == 200 and isinstance(тело, dict):
                    (КЭШ / f"{ид}.json").write_text(json.dumps(
                        {"detail": тело, "fetched_at": time.time(),
                         "status": "ok"}, ensure_ascii=False), encoding="utf-8")
                    исход, причина = "ENRICHED", ""
                    break
                if код == 404:
                    исход, причина = "PROVIDER_NOT_FOUND", "источник не знает такого id"
                    break
                if код in (401, 403):
                    исход, причина = "PROVIDER_ERROR", f"доступ запрещён ({код})"
                    break
                причина = ош or f"HTTP {код}"
                исход = "RETRY_PENDING" if попытка < ПОПЫТОК else "PROVIDER_ERROR"
                if попытка < ПОПЫТОК:
                    time.sleep(min(2 ** попытка, 8) + random.random())
            time.sleep(ПАУЗА)
        соед.execute(
            "INSERT INTO enrichment_state(entity_id, outcome, attempts, "
            "http_code, reason, updated_at) VALUES(?,?,?,?,?,datetime('now')) "
            "ON CONFLICT(entity_id) DO UPDATE SET outcome=excluded.outcome, "
            "attempts=enrichment_state.attempts+1, http_code=excluded.http_code, "
            "reason=excluded.reason, updated_at=excluded.updated_at",
            (ид, исход, 1, код, (причина or "")[:200]))
        итоги[исход] = итоги.get(исход, 0) + 1
        if n % 200 == 0:
            соед.commit()
            print(f"  {n}/{len(цели)} за {time.time()-т0:.0f} с: "
                  f"{json.dumps(итоги, ensure_ascii=False)}", flush=True)
        if исход == "PROVIDER_ERROR" and итоги.get("PROVIDER_ERROR", 0) > 50:
            print("слишком много отказов источника — останов, "
                  "уже полученное сохранено", flush=True)
            break
    соед.commit()
    print("итог:", json.dumps(итоги, ensure_ascii=False), flush=True)
    print("применяю detail к сущностям…", flush=True)
    print(json.dumps(detail_mod.обогатить(соед), ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
