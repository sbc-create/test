"""Проверка форматов действительно работает, а не проходит молча.

`jsonschema` проверяет `format` только тогда, когда установлен подходящий
дополнительный пакет. Для `date-time` это `rfc3339-validator`. Пропадёт он —
и `"format": "date-time"` перестанет проверять что-либо: схемы останутся
прежними, данные с испорченной датой пройдут, тесты позеленеют.

Это худший вид отказа: не ошибка, а тишина. Пакет объявлен в `requirements.txt`
и ни одним нашим модулем не импортируется, поэтому обычная проверка
неиспользуемых зависимостей назвала бы его лишним — и удаление выглядело бы
уборкой.

Здесь проверяется не наличие пакета, а работа: неверное значение обязано быть
отвергнуто. Так проверка переживёт и смену пакета, и смену способа подключения.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2]


class TestФорматДатыПроверяется:
    @pytest.fixture(scope="class")
    def проверяющий(self):
        return Draft202012Validator({"type": "string", "format": "date-time"},
                                    format_checker=FormatChecker())

    def test_неверная_дата_отвергается(self, проверяющий):
        assert list(проверяющий.iter_errors("не-дата")), (
            "проверка формата не работает: вероятно, пропал rfc3339-validator, "
            "и все поля date-time во всех схемах перестали проверяться молча")

    def test_дата_без_времени_отвергается(self, проверяющий):
        assert list(проверяющий.iter_errors("2026-09-07"))

    def test_верная_дата_принимается(self, проверяющий):
        assert not list(проверяющий.iter_errors("2026-09-07T14:00:00Z"))

    def test_проверяльщик_зарегистрирован(self):
        assert "date-time" in FormatChecker.checkers


class TestЗависимостьОбъявлена:
    def test_пакет_в_требованиях(self):
        """Работает он через jsonschema, и удалить его как «неиспользуемый» легко."""
        требования = (ROOT / "requirements.txt").read_text(encoding="utf-8")
        assert "rfc3339-validator" in требования


class TestСхемыПользуютсяПроверкойФорматов:
    def test_есть_схемы_с_датами(self):
        """Иначе проверка выше охраняет то, чем никто не пользуется."""
        с_датами = []
        for path in sorted((ROOT / "schemas").glob("*.json")):
            if '"date-time"' in path.read_text(encoding="utf-8"):
                с_датами.append(path.name)
        assert с_датами, "ни одна схема не объявляет date-time"

    def test_проверяющий_реестров_включает_проверку_форматов(self):
        source = (ROOT / "scripts" / "validate_registries.py").read_text(encoding="utf-8")
        assert "FormatChecker" in source, (
            "без format_checker объявленный в схеме формат не проверяется вовсе")

    def test_данные_с_испорченной_датой_отвергаются_настоящей_схемой(self):
        """Сквозная проверка: схема проекта, а не выдуманная в тесте."""
        схемы = [p for p in sorted((ROOT / "schemas").glob("*.json"))
                 if '"date-time"' in p.read_text(encoding="utf-8")]
        схема = json.loads(схемы[0].read_text(encoding="utf-8"))
        проверяющий = Draft202012Validator(схема, format_checker=FormatChecker())
        поле = _первое_поле_даты(схема)
        assert поле, f"в {схемы[0].name} не нашлось поля с date-time"
        ошибки = list(проверяющий.iter_errors({поле: "вчера"}))
        assert any(e.validator == "format" for e in ошибки), (
            f"{схемы[0].name}: значение «вчера» принято как date-time")


def _первое_поле_даты(схема: dict) -> str:
    for имя, описание in (схема.get("properties") or {}).items():
        if isinstance(описание, dict) and описание.get("format") == "date-time":
            return имя
    return ""
