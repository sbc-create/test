"""Политика индексации: единственный источник истины и производные от него."""

from factory.indexing.policy import (
    CLOSED,
    OPEN,
    IndexingPolicy,
    PolicyError,
    compile_policy,
    load_profiles,
    normalize_domain,
)

__all__ = [
    "CLOSED",
    "OPEN",
    "IndexingPolicy",
    "PolicyError",
    "compile_policy",
    "load_profiles",
    "normalize_domain",
]
