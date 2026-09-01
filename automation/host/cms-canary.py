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
import pathlib
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

    def рейтинги() -> list[dict]:
        """Оценки из сохранённого снимка каталога.

        Источник настоящий и лежит рядом: поля ``imdb_rating`` и
        ``kinopoisk_rating`` есть у записей каталожного кэша. Ничего не
        вычисляется и не усредняется — показывается то, что пришло от
        поставщика, вместе с признаком, что оценки нет.

        Записи без обеих оценок пропускаются: строка «нет оценки» в списке
        оценок не несёт сведений, а список раздувает.
        """
        итог: list[dict] = []
        for файл in sorted(cache_root.glob("*.json"))[:1]:
            try:
                данные = json.loads(файл.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            for запись in (данные.get("items") or []):
                imdb = запись.get("imdb_rating")
                kp = запись.get("kinopoisk_rating")
                if imdb in (None, "", 0) and kp in (None, "", 0):
                    continue
                итог.append({
                    "id": запись.get("external_id", ""),
                    "name": запись.get("name", ""),
                    "imdb": imdb if imdb not in (None, "") else "—",
                    "kinopoisk": kp if kp not in (None, "") else "—",
                    "year": запись.get("year", ""),
                    "provenance": "cdnvideohub",
                    "site_id": файл.stem,
                })
                if len(итог) >= 400:
                    break
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
            корень_релизов = каталог / "releases"
            релизы = sorted(корень_релизов.glob("*")) if корень_релизов.is_dir() else []
            итог.append({
                "id": f"{каталог.name}:{ревизия}",
                "site_id": каталог.name,
                "revision": ревизия,
                "state": "active" if ревизия else "unknown",
                "releases_kept": len(релизы),
            })
        return итог

    def задания() -> list[dict]:
        """Периодические работы. Читается у systemd, а не выдумывается."""
        import subprocess

        итог: list[dict] = []
        try:
            вывод = subprocess.run(
                ["systemctl", "list-timers", "--all", "--no-pager", "--no-legend"],
                capture_output=True, text=True, timeout=20,
            ).stdout
        except Exception:  # noqa: BLE001
            return итог
        for строка in вывод.splitlines():
            части = строка.split()
            if len(части) < 2:
                continue
            юнит = next((c for c in части if c.endswith(".timer")), "")
            служба = next((c for c in части if c.endswith(".service")), "")
            if not юнит:
                continue
            итог.append({
                "id": юнит,
                "name": юнит,
                "service": служба,
                "raw": " ".join(части[:6]),
                "site_id": "yummy" if юнит.startswith("yummy") else
                           ("lords" if юнит.startswith("lords") else ""),
            })
        return итог

    def события() -> list[dict]:
        """События выхода серий. Отметка `observedAt` — когда МЫ увидели."""
        путь = pathlib.Path("/srv/sites/yummyani-staging/runtime/episode-state/events.jsonl")
        итог: list[dict] = []
        try:
            строки = путь.read_text(errors="replace").strip().split("\n")[-200:]
        except OSError:
            return итог
        for строка in строки:
            try:
                e = json.loads(строка)
            except ValueError:
                continue
            итог.append({
                "id": f"{e.get('titleId', '')}:{e.get('observedAt', '')}",
                "kind": e.get("kind", ""),
                "title": e.get("name", ""),
                "from": e.get("from"),
                "to": e.get("to"),
                # Время провайдера и время наблюдения хранятся раздельно:
                # провайдер не сообщает, когда изменение произошло.
                "observedAt": e.get("observedAt", ""),
                "providerTimestamp": e.get("providerTimestamp", ""),
                "site_id": "yummy",
            })
        return list(reversed(итог))

    def медиа() -> list[dict]:
        """Состояние кэша изображений. Размеры, а не содержимое."""
        каталог = pathlib.Path("/var/cache/nginx/yummy-posters")
        if not каталог.is_dir():
            return []
        всего = 0
        байт = 0
        try:
            for файл in каталог.rglob("*"):
                if файл.is_file():
                    всего += 1
                    байт += файл.stat().st_size
        except OSError:
            pass
        return [{
            "id": "yummy-posters",
            "kind": "poster-cache",
            "objects": всего,
            "bytes": байт,
            "limit_bytes": 700 * 1024 * 1024,
            "site_id": "yummy",
        }]

    def полки() -> list[dict]:
        """Полки берутся из профилей, а не из разметки витрины."""
        итог = []
        for p in profiles_mod.load_all(repo):
            слои = ((getattr(p, "cache_policy", None) or {}) or {})
            if hasattr(слои, "get"):
                слои = слои.get("layers") or {}
            for имя in sorted(слои):
                итог.append({
                    "id": f"{p.site_id}:{имя}",
                    "site_id": p.site_id,
                    "title": имя,
                    "items": ", ".join((слои[имя] or {}).get("tags", []) or []),
                })
        return итог

    return {
        "sites": сайты,
        "site-profiles": профили,
        "content": контент,
        "sources": источники,
        "deployments": выкладки,
        "publications": выкладки,
        "jobs": задания,
        "content-events": события,
        "media": медиа,
        "shelves": полки,
        # Ниже — источники, которых в этом контуре нет. Отвечают 501, а не
        # пустым списком: пустой список неотличим от «данных нет» и скрывает
        # отсутствие источника.
        "ratings": рейтинги,
        # Ниже — источники, которых в этом контуре нет. Отвечают 501, а не
        # пустым списком: пустой список неотличим от «данных нет» и скрывает
        # отсутствие источника.
        #
        # `schedules` намеренно оставлен отключённым, хотя файл календаря на
        # машине есть: в `config/editorial-calendar.json` все записи помечены
        # `"synthetic": true`, и сам файл говорит «реальных записей нет».
        # Подключить его значило бы вывести в CMS выдуманные даты.
        #
        # `seo-documents`: robots.txt и sitemap.xml отдаёт `serve.py` витрины, в
        # каталоге релиза их нет. Читать их из CMS означало бы ходить по сети к
        # боевым доменам на каждую отрисовку страницы — цена выше пользы.
        "audit-events": lambda: [],
        "schedules": lambda: [],
        "announcements": lambda: [],
        "seo-documents": lambda: [],
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
    # Журналы связываются после создания API: они принадлежат ему самому, а не
    # внешнему источнику. Пустой список вместо настоящего журнала выглядел бы
    # как «записей нет», хотя записи есть.
    api.collectors["audit-events"] = lambda: [
        {
            "id": e.event_id,
            "actor": e.actor,
            "action": e.action,
            "subject": e.subject,
            "at": e.at.isoformat(),
            "correlation_id": e.correlation_id or "",
            "digest": e.digest(),
            "site_id": (e.site_ids[0] if e.site_ids else ""),
        }
        for e in api.audit
    ]
    api.collectors["commands"] = lambda: [
        {**c, "id": c["command_id"]} for c in api.commands.as_list()
    ]

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
