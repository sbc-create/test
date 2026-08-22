#!/usr/bin/env python3
"""Доказательство восстановления из бэкапа, а не наличия файла бэкапа.

Порядок: снимок состояния → бэкап → изменение данных → восстановление →
повторный снимок и сравнение. Проверка считается пройденной, только если после
восстановления вернулось прежнее содержимое, а внесённое изменение исчезло.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from factory import database  # noqa: E402

APP = ROOT / "blueprints" / "payload-next-multisite" / "app"
ARTIFACT = ROOT / "var" / "artifacts" / "restore-proof.json"
SCOPE = "anime"


def run_node(script: str, *args: str) -> tuple[int, str]:
    result = subprocess.run(
        [sys.executable, str(ROOT / "tests/tools/with_app_env.py"), "--scope", SCOPE, "--",
         str(APP / "node_modules/.bin/tsx"), str(APP / "scripts" / script), *args],
        cwd=ROOT, capture_output=True, text=True, timeout=600, check=False)
    return result.returncode, (result.stdout + result.stderr).strip()


def snapshot() -> dict:
    code, output = run_node("db-snapshot.ts")
    if code != 0:
        raise RuntimeError(f"снимок состояния не снят: {output[-600:]}")
    return json.loads(output.splitlines()[-1])


def main() -> int:
    steps: list[dict] = []

    def step(name: str, ok: bool, detail: str) -> None:
        steps.append({"step": name, "ok": ok, "detail": detail})
        print(("PASS  " if ok else "FAIL  ") + name + (f"\n      {detail}" if detail and not ok else ""))

    before = snapshot()
    step("снимок состояния до бэкапа", True, json.dumps(before, ensure_ascii=False))

    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    backup_path = ROOT / "var" / "backups" / "restore-proof" / f"{SCOPE}-{stamp}.sql"
    database.dump(SCOPE, backup_path)
    step("бэкап создан", backup_path.exists() and backup_path.stat().st_size > 0,
         f"{backup_path.relative_to(ROOT)} ({backup_path.stat().st_size} байт)")

    code, output = run_node("db-mutate.ts")
    step("данные изменены после бэкапа", code == 0, output[-400:])
    mutated = snapshot()
    step("изменение видно в состоянии", mutated != before,
         f"снимок не изменился после мутации: {json.dumps(mutated, ensure_ascii=False)}")
    step("изменены три вида данных: вставка, правка и удаление",
         mutated.get("posts") == before.get("posts") + 1
         and mutated.get("pages:digest") != before.get("pages:digest")
         and mutated.get("comments") == before.get("comments") - 1,
         f"до={json.dumps(before, ensure_ascii=False)} после={json.dumps(mutated, ensure_ascii=False)}")

    restored = database.restore(SCOPE, backup_path)
    step("восстановление выполнено", restored, "psql вернул ненулевой код" if not restored else "")

    after = snapshot()
    same = after == before
    step("состояние после восстановления совпадает с исходным", same,
         f"до={json.dumps(before, ensure_ascii=False)} после={json.dumps(after, ensure_ascii=False)}")
    step("внесённое изменение исчезло", after.get("posts") == before.get("posts"),
         f"ожидалось {before.get('posts')}, получено {after.get('posts')}")
    # Совпадение счётчиков без совпадения отпечатков означало бы восстановление
    # «правильного количества испорченных записей».
    digests = [key for key in before if key.endswith(":digest")]
    step("отпечатки содержимого совпадают", all(after.get(k) == before.get(k) for k in digests),
         ", ".join(f"{k}: {before.get(k)} → {after.get(k)}" for k in digests
                   if after.get(k) != before.get(k)))

    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(json.dumps({
        "backup": str(backup_path.relative_to(ROOT)),
        "before": before, "mutated": mutated, "after": after,
        "steps": steps,
        "restore_verified": all(item["ok"] for item in steps),
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    failed = [item for item in steps if not item["ok"]]
    print(f"\n{len(steps) - len(failed)}/{len(steps)} шагов пройдено; артефакт: {ARTIFACT.relative_to(ROOT)}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
