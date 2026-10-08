"""Инвентаризация Яндекс.Вебмастера: почему у домена нет данных. Только чтение.

У всех доменов сети `webmaster.host_id` пуст, и из этого нельзя заключить
ничего, кроме «фабрика не знает host_id». Три разных состояния выглядят
одинаково и требуют разных действий:

* ``NOT_IN_ACCOUNT`` — в аккаунте, к которому выдан токен, такого сайта нет.
  Действие: добавить сайт (запись в Вебмастер, нужно разрешение владельца).
* ``IN_ACCOUNT_UNVERIFIED`` — сайт добавлен, права не подтверждены.
  Действие: разместить маркер и запустить подтверждение.
* ``MAPPING_MISMATCH`` — в аккаунте есть сайт того же домена, но под другим
  хостом (http, www, другой порт) — ИЛИ подтверждённый хост есть, а реестр
  фабрики его не знает. Это ошибка локального сопоставления, а не отсутствие
  сайта: действие — исправить реестр, а не добавлять второй сайт.
* ``VERIFIED_MAPPED`` — подтверждён, host_id в реестре совпадает.

Отсутствие привязки НЕ означает отсутствия индексации: страница может быть в
поиске и без сайта в Вебмастере. Модуль это и не утверждает — он называет,
почему данных Вебмастера нет.

Запросы: GET /v4/user, GET /v4/user/{id}/hosts, GET .../verification для
совпавших хостов. Ничего не добавляет, не подтверждает и не меняет реестр.
Токен приходит через LoadCredential службы; из сессии агента модуль токена не
получает и честно отвечает BLOCKED_ACCESS.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

from factory.analytics import registry
from factory.analytics.yandex import YandexAnalyticsProvider, normalize_domain
from factory.errors import FactoryError

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT = REPO_ROOT / "var" / "analytics" / "webmaster-inventory.json"


def exact_host_id(domain: str) -> str:
    """host_id, который Вебмастер присваивает https://<домен> (контракт: https:example.tld:443)."""
    return f"https:{normalize_domain(domain)}:443"


def classify(entry: dict, hosts: list[dict], verification: dict[str, str]) -> dict:
    """Состояние одного домена реестра по списку хостов аккаунта."""
    domain = normalize_domain(entry["domain"])
    local = (entry.get("webmaster") or {}).get("host_id")
    candidates = [h for h in hosts
                  if normalize_domain(str(h.get("ascii_host_url") or h.get("unicode_host_url") or "")) == domain]
    ids = [str(h.get("host_id")) for h in candidates]
    want = exact_host_id(domain)
    row: dict[str, Any] = {"domain": domain, "registry_host_id": local, "account_host_ids": ids,
                           "expected_host_id": want}
    if not candidates:
        row["state"] = "NOT_IN_ACCOUNT"
        row["action"] = "добавить https-сайт в Вебмастер и подтвердить права (запись, нужно разрешение)"
        return row
    if want not in ids:
        row["state"] = "MAPPING_MISMATCH"
        row["action"] = (f"в аккаунте домен есть только как {ids}; https-хоста {want} нет. "
                         "Сайт не добавлять вслепую: сначала решить, какой хост главный")
        return row
    state = verification.get(want, "UNKNOWN")
    row["verification_state"] = state
    if state != "VERIFIED":
        row["state"] = "IN_ACCOUNT_UNVERIFIED"
        row["action"] = "разместить маркер META_TAG или HTML_FILE и запустить подтверждение"
    elif local != want:
        row["state"] = "MAPPING_MISMATCH"
        row["action"] = f"сайт подтверждён как {want}, реестр хранит {local!r} — исправить реестр"
    else:
        row["state"] = "VERIFIED_MAPPED"
        row["action"] = "—"
    return row


def inventory(provider: YandexAnalyticsProvider | None = None,
              entries: list[dict] | None = None) -> dict:
    provider = provider or YandexAnalyticsProvider(dry_run=True)
    entries = entries if entries is not None else registry.load()["properties"]
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        hosts = provider.list_hosts()
    except FactoryError as exc:
        return {"collected_at": now, "status": "BLOCKED_ACCESS", "reason": exc.reason,
                "domains": [], "read_only": True}
    verification: dict[str, str] = {}
    wanted = {exact_host_id(e["domain"]) for e in entries}
    for host in hosts:
        host_id = str(host.get("host_id") or "")
        if host_id in wanted:
            try:
                verification[host_id] = provider.get_verification_marker(host_id)["verification_state"]
            except FactoryError as exc:
                verification[host_id] = f"NOT_READ: {exc.reason}"
    rows = [classify(e, hosts, verification) for e in entries]
    summary: dict[str, int] = {}
    for row in rows:
        summary[row["state"]] = summary.get(row["state"], 0) + 1
    return {"collected_at": now, "status": "MEASURED", "account_hosts": len(hosts),
            "summary": summary, "domains": rows, "read_only": True,
            "note": "отсутствие привязки к Вебмастеру не означает отсутствия индексации"}


def main(out: Path = OUT) -> int:
    report = inventory()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: report.get(k) for k in ("status", "reason", "account_hosts", "summary")},
                     ensure_ascii=False))
    return 0 if report["status"] == "MEASURED" else 69
