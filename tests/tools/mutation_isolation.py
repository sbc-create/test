#!/usr/bin/env python3
"""Мутационная проверка ворот изоляции сайтов.

Зелёный прогон сам по себе ничего не доказывает: тест мог не проверять ничего.
Здесь в исходники по очереди вносится ровно одна поломка защиты, и прогон обязан
упасть. Если он остаётся зелёным — падает эта проверка: значит, ворота фиктивные.
"""
from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "blueprints" / "payload-next-multisite" / "app"
SUITE = APP / "tests" / "tenant-isolation.ts"
TSX = APP / "node_modules" / ".bin" / "tsx"


@dataclass(frozen=True)
class Mutation:
    name: str
    path: Path
    before: str
    after: str


MUTATIONS = [
    Mutation(
        "плагин перестаёт ограничивать выборку по сайту",
        APP / "src/payload.config.ts",
        "const SCOPED = { useTenantAccess: true, useBaseFilter: true } as const",
        "const SCOPED = { useTenantAccess: false, useBaseFilter: false } as const",
    ),
    Mutation(
        "tenantSelfAccess фильтрует сайты по несуществующему полю tenant",
        APP / "src/access/index.ts",
        "  return { id: { in: tenants } }",
        "  return { tenant: { in: tenants } }",
    ),
    Mutation(
        "хук целостности перестаёт проверять межсайтовые ссылки",
        APP / "src/hooks/tenant-integrity.ts",
        "  const references = collectReferences(collection.fields, data).filter((reference) =>",
        "  if (true) return data\n  const references = collectReferences(collection.fields, data).filter((reference) =>",
    ),
    Mutation(
        "tenantFind перестаёт добавлять констрейнт сайта",
        APP / "src/lib/tenant-query.ts",
        "  return where ? { and: [constraint, where] } : constraint",
        "  return where ?? {}",
    ),
    Mutation(
        "неизвестный домен подставляет первый попавшийся сайт",
        APP / "src/lib/tenant-query.ts",
        "    where: { domain: { equals: domain } },",
        "    where: {},",
    ),
]


def run_suite() -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(ROOT / "tests/tools/with_app_env.py"), "--scope", "anime", "--",
         str(TSX), str(SUITE)],
        cwd=ROOT, capture_output=True, text=True, timeout=1800, check=False,
    )


def main() -> int:
    baseline = run_suite()
    if baseline.returncode != 0:
        print("BASELINE FAIL: прогон изоляции красный до мутаций, мутировать нечего")
        print(baseline.stdout[-4000:])
        return 1
    print("BASELINE OK: изоляция зелёная")

    failures = 0
    for mutation in MUTATIONS:
        original = mutation.path.read_text(encoding="utf-8")
        if mutation.before not in original:
            print(f"SKIP  {mutation.name}: якорь не найден в {mutation.path.relative_to(ROOT)}")
            failures += 1
            continue
        mutation.path.write_text(original.replace(mutation.before, mutation.after, 1), encoding="utf-8")
        try:
            result = run_suite()
        finally:
            mutation.path.write_text(original, encoding="utf-8")
        if result.returncode == 0:
            print(f"FAIL  {mutation.name}: поломка защиты НЕ обнаружена тестами")
            failures += 1
        else:
            failed_lines = [line for line in result.stdout.splitlines() if line.startswith("FAIL")]
            print(f"OK    {mutation.name}: обнаружена, упавших проверок {len(failed_lines)}")

    print(f"\nмутаций: {len(MUTATIONS)}, не обнаружено: {failures}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
