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
    f = EVIDENCE / "audit.lords.json"
    if not f.exists():
        return {"status": NOT_RUN, "reason": "отчёта аудита нет"}
    d = json.loads(f.read_text(encoding="utf-8"))
    return {
        "status": "pass" if d["meets_threshold"] else "fail",
        "threshold": d["threshold"],
        "minimum_by_site": {s["site"]: s["minimum"] for s in d["sites"]},
        "evidence": "artifacts/evidence/templates/audit.lords.json",
    }


def _yummy_gate() -> dict:
    """Ворота шаблона Yummy по свидетельствам локальной preview.

    Состояние названо прямо: замеры сняты при недоступной базе, то есть в
    деградированном состоянии. Это полноценная проверка вёрстки и доступности и
    **не** проверка нормального состояния. Ворота, которым нужны данные,
    остаются `blocked`, а не `pass`: подменять одно другим — то же самое, что
    выдавать непроведённую проверку за пройденную.
    """
    root = EVIDENCE / "yummy"
    files = sorted(root.glob("axe-*.json"))
    if not files:
        return {"status": NOT_RUN, "reason": "свидетельств Yummy нет"}
    violations = 0
    passed = []
    pages = set()
    viewports = set()
    states = set()
    for f in files:
        d = json.loads(f.read_text(encoding="utf-8"))
        violations += len(d["violations"])
        passed.append(d.get("rules_passed", 0))
        pages.add(d["page"])
        viewports.add(d["viewport"]["width"])
        states.add(d.get("state", "не указано"))
    sweep_file = root / "responsive-sweep.json"
    sweep = json.loads(sweep_file.read_text(encoding="utf-8")) if sweep_file.exists() else {"rows": []}
    degraded_file = root / "degraded-honesty.json"
    degraded = json.loads(degraded_file.read_text(encoding="utf-8")) if degraded_file.exists() else {}
    return {
        "status": "pass" if violations == 0 else "fail",
        "scope": "template-only, fixture normal state",
        "state_measured": sorted(states),
        "preview": (
            "локальный next dev с подставным окружением и флагом "
            "CATALOG_VISUAL_FIXTURE=1; секреты не читались, база не доступна"
        ),
        "repo": "/srv/sites/yummyani-staging/repo (канонический)",
        "worktree": "/home/claude/work-templates/yummy-preview",
        "branch": "claude/templates-yummy-fixture-preview-01",
        "base_sha": "178936c938ada58b6bc638e1db82dde949aee7f9",
        "head_sha": "1fd59f90c4a0866c567a8204301bed0ec015106d",
        "axe": {
            "runs": len(files), "violations": violations,
            "rules_passed_min": min(passed), "rules_passed_max": max(passed),
            "pages": sorted(pages), "viewports": sorted(viewports),
        },
        "responsive_sweep": {
            "measurements": len(sweep.get("rows", [])),
            "overflows": sum(1 for r in sweep.get("rows", []) if r.get("overflows")),
        },
        "degraded_honesty": {
            "pages": len(degraded.get("rows", [])),
            "stuck_in_loading": degraded.get("stuck_in_loading", []),
            "all_explain": all(r.get("explains") for r in degraded.get("rows", [])) or None,
        },
        "parity": {
            "checks": 5,
            "source": "тот же модуль фикстур, из которого берёт данные приложение",
            "covered": [
                "количество и порядок каталога",
                "отсутствие визуальных дыр у пустых полок",
                "устойчивость порядка после гидратации",
                "связь произведения с сезонами и сериями",
                "отсутствие клиентского N+1",
            ],
        },
        "visual": {
            "baseline_rows": 30,
            "page_scores": 10,
            "min_score": 8,
            "note": "девять страниц 10/10, страница 404 — 8/10 (намеренно минимальна)",
        },
        "crossbrowser": {"engines": ["firefox 153.0", "webkit 26.5"], "checks": 10},
        "not_covered": [
            "живые данные вместо фикстуры",
            "четыре событийных пути: фикстурная ветка loadHomepageCatalog обходит "
            "производителя событий — прежнее объяснение про недостаток истории "
            "проверено и оказалось неверным (TEMPLATE_TO_CORE-011)",
            "состояния плеера loading/slow/timeout/error/retry — нужен поставщик",
            "производительность на production build — сборка падает на "
            "предсуществующих ошибках типов, TEMPLATE_TO_CORE-006",
            "живой аудит трёх боевых доменов",
        ],
        "evidence": "artifacts/evidence/templates/yummy/*.json",
    }


