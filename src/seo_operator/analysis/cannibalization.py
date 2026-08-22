"""
Каннибализация: несколько URL конкурируют за один интент — внутри сайта и между сайтами портфеля.

Primary URL выбирается по фактической полезности, а не по текущей позиции:
страница с лучшей позицией, но без плеера и без глубины, проиграет пользователю.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class Conflict:
    cluster_key: str
    scope: str                    # "intra_site" | "cross_tenant"
    urls: list[str]
    sites: list[str]
    total_impressions: float
    recommended_primary: str
    reason: str
    severity: str


def _utility(page: dict[str, Any]) -> float:
    """
    Полезность страницы для интента. Позиция входит с малым весом,
    чтобы не закреплять случайно выигравший URL.
    """
    score = 0.0
    score += 3.0 if page.get("has_media_available") else 0.0
    score += 2.0 * min(page.get("content_depth_score", 0.0), 1.0)
    score += 1.5 if page.get("internal_links_in", 0) >= 3 else 0.0
    score += 1.0 * min(page.get("engagement_score", 0.0), 1.0)
    score += 0.5 if page.get("canonical_self") else 0.0
    pos = page.get("position")
    if pos:
        score += max(0.0, (20 - float(pos)) / 20) * 0.8
    return round(score, 3)


def detect(rows: Iterable[dict[str, Any]], page_meta: dict[str, dict[str, Any]] | None = None,
           min_impressions: float = 100.0) -> list[Conflict]:
    """
    rows: {cluster_key, url, site_id, impressions, clicks, position}
    page_meta: url -> признаки полезности.
    """
    page_meta = page_meta or {}
    grouped: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        grouped[r["cluster_key"]].append(r)

    conflicts: list[Conflict] = []
    for key, entries in grouped.items():
        by_url: dict[str, dict] = {}
        for e in entries:
            u = e["url"]
            agg = by_url.setdefault(u, {"url": u, "site_id": e.get("site_id"),
                                        "impressions": 0.0, "clicks": 0.0, "positions": []})
            agg["impressions"] += float(e.get("impressions") or 0)
            agg["clicks"] += float(e.get("clicks") or 0)
            if e.get("position") is not None:
                agg["positions"].append(float(e["position"]))

        material = [v for v in by_url.values() if v["impressions"] >= min_impressions]
        if len(material) < 2:
            continue

        sites = sorted({v["site_id"] for v in material if v["site_id"]})
        scope = "cross_tenant" if len(sites) > 1 else "intra_site"

        scored = []
        for v in material:
            meta = dict(page_meta.get(v["url"], {}))
            meta.setdefault("position", min(v["positions"]) if v["positions"] else None)
            scored.append((_utility(meta), v))
        scored.sort(key=lambda t: (-t[0], -t[1]["impressions"]))

        best_score, best = scored[0]
        runner_score = scored[1][0]
        total_imp = sum(v["impressions"] for v in material)

        if scope == "cross_tenant":
            severity = "high"
            reason = ("Разные tenant портфеля конкурируют за один интент. "
                      "Требуется отдельное решение о разделении интентов, а не canonical.")
        elif best_score - runner_score < 0.5:
            severity = "medium"
            reason = ("Полезность страниц сопоставима — автоматический выбор primary небезопасен, "
                      "нужна редакционная дифференциация интентов.")
        else:
            severity = "low"
            reason = f"Явный лидер по полезности (utility {best_score} против {runner_score})."

        conflicts.append(Conflict(
            cluster_key=key, scope=scope,
            urls=[v["url"] for v in material], sites=sites,
            total_impressions=round(total_imp, 1),
            recommended_primary=best["url"], reason=reason, severity=severity,
        ))

    conflicts.sort(key=lambda c: (-{"high": 2, "medium": 1, "low": 0}[c.severity], -c.total_impressions))
    return conflicts


def auto_resolvable(conflict: Conflict) -> bool:
    """Автоматически решаем только однозначные внутрисайтовые случаи."""
    return conflict.scope == "intra_site" and conflict.severity == "low"
