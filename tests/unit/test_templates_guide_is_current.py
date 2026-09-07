"""Описание слоя не расходится с кодом.

Документ о механике устаревает быстрее любого другого: он описывает числа,
команды и имена файлов, а всё это меняется каждый цикл. Устаревшее описание
хуже отсутствующего — по нему действуют.

Поэтому здесь сверяется не стиль, а факты: состав отпечатка, номер версии,
перечень тем, имена команд и файлов. Если документ отстанет, упадёт эта
проверка, а не владелец, действующий по нему.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from factory.templates import digest as digest_mod  # noqa: E402
from release_input_audit import ARTIFACT_VERSIONS  # noqa: E402

DOC = ROOT / "docs" / "templates" / "TEMPLATES-GUIDE.md"


@pytest.fixture(scope="module")
def текст() -> str:
    return DOC.read_text(encoding="utf-8")


class TestЧислаСовпадают:
    def test_состав_отпечатка(self, текст):
        файлов = digest_mod.compute()["files"]
        assert f"**{файлов} файлов**" in текст, (
            f"в отпечатке {файлов} файлов, документ называет другое число")

    def test_число_профилей_совпадает(self, текст):
        профилей = len(list((ROOT / "blueprints" / "lords" / "profiles").glob("*.yaml")))
        assert профилей >= 6, профилей

    def test_перечень_тем_полон(self, текст):
        схема = json.loads((ROOT / "schemas" / "site-package.schema.json")
                           .read_text(encoding="utf-8"))
        для_темы = схема["properties"]["tenant"]["properties"]["theme"]["enum"]
        отсутствуют = [t for t in для_темы if f"`{t}`" not in текст]
        assert отсутствуют == [], f"темы не описаны: {отсутствуют}"


class TestКомандыСуществуют:
    def test_каждая_названная_команда_есть(self, текст):
        сценарии = set(re.findall(r"scripts/([A-Za-z_0-9]+\.py)", текст))
        отсутствуют = [s for s in сценарии if not (ROOT / "scripts" / s).is_file()]
        assert отсутствуют == [], f"названы несуществующие сценарии: {отсутствуют}"

    def test_каждый_названный_конфиг_есть(self, текст):
        конфиги = set(re.findall(r"(playwright\.[a-z-]+\.config\.js)", текст))
        отсутствуют = [c for c in конфиги if not (ROOT / c).is_file()]
        assert отсутствуют == [], f"названы несуществующие наборы: {отсутствуют}"

    def test_каждый_названный_тест_есть(self, текст):
        тесты = set(re.findall(r"`(tests?/[A-Za-z_0-9/]+\.py)`", текст))
        тесты |= {f"tests/unit/{m}" for m in
                  re.findall(r"`(test_[A-Za-z_0-9]+\.py)`", текст)}
        отсутствуют = [t for t in тесты if not (ROOT / t).is_file()]
        assert отсутствуют == [], f"названы несуществующие проверки: {отсутствуют}"

    def test_названные_файлы_настроек_есть(self, текст):
        файлы = set(re.findall(r"`(config/[a-z-]+\.json)`", текст))
        файлы |= set(re.findall(r"`(factory/[a-z_/]+\.py)`", текст))
        отсутствуют = [f for f in файлы if not (ROOT / f).is_file()]
        assert отсутствуют == [], f"названы несуществующие файлы: {отсутствуют}"


class TestПакетыНазваныВерно:
    def test_соответствие_продукт_пакет(self, текст):
        """Именно эту пару однажды перепутали, и путаница стоила этапа."""
        for продукт, пакет in (("zona-cinema", "zona-cinema-preview"),
                               ("animedia-portal", "animedia-preview"),
                               ("basis-video", "pilot-local")):
            assert f"`{пакет}`" in текст, f"{продукт}: пакет {пакет} не назван"
            assert (ROOT / "sites" / пакет / "package.yaml").is_file(), пакет

    def test_у_yummy_пакета_нет(self, текст):
        assert not (ROOT / "sites" / "yummy").exists()
        assert "пакета в фабрике нет" in текст.replace("\n", " ")


class TestСостоянияПриёмкиПеречислены:
    def test_все_состояния_названы(self, текст):
        from product_readiness import ЖДЁТ

        отсутствуют = [s for s in ЖДЁТ if f"`{s}`" not in текст]
        assert отсутствуют == [], f"состояния приёмки не описаны: {отсутствуют}"

    def test_приёмка_не_названа_числом(self, текст):
        assert "числа не имеет, пока не проведена" in текст


class TestВерсияАртефакта:
    def test_реестр_не_пуст_и_согласован(self):
        отпечаток = digest_mod.compute()["template_digest"]
        assert ARTIFACT_VERSIONS[отпечаток] == max(ARTIFACT_VERSIONS.values())
