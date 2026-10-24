"""Регулярный приём поставок Qwen: один проход по var/qwen-intake (запуск по таймеру или вручную).

    python3 tools/qwen_intake_run.py [--intake var/qwen-intake] [--max-attempts 3]

Что делает один проход
----------------------
1. Каждый архив `*.tar.gz` и каталог с manifest.json в каталоге приёма — по sha256 содержимого: уже
   обработанный не трогается, новый проходит `plan` штатного приёмника (`qwen_recipes_intake.py`).
   Результат — в `var/qwen-recipes/<set_id>/` (другая версия того же set_id — в `<set_id>@<sha8>/`,
   прежний результат не затирается). Исходные архивы не меняются.
2. Состояние — `var/qwen-recipes/runs.json`: по каждому архиву sha256, set_id, время, итог, принято
   по сайтам, причины отказа; запись сохраняется после каждого архива — сбой посередине
   не теряет сделанного, следующий проход продолжает с необработанного.
3. Ошибка чтения архива — не падение прохода: попытка записывается, после `--max-attempts` неудач
   архив помечается `failed` и больше не берётся до появления нового файла.
4. Очередь тем `tools/qwen_contract/queue.json` пересобирается: опубликованное уходит из неё.

Импорт принятых блюд в базы сайтов и выпуск комплекта сюда не входят: это отдельные штатные шаги
(`set-import` с резервной копией, `kit build`, выкладка владельцем) — проход только готовит их
и называет в `runs.json` (`next`).
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, REPO / "tools" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


intake = _load("qwen_recipes_intake")
topic_queue = _load("qwen_topic_queue")


def sha256_of(p: Path) -> str:
    h = hashlib.sha256()
    files = (
        [p]
        if p.is_file()
        else sorted(x for x in p.rglob("*") if x.is_file() and not x.is_symlink())
    )
    for f in files:
        h.update(str(f.relative_to(p) if p.is_dir() else f.name).encode())
        h.update(f.read_bytes())
    return h.hexdigest()


def deliveries(intake_dir: Path) -> list[Path]:
    out = sorted(intake_dir.glob("*.tar.gz"))
    out += sorted(d for d in intake_dir.iterdir() if d.is_dir() and any(d.rglob("manifest.json")))
    return out


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run(
    intake_dir: Path, out_root: Path, max_attempts: int = 3, existing: dict | None = None
) -> dict:
    state_path = out_root / "runs.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else {"runs": {}}
    out_root.mkdir(parents=True, exist_ok=True)
    done = []

    def save():
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=1) + "\n")

    for src in deliveries(intake_dir):
        key = sha256_of(src)
        rec = state["runs"].get(key, {"file": src.name, "attempts": 0})
        if rec.get("status") in ("done", "failed"):
            continue
        rec["attempts"] = rec.get("attempts", 0) + 1
        rec["at"] = now()
        try:
            files = intake.read_set(src)
            res = intake.plan(files, existing=existing)
        except Exception as e:  # noqa: BLE001 — один плохой архив не останавливает остальные
            rec["error"] = f"{type(e).__name__}: {str(e)[:200]}"
            rec["status"] = "failed" if rec["attempts"] >= max_attempts else "retry"
            state["runs"][key] = rec
            save()
            continue
        man = next(
            (
                d
                for n, d in files.items()
                if n.rsplit("/", 1)[-1] == "manifest.json" and isinstance(d, dict)
            ),
            {},
        )
        sid = str(man.get("set_id") or src.name.split(".")[0])
        sid = (
            sid
            if all(c.isalnum() or c in "._-" for c in sid)
            else hashlib.sha1(sid.encode()).hexdigest()[:12]
        )
        others = [k for k, r in state["runs"].items() if r.get("set_id") == sid and k != key]
        # каталог уже занят (другой версией или разбором до этого механизма) — прежнее не затираем
        folder = out_root / (
            sid if not others and not (out_root / sid).exists() else f"{sid}@{key[:8]}"
        )
        if res.get("status") != "OK":
            rec.update(
                status="done", set_id=sid, result=res.get("status"), reason=res.get("reason")
            )
        else:
            ids = {
                site: {r_["recipe_id"] for r_ in recs}
                for site, recs in res.get("_accepted", {}).items()
            }
            report = intake.write(res, folder)
            accepted = report.get("accepted", {})
            # «принято» — и уже опубликованные из этого набора (свой recipe_id); новые — без них
            pub = intake.published_titles() if existing is None else existing
            on_site = {site: {x[2] for x in pub.get(site, [])} for site in pub}
            new = {site: len(ids.get(site, set()) - on_site.get(site, set())) for site in accepted}
            reasons: dict[str, int] = {}
            for d in report.get("deferred", []):
                reasons[d["kind"]] = reasons.get(d["kind"], 0) + 1
            rec.update(
                status="done",
                set_id=sid,
                folder=str(folder.relative_to(REPO))
                if folder.is_relative_to(REPO)
                else str(folder),
                result="OK",
                accepted=accepted,
                new=new,
                deferred=reasons,
                next=(
                    "set-import принятых из batches/<сайт>, затем kit build и выкладка"
                    if any(new.values())
                    else "новых принятых нет: исправления — в report.json (deferred) этой поставки"
                ),
            )
        rec.pop("error", None)
        state["runs"][key] = rec
        save()
        done.append(rec)
    q = topic_queue.build(existing=existing)
    (REPO / "tools" / "qwen_contract" / "queue.json").write_text(
        json.dumps(q, ensure_ascii=False, indent=1) + "\n"
    )
    state["last_pass"] = {"at": now(), "processed": len(done), "queue": q["totals"]}
    save()
    return {
        "processed": [
            {k: r.get(k) for k in ("file", "set_id", "status", "accepted", "new", "deferred")}
            for r in done
        ],
        "queue": q["totals"],
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="qwen_intake_run")
    ap.add_argument("--intake", type=Path, default=REPO / "var" / "qwen-intake")
    ap.add_argument("--out", type=Path, default=REPO / "var" / "qwen-recipes")
    ap.add_argument("--max-attempts", type=int, default=3)
    a = ap.parse_args(argv)
    if not a.intake.is_dir():
        print(
            json.dumps({"status": "BLOCKED_ACCESS", "missing": str(a.intake)}, ensure_ascii=False)
        )
        return 2
    print(json.dumps(run(a.intake, a.out, a.max_attempts), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
