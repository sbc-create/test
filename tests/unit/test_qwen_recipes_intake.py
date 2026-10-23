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
            else f"Теперь по порядку: {b['steps'][i].rstrip('.').lower()}, не торопитесь.",
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
        "intro": "Домашнее блюдо из простых продуктов на обычной кухне.",
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
    res = intake.plan(intake.read_set(d), EXISTING, {})
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
    a = intake.plan(intake.read_set(d), EXISTING, {})
    b = intake.plan(intake.read_set(tgz), EXISTING, {})
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
    res = intake.plan(intake.read_set(tmp_path / "x"), EXISTING, {})
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


# ---------------------------------------------------------------- формат поставки 22.10.2026 (qwen-night/1)
def night_base(n, theme, steps, ings, url="https://example.invalid/r"):
    return {
        "base_recipe_id": f"FD-NIGHT-{n:03d}",
        "theme": theme,
        **({"source_url": url} if url is not None else {}),
        "metadata": {"servings": 4, "cook_time_minutes": 30},
        "locked_ingredients": [
            {"original_name": a, "quantity": q, "unit": u, "notes": note} for a, q, u, note in ings
        ],
        "locked_steps": [{"step_id": k + 1, "instruction": x} for k, x in enumerate(steps)],
    }


def night_set(tmp: Path, bases_variants) -> Path:
    d = tmp / intake.SET_ID
    for sub in ("manifest", "recipes/base_recipes", "variants", "reports"):
        (d / sub).mkdir(parents=True, exist_ok=True)
    (d / "manifest" / "manifest-food-daily-night-001.json").write_text(
        json.dumps({"run_id": intake.SET_ID, "scope": {"total_themes": 3, "total_variants": 15}})
    )
    (d / "reports" / "checkpoint_003.json").write_text("")  # битый отчёт не роняет приём
    for b, vs in bases_variants:
        (d / "recipes/base_recipes" / f"recipe_{b['base_recipe_id']}.json").write_text(
            json.dumps(b, ensure_ascii=False)
        )
        for label in intake.LABELS:
            v = {
                "variant_id": f"{b['base_recipe_id']}-{label}",
                "base_recipe_id": b["base_recipe_id"],
                "variant_type": label,
                "title": b["theme"] + " — компактно",
                **vs.get(label, {}),
            }
            (d / "variants" / f"{v['variant_id']}.json").write_text(
                json.dumps(v, ensure_ascii=False)
            )
    return d


INTRO = "Сытное домашнее блюдо на каждый день из простых продуктов."
GOOD = (
    night_base(
        1,
        "Капуста тушёная с морковью",
        ["Капусту нашинковать, посолить.", "Морковь натереть, тушить с капустой 30 минут."],
        [("Капуста", 500, "г", ""), ("Морковь", 1, "шт.", ""), ("Соль", 1, "ч.л.", "")],
    ),
    {
        "V1": {  # полный пересказ — публикуется
            "intro": INTRO,
            "steps": [
                "1. Тонко нашинкуйте капусту и слегка подсолите.",
                "2. Натрите морковь, затем всё вместе тушите 30 минут под крышкой.",
            ],
        },
        "V5": {  # потерян шаг и время — в архив
            "intro": INTRO,
            "steps": ["Нарезать и тушить."],
        },
        "V3": {"step_sequence": [{"stage": "Нарезка"}]},  # без шагов строками — публиковать нечего
    },
)


def test_night_format_is_normalized_and_one_dish_one_page(tmp_path):
    placeholder = night_base(
        2,
        "Салат из редиса",
        ["Нарезать редис."],
        [("Редис", 200, "г", "")],
        url="_VERIFY_REAL_SOURCE",
    )
    copied = night_base(
        3,
        "Суп из чечевицы с тыквой",
        ["Чечевицу варить 20 минут.", "Добавить тыкву."],
        [("Чечевица", 200, "г", ""), ("Тыква", 300, "г", "")],
    )
    d = night_set(
        tmp_path,
        [
            GOOD,
            (placeholder, {"V1": {"intro": INTRO, "steps": ["Нарежьте редис кружками."]}}),
            (
                copied,
                {"V1": {"intro": INTRO, "steps": ["Чечевицу варить 20 минут.", "Добавить тыкву."]}},
            ),
        ],
    )
    res = intake.plan(intake.read_set(d), {"bestreciept.site": [], "myfood.mobi": []}, {})
    assert res["status"] == "OK" and res["format"] == "qwen-night/1"
    assert res["counts"]["files_base"] == 3 and res["counts"]["files_variants"] == 15
    assert res["counts"]["unreadable_files"] == ["reports/checkpoint_003.json"]
    acc = res["_accepted"]["bestreciept.site"]
    assert [(r["base_id"], r["label"]) for r in acc] == [("FD-NIGHT-001", "V1")]
    rec = acc[0]
    # название — блюдо из базы, а не подпись подачи; количества — из базы
    assert rec["variant"]["title"] == "Капуста тушёная с морковью"
    assert [i["display_name"] for i in rec["variant"]["ingredients"]] == [
        "Капуста",
        "Морковь",
        "Соль",
    ]
    assert [s["base_steps"] for s in rec["variant"]["steps"]] == [[0], [1]]
    why = {x["variant_id"]: x["why"] for x in res["_archive"]}
    assert "потеряно 30" in why["FD-NIGHT-001-V5"] and "нет текста шагов" in why["FD-NIGHT-001-V3"]
    reasons = {x["base_id"]: (x["kind"], x["reason"]) for x in res["deferred"]}
    assert (
        reasons["FD-NIGHT-002"][0] == "rights"
        and "_VERIFY_REAL_SOURCE" in reasons["FD-NIGHT-002"][1]
    )
    assert reasons["FD-NIGHT-003"][0] == "quality" and "дословно" in reasons["FD-NIGHT-003"][1]
    # 15 вариантов учтены: 1 опубликован, 14 — в архиве
    assert res["archived_variants"] + 1 == 15


