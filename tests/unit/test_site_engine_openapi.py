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
from factory.site_engine.api.openapi import spec
from factory.site_engine.store import InMemoryStore

ROOT = Path(__file__).resolve().parents[2]
ВКЛЮЧЁН = {"SITE_ENGINE_API_ENABLED": "1", "SITE_ENGINE_ENVIRONMENT": "test"}


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

    def test_все_описанные_маршруты_отвечают(self, описание, api):
        """Описание, обещающее несуществующий маршрут, хуже отсутствия описания."""
        for путь in описание["paths"]:
            конкретный = путь.replace("{siteId}", "lords-01").replace("{titleId}", "нет")
            ответ = api.handle(конкретный)
            assert ответ.status in (200, 404), f"{путь} ответил {ответ.status}"
            if "{titleId}" not in путь:
                assert ответ.status == 200, f"{путь} должен отвечать успехом"

    def test_каждый_маршрут_описывает_ошибку(self, описание):
        for путь, узел in описание["paths"].items():
            ответы = узел["get"]["responses"]
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
