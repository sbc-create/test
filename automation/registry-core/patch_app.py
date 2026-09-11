import pathlib, shutil
p = pathlib.Path("/srv/site-factory/control-api/current/factory/site_engine/api/app.py")
shutil.copyfile(p, p.with_suffix(".py.before-fleet-arc-001"))
s = p.read_text(encoding="utf-8")

старое = '''    def _sites(self) -> ApiResponse:
        return ApiResponse(
            200,
            {
                "items": [
                    {
                        "site_id": b.profile.site_id,
                        "site_type": b.profile.site_type,
                        "domains": list(b.profile.domains),
                        "render_mode": b.profile.render_mode,
                    }
                    for b in sorted(self._bindings.values(), key=lambda x: x.profile.site_id)
                ],
                "total": len(self._bindings),
            },
        )'''

новое = '''    # --- канонический реестр (FLEET-ARC-001) --------------------------------
    #
    # Авторитетом о сайтах становится хранилище реестра, а не каталог
    # профилей: над файлами нельзя изменить запись и записать событие одной
    # транзакцией, а без этого нет ни outbox, ни версии, по которой
    # потребитель отличит «я отстал» от «ничего не менялось».
    #
    # Профили остаются на диске и остаются источником первичного наполнения,
    # поэтому переход обратим. Если хранилища нет или оно недоступно, ответ
    # собирается по-прежнему из профилей: реестр не должен становиться
    # единственной точкой отказа для чтения.
    _РЕЕСТР_БД = "/srv/site-factory/registry-core/registry.sqlite3"

    def _реестр(self):
        import os
        import sqlite3
        if not os.path.exists(self._РЕЕСТР_БД):
            return None
        try:
            с = sqlite3.connect("file:%s?mode=ro" % self._РЕЕСТР_БД, uri=True,
                                timeout=5)
            с.row_factory = sqlite3.Row
            return с
        except Exception:  # noqa: BLE001
            return None

    def _реестр_запись(self, с, d):
        import json as _json
        тип = {"lords": "video-showcase", "zona": "video-showcase",
               "animedia": "anime-portal", "yummy": "anime-portal"}
        псевдонимы = [a["alias"] for a in с.execute(
            "SELECT alias FROM site_alias WHERE site_id=? ORDER BY alias",
            (d["site_id"],))]
        d["integration_refs"] = _json.loads(d.get("integration_refs") or "{}")
        d["aliases"] = псевдонимы
        # Прежние четыре ключа сохраняются с прежним смыслом, новые поля
        # приходят дополнительно: аддитивное расширение старого потребителя
        # не ломает, переименование сломало бы.
        d["site_type"] = тип.get(d.get("family"), "unknown")
        d["domains"] = [d["canonical_domain"]] + псевдонимы
        d["render_mode"] = "static"
        return d

    def _sites(self) -> ApiResponse:
        с = self._реестр()
        if с is not None:
            try:
                строки = [self._реестр_запись(с, dict(р)) for р in
                          с.execute("SELECT * FROM site ORDER BY site_id")]
                версия = с.execute(
                    "SELECT version FROM registry_version WHERE id=1").fetchone()
                return ApiResponse(200, {"items": строки, "total": len(строки),
                                         "registry_version": версия["version"],
                                         "source": "registry"})
            except Exception:  # noqa: BLE001
                pass
            finally:
                с.close()
        return ApiResponse(
            200,
            {
                "items": [
                    {
                        "site_id": b.profile.site_id,
                        "site_type": b.profile.site_type,
                        "domains": list(b.profile.domains),
                        "render_mode": b.profile.render_mode,
                    }
                    for b in sorted(self._bindings.values(), key=lambda x: x.profile.site_id)
                ],
                "total": len(self._bindings),
                "source": "profiles",
            },
        )

    def _registry_version(self) -> ApiResponse:
        с = self._реестр()
        if с is None:
            return error(503, "registry_unavailable", "хранилище реестра недоступно")
        try:
            в = с.execute("SELECT version FROM registry_version WHERE id=1").fetchone()
            return ApiResponse(200, {"registry_version": в["version"],
                                     "schema_version": "fleet-registry/1.0.0"})
        finally:
            с.close()

    def _registry_snapshot(self) -> ApiResponse:
        import hashlib as _h
        import json as _json
        с = self._реестр()
        if с is None:
            return error(503, "registry_unavailable", "хранилище реестра недоступно")
        try:
            сайты = [self._реестр_запись(с, dict(р)) for р in с.execute(
                "SELECT * FROM site WHERE environment='production' "
                "AND lifecycle_state='ACTIVE' ORDER BY site_id")]
            в = с.execute("SELECT version FROM registry_version WHERE id=1").fetchone()
            сырое = _json.dumps(сайты, ensure_ascii=False, sort_keys=True,
                                separators=(",", ":")).encode()
            отпечаток = _h.sha256(сырое).hexdigest()
            return ApiResponse(200, {
                "schema_version": "fleet-registry/1.0.0",
                "registry_version": в["version"], "count": len(сайты),
                "checksum": отпечаток,
                "etag": 'W/"%s-%d"' % (отпечаток[:16], в["version"]),
                "sites": сайты})
        finally:
            с.close()

    def _registry_events(self, params) -> ApiResponse:
        import json as _json
        с = self._реестр()
        if с is None:
            return error(503, "registry_unavailable", "хранилище реестра недоступно")
        try:
            def _ц(имя, умолч):
                v = (params or {}).get(имя, умолч)
                if isinstance(v, list):
                    v = v[0] if v else умолч
                try:
                    return int(v)
                except (TypeError, ValueError):
                    return умолч
            after, limit = _ц("after", 0), _ц("limit", 100)
            строки = []
            for р in с.execute(
                    "SELECT * FROM outbox WHERE seq > ? ORDER BY seq LIMIT ?",
                    (after, min(limit, 1000))):
                d = dict(р)
                d["payload"] = _json.loads(d["payload"])
                строки.append(d)
            return ApiResponse(200, {
                "schema_version": "fleet-registry/1.0.0", "items": строки,
                "next_cursor": строки[-1]["seq"] if строки else after})
        finally:
            с.close()'''

assert s.count(старое) == 1, "обработчик _sites не найден"
s = s.replace(старое, новое)

якорь = '''        if rest == ["sites"]:
            return self._sites()'''
маршруты = '''        if rest == ["sites"]:
            return self._sites()
        if rest == ["registry", "version"]:
            return self._registry_version()
        if rest == ["registry", "snapshot"]:
            return self._registry_snapshot()
        if rest == ["events"]:
            return self._registry_events(params)'''
assert s.count(якорь) == 1, "точка маршрутизации не найдена"
s = s.replace(якорь, маршруты)
p.write_text(s, encoding="utf-8")
print("app.py дополнен; резервная копия app.py.before-fleet-arc-001")