def test_variant_must_keep_numbers_ingredients_and_honest_intro():
    assert intake.normalize({}) == {}  # пустой вход не ломает normalize
    base_ = {
        "base_id": "x",
        "title": "Рис",
        "servings": 2,
        "steps": ["Рис варить 15 минут, посолить."],
        "ingredients": [{"name": "Рис"}, {"name": "Соль"}],
        "source": {"url": "https://e.invalid"},
    }

    def v(text, intro=INTRO):
        return {
            "variant_id": "x-V1",
            "base_id": "x",
            "label": "V1",
            "title": "Рис",
            "intro": intro,
            "ingredients": [
                {"base_index": 0, "display_name": "Рис"},
                {"base_index": 1, "display_name": "Соль"},
            ],
            "steps": [{"text": text, "base_steps": [0]}],
        }

    assert (
        intake.check_variant(v("Отварите рис до мягкости, подсолив воду, 15 минут."), base_) == []
    )
    assert any(
        "потеряно 15" in e for e in intake.check_variant(v("Отварите рис, подсолив воду."), base_)
    )
    assert any(
        "не используются: Соль" in e
        for e in intake.check_variant(v("Отварите рис 15 минут."), base_)
    )
    bad = intake.check_variant(
        v(
            "Отварите рис до мягкости, подсолив воду, 15 минут.",
            "Делюсь своим рецептом риса на каждый день.",
        ),
        base_,
    )
    assert any("недопустимое" in e for e in bad)


def test_unsure_quantity_is_draft_and_duplicates_match_by_stem():
    b = {
        "base_id": "y",
        "title": "Шуба",
        "servings": 8,
        "steps": ["Собрать."],
        "source": {"url": "https://e.invalid"},
        "ingredients": [
            {"name": "Майонез", "quantity": 1, "unit": "шт.", "note": "вероятно, единица упаковки"}
        ],
    }
    assert any("не подтверждено" in e for e in intake.check_base(b))
    k = intake.title_key
    assert intake.similar(k("Ленивые вареники с творогом"), k("Ленивые вареники из творога"))
    assert intake.similar(k("Плов с курицей"), k("Плов с курицей на сковороде"))
    assert not intake.similar(k("Оладьи из кабачков"), k("Пышные оладьи на кефире"))
    assert not intake.similar(
        k("Овсяное печенье"), k("Тыквенное печенье с шоколадными каплями и пряностями")
    )


# ---------------------------------------------------------------- реальные структуры поставки и редакция
def test_real_variant_structures_are_read_and_outlines_are_not_instructions():
    swe = {
        "steps_with_explanations": [
            {"step": 1, "instruction": "Х", "explanation": "Нашинкуйте капусту."}
        ]
    }
    assert intake.variant_steps(swe) == (["Нашинкуйте капусту."], "steps_with_explanations")
    seq = {"step_sequence": [{"stage": "Нарезка", "steps": ["Нашинковать капусту", "Посолить"]}]}
    assert intake.variant_steps(seq) == (["Нашинковать капусту; Посолить"], "step_sequence")
    only_stages = {"step_sequence": [{"stage": "Нарезка", "steps": []}]}
    assert intake.variant_steps(only_stages)[0] is None
    assert (
        intake.variant_steps({"control_points": [{"step": 1, "control_signs": ["Мягкая"]}]})[0]
        is None
    )
    long_intro = "Подробный рецепт тушёной капусты с морковью для будней."
    assert intake.variant_intro({"intro": "Коротко.", "detailed_intro": long_intro}) == (
        long_intro,
        "detailed_intro",
    )
    assert (
        intake.variant_intro({"detailed_intro": "В этом рецепте я расскажу, как тушить капусту."})[
            1
        ]
        == "detailed_intro"
    )


