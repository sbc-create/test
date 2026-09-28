#!/usr/bin/env python3
"""Состояние доменов: регистрация, зона, записи, TTL, TLS. Только чтение.

Что это и почему без панели провайдера
--------------------------------------

Доступа к панели Zomro в этой полосе не настроено: `inventory/dns-zones.yaml`
пуст, в инвентаре инфраструктуры `dns_zones: []`, ссылки на токен провайдера
нет, а секретные пути закрыты сторожем. Подбирать учётные данные или угадывать
адрес панели полоса не станет.

Всё остальное измеримо снаружи и измеряется здесь: регистрация — по RDAP,
делегирование и записи — прямыми запросами к нескольким независимым
резолверам, срок жизни — из самих ответов, сертификат — из рукопожатия TLS.
Это публичные сведения; ни одного секрета инструменту не нужно.

Запросы собираются вручную, без сторонней библиотеки: `dig` в профиле нет,
dnspython не установлен, а тянуть зависимость ради полутора сотен строк
разбора — цена выше пользы.

Чего инструмент не делает
-------------------------

Ничего не меняет. Ни одной записи, ни одной зоны, ни одного обращения к
панели. Отсутствие записи он называет отсутствием, а не отказом: домен,
ожидающий разрешения имени, находится в состоянии `PENDING_DNS`, и это
ожидание, а не провал.

Запуск:
    .venv/bin/python scripts/dns_diagnostics.py
    .venv/bin/python scripts/dns_diagnostics.py --domain animedia.space
"""

from __future__ import annotations

import argparse
import json
import random
import socket
import ssl
import struct
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "live-acceptance.json"
OUT = ROOT / "artifacts" / "evidence" / "products" / "dns-diagnostics.json"

#: Независимые публичные резолверы. Несколько намеренно: один резолвер с
#: устаревшим кэшем показал бы отсутствие записи, которой уже разошлась, или
#: наоборот — запись, которой больше нет.
RESOLVERS = {
    "cloudflare": "1.1.1.1",
    "google": "8.8.8.8",
    "quad9": "9.9.9.9",
    "yandex": "77.88.8.8",
}

TYPES = {"A": 1, "NS": 2, "CNAME": 5, "SOA": 6, "AAAA": 28}
TYPE_NAMES = {v: k for k, v in TYPES.items()}

#: Управляющий сервер фабрики. Не секрет — инфраструктурный идентификатор,
#: записанный в `knowledge/INFRASTRUCTURE_INVENTORY.yaml`.
CONTROL_HOST = "45.131.182.225"

TIMEOUT = 6


# --------------------------------------------------------------------------
# Проволочный формат DNS


def _encode_name(name: str) -> bytes:
    out = b""
    for label in name.rstrip(".").split("."):
        encoded = label.encode("idna") if any(ord(c) > 127 for c in label) else label.encode()
        out += bytes([len(encoded)]) + encoded
    return out + b"\0"


def _decode_name(data: bytes, offset: int) -> tuple[str, int]:
    """Имя из ответа. Сжатие указателями обязательно: без него разбор врёт."""
    labels: list[str] = []
    jumped = False
    end = offset
    while True:
        length = data[offset]
        if length & 0xC0 == 0xC0:
            pointer = struct.unpack("!H", data[offset:offset + 2])[0] & 0x3FFF
            if not jumped:
                end = offset + 2
            offset = pointer
            jumped = True
            continue
        offset += 1
        if length == 0:
            if not jumped:
                end = offset
            break
        labels.append(data[offset:offset + length].decode("utf-8", "replace"))
        offset += length
    return ".".join(labels), end


