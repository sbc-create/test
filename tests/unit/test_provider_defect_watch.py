import importlib.util
import json
from pathlib import Path

_PATH = Path(__file__).resolve().parents[2] / "automation" / "local" / "provider-defect-watch.py"
_spec = importlib.util.spec_from_file_location("provider_defect_watch", _PATH)
pdw = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pdw)


def _snapshot(tmp_path: Path, name: str, slugs: list[str]) -> str:
    p = tmp_path / name
    p.write_text(json.dumps({"catalog_revision": "r1", "catalog_built_at": "2026-10-27T03:00:00Z",
                             "details": {s: {"id": s} for s in slugs}}), encoding="utf-8")
    return str(p)


def test_returned_record_is_reported_once_any_snapshot_has_it(tmp_path):
    a = _snapshot(tmp_path, "a.json", ["drugoe"])
    b = _snapshot(tmp_path, "b.json", ["chuzhaya-zhizn"])
    r = pdw.проверить({"watch": [{"slug": "chuzhaya-zhizn", "catalogs": [a, b]}]})
    assert r[0]["returned"] is True
    assert [s["present"] for s in r[0]["catalogs"]] == [False, True]


def test_absent_and_unreadable_snapshots_are_not_a_return(tmp_path):
    a = _snapshot(tmp_path, "a.json", ["chuzhaya-zhizn-moego-serdca"])
    r = pdw.проверить({"watch": [{"slug": "chuzhaya-zhizn", "catalogs": [a, str(tmp_path / "missing.json")]}]})
    assert r[0]["returned"] is False
    assert r[0]["catalogs"][1]["readable"] is False


def test_committed_watch_list_is_valid():
    data = json.loads((_PATH.parents[2] / "config" / "provider-defect-watch.json").read_text(encoding="utf-8"))
    assert {w["slug"] for w in data["watch"]} >= {"chuzhaya-zhizn"}
    assert all(w["catalogs"] for w in data["watch"])
