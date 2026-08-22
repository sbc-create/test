"""
Утренний отчёт владельцу.

Отчёт управленческий, а не технический лог: полные доказательства лежат в
audit/state, здесь — что произошло, что это значит и что требует решения.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from ..scheduler import RunReport, Step

STATUS_LABEL = {
    "ok": "готово",
    "skipped": "пропущено",
    "WAITING_DATA": "ждём данных",
    "BLOCKED_AUTHORIZATION": "нужна авторизация",
    "BLOCKED_PROTECTED_GUARDRAIL": "блокировка защищённого ядра",
    "error": "ошибка",
}


def _step(report: RunReport, step: Step):
    for s in report.steps:
        if s.step is step:
            return s
    return None


def render(report: RunReport, portfolio_status: str = "UNKNOWN") -> str:
    lines: list[str] = []
    add = lines.append

    add(f"# Ежедневный SEO/редакционный отчёт — {report.run_date}")
    add("")
    mode = "DRY-RUN (изменения не применяются)" if report.dry_run else "APPLY"
    add(f"Режим: **{mode}**. Сайтов в прогоне: {len(report.sites)}. Статус портфеля: `{portfolio_status}`.")
    add("")

    if portfolio_status != "POPULATED":
        add("> Портфель ещё не заполнен реальными сайтами: цифры ниже получены на фикстуре "
            "и не являются производственными показателями.")
        add("")

    # 1. Портфель
    add("## Портфель")
    baselines = (_step(report, Step.UPDATE_BASELINES) or {}).data if _step(report, Step.UPDATE_BASELINES) else {}
    collect = _step(report, Step.COLLECT)
    if collect and collect.data.get("blocked"):
        add(f"- Источников не подключено: **{len(collect.data['blocked'])}** "
            f"({', '.join(collect.data['blocked'][:5])}).")
    if collect and collect.data.get("waiting"):
        add(f"- Ждут данных: {', '.join(collect.data['waiting'][:5])}.")
    add(f"- Baseline обновлён для {len(baselines.get('sites', []))} сайтов.")
    add("- Clicks / impressions / TOP-3 / TOP-10 / TOP-20: расчёт доступен после подключения "
        "Search Console и Вебмастера — сравнение на неполных данных не публикуется.")
    add("")

    # 2. Новые тайтлы
    add("## Новые тайтлы")
    prio = _step(report, Step.PRIORITIZE)
    if prio and prio.data.get("top"):
        for item in prio.data["top"][:5]:
            flag = "🚫 " if item["blockers"] else ""
            add(f"- {flag}`{item['subject']}` ({item['site_id']}), score {item['score']} → {item['action']}"
                + (f" — блокеры: {'; '.join(item['blockers'])}" if item["blockers"] else ""))
    else:
        add("- Приоритетов нет: каталог не подключён.")
    add("")

    # 3. Редакционный план
    add("## Редакционный план")
    cal = _step(report, Step.REFRESH_RELEASE_CALENDAR)
    if cal and cal.data.get("transitions"):
        for t in cal.data["transitions"]:
            add(f"- {t['site_id']}: вышло {len(t['released'])}, просрочено анонсов {len(t['expired'])}"
                + (f" ({', '.join(t['expired'])})" if t["expired"] else ""))
    else:
        add("- Переходов статусов нет.")
    fresh = _step(report, Step.VERIFY_EDITORIAL_FACTS_AND_FRESHNESS)
    if fresh:
        add(f"- {fresh.detail}")
    add("")

    # 4. Что изменено
    add("## Изменения")
    applied = _step(report, Step.APPLY_ALLOWED_CHANGES)
    if applied:
        add(f"- {applied.detail}")
        for item in applied.data.get("blocked", [])[:5]:
            add(f"  - заблокировано ({item['site_id']}): {item['reason']}")
    add("")

    # 5. Эксперименты
    add("## Эксперименты")
    plan = _step(report, Step.PLAN_CANARY)
    evals = _step(report, Step.EVALUATE_MATURE_EXPERIMENTS)
    decisions = _step(report, Step.KEEP_OR_ROLLBACK)
    if plan:
        add(f"- {plan.detail}")
        for r in plan.data.get("refusals", [])[:3]:
            add(f"  - не запущен на {r['site_id']}: {r['reason']}")
    if evals:
        add(f"- {evals.detail}")
        for e in evals.data.get("evaluations", [])[:5]:
            add(f"  - `{e['id']}`: {e['decision']} (уверенность {e['confidence']}) — {e['explanation']}")
    if decisions:
        add(f"- {decisions.detail}")
    add("")

    # 6. Инциденты и guardrails
    add("## Инциденты и защита")
    inc = _step(report, Step.DETECT_INCIDENTS)
    safety = _step(report, Step.SAFETY_REVIEW)
    if inc:
        add(f"- {inc.detail}")
        for i in inc.data.get("incidents", [])[:5]:
            add(f"  - `{i['incident_id']}` ({i['severity']}), заморожено экспериментов: "
                f"{len(i['frozen_experiments'])}")
    if safety:
        add(f"- Защищённое ядро: {safety.detail}")
    if report.protected_drift:
        add(f"- ⚠️ Дрейф protected файлов: {', '.join(report.protected_drift)} — мутации остановлены.")
    add("")

    # 7. Обучение
    learn = _step(report, Step.LEARN)
    add("## Чему научились")
    add(f"- {learn.detail if learn else 'нет данных'}")
    add("")

    # 8. Блокеры — одним пакетом
    add("## Требуется решение владельца")
    if report.blockers:
        for b in report.blockers:
            add(f"- **{b['kind']}** — {b['detail']}")
    else:
        add("- Нет новых блокеров.")
    add("")

    # 9. Ошибки
    errors = [s for s in report.steps if s.status == "error"]
    if errors:
        add("## Ошибки прогона")
        for e in errors:
            add(f"- `{e.step.value}`: {e.detail}")
        add("")

    add("## План на сегодня и бюджет риска")
    add(f"- Шаги цикла: {', '.join(f'{k}×{v}' for k, v in report.status_counts().items())}.")
    add("- Бюджет риска: без подключённых источников и подписанной production policy "
        "доступны только Tier 0 и dry-run Tier 1.")
    add("")
    add("_Полные доказательства: `.seo-state/audit.sqlite3` (hash-chain), "
        "`.seo-state/state.sqlite3` (наблюдения, снапшоты, эксперименты)._")

    return "\n".join(lines)
