#!/usr/bin/env python3
"""Exact-domain реестр рантайма витрин: домен → витрина → юнит → порт → релиз.

## Зачем

Имена юнитов до сих пор лежали в трёх местах и в каждом по-своему: в таблице
внутри `lords-nova-canary.py`, в жёстком списке внутри сторожа когерентности и
в головах. Асимметрия реальна и неочевидна — `lords-nova-01.service` против
`nova-lords-02.service` и `nova-lords-03.service`, — поэтому угадывание имени
здесь не мелкая ошибка, а перезапуск не той витрины.

Реестр собирается из двух независимых источников и падает, если они расходятся:

* `config/site-profiles/<site>.json` — точный домен, канонический хост и
  ожидаемая индексируемость. Это Core-реестр сайта;
* `/etc/systemd/system/*.service` — какой юнит какой порт слушает и какой файл
  исполняет. Это единственная правда о запуске.

Ничего не достраивается. Витрина, которой нет в systemd, в реестр не попадает.
Витрина, у которой нет профиля, попадает со `scope: out-of-registry` и честно
помечается: её можно не трогать, но нельзя делать вид, что её не существует —
она исполняет тот же файл.

## Что такое release_link

Путь `sites/<site>/current`. Это символическая ссылка на неизменяемый каталог
релиза, назначенный ИМЕННО этой витрине. Пока её нет, витрина привязана к
общему изменяемому файлу, и любая выкладка соседа меняет её байты.

Запуск:

    nova-runtime-registry.py --emit config/lords-runtime-registry.json
    nova-runtime-registry.py --check      # расхождение источников → код 2
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

UNITS_DIR = pathlib.Path("/etc/systemd/system")
FRONT = pathlib.Path("/srv/lords/.frontend")
SHARED_RUNTIME_NAME = "lords-frontend.py"

OK = 0
MISMATCH = 2

#: Семейство витрины по префиксу идентификатора. Профиль отдаёт манифест, а
#: семейство нужно раньше манифеста — чтобы понять, чей это домен.
FAMILY_BY_PREFIX = {"lords": "lords", "animedia": "animedia", "zona": "zona"}


def _repo_root() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parents[2]


def scan_units(units_dir: pathlib.Path = UNITS_DIR) -> dict[str, dict]:
    """Юниты, исполняющие общий файл рантайма: порт → юнит и путь.

    Разбирается ExecStart, а не имя файла: именно ExecStart решает, что
    запустится. Строка вида
    `ExecStart=/usr/bin/python3 /srv/lords/.frontend/lords-frontend.py --port 9111`.
    """
    found: dict[str, dict] = {}
    if not units_dir.is_dir():
        return found
    for unit in sorted(units_dir.glob("*.service")):
        try:
            text = unit.read_text(errors="replace")
        except OSError:
            continue
        match = re.search(r"^ExecStart=.*?(\S*%s)\s+--port\s+(\d+)" % re.escape(SHARED_RUNTIME_NAME),
                          text, re.MULTILINE)
        if not match:
            continue
        exec_path, port = match.group(1), match.group(2)
        description = ""
        desc = re.search(r"^Description=(.*)$", text, re.MULTILINE)
        if desc:
            description = desc.group(1).strip()
        manifest_env = re.search(r"^Environment=LORDS_TEMPLATE_MANIFEST=(\S+)", text, re.MULTILINE)
        found[port] = {
            "unit": unit.name,
            "unit_path": str(unit),
            "exec_path": exec_path,
            "description": description,
            "manifest_path": manifest_env.group(1) if manifest_env else str(
                FRONT / "template-manifest.json"
            ),
        }
    return found


def site_profiles(repo: pathlib.Path | None = None) -> dict[str, dict]:
    """Core-реестр сайта: точный домен, канонический хост, индексируемость."""
    repo = repo or _repo_root()
    profiles: dict[str, dict] = {}
    directory = repo / "config" / "site-profiles"
    if not directory.is_dir():
        return profiles
    for path in sorted(directory.glob("*.json")):
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        domains = data.get("domains") or []
        if not domains:
            continue
        seo = data.get("seo") or {}
        profiles[path.stem] = {
            "site_id": data.get("site_id", path.stem),
            "domains": domains,
            "exact_domain": domains[0],
            "canonical_host": seo.get("canonical_host", domains[0]),
            "indexing_enabled": bool(seo.get("indexing_enabled", False)),
        }
    return profiles


def _site_id_from_unit(entry: dict) -> str:
    """Идентификатор витрины из описания юнита, затем из его имени.

    Описание юнита пишется установщиком и содержит идентификатор явно
    («Lords nova frontend: lords-02 (lordserial33.biz)»). Имя юнита —
    запасной путь, потому что порядок слов в нём непостоянен.
    """
    match = re.search(r"\b((?:lords|animedia|zona)-\d{2})\b", entry.get("description", ""))
    if match:
        return match.group(1)
    match = re.search(r"\b((?:lords|animedia|zona)-\d{2})\b", entry["unit"])
    if match:
        return match.group(1)
    match = re.search(r"\b(\d{2})\b", entry["unit"])
    family = next((f for f in FAMILY_BY_PREFIX if f in entry["unit"]), "")
    return f"{family}-{match.group(1)}" if (match and family) else entry["unit"]


def build(units_dir: pathlib.Path = UNITS_DIR, repo: pathlib.Path | None = None,
          front: pathlib.Path = FRONT) -> dict:
    units = scan_units(units_dir)
    profiles = site_profiles(repo)
    by_site = {p["site_id"]: p for p in profiles.values()}

    sites = {}
    conflicts = []
    for port, entry in sorted(units.items()):
        site_id = _site_id_from_unit(entry)
        profile = by_site.get(site_id)
        family = next((f for pfx, f in FAMILY_BY_PREFIX.items() if site_id.startswith(pfx)), "")

        if profile:
            # Домен из юнита сверяется с доменом профиля: расходятся — конфликт.
            in_description = re.search(r"\(([^)]+)\)", entry.get("description", ""))
            declared = in_description.group(1).strip() if in_description else ""
            if declared and declared != profile["exact_domain"]:
                conflicts.append(
                    f"{site_id}: юнит называет домен {declared}, профиль — {profile['exact_domain']}"
                )

        sites[site_id] = {
            "site_id": site_id,
            "family": family,
            "port": int(port),
            "unit": entry["unit"],
            "unit_path": entry["unit_path"],
            "exec_path": entry["exec_path"],
            "manifest_path": entry["manifest_path"],
            "exact_domain": profile["exact_domain"] if profile else None,
            "canonical_host": profile["canonical_host"] if profile else None,
            "indexing_enabled": profile["indexing_enabled"] if profile else None,
            "scope": "exact-domain-registry" if profile else "out-of-registry",
            "release_link": str(front / "sites" / site_id / "current"),
        }

    return {
        "schema_version": 1,
        "note": (
            "Производный файл. Источники — config/site-profiles/*.json и юниты systemd. "
            "Правится источник, а не этот файл."
        ),
        "shared_runtime_path": str(front / SHARED_RUNTIME_NAME),
        "sites": sites,
        "conflicts": conflicts,
        "in_registry": sorted(s for s, v in sites.items() if v["scope"] == "exact-domain-registry"),
        "out_of_registry": sorted(s for s, v in sites.items() if v["scope"] == "out-of-registry"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--emit", help="записать реестр в файл")
    parser.add_argument("--check", action="store_true", help="только проверить согласованность")
    parser.add_argument("--units-dir", default=str(UNITS_DIR))
    args = parser.parse_args()

    registry = build(pathlib.Path(args.units_dir))
    text = json.dumps(registry, ensure_ascii=False, indent=2)
    if args.emit:
        pathlib.Path(args.emit).write_text(text + "\n", encoding="utf-8")
        print(f"реестр записан: {args.emit}")
    if not args.emit or args.check:
        print(text)
    if registry["conflicts"]:
        for line in registry["conflicts"]:
            print("КОНФЛИКТ:", line, file=sys.stderr)
        return MISMATCH
    return OK


if __name__ == "__main__":
    raise SystemExit(main())
