"""Daily and weekly management reports.

The report is written for an owner who will read it in two minutes and does not
want to be reassured. Two rules shape it:

1. A metric with no usable source prints "не измерено" and the reason, never 0.
2. Blockers appear at the top, as one consolidated list, not scattered per site.
"""

from __future__ import annotations

from datetime import date

from seo_operator.pipeline import RunResult
from seo_operator.quality import GateResult

SEVERITY_RU = {
    "critical": "критично",
    "high": "высокая",
    "medium": "средняя",
    "low": "низкая",
    "info": "информация",
}

GATE_RU = {
    GateResult.PASS: "PASS — все источники доступны",
    GateResult.DEGRADED: "DEGRADED — часть источников недоступна",
    GateResult.FAIL: "FAIL — поисковая статистика не измеряется",
}


def render_delta(before, after, width: int = 34) -> str:
    """Render before -> after so the *difference* survives truncation.

    Truncating both sides independently is how two different values end up
    looking identical in a table. When one value is a prefix of the other
    (the common case for a trimmed title) the shared head is elided and the
    changed tail is shown instead.
    """
    b, a = str(before), str(after)
    if b == a:
        return f"{b[:width]} (без изменений)"

    common = 0
    for cb, ca in zip(b, a, strict=False):
        if cb != ca:
            break
        common += 1

    if common >= min(len(b), len(a)) and common > 0:
        # One is a prefix of the other: show what was added or removed.
        longer, shorter = (b, a) if len(b) > len(a) else (a, b)
        tail = longer[common:]
        verb = "убрано" if len(b) > len(a) else "добавлено"
        head = shorter[-width:] if len(shorter) > width else shorter
        return f"…{head} · {verb} «{tail[:width]}» ({len(b)}→{len(a)} симв.)"

    if common > 12:
        return f"…{b[common:][:width]} → …{a[common:][:width]} " f"({len(b)}→{len(a)} симв.)"

    return f"{b[:width]} → {a[:width]} ({len(b)}→{len(a)} симв.)"


def _metric_line(label: str, measured: bool, value=None, reason: str = "") -> str:
    if measured:
        return f"| {label} | {value} | измерено |"
    return f"| {label} | не измерено | {reason} |"


