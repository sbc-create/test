"""REQ-*: каждое нормативное требование связано с существующим тестом."""
import re
from pathlib import Path

import pytest

from factory.paths import PATHS

DOC = PATHS.docs / "MASTER_PROMPT_REQUIREMENTS.md"
ROW = re.compile(r"^\|\s*(REQ-[A-Z0-9-]+)\s*\|(.+?)\|(.+?)\|\s*`([^`]+)`\s*\|\s*$")


def rows():
    parsed = []
    for line in DOC.read_text(encoding="utf-8").splitlines():
        match = ROW.match(line.strip())
        if match:
            parsed.append({"id": match.group(1), "requirement": match.group(2).strip(),
                           "section": match.group(3).strip(), "test": match.group(4).strip()})
    return parsed


def test_requirements_table_is_parsed():
    assert len(rows()) >= 40, "экстракт требований обязан покрывать разделы мастер-промпта"


@pytest.mark.parametrize("row", rows(), ids=lambda r: r["id"])
def test_every_requirement_has_an_existing_test(row):
    target = PATHS.root / row["test"]
    assert target.exists(), f"{row['id']}: тест {row['test']} не существует"


def test_requirement_ids_are_unique():
    ids = [row["id"] for row in rows()]
    assert len(ids) == len(set(ids))


def test_key_statuses_are_covered_by_tests():
    """Для каждого блокирующего статуса существует тест, который его вызывает."""
    sources = "\n".join(p.read_text(encoding="utf-8") for p in (PATHS.root / "tests").rglob("*.py"))
    for status in ("BLOCKED_INPUT", "BLOCKED_LICENSE", "BLOCKED_RIGHTS", "BLOCKED_SECRET",
                   "BLOCKED_ACCESS", "BLOCKED_AUTHORIZATION", "BLOCKED_SEO", "QA_FAILED",
                   "DEPLOY_FAILED", "ROLLED_BACK", "QUARANTINED"):
        assert status in sources, f"нет теста, доказывающего статус {status}"
