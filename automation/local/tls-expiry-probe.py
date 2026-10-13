#!/usr/bin/env python3
"""Сколько осталось сертификату каждой витрины и покрывает ли он свой домен.

Зачем. Истёкший сертификат — отказ сайта целиком, и срок у него жёсткий: он не
зависит от нагрузки, бюджета CI и чьего-либо решения. Определение готовности
называет «TLS указывает не на тот сайт» блокирующим, но молчит про срок —
потому что срок не проверяют один раз, его проверяют периодически.

**Факт успешного запроса сертификат НЕ проверяет достаточно.** `curl` молчит,
пока цепочка верна, и ничего не говорит про остаток дней. Поэтому здесь
сертификат разбирается: `notAfter` и список имён `subjectAltName`.

Что считается замечанием:

* до истечения меньше `--дней` (по умолчанию 21 — две недели запаса плюс
  неделя на реакцию владельца);
* собственного имени домена в сертификате нет — он покрывает не этот сайт.

Инструмент только читает: одно TLS-соединение на домен, без запроса страницы.

    python3 automation/local/tls-expiry-probe.py --all
    python3 automation/local/tls-expiry-probe.py zonafilm.space --дней 30
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import socket
import ssl
import sys
from pathlib import Path

ПАСПОРТ = Path("/home/claude/wt-portable-site-cell-01/config/site-cells.json")


def сведения(домен: str, таймаут: int = 15) -> tuple[dt.datetime, list[str]] | str:
    """(до какого времени годен, имена) либо строка-причина, почему не измерено."""
    контекст = ssl.create_default_context()
    try:
        with socket.create_connection((домен, 443), timeout=таймаут) as гнездо, \
                контекст.wrap_socket(гнездо, server_hostname=домен) as оболочка:
            сертификат = оболочка.getpeercert()
    except socket.gaierror:
        return "имя не разрешается"
    except TimeoutError:
        return "таймаут соединения"
    except ssl.SSLError as ош:
        return f"TLS отказал: {type(ош).__name__}"
    except OSError as ош:
        return f"соединение не состоялось: {type(ош).__name__}"
    if not сертификат:
        return "сертификат не получен (возможно, проверка отключена)"
    try:
        до = dt.datetime.strptime(
            сертификат["notAfter"], "%b %d %H:%M:%S %Y %Z").replace(
            tzinfo=dt.timezone.utc)
    except (KeyError, ValueError) as ош:
        return f"notAfter не разобран: {type(ош).__name__}"
    имена = sorted({з for вид, з in сертификат.get("subjectAltName", ())
                    if вид == "DNS"})
    return до, имена


def домены() -> list[str]:
    if not ПАСПОРТ.is_file():
        return []
    ячейки = json.loads(ПАСПОРТ.read_text(encoding="utf-8")).get("cells") or []
    return [str(я["domain"]) for я in ячейки
            if я.get("domain")
            and not str(я["domain"]).endswith((".test", ".localhost"))]


def main() -> int:
    р = argparse.ArgumentParser()
    р.add_argument("домены", nargs="*")
    р.add_argument("--all", action="store_true")
    р.add_argument("--дней", type=int, default=21,
                   help="порог запаса в днях; меньше — замечание")
    а = р.parse_args()
    цели = а.домены or (домены() if а.all else [])
    if not цели:
        print("не названо ни одной витрины: домен аргументом или --all")
        return 2

    сейчас = dt.datetime.now(dt.timezone.utc)
    замечания: list[str] = []
    не_измерено: list[str] = []
    строки: list[tuple[int, str, int, bool]] = []
    for домен in цели:
        итог = сведения(домен)
        if isinstance(итог, str):
            не_измерено.append(f"{домен}: {итог}")
            continue
        до, имена = итог
        дней = (до - сейчас).days
        свой = домен in имена
        строки.append((дней, домен, len(имена), свой))
        if дней < а.дней:
            замечания.append(
                f"{домен}: осталось {дней} дней (порог {а.дней}) — "
                f"годен до {до.strftime('%d.%m.%Y %H:%M')}Z")
        if not свой:
            замечания.append(
                f"{домен}: собственного имени в сертификате НЕТ; покрыты "
                f"{имена[:4]} — сертификат не про этот сайт")

    for дней, домен, сколько, свой in sorted(строки):
        метка = "" if свой else "  ← своего имени нет"
        print(f"{домен:24} осталось {дней:4} дней, имён {сколько}{метка}")

    print(f"\nзамечаний: {len(замечания)}")
    for з in замечания:
        print(f"  • {з}")
    if не_измерено:
        print(f"\nне измерено: {len(не_измерено)}")
        for н in не_измерено:
            print(f"  • {н}")
        print("  «не измерено» — это не «просрочен» и не «в порядке».")
    return 1 if замечания else 0


if __name__ == "__main__":
    sys.exit(main())
