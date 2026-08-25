"""
Ежемесячный отчёт владельцу (ТЗ §10).

Отвечает на один вопрос, ради которого он существует: достаточно ли текущего
портфеля для 7 млн уников в сутки. Ответ либо в трёх сценариях с диапазоном,
либо честное «данных недостаточно» — но не одна успокаивающая цифра.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Sequence

from ..forecast import capacity as cap
from ..metrics.north_star import PortfolioNorthStar
from ..secrets import assert_no_secret
from ..statuses import Confidence, Status


def render(*, portfolio: PortfolioNorthStar, forecast: cap.CapacityForecast,
           month: date, direction_stats: Sequence[dict[str, Any]] = (),
           ledger_summary: dict[str, int] | None = None,
           risks: Sequence[str] = ()) -> str:
    lines: list[str] = []
    add = lines.append

    add(f"# Ежемесячный отчёт владельцу — {month:%Y-%m}")
    add("")

    # 1. Прогресс к цели
    add("## Прогресс к 7 млн уников/сутки")
    add("")
    add(f"- **Текущий показатель:** {portfolio.headline.render()}")
    add(f"- **Цель:** {cap.TARGET_DAILY_UNIQUE:,}".replace(",", " "))
    add(f"- **Разрыв:** {forecast.gap.render()}")
    add("")
    add(f"> {portfolio.caveat}")
    add("")
    add("Разбивка по поисковым системам:")
    for engine, m in portfolio.by_engine.items():
        add(f"- {engine.value}: {m.render()}")
    add("")

    # 2. Три сценария
    add("## Достаточно ли текущих сайтов")
    add("")
    if forecast.required_range == Status.INCONCLUSIVE.value:
        add("**Ответ: данных недостаточно для расчёта.** Причины:")
        for b in forecast.blockers:
            add(f"- {b}")
        add("")
        add("Пока эти пробелы не закрыты, любая цифра «нужно N сайтов» была бы выдумкой.")
    else:
        add(f"**Требуется новых сайтов: {forecast.required_range}** "
            "(диапазон по трём сценариям, не одна цифра).")
        add("")
        add(cap.render_table(forecast))
        if forecast.blockers:
            add("")
            add("Ограничения расчёта:")
            for b in forecast.blockers:
                add(f"- {b}")
    add("")

    # 3. Альтернатива без новых доменов
    add("## Альтернатива: рост без новых доменов")
    add("")
    add(f"- Потенциал доведения существующих сайтов до P75 своей когорты: "
        f"{forecast.growth_without_new_sites.render()}")
    add(f"- {forecast.operational_capacity_note}")
    add("")

    # 4. Когорты
    add("## Когорты по возрасту")
    add("")
    add("| Когорта | Сайтов | Измерено | Живых | P25 | P50 | P75 | Выживаемость |")
    add("|---|---|---|---|---|---|---|---|")
    for c in forecast.cohorts:
        add(f"| {c.age_bucket}+ дн. | {c.total} | {c.measured} | {c.alive} | "
            f"{c.p25.render()} | {c.p50.render()} | {c.p75.render()} | {c.survival_rate.render()} |")
    add("")

    # 5. Эффективность направлений
    if direction_stats:
        add("## Эффективность направлений")
        add("")
        add("| Направление | Сайтов | Медиана уников | Что делать |")
        add("|---|---|---|---|")
        for d in direction_stats:
            add(f"| {d['direction']} | {d['sites']} | {d.get('median', 'NOT_MEASURED')} | "
                f"{d.get('recommendation', 'наблюдать')} |")
        add("")

    # 6. Результаты гипотез
    add("## Результаты гипотез за месяц")
    add("")
    if ledger_summary:
        total_closed = sum(v for k, v in ledger_summary.items() if k != "OPEN")
        add(f"- Закрыто: {total_closed}, открыто: {ledger_summary.get('OPEN', 0)}")
        for outcome in ("WIN", "LOSS", "NEUTRAL", "INCONCLUSIVE", "INVALIDATED", "ROLLED_BACK"):
            add(f"  - {outcome}: {ledger_summary.get(outcome, 0)}")
        losses = ledger_summary.get("LOSS", 0) + ledger_summary.get("ROLLED_BACK", 0)
        if losses:
            add(f"- Неудачных изменений: {losses}. Они не скрыты и учтены в базе знаний.")
    else:
        add("- Журнал действий пуст: гипотезы ещё не закрывались.")
    add("")

    # 7. Риски
    add("## Риски")
    add("")
    add(f"- {forecast.cannibalization_risk_note}")
    for r in risks:
        add(f"- {r}")
    if forecast.required_range != Status.INCONCLUSIVE.value:
        low_conf = [s for s in forecast.scenarios if s.confidence is Confidence.LOW]
        if low_conf:
            add("- Уверенность прогноза LOW: выборка зрелых сайтов мала, "
                "диапазон может измениться при её росте.")
    add("")

    # 8. Решения владельца
    add("## Требуется от владельца")
    add("")
    add("- Покупка доменов, изменение DNS, публикация новых production-сайтов и включение "
        "индексации выполняются только после отдельного подтверждения. Оператор рекомендует, "
        "но не приобретает и не включает их самостоятельно.")
    if forecast.blockers:
        for b in forecast.blockers:
            add(f"- {b}")
    add("")

    text = "\n".join(lines)
    assert_no_secret(text, "monthly_report")
    return text
