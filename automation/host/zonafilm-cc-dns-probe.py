#!/usr/bin/env python3
"""Делегация и записи домена: публичные резолверы плюс авторитетный путь.

Расширение `tests/tools/dns_check.py` на то, чего там нет и что нужно для
приёмки нового домена: AAAA, CNAME, SOA, явный разбор кода ответа (NXDOMAIN и
NODATA — разные факты) и трассировка от TLD-серверов, а не только опрос кеша.

Почему два пути. Публичный резолвер отвечает из кеша: он может отставать от
зоны на TTL и не доказывает, что запись существует сейчас. Авторитетный сервер
отвечает за зону, но его сначала надо найти — и найти независимо от того же
кеша, иначе проверка замыкается сама на себя. Поэтому NS берутся у TLD-серверов
`.cc`, а не у резолвера.

Расхождение между путями не сглаживается: оно печатается как расхождение.
DNS-over-HTTPS не используется — агентский прокси отвечает на CONNECT к
`cloudflare-dns.com` и `dns.google` кодом 403, и путь через него был бы не
проверкой, а её имитацией.

Ничего не меняет. Только читает.
"""

from __future__ import annotations

import argparse
import json
import random
import socket
import struct
import sys
import time

TYPE_A = 1
TYPE_NS = 2
TYPE_CNAME = 5
TYPE_SOA = 6
TYPE_AAAA = 28
TYPE_NAME = {TYPE_A: "A", TYPE_NS: "NS", TYPE_CNAME: "CNAME", TYPE_SOA: "SOA", TYPE_AAAA: "AAAA"}

RCODE_NAME = {0: "NOERROR", 1: "FORMERR", 2: "SERVFAIL", 3: "NXDOMAIN", 4: "NOTIMP", 5: "REFUSED"}

#: Независимые операторы. Один резолвер подтверждает только сам себя.
PUBLIC_RESOLVERS = (
    ("cloudflare", "1.1.1.1"),
    ("google", "8.8.8.8"),
    ("quad9", "9.9.9.9"),
    ("opendns", "208.67.222.222"),
)

#: Корневые серверы: точка входа трассировки, не зависящая от кеша резолверов.
ROOT_SERVERS = ("198.41.0.4", "199.9.14.201", "192.33.4.12")


# ---------------------------------------------------------------------------
# Разбор пакета
# ---------------------------------------------------------------------------
def _encode_name(name: str) -> bytes:
    out = b""
    for label in name.rstrip(".").split("."):
        if not label:
            continue
        out += bytes([len(label)]) + label.encode("ascii" if label.isascii() else "idna")
    return out + b"\0"


def _read_name(payload: bytes, offset: int) -> tuple[str, int]:
    labels: list[str] = []
    jumped = False
    end = offset
    hops = 0
    while True:
        length = payload[offset]
        if length == 0:
            offset += 1
            if not jumped:
                end = offset
            break
        if length & 0xC0 == 0xC0:
            pointer = struct.unpack("!H", payload[offset:offset + 2])[0] & 0x3FFF
            if not jumped:
                end = offset + 2
            offset = pointer
            jumped = True
            hops += 1
            if hops > 16:  # защита от зацикленного сжатия
                break
            continue
        labels.append(payload[offset + 1:offset + 1 + length].decode("ascii", "replace"))
        offset += 1 + length
    return ".".join(labels), end


class DnsError(RuntimeError):
    pass


