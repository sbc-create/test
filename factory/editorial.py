"""Редакционный контур: главный редактор в режиме dry-run.

Контур делает то, что можно решить по собственным данным, и честно называет то,
что решить нельзя. Поиск новинок в источнике и метрики поведения требуют
переданного контракта и подключённой аналитики: без них шаг помечается
`BLOCKED_INPUT`, а не заполняется правдоподобными числами.

Запись в базу включается только явным `--apply`; по умолчанию проход ничего не
меняет и показывает, что бы он сделал.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

from factory import audit
from factory.errors import BlockedInput
from factory.paths import PATHS
from factory.redaction import redact

APP = PATHS.root / "blueprints" / "payload-next-multisite" / "app"
SCRIPT = APP / "scripts" / "editorial-pass.ts"
TSX = APP / "node_modules" / ".bin" / "tsx"

#: Показатели, которые контур обязан отслеживать по заданию. Каждый помечен
#: признаком «измерено»: неизмеренный показатель не превращается в число.
TRACKED_METRICS = (
    ("card_ctr", "CTR карточки произведения в выдаче витрины"),
    ("playback_start", "переход от карточки к просмотру"),
    ("recirculation", "переходы между произведениями внутри сайта"),
    ("returning_users", "доля вернувшихся посетителей"),
)


def _run_pass(scope: str, apply: bool) -> dict:
    """Запуск редакционного прохода в CMS через проверенную обёртку окружения."""
    if not TSX.exists():
        raise BlockedInput(
            "Зависимости blueprint не установлены: tsx недоступен.",
            field="editorial.runtime",
            required_input="npm ci в blueprints/payload-next-multisite/app",
            blocks_stage="MONITORING")

    command = [sys.executable, str(PATHS.root / "tests/tools/with_app_env.py"),
               "--scope", scope, "--", str(TSX), str(SCRIPT)]
    if apply:
        command.append("--apply")

    result = subprocess.run(command, cwd=PATHS.root, capture_output=True, text=True,
                            timeout=900, check=False)
    if result.returncode != 0:
        raise BlockedInput(
            f"Редакционный проход не выполнен: {redact(result.stderr)[-400:]}",
            field="editorial.pass",
            required_input="Работоспособный стенд и база сайта",
            blocks_stage="MONITORING")

    for line in reversed(result.stdout.splitlines()):
        line = line.strip()
        if line.startswith("{"):
            return json.loads(line)
    raise BlockedInput("Редакционный проход не вернул отчёт.", field="editorial.pass",
                       blocks_stage="MONITORING")


def opportunity(action: dict) -> int:
    """Редакционная ценность действия: чем выше, тем раньше его брать в работу.

    Оценка считается из состава действия, а не назначается «на глаз»: смена
    состояния после выхода срочна, потому что до неё произведение лежит не на
    том сайте; отсутствие собственного текста важно, но не срочно.
    """
    weights = {
        "release_state_transition": 100,
        "stale_announcement": 60,
        "missing_own_text": 30,
    }
    return weights.get(action.get("action", ""), 10)


def run(scope: str = "anime", *, apply: bool = False) -> dict:
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    report = _run_pass(scope, apply)

    actions = sorted(report.get("actions", []), key=opportunity, reverse=True)
    for action in actions:
        action["opportunity"] = opportunity(action)

    metrics = [
        {"metric": key, "description": description, "measured": False,
         "value": None,
         "reason": "аналитика не подключена; значение не измерялось"}
        for key, description in TRACKED_METRICS
    ]

    summary = {
        "generated_at": started,
        "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "mode": report.get("mode", "dry_run"),
        "scope": scope,
        "counts": report.get("counts", {}),
        "actions": actions,
        "blocked": report.get("blocked", []),
        "metrics": metrics,
        # Отчёт не объявляет контур рабочим: пока хотя бы один шаг заблокирован
        # внешними данными, состояние именно такое.
        "status": "DRY_RUN_BLOCKED_INPUT" if report.get("blocked") else "DRY_RUN_COMPLETE",
    }

    out_dir = PATHS.artifacts / "editorial"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = started.replace(":", "").replace("-", "")
    (out_dir / f"editorial-{stamp}.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "latest.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "latest.md").write_text(render_markdown(summary), encoding="utf-8")

    audit.record(job_id=f"editorial-{stamp}", site_id=scope, environment="staging",
                 action="editorial.pass", target=scope,
                 exit_code=0, mutation=apply,
                 extra={"actions": len(actions), "blocked": len(summary["blocked"])})
    return summary


def render_markdown(summary: dict) -> str:
    """Ежедневный редакционный отчёт в читаемом виде."""
    lines = [
        "# Редакционный отчёт",
        "",
        f"**Дата:** {summary['generated_at']}",
        f"**Режим:** {summary['mode']} (запись в базу "
        f"{'включена' if summary['mode'] == 'apply' else 'выключена'})",
        f"**Состояние контура:** {summary['status']}",
        "",
        "## Что контур сделал бы сейчас",
        "",
    ]
    if summary["actions"]:
        lines += ["| Ценность | Действие | Объект | Причина | Применено |", "|---|---|---|---|---|"]
        for action in summary["actions"]:
            lines.append(
                f"| {action['opportunity']} | {action['action']} | {action['title']} | "
                f"{action['reason']} | {'да' if action['applied'] else 'нет'} |")
    else:
        lines.append("Действий нет: данные в порядке.")

    lines += ["", "## Что выполнить нельзя", ""]
    if summary["blocked"]:
        for item in summary["blocked"]:
            lines.append(f"- **{item['step']}** — {item['reason']}")
    else:
        lines.append("Блокировок нет.")

    lines += ["", "## Показатели", "",
              "| Показатель | Что означает | Измерено | Значение |", "|---|---|---|---|"]
    for metric in summary["metrics"]:
        lines.append(
            f"| {metric['metric']} | {metric['description']} | "
            f"{'да' if metric['measured'] else 'нет'} | "
            f"{metric['value'] if metric['measured'] else '— ' + metric['reason']} |")

    lines += ["", "Ни одно значение не проставлено без измерения: пустой показатель честнее "
              "правдоподобного числа.", ""]
    return "\n".join(lines)
