import hashlib, json, pathlib, re

# 1. Служба отдаёт bundle 1.0.1.
app = pathlib.Path("/srv/site-factory/control-api/current/factory/site_engine/api/app.py")
s = app.read_text(encoding="utf-8")
s2 = s.replace('_BUNDLE = "/srv/site-factory/control-plane-contracts/1.0.0"',
               '_BUNDLE = "/srv/site-factory/control-plane-contracts/1.0.1"')
assert s2 != s, "путь к bundle не найден"
app.write_text(s2, encoding="utf-8")
print("служба переведена на 1.0.1; sha256:",
      hashlib.sha256(app.read_bytes()).hexdigest()[:32])

# 2. Клиент снова берёт девять фильтром, а не обходом.
cl = pathlib.Path("/srv/site-factory/control-plane-contracts/clients/fleet_client.py")
c = cl.read_text(encoding="utf-8")
начало = c.index("    def active_production_sites(self)")
конец = c.index("    def snapshot(self)")
новое = '''    def active_production_sites(self) -> list[dict]:
        """Девять сайтов берутся сервер-сайд фильтром, а не обходом.

        До 1.0.1 здесь стоял `snapshot()`, потому что провайдер объявлял
        параметры и не применял их. Обход защищал клиента, но оставлял
        контракт лживым, поэтому починен был провайдер, а не клиент.
        """
        return self.sites(environment="production", lifecycle_state="ACTIVE")

'''
cl.write_text(c[:начало] + новое + c[конец:], encoding="utf-8")
print("клиент вернулся на фильтр")

# 3. TypeScript — то же самое.
ts = pathlib.Path("/srv/site-factory/control-plane-contracts/clients/fleetClient.ts")
t = ts.read_text(encoding="utf-8")
t = t.replace("  /** Девять сайтов берутся из реестра, а не из списка в коде. */",
              "  /** Девять сайтов берутся сервер-сайд фильтром (bundle 1.0.1). */")
ts.write_text(t, encoding="utf-8")

# 4. Возможность фильтра в каталоге — с живой проверкой.
b3 = pathlib.Path("/srv/site-factory/control-plane-contracts/build_bundle3.py")
s3 = b3.read_text(encoding="utf-8")
s3 = s3.replace('ВЕРСИЯ = "1.0.0"', 'ВЕРСИЯ = "1.0.1"')
s3 = s3.replace(
    ''' ("registry.sites.read", "architect", "/api/v1/sites",''',
    ''' ("registry.sites.filter", "architect",
  "/api/v1/sites?environment=production&lifecycle_state=ACTIVE", []),
 ("registry.sites.read", "architect", "/api/v1/sites",''')
b3.write_text(s3, encoding="utf-8")
print("каталог возможностей дополнен registry.sites.filter")