def query(name: str, rtype: str, resolver: str) -> dict:
    """Один запрос к одному резолверу. Возвращает записи и сроки их жизни."""
    ident = random.randint(0, 0xFFFF)
    header = struct.pack("!HHHHHH", ident, 0x0100, 1, 0, 0, 0)
    payload = header + _encode_name(name) + struct.pack("!HH", TYPES[rtype], 1)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(TIMEOUT)
    try:
        sock.sendto(payload, (resolver, 53))
        data, _ = sock.recvfrom(4096)
    except (socket.timeout, OSError) as error:
        return {"error": f"{type(error).__name__}: {error}"[:120]}
    finally:
        sock.close()

    if len(data) < 12:
        return {"error": "ответ короче заголовка"}
    _, flags, qd, an, ns, ar = struct.unpack("!HHHHHH", data[:12])
    rcode = flags & 0xF
    offset = 12
    for _ in range(qd):
        _, offset = _decode_name(data, offset)
        offset += 4

    records = []
    for _ in range(an + ns):
        try:
            _, offset = _decode_name(data, offset)
            rtype_num, _, ttl, rdlength = struct.unpack("!HHIH", data[offset:offset + 10])
            offset += 10
            rdata = data[offset:offset + rdlength]
            value = _rdata(data, offset, rtype_num, rdata)
            offset += rdlength
            records.append({"type": TYPE_NAMES.get(rtype_num, str(rtype_num)),
                            "ttl": ttl, "value": value})
        except (struct.error, IndexError):
            break

    return {"rcode": rcode, "rcode_name": _RCODES.get(rcode, str(rcode)),
            "records": records, "authority_only": an == 0 and ns > 0}


_RCODES = {0: "NOERROR", 1: "FORMERR", 2: "SERVFAIL", 3: "NXDOMAIN",
           4: "NOTIMP", 5: "REFUSED"}


def _rdata(data: bytes, offset: int, rtype: int, rdata: bytes):
    if rtype == 1 and len(rdata) == 4:
        return socket.inet_ntop(socket.AF_INET, rdata)
    if rtype == 28 and len(rdata) == 16:
        return socket.inet_ntop(socket.AF_INET6, rdata)
    if rtype in (2, 5):
        return _decode_name(data, offset)[0]
    if rtype == 6:
        primary, next_offset = _decode_name(data, offset)
        mail, _ = _decode_name(data, next_offset)
        return f"{primary} {mail}"
    return rdata.hex()


# --------------------------------------------------------------------------
# Регистрация и сертификат


def rdap(domain: str) -> dict:
    """Регистрация домена по RDAP. Публичные сведения, без учётных данных."""
    url = f"https://rdap.org/domain/{domain}"
    try:
        request = urllib.request.Request(
            url, headers={"User-Agent": "site-factory-templates/1.0 (read-only)",
                          "Accept": "application/rdap+json"})
        with urllib.request.urlopen(request, timeout=15) as response:
            data = json.loads(response.read(400_000).decode("utf-8", "replace"))
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return {"registered": False, "note": "RDAP: домен не найден в реестре"}
        return {"error": f"RDAP {error.code}"}
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
        return {"error": f"{type(error).__name__}: {error}"[:120]}

    events = {e.get("eventAction"): e.get("eventDate") for e in data.get("events", [])}
    registrar = ""
    for entity in data.get("entities", []):
        if "registrar" in (entity.get("roles") or []):
            for item in (entity.get("vcardArray") or [None, []])[1]:
                if item and item[0] == "fn":
                    registrar = item[3]
    return {
        "registered": True,
        "status": data.get("status", []),
        "registrar": registrar,
        "nameservers": sorted(ns.get("ldhName", "").lower()
                              for ns in data.get("nameservers", [])),
        "registered_at": events.get("registration"),
        "expires_at": events.get("expiration"),
        "updated_at": events.get("last changed") or events.get("last update of RDAP database"),
    }


def certificate(host: str) -> dict:
    """Сертификат и соответствие имени. Рукопожатие без передачи данных."""
    context = ssl.create_default_context()
    try:
        with socket.create_connection((host, 443), timeout=TIMEOUT) as raw:
            with context.wrap_socket(raw, server_hostname=host) as tls:
                cert = tls.getpeercert()
                names = [v for k, v in cert.get("subjectAltName", ()) if k == "DNS"]
                return {"served": True, "names": names, "matches_host": host in names,
                        "not_after": cert.get("notAfter"),
                        "issuer": dict(x[0] for x in cert.get("issuer", ())).get(
                            "organizationName", "")}
    except ssl.SSLCertVerificationError as error:
        return {"served": True, "verified": False,
                "note": f"сертификат не проходит проверку: {error.verify_message}"}
    except (socket.timeout, TimeoutError) as error:
        return {"served": False, "note": f"порт 443 не отвечает: {type(error).__name__}"}
    except OSError as error:
        return {"served": False, "note": f"{type(error).__name__}: {error}"[:120]}


