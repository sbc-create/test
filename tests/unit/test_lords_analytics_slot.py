"""REQ-LORDS-ANALYTICS: у рендерера Lords есть место под счётчик, и оно безопасно.

Три домена Lords не имели счётчика Метрики — и причина была не в том, что его
забыли завести. `factory/lords/render.py` вообще не подключал аналитику: в
собираемом `<head>` не было ни тега Метрики, ни точки, куда его можно положить.
Счётчик было некуда вставить, даже если бы он существовал в реестре.

Проверяется не наличие конкретного counter_id — его заводит
`analytics apply --confirm-writes` с OAuth, которого у сборки нет. Проверяется
инвариант: слот существует, проходит через тот же `snippet.analytics_script_tag`,
что и остальная фабрика, и по умолчанию не печатает ничего. Пустая строка здесь
означает «тега нет», а не «тег есть, но молчит».

Отдельно проверяется `allowed_hosts`: три сайта Lords обслуживает один рендерер,
и общий список хостов означал бы, что счётчик одного домена собирает визиты двух
соседних. По умолчанию список — собственный домен пакета и ничей больше.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RENDER = REPO / "factory" / "lords" / "render.py"
SOURCE = RENDER.read_text(encoding="utf-8")


def _call_block() -> str:
    """Аргументы вызова целиком: срез по `),` обрывался на первом же аргументе."""
    start = SOURCE.index("analytics_snippet.analytics_script_tag(")
    depth = 0
    for i in range(start, len(SOURCE)):
        if SOURCE[i] == "(":
            depth += 1
        elif SOURCE[i] == ")":
            depth -= 1
            if depth == 0:
                return SOURCE[start : i + 1]
    raise AssertionError("не найден конец вызова analytics_script_tag")


class TestSlotExists:
    def test_renderer_imports_the_shared_snippet(self):
        """Собственная реализация тега разошлась бы с проверками snippet.py."""
        assert "from factory.analytics import snippet as analytics_snippet" in SOURCE, (
            "рендерер Lords не подключает общий модуль аналитики"
        )

    def test_head_emits_the_slot(self):
        """В <head> есть ветка, добавляющая готовый тег."""
        assert re.search(r'ctx\.get\("analytics_script"\)', SOURCE), (
            "в <head> нет места под тег аналитики"
        )

    def test_context_builds_the_tag_through_the_snippet(self):
        """Тег строится вызовом snippet, а не конкатенацией строк на месте."""
        assert "analytics_snippet.analytics_script_tag(" in SOURCE, (
            "тег собирается в обход snippet.analytics_script_tag"
        )

    def test_no_hand_rolled_counter_markup(self):
        """Прямая вставка mc.yandex обошла бы все проверки разом."""
        assert "mc.yandex" not in SOURCE, "в рендерере Lords есть ручная разметка Метрики"


class TestSafeDefaults:
    def test_allowed_hosts_default_to_the_own_domain(self):
        """Список хостов по умолчанию не может содержать соседний домен."""
        call = _call_block()
        assert "[domain] if domain else []" in call, (
            "allowed_hosts по умолчанию не сведён к собственному домену пакета: "
            f"{call}"
        )

    def test_environment_defaults_to_non_production(self):
        """Пакет без явного окружения не должен начать собирать статистику."""
        call = _call_block()
        match = re.search(r'environment=str\(package\.get\("environment"\) or "(\w+)"\)', call)
        assert match, f"окружение не берётся из пакета с безопасным умолчанием: {call}"
        assert match.group(1) != "production", (
            "умолчание окружения — production: пакет без настройки начнёт слать визиты"
        )

    def test_module_still_parses(self):
        ast.parse(SOURCE)