def test_merged_and_split_steps_are_aligned_and_must_keep_everything():
    base_steps = [
        "Капусту нашинковать, посолить.",
        "Морковь натереть.",
        "Тушить с капустой 30 минут.",
    ]
    merged = ["Нашинкуйте и посолите капусту, натрите морковь.", "Тушите всё вместе 30 минут."]
    assert intake.align(merged, base_steps) == [[0, 1], [2]]
    split = [
        "Нашинкуйте капусту.",
        "Посолите капусту.",
        "Натрите морковь.",
        "Тушите с капустой 30 минут.",
    ]
    assert intake.align(split, base_steps) == [[0], [0], [1], [2]]
    b = {
        "base_id": "z",
        "title": "Капуста",
        "servings": 2,
        "steps": base_steps,
        "ingredients": [{"name": "Капуста"}, {"name": "Морковь"}, {"name": "Соль"}],
        "source": {"url": "https://e.invalid"},
    }

    def v(texts):
        return {
            "variant_id": "z-V1",
            "base_id": "z",
            "label": "V1",
            "title": "Капуста",
            "intro": INTRO,
            "ingredients": [
                {"base_index": k, "display_name": i["name"]} for k, i in enumerate(b["ingredients"])
            ],
            "steps": [
                {"text": t, "base_steps": r}
                for t, r in zip(texts, intake.align(texts, base_steps), strict=True)
            ],
        }

    assert intake.check_variant(v(merged), b) == []
    assert intake.check_variant(v(split), b) == []
    lost = intake.check_variant(
        v(["Нашинкуйте капусту, натрите морковь.", "Тушите всё вместе."]), b
    )
    assert any("потеряно 30" in e for e in lost) and any("посолить" in e for e in lost)


def test_editorial_version_goes_through_the_same_checks_and_is_preferred(tmp_path):
    d = night_set(tmp_path, [GOOD])
    ed = {
        "FD-NIGHT-001": {
            "base_id": "FD-NIGHT-001",
            "intro": INTRO,
            "display_names": {"0": "Капуста белокочанная"},
            "steps": [
                {"text": "Нашинкуйте капусту тонкой соломкой и посолите.", "base_steps": [0]},
                {"text": "Натрите морковь и тушите её с капустой 30 минут.", "base_steps": [1]},
            ],
        }
    }
    res = intake.plan(intake.read_set(d), {"bestreciept.site": [], "myfood.mobi": []}, ed)
    rec = res["_accepted"]["bestreciept.site"][0]
    assert (
        rec["label"] == "ED"
        and rec["variant"]["ingredients"][0]["display_name"] == "Капуста белокочанная"
    )
    bad = {"FD-NIGHT-001": {**ed["FD-NIGHT-001"], "steps": ed["FD-NIGHT-001"]["steps"][:1]}}
    res = intake.plan(intake.read_set(d), {"bestreciept.site": [], "myfood.mobi": []}, bad)
    assert res["_accepted"]["bestreciept.site"][0]["label"] == "V1"  # неполная редакция не проходит
    assert any(x["variant_id"] == "FD-NIGHT-001-ED" for x in res["_archive"])


def test_already_imported_dish_is_not_a_duplicate_of_itself(tmp_path):
    d = night_set(tmp_path, [GOOD])
    own = sorted(intake.own_ids(intake.SET_ID, "FD-NIGHT-001"))[1]  # fdq- — так его сохранил сайт
    key = intake.title_key("Капуста тушёная с морковью")
    res = intake.plan(
        intake.read_set(d), {"bestreciept.site": [("kapusta", key, own)], "myfood.mobi": []}, {}
    )
    assert [r["base_id"] for r in res["_accepted"]["bestreciept.site"]] == ["FD-NIGHT-001"]
    res = intake.plan(
        intake.read_set(d),
        {"bestreciept.site": [("kapusta", key, "fd-other")], "myfood.mobi": []},
        {},
    )
    assert res["deferred"][0]["kind"] == "duplicate"


def test_verb_roots_accept_aspect_pairs_but_not_other_actions():
    def have(text):
        return {intake.root(w) for w in intake.norm(text).split() if intake.VERBISH.search(w)}

    assert intake.same_action("взбить", have("Взбивайте яйца"))
    assert intake.same_action("нарезать", have("Нарежьте лук"))
    assert intake.same_action("натереть", have("Натрите морковь"))
    assert intake.same_action("размять", have("Разомните картофель"))
    assert not intake.same_action("посолить", have("Нарежьте лук"))
