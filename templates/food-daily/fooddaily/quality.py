"""Ворота публикации: что не пускает материал в preview.

Импорт черновика и его публикация — разные решения. Черновик с
сомнительными фактами принимается в хранилище (редактор должен его видеть),
но не попадает на страницы, пока факты не исправлены.
"""

from __future__ import annotations

# Верхние пределы на один рецепт. Не нормы, а грубый фильтр явных ошибок
# единиц: «400 л бульона на 2 порции», «100 стаканов сливок».
LIMITS = {
    "l": 10,
    "ml": 10000,
    "kg": 10,
    "g": 10000,
    "cup": 20,
    "tbsp": 40,
    "tsp": 40,
    "pcs": 60,
    "clove": 30,
    "head": 10,
    "piece": 40,
    "pack": 10,
    "can": 10,
    "bunch": 10,
}


def fact_problems(facts: dict) -> list[str]:
    out = []
    for i in facts["ingredients"]:
        q = i.get("quantity_max") or i.get("quantity")
        lim = LIMITS.get(i.get("unit") or "")
        if q is not None and lim is not None and q > lim:
            out.append(f"неправдоподобное количество: {i['name']} — {q:g} {i['unit']}")
    if not facts.get("servings"):
        out.append("не указано число порций")
    return out


def publish_blockers(payload: dict) -> list[str]:
    blockers = fact_problems(payload["facts"])
    notes = payload["draft"].get("editor_notes") or []
    if any("заблокирован" in n for n in notes):
        blockers.append("редакторская пометка о блокировке")
    return blockers
