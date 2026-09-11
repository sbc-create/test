"""G04: проверка endpoint'ов, OpenAPI, аутентификации, идемпотентности."""
import json, urllib.error, urllib.request, uuid
Б = "http://127.0.0.1:8791"
ТОКЕН = "local-architect-token"

def дай(п, заг=None):
    r = urllib.request.Request(Б + п, headers=заг or {})
    try:
        with urllib.request.urlopen(r, timeout=15) as o:
            return o.status, json.loads(o.read() or b"{}"), dict(o.headers)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}"), dict(e.headers)

def пост(п, тело, заг):
    r = urllib.request.Request(Б + п, data=json.dumps(тело).encode(),
                               headers={"Content-Type": "application/json", **заг},
                               method="POST")
    try:
        with urllib.request.urlopen(r, timeout=15) as o:
            return o.status, json.loads(o.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")

ок = 0; всего = 0
def проверка(имя, условие, деталь=""):
    global ок, всего
    всего += 1; ок += 1 if условие else 0
    print("  %-52s %s %s" % (имя, "OK" if условие else "СБОЙ", деталь))

к, т, _ = дай("/api/v1/sites")
проверка("GET /api/v1/sites", к == 200 and len(т["items"]) == 10, f"записей {len(т.get('items',[]))}")
прежние = all({"site_id","site_type","domains","render_mode"} <= set(i) for i in т["items"])
проверка("совместимость: прежние ключи на месте", прежние)
проверка("аддитивно: новые поля тоже есть",
         all("lifecycle_state" in i and "build_id" in i for i in т["items"]))

к, т, _ = дай("/api/v1/sites?environment=production&lifecycle_state=ACTIVE")
проверка("фильтр production+ACTIVE = 9", к == 200 and len(т["items"]) == 9,
         f"получено {len(т.get('items',[]))}")

к, т, _ = дай("/api/v1/sites/lords-01")
проверка("GET /api/v1/sites/{id}", к == 200 and т["site_id"] == "lords-01")
к, _, _ = дай("/api/v1/sites/no-such-site")
проверка("неизвестный site_id -> 404", к == 404)

к, т, _ = дай("/api/v1/registry/version")
проверка("GET /api/v1/registry/version", к == 200 and isinstance(т["registry_version"], int),
         f"версия {т.get('registry_version')}")

к, т, h = дай("/api/v1/registry/snapshot")
проверка("GET snapshot: 9 записей, checksum, ETag",
         к == 200 and т["count"] == 9 and т["checksum"] and h.get("ETag"))
проверка("snapshot не содержит fixture/demo",
         all(s["canonical_domain"] != "demo-books.invalid" for s in т["sites"]))

к, т, _ = дай("/api/v1/events?after=0&limit=5")
проверка("GET /api/v1/events по курсору", к == 200 and len(т["items"]) == 5)
к2, т2, _ = дай(f"/api/v1/events?after={т['next_cursor']}&limit=5")
проверка("курсор продвигается без дублей",
         к2 == 200 and not ({e["event_id"] for e in т["items"]} &
                            {e["event_id"] for e in т2["items"]}))

к, т, _ = дай("/api/v1/openapi.json")
пути = set((т or {}).get("paths", {}))
нужно = {"/api/v1/sites", "/api/v1/sites/{site_id}", "/api/v1/registry/version",
         "/api/v1/registry/snapshot", "/api/v1/events", "/health", "/ready"}
проверка("OpenAPI versioned и содержит обязательные пути",
         к == 200 and т.get("openapi", "").startswith("3.") and нужно <= пути,
         f"нет: {sorted(нужно - пути)}" if not нужно <= пути else "")

к, _, _ = дай("/health"); проверка("GET /health", к == 200)
к, _, _ = дай("/ready");  проверка("GET /ready", к == 200)

# --- команды ---
к, т = пост("/api/v1/internal/commands/register",
            {"site_id": "x", "fields": {"canonical_domain": "x.test"}}, {})
проверка("команда без токена -> 401", к == 401)

ключ = "http-" + uuid.uuid4().hex[:8]
sid = "synthetic-http-" + uuid.uuid4().hex[:6]
заг = {"Authorization": f"Bearer {ТОКЕН}", "X-Service-Name": "service:test",
       "Idempotency-Key": ключ}
к, a = пост("/api/v1/internal/commands/register",
            {"site_id": sid, "fields": {"canonical_domain": f"{sid}.test",
             "family": "test", "environment": "test",
             "lifecycle_state": "DRAFT"}}, заг)
проверка("команда с токеном применена", к == 200 and a.get("registry_version"),
         f"версия {a.get('registry_version')}")
к, b = пост("/api/v1/internal/commands/register",
            {"site_id": sid, "fields": {"canonical_domain": f"{sid}.test"}}, заг)
проверка("повтор с тем же Idempotency-Key -> тот же ответ",
         к == 200 and b.get("idempotent_replay") is True
         and b["registry_version"] == a["registry_version"])

заг2 = dict(заг, **{"Idempotency-Key": ключ + "-2", "If-Match": "999999"})
к, _ = пост("/api/v1/internal/commands/update", {"site_id": sid, "fields": {}}, заг2)
проверка("If-Match с чужой версией -> 409", к == 409)

к, т, _ = дай("/api/v1/registry/snapshot")
проверка("синтетический сайт не попал в production snapshot",
         all(s["site_id"] != sid for s in т["sites"]) and т["count"] == 9)

print(f"\nитого: {ок}/{всего}")
