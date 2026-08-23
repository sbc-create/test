"""Разрешение ссылок site package по реестру inventory/.

Значения, которого нет в inventory, не существует: возвращается BLOCKED_ACCESS,
а не догадка об адресе.
"""
from __future__ import annotations

import functools
from typing import Any

import yaml

from factory.errors import BlockedAccess, BlockedInput
from factory.paths import PATHS


def _load(name: str) -> dict:
    path = PATHS.inventory / name
    if not path.exists():
        raise BlockedInput(
            f"Реестр {name} отсутствует.",
            field=f"inventory/{name}",
            required_input=f"Создай {path.relative_to(PATHS.root)} по образцу inventory/README.md",
        )
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise BlockedInput(f"Реестр {name} должен быть YAML-объектом.", field=f"inventory/{name}", required_input="корректный YAML")
    return data


@functools.cache
def _cached(name: str, mtime: float) -> dict:  # noqa: ARG001 — mtime участвует в ключе кеша
    return _load(name)


def load(name: str) -> dict:
    path = PATHS.inventory / name
    mtime = path.stat().st_mtime if path.exists() else 0.0
    return _cached(name, mtime)


def _find(items: list[dict], ref: str, kind: str) -> dict:
    for item in items or []:
        if item.get("ref") == ref:
            return item
    raise BlockedAccess(
        f"{kind} «{ref}» отсутствует в inventory.",
        field=f"{kind}_ref",
        required_input=f"Добавь запись с ref: {ref} в inventory/",
        blocks_stage="deploy",
    )


def target(ref: str) -> dict:
    return _find(load("targets.yaml").get("targets", []), ref, "target")


def ssh_host(ref: str) -> dict:
    host = _find(load("ssh-hosts.yaml").get("hosts", []), ref, "ssh_host")
    missing = [k for k in ("hostname", "deploy_user", "known_hosts_entry_ref") if not host.get(k)]
    if missing:
        raise BlockedAccess(
            f"У SSH-хоста «{ref}» не заполнено: {', '.join(missing)}.",
            field="ssh_host_ref",
            required_input="hostname, deploy_user, known_hosts_entry_ref (host key pinning обязателен)",
            blocks_stage="deploy",
        )
    if host.get("deploy_user") == "root":
        raise BlockedAccess(
            f"SSH-хост «{ref}» настроен на root-логин.",
            field="ssh_host_ref",
            required_input="least-privilege deploy user, не root",
            blocks_stage="deploy",
        )
    return host


def dns_zone(ref: str) -> dict:
    return _find(load("dns-zones.yaml").get("zones", []), ref, "dns_zone")


def license_entry(ref: str) -> dict:
    return _find(load("dle-licenses.yaml").get("licenses", []), ref, "dle_license")


def distribution(ref: str) -> dict:
    return _find(load("dle-distributions.yaml").get("distributions", []), ref, "dle_distribution")


def all_licenses() -> list[dict]:
    return load("dle-licenses.yaml").get("licenses", []) or []


def multi_label_suffixes() -> set[str]:
    return set(load("public-suffixes.yaml").get("multi_label_suffixes", []) or [])


def as_dict() -> dict[str, Any]:
    return {
        "targets": load("targets.yaml").get("targets", []),
        "ssh_hosts": load("ssh-hosts.yaml").get("hosts", []),
        "dns_zones": load("dns-zones.yaml").get("zones", []),
        "licenses": all_licenses(),
        "distributions": load("dle-distributions.yaml").get("distributions", []),
    }
