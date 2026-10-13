"""REQ-CONTRACT-COMPAT: ломающее изменение схемы видно до вливания, а не в бою.

После заморозки контракта в major-версии v1 разрешены только обратно
совместимые добавления. Правило нельзя удержать глазами: схема витрины — сотни
вложенных полей, и удаление поля выглядит в диффе так же безобидно, как
добавление. Поэтому классификация машинная.

Проверяется поведение на настоящих парах схем, а не наличие слов в коде.
"""

from __future__ import annotations

import json

from factory.contracts.schema_compat import (
    ADDITIVE,
    BREAKING,
    REVIEW,
    breaking_changes,
    compare_files,
    compare_schemas,
    main,
)


def obj(properties: dict, required: list[str] | None = None, **extra) -> dict:
    schema = {"type": "object", "properties": properties}
    if required is not None:
        schema["required"] = required
    schema.update(extra)
    return schema


def kinds_at(changes, path):
    return {c.kind for c in changes if c.path == path}


def test_identical_schemas_produce_no_changes() -> None:
    schema = obj({"id": {"type": "string"}}, ["id"])
    assert compare_schemas(schema, schema) == []


def test_removed_property_is_breaking() -> None:
    old = obj({"id": {"type": "string"}, "slug": {"type": "string"}})
    new = obj({"id": {"type": "string"}})
    assert kinds_at(compare_schemas(old, new), "slug") == {BREAKING}


def test_new_optional_property_is_additive() -> None:
    """Ровно то единственное, что разрешено внутри major-версии."""
    old = obj({"id": {"type": "string"}}, ["id"])
    new = obj({"id": {"type": "string"}, "badge": {"type": "string"}}, ["id"])
    changes = compare_schemas(old, new)
    assert kinds_at(changes, "badge") == {ADDITIVE}
    assert breaking_changes(changes) == []


def test_new_required_property_is_breaking() -> None:
    """Новое поле безопасно только пока оно необязательное."""
    old = obj({"id": {"type": "string"}}, ["id"])
    new = obj({"id": {"type": "string"}, "locale": {"type": "string"}}, ["id", "locale"])
    assert kinds_at(compare_schemas(old, new), "locale") == {BREAKING}


def test_existing_property_becoming_required_is_breaking() -> None:
    old = obj({"id": {"type": "string"}, "theme": {"type": "string"}}, ["id"])
    new = obj({"id": {"type": "string"}, "theme": {"type": "string"}}, ["id", "theme"])
    assert kinds_at(compare_schemas(old, new), "theme") == {BREAKING}


def test_dropping_null_from_type_is_breaking() -> None:
    """Значение, что прежде законно приходило пустым, теперь невалидно."""
    old = obj({"rating": {"type": ["number", "null"]}})
    new = obj({"rating": {"type": "number"}})
    changes = compare_schemas(old, new)
    assert kinds_at(changes, "rating") == {BREAKING}
    assert "null" in str(changes[0])


def test_widening_type_is_additive() -> None:
    old = obj({"rating": {"type": "number"}})
    new = obj({"rating": {"type": ["number", "null"]}})
    assert kinds_at(compare_schemas(old, new), "rating") == {ADDITIVE}


def test_removing_enum_value_is_breaking_and_adding_needs_review() -> None:
    """Новое значение enum безопасно для пишущего и ломающе для разбирающего."""
    old = obj({"state": {"enum": ["ready", "error"]}})
    new = obj({"state": {"enum": ["ready", "degraded"]}})
    kinds = kinds_at(compare_schemas(old, new), "state")
    assert kinds == {BREAKING, REVIEW}


def test_tightening_additional_properties_is_breaking() -> None:
    old = obj({"id": {"type": "string"}})
    new = obj({"id": {"type": "string"}}, additionalProperties=False)
    assert kinds_at(compare_schemas(old, new), "") == {BREAKING}


def test_nested_and_array_item_changes_are_found() -> None:
    """Вложенность — обычное место, где ломающее изменение прячется от глаз."""
    old = obj({"cards": {"type": "array", "items": obj({"href": {"type": "string"}})}})
    new = obj({"cards": {"type": "array", "items": obj({})}})
    assert kinds_at(compare_schemas(old, new), "cards.[].href") == {BREAKING}


def test_cosmetic_changes_are_not_reported() -> None:
    """Описания не влияют на совместимость и не должны топить находки в шуме."""
    old = obj({"id": {"type": "string", "description": "было"}})
    new = obj({"id": {"type": "string", "description": "стало", "title": "Идентификатор"}})
    assert compare_schemas(old, new) == []


def test_cli_exit_code_counts_breaking_changes(tmp_path, capsys) -> None:
    old_file = tmp_path / "old.json"
    new_file = tmp_path / "new.json"
    old_file.write_text(json.dumps(obj({"id": {"type": "string"}, "slug": {"type": "string"}})), encoding="utf-8")
    new_file.write_text(json.dumps(obj({"id": {"type": "string"}})), encoding="utf-8")

    assert main([str(old_file), str(new_file)]) == 1
    # Осознанный переход на новую major не должен валить прогон.
    assert main([str(old_file), str(new_file), "--allow-breaking"]) == 0
    assert compare_files(old_file, new_file)


def test_cli_is_quiet_when_nothing_affects_compatibility(tmp_path) -> None:
    schema = json.dumps(obj({"id": {"type": "string"}}, ["id"]))
    old_file, new_file = tmp_path / "a.json", tmp_path / "b.json"
    old_file.write_text(schema, encoding="utf-8")
    new_file.write_text(schema, encoding="utf-8")
    assert main([str(old_file), str(new_file)]) == 0
