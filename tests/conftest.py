import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / ".claude" / "hooks"))


@pytest.fixture()
def isolated_state(tmp_path, monkeypatch):
    """Каждый тест получает собственный durable state, чтобы не смешивать прогоны."""
    monkeypatch.setenv("SEO_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("SEO_REPO_ROOT", str(ROOT))
    from seo_operator import config
    config.reset_caches()
    yield tmp_path
    config.reset_caches()


@pytest.fixture()
def store(isolated_state):
    from seo_operator.state import Store
    s = Store()
    yield s
    s.close()


@pytest.fixture()
def audit(isolated_state):
    from seo_operator.audit import AuditLog
    a = AuditLog()
    yield a
    a.close()
