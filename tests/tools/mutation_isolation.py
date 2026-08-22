#!/usr/bin/env python3
"""Мутационная проверка критических ворот: изоляция сайтов и SEO.

Зелёный прогон сам по себе ничего не доказывает: тест мог не проверять ничего.
Здесь в исходники по очереди вносится ровно одна поломка защиты, и прогон обязан
упасть. Если он остаётся зелёным — падает эта проверка: значит, ворота фиктивные.
"""
from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "blueprints" / "payload-next-multisite" / "app"
SUITE = APP / "tests" / "tenant-isolation.ts"
SEO_SUITE = ROOT / "tests" / "tools" / "frontend_http.py"
SEO_RULES = APP / "tests" / "seo-matrix.ts"
TSX = APP / "node_modules" / ".bin" / "tsx"


@dataclass(frozen=True)
class Mutation:
    name: str
    path: Path
    before: str
    after: str
    #: Каким прогоном ловится поломка. Ворота изоляции и SEO проверяются разными.
    suite: str = "isolation"


SEO_MUTATIONS = [
    Mutation(
        "canonical перестаёт быть абсолютным",
        APP / "src/seo/metadata.ts",
        "    rule.canonical === 'none_no_index' || !indexable ? null : absoluteUrl(input.tenant, input.path)",
        "    rule.canonical === 'none_no_index' || !indexable ? null : input.path",
        suite="seo",
    ),
    Mutation(
        "раздел без владельца снова индексируется",
        APP / "src/app/(frontend)/catalog/page.tsx",
        "      documentRobots: ownsListing(site.profile, '/catalog/') ? 'inherit' : 'noindex',",
        "      documentRobots: 'inherit',",
        suite="seo",
    ),
    Mutation(
        "в карту сайта попадают материалы без собственного текста",
        APP / "src/seo/inclusion.ts",
        "  if (!profile.requiresOwnText.includes(type)) return true",
        "  return true",
        suite="seo",
    ),
    Mutation(
        "владение страницей произведения перестаёт проверяться",
        APP / "src/seo/profiles.ts",
        "  return profile.titleOwnership.kinds.includes(kind)\n    && profile.titleOwnership.releaseStates.includes(state)",
        "  return true",
        suite="seo",
    ),
    Mutation(
        "фильтр по жанру не доходит до запроса",
        APP / "src/lib/content.ts",
        "  if (options.genreId) constraints.push({ 'title.genres': { in: [options.genreId] } })",
        "  if (false) constraints.push({ 'title.genres': { in: [options.genreId] } })",
        suite="seo",
    ),
    Mutation(
        "несуществующее значение фильтра молча игнорируется",
        APP / "src/lib/content.ts",
        "  if (options.impossible) constraints.push({ id: { exists: false } })",
        "  if (false) constraints.push({ id: { exists: false } })",
        suite="seo",
    ),
    Mutation(
        "посадочные страницы фильтров перестают быть закрытым списком",
        APP / "src/seo/profiles.ts",
        "export const ownsFacet = (profile: SeoProfile, path: string): boolean =>\n  profile.indexableFacets.includes(path)",
        "export const ownsFacet = (profile: SeoProfile, path: string): boolean =>\n  Boolean(profile.indexableFacets.length) || Boolean(path)",
        suite="seo",
    ),
    Mutation(
        "страницы серий индексируются вторым сайтом",
        APP / "src/seo/profiles.ts",
        "    content_unavailable: true,\n    // Сезоны, эпизоды и подборки закрыты.",
        "    content_unavailable: true,\n    episode: true,\n    // Сезоны, эпизоды и подборки закрыты.",
        suite="seo",
    ),
    Mutation(
        "сезон без собственной заметки попадает в карту сайта",
        APP / "src/seo/inclusion.ts",
        "  && seasonNote(doc, season) !== null",
        "  && true",
        suite="seo",
    ),
]

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


def run_suite(kind: str = "isolation") -> subprocess.CompletedProcess:
    if kind == "seo":
        # Сначала быстрые правила: часть поломок (canonical, состав карты сайта)
        # видна на чистых функциях за секунду, и гонять ради них живой стенд
        # незачем. Живой HTTP остаётся для того, что видно только на странице.
        rules = subprocess.run([str(TSX), str(SEO_RULES)], cwd=APP,
                               capture_output=True, text=True, timeout=600, check=False)
        if rules.returncode != 0:
            return rules
        return subprocess.run([sys.executable, str(SEO_SUITE)], cwd=ROOT,
                              capture_output=True, text=True, timeout=3600, check=False)
    return subprocess.run(
        [sys.executable, str(ROOT / "tests/tools/with_app_env.py"), "--scope", "anime", "--push", "--",
         str(TSX), str(SUITE)],
        cwd=ROOT, capture_output=True, text=True, timeout=1800, check=False,
    )


ARTIFACT = ROOT / "var" / "artifacts" / "mutation-isolation.json"


def main() -> int:
    results: list[dict] = []
    baseline = run_suite()
    if baseline.returncode != 0:
        print("BASELINE FAIL: прогон изоляции красный до мутаций, мутировать нечего")
        print(baseline.stdout[-4000:])
        return 1
    print("BASELINE OK: изоляция зелёная")

    seo_baseline = run_suite("seo")
    if seo_baseline.returncode != 0:
        print("BASELINE FAIL: SEO-прогон красный до мутаций")
        print(seo_baseline.stdout[-3000:])
        return 1
    print("BASELINE OK: SEO-ворота зелёные")

    failures = 0
    for mutation in [*MUTATIONS, *SEO_MUTATIONS]:
        original = mutation.path.read_text(encoding="utf-8")
        if mutation.before not in original:
            print(f"SKIP  {mutation.name}: якорь не найден в {mutation.path.relative_to(ROOT)}")
            results.append({"mutation": mutation.name, "file": str(mutation.path.relative_to(ROOT)),
                            "suite": mutation.suite, "detected": False, "reason": "якорь не найден"})
            failures += 1
            continue
        mutation.path.write_text(original.replace(mutation.before, mutation.after, 1), encoding="utf-8")
        try:
            result = run_suite(mutation.suite)
        finally:
            mutation.path.write_text(original, encoding="utf-8")
        failed_lines = [line for line in result.stdout.splitlines() if line.startswith("FAIL")]
        if result.returncode == 0:
            print(f"FAIL  {mutation.name}: поломка защиты НЕ обнаружена тестами")
            failures += 1
            results.append({"mutation": mutation.name, "file": str(mutation.path.relative_to(ROOT)),
                            "suite": mutation.suite, "detected": False,
                            "reason": "прогон остался зелёным при сломанной защите"})
        else:
            print(f"OK    {mutation.name}: обнаружена, упавших проверок {len(failed_lines)}")
            results.append({"mutation": mutation.name, "file": str(mutation.path.relative_to(ROOT)),
                            "suite": mutation.suite, "detected": True,
                            "failed_checks": len(failed_lines)})

    # Мутационный прогон — доказательство, что ворота срабатывают, а не что
    # тесты запускались. Результат каждой мутации фиксируется файлом.
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(json.dumps({
        "mutations": len(MUTATIONS) + len(SEO_MUTATIONS),
        "undetected": failures,
        "results": results,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nмутаций: {len(MUTATIONS) + len(SEO_MUTATIONS)}, не обнаружено: {failures}; "
          f"артефакт: {ARTIFACT.relative_to(ROOT)}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
