#!/usr/bin/env python3
"""Проверка делегации и A-записей доменов Lords.

Проверка идёт двумя независимыми путями, потому что один путь ничего не
доказывает: публичный резолвер отвечает из кеша и может отставать, а
авторитетный сервер отвечает за зону, но его ещё нужно правильно найти.

* публичный путь — рекурсивный UDP-запрос к двум независимым резолверам;
* авторитетный путь — UDP-запрос с RD=0 к NS самой зоны.

DNS-over-HTTPS здесь не используется: агентский прокси отвечает на CONNECT к
`cloudflare-dns.com` и `dns.google` кодом 403, и путь через него был бы не
проверкой, а её имитацией.

Расхождение между путями не сглаживается: оно печатается как расхождение.
Собственного разбора DNS-пакета здесь ровно столько, сколько нужно для A и NS —
тянуть зависимость ради двух типов записей не за чем.
"""

from __future__ import annotations

import json
import random
import socket
import struct
import sys

DOMAINS = ("lordfilm47.space", "lordserial33.biz", "1lordserials1.online")
EXPECTED_A = "45.131.182.225"

#: Два независимых оператора. Один резолвер подтверждает только сам себя.
PUBLIC_RESOLVERS = (("cloudflare", "1.1.1.1"), ("google", "8.8.8.8"))

TYPE_A = 1
TYPE_NS = 2


# ---------------------------------------------------------------------------
# Разбор DNS-пакета
# ---------------------------------------------------------------------------
def _encode_name(name: str) -> bytes:
    out = b""
    for label in name.rstrip(".").split("."):
        out += bytes([len(label)]) + label.encode("idna" if not label.isascii() else "ascii")
    return out + b"\0"


def _skip_name(payload: bytes, offset: int) -> int:
    while True:
        length = payload[offset]
        if length == 0:
            return offset + 1
        if length & 0xC0 == 0xC0:  # указатель сжатия занимает два байта
            return offset + 2
        offset += 1 + length


def _read_name(payload: bytes, offset: int) -> str:
    labels = []
    seen = 0
    while True:
        length = payload[offset]
        if length == 0:
            break
        if length & 0xC0 == 0xC0:
            offset = struct.unpack("!H", payload[offset:offset + 2])[0] & 0x3FFF
            seen += 1
            if seen > 16:  # защита от зацикленного сжатия
                break
            continue
        labels.append(payload[offset + 1:offset + 1 + length].decode("ascii", "replace"))
        offset += 1 + length
    return ".".join(labels)


def query(server: str, name: str, rtype: int, *, recursive: bool = False,
          timeout: float = 5.0) -> list:
    """Один запрос к одному серверу. Ответ разбирается, а не угадывается.

    `recursive=False` — вопрос авторитетному серверу зоны: он обязан ответить
    сам. `recursive=True` — вопрос публичному резолверу, который вправе ответить
    из кеша; именно поэтому оба пути нужны вместе.
    """
    ident = random.SystemRandom().randrange(0, 0xFFFF)
    header = struct.pack("!HHHHHH", ident, 0x0100 if recursive else 0x0000, 1, 0, 0, 0)
    question = _encode_name(name) + struct.pack("!HH", rtype, 1)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    try:
        sock.sendto(header + question, (server, 53))
        payload, _ = sock.recvfrom(4096)
    finally:
        sock.close()
    if struct.unpack("!H", payload[:2])[0] != ident:
        raise RuntimeError("идентификатор ответа не совпал с запросом")

    _, flags, qd, an, ns, _ = struct.unpack("!HHHHHH", payload[:12])
    rcode = flags & 0x0F
    if rcode != 0:
        raise RuntimeError(f"сервер ответил кодом {rcode}")
    offset = 12
    for _ in range(qd):
        offset = _skip_name(payload, offset) + 4

    out = []
    for _ in range(an + ns):
        offset = _skip_name(payload, offset)
        rr_type, _, _, rdlength = struct.unpack("!HHIH", payload[offset:offset + 10])
        offset += 10
        if rr_type == TYPE_A and rdlength == 4:
            out.append(socket.inet_ntoa(payload[offset:offset + 4]))
        elif rr_type == TYPE_NS:
            out.append(_read_name(payload, offset))
        offset += rdlength
    return sorted(set(out))


def query_retry(server: str, name: str, rtype: int, *, recursive: bool = False,
                attempts: int = 4) -> list:
    """То же с повторами.

    UDP теряет пакеты молча, и одиночный пустой ответ неотличим от «записи нет».
    Пустой результат — повод переспросить, а не вывод: записать «A не найден»
    из-за потерянной датаграммы значило бы сообщить о несуществующей проблеме.
    """
    last = None
    for _ in range(attempts):
        try:
            found = query(server, name, rtype, recursive=recursive)
            if found:
                return found
            last = []
        except Exception as exc:
            last = exc
    if isinstance(last, Exception):
        raise last
    return []


def main() -> int:
    report = {"expected_a": EXPECTED_A, "domains": {}, "mismatches": []}

    for apex in DOMAINS:
        www = f"www.{apex}"
        entry: dict = {"apex": apex, "www": www, "public": {}, "authoritative": {}}

        for provider, address in PUBLIC_RESOLVERS:
            try:
                entry["public"][provider] = {
                    "resolver": address,
                    "ns": query_retry(address, apex, TYPE_NS, recursive=True),
                    "a_apex": query_retry(address, apex, TYPE_A, recursive=True),
                    "a_www": query_retry(address, www, TYPE_A, recursive=True),
                }
            except Exception as exc:
                entry["public"][provider] = {"error": f"{type(exc).__name__}: {exc}"}

        nameservers = []
        for provider in entry["public"].values():
            nameservers = provider.get("ns") or nameservers
        entry["nameservers"] = nameservers

        for server in nameservers:
            try:
                address = socket.getaddrinfo(server, None, socket.AF_INET)[0][4][0]
                entry["authoritative"][server] = {
                    "address": address,
                    "a_apex": query_retry(address, apex, TYPE_A),
                    "a_www": query_retry(address, www, TYPE_A),
                }
            except Exception as exc:
                entry["authoritative"][server] = {"error": f"{type(exc).__name__}: {exc}"}

        observed = set()
        answered = 0
        sources = list(entry["public"].values()) + list(entry["authoritative"].values())
        for source in sources:
            names = (source.get("a_apex") or []) + (source.get("a_www") or [])
            if names:
                answered += 1
            observed.update(names)
        entry["observed_a"] = sorted(observed)
        entry["sources_answered"] = f"{answered}/{len(sources)}"
        if observed and observed != {EXPECTED_A}:
            report["mismatches"].append({"domain": apex, "observed": sorted(observed)})
        # Молчание источника — не подтверждение. Ноль ответивших означает, что
        # проверять было нечем, и это должно быть видно, а не выглядеть успехом.
        if not observed:
            report["mismatches"].append({"domain": apex, "observed": "ни один источник не ответил"})
        report["domains"][apex] = entry

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report["mismatches"] else 0


if __name__ == "__main__":
    sys.exit(main())
