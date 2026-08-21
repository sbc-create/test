"""REQ-MODE-A: заморозка базы знаний и обнаружение изменений."""
from factory import knowledge
from factory.paths import PATHS


def test_freeze_exists_and_is_consistent():
    ok, problems = knowledge.verify()
    assert ok, f"база знаний разошлась с freeze: {problems}"


def test_freeze_records_every_knowledge_file():
    data = knowledge.load_freeze()
    recorded = {entry["path"] for entry in data["files"]}
    actual = {str(p.relative_to(PATHS.root)) for p in knowledge.tracked_files()}
    assert recorded == actual


def test_freeze_has_version_and_aggregate_digest():
    data = knowledge.load_freeze()
    assert data["freeze_version"]
    assert len(data["aggregate_sha256"]) == 64


def test_tampering_is_detected(tmp_path):
    target = PATHS.knowledge / "FACTS.md"
    original = target.read_bytes()
    try:
        target.write_bytes(original + "\n<!-- изменение мимо /research-freeze -->\n".encode("utf-8"))
        ok, problems = knowledge.verify()
        assert not ok
        assert any("FACTS.md" in problem for problem in problems)
    finally:
        target.write_bytes(original)
    assert knowledge.verify()[0]


def test_required_knowledge_documents_exist():
    required = [
        "SOURCE_REGISTRY.yaml", "FACTS.md", "DECISIONS.md", "UNKNOWNS.md",
        "THIRD_PARTY_REVIEW.md", "DLE_20_COMPATIBILITY.md", "VK_CONTENT_AND_ADS_CONTRACT.md",
        "SEO_KNOWLEDGE_PACK.md", "SEO_INDEXABILITY_MATRIX.yaml", "INFRASTRUCTURE_INVENTORY.yaml",
        "KNOWLEDGE_FREEZE.yaml",
    ]
    for name in required:
        assert (PATHS.knowledge / name).exists(), f"нет обязательного документа: {name}"