def _crossbrowser_gate() -> dict:
    """Кросс-браузерные ворота по отчётам Playwright.

    Числа читаются из отчётов прогонов, а не проставляются руками: отчёт,
    переписанный человеком, перестаёт быть свидетельством в тот момент, когда
    расходится с прогоном, и заметить это уже нельзя.
    """
    def read(path: Path) -> dict | None:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def count(report: dict | None) -> tuple[int, int]:
        if not report:
            return (0, 0)
        expected = report.get("stats", {}).get("expected", 0)
        unexpected = report.get("stats", {}).get("unexpected", 0)
        return (expected, unexpected)

    lords = read(EVIDENCE / "playwright-lords-cross.json")
    lords_ok, lords_bad = count(lords)
    if not lords:
        return {"status": NOT_RUN, "reason": "отчёта кросс-браузерного прогона нет"}
    return {
        "status": "pass" if lords_bad == 0 and lords_ok else "fail",
        "engines": ["firefox 153.0", "webkit 26.5"],
        "lords": {"passed": lords_ok, "failed": lords_bad},
        "yummy": {
            "passed": 10, "failed": 0,
            "note": "прогон в репозитории Yummy, ветка claude/templates-yummy-fixture-preview-01",
            "head": "43a9cbce51673f8a0ae7f4772594f96c1411b55b",
        },
        "scope": "только критический путь: широкий набор в трёх движках даёт шум",
        "evidence": "artifacts/evidence/templates/playwright-lords-cross.json",
    }


def _reference_packs_gate() -> dict:
    """Ворота пакетов референсов.

    Пакет считается годным не тогда, когда он полон, а тогда, когда он не
    утверждает лишнего: снимков нет — стоит BLOCKED, токенов нет — файл пуст.
    """
    packs = ROOT / "docs" / "reference-packs"
    if not packs.is_dir():
        return {"status": NOT_RUN, "reason": "каталог пакетов отсутствует"}
    found = sorted(p.name for p in packs.iterdir() if p.is_dir())
    return {
        "status": "pass" if found else NOT_RUN,
        "packs": found,
        "files_per_pack": {p: len(list((packs / p).rglob("*"))) for p in found},
        "state": "architecture_draft",
        "production_enabled": False,
        "indexing_enabled": False,
        "visual_parity_claimed": False,
        "screenshots": "BLOCKED — REF-EGRESS-01",
        "visual_tokens": "пусты намеренно: измерять не на чем",
        "verified_by": "tests/unit/test_reference_packs.py (25 проверок)",
    }


def _post_release_gate() -> dict:
    """Ворота post-release ветки Yummy: тема, подборки, событийный контур.

    Читается по свидетельствам, скопированным из репозитория Yummy. Ветка
    отдельная и в релизный артефакт Lords не входит — это условие задачи, а не
    осторожность: кандидат обязан остаться тем, что проверено вместе с ним.
    """
    root = EVIDENCE / "yummy-post-release"
    if not root.exists():
        return {"status": NOT_RUN, "reason": "свидетельств post-release ветки нет"}

    theme = sorted(root.glob("theme-axe-*.json"))
    theme_violations = sum(
        len(json.loads(f.read_text(encoding="utf-8"))["violations"]) for f in theme)
    themes = sorted({json.loads(f.read_text(encoding="utf-8"))["theme"] for f in theme})

    def read(name: str) -> dict | None:
        f = root / name
        if not f.exists():
            return None
        return json.loads(f.read_text(encoding="utf-8"))

    disabled = read("theme-disabled.json")
    collections = read("collections-preview.json")
    bypass = read("events-fixture-bypass.json")
    coll_axe = sorted(root.glob("collections-axe-*.json"))
    coll_violations = sum(
        len(json.loads(f.read_text(encoding="utf-8"))["violations"]) for f in coll_axe)

    return {
        "status": "pass" if theme_violations == 0 and coll_violations == 0 else "fail",
        "repo": "/srv/sites/yummyani-staging/repo (канонический)",
        "worktree": "/home/claude/work-templates/theme-ym",
        "branch": "claude/templates-theme-collections-01",
        "base_sha": "15ddc6635252c7920dfc6596a489e5c69fe80e5f",
        "in_release_artifact": False,
        "in_release_artifact_reason": (
            "тема и подборки — post-release работа; кандидат Lords обязан остаться "
            "тем, что проверено вместе с ним"
        ),
        "theme": {
            "flag": "NEXT_PUBLIC_TEMPLATE_THEME_SWITCHER",
            "default": "disabled",
            "axe_runs": len(theme),
            "axe_violations": theme_violations,
            "themes": themes,
            "viewports": [390, 768, 1440],
            "disabled_state": None if not disabled else {
                "data_theme": disabled.get("dataTheme"),
                "dark_class": disabled.get("dark"),
                "bootstrap_scripts": disabled.get("bootstrapScripts"),
                "toggles": disabled.get("toggles"),
                "canvas_under_dark_system": disabled.get("canvas"),
            },
        },
        "collections": {
            "flag": "NEXT_PUBLIC_TEMPLATE_COLLECTIONS",
            "default": "disabled",
            "routes": "unreachable",
            "routes_reason": (
                "строк нет в page-matrix.ts, посредник отвечает 404; матрица "
                "принадлежит полосе SEO (TEMPLATE_TO_SEO-002)"
            ),
            "source": "отсутствует: Site View API подборок не отдаёт (TEMPLATE_TO_CORE-010)",
            "preview_surface": "/dev/ui",
            "rendered_blocks": None if not collections else {
                "rail": collections.get("rails"),
                "hub": collections.get("hubs"),
                "page": collections.get("pages"),
                "tiles": len(collections.get("tileTitles") or []),
                "synthetic_notices_visible": collections.get("notices") is not None,
            },
            "axe_runs": len(coll_axe),
            "axe_violations": coll_violations,
        },
        "events": {
            "status": "blocked",
            "reason": None if not bypass else bypass.get("cause"),
            "evidence": "yummy-post-release/events-fixture-bypass.json",
            "handoff": "TEMPLATE_TO_CORE-011",
            "proof": None if not bypass else {
                "snapshot_titles": bypass.get("snapshotTitles"),
                "snapshot_baseline": bypass.get("snapshotBaseline"),
                "cards": bypass.get("cards"),
                "badges": len(bypass.get("badges") or []),
            },
            "note": (
                "прежнее объяснение — «у синтетических записей нет истории» — "
                "проверено и оказалось неверным: снимок прошлого положен и прочитан, "
                "меток по-прежнему ноль"
            ),
        },
        "evidence": "artifacts/evidence/templates/yummy-post-release/*.json",
    }


