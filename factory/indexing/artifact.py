"""Сборка политики индексации в выкладываемый артефакт.

Артефакт нужен затем, что посредник на хосте не должен читать репозиторий: он
читает один файл, собранный из профилей и подписанный отпечатками. Без этого
разъезжаются две вещи — что решено в Git и что работает на сервере, — и именно
это разъезжание однажды закрыло живую витрину.

Манифест несёт отпечаток каждого профиля и отпечаток получившейся матрицы.
Сборка детерминирована: из одного и того же дерева получается байт в байт один и
тот же файл, поэтому расхождение отпечатков означает расхождение входа, а не
случайность сериализации.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from factory.indexing.policy import FLEET_REGISTRY, IndexingPolicy, compile_policy

ARTIFACT_NAME = "indexing-policy.json"
ARTIFACT_SCHEMA = "indexing-policy/1.0"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build(
    profiles_dir: Path,
    *,
    environment: str = "production",
    fleet_path: Path | None = None,
    expected_domains: set[str] | None = None,
    source_commit: str | None = None,
) -> dict:
    """Собрать артефакт. Любая неполнота входа — исключение, а не пустая матрица."""
    реестр = fleet_path if fleet_path is not None else profiles_dir.parent / FLEET_REGISTRY.name
    policy = compile_policy(
        profiles_dir,
        environment=environment,
        fleet_path=реестр,
        expected_domains=expected_domains,
    )
    профили = {}
    for путь in sorted(profiles_dir.glob("*.json")):
        профили[путь.name] = _sha256(путь.read_bytes())
    # Реестр флота — такой же вход, как профили: он задаёт, какие домены вообще
    # обслуживаются. Без его отпечатка манифест не заметил бы появления сайта.
    профили[реестр.name] = _sha256(реестр.read_bytes())

    домены = {
        домен: {
            "site_id": решение.site_id,
            "indexing_expected": решение.expected,
            "indexing_reason": решение.reason,
            "canonical_domain": решение.canonical_domain,
            "profile_family": решение.family,
            "profile_version": решение.profile_version,
            "aliases": list(решение.aliases),
        }
        for домен, решение in sorted(policy.decisions.items())
    }
    матрица = policy.matrix()
    тело = {
        "schema": ARTIFACT_SCHEMA,
        "environment": environment,
        "matrix": матрица,
        "domains": домены,
    }
    # Отпечаток матрицы считается по её каноническому виду: он должен зависеть
    # от решений, а не от порядка ключей или пробелов.
    матрица_байты = json.dumps(тело, ensure_ascii=False, sort_keys=True,
                               separators=(",", ":")).encode("utf-8")
    тело["manifest"] = {
        "profiles": профили,
        "profiles_sha256": _sha256(
            json.dumps(профили, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ),
        "policy_sha256": _sha256(матрица_байты),
        "source_commit": source_commit,
    }
    return тело


def write(artifact: dict, destination: Path) -> Path:
    """Записать артефакт детерминированно."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(artifact, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return destination


def load(path: Path) -> IndexingPolicy:
    """Прочитать собранный артефакт обратно в политику.

    Нужна посреднику: он не должен уметь ничего, кроме как спросить у готового
    файла, открыт ли домен.
    """
    from factory.indexing.policy import DomainDecision, PolicyError, normalize_domain

    текст = path.read_text(encoding="utf-8")
    if not текст.strip():
        raise PolicyError(f"{path.name}: артефакт пуст")
    данные = json.loads(текст)
    if данные.get("schema") != ARTIFACT_SCHEMA:
        raise PolicyError(f"{path.name}: чужая схема {данные.get('schema')!r}")
    policy = IndexingPolicy(source_environment=данные.get("environment", "production"))
    for домен, запись in данные.get("domains", {}).items():
        нормальный = normalize_domain(домен)
        policy.decisions[нормальный] = DomainDecision(
            domain=нормальный,
            site_id=запись["site_id"],
            expected=запись["indexing_expected"],
            reason=запись["indexing_reason"],
            environment=данные.get("environment", "production"),
            family=запись.get("profile_family", ""),
            profile_version=str(запись.get("profile_version", "")),
            canonical_domain=normalize_domain(запись["canonical_domain"]),
            aliases=tuple(запись.get("aliases", ())),
        )
    return policy
