"""REQ-CONTROL-HTTP: API действительно подаётся и подаётся безопасно.

Проверка идёт через настоящий сокет, а не вызовом handle(): контракт, у которого
не проверен транспорт, выглядит готовым и не является таковым — ровно это и было
до появления server.py.
"""
import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from factory.site_engine.api import create_api
from factory.site_engine.api.control import ControlApi
from factory.site_engine.api.server import (
    MAX_BODY_BYTES,
    ServerConfig,
    build_server,
    http_enabled,
)
from factory.site_engine.store import InMemoryStore

ROOT = Path(__file__).resolve().parents[2]
ЧТЕНИЕ = {"SITE_ENGINE_API_ENABLED": "1", "SITE_ENGINE_ENVIRONMENT": "test"}
УПРАВЛЕНИЕ = {
    "SITE_ENGINE_CONTROL_WRITES": "1",
    "SITE_ENGINE_CONTROL_TOKENS": "t=read,jobs:write,config:write,cache:write,audit:read",
}
ЗАГОЛОВКИ = {"Authorization": "Bearer t", "Content-Type": "application/json"}


def _read_api():
    return create_api(["lords-01"], root=ROOT,
                      loader=lambda p: (InMemoryStore(p.site_id), "тестовый"), env=ЧТЕНИЕ)


@pytest.fixture
def сервер():
    srv = build_server(ServerConfig(host="127.0.0.1", port=0), _read_api(),
                       ControlApi(root=ROOT, env=УПРАВЛЕНИЕ))
    поток = threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
    поток.start()
    try:
        yield f"http://127.0.0.1:{srv.server_address[1]}"
    finally:
        srv.shutdown()
        поток.join(timeout=5)
        srv.server_close()


def запрос(база, путь, *, метод="GET", тело=None, заголовки=None, сырое=None):
    данные = сырое if сырое is not None else (
        json.dumps(тело).encode("utf-8") if тело is not None else None)
    req = urllib.request.Request(база + путь, data=данные, method=метод,
                                 headers=заголовки or {})
    try:
        with urllib.request.urlopen(req, timeout=10) as ответ:
            сырой = ответ.read().decode("utf-8")
            try:
                разобрано = json.loads(сырой)
            except json.JSONDecodeError:
                разобрано = {"raw": сырой}
            return ответ.status, разобрано, dict(ответ.headers)
    except urllib.error.HTTPError as e:
        сырой = e.read().decode("utf-8")
        try:
            разобрано = json.loads(сырой)
        except json.JSONDecodeError:
            разобрано = {"raw": сырой}
        return e.code, разобрано, dict(e.headers)


def test_подача_выключена_по_умолчанию():
    assert http_enabled({}) is False


def test_читающий_маршрут_отвечает_по_http(сервер):
    код, тело, _ = запрос(сервер, "/api/v1/health")
    assert код == 200
    assert isinstance(тело, dict)


def test_записывающий_маршрут_без_токена_отклонён(сервер):
    код, тело, _ = запрос(сервер, "/api/v1/sites/lords-01/jobs", метод="POST",
                          тело={"action": "reindex", "dryRun": True},
                          заголовки={"Content-Type": "application/json"})
    assert код == 401
    assert тело["error"]["code"] == "unauthorized"


def test_записывающий_маршрут_с_токеном_проходит(сервер):
    код, тело, _ = запрос(сервер, "/api/v1/sites/lords-01/jobs", метод="POST",
                          тело={"action": "reindex", "dryRun": True}, заголовки=ЗАГОЛОВКИ)
    assert код == 200
    assert тело["dryRun"] is True
    assert тело["correlationId"].startswith("cid-")


def test_управляющее_чтение_принимает_параметры_строки_запроса(сервер):
    код, тело, _ = запрос(сервер, "/api/v1/audit?limit=3", заголовки=ЗАГОЛОВКИ)
    assert код == 200
    assert len(тело["entries"]) <= 3


def test_негодный_limit_в_строке_запроса_не_роняет_сервер(сервер):
    код, тело, _ = запрос(сервер, "/api/v1/audit?limit=abc", заголовки=ЗАГОЛОВКИ)
    assert код == 400
    assert тело["error"]["code"] == "invalid_limit"


