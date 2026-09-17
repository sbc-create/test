"""Сверка описания API с тем, что API действительно делает.

Отдельное описание расходится с кодом за одну итерацию. Здесь описание
порождается из кода, а тест проверяет, что порождённое соответствует
отвечающим маршрутам, а не наоборот.
"""
import json
from pathlib import Path

import jsonschema
import pytest

from factory.site_engine.api import create_api
from factory.site_engine.api.control import ControlApi
from factory.site_engine.api.openapi import ЗАПИСЬ, spec
from factory.site_engine.store import InMemoryStore

ROOT = Path(__file__).resolve().parents[2]
ВКЛЮЧЁН = {"SITE_ENGINE_API_ENABLED": "1", "SITE_ENGINE_ENVIRONMENT": "test"}
УПРАВЛЕНИЕ = {
    "SITE_ENGINE_CONTROL_WRITES": "1",
    "SITE_ENGINE_CONTROL_TOKENS": "t=read,jobs:write,config:write,cache:write,audit:read",
}
ЗАГОЛОВКИ = {"Authorization": "Bearer t"}

# Тела для опроса записывающих маршрутов. Всюду dryRun: проверка описания
# не должна ничего выполнять — иначе тест сам станет источником изменений.
ПРОБНЫЕ_ТЕЛА = {
    "/api/v1/sites/{siteId}/jobs": {"action": "reindex", "dryRun": True},
    "/api/v1/sites/{siteId}/settings": {"changes": {"keep_releases": 5}, "dryRun": True},
    "/api/v1/sites/{siteId}/cache/invalidate": {"scope": "catalog", "dryRun": True},
    "/api/v1/jobs/{jobId}": {},
    "/api/v1/audit": {"limit": 1},
    "/api/v1/metrics": {},
    "/api/v1/compatibility": {},
    "/api/v1/traces/{traceId}": {},
    "/api/v1/content-health": {},
    "/api/v1/content-health/{siteId}": {},
    "/api/v1/reasons": {},
    "/api/v1/playback-policy": {},
}


@pytest.fixture
def описание() -> dict:
    return spec()


@pytest.fixture
def api():
    return create_api(["lords-01"], root=ROOT,
                      loader=lambda p: (InMemoryStore(p.site_id), "тестовый"), env=ВКЛЮЧЁН)


class TestОписание:
    def test_версия_openapi(self, описание):
        assert описание["openapi"].startswith("3.")

    def test_каждый_описанный_маршрут_принадлежит_слою(self, описание):
        """Маршрут, не обслуживаемый ни одним слоем, — обещание без исполнителя."""
        from factory.site_engine.api.openapi import ПУТИ
        assert set(описание["paths"]) == set(ПУТИ) | set(ЗАПИСЬ)

    def test_все_описанные_читающие_маршруты_отвечают(self, описание, api):
        """Описание, обещающее несуществующий маршрут, хуже отсутствия описания."""
        for путь in описание["paths"]:
            if путь in ЗАПИСЬ:
                continue
            конкретный = путь.replace("{siteId}", "lords-01").replace("{titleId}", "нет")
            ответ = api.handle(конкретный)
            assert ответ.status in (200, 404), f"{путь} ответил {ответ.status}"
            if "{titleId}" not in путь:
                assert ответ.status == 200, f"{путь} должен отвечать успехом"

    def test_все_описанные_управляющие_маршруты_отвечают(self, описание):
        """То же требование к записывающему слою, но без побочных действий."""
        control = ControlApi(root=ROOT, env=УПРАВЛЕНИЕ)
        for путь, узел in описание["paths"].items():
            if путь not in ЗАПИСЬ:
                continue
            метод = ЗАПИСЬ[путь]["method"].upper()
            assert метод.lower() in узел, f"{путь}: описан не тот метод"
            конкретный = (путь.replace("{siteId}", "lords-01")
                          .replace("{jobId}", "нет-такого")
                          .replace("{traceId}", "0" * 32)
                          .replace("{siteId}", "lords-01"))
            ответ = control.handle(метод, конкретный,
                                   body=dict(ПРОБНЫЕ_ТЕЛА[путь]), headers=ЗАГОЛОВКИ)
            код = ответ.body.get("error", {}).get("code")
            assert код != "not_found", f"{путь}: описан, но не обслуживается"
            assert ответ.status != 401, f"{путь}: токен со всеми правами получил отказ"

    def test_каждый_маршрут_описывает_ошибку(self, описание):
        for путь, узел in описание["paths"].items():
            for метод, операция in узел.items():
                ответы = операция["responses"]
                if путь in ЗАПИСЬ:
                    # У записи «не туда» менее вероятно, чем «нельзя»: проверяем,
                    # что описан отказ по праву, а не только отсутствие объекта.
                    assert "403" in ответы, f"{путь}.{метод}: не описан отказ по праву"
                    continue
                assert "404" in ответы, f"{путь}: не описано, что бывает при отсутствии"

    def test_страничные_маршруты_описывают_пределы(self, описание):
        узел = описание["paths"]["/api/v1/sites/{siteId}/titles"]["get"]
        limit = next(p for p in узел["parameters"] if p["name"] == "limit")
        assert limit["schema"]["maximum"] >= 1
        assert "400" in узел["responses"], "негодные параметры обязаны быть описаны"

    def test_файл_описания_совпадает_с_порождённым(self, tmp_path, описание):
        """Файл в репозитории не должен отставать от кода."""
        сохранённый = ROOT / "schemas/site-engine/openapi-v1.json"
        assert sorted(json.loads(сохранённый.read_text(encoding="utf-8"))["paths"]) == sorted(
            описание["paths"]
        )


class TestОтветыСоответствуютСхемам:
    def test_ошибка_всегда_одной_формы(self, описание, api):
        схема = описание["components"]["schemas"]["Error"]
        for путь in ("/api/v1/sites/нет", "/api/v1/чего-нет"):
            jsonschema.validate(api.handle(путь).body, схема)

    def test_краткая_карточка_соответствует_схеме(self, описание):
        from datetime import datetime, timezone

        from factory.site_engine.contracts import Title
        from factory.site_engine.store import WriteToken

        схема = описание["components"]["schemas"]["TitleBrief"]
        store = InMemoryStore("lords-01")
        store.put(
            WriteToken("r", "lords-01"),
            [Title(canonical_id="p:1", provider="p", provider_id="1", name="Т",
                   observed_at=datetime(2026, 8, 30, tzinfo=timezone.utc))],
        )
        api = create_api(["lords-01"], root=ROOT, loader=lambda p: (store, "тест"), env=ВКЛЮЧЁН)
        тело = api.handle("/api/v1/sites/lords-01/titles").body
        for карточка in тело["items"]:
            jsonschema.validate(карточка, схема)
