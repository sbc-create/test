#!/usr/bin/env python3
"""Запуск CMS canary с настоящими источниками.

Слушает только loopback. Публичного домена не имеет и иметь не должен: выкладка
CMS в production этой задачей запрещена.

Ключи сеансов печатаются один раз при запуске и больше нигде не появляются.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from factory.site_engine import audit as audit_mod  # noqa: E402
from factory.site_engine import profiles as profiles_mod  # noqa: E402
from factory.site_engine.access import Principal, Role  # noqa: E402
from factory.site_engine.api.control_plane import ControlPlaneApi  # noqa: E402
from factory.site_engine.cms.server import serve  # noqa: E402
from factory.site_engine.commands import CommandLog  # noqa: E402


def collectors(repo: Path, lords_root: Path, cache_root: Path) -> dict:
    """Источники данных для CMS. Ни один не обращается к API поставщика."""

    def сайты() -> list[dict]:
        итог = []
        for p in profiles_mod.load_all(repo):
            итог.append({
                "id": p.site_id,
                "site_id": p.site_id,
                "site_type": getattr(p, "site_type", ""),
                "domains": list(getattr(p, "domains", ()) or ()),
                "modules": len(getattr(p, "modules", ()) or ()),
                "indexing": getattr(getattr(p, "indexing", None), "allowed", None),
            })
        return итог

    def профили() -> list[dict]:
        итог = []
        for p in profiles_mod.load_all(repo):
            источник = getattr(p, "normalized_content", None)
            итог.append({
                "id": p.site_id,
                "site_id": p.site_id,
                "site_type": getattr(p, "site_type", ""),
                "source_kind": getattr(источник, "kind", "") if источник else "",
                "modules": ", ".join(getattr(p, "modules", ()) or ()),
            })
        return итог

    def контент() -> list[dict]:
        """Каталог витрины. Читается из сохранённого снимка, а не у поставщика."""
        итог: list[dict] = []
        for файл in sorted(cache_root.glob("*.json"))[:1]:
            try:
                данные = json.loads(файл.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            for запись in (данные.get("items") or [])[:400]:
                итог.append({
                    "id": запись.get("external_id", ""),
                    "name": запись.get("name", ""),
                    "type": запись.get("type", ""),
                    "year": запись.get("year", ""),
                    "provenance": "cdnvideohub",
                    "updated_at": запись.get("updated_at", ""),
                    "site_id": файл.stem,
                })
        return итог

    def источники() -> list[dict]:
        return [{"id": "cdnvideohub", "kind": "provider", "adapter": "cdnvideohub",
                 "sites": "yummy, lords", "direct_access_from_cms": "нет"}]

    def выкладки() -> list[dict]:
        итог = []
        for каталог in sorted(lords_root.glob("lords-*")):
            текущий = каталог / "current"
            try:
                ревизия = текущий.resolve().name
            except OSError:
                ревизия = ""
            релизы = sorted((каталог / "releases").glob("*")) if (каталог / "releases").is_dir() else []
            итог.append({
                "id": f"{каталог.name}:{ревизия}",
                "site_id": каталог.name,
                "revision": ревизия,
                "state": "active" if ревизия else "unknown",
                "releases_kept": len(релизы),
            })
        return итог

    return {
        "sites": сайты,
        "site-profiles": профили,
        "content": контент,
        "sources": источники,
        "deployments": выкладки,
        "publications": выкладки,
        "audit-events": lambda: [],
        "jobs": lambda: [],
        "shelves": lambda: [],
        "schedules": lambda: [],
        "announcements": lambda: [],
        "ratings": lambda: [],
        "media": lambda: [],
        "seo-documents": lambda: [],
        "content-events": lambda: [],
        "commands": lambda: [],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default="/home/claude/work-night03")
    parser.add_argument("--lords-root", default="/srv/lords")
    parser.add_argument("--cache", default="/srv/site-factory/repo/var/lords/lords/catalog-cache")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8710)
    parser.add_argument("--keys-out", default="", help="куда записать ключи (файл 0600)")
    args = parser.parse_args()

    os.environ.setdefault("SITE_ENGINE_API_ENABLED", "1")
    os.environ.setdefault("APP_ENV", "staging")

    лица = {
        "owner": Principal("owner", (Role.OWNER,)),
        "admin": Principal("admin", (Role.ADMIN,)),
        "operator": Principal("operator", (Role.OPERATOR,)),
        "editor": Principal("editor", (Role.EDITOR,)),
        "seo": Principal("seo", (Role.SEO,)),
        "viewer": Principal("viewer", (Role.VIEWER,)),
    }
    api = ControlPlaneApi(
        read_api=None,
        commands=CommandLog(),
        audit=audit_mod.AuditLog(),
        principals=лица,
        collectors=collectors(Path(args.repo), Path(args.lords_root), Path(args.cache)),
        env=dict(os.environ),
    )
    сервер, canary = serve(api, host=args.host, port=args.port)
    ключи = {имя: canary.выдать_ключ(имя) for имя in лица}

    if args.keys_out:
        путь = Path(args.keys_out)
        путь.write_text(json.dumps(ключи, ensure_ascii=False, indent=2), encoding="utf-8")
        путь.chmod(0o600)
        print(f"ключи сеансов записаны в {путь} (0600)", flush=True)
    else:
        print("ключи сеансов (в разметку и журнал не попадают):", flush=True)
        for имя, ключ in ключи.items():
            print(f"  {имя}: /login?key={ключ}", flush=True)

    print(f"CMS canary слушает http://{args.host}:{args.port} — только loopback", flush=True)
    try:
        сервер.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        сервер.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
