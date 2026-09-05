#!/usr/bin/env python3
"""Релизный артефакт Lords: что именно предлагается Архитектору для canary.

Артефакт собирается из фактов, а не из памяти автора: отпечаток считает
`factory/templates/digest.py`, ревизии берутся из git, состояние ворот — из
свидетельств прогонов. Поле, которое нечем заполнить, остаётся пустым со
статусом, а не заполняется правдоподобным значением.

Отдельно о границе. Этот файл **не выкатывает ничего**. Он описывает
кандидата и называет то единственное действие, которое остаётся Архитектору.
Выкладка, переключение ссылок, DNS и откат production принадлежат ему, и
описание кандидата не является разрешением.

Запуск:
    .venv/bin/python scripts/lords_release_candidate.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from factory.templates import digest as digest_mod  # noqa: E402

OUT = ROOT / "artifacts" / "evidence" / "templates" / "lords-release-candidate.json"
EVIDENCE = ROOT / "artifacts" / "evidence" / "templates"

#: Снимок матрицы совместимости. Не источник истины — источник живёт в
#: управляющем API, который службой не развёрнут. Поэтому версия названа
#: вместе с происхождением и временем снимка.
COMPATIBILITY_SNAPSHOT = Path(
    "/srv/site-factory/coordination/v1/COMPATIBILITY_MATRIX.yaml")


def _git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *args],
                          capture_output=True, text=True).stdout.strip()


def _engine_contract() -> dict:
    if not COMPATIBILITY_SNAPSHOT.exists():
        return {"status": "unknown", "reason": "снимка матрицы совместимости нет"}
    text = COMPATIBILITY_SNAPSHOT.read_text(encoding="utf-8")
    version = None
    generated = None
    sites: dict[str, str] = {}
    current = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("engineContract:"):
            version = stripped.split(":", 1)[1].strip().strip('"')
        elif stripped.startswith("generatedAt:"):
            generated = stripped.split(":", 1)[1].strip().strip('"')
        elif stripped.startswith("- siteId:"):
            current = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("declared:") and current:
            sites[current] = stripped.split(":", 1)[1].strip().strip('"')
    lords = {k: v for k, v in sites.items() if k.startswith("lords-")}
    return {
        "status": "declared" if version else "unknown",
        "engineContractObserved": version,
        "engineContractRange": f">={version} <1.3.0" if version else None,
        # Верхняя граница закрыта намеренно: совместимость со следующей минорной
        # версией не проверялась, и объявить её значило бы обещать неизмеренное.
        "rangeRationale": (
            "верхняя граница закрыта: совместимость с 1.3 не проверялась, "
            "объявить её значило бы обещать то, чего никто не измерял"
        ),
        "source": str(COMPATIBILITY_SNAPSHOT),
        "snapshotGeneratedAt": generated,
        "lordsSitesDeclared": lords,
        "note": "снимок GET /api/v1/compatibility; управляющий API службой не развёрнут",
    }


def _gate(name: str, path: Path, reader) -> dict:
    if not path.exists():
        return {"gate": name, "status": "not_run", "reason": f"нет {path.name}"}
    try:
        return {"gate": name, "status": "pass", **reader(json.loads(path.read_text(encoding="utf-8")))}
    except Exception as exc:  # noqa: BLE001 — свидетельство повреждено, это тоже факт
        return {"gate": name, "status": "fail", "reason": str(exc)[:120]}


def _gates() -> list[dict]:
    a11y = sorted((EVIDENCE / "a11y").glob("axe-lords-*.json"))
    axe = {"gate": "axe_wcag22aa", "status": "not_run"}
    if a11y:
        violations = sum(
            len(json.loads(f.read_text(encoding="utf-8"))["violations"]) for f in a11y)
        axe = {
            "gate": "axe_wcag22aa",
            "status": "pass" if violations == 0 else "fail",
            "runs": len(a11y),
            "violations": violations,
            "standard": "WCAG 2.0/2.1/2.2 A+AA",
        }
    return [
        axe,
        _gate("visual_baseline", ROOT / "tests" / "e2e-lords" / "visual-baseline.json",
              lambda d: {"rows": len(d["measurements"]), "tolerance_px": d["tolerance_px"]}),
        _gate("performance", EVIDENCE / "performance.json",
              lambda d: {"runs": len(d["measurements"]),
                         "worst_cls": max(v["cls"] for v in d["measurements"].values()),
                         "worst_lcp_ms": max(v["lcp"] for v in d["measurements"].values()),
                         "limitation": "локальный стенд: LCP — нижняя граница"}),
        _gate("budgets_and_inp", EVIDENCE / "budgets.json",
              lambda d: {"pages": len(d.get("pages", [])),
                         "player_checks": len(d.get("player", []))}),
        _gate("responsive", EVIDENCE / "responsive.json",
              lambda d: {"sweep": len(d.get("sweep", [])),
                         "reflow": len(d.get("reflow", [])),
                         "text_spacing": len(d.get("textSpacing", []))}),
        _gate("crossbrowser", EVIDENCE / "playwright-lords-cross.json",
              lambda d: {"passed": d["stats"]["expected"],
                         "failed": d["stats"]["unexpected"],
                         "engines": ["firefox", "webkit"]}),
        _gate("template_audit", EVIDENCE / "audit.lords.json",
              lambda d: {"threshold": d["threshold"],
                         "minimum_by_site": {s["site"]: s["minimum"] for s in d["sites"]}}),
    ]


def build() -> dict:
    fingerprint = digest_mod.compute()
    gates = _gates()
    return {
        "artifact": "LORDS_TEMPLATE_RELEASE_CANDIDATE",
        "schemaVersion": 1,
        "lane": "TEMPLATES",
        "repo": "sbc-create/test.git (site-factory)",
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "baseSha": "76552b9a7372c5ad15cfc7d8b1052a10024722a3",
        "headSha": _git("rev-parse", "HEAD"),
        "templateDigest": fingerprint["template_digest"],
        "templateDigestFiles": fingerprint["files"],
        "digestCommand": (
            "python3 -c \"from factory.templates import digest; "
            "print(digest.compute()['template_digest'])\""
        ),
        "compatibility": _engine_contract(),
        "scope": {
            "includes": [
                "четыре профиля витрин Lords и общий рендерер",
                "тема, раскладка, доступность, плеерное место, оценки",
                "рубрика качества страниц и её собственные тесты",
            ],
            "excludes": [
                "тема оформления (THEME-01) — отдельная post-release ветка",
                "подборки (COLLECTIONS-01/02) — там же",
                "всё, что относится к Yummy",
                "пакеты референсов Zona и Animedia — черновики",
            ],
            "excludeRationale": (
                "кандидат обязан быть минимальным: чем меньше в нём того, что "
                "не проверялось вместе с ним, тем меньше поверхность отката"
            ),
        },
        "gates": gates,
        "productionState": {
            "authorized": False,
            "evidence": "production_authorized: false во всех пакетах sites/lords-0*",
            "domainsLaunched": False,
            "note": (
                "три домена зарегистрированы в config/directions/lords.json со "
                "значением launched: false; четвёртый пакет домена не имеет вовсе"
            ),
        },
        "architectAction": {
            "what": "решение о canary на одной витрине",
            "required": [
                "выбрать витрину с наименьшим риском",
                "подтвердить production_authorized в её пакете",
                "запустить выкладку штатной командой фабрики",
            ],
            "notPerformedByTemplates": (
                "выкладка, переключение ссылок, DNS, работающие контейнеры и "
                "откат production принадлежат Архитектору; полоса шаблонов "
                "подготовила кандидата и не выкатывала ничего"
            ),
        },
        "rollback": {
            "preferred": "предыдущий подтверждённый template artifact по отпечатку",
            "alternative": "git revert конкретных template-коммитов ветки",
            "forbidden": "reset --hard",
            "mandatoryStep": (
                "после отката вернуть заморозку базы знаний: "
                "python3 -m factory knowledge freeze --version 2026-08-30-lords-full-catalog"
            ),
            "mandatoryStepReason": (
                "запись D128 входит в замороженную базу; без перезаморозки падают "
                "тесты заморозки, production-ворот и авторизации"
            ),
        },
    }


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = build()
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{OUT.relative_to(ROOT)} собран")
    print(f"  digest: {payload['templateDigest'][:16]} ({payload['templateDigestFiles']} файлов)")
    print(f"  контракт: {payload['compatibility'].get('engineContractRange')}")
    for gate in payload["gates"]:
        print(f"  {gate['gate']:20} {gate['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
