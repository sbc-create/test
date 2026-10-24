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
#: Реестр действующих домéнов этой копии. Нужен ВТОРЫМ источником, потому
#: что паспорт ячеек не знает о восьми живых витринах партии K2 (MOD-107),
#: и прогон `--all` по одному паспорту печатал «замечаний: 0», молча не
#: посмотрев на восемь работающих сайтов. Чистый вердикт, который
#: исключает живые витрины, хуже отсутствия вердикта.
РЕЕСТР = Path(__file__).resolve().parents[2] / "config/active-domains.json"


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


def _годный(домен: str) -> bool:
    return bool(домен) and not str(домен).endswith((".test", ".localhost"))


def из_паспорта() -> list[str]:
    if not ПАСПОРТ.is_file():
        return []
    ячейки = json.loads(ПАСПОРТ.read_text(encoding="utf-8")).get("cells") or []
    return [str(я["domain"]) for я in ячейки if _годный(я.get("domain"))]


def из_реестра() -> list[str]:
    """Действующие домены реестра, без ожидающих замены.

    Ожидающие замены не берутся намеренно: по заданию владельца продвижение и
    миграции по ним не запускаются, и их имена не разрешаются в DNS.
    """
    if not РЕЕСТР.is_file():
        return []
    д = json.loads(РЕЕСТР.read_text(encoding="utf-8"))
    ждут = {з.get("domain") for з in (д.get("awaiting_replacement") or [])}
    return [str(з["domain"]) for з in (д.get("domains") or [])
            if _годный(з.get("domain")) and з.get("domain") not in ждут
            and з.get("state") == "active"]


def домены() -> list[str]:
    """Объединение двух источников: паспорт ячеек И реестр домéнов.

    Порядок сохраняется: сперва паспорт, затем то, чего в нём нет.
    """
    итог = list(dict.fromkeys(из_паспорта()))
    for д in из_реестра():
        if д not in итог:
            итог.append(д)
    return итог


def расхождение_источников() -> dict[str, list[str]]:
    """Чего нет в каждом источнике. Печатается рядом с вердиктом."""
    п, р = set(из_паспорта()), set(из_реестра())
    return {"нет_в_паспорте": sorted(р - п), "нет_в_реестре": sorted(п - р)}


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
    # ЧИСЛО ОСМОТРЕННЫХ ПЕЧАТАЕТСЯ ВСЕГДА, И РАСХОЖДЕНИЕ ИСТОЧНИКОВ ТОЖЕ.
    # Прогон `--all` по одному паспорту ячеек печатал «замечаний: 0», не
    # посмотрев на восемь живых витрин партии K2: их в паспорте нет (MOD-107).
    # Чистый вердикт, молча исключающий работающие сайты, — это тот же
    # молчаливый успех, что класс 24 в docs/RECURRING_FAILURES.md.
    print(f"\nосмотрено домéнов: {len(цели)}"
          f" (измерено {len(строки)}, не измерено {len(не_измерено)})")
    if а.all:
        р = расхождение_источников()
        if р["нет_в_паспорте"]:
            print("  в паспорте ячеек НЕТ, взяты из реестра: "
                  + ", ".join(р["нет_в_паспорте"]))
        if р["нет_в_реестре"]:
            print("  в реестре домéнов НЕТ, взяты из паспорта: "
                  + ", ".join(р["нет_в_реестре"]))
        if not (р["нет_в_паспорте"] or р["нет_в_реестре"]):
            print("  источники совпадают")
    return 1 if замечания else 0


if __name__ == "__main__":
    sys.exit(main())
