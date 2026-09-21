"""Различимость и отрисовка шаблонных пакетов.

Главная проверка здесь — не «пакеты различны», а «проверка умеет падать».
Метрика, которая никогда не срабатывает, ничего не доказывает: поэтому тесты
подсовывают ей копию пакета и копию с перекрашенными токенами и требуют, чтобы
оба случая были пойманы.
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import shutil

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ЯДРО = КОРЕНЬ / "factory" / "templates" / "lords" / "shared"
ПАКЕТЫ = КОРЕНЬ / "factory" / "templates" / "lords"


def _загрузить(имя: str, файл: pathlib.Path):
    spec = importlib.util.spec_from_file_location(имя, файл)
    модуль = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(модуль)
    return модуль


distinctness = _загрузить("lords_distinctness", ЯДРО / "distinctness.py")
render = _загрузить("lords_render", ЯДРО / "render.py")


def пакеты() -> list[pathlib.Path]:
    return sorted(p for p in ПАКЕТЫ.iterdir() if p.is_dir() and p.name[:1] == "T"
                  and p.name[1:4].isdigit())


@pytest.fixture(scope="module")
def фикстура() -> dict:
    return json.loads((ЯДРО / "test-fixtures" / "catalog.json").read_text(encoding="utf-8"))


# --- различимость -----------------------------------------------------------

def test_shipped_templates_are_distinct():
    отчёт = distinctness.проверить(пакеты())
    assert отчёт["PASS"], отчёт["violations"] or отчёт["color_only_pairs"]
    assert отчёт["COLOR_ONLY_VARIANTS"] == 0
    assert отчёт["HOME_BLOCK_ORDER_DUPLICATES"] == 0


def test_exact_copy_is_caught(tmp_path):
    """Копия пакета обязана быть поймана как нарушение."""
    оригинал = пакеты()[0]
    копия = tmp_path / "T099-copy"
    shutil.copytree(оригинал, копия)
    манифест = json.loads((копия / "template.json").read_text(encoding="utf-8"))
    манифест["template_id"] = "T099"
    манифест["slug"] = "copy-of-original"
    (копия / "template.json").write_text(json.dumps(манифест, ensure_ascii=False), encoding="utf-8")

    отчёт = distinctness.проверить([оригинал, копия])
    assert not отчёт["PASS"], "копия пакета не была поймана"
    assert отчёт["PAIRWISE_SIMILARITY_VIOLATIONS"] >= 1
    assert отчёт["HOME_BLOCK_ORDER_DUPLICATES"] >= 1


def test_recolour_only_is_caught_as_color_variant(tmp_path):
    """Перекрашенная копия — это не новый шаблон."""
    оригинал = пакеты()[0]
    копия = tmp_path / "T098-recolour"
    shutil.copytree(оригинал, копия)
    манифест = json.loads((копия / "template.json").read_text(encoding="utf-8"))
    манифест["template_id"] = "T098"
    манифест["slug"] = "recoloured"
    (копия / "template.json").write_text(json.dumps(манифест, ensure_ascii=False), encoding="utf-8")
    токены = (копия / "tokens.css").read_text(encoding="utf-8")
    (копия / "tokens.css").write_text(
        токены.replace("--bg:#070d0a", "--bg:#1a0707"), encoding="utf-8")

    отчёт = distinctness.проверить([оригинал, копия])
    assert отчёт["COLOR_ONLY_VARIANTS"] >= 1, "отличие только цветом не поймано"
    assert not отчёт["PASS"]


def test_signature_includes_more_than_colour():
    """Цвет — лишь одна составляющая подписи, иначе метрику легко обмануть."""
    подпись = distinctness.подпись(пакеты()[0])
    цветовые = [п for п in подпись["features"] if п.startswith(("фон:", "зелёный:"))]
    assert len(цветовые) <= 2
    assert len(подпись["features"]) >= 12, "подпись слишком бедная, чтобы что-то доказывать"


# --- отрисовка ---------------------------------------------------------------

@pytest.mark.parametrize("пакет", пакеты(), ids=lambda p: p.name[:4])
def test_package_renders_and_is_closed_to_indexing(пакет, фикстура):
    html = render.отрисовать(пакет, фикстура, ЯДРО)
    assert '<meta name="robots" content="noindex, nofollow">' in html, \
        "индексация обязана оставаться закрытой в каждом пакете"
    assert 'rel="canonical"' in html
    assert html.count("<h1") <= 1, "на странице не должно быть двух h1"


@pytest.mark.parametrize("пакет", пакеты(), ids=lambda p: p.name[:4])
def test_package_declares_every_required_field(пакет):
    манифест = json.loads((пакет / "template.json").read_text(encoding="utf-8"))
    обязательные = {
        "template_id", "slug", "version", "family", "title", "brand", "footer",
        "design_intent", "primary_user_journey", "card_grammar", "green_identity",
        "navigation", "home_block_order",
    }
    отсутствуют = обязательные - set(манифест)
    assert not отсутствуют, f"{пакет.name}: в паспорте нет полей {sorted(отсутствуют)}"
    assert манифест["template_id"] == пакет.name[:4]
    assert пакет.name.endswith(манифест["slug"])


@pytest.mark.parametrize("пакет", пакеты(), ids=lambda p: p.name[:4])
def test_package_has_no_markup_of_its_own(пакет):
    """Пакет объявляет композицию, а не разметку: иначе это пятьдесят копий DOM."""
    for файл in пакет.iterdir():
        if файл.suffix in (".html", ".htm", ".jinja", ".j2"):
            pytest.fail(f"{пакет.name}: пакет содержит разметку {файл.name}")


def test_renderer_hides_block_without_enough_data(фикстура):
    """Блок с нехваткой данных скрывается, а не рисует пустые ячейки."""
    бедная = dict(фикстура)
    бедная["items"] = фикстура["items"][:2]
    настройка = {"заголовок": "Мало данных", "грамматика": "poster", "минимум": 6, "максимум": 12}
    assert render.блок_сетка(бедная, настройка) == ""


def test_feed_skips_items_without_proven_date(фикстура):
    """В ленту свежести не попадает запись с оценочной датой."""
    подделка = dict(фикстура)
    подделка["items"] = [
        {**фикстура["items"][0], "published_at": "2026-09-20T00:00:00Z",
         "published_at_estimated": True},
    ]
    настройка = {"заголовок": "Новое", "грамматика": "compact", "минимум": 1, "максимум": 5}
    assert render.блок_лента(подделка, настройка) == ""


def test_escaping_is_applied(фикстура):
    злая = {**фикстура["items"][0], "title": '<script>alert(1)</script>'}
    html = render.карточка_постер(злая)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
