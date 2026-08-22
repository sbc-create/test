#!/usr/bin/env python3
"""End-to-end demonstration: dry-run -> canary -> observation -> rollback.

Runs against the synthetic fixture tenant and writes an evidence file. Nothing
here touches a real site: the fixture portfolio is marked synthetic and the
operator refuses to write to it unless ``allow_synthetic`` is set explicitly.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from seo_operator.audit import AuditLog  # noqa: E402
from seo_operator.experiments import Experiment, Observation  # noqa: E402
from seo_operator.pipeline import Mode, Operator  # noqa: E402
from seo_operator.registry import load_portfolio  # noqa: E402
from seo_operator.reporting import render_delta  # noqa: E402
from seo_operator.technical_seo import Page  # noqa: E402

OUT = REPO / "docs" / "seo-operator" / "demo-canary-rollback.md"
TODAY = date(2026, 8, 22)


def load_pages() -> list[Page]:
    import json

    data = json.loads(
        (REPO / "tests" / "fixtures" / "crawl.fixture-anime.json").read_text(encoding="utf-8")
    )
    return [Page(**p) for p in data["pages"]]


def main() -> int:
    lines: list[str] = []
    a = lines.append

    a("# Демонстрация canary и отката")
    a("")
    a(
        "Сгенерировано `scripts/demo_canary.py`. Все данные синтетические "
        "(тенант `fixture-anime`, домен `example-fixture.test` не резолвится)."
    )
    a("")

    audit_path = REPO / "var" / "audit" / "demo-canary.jsonl"
    audit_path.unlink(missing_ok=True)

    op = Operator(
        portfolio=load_portfolio(REPO / "config" / "portfolio.fixture.json"),
        audit_log=AuditLog(audit_path),
        allow_synthetic=True,
    )
    pages = load_pages()

    # --- 1. dry-run --------------------------------------------------
    result = op.run(Mode.DRY_RUN, pages_by_site={"fixture-anime": pages}, today=TODAY)
    a("## 1. Dry-run")
    a("")
    a(f"- Обследовано страниц: **{len(pages)}**")
    a(f"- Находок: **{len(result.findings)}**")
    a(f"- Предложено изменений: **{len(result.proposed_changes)}**")
    a(
        f"- Записей в audit log после dry-run: **{len(op.audit.records())}** "
        "(dry-run ничего не пишет)"
    )
    a("")

    # --- 2. canary ---------------------------------------------------
    experiment = Experiment(
        hypothesis="Сокращение переполненных title до 60 символов повысит CTR карточек",
        site_id="fixture-anime",
        primary_metric="ctr",
        scope_pages=len(result.proposed_changes),
        site_total_pages=100,
        applicability="Карточки произведений с title > 60 символов на одном сайте",
    )
    applied = op.apply_canary(experiment, result.proposed_changes, sites_touched=1)

    a("## 2. Canary")
    a("")
    a(f"- Эксперимент: `{experiment.experiment_id}`")
    a(f"- Гипотеза: {experiment.hypothesis}")
    a(
        f"- Охват: **{experiment.page_share:.1%}** страниц одного сайта "
        f"(лимит 10%, максимум 1 сайт)"
    )
    a(f"- Применено изменений: **{len(applied)}**")
    a("")
    a("| change_id | поле | было → стало |")
    a("| --- | --- | --- |")
    for c in applied:
        a(f"| `{c.change_id}` | {c.field_name} | {render_delta(c.before, c.after, 44)} |")
    a("")

    # --- 3. попытка выйти за пределы canary --------------------------
    from seo_operator.experiments import CanaryScopeError

    a("## 3. Попытка массового раскатывания без canary")
    a("")
    try:
        op.apply_canary(experiment, applied, sites_touched=15)
        a("- ОШИБКА: массовое изменение не было заблокировано")
    except CanaryScopeError as exc:
        a(f"- Заблокировано: `{exc}`")
    a("")

    # --- 4. наблюдение и откат ---------------------------------------
    observation = Observation(
        days_elapsed=15,
        impressions=5200,
        primary_metric_delta=-0.084,
        note="CTR упал относительно контрольной группы",
    )
    verdict, reason, rolled_back = op.observe_and_decide(experiment, observation)

    a("## 4. Наблюдение и решение")
    a("")
    a(
        f"- Наблюдение: {observation.days_elapsed} дней, {observation.impressions} показов, "
        f"изменение метрики **{observation.primary_metric_delta:+.1%}**"
    )
    a(f"- Вердикт: **{verdict.value}** — {reason}")
    a(f"- Фаза эксперимента: **{experiment.phase.value}**")
    a("")

    a("## 5. Откат")
    a("")
    a(f"- Откачено изменений: **{len(rolled_back)}**")
    a("")
    a("| change_id | поле | восстановленное значение |")
    a("| --- | --- | --- |")
    for record in rolled_back:
        a(
            f"| `{record['change_id']}` | {record['field_name']} | "
            f"`{str(record['restore_value'])[:52]}` |"
        )
    a("")

    restored_ok = all(
        record["restore_value"] == change.before
        for record, change in zip(reversed(rolled_back), applied, strict=False)
    )
    a(f"- Все значения совпали с исходными: **{'да' if restored_ok else 'НЕТ'}**")
    a("")

    # --- 6. защита от затирания правки редактора ---------------------
    from seo_operator.audit import ConflictError, apply_rollback

    a("## 6. Защита ручной правки при откате")
    a("")
    payload = applied[0].rollback_payload
    try:
        apply_rollback(payload, current_value="Заголовок, переписанный редактором вручную")
        a("- ОШИБКА: откат затёр ручную правку")
    except ConflictError as exc:
        a(f"- Откат остановлен: `{exc}`")
    a("")

    # --- 7. audit log ------------------------------------------------
    records = op.audit.records()
    a("## 7. Audit log")
    a("")
    a(
        f"- Всего записей: **{len(records)}** "
        f"({len(applied)} применений + {len(rolled_back)} откатов)"
    )
    a(f"- Файл: `{audit_path.relative_to(REPO)}`")
    a("- Каждая запись содержит before/after snapshot, experiment_id и rollback payload.")
    a("")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"записано: {OUT.relative_to(REPO)}")
    print(f"вердикт={verdict.value} применено={len(applied)} откачено={len(rolled_back)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
