#!/usr/bin/env python3
"""Validate SEO data files against the repository's JSON Schemas.

Usage:
    validate_schemas.py                 # self-check: every schema compiles
    validate_schemas.py FILE [FILE ...] # validate data files

A data file is matched to its schema by filename prefix: ``seo-audit.*.json``
validates against ``schemas/seo-audit.schema.json``. Exit code is non-zero if
any file fails, so CI and the pre-commit path can gate on it.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = REPO_ROOT / "schemas"


def load_schemas() -> dict[str, dict]:
    """Return every schema in schemas/ keyed by its stem (e.g. ``seo-audit``)."""
    schemas = {}
    for path in sorted(SCHEMA_DIR.glob("*.schema.json")):
        stem = path.name[: -len(".schema.json")]
        schemas[stem] = json.loads(path.read_text())
    return schemas


def check_schemas_compile(schemas: dict[str, dict]) -> list[str]:
    """Confirm each schema is itself a legal Draft 2020-12 schema."""
    errors = []
    for name, schema in schemas.items():
        try:
            Draft202012Validator.check_schema(schema)
        except Exception as exc:  # noqa: BLE001 - report any malformed schema
            errors.append(f"{name}.schema.json is not a valid schema: {exc}")
    return errors


def schema_for(data_path: Path, schemas: dict[str, dict]) -> tuple[str, dict] | None:
    """Match a data file to a schema by its leading filename segment."""
    stem = data_path.name.split(".")[0]
    if stem in schemas:
        return stem, schemas[stem]
    return None


def validate_file(data_path: Path, schemas: dict[str, dict]) -> list[str]:
    match = schema_for(data_path, schemas)
    if match is None:
        return [f"{data_path}: no schema matches this filename"]

    name, schema = match
    try:
        data = json.loads(data_path.read_text())
    except json.JSONDecodeError as exc:
        return [f"{data_path}: invalid JSON: {exc}"]

    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    problems = []
    for error in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
        location = "/".join(str(p) for p in error.path) or "(root)"
        problems.append(f"{data_path} [{name}] at {location}: {error.message}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="*", type=Path)
    args = parser.parse_args()

    schemas = load_schemas()
    if not schemas:
        print("no schemas found in schemas/", file=sys.stderr)
        return 1

    errors = check_schemas_compile(schemas)
    if errors:
        for err in errors:
            print(f"ERROR: {err}", file=sys.stderr)
        return 1

    if not args.files:
        print(f"OK: {len(schemas)} schema(s) compile: {', '.join(sorted(schemas))}")
        return 0

    failures = []
    for data_path in args.files:
        problems = validate_file(data_path, schemas)
        if problems:
            failures.extend(problems)
        else:
            print(f"OK: {data_path}")

    for problem in failures:
        print(f"FAIL: {problem}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