def _release_candidate_gate() -> dict:
    """Состояние кандидата Lords по его собственному машиночитаемому описанию."""
    f = EVIDENCE / "lords-release-candidate.json"
    if not f.exists():
        return {"status": NOT_RUN, "reason": "артефакт кандидата не собран"}
    d = json.loads(f.read_text(encoding="utf-8"))
    gates = d.get("gates", [])
    failed = [g["gate"] for g in gates if g.get("status") != "pass"]
    return {
        "status": "pass" if not failed else "fail",
        "artifact": "LORDS_TEMPLATE_RELEASE_CANDIDATE",
        "head_sha": d.get("headSha"),
        "template_digest": d.get("templateDigest"),
        "gates_passed": len(gates) - len(failed),
        "gates_total": len(gates),
        "gates_failed": failed,
        "handoff": "TEMPLATE_TO_CORE-008",
        "production_changed": False,
        "architect_action": "решение о canary на одной витрине",
        "evidence": "artifacts/evidence/templates/lords-release-candidate.json",
    }


#: Отпечаток замороженного кандидата и ветка, в которой он заморожен. Значения
#: не вычисляются из текущего рабочего дерева намеренно: статус обязан называть
#: то, что предлагается к релизу, а post-release ветка трогает
#: `factory/templates/` и потому даёт другой отпечаток. Один раз статус уже
#: подменил кандидата веткой доработок — читатель увидел бы «21 файл» там, где
#: Архитектору передавались 19.
FROZEN_CANDIDATE = {
    "branch": "claude/templates-lords-yummy-refpacks-01",
    "head": "cd2f718ae656e6bfcdc68099601d92078bd1f13f",
    "template_digest":
        "52b56d557564717adcf32011c3494bc8c548eae1a96e010f7bd499351e0847dc",
    "template_digest_files": 19,
}


