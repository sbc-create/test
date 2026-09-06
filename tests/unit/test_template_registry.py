"""REQ-TEMPLATE-REGISTRY: регистрируется проверенный пакет, а не любой код.

Разница видна на одном вопросе: «чем доказано, что этот пакет работает». Если
ответа нет, пакет не регистрируется — не потому, что он плох, а потому что
неизвестно. Запись с пропуском хуже отсутствия записи: она выглядит проверенной.
"""

from __future__ import annotations

import pytest
import yaml

from factory.site_engine import template_registry as реестр

ГОДНАЯ = {
    "family": "family_a",
    "version": "2.0.0",
    "digest": "a" * 64,
    "renderer_revision": "b" * 40,
    "contract": "site-template/1.0.0",
    "capabilities": ["pagination", "player"],
    "contract_tests": {"passed": True, "at": "2026-09-06T10:00:00Z", "suite": "unit"},
    "rollback_compatible_with": ["1.0.0"],
}


def _записать(tmp_path, шаблоны):
    (tmp_path / "config").mkdir(parents=True, exist_ok=True)
    (tmp_path / реестр.РЕЕСТР).write_text(
        yaml.safe_dump({"version": 1, "templates": шаблоны}, allow_unicode=True),
        encoding="utf-8")
    return tmp_path


def test_годная_запись_регистрируется(tmp_path):
    из = реестр.прочитать(_записать(tmp_path, [ГОДНАЯ]))
    assert len(из["templates"]) == 1
    assert из["rejected"] == []


@pytest.mark.parametrize("поле", ["family", "version", "digest", "renderer_revision",
                                  "contract", "capabilities", "contract_tests"])
def test_запись_без_обязательного_поля_отвергается(tmp_path, поле):
    плохая = {к: з for к, з in ГОДНАЯ.items() if к != поле}
    из = реестр.прочитать(_записать(tmp_path, [плохая]))
    assert из["templates"] == []
    assert поле in из["rejected"][0]["reason"]


def test_пустой_список_отката_это_ответ_а_отсутствие_нет(tmp_path):
    первая = {**ГОДНАЯ, "rollback_compatible_with": []}
    assert реестр.прочитать(_записать(tmp_path, [первая]))["templates"]

    без_поля = {к: з for к, з in ГОДНАЯ.items() if к != "rollback_compatible_with"}
    из = реестр.прочитать(_записать(tmp_path, [без_поля]))
    assert из["templates"] == []
    assert "пустой список — это ответ" in из["rejected"][0]["reason"]


def test_непройденные_проверки_не_регистрируются(tmp_path):
    плохая = {**ГОДНАЯ, "contract_tests": {"passed": False, "at": "2026-09-06T10:00:00Z",
                                           "suite": "unit"}}
    из = реестр.прочитать(_записать(tmp_path, [плохая]))
    assert из["templates"] == []
    assert "не пройдены" in из["rejected"][0]["reason"]


def test_проверки_без_времени_не_считаются(tmp_path):
    плохая = {**ГОДНАЯ, "contract_tests": {"passed": True, "suite": "unit"}}
    из = реестр.прочитать(_записать(tmp_path, [плохая]))
    assert "без даты" in из["rejected"][0]["reason"]


def test_короткая_ревизия_отвергается(tmp_path):
    плохая = {**ГОДНАЯ, "renderer_revision": "b" * 12}
    из = реестр.прочитать(_записать(tmp_path, [плохая]))
    assert "полным SHA" in из["rejected"][0]["reason"]


def test_отпечаток_не_sha256_отвергается(tmp_path):
    плохая = {**ГОДНАЯ, "digest": "не-отпечаток"}
    из = реестр.прочитать(_записать(tmp_path, [плохая]))
    assert "не sha256" in из["rejected"][0]["reason"]


def test_неизвестная_способность_отвергается(tmp_path):
    плохая = {**ГОДНАЯ, "capabilities": ["телепортация"]}
    из = реестр.прочитать(_записать(tmp_path, [плохая]))
    assert "неизвестные способности" in из["rejected"][0]["reason"]


def test_откат_только_на_объявленную_совместимой(tmp_path):
    старая = {**ГОДНАЯ, "version": "1.0.0", "rollback_compatible_with": []}
    корень = _записать(tmp_path, [ГОДНАЯ, старая])
    можно, почему = реестр.можно_откатиться(корень, "family_a",
                                            с_версии="2.0.0", на_версию="1.0.0")
    assert можно and почему == ""
    нельзя, причина = реестр.можно_откатиться(корень, "family_a",
                                              с_версии="1.0.0", на_версию="2.0.0")
    assert not нельзя and "вторая авария" in причина


def test_откат_на_незарегистрированную_версию_отклонён(tmp_path):
    корень = _записать(tmp_path, [ГОДНАЯ])
    можно, причина = реестр.можно_откатиться(корень, "family_a",
                                             с_версии="2.0.0", на_версию="0.9.0")
    assert not можно and "не зарегистрирована" in причина


def test_способность_проверяется_по_версии(tmp_path):
    корень = _записать(tmp_path, [ГОДНАЯ])
    assert реестр.проверить_способность(корень, "family_a", "2.0.0", "pagination")
    assert not реестр.проверить_способность(корень, "family_a", "2.0.0", "server-search")
    assert not реестр.проверить_способность(корень, "family_a", "9.9.9", "pagination")


def test_отсутствующий_реестр_называет_причину(tmp_path):
    из = реестр.прочитать(tmp_path)
    assert из["templates"] == []
    assert "реестра нет" in из["error"]


def test_отвергнутые_видны_а_не_выброшены(tmp_path):
    плохая = {"family": "family_b", "version": "1.0.0"}
    из = реестр.прочитать(_записать(tmp_path, [ГОДНАЯ, плохая]))
    assert len(из["templates"]) == 1
    assert из["rejected"][0]["family"] == "family_b", (
        "отвергнутая запись выброшена молча — добавивший не узнает, чем она не годится")


def test_настоящий_реестр_репозитория_годен():
    """Реестр в репозитории обязан быть годным целиком."""
    from pathlib import Path

    корень = Path(__file__).resolve().parents[2]
    из = реестр.прочитать(корень)
    assert из["error"] == ""
    assert из["rejected"] == [], f"в реестре есть отвергнутые записи: {из['rejected']}"
    assert из["templates"], "реестр пуст"
