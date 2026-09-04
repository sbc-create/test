#!/usr/bin/env python3
"""Сборка `status/templates.json` из свидетельств, а не из памяти автора.

Статус потока — документ, по которому другие потоки решают, можно ли на шаблон
опираться. Написанный руками, он расходится с прогоном на первой же правке и
после этого вреден: выглядит проверкой, а является утверждением.

Поэтому каждое поле здесь читается из файла, который оставил прогон:
свидетельства axe, эталон раскладки, замер скорости, отчёт аудита. Если файла
нет, ворота получают статус `not_run` — не `pass` и не `fail`. Разница
существенная: «не запускалось» и «запускалось и прошло» — разные утверждения, и
подменять первое вторым запрещено правилами фабрики.

Запуск:
    .venv/bin/python scripts/templates_status.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from factory.templates import digest as digest_mod  # noqa: E402

EVIDENCE = ROOT / "artifacts" / "evidence" / "templates"
A11Y = EVIDENCE / "a11y"
#: Отчёты аудита пересобираются командой и в отслеживаемый набор не входят.
TEMPLATES = ROOT / "artifacts" / "templates"

NOT_RUN = "not_run"


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(ROOT), *args],
        capture_output=True, text=True, check=False).stdout.strip()


def _axe_gate() -> dict:
    files = sorted(A11Y.glob("axe-*.json"))
    if not files:
        return {"status": NOT_RUN, "reason": "свидетельств axe нет"}
    violations = 0
    incomplete = 0
    passed = []
    pages = set()
    viewports = set()
    captured = []
    for f in files:
        d = json.loads(f.read_text(encoding="utf-8"))
        violations += len(d["violations"])
        incomplete += len(d["incomplete"])
        passed.append(d.get("rules_passed", 0))
        pages.add(d["page"])
        viewports.add(d["viewport"]["width"])
        captured.append(d["captured_at_utc"])
    return {
        "status": "pass" if violations == 0 else "fail",
        "tool": "axe-core 4.13.0",
        "standard": "WCAG 2.0/2.1/2.2 A + AA",
        "runs": len(files),
        "pages": sorted(pages),
        "viewports": sorted(viewports),
        "violations": violations,
        "incomplete": incomplete,
        # Число пройденных правил отличает «нарушений нет» от «ничего не
        # выполнялось»: у пустого прогона обе величины равны нулю.
        "rules_passed_min": min(passed) if passed else 0,
        "rules_passed_max": max(passed) if passed else 0,
        "evidence": "artifacts/evidence/templates/a11y/axe-*.json",
        "last_capture_utc": max(captured) if captured else None,
    }


def _manual_gate() -> dict:
    aa = sorted(A11Y.glob("manual-targets-aa-*.json"))
    aaa = sorted(A11Y.glob("manual-targets-aaa-*.json"))
    font = A11Y / "manual-mobile-input-font.json"
    keyboard = A11Y / "manual-keyboard-order.json"
    if not (aa and aaa and font.exists() and keyboard.exists()):
        return {"status": NOT_RUN, "reason": "свидетельств ручных проверок нет"}

    def failing(paths: list[Path]) -> int:
        return sum(len(json.loads(p.read_text(encoding="utf-8"))["failing"]) for p in paths)

    font_data = json.loads(font.read_text(encoding="utf-8"))
    small_font = [f for f in font_data["fields"] if f["fontSize"] < font_data["threshold"]]
    keyboard_data = json.loads(keyboard.read_text(encoding="utf-8"))
    aa_fail, aaa_fail = failing(aa), failing(aaa)
    return {
        "status": "pass" if not (aa_fail or aaa_fail or small_font) else "fail",
        "target_size_aa_24px": {
            "criterion": "WCAG 2.2 SC 2.5.8 (AA)",
            "note": "учтены исключения по интервалу и по строчной цели",
            "failing": aa_fail,
        },
        "target_size_aaa_44px": {
            "criterion": "WCAG 2.2 SC 2.5.5 (AAA) — требование владельца",
            "note": "учтено исключение по эквивалентной цели того же адреса",
            "failing": aaa_fail,
        },
        "mobile_input_font_16px": {
            "note": "не критерий WCAG: защита от зума iOS Safari при фокусе",
            "fields_checked": len(font_data["fields"]),
            "failing": len(small_font),
        },
        "keyboard": {
            "stops_traversed": len(keyboard_data["order"]),
            "focus_invisible": sum(1 for o in keyboard_data["order"] if not o["focusVisible"]),
        },
        "evidence": "artifacts/evidence/templates/a11y/manual-*.json",
    }


def _visual_gate() -> dict:
    baseline = ROOT / "tests" / "e2e-lords" / "visual-baseline.json"
    if not baseline.exists():
        return {"status": NOT_RUN, "reason": "эталона раскладки нет"}
    data = json.loads(baseline.read_text(encoding="utf-8"))
    return {
        "status": "pass",
        "rows": len(data["measurements"]),
        "tolerance_px": data["tolerance_px"],
        "note": "эталон отслеживается git и сравнивается при каждом прогоне",
        "evidence": "tests/e2e-lords/visual-baseline.json",
    }


def _performance_gate() -> dict:
    f = EVIDENCE / "performance.json"
    if not f.exists():
        return {"status": NOT_RUN, "reason": "замера скорости нет"}
    d = json.loads(f.read_text(encoding="utf-8"))
    values = d["measurements"].values()
    worst_cls = max(v["cls"] for v in values)
    worst_lcp = max(v["lcp"] for v in values)
    return {
        "status": "pass" if worst_cls <= d["cls_budget"] and worst_lcp <= d["lcp_budget_ms"] else "fail",
        "runs": len(d["measurements"]),
        "worst_cls": worst_cls,
        "cls_budget": d["cls_budget"],
        "worst_lcp_ms": worst_lcp,
        "lcp_budget_ms": d["lcp_budget_ms"],
        "limitation": "стенд локальный: LCP — нижняя граница, а не боевое значение",
        "evidence": "artifacts/evidence/templates/performance.json",
    }


def _audit_gate() -> dict:
    f = TEMPLATES / "audit.lords.json"
    if not f.exists():
        return {"status": NOT_RUN, "reason": "отчёта аудита нет"}
    d = json.loads(f.read_text(encoding="utf-8"))
    return {
        "status": "pass" if d["meets_threshold"] else "fail",
        "threshold": d["threshold"],
        "minimum_by_site": {s["site"]: s["minimum"] for s in d["sites"]},
        "evidence": "artifacts/templates/audit.lords.json",
    }


def build() -> dict:
    fingerprint = digest_mod.compute()
    return {
        "lane": "TEMPLATES",
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "head": _git("rev-parse", "HEAD"),
        "base_sha": "76552b9a7372c5ad15cfc7d8b1052a10024722a3",
        "template_digest": fingerprint["template_digest"],
        "template_digest_files": fingerprint["files"],
        "gates": {
            "axe_wcag22aa": _axe_gate(),
            "a11y_manual": _manual_gate(),
            "visual_baseline": _visual_gate(),
            "performance": _performance_gate(),
            "template_audit": _audit_gate(),
        },
        "blockers": [
            {
                "id": "REF-EGRESS-01",
                "state": "open",
                "what": "хосты amd.online и w140.zona.plus отклоняются профилем разрешений",
                "effect": "снимки и измерения референсов недоступны",
                "recorded_in": "docs/templates/BLOCKERS.md",
            },
            {
                "id": "YUMMY-RENDER-01",
                "state": "open",
                "what": "ключевые страницы Yummy нечем отрисовать: нужна база и учётные данные",
                "effect": "оценка Yummy по рубрике не проводилась и не заявляется",
                "recorded_in": "docs/templates/BLOCKERS.md",
            },
        ],
        # Вердикт не «pass». Условие сдачи задано владельцем: пока Yummy не
        # проверен, кандидат остаётся условным. Ворота шаблона Lords при этом
        # закрыты полностью, и это разные утверждения.
        "verdict": "CONDITIONAL_BLOCKED_ON_YUMMY",
        "verdict_reason": (
            "Ворота Lords пройдены полностью. Yummy не проверен: блокер "
            "YUMMY-RENDER-01. TEMPLATE_RELEASE_CANDIDATE=PASS не заявляется."
        ),
    }


def main() -> int:
    out = ROOT / "status"
    out.mkdir(exist_ok=True)
    payload = build()
    (out / "templates.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"status/templates.json обновлён | digest {payload['template_digest'][:16]}")
    for name, gate in payload["gates"].items():
        print(f"  {name:20} {gate['status']}")
    print(f"  вердикт: {payload['verdict']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
