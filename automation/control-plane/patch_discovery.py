import hashlib, pathlib, shutil, datetime as dt
p = pathlib.Path("/srv/site-factory/control-api/current/factory/site_engine/api/app.py")
ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
b = pathlib.Path("/srv/site-factory/registry-core/backup")
b.mkdir(parents=True, exist_ok=True)
shutil.copyfile(p, b / f"app.py.{ts}.before-fleet-core-001")
print("backup:", b / f"app.py.{ts}.before-fleet-core-001")
print("sha256 до:", hashlib.sha256(p.read_bytes()).hexdigest()[:32])

s = p.read_text(encoding="utf-8")

якорь = '''        if rest == ["registry", "version"]:
            return self._registry_version()'''
маршруты = '''        if rest == ["contracts", "manifest"]:
            return self._contract_file("manifest.json")
        if rest == ["contracts", "openapi"]:
            return self._contract_file("openapi.json")
        if rest == ["contracts", "asyncapi"]:
            return self._contract_file("asyncapi.json")
        if rest[:2] == ["contracts", "schemas"] and len(rest) == 3:
            return self._contract_schema(rest[2])
        if rest == ["capabilities"]:
            return self._capabilities()
        if rest[:1] == ["capabilities"] and len(rest) == 2:
            return self._capability(rest[1])
        if rest == ["control-plane", "version"]:
            return self._control_plane_version()
        if rest == ["registry", "version"]:
            return self._registry_version()'''
assert s.count(якорь) == 1, "точка маршрутизации не найдена"
s = s.replace(якорь, маршруты)

метка = '''    def _registry_version(self) -> ApiResponse:'''
методы = '''    # --- contract discovery (FLEET-CORE-001) --------------------------------
    #
    # Контракты отдаются только на чтение и только из канонического bundle.
    # Второго источника контрактов не заводится: разошедшиеся описания одного
    # и того же API хуже отсутствующих, потому что каждое выглядит истинным.
    _BUNDLE = "/srv/site-factory/control-plane-contracts/1.0.0"

    def _bundle_path(self, отн: str):
        import os
        корень = os.path.realpath(self._BUNDLE)
        полный = os.path.realpath(os.path.join(корень, отн))
        # Выход за пределы bundle запрещён: имя схемы приходит из запроса, и
        # без этой проверки «../» отдал бы произвольный файл службы.
        if not полный.startswith(корень + os.sep) and полный != корень:
            return None
        return полный if os.path.isfile(полный) else None

    def _contract_file(self, имя: str) -> ApiResponse:
        import json as _json
        путь = self._bundle_path(имя)
        if путь is None:
            return error(404, "SCHEMA_UNKNOWN", "артефакта контракта нет")
        try:
            return ApiResponse(200, _json.loads(open(путь, encoding="utf-8").read()))
        except Exception:  # noqa: BLE001
            return error(503, "REGISTRY_UNAVAILABLE", "артефакт нечитаем")

    def _contract_schema(self, schema_id: str) -> ApiResponse:
        имя = schema_id if schema_id.endswith(".json") else schema_id + ".json"
        return self._contract_file("schemas/" + имя)

    def _capabilities(self) -> ApiResponse:
        return self._contract_file("capability-catalog.json")

    def _capability(self, capability_id: str) -> ApiResponse:
        import json as _json
        путь = self._bundle_path("capability-catalog.json")
        if путь is None:
            return error(404, "CAPABILITY_UNKNOWN", "каталога возможностей нет")
        каталог = _json.loads(open(путь, encoding="utf-8").read())
        for c in каталог.get("capabilities", []):
            if c.get("capability_id") == capability_id:
                return ApiResponse(200, c)
        return error(404, "CAPABILITY_UNKNOWN", "возможности с таким идентификатором нет")

    def _control_plane_version(self) -> ApiResponse:
        import json as _json
        путь = self._bundle_path("manifest.json")
        манифест = _json.loads(open(путь, encoding="utf-8").read()) if путь else {}
        ответ = {"control_plane_version": манифест.get("version"),
                 "bundle": манифест.get("bundle"),
                 "supported_majors": (манифест.get("compatibility_policy") or {}
                                      ).get("supported_majors", ["v1"]),
                 "registry_version": None}
        с = self._реестр()
        if с is not None:
            try:
                ответ["registry_version"] = с.execute(
                    "SELECT version FROM registry_version WHERE id=1"
                ).fetchone()["version"]
            finally:
                с.close()
        return ApiResponse(200, ответ)

    def _registry_version(self) -> ApiResponse:'''
assert s.count(метка) == 1
s = s.replace(метка, методы)
p.write_text(s, encoding="utf-8")
print("sha256 после:", hashlib.sha256(p.read_bytes()).hexdigest()[:32])
print("строк:", len(s.splitlines()))
