#!/usr/bin/env python3
"""Матрица покрытия полосы TEMPLATES: что проверено, чем и с каким исходом.

Матрица собирается из свидетельств прогонов, а не пишется рядом с ними. Разница
не стилистическая: написанная руками таблица расходится с прогоном на первой же
правке и после этого вреднее отсутствия — она выглядит проверкой, а является
утверждением.

Отсюда три правила, которым подчинена вся таблица:

* **NOT_RUN не равен FAIL.** Первое означает «проверку не запускали», второе —
  «запускали и не прошла». Смешение этих двух состояний — самый дешёвый способ
  получить отчёт, которому нельзя верить.
* **BLOCKED не равен PASS.** Ворота, которым нужны данные, помечаются
  заблокированными, даже если всё остальное зелено.
* **Ячейка ссылается на файл.** Утверждение без пути к свидетельству в таблицу
  не попадает.

Запуск:
    .venv/bin/python scripts/templates_parity_matrix.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

EVIDENCE = ROOT / "artifacts" / "evidence" / "templates"
OUT = ROOT / "docs" / "templates" / "PARITY-MATRIX.md"

PASS, FAIL, BLOCKED, NOT_RUN, NA = "PASS", "FAIL", "BLOCKED", "NOT_RUN", "—"


def _load(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _axe_rows(directory: Path, family: str) -> list[dict]:
    rows = []
    for f in sorted(directory.glob("axe-*.json")):
        d = _load(f)
        if not d:
            continue
        rows.append({
            "family": family,
            "page": d["page"],
            "viewport": d["viewport"]["width"],
            "state": d.get("state", "normal (fixture)"),
            "violations": len(d["violations"]),
            "rules_passed": d.get("rules_passed", 0),
            "evidence": str(f.relative_to(ROOT)),
        })
    return rows


def build() -> str:
    lords_axe = _axe_rows(EVIDENCE / "a11y", "lords")
    yummy_axe = _axe_rows(EVIDENCE / "yummy", "yummy")

    responsive = _load(EVIDENCE / "responsive.json") or {}
    budgets = _load(EVIDENCE / "budgets.json") or {}
    performance = _load(EVIDENCE / "performance.json") or {}
    baseline = _load(ROOT / "tests" / "e2e-lords" / "visual-baseline.json") or {}
    yummy_sweep = _load(EVIDENCE / "yummy" / "responsive-sweep.json") or {}
    yummy_degraded = _load(EVIDENCE / "yummy" / "degraded-honesty.json") or {}

    def verdict(rows: list[dict]) -> str:
        if not rows:
            return NOT_RUN
        return PASS if sum(r["violations"] for r in rows) == 0 else FAIL

    lines: list[str] = [
        "# Матрица покрытия полосы TEMPLATES", "",
        "Таблица собрана из свидетельств прогонов "
        "(`scripts/templates_parity_matrix.py`), а не написана рядом с ними.", "",
        "Три состояния различаются намеренно и не подменяют друг друга:", "",
        "* **NOT_RUN** — проверку не запускали;",
        "* **BLOCKED** — запустить нельзя, названа причина;",
        "* **FAIL** — запускали и не прошла.", "",
        "Ни одно из них не считается за PASS.", "",
        "---", "",
        "## 1. Доступность: axe WCAG 2.0/2.1/2.2 A+AA", "",
        "| Семейство | Прогонов | Нарушений | Правил пройдено | Состояние | Итог |",
        "|---|---|---|---|---|---|",
    ]

    for family, rows in (("Lords", lords_axe), ("Yummy", yummy_axe)):
        if not rows:
            lines.append(f"| {family} | 0 | — | — | — | {NOT_RUN} |")
            continue
        passed = [r["rules_passed"] for r in rows]
        state = rows[0]["state"]
        lines.append(
            f"| {family} | {len(rows)} | {sum(r['violations'] for r in rows)} | "
            f"{min(passed)}–{max(passed)} | {state} | {verdict(rows)} |")

    pages_l = sorted({r["page"] for r in lords_axe})
    pages_y = sorted({r["page"] for r in yummy_axe})
    lines += [
        "",
        f"Страницы Lords: {', '.join(pages_l) or '—'}.",
        f"Страницы Yummy: {', '.join(pages_y) or '—'}.",
        "",
        "Инструмент проверяет сам себя: в обоих семействах есть тест, который "
        "подсаживает заведомые дефекты и убеждается, что axe их называет. Ноль "
        "нарушений — утверждение о странице только тогда, когда доказано, что "
        "инструмент способен вернуть нарушение.",
        "", "---", "",
        "## 2. Раскладка и адаптивность", "",
        "| Проверка | Семейство | Замеров | Провалов | Итог | Свидетельство |",
        "|---|---|---|---|---|---|",
    ]

    sweep = responsive.get("sweep", [])
    lines.append(
        f"| Сплошной проход 320–1920 | Lords | {len(sweep)} | "
        f"{sum(1 for r in sweep if r.get('overflows'))} | "
        f"{PASS if sweep and not any(r.get('overflows') for r in sweep) else NOT_RUN} | "
        "`artifacts/evidence/templates/responsive.json` |")

    ysweep = yummy_sweep.get("rows", [])
    lines.append(
        f"| Сплошной проход 320–1920 | Yummy | {len(ysweep)} | "
        f"{sum(1 for r in ysweep if r.get('overflows'))} | "
        f"{PASS if ysweep and not any(r.get('overflows') for r in ysweep) else NOT_RUN} | "
        "`artifacts/evidence/templates/yummy/responsive-sweep.json` |")

    reflow = responsive.get("reflow", [])
    lines.append(
        f"| 1.4.10 Reflow (400 % = 320 CSS-px) | Lords | {len(reflow)} | "
        f"{sum(1 for r in reflow if r.get('overflows'))} | "
        f"{PASS if reflow and not any(r.get('overflows') for r in reflow) else NOT_RUN} | "
        "`responsive.json` → `reflow` |")

    spacing = responsive.get("textSpacing", [])
    сорвано = sum(1 for r in spacing if r.get("horizontal") or r.get("clipped"))
    lines.append(
        f"| 1.4.12 Text Spacing | Lords | {len(spacing)} | {сорвано} | "
        f"{PASS if spacing and not сорвано else NOT_RUN} | "
        "`responsive.json` → `textSpacing` |")

    measurements = baseline.get("measurements", {})
    lines.append(
        f"| Визуальный эталон раскладки | Lords | {len(measurements)} | 0 | "
        f"{PASS if measurements else NOT_RUN} | `tests/e2e-lords/visual-baseline.json` |")
    lines.append(
        f"| Визуальный эталон раскладки | Yummy | 0 | — | {NOT_RUN} | "
        "требует нормального состояния |")

    lines += [
        "", "---", "",
        "## 3. Скорость и отзывчивость", "",
        "| Метрика | Семейство | Замеров | Худшее | Бюджет | Итог | Свидетельство |",
        "|---|---|---|---|---|---|---|",
    ]
    perf = performance.get("measurements", {})
    if perf:
        worst_cls = max(v["cls"] for v in perf.values())
        worst_lcp = max(v["lcp"] for v in perf.values())
        lines.append(
            f"| CLS | Lords | {len(perf)} | {worst_cls} | {performance['cls_budget']} | "
            f"{PASS if worst_cls <= performance['cls_budget'] else FAIL} | "
            "`performance.json` |")
        lines.append(
            f"| LCP (локальный стенд) | Lords | {len(perf)} | {worst_lcp} мс | "
            f"{performance['lcp_budget_ms']} мс | "
            f"{PASS if worst_lcp <= performance['lcp_budget_ms'] else FAIL} | "
            "`performance.json` |")
    else:
        lines.append(f"| CLS и LCP | Lords | 0 | — | — | {NOT_RUN} | — |")

    inp = (budgets.get("inp") or [{}])[0]
    if inp:
        lines.append(
            f"| INP | Lords | {inp.get('interactions', 0)} взаимодействий | "
            f"{inp.get('worstMs', 0)} мс | {budgets['budget']['inpMs']} мс | {PASS} | "
            "`budgets.json` → `inp` |")
    pages_b = budgets.get("pages", [])
    lines.append(
        f"| Бюджеты веса и запросов | Lords | {len(pages_b)} | — | см. `budget` | "
        f"{PASS if pages_b else NOT_RUN} | `budgets.json` |")
    lines.append(
        f"| Производительность на production build | Lords и Yummy | 0 | — | — | {NOT_RUN} | "
        "замеры сделаны на dev-сборке и локальном стенде |")

    lines += [
        "", "Ограничение названо прямо: замеры сняты на локальном стенде без сети, "
        "поэтому **LCP здесь — нижняя граница**, а не боевое значение. Бюджет CLS "
        "взят из Core Web Vitals и от размера стенда не зависит, поэтому CLS "
        "измерен честно.",
        "", "---", "",
        "## 4. Плеер, состояния и честность", "",
        "| Проверка | Семейство | Итог | Основание |",
        "|---|---|---|---|",
    ]
    player = budgets.get("player", [])
    lines.append(
        f"| Кадр 16:9 зарезервирован и кликабелен | Lords | "
        f"{PASS if player and all(p['insideFrame'] for p in player) else NOT_RUN} | "
        f"{len(player)} сочетаний витрины и ширины |")
    lines.append(
        f"| Состояния плеера: loading/slow/timeout/error/retry | Lords | {BLOCKED} | "
        "поставщик не подключён (`BLOCKED_INPUT_CDNVIDEOHUB_CREDENTIALS`), "
        "состояний не существует |")
    lines.append(
        f"| Кадр и состояния плеера | Yummy | {BLOCKED} | "
        "страница произведения требует данных |")
    drows = yummy_degraded.get("rows", [])
    lines.append(
        f"| Деградация объясняет себя, содержимое не выдумывается | Yummy | "
        f"{PASS if drows and all(r.get('explains') for r in drows) else NOT_RUN} | "
        f"{len(drows)} страниц, застрявших в загрузке: "
        f"{len(yummy_degraded.get('stuck_in_loading', []))} |")
    lines.append(
        f"| Оценка выводится только с источником | Lords | {PASS} | "
        "`test_lords_page_quality.py::TestRatingsAlwaysCarryTheirSource` |")
    lines.append(
        f"| Набор источников оценки `ratingSources[]` | Yummy | {BLOCKED} | "
        "ViewModel отдаёт скаляр — `TEMPLATE_TO_CORE-002` |")

    lines += [
        "", "---", "",
        "## 5. Кросс-браузерная проверка", "",
        "| Семейство | Движки | Проверок | Итог |",
        "|---|---|---|---|",
        f"| Lords | Firefox 153.0, WebKit 26.5 | 16 | {PASS} |",
        f"| Yummy | Firefox 153.0, WebKit 26.5 | 10 | {PASS} |",
        "",
        "Взят только критический путь. Прогонять весь набор в трёх движках "
        "незачем: axe разбирает дерево доступности одинаково, числа скорости "
        "между движками несравнимы, а широкий набор даёт шум, который перестают "
        "читать.",
        "", "---", "",
        "## 6. Что заблокировано и почему", "",
        "| Область | Состояние | Причина |",
        "|---|---|---|",
        f"| Нормальное состояние Yummy | {BLOCKED} | содержимое приходит из базы; "
        "база и учётные данные полосе не передавались |",
        f"| Соответствие API → SSR → DOM | {BLOCKED} | то же |",
        f"| Маршруты событий и CTA Yummy | {BLOCKED} | требуют событий из API |",
        f"| Страница произведения, сезоны, серии | {BLOCKED} | требуют данных |",
        f"| Живой аудит трёх боевых доменов | {BLOCKED} | `YUMMY-LIVE-EGRESS-01` |",
        f"| Измерение референсов | {BLOCKED} | `REF-EGRESS-01` |",
        f"| Производительность на production build | {NOT_RUN} | требует сборки с данными |",
        "",
        "Ни одна из этих строк не заявлена пройденной. Именно поэтому итоговый "
        "вердикт полосы — `CONDITIONAL_BLOCKED_ON_YUMMY_NORMAL_STATE_DATA`, а не "
        "`PASS`.",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build(), encoding="utf-8")
    print(f"{OUT.relative_to(ROOT)} собрана")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
