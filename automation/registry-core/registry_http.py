"""HTTP-слой канонического реестра: чтение, снимок, события, команды.

Совместимость. Существующий `GET /api/v1/sites` обязан продолжать отвечать в
прежней форме — на него уже кто-то опирается. Поэтому новые поля приходят
ДОПОЛНИТЕЛЬНО, а прежние ключи (`site_id`, `site_type`, `domains`,
`render_mode`) остаются на месте с прежним смыслом. Аддитивное расширение
потребителя не ломает; переименование сломало бы.
"""
from __future__ import annotations

import json, os, sqlite3, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import registry_store as rs, registry_command as rc

БД = os.environ.get("REGISTRY_DB",
                    "/srv/site-factory/registry-core/registry.sqlite3")
ВЕРСИЯ_API = "v1"

OPENAPI = {
    "openapi": "3.0.3",
    "info": {"title": "Site Registry", "version": "1.0.0",
             "description": "Канонический реестр сайтов Site Factory"},
    "paths": {
        "/api/v1/sites": {"get": {"summary": "Список сайтов",
            "parameters": [
                {"name": "environment", "in": "query",
                 "schema": {"type": "string"}},
                {"name": "lifecycle_state", "in": "query",
                 "schema": {"type": "string"}}],
            "responses": {"200": {"description": "Список"}}}},
        "/api/v1/sites/{site_id}": {"get": {"summary": "Сайт",
            "parameters": [{"name": "site_id", "in": "path", "required": True,
                            "schema": {"type": "string"}}],
            "responses": {"200": {"description": "Запись"},
                          "404": {"description": "Нет такого сайта"}}}},
        "/api/v1/registry/version": {"get": {"summary": "Версия реестра",
            "responses": {"200": {"description": "Версия"}}}},
        "/api/v1/registry/snapshot": {"get": {"summary": "Снимок ACTIVE production",
            "responses": {"200": {"description": "Снимок с checksum и ETag"}}}},
        "/api/v1/events": {"get": {"summary": "Лента событий",
            "parameters": [
                {"name": "after", "in": "query", "schema": {"type": "integer"}},
                {"name": "limit", "in": "query", "schema": {"type": "integer"}}],
            "responses": {"200": {"description": "События"}}}},
        "/api/v1/internal/commands/{command}": {"post": {
            "summary": "Команда изменения реестра",
            "description": ("Требует служебный токен, Idempotency-Key и "
                            "необязательный If-Match с версией реестра"),
            "responses": {"200": {"description": "Применено"},
                          "401": {"description": "Нет прав"},
                          "409": {"description": "Конфликт версии или домена"},
                          "422": {"description": "Неверная команда"}}}},
        "/health": {"get": {"summary": "Живость",
                            "responses": {"200": {"description": "ok"}}}},
        "/ready": {"get": {"summary": "Готовность",
                           "responses": {"200": {"description": "ready"},
                                         "503": {"description": "не готов"}}}},
    },
}

#: Прежняя форма записи. Менять её нельзя — на неё опираются потребители.
def прежний_вид(р: dict) -> dict:
    тип = {"lords": "video-showcase", "zona": "video-showcase",
           "animedia": "anime-portal", "yummy": "anime-portal"}
    return {"site_id": р["site_id"],
            "site_type": тип.get(р["family"], "unknown"),
            "domains": [р["canonical_domain"]] + р.get("aliases", []),
            "render_mode": "static"}


def полный_вид(р: dict) -> dict:
    д = dict(р)
    д["registry_schema"] = rs.СХЕМА
    return д


