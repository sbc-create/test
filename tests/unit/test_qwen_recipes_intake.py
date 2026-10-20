"""Приёмник набора рецептов Qwen: проверки на синтетическом наборе (создаётся в тесте, нигде не публикуется)."""

import importlib.util
import json
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("intake", ROOT / "tools" / "qwen_recipes_intake.py")
intake = importlib.util.module_from_spec(spec)
spec.loader.exec_module(intake)


def base(bid, title, steps, ings, source=True, oven=None):
    b = {
        "base_id": bid,
        "title": title,
        "servings": 4,
        "total_minutes": 40,
        "ingredients": [{"name": n, "quantity": q, "unit": "g"} for n, q in ings],
        "steps": steps,
    }
    if source:
        b["source"] = {"url": f"https://example.invalid/{bid}"}
    if oven:
        b["oven"] = oven
    return b


def variant(b, label, *, cues=0, text_override=None, extra_ing=False):
    steps = [
        {
            "text": text_override
            if (text_override and i == 0)
            else f"Сделайте шаг {i + 1} аккуратно.",
            "base_steps": [i],
            **({"readiness_cue": "Готово, когда масса однородная."} if i < cues else {}),
        }
        for i in range(len(b["steps"]))
    ]
    ings = [{"base_index": i, "display_name": x["name"]} for i, x in enumerate(b["ingredients"])]
    if extra_ing:
        ings.append({"base_index": len(ings), "display_name": "Мята"})
    return {
        "variant_id": f"{b['base_id']}-{label}",
        "base_id": b["base_id"],
        "label": label,
        "title": b["title"],
        "intro": "Короткое вступление.",
        "ingredients": ings,
        "steps": steps,
    }


def make_set(tmp: Path) -> Path:
    d = tmp / intake.SET_ID
    (d / "base").mkdir(parents=True)
    (d / "variants").mkdir()
    bases = [
        base(
            "b001",
            "Суп с фрикадельками и сладким перцем",
            ["Сварите бульон 20 минут.", "Добавьте перец."],
            [("Фарш", 300), ("Перец", 100)],
        ),  # совпадает с опубликованным на bestreciept.site
        base(
            "b002",
            "Гороховый суп с копчёностями",
            ["Варите горох 60 минут.", "Добавьте копчёности."],
            [("Горох", 200), ("Грудинка", 150)],
        ),
        base(
            "b003",
            "Апельсиновый кекс",
            ["Смешайте тесто.", "Выпекайте при 180 градусах 40 минут."],
            [("Мука", 200), ("Апельсин", 1)],
            oven={"temperatures_c": [180]},
        ),
        base("b004", "Салат без источника", ["Нарежьте овощи."], [("Огурец", 100)], source=False),
    ]
    items = []
    for b in bases:
        (d / "base" / f"{b['base_id']}.json").write_text(json.dumps(b, ensure_ascii=False))
        vs = []
        for label in intake.LABELS:
            v = variant(b, label, cues=1 if label == "V3" else 0)
            if b["base_id"] == "b002" and label == "V3":
                v = variant(
                    b, label, cues=2, text_override="Варите горох 90 минут."
                )  # число не из базы
            if b["base_id"] == "b003" and label == "V1":
                v = variant(b, label, extra_ing=True)  # новый продукт — запрещено
            (d / "variants" / f"{v['variant_id']}.json").write_text(
                json.dumps(v, ensure_ascii=False)
            )
            vs.append(
                {
                    "variant_id": v["variant_id"],
                    "label": label,
                    "file": f"variants/{v['variant_id']}.json",
                }
            )
        items.append({"base_id": b["base_id"], "file": f"base/{b['base_id']}.json", "variants": vs})
    (d / "manifest.json").write_text(
        json.dumps(
            {"set_id": intake.SET_ID, "base_count": 4, "variant_count": 20, "items": items},
            ensure_ascii=False,
        )
    )
    return d


EXISTING = {
    "bestreciept.site": [
        ("sup-s-frikadelkami", intake.title_key("Суп с фрикадельками и сладким перцем"))
    ],
    "myfood.mobi": [],
}


def test_plan_routes_picks_one_variant_and_defers_honestly(tmp_path):
    d = make_set(tmp_path)
    res = intake.plan(intake.read_set(d), EXISTING)
    assert res["status"] == "OK"
    assert res["counts"] == {
        "manifest_base": 4,
        "manifest_variants": 20,
        "files_base": 4,
        "files_variants": 20,
    }
    acc = res["_accepted"]
    assert [r["base_id"] for r in acc["bestreciept.site"]] == ["b002"]
    assert [r["base_id"] for r in acc["myfood.mobi"]] == ["b003"]
    # из пяти вариантов подачи публикуется один: V3 у b002 отклонён (число не из базы), выбран лучший из остальных
    assert acc["bestreciept.site"][0]["label"] != "V3"
    assert (
        acc["myfood.mobi"][0]["label"] == "V3"
    )  # больше признаков готовности; V1 с лишним продуктом отклонён
    reasons = {x["base_id"]: x["reason"] for x in res["deferred"]}
    assert "BLOCKED_RIGHTS" in reasons["b004"]
    assert "совпадает с опубликованным" in reasons["b001"]
    assert (
        next(x for x in res["deferred"] if x["base_id"] == "b001")["update_candidate"]
        == "sup-s-frikadelkami"
    )
    why = {x["variant_id"]: x["why"] for x in res["_archive"]}
    assert "число 90" in why["b002-V3"] and "без новых продуктов" in why["b003-V1"]
    # все 20 вариантов учтены: 2 опубликованы, остальные — в архиве (у b004 — как непринятая база)
    assert res["archived_variants"] + sum(res["accepted"].values()) == 20


def test_plan_is_deterministic_and_reads_tar(tmp_path):
    d = make_set(tmp_path)
    tgz = tmp_path / f"{intake.SET_ID}.tar.gz"
    with tarfile.open(tgz, "w:gz") as t:
        t.add(d, arcname=intake.SET_ID)
    a = intake.plan(intake.read_set(d), EXISTING)
    b = intake.plan(intake.read_set(tgz), EXISTING)
    assert [r["digest"] for r in a["_accepted"]["myfood.mobi"]] == [
        r["digest"] for r in b["_accepted"]["myfood.mobi"]
    ]
    out = intake.write(b, tmp_path / "out")
    assert (tmp_path / "out" / "batches" / "myfood.mobi" / "b003.json").exists()
    assert (
        "_accepted" not in json.loads((tmp_path / "out" / "report.json").read_text())
        and out["status"] == "OK"
    )


def test_unknown_layout_is_blocked_input_not_guessed(tmp_path):
    (tmp_path / "x").mkdir()
    (tmp_path / "x" / "recipes.json").write_text(json.dumps([{"name": "что-то"}]))
    res = intake.plan(intake.read_set(tmp_path / "x"), EXISTING)
    assert res["status"] == "BLOCKED_INPUT" and res["inspect"]["json_files"] == 1


def test_liver_is_not_baking():
    """«печень» (субпродукт) ≠ «печенье»: куриная печень — повседневное блюдо bestreciept.site."""
    liver = base(
        "b050", "Куриная печень с луком", ["Обжарьте печень с луком 10 минут."], [("Печень", 500)]
    )
    v = variant(liver, "V1")
    assert intake.route(liver, v) == "bestreciept.site"
    for title in ("Овсяное печенье", "Печенья с изюмом", "Ассорти печений"):
        b = base("b051", title, ["Смешайте тесто."], [("Мука", 200)])
        assert intake.route(b, variant(b, "V1")) == "myfood.mobi", title