def query(server: str, name: str, rtype: int, *, recursive: bool, timeout: float = 4.0) -> dict:
    """Один запрос к одному серверу. Ответ разбирается целиком, а не угадывается."""
    ident = random.SystemRandom().randrange(0, 0xFFFF)
    header = struct.pack("!HHHHHH", ident, 0x0100 if recursive else 0x0000, 1, 0, 0, 0)
    packet = header + _encode_name(name) + struct.pack("!HH", rtype, 1)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    started = time.monotonic()
    try:
        sock.sendto(packet, (server, 53))
        payload, _ = sock.recvfrom(4096)
    finally:
        sock.close()
    elapsed_ms = round((time.monotonic() - started) * 1000, 1)

    if struct.unpack("!H", payload[:2])[0] != ident:
        raise DnsError("идентификатор ответа не совпал с запросом")

    _, flags, qd, an, ns, ar = struct.unpack("!HHHHHH", payload[:12])
    rcode = flags & 0x0F
    authoritative = bool(flags & 0x0400)

    offset = 12
    for _ in range(qd):
        _, offset = _read_name(payload, offset)
        offset += 4

    answers: list[dict] = []
    authority: list[dict] = []
    additional: list[dict] = []
    for index in range(an + ns + ar):
        owner, offset = _read_name(payload, offset)
        rr_type, _, ttl, rdlength = struct.unpack("!HHIH", payload[offset:offset + 10])
        offset += 10
        value = None
        if rr_type == TYPE_A and rdlength == 4:
            value = socket.inet_ntoa(payload[offset:offset + 4])
        elif rr_type == TYPE_AAAA and rdlength == 16:
            value = socket.inet_ntop(socket.AF_INET6, payload[offset:offset + 16])
        elif rr_type in (TYPE_NS, TYPE_CNAME):
            value, _ = _read_name(payload, offset)
        elif rr_type == TYPE_SOA:
            mname, next_offset = _read_name(payload, offset)
            rname, _ = _read_name(payload, next_offset)
            value = f"{mname} {rname}"
        record = {"owner": owner, "type": TYPE_NAME.get(rr_type, str(rr_type)),
                  "ttl": ttl, "value": value}
        bucket = answers if index < an else (authority if index < an + ns else additional)
        bucket.append(record)
        offset += rdlength

    return {
        "server": server,
        "rcode": RCODE_NAME.get(rcode, str(rcode)),
        "authoritative": authoritative,
        "elapsed_ms": elapsed_ms,
        "answers": answers,
        "authority": authority,
        "additional": additional,
    }


def query_retry(server: str, name: str, rtype: int, *, recursive: bool, attempts: int = 3) -> dict:
    """UDP теряет датаграммы молча. Одиночный таймаут — не вывод о записи."""
    last: Exception | None = None
    for _ in range(attempts):
        try:
            return query(server, name, rtype, recursive=recursive)
        except (OSError, DnsError) as exc:
            last = exc
    return {"server": server, "error": f"{type(last).__name__}: {last}"}


def _values(result: dict, rtype: str) -> list[str]:
    if "error" in result:
        return []
    return sorted({r["value"] for r in result.get("answers", []) if r["type"] == rtype and r["value"]})


# ---------------------------------------------------------------------------
# Авторитетный путь: от корня к зоне, мимо кеша
# ---------------------------------------------------------------------------
def delegation_trace(apex: str) -> dict:
    """NS зоны, полученные у серверов TLD, а не у публичного резолвера."""
    tld = apex.rstrip(".").split(".")[-1]
    trace: dict = {"tld": tld, "steps": []}

    tld_servers: list[str] = []
    for root in ROOT_SERVERS:
        result = query_retry(root, tld, TYPE_NS, recursive=False)
        trace["steps"].append({"asked": root, "for": tld, "result": result})
        names = sorted({r["value"] for r in result.get("authority", []) + result.get("answers", [])
                        if r["type"] == "NS" and r["value"]})
        glue = {r["owner"].lower(): r["value"] for r in result.get("additional", [])
                if r["type"] == "A"}
        for name in names:
            address = glue.get(name.lower())
            if address:
                tld_servers.append(address)
        if tld_servers:
            break
    trace["tld_servers"] = sorted(set(tld_servers))[:4]

    zone_ns: list[str] = []
    for server in trace["tld_servers"]:
        result = query_retry(server, apex, TYPE_NS, recursive=False)
        trace["steps"].append({"asked": server, "for": apex, "result": result})
        names = sorted({r["value"] for r in result.get("authority", []) + result.get("answers", [])
                        if r["type"] == "NS" and r["value"]})
        if names:
            zone_ns = names
            break
    trace["zone_nameservers"] = sorted(set(n.lower().rstrip(".") for n in zone_ns))
    return trace


