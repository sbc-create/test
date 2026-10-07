#!/usr/bin/env python3
"""Статус домена в РЕЕСТРЕ зоны: прямой сокет на whois, порт 43. Только чтение.

    python3 automation/local/registry-whois.py lordserials22.site …

Зачем прямой сокет. Статус удержания (`serverHold`) объявляет реестр, и только
он: ответ DNS его не показывает, а ответ рекурсивного резолвера вообще может
прийти из кеша. Утилита `whois` в окружении не установлена, поэтому запрос идёт
сокетом по той же схеме, что в `automation/host/release-chain.py`.

Печатаются ТОЛЬКО поля статуса и времени обновления: остальное в ответе реестра —
данные регистратора и контакты, и тащить их в отчёт незачем.
"""
from __future__ import annotations

import datetime
import re
import socket
import sys

#: Сервер реестра по зоне. Зона, которой здесь нет, — `BLOCKED_INPUT`, а не
#: догадка: спрашивать не тот сервер значит получить не тот ответ.
СЕРВЕРЫ = {
    "site": "whois.nic.site",
    "online": "whois.nic.online",
    "space": "whois.nic.space",
    "cc": "ccwhois.verisign-grs.com",
    "biz": "whois.nic.biz",
    "info": "whois.nic.info",
    "icu": "whois.nic.icu",
}

ПОЛЯ = ("Domain Status", "Updated Date", "Creation Date",
        "Registry Expiry Date", "Registrar:", "Name Server")


def спросить(домен: str, таймаут: float = 20.0) -> str:
    зона = домен.rsplit(".", 1)[-1].lower()
    сервер = СЕРВЕРЫ.get(зона)
    if not сервер:
        return f"зоны {зона} нет в перечне серверов реестра — не спрашиваю наугад"
    try:
        with socket.create_connection((сервер, 43), timeout=таймаут) as s:
            s.sendall((домен + "\r\n").encode("idna" if domain_ascii(домен) else "utf-8"))
            куски = []
            while True:
                кусок = s.recv(8192)
                if not кусок:
                    break
                куски.append(кусок)
        return b"".join(куски).decode("utf-8", "replace")
    except OSError as ош:
        return f"сокет не ответил: {type(ош).__name__}: {ош}"


def domain_ascii(домен: str) -> bool:
    return all(ord(с) < 128 for с in домен)


def главная(argv: list[str]) -> int:
    домены = argv[1:]
    if not домены:
        print(__doc__)
        return 2
    сейчас = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"запрошено {сейчас}")
    for домен in домены:
        ответ = спросить(домен)
        статусы = sorted(set(re.findall(r"(?mi)^\s*Domain Status:\s*(\S+)", ответ)))
        обновлён = (re.search(r"(?mi)^\s*Updated Date:\s*(\S+)", ответ) or [None, ""])[1]
        регистратор = (re.search(r"(?mi)^\s*Registrar:\s*(.+)$", ответ) or [None, ""])[1]
        истекает = (re.search(r"(?mi)^\s*Registry Expiry Date:\s*(\S+)", ответ)
                    or [None, ""])[1]
        if not статусы and "сокет не ответил" in ответ:
            print(f"{домен:24} {ответ}")
            continue
        print(f"{домен:24} {', '.join(статусы) or 'статуса в ответе нет'}")
        print(f"{'':24} обновлён {обновлён or '—'}, истекает {истекает or '—'}, "
              f"регистратор {регистратор.strip() or '—'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(главная(sys.argv))
