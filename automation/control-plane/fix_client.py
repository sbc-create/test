import json, pathlib

# 1. Клиент берёт девять из snapshot — канонической проекции ACTIVE production.
p = pathlib.Path("/srv/site-factory/control-plane-contracts/clients/fleet_client.py")
s = p.read_text(encoding="utf-8")
старое = '''    def active_production_sites(self) -> list[dict]:
        """Девять сайтов берутся из реестра, а не из списка в коде."""
        return self.sites(environment="production", lifecycle_state="ACTIVE")'''
новое = '''    def active_production_sites(self) -> list[dict]:
        """Девять сайтов берутся из реестра, а не из списка в коде.

        Источник — `/api/v1/registry/snapshot`, каноническая проекция ACTIVE
        production. Фильтры `/api/v1/sites?environment=&lifecycle_state=`
        объявлены в OpenAPI, но провайдером ПОКА НЕ РЕАЛИЗОВАНЫ: он вернёт
        весь реестр, и потребитель посчитал бы одиннадцать записей девятью,
        включив демо и синтетику. Пока фильтры не реализованы, единственный
        честный источник числа девять — снимок.
        """
        снимок, _ = self.snapshot()
        return снимок.get("sites", [])'''
assert s.count(старое) == 1
p.write_text(s.replace(старое, новое), encoding="utf-8")
print("клиент переведён на snapshot")

# 2. OpenAPI перестаёт обещать нереализованный фильтр.
o = pathlib.Path("/srv/site-factory/control-plane-contracts/1.0.0/openapi.json")
d = json.loads(o.read_text(encoding="utf-8"))
sites = d["paths"]["/api/v1/sites"]["get"]
for prm in sites.get("parameters", []):
    prm["x-status"] = "PLANNED"
    prm["description"] = ("объявлен, но провайдером ещё не применяется: ответ "
                          "не фильтруется. Для ACTIVE production используйте "
                          "/api/v1/registry/snapshot")
sites["x-known-gap"] = {
    "gap_id": "SITES_QUERY_FILTER_NOT_APPLIED",
    "owner": "architect",
    "detail": ("параметры environment и lifecycle_state принимаются, но не "
               "влияют на выдачу; провайдер возвращает весь реестр"),
    "workaround": "/api/v1/registry/snapshot даёт ровно ACTIVE production",
    "fix_requires": "аддитивная правка _sites() в Control API",
    "status": "BLOCKED_PENDING_OWNER_APPROVAL"}
o.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print("OpenAPI: фильтр помечен PLANNED, разрыв задокументирован")
