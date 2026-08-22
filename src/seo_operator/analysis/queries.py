"""Классификация запросов по интенту и кластеризация. Правила — из QUERY_TAXONOMY.yaml."""
from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Iterable

from .. import config


@dataclass(frozen=True)
class ClassifiedQuery:
    query: str
    intent: str
    is_brand: bool
    confidence: float
    target_page_type: str | None
    matched_title: str | None = None

    @property
    def assignable(self) -> bool:
        threshold = config.query_taxonomy()["confidence"]["min_to_assign_target_page"]
        return self.confidence >= threshold and self.target_page_type is not None


def normalize(query: str) -> str:
    q = unicodedata.normalize("NFKC", query).lower().strip()
    q = re.sub(r"[ё]", "е", q)
    return re.sub(r"\s+", " ", q)


class QueryClassifier:
    """
    Титульный словарь передаётся снаружи (из CMS/каталога), а не зашивается:
    без реальных идентификаторов тайтлов exact_title определить нельзя.
    """

    def __init__(self, brand_tokens: Iterable[str], title_index: dict[str, str] | None = None) -> None:
        self.brand_tokens = [normalize(t) for t in brand_tokens]
        # normalized alias -> canonical title slug
        self.title_index = {normalize(k): v for k, v in (title_index or {}).items()}
        self.taxonomy = config.query_taxonomy()
        self._classes = sorted(self.taxonomy["classes"], key=lambda c: c["priority"])

    def _match_title(self, q: str) -> tuple[str | None, bool]:
        """Возвращает (slug, is_exact). Точное совпадение отличается от вхождения."""
        if q in self.title_index:
            return self.title_index[q], True
        for alias, slug in self.title_index.items():
            if len(alias) >= 4 and alias in q:
                return slug, False
        return None, False

    def classify(self, query: str) -> ClassifiedQuery:
        q = normalize(query)
        is_brand = any(tok and tok in q for tok in self.brand_tokens)
        slug, exact = self._match_title(q)

        for cls in self._classes:
            cid = cls["id"]
            if cid == "unknown":
                continue

            if cid == "exact_title":
                if slug and exact:
                    return ClassifiedQuery(query, cid, is_brand, 0.95, cls["target_page_type"], slug)
                continue
            if cid == "alt_title":
                if slug and not exact and not self._has_modifier(q):
                    return ClassifiedQuery(query, cid, is_brand, 0.8, cls["target_page_type"], slug)
                continue
            if cid == "navigational":
                if is_brand and len(q.split()) <= 3:
                    return ClassifiedQuery(query, cid, is_brand, 0.85, cls["target_page_type"], slug)
                continue

            for pattern in cls.get("signals_ru", []):
                if re.search(pattern, q):
                    conf = 0.9 if slug else 0.75
                    return ClassifiedQuery(query, cid, is_brand, conf, cls["target_page_type"], slug)

        if slug:
            return ClassifiedQuery(query, "alt_title", is_brand, 0.7, "title", slug)
        return ClassifiedQuery(query, "unknown", is_brand, 0.2, None, None)

    def _has_modifier(self, q: str) -> bool:
        modifiers = ["сезон", "серия", "эпизод", "смотреть", "когда выйдет", "дата выхода", "порядок"]
        return any(m in q for m in modifiers)


def cluster(classified: Iterable[ClassifiedQuery]) -> dict[str, list[ClassifiedQuery]]:
    """Кластер = (intent, title_slug|'_'). Один кластер => одна целевая страница."""
    clusters: dict[str, list[ClassifiedQuery]] = defaultdict(list)
    for cq in classified:
        key = f"{cq.intent}:{cq.matched_title or '_'}"
        clusters[key].append(cq)
    return dict(clusters)


def coverage_report(rows: list[dict[str, Any]], classifier: QueryClassifier) -> dict[str, Any]:
    """Сколько запросов классифицировано уверенно и как распределены клики по интентам."""
    by_intent: dict[str, dict[str, float]] = defaultdict(lambda: {"queries": 0, "clicks": 0.0, "impressions": 0.0})
    unknown = []
    for row in rows:
        q = row.get("query")
        if not q:
            continue
        cq = classifier.classify(q)
        bucket = by_intent[cq.intent]
        bucket["queries"] += 1
        bucket["clicks"] += row.get("clicks", 0)
        bucket["impressions"] += row.get("impressions", 0)
        if not cq.assignable:
            unknown.append(q)
    total = sum(b["queries"] for b in by_intent.values()) or 1
    return {
        "by_intent": {k: dict(v) for k, v in by_intent.items()},
        "unassignable_share": round(len(unknown) / total, 3),
        "unassignable_sample": unknown[:20],
    }
