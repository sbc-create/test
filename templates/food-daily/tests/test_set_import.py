"""Импорт набора Qwen в food-daily: пробная партия, повтор без дублей, правки редактора не затираются.
Данные — синтетическая запись в формате приёмника (только в тесте, на сайт не попадает)."""

import json

import pytest

from fooddaily import editorial, set_import


def rec(bid="b002", title="Гороховый суп с копчёностями", label="V2", text="Замочите горох и варите до мягкости."):
    base = {
        "base_id": bid,
        "title": title,
        "servings": 4,
        "total_minutes": 90,
        "ingredients": [
            {"name": "Горох колотый", "quantity": 200, "unit": "г"},
            {"name": "Копчёная грудинка", "quantity": 150, "unit": "г"},
            {"name": "Соль", "quantity": None, "unit": "по вкусу"},
        ],
        "steps": ["Варите горох 60 минут.", "Обжарьте грудинку.", "Соедините и посолите."],
        "source": {"url": "https://example.invalid/gorohovyj-sup"},
    }
    variant = {
        "variant_id": f"{bid}-{label}",
        "base_id": bid,
        "label": label,
        "title": title,
        "intro": "Густой гороховый суп на копчёной грудинке: горох разваривается, а грудинка даёт аромат.",
        "ingredients": [{"base_index": i, "display_name": x["name"]} for i, x in enumerate(base["ingredients"])],
        "steps": [
            {"text": text, "base_steps": [0], "readiness_cue": "Горох разваривается."},
            {"text": "Обжарьте грудинку до румяного цвета.", "base_steps": [1]},
            {"text": "Соедините суп с грудинкой и посолите по вкусу.", "base_steps": [2]},
        ],
    }
    return {
        "set_id": "QWEN-NIGHT-RECIPES-100X5-001",
        "base_id": bid,
        "variant_id": variant["variant_id"],
        "label": label,
        "site": "bestreciept.site",
        "base": base,
        "variant": variant,
        "digest": "d1",
    }


def write(d, *recs):
    d.mkdir(exist_ok=True)
    for r in recs:
        (d / f"{r['base_id']}.json").write_text(json.dumps(r, ensure_ascii=False))
    return d


@pytest.fixture
def isolated(tmp_store, tmp_path, monkeypatch):
    monkeypatch.setattr(set_import, "VAR", tmp_path / "var")
    return tmp_store


def test_payload_maps_facts_and_category():
    p = set_import.to_payload(rec())
    assert p["draft"]["slug"] == "gorohovyj-sup-s-kopchenostyami"
    assert p["draft"]["category"] == "supy" and p["draft"]["meal"] == "lunch"
    assert [i["unit"] for i in p["facts"]["ingredients"]] == ["g", "g", "to_taste"]
    assert "Набор QWEN-NIGHT-RECIPES-100X5-001" in p["draft"]["editor_notes"][0]  # происхождение — только внутри


def test_trial_then_full_then_repeat_without_duplicates(isolated, tmp_path):
    batch = write(tmp_path / "batch", rec(), rec("b007", "Курица с рисом в духовке"))
    dry = set_import.run(batch, dry_run=True, st=isolated)
    assert dry["n_created"] == 2 and dry["backup"] is None
    trial = set_import.run(batch, limit=1, st=isolated)
    assert trial["n_created"] == 1 and trial["backup"] and (tmp_path / "var" / "backups").is_dir()
    full = set_import.run(batch, st=isolated)
    assert full["n_created"] == 1 and full["n_unchanged"] == 1
    again = set_import.run(batch, st=isolated)
    assert again["n_unchanged"] == 2 and again["n_created"] == 0
    n = isolated.db.execute("SELECT COUNT(*) FROM content WHERE dedupe_key LIKE 'qwen-set:%'").fetchone()[0]
    assert n == 2
    # исправленный вариант того же блюда — новая версия, а не новая страница
    upd = set_import.run(write(batch, rec(text="Замочите горох и варите до полной мягкости.")), st=isolated)
    assert upd["n_updated"] == 1
    assert isolated.db.execute("SELECT COUNT(*) FROM content WHERE dedupe_key LIKE 'qwen-set:%'").fetchone()[0] == 2


def test_editor_changes_are_not_overwritten(isolated, tmp_path):
    batch = write(tmp_path / "batch", rec())
    set_import.run(batch, st=isolated)
    cid = isolated.db.execute("SELECT content_id FROM content WHERE dedupe_key LIKE 'qwen-set:%'").fetchone()[0]
    cur = isolated.current(cid)["current_version"]
    editorial.revise(
        isolated,
        cid,
        {"intro": "Редактор переписал вступление: суп густой и сытный, на грудинке."},
        base_version=cur,
        actor="editor",
        reason="правка",
    )
    res = set_import.run(write(batch, rec(text="Другой текст первого шага про горох.")), st=isolated)
    assert res["n_deferred"] == 1 and "редактор" in res["deferred"][0]["reason"]


def test_unknown_unit_and_taken_slug_are_deferred(isolated, tmp_path):
    bad = rec("b009", "Суп с фрикадельками")
    bad["base"]["ingredients"][0]["unit"] = "горсть"
    res = set_import.run(write(tmp_path / "b", bad), st=isolated)
    assert res["n_deferred"] == 1 and "единица" in res["deferred"][0]["reason"]
    isolated.ensure_content(content_id="other", slug="gorohovyj-sup-s-kopchenostyami", dedupe_key="other")
    res = set_import.run(write(tmp_path / "c", rec()), st=isolated)
    assert res["n_deferred"] == 1 and "занят" in res["deferred"][0]["reason"]


