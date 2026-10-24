"""Регулярный приём поставок Qwen: один проход идемпотентен, сбой одного архива ограниченно повторяется."""

import importlib.util
import io
import json
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("run", ROOT / "tools" / "qwen_intake_run.py")
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)
EXAMPLE = ROOT / "tools" / "qwen_contract" / "example"
NO_SITE = {"bestreciept.site": [], "myfood.mobi": []}


def _tgz(path, members):
    with tarfile.open(path, "w:gz") as t:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            t.addfile(info, io.BytesIO(data))


def _delivery(path, set_id):
    man = json.loads((EXAMPLE / "manifest.json").read_text(encoding="utf-8"))
    man["set_id"] = set_id
    _tgz(
        path,
        {
            "manifest.json": json.dumps(man).encode(),
            "dishes/EXAMPLE-001.json": (EXAMPLE / "dishes" / "EXAMPLE-001.json").read_bytes(),
        },
    )


def test_pass_is_idempotent_keeps_old_results_and_retries_bad_archive(tmp_path, monkeypatch):
    monkeypatch.setattr(r, "REPO", tmp_path)
    (tmp_path / "tools" / "qwen_contract").mkdir(parents=True)
    inbox, out = tmp_path / "in", tmp_path / "out"
    inbox.mkdir()
    (out / "SET-A").mkdir(parents=True)  # разбор до появления прохода — не затирается
    (out / "SET-A" / "report.json").write_text("old")
    _delivery(inbox / "a.tar.gz", "SET-A")
    (inbox / "broken.tar.gz").write_bytes(b"not a tar")

    first = r.run(inbox, out, max_attempts=2, existing=NO_SITE)
    assert [x["set_id"] for x in first["processed"]] == ["SET-A"]
    assert (out / "SET-A" / "report.json").read_text() == "old"
    state = json.loads((out / "runs.json").read_text())
    folders = [v.get("folder") for v in state["runs"].values() if v.get("set_id") == "SET-A"]
    assert folders and folders[0].endswith(tuple(f"SET-A@{k[:8]}" for k in state["runs"]))
    bad = next(v for v in state["runs"].values() if v["file"] == "broken.tar.gz")
    assert bad["status"] == "retry" and bad["attempts"] == 1

    second = r.run(inbox, out, max_attempts=2, existing=NO_SITE)  # обработанное не берётся повторно
    assert second["processed"] == []
    bad = next(
        v
        for v in json.loads((out / "runs.json").read_text())["runs"].values()
        if v["file"] == "broken.tar.gz"
    )
    assert bad["status"] == "failed" and bad["attempts"] == 2
    assert r.run(inbox, out, max_attempts=2, existing=NO_SITE)["processed"] == []
    assert (out / "queue.json").is_file()
