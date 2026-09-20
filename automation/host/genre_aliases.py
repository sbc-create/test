"""Canonical genre alias registry for Zona/Lords host runtime.

Single membership key for catalog facets, collections, and recommendations.
Presentation and collection_contract must resolve through this table — never
maintain a second private mapping.
"""
from __future__ import annotations

#: canonical_code → frozenset of all accepted aliases (codes + RU labels + translits)
GENRE_ALIAS_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("comedy", ("comedy", "komediya", "комедия", "comedies")),
    ("drama", ("drama", "drama", "драма")),
    ("triller", ("triller", "thriller", "триллер")),
    ("action", ("action", "боевик", "boevik")),
    ("dorama", ("dorama", "дорама")),
    ("melodrama", ("melodrama", "мелодрама", "romantika", "романтика")),
    ("west_content", ("west_content", "западный контент", "zapadnyy-kontent")),
    ("history", ("history", "исторический", "istoricheskiy")),
    ("detective", ("detective", "детектив", "detektiv")),
    ("animation", ("animation", "анимация", "мультфильм", "multfilm")),
)

# Build reverse lookup: any alias → canonical code
_ALIAS_TO_CANONICAL: dict[str, str] = {}
_CANONICAL_ALIASES: dict[str, frozenset[str]] = {}
for _canon, _aliases in GENRE_ALIAS_GROUPS:
    bag = frozenset(a.strip().lower() for a in _aliases if a and a.strip())
    _CANONICAL_ALIASES[_canon] = bag
    for a in bag:
        _ALIAS_TO_CANONICAL[a] = _canon


def нормализовать_ключ_жанра(сырой: str) -> str:
    """Lower/strip only — translit/NFKC left to caller when available."""
    return (сырой or "").strip().lower()


def канон_жанра(сырой: str) -> str | None:
    """Map any known alias to canonical code; None if unknown."""
    ключ = нормализовать_ключ_жанра(сырой)
    if not ключ:
        return None
    if ключ in _ALIAS_TO_CANONICAL:
        return _ALIAS_TO_CANONICAL[ключ]
    return None


def алиасы_жанра(сырой: str) -> frozenset[str]:
    """All aliases for a code/label, or {normalized raw} if unknown."""
    ключ = нормализовать_ключ_жанра(сырой)
    if not ключ:
        return frozenset()
    канон = _ALIAS_TO_CANONICAL.get(ключ)
    if канон:
        return _CANONICAL_ALIASES[канон]
    return frozenset({ключ})


def жанр_совпадает(запрос: str, коды: list | tuple, имена: list | tuple) -> bool:
    """True if title genre codes/labels share a canonical group with the query.

    Matches whole labels and whitespace/comma/slash tokens after alias
    expansion. Avoids accidental character-substring matches like ``коме``∈
    unrelated words, while still accepting compound labels
    «романтическая комедия».
    """
    запрос_алиасы = алиасы_жанра(запрос)
    if not запрос_алиасы:
        return False
    токены: set[str] = set()
    for сырьё in list(коды or []) + list(имена or []):
        s = нормализовать_ключ_жанра(str(сырьё or ""))
        if not s:
            continue
        токены.add(s)
        токены |= set(алиасы_жанра(s))
        for часть in s.replace("/", " ").replace(",", " ").replace("·", " ").split():
            ч = часть.strip()
            if ч:
                токены.add(ч)
                токены |= set(алиасы_жанра(ч))
    return bool(запрос_алиасы & токены)