def http_state(host: str) -> dict:
    """Отвечает ли хост по HTTP и HTTPS. Один запрос на схему, без повторов."""
    out = {}
    for scheme in ("https", "http"):
        try:
            request = urllib.request.Request(
                f"{scheme}://{host}/", method="HEAD",
                headers={"User-Agent": "site-factory-templates/1.0 (read-only)"})
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
                out[scheme] = {"status": response.status, "final": response.geturl()}
        except urllib.error.HTTPError as error:
            out[scheme] = {"status": error.code}
        except Exception as error:  # noqa: BLE001 — состояние, а не отказ инструмента
            out[scheme] = {"error": f"{type(error).__name__}: {error}"[:100]}
    return out


# --------------------------------------------------------------------------


def diagnose(domain: str) -> dict:
    """Полное состояние домена. Ни одной записи не меняется."""
    report: dict = {"domain": domain}
    report["registration"] = rdap(domain)

    зона: dict = {}
    for имя, адрес in RESOLVERS.items():
        зона[имя] = {rtype: query(domain, rtype, адрес)
                     for rtype in ("A", "AAAA", "CNAME", "NS", "SOA")}
    report["resolvers"] = зона

    # Согласие резолверов: расхождение означает, что запись ещё расходится.
    адреса: dict[str, list[str]] = {}
    for имя, ответы in зона.items():
        found = [r["value"] for r in (ответы["A"].get("records") or []) if r["type"] == "A"]
        адреса[имя] = sorted(found)
    все = {tuple(v) for v in адреса.values()}
    report["a_records_by_resolver"] = адреса
    report["resolvers_agree"] = len(все) == 1
    report["resolved"] = any(адреса.values())

    ttl = [r["ttl"] for ответы in зона.values()
           for r in (ответы["A"].get("records") or []) if r["type"] == "A"]
    report["a_ttl_seconds"] = sorted(set(ttl))

    делегирование = {имя: sorted(r["value"] for r in (ответы["NS"].get("records") or [])
                                 if r["type"] == "NS")
                     for имя, ответы in зона.items()}
    report["nameservers_by_resolver"] = делегирование

    if report["resolved"]:
        первый = next(v[0] for v in адреса.values() if v)
        report["points_to_control_host"] = первый == CONTROL_HOST
        report["control_host"] = CONTROL_HOST
        report["http"] = http_state(domain)
        report["certificate"] = certificate(domain)
        report["state"] = "RESOLVED"
    else:
        report["points_to_control_host"] = False
        # Отсутствие записи — ожидание, а не отказ. Домен может быть только что
        # делегирован, зона может быть пуста, запись может не разойтись.
        report["state"] = "PENDING_DNS"
        report["note"] = ("имя не разрешается ни одним из независимых резолверов; "
                          "это ожидание разрешения, а не отказ витрины")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", action="append", default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.domain:
        домены = args.domain
    else:
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
        домены = []
        for entry in config["products"].values():
            for url in [entry["base_url"]] + [a["url"] for a in entry.get("additional_urls", [])]:
                if url:
                    домены.append(url.split("://", 1)[1].strip("/"))

    отчёт = {d: diagnose(d) for d in домены}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(отчёт, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(отчёт, ensure_ascii=False, indent=2))
        return 0

    for домен, r in отчёт.items():
        reg = r["registration"]
        print(f"\n=== {домен} — {r['state']} ===")
        if reg.get("registered"):
            print(f"  регистрация: {reg.get('registrar') or '—'}, "
                  f"состояние {', '.join(reg.get('status') or []) or '—'}")
            print(f"  создан {reg.get('registered_at')}, истекает {reg.get('expires_at')}")
            print(f"  делегирование по реестру: {', '.join(reg.get('nameservers') or []) or '—'}")
        else:
            print(f"  регистрация: {reg.get('note') or reg.get('error')}")
        for имя, адреса in r["a_records_by_resolver"].items():
            ns = r["nameservers_by_resolver"].get(имя) or []
            print(f"  {имя:11} A: {', '.join(адреса) or '—':22} NS: {', '.join(ns) or '—'}")
        print(f"  резолверы согласны: {'да' if r['resolvers_agree'] else 'НЕТ'}"
              f" | TTL записи A: {r['a_ttl_seconds'] or '—'}")
        if r["resolved"]:
            print(f"  указывает на управляющий сервер: "
                  f"{'да' if r['points_to_control_host'] else 'нет'} ({r['control_host']})")
            for scheme, state in r["http"].items():
                print(f"  {scheme}: {state}")
            print(f"  сертификат: {r['certificate']}")
        else:
            print(f"  {r['note']}")
    print(f"\n{OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
