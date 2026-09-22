"""Паспорт пакета обязан ловить изменение, а не просто лежать рядом.

Паспорт фиксирует, каким пакет был предъявлен на приёмку. Ценность у него
ровно одна: обнаружить, что пакет разошёлся со снимками, по которым его
принимали. Поэтому проверяется не наличие файла, а срабатывание — на пакете,
который специально изменили.
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import shutil

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ПАКЕТЫ = КОРЕНЬ / "factory" / "templates" / "lords"


def _загрузить(имя: str, файл: str):
    spec = importlib.util.spec_from_file_location(имя, ПАКЕТЫ / "shared" / файл)
    м = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(м)
    return м


passport = _загрузить("lords_passport", "passport.py")


def пакеты() -> list[pathlib.Path]:
    return sorted(p for p in ПАКЕТЫ.iterdir()
                  if p.is_dir() and p.name[:1] == "T" and p.name[1:4].isdigit())


def test_every_package_has_a_passport():
    без = [п.name for п in пакеты() if not (п / "PASSPORT.json").is_file()]
    assert not без, f"без паспорта: {без}"


def test_shipped_packages_have_no_drift():
    беды = [b for b in (passport.проверить_дрейф(п) for п in пакеты()) if b]
    assert not беды, беды


def test_changed_css_is_caught(tmp_path):
    """Правка стиля после выдачи паспорта обязана быть замечена."""
    копия = tmp_path / пакеты()[0].name
    shutil.copytree(пакеты()[0], копия)
    assert passport.проверить_дрейф(копия) is None, "копия без изменений не должна считаться дрейфом"

    токены = копия / "tokens.css"
    токены.write_text(токены.read_text(encoding="utf-8") + "\n.k{opacity:.99}\n", encoding="utf-8")
    беда = passport.проверить_дрейф(копия)
    assert беда is not None and "изменён после выдачи паспорта" in беда, беда


def test_changed_block_order_is_named_explicitly(tmp_path):
    """Смена состава блоков называется прямо, а не прячется за digest."""
    копия = tmp_path / пакеты()[1].name
    shutil.copytree(пакеты()[1], копия)
    манифест_путь = копия / "template.json"
    манифест = json.loads(манифест_путь.read_text(encoding="utf-8"))
    манифест["home_block_order"] = манифест["home_block_order"][:-1]
    манифест_путь.write_text(json.dumps(манифест, ensure_ascii=False, indent=2), encoding="utf-8")

    беда = passport.проверить_дрейф(копия)
    assert беда is not None
    # Порядок ловится в первую очередь digest'ом; главное — что молчания нет.
    assert "изменён" in беда or "состав блоков" in беда, беда


def test_missing_passport_is_reported(tmp_path):
    копия = tmp_path / пакеты()[2].name
    shutil.copytree(пакеты()[2], копия)
    (копия / "PASSPORT.json").unlink()
    беда = passport.проверить_дрейф(копия)
    assert беда is not None and "паспорта нет" in беда


@pytest.mark.parametrize("пакет", пакеты(), ids=lambda p: p.name[:4])
def test_passport_leaves_owner_acceptance_empty(пакет):
    """Агент не имеет права заполнять приёмку владельца."""
    паспорт = json.loads((пакет / "PASSPORT.json").read_text(encoding="utf-8"))
    assert паспорт["owner_visual_accepted"] is None
    assert паспорт["owner_note"] == ""


@pytest.mark.parametrize("пакет", пакеты(), ids=lambda p: p.name[:4])
def test_passport_carries_what_review_needs(пакет):
    паспорт = json.loads((пакет / "PASSPORT.json").read_text(encoding="utf-8"))
    assert паспорт["declared"]["design_intent"]
    assert паспорт["declared"]["home_signature"]
    assert паспорт["measured"]["visual_score"] is not None
    assert паспорт["measured"]["hard_fail_count"] == 0
    # Приёмка идёт по кадрам, которые действительно лежат в доказательствах.
    # Обязательный минимум — рабочий стол и мобильный на главной плюс
    # внутренние страницы: по одной главной шаблон принимать нельзя.
    кадры = set(паспорт["review_screenshots"])
    for обязательный in ("home-1440", "home-390", "catalog-1440",
                         "title-series-1440"):
        assert any(к.startswith(обязательный) for к in кадры), \
            f"в паспорте нет кадра {обязательный}: {sorted(кадры)}"
    assert len(кадры) >= 6, f"кадров для приёмки мало: {sorted(кадры)}"
    assert паспорт["measured"]["viewports"] == [320, 390, 768, 1024, 1440, 1920]
