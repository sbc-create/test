"""
Редакционный ответ с раскрытым авторством.

Ответ — отдельная сущность (editorial_reply), а не пользовательский комментарий.
Он не маскируется под человека и не участвует в оценках.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from ..guardrails import AuthorizationBlocked, GuardrailViolation

ALLOWED_AUTHORS = ("Редакция сайта", "AI-ассистент редакции")

PERSONAL_EXPERIENCE_PATTERNS = [
    r"\bя\s+смотрел[аи]?\b", r"\bмне\s+понравил", r"\bя\s+пересматрива",
    r"\bмоя\s+любим", r"\bя\s+плакал",
]
PROMISE_PATTERNS = [r"\bмы\s+добавим\b", r"\bскоро\s+будет\s+доступно\b", r"\bобещаю\b"]
HIDDEN_AD_PATTERNS = [r"https?://(?!.*(?:\bdocs\b))\S+", r"\bпромокод\b", r"\bподпишись\s+на\b"]


@dataclass
class EditorialReply:
    comment_id: str
    site_id: str
    author_label: str
    text: str
    entity_type: str = "editorial_reply"     # никогда не "user_comment"
    sources: list[str] = field(default_factory=list)
    editable: bool = True
    deletable_with_audit: bool = True


@dataclass
class ReplyCheck:
    ok: bool
    violations: list[str] = field(default_factory=list)


def check_reply(reply: EditorialReply, site_manifest: dict[str, Any] | None,
                answers_real_comment: bool, states_facts: bool) -> ReplyCheck:
    violations: list[str] = []

    if not (site_manifest or {}).get("disclosed_editorial_reply_enabled"):
        raise AuthorizationBlocked(
            f"disclosed_editorial_reply_enabled выключен для {reply.site_id}.",
            {"site": reply.site_id, "needs": "disclosed_editorial_reply_enabled: true"})

    if reply.author_label not in ALLOWED_AUTHORS:
        violations.append(f"Автор должен быть раскрыт: {list(ALLOWED_AUTHORS)}.")
    if reply.entity_type != "editorial_reply":
        violations.append("Ответ не может быть записан как пользовательский комментарий.")
    if not answers_real_comment:
        violations.append("Ответ должен относиться к реальному комментарию.")

    lowered = reply.text.lower()
    for pattern in PERSONAL_EXPERIENCE_PATTERNS:
        if re.search(pattern, lowered):
            violations.append("Ответ имитирует личный опыт просмотра.")
            break
    for pattern in PROMISE_PATTERNS:
        if re.search(pattern, lowered):
            violations.append("Ответ обещает действие, которое система не гарантирует.")
            break
    for pattern in HIDDEN_AD_PATTERNS:
        if re.search(pattern, lowered):
            violations.append("Ответ содержит скрытую рекламу или внешнее продвижение.")
            break
    if states_facts and not reply.sources:
        violations.append("Фактические утверждения без источника не публикуются.")

    return ReplyCheck(not violations, violations)


def build_reply(comment_id: str, site_id: str, text: str, sources: list[str],
                author_label: str = "AI-ассистент редакции") -> EditorialReply:
    if author_label not in ALLOWED_AUTHORS:
        raise GuardrailViolation("GR-002", f"Недопустимая подпись автора: {author_label}")
    return EditorialReply(comment_id=comment_id, site_id=site_id,
                          author_label=author_label, text=text, sources=sources)
