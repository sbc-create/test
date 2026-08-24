"""Ворота уникальности для направления Lords поверх планов сайтов.

Проверка работает по плану, а не по отданным страницам, и в этом её смысл:
дубли между четырьмя сайтами видны до того, как что-то развёрнуто, а не после.
Метрика и правила общие с `factory.seo.uniqueness` — второй реализации нет.

Одна проверка из общего набора здесь честно не выполняется. CSU-7 сверяет
canonical индексируемой страницы с её собственным сайтом, а домены не переданы,
поэтому canonical пуст. Пропуск записывается как пропуск с причиной, а не
засчитывается как успех.
"""

from __future__ import annotations

from factory.lords.plan import SitePlan
from factory.seo import uniqueness
from factory.seo.model import Report

CANONICAL_CHECK = "CSU-7"


def check_plans(plans: list[SitePlan], names: dict[str, str] | None = None) -> Report:
    """Отчёт ворот по планам четырёх сайтов."""
    observations = []
    for plan in plans:
        site_name = (names or {}).get(plan.site_id, "")
        observations.extend(page.observation(site_name) for page in plan.pages)

    report = uniqueness.check(observations)

    domains_known = any(page.canonical for plan in plans for page in plan.pages)
    report.counts["canonical_check"] = "executed" if domains_known else "skipped"
    if not domains_known:
        report.counts["canonical_check_reason"] = (
            f"{CANONICAL_CHECK} не выполнялась: домены не переданы, canonical пуст. "
            "Это пропуск проверки, а не её прохождение."
        )
    report.counts["sites"] = len({plan.site_id for plan in plans})
    report.counts["planned_pages"] = len(observations)
    return report


def ownership_overlap(plans: list[SitePlan]) -> list[dict]:
    """Разделы, которые индексирует больше одного сайта.

    Ворота уникальности ловят одинаковый состав адресов целиком (CSU-6), но два
    сайта могут индексировать один раздел и при этом отличаться остальными —
    такая пара пройдёт CSU-6 и всё равно останется дублем по этому разделу.
    """
    owners: dict[str, list[str]] = {}
    for plan in plans:
        for page in plan.pages:
            if page.indexable:
                owners.setdefault(page.section, []).append(plan.site_id)
    return [
        {"section": section, "sites": sorted(sites)}
        for section, sites in sorted(owners.items())
        if len(sites) > 1
    ]
