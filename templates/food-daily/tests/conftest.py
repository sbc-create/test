import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@pytest.fixture
def tmp_store(tmp_path, monkeypatch):
    """Изолированная БД food-daily во временном каталоге — тесты не трогают preview."""
    from fooddaily import pipeline, qwen

    monkeypatch.setattr(pipeline, "DB_PATH", tmp_path / "db" / "food-daily.sqlite3")
    monkeypatch.setattr(qwen, "QDIR", tmp_path / "qwen")
    return pipeline.open_store()


@pytest.fixture(scope="session")
def site():
    from fooddaily.views import Site

    return Site()


@pytest.fixture(scope="session")
def app():
    from fooddaily.server import App

    return App()


FACTS = {
    "source_url": "https://example.invalid/r/1",
    "canonical_url": None,
    "title": "Тестовые сырники",
    "servings": 2,
    "servings_raw": "2",
    "prep_minutes": None,
    "cook_minutes": 20,
    "total_minutes": 20,
    "ingredients": [
        {
            "raw": "Творог, 200 г",
            "name": "Творог",
            "quantity": 200.0,
            "quantity_max": None,
            "unit": "g",
            "scalable": True,
            "note": None,
        },
        {
            "raw": "Яйцо, 1 шт",
            "name": "Яйцо",
            "quantity": 1.0,
            "quantity_max": None,
            "unit": "pcs",
            "scalable": True,
            "note": None,
        },
    ],
    "steps": [
        "Смешайте творог с яйцом в миске до однородной массы без комочков совсем.",
        "Жарьте на сковороде по 3 минуты с каждой стороны на среднем огне до корочки.",
    ],
    "category": None,
    "cuisine": None,
    "keywords": [],
    "method_hints": [],
    "image_present": False,
    "extracted_with": "json-ld",
    "parser_version": "t",
    "remarks": [],
    "content_hash": "h1",
    "topic_id": "syrniki",
}


@pytest.fixture
def record(tmp_store):
    st = tmp_store
    st.db.execute(
        "INSERT INTO records VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            "rec-test",
            "food-daily",
            "eda-rambler",
            FACTS["source_url"],
            FACTS["source_url"],
            None,
            200,
            "2026-10-11T00:00:00Z",
            "h1",
            "t",
            "json-ld",
            1,
            json.dumps(FACTS, ensure_ascii=False),
            "[]",
            None,
            None,
            "syrniki:abc",
            "extracted",
        ),
    )
    return "rec-test"


def good_response(job: dict) -> dict:
    return {
        "schema_version": 1,
        "job_id": job["job_id"],
        "base_version": job["base_version"],
        "producer": {"provider": "test", "model": "test", "mode": "manual_standin"},
        "draft": {
            "title": "Сырники для теста",
            "slug": "test-syrniki",
            "seo_title": "Тестовые сырники на сковороде",
            "seo_description": "Описание тестовых сырников достаточно длинное, чтобы пройти минимальную длину схемы.",
            "intro": "Вступление к тестовому рецепту сырников, которое длиннее сорока знаков.",
            "ingredients": [
                {"fact_index": 0, "display_name": "Творог"},
                {"fact_index": 1, "display_name": "Яйцо"},
            ],
            "steps": [
                {"text": "Соедините творог и яйцо, вымешайте массу.", "source_steps": [0]},
                {"text": "Обжарьте сырники, на сторону уйдёт 3 минуты.", "source_steps": [1]},
            ],
            "tips": [],
            "substitutions": [],
            "category": "zavtraki",
            "meal": "breakfast",
            "tags": ["tvorog"],
            "editor_notes": [],
        },
    }
