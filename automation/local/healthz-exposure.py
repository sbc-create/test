#!/usr/bin/env python3
"""Что публичный `/healthz` рассказывает о внутреннем устройстве витрины.

Повод. `/healthz` — сознательно ПУБЛИЧНЫЙ служебный путь: он нужен наблюдению,
и решения D150, D166 и D187 закрывают его только от ИНДЕКСАЦИИ, причём в двух
слоях. Но закрыть от индексации и ограничить содержимое — разные вещи, и
второе до сих пор не измерялось. Замер 12.10 на `animedia.icu` показал в
публичном ответе `runtime_path`, `runtime_sha256` и `pid`.

Инструмент НЕ выносит вердикт: публичность пути решена и не обсуждается, а
состав ответа может быть и сознательным. Он отвечает на один вопрос числом:
какие поля видны снаружи у каждой витрины и у скольких из них видно то, что
описывает устройство машины — путь в файловой системе, хеш файла рантайма,
номер процесса, имя учётной записи.

Секретов инструмент не печатает: он показывает ИМЕНА полей и, для путей,
только то, что путь присутствует. Значения путей и хешей в вывод не идут —
иначе отчёт сам стал бы способом их распространения.

Только чтение.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[1].parent
РЕЕСТР = КОРЕНЬ / "config" / "site-cells.json"
ИСПЫТАТЕЛЬНЫЕ = (".localhost", ".test", ".invalid", ".example")

#: Поля, которые описывают УСТРОЙСТВО машины, а не состояние службы.
#: Разделение именно такое: `ok`, `ready`, `build_id` отвечают на вопрос
#: «работает ли», а путь, хеш и номер процесса — на вопрос «как устроено».
ОПИСЫВАЮТ_УСТРОЙСТВО = ("runtime_path", "runtime_sha256", "pid",
                        "process_start_time", "account", "data_dir",
                        "app_dir", "unit", "port", "python")


def домены(путь: Path) -> list[str]:
    try:
        документ = json.loads(путь.read_text(encoding="utf-8"))
    except (OSError, ValueError) as сбой:
        print(f"реестр ячеек не прочитан ({путь}): {сбой}", file=sys.stderr)
        return []
    return [я["domain"] for я in документ.get("cells") or []
            if я.get("domain") and not я["domain"].endswith(ИСПЫТАТЕЛЬНЫЕ)]


def ответ(домен: str, таймаут: int) -> tuple[str, str]:
    итог = subprocess.run(
        ["curl", "-sS", "-w", "\n%{http_code}", "--max-time", str(таймаут),
         f"https://{домен}/healthz"],
        capture_output=True, text=True)
    вывод = итог.stdout or ""
    тело, _, код = вывод.rpartition("\n")
    if итог.returncode == 6:
        return "dns", ""
    return (код.strip() or "000"), тело


def поля(тело: str) -> tuple[list[str], bool]:
    """(имена полей верхнего уровня, разобрался ли JSON).

    Имена, а не значения: отчёт о раскрытии не должен сам раскрывать.
    """
    try:
        документ = json.loads(тело)
    except ValueError:
        # Не JSON — тогда хотя бы скажем, похож ли ответ на служебный.
        return ([], False)
    if not isinstance(документ, dict):
        return ([], False)
    return (sorted(документ), True)


def разбор(аргв=None):
    р = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--registry", type=Path, default=РЕЕСТР)
    р.add_argument("--domain", action="append", default=[])
    р.add_argument("--timeout", type=int, default=25)
    р.add_argument("--json", action="store_true")
    return р.parse_args(аргв)


def главное(аргв=None) -> int:
    опции = разбор(аргв)
    список = опции.domain or домены(опции.registry)
    if not список:
        return 2
    итоги = []
    for домен in список:
        код, тело = ответ(домен, опции.timeout)
        имена, разобрался = поля(тело)
        устройство = [и for и in имена if и in ОПИСЫВАЮТ_УСТРОЙСТВО]
        итоги.append({"домен": домен, "код": код, "json": разобрался,
                      "полей": len(имена), "про_устройство": устройство,
                      "имена": имена})

    if опции.json:
        print(json.dumps(итоги, ensure_ascii=False, indent=2))
        return 0

    print(f"{'домен':24} {'код':>5} {'полей':>6}  поля про устройство машины")
    открытых = 0
    for и in итоги:
        if и["про_устройство"]:
            открытых += 1
        print(f"{и['домен']:24} {и['код']:>5} {и['полей']:>6}  "
              + (", ".join(и["про_устройство"]) if и["про_устройство"]
                 else "—"))
    живых = [и for и in итоги if и["код"] == "200"]
    print(f"\nответили 200: {len(живых)} из {len(итоги)}; "
          f"показывают устройство машины: {открытых}")
    print("Вердикта инструмент не выносит: публичность /healthz решена "
          "(D150, D166, D187 закрывают его от ИНДЕКСАЦИИ, а не от доступа), и "
          "состав ответа может быть сознательным. Значения путей и хешей в "
          "вывод не идут — иначе отчёт сам стал бы способом их "
          "распространения.")
    return 0


if __name__ == "__main__":
    raise SystemExit(главное())
