#!/usr/bin/env python3
"""Validate every registry in config/ against its schema.

Mapping is explicit rather than filename-derived, because a registry silently
skipped for want of a matching name would defeat the point of validating at all.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

REPO = Path(__file__).resolve().parent.parent

MAPPING = {
    "portfolio.json": "portfolio-registry.schema.json",
    "portfolio.fixture.json": "portfolio-registry.schema.json",
    "data-sources.json": "data-source-registry.schema.json",
    "editorial-sources.json": "editorial-sources.schema.json",
    "editorial-calendar.json": "editorial-calendar.schema.json",
    "content-backlog.json": "content-backlog.schema.json",
    "experiments.json": "experiment-registry.schema.json",
    "analytics.json": "analytics-registry.schema.json",
    # Реестр направлений Secret Hub. Значений секретов в нём нет и быть не
    # может: схема запрещает их структурно (additionalProperties выключены на
    # каждом уровне), а проверка здесь ловит попытку добавить поле в обход.
    "secret-hub.json": "secret-hub.schema.json",
}

# Производные артефакты: файл порождается из другого источника и в некоторых
# ветках отсутствует вовсе.
#
# Почему не в MAPPING. Там отсутствие файла — провал, и это правильно для
# реестра, который обязан быть. SITE-MATRIX.json порождается из
# config/site-profiles/*.json, живёт не во всех ветках, и требовать его
# повсеместно значит ломать проверку там, где генератор ещё не подключён.
#
# Почему не в списке исключений. Молчаливый пропуск вернул бы ровно ту дыру,
# ради закрытия которой сопоставление сделано явным: файл, не сопоставленный
# ни одной схеме, не проверяется никем. Здесь отсутствие разрешено, а
# присутствие обязано пройти схему.
DERIVED = {
    "SITE-MATRIX.json": "site-matrix.schema.json",
}


def main() -> int:
    config_dir = REPO / "config"
    present = {p.name for p in config_dir.glob("*.json")}
    unmapped = present - set(MAPPING) - set(DERIVED)
    failures: list[str] = []

    for name in sorted(unmapped):
        failures.append(f"{name}: реестр не сопоставлен ни одной схеме")

    for name, schema_name in sorted(MAPPING.items()):
        path = config_dir / name
        if not path.exists():
            failures.append(f"{name}: файл отсутствует")
            continue
        schema = json.loads((REPO / "schemas" / schema_name).read_text(encoding="utf-8"))
        data = json.loads(path.read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
        if errors:
            for err in errors[:5]:
                loc = "/".join(str(p) for p in err.path) or "(root)"
                failures.append(f"{name} at {loc}: {err.message}")
        else:
            print(f"OK: config/{name} -> {schema_name}")

    for name, schema_name in sorted(DERIVED.items()):
        path = config_dir / name
        if not path.exists():
            print(f"SKIP: config/{name} -> производный артефакт отсутствует в этой ветке")
            continue
        schema = json.loads((REPO / "schemas" / schema_name).read_text(encoding="utf-8"))
        data = json.loads(path.read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
        if errors:
            for err in errors[:5]:
                loc = "/".join(str(p) for p in err.path) or "(root)"
                failures.append(f"{name} at {loc}: {err.message}")
        else:
            print(f"OK: config/{name} -> {schema_name}")

    for failure in failures:
        print(f"FAIL: {failure}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
