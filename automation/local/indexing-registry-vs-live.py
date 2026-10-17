#!/usr/bin/env python3
"""Совпадает ли ЗАПИСЬ о режиме индексации с тем, что отдаёт домен.

Зачем. В паспорте ячейки поле `indexing.desired_state` объявлено отражением
фактического режима («Запись отражает фактический режим и меняется вместе с
ним»). Если запись говорит CLOSED, а домен отдаёт `index, follow`, то неверно
одно из двух — и дороже всего, если следующая выкладка применит запись и
закроет открытый сайт.

Сравниваются три факта по каждому домену:

  запись      `indexing.desired_state` и наличие подтверждённого разрешения
              владельца (`open_authorization_ref`);
  заголовок   `X-Robots-Tag` публичного ответа;
  разметка    `<meta name="robots">`.

Домен без записи — это «не объявлено», а не «закрыто».

    python3 automation/local/indexing-registry-vs-live.py
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
ЯЧЕЙКИ = КОРЕНЬ / "config" / "site-cells.json"


def записи() -> list[dict]:
    j = json.loads(ЯЧЕЙКИ.read_text(encoding="utf-8"))
    список = j.get("cells") or []
    return list(список.values()) if isinstance(список, dict) else список


def живой(домен: str) -> dict:
    г = subprocess.run(["curl", "-sSI", "--max-time", "30",
                        f"https://{домен}/"], capture_output=True, text=True)
    заголовки = re.findall(r"(?mi)^x-robots-tag:\s*(.+)$", г.stdout or "")
    т = subprocess.run(["curl", "-sS", "--max-time", "45",
                        f"https://{домен}/"], capture_output=True, text=True)
    м = re.search(r'<meta[^>]+name="robots"[^>]+content="([^"]*)"',
                  т.stdout or "", re.I)
    код = re.search(r"HTTP/[\d.]+ (\d{3})", г.stdout or "")
    return {"код": код.group(1) if код else "—",
            "заголовки": [з.strip() for з in заголовки],
            "мета": м.group(1) if м else None}


def главная() -> int:
    ячейки = [з for з in записи()
              if з.get("domain") and not з["domain"].endswith(".localhost")
              and not з["domain"].endswith(".localhost.test")]
    домены = [з["domain"] for з in ячейки]
    with ThreadPoolExecutor(max_workers=6) as пул:
        живые = dict(zip(домены, пул.map(живой, домены)))

    расхождений = 0
    print(f"{'домен':22} {'запись':9} {'разрешение':11} {'заголовок':22} "
          f"{'мета':14} вывод")
    for з in sorted(ячейки, key=lambda x: x["domain"]):
        д = з["domain"]
        инд = з.get("indexing") or {}
        запись = инд.get("desired_state") or "—"
        разрешение = "есть" if инд.get("open_authorization_ref") else "нет"
        ж = живые[д]
        заголовок = ", ".join(ж["заголовки"]) or "—"
        мета = ж["мета"] or "—"
        открыт_живой = ("noindex" not in (мета or "").lower()
                        and не_закрыт(ж["заголовки"]) and мета != "—")
        закрыт_живой = ("noindex" in (мета or "").lower()
                        or any("noindex" in з_.lower() for з_ in ж["заголовки"]))
        if ж["код"] not in ("200", "301", "302"):
            вывод = f"НЕ ИЗМЕРЕНО: код {ж['код']}"
        elif запись == "—":
            вывод = ("режим не объявлен в паспорте"
                     if открыт_живой or закрыт_живой else "нет данных")
        elif запись == "CLOSED" and открыт_живой:
            вывод = "РАСХОЖДЕНИЕ: запись CLOSED, домен открыт"
            расхождений += 1
        elif запись == "OPEN" and закрыт_живой:
            вывод = "РАСХОЖДЕНИЕ: запись OPEN, домен закрыт"
            расхождений += 1
        else:
            вывод = "совпадает"
        print(f"{д:22} {запись:9} {разрешение:11} {заголовок[:22]:22} "
              f"{мета[:14]:14} {вывод}")
    print(f"\nрасхождений записи и живого режима: {расхождений}")
    return 1 if расхождений else 0


def не_закрыт(заголовки: list[str]) -> bool:
    return not any("noindex" in з.lower() for з in заголовки)


if __name__ == "__main__":
    sys.exit(главная())
