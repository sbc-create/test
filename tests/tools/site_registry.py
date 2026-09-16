"""Реестр реальных витрин: что действительно развёрнуто, а не что объявлено.

Собирается из шести независимых источников — профили Control API, пакеты витрин,
конфигурации nginx, юниты systemd, ссылки релизов и координация. Источники
сверяются друг с другом: витрина, объявленная в профиле, но без vhost и юнита,
называется здесь неразвёрнутой, а не «готовой».

Секреты не читаются и не показываются. Проверяется только то, что ссылка на
секрет разрешается — сам факт, без значения.
"""

from __future__ import annotations

import json
import re
import socket
import subprocess
from pathlib import Path
from typing import Any

РЕПО = Path("/srv/site-factory/repo")
NGINX = Path("/etc/nginx/sites-enabled")
КООРДИНАЦИЯ = Path("/srv/site-factory/coordination/v1")

#: Домены, названные в постановке как возможные цели. Проверяются наравне с
#: найденными: назвать домен — не то же самое, что им владеть.
ПРОВЕРИТЬ_ОТДЕЛЬНО = ("lordfilm1.online", "lorserial66.lol", "newlordfilm.lol")


def _выход(*аргументы: str) -> str:
    try:
        готово = subprocess.run(аргументы, capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return ""
    return готово.stdout


def _профили() -> dict[str, dict[str, Any]]:
    итог = {}
    каталог = РЕПО / "config" / "site-profiles"
    for путь in sorted(каталог.glob("*.json")):
        try:
            итог[путь.stem] = json.loads(путь.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            итог[путь.stem] = {}
    return итог


def _пакеты() -> dict[str, dict[str, Any]]:
    import yaml

    итог = {}
    for путь in sorted((РЕПО / "sites").glob("*/package.yaml")):
        try:
            итог[путь.parent.name] = yaml.safe_load(путь.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            итог[путь.parent.name] = {}
    return итог


def _vhosts() -> dict[str, dict[str, Any]]:
    """Домен -> чем обслуживается. Источник — то, что nginx действительно читает."""
    итог: dict[str, dict[str, Any]] = {}
    if not NGINX.is_dir():
        return итог
    for путь in sorted(NGINX.iterdir()):
        try:
            текст = путь.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        имена = set()
        for кусок in re.findall(r"^\s*server_name\s+([^;]+);", текст, re.M):
            имена.update(и for и in кусок.split() if и not in ("_", "default_server"))
        порты = sorted(set(re.findall(r"proxy_pass\s+https?://127\.0\.0\.1:(\d+)", текст)))
        ssl = bool(re.search(r"listen\s+443", текст))
        for имя in имена:
            итог[имя.lstrip("*.")] = {"vhost": путь.name, "upstreamPorts": порты, "tls": ssl}
    return итог


def _юниты() -> dict[str, dict[str, Any]]:
    итог: dict[str, dict[str, Any]] = {}
    for строка in _выход("systemctl", "list-units", "--type=service", "--all",
                         "--no-pager", "--plain", "--no-legend").splitlines():
        поля = строка.split()
        if not поля:
            continue
        имя = поля[0]
        if not re.match(r"^(lords-\d+|yummy|site-factory)", имя):
            continue
        итог[имя] = {"loaded": поля[1] if len(поля) > 1 else "",
                     "active": поля[2] if len(поля) > 2 else "",
                     "sub": поля[3] if len(поля) > 3 else ""}
    for имя in list(итог):
        текст = _выход("systemctl", "cat", имя)
        порт = re.search(r"_PORT=(\d+)", текст)
        корень = re.search(r"WorkingDirectory=(\S+)", текст)
        итог[имя]["port"] = порт.group(1) if порт else None
        итог[имя]["workdir"] = корень.group(1) if корень else None
    return итог


def _релиз(корень: Path) -> dict[str, Any]:
    текущий = корень / "current"
    прошлый = корень / "previous"
    return {
        "root": str(корень),
        "current": текущий.resolve().name if текущий.exists() else None,
        "previous": прошлый.resolve().name if прошлый.exists() else None,
        "releases": len(list((корень / "releases").glob("*"))) if (корень / "releases").is_dir() else 0,
    }


def _dns(домен: str) -> dict[str, Any]:
    try:
        адреса = sorted({к[4][0] for к in socket.getaddrinfo(домен, None)})
    except OSError as ошибка:
        return {"resolves": False, "error": type(ошибка).__name__}
    return {"resolves": True, "addresses": адреса}


def собрать() -> dict[str, Any]:
    профили, пакеты, vhosts, юниты = _профили(), _пакеты(), _vhosts(), _юниты()
    мой_адрес = (_выход("hostname", "-I") or "").split()

    витрины: dict[str, dict[str, Any]] = {}
    for сайт, профиль in профили.items():
        пакет = пакеты.get(сайт, {})
        домены = list(профиль.get("domains") or [])
        if пакет.get("domain"):
            домены.append(str(пакет["domain"]))
        домены = sorted(dict.fromkeys(домены))

        юнит = next((и for и in юниты if и.startswith(сайт)), None)
        рантайм = _релиз(Path("/srv/lords") / сайт) if (Path("/srv/lords") / сайт).is_dir() else None

        витрины[сайт] = {
            "siteId": сайт,
            "family": пакет.get("theme_ref"),
            "engineTheme": (профиль.get("theme") or {}).get("name"),
            "domains": домены,
            "canonicalHost": профиль.get("canonical_host"),
            "blueprint": пакет.get("blueprint"),
            "environment": пакет.get("environment"),
            "productionAuthorized": пакет.get("production_authorized"),
            "contentPackageRef": пакет.get("content_package_ref"),
            "contentPackageDigestDeclared": пакет.get("content_package_sha256") is not None,
            "contentSource": (пакет.get("content_source") or {}).get("kind"),
            "sshHostRef": пакет.get("ssh_host_ref"),
            "secretRefs": sorted({
                str(v) for k, v in _плоско(пакет) if k.endswith("secret_ref") and v
            }),
            "systemdUnit": юнит,
            "unitState": юниты.get(юнит) if юнит else None,
            "runtime": рантайм,
            "vhosts": {д: vhosts[д] for д in домены if д in vhosts},
            "dns": {д: _dns(д) for д in домены},
        }
        свои = [д for д in домены if д in vhosts]
        живой = bool(свои) and bool(юнит) and (юниты.get(юнит, {}).get("active") == "active")
        витрины[сайт]["deployment"] = (
            "LIVE_PUBLIC" if живой else
            "RUNNING_NO_VHOST" if юнит and юниты.get(юнит, {}).get("active") == "active" else
            "NOT_DEPLOYED"
        )

    # Домены с vhost, которым не нашлось витрины в профилях: они существуют
    # публично и обязаны быть названы, даже если Control API о них не знает.
    сироты = {}
    занятые = {д for в in витрины.values() for д in в["domains"]}
    for домен, о in vhosts.items():
        if домен in занятые or домен.startswith("www."):
            continue
        сироты[домен] = {**о, "dns": _dns(домен),
                         "note": "vhost есть, витрины в config/site-profiles нет"}

    названные = {д: {"dns": _dns(д), "vhost": vhosts.get(д),
                     "note": "назван в постановке; проверяется наравне с найденными"}
                 for д in ПРОВЕРИТЬ_ОТДЕЛЬНО}

    return {
        "generatedAt": _выход("date", "-u", "+%Y-%m-%dT%H:%M:%SZ").strip(),
        "hostAddresses": мой_адрес,
        "sites": витрины,
        "orphanDomains": сироты,
        "namedInBrief": названные,
        "sources": ["config/site-profiles/*.json", "sites/*/package.yaml",
                    "/etc/nginx/sites-enabled/*", "systemctl list-units",
                    "/srv/lords/*/current", "DNS"],
    }


def _плоско(о: Any, префикс: str = "") -> list[tuple[str, Any]]:
    из = []
    if isinstance(о, dict):
        for к, з in о.items():
            из += _плоско(з, f"{префикс}.{к}" if префикс else str(к))
    elif isinstance(о, list):
        for н, з in enumerate(о):
            из += _плоско(з, f"{префикс}[{н}]")
    else:
        из.append((префикс, о))
    return из


if __name__ == "__main__":
    print(json.dumps(собрать(), ensure_ascii=False, indent=2))