class Обработчик(BaseHTTPRequestHandler):
    server_version = "SiteRegistry/1.0"

    def log_message(self, *a):    # тишина в stderr: журнал ведёт служба
        pass

    def _ответ(self, код: int, тело, заголовки: dict | None = None):
        сырое = json.dumps(тело, ensure_ascii=False).encode()
        self.send_response(код)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(сырое)))
        for k, v in (заголовки or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(сырое)

    def _бд(self):
        с = sqlite3.connect(БД, timeout=30, isolation_level=None)
        с.row_factory = sqlite3.Row
        return с

    def do_GET(self):
        u = urlparse(self.path)
        путь, q = u.path.rstrip("/") or "/", parse_qs(u.query)
        try:
            с = self._бд()
        except Exception:
            return self._ответ(503, {"error": "registry_unavailable"})
        if путь == "/health":
            return self._ответ(200, {"status": "ok"})
        if путь == "/ready":
            try:
                rs._версия(с)
                return self._ответ(200, {"status": "ready"})
            except Exception:
                return self._ответ(503, {"status": "not_ready"})
        if путь == "/api/v1/openapi.json":
            return self._ответ(200, OPENAPI)
        if путь == "/api/v1/registry/version":
            return self._ответ(200, {"registry_version": rs._версия(с),
                                     "schema_version": rs.СХЕМА})
        if путь == "/api/v1/registry/snapshot":
            сн = rs.снимок(с)
            return self._ответ(200, сн, {"ETag": сн["etag"]})
        if путь == "/api/v1/events":
            after = int((q.get("after") or ["0"])[0])
            limit = int((q.get("limit") or ["100"])[0])
            return self._ответ(200, rs.события(с, after, limit))
        if путь == "/api/v1/sites":
            где, парам = [], []
            if q.get("environment"):
                где.append("environment=?"); парам.append(q["environment"][0])
            if q.get("lifecycle_state"):
                где.append("lifecycle_state=?"); парам.append(q["lifecycle_state"][0])
            sql = "SELECT * FROM site" + (" WHERE " + " AND ".join(где) if где else "")
            строки = []
            for р in с.execute(sql + " ORDER BY site_id", парам):
                d = dict(р)
                d["integration_refs"] = json.loads(d["integration_refs"] or "{}")
                d["aliases"] = [a["alias"] for a in с.execute(
                    "SELECT alias FROM site_alias WHERE site_id=?", (d["site_id"],))]
                # Прежние ключи + новые поля: аддитивно, ничего не переименовано.
                строки.append({**прежний_вид(d), **полный_вид(d)})
            return self._ответ(200, {"items": строки,
                                     "registry_version": rs._версия(с)})
        if путь.startswith("/api/v1/sites/"):
            sid = путь.rsplit("/", 1)[-1]
            р = с.execute("SELECT * FROM site WHERE site_id=?", (sid,)).fetchone()
            if not р:
                return self._ответ(404, {"error": {"code": "site_not_found",
                                                   "message": f"сайта {sid} нет"}})
            d = dict(р)
            d["integration_refs"] = json.loads(d["integration_refs"] or "{}")
            d["aliases"] = [a["alias"] for a in с.execute(
                "SELECT alias FROM site_alias WHERE site_id=?", (sid,))]
            return self._ответ(200, {**прежний_вид(d), **полный_вид(d)})
        return self._ответ(404, {"error": {"code": "not_found",
                                           "message": "маршрут не найден"}})

    def do_POST(self):
        u = urlparse(self.path)
        путь = u.path.rstrip("/")
        if not путь.startswith("/api/v1/internal/commands/"):
            return self._ответ(404, {"error": {"code": "not_found"}})
        команда = путь.rsplit("/", 1)[-1]
        длина = int(self.headers.get("Content-Length") or 0)
        тело = json.loads(self.rfile.read(длина) or b"{}")
        заг = {k.lower(): v for k, v in self.headers.items()}
        ожид = заг.get("if-match")
        try:
            с = self._бд()
            итог = rc.выполнить(
                с, команда=команда, site_id=тело["site_id"],
                поля=тело.get("fields") or {}, заголовки=заг,
                expected_version=int(ожид) if ожид else None,
                aliases=тело.get("aliases"))
            return self._ответ(200, итог)
        except rc.AuthError as e:
            return self._ответ(401, {"error": {"code": "unauthorized",
                                               "message": str(e)}})
        except rs.ConflictError as e:
            return self._ответ(409, {"error": {"code": "conflict",
                                               "message": str(e)}})
        except (KeyError, ValueError) as e:
            return self._ответ(422, {"error": {"code": "invalid",
                                               "message": str(e)}})


def main() -> int:
    порт = int(os.environ.get("REGISTRY_PORT", "8791"))
    сервер = ThreadingHTTPServer(("127.0.0.1", порт), Обработчик)
    print(f"registry слушает 127.0.0.1:{порт}, БД {БД}", flush=True)
    сервер.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
