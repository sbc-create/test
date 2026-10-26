"""Где теряется путь до адреса: трассировка без прав root (как tracepath).

UDP-датаграммы с растущим TTL; ответы ICMP «время жизни истекло» и
«порт недоступен» читаются из очереди ошибок сокета (IP_RECVERR), поэтому
ни raw-сокет, ни sudo не нужны. Плюс TCP-рукопожатие на тот же адрес.
Только чтение сети, никаких данных приложения не отправляется.

    python3 automation/local/net-path-probe.py 213.180.193.61 [ещё адреса…]
"""
from __future__ import annotations

import json
import select
import socket
import struct
import sys
import time

IP_RECVERR = 11
SO_EE_ORIGIN_ICMP = 2
ТИПЫ = {(11, 0): "ttl_exceeded", (3, 3): "port_unreachable", (3, 1): "host_unreachable",
        (3, 0): "net_unreachable", (3, 13): "admin_prohibited", (3, 10): "host_prohibited",
        (3, 9): "net_prohibited"}


def хоп(адрес: str, ttl: int, ждать: float = 2.0) -> dict:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.IPPROTO_IP, IP_RECVERR, 1)
    s.setsockopt(socket.IPPROTO_IP, socket.IP_TTL, ttl)
    t0 = time.time()
    try:
        s.sendto(b"probe", (адрес, 33434 + ttl))
        конец = t0 + ждать
        while time.time() < конец:
            r, _, x = select.select([s], [], [s], max(0.0, конец - time.time()))
            if not (r or x):
                break
            try:
                _, anc, _, _ = s.recvmsg(512, 512, socket.MSG_ERRQUEUE)
            except BlockingIOError:
                continue
            for уровень, тип, данные in anc:
                if уровень == socket.IPPROTO_IP and тип == IP_RECVERR and len(данные) >= 16:
                    errno_, origin, icmp_type, icmp_code = struct.unpack_from("IBBB", данные)
                    кто = socket.inet_ntoa(данные[20:24]) if len(данные) >= 24 else None
                    return {"ttl": ttl, "from": кто, "icmp": ТИПЫ.get((icmp_type, icmp_code),
                            f"type{icmp_type}/code{icmp_code}"), "ms": round((time.time() - t0) * 1000)}
        return {"ttl": ttl, "from": None, "icmp": None, "ms": None}
    finally:
        s.close()


def tcp(адрес: str, порт: int = 443, ждать: float = 6.0) -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(ждать)
    try:
        s.connect((адрес, порт))
        return "connected"
    except socket.timeout:
        return "timeout (нет SYN-ACK и нет RST/ICMP)"
    except OSError as exc:
        return f"{type(exc).__name__}: {exc.strerror or exc}"
    finally:
        s.close()


def путь(адрес: str, макс: int = 20) -> dict:
    хопы = []
    for ttl in range(1, макс + 1):
        х = хоп(адрес, ttl)
        хопы.append(х)
        if х["icmp"] and х["icmp"] != "ttl_exceeded":
            break
    последний = next((х for х in reversed(хопы) if х["from"]), None)
    return {"target": адрес, "tcp443": tcp(адрес), "hops": хопы,
            "last_responding_hop": последний,
            "reached": any(х["from"] == адрес for х in хопы)}


def main() -> int:
    итог = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "paths": [путь(a) for a in sys.argv[1:]]}
    print(json.dumps(итог, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
