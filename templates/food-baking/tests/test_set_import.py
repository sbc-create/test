"""Импорт набора Qwen в книгу выпечки: пробная партия, повтор без дублей, правки редактора не затираются.
Данные — синтетическая запись в формате приёмника; все каталоги временные, файлы сайта не меняются."""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bakebook import drafts, set_import  # noqa: E402


def rec(bid="b003", title="Апельсиновый кекс", label="V3", text="Соедините муку с маслом, сахаром и яйцами."):
    base = {
        "base_id": bid,
        "title": title,
        "servings": 8,
        "total_minutes": 70,
        "ingredients": [
            {"name": "Пшеничная мука", "quantity": 200, "unit": "г"},
            {"name": "Сливочное масло", "quantity": 150, "unit": "г"},
            {"name": "Куриные яйца", "quantity": 3, "unit": "шт"},
            {"name": "Апельсин", "quantity": 1, "unit": "шт"},
        ],
        "steps": ["Смешайте муку, масло и яйца.", "Добавьте цедру апельсина.", "Выпекайте при 180 градусах 45 минут."],
        "oven": {"temperatures_c": [180], "bake_minutes": [45], "form": "форма для кекса"},
        "source": {"url": "https://example.invalid/apelsinovyj-keks"},
    }
    variant = {
        "variant_id": f"{bid}-{label}",
        "base_id": bid,
        "label": label,
        "title": title,
        "intro": "Кекс на сливочном масле с цедрой апельсина: плотный, влажный и ароматный.",
        "ingredients": [{"base_index": i, "display_name": x["name"]} for i, x in enumerate(base["ingredients"])],
        "steps": [
            {"text": text, "base_steps": [0]},
            {"text": "Натрите цедру прямо в тесто и перемешайте.", "base_steps": [1]},
            {
                "text": "Переложите тесто в форму и пеките при 180 °C 45 минут.",
                "base_steps": [2],
                "readiness_cue": "Шпажка из центра выходит сухой.",
            },
        ],
    }
    return {
        "set_id": "QWEN-NIGHT-RECIPES-100X5-001",
        "base_id": bid,
        "variant_id": variant["variant_id"],
        "label": label,
        "site": "myfood.mobi",
        "base": base,
        "variant": variant,
        "digest": "d3",
    }


def write(d, *recs):
    d.mkdir(exist_ok=True)
    for r in recs:
        (d / f"{r['base_id']}.json").write_text(json.dumps(r, ensure_ascii=False))
    return d


@pytest.fixture
def iso(tmp_path, monkeypatch):
    for sub in ("facts", "drafts", "private"):
        (tmp_path / sub).mkdir()
    content = tmp_path / "content.json"
    content.write_text(json.dumps({"site_id": "food-baking", "items": [{"slug": "limonnyj-keks", "record_id": "x"}]}))
    for mod in (drafts, set_import):
        monkeypatch.setattr(mod, "FACTS", tmp_path / "facts")
        monkeypatch.setattr(mod, "PRIVATE", tmp_path / "private")
    monkeypatch.setattr(drafts, "DRAFTS", tmp_path / "drafts")
    monkeypatch.setattr(drafts, "CONTENT", content)
    monkeypatch.setattr(set_import, "LEDGER", tmp_path / "ledger.json")
    monkeypatch.setattr(set_import, "BACKUPS", tmp_path / "backups")
    return tmp_path


def test_files_follow_template_format():
    rid, facts, draft = set_import.to_files(rec())
    assert rid.startswith("fbq-") and facts["group_hint"] == "keks" and draft["slug"] == "apelsinovyj-keks"
    assert facts["oven"]["temperatures"] == [{"value_c": 180, "step": 2}]
    assert facts["oven"]["bake_times"] == [{"min": 45, "max": None, "step": 2}]
    assert [i["unit"] for i in facts["ingredients"]] == ["g", "g", "pcs", "pcs"]


def test_trial_full_repeat_and_editor_protection(iso):
    batch = write(iso / "batch", rec(), rec("b011", "Ореховое печенье"))
    assert set_import.run(batch, dry_run=True)["n_created"] == 2 and not list((iso / "drafts").iterdir())
    assert set_import.run(batch, limit=1)["n_created"] == 1
    full = set_import.run(batch)
    assert full["n_created"] == 1 and full["n_unchanged"] == 1
    assert set_import.run(batch)["n_unchanged"] == 2
    assert len(list((iso / "drafts").glob("*.json"))) == 2
    # редактор поправил черновик — новый импорт его не трогает
    d = next((iso / "drafts").glob("*.json"))
    j = json.loads(d.read_text())
    j["intro"] = "Редактор переписал вступление кекса: плотный, влажный, с ароматом апельсина."
    d.write_text(json.dumps(j, ensure_ascii=False))
    res = set_import.run(
        write(
            batch,
            rec(text="Смешайте муку с мягким маслом и яйцами."),
            rec("b011", "Ореховое печенье", text="Смешайте муку с мягким маслом и яйцами."),
        )
    )
    assert res["n_deferred"] == 1 and "редактор" in res["deferred"][0]["reason"] and res["n_updated"] == 1


def test_invented_number_rejected_and_files_rolled_back(iso):
    bad = rec("b012", "Кекс с изюмом", text="Смешайте 300 г муки с маслом и яйцами.")
    res = set_import.run(write(iso / "b", bad))
    assert res["n_deferred"] == 1 and "300" in res["deferred"][0]["reason"]
    assert not list((iso / "facts").iterdir()) and not list((iso / "private").iterdir())


def test_taken_slug_and_unknown_group_deferred(iso):
    res = set_import.run(write(iso / "b", rec("b013", "Лимонный кекс")))
    assert res["n_deferred"] == 1 and "занят" in res["deferred"][0]["reason"]
    res = set_import.run(write(iso / "c", rec("b014", "Овсяная гранола")))
    assert "раздел" in res["deferred"][0]["reason"]
