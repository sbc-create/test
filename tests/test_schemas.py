"""Tests for the SEO data schemas and their validator.

These guard two things: that every schema in ``schemas/`` is itself legal, and
that the validator actually rejects bad data. A schema that accepts anything is
worse than no schema, so each ``*.invalid.json`` fixture must fail.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from validate_schemas import (  # noqa: E402
    check_schemas_compile,
    load_schemas,
    validate_file,
)

FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures"
VALID_FIXTURES = sorted(FIXTURE_DIR.glob("*.valid.json"))
INVALID_FIXTURES = sorted(FIXTURE_DIR.glob("*.invalid.json"))


@pytest.fixture(scope="module")
def schemas() -> dict[str, dict]:
    return load_schemas()


def test_schemas_exist(schemas):
    assert schemas, "no schemas found in schemas/"


def test_every_schema_compiles(schemas):
    assert check_schemas_compile(schemas) == []


@pytest.mark.parametrize("path", VALID_FIXTURES, ids=lambda p: p.name)
def test_valid_fixture_passes(path, schemas):
    problems = validate_file(path, schemas)
    assert problems == [], f"{path.name} should validate cleanly:\n" + "\n".join(problems)


@pytest.mark.parametrize("path", INVALID_FIXTURES, ids=lambda p: p.name)
def test_invalid_fixture_is_rejected(path, schemas):
    problems = validate_file(path, schemas)
    assert problems, f"{path.name} is meant to be invalid but the schema accepted it"


def test_every_schema_has_a_valid_fixture(schemas):
    """A schema nobody exercises drifts silently."""
    covered = {p.name.split(".")[0] for p in VALID_FIXTURES}
    assert set(schemas) <= covered, f"schemas without a valid fixture: {set(schemas) - covered}"


@pytest.mark.parametrize(
    "path", sorted((REPO_ROOT / "schemas").glob("*.json")), ids=lambda p: p.name
)
def test_schema_declares_id_and_title(path):
    schema = json.loads(path.read_text())
    assert schema.get("$id"), f"{path.name} is missing $id"
    assert schema.get("title"), f"{path.name} is missing title"
    assert schema.get("description"), f"{path.name} is missing description"


def test_unmatched_filename_is_reported(tmp_path, schemas):
    stray = tmp_path / "not-a-known-kind.json"
    stray.write_text("{}")
    problems = validate_file(stray, schemas)
    assert any("no schema matches" in p for p in problems)