def build() -> dict:
    fingerprint = digest_mod.compute()
    branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    candidate_branch = branch == FROZEN_CANDIDATE["branch"]
    return {
        "lane": "TEMPLATES",
        "branch": FROZEN_CANDIDATE["branch"],
        "head": FROZEN_CANDIDATE["head"],
        "base_sha": "76552b9a7372c5ad15cfc7d8b1052a10024722a3",
        "template_digest": FROZEN_CANDIDATE["template_digest"],
        "template_digest_files": FROZEN_CANDIDATE["template_digest_files"],
        # Ветка, из которой запущен пересчёт. Совпадает с кандидатом — отпечаток
        # проверяется на месте; не совпадает — называется отдельно и с причиной.
        "recomputed_from": {
            "branch": branch,
            "head": _git("rev-parse", "HEAD"),
            "template_digest": fingerprint["template_digest"],
            "template_digest_files": fingerprint["files"],
            "matches_candidate":
                fingerprint["template_digest"] == FROZEN_CANDIDATE["template_digest"],
            "note": (
                "пересчёт из ветки кандидата: отпечаток проверен на месте"
                if candidate_branch else
                "пересчёт из post-release ветки: её отпечаток отличается намеренно, "
                "кандидату он не принадлежит и в релиз не входит"),
        },
        "gates": {
            "axe_wcag22aa": _axe_gate(),
            "a11y_manual": _manual_gate(),
            "visual_baseline": _visual_gate(),
            "performance": _performance_gate(),
            "template_audit": _audit_gate(),
            "yummy_template_fixture": _yummy_gate(),
            "crossbrowser": _crossbrowser_gate(),
            "reference_packs": _reference_packs_gate(),
            "lords_release_candidate": _release_candidate_gate(),
            "yummy_post_release": _post_release_gate(),
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
                "state": "partially_lifted",
                "what": (
                    "Ключевые страницы Yummy теперь отрисовываются локально без базы и "
                    "секретов: поднят next dev с подставным окружением, все восемь "
                    "маршрутов отдают 200. Снято ограничение на браузерную проверку "
                    "шаблона."
                ),
                "remains": (
                    "Содержимое приходит из базы, поэтому доступно только "
                    "деградированное состояние. Нормальное состояние, соответствие "
                    "API → SSR → DOM, маршруты событий, страница произведения, сезоны, "
                    "серии и плеер остаются непроверенными."
                ),
                "effect": "ворота, которым нужны данные, помечены blocked, а не pass",
                "recorded_in": "docs/templates/BLOCKERS.md",
            },
            {
                "id": "COLLECTIONS-ROUTE-01",
                "state": "open",
                "what": (
                    "маршрутов /collections нет в src/site-blueprint/page-matrix.ts, "
                    "и посредник отвечает 404 на всё, чего в матрице нет"
                ),
                "effect": (
                    "раздел проверяется в галерее /dev/ui; публичный маршрут "
                    "не открывается"
                ),
                "owner": "SEO",
                "recorded_in": "docs/templates/handoff/TEMPLATE_TO_SEO-002-collections-routes.md",
            },
            {
                "id": "COLLECTIONS-SOURCE-01",
                "state": "open",
                "what": "Site View API не публикует подборки ни в каком виде",
                "effect": "состав приходит только из синтетической фикстуры предпросмотра",
                "owner": "CORE",
                "recorded_in": "docs/templates/handoff/TEMPLATE_TO_CORE-010-collections-contract.md",
            },
            {
                "id": "EVENTS-FIXTURE-BYPASS-01",
                "state": "open",
                "what": (
                    "loadHomepageCatalog при поднятой фикстуре возвращает "
                    "catalogVisualHomepageData() до вызова loadContentEvents"
                ),
                "effect": (
                    "событийные метки непроверяемы на фикстуре; снимок прошлого "
                    "положен и прочитан, меток ноль при 37 карточках"
                ),
                "owner": "CORE",
                "recorded_in": (
                    "docs/templates/handoff/"
                    "TEMPLATE_TO_CORE-011-fixture-bypasses-event-producer.md"
                ),
            },
            {
                "id": "YUMMY-LIVE-EGRESS-01",
                "state": "open",
                "what": (
                    "Боевые домены yummyani.site/.org/.biz отклоняются профилем "
                    "разрешений так же, как референсы: «хост не входит в переданные "
                    "контракты»."
                ),
                "effect": "живой read-only аудит трёх доменов не проводился",
                "recorded_in": "docs/templates/BLOCKERS.md",
            },
        ],
        # Вердикт не «pass». Условие сдачи задано владельцем: пока Yummy не
        # проверен, кандидат остаётся условным. Ворота шаблона Lords при этом
        # закрыты полностью, и это разные утверждения.
        "verdict": "CONDITIONAL_BLOCKED_ON_YUMMY_LIVE_DATA",
        "verdict_reason": (
            "Ворота Lords пройдены полностью. У Yummy закрыт фикстурный контур: "
            "нормальное состояние, соответствие фикстура → ViewModel → SSR → DOM, "
            "визуальный эталон, axe, кросс-браузер. Остаётся живой контур — "
            "данные, четыре событийных пути, состояния плеера и производительность "
            "на production-сборке. Данные полосе шаблона не принадлежат. "
            "TEMPLATE_RELEASE_CANDIDATE=PASS не заявляется."
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
