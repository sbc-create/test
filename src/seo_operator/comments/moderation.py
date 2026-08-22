"""
Работа с НАСТОЯЩИМИ комментариями.

Единственное, чего этот модуль не умеет и не должен уметь, — создавать
пользовательскую активность. Любая попытка перехватывается GR-002 ещё
до записи, в guardrails.check_no_fake_engagement.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Iterable

from ..guardrails import GuardrailViolation

SPAM_PATTERNS = [
    (r"https?://\S+", 0.25, "внешняя ссылка"),
    (r"\b(казино|ставк[аи]|букмекер|заработок\s+без)\b", 0.5, "азартная/финансовая реклама"),
    (r"\b(промокод|скидк[аи]\s+\d+%)\b", 0.4, "промо"),
    (r"(.)\1{6,}", 0.4, "флуд-повтор символов"),
    (r"\b(t\.me/|wa\.me/|@[a-z0-9_]{5,})\b", 0.35, "переход в мессенджер"),
]

ABUSE_PATTERNS = [
    (r"\b(убей|сдохн|ненавижу\s+всех)\b", 0.6, "агрессия"),
]

QUESTION_MARKERS = [
    r"\?$", r"^(как|где|когда|почему|зачем|сколько|кто|что\s+за|можно\s+ли|будет\s+ли)\b",
]


@dataclass
class Comment:
    id: str
    site_id: str
    page_url: str
    author_type: str          # "user" — всегда настоящий пользователь
    text: str
    created_at: str
    links: list[str] = field(default_factory=list)


@dataclass
class ModerationVerdict:
    comment_id: str
    action: str               # publish | hold | reject
    spam_score: float
    reasons: list[str]
    link_treatment: str
    appealable: bool = True


def classify(comment: Comment) -> ModerationVerdict:
    score = 0.0
    reasons: list[str] = []
    text = comment.text.strip()

    for pattern, weight, label in SPAM_PATTERNS + ABUSE_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            score += weight
            reasons.append(label)

    if len(text) < 3:
        score += 0.4
        reasons.append("пустой/бессодержательный")

    score = round(min(score, 1.0), 3)
    if score >= 0.7:
        action = "reject"
    elif score >= 0.35:
        action = "hold"
    else:
        action = "publish"

    return ModerationVerdict(
        comment_id=comment.id, action=action, spam_score=score, reasons=reasons,
        # GR: пользовательские ссылки всегда ugc nofollow.
        link_treatment='rel="ugc nofollow"' if (comment.links or "http" in text) else "none",
    )


def detect_duplicates(comments: Iterable[Comment]) -> list[tuple[str, str]]:
    seen: dict[str, str] = {}
    dupes = []
    for c in comments:
        key = re.sub(r"\W+", "", c.text.lower())[:120]
        if not key:
            continue
        if key in seen:
            dupes.append((seen[key], c.id))
        else:
            seen[key] = c.id
    return dupes


def sanitize_links(html: str) -> str:
    """Добавляет rel="ugc nofollow" ко всем пользовательским ссылкам."""
    def repl(m: re.Match) -> str:
        tag = m.group(0)
        if "rel=" in tag:
            return re.sub(r'rel="[^"]*"', 'rel="ugc nofollow"', tag)
        return tag[:-1] + ' rel="ugc nofollow">'
    return re.sub(r"<a\s[^>]*>", repl, html, flags=re.IGNORECASE)


def extract_questions(comments: Iterable[Comment]) -> list[dict[str, Any]]:
    """Повторяющиеся вопросы аудитории — источник улучшений страницы и FAQ."""
    questions = []
    for c in comments:
        text = c.text.strip()
        for marker in QUESTION_MARKERS:
            if re.search(marker, text, re.IGNORECASE | re.MULTILINE):
                questions.append({"comment_id": c.id, "page_url": c.page_url,
                                  "site_id": c.site_id, "text": text})
                break
    return questions


def recurring_questions(questions: list[dict[str, Any]], min_count: int = 3) -> list[dict[str, Any]]:
    """Только реально повторяющиеся вопросы попадают в FAQ — не выдуманные."""
    def norm(t: str) -> str:
        return " ".join(sorted(set(re.findall(r"\w{4,}", t.lower()))))[:80]

    counter = Counter(norm(q["text"]) for q in questions)
    out = []
    for key, count in counter.most_common():
        if count < min_count or not key:
            continue
        samples = [q for q in questions if norm(q["text"]) == key]
        out.append({
            "signature": key, "count": count,
            "pages": sorted({q["page_url"] for q in samples}),
            "sample_texts": [q["text"] for q in samples[:3]],
            "proposed_action": "добавить в FAQ страницы с фактическим ответом и источником",
        })
    return out


def quality_score(comment: Comment) -> float:
    """
    Для сортировки существующих комментариев. НЕ создаёт вовлечённость,
    только упорядочивает то, что уже написали люди.
    """
    text = comment.text.strip()
    score = 0.0
    score += min(len(text) / 400.0, 1.0) * 0.4
    score += 0.2 if re.search(r"[.!?]", text) else 0.0
    score += 0.2 if len(set(re.findall(r"\w{4,}", text.lower()))) >= 8 else 0.0
    score -= classify(comment).spam_score * 0.5
    return round(max(0.0, min(1.0, score)), 3)


def detect_rating_manipulation(ratings: list[dict[str, Any]]) -> list[str]:
    """
    Аномалии в НАСТОЯЩИХ оценках. Обнаружение накрутки — защитная функция,
    противоположная её созданию.
    """
    alerts = []
    if not ratings:
        return alerts
    by_day = Counter(r["date"] for r in ratings)
    if by_day:
        avg = sum(by_day.values()) / len(by_day)
        for day, count in by_day.items():
            if avg > 0 and count > max(10, avg * 5):
                alerts.append(f"Всплеск оценок {day}: {count} при среднем {avg:.1f}")
    values = Counter(r["value"] for r in ratings)
    total = sum(values.values())
    for value, count in values.items():
        if total >= 20 and count / total > 0.9:
            alerts.append(f"{count}/{total} оценок имеют одно значение {value} — вероятная накрутка")
    return alerts


def forbid_synthetic(payload: dict[str, Any]) -> None:
    """Явный барьер для любого кода, который попытается создать активность."""
    if payload.get("author_type") == "user" and payload.get("generated_by"):
        raise GuardrailViolation("GR-002", "Создание комментария от лица пользователя запрещено.")
    if payload.get("kind") in {"rating", "vote", "review"} and payload.get("generated_by"):
        raise GuardrailViolation("GR-002", f"Генерация '{payload['kind']}' запрещена.")
