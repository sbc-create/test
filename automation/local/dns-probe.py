#!/usr/bin/env python3
"""Диагностика DNS без внешних зависимостей: RCODE, секции, делегирование.

    python3 dns_probe.py <домен> [<домен> ...]

Зачем свой запрос, а не `socket.gethostbyname`. Тот отвечает `gaierror` и на
отсутствие домена, и на отсутствие записи нужного типа, и на сбой резолвера —
то есть три РАЗНЫЕ причины сливает в одну. Для решения «кто должен что
сделать» это непригодно: отсутствие A-записи правит владелец в панели
регистратора, ошибка делегирования — у регистратора, а сбой локального
резолвера вообще не про домен.

Различаются:

* RCODE 3 (NXDOMAIN) — имени нет в родительской зоне: домен не
  зарегистрирован либо делегирование отсутствует;
* RCODE 0 и ноль ответов — имя существует, записей ЭТОГО типа нет;
* RCODE 2 (SERVFAIL) — авторитетный сервер не ответил или ответил ошибкой:
  это ошибка делегирования/зоны, а не отсутствие записи;
* таймаут всех резолверов — сбой локального DNS, и о домене это не говорит
  НИЧЕГО.
"""
from __future__ import annotations

import random
import socket
import struct
import sys

РЕЗОЛВЕРЫ: list[str] = []
ТИПЫ = {"A": 1, "NS": 2, "SOA": 6, "CNAME": 5, "AAAA": 28}
ИМЕНА_ТИПОВ = {з: и for и, з in ТИПЫ.items()}
RCODE = {0: "NOERROR", 1: "FORMERR", 2: "SERVFAIL", 3: "NXDOMAIN",
         4: "NOTIMP", 5: "REFUSED"}


def резолверы() -> list[str]:
    if РЕЗОЛВЕРЫ:
        return РЕЗОЛВЕРЫ
    try:
        with open("/etc/resolv.conf", encoding="utf-8") as ф:
            for строка in ф:
                если = строка.split()
                if len(если) >= 2 and если[0] == "nameserver":
                    РЕЗОЛВЕРЫ.append(если[1])
    except OSError:
        pass
    return РЕЗОЛВЕРЫ


def _имя(домен: str) -> bytes:
    тело = b""
    for часть in домен.strip(".").split("."):
        тело += bytes([len(часть)]) + часть.encode("idna")
    return тело + b"\x00"


def _прочитать_имя(данные: bytes, смещение: int) -> tuple[str, int]:
    части: list[str] = []
    прыжков = 0
    текущее = смещение
    конец = None
    while True:
        if текущее >= len(данные):
            break
        длина = данные[текущее]
        if длина == 0:
            текущее += 1
            break
        if длина & 0xC0 == 0xC0:
            указатель = struct.unpack("!H", данные[текущее:текущее + 2])[0] & 0x3FFF
            if конец is None:
                конец = текущее + 2
            текущее = указатель
            прыжков += 1
            if прыжков > 20:
                break
            continue
        части.append(данные[текущее + 1:текущее + 1 + длина].decode("latin1"))
        текущее += 1 + длина
    return ".".join(части), (конец if конец is not None else текущее)


def запрос(домен: str, тип: str, сервер: str, таймаут: float = 5.0) -> dict:
    ид = random.randint(0, 0xFFFF)
    голова = struct.pack("!HHHHHH", ид, 0x0100, 1, 0, 0, 0)
    тело = голова + _имя(домен) + struct.pack("!HH", ТИПЫ[тип], 1)
    с = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    с.settimeout(таймаут)
    try:
        с.sendto(тело, (сервер, 53))
        ответ, _ = с.recvfrom(4096)
    except (socket.timeout, TimeoutError, OSError) as ош:
        return {"resolver": сервер, "type": тип, "error": type(ош).__name__}
    finally:
        с.close()

    (_, флаги, вопросов, ответов, авторитетных, доп) = struct.unpack(
        "!HHHHHH", ответ[:12])
    смещение = 12
    for _ in range(вопросов):
        _, смещение = _прочитать_имя(ответ, смещение)
        смещение += 4
    записи: list[dict] = []
    for раздел, сколько in (("answer", ответов), ("authority", авторитетных),
                            ("additional", доп)):
        for _ in range(сколько):
            имя, смещение = _прочитать_имя(ответ, смещение)
            if смещение + 10 > len(ответ):
                break
            т, кл, ttl, длина = struct.unpack("!HHIH", ответ[смещение:смещение + 10])
            смещение += 10
            данные = ответ[смещение:смещение + длина]
            смещение += длина
            значение = ""
            if т == 1 and длина == 4:
                значение = socket.inet_ntoa(данные)
            elif т in (2, 5):
                значение, _ = _прочитать_имя(ответ, смещение - длина)
            elif т == 6:
                первичный, сдвиг = _прочитать_имя(ответ, смещение - длина)
                значение = первичный
            elif т == 28 and длина == 16:
                значение = socket.inet_ntop(socket.AF_INET6, данные)
            else:
                значение = данные.hex()[:48]
            записи.append({"section": раздел, "name": имя,
                           "type": ИМЕНА_ТИПОВ.get(т, str(т)),
                           "ttl": ttl, "value": значение})
    return {"resolver": сервер, "type": тип,
            "rcode": RCODE.get(флаги & 0x0F, str(флаги & 0x0F)),
            "authoritative": bool(флаги & 0x0400),
            "answers": [з for з in записи if з["section"] == "answer"],
            "authority": [з for з in записи if з["section"] == "authority"],
            "additional": [з for з in записи if з["section"] == "additional"]}


def вывод(домен: str) -> None:
    print(f"=== {домен}")
    серверы = резолверы()
    if not серверы:
        print("   резолверов в /etc/resolv.conf нет: это СБОЙ ЛОКАЛЬНОГО DNS, "
              "и о домене он не говорит ничего")
        return
    for тип in ("NS", "SOA", "A", "AAAA", "CNAME"):
        ответы = [запрос(домен, тип, с) for с in серверы]
        живые = [о for о in ответы if "error" not in о]
        if not живые:
            причины = ", ".join(f"{о['resolver']}: {о['error']}" for о in ответы)
            print(f"   {тип}: ни один резолвер не ответил ({причины}) — "
                  "СБОЙ ЛОКАЛЬНОГО DNS")
            continue
        о = живые[0]
        строки = [f"{з['name']} {з['type']} {з['value']} (ttl {з['ttl']})"
                  for з in о["answers"]]
        автор = [f"{з['name']} {з['type']} {з['value']}" for з in о["authority"]]
        расхождение = {щ.get("rcode") for щ in живые}
        print(f"   {тип}: rcode={о['rcode']}"
              + (f" (резолверы расходятся: {sorted(расхождение)})"
                 if len(расхождение) > 1 else "")
              + f" | ответов {len(о['answers'])}"
              + (": " + "; ".join(строки) if строки else "")
              + (f" | authority: {'; '.join(автор)}" if автор and not строки else ""))


if __name__ == "__main__":
    for д in sys.argv[1:]:
        вывод(д)