def daily_report(result: RunResult, today: date | None = None) -> str:
    today = today or date.today()
    lines: list[str] = []
    a = lines.append

    a(f"# Ежедневный SEO-редакционный отчёт — {today.isoformat()}")
    a("")
    a(f"Режим прогона: `{result.mode.value}` · запуск: {result.started_at}")
    a("")

    # --- Резюме -------------------------------------------------------
    a("## Кратко для владельца")
    a("")
    if result.real_sites == 0:
        a(
            "- **Реальных сайтов под управлением: 0.** Оператор работает вхолостую: "
            "портфель не заполнен, писать некуда."
        )
    else:
        a(f"- Сайтов под управлением: **{result.real_sites}**.")
    a(f"- Качество данных: **{GATE_RU[result.quality.result]}**.")
    a(f"- Найдено технических проблем: **{len(result.findings)}**.")
    a(
        f"- Предложено изменений: **{len(result.proposed_changes)}**, "
        f"применено: **{len(result.applied_changes)}**, "
        f"откачено: **{len(result.rolled_back)}**."
    )
    if result.blockers:
        a(f"- **Блокеров, требующих вашего решения: {len(result.blockers)}** (список ниже).")
    a("")

    # --- Метрики ------------------------------------------------------
    a("## Поисковая эффективность")
    a("")
    a("| Метрика | Значение | Статус |")
    a("| --- | --- | --- |")
    search_measurable = result.quality.can_publish_metrics
    unmeasured_reason = "нет доступного источника поисковой статистики"
    for label in (
        "Показы",
        "Клики",
        "CTR",
        "Средняя позиция",
        "TOP-3",
        "TOP-10",
        "TOP-20",
        "Индексация",
        "Переходы к просмотру",
        "Глубина просмотра",
        "Возвращаемость",
    ):
        a(_metric_line(label, measured=search_measurable, reason=unmeasured_reason))
    a("")
    if not search_measurable:
        a(
            "> Прочерки выше — это отсутствие измерения, а не нулевые значения. "
            "Оператор не подставляет нули вместо недоступных данных."
        )
        a("")

    # --- Технические находки ------------------------------------------
    a("## Технические находки")
    a("")
    if not result.findings:
        if result.mode.value == "inventory" or not result.notes:
            a(
                "Обход не выполнялся — находок нет по причине отсутствия данных, "
                "а не потому, что сайты чисты."
            )
        else:
            a("Находок нет.")
    else:
        a("| Severity | ID | Сайт | Проблема | URL |")
        a("| --- | --- | --- | --- | --- |")
        for f in result.findings[:20]:
            a(
                f"| {SEVERITY_RU.get(f['severity'], f['severity'])} | {f['id']} | "
                f"{f.get('site_id', '—')} | {f['summary']} | {len(f['affected_urls'])} |"
            )
    a("")

    # --- Изменения ----------------------------------------------------
    a("## Изменения")
    a("")
    if result.proposed_changes:
        a("| Изменение | Сайт | Поле | Было → Стало | Причина |")
        a("| --- | --- | --- | --- | --- |")
        for c in result.proposed_changes[:15]:
            a(
                f"| `{c.change_id}` | {c.site_id} | {c.field_name} | "
                f"{render_delta(c.before, c.after)} | {c.reason} |"
            )
        a("")
        a(
            f"Каждое изменение имеет before/after snapshot и rollback payload "
            f"(всего {len(result.proposed_changes)})."
        )
    else:
        a("Изменений не предложено.")
    a("")

    # --- Эксперименты --------------------------------------------------
    if result.experiments:
        a("## Эксперименты")
        a("")
        a("| ID | Гипотеза | Фаза | Охват |")
        a("| --- | --- | --- | --- |")
        for e in result.experiments:
            a(
                f"| `{e.experiment_id}` | {e.hypothesis} | {e.phase.value} | "
                f"{e.page_share:.1%} страниц |"
            )
        a("")

    # --- Блокеры -------------------------------------------------------
    a("## Блокеры")
    a("")
    if result.blockers:
        a("Единым списком, чтобы можно было закрыть одним пакетом:")
        a("")
        for i, blocker in enumerate(result.blockers, 1):
            a(f"{i}. {blocker}")
    else:
        a("Блокеров нет.")
    a("")

    if result.notes:
        a("## Примечания к прогону")
        a("")
        for note in result.notes:
            a(f"- {note}")
        a("")

    return "\n".join(lines)


def weekly_report(results: list[RunResult], week_ending: date) -> str:
    lines: list[str] = []
    a = lines.append
    a(f"# Недельный SEO-редакционный отчёт — неделя до {week_ending.isoformat()}")
    a("")
    a(f"Прогонов за период: **{len(results)}**.")
    a("")
    total_findings = sum(len(r.findings) for r in results)
    total_applied = sum(len(r.applied_changes) for r in results)
    total_rolled = sum(len(r.rolled_back) for r in results)
    a("## Итоги")
    a("")
    a(f"- Находок: **{total_findings}**")
    a(f"- Применено изменений: **{total_applied}**")
    a(f"- Откачено: **{total_rolled}**")
    a("")
    gates = [r.quality.result.value for r in results]
    a(f"- Состояния gate качества данных за период: {', '.join(sorted(set(gates)))}")
    a("")
    blockers = sorted({b for r in results for b in r.blockers})
    a("## Незакрытые блокеры")
    a("")
    if blockers:
        for i, b in enumerate(blockers, 1):
            a(f"{i}. {b}")
    else:
        a("Нет.")
    a("")
    return "\n".join(lines)
