"""Сравнение двух версий JSON Schema: что здесь ломающее, а что добавочное.

Зачем это существует. После заморозки контракта в major-версии v1 разрешены
только обратно совместимые добавления: необязательное поле, эндпоинт или
возможность с безопасным запасным поведением. Переименование, удаление, смена
типа, смена обязательности и смена допустимости `null` требуют новой major —
иначе шаблоны, собранные против прежней схемы, сломаются молча и не в момент
изменения, а когда-нибудь потом.

Правило нельзя удержать глазами: схема витрины — это сотни вложенных полей, и
ломающее изменение выглядит в диффе так же безобидно, как добавочное. Поэтому
классификация здесь машинная, а спорные случаи выделены отдельной категорией
вместо того, чтобы быть молча отнесёнными к безопасным.

Категории:

* `BREAKING` — потребитель, написанный против старой схемы, может перестать
  работать. Требует новой major-версии.
* `ADDITIVE`  — старый потребитель продолжает работать без изменений.
* `REVIEW`    — решает человек. Сюда попадает то, что формально совместимо для
  одной стороны и ломающее для другой: например, новое значение enum безопасно
  для того, кто пишет данные, и ломающе для того, кто их разбирает
  исчерпывающим сопоставлением.

Намеренно не угадывается семантика: смена `description` или `title` не влияет
на совместимость и здесь не показывается вовсе, чтобы не топить настоящие
находки в шуме.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

BREAKING = "BREAKING"
ADDITIVE = "ADDITIVE"
REVIEW = "REVIEW"


@dataclass(frozen=True)
class Change:
    kind: str
    path: str
    message: str

    def __str__(self) -> str:  # pragma: no cover - формат вывода
        return f"{self.kind}: {self.path or '(root)'}: {self.message}"


def _types(schema: Any) -> set[str]:
    """Множество типов узла. Отсутствие `type` означает «любой»."""
    if not isinstance(schema, dict):
        return set()
    declared = schema.get("type")
    if declared is None:
        return set()
    if isinstance(declared, str):
        return {declared}
    return {t for t in declared if isinstance(t, str)}


def _required(schema: Any) -> set[str]:
    if not isinstance(schema, dict):
        return set()
    value = schema.get("required")
    return set(value) if isinstance(value, list) else set()


def _properties(schema: Any) -> dict[str, Any]:
    if not isinstance(schema, dict):
        return {}
    value = schema.get("properties")
    return value if isinstance(value, dict) else {}


def _join(path: str, part: str) -> str:
    return f"{path}.{part}" if path else part


def _compare_node(old: Any, new: Any, path: str, out: list[Change]) -> None:
    if not isinstance(old, dict) or not isinstance(new, dict):
        return

    old_types, new_types = _types(old), _types(new)
    if old_types and new_types and old_types != new_types:
        lost = old_types - new_types
        # Потеря «null» — это сужение допустимости, а не просто смена типа:
        # значение, которое прежде законно приходило пустым, теперь невалидно.
        if lost == {"null"}:
            out.append(Change(BREAKING, path, "поле перестало допускать null"))
        elif lost:
            out.append(
                Change(BREAKING, path, f"тип сузился: было {sorted(old_types)}, стало {sorted(new_types)}")
            )
        else:
            out.append(
                Change(ADDITIVE, path, f"тип расширен: было {sorted(old_types)}, стало {sorted(new_types)}")
            )

    old_enum, new_enum = old.get("enum"), new.get("enum")
    if isinstance(old_enum, list) and isinstance(new_enum, list):
        removed = [v for v in old_enum if v not in new_enum]
        added = [v for v in new_enum if v not in old_enum]
        if removed:
            out.append(Change(BREAKING, path, f"из enum убраны значения: {removed}"))
        if added:
            out.append(
                Change(REVIEW, path, f"в enum добавлены значения: {added} — сломает исчерпывающий разбор")
            )
    elif isinstance(old_enum, list) and new_enum is None:
        out.append(Change(ADDITIVE, path, "ограничение enum снято"))
    elif old_enum is None and isinstance(new_enum, list):
        out.append(Change(BREAKING, path, f"появилось ограничение enum: {new_enum}"))

    if old.get("additionalProperties") is not False and new.get("additionalProperties") is False:
        out.append(Change(BREAKING, path, "additionalProperties сужен до false"))

    old_props, new_props = _properties(old), _properties(new)
    old_req, new_req = _required(old), _required(new)

    for name in sorted(set(old_props) - set(new_props)):
        out.append(Change(BREAKING, _join(path, name), "поле удалено"))

    for name in sorted(set(new_props) - set(old_props)):
        if name in new_req:
            out.append(Change(BREAKING, _join(path, name), "добавлено обязательное поле"))
        else:
            out.append(Change(ADDITIVE, _join(path, name), "добавлено необязательное поле"))

    for name in sorted(set(old_req) & set(new_props) - old_req.intersection(new_req)):
        out.append(Change(ADDITIVE, _join(path, name), "поле стало необязательным"))

    for name in sorted((new_req - old_req) & set(old_props)):
        out.append(Change(BREAKING, _join(path, name), "существующее поле стало обязательным"))

    for name in sorted(set(old_props) & set(new_props)):
        _compare_node(old_props[name], new_props[name], _join(path, name), out)

    old_items, new_items = old.get("items"), new.get("items")
    if isinstance(old_items, dict) and isinstance(new_items, dict):
        _compare_node(old_items, new_items, _join(path, "[]"), out)


def compare_schemas(old: dict[str, Any], new: dict[str, Any]) -> list[Change]:
    """Все различия двух схем, классифицированные по влиянию на потребителя."""
    out: list[Change] = []
    _compare_node(old, new, "", out)
    return out


def breaking_changes(changes: list[Change]) -> list[Change]:
    return [c for c in changes if c.kind == BREAKING]


def compare_files(old_path: str | Path, new_path: str | Path) -> list[Change]:
    old = json.loads(Path(old_path).read_text(encoding="utf-8"))
    new = json.loads(Path(new_path).read_text(encoding="utf-8"))
    return compare_schemas(old, new)


def main(argv: list[str] | None = None) -> int:
    """Код возврата — число ломающих изменений, чтобы CI падал видимо."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Сравнить две версии JSON Schema")
    parser.add_argument("old")
    parser.add_argument("new")
    parser.add_argument(
        "--allow-breaking",
        action="store_true",
        help="не падать на ломающих изменениях (для осознанного перехода на новую major)",
    )
    args = parser.parse_args(argv)

    changes = compare_files(args.old, args.new)
    for change in changes:
        print(change)
    broken = breaking_changes(changes)
    if not changes:
        print("различий, влияющих на совместимость, нет")
    if broken and not args.allow_breaking:
        print(f"\nломающих изменений: {len(broken)} — требуется новая major-версия", file=sys.stderr)
        return len(broken)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
