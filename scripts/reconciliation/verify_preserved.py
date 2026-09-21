#!/usr/bin/env python3
"""Проверяет, что чужие незакоммиченные изменения остались нетронутыми.

Снимок их состояния снят в начале этапа. Здесь он пересчитывается заново:
совпадение размеров и sha256 — доказательство того, что работа этапа не
задела чужой checkout. Утверждать это без пересчёта нельзя: «я туда не писал»
проверкой не является.

Запуск: python3 scripts/reconciliation/verify_preserved.py
"""

from __future__ import annotations

import hashlib
import json
import os
import sys

СНИМОК = ("/home/claude/wt-ten-templates-01/artifacts/evidence/"
          "ten-template-factory-01/preserved/shared-checkout-inventory.json")
ОТЧЁТ = "artifacts/evidence/cursor-work-reconciliation-01/PRESERVED_VERIFY.json"


def main() -> int:
    if not os.path.isfile(СНИМОК):
        print(f"снимок не найден: {СНИМОК}", file=sys.stderr)
        return 1
    with open(СНИМОК, encoding="utf-8") as handle:
        снимок = json.load(handle)

    корень = снимок["source_checkout"]
    расхождения: list[dict[str, object]] = []
    проверено = 0
    for запись in снимок["files"]:
        путь = os.path.join(корень, str(запись["path"]))
        if not os.path.isfile(путь):
            расхождения.append({"path": запись["path"], "что": "исчез"})
            continue
        with open(путь, "rb") as handle:
            данные = handle.read()
        проверено += 1
        if hashlib.sha256(данные).hexdigest() != запись["sha256"]:
            расхождения.append({
                "path": запись["path"], "что": "содержимое изменилось",
                "было": запись["sha256"][:16], "стало": hashlib.sha256(данные).hexdigest()[:16],
            })

    документ = {
        "источник_снимка": СНИМОК,
        "checkout": корень,
        "файлов_в_снимке": снимок["file_count"],
        "файлов_проверено": проверено,
        "FOREIGN_FILES_CHANGED": len(расхождения),
        "расхождения": расхождения,
        "вывод": ("Чужие изменения не тронуты." if not расхождения
                  else "ЧУЖИЕ ИЗМЕНЕНИЯ ЗАТРОНУТЫ — разобраться до продолжения."),
    }
    os.makedirs(os.path.dirname(ОТЧЁТ), exist_ok=True)
    with open(ОТЧЁТ, "w", encoding="utf-8") as handle:
        json.dump(документ, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps({k: v for k, v in документ.items() if k != "расхождения"},
                     ensure_ascii=False, indent=2))
    return 0 if not расхождения else 1


if __name__ == "__main__":
    raise SystemExit(main())