def test_слишком_большое_тело_отклоняется_до_разбора(сервер):
    """Без предела отправитель решает, сколько занять памяти."""
    код, тело, _ = запрос(сервер, "/api/v1/sites/lords-01/jobs", метод="POST",
                          сырое=b"x" * (MAX_BODY_BYTES + 1), заголовки=ЗАГОЛОВКИ)
    assert код == 413
    assert тело["error"]["code"] == "body_too_large"


def test_негодный_json_даёт_400_а_не_500(сервер):
    код, тело, _ = запрос(сервер, "/api/v1/sites/lords-01/jobs", метод="POST",
                          сырое="{не json".encode(), заголовки=ЗАГОЛОВКИ)
    assert код == 400
    assert тело["error"]["code"] == "invalid_json"


def test_json_не_объект_отклоняется(сервер):
    код, тело, _ = запрос(сервер, "/api/v1/sites/lords-01/jobs", метод="POST",
                          сырое=b"[1,2,3]", заголовки=ЗАГОЛОВКИ)
    assert код == 400


def test_запись_в_читающий_маршрут_запрещена(сервер):
    код, тело, _ = запрос(сервер, "/api/v1/health", метод="PUT", тело={}, заголовки=ЗАГОЛОВКИ)
    assert код == 405


def test_удаление_не_предусмотрено(сервер):
    код, _, _ = запрос(сервер, "/api/v1/sites/lords-01/jobs", метод="DELETE",
                       заголовки=ЗАГОЛОВКИ)
    assert код == 405


def test_ответы_не_кэшируются(сервер):
    """Устаревшее состояние задания хуже отсутствия ответа."""
    _, _, заголовки = запрос(сервер, "/api/v1/health")
    assert заголовки.get("Cache-Control") == "no-store"


def test_ответ_об_ошибке_не_раскрывает_устройство(сервер):
    код, тело, _ = запрос(сервер, "/api/v1/sites/lords-01/settings", метод="PATCH",
                          тело={"changes": {"нет_такой": 1}}, заголовки=ЗАГОЛОВКИ)
    сырое = json.dumps(тело, ensure_ascii=False)
    assert "Traceback" not in сырое and "factory/" not in сырое


def test_публичная_привязка_требует_явного_разрешения():
    """«host: 0.0.0.0» проходит ревью как настройка сети, хотя это не она."""
    with pytest.raises(ValueError, match="allow_public_bind"):
        build_server(ServerConfig(host="0.0.0.0", port=0), _read_api(),
                     ControlApi(root=ROOT, env=УПРАВЛЕНИЕ))


def test_локальная_привязка_разрешена_без_оговорок():
    srv = build_server(ServerConfig(host="127.0.0.1", port=0), _read_api(),
                       ControlApi(root=ROOT, env=УПРАВЛЕНИЕ))
    try:
        assert srv.server_address[0] == "127.0.0.1"
    finally:
        srv.server_close()


def test_выключенная_запись_невидима_и_по_http():
    """Через транспорт выключатель должен вести себя так же, как в модуле."""
    srv = build_server(ServerConfig(host="127.0.0.1", port=0), _read_api(),
                       ControlApi(root=ROOT, env={"SITE_ENGINE_CONTROL_TOKENS":
                                                  УПРАВЛЕНИЕ["SITE_ENGINE_CONTROL_TOKENS"]}))
    поток = threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
    поток.start()
    try:
        база = f"http://127.0.0.1:{srv.server_address[1]}"
        код, тело, _ = запрос(база, "/api/v1/sites/lords-01/jobs", метод="POST",
                              тело={"action": "reindex", "dryRun": True}, заголовки=ЗАГОЛОВКИ)
        assert код == 404
        assert "disabled" not in json.dumps(тело).lower()
    finally:
        srv.shutdown()
        поток.join(timeout=5)
        srv.server_close()


def test_метрики_отдаются_текстом_для_сборщика(сервер):
    """Сборщик не разбирает JSON; текстовый формат — не украшение."""
    код, _, заголовки = запрос(сервер, "/api/v1/metrics", заголовки=ЗАГОЛОВКИ)
    assert код == 200
    assert заголовки.get("Content-Type", "").startswith("text/plain")
    assert "version=0.0.4" in заголовки.get("Content-Type", "")


def test_метрики_без_токена_не_отдаются(сервер):
    """Состав очереди и число витрин — сведения о работе, а не о погоде."""
    код, _, _ = запрос(сервер, "/api/v1/metrics")
    assert код == 401
