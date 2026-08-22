"""
Межсайтовое и внутрисайтовое дублирование.

Порог намеренно строгий: одинаковый текст/подборка/раскладка на 15-20 сайтах —
это scaled content abuse, даже если каждый сайт по отдельности выглядит нормально.
"""
from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Iterable

SHINGLE_SIZE = 5
NEAR_DUPLICATE_THRESHOLD = 0.65
LAYOUT_DUPLICATE_THRESHOLD = 0.85


def _tokens(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower(), flags=re.UNICODE)


def shingles(text: str, size: int = SHINGLE_SIZE) -> set[str]:
    toks = _tokens(text)
    if len(toks) < size:
        return {" ".join(toks)} if toks else set()
    return {" ".join(toks[i:i + size]) for i in range(len(toks) - size + 1)}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


@dataclass(frozen=True)
class DuplicateFinding:
    kind: str                    # text | collection | layout
    scope: str                   # intra_site | cross_tenant
    a: str
    b: str
    similarity: float
    blocking: bool
    detail: str


def compare_texts(items: list[dict[str, Any]]) -> list[DuplicateFinding]:
    """items: {id, site_id, text}"""
    prepared = [(it, shingles(it.get("text", ""))) for it in items]
    findings = []
    for i in range(len(prepared)):
        for j in range(i + 1, len(prepared)):
            (a, sa), (b, sb) = prepared[i], prepared[j]
            sim = jaccard(sa, sb)
            if sim < NEAR_DUPLICATE_THRESHOLD:
                continue
            scope = "cross_tenant" if a["site_id"] != b["site_id"] else "intra_site"
            findings.append(DuplicateFinding(
                kind="text", scope=scope, a=a["id"], b=b["id"], similarity=round(sim, 3),
                blocking=True,
                detail=("Одинаковый текст между tenant портфеля — запрещено." if scope == "cross_tenant"
                        else "Дублирующий текст внутри сайта — объединить или дифференцировать."),
            ))
    return findings


def compare_collections(collections: list[dict[str, Any]]) -> list[DuplicateFinding]:
    """collections: {id, site_id, item_ids}. Одинаковая подборка на разных сайтах — не редакция."""
    findings = []
    for i in range(len(collections)):
        for j in range(i + 1, len(collections)):
            a, b = collections[i], collections[j]
            sa, sb = set(a["item_ids"]), set(b["item_ids"])
            sim = jaccard(sa, sb)
            if sim < 0.8:
                continue
            scope = "cross_tenant" if a["site_id"] != b["site_id"] else "intra_site"
            findings.append(DuplicateFinding(
                kind="collection", scope=scope, a=a["id"], b=b["id"], similarity=round(sim, 3),
                blocking=scope == "cross_tenant",
                detail="Состав подборки практически совпадает — нужна разная редакционная логика.",
            ))
    return findings


def compare_layouts(layouts: list[dict[str, Any]]) -> list[DuplicateFinding]:
    """layouts: {site_id, module_order: [str]}"""
    findings = []
    for i in range(len(layouts)):
        for j in range(i + 1, len(layouts)):
            a, b = layouts[i], layouts[j]
            if a["site_id"] == b["site_id"]:
                continue
            oa, ob = a["module_order"], b["module_order"]
            common = sum(1 for x, y in zip(oa, ob) if x == y)
            sim = common / max(len(oa), len(ob), 1)
            if sim >= LAYOUT_DUPLICATE_THRESHOLD:
                findings.append(DuplicateFinding(
                    kind="layout", scope="cross_tenant", a=a["site_id"], b=b["site_id"],
                    similarity=round(sim, 3), blocking=True,
                    detail="Идентичная раскладка главной на разных сайтах портфеля.",
                ))
    return findings


def gate(findings: Iterable[DuplicateFinding]) -> tuple[bool, list[str]]:
    """Возвращает (можно_публиковать, причины_блокировки)."""
    blocking = [f for f in findings if f.blocking]
    reasons = [f"{f.kind}/{f.scope}: {f.a} ~ {f.b} ({f.similarity}) — {f.detail}" for f in blocking]
    return (not blocking), reasons


def distinct_value_check(new_item: dict[str, Any], existing: list[dict[str, Any]]) -> tuple[bool, str]:
    """
    Материал без отдельной ценности относительно существующего URL (своего или чужого tenant)
    не публикуется автоматически.
    """
    new_sh = shingles(new_item.get("text", ""))
    for ex in existing:
        sim = jaccard(new_sh, shingles(ex.get("text", "")))
        if sim >= NEAR_DUPLICATE_THRESHOLD:
            return False, f"Дублирует {ex['id']} (сходство {sim:.2f}); отдельной ценности нет."
    covered_facts = set()
    for ex in existing:
        covered_facts |= set(ex.get("facts", []))
    new_facts = set(new_item.get("facts", [])) - covered_facts
    if not new_facts and existing:
        return False, "Не добавляет ни одного факта сверх уже опубликованного."
    return True, f"Добавляет {len(new_facts)} новых фактов."
