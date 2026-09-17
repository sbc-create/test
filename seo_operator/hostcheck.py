"""
Проверка целевого хоста (BLOCKED_WRONG_HOST).

Аудит инфраструктуры, выполненный не на том хосте, хуже отсутствия аудита:
он выглядит завершённым. Поэтому проверка стоит ПЕРЕД любым выводом об
инвентаре, а её провал запрещает объявлять аудит выполненным.

Все проверки read-only и не требуют привилегий.
"""
from __future__ import annotations

import os
import re
import socket
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from .statuses import Status

# Диапазоны, которые заведомо не являются публичным адресом production-хоста.
DOC_AND_PRIVATE = (
    re.compile(r"^127\."), re.compile(r"^10\."), re.compile(r"^192\.168\."),
    re.compile(r"^172\.(1[6-9]|2\d|3[01])\."), re.compile(r"^169\.254\."),
    re.compile(r"^192\.0\.2\."),        # TEST-NET-1, RFC 5737
    re.compile(r"^198\.51\.100\."),     # TEST-NET-2
    re.compile(r"^203\.0\.113\."),      # TEST-NET-3
    re.compile(r"^0\."),
)


@dataclass
class HostExpectation:
    hostname: str
    ipv4: str
    repo_path: str


@dataclass
class HostCheck:
    expected: HostExpectation
    actual_hostname: str
    actual_ipv4: list[str]
    repo_path_exists: bool
    evidence: dict[str, Any] = field(default_factory=dict)
    mismatches: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.mismatches

    @property
    def status(self) -> str:
        return "pass" if self.passed else "BLOCKED_WRONG_HOST"

    def render(self) -> str:
        lines = [f"HOST_VERIFIED={self.status}", ""]
        lines.append("| Проверка | Ожидается | Фактически | Итог |")
        lines.append("|---|---|---|---|")
        lines.append(f"| hostname | {self.expected.hostname} | {self.actual_hostname} | "
                     f"{'ok' if self.actual_hostname == self.expected.hostname else 'MISMATCH'} |")
        actual_ips = ", ".join(self.actual_ipv4) or "нет"
        lines.append(f"| IPv4 | {self.expected.ipv4} | {actual_ips} | "
                     f"{'ok' if self.expected.ipv4 in self.actual_ipv4 else 'MISMATCH'} |")
        lines.append(f"| {self.expected.repo_path} | существует | "
                     f"{'существует' if self.repo_path_exists else 'отсутствует'} | "
                     f"{'ok' if self.repo_path_exists else 'MISMATCH'} |")
        if self.mismatches:
            lines.append("")
            lines.append("Расхождения:")
            for m in self.mismatches:
                lines.append(f"- {m}")
        return "\n".join(lines)


def read_hostname() -> str:
    for path in ("/proc/sys/kernel/hostname", "/etc/hostname"):
        try:
            value = Path(path).read_text(encoding="utf-8").strip()
            if value:
                return value
        except OSError:
            continue
    try:
        return socket.gethostname()
    except OSError:
        return ""


def read_ipv4_addresses() -> list[str]:
    """
    Адреса читаются из /proc — без вызова внешних утилит, которые могут быть
    недоступны в урезанном окружении.
    """
    found: set[str] = set()
    try:
        text = Path("/proc/net/fib_trie").read_text(encoding="utf-8", errors="ignore")
        found.update(re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", text))
    except OSError:
        pass
    if not found:
        try:
            found.add(socket.gethostbyname(socket.gethostname()))
        except (OSError, socket.gaierror):
            pass
    return sorted(a for a in found if not a.endswith(".255") and a != "0.0.0.0")


def looks_like_ephemeral(addresses: Sequence[str]) -> bool:
    """True, если среди адресов нет ни одного публичного."""
    return not any(not any(p.match(a) for p in DOC_AND_PRIVATE) for a in addresses)


def check(expected: HostExpectation) -> HostCheck:
    hostname = read_hostname()
    addresses = read_ipv4_addresses()
    repo_exists = Path(expected.repo_path).is_dir()

    mismatches: list[str] = []
    if hostname != expected.hostname:
        mismatches.append(
            f"hostname '{hostname}' не совпадает с ожидаемым '{expected.hostname}'")
    if expected.ipv4 not in addresses:
        mismatches.append(
            f"адрес {expected.ipv4} не найден среди интерфейсов: {addresses or 'нет адресов'}")
    if not repo_exists:
        mismatches.append(f"каталог {expected.repo_path} отсутствует")

    evidence: dict[str, Any] = {
        "hostname_source": "/proc/sys/kernel/hostname",
        "ipv4_source": "/proc/net/fib_trie",
        "addresses": addresses,
        "ephemeral_addressing": looks_like_ephemeral(addresses),
        "container_markers": _container_markers(),
    }
    return HostCheck(expected=expected, actual_hostname=hostname, actual_ipv4=addresses,
                     repo_path_exists=repo_exists, evidence=evidence, mismatches=mismatches)


def _container_markers() -> list[str]:
    """Признаки эфемерного окружения — помогают объяснить, ГДЕ выполнялась сессия."""
    markers = []
    if Path("/.dockerenv").exists():
        markers.append("/.dockerenv")
    try:
        hosts = Path("/etc/hosts").read_text(encoding="utf-8", errors="ignore")
        if "runsc" in hosts:
            markers.append("gVisor (runsc) в /etc/hosts")
    except OSError:
        pass
    if os.environ.get("CLAUDE_PROJECT_DIR"):
        markers.append("CLAUDE_PROJECT_DIR задан")
    return markers


# Ожидание для этого проекта. Значения из ТЗ владельца, не из окружения:
# хост, который сам себя объявляет целевым, проверкой не является.
EXPECTED_HOST = HostExpectation(
    hostname="claude-control-01",
    ipv4="45.131.182.225",
    repo_path="/srv/site-factory/repo",
)
