"""REQ-*: каждое нормативное требование связано с существующим тестом."""
from factory.errors import FAILURE_STATES
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
def test_every_requirement_is_named_inside_its_test(row):
    """Файл обязан не просто существовать, а называть требование, которое доказывает.

    Прежняя версия проверяла только `Path.exists()`, поэтому «прослеженность»
    держалась на имени файла, а не на его содержимом.
    """
    target = PATHS.root / row["test"]
    assert target.exists(), f"{row['id']}: тест {row['test']} не существует"
    if target.suffix in (".sh",):
        return
    text = target.read_text(encoding="utf-8")
    assert row["id"] in text, f"{row['id']}: в {row['test']} нет ссылки на это требование"


def test_requirement_ids_are_unique():
    ids = [row["id"] for row in rows()]
    assert len(ids) == len(set(ids))


STATUSES = FAILURE_STATES  # список берётся из кода, а не дублируется здесь


@pytest.mark.parametrize("status", STATUSES)
def test_every_blocking_status_is_asserted_somewhere(status):
    """Статус обязан встречаться в assert-выражении вне самого traceability-теста.

    Прежняя версия склеивала все тесты вместе, включая этот файл со списком
    статусов, и потому проходила всегда — сама себя и удовлетворяла.
    """
    hits = []
    for path in (PATHS.root / "tests").rglob("*.py"):
        if path.name == "test_traceability.py":
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            stripped = line.strip()
            if status in stripped and (stripped.startswith("assert") or "pytest.raises" in stripped
                                       or "== \"" + status in stripped or "status ==" in stripped):
                hits.append(f"{path.name}:{number}")
    assert hits, f"статус {status} не проверяется ни одним assert вне traceability-теста"
