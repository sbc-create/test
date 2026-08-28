"""Редакторский CLI поверх Ranker v1.

Интерфейс, поверх которого позже встанет админка. Проверяется не удобство
команд, а два обещания: редактор не может показать то, что не играет, и у
каждого решения есть срок.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
import yaml

from factory.recs import cli
from factory.recs.editorial import Editorial
from factory.recs.model import ItemFeatures
from factory.recs.ranker import rank

NOW = datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def store(tmp_path):
    return tmp_path / "editorial.yaml"


def run(store, *argv) -> int:
    return cli.main(["--file", str(store), *argv])


def documents(store) -> list:
    return yaml.safe_load(store.read_text(encoding="utf-8")) or []


class TestDecisionsAreWrittenAndRead:
    def test_pin_is_recorded_with_its_position(self, store, capsys):
        assert run(store, "pin", "abc", "--position", "3", "--reason", "премьера") == 0
        entry = documents(store)[0]
        assert entry["action"] == "pin" and entry["position"] == 3
        assert entry["reason"] == "премьера"

    def test_ban_boost_and_replace_are_recorded(self, store):
        run(store, "ban", "x", "--reason", "жалоба")
        run(store, "boost", "y", "--value", "0.2")
        run(store, "replace", "z", "w")
        kinds = [d["action"] for d in documents(store)]
        assert kinds == ["ban", "boost", "replace"]

    def test_unpin_and_unban_remove_the_decision(self, store):
        run(store, "pin", "abc")
        run(store, "ban", "abc")
        assert run(store, "unpin", "abc") == 0
        assert [d["action"] for d in documents(store)] == ["ban"]
        assert run(store, "unban", "abc") == 0
        assert documents(store) == []

    def test_removing_something_absent_reports_failure(self, store):
        store.write_text("[]", encoding="utf-8")
        assert run(store, "unpin", "нет-такого") == 1


class TestEveryDecisionExpires:
    def test_a_pin_gets_an_expiry_by_default(self, store):
        run(store, "pin", "abc")
        assert documents(store)[0]["expires_at"]

    def test_the_expiry_can_be_shortened(self, store):
        run(store, "pin", "abc", "--days", "1")
        expires = datetime.fromisoformat(documents(store)[0]["expires_at"])
        assert expires - datetime.now(timezone.utc) < timedelta(days=2)

    def test_audit_separates_active_from_expired(self, store, capsys):
        run(store, "pin", "живой", "--days", "30")
        stale = documents(store)
        stale.append({"action": "ban", "content_id": "старый",
                      "expires_at": (NOW - timedelta(days=400)).isoformat()})
        store.write_text(yaml.safe_dump(stale, allow_unicode=True), encoding="utf-8")
        capsys.readouterr()
        run(store, "audit")
        report = json.loads(capsys.readouterr().out)
        assert report["всего"] == 2
        assert report["действующих"] == 1


class TestDryRunChangesNothing:
    def test_a_dry_run_leaves_the_file_untouched(self, store):
        store.write_text("[]", encoding="utf-8")
        cli.main(["--file", str(store), "--dry-run", "pin", "abc"])
        assert documents(store) == []


class TestRollback:
    def test_rollback_clears_the_configuration(self, store):
        run(store, "pin", "abc")
        assert run(store, "rollback") == 0
        assert documents(store) == []

    def test_rollback_to_a_copy_restores_it(self, store, tmp_path):
        backup = tmp_path / "backup.yaml"
        backup.write_text(yaml.safe_dump(
            [{"action": "pin", "content_id": "из-копии", "position": 1}],
            allow_unicode=True), encoding="utf-8")
        run(store, "pin", "текущий")
        assert run(store, "rollback", "--to", str(backup)) == 0
        assert documents(store)[0]["content_id"] == "из-копии"

    def test_rollback_to_a_missing_copy_fails_loudly(self, store, tmp_path):
        assert run(store, "rollback", "--to", str(tmp_path / "нет.yaml")) == 1


class TestEditorCannotShowWhatDoesNotPlay:
    """Главное ограничение слоя: закрепление управляет порядком, а не допуском."""

    def _items(self, n=12):
        return [ItemFeatures(content_id=f"c{i}", title=f"Т{i}", content_type="movie",
                             poster="p.webp", playback_state=True,
                             added_at=NOW - timedelta(days=i), genres=(f"ж{i % 4}",))
                for i in range(n)]

    def test_a_pinned_unplayable_title_never_appears(self, store):
        run(store, "pin", "мертвец", "--position", "1")
        editorial = Editorial.from_documents(documents(store))
        pool = self._items() + [ItemFeatures(
            content_id="мертвец", title="Мертвец", content_type="movie",
            poster="p.webp", playback_state=False, added_at=NOW)]
        ranked = rank(pool, now=NOW, limit=12, editorial=editorial)
        assert "мертвец" not in [s.item.content_id for s in ranked]
        assert any(r["action"] == "pin_skipped" for r in editorial.audit_log)

    def test_a_boost_cannot_resurrect_an_unplayable_title(self, store):
        run(store, "boost", "мертвец", "--value", "10")
        editorial = Editorial.from_documents(documents(store))
        pool = self._items() + [ItemFeatures(
            content_id="мертвец", title="Мертвец", content_type="movie",
            poster="p.webp", playback_state=False, added_at=NOW)]
        ranked = rank(pool, now=NOW, limit=12, editorial=editorial)
        assert "мертвец" not in [s.item.content_id for s in ranked]

    def test_a_pin_does_move_a_playable_title_to_the_front(self, store):
        run(store, "pin", "c9", "--position", "1")
        editorial = Editorial.from_documents(documents(store))
        ranked = rank(self._items(), now=NOW, limit=12, editorial=editorial)
        assert ranked[0].item.content_id == "c9"


class TestTheStoreHoldsNoSecrets:
    def test_only_identifiers_positions_and_dates_are_written(self, store):
        run(store, "pin", "abc", "--reason", "премьера", "--author", "редакция")
        text = store.read_text(encoding="utf-8")
        for marker in ("Bearer", "token", "password", "secret", "api-token"):
            assert marker.lower() not in text.lower()


class TestBadInputIsRefused:
    def test_an_unknown_action_in_the_file_is_rejected(self, store):
        store.write_text(yaml.safe_dump(
            [{"action": "сделай-хорошо", "content_id": "x"}], allow_unicode=True),
            encoding="utf-8")
        with pytest.raises(ValueError):
            Editorial.from_documents(documents(store))

    def test_a_decision_without_a_content_id_is_rejected(self, store):
        with pytest.raises(ValueError):
            Editorial.from_documents([{"action": "pin"}])
