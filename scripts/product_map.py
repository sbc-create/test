#!/usr/bin/env python3
"""Соответствие продукт → пакет → тема → маршруты, собранное из фактов.

Зачем этот файл существует
--------------------------

В отчётах ходили два набора имён: продуктовые слоты (Lords, Yummy,
zona-cinema, animedia-portal, basis-video) и семейства тем (`lords_dark`,
`lords_light`, `portal_light`, `pulse`, `editorial`). Их начали считать одним и
тем же, и готовность одного набора перешла в отчёт о другом.

Соответствие оказалось иным. Проверено по манифестам и профилям:

* `portal_light`, `pulse`, `editorial` — это витрины `site-a`, `site-b` и
  `site-c` на движке `payload-next-multisite`;
* `zona-cinema` и `animedia-portal` — витрины на движке Lords со своими
  профилями и темами `zona_light` и `animedia_night`;
* `basis-video` — theme pack для DLE, витрина `pilot-local`.

То есть равенства «portal_light = zona-cinema» не существует, и 73 %, добытые
на витринах site-a/b/c, к zona-cinema отношения не имеют.

Что здесь считается, а что нет
------------------------------

Здесь только соответствие и наблюдаемые факты пакета: имя, тема, профиль,
движок, источник, домен, наличие предпросмотра. Готовность считает
`scripts/product_readiness.py` — раздельно и по своей рубрике; смешивать
«что с чем связано» и «насколько это готово» в одном файле значит получить
таблицу, в которой ошибка одного столбца незаметно правит другой.

Запуск:
    .venv/bin/python scripts/product_map.py [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT = ROOT / "artifacts" / "evidence" / "products" / "product-map.json"

#: Продукты этапа и витрины, которые их несут. Соответствие снято из пакетов
#: (`tenant.slug`, `tenant.seo_profile`, `theme_ref`), а не назначено здесь;
#: имя продукта — единственное, что берётся из задания.
PRODUCTS = {
    "zona-cinema": {"package": "zona-cinema-preview", "owner": "TEMPLATES"},
    "animedia-portal": {"package": "animedia-preview", "owner": "TEMPLATES"},
    "basis-video": {"package": "pilot-local", "owner": "TEMPLATES"},
    "yummy": {"package": None, "owner": "TEMPLATES",
              "repo": "/srv/sites/yummyani-staging/repo"},
}

#: Витрины соседнего набора. Перечислены затем, чтобы их готовность нельзя
#: было по ошибке приписать продуктам выше.
ADJACENT = {
    "portal_light": "site-a",
    "pulse": "site-b",
    "editorial": "site-c",
    "lords_dark": "lords-01",
    "lords_light": "lords-03",
}

CATALOG_CACHE = Path("/srv/site-factory/repo/var/lords/lords/catalog-cache")


def _package(name: str | None) -> dict:
    if not name:
        return {}
    path = ROOT / "sites" / name / "package.yaml"
    if not path.is_file():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _profile(name: str | None) -> dict:
    if not name:
        return {}
    path = ROOT / "blueprints" / "lords" / "profiles" / f"{name}.yaml"
    if not path.is_file():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _fixture_or_real(pkg: dict) -> str:
    """Реальные данные или синтетика. Различие существенно для приёмки."""
    kind = str((pkg.get("content_source") or {}).get("kind") or "")
    if kind == "fixture":
        return "fixture"
    if kind == "cdnvideohub":
        site = str(pkg.get("site_id") or "")
        snapshot = CATALOG_CACHE / f"{site}.json"
        return "real (снимок есть)" if snapshot.is_file() else "real (снимка нет)"
    return kind or "не объявлен"


def _domain(pkg: dict) -> str:
    domain = pkg.get("domain")
    if not domain:
        return "нет"
    text = str(domain)
    if text.endswith((".localhost", ".localhost.test", ".test", ".invalid")):
        return f"{text} — не боевой"
    return text


def describe(product: str, spec: dict) -> dict:
    pkg = _package(spec.get("package"))
    tenant = pkg.get("tenant") or {}
    profile_name = tenant.get("seo_profile")
    profile = _profile(profile_name)
    # Без пакета путь предпросмотра не существует: `preview / ""` даёт корневой
    # каталог, и опись показывала бы его как собранный предпросмотр Yummy.
    package_name = spec.get("package")
    preview = (ROOT / "artifacts" / "lords" / "preview" / str(package_name)
               if package_name else None)
    return {
        "product": product,
        "package": spec.get("package") or "—",
        "package_present": bool(pkg),
        "schema_version": pkg.get("schema_version"),
        "tenant_theme": tenant.get("theme") or pkg.get("theme_ref") or "—",
        "tenant_slug": tenant.get("slug") or "—",
        "profile": profile_name or "—",
        "profile_present": bool(profile),
        "profile_theme": (profile.get("theme") or {}).get("name") or "—",
        "blueprint": pkg.get("blueprint") or "—",
        "content_adapter": (pkg.get("content_source") or {}).get("kind") or "—",
        "data": _fixture_or_real(pkg),
        "domain": _domain(pkg),
        "environment": pkg.get("environment") or "—",
        "production_authorized": bool(pkg.get("production_authorized")),
        "render_path": ("factory.lords.render" if pkg.get("blueprint") == "lords"
                        else ("blueprints/payload-next-multisite/app"
                              if pkg.get("blueprint") == "payload-next-multisite"
                              else ("themes/" + str(pkg.get("theme_ref"))
                                    if pkg.get("theme_ref") else "—"))),
        "preview_path": (str(preview.relative_to(ROOT))
                         if preview is not None and preview.is_dir() else "не собран"),
        "owner": spec.get("owner"),
        "repo": spec.get("repo", "site-factory"),
    }


def conflicts(rows: list[dict]) -> list[str]:
    """Расхождения, которые нельзя разрешить догадкой."""
    out = []
    for row in rows:
        if not row["package_present"] and row["package"] != "—":
            out.append(f"{row['product']}: пакета {row['package']} нет в дереве")
        if row["profile"] != "—" and not row["profile_present"]:
            out.append(f"{row['product']}: профиль {row['profile']} объявлен, но отсутствует")
        # Манифест сильнее профиля; расхождение обязано быть видно, а не
        # разрешаться молча в пользу того, кто ближе к рендереру.
        if (row["profile_theme"] != "—" and row["tenant_theme"] != "—"
                and row["profile_theme"] != row["tenant_theme"]):
            out.append(f"{row['product']}: манифест объявляет тему {row['tenant_theme']}, "
                       f"профиль — {row['profile_theme']}")
    return out


def build() -> dict:
    rows = [describe(name, spec) for name, spec in PRODUCTS.items()]
    adjacent = [describe(theme, {"package": site, "owner": "TEMPLATES"})
                for theme, site in ADJACENT.items()]
    return {
        "artifact": "TEMPLATE_PRODUCT_MAP",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "products": rows,
        "adjacent": adjacent,
        "conflicts": conflicts(rows + adjacent),
        "note": ("Продукты и соседние витрины перечислены раздельно намеренно: "
                 "portal_light, pulse и editorial — это site-a/b/c, а не "
                 "zona-cinema, animedia-portal и basis-video, и готовность "
                 "одних не является готовностью других."),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    columns = ("product", "package", "tenant_theme", "profile", "blueprint",
               "content_adapter", "data", "domain", "preview_path")
    widths = {c: max(len(c), *(len(str(r[c])) for r in report["products"])) for c in columns}
    print("ПРОДУКТЫ ЭТАПА")
    print("  ".join(c.ljust(widths[c]) for c in columns))
    print("-" * (sum(widths.values()) + 2 * len(columns)))
    for row in report["products"]:
        print("  ".join(str(row[c]).ljust(widths[c]) for c in columns))

    print("\nСОСЕДНИЕ ВИТРИНЫ (их готовность к продуктам выше не относится)")
    for row in report["adjacent"]:
        print(f"  {row['product']:14} → {row['package']:12} "
              f"движок {row['blueprint']:24} данные {row['data']}")

    if report["conflicts"]:
        print("\nРАСХОЖДЕНИЯ, требующие решения:")
        for line in report["conflicts"]:
            print(f"  • {line}")
    else:
        print("\nРасхождений манифестов и профилей нет.")
    print(f"\n{OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
