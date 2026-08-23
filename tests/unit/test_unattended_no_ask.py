"""UNATTENDED_NO_ASK: каждое решение — allow или deny, ask не существует.

Профиль рассчитан на работу без человека у клавиатуры. Вопрос, на который
некому ответить, останавливает конвейер так же надёжно, как запрет, но при этом
не оставляет следа в отчёте. Поэтому решений ровно два, а всё неизвестное
закрывается и называется.

Тест закрывает две стороны одного утверждения: штатный цикл YummyAnime проходит
целиком без единой остановки, а опасные операции остаются запрещёнными. Проверять
только первое — значит доказывать, что дверь открыта, не проверив замок.
"""

from __future__ import annotations

import pytest

from seo_operator import hookguard

#: Полный штатный цикл: от клона до pull request.
ROUTINE_CYCLE = [
    ("git clone", "git clone https://github.com/sbc-create/yummyani.git /srv/sites/yummyani"),
    ("git fetch", "git fetch origin"),
    ("git checkout", "git checkout -b claude/yummyani-three-sites-staging"),
    ("git switch", "git switch claude/yummyani-three-sites-staging"),
    ("рабочий каталог", "mkdir -p /srv/sites/yummyani-staging"),
    ("правка файлов", "cp compose.yaml /srv/sites/yummyani-staging/compose.yaml"),
    ("pnpm install", "pnpm install --frozen-lockfile"),
    ("prisma generate", "pnpm prisma generate"),
    ("pnpm build", "pnpm build"),
    ("pytest", "pytest tests/ -q"),
    ("playwright", "npx playwright test"),
    ("docker build", "docker compose -f compose.staging.yaml build"),
    ("docker up", "docker compose -f compose.staging.yaml up -d"),
    ("migrate deploy", "docker compose exec web pnpm prisma migrate deploy"),
    ("migrate status", "pnpm prisma migrate status"),
    ("backup", "docker exec pg-site pg_dump -U app site > /srv/backups/site.sql"),
    ("health-check", "curl -sS http://127.0.0.1:8081/api/health"),
    ("цикл по сайтам", "for s in site org biz; do curl -sS http://127.0.0.1/$s; done"),
    ("аудит хоста", "df -h"),
    ("git add", "git add -A"),
    ("git commit", "git commit -m 'staging: three isolated sites'"),
    ("push рабочей ветки", "git push origin claude/yummyani-three-sites-staging"),
    ("push ветки cursor", "git push origin cursor/zomro-three-sites-check"),
    ("создание PR", "gh pr create --base cursor/zomro-three-sites --title t --body b"),
]

#: Операции, которые обязаны закрываться сами, без вопроса человеку.
DANGEROUS = [
    ("force push", "git push --force origin main"),
    ("push в main", "git push origin main"),
    ("удаление ветки", "git branch -D cursor/zomro-three-sites"),
    ("удаление репозитория", "gh repo delete sbc-create/yummyani"),
    ("слияние PR", "gh pr merge 12 --merge"),
    ("вывод токена", "gh auth token"),
    ("вывод секрета", "echo $CDNVIDEOHUB_API_TOKEN"),
    ("дамп окружения", "printenv"),
    ("prisma reset", "pnpm prisma migrate reset --force"),
    ("db:reset", "pnpm db:reset"),
    ("автоматический seed", "pnpm db:seed"),
    ("destructive push схемы", "pnpm prisma db push --accept-data-loss"),
    ("удаление backups", "rm -rf /srv/backups"),
    ("удаление базы", "dropdb site"),
    ("перенос домена", "aws route53domains transfer-domain --domain-name yummyani.site"),
    ("отключение проверок", "claude --dangerously-skip-permissions"),
]


def decide(tool: str, **tool_input) -> str:
    payload = {"tool_name": tool, "tool_input": tool_input}
    return hookguard.decide(payload)["hookSpecificOutput"]["permissionDecision"]


def bash(command: str) -> str:
    return decide("Bash", command=command)


@pytest.mark.parametrize(("label", "command"), ROUTINE_CYCLE, ids=[c[0] for c in ROUTINE_CYCLE])
def test_routine_cycle_is_allowed(label: str, command: str) -> None:
    assert bash(command) == "allow", f"{label}: штатный шаг остановлен"


@pytest.mark.parametrize(("label", "command"), DANGEROUS, ids=[c[0] for c in DANGEROUS])
def test_dangerous_is_denied(label: str, command: str) -> None:
    assert bash(command) == "deny", f"{label}: опасная операция не закрыта"


def test_no_ask_anywhere_in_the_cycle() -> None:
    """Главное утверждение: за весь цикл ask не встречается ни разу."""
    decisions = [bash(command) for _, command in ROUTINE_CYCLE + DANGEROUS]
    assert decisions.count("ask") == 0
    assert set(decisions) == {"allow", "deny"}


def test_unknown_tool_is_denied_not_asked() -> None:
    assert decide("SomeToolInventedTomorrow") == "deny"


def test_unparseable_payload_fails_closed_to_deny() -> None:
    assert hookguard.decide({})["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_protective_machinery_is_not_self_editable() -> None:
    """Хук не может переписать сам себя даже в неинтерактивном режиме."""
    assert decide("Edit", file_path="/srv/site-factory/repo/.claude/settings.json") == "deny"
    assert decide("Edit", file_path="/srv/site-factory/repo/.claude/hooks/guard_bash.py") == "deny"


def test_ordinary_repository_edit_is_allowed() -> None:
    assert decide("Edit", file_path="/srv/sites/yummyani/src/app/page.tsx") == "allow"


def test_github_read_and_pr_are_allowed_delete_is_not() -> None:
    assert decide("mcp__github__get_file_contents") == "allow"
    assert decide("mcp__github__create_pull_request") == "allow"
    assert decide("mcp__github__create_repository") == "deny"


def test_decision_map_has_no_ask_leg() -> None:
    assert "ask" not in set(hookguard.DECISION_MAP.values())