def test_chicken_liver_is_everyday_dish_tagged_chicken_only_by_meat():
    r = rec("b020", "Куриная печень с луком")
    r["base"]["ingredients"] = [
        {"name": "Куриная печень", "quantity": 500, "unit": "г"},
        {"name": "Репчатый лук", "quantity": 2, "unit": "шт"},
        {"name": "Соль", "quantity": None, "unit": "по вкусу"},
    ]
    p = set_import.to_payload(r)
    assert p["draft"]["category"] == "vtorye-blyuda" and "kurica" in p["draft"]["tags"]
    eggs = rec("b021", "Оладьи на кефире")
    eggs["base"]["ingredients"] = [
        {"name": "Куриные яйца", "quantity": 2, "unit": "шт"},
        {"name": "Кефир", "quantity": 500, "unit": "мл"},
        {"name": "Соль", "quantity": None, "unit": "по вкусу"},
    ]
    tags = set_import.to_payload(eggs)["draft"]["tags"]
    assert "kurica" not in tags and "yajca" in tags


def test_slice_can_and_head_units_from_the_delivery_are_known():
    """Поставка 22.10: «2 ломтика» хлеба, «1 банки» горошка, «1 кочан» капусты — единицы, которые сайт
    уже показывает (ломт., банка, гол.); раньше такие блюда откладывались как «неизвестная единица»."""
    r = rec()
    r["base"]["ingredients"] += [
        {"name": "Хлеб белый", "quantity": 2, "unit": "ломтика"},
        {"name": "Горошек консервированный", "quantity": 1, "unit": "банки"},
        {"name": "Капуста белокочанная", "quantity": 1, "unit": "кочан"},
    ]
    r["variant"]["ingredients"] = [
        {"base_index": i, "display_name": x["name"]} for i, x in enumerate(r["base"]["ingredients"])
    ]
    units = [i["unit"] for i in set_import.to_payload(r)["facts"]["ingredients"][-3:]]
    assert units == ["slice", "can", "head"]


def test_wheat_flour_and_syrniki_do_not_tag_millet_or_cheese():
    """«Мука пшеничная» не делает блюдо «с пшеном», «сырники» — «с сыром» (блины и сырники поставки 22.10)."""
    r = rec(title="Сырники из творога на сковороде")
    r["base"]["ingredients"] = [
        {"name": "Творог", "quantity": 500, "unit": "г"},
        {"name": "Мука пшеничная", "quantity": 3, "unit": "ст.л."},
        {"name": "Соль", "quantity": None, "unit": "по вкусу"},
    ]
    tags = set_import.to_payload(r)["draft"]["tags"]
    assert "tvorog" in tags and "pshyono" not in tags and "syr" not in tags
    r = rec(title="Пшённая каша с сыром")
    assert {"pshyono", "syr"} <= set(set_import.to_payload(r)["draft"]["tags"])


NUTRITION = {
    "kcal_per_serving": 310,
    "protein_g": 14,
    "fat_g": 11.5,
    "carbs_g": 38,
    "method": "Расчёт по составу: сумма по ингредиентам / число порций",
    "data_source": "таблица состава продуктов (образец для теста)",
    "approximate": True,
}


def test_nutrition_and_image_job_survive_import_and_reach_page_markup_and_card(app):
    """qwen-dish/1: принятый приёмником расчёт калорийности и описание подачи сохраняются в фактах,
    страница и Recipe-разметка показывают одно и то же; пересчёт порций меняет «всего», не «на порцию»."""
    from fooddaily import media, seo

    r0 = rec()
    r0["base"]["nutrition"] = NUTRITION
    r0["base"]["image_job"] = {"look": "Густой суп в глубокой тарелке", "alt": "Гороховый суп в тарелке"}
    facts = set_import.to_payload(r0)["facts"]
    assert facts["nutrition"] == NUTRITION and facts["image_job"]["alt"] == "Гороховый суп в тарелке"
    no_src = rec()
    no_src["base"]["nutrition"] = {**NUTRITION, "data_source": ""}
    assert "nutrition" not in set_import.to_payload(no_src)["facts"]  # без основания расчёта — не переносится

    r = next(x for x in app.site.recipes if x.yield_n == 4)
    saved = dict(r.raw["facts"])
    try:
        r.raw["facts"]["nutrition"] = NUTRITION
        r.raw["facts"]["image_job"] = facts["image_job"]
        assert r.nutrition["kcal"] == 310 and r.nutrition["kcal_total"] == 1240
        html = app.route(r.url, {})[1]
        assert "≈&nbsp;310 <small>ккал на порцию</small>" in html and 'data-kcal-total="1240"' in html
        assert "Калорийность примерная: расчёт по составу" in html and "таблица состава продуктов" in html
        ld = seo.recipe_ld(app.site, r)["nutrition"]
        assert ld == {
            "@type": "NutritionInformation",
            "servingSize": "1 порция",
            "calories": "310 ккал",
            "proteinContent": "14 г",
            "fatContent": "11.5 г",
            "carbohydrateContent": "38 г",
        }
        cat = app.route(f"/recepty/{r.category}/", {})[1]
        assert "≈&nbsp;310&nbsp;ккал" in cat
        j = media.job(app.site, r)
        assert j["alt"] == "Гороховый суп в тарелке" and "Густой суп в глубокой тарелке." in j["prompt"]
        assert j["recipe_id"] == r.raw["content_id"]
    finally:
        r.raw["facts"] = saved
    assert r.nutrition is None and "ккал" not in app.route(r.url, {})[1]