def probe(apex: str, expected_ns: tuple[str, ...], expected_a: str | None) -> dict:
    www = f"www.{apex}"
    report: dict = {
        "apex": apex,
        "www": www,
        "expected_ns": sorted(expected_ns),
        "expected_a": expected_a,
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "public": {},
        "authoritative": {},
        "findings": [],
    }

    for provider, address in PUBLIC_RESOLVERS:
        entry: dict = {"resolver": address}
        for label, name, rtype in (
            ("ns", apex, TYPE_NS),
            ("soa", apex, TYPE_SOA),
            ("a_apex", apex, TYPE_A),
            ("aaaa_apex", apex, TYPE_AAAA),
            ("a_www", www, TYPE_A),
            ("aaaa_www", www, TYPE_AAAA),
            ("cname_www", www, TYPE_CNAME),
        ):
            entry[label] = query_retry(address, name, rtype, recursive=True)
        report["public"][provider] = entry

    report["delegation_trace"] = delegation_trace(apex)
    zone_ns = report["delegation_trace"]["zone_nameservers"]

    for server in zone_ns:
        try:
            address = socket.getaddrinfo(server, None, socket.AF_INET)[0][4][0]
        except OSError as exc:
            report["authoritative"][server] = {"error": f"{type(exc).__name__}: {exc}"}
            continue
        entry = {"address": address}
        for label, name, rtype in (
            ("a_apex", apex, TYPE_A),
            ("aaaa_apex", apex, TYPE_AAAA),
            ("a_www", www, TYPE_A),
            ("aaaa_www", www, TYPE_AAAA),
            ("cname_www", www, TYPE_CNAME),
            ("soa", apex, TYPE_SOA),
        ):
            entry[label] = query_retry(address, name, rtype, recursive=False)
        report["authoritative"][server] = entry

    # --- выводы ------------------------------------------------------------
    if sorted(zone_ns) != sorted(n.lower() for n in expected_ns):
        report["findings"].append({
            "id": "NS_DELEGATION",
            "status": "MISMATCH" if zone_ns else "UNRESOLVED",
            "observed": zone_ns,
            "expected": sorted(n.lower() for n in expected_ns),
        })
    else:
        report["findings"].append({"id": "NS_DELEGATION", "status": "MATCH", "observed": zone_ns})

    observed_a = sorted({v for entry in report["public"].values() for v in _values(entry["a_apex"], "A")}
                        | {v for entry in report["authoritative"].values()
                           if "error" not in entry for v in _values(entry["a_apex"], "A")})
    observed_a_www = sorted({v for entry in report["public"].values() for v in _values(entry["a_www"], "A")}
                            | {v for entry in report["authoritative"].values()
                               if "error" not in entry for v in _values(entry["a_www"], "A")})
    report["observed_a_apex"] = observed_a
    report["observed_a_www"] = observed_a_www

    for label, observed in (("APEX_A", observed_a), ("WWW_A", observed_a_www)):
        if not observed:
            report["findings"].append({"id": label, "status": "ABSENT"})
        elif expected_a and observed != [expected_a]:
            report["findings"].append({"id": label, "status": "MISMATCH",
                                       "observed": observed, "expected": [expected_a]})
        else:
            report["findings"].append({"id": label, "status": "PRESENT", "observed": observed})

    # NODATA и NXDOMAIN — разные факты, и слипаться им нельзя.
    for provider, entry in report["public"].items():
        rcode = entry["a_apex"].get("rcode")
        if rcode and rcode != "NOERROR":
            report["findings"].append({"id": "APEX_RCODE", "status": rcode, "resolver": provider})

    report["verdict"] = (
        "DELEGATED_NO_RECORDS"
        if any(f["id"] == "NS_DELEGATION" and f["status"] == "MATCH" for f in report["findings"])
        and not observed_a and not observed_a_www
        else "RESOLVES"
        if observed_a
        else "BLOCKED_DNS_DELEGATION"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--domain", required=True)
    parser.add_argument("--expect-ns", action="append", default=[])
    parser.add_argument("--expect-a", default=None)
    args = parser.parse_args()

    report = probe(args.domain, tuple(args.expect_ns), args.expect_a)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["verdict"] in ("RESOLVES", "DELEGATED_NO_RECORDS") else 1


if __name__ == "__main__":
    raise SystemExit(main())
